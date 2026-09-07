from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from neuro_symbolic_vln.contracts import (
    BeliefRecord,
    CommittedPlanningState,
    Evidence,
    GroundAtom,
    LocationGraph,
    ValidationDecision,
    ValidationDisposition,
    Validator,
)

VALID_HEADINGS = frozenset({"north", "east", "south", "west"})

PREDICATE_ARITIES: Mapping[str, int] = {
    "robot-at": 2,
    "facing": 2,
    "turn-right-of": 2,
    "turn-left-of": 2,
    "front-cell": 3,
    "passable": 1,
    "wall": 1,
    "key-at": 2,
    "door-at": 2,
    "door-open": 1,
    "door-locked": 1,
    "handempty": 1,
    "holding": 2,
    "key-opens": 2,
    "target-at": 2,
    "task-satisfied": 0,
}


def validate_robot_location(
    objs: tuple[GroundAtom | Evidence, ...],
) -> tuple[ValidationDecision, ...]:
    """
    Check the uniqueness of the robot's position.
    If the robot is recorded in >= 2 different locations, all decisions are UNCERTAIN.
    """
    locations: set[str] = set()
    items: list[tuple[str, GroundAtom, bool]] = []

    for idx, item in enumerate(objs):
        if isinstance(item, Evidence):
            ev_id = item.evidence_id
            atom = item.atom
            polarity = item.polarity
        else:
            ev_id = f"virtual-ev-{idx}"
            atom = item
            polarity = True

        if atom.predicate == "robot-at" and len(atom.arguments) == 2:
            if polarity:
                locations.add(atom.arguments[1])
            items.append((ev_id, atom, polarity))

    decisions: list[ValidationDecision] = []
    has_conflict = len(locations) > 1

    for ev_id, _atom, polarity in items:
        if not polarity:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.negative_robot_location",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )
        elif has_conflict:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.UNCERTAIN,
                    reason_code="conflict.multiple_robot_locations",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=tuple(
                        e for e, _, _ in items if e != ev_id
                    ),
                )
            )
        else:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.single_robot_location",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )

    return tuple(decisions)


def validate_held_objects(
    objs: tuple[GroundAtom | Evidence, ...],
) -> tuple[ValidationDecision, ...]:
    """Check that the robot can only hold a maximum of one object,
    it cannot be holding and handempty at the same time.
    """
    holding_objs: set[str] = set()
    has_positive_handempty: bool = False
    items: list[tuple[str, GroundAtom, bool]] = []

    for idx, obj in enumerate(objs):
        if isinstance(obj, Evidence):
            ev_id = obj.evidence_id
            atom = obj.atom
            polarity = obj.polarity
        else:
            ev_id = f"virtual-ev-{idx}"
            atom = obj
            polarity = True

        if atom.predicate == "handempty" and len(atom.arguments) == 1:
            if polarity:
                has_positive_handempty = True
            items.append((ev_id, atom, polarity))
        elif atom.predicate == "holding" and len(atom.arguments) == 2:
            if polarity:
                holding_objs.add(atom.arguments[1])
            items.append((ev_id, atom, polarity))

    has_multi_items = len(holding_objs) > 1
    has_handempty_and_holding = has_positive_handempty and (len(holding_objs) > 0)
    has_conflict = has_multi_items or has_handempty_and_holding

    if has_conflict:
        conflict_reason = (
            "conflict.multiple_held_objects"
            if has_multi_items
            else "conflict.holding_and_handempty"
        )

    decisions: list[ValidationDecision] = []

    for ev_id, _atom, polarity in items:
        if not polarity:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.negative_holding_assertion",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )
        elif has_conflict:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.UNCERTAIN,
                    reason_code=conflict_reason,
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=tuple(
                        e for e, _, _ in items if e != ev_id
                    ),
                )
            )
        else:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.held_object_consistent",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )

    return tuple(decisions)


