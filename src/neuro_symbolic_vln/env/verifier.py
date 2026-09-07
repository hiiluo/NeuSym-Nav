from dataclasses import dataclass, field
from typing import Any

_DIRECTION_TO_DELTA = {
    0: (1, 0),
    1: (0, 1),
    2: (-1, 0),
    3: (0, -1),
}


@dataclass(frozen=True)
class VerificationResult:
    """Typed verifier outcome: task success plus a stable reason code."""

    task_success: bool
    terminated: bool
    reason_code: str


@dataclass(frozen=True)
class GoToVerifier:
    target_position: tuple[int, int]
    env: Any = field(default=None, repr=False, compare=False)

    def is_satisfied(
        self, agent_position: tuple[int, int], agent_direction: int
    ) -> bool:
        """Pure check: the target sits in the agent's front cell."""
        try:
            dx, dy = _DIRECTION_TO_DELTA[agent_direction]
        except KeyError as error:
            raise ValueError(
                f"invalid MiniGrid direction: {agent_direction}"
            ) from error
        return (
            agent_position[0] + dx,
            agent_position[1] + dy,
        ) == self.target_position

    def evaluate(self) -> VerificationResult:
        """Authoritative result over the environment bound at construction."""
        if self.env is None:
            raise RuntimeError(
                "GoToVerifier.evaluate() requires an environment bound "
                "at construction"
            )
        position = self.env.unwrapped.agent_pos
        direction = int(self.env.unwrapped.agent_dir)
        satisfied = self.is_satisfied(
            (int(position[0]), int(position[1])), direction
        )
        return VerificationResult(
            task_success=satisfied,
            # MiniGrid carries episode termination in StepResult.
            terminated=False,
            reason_code=(
                "target-in-front" if satisfied else "target-not-in-front"
            ),
        )
