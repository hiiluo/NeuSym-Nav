from minigrid.core.actions import Actions

from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env


def test_pickup_targets_front_cell() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    assert env.unwrapped.carrying is None

    env.step(Actions.pickup)

    assert env.unwrapped.carrying is not None
    assert env.unwrapped.carrying.type == "key"


def test_pickup_empty_front_cell_keeps_hands_empty() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    env.step(Actions.right)  # face south: floor cell (1, 2) is empty
    env.step(Actions.pickup)

    assert env.unwrapped.carrying is None


def test_toggle_targets_front_cell() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    env.step(Actions.pickup)
    assert env.unwrapped.carrying is not None
    assert env.unwrapped.carrying.type == "key"

    env.step(Actions.forward)
    env.step(Actions.toggle)

    # Door should be open
    door = env.unwrapped.grid.get(3, 1)
    assert door is not None
    assert door.type == "door"
    assert door.is_open

    # The task goal occupies the first cell beyond the door.
    goal = env.unwrapped.grid.get(4, 1)
    assert goal is not None
    assert goal.type == "goal"


def test_wrong_key_does_not_open_door() -> None:
    env = make_locked_door_probe_env(key_color="blue")
    env.reset(seed=0)

    env.step(Actions.pickup)
    assert env.unwrapped.carrying is not None
    assert env.unwrapped.carrying.color == "blue"

    env.step(Actions.forward)
    env.step(Actions.toggle)

    # Door is red, the carried key is blue: it must stay locked
    door = env.unwrapped.grid.get(3, 1)
    assert door is not None
    assert door.type == "door"
    assert not door.is_open
    assert door.is_locked


def test_blocked_toggle_does_not_open_door() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    env.step(Actions.forward)
    env.step(Actions.toggle)

    # Door should still be closed
    door = env.unwrapped.grid.get(3, 1)
    assert door is not None
    assert door.type == "door"
    assert not door.is_open


def test_blocked_forward_keeps_position() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    env.step(Actions.left)  # face north: wall at (1, 0)
    env.step(Actions.forward)

    assert env.unwrapped.agent_pos == (1, 1)


def test_done_does_not_create_success() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    _, reward, terminated, truncated, _ = env.step(Actions.done)

    # In MiniGrid 3.1.0 "done" is a no-op: no reward, no termination.
    assert reward == 0
    assert not terminated
    assert not truncated
