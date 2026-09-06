import pytest

from neuro_symbolic_vln.contracts import SymbolicAction
from neuro_symbolic_vln.control.controller import MiniGridController


def test_controller_maps_turn_left() -> None:
    controller = MiniGridController()
    assert controller.to_primitive(SymbolicAction("turn-left", ())) == "turn_left"


def test_controller_maps_all_symbolic_actions() -> None:
    controller = MiniGridController()
    expected = {
        "turn-left": "turn_left",
        "turn-right": "turn_right",
        "move-forward": "move_forward",
        "pickup-key": "pickup",
        "toggle-locked-door": "toggle",
    }
    for symbolic, primitive in expected.items():
        assert controller.to_primitive(SymbolicAction(symbolic, ())) == primitive


def test_confirm_goto_is_not_a_primitive_action() -> None:
    # confirm-goto is a non-primitive confirmation action: the controller
    # must never emit a MiniGrid primitive for it.
    controller = MiniGridController()
    with pytest.raises(
        ValueError, match="unsupported symbolic action: confirm-goto"
    ):
        controller.to_primitive(SymbolicAction("confirm-goto", ()))


def test_unsupported_action_raises_typed_error() -> None:
    controller = MiniGridController()
    with pytest.raises(
        ValueError, match="unsupported symbolic action: unknown-action"
    ):
        controller.to_primitive(SymbolicAction("unknown-action", ()))
