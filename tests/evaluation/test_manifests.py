import pytest

from neuro_symbolic_vln.contracts import EpisodeSpec
from neuro_symbolic_vln.evaluation.manifests import (
    ManifestGenerationError,
    generate_manifests,
    stable_hash,
)


def _config(smoke_count: int = 10, dev_start: int = 10, dev_count: int = 20) -> dict:
    return {
        "generator_version": "minigrid-core-v1",
        "public_action_budget": 32,
        "splits": {
            "smoke": {"combo_start": 0, "combo_count": smoke_count},
            "dev": {"combo_start": dev_start, "combo_count": dev_count},
        },
    }


def test_stable_hash_is_deterministic_and_canonical() -> None:
    first = stable_hash({"b": 1, "a": [2, 3]})
    second = stable_hash({"a": [2, 3], "b": 1})
    assert first == second
    assert first.startswith("sha256:")
    assert first != stable_hash({"a": [2, 3], "b": 2})


def test_generate_twice_produces_identical_hashes() -> None:
    config = _config()

    first = generate_manifests(config)
    second = generate_manifests(config)

    assert [m.manifest_hash() for m in first.public_manifests] == [
        m.manifest_hash() for m in second.public_manifests
    ]
    assert [m.layout_hash for m in first.public_manifests] == [
        m.layout_hash for m in second.public_manifests
    ]


def test_all_generated_episodes_are_solvable() -> None:
    result = generate_manifests(_config())

    assert len(result.public_manifests) == 60  # 2 families x (10 + 20)
    assert all(sidecar.solvable for sidecar in result.sidecars)
    assert all(
        sidecar.optimal_primitive_actions is not None
        for sidecar in result.sidecars
    )


def test_cross_split_layout_collision_is_rejected() -> None:
    # Overlapping combo ranges force the same layout into both splits.
    config = _config(smoke_count=2, dev_start=1, dev_count=2)

    with pytest.raises(ManifestGenerationError, match="already used"):
        generate_manifests(config)


def test_layout_hashes_are_unique_within_a_split() -> None:
    result = generate_manifests(_config())

    for split in ("smoke", "dev"):
        hashes = [
            m.layout_hash
            for m in result.public_manifests
            if m.split == split
        ]
        assert len(hashes) == len(set(hashes))


def test_episode_spec_carries_no_sidecar_fields() -> None:
    result = generate_manifests(_config())
    spec = result.public_manifests[0].to_episode_spec()

    assert isinstance(spec, EpisodeSpec)
    assert set(spec.__dataclass_fields__) == {
        "episode_id",
        "family",
        "instruction",
        "public_action_budget",
        "manifest_hash",
    }
    assert "optimal_primitive_actions" not in spec.__dataclass_fields__
    assert "solvable" not in spec.__dataclass_fields__
