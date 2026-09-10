"""B3 typed planning outcomes and oracle state identity integration tests."""

import pytest

import neuro_symbolic_vln.agent as agent
from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    CommittedPlanningState,
    EpisodeOutcome,
    GroundAtom,
    LocationGraph,
    ObservationPacket,
    PlanResult,
    PlanStatus,
    StepResult,
    SymbolicAction,
)
from neuro_symbolic_vln.env.tasks import make_goto_goal_probe_env
from neuro_symbolic_vln.env.verifier import VerificationResult


def _plan(
    status: PlanStatus,
    actions: tuple[SymbolicAction, ...] = (),
    *,
    state_hash: str = "oracle-state",
) -> PlanResult:
    """Create a complete planner result at the B3 planning boundary."""
    return PlanResult(
        status=status,
        actions=actions,
        planning_time_ms=0.0,
        state_hash=state_hash,
        problem_hash="problem",
        reason="test planner result",
    )


def _oracle_state_for(
    agent_pos: tuple[int, int], *, version: int = 1
) -> CommittedPlanningState:
    env = make_goto_goal_probe_env(agent_pos=agent_pos)
    env.reset(seed=0)
    return agent.extract_oracle_committed_state(env, version=version)


@pytest.mark.parametrize(
    ("status", "expected_outcome"),
    [
        (PlanStatus.TIMEOUT, EpisodeOutcome.PLANNER_TIMEOUT),
        (PlanStatus.PLANNER_ERROR, EpisodeOutcome.PLANNER_ERROR),
        (PlanStatus.SERIALIZATION_ERROR, EpisodeOutcome.PLANNER_ERROR),
        (PlanStatus.NO_PLAN_KNOWN_SPACE, EpisodeOutcome.KNOWN_SPACE_DISCONNECTED),
    ],
)
def test_initial_planner_failure_has_typed_terminal_outcome(
    monkeypatch: pytest.MonkeyPatch,
    status: PlanStatus,
    expected_outcome: EpisodeOutcome,
) -> None:
    """Catch initial planning failures collapsed into an untyped terminal result."""
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: _plan(status),
    )

    result = agent.run_b3_episode()

    assert result.terminal_outcome is expected_outcome
    assert result.task_success is False
    assert result.replan_count == 0