def validate_door_states(
    objs: tuple[GroundAtom | Evidence, ...],
) -> tuple[ValidationDecision, ...]:
    """The door cannot be opened and locked simultaneously."""
    locked_doors: set[str] = set()
    opened_doors: set[str] = set()
    door_locations: dict[str, set[str]] = {}
    items: list[tuple[str, GroundAtom, bool, str]] = []

    for idx, obj in enumerate(objs):
        if isinstance(obj, Evidence):
            ev_id = obj.evidence_id
            atom = obj.atom
            polarity = obj.polarity
        else:
            ev_id = f"virtual-ev-{idx}"
            atom = obj
            polarity = True

        if atom.predicate == "door-locked" and len(atom.arguments) == 1:
            door_name = atom.arguments[0]
            if polarity:
                locked_doors.add(door_name)
            items.append((ev_id, atom, polarity, door_name))
        elif atom.predicate == "door-open" and len(atom.arguments) == 1:
            door_name = atom.arguments[0]
            if polarity:
                opened_doors.add(door_name)
            items.append((ev_id, atom, polarity, door_name))
        elif atom.predicate == "door-at" and len(atom.arguments) == 2:
            door_name = atom.arguments[0]
            loc = atom.arguments[1]
            if polarity:
                door_locations.setdefault(door_name, set()).add(loc)
            items.append((ev_id, atom, polarity, door_name))

    # Conflict 1: The door is locked as well as opened
    conflict_open_locked = opened_doors.intersection(locked_doors)

    # Conflict 2: The door in more than one location
    conflict_multi_loc = {d for d, locs in door_locations.items() if len(locs) > 1}

    decisions: list[ValidationDecision] = []

    for ev_id, atom, polarity, door_name in items:
        if not polarity:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.negative_door_state",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )
        elif (
            atom.predicate in ("door-open", "door-locked")
            and door_name in conflict_open_locked
        ):
            conflict_ids = tuple(
                e
                for e, a, p, d in items
                if d == door_name
                and e != ev_id
                and p
                and a.predicate in ("door-open", "door-locked")
            )
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.UNCERTAIN,
                    reason_code="conflict.door_open_and_locked",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=conflict_ids,
                )
            )
        elif atom.predicate == "door-at" and door_name in conflict_multi_loc:
            conflict_ids = tuple(
                e
                for e, a, p, d in items
                if d == door_name and e != ev_id and p and a.predicate == "door-at"
            )
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.UNCERTAIN,
                    reason_code="conflict.multiple_door_locations",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=conflict_ids,
                )
            )
        else:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.door_state_consistent",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )

    return tuple(decisions)


def validate_occupancy(
    objs: tuple[GroundAtom | Evidence, ...],
) -> tuple[ValidationDecision, ...]:
    """
    Spatial consistency check (Occupancy consistency):
    A location cannot simultaneously be a passable cell (passable) and a wall (wall).
    """
    positive_passable_locs: set[str] = set()
    blocker_locs: set[str] = set()
    items: list[tuple[str, GroundAtom, bool, str, bool]] = []

    for idx, obj in enumerate(objs):
        if isinstance(obj, Evidence):
            ev_id = obj.evidence_id
            atom = obj.atom
            polarity = obj.polarity
        else:
            ev_id = f"virtual-ev-{idx}"
            atom = obj
            polarity = True

        if atom.predicate == "passable" and len(atom.arguments) == 1:
            loc = atom.arguments[0]
            if polarity:
                positive_passable_locs.add(loc)
                items.append((ev_id, atom, polarity, loc, False))
        elif atom.predicate == "wall" and len(atom.arguments) == 1:
            loc = atom.arguments[0]
            if polarity:
                blocker_locs.add(loc)
                items.append((ev_id, atom, polarity, loc, True))

    conflict_locations = positive_passable_locs.intersection(blocker_locs)

    decisions: list[ValidationDecision] = []

    for ev_id, _atom, _polarity, loc, _is_blocker in items:
        if loc in conflict_locations:
            conflict_ids = tuple(
                e for e, _, _, location, _ in items if location == loc and e != ev_id
            )
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.UNCERTAIN,
                    reason_code="conflict.passable_and_wall",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=conflict_ids,
                )
            )
        else:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.occupancy_consistent",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )

    return tuple(decisions)


def validate_staleness(
    objs: tuple[GroundAtom | Evidence, ...],
    current_step: int,
    belief: Mapping[GroundAtom, BeliefRecord] | None = None,
) -> tuple[ValidationDecision, ...]:
    """
    Check the validity period (Staleness) of the facts/evidence:
    If the dynamic proof exceeds stale_after_steps or the stale=True flag in belief,
    the proof is REJECTED to prevent commits from being made to the plan.
    """
    decisions: list[ValidationDecision] = []

    for idx, obj in enumerate(objs):
        if isinstance(obj, Evidence):
            ev_id = obj.evidence_id
            atom = obj.atom
            observed_step = obj.observed_step
            stale_limit = obj.stale_after_steps
        else:
            ev_id = f"virtual-ev-{idx}"
            atom = obj
            observed_step = current_step
            stale_limit = None

        is_stale = False

        if stale_limit is not None:
            if current_step - observed_step >= stale_limit:
                is_stale = True

        if belief is not None:
            record = belief.get(atom)
            if record is not None and record.stale:
                is_stale = True

        if is_stale:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.REJECTED,
                    reason_code="temporal.stale_dynamic_fact",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )
        else:
            decisions.append(
                ValidationDecision(
                    evidence_id=ev_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.fresh_fact",
                    supporting_evidence_ids=(),
                    conflicting_evidence_ids=(),
                )
            )

    return tuple(decisions)


