from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

import yaml

from neuro_symbolic_vln.contracts import PlanStatus
from neuro_symbolic_vln.evaluation.manifests import (
    generate_manifests,
    write_manifests,
)
from neuro_symbolic_vln.evaluation.runner import (
    ConfigHashMismatchError,
    ManifestHashMismatchError,
    run_config,
    validate_results,
)
from neuro_symbolic_vln.testing import run_b3_episode


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="ns-vln")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--method", default=None)
    evaluate.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory in config",
    )

    generate = subparsers.add_parser("generate-manifests")
    generate.add_argument("--config", required=True)

    # B-09 commands
    audit = subparsers.add_parser("audit")
    audit.add_argument("--runs", required=True, help="Path to runs directory")
    audit.add_argument(
        "--src",
        default="src/neuro_symbolic_vln",
        help="Path to source directory for import/constructor scan",
    )
    audit.add_argument(
        "--output",
        default=None,
        help="Path to write audit report (default: prints to stdout)",
    )
    audit.add_argument(
        "--skip-import-scan",
        action="store_true",
        help="Skip subprocess import-graph scan",
    )

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--runs", required=True, help="Path to runs directory")
    summarize.add_argument(
        "--output",
        required=True,
        help="Output directory for reports",
    )
    summarize.add_argument(
        "--config",
        default=None,
        help="Analysis config YAML (default: configs/analysis.yaml)",
    )

    validate_traces = subparsers.add_parser("validate-traces")
    validate_traces.add_argument(
        "--runs",
        required=True,
        help="Path to runs/trace directory",
    )
    validate_traces.add_argument(
        "--episodes",
        default=None,
        help="Path to manifest JSONL for expected episode ID validation",
    )

    validate_results = subparsers.add_parser("validate-results")
    validate_results.add_argument(
        "--runs",
        required=True,
        help="Path to runs directory",
    )
    validate_results.add_argument(
        "--expected-config",
        required=True,
        help="Path to expected results config YAML",
    )

    validate_report = subparsers.add_parser("validate-report")
    validate_report.add_argument(
        "--report",
        required=True,
        help="Path to report file or directory",
    )

    validate_habitat_decision = subparsers.add_parser("validate-habitat-decision")
    validate_habitat_decision.add_argument(
        "--report",
        required=True,
        help="Path to habitat decision YAML file",
    )

    audit_portability = subparsers.add_parser("audit-portability")
    audit_portability.add_argument(
        "--src",
        default="src/neuro_symbolic_vln",
        help="Path to source directory for portability audit",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print("0.1.0")
        return 0
    if args.command == "evaluate":
        return _run_evaluate(args)
    if args.command == "generate-manifests":
        return _run_generate_manifests(args)
    if args.command == "audit":
        return _run_audit(args)
    if args.command == "summarize":
        return _run_summarize(args)
    if args.command == "validate-traces":
        return _run_validate_traces(args)
    if args.command == "validate-results":
        return _run_validate_results(args)
    if args.command == "validate-report":
        return _run_validate_report(args)
    if args.command == "validate-habitat-decision":
        return _run_validate_habitat_decision(args)
    if args.command == "audit-portability":
        return _run_audit_portability(args)
    parser.print_help()
    return 0


def _run_generate_manifests(args: Namespace) -> int:
    config_path = Path(args.config)
    with config_path.open() as handle:
        config = yaml.safe_load(handle)

    result = generate_manifests(config)
    written = write_manifests(config["output_dir"], result)
    print(
        f"Generated {len(result.public_manifests)} public manifests "
        f"and {len(result.sidecars)} sidecars"
    )
    for name, path in written.items():
        print(f"  {name}: {path}")
    return 0


def _run_evaluate(args: Namespace) -> int:
    config_path = Path(args.config)
    with config_path.open() as handle:
        config = yaml.safe_load(handle)

    # Frozen runner path: config declares run_id/manifests_dir/output_dir.
    if "run_id" in config and "manifests_dir" in config:
        if args.method:
            config = {**config, "method": args.method}
        if getattr(args, "output_dir", None):
            config = {**config, "output_dir": args.output_dir}
        try:
            report = run_config(config)
        except (ManifestHashMismatchError, ConfigHashMismatchError) as exc:
            print(f"freeze violation: {exc}", file=sys.stderr)
            return 3
        print(
            f"{report.run_id} [{report.method}]: "
            f"{report.n_executed} executed / {report.n_skipped} skipped "
            f"/ {report.n_rows} rows"
        )
        if report.summary is not None:
            print(f"  metrics: {json.dumps(report.summary.to_dict())}")
        print(f"  rows: {report.rows_path}")
        print(f"  summary: {report.summary_path}")
        if report.n_executed == 0 and report.n_skipped > 0:
            return 4  # Loud: method unavailable, artifacts still written.
        return 0

    # Legacy smoke path (configs/smoke.yaml).
    method = args.method or config.get("method")

    if method in ("V0R0", "V1R0", "V0R1", "V1R1"):
        from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode

        use_validator = method in ("V1R0", "V1R1")
        use_recovery = method in ("V0R1", "V1R1")
        results: list[Any] = []
        for entry in config["episodes"]:
            for seed in entry["seeds"]:
                results.append(
                    run_v1r1_episode(
                        seed=seed,
                        family=entry["family"],
                        method=method,
                        use_validator=use_validator,
                        use_recovery=use_recovery,
                    )
                )
        successes = sum(1 for result in results if result.task_success)
        print(f"{method} smoke: {len(results)} episodes, {successes} task successes")
        return 0 if successes == len(results) else 1

    if method != "B3":
        print(f"unsupported method: {method}", file=sys.stderr)
        return 2

    results = []
    for entry in config["episodes"]:
        for seed in entry["seeds"]:
            results.append(run_b3_episode(seed=seed, family=entry["family"]))

    plans_found = sum(1 for result in results if result.plan.status is PlanStatus.FOUND)
    successes = sum(1 for result in results if result.task_success)
    print(
        f"B3 smoke: {len(results)} episodes, "
        f"{plans_found} plans found, {successes} task successes"
    )

    if plans_found == len(results) and successes == len(results):
        return 0
    return 1


def _run_validate_results(args: Namespace) -> int:
    expected_path = Path(args.expected_config)
    with expected_path.open() as handle:
        expected_doc = yaml.safe_load(handle)
    expected = expected_doc.get("expected_rows", expected_doc)
    report = validate_results(args.runs, expected)
    print(
        f"validate-results: {report['total_actual_rows']} actual / "
        f"{report['total_expected_rows']} expected rows"
    )
    for mismatch in report["mismatches"]:
        print(f"  MISMATCH {mismatch}", file=sys.stderr)
    return 0 if report["ok"] else 5


# ---------------------------------------------------------------------------
# B-09: audit
# ---------------------------------------------------------------------------


def _run_audit(args: Namespace) -> int:
    from neuro_symbolic_vln.evaluation.audit import (
        run_leakage_audit,
        write_audit_report,
    )

    runs_dir = Path(args.runs)
    src_dir = Path(args.src)

    report = run_leakage_audit(
        src_dir=src_dir,
        trace_dir=runs_dir,
        skip_import_scan=args.skip_import_scan,
    )

    print(report.summary())

    if args.output:
        output_path = Path(args.output)
        write_audit_report(report, output_path)
        print(f"\nReport written to: {output_path}")

    return 0 if report.ok else 1


# ---------------------------------------------------------------------------
# B-09: summarize
# ---------------------------------------------------------------------------


def _run_summarize(args: Namespace) -> int:
    from neuro_symbolic_vln.evaluation.statistics import (
        generate_rq1_summary,
        generate_rq2_summary,
        write_summary_reports,
    )

    runs_dir = Path(args.runs)
    output_dir = Path(args.output)

    # Load analysis config
    config: dict[str, Any] = {}
    config_path = Path(args.config) if args.config else Path("configs/analysis.yaml")
    if config_path.exists():
        with config_path.open() as handle:
            config = yaml.safe_load(handle) or {}

    seed = config.get("analysis_seed", 42)
    bootstrap_cfg = config.get("bootstrap", {})
    n_resamples = bootstrap_cfg.get("n_resamples", 10_000)
    ci_level = bootstrap_cfg.get("ci_level", 0.95)

    rq1_cfg = config.get("rq1", {})
    rq2_cfg = config.get("rq2", {})

    print(f"Generating RQ1 summaries from {runs_dir}...")
    rq1_tables = generate_rq1_summary(
        runs_dir,
        treatment_method=rq1_cfg.get("treatment_method", "V1R0"),
        control_method=rq1_cfg.get("control_method", "V0R0"),
        metrics=tuple(rq1_cfg.get("metrics", ["task_success"])),
        n_resamples=n_resamples,
        ci_level=ci_level,
        seed=seed,
    )

    print(f"Generating RQ2 summaries from {runs_dir}...")
    rq2_tables = generate_rq2_summary(
        runs_dir,
        treatment_method=rq2_cfg.get("treatment_method", "V1R1"),
        control_method=rq2_cfg.get("control_method", "V1R0"),
        metrics=tuple(rq2_cfg.get("metrics", ["task_success"])),
        n_resamples=n_resamples,
        ci_level=ci_level,
        seed=seed,
    )

    written = write_summary_reports(output_dir, rq1_tables, rq2_tables)
    print(f"\nSummary reports written to {output_dir}:")
    for name, path in sorted(written.items()):
        print(f"  {name}: {path}")

    return 0


# ---------------------------------------------------------------------------
# B-09: validate-traces
# ---------------------------------------------------------------------------


def _run_validate_traces(args: Namespace) -> int:
    from neuro_symbolic_vln.trace import (
        TraceSchemaError,
        deserialize_record,
        scan_record_for_leakage,
    )

    runs_dir = Path(args.runs)
    expected_ids: set[str] | None = None
    if args.episodes:
        episodes_path = Path(args.episodes)
        expected_ids = set()
        for line in episodes_path.read_text().strip().splitlines():
            if line.strip():
                data = json.loads(line)
                expected_ids.add(data["episode_id"])

    violations: list[str] = []
    records_by_episode: dict[str, list[Any]] = {}
    record_count = 0

    for jsonl_file in sorted(runs_dir.rglob("*.jsonl")):
        if jsonl_file.name.endswith(".rows.jsonl"):
            continue
        for line_no, line in enumerate(jsonl_file.read_text().splitlines(), 1):
            if not line.strip():
                continue
            record_count += 1
            try:
                record = deserialize_record(line)
            except TraceSchemaError as exc:
                violations.append(f"{jsonl_file}:{line_no}: schema error: {exc}")
                continue

            # Scan the serialized payload, rather than only ``record``: the
            # schema intentionally permits forward-compatible extra fields,
            # so constructing TraceRecord would otherwise discard a leaked
            # private field before it can be reported.
            for leak in scan_record_for_leakage(line):
                violations.append(f"{jsonl_file}:{line_no}: {leak}")
            records_by_episode.setdefault(record.episode_id, []).append(record)

    for episode_id, records in sorted(records_by_episode.items()):
        if records[-1].episode_outcome is None:
            violations.append(
                f"{episode_id}: final trace record has no typed episode_outcome"
            )
    if expected_ids is not None:
        for episode_id in sorted(expected_ids - records_by_episode.keys()):
            violations.append(f"{episode_id}: no trace records found")

    print(f"validate-traces: {record_count} records scanned")
    if not violations:
        print("Trace validation: PASS — schema-valid, typed, no leakage")
        return 0

    for violation in violations:
        print(f"  VIOLATION: {violation}", file=sys.stderr)
    return 6


# ---------------------------------------------------------------------------
# Task B-J04: validate-report, validate-habitat-decision, audit-portability
# ---------------------------------------------------------------------------


def _run_validate_report(args: Namespace) -> int:
    from neuro_symbolic_vln.evaluation.report_validator import validate_report

    result = validate_report(args.report)
    if result["ok"]:
        print(f"validate-report: PASS — {result['report_file']}")
        print(f"  sections found: {', '.join(result['sections'])}")
        return 0
    print("validate-report: FAIL", file=sys.stderr)
    for err in result["mismatches"]:
        print(f"  VIOLATION: {err}", file=sys.stderr)
    return 7


def _run_validate_habitat_decision(args: Namespace) -> int:
    from neuro_symbolic_vln.evaluation.report_validator import validate_habitat_decision

    result = validate_habitat_decision(args.report)
    if result["ok"]:
        print(
            f"validate-habitat-decision: PASS — decision '{result['decision']}' "
            "is valid and backed by evidence"
        )
        return 0
    print("validate-habitat-decision: FAIL", file=sys.stderr)
    for err in result["mismatches"]:
        print(f"  VIOLATION: {err}", file=sys.stderr)
    return 8


def _run_audit_portability(args: Namespace) -> int:
    from neuro_symbolic_vln.evaluation.report_validator import audit_portability

    result = audit_portability(args.src)
    print(f"audit-portability: {result['files_scanned']} files scanned")
    if result["ok"]:
        print("audit-portability: PASS — core modules decoupled from MiniGrid")
        return 0
    print("audit-portability: FAIL — violations found", file=sys.stderr)
    for err in result["violations"]:
        print(f"  VIOLATION: {err}", file=sys.stderr)
    return 9
