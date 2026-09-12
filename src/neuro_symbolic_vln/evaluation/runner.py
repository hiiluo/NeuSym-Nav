from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode
from neuro_symbolic_vln.contracts import PlanStatus
from neuro_symbolic_vln.evaluation.interventions import InterventionSpec
from neuro_symbolic_vln.evaluation.manifests import (
    SCHEMA_VERSION,
    EvaluationSidecar,
    PublicManifest,
    stable_hash,
)
from neuro_symbolic_vln.evaluation.metrics import (
    MetricSummary,
    aggregate_metrics,
)
from neuro_symbolic_vln.testing import run_b3_episode

_BELIEF_METHODS: dict[str, dict[str, bool]] = {
    "V0R0": {"use_validator": False, "use_recovery": False},
    "V1R0": {"use_validator": True, "use_recovery": False},
    "V0R1": {"use_validator": False, "use_recovery": True},
    "V1R1": {"use_validator": True, "use_recovery": True},
}
SUPPORTED_METHODS = frozenset({"B3"} | set(_BELIEF_METHODS))
_AVAILABLE_METHODS = frozenset({"B3"} | set(_BELIEF_METHODS))


class ManifestHashMismatchError(RuntimeError):
    """Raised when a manifest hash on disk drifts from the frozen index."""


class ConfigHashMismatchError(RuntimeError):
    """Raised when a run config drifts from the expected frozen hash."""


class MethodUnavailableError(RuntimeError):
    """Raised when a requested evaluation method is not yet wired."""


@dataclass(frozen=True)
class LoadedManifests:
    publics: tuple[PublicManifest, ...]
    sidecars: tuple[EvaluationSidecar, ...]
    manifest_hashes: dict[str, str]

    def sidecar_for(self, episode_id: str) -> EvaluationSidecar:
        for sidecar in self.sidecars:
            if sidecar.episode_id == episode_id:
                return sidecar
        raise KeyError(f"sidecar not found for episode {episode_id}")


@dataclass
class RunRow:
    """One (episode × crossing) row (plan §16.2 schema).

    ``status`` is either ``"ok"``, ``"method_unavailable"`` or a typed
    outcome string; only ``"ok"`` rows feed metric aggregation.
    """

    run_id: str
    method: str
    condition: str
    episode_id: str
    family: str
    split: str
    seed: int
    manifest_hash: str
    config_hash: str
    status: str
    success: bool
    optimal_distance: int
    executed_distance: int
    optimal_actions: int
    attempted_actions: int
    invalid_actions: int
    plan_status: str
    intervention: bool
    recoverable: bool
    terminal_outcome: str | None
    replan_count: int
    runtime_ms: float
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "method": self.method,
            "condition": self.condition,
            "episode_id": self.episode_id,
            "family": self.family,
            "split": self.split,
            "seed": self.seed,
            "manifest_hash": self.manifest_hash,
            "config_hash": self.config_hash,
            "status": self.status,
            "success": self.success,
            "optimal_distance": self.optimal_distance,
            "executed_distance": self.executed_distance,
            "optimal_actions": self.optimal_actions,
            "attempted_actions": self.attempted_actions,
            "invalid_actions": self.invalid_actions,
            "plan_status": self.plan_status,
            "intervention": self.intervention,
            "recoverable": self.recoverable,
            "terminal_outcome": self.terminal_outcome,
            "replan_count": self.replan_count,
            "runtime_ms": self.runtime_ms,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RunReport:
    run_id: str
    method: str
    config_hash: str
    schema_version: str
    n_rows: int
    n_executed: int
    n_skipped: int
    summary: MetricSummary | None
    rows_path: Path
    summary_path: Path


def load_manifests(manifests_dir: str | Path) -> LoadedManifests:
    root = Path(manifests_dir)
    hashes_path = root / "manifest_hashes.json"
    if not hashes_path.exists():
        raise FileNotFoundError(
            f"missing frozen manifest index: {hashes_path}"
        )
    manifest_hashes = json.loads(hashes_path.read_text())

    publics: list[PublicManifest] = []
    sidecars: list[EvaluationSidecar] = []
    for public_path in sorted(root.glob("*.jsonl")):
        if public_path.name.endswith(".sidecar.jsonl"):
            continue
        sidecar_path = public_path.with_name(
            public_path.name.replace(".jsonl", ".sidecar.jsonl")
        )
        if not sidecar_path.exists():
            raise FileNotFoundError(f"missing sidecar for {public_path.name}")
        for line in public_path.read_text().splitlines():
            payload = json.loads(line)
            manifest = _manifest_from_dict(payload)
            expected = manifest_hashes.get(manifest.episode_id)
            actual = manifest.manifest_hash()
            if expected is None or expected != actual:
                raise ManifestHashMismatchError(
                    f"hash drift for {manifest.episode_id}: "
                    f"expected {expected}, got {actual}"
                )
            publics.append(manifest)
        for line in sidecar_path.read_text().splitlines():
            sidecars.append(_sidecar_from_dict(json.loads(line)))
    return LoadedManifests(
        publics=tuple(publics),
        sidecars=tuple(sidecars),
        manifest_hashes=manifest_hashes,
    )


