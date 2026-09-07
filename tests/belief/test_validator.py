from __future__ import annotations

from neuro_symbolic_vln.belief.validator import (
    StandardValidator,
    build_committed_planning_state,
    commit_true_facts,
    validate_door_states,
    validate_held_objects,
    validate_occupancy,
    validate_robot_location,
    validate_staleness,
)
from neuro_symbolic_vln.contracts import (
    BeliefRecord,
    Evidence,
    GroundAtom,
    LocationGraph,
    Provenance,
    TriValue,
    ValidationDisposition,
)


def _make_evidence(
    evidence_id: str,
    predicate: str,
    args: tuple[str, ...],
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


# --- Handbook Step 1: validate_robot_location test ---
def test_two_robot_locations_are_rejected() -> None:
    decisions = validate_robot_location(
        (
            GroundAtom("robot-at", ("robot", "loc-1")),
            GroundAtom("robot-at", ("robot", "loc-2")),
        )
    )
    assert {decision.disposition.value for decision in decisions} == {"uncertain"}
    assert all(d.reason_code == "conflict.multiple_robot_locations" for d in decisions)


# --- Standalone Rule Tests ---
def test_validate_held_objects_conflict() -> None:
    decisions = validate_held_objects(
        (
            GroundAtom("holding", ("robot", "red-key")),
            GroundAtom("holding", ("robot", "blue-key")),
        )
    )
    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.multiple_held_objects" for d in decisions)


def test_validate_held_and_handempty_conflict() -> None:
    decisions = validate_held_objects(
        (
            GroundAtom("holding", ("robot", "red-key")),
            GroundAtom("handempty", ("robot",)),
        )
    )
    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.holding_and_handempty" for d in decisions)


def test_validate_door_states_conflict() -> None:
    decisions = validate_door_states(
        (
            GroundAtom("door-open", ("red-door",)),
            GroundAtom("door-locked", ("red-door",)),
        )
    )
    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.door_open_and_locked" for d in decisions)


def test_validate_occupancy_conflict() -> None:
    decisions = validate_occupancy(
        (
            GroundAtom("passable", ("loc-1",)),
            GroundAtom("wall", ("loc-1",)),
        )
    )
    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.passable_and_wall" for d in decisions)


def test_validate_staleness_rejection() -> None:
    ev = _make_evidence(
        "ev-old",
        "door-open",
        ("red-door",),
        observed_step=1,
        stale_after_steps=3,
    )
    decisions = validate_staleness((ev,), current_step=5)
    assert decisions[0].disposition is ValidationDisposition.REJECTED
    assert decisions[0].reason_code == "temporal.stale_dynamic_fact"


# --- Consolidated StandardValidator Tests ---
def test_standard_validator_schema_invalid_arity() -> None:
    validator = StandardValidator()
    ev = _make_evidence("ev-1", "robot-at", ("robot",))  # Arity is 2, got 1
    decisions = validator.validate((ev,), belief={}, current_step=0)

    assert decisions[0].disposition is ValidationDisposition.REJECTED
    assert decisions[0].reason_code == "schema.invalid_arity"


def test_standard_validator_ontology_invalid_heading() -> None:
    validator = StandardValidator()
    ev = _make_evidence("ev-1", "facing", ("robot", "upward"))  # Invalid heading
    decisions = validator.validate((ev,), belief={}, current_step=0)

    assert decisions[0].disposition is ValidationDisposition.REJECTED
    assert decisions[0].reason_code == "ontology.invalid_heading"


def test_standard_validator_staleness_rejection() -> None:
    validator = StandardValidator()
    ev = _make_evidence(
        "ev-1",
        "door-open",
        ("red-door",),
        observed_step=1,
        stale_after_steps=3,
    )
    decisions = validator.validate((ev,), belief={}, current_step=4)  # 4 - 1 >= 3

    assert decisions[0].disposition is ValidationDisposition.REJECTED
    assert decisions[0].reason_code == "temporal.stale_dynamic_fact"


def test_standard_validator_reliability_below_threshold() -> None:
    validator = StandardValidator(min_reliability=0.5)
    ev = _make_evidence("ev-1", "passable", ("loc-1",), reliability=0.3)
    decisions = validator.validate((ev,), belief={}, current_step=0)

    assert decisions[0].disposition is ValidationDisposition.UNCERTAIN
    assert decisions[0].reason_code == "reliability.below_threshold"


def test_standard_validator_two_robot_locations_in_batch() -> None:
    validator = StandardValidator()
    ev1 = _make_evidence("ev-1", "robot-at", ("robot", "loc-1"))
    ev2 = _make_evidence("ev-2", "robot-at", ("robot", "loc-2"))
    decisions = validator.validate((ev1, ev2), belief={}, current_step=0)

    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.multiple_robot_locations" for d in decisions)


def test_standard_validator_conflict_with_existing_belief() -> None:
    validator = StandardValidator()
    # Belief already has robot at loc-1
    belief = {
        GroundAtom("robot-at", ("robot", "loc-1")): BeliefRecord(
            value=TriValue.TRUE,
            reliability=1.0,
            last_observed_step=0,
            stale=False,
            evidence_ids=("prior-ev",),
        )
    }
    # Incoming evidence asserts robot at loc-2
    ev = _make_evidence("ev-2", "robot-at", ("robot", "loc-2"))
    decisions = validator.validate((ev,), belief=belief, current_step=1)

    assert decisions[0].disposition is ValidationDisposition.UNCERTAIN
    assert decisions[0].reason_code == "conflict.multiple_robot_locations"


def test_standard_validator_open_and_locked_door_conflict() -> None:
    validator = StandardValidator()
    ev1 = _make_evidence("ev-1", "door-open", ("red-door",))
    ev2 = _make_evidence("ev-2", "door-locked", ("red-door",))
    decisions = validator.validate((ev1, ev2), belief={}, current_step=0)

    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.door_open_and_locked" for d in decisions)


def test_standard_validator_passable_and_wall_conflict() -> None:
    validator = StandardValidator()
    ev1 = _make_evidence("ev-1", "passable", ("loc-1",), polarity=True)
    ev2 = _make_evidence("ev-2", "wall", ("loc-1",), polarity=True)
    decisions = validator.validate((ev1, ev2), belief={}, current_step=0)

    assert all(d.disposition is ValidationDisposition.UNCERTAIN for d in decisions)
    assert all(d.reason_code == "conflict.passable_and_wall" for d in decisions)


def test_standard_validator_clean_facts_accepted() -> None:
    validator = StandardValidator()
    ev1 = _make_evidence("ev-1", "robot-at", ("robot", "loc-1"))
    ev2 = _make_evidence("ev-2", "facing", ("robot", "east"))
    ev3 = _make_evidence("ev-3", "handempty", ("robot",))
    ev4 = _make_evidence("ev-4", "passable", ("loc-2",))

    decisions = validator.validate((ev1, ev2, ev3, ev4), belief={}, current_step=0)

    assert len(decisions) == 4
    assert all(d.disposition is ValidationDisposition.ACCEPTED for d in decisions)
    assert all(d.reason_code == "valid.clean_fact" for d in decisions)


# --- Commitment and State Building Tests ---
def test_commit_true_facts_filter() -> None:
    validator = StandardValidator()
    ev_pos = _make_evidence("ev-pos", "passable", ("loc-1",), polarity=True)
    ev_neg = _make_evidence("ev-neg", "passable", ("loc-2",), polarity=False)

    decisions = validator.validate((ev_pos, ev_neg), belief={}, current_step=0)
    evidence_by_id = {"ev-pos": ev_pos, "ev-neg": ev_neg}

    committed = commit_true_facts(decisions, evidence_by_id)

    # Only positive accepted fact is committed
    assert GroundAtom("passable", ("loc-1",)) in committed
    assert GroundAtom("passable", ("loc-2",)) not in committed


def test_build_committed_planning_state_determinism() -> None:
    true_facts = frozenset(
        {
            GroundAtom("robot-at", ("robot", "loc-0")),
            GroundAtom("facing", ("robot", "east")),
            GroundAtom("passable", ("loc-1",)),
        }
    )
    graph = LocationGraph(
        nodes=frozenset({"loc-0", "loc-1"}),
        directed_edges=frozenset({("loc-0", "east", "loc-1")}),
        frontier_nodes=frozenset({"loc-1"}),
    )

    state1 = build_committed_planning_state(
        version=1,
        true_facts=true_facts,
        location_graph=graph,
        provenance_by_fact={},
    )
    state2 = build_committed_planning_state(
        version=1,
        true_facts=true_facts,
        location_graph=graph,
        provenance_by_fact={},
    )

    assert len(state1.state_hash) == 64
    assert state1.state_hash == state2.state_hash
    assert state1.true_facts == true_facts
