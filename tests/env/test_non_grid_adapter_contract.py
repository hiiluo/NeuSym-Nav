from __future__ import annotations

import ast
from pathlib import Path

from neuro_symbolic_vln.contracts import (
    ObservationPacket,
    PrimitiveAction,
)
from tests.fakes import FakeGraphAdapter


def test_fake_graph_adapter_satisfies_step_contract() -> None:
    adapter = FakeGraphAdapter()
    observation = adapter.reset()
    result = adapter.step(PrimitiveAction("move_forward"))
    assert observation.heading in {"north", "east", "south", "west"}
    assert isinstance(result.action_succeeded, bool)


def test_fake_graph_adapter_uses_opaque_string_locations() -> None:
    adapter = FakeGraphAdapter()
    adapter.reset()
    assert isinstance(adapter.current_location, str)
    assert adapter.current_location == "room_1"

    # Forward to corridor
    result = adapter.step(PrimitiveAction("move_forward"))
    assert result.action_succeeded
    assert adapter.current_location == "corridor"
    assert isinstance(adapter.current_location, str)


def test_fake_graph_adapter_deterministic_navigation_to_goal() -> None:
    adapter = FakeGraphAdapter()
    obs = adapter.reset()
    assert isinstance(obs, ObservationPacket)
    assert not obs.carried_entity

    # room_1 facing north -> move_forward -> corridor
    r1 = adapter.step(PrimitiveAction("move_forward"))
    assert r1.action_succeeded
    assert not r1.task_success
    assert adapter.current_location == "corridor"

    # in corridor facing north -> turn_right -> facing east
    r2 = adapter.step(PrimitiveAction("turn_right"))
    assert r2.action_succeeded
    assert r2.observation.heading == "east"

    # in corridor facing east -> move_forward -> room_2 (goal)
    r3 = adapter.step(PrimitiveAction("move_forward"))
    assert r3.action_succeeded
    assert r3.task_success
    assert r3.terminated
    assert adapter.current_location == "room_2"


def test_fake_graph_adapter_blocked_action_reports_failure() -> None:
    adapter = FakeGraphAdapter()
    adapter.reset()

    # In room_1 facing north, turn left -> facing west (no edge from room_1 going west)
    adapter.step(PrimitiveAction("turn_left"))
    result = adapter.step(PrimitiveAction("move_forward"))
    assert not result.action_succeeded
    assert result.failure_reason == "action had no actuator effect"
    assert not result.task_success


def test_fake_graph_adapter_has_no_minigrid_dependencies() -> None:
    fakes_path = Path(__file__).parent.parent / "fakes.py"
    content = fakes_path.read_text()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("minigrid"), (
                    f"Found minigrid import in fakes.py: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("minigrid"), (
                f"Found from minigrid import in fakes.py: {node.module}"
            )
