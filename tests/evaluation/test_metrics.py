from __future__ import annotations

import pytest

from neuro_symbolic_vln.evaluation.metrics import (
    MetricSummary,
    aggregate_metrics,
    grid_spl,
    invalid_action_rate,
    plan_validity,
    recovery_denominator,
    sope,
    sr,
)


def test_grid_spl_success() -> None:
    assert grid_spl(success=True, optimal_distance=4, executed_distance=8) == 0.5


def test_grid_spl_failure_is_zero() -> None:
    assert grid_spl(success=False, optimal_distance=4, executed_distance=4) == 0.0


def test_grid_spl_zero_optimal_only_valid_when_already_at_target() -> None:
    # Plan §16.1: SPL undefined when optimal distance is zero and the
    # episode required movement. Guard against silent divide-by-zero.
    assert grid_spl(success=True, optimal_distance=0, executed_distance=0) == 1.0
    with pytest.raises(ValueError):
        grid_spl(success=True, optimal_distance=0, executed_distance=4)


def test_sope_counts_primitive_actions() -> None:
    assert sope(success=True, optimal_actions=5, attempted_actions=10) == 0.5


def test_sope_failure_is_zero() -> None:
    assert sope(success=False, optimal_actions=5, attempted_actions=5) == 0.0


def test_sope_zero_optimal_requires_zero_attempted() -> None:
    assert sope(success=True, optimal_actions=0, attempted_actions=0) == 1.0
    with pytest.raises(ValueError):
        sope(success=True, optimal_actions=0, attempted_actions=3)


def test_sr_counts_successes_over_total() -> None:
    assert sr([True, True, False, False]) == 0.5
    assert sr([True] * 3) == 1.0


def test_sr_rejects_empty_denominator() -> None:
    with pytest.raises(ValueError):
        sr([])


def test_invalid_action_rate() -> None:
    assert invalid_action_rate(attempted_actions=10, invalid_actions=3) == 0.3
    assert invalid_action_rate(attempted_actions=0, invalid_actions=0) == 0.0
    with pytest.raises(ValueError):
        invalid_action_rate(attempted_actions=0, invalid_actions=1)


def test_recovery_denominator_uses_only_recoverable_intervention_episodes() -> None:
    rows = [
        {"intervention": True, "recoverable": True, "success": True},
        {"intervention": True, "recoverable": True, "success": False},
        {"intervention": True, "recoverable": False, "success": False},
        {"intervention": False, "recoverable": False, "success": True},
    ]
    denom = recovery_denominator(rows)
    # Two eligible (recoverable + intervention) episodes.
    assert denom == 2


def test_plan_validity_counts_found_plans() -> None:
    assert plan_validity(["found", "found", "timeout", "no_plan_known_space"]) == 0.5
    with pytest.raises(ValueError):
        plan_validity([])


def test_aggregate_metrics_produces_summary_with_all_required_fields() -> None:
    rows = [
        {
            "episode_id": "goto-smoke-0000",
            "success": True,
            "optimal_distance": 4,
            "executed_distance": 4,
            "optimal_actions": 5,
            "attempted_actions": 5,
            "invalid_actions": 0,
            "plan_status": "found",
            "intervention": False,
            "recoverable": False,
        },
        {
            "episode_id": "goto-smoke-0001",
            "success": False,
            "optimal_distance": 4,
            "executed_distance": 12,
            "optimal_actions": 5,
            "attempted_actions": 20,
            "invalid_actions": 3,
            "plan_status": "found",
            "intervention": True,
            "recoverable": True,
        },
    ]

    summary = aggregate_metrics(rows)

    assert isinstance(summary, MetricSummary)
    assert summary.sr == 0.5
    assert summary.mean_grid_spl == pytest.approx(0.5)
    assert summary.mean_sope == pytest.approx(0.5)
    assert summary.invalid_action_rate == pytest.approx(3 / 25)
    assert summary.plan_validity == 1.0
    assert summary.recovery_denominator == 1
    assert summary.n_episodes == 2
