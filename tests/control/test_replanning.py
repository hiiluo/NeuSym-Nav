import pytest

from neuro_symbolic_vln.contracts import (
    CategoricalView,
    EpisodeOutcome,
    GroundAtom,
    ObservationPacket,
    StepResult,
    SymbolicAction,
)
from neuro_symbolic_vln.control.monitor import ExecutionMonitor


def _atom(predicate: str, *arguments: str) -> GroundAtom:
    return GroundAtom(predicate, arguments)


def _failed_step(reason: str | None = "blocked") -> StepResult:
    return StepResult(
        observation=ObservationPacket(
            observation_id="obs-1",
            step=1,
            categorical_view=CategoricalView(cells_by_x=()),
            heading="east",
            carried_entity=None,
            instruction="go to the target",
        ),
        action_succeeded=False,
        failure_reason=reason,
        task_success=False,
        terminated=False,
        truncated=False,
    )


def test_missing_feedback_is_rejected() -> None:
    with pytest.raises(ValueError, match="StepResult or action_succeeded"):
        ExecutionMonitor().observe_action_result(action="move-forward")


def test_failed_move_invalidates_destination_passability() -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction("move-forward", ("robot", "loc-a", "loc-b", "east")),
        action_succeeded=False,
        failure_reason="blocked",
    )

    assert decision.atoms_to_invalidate == (_atom("passable", "loc-b"),)
    assert decision.requires_reobservation is True
    assert decision.requires_replan is True


def test_failed_pickup_does_not_invalidate_handempty() -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction(
            "pickup-key", ("robot", "red-key", "loc-a", "loc-b", "east")
        ),
        action_succeeded=False,
        failure_reason="action had no actuator effect",
    )

    assert decision.atoms_to_invalidate == (_atom("key-at", "red-key", "loc-b"),)


def test_failed_toggle_invalidates_door_key_and_front_state() -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction(
            "toggle-locked-door",
            ("robot", "red-key", "red-door", "loc-a", "loc-b", "east"),
        ),
        step_result=_failed_step("action had no actuator effect"),
    )

    assert decision.atoms_to_invalidate == (
        _atom("door-locked", "red-door"),
        _atom("door-open", "red-door"),
        _atom("passable", "loc-b"),
        _atom("holding", "robot", "red-key"),
    )


def test_rejected_confirmation_invalidates_pose_not_target_location() -> None:
    target = _atom("target-at", "target-1", "loc-b")
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction(
            "confirm-goto", ("robot", "target-1", "loc-a", "loc-b", "east")
        ),
        action_succeeded=False,
        failure_reason="target-not-in-front",
    )

    assert target not in decision.atoms_to_invalidate
    assert _atom("robot-at", "robot", "loc-a") in decision.atoms_to_invalidate
    assert _atom("facing", "robot", "east") in decision.atoms_to_invalidate
    assert _atom("front-cell", "loc-a", "east", "loc-b") in (
        decision.atoms_to_invalidate
    )


def test_successful_execution_requires_no_recovery() -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction("move-forward", ("robot", "loc-a", "loc-b", "east")),
        action_succeeded=True,
    )

    assert decision.reason_code == "execution.success"
    assert decision.atoms_to_invalidate == ()
    assert decision.requires_reobservation is False
    assert decision.requires_replan is False


def test_failed_bare_string_action_reobserves_and_replans(
) -> None:
    decision = ExecutionMonitor().observe_action_result(
        action="move-forward", action_succeeded=False, failure_reason="blocked"
    )

    assert decision.atoms_to_invalidate == ()
    assert decision.requires_reobservation is True
    assert decision.requires_replan is True


def test_unrecognized_failure_reason_uses_generic_failure_decision() -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction("move-forward", ("robot", "loc-a", "loc-b", "east")),
        action_succeeded=False,
        failure_reason="unexpected-adapter-message",
    )

    assert decision.reason_code == "execution.failed:unexpected-adapter-message"
    assert decision.atoms_to_invalidate == ()
    assert decision.requires_reobservation is True
    assert decision.requires_replan is True


@pytest.mark.parametrize("failure_reason", [None, ""])
def test_missing_or_empty_reason_uses_generic_recovery(
    failure_reason: str | None,
) -> None:
    decision = ExecutionMonitor().observe_action_result(
        action=SymbolicAction(
            "toggle-locked-door",
            ("robot", "red-key", "red-door", "loc-a", "loc-b", "east"),
        ),
        action_succeeded=False,
        failure_reason=failure_reason,
    )

    assert decision.reason_code == "execution.unknown_failure"
    assert decision.atoms_to_invalidate == ()
    assert decision.requires_reobservation is True
    assert decision.requires_replan is True


