from __future__ import annotations

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
from neuro_symbolic_vln.testing import run_b3_episode


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="ns-vln")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--method", required=True)

    generate = subparsers.add_parser("generate-manifests")
    generate.add_argument("--config", required=True)

    # B-09 commands
    audit = subparsers.add_parser("audit")
    audit.add_argument("--runs", required=True, help="Path to runs directory")
    audit.add_argument(
        "--src", default="src/neuro_symbolic_vln",
        help="Path to source directory for import/constructor scan",
    )
    audit.add_argument(
        "--output", default=None,
        help="Path to write audit report (default: prints to stdout)",
    )
    audit.add_argument(
        "--skip-import-scan", action="store_true",
        help="Skip subprocess import-graph scan",
    )

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--runs", required=True, help="Path to runs directory")
    summarize.add_argument(
        "--output", required=True, help="Output directory for reports",
    )
    summarize.add_argument(
        "--config", default=None,
        help="Analysis config YAML (default: configs/analysis.yaml)",
    )

    validate_traces = subparsers.add_parser("validate-traces")
    validate_traces.add_argument(
        "--runs", required=True, help="Path to runs/trace directory",
    )
    validate_traces.add_argument(
        "--episodes", default=None,
        help="Path to manifest JSONL for expected episode ID validation",
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
    if args.method != "B3":
        print(f"unsupported method: {args.method}", file=sys.stderr)
        return 2

    config_path = Path(args.config)
    with config_path.open() as handle:
        config = yaml.safe_load(handle)

    results = []
    for entry in config["episodes"]:
        for seed in entry["seeds"]:
            results.append(
                run_b3_episode(seed=seed, family=entry["family"])
            )

    plans_found = sum(
        1 for result in results if result.plan.status is PlanStatus.FOUND
    )
    successes = sum(1 for result in results if result.task_success)
    print(
        f"B3 smoke: {len(results)} episodes, "
        f"{plans_found} plans found, {successes} task successes"
    )

    if plans_found == len(results) and successes == len(results):
        return 0
    return 1


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
    import json

    from neuro_symbolic_vln.evaluation.statistics import validate_trace_completeness

    runs_dir = Path(args.runs)

    expected_ids: set[str] | None = None
    if args.episodes:
        episodes_path = Path(args.episodes)
        expected_ids = set()
        for line in episodes_path.read_text().strip().splitlines():
            if line.strip():
                data = json.loads(line)
                expected_ids.add(data["episode_id"])

    report = validate_trace_completeness(runs_dir, expected_ids)

    if report.ok:
        print("Trace validation: PASS — all traces complete with typed outcomes")
        return 0

    print("Trace validation: FAIL")
    if report.incomplete_traces:
        print(f"\n  Incomplete traces ({len(report.incomplete_traces)}):")
        for issue in report.incomplete_traces:
            print(f"    - {issue}")
    if report.untyped_outcomes:
        print(f"\n  Untyped outcomes ({len(report.untyped_outcomes)}):")
        for issue in report.untyped_outcomes:
            print(f"    - {issue}")

    return 1
