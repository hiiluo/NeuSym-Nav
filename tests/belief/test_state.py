from __future__ import annotations

from neuro_symbolic_vln.belief.state import BeliefMap
from neuro_symbolic_vln.contracts import (
    Evidence,
    GroundAtom,
    Provenance,
    TriValue,
)


def _make_evidence(
    evidence_id: str,
    predicate: str = "passable",
    args: tuple[str, ...] = ("loc_0",),
    polarity: bool = True,
    reliability: float = 1.0,
    observed_step: int = 0,
    stale_after_steps: int | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        atom=GroundAtom(predicate, args),
        polarity=polarity,
        reliability=reliability,
        observed_step=observed_step,
        stale_after_steps=stale_after_steps,
        source="local_sensor",
        provenance=Provenance(
            episode_id="ep-1",
            observation_id=f"obs-{observed_step}",
            sensor_model_id="local_categorical",
            local_cell=None,
            corruption_channel=None,
        ),
    )


# Case 1: unseen/drop -> UNKNOWN
def test_unseen_atom_is_unknown() -> None:
    belief = BeliefMap()
    atom = GroundAtom("passable", ("loc_9",))

    record = belief.get(atom)
    assert record.value is TriValue.UNKNOWN
    assert record.reliability is None
    assert record.last_observed_step is None
    assert record.stale is False
    assert record.evidence_ids == ()
    assert record.conflict_reason is None
    assert atom not in belief


# Case 2: accepted positive -> TRUE
def test_accepted_positive_is_true() -> None:
    belief = BeliefMap()
    atom = GroundAtom("passable", ("loc_1",))
    ev = _make_evidence(
        "ev-pos", predicate="passable", args=("loc_1",), polarity=True, reliability=1.0
    )

    belief.merge(ev)

    record = belief.get(atom)
    assert record.value is TriValue.TRUE
    assert record.reliability == 1.0
    assert record.last_observed_step == 0
    assert record.stale is False
    assert record.evidence_ids == ("ev-pos",)
    assert record.conflict_reason is None
    assert atom in belief


# Case 3: accepted negative -> FALSE
def test_accepted_negative_is_false() -> None:
    belief = BeliefMap()
    atom = GroundAtom("passable", ("loc_wall",))
    ev = _make_evidence(
        "ev-neg",
        predicate="passable",
        args=("loc_wall",),
        polarity=False,
        reliability=1.0,
    )

    belief.merge(ev)

    record = belief.get(atom)
    assert record.value is TriValue.FALSE
    assert record.reliability == 1.0
    assert record.last_observed_step == 0
    assert record.stale is False
    assert record.evidence_ids == ("ev-neg",)
    assert record.conflict_reason is None


# Case 4: conflicts preserve both evidence IDs
def test_conflicts_preserve_both_evidence_ids() -> None:
    belief = BeliefMap()
    atom = GroundAtom("passable", ("loc_2",))
    ev_pos = _make_evidence(
        "ev-pos-1",
        predicate="passable",
        args=("loc_2",),
        polarity=True,
        reliability=1.0,
    )
    ev_neg = _make_evidence(
        "ev-neg-1",
        predicate="passable",
        args=("loc_2",),
        polarity=False,
        reliability=0.8,
    )

    belief.merge(ev_pos)
    assert belief.get(atom).value is TriValue.TRUE

    belief.merge(ev_neg)
    record = belief.get(atom)

    assert record.value is TriValue.UNKNOWN
    assert record.conflict_reason == "contradictory_polarity"
    assert "ev-pos-1" in record.evidence_ids
    assert "ev-neg-1" in record.evidence_ids
    assert len(record.evidence_ids) == 2
    assert record.reliability == 0.8


def test_conflict_from_negative_to_positive() -> None:
    belief = BeliefMap()
    atom = GroundAtom("door-open", ("red-door",))
    ev_neg = _make_evidence(
        "ev-1", predicate="door-open", args=("red-door",), polarity=False
    )
    ev_pos = _make_evidence(
        "ev-2", predicate="door-open", args=("red-door",), polarity=True
    )

    belief.merge(ev_neg)
    assert belief.get(atom).value is TriValue.FALSE

    belief.merge(ev_pos)
    record = belief.get(atom)
    assert record.value is TriValue.UNKNOWN
    assert record.conflict_reason == "contradictory_polarity"
    assert set(record.evidence_ids) == {"ev-1", "ev-2"}


