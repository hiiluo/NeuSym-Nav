import pytest

from neuro_symbolic_vln.env.verifier import GoToVerifier


def test_goto_requires_adjacent_and_facing() -> None:
    verifier = GoToVerifier(target_position=(2, 1))

    assert not verifier.is_satisfied(agent_position=(1, 1), agent_direction=1)
    assert verifier.is_satisfied(agent_position=(1, 1), agent_direction=0)


def test_invalid_direction_raises() -> None:
    verifier = GoToVerifier(target_position=(2, 1))

    with pytest.raises(ValueError):
        verifier.is_satisfied(agent_position=(1, 1), agent_direction=9)


def test_evaluate_returns_typed_result() -> None:
    from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env

    env = make_locked_door_probe_env()
    verifier = GoToVerifier(target_position=(2, 1), env=env)
    env.reset(seed=0)  # agent at (1,1) facing east: front cell is (2,1)

    result = verifier.evaluate()

    assert result.task_success
    assert not result.terminated
    assert result.reason_code == "target-in-front"


def test_evaluate_without_bound_env_raises() -> None:
    verifier = GoToVerifier(target_position=(2, 1))

    with pytest.raises(RuntimeError, match="environment bound"):
        verifier.evaluate()
