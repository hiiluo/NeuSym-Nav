from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from minigrid.core.actions import Actions
from minigrid.core.world_object import Wall

from neuro_symbolic_vln.evaluation.manifests import stable_hash
from neuro_symbolic_vln.evaluation.oracle import (
    ExactOracle,
    OracleSolution,
    model_from_probe_env,
)

CHECKPOINT_PRE_MOVE = "pre-move-forward"
CHECKPOINT_POST_TOGGLE = "post-toggle"


@dataclass(frozen=True)
class InterventionSpec:
    """Immutable intervention: what changes, where and at which checkpoint."""

    intervention_id: str
    kind: str  # "block" | "relock"
    target: tuple[int, int]
    checkpoint: str
    seed: int
    recoverable: bool  # static eligibility; the oracle confirms it

    def to_dict(self) -> dict[str, object]:
        return {
            "intervention_id": self.intervention_id,
            "kind": self.kind,
            "target": list(self.target),
            "checkpoint": self.checkpoint,
            "seed": self.seed,
            "recoverable": self.recoverable,
        }

    def hash(self) -> str:
        """Deterministic hash over the design fields (plan §13.2: same
        seed produces the same intervention)."""
        return stable_hash(
            {
                "intervention_id": self.intervention_id,
                "kind": self.kind,
                "target": list(self.target),
                "checkpoint": self.checkpoint,
                "seed": self.seed,
            }
        )

    @classmethod
    def from_sidecar(
        cls, payload: dict[str, Any] | None
    ) -> InterventionSpec | None:
        """Rehydrate from a manifest-sidecar ``intervention`` payload."""
        if not payload:
            return None
        target = payload["target"]
        return cls(
            intervention_id=str(payload["intervention_id"]),
            kind=str(payload["kind"]),
            target=(int(target[0]), int(target[1])),
            checkpoint=str(payload["checkpoint"]),
            seed=int(payload["seed"]),
            recoverable=bool(payload.get("recoverable", False)),
        )


def choose_block_intervention(
    planned_next: tuple[int, int],
    alternate_route: Collection[tuple[int, int]],
    seed: int = 0,
) -> InterventionSpec:
    """Navigation intervention (plan §13.2): block the designated next
    location right before a planned move-forward."""
    route = tuple(alternate_route)
    return InterventionSpec(
        intervention_id=f"block-{planned_next[0]}-{planned_next[1]}",
        kind="block",
        target=planned_next,
        checkpoint=CHECKPOINT_PRE_MOVE,
        seed=seed,
        recoverable=bool(route) and planned_next not in route,
    )


def choose_relock_intervention(
    door_cell: tuple[int, int],
    seed: int = 0,
) -> InterventionSpec:
    """Key-door intervention (plan §13.2): re-lock the door right after a
    successful toggle and before the first crossing. The checkpoint
    construction guarantees the matching key is still carried."""
    return InterventionSpec(
        intervention_id=f"relock-{door_cell[0]}-{door_cell[1]}",
        kind="relock",
        target=door_cell,
        checkpoint=CHECKPOINT_POST_TOGGLE,
        seed=seed,
        recoverable=True,
    )


def apply_intervention(env: Any, spec: InterventionSpec) -> None:
    """Apply the fixed world change (evaluator-privileged)."""
    if spec.kind == "block":
        env.unwrapped.grid.set(spec.target[0], spec.target[1], Wall())
    elif spec.kind == "relock":
        door = env.unwrapped.grid.get(*spec.target)
        door.is_open = False
        door.is_locked = True
    else:
        raise ValueError(f"unknown intervention kind: {spec.kind}")


def build_relock_checkpoint(env: Any) -> None:
    """Advance a fresh key-door probe env to the post-toggle checkpoint.

    Privileged world manipulation: face east, pick up the matching key,
    move to the door cell and toggle it open. The re-lock then applies
    before the first crossing, exactly as plan §13.2 describes.
    """
    env.unwrapped.agent_dir = 0
    env.step(Actions.pickup)
    env.step(Actions.forward)
    env.step(Actions.toggle)


@dataclass(frozen=True)
class InterventionAnnotation:
    """Oracle-confirmed recoverability plus pre/post optima (sidecar only)."""

    intervention_id: str
    recoverable: bool
    pre_optimum: int | None
    post_optimum: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "intervention_id": self.intervention_id,
            "recoverable": self.recoverable,
            "pre_optimum": self.pre_optimum,
            "post_optimum": self.post_optimum,
        }


def annotate_intervention(
    env: Any,
    family: str,
    target: tuple[int, int],
    spec: InterventionSpec,
    pre_solution: OracleSolution,
) -> InterventionAnnotation:
    """Apply the intervention and oracle-confirm the post-state (plan §13.2:
    "Mỗi intervention được pre-generate và oracle xác nhận post-intervention
    solvable")."""
    if spec.kind == "block":
        apply_intervention(env, spec)
    elif spec.kind == "relock":
        build_relock_checkpoint(env)
        apply_intervention(env, spec)
    else:
        raise ValueError(f"unknown intervention kind: {spec.kind}")
    post_solution = ExactOracle().solve(
        model_from_probe_env(env, family, target)
    )
    return InterventionAnnotation(
        intervention_id=spec.intervention_id,
        recoverable=post_solution.solvable,
        pre_optimum=pre_solution.optimal_primitive_actions,
        post_optimum=post_solution.optimal_primitive_actions,
    )
