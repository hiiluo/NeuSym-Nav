from __future__ import annotations

import pytest

from neuro_symbolic_vln.belief.state import BeliefMap
from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    Evidence,
    GroundAtom,
    ObservationPacket,
    Provenance,
    TriValue,
)
from neuro_symbolic_vln.evaluation.corruption import (
    VALID_COLORS,
    VALID_OBJECTS,
    apply_corruption,
    apply_n1_flip,
    drop_evidence,
)
from neuro_symbolic_vln.perception.observation_decoder import (
    LocalObservationDecoder,
    SensorModelSpec,
    decode_view,
)


def _make_cell(
    object_index: int = 1,
    color_index: int = 0,
    state_index: int = 0,
    visible: bool = True,
) -> CategoricalCell:
    return CategoricalCell(
        object_index=object_index,
        color_index=color_index,
        state_index=state_index,
        visible=visible,
    )


def _make_view(
    visible_predicate=lambda x, y: True,
    overrides: dict[tuple[int, int], CategoricalCell] | None = None,
) -> CategoricalView:
    overrides = overrides or {}
    columns = []
    for x in range(7):
        column = []
        for y in range(7):
            if (x, y) in overrides:
                column.append(overrides[(x, y)])
            else:
                is_vis = visible_predicate(x, y)
                column.append(_make_cell(object_index=1, visible=is_vis))
        columns.append(tuple(column))
    return CategoricalView(cells_by_x=tuple(columns))


def _make_packet(
    view: CategoricalView, heading: str = "east", step: int = 0
) -> ObservationPacket:
    return ObservationPacket(
        observation_id="ep-test:1",
        step=step,
        categorical_view=view,
        heading=heading,
        carried_entity=None,
        instruction="go forward",
    )


def _resolve(xy: tuple[int, int]) -> str:
    return f"loc_{xy[0]}_{xy[1]}"


def test_corruption_does_not_inject_unseen_cells() -> None:
    """Visibility boundary test:

    Cells marked visible=False produce no evidence.
    N1 corruption must never inject, invent or hallucinate facts for unseen cells.
    Every location referenced in corrupted evidence must be in the visible set.
    """
    # Only top-left 3x3 cells are visible, rest are unseen
    view = _make_view(visible_predicate=lambda x, y: x < 3 and y < 3)
    packet = _make_packet(view)

    original_evidence = decode_view(
        packet,
        episode_id="ep-test",
        pose_x=0,
        pose_y=0,
        resolve_location=_resolve,
    )
    assert len(original_evidence) > 0

    visible_locations = {
        ev.atom.arguments[-1] for ev in original_evidence if len(ev.atom.arguments) > 0
    }

    # Apply N1-FLIP
    corrupted_flip, _ = apply_n1_flip(original_evidence, rate=0.50, seed=42)
    corrupted_locations = {
        ev.atom.arguments[-1] for ev in corrupted_flip if len(ev.atom.arguments) > 0
    }
    assert corrupted_locations.issubset(visible_locations)

    # Apply N1-DROP
    corrupted_drop = drop_evidence(original_evidence, rate=0.50, seed=42)
    drop_locations = {
        ev.atom.arguments[-1] for ev in corrupted_drop if len(ev.atom.arguments) > 0
    }
    assert drop_locations.issubset(visible_locations)


def test_ineligible_predicates_strictly_unmodified() -> None:
    """Eligibility boundary test:

    Non-eligible predicates (e.g., robot state: robot-at, facing, holding)
    must NEVER be altered by N1-FLIP, even with rate=1.0.
    """
    visible_ev = Evidence(
        evidence_id="ev-vis-1",
        atom=GroundAtom("passable", ("loc_1_0",)),
        polarity=True,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="local-categorical",
        provenance=Provenance("ep-1", "obs-1", "sensor", (1, 0), None),
    )
    ineligible_ev = Evidence(
        evidence_id="ev-robot-1",
        atom=GroundAtom("robot-at", ("robot", "loc_0_0")),
        polarity=True,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="dead-reckoning",
        provenance=Provenance("ep-1", "obs-1", "odometry", None, None),
    )

    evidences = (visible_ev, ineligible_ev)
    corrupted, labels = apply_n1_flip(evidences, rate=1.0, seed=42)

    # Ineligible record must remain 100% untouched in atom and polarity
    corrupted_ineligible = next(e for e in corrupted if e.evidence_id == "ev-robot-1")
    assert corrupted_ineligible.atom == ineligible_ev.atom
    assert corrupted_ineligible.polarity == ineligible_ev.polarity
    assert labels["ev-robot-1"] is True


