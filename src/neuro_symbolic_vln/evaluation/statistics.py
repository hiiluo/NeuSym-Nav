from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# 1. Paired delta
# ---------------------------------------------------------------------------


def paired_delta(
    treatment: dict[str, float],
    control: dict[str, float],
) -> float:
    """Mean of per-episode deltas between treatment and control.

    Raises ValueError when episode ID sets differ or are empty.
    """
    if not treatment and not control:
        raise ValueError("cannot compute paired delta on empty inputs")
    if treatment.keys() != control.keys():
        raise ValueError("paired episode IDs must match")
    deltas = [treatment[key] - control[key] for key in sorted(treatment)]
    return sum(deltas) / len(deltas)


# ---------------------------------------------------------------------------
# 2. Stratified bootstrap CI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapResult:
    """Result of a single bootstrap CI computation."""

    point_estimate: float
    ci_lower: float
    ci_upper: float
    n_episodes: int
    n_resamples: int
    ci_level: float


def bootstrap_ci(
    treatment: dict[str, float],
    control: dict[str, float],
    *,
    n_resamples: int = 10_000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    """Paired-bootstrap confidence interval for mean(treatment - control).

    Uses a fixed analysis seed for full reproducibility.
    Raises ValueError on mismatched or empty ID sets.
    """
    if not treatment and not control:
        raise ValueError("cannot bootstrap on empty inputs")
    if treatment.keys() != control.keys():
        raise ValueError("paired episode IDs must match")

    keys = sorted(treatment)
    deltas = np.array([treatment[k] - control[k] for k in keys])
    point = float(deltas.mean())
    n = len(deltas)

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_resamples)
    for i in range(n_resamples):
        indices = rng.integers(0, n, size=n)
        boot_means[i] = deltas[indices].mean()

    alpha = 1.0 - ci_level
    ci_lower = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    return BootstrapResult(
        point_estimate=point,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        n_episodes=n,
        n_resamples=n_resamples,
        ci_level=ci_level,
    )


@dataclass(frozen=True)
class StratumResult:
    """Bootstrap result for one family × condition stratum."""

    family: str
    condition: str
    metric: str
    bootstrap: BootstrapResult


def stratified_summary(
    treatment_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    *,
    metric_key: str = "task_success",
    family_key: str = "family",
    condition_key: str = "condition",
    episode_key: str = "episode_id",
    n_resamples: int = 10_000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> list[StratumResult]:
    """Compute paired bootstrap CIs per (family, condition) stratum.

    Each row dict must contain episode_id, family, condition, and the
    metric column. Treatment and control rows are paired by episode_id
    within each stratum.
    """
    def _group(
        rows: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, float]]:
        groups: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for row in rows:
            key = (row[family_key], row[condition_key])
            groups[key][row[episode_key]] = float(row[metric_key])
        return groups

    t_groups = _group(treatment_rows)
    c_groups = _group(control_rows)

    all_strata = sorted(set(t_groups) | set(c_groups))
    results: list[StratumResult] = []

    for stratum in all_strata:
        family, condition = stratum
        t_map = t_groups.get(stratum, {})
        c_map = c_groups.get(stratum, {})
        if not t_map and not c_map:
            continue

        # Derive a deterministic per-stratum seed so strata are independent
        stratum_hash = int(
            hashlib.sha256(
                f"{family}:{condition}".encode()
            ).hexdigest()[:8],
            16,
        )
        stratum_seed = seed + stratum_hash

        ci = bootstrap_ci(
            t_map,
            c_map,
            n_resamples=n_resamples,
            ci_level=ci_level,
            seed=stratum_seed,
        )
        results.append(
            StratumResult(
                family=family,
                condition=condition,
                metric=metric_key,
                bootstrap=ci,
            )
        )

    return results


# ---------------------------------------------------------------------------
# 3. Run pair / hash / trace validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    """Aggregated result from run-level validation checks."""

    missing_pairs: list[str] = field(default_factory=list)
    duplicate_pairs: list[str] = field(default_factory=list)
    hash_mismatches: list[str] = field(default_factory=list)
    incomplete_traces: list[str] = field(default_factory=list)
    untyped_outcomes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any([
            self.missing_pairs,
            self.duplicate_pairs,
            self.hash_mismatches,
            self.incomplete_traces,
            self.untyped_outcomes,
        ])