def _manifest_from_dict(payload: dict[str, Any]) -> PublicManifest:
    return PublicManifest(
        schema_version=payload["schema_version"],
        episode_id=payload["episode_id"],
        family=payload["family"],
        split=payload["split"],
        generator_version=payload["generator_version"],
        seed=int(payload["seed"]),
        layout_hash=payload["layout_hash"],
        instruction=payload["instruction"],
        task_spec=payload["task_spec"],
        condition=payload.get("condition"),
        public_action_budget=int(payload["public_action_budget"]),
        config_hash=payload["config_hash"],
    )


def _sidecar_from_dict(payload: dict[str, Any]) -> EvaluationSidecar:
    return EvaluationSidecar(
        schema_version=payload["schema_version"],
        episode_id=payload["episode_id"],
        solvable=bool(payload["solvable"]),
        optimal_grid_distance=payload.get("optimal_grid_distance"),
        optimal_primitive_actions=payload.get("optimal_primitive_actions"),
        oracle_target_entity_id=payload["oracle_target_entity_id"],
        observable_predicate_universe_hash=payload.get(
            "observable_predicate_universe_hash"
        ),
        uncorrupted_evidence_hash=payload.get("uncorrupted_evidence_hash"),
        intervention=payload.get("intervention"),
    )


def _select_publics(
    manifests: LoadedManifests, splits: list[str], families: list[str] | None
) -> Iterator[PublicManifest]:
    split_set = set(splits)
    family_set = set(families) if families else None
    for manifest in manifests.publics:
        if manifest.split not in split_set:
            continue
        if family_set is not None and manifest.family not in family_set:
            continue
        yield manifest


def _run_b3_row(
    *,
    run_id: str,
    method: str,
    condition: str,
    manifest: PublicManifest,
    sidecar: EvaluationSidecar,
    config_hash: str,
) -> RunRow:
    started = time.perf_counter()
    result = run_b3_episode(seed=manifest.seed, family=manifest.family)
    runtime_ms = (time.perf_counter() - started) * 1000.0

    attempted = result.step_count
    invalid = sum(
        1
        for trace in result.traces
        if trace.step_result is not None and not trace.step_result.action_succeeded
    )
    intervention_dict = sidecar.intervention or {}
    return RunRow(
        run_id=run_id,
        method=method,
        condition=condition,
        episode_id=manifest.episode_id,
        family=manifest.family,
        split=manifest.split,
        seed=manifest.seed,
        manifest_hash=manifest.manifest_hash(),
        config_hash=config_hash,
        status="ok",
        success=result.task_success,
        optimal_distance=sidecar.optimal_grid_distance or 0,
        executed_distance=attempted,
        optimal_actions=sidecar.optimal_primitive_actions or 0,
        attempted_actions=attempted,
        invalid_actions=invalid,
        plan_status=result.plan.status.value
        if isinstance(result.plan.status, PlanStatus)
        else str(result.plan.status),
        intervention=bool(intervention_dict),
        recoverable=bool(intervention_dict.get("recoverable", False)),
        terminal_outcome=(
            result.terminal_outcome.value
            if result.terminal_outcome is not None
            else None
        ),
        replan_count=result.replan_count,
        runtime_ms=runtime_ms,
    )


def _run_belief_row(
    *,
    run_id: str,
    method: str,
    condition: str,
    manifest: PublicManifest,
    sidecar: EvaluationSidecar,
    config_hash: str,
) -> RunRow:
    flags = _BELIEF_METHODS[method]
    intervention = InterventionSpec.from_sidecar(sidecar.intervention)
    started = time.perf_counter()
    result = run_v1r1_episode(
        seed=manifest.seed,
        family=manifest.family,
        method=method,
        intervention=intervention,
        use_validator=flags["use_validator"],
        use_recovery=flags["use_recovery"],
    )
    runtime_ms = (time.perf_counter() - started) * 1000.0

    attempted = result.step_count
    invalid = sum(
        1
        for trace in result.traces
        if trace.step_result is not None
        and not trace.step_result.action_succeeded
    )
    intervention_dict = sidecar.intervention or {}
    return RunRow(
        run_id=run_id,
        method=method,
        condition=condition,
        episode_id=manifest.episode_id,
        family=manifest.family,
        split=manifest.split,
        seed=manifest.seed,
        manifest_hash=manifest.manifest_hash(),
        config_hash=config_hash,
        status="ok",
        success=result.task_success,
        optimal_distance=sidecar.optimal_grid_distance or 0,
        executed_distance=attempted,
        optimal_actions=sidecar.optimal_primitive_actions or 0,
        attempted_actions=attempted,
        invalid_actions=invalid,
        plan_status=result.plan.status.value
        if isinstance(result.plan.status, PlanStatus)
        else str(result.plan.status),
        intervention=bool(intervention_dict),
        recoverable=bool(intervention_dict.get("recoverable", False)),
        terminal_outcome=(
            result.terminal_outcome.value
            if result.terminal_outcome is not None
            else None
        ),
        replan_count=result.replan_count,
        runtime_ms=runtime_ms,
        notes={"belief_state_hash": result.belief_state_hash}
        if result.belief_state_hash
        else {},
    )


