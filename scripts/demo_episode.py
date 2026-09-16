#!/usr/bin/env python3
"""Interactive MiniGrid2D demonstration script.

Usage:
    uv run python scripts/demo_episode.py --family key_door_goal --seed 0
    uv run python scripts/demo_episode.py --family goto_type_color --seed 42
    uv run python scripts/demo_episode.py --method V1R1 --verbose
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode
from neuro_symbolic_vln.contracts import EpisodeSpec


def render_ascii_grid(env: Any) -> str:
    """Render a MiniGrid environment to an ASCII string."""
    dir_symbols = [">", "v", "<", "^"]
    agent_dir = env.unwrapped.agent_dir
    agent_pos = env.unwrapped.agent_pos
    lines = []
    for y in range(env.unwrapped.height):
        row = []
        for x in range(env.unwrapped.width):
            cell = env.unwrapped.grid.get(x, y)
            if (x, y) == agent_pos:
                row.append(f"A{dir_symbols[agent_dir]}")
            elif cell is None:
                row.append(" . ")
            else:
                obj_type = cell.type[:3]
                row.append(f"{obj_type:3}")
        lines.append(" ".join(row))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run and visualize a MiniGrid2D episode"
    )
    parser.add_argument(
        "--family",
        choices=["key_door_goal", "goto_type_color"],
        default="key_door_goal",
        help="Task family to run",
    )
    parser.add_argument(
        "--method",
        choices=["V1R1", "V1R0", "V0R1", "V0R0"],
        default="V1R1",
        help="Agent method variant (default: V1R1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for environment generation (default: 0)",
    )
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(
        f" MiniGrid2D Demo: {args.family} | Method: {args.method} | Seed: {args.seed}"
    )
    print(f"{'='*55}\n")

    from neuro_symbolic_vln.agent_v1r1 import _make_env_and_verifier

    env, verifier, instruction = _make_env_and_verifier(args.family, args.seed)
    env.reset(seed=args.seed)

    print(f"Task Instruction: \"{instruction}\"")
    print("\nInitial MiniGrid Layout:")
    print("-" * 30)
    print(render_ascii_grid(env))
    print("-" * 30)
    print(
        "Legend: wal=Wall | A>=Agent | key=Key | doo=Door | goa=Goal | bal=Ball\n"
    )

    episode_spec = EpisodeSpec(
        episode_id=f"demo-{args.family}-seed-{args.seed}",
        family=args.family,
        instruction=instruction,
        public_action_budget=32,
        manifest_hash="demo-manifest",
    )

    use_validator = args.method in ("V1R0", "V1R1")
    use_recovery = args.method in ("V0R1", "V1R1")

    result = run_v1r1_episode(
        seed=args.seed,
        family=args.family,
        method=args.method,
        use_validator=use_validator,
        use_recovery=use_recovery,
        episode=episode_spec,
        env=env,
        verifier=verifier,
    )

    print("Execution Trace:")
    print("-" * 55)
    for t in result.traces:
        primitive = t.primitive if t.primitive else "symbolic"
        success_str = (
            "SUCCESS" if (t.step_result and t.step_result.action_succeeded) else "DONE"
        )
        act_name = t.action.name
        print(
            f"  Step {t.step:2d} | Primitive: {primitive:<10} | "
            f"Action: {act_name:<18} | [{success_str}]"
        )
    print("-" * 55)

    print("\nFinal MiniGrid Layout:")
    print("-" * 30)
    print(render_ascii_grid(env))
    print("-" * 30)

    outcome = (
        result.terminal_outcome.value
        if result.terminal_outcome
        else "unknown"
    )
    status_str = "✅ SUCCESS" if result.task_success else "❌ FAILED"

    print("\nResult Summary:")
    print(f"  - Episode ID:        {result.episode_id}")
    print(f"  - Plan Status:       {result.plan.status.value}")
    print(f"  - Steps Taken:       {result.step_count}")
    print(f"  - Replans Required:  {result.replan_count}")
    print(f"  - Terminal Outcome:  {outcome}")
    print(f"  - Task Success:      {status_str}\n")

    return 0 if result.task_success else 1


if __name__ == "__main__":
    sys.exit(main())
