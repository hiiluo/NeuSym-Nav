"""End-to-end smoke test suite for B3 oracle-input planning baseline (Gate G1)."""

import pytest

from neuro_symbolic_vln.agent import plan_committed_state
from neuro_symbolic_vln.contracts import (
    CommittedPlanningState,
    EpisodeOutcome,
    GoalProgram,
    GroundAtom,
    LocationGraph,
    PlanStatus,
    SymbolicAction,
)
from neuro_symbolic_vln.control.controller import MiniGridController
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder
from neuro_symbolic_vln.planning.pyperplan_adapter import PlannerConfig
from neuro_symbolic_vln.testing import B3EpisodeResult, run_b3_episode

# ---------------------------------------------------------------------------
# 1. Canonical handbook tests (Task B-J01 & Task A-J01 specification)
# ---------------------------------------------------------------------------


def test_b3_key_door_plan_executes_successfully() -> None:
    """Canonical test case from Member B Implementation Handbook."""
    result = run_b3_episode(seed=7, family="key_door_goal")
    assert result.plan.status is PlanStatus.FOUND
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.task_success
    assert not result.untyped_failures
    assert result.oracle_input is True


def test_b3_goto_plan_executes_successfully() -> None:
    """Canonical test case for goto_type_color family."""
    result = run_b3_episode(seed=7, family="goto_type_color")
    assert result.plan.status is PlanStatus.FOUND
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.task_success
    assert not result.untyped_failures
    assert result.oracle_input is True


# ---------------------------------------------------------------------------
# 2. Gate G1: Full 20 B3 Smoke Episodes Evaluation (20/20 Success Rate)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", list(range(10)))
def test_b3_smoke_key_door_episodes(seed: int) -> None:
    """Validate 10 deterministic key_door_goal episodes across initial headings."""
    result: B3EpisodeResult = run_b3_episode(seed=seed, family="key_door_goal")

    # 1. Planning found valid plan
    assert result.plan.status is PlanStatus.FOUND, (
        f"Plan failed on seed {seed}: {result.plan.reason}"
    )
    assert result.plan.problem_hash is not None
    assert len(result.plan.actions) > 0

    # 2. Episode succeeded on MiniGrid
    assert result.task_success is True, f"Episode failed on seed {seed}"
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.replan_count == 0
    assert result.untyped_failures is False

    # 3. Gate G1 constraints
    assert result.oracle_input is True
    # Verify no primitive "done" was emitted anywhere in the trace
    for trace in result.traces:
        assert trace.primitive != "done", (
            "Violation of G1: primitive 'done' must never be emitted"
        )
        assert trace.oracle_input is True
        assert trace.monitor_decision is None


@pytest.mark.parametrize("seed", list(range(10)))
def test_b3_smoke_goto_episodes(seed: int) -> None:
    """Validate 10 deterministic goto_type_color episodes across initial headings."""
    result: B3EpisodeResult = run_b3_episode(seed=seed, family="goto_type_color")

    assert result.plan.status is PlanStatus.FOUND, (
        f"Plan failed on seed {seed}: {result.plan.reason}"
    )
    assert result.plan.problem_hash is not None
    assert len(result.plan.actions) > 0

    assert result.task_success is True, f"Episode failed on seed {seed}"
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.replan_count == 0
    assert result.untyped_failures is False

    assert result.oracle_input is True
    for trace in result.traces:
        assert trace.primitive != "done", (
            "Violation of G1: primitive 'done' must never be emitted"
        )
        assert trace.oracle_input is True
        assert trace.monitor_decision is None


def test_20_episodes_aggregate_smoke_metrics() -> None:
    """Aggregates all 20 episodes to ensure 100% success rate required by Gate G1."""
    episodes = [("key_door_goal", s) for s in range(10)] + [
        ("goto_type_color", s) for s in range(10)
    ]
    assert len(episodes) == 20

    success_count = 0
    valid_plan_count = 0

    for family, seed in episodes:
        res = run_b3_episode(seed=seed, family=family)
        if res.plan.status is PlanStatus.FOUND:
            valid_plan_count += 1
        if res.task_success:
            success_count += 1

    assert valid_plan_count == 20, (
        f"Expected 20/20 valid plans, got {valid_plan_count}/20"
    )
    assert success_count == 20, f"Expected 20/20 task success, got {success_count}/20"


