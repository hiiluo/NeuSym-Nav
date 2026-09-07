import pytest

from neuro_symbolic_vln.contracts import (
    EpisodeSpec,
    ObservationPacket,
    PrimitiveAction,
    StepResult,
)
from neuro_symbolic_vln.env.minigrid_adapter import MiniGridAdapter
from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env
from neuro_symbolic_vln.env.verifier import GoToVerifier


def _make_episode() -> EpisodeSpec:
    return EpisodeSpec(
        episode_id="adapter-contract",
        family="probe",
        instruction="open the door",
        public_action_budget=32,
        manifest_hash="test-manifest",
    )


def _make_adapter() -> MiniGridAdapter:
    env = make_locked_door_probe_env()
    return MiniGridAdapter(
        env,
        _make_episode(),
        GoToVerifier(target_position=(4, 1), env=env),
    )


def test_reset_returns_observation_packet() -> None:
    adapter = _make_adapter()

    observation = adapter.reset(seed=0)

    assert isinstance(observation, ObservationPacket)
    assert observation.step == 0
    assert observation.heading == "east"
    assert observation.carried_entity is None


def test_local_view_marks_unseen_cells() -> None:
    adapter = _make_adapter()

    observation = adapter.reset(seed=0)

    cells = [
        cell
        for column in observation.categorical_view.cells_by_x
        for cell in column
    ]
    assert any(cell.visible for cell in cells)
    assert any(not cell.visible for cell in cells)


def test_public_contract_has_no_privileged_fields() -> None:
    adapter = _make_adapter()
    observation = adapter.reset(seed=0)
    result = adapter.step(PrimitiveAction("turn_left"))

    # The adapter output carries only the local categorical view:
    # no global map, absolute coordinates or object positions.
    assert set(observation.__dataclass_fields__) == {
        "observation_id",
        "step",
        "categorical_view",
        "heading",
        "carried_entity",
        "instruction",
    }
    assert set(result.__dataclass_fields__) == {
        "observation",
        "action_succeeded",
        "failure_reason",
        "task_success",
        "terminated",
        "truncated",
    }
    # Adapter instance state is entirely private.
    assert {name for name in vars(adapter) if not name.startswith("_")} == set()


def test_ordered_key_door_goal_success() -> None:
    adapter = _make_adapter()
    adapter.reset(seed=0)

    pickup = adapter.step(PrimitiveAction("pickup"))
    assert isinstance(pickup, StepResult)
    assert pickup.action_succeeded
    assert pickup.observation.carried_entity == "red:key"
    assert not pickup.task_success

    approach = adapter.step(PrimitiveAction("move_forward"))
    assert approach.action_succeeded
    assert not approach.task_success

    toggle = adapter.step(PrimitiveAction("toggle"))
    assert toggle.action_succeeded
    assert not toggle.task_success

    enter = adapter.step(PrimitiveAction("move_forward"))
    assert enter.action_succeeded
    assert enter.task_success
    assert not enter.terminated


def test_blocked_forward_reports_failure() -> None:
    adapter = _make_adapter()
    adapter.reset(seed=0)

    adapter.step(PrimitiveAction("turn_left"))  # face north: wall ahead
    result = adapter.step(PrimitiveAction("move_forward"))

    assert not result.action_succeeded
    assert result.failure_reason == "action had no actuator effect"


def test_done_does_not_create_success() -> None:
    adapter = _make_adapter()
    adapter.reset(seed=0)

    result = adapter.step(PrimitiveAction("done"))

    # "done" is a no-op in MiniGrid 3.1.0: never a success signal.
    assert not result.action_succeeded
    assert not result.task_success
    assert not result.terminated


def test_unsupported_action_raises() -> None:
    adapter = _make_adapter()
    adapter.reset(seed=0)

    with pytest.raises(ValueError):
        adapter.step(PrimitiveAction("fly"))
