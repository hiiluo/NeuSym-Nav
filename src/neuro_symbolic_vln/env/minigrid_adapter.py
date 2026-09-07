from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from minigrid.core.actions import Actions

from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    EpisodeSpec,
    ObservationPacket,
    PrimitiveAction,
    StepResult,
)
from neuro_symbolic_vln.env.base import EnvironmentAdapter, TaskVerifier

# MiniGrid directions (agent_dir) as the compass headings used
# everywhere else in the project: 0=east, 1=south, 2=west, 3=north.
_DIRECTION_TO_HEADING = {
    0: "east",
    1: "south",
    2: "west",
    3: "north",
}


@dataclass(frozen=True)
class _ActuatorState:
    position: tuple[int, int]
    direction: int
    carried: tuple[str, str, bool] | None
    front: tuple[str, str, bool] | None


class MiniGridAdapter(EnvironmentAdapter):
    """Expose only the local categorical view and typed step result."""

    _ACTION_MAP = {
        "turn_left": Actions.left,
        "turn_right": Actions.right,
        "move_forward": Actions.forward,
        "pickup": Actions.pickup,
        "toggle": Actions.toggle,
        "done": Actions.done,
    }

    def __init__(
        self,
        env: Any,
        episode: EpisodeSpec | None = None,
        verifier: TaskVerifier | None = None,
    ) -> None:
        self._env = env
        self._episode = episode
        self._verifier = verifier
        self._step = 0
        self._observation_id = 0

    def reset(
        self,
        episode: EpisodeSpec | None = None,
        *,
        seed: int | None = None,
    ) -> ObservationPacket:
        if episode is not None:
            self._episode = episode
        self._env.reset(seed=seed)
        self._step = 0
        self._observation_id = 0
        return self._observation()

    def close(self) -> None:
        close = getattr(self._env, "close", None)
        if close is not None:
            close()

    def step(self, action: PrimitiveAction) -> StepResult:
        try:
            native_action = self._ACTION_MAP[action.name]
        except KeyError as error:
            raise ValueError(f"unsupported primitive action: {action.name}") from error

        before = self._actuator_state()
        _, _, terminated, truncated, _ = self._env.step(native_action)
        after = self._actuator_state()
        self._step += 1
        observation = self._observation()
        action_succeeded = before != after and action.name != "done"
        if self._verifier is None:
            raise RuntimeError(
                "MiniGridAdapter.step() requires a TaskVerifier"
            )
        task_success = self._verifier.evaluate().task_success
        return StepResult(
            observation=observation,
            action_succeeded=action_succeeded,
            failure_reason=(
                None if action_succeeded else "action had no actuator effect"
            ),
            task_success=task_success,
            terminated=terminated,
            truncated=truncated,
        )

    def _actuator_state(self) -> _ActuatorState:
        raw_position = self._env.unwrapped.agent_pos
        position = (int(raw_position[0]), int(raw_position[1]))
        direction = int(self._env.unwrapped.agent_dir)
        carried = self._object_state(self._env.unwrapped.carrying)
        front_position = (
            position[0] + ((1, 0, -1, 0)[direction]),
            position[1] + ((0, 1, 0, -1)[direction]),
        )
        front = self._object_state(self._env.unwrapped.grid.get(*front_position))
        return _ActuatorState(position, direction, carried, front)

    @staticmethod
    def _object_state(obj: Any) -> tuple[str, str, bool] | None:
        if obj is None:
            return None
        return (
            str(obj.type),
            str(getattr(obj, "color", "")),
            bool(getattr(obj, "is_locked", False)),
        )

    def _observation(self) -> ObservationPacket:
        assert self._episode is not None
        encoded = np.asarray(self._env.unwrapped.gen_obs()["image"])
        cells = tuple(
            tuple(
                CategoricalCell(
                    object_index=int(cell[0]),
                    color_index=int(cell[1]),
                    state_index=int(cell[2]),
                    # object_index 0 is MiniGrid's "unseen" sentinel.
                    visible=bool(cell[0] != 0),
                )
                for cell in column
            )
            for column in encoded
        )
        self._observation_id += 1
        carried = self._env.unwrapped.carrying
        carried_entity = (
            None if carried is None else f"{carried.color}:{carried.type}"
        )
        return ObservationPacket(
            observation_id=f"{self._episode.episode_id}:{self._observation_id}",
            step=self._step,
            categorical_view=CategoricalView(cells_by_x=cells),
            heading=_DIRECTION_TO_HEADING[int(self._env.unwrapped.agent_dir)],
            carried_entity=carried_entity,
            instruction=self._episode.instruction,
        )
