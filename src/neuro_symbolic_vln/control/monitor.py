"""Execution monitoring and bounded replanning for Neuro-Symbolic VLN."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from neuro_symbolic_vln.contracts import (
    EpisodeOutcome,
    GroundAtom,
    StepResult,
    SymbolicAction,
)

# Canonical failure reasons from real execution and verifier contracts:
# - MiniGridAdapter: "action had no actuator effect"
# - GoToVerifier: "target-not-in-front"
# - Handbook test fixtures: "blocked", "verifier_rejected"
REAL_MOVE_FAILURES = frozenset({"action had no actuator effect", "blocked"})
REAL_TOGGLE_FAILURES = frozenset({"action had no actuator effect"})
REAL_VERIFIER_FAILURES = frozenset({"target-not-in-front", "verifier_rejected"})
REAL_PICKUP_FAILURES = frozenset({"action had no actuator effect"})

_ACTION_ARITIES = {
    "turn-left": 3,
    "turn-right": 3,
    "move-forward": 4,
    "pickup-key": 5,
    "toggle-locked-door": 6,
    "confirm-goto": 5,
}


@dataclass(frozen=True)
class MonitorDecision:
    """Typed outcome from observing execution feedback."""

    reason_code: str
    atoms_to_invalidate: tuple[GroundAtom, ...]
    requires_reobservation: bool
    requires_replan: bool


def _recovery_decision(
    reason_code: str, atoms_to_invalidate: tuple[GroundAtom, ...] = ()
) -> MonitorDecision:
    return MonitorDecision(
        reason_code=reason_code,
        atoms_to_invalidate=atoms_to_invalidate,
        requires_reobservation=True,
        requires_replan=True,
    )


def _expected_dynamic_preconditions(
    action: SymbolicAction,
) -> tuple[GroundAtom, ...]:
    """Return the PDDL dynamic preconditions for a fully grounded action."""
    if len(action.arguments) != _ACTION_ARITIES.get(action.name):
        return ()

    if action.name in {"turn-left", "turn-right"}:
        robot_id, from_heading, _ = action.arguments
        return (GroundAtom("facing", (robot_id, from_heading)),)

    if action.name == "move-forward":
        robot_id, from_loc, to_loc, heading = action.arguments
        return (
            GroundAtom("robot-at", (robot_id, from_loc)),
            GroundAtom("facing", (robot_id, heading)),
            GroundAtom("front-cell", (from_loc, heading, to_loc)),
            GroundAtom("passable", (to_loc,)),
        )

    if action.name == "pickup-key":
        robot_id, key_id, loc, front_loc, heading = action.arguments
        return (
            GroundAtom("robot-at", (robot_id, loc)),
            GroundAtom("facing", (robot_id, heading)),
            GroundAtom("front-cell", (loc, heading, front_loc)),
            GroundAtom("key-at", (key_id, front_loc)),
            GroundAtom("handempty", (robot_id,)),
        )

    if action.name == "toggle-locked-door":
        robot_id, key_id, door_id, loc, front_loc, heading = action.arguments
        return (
            GroundAtom("robot-at", (robot_id, loc)),
            GroundAtom("facing", (robot_id, heading)),
            GroundAtom("front-cell", (loc, heading, front_loc)),
            GroundAtom("door-at", (door_id, front_loc)),
            GroundAtom("door-locked", (door_id,)),
            GroundAtom("holding", (robot_id, key_id)),
            GroundAtom("key-opens", (key_id, door_id)),
        )

    if action.name == "confirm-goto":
        robot_id, target_id, from_loc, target_loc, heading = action.arguments
        return (
            GroundAtom("robot-at", (robot_id, from_loc)),
            GroundAtom("facing", (robot_id, heading)),
            GroundAtom("front-cell", (from_loc, heading, target_loc)),
            GroundAtom("target-at", (target_id, target_loc)),
        )

    return ()


class ExecutionMonitor:
    """Monitors action execution, detects mismatches, and enforces replan bounds."""

    def __init__(self, max_replans: int = 5, max_loop_repeats: int = 2) -> None:
        self.max_replans = max_replans
        self.max_loop_repeats = max_loop_repeats
        self.replan_count = 0
        self._signature_history: dict[tuple[str, str, tuple[str, str], str], int] = {}

    def observe_action_result(
        self,
        action: SymbolicAction | str | None = None,
        step_result: StepResult | None = None,
        action_succeeded: bool | None = None,
        failure_reason: str | None = None,
        *,
        symbolic_action: SymbolicAction | str | None = None,
    ) -> MonitorDecision:
        """Analyze execution feedback and return a recovery decision."""
        if step_result is None and action_succeeded is None:
            raise ValueError(
                "observe_action_result requires StepResult or action_succeeded"
            )

        raw_action = action if action is not None else symbolic_action
        if raw_action is None:
            raise ValueError(
                "observe_action_result requires an action or symbolic_action"
            )

        if isinstance(raw_action, str):
            is_bare_string = True
            symbolic = SymbolicAction(raw_action, ())
        else:
            is_bare_string = False
            symbolic = raw_action
        expected_arity = _ACTION_ARITIES.get(symbolic.name)
        if (
            expected_arity is not None
            and not (is_bare_string and not symbolic.arguments)
            and len(symbolic.arguments) != expected_arity
        ):
            raise ValueError(
                f"Invalid arity for {symbolic.name}: expected {expected_arity} "
                f"arguments, got {len(symbolic.arguments)} ({symbolic.arguments})"
            )

        if step_result is not None:
            succeeded = step_result.action_succeeded
            reason = step_result.failure_reason
        else:
            assert action_succeeded is not None
            succeeded = action_succeeded
            reason = failure_reason

        if succeeded:
            return MonitorDecision(
                reason_code="execution.success",
                atoms_to_invalidate=(),
                requires_reobservation=False,
                requires_replan=False,
            )

        if not is_bare_string and symbolic.name == "move-forward":
            if reason in REAL_MOVE_FAILURES:
                _, _, target_loc, _ = symbolic.arguments
                return _recovery_decision(
                    "execution.predicted_move_failed",
                    (GroundAtom("passable", (target_loc,)),),
                )

        if not is_bare_string and symbolic.name == "toggle-locked-door":
            if reason in REAL_TOGGLE_FAILURES:
                _, key_id, door_id, _, front_loc, _ = symbolic.arguments
                return _recovery_decision(
                    "execution.toggle_failed",
                    (
                        GroundAtom("door-locked", (door_id,)),
                        GroundAtom("door-open", (door_id,)),
                        GroundAtom("passable", (front_loc,)),
                        GroundAtom("holding", ("robot", key_id)),
                    ),
                )

        if not is_bare_string and symbolic.name == "confirm-goto":
            if reason in REAL_VERIFIER_FAILURES:
                _, _, from_loc, target_loc, heading = symbolic.arguments
                return _recovery_decision(
                    "execution.verifier_rejected",
                    (
                        GroundAtom("robot-at", ("robot", from_loc)),
                        GroundAtom("facing", ("robot", heading)),
                        GroundAtom("front-cell", (from_loc, heading, target_loc)),
                    ),
                )

        if not is_bare_string and symbolic.name == "pickup-key":
            if reason in REAL_PICKUP_FAILURES:
                _, key_id, _, front_loc, _ = symbolic.arguments
                return _recovery_decision(
                    "execution.pickup_failed",
                    (GroundAtom("key-at", (key_id, front_loc)),),
                )

        if (
            not is_bare_string
            and symbolic.name in {"turn-left", "turn-right"}
            and reason in REAL_MOVE_FAILURES
        ):
            robot_id, from_heading, _ = symbolic.arguments
            return _recovery_decision(
                "execution.turn_failed",
                (GroundAtom("facing", (robot_id, from_heading)),),
            )

        detail_reason = (
            f"execution.failed:{reason}" if reason else "execution.unknown_failure"
        )
        return _recovery_decision(detail_reason)

    def check_preconditions(
        self,
        action: SymbolicAction,
        stale_atoms: Sequence[GroundAtom],
    ) -> MonitorDecision | None:
        """Request recovery when a dynamic PDDL precondition is stale."""
        expected_atoms = _expected_dynamic_preconditions(action)
        for atom in stale_atoms:
            if atom in expected_atoms:
                return _recovery_decision("temporal.stale_dynamic_fact", (atom,))
        return None

    def check_replan_budget(self) -> EpisodeOutcome | None:
        """Enforce the hard budget on replans per episode."""
        if self.replan_count >= self.max_replans:
            return EpisodeOutcome.REPLAN_BUDGET_EXHAUSTED
        self.replan_count += 1
        return None

    def record_and_check_loop(
        self, sig: tuple[str, str, tuple[str, str], str]
    ) -> EpisodeOutcome | None:
        """Detect no-progress loops when a signature repeats too often."""
        count = self._signature_history.get(sig, 0) + 1
        self._signature_history[sig] = count
        if count > self.max_loop_repeats:
            return EpisodeOutcome.LOOP_DETECTED
        return None