def test_multiple_consistent_evidences_accumulate_ids() -> None:
    belief = BeliefMap()
    atom = GroundAtom("passable", ("loc_3",))
    ev1 = _make_evidence(
        "ev-1", predicate="passable", args=("loc_3",), polarity=True, observed_step=1
    )
    ev2 = _make_evidence(
        "ev-2", predicate="passable", args=("loc_3",), polarity=True, observed_step=2
    )

    belief.merge_all((ev1, ev2))

    record = belief.get(atom)
    assert record.value is TriValue.TRUE
    assert record.last_observed_step == 2
    assert set(record.evidence_ids) == {"ev-1", "ev-2"}
    assert record.conflict_reason is None


# Case 5: dynamic facts stale after declared steps
def test_dynamic_facts_stale_after_declared_steps() -> None:
    belief = BeliefMap()
    door_atom = GroundAtom("door-open", ("door_1",))
    wall_atom = GroundAtom("wall", ("loc_w",))

    # Door state is dynamic: stale_after_steps = 3, observed at step 1
    ev_door = _make_evidence(
        "ev-door",
        predicate="door-open",
        args=("door_1",),
        polarity=True,
        observed_step=1,
        stale_after_steps=3,
    )
    # Wall is static: stale_after_steps = None, observed at step 1
    ev_wall = _make_evidence(
        "ev-wall",
        predicate="wall",
        args=("loc_w",),
        polarity=True,
        observed_step=1,
        stale_after_steps=None,
    )

    belief.merge_all((ev_door, ev_wall))

    # At step 2: 1 step elapsed -> not stale
    belief.update_staleness(2)
    assert belief.get(door_atom).stale is False
    assert belief.get(wall_atom).stale is False

    # At step 3: 2 steps elapsed -> not stale
    belief.update_staleness(3)
    assert belief.get(door_atom).stale is False
    assert belief.get(wall_atom).stale is False

    # At step 4: 3 steps elapsed -> dynamic door becomes stale!
    belief.update_staleness(4)
    assert belief.get(door_atom).stale is True
    assert belief.get(door_atom).value is TriValue.TRUE  # value preserved
    assert belief.get(wall_atom).stale is False  # static never stale

    # Fresh observation at step 5 resets stale to False
    ev_door_fresh = _make_evidence(
        "ev-door-fresh",
        predicate="door-open",
        args=("door_1",),
        polarity=True,
        observed_step=5,
        stale_after_steps=3,
    )
    belief.merge(ev_door_fresh)
    assert belief.get(door_atom).stale is False
    assert belief.get(door_atom).last_observed_step == 5


# Case 6: failed move invalidates affected facts
def test_failed_move_invalidates_affected_facts() -> None:
    belief = BeliefMap()
    passable_atom = GroundAtom("passable", ("loc_front",))
    ev = _make_evidence(
        "ev-p",
        predicate="passable",
        args=("loc_front",),
        polarity=True,
        observed_step=1,
    )

    belief.merge(ev)
    assert belief.get(passable_atom).value is TriValue.TRUE

    # Robot attempts move_forward but is blocked -> invalidate affected fact
    belief.invalidate(passable_atom, reason="blocked_move")

    record = belief.get(passable_atom)
    assert record.value is TriValue.UNKNOWN
    assert record.conflict_reason == "blocked_move"
    assert "ev-p" in record.evidence_ids  # provenance preserved


# Case 7: deterministic hash
def test_deterministic_hash() -> None:
    ev_a = _make_evidence(
        "ev-a",
        predicate="robot-at",
        args=("robot", "loc_0"),
        polarity=True,
        observed_step=0,
    )
    ev_b = _make_evidence(
        "ev-b",
        predicate="facing",
        args=("robot", "east"),
        polarity=True,
        observed_step=0,
    )
    ev_c = _make_evidence(
        "ev-c", predicate="passable", args=("loc_1",), polarity=True, observed_step=0
    )

    # Insert in order A, B, C
    map_1 = BeliefMap()
    map_1.merge_all((ev_a, ev_b, ev_c))

    # Insert in different order C, A, B
    map_2 = BeliefMap()
    map_2.merge_all((ev_c, ev_a, ev_b))

    hash_1 = map_1.state_hash()
    hash_2 = map_2.state_hash()

    assert len(hash_1) == 64
    assert hash_1 == hash_2


def test_hash_changes_on_state_modification() -> None:
    belief = BeliefMap()
    ev = _make_evidence(
        "ev-1",
        predicate="passable",
        args=("loc_1",),
        polarity=True,
        observed_step=1,
        stale_after_steps=2,
    )
    belief.merge(ev)
    h1 = belief.state_hash()

    # Staleness change updates hash
    belief.update_staleness(3)
    h2 = belief.state_hash()
    assert h1 != h2

    # Invalidation updates hash
    belief.invalidate(GroundAtom("passable", ("loc_1",)), reason="blocked")
    h3 = belief.state_hash()
    assert h2 != h3
