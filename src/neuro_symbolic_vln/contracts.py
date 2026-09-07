from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

LocationId = str
HeadingId = str
EntityId = str
EvidenceId = str


@dataclass(frozen=True)
class EpisodeSpec:
    episode_id: str
    family: str
    instruction: str
    public_action_budget: int
    manifest_hash: str


@dataclass(frozen=True)
class CategoricalCell:
    object_index: int
    color_index: int
    state_index: int
    visible: bool


@dataclass(frozen=True)
class CategoricalView:
    cells_by_x: tuple[tuple[CategoricalCell, ...], ...]


@dataclass(frozen=True)
class ObservationPacket:
    observation_id: str
    step: int
    categorical_view: CategoricalView
    heading: HeadingId
    carried_entity: EntityId | None
    instruction: str


@dataclass(frozen=True)
class PrimitiveAction:
    name: str


@dataclass(frozen=True)
class StepResult:
    observation: ObservationPacket
    action_succeeded: bool
    failure_reason: str | None
    task_success: bool
    terminated: bool
    truncated: bool


class TriValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class PlanStatus(StrEnum):
    FOUND = "found"
    ALREADY_SATISFIED = "already_satisfied"
    NEEDS_INFORMATION = "needs_information"
    NO_PLAN_KNOWN_SPACE = "no_plan_known_space"
    UNSUPPORTED_GOAL = "unsupported_goal"
    TIMEOUT = "timeout"
    SERIALIZATION_ERROR = "serialization_error"
    PLANNER_ERROR = "planner_error"


@dataclass(frozen=True, order=True)
class GroundAtom:
    predicate: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Provenance:
    episode_id: str
    observation_id: str
    sensor_model_id: str
    local_cell: tuple[int, int] | None
    corruption_channel: str | None


@dataclass(frozen=True)
class Evidence:
    evidence_id: EvidenceId
    atom: GroundAtom
    polarity: bool
    reliability: float
    observed_step: int
    stale_after_steps: int | None
    source: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be in [0, 1]")
        if self.observed_step < 0:
            raise ValueError("observed_step must be non-negative")


@dataclass(frozen=True)
class BeliefRecord:
    value: TriValue
    reliability: float | None
    last_observed_step: int | None
    stale: bool
    evidence_ids: tuple[EvidenceId, ...]
    conflict_reason: str | None = None


@dataclass(frozen=True)
class LocationGraph:
    nodes: frozenset[LocationId]
    directed_edges: frozenset[tuple[LocationId, HeadingId, LocationId]]
    frontier_nodes: frozenset[LocationId]


@dataclass(frozen=True)
class CommittedPlanningState:
    version: int
    state_hash: str
    true_facts: frozenset[GroundAtom]
    unresolved_required_facts: frozenset[GroundAtom]
    provenance_by_fact: Mapping[GroundAtom, tuple[EvidenceId, ...]]
    location_graph: LocationGraph


@dataclass(frozen=True)
class SymbolicAction:
    name: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class PlanResult:
    status: PlanStatus
    actions: tuple[SymbolicAction, ...]
    planning_time_ms: float
    state_hash: str
    problem_hash: str | None
    reason: str | None


@dataclass(frozen=True)
class GoalProgram:
    family: str
    ordered_subgoals: tuple[GroundAtom, ...]


@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    goal_program: GoalProgram | None
    alternatives: tuple[GoalProgram, ...]
    reason: str | None


class EpisodeOutcome(StrEnum):
    SUCCESS = "success"
    UNSUPPORTED_INSTRUCTION = "unsupported_instruction"
    AMBIGUOUS_GROUNDING = "ambiguous_grounding"
    FRONTIER_EXHAUSTED = "frontier_exhausted"
    KNOWN_SPACE_DISCONNECTED = "known_space_disconnected"
    BELIEF_CONFLICT_UNRESOLVED = "belief_conflict_unresolved"
    PLANNER_TIMEOUT = "planner_timeout"
    PLANNER_ERROR = "planner_error"
    REPLAN_BUDGET_EXHAUSTED = "replan_budget_exhausted"
    LOOP_DETECTED = "loop_detected"
    ACTION_BUDGET_EXHAUSTED = "action_budget_exhausted"
    ENVIRONMENT_TERMINATED_FAILURE = "environment_terminated_failure"


class ParseStatus(StrEnum):
    DETERMINISTIC = "deterministic"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class GroundingStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ValidationDisposition(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ValidationDecision:
    evidence_id: EvidenceId
    disposition: ValidationDisposition
    reason_code: str
    supporting_evidence_ids: tuple[EvidenceId, ...]
    conflicting_evidence_ids: tuple[EvidenceId, ...]


class Validator(Protocol):
    def validate(
        self,
        evidence: tuple[Evidence, ...],
        belief: Mapping[GroundAtom, BeliefRecord],
        current_step: int,
    ) -> tuple[ValidationDecision, ...]: ...
