from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

_FOUND_PLAN_STATUS = "found"


def grid_spl(
    success: bool, optimal_distance: int, executed_distance: int
) -> float:
    """Success-weighted path length in grid cells (plan §16.1)."""
    if not success:
        return 0.0
    if optimal_distance < 0 or executed_distance < 0:
        raise ValueError("distances must be non-negative")
    if optimal_distance == 0:
        if executed_distance != 0:
            raise ValueError(
                "optimal_distance=0 requires executed_distance=0 "
                "(episode already at target)"
            )
        return 1.0
    return optimal_distance / max(optimal_distance, executed_distance)


def sope(
    success: bool, optimal_actions: int, attempted_actions: int
) -> float:
    """Success-weighted primitive actions (plan §16.1)."""
    if not success:
        return 0.0
    if optimal_actions < 0 or attempted_actions < 0:
        raise ValueError("action counts must be non-negative")
    if optimal_actions == 0:
        if attempted_actions != 0:
            raise ValueError(
                "optimal_actions=0 requires attempted_actions=0"
            )
        return 1.0
    return optimal_actions / max(optimal_actions, attempted_actions)


def sr(successes: Sequence[bool]) -> float:
    """Success rate over an episode batch."""
    if not successes:
        raise ValueError("successes must be non-empty")
    return sum(1 for s in successes if s) / len(successes)


def invalid_action_rate(attempted_actions: int, invalid_actions: int) -> float:
    """Fraction of primitives the environment rejected (plan §16.1)."""
    if invalid_actions < 0 or attempted_actions < 0:
        raise ValueError("counts must be non-negative")
    if attempted_actions == 0:
        if invalid_actions != 0:
            raise ValueError(
                "attempted_actions=0 cannot have invalid_actions>0"
            )
        return 0.0
    if invalid_actions > attempted_actions:
        raise ValueError("invalid_actions cannot exceed attempted_actions")
    return invalid_actions / attempted_actions


def recovery_denominator(rows: Iterable[dict[str, Any]]) -> int:
    """Denominator for recovery success rate (plan §16.1: only episodes
    with a recoverable intervention count against R1/V1R1)."""
    count = 0
    for row in rows:
        if row.get("intervention") and row.get("recoverable"):
            count += 1
    return count


def plan_validity(plan_statuses: Sequence[str]) -> float:
    """Fraction of episodes whose initial plan status is FOUND."""
    if not plan_statuses:
        raise ValueError("plan_statuses must be non-empty")
    found = sum(1 for status in plan_statuses if status == _FOUND_PLAN_STATUS)
    return found / len(plan_statuses)


@dataclass(frozen=True)
class MetricSummary:
    """Aggregate view of a single run batch (matches the row schema written
    by the frozen runner, plan §16.2)."""

    n_episodes: int
    sr: float
    mean_grid_spl: float
    mean_sope: float
    invalid_action_rate: float
    plan_validity: float
    recovery_denominator: int
    recovery_success: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_episodes": self.n_episodes,
            "sr": self.sr,
            "mean_grid_spl": self.mean_grid_spl,
            "mean_sope": self.mean_sope,
            "invalid_action_rate": self.invalid_action_rate,
            "plan_validity": self.plan_validity,
            "recovery_denominator": self.recovery_denominator,
            "recovery_success": self.recovery_success,
        }


def aggregate_metrics(rows: Sequence[dict[str, Any]]) -> MetricSummary:
    """Reduce per-episode rows to a summary. Rows must carry:
    success, optimal_distance, executed_distance, optimal_actions,
    attempted_actions, invalid_actions, plan_status, intervention,
    recoverable."""
    if not rows:
        raise ValueError("rows must be non-empty")

    successes = [bool(row["success"]) for row in rows]
    grid_spls = [
        grid_spl(
            success=bool(row["success"]),
            optimal_distance=int(row["optimal_distance"]),
            executed_distance=int(row["executed_distance"]),
        )
        for row in rows
    ]
    sopes = [
        sope(
            success=bool(row["success"]),
            optimal_actions=int(row["optimal_actions"]),
            attempted_actions=int(row["attempted_actions"]),
        )
        for row in rows
    ]
    total_attempted = sum(int(row["attempted_actions"]) for row in rows)
    total_invalid = sum(int(row["invalid_actions"]) for row in rows)
    plan_statuses = [str(row["plan_status"]) for row in rows]
    recovery_success = sum(
        1
        for row in rows
        if row.get("intervention")
        and row.get("recoverable")
        and bool(row["success"])
    )
    return MetricSummary(
        n_episodes=len(rows),
        sr=sr(successes),
        mean_grid_spl=sum(grid_spls) / len(grid_spls),
        mean_sope=sum(sopes) / len(sopes),
        invalid_action_rate=invalid_action_rate(
            attempted_actions=total_attempted,
            invalid_actions=total_invalid,
        ),
        plan_validity=plan_validity(plan_statuses),
        recovery_denominator=recovery_denominator(rows),
        recovery_success=recovery_success,
    )


__all__ = [
    "MetricSummary",
    "aggregate_metrics",
    "grid_spl",
    "invalid_action_rate",
    "plan_validity",
    "recovery_denominator",
    "sope",
    "sr",
]
