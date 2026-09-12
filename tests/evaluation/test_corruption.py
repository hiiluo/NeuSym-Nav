import numpy as np

from neuro_symbolic_vln.contracts import Evidence, GroundAtom, Provenance
from neuro_symbolic_vln.evaluation.corruption import (
    CORRUPTION_MODEL_VERSION,
    apply_corruption,
    apply_n1_flip,
    compute_evidence_hash,
    drop_evidence,
    reliability_score,
    substitute_entity,
)


def test_drop_evidence_is_seeded() -> None:
    evidence = tuple(f"ev-{index}" for index in range(20))
    first = drop_evidence(evidence, rate=0.15, seed=17)
    second = drop_evidence(evidence, rate=0.15, seed=17)
    assert first == second
    assert len(first) == 17  # 20 * 0.15 = 3 dropped


def test_drop_evidence_edge_cases() -> None:
    evidence = tuple(f"ev-{i}" for i in range(10))
    assert drop_evidence(evidence, rate=0.0) == evidence
    assert drop_evidence(evidence, rate=1.0) == ()
    assert drop_evidence((), rate=0.15) == ()


def test_reliability_score_bounds_and_distribution() -> None:
    rng = np.random.default_rng(42)
    correct_scores = [reliability_score(correct=True, rng=rng) for _ in range(500)]
    flipped_scores = [reliability_score(correct=False, rng=rng) for _ in range(500)]

    assert all(0.05 <= s <= 0.99 for s in correct_scores)
    assert all(0.05 <= s <= 0.99 for s in flipped_scores)
    assert np.mean(correct_scores) > np.mean(flipped_scores)


def test_substitute_entity_is_typed_and_distinct() -> None:
    rng = np.random.default_rng(42)
    for _ in range(50):
        sub = substitute_entity("red-ball", rng)
        assert sub != "red-ball"
        assert "-" in sub
        color, obj = sub.split("-", 1)
        assert color in ("red", "green", "blue", "purple", "yellow", "grey")
        assert obj in ("key", "ball", "box", "door")


def _make_dummy_evidence(
    idx: int,
    predicate: str = "passable",
    args: tuple[str, ...] = ("loc_0_0",),
    polarity: bool = True,
) -> Evidence:
    return Evidence(
        evidence_id=f"ev-{idx}",
        atom=GroundAtom(predicate, args),
        polarity=polarity,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="local-categorical",
        provenance=Provenance(
            episode_id="ep-1",
            observation_id="obs-1",
            sensor_model_id="local-categorical",
            local_cell=(0, 0),
            corruption_channel=None,
        ),
    )


def test_apply_n1_flip_corrupts_only_eligible_and_seeded() -> None:
    # 20 items: 10 eligible ('passable'), 10 ineligible ('robot-at')
    evs = tuple(
        _make_dummy_evidence(i, "passable", (f"loc_{i}",)) for i in range(10)
    ) + tuple(
        _make_dummy_evidence(i + 10, "robot-at", (f"loc_{i}",)) for i in range(10)
    )

    first_corrupted, first_labels = apply_n1_flip(evs, rate=0.20, seed=42)
    second_corrupted, second_labels = apply_n1_flip(evs, rate=0.20, seed=42)

    assert first_corrupted == second_corrupted
    assert first_labels == second_labels

    # 10 eligible * 0.20 = 2 items flipped
    flipped_ids = [eid for eid, correct in first_labels.items() if not correct]
    assert len(flipped_ids) == 2

    # Ineligible items (robot-at) must NEVER be flipped
    for ev in first_corrupted:
        if ev.atom.predicate == "robot-at":
            assert first_labels[ev.evidence_id] is True
            assert ev.polarity is True


def test_compute_evidence_hash_and_version() -> None:
    assert CORRUPTION_MODEL_VERSION == "1.0"
    evs = tuple(_make_dummy_evidence(i) for i in range(5))
    h1 = compute_evidence_hash(evs)
    h2 = compute_evidence_hash(evs)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_apply_corruption_dispatch() -> None:
    evs = tuple(_make_dummy_evidence(i) for i in range(20))
    clean_evs, clean_labels = apply_corruption(evs, condition="clean")
    assert clean_evs == evs
    assert all(clean_labels.values())

    drop_evs, _ = apply_corruption(evs, condition="N1-DROP-15", seed=42)
    assert len(drop_evs) == 17

    flip_evs, flip_labels = apply_corruption(evs, condition="N1-FLIP-10", seed=42)
    assert len(flip_evs) == 20
    assert sum(not v for v in flip_labels.values()) == 2
