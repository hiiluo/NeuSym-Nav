from __future__ import annotations

from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode
from neuro_symbolic_vln.contracts import EpisodeOutcome, ParseStatus, PlanStatus


def test_v1r1_solves_clean_goto_across_all_headings() -> None:
    for seed in range(4):
        result = run_v1r1_episode(seed=seed, family="goto_type_color")
        assert result.task_success, (seed, result.terminal_outcome)
        assert result.terminal_outcome is EpisodeOutcome.SUCCESS
        assert result.parse_status is ParseStatus.DETERMINISTIC
        assert result.plan.status is PlanStatus.FOUND
        # Belief-driven; the tracker's initial 360 scan alone should not
        # exceed a handful of extra primitives.
        assert result.step_count <= 12


def test_v1r1_solves_clean_keydoor_across_all_headings() -> None:
    for seed in range(4):
        result = run_v1r1_episode(seed=seed, family="key_door_goal")
        assert result.task_success, (seed, result.terminal_outcome)
        assert result.terminal_outcome is EpisodeOutcome.SUCCESS
        # Keydoor decomposes into three subgoals so multiple replan
        # events are legitimate; the recovery budget must still hold.
        assert result.replan_count <= 3
        assert result.step_count <= 24


def test_v1r1_result_carries_traces_and_belief_hash() -> None:
    result = run_v1r1_episode(seed=0, family="goto_type_color")
    assert result.traces
    assert result.belief_state_hash
    # Every trace records the executed action (primitive or confirmation).
    for trace in result.traces:
        assert trace.action.name


def test_v1r1_recovers_from_block_intervention_where_v1r0_fails() -> None:
    """Recovery ablation: V1R0 has to fail on the RQ2 block; V1R1 must
    route around it. Confirms the runner's V1R0 vs V1R1 differential
    for the RQ2 goto family (plan §15.5)."""
    from neuro_symbolic_vln.evaluation.interventions import (
        choose_block_intervention,
    )

    spec = choose_block_intervention(
        (2, 1), ((1, 2), (2, 2), (3, 2), (4, 2), (4, 1)), seed=40
    )
    v1r0 = run_v1r1_episode(
        seed=40,
        family="goto_type_color",
        method="V1R0",
        use_validator=True,
        use_recovery=False,
        intervention=spec,
    )
    v1r1 = run_v1r1_episode(
        seed=40,
        family="goto_type_color",
        method="V1R1",
        use_validator=True,
        use_recovery=True,
        intervention=spec,
    )
    assert v1r0.task_success is False
    assert v1r1.task_success is True
    assert v1r1.replan_count >= 1


def test_v1r1_recovers_from_relock_intervention_where_v1r0_fails() -> None:
    from neuro_symbolic_vln.evaluation.interventions import (
        choose_relock_intervention,
    )

    spec = choose_relock_intervention((3, 1), seed=32)
    v1r0 = run_v1r1_episode(
        seed=32,
        family="key_door_goal",
        method="V1R0",
        use_validator=True,
        use_recovery=False,
        intervention=spec,
    )
    v1r1 = run_v1r1_episode(
        seed=32,
        family="key_door_goal",
        method="V1R1",
        use_validator=True,
        use_recovery=True,
        intervention=spec,
    )
    assert v1r0.task_success is False
    assert v1r1.task_success is True
    assert v1r1.replan_count >= 1
