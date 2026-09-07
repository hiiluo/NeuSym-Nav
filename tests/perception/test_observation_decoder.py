import pytest

from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    GroundAtom,
    ObservationPacket,
)
from neuro_symbolic_vln.perception import observation_decoder
from neuro_symbolic_vln.perception.observation_decoder import (
    LocalObservationDecoder,
    SensorModelSpec,
    decode_view,
    egocentric_delta_to_world,
)


def _make_cell(
    object_index: int,
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
    object_index: int = 1,
    visible: bool = True,
    overrides: dict[tuple[int, int], CategoricalCell] | None = None,
) -> CategoricalView:
    overrides = overrides or {}
    columns = []
    for x in range(7):
        column = [
            overrides.get((x, y), _make_cell(object_index, visible=visible))
            for y in range(7)
        ]
        columns.append(tuple(column))
    return CategoricalView(cells_by_x=tuple(columns))


def _make_packet(
    view: CategoricalView, heading: str = "east", step: int = 0
) -> ObservationPacket:
    return ObservationPacket(
        observation_id="ep-1:1",
        step=step,
        categorical_view=view,
        heading=heading,
        carried_entity=None,
        instruction="go",
    )


def _resolve(xy: tuple[int, int]) -> str:
    return f"loc-{xy[0]}_{xy[1]}"


def test_rotate_local_delta_east() -> None:
    assert egocentric_delta_to_world(right=0, forward=-1, heading="east") == (-1, 0)


def test_rotate_local_delta_north() -> None:
    assert egocentric_delta_to_world(right=1, forward=0, heading="north") == (1, 0)


def test_rotate_local_delta_south() -> None:
    assert egocentric_delta_to_world(right=0, forward=-1, heading="south") == (0, -1)


def test_rotate_local_delta_west() -> None:
    assert egocentric_delta_to_world(right=0, forward=-1, heading="west") == (1, 0)


def test_unseen_cells_emit_no_evidence() -> None:
    view = _make_view(object_index=0, visible=False)

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    # Unseen is never reported as free, blocked or occupied.
    assert evidence == ()


def test_visible_empty_cell_emits_passable_true() -> None:
    view = _make_view()  # every cell empty and visible

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    passable = [e for e in evidence if e.atom.predicate == "passable"]
    assert passable
    assert all(e.polarity for e in passable)
    # Front cell of an east-facing agent at the origin is world (1, 0).
    assert "loc-2_0" in {e.atom.arguments[0] for e in passable}


def test_wall_emits_negative_passable() -> None:
    view = _make_view(overrides={(3, 5): _make_cell(2)})  # wall in front

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    wall = [
        e
        for e in evidence
        if e.atom.predicate == "passable"
        and e.atom.arguments == ("loc-1_0",)
    ]
    assert len(wall) == 1
    assert not wall[0].polarity

def test_wall_emits_negative_passable_2() -> None:
    view = _make_view(overrides={(3, 4): _make_cell(2)})  # wall in front

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    wall = [
        e
        for e in evidence
        if e.atom.predicate == "passable"
        and e.atom.arguments == ("loc-2_0",)
    ]
    assert len(wall) == 1
    assert not wall[0].polarity


def test_key_cell_maps_to_key_at() -> None:
    view = _make_view(overrides={(3, 5): _make_cell(5, color_index=0)})

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    key_at = [e for e in evidence if e.atom.predicate == "key-at"]
    assert len(key_at) == 1
    assert key_at[0].polarity
    assert key_at[0].atom.arguments == ("red-key", "loc-1_0")
    assert key_at[0].provenance.local_cell == (0, 1)
    assert key_at[0].provenance.sensor_model_id == "local-categorical"


def test_locked_door_state_mapping() -> None:
    # Door state encoding: 0=open, 1=closed, 2=locked.
    view = _make_view(
        overrides={(3, 5): _make_cell(4, color_index=0, state_index=2)}
    )

    evidence = decode_view(_make_packet(view), "ep-1", 0, 0, _resolve)

    atoms = {e.atom: e.polarity for e in evidence}
    assert atoms[GroundAtom("door-at", ("red-door", "loc-1_0"))] is True
    assert atoms[GroundAtom("door-locked", ("red-door",))] is True
    assert atoms[GroundAtom("door-open", ("red-door",))] is False
    assert atoms[GroundAtom("passable", ("loc-1_0",))] is False
    door_evidence = [e for e in evidence if e.atom.predicate == "door-locked"]
    assert door_evidence[0].stale_after_steps == 3


def test_module_has_no_global_state() -> None:
    for name in dir(observation_decoder):
        if name.startswith("_"):
            continue
        attr = getattr(observation_decoder, name)
        assert not isinstance(attr, (dict, list, set)), name


def test_local_observation_decoder_matches_pure_decode() -> None:
    view = _make_view()
    packet = _make_packet(view)
    decoder = LocalObservationDecoder(
        episode_id="ep-1",
        pose=lambda: (0, 0),
        resolve_location=_resolve,
    )

    decoded = decoder.decode(packet, SensorModelSpec())

    assert decoded == decode_view(packet, "ep-1", 0, 0, _resolve)


def test_decoder_rejects_n1_corruption_channel() -> None:
    decoder = LocalObservationDecoder(
        episode_id="ep-1",
        pose=lambda: (0, 0),
        resolve_location=_resolve,
    )

    with pytest.raises(ValueError, match="after decoding"):
        decoder.decode(
            _make_packet(_make_view()),
            SensorModelSpec(corruption_channel="N1-FLIP-10"),
        )
