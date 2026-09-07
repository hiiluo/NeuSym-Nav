from __future__ import annotations

from typing import Protocol

from neuro_symbolic_vln.contracts import (
    EpisodeSpec,
    ObservationPacket,
    PrimitiveAction,
    StepResult,
)
from neuro_symbolic_vln.env.verifier import VerificationResult


class EnvironmentAdapter(Protocol):
    def reset(self, episode: EpisodeSpec) -> ObservationPacket: ...
    def step(self, action: PrimitiveAction) -> StepResult: ...
    def close(self) -> None: ...


class TaskVerifier(Protocol):
    """Authoritative environment-side success contract (plan §8.5).

    Returns a typed result only; never provides planning facts.
    """

    def evaluate(self) -> VerificationResult: ...