@pytest.mark.parametrize(
    ("action", "stale_atoms"),
    [
        (
            SymbolicAction("turn-left", ("robot", "east", "north")),
            (_atom("facing", "robot", "east"),),
        ),
        (
            SymbolicAction("turn-right", ("robot", "east", "south")),
            (_atom("facing", "robot", "east"),),
        ),
        (
            SymbolicAction("move-forward", ("robot", "loc-a", "loc-b", "east")),
            (
                _atom("robot-at", "robot", "loc-a"),
                _atom("facing", "robot", "east"),
                _atom("front-cell", "loc-a", "east", "loc-b"),
                _atom("passable", "loc-b"),
            ),
        ),
        (
            SymbolicAction(
                "pickup-key", ("robot", "red-key", "loc-a", "loc-b", "east")
            ),
            (
                _atom("robot-at", "robot", "loc-a"),
                _atom("facing", "robot", "east"),
                _atom("front-cell", "loc-a", "east", "loc-b"),
                _atom("key-at", "red-key", "loc-b"),
                _atom("handempty", "robot"),
            ),
        ),
        (
            SymbolicAction(
                "toggle-locked-door",
                ("robot", "red-key", "red-door", "loc-a", "loc-b", "east"),
            ),
            (
                _atom("robot-at", "robot", "loc-a"),
                _atom("facing", "robot", "east"),
                _atom("front-cell", "loc-a", "east", "loc-b"),
                _atom("door-at", "red-door", "loc-b"),
                _atom("door-locked", "red-door"),
                _atom("holding", "robot", "red-key"),
                _atom("key-opens", "red-key", "red-door"),
            ),
        ),
        (
            SymbolicAction(
                "confirm-goto", ("robot", "target-1", "loc-a", "loc-b", "east")
            ),
            (
                _atom("robot-at", "robot", "loc-a"),
                _atom("facing", "robot", "east"),
                _atom("front-cell", "loc-a", "east", "loc-b"),
                _atom("target-at", "target-1", "loc-b"),
            ),
        ),
    ],
)
def test_each_dynamic_precondition_stale_fact_requires_recovery(
    action: SymbolicAction, stale_atoms: tuple[GroundAtom, ...]
) -> None:
    monitor = ExecutionMonitor()

    for stale_atom in stale_atoms:
        decision = monitor.check_preconditions(action, (stale_atom,))

        assert decision is not None
        assert decision.reason_code == "temporal.stale_dynamic_fact"
        assert decision.atoms_to_invalidate == (stale_atom,)
        assert decision.requires_reobservation is True
        assert decision.requires_replan is True


def test_precondition_check_returns_the_first_matching_stale_atom() -> None:
    action = SymbolicAction("move-forward", ("robot", "loc-a", "loc-b", "east"))
    first = _atom("facing", "robot", "east")
    second = _atom("passable", "loc-b")

    decision = ExecutionMonitor().check_preconditions(action, (first, second))

    assert decision is not None
    assert decision.atoms_to_invalidate == (first,)


@pytest.mark.parametrize(
    "action",
    [
        SymbolicAction("turn-left", ()),
        SymbolicAction("turn-right", ()),
        SymbolicAction("move-forward", ("robot",)),
        SymbolicAction("pickup-key", ("robot",)),
        SymbolicAction("toggle-locked-door", ("robot",)),
        SymbolicAction("confirm-goto", ("robot",)),
    ],
)
def test_malformed_symbolic_action_arguments_are_rejected(
    action: SymbolicAction,
) -> None:
    with pytest.raises(ValueError, match="Invalid arity"):
        ExecutionMonitor().observe_action_result(
            action=action, action_succeeded=False, failure_reason="blocked"
        )


def test_sixth_replan_exhausts_budget() -> None:
    monitor = ExecutionMonitor()

    for _ in range(5):
        assert monitor.check_replan_budget() is None

    assert monitor.check_replan_budget() is EpisodeOutcome.REPLAN_BUDGET_EXHAUSTED


def test_third_duplicate_signature_detects_loop() -> None:
    monitor = ExecutionMonitor()
    signature = ("target", "state-hash", ("loc-a", "east"), "found")

    assert monitor.record_and_check_loop(signature) is None
    assert monitor.record_and_check_loop(signature) is None
    assert monitor.record_and_check_loop(signature) is EpisodeOutcome.LOOP_DETECTED