def validate_run_pairs(
    treatment_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    *,
    episode_key: str = "episode_id",
    family_key: str = "family",
    condition_key: str = "condition",
) -> ValidationReport:
    """Verify every episode has exactly one row in both treatment and control.

    Rejects missing pairs (episode in one arm but not the other) and
    duplicate pairs (same episode appears twice in the same arm).
    """
    report = ValidationReport()

    def _check_duplicates(
        rows: list[dict[str, Any]], label: str,
    ) -> dict[tuple[str, str, str], str]:
        seen: dict[tuple[str, str, str], str] = {}
        for row in rows:
            key = (row[episode_key], row[family_key], row[condition_key])
            if key in seen:
                report.duplicate_pairs.append(
                    f"{label}: duplicate {row[episode_key]} "
                    f"in {row[family_key]}/{row[condition_key]}"
                )
            seen[key] = row[episode_key]
        return seen

    t_seen = _check_duplicates(treatment_rows, "treatment")
    c_seen = _check_duplicates(control_rows, "control")

    t_keys = set(t_seen)
    c_keys = set(c_seen)

    for key in sorted(t_keys - c_keys):
        report.missing_pairs.append(
            f"treatment only: {key[0]} ({key[1]}/{key[2]})"
        )
    for key in sorted(c_keys - t_keys):
        report.missing_pairs.append(
            f"control only: {key[0]} ({key[1]}/{key[2]})"
        )

    return report


def validate_run_hashes(
    rows: list[dict[str, Any]],
    *,
    expected_config_hash: str | None = None,
    expected_manifest_hashes: dict[str, str] | None = None,
    episode_key: str = "episode_id",
    config_hash_key: str = "config_hash",
    manifest_hash_key: str = "manifest_hash",
) -> ValidationReport:
    """Verify config and manifest hashes are consistent across all rows.

    If expected values are given, rows must match exactly. Otherwise rows
    must at least be self-consistent (all same config hash).
    """
    report = ValidationReport()

    config_hashes: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        ep = row[episode_key]
        config_hashes[ep].add(row.get(config_hash_key, ""))
        if expected_manifest_hashes and manifest_hash_key in row:
            expected = expected_manifest_hashes.get(ep)
            actual = row[manifest_hash_key]
            if expected is not None and actual != expected:
                report.hash_mismatches.append(
                    f"{ep}: manifest hash mismatch "
                    f"(expected={expected}, actual={actual})"
                )

    # Check config hash consistency
    all_config = set()
    for hashes in config_hashes.values():
        all_config |= hashes
    if expected_config_hash is not None:
        for h in all_config:
            if h and h != expected_config_hash:
                report.hash_mismatches.append(
                    f"config hash mismatch "
                    f"(expected={expected_config_hash}, found={h})"
                )
    elif len(all_config - {""}) > 1:
        report.hash_mismatches.append(
            f"inconsistent config hashes across runs: "
            f"{sorted(all_config - {''})}"
        )

    return report


