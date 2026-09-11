from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

# MiniGrid grid frame: x grows east, y grows south.
_HEADING_DELTA = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0),
}
_LEFT_OF = {"north": "west", "west": "south", "south": "east", "east": "north"}
_RIGHT_OF = {value: key for key, value in _LEFT_OF.items()}


def shortest_primitive_cost(
    start: tuple[int, int, str],
    goal: tuple[int, int, str],
    passable: Collection[tuple[int, int]],
) -> int | None:
    """Minimal turn+forward primitive count from a start pose to a goal pose.

    Every primitive action (turn or forward) costs 1. Returns None when the
    goal pose is unreachable.
    """
    passable_set = frozenset(passable)
    start_state = start
    queue: deque[tuple[tuple[int, int, str], int]] = deque([(start_state, 0)])
    visited = {start_state}
    while queue:
        (x, y, heading), cost = queue.popleft()
        if (x, y, heading) == goal:
            return cost
        for next_state in _pose_transitions(x, y, heading, passable_set):
            if next_state not in visited:
                visited.add(next_state)
                queue.append((next_state, cost + 1))
    return None


def _pose_transitions(
    x: int,
    y: int,
    heading: str,
    passable: frozenset[tuple[int, int]],
) -> tuple[tuple[int, int, str], ...]:
    dx, dy = _HEADING_DELTA[heading]
    transitions = [(x, y, _LEFT_OF[heading]), (x, y, _RIGHT_OF[heading])]
    if (x + dx, y + dy) in passable:
        transitions.append((x + dx, y + dy, heading))
    return tuple(transitions)


@dataclass(frozen=True)
class OracleTaskModel:
    """Minimal exact model of one core-task episode for BFS planning."""

    family: str
    start: tuple[int, int]
    start_heading: str
    passable: frozenset[tuple[int, int]]
    keys: frozenset[tuple[tuple[int, int], str]]
    locked_doors: frozenset[tuple[tuple[int, int], str]]
    target: tuple[int, int]
    carrying: str | None = None


@dataclass(frozen=True)
class OracleSolution:
    solvable: bool
    optimal_primitive_actions: int | None
    optimal_grid_distance: int | None


@dataclass(frozen=True)
class _State:
    x: int
    y: int
    heading: str
    carrying: str | None
    remaining_keys: frozenset[tuple[int, int]]
    locked_doors: frozenset[tuple[int, int]]

    def front(self) -> tuple[int, int]:
        dx, dy = _HEADING_DELTA[self.heading]
        return (self.x + dx, self.y + dy)


class ExactOracle:
    """Exact solver over (location, heading, carrying, door state).

    Success means the target sits in the agent's front cell, matching the
    GoToVerifier contract used by both core probe families. All primitive
    actions cost 1; grid distance counts forward moves only.
    """

    def solve(self, model: OracleTaskModel) -> OracleSolution:
        key_colors = {position: color for position, color in model.keys}
        door_colors = {position: color for position, color in model.locked_doors}
        initial = _State(
            x=model.start[0],
            y=model.start[1],
            heading=model.start_heading,
            carrying=model.carrying,
            remaining_keys=frozenset(key_colors),
            locked_doors=frozenset(door_colors),
        )
        queue: deque[tuple[_State, int, int]] = deque([(initial, 0, 0)])
        visited = {initial}
        while queue:
            state, actions, forwards = queue.popleft()
            if state.front() == model.target:
                return OracleSolution(True, actions, forwards)
            for next_state, is_forward in self._transitions(state, model):
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append(
                        (next_state, actions + 1, forwards + int(is_forward))
                    )
        return OracleSolution(False, None, None)

    @staticmethod
    def _passable_now(
        state: _State, model: OracleTaskModel
    ) -> frozenset[tuple[int, int]]:
        key_positions = {position for position, _ in model.keys}
        door_positions = {position for position, _ in model.locked_doors}
        released_keys = key_positions - state.remaining_keys
        opened_doors = door_positions - state.locked_doors
        return model.passable | released_keys | opened_doors

    def _transitions(
        self, state: _State, model: OracleTaskModel
    ) -> tuple[tuple[_State, bool], ...]:
        transitions: list[tuple[_State, bool]] = []

        # Turns always succeed.
        for heading in (_LEFT_OF[state.heading], _RIGHT_OF[state.heading]):
            transitions.append(
                (_State(
                    state.x, state.y, heading,
                    state.carrying, state.remaining_keys, state.locked_doors,
                ), False)
            )

        front = state.front()
        passable = self._passable_now(state, model)

        # Forward: allowed when the front cell is passable now.
        if front in passable:
            transitions.append(
                (_State(
                    front[0], front[1], state.heading,
                    state.carrying, state.remaining_keys, state.locked_doors,
                ), True)
            )

        # Pickup: front cell holds a key and hands are empty.
        for position, color in model.keys:
            if position == front and state.carrying is None:
                transitions.append(
                    (_State(
                        state.x, state.y, state.heading,
                        color, state.remaining_keys - {position},
                        state.locked_doors,
                    ), False)
                )

        # Toggle: front cell holds a locked door matching the carried key.
        for position, color in model.locked_doors:
            if position == front and state.carrying == color:
                transitions.append(
                    (_State(
                        state.x, state.y, state.heading,
                        state.carrying, state.remaining_keys,
                        state.locked_doors - {position},
                    ), False)
                )

        return tuple(transitions)


def model_from_probe_env(
    env: Any, family: str, target: tuple[int, int]
) -> OracleTaskModel:
    """Build an exact model by reading the probe environment grid.

    Privileged: evaluator code only, never the normal agent path.
    """
    grid = env.unwrapped.grid
    passable: set[tuple[int, int]] = set()
    keys: set[tuple[tuple[int, int], str]] = set()
    locked_doors: set[tuple[tuple[int, int], str]] = set()
    for x in range(1, grid.width - 1):
        for y in range(1, grid.height - 1):
            obj = grid.get(x, y)
            if obj is None or obj.type in ("floor", "goal"):
                passable.add((x, y))
            elif obj.type == "key":
                keys.add(((x, y), str(obj.color)))
            elif obj.type == "door":
                if getattr(obj, "is_locked", False):
                    locked_doors.add(((x, y), str(obj.color)))
                else:
                    passable.add((x, y))
    heading = {0: "east", 1: "south", 2: "west", 3: "north"}[
        int(env.unwrapped.agent_dir)
    ]
    position = env.unwrapped.agent_pos
    carrying = None
    if env.unwrapped.carrying is not None:
        carrying = str(env.unwrapped.carrying.color)
    return OracleTaskModel(
        family=family,
        start=(int(position[0]), int(position[1])),
        start_heading=heading,
        passable=frozenset(passable),
        keys=frozenset(keys),
        locked_doors=frozenset(locked_doors),
        target=target,
        carrying=carrying,
    )
