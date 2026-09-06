from __future__ import annotations

from collections.abc import Callable

from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    Evidence,
    GroundAtom,
    ObservationPacket,
    Provenance,
)

# MiniGrid 3.1.0 fixed encodings (see minigrid/core/constants.py).
_OBJECT_NAMES = (
    "unseen", "empty", "wall", "floor", "door",
    "key", "ball", "box", "goal", "lava", "agent",
)
_COLOR_NAMES = ("red", "green", "blue", "purple", "yellow", "grey")

_VIEW_SIZE = 7
# The agent sits at the bottom centre of the egocentric view.
_AGENT_VIEW_CELL = (_VIEW_SIZE // 2, _VIEW_SIZE - 1)

SENSOR_MODEL_ID = "local-categorical"

LocationResolver = Callable[[tuple[int, int]], str]


# def rotate_local_delta(dx: int, dy: int, heading: str) -> tuple[int, int]:
#     """Rotate a north-up world delta into the egocentric (right, forward) frame.

#     World deltas use x=east, y=south (north is -y), matching MiniGrid axes.
#     """
#     transforms = {
#         "north": (dx, dy),
#         "east": (-dy, dx),
#         "south": (-dx, -dy),
#         "west": (dy, -dx),
#     }
#     try:
#         return transforms[heading]
#     except KeyError as error:
#         raise ValueError(f"unsupported heading: {heading}") from error


# def egocentric_delta_to_world(dx: int, dy: int, heading: str) -> tuple[int, int]:
#     """Rotate an egocentric (right, forward) delta into the north-up frame."""
#     opposite = {
#         "north": "south",
#         "south": "north",
#         "east": "west",
#         "west": "east",
#     }
#     return rotate_local_delta(dx, dy, opposite[heading])

def egocentric_delta_to_world(
    right: int,
    forward: int,
    heading: str,
) -> tuple[int, int]:
    """Convert an egocentric (right, forward) delta into World coordinates.

    World frame:
        +x = east
        +y = south

    Egocentric frame:
        +right = right of the agent
        +forward = forward of the agent
    """
    transforms = {
        "north": (right, -forward),
        "east": (forward, right),
        "south": (-right, forward),
        "west": (-forward, -right)
    }

    try:
        return transforms[heading]
    except KeyError as error:
        raise ValueError(f"unsupported heading: {heading}") from error


def decode_view(
    packet: ObservationPacket,
    episode_id: str,
    pose_x: int,
    pose_y: int,
    resolve_location: LocationResolver,
) -> tuple[Evidence, ...]:
    """Decode one egocentric categorical view into local Evidence items.

    Cells with ``visible=False`` (MiniGrid's "unseen" sentinel) produce no
    evidence at all: an unseen cell is never reported as free or blocked.
    """
    evidence: list[Evidence] = []
    for cell_x in range(_VIEW_SIZE):
        for cell_y in range(_VIEW_SIZE):
            cell = packet.categorical_view.cells_by_x[cell_x][cell_y]
            if not cell.visible:
                continue
            right = cell_x - _AGENT_VIEW_CELL[0]
            forward = _AGENT_VIEW_CELL[1] - cell_y
            dx, dy = egocentric_delta_to_world(right, forward, packet.heading)
            location = resolve_location((pose_x + dx, pose_y + dy))
            evidence.extend(
                _cell_evidence(
                    cell,
                    location,
                    packet,
                    episode_id,
                    (right, forward),
                    f"{cell_x}-{cell_y}",
                )
            )
    return tuple(evidence)


def _cell_evidence(
    cell: CategoricalCell,
    location: str,
    packet: ObservationPacket,
    episode_id: str,
    local_cell: tuple[int, int],
    cell_tag: str,
) -> tuple[Evidence, ...]:
    object_name = (
        _OBJECT_NAMES[cell.object_index]
        if cell.object_index < len(_OBJECT_NAMES)
        else ""
    )
    color = (
        _COLOR_NAMES[cell.color_index]
        if cell.color_index < len(_COLOR_NAMES)
        else "unknown"
    )
    entity = f"{color}-{object_name}"
    items: list[Evidence] = []

    def add(
        predicate: str,
        arguments: tuple[str, ...],
        polarity: bool,
        stale_after_steps: int | None = None,
    ) -> None:
        items.append(
            Evidence(
                evidence_id=(
                    f"{packet.observation_id}:cell-{cell_tag}-{len(items)}"
                ),
                atom=GroundAtom(predicate, arguments),
                polarity=polarity,
                reliability=1.0,
                observed_step=packet.step,
                stale_after_steps=stale_after_steps,
                source=SENSOR_MODEL_ID,
                provenance=Provenance(
                    episode_id=episode_id,
                    observation_id=packet.observation_id,
                    sensor_model_id=SENSOR_MODEL_ID,
                    local_cell=local_cell,
                    corruption_channel=None,
                ),
            )
        )

    if object_name in ("empty", "floor", "agent"):
        add("passable", (location,), True)
    elif object_name == "wall":
        add("passable", (location,), False)
    elif object_name == "door":
        # Door state encoding: 0=open, 1=closed, 2=locked.
        add("door-at", (entity, location), True)
        add("door-open", (entity,), cell.state_index == 0, stale_after_steps=3)
        add(
            "door-locked",
            (entity,),
            cell.state_index == 2,
            stale_after_steps=3,
        )
        add("passable", (location,), cell.state_index == 0, stale_after_steps=3)
    elif object_name == "key":
        # In MiniGrid 3.1.0 a key on the ground blocks movement.
        add("key-at", (entity, location), True)
        add("passable", (location,), False)
    elif object_name in ("ball", "box"):
        add("target-at", (entity, location), True)
        add("passable", (location,), False)
    elif object_name == "goal":
        add("goal-at", (entity, location), True)
        add("passable", (location,), True)
    elif object_name == "lava":
        add("passable", (location,), False)
    return tuple(items)