def test_completed_unsuccessful_found_plan_has_typed_terminal_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch completed FOUND plans that return without a typed failure outcome."""
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: _plan(PlanStatus.FOUND, (_confirm_action(),)),
    )

    result = agent.run_b3_episode(family="goto_type_color")

    assert result.task_success is False
    assert result.terminal_outcome is EpisodeOutcome.LOOP_DETECTED
    assert result.replan_count == 2


def test_oracle_state_hash_changes_for_different_same_size_fact_sets() -> None:
    """Catch hashes that omit pose or fact identity in favor of fact count."""
    first = _oracle_state_for((1, 1))
    second = _oracle_state_for((1, 2))

    assert len(first.true_facts) == len(second.true_facts)
    assert first.state_hash != second.state_hash


def test_oracle_state_version_preserves_semantic_state_hash() -> None:
    """Catch version metadata changing the no-op detection state identity."""
    initial = _oracle_state_for((1, 1), version=1)
    revision = _oracle_state_for((1, 1), version=2)

    assert initial.version == 1
    assert revision.version == 2
    assert revision.state_hash == initial.state_hash


def _packet(step: int = 0) -> ObservationPacket:
    return ObservationPacket(
        observation_id=f"scripted-{step}",
        step=step,
        categorical_view=CategoricalView(
            cells_by_x=((CategoricalCell(0, 0, 0, False),),)
        ),
        heading="east",
        carried_entity=None,
        instruction="scripted",
    )


def _step_result(
    *,
    action_succeeded: bool,
    failure_reason: str | None = None,
    task_success: bool = False,
    terminated: bool = False,
    truncated: bool = False,
) -> StepResult:
    return StepResult(
        observation=_packet(),
        action_succeeded=action_succeeded,
        failure_reason=failure_reason,
        task_success=task_success,
        terminated=terminated,
        truncated=truncated,
    )


def _state(state_hash: str, *, version: int = 1) -> CommittedPlanningState:
    return CommittedPlanningState(
        version=version,
        state_hash=state_hash,
        true_facts=frozenset(
            {
                GroundAtom("robot-at", ("robot", "loc-1-1")),
                GroundAtom("facing", ("robot", "east")),
            }
        ),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=LocationGraph(
            nodes=frozenset({"loc-1-1"}),
            directed_edges=frozenset(),
            frontier_nodes=frozenset(),
        ),
    )


class ScriptedAdapter:
    def __init__(self, _env: object, _episode: object, _verifier: object) -> None:
        self.results: list[StepResult] = []

    def reset(self, *, seed: int | None = None) -> ObservationPacket:
        del seed
        return _packet()

    def step(self, _action: object) -> StepResult:
        return self.results.pop(0)


class ScriptedVerifier:
    def __init__(self, outcomes: list[VerificationResult]) -> None:
        self.outcomes = outcomes

    def evaluate(self) -> VerificationResult:
        return self.outcomes.pop(0)


def _move_action() -> SymbolicAction:
    return SymbolicAction("move-forward", ("robot", "loc-1-1", "loc-2-1", "east"))


def _confirm_action() -> SymbolicAction:
    return SymbolicAction(
        "confirm-goto",
        ("robot", "target-1", "loc-1-1", "loc-2-1", "east"),
    )


def test_failed_move_reobserves_and_replans_from_new_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed primitive re-extracts oracle state before replanning."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [_step_result(action_succeeded=False, failure_reason="blocked")]
    verifier = ScriptedVerifier(
        [
            VerificationResult(
                task_success=True,
                terminated=False,
                reason_code="target-in-front",
            )
        ]
    )
    plans = iter(
        (
            _plan(PlanStatus.FOUND, (_move_action(),), state_hash="initial-hash"),
            _plan(PlanStatus.FOUND, (_confirm_action(),), state_hash="recovered-hash"),
        )
    )
    states = iter((_state("initial-hash"), _state("recovered-hash", version=2)))

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(agent, "GoToVerifier", lambda *_args, **_kwargs: verifier)
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )

    def scripted_plan(*_args: object, **_kwargs: object) -> PlanResult:
        return next(plans)

    monkeypatch.setattr(agent, "plan_committed_state", scripted_plan)

    result = agent.run_b3_episode()

    assert result.task_success is True
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.replan_count == 1
    assert result.traces[0].monitor_decision is not None
    assert result.plan.state_hash == "recovered-hash"
    assert all(trace.primitive != "confirm-goto" for trace in result.traces)


def test_terminal_failed_step_stops_before_replanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminated unsuccessful step never enters recovery."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [
        _step_result(
            action_succeeded=False,
            failure_reason="blocked",
            terminated=True,
        )
    ]
    states = iter((_state("initial-hash"),))
    planner_calls = 0

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(
        agent,
        "GoToVerifier",
        lambda *_args, **_kwargs: ScriptedVerifier([]),
    )
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )

    def scripted_plan(*_args: object, **_kwargs: object) -> PlanResult:
        nonlocal planner_calls
        planner_calls += 1
        return _plan(PlanStatus.FOUND, (_move_action(),), state_hash="initial-hash")

    monkeypatch.setattr(agent, "plan_committed_state", scripted_plan)

    result = agent.run_b3_episode()

    assert result.terminal_outcome is EpisodeOutcome.ENVIRONMENT_TERMINATED_FAILURE
    assert planner_calls == 1


def test_terminal_successful_step_preserves_successful_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful terminal primitive is not classified as environment failure."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [
        _step_result(
            action_succeeded=True,
            task_success=True,
            terminated=True,
        )
    ]
    verifier = ScriptedVerifier(
        [
            VerificationResult(
                task_success=True,
                terminated=False,
                reason_code="target-in-front",
            )
        ]
    )
    state = _state("initial-hash")

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(agent, "GoToVerifier", lambda *_args, **_kwargs: verifier)
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: state,
    )
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: _plan(
            PlanStatus.FOUND,
            (_move_action(), _confirm_action()),
            state_hash="initial-hash",
        ),
    )

    result = agent.run_b3_episode()

    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert result.task_success is True
    assert result.replan_count == 0
    assert result.step_count == 1
    assert result.traces[0].step_result is not None
    assert result.traces[0].step_result.task_success is True
    assert result.traces[-1].primitive is None


def test_confirmation_rejection_replans_with_pose_invalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected confirmation invalidates pose facts before replanning."""
    adapter = ScriptedAdapter(None, None, None)
    verifier = ScriptedVerifier(
        [
            VerificationResult(
                task_success=False,
                terminated=False,
                reason_code="target-not-in-front",
            ),
            VerificationResult(
                task_success=True,
                terminated=False,
                reason_code="target-in-front",
            ),
        ]
    )
    plans = iter(
        (
            _plan(PlanStatus.FOUND, (_confirm_action(),), state_hash="initial-hash"),
            _plan(PlanStatus.FOUND, (_confirm_action(),), state_hash="recovered-hash"),
        )
    )
    states = iter((_state("initial-hash"), _state("recovered-hash", version=2)))

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(agent, "GoToVerifier", lambda *_args, **_kwargs: verifier)
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: next(plans),
    )

    result = agent.run_b3_episode()

    decision = result.traces[0].monitor_decision
    assert decision is not None
    assert (
        GroundAtom("target-at", ("target-1", "loc-b"))
        not in decision.atoms_to_invalidate
    )
    assert result.terminal_outcome is EpisodeOutcome.SUCCESS
    assert all(trace.primitive != "confirm-goto" for trace in result.traces)