def _skip_row(
    *,
    run_id: str,
    method: str,
    condition: str,
    manifest: PublicManifest,
    sidecar: EvaluationSidecar,
    config_hash: str,
    status: str,
    note: str,
) -> RunRow:
    intervention_dict = sidecar.intervention or {}
    return RunRow(
        run_id=run_id,
        method=method,
        condition=condition,
        episode_id=manifest.episode_id,
        family=manifest.family,
        split=manifest.split,
        seed=manifest.seed,
        manifest_hash=manifest.manifest_hash(),
        config_hash=config_hash,
        status=status,
        success=False,
        optimal_distance=sidecar.optimal_grid_distance or 0,
        executed_distance=0,
        optimal_actions=sidecar.optimal_primitive_actions or 0,
        attempted_actions=0,
        invalid_actions=0,
        plan_status="skipped",
        intervention=bool(intervention_dict),
        recoverable=bool(intervention_dict.get("recoverable", False)),
        terminal_outcome=None,
        replan_count=0,
        runtime_ms=0.0,
        notes={"reason": note},
    )


def _run_row(
    *,
    run_id: str,
    method: str,
    condition: str,
    manifest: PublicManifest,
    sidecar: EvaluationSidecar,
    config_hash: str,
) -> RunRow:
    if method == "B3":
        return _run_b3_row(
            run_id=run_id,
            method=method,
            condition=condition,
            manifest=manifest,
            sidecar=sidecar,
            config_hash=config_hash,
        )
    if method in _BELIEF_METHODS:
        return _run_belief_row(
            run_id=run_id,
            method=method,
            condition=condition,
            manifest=manifest,
            sidecar=sidecar,
            config_hash=config_hash,
        )
    return _skip_row(
        run_id=run_id,
        method=method,
        condition=condition,
        manifest=manifest,
        sidecar=sidecar,
        config_hash=config_hash,
        status="method_unavailable",
        note=f"method {method} not wired in runner",
    )


