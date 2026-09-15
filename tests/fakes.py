from __future__ import annotations

from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    HeadingId,
    LocationId,
    ObservationPacket,
    PrimitiveAction,
    StepResult,
)


def make_dummy_categorical_view() -> CategoricalView:
    col = tuple(
        CategoricalCell(object_index=0, color_index=0, state_index=0, visible=True)
        for _ in range(7)
    )
    return CategoricalView(cells_by_x=tuple(col for _ in range(7)))


class FakeGraphAdapter:
    """Non-grid topological graph environment adapter.

    Demonstrates portability: uses opaque location IDs ('room_1', 'corridor',
    'room_2') and graph connectivity rather than 2D grid coordinates.
    Zero MiniGrid imports.
    """

    HEADINGS: list[HeadingId] = ["north", "east", "south", "west"]

    def __init__(
        self,
        initial_location: LocationId = "room_1",
        initial_heading: HeadingId = "north",
        goal_location: LocationId = "room_2",
    ) -> None:
        self._initial_location = initial_location
        self._initial_heading = initial_heading
        self._goal_location = goal_location
        self._current_location = initial_location
        self._current_heading = initial_heading
        self._step_count = 0
        self._carried_entity: str | None = None
        self._door_open: bool = False

        # Graph transitions: (from_node, heading) -> to_node
        self._transitions: dict[tuple[LocationId, HeadingId], LocationId] = {
            ("room_1", "north"): "corridor",
            ("corridor", "south"): "room_1",
            ("corridor", "east"): "room_2",
            ("room_2", "west"): "corridor",
        }

    def reset(self, seed: int | None = None) -> ObservationPacket:
        self._current_location = self._initial_location
        self._current_heading = self._initial_heading
        self._step_count = 0
        self._carried_entity = None
        self._door_open = False
        return self._make_observation()

    def _make_observation(self) -> ObservationPacket:
        return ObservationPacket(
            observation_id=f"obs-{self._step_count}",
            step=self._step_count,
            categorical_view=make_dummy_categorical_view(),
            heading=self._current_heading,
            carried_entity=self._carried_entity,
            instruction="go to room 2",
        )

    @property
    def current_location(self) -> LocationId:
        return self._current_location

    def step(self, action: PrimitiveAction) -> StepResult:
        self._step_count += 1
        heading_idx = self.HEADINGS.index(self._current_heading)
        succeeded = True
        failure_reason = None

        if action.name == "turn_left":
            self._current_heading = self.HEADINGS[(heading_idx - 1) % 4]
        elif action.name == "turn_right":
            self._current_heading = self.HEADINGS[(heading_idx + 1) % 4]
        elif action.name == "move_forward":
            key = (self._current_location, self._current_heading)
            if key in self._transitions:
                self._current_location = self._transitions[key]
            else:
                succeeded = False
                failure_reason = "action had no actuator effect"
        elif action.name == "pickup":
            if self._current_location == "room_1" and self._carried_entity is None:
                self._carried_entity = "key_card"
            else:
                succeeded = False
                failure_reason = "cannot pickup"
        elif action.name == "toggle":
            if self._current_location == "corridor":
                self._door_open = not self._door_open
            else:
                succeeded = False
                failure_reason = "nothing to toggle"
        elif action.name == "done":
            succeeded = False
        else:
            raise ValueError(f"unsupported action: {action.name}")

        task_success = self._current_location == self._goal_location

        return StepResult(
            observation=self._make_observation(),
            action_succeeded=succeeded,
            failure_reason=failure_reason,
            task_success=task_success,
            terminated=task_success,
            truncated=False,
        )