def test_sixth_replan_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catch a sixth recovery that invokes planning beyond the hard bound."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [
        _step_result(action_succeeded=False, failure_reason="blocked") for _ in range(6)
    ]
    state_hashes = tuple(f"state-{index}" for index in range(6))
    states = iter(
        _state(state_hash, version=index + 1)
        for index, state_hash in enumerate(state_hashes)
    )
    plans = iter(
        _plan(PlanStatus.FOUND, (_move_action(),), state_hash=state_hash)
        for state_hash in state_hashes
    )
    planner_calls = 0

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(
        agent,
        "GoToVerifier",
        lambda *_args, **_kwargs: ScriptedVerifier([]),
    )
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )

    def scripted_plan(*_args: object, **_kwargs: object) -> PlanResult:
        nonlocal planner_calls
        planner_calls += 1
        return next(plans)

    monkeypatch.setattr(agent, "plan_committed_state", scripted_plan)

    result = agent.run_b3_episode()

    assert result.terminal_outcome is EpisodeOutcome.REPLAN_BUDGET_EXHAUSTED
    assert result.replan_count == 5
    assert planner_calls == 6


def test_third_identical_replan_signature_detects_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch recovery that accepts a third identical plan signature."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [
        _step_result(action_succeeded=False, failure_reason="blocked") for _ in range(2)
    ]
    states = iter(_state("same-state", version=index) for index in range(1, 4))
    plans = iter(
        _plan(PlanStatus.FOUND, (_move_action(),), state_hash="same-state")
        for _ in range(3)
    )

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(
        agent,
        "GoToVerifier",
        lambda *_args, **_kwargs: ScriptedVerifier([]),
    )
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: next(plans),
    )

    result = agent.run_b3_episode()

    assert result.terminal_outcome is EpisodeOutcome.LOOP_DETECTED
    assert result.replan_count == 2
    assert len(result.traces) == 2


def test_public_primitive_action_budget_is_hard_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a 33rd primitive reaching the adapter after the public limit."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [_step_result(action_succeeded=True) for _ in range(32)]
    turn = SymbolicAction("turn-left", ("robot", "east", "north"))
    state = _state("initial-state")

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(
        agent,
        "GoToVerifier",
        lambda *_args, **_kwargs: ScriptedVerifier([]),
    )
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: state,
    )
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: _plan(
            PlanStatus.FOUND,
            (turn,) * 33,
            state_hash="initial-state",
        ),
    )

    result = agent.run_b3_episode()

    assert result.terminal_outcome is EpisodeOutcome.ACTION_BUDGET_EXHAUSTED
    assert result.step_count == 32
    assert len(adapter.results) == 0


@pytest.mark.parametrize(
    ("status", "expected_outcome"),
    [
        (PlanStatus.TIMEOUT, EpisodeOutcome.PLANNER_TIMEOUT),
        (PlanStatus.PLANNER_ERROR, EpisodeOutcome.PLANNER_ERROR),
        (PlanStatus.NO_PLAN_KNOWN_SPACE, EpisodeOutcome.KNOWN_SPACE_DISCONNECTED),
    ],
)
def test_replan_planner_failure_retains_latest_typed_plan_result(
    monkeypatch: pytest.MonkeyPatch,
    status: PlanStatus,
    expected_outcome: EpisodeOutcome,
) -> None:
    """Catch recovery that loses the latest typed planner failure result."""
    adapter = ScriptedAdapter(None, None, None)
    adapter.results = [_step_result(action_succeeded=False, failure_reason="blocked")]
    states = iter((_state("initial-state"), _state("recovered-state", version=2)))
    plans = iter(
        (
            _plan(PlanStatus.FOUND, (_move_action(),), state_hash="initial-state"),
            _plan(status, state_hash="recovered-state"),
        )
    )

    monkeypatch.setattr(agent, "MiniGridAdapter", lambda *_args: adapter)
    monkeypatch.setattr(
        agent,
        "GoToVerifier",
        lambda *_args, **_kwargs: ScriptedVerifier([]),
    )
    monkeypatch.setattr(
        agent,
        "extract_oracle_committed_state",
        lambda *_args, **_kwargs: next(states),
    )
    monkeypatch.setattr(
        agent,
        "plan_committed_state",
        lambda *_args, **_kwargs: next(plans),
    )

    result = agent.run_b3_episode()

    assert result.terminal_outcome is expected_outcome
    assert result.plan.status is status
    assert result.replan_count == 1
