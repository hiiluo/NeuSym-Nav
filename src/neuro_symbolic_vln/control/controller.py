from __future__ import annotations

from dataclasses import dataclass

from neuro_symbolic_vln.contracts import (
    Evidence,
    GroundAtom,
    ObservationPacket,
    PrimitiveAction,
    Provenance,
    StepResult,
    SymbolicAction,
)


class MiniGridController:
    """Translates symbolic planner actions into MiniGrid primitive actions."""

    _ACTION_MAP = {
        "turn-left": "turn_left",
        "turn-right": "turn_right",
        "move-forward": "move_forward",
        "pickup-key": "pickup",
        "toggle-locked-door": "toggle",
    }

    def to_primitive(self, action: SymbolicAction) -> str:
        try:
            return self._ACTION_MAP[action.name]
        except KeyError as error:
            raise ValueError(f"unsupported symbolic action: {action.name}") from error


# Episode-local frame: origin at reset, x grows east, y grows south.
_HEADING_DELTA = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0),
}


@dataclass(frozen=True)
class LocalPose:
    """Pose in the episode-local frame."""

    x: int
    y: int
    heading: str
    location_id: str


class DeadReckoningTracker:
    """Track internal pose and carrying state from action feedback only.

    The pose advances only when ``StepResult.action_succeeded`` confirms a
    movement action; blocked moves leave the internal location unchanged.
    """

    SENSOR_MODEL_ID = "dead-reckoning"

    def __init__(self, episode_id: str) -> None:
        self._episode_id = episode_id
        self._locations: dict[tuple[int, int], str] = {(0, 0): "loc_0"}
        self._next_location_id = 1
        self._pose: LocalPose | None = None
        self._carried: str | None = None
        self._evidence_seq = 0

    def location_id(self, coordinate: tuple[int, int]) -> str:
        """Return the stable LocationId of an episode-local coordinate."""
        location = self._locations.get(coordinate)
        if location is None:
            location = f"loc_{self._next_location_id}"
            self._next_location_id += 1
            self._locations[coordinate] = location
        return location

    def pose(self) -> LocalPose:
        """Current internal pose (reset() must have been called first)."""
        return self._require_pose()

    def reset(self, observation: ObservationPacket) -> tuple[Evidence, ...]:
        """Establish the local origin and emit initial pose evidence."""
        self._pose = LocalPose(0, 0, observation.heading, "loc_0")
        self._carried = observation.carried_entity
        evidence = [
            self._pose_evidence(observation),
            self._facing_evidence(observation, True),
        ]
        evidence.extend(self._front_cell_evidence(observation))
        evidence.extend(self._carrying_evidence(observation, None))
        return tuple(evidence)

    def step(self, action: PrimitiveAction, result: StepResult) -> tuple[Evidence, ...]:
        """Apply action feedback; blocked or failed actions move nothing."""
        pose = self._require_pose()
        observation = result.observation
        evidence: list[Evidence] = []

        if result.action_succeeded and action.name == "move_forward":
            dx, dy = _HEADING_DELTA[pose.heading]
            new_x, new_y = pose.x + dx, pose.y + dy
            old_id = pose.location_id
            new_id = self.location_id((new_x, new_y))
            self._pose = LocalPose(new_x, new_y, pose.heading, new_id)
            evidence.extend(self._robot_at_evidence(observation, old_id, new_id))
            evidence.extend(self._front_cell_evidence(observation))
        elif (
            result.action_succeeded
            and action.name in ("turn_left", "turn_right")
            and observation.heading != pose.heading
        ):
            self._pose = LocalPose(
                pose.x, pose.y, observation.heading, pose.location_id
            )
            evidence.extend(self._heading_change_evidence(observation, pose.heading))
            evidence.extend(self._front_cell_evidence(observation))

        if observation.carried_entity != self._carried:
            old_carried = self._carried
            self._carried = observation.carried_entity
            evidence.extend(self._carrying_evidence(observation, old_carried))

        return tuple(evidence)

    def _require_pose(self) -> LocalPose:
        if self._pose is None:
            raise RuntimeError("reset() must be called before step()")
        return self._pose

    def _evidence(
        self, observation: ObservationPacket, atom: GroundAtom, polarity: bool
    ) -> Evidence:
        self._evidence_seq += 1
        return Evidence(
            evidence_id=f"{observation.observation_id}:pose:{self._evidence_seq}",
            atom=atom,
            polarity=polarity,
            reliability=1.0,
            observed_step=observation.step,
            stale_after_steps=None,
            source=self.SENSOR_MODEL_ID,
            provenance=Provenance(
                episode_id=self._episode_id,
                observation_id=observation.observation_id,
                sensor_model_id=self.SENSOR_MODEL_ID,
                local_cell=None,
                corruption_channel=None,
            ),
        )

    def _pose_evidence(self, observation: ObservationPacket) -> Evidence:
        pose = self._require_pose()
        return self._evidence(
            observation,
            GroundAtom("robot-at", ("robot", pose.location_id)),
            True,
        )

    def _robot_at_evidence(
        self, observation: ObservationPacket, old_id: str, new_id: str
    ) -> tuple[Evidence, Evidence]:
        return (
            self._evidence(
                observation, GroundAtom("robot-at", ("robot", old_id)), False
            ),
            self._evidence(
                observation, GroundAtom("robot-at", ("robot", new_id)), True
            ),
        )

    def _facing_evidence(
        self, observation: ObservationPacket, polarity: bool
    ) -> Evidence:
        pose = self._require_pose()
        return self._evidence(
            observation,
            GroundAtom("facing", ("robot", pose.heading)),
            polarity,
        )

    def _heading_change_evidence(
        self, observation: ObservationPacket, old_heading: str
    ) -> tuple[Evidence, Evidence]:
        pose = self._require_pose()
        return (
            self._evidence(
                observation,
                GroundAtom("facing", ("robot", old_heading)),
                False,
            ),
            self._evidence(
                observation,
                GroundAtom("facing", ("robot", pose.heading)),
                True,
            ),
        )

    def _front_cell_evidence(
        self, observation: ObservationPacket
    ) -> tuple[Evidence, ...]:
        pose = self._require_pose()
        # The coordinate registry may allocate neighbouring IDs, but a
        # front-cell edge is known only for the currently observed heading.
        # This keeps unknown adjacency out of the observed topology/frontier.
        cells = observation.categorical_view.cells_by_x
        if len(cells) <= 3 or len(cells[3]) <= 5:
            return ()
        view_cell = cells[3][5]
        if not view_cell.visible:
            return ()
        heading = pose.heading
        dx, dy = _HEADING_DELTA[heading]
        to_id = self.location_id((pose.x + dx, pose.y + dy))
        return (
            self._evidence(
                observation,
                GroundAtom("front-cell", (pose.location_id, heading, to_id)),
                True,
            ),
        )

    def _carrying_evidence(
        self, observation: ObservationPacket, old_carried: str | None
    ) -> tuple[Evidence, ...]:
        carried = observation.carried_entity
        items: list[Evidence] = []
        if old_carried is not None:
            items.append(
                self._evidence(
                    observation,
                    GroundAtom("holding", ("robot", old_carried.replace(":", "-"))),
                    False,
                )
            )
        if carried is None:
            items.append(
                self._evidence(observation, GroundAtom("handempty", ("robot",)), True)
            )
        else:
            items.append(
                self._evidence(observation, GroundAtom("handempty", ("robot",)), False)
            )
            items.append(
                self._evidence(
                    observation,
                    GroundAtom("holding", ("robot", carried.replace(":", "-"))),
                    True,
                )
            )
        return tuple(items)