class StandardValidator(Validator):
    """Consolidated validator executing all 7 layers of checks in an efficient,
    two-pass scan without redundant per-rule iterations.
    """

    def __init__(self, min_reliability: float = 0.5) -> None:
        self.min_reliability = min_reliability

    def validate(
        self,
        evidence: tuple[Evidence, ...],
        belief: Mapping[GroundAtom, BeliefRecord],
        current_step: int,
    ) -> tuple[ValidationDecision, ...]:
        """Validate a batch of evidence against ontology, consistency, staleness,
        and belief state.
        """
        # --- PASS 1: Aggregate active positive assertions and conflict sets ---
        robot_locs: set[str] = set()
        held_items: set[str] = set()
        has_handempty: bool = False
        open_doors: set[str] = set()
        locked_doors: set[str] = set()
        passable_locs: set[str] = set()
        blocker_locs: set[str] = set()
        door_locations: dict[str, set[str]] = {}
        key_locations: dict[str, set[str]] = {}

        # 1.1 From incoming evidence
        for ev in evidence:
            atom = ev.atom
            if ev.polarity:
                if atom.predicate == "robot-at" and len(atom.arguments) == 2:
                    robot_locs.add(atom.arguments[1])
                elif atom.predicate == "handempty" and len(atom.arguments) == 1:
                    has_handempty = True
                elif atom.predicate == "holding" and len(atom.arguments) == 2:
                    held_items.add(atom.arguments[1])
                elif atom.predicate == "door-open" and len(atom.arguments) == 1:
                    open_doors.add(atom.arguments[0])
                elif atom.predicate == "door-locked" and len(atom.arguments) == 1:
                    locked_doors.add(atom.arguments[0])
                elif atom.predicate == "passable" and len(atom.arguments) == 1:
                    passable_locs.add(atom.arguments[0])
                elif atom.predicate == "wall" and len(atom.arguments) == 1:
                    blocker_locs.add(atom.arguments[0])
                elif atom.predicate == "door-at" and len(atom.arguments) == 2:
                    door_locations.setdefault(atom.arguments[0], set()).add(
                        atom.arguments[1]
                    )
                elif atom.predicate == "key-at" and len(atom.arguments) == 2:
                    key_locations.setdefault(atom.arguments[0], set()).add(
                        atom.arguments[1]
                    )
            else:
                if atom.predicate == "passable" and len(atom.arguments) == 1:
                    blocker_locs.add(atom.arguments[0])

        # 1.2 From existing belief (clean non-stale true facts)
        for atom, rec in belief.items():
            if (
                rec.value.value == "true"
                and not rec.stale
                and rec.conflict_reason is None
            ):
                if atom.predicate == "robot-at" and len(atom.arguments) == 2:
                    robot_locs.add(atom.arguments[1])
                elif atom.predicate == "handempty" and len(atom.arguments) == 1:
                    has_handempty = True
                elif atom.predicate == "holding" and len(atom.arguments) == 2:
                    held_items.add(atom.arguments[1])
                elif atom.predicate == "door-open" and len(atom.arguments) == 1:
                    open_doors.add(atom.arguments[0])
                elif atom.predicate == "door-locked" and len(atom.arguments) == 1:
                    locked_doors.add(atom.arguments[0])
                elif atom.predicate == "passable" and len(atom.arguments) == 1:
                    passable_locs.add(atom.arguments[0])
                elif atom.predicate == "wall" and len(atom.arguments) == 1:
                    blocker_locs.add(atom.arguments[0])
                elif atom.predicate == "door-at" and len(atom.arguments) == 2:
                    door_locations.setdefault(atom.arguments[0], set()).add(
                        atom.arguments[1]
                    )
                elif atom.predicate == "key-at" and len(atom.arguments) == 2:
                    key_locations.setdefault(atom.arguments[0], set()).add(
                        atom.arguments[1]
                    )

        # Precompute conflict conditions in O(1) set lookups
        has_multi_robot_locs = len(robot_locs) > 1
        has_multi_held = len(held_items) > 1
        has_holding_and_handempty = has_handempty and len(held_items) > 0
        conflicting_open_locked = open_doors.intersection(locked_doors)
        conflicting_occupancy = passable_locs.intersection(blocker_locs)
        conflicting_door_locs = {
            d for d, locs in door_locations.items() if len(locs) > 1
        }
        conflicting_key_locs = {k for k, locs in key_locations.items() if len(locs) > 1}

        # --- PASS 2: Evaluate each evidence item in order ---
        decisions: list[ValidationDecision] = []

        for ev in evidence:
            atom = ev.atom

            # Layer 1: Schema Check (Arity, Predicate, Reliability bounds)
            if atom.predicate not in PREDICATE_ARITIES:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="schema.invalid_predicate",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            expected_arity = PREDICATE_ARITIES[atom.predicate]
            if len(atom.arguments) != expected_arity:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="schema.invalid_arity",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if not (0.0 <= ev.reliability <= 1.0):
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="schema.invalid_reliability",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Layer 2: Ontology / Entity Typing Check
            if atom.predicate == "facing" and atom.arguments[1] not in VALID_HEADINGS:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="ontology.invalid_heading",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if (
                atom.predicate in ("robot-at", "facing", "handempty", "holding")
                and atom.arguments[0] != "robot"
            ):
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="ontology.invalid_robot_entity",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Layer 5: Temporal / Staleness Check
            is_stale = False
            if ev.stale_after_steps is not None and (
                current_step - ev.observed_step >= ev.stale_after_steps
            ):
                is_stale = True
            belief_rec = belief.get(atom)
            if belief_rec is not None and belief_rec.stale:
                is_stale = True

            if is_stale:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.REJECTED,
                        reason_code="temporal.stale_dynamic_fact",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Layer 6: Reliability Threshold Check
            if ev.reliability < self.min_reliability:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="reliability.below_threshold",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Layer 7: Unresolved Prior Belief Conflict Check
            if belief_rec is not None and belief_rec.conflict_reason is not None:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.unresolved_belief_conflict",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=belief_rec.evidence_ids,
                    )
                )
                continue

            # Negative Evidence pass-through
            if not ev.polarity:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.ACCEPTED,
                        reason_code="valid.negative_assertion",
                        supporting_evidence_ids=(ev.evidence_id,),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Layers 3 & 4: Uniqueness, Exclusivity, and Occupancy Consistency
            if atom.predicate == "robot-at" and has_multi_robot_locs:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.multiple_robot_locations",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if atom.predicate == "holding" and has_multi_held:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.multiple_held_objects",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if atom.predicate in ("holding", "handempty") and has_holding_and_handempty:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.holding_and_handempty",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if (
                atom.predicate in ("door-open", "door-locked")
                and atom.arguments[0] in conflicting_open_locked
            ):
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.door_open_and_locked",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if (
                atom.predicate == "door-at"
                and atom.arguments[0] in conflicting_door_locs
            ):
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.multiple_door_locations",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if atom.predicate == "key-at" and atom.arguments[0] in conflicting_key_locs:
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.multiple_key_locations",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            if (
                atom.predicate in ("passable", "wall")
                and atom.arguments[0] in conflicting_occupancy
            ):
                decisions.append(
                    ValidationDecision(
                        evidence_id=ev.evidence_id,
                        disposition=ValidationDisposition.UNCERTAIN,
                        reason_code="conflict.passable_and_wall",
                        supporting_evidence_ids=(),
                        conflicting_evidence_ids=(),
                    )
                )
                continue

            # Passed all layers -> Clean accepted fact
            decisions.append(
                ValidationDecision(
                    evidence_id=ev.evidence_id,
                    disposition=ValidationDisposition.ACCEPTED,
                    reason_code="valid.clean_fact",
                    supporting_evidence_ids=(ev.evidence_id,),
                    conflicting_evidence_ids=(),
                )
            )

        return tuple(decisions)


def commit_true_facts(
    decisions: tuple[ValidationDecision, ...],
    evidence_by_id: Mapping[str, Evidence],
) -> frozenset[GroundAtom]:
    """Return the set of grounded atoms that are verified and accepted."""
    return frozenset(
        evidence_by_id[decision.evidence_id].atom
        for decision in decisions
        if decision.disposition is ValidationDisposition.ACCEPTED
        and evidence_by_id[decision.evidence_id].polarity
    )


def build_committed_planning_state(
    version: int,
    true_facts: frozenset[GroundAtom],
    location_graph: LocationGraph,
    provenance_by_fact: Mapping[GroundAtom, tuple[str, ...]],
    unresolved_required_facts: frozenset[GroundAtom] = frozenset(),
) -> CommittedPlanningState:
    """Build a deterministic CommittedPlanningState with canonical hash."""
    sorted_facts = sorted((a.predicate, a.arguments) for a in true_facts)
    payload = json.dumps(sorted_facts, sort_keys=True)
    state_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return CommittedPlanningState(
        version=version,
        state_hash=state_hash,
        true_facts=true_facts,
        unresolved_required_facts=unresolved_required_facts,
        provenance_by_fact=provenance_by_fact,
        location_graph=location_graph,
    )