def validate_trace_completeness(
    trace_dir: Path,
    expected_episode_ids: set[str] | None = None,
) -> ValidationReport:
    """Validate JSONL trace files for completeness and typed outcomes.

    Checks:
    - Every expected episode has at least one trace record.
    - Every episode's final record has a non-null episode_outcome.
    - No missing required fields per the trace schema.
    """
    report = ValidationReport()

    from neuro_symbolic_vln.trace import (
        REQUIRED_TRACE_FIELDS,
        TraceSchemaError,
        deserialize_record,
    )

    episode_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for trace_file in sorted(trace_dir.glob("*.jsonl")):
        for line_num, line in enumerate(
            trace_file.read_text().strip().splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                report.incomplete_traces.append(
                    f"{trace_file.name}:{line_num}: malformed JSON"
                )
                continue

            missing = REQUIRED_TRACE_FIELDS - data.keys()
            if missing:
                report.incomplete_traces.append(
                    f"{trace_file.name}:{line_num}: "
                    f"missing fields {sorted(missing)}"
                )
                continue

            try:
                deserialize_record(data)
            except TraceSchemaError as exc:
                report.incomplete_traces.append(
                    f"{trace_file.name}:{line_num}: schema error: {exc}"
                )
                continue

            episode_records[data["episode_id"]].append(data)

    # Check typed terminal outcomes
    for ep_id, records in sorted(episode_records.items()):
        final = records[-1]
        if final.get("episode_outcome") is None:
            report.untyped_outcomes.append(
                f"{ep_id}: final trace record has no typed episode_outcome"
            )

    # Check expected episodes are present
    if expected_episode_ids is not None:
        found = set(episode_records)
        for ep in sorted(expected_episode_ids - found):
            report.incomplete_traces.append(
                f"{ep}: no trace records found"
            )

    return report


# ---------------------------------------------------------------------------
# 4. RQ summary generators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RQSummaryTable:
    """Complete RQ summary with per-stratum bootstrap results."""

    rq_label: str
    treatment_method: str
    control_method: str
    metrics: tuple[str, ...]
    strata: tuple[StratumResult, ...]
    aggregate: BootstrapResult | None


def _load_rows(path: Path) -> list[dict[str, Any]]:
    """Load JSONL rows from a file."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text().strip().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def generate_rq1_summary(
    runs_dir: Path,
    *,
    treatment_method: str = "V1R0",
    control_method: str = "V0R0",
    metrics: tuple[str, ...] = ("task_success", "plan_validity", "efficiency"),
    n_resamples: int = 10_000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> list[RQSummaryTable]:
    """Generate RQ1 summaries: V1R0 vs V0R0 per N1 condition × family.

    Expects runs_dir to contain JSONL files with columns:
    episode_id, family, condition, method, task_success, plan_validity,
    efficiency, config_hash, manifest_hash.
    """
    all_rows = []
    for path in sorted(runs_dir.glob("*.jsonl")):
        all_rows.extend(_load_rows(path))

    treatment_rows = [r for r in all_rows if r.get("method") == treatment_method]
    control_rows = [r for r in all_rows if r.get("method") == control_method]

    tables: list[RQSummaryTable] = []
    for metric in metrics:
        strata = stratified_summary(
            treatment_rows,
            control_rows,
            metric_key=metric,
            n_resamples=n_resamples,
            ci_level=ci_level,
            seed=seed,
        )

        # Aggregate across all strata
        t_all = {r["episode_id"]: float(r[metric]) for r in treatment_rows}
        c_all = {r["episode_id"]: float(r[metric]) for r in control_rows}
        aggregate = None
        if t_all and c_all and t_all.keys() == c_all.keys():
            aggregate = bootstrap_ci(
                t_all, c_all,
                n_resamples=n_resamples,
                ci_level=ci_level,
                seed=seed,
            )

        tables.append(RQSummaryTable(
            rq_label="RQ1",
            treatment_method=treatment_method,
            control_method=control_method,
            metrics=(metric,),
            strata=tuple(strata),
            aggregate=aggregate,
        ))

    return tables


def generate_rq2_summary(
    runs_dir: Path,
    *,
    treatment_method: str = "V1R1",
    control_method: str = "V1R0",
    metrics: tuple[str, ...] = ("task_success", "recovery_rate", "efficiency"),
    n_resamples: int = 10_000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> list[RQSummaryTable]:
    """Generate RQ2 summaries: V1R1 vs V1R0 (replanning effect).

    Same structure as RQ1 but measures whether bounded replanning
    improves outcomes over validation-only.
    """
    all_rows = []
    for path in sorted(runs_dir.glob("*.jsonl")):
        all_rows.extend(_load_rows(path))

    treatment_rows = [r for r in all_rows if r.get("method") == treatment_method]
    control_rows = [r for r in all_rows if r.get("method") == control_method]

    tables: list[RQSummaryTable] = []
    for metric in metrics:
        strata = stratified_summary(
            treatment_rows,
            control_rows,
            metric_key=metric,
            n_resamples=n_resamples,
            ci_level=ci_level,
            seed=seed,
        )

        t_all = {r["episode_id"]: float(r[metric]) for r in treatment_rows}
        c_all = {r["episode_id"]: float(r[metric]) for r in control_rows}
        aggregate = None
        if t_all and c_all and t_all.keys() == c_all.keys():
            aggregate = bootstrap_ci(
                t_all, c_all,
                n_resamples=n_resamples,
                ci_level=ci_level,
                seed=seed,
            )

        tables.append(RQSummaryTable(
            rq_label="RQ2",
            treatment_method=treatment_method,
            control_method=control_method,
            metrics=(metric,),
            strata=tuple(strata),
            aggregate=aggregate,
        ))

    return tables


# ---------------------------------------------------------------------------
# 5. Summary table serializers
# ---------------------------------------------------------------------------


def format_summary_markdown(tables: list[RQSummaryTable]) -> str:
    """Render RQ summary tables as a GitHub-flavored markdown string."""
    lines: list[str] = []

    for table in tables:
        metric = table.metrics[0] if table.metrics else "metric"
        lines.append(
            f"## {table.rq_label}: {table.treatment_method} vs "
            f"{table.control_method} — {metric}"
        )
        lines.append("")
        lines.append(
            "| Family | Condition | N | Δ (point) | "
            "95% CI Lower | 95% CI Upper |"
        )
        lines.append(
            "|--------|-----------|---|-----------|"
            "--------------|--------------|"
        )

        for s in table.strata:
            b = s.bootstrap
            lines.append(
                f"| {s.family} | {s.condition} | {b.n_episodes} | "
                f"{b.point_estimate:+.4f} | {b.ci_lower:+.4f} | "
                f"{b.ci_upper:+.4f} |"
            )

        if table.aggregate:
            a = table.aggregate
            lines.append(
                f"| **ALL** | **ALL** | {a.n_episodes} | "
                f"{a.point_estimate:+.4f} | {a.ci_lower:+.4f} | "
                f"{a.ci_upper:+.4f} |"
            )

        lines.append("")

    return "\n".join(lines)


def format_summary_csv(tables: list[RQSummaryTable]) -> str:
    """Render RQ summary tables as CSV for machine consumption."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "rq", "treatment", "control", "metric",
        "family", "condition", "n_episodes",
        "point_estimate", "ci_lower", "ci_upper",
        "n_resamples", "ci_level",
    ])

    for table in tables:
        metric = table.metrics[0] if table.metrics else ""
        for s in table.strata:
            b = s.bootstrap
            writer.writerow([
                table.rq_label, table.treatment_method,
                table.control_method, metric,
                s.family, s.condition, b.n_episodes,
                f"{b.point_estimate:.6f}",
                f"{b.ci_lower:.6f}",
                f"{b.ci_upper:.6f}",
                b.n_resamples, b.ci_level,
            ])
        if table.aggregate:
            a = table.aggregate
            writer.writerow([
                table.rq_label, table.treatment_method,
                table.control_method, metric,
                "ALL", "ALL", a.n_episodes,
                f"{a.point_estimate:.6f}",
                f"{a.ci_lower:.6f}",
                f"{a.ci_upper:.6f}",
                a.n_resamples, a.ci_level,
            ])

    return output.getvalue()


def write_summary_reports(
    output_dir: Path,
    rq1_tables: list[RQSummaryTable],
    rq2_tables: list[RQSummaryTable],
) -> dict[str, Path]:
    """Write markdown and CSV summary files to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    all_tables = rq1_tables + rq2_tables

    md_path = output_dir / "rq_summary.md"
    md_path.write_text(format_summary_markdown(all_tables))
    written["rq_summary.md"] = md_path

    csv_path = output_dir / "rq_summary.csv"
    csv_path.write_text(format_summary_csv(all_tables))
    written["rq_summary.csv"] = csv_path

    # Per-RQ files
    if rq1_tables:
        p = output_dir / "rq1_summary.md"
        p.write_text(format_summary_markdown(rq1_tables))
        written["rq1_summary.md"] = p

    if rq2_tables:
        p = output_dir / "rq2_summary.md"
        p.write_text(format_summary_markdown(rq2_tables))
        written["rq2_summary.md"] = p

    return written
