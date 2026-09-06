from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

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
