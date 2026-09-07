from neuro_symbolic_vln.contracts import (
    EpisodeSpec,
    PrimitiveAction,
    StepResult,
)
from neuro_symbolic_vln.env.minigrid_adapter import MiniGridAdapter
from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env
from neuro_symbolic_vln.env.verifier import GoToVerifier


def test_adapter_step_returns_step_result() -> None:
    env = make_locked_door_probe_env()

    episode = EpisodeSpec(
        episode_id="test-episode",
        family="test-family",
        instruction="go to the door",
        public_action_budget=36,
        manifest_hash="test-hash",
    )

    verifier = GoToVerifier(target_position=(3, 1), env=env)

    adapter = MiniGridAdapter(env, episode, verifier)

    adapter.reset(seed=0)

    result = adapter.step(PrimitiveAction(name="move_forward"))

    print(f"Step result: {result}")

    assert isinstance(result, StepResult)


def test_adapter_step_returns_task_success() -> None:
    env = make_locked_door_probe_env()

    episode = EpisodeSpec(
        episode_id="test-episode",
        family="test-family",
        instruction="go to the door",
        public_action_budget=36,
        manifest_hash="test-hash",
    )

    verifier = GoToVerifier(target_position=(3, 1), env=env)

    adapter = MiniGridAdapter(env, episode, verifier)

    adapter.reset(seed=0)

    pickup = adapter.step(PrimitiveAction(name="pickup"))
    assert pickup.action_succeeded
    assert not pickup.task_success

    result = adapter.step(PrimitiveAction(name="move_forward"))

    print(f"Step result: {result}")

    assert isinstance(result, StepResult)
    assert result.action_succeeded