# ---------------------------------------------------------------------------
# 3. Confirm-GoTo & Primitive Controller Semantics
# ---------------------------------------------------------------------------


def test_confirm_goto_does_not_emit_primitive_action() -> None:
    """Verify confirm-goto queries TaskVerifier and emits no primitive step."""
    result = run_b3_episode(seed=0, family="goto_type_color")
    assert result.task_success

    last_trace = result.traces[-1]
    assert last_trace.action.name == "confirm-goto"
    assert last_trace.primitive is None, (
        "confirm-goto must not emit any primitive action"
    )
    assert last_trace.step_result is None


def test_controller_unsupported_action_raises_typed_error() -> None:
    """Controller must raise ValueError when given an unknown symbolic action."""
    controller = MiniGridController()
    with pytest.raises(ValueError, match="unsupported symbolic action: unknown-action"):
        controller.to_primitive(SymbolicAction("unknown-action", ()))


# ---------------------------------------------------------------------------
# 4. Edge Cases: GoalProgram & Planning Statuses
# ---------------------------------------------------------------------------


def test_empty_goal_program_raises_error() -> None:
    """Empty GoalProgram must raise ValueError."""
    graph = LocationGraph(frozenset(), frozenset(), frozenset())
    state = CommittedPlanningState(
        version=1,
        state_hash="dummy",
        true_facts=frozenset(),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )
    empty_goal = GoalProgram(family="test", ordered_subgoals=())
    with pytest.raises(
        ValueError, match="GoalProgram must contain at least one subgoal"
    ):
        plan_committed_state(state, empty_goal)


def test_no_plan_in_unreachable_space() -> None:
    """Verify planner returns typed NO_PLAN_KNOWN_SPACE when goal is unreachable."""
    builder = LocationGraphBuilder()
    builder.add_node("loc-1-1")
    builder.add_node("loc-2-1")
    # No edge between loc-1-1 and loc-2-1 (disconnected)
    graph = builder.build()

    state = CommittedPlanningState(
        version=1,
        state_hash="blocked-state",
        true_facts=frozenset(
            {
                GroundAtom("robot-at", ("robot", "loc-1-1")),
                GroundAtom("facing", ("robot", "east")),
                GroundAtom("target-at", ("target-1", "loc-2-1")),
            }
        ),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )

    res = plan_committed_state(state, GroundAtom("task-satisfied", ()))
    assert res.status == PlanStatus.NO_PLAN_KNOWN_SPACE
    assert res.actions == ()
    assert res.problem_hash is not None


def test_bounded_worker_timeout_is_graceful() -> None:
    """Verify planner timeout bounding terminates process safely and returns TIMEOUT."""
    builder = LocationGraphBuilder()
    builder.add_edge("loc-1", "east", "loc-2")
    graph = builder.build()

    state = CommittedPlanningState(
        version=1,
        state_hash="state-timeout",
        true_facts=frozenset(
            {
                GroundAtom("robot-at", ("robot", "loc-1")),
                GroundAtom("facing", ("robot", "east")),
                GroundAtom("target-at", ("target-1", "loc-2")),
            }
        ),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )

    # Force immediate timeout with 0.0001s
    res = plan_committed_state(
        state,
        GroundAtom("task-satisfied", ()),
        config=PlannerConfig(timeout_seconds=0.0001, search="bfs"),
    )
    assert res.status == PlanStatus.TIMEOUT
    assert res.actions == ()
    assert "timeout" in (res.reason or "").lower()


def test_unknown_family_raises_value_error() -> None:
    """Invalid task family must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown task family"):
        run_b3_episode(seed=0, family="nonexistent_family")