def test_no_hidden_correctness_leak_in_agent_input() -> None:
    """Trust boundary test:

    The public Evidence items received by the agent must NOT contain any hidden
    labels, flags, or oracle information indicating whether they were corrupted.
    """
    view = _make_view(overrides={(3, 5): _make_cell(object_index=2)})  # wall in front
    packet = _make_packet(view)
    original_evidence = decode_view(
        packet,
        episode_id="ep-1",
        pose_x=0,
        pose_y=0,
        resolve_location=_resolve,
    )

    corrupted_evidence, hidden_labels = apply_n1_flip(
        original_evidence, rate=0.20, seed=42
    )

    # Public agent objects must NOT contain correctness flags
    for ev in corrupted_evidence:
        assert not hasattr(ev, "correct")
        assert not hasattr(ev, "is_correct")
        assert not hasattr(ev, "hidden_label")
        assert not hasattr(ev, "is_flipped")
        # Provenance only records the generic corruption channel, not true correctness
        assert ev.provenance.corruption_channel == "N1-FLIP-10"
        assert 0.05 <= ev.reliability <= 0.99

    # Hidden labels are in a separate dictionary for the evaluator sidecar
    assert isinstance(hidden_labels, dict)
    assert all(isinstance(k, str) for k in hidden_labels)
    assert all(isinstance(v, bool) for v in hidden_labels.values())


def test_dropped_evidence_absent_leads_to_unknown_belief() -> None:
    """Belief test:

    Dropped evidence must be absent from the store, and querying
    its atom on the BeliefMap must evaluate to TriValue.UNKNOWN.
    """
    target_atom = GroundAtom("door-at", ("yellow-door", "loc_2_2"))
    original_ev = Evidence(
        evidence_id="ev-door-1",
        atom=target_atom,
        polarity=True,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="local-categorical",
        provenance=Provenance("ep-1", "obs-1", "sensor", (2, 2), None),
    )

    # Drop 100% of this single evidence
    dropped = drop_evidence((original_ev,), rate=1.0, seed=42)
    assert len(dropped) == 0

    # Merge surviving evidence into belief map
    belief_map = BeliefMap()
    for ev in dropped:
        belief_map.merge(ev)

    # Absent evidence must return UNKNOWN
    assert belief_map.get(target_atom).value == TriValue.UNKNOWN


def test_typed_attribute_substitution_entity_validity() -> None:
    """Typed substitution test:

    When an object/key/target atom is flipped, the substituted entity must
    conform to the MiniGrid '{color}-{object}' convention and belong to
    recognized domain colors and objects.
    """
    key_ev = Evidence(
        evidence_id="ev-key-1",
        atom=GroundAtom("key-at", ("red-key", "loc_1_1")),
        polarity=True,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="local-categorical",
        provenance=Provenance("ep-1", "obs-1", "sensor", (1, 1), None),
    )

    # Force flip
    corrupted, labels = apply_n1_flip((key_ev,), rate=1.0, seed=42)
    assert labels["ev-key-1"] is False

    new_entity = corrupted[0].atom.arguments[0]
    assert new_entity != "red-key"
    assert "-" in new_entity
    color, obj = new_entity.split("-", 1)
    assert color in VALID_COLORS
    assert obj in VALID_OBJECTS


def test_decoder_applies_corruption_strictly_after_decoding() -> None:
    """Layering boundary test:

    LocalObservationDecoder must reject non-null corruption channel,
    confirming that N1 corruption is decoupled and applied post-decoding.
    """
    decoder = LocalObservationDecoder(
        episode_id="ep-1",
        pose=lambda: (0, 0),
        resolve_location=_resolve,
    )
    view = _make_view()
    packet = _make_packet(view)

    # Direct decoder call with corruption channel must fail
    with pytest.raises(ValueError, match="N1 corruption is applied after decoding"):
        decoder.decode(
            packet,
            SensorModelSpec(corruption_channel="N1-FLIP-10"),
        )

    # Decoding cleanly first, then applying corruption post-decoding succeeds
    clean_evs = decoder.decode(packet, SensorModelSpec())
    corrupted_evs, _ = apply_corruption(clean_evs, condition="N1-FLIP-10", seed=42)
    assert len(corrupted_evs) == len(clean_evs)
