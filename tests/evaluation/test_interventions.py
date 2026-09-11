from neuro_symbolic_vln.env.tasks import (
    make_goto_goal_probe_env,
    make_locked_door_probe_env,
)
from neuro_symbolic_vln.evaluation.interventions import (
    annotate_intervention,
    apply_intervention,
    build_relock_checkpoint,
    choose_block_intervention,
    choose_relock_intervention,
)
from neuro_symbolic_vln.evaluation.manifests import generate_manifests
from neuro_symbolic_vln.evaluation.oracle import (
    ExactOracle,
    model_from_probe_env,
)


def test_block_intervention_requires_alternate_route() -> None:
    intervention = choose_block_intervention(
        planned_next=(2, 1),
        alternate_route=((1, 2), (2, 2), (3, 2)),
    )
    assert intervention.target == (2, 1)
    assert intervention.recoverable


def test_block_without_alternate_route_is_not_recoverable() -> None:
    intervention = choose_block_intervention(
        planned_next=(2, 1),
        alternate_route=(),
    )
    assert not intervention.recoverable


def test_same_seed_produces_same_intervention_hash() -> None:
    first = choose_block_intervention((2, 1), ((1, 2),), seed=7)
    second = choose_block_intervention((2, 1), ((1, 2),), seed=7)
    other = choose_block_intervention((2, 1), ((1, 2),), seed=8)

    assert first == second
    assert first.hash() == second.hash()
    assert first.hash() != other.hash()


def test_block_intervention_recoverable_via_alternate_route() -> None:
    env = make_goto_goal_probe_env(
        target_color="green", agent_dir=0, distractor_pos=(3, 3)
    )
    env.reset(seed=0)

    pre = ExactOracle().solve(
        model_from_probe_env(env, "goto_type_color", (3, 1))
    )
    spec = choose_block_intervention(
        (2, 1), ((1, 2), (2, 2), (3, 2)), seed=0
    )
    annotation = annotate_intervention(env, "goto_type_color", (3, 1), spec, pre)

    assert annotation.recoverable
    assert annotation.pre_optimum == 1
    assert annotation.post_optimum is not None
    assert annotation.post_optimum > annotation.pre_optimum


def test_blocking_all_approach_cells_is_unsolvable() -> None:
    # The probe room is an open 4x3 ring, so no single-cell block can
    # disconnect it: blocking the door cell still leaves the south
    # approach at (4, 2). Blocking EVERY approach cell to the target
    # does disconnect it — the oracle must report unsolvable, and the
    # generator rejects such interventions.
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    apply_intervention(
        env, choose_block_intervention((3, 1), (), seed=0)
    )
    apply_intervention(
        env, choose_block_intervention((4, 2), (), seed=0)
    )

    solution = ExactOracle().solve(
        model_from_probe_env(env, "key_door_goal", (4, 1))
    )
    assert not solution.solvable
    assert solution.optimal_primitive_actions is None


def test_relock_with_carried_key_is_recoverable() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    pre = ExactOracle().solve(
        model_from_probe_env(env, "key_door_goal", (4, 1))
    )
    spec = choose_relock_intervention((3, 1), seed=0)
    annotation = annotate_intervention(env, "key_door_goal", (4, 1), spec, pre)

    assert annotation.recoverable
    # From the post-toggle checkpoint: toggle again + forward.
    assert annotation.post_optimum == 2


def test_relock_checkpoint_reaches_post_toggle_state() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)

    build_relock_checkpoint(env)

    door = env.unwrapped.grid.get(3, 1)
    assert door.is_open
    assert env.unwrapped.carrying is not None
    assert tuple(env.unwrapped.agent_pos) == (2, 1)


def _rq2_config() -> dict:
    return {
        "generator_version": "minigrid-core-v1",
        "public_action_budget": 32,
        "splits": {
            "rq2_test": {
                "interventions": True,
                "combos": {
                    "goto_type_color": {"start": 40, "count": 40},
                    "key_door_goal": {"start": 32, "count": 40},
                },
            }
        },
    }


def test_rq2_manifests_carry_interventions_in_sidecar_only() -> None:
    first = generate_manifests(_rq2_config())
    second = generate_manifests(_rq2_config())

    assert len(first.public_manifests) == 80
    assert len(first.sidecars) == 80

    # The public input never carries target/effect/optimum labels.
    for manifest in first.public_manifests:
        public = manifest.to_dict()
        assert "intervention" not in public
        assert "recoverable" not in public
        assert "target" not in public
        assert "post_optimum" not in public

    # Every sidecar holds an oracle-confirmed recoverable intervention.
    for sidecar in first.sidecars:
        assert sidecar.intervention is not None
        assert sidecar.intervention["recoverable"] is True
        assert sidecar.intervention["post_optimum"] is not None
        assert sidecar.intervention["pre_optimum"] is not None

    # Paired V1R0/V1R1 runs share the identical checkpoint and seed.
    assert [s.intervention for s in first.sidecars] == [
        s.intervention for s in second.sidecars
    ]
