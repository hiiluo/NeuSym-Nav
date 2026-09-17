"""User-authored MiniGrid maps for the interactive Pygame demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Ball, Door, Goal, Key, Wall
from minigrid.minigrid_env import MiniGridEnv

CellKind = Literal["empty", "wall", "key", "door", "goal", "ball"]


@dataclass(frozen=True)
class CustomMapSpec:
    width: int
    height: int
    cells: dict[tuple[int, int], tuple[CellKind, str]]
    robot_position: tuple[int, int]
    robot_direction: int

    def validate(self) -> str | None:
        if not 3 <= self.width <= 35 or not 3 <= self.height <= 35:
            return "Map size must be between 3 and 35 cells."
        if not 0 <= self.robot_direction <= 3:
            return "Robot direction is invalid."
        if not self._inside(self.robot_position):
            return "Robot must be placed inside the map."
        goals = [kind for kind, _ in self.cells.values() if kind == "goal"]
        if len(goals) != 1:
            return "Custom map must contain exactly one goal."
        for position in self.cells:
            if not self._inside(position):
                return "An object is outside the map."
            if position == self.robot_position:
                return "Robot cannot share a cell with an object."
        return None

    def _inside(self, position: tuple[int, int]) -> bool:
        x, y = position
        return 0 < x < self.width - 1 and 0 < y < self.height - 1


class CustomMapEnv(MiniGridEnv):
    def __init__(self, spec: CustomMapSpec) -> None:
        # ``MiniGridEnv`` inherits Gym's ``spec: EnvSpec | None`` attribute.
        # Keep the authored map under a distinct name rather than narrowing it.
        self.map_spec = spec
        super().__init__(
            mission_space=MissionSpace(mission_func=lambda: "custom navigation"),
            width=spec.width,
            height=spec.height,
            max_steps=max(64, spec.width * spec.height * 4),
        )

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        for (x, y), (kind, color) in self.map_spec.cells.items():
            if kind == "wall":
                self.put_obj(Wall(), x, y)
            elif kind == "key":
                self.put_obj(Key(color), x, y)
            elif kind == "door":
                self.put_obj(Door(color, is_locked=True), x, y)
            elif kind == "goal":
                self.put_obj(Goal(), x, y)
            elif kind == "ball":
                self.put_obj(Ball(color), x, y)  # type: ignore[no-untyped-call]
        self.agent_pos = self.map_spec.robot_position
        self.agent_dir = self.map_spec.robot_direction
        self.mission = "custom navigation"


def object_positions(
    spec: CustomMapSpec, kind: CellKind, color: str | None = None
) -> list[tuple[int, int]]:
    return [
        position
        for position, (candidate_kind, candidate_color) in spec.cells.items()
        if candidate_kind == kind and (color is None or candidate_color == color)
    ]