def _crossings_from_config(
    config: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    """Normalize ``method`` / ``matrix`` fields into (method, condition) pairs.

    - ``method: B3`` (legacy single-crossing form): ``[("B3", "clean")]``.
    - ``matrix: [{method: V0R0, condition: N1-a}, ...]``: one entry per
      dict; ``condition`` defaults to ``"clean"``.
    """
    if "matrix" in config:
        crossings = tuple(
            (str(entry["method"]), str(entry.get("condition", "clean")))
            for entry in config["matrix"]
        )
        if not crossings:
            raise ValueError("matrix must contain at least one crossing")
        return crossings
    if "method" in config:
        return ((str(config["method"]), str(config.get("condition", "clean"))),)
    raise ValueError("config must declare either 'method' or 'matrix'")


def run_config(
    config: dict[str, Any], *, manifests: LoadedManifests | None = None
) -> RunReport:
    """Execute a frozen run config end-to-end.

    Verifies the config_hash against the ``config_hash_expected`` field if
    present (freeze check), then iterates episodes × crossings and writes
    one row per crossing.
    """
    crossings = _crossings_from_config(config)
    for method, _condition in crossings:
        if method not in SUPPORTED_METHODS and method not in _AVAILABLE_METHODS:
            # Unknown methods still produce rows via _skip_row so the row
            # count stays honest.
            continue

    run_id = str(config["run_id"])
    manifests_dir = config["manifests_dir"]
    output_dir = Path(config["output_dir"])
    splits = list(config.get("splits", []))
    families = config.get("families")

    config_hash = stable_hash(_hashable_config(config))
    expected_config_hash = config.get("config_hash_expected")
    if expected_config_hash and expected_config_hash != config_hash:
        raise ConfigHashMismatchError(
            f"config drift for {run_id}: expected {expected_config_hash}, "
            f"got {config_hash}"
        )

    if manifests is None:
        manifests = load_manifests(manifests_dir)

    rows: list[RunRow] = []
    n_executed = 0
    n_skipped = 0
    selected_manifests = list(_select_publics(manifests, splits, families))
    total_rows = len(selected_manifests) * len(crossings)

    for manifest_idx, manifest in enumerate(selected_manifests, start=1):
        sidecar = manifests.sidecar_for(manifest.episode_id)

        for crossing_idx, (method, condition) in enumerate(crossings, start=1):
            completed = (manifest_idx - 1) * len(crossings) + crossing_idx

            print(
                f"[{completed}/{total_rows}] "
                f"{manifest.episode_id} | {method} | {condition}",
                flush=True,
            )

            row = _run_row(
                run_id=run_id,
                method=method,
                condition=condition,
                manifest=manifest,
                sidecar=sidecar,
                config_hash=config_hash,
            )
            rows.append(row)
            if row.status == "ok":
                n_executed += 1
            else:
                n_skipped += 1

    if not rows:
        raise ValueError(
            f"run {run_id} produced zero rows — check splits/families"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / f"{run_id}.rows.jsonl"
    summary_path = output_dir / f"{run_id}.summary.json"
    rows_path.write_text(
        "\n".join(
            json.dumps(row.to_dict(), sort_keys=True, separators=(",", ":"))
            for row in rows
        )
        + "\n"
    )

    executed_dicts = [
        row.to_dict() for row in rows if row.status == "ok"
    ]
    summary = aggregate_metrics(executed_dicts) if executed_dicts else None
    method_label = crossings[0][0] if len(crossings) == 1 else "matrix"
    summary_payload = {
        "run_id": run_id,
        "method": method_label,
        "crossings": [
            {"method": m, "condition": c} for m, c in crossings
        ],
        "config_hash": config_hash,
        "schema_version": SCHEMA_VERSION,
        "n_rows": len(rows),
        "n_executed": n_executed,
        "n_skipped": n_skipped,
        "metrics": summary.to_dict() if summary is not None else None,
    }
    summary_path.write_text(
        json.dumps(summary_payload, sort_keys=True, indent=2) + "\n"
    )

    return RunReport(
        run_id=run_id,
        method=method_label,
        config_hash=config_hash,
        schema_version=SCHEMA_VERSION,
        n_rows=len(rows),
        n_executed=n_executed,
        n_skipped=n_skipped,
        summary=summary,
        rows_path=rows_path,
        summary_path=summary_path,
    )


def _hashable_config(config: dict[str, Any]) -> dict[str, Any]:
    """Config fields that participate in the freeze hash.

    ``config_hash_expected`` and free-form ``notes`` are excluded so the
    hash reflects behaviour, not documentation drift.
    """
    excluded = {"config_hash_expected", "notes"}
    return {k: v for k, v in config.items() if k not in excluded}


def validate_results(
    runs_dir: str | Path,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Compare frozen ``runs_dir`` against ``expected_rows.yaml`` schema.

    ``expected`` is a mapping ``{run_id: {"row_count": int, "method": str,
    "config_hash_expected": str | None}}``. Returns a diagnostic dict with
    ``ok`` and per-run mismatches; a non-empty ``mismatches`` list means
    the frozen artifacts drifted.
    """
    root = Path(runs_dir)
    mismatches: list[dict[str, Any]] = []
    total_expected = 0
    total_actual = 0
    for run_id, spec in expected.items():
        summary_path = root / f"{run_id}.summary.json"
        rows_path = root / f"{run_id}.rows.jsonl"
        expected_rows = int(spec["row_count"])
        total_expected += expected_rows
        if not summary_path.exists() or not rows_path.exists():
            mismatches.append(
                {"run_id": run_id, "reason": "artifacts_missing"}
            )
            continue
        summary = json.loads(summary_path.read_text())
        actual_rows = int(summary["n_rows"])
        total_actual += actual_rows
        if actual_rows != expected_rows:
            mismatches.append(
                {
                    "run_id": run_id,
                    "reason": "row_count",
                    "expected": expected_rows,
                    "actual": actual_rows,
                }
            )
        if summary["method"] != spec["method"]:
            mismatches.append(
                {
                    "run_id": run_id,
                    "reason": "method",
                    "expected": spec["method"],
                    "actual": summary["method"],
                }
            )
        expected_config_hash = spec.get("config_hash_expected")
        if (
            expected_config_hash
            and summary["config_hash"] != expected_config_hash
        ):
            mismatches.append(
                {
                    "run_id": run_id,
                    "reason": "config_hash",
                    "expected": expected_config_hash,
                    "actual": summary["config_hash"],
                }
            )
    return {
        "ok": not mismatches,
        "total_expected_rows": total_expected,
        "total_actual_rows": total_actual,
        "mismatches": mismatches,
    }


__all__ = [
    "ConfigHashMismatchError",
    "LoadedManifests",
    "ManifestHashMismatchError",
    "MethodUnavailableError",
    "RunReport",
    "RunRow",
    "SUPPORTED_METHODS",
    "load_manifests",
    "run_config",
    "validate_results",
]
