from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Door, Key
from minigrid.minigrid_env import MiniGridEnv


class LockedDoorProbeEnv(MiniGridEnv):
    """A matching key in front of the agent and a locked red door.

    Optionally places a non-red distractor key somewhere off the
    start-to-door corridor, so the layout stays solvable.
    """

    def __init__(
        self,
        key_color: str = "red",
        agent_dir: int = 0,
        distractor_key_color: str | None = None,
        distractor_key_pos: tuple[int, int] = (1, 3),
    ) -> None:
        self._key_color = key_color
        self._agent_dir = agent_dir
        self._distractor_key_color = distractor_key_color
        self._distractor_key_pos = distractor_key_pos
        super().__init__(
            mission_space=MissionSpace(mission_func=lambda: "probe"),
            width=6,
            height=5,
            max_steps=32,
        )

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.agent_pos = (1, 1)
        self.agent_dir = self._agent_dir
        self.put_obj(Key(self._key_color), 2, 1)
        self.put_obj(Door("red", is_locked=True), 3, 1)
        if self._distractor_key_color is not None:
            self.put_obj(
                Key(self._distractor_key_color), *self._distractor_key_pos
            )
        self.mission = "probe"


def make_locked_door_probe_env(
    key_color: str = "red",
    agent_dir: int = 0,
    distractor_key_color: str | None = None,
    distractor_key_pos: tuple[int, int] = (1, 3),
) -> LockedDoorProbeEnv:
    return LockedDoorProbeEnv(
        key_color=key_color,
        agent_dir=agent_dir,
        distractor_key_color=distractor_key_color,
        distractor_key_pos=distractor_key_pos,
    )


class GoToGoalProbeEnv(MiniGridEnv):
    """A target object (e.g. green ball) and optionally distractors."""

    def __init__(
        self,
        target_type: str = "ball",
        target_color: str = "green",
        target_pos: tuple[int, int] = (3, 1),
        agent_pos: tuple[int, int] = (1, 1),
        agent_dir: int = 0,
        distractor: bool = True,
    ) -> None:
        self._target_type = target_type
        self._target_color = target_color
        self._target_pos = target_pos
        self._agent_init_pos = agent_pos
        self._agent_init_dir = agent_dir
        self._distractor = distractor
        super().__init__(
            mission_space=MissionSpace(
                mission_func=lambda: f"go to the {target_color} {target_type}"
            ),
            width=6,
            height=5,
            max_steps=32,
        )

    def _gen_grid(self, width: int, height: int) -> None:
        from minigrid.core.world_object import Ball, Box

        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.agent_pos = self._agent_init_pos
        self.agent_dir = self._agent_init_dir
        if self._target_type == "ball":
            self.put_obj(Ball(self._target_color), *self._target_pos)  # type: ignore[no-untyped-call]
        else:
            self.put_obj(Box(self._target_color), *self._target_pos)
        if self._distractor:
            self.put_obj(Box("yellow"), 2, 2)
        self.mission = f"go to the {self._target_color} {self._target_type}"


def make_goto_goal_probe_env(
    target_type: str = "ball",
    target_color: str = "green",
    target_pos: tuple[int, int] = (3, 1),
    agent_pos: tuple[int, int] = (1, 1),
    agent_dir: int = 0,
    distractor: bool = True,
) -> GoToGoalProbeEnv:
    return GoToGoalProbeEnv(
        target_type=target_type,
        target_color=target_color,
        target_pos=target_pos,
        agent_pos=agent_pos,
        agent_dir=agent_dir,
        distractor=distractor,
    )
