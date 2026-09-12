"""Trace record serialization, lineage, replay verification, and security checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from neuro_symbolic_vln.contracts import EpisodeOutcome


@dataclass(frozen=True)
class InstructionParseRecord:
    status: str
    goal_program_hash: str


@dataclass(frozen=True)
class ValidationRecord:
    accepted: tuple[str, ...]
    rejected: tuple[str, ...]
    uncertain: tuple[str, ...]


@dataclass(frozen=True)
class TraceRecord:
    schema_version: str
    episode_id: str
    method: str
    oracle_input: bool
    step: int
    manifest_hash: str
    config_hash: str
    instruction_parse: InstructionParseRecord
    observation_id: str
    evidence_ids: tuple[str, ...]
    belief_state_hash: str
    committed_state_hash: str
    validation: ValidationRecord
    problem_hash: str | None
    plan_status: str | None
    symbolic_action: tuple[str, ...] | None
    primitive_action: str | None
    action_succeeded: bool
    failure_reason: str | None
    monitor_decision: str | None
    replan_reason: str | None
    task_success: bool
    episode_outcome: EpisodeOutcome | None


REQUIRED_TRACE_FIELDS: frozenset[str] = frozenset({
    "schema_version",
    "episode_id",
    "method",
    "oracle_input",
    "step",
    "manifest_hash",
    "config_hash",
    "instruction_parse",
    "observation_id",
    "evidence_ids",
    "belief_state_hash",
    "committed_state_hash",
    "validation",
    "problem_hash",
    "plan_status",
    "symbolic_action",
    "primitive_action",
    "action_succeeded",
    "failure_reason",
    "monitor_decision",
    "replan_reason",
    "task_success",
    "episode_outcome",
})

FORBIDDEN_PRIVATE_FIELDS: frozenset[str] = frozenset({
    "optimal_grid_distance",
    "optimal_primitive_actions",
    "oracle_target_entity_id",
    "solvable",
    "uncorrupted_evidence_hash",
    "intervention",
    "grid",
    "grid_bytes",
    "full_grid",
})


class TraceSchemaError(ValueError):
    """Exception when a trace record violates schema contract rules."""


class ReplayMismatchError(ValueError):
    """Exception when discrepancies are detected during trace replay."""


def serialize_record(record: TraceRecord) -> str:
    """Canonical JSON serialization for a TraceRecord."""
    return json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))


def deserialize_record(payload: str | dict[str, Any]) -> TraceRecord:
    """Deserialize JSON string or dict into TraceRecord with strict schema checks."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TraceSchemaError(f"Malformed JSON payload: {exc}") from exc
    elif isinstance(payload, dict):
        data = payload
    else:
        raise TraceSchemaError(f"Expected str or dict, got {type(payload).__name__}")

    missing_fields = REQUIRED_TRACE_FIELDS - data.keys()
    if missing_fields:
        raise TraceSchemaError(f"Missing required fields: {sorted(missing_fields)}")

    if data["schema_version"] != "1.0":
        raise TraceSchemaError(
            f"Unsupported schema_version: {data['schema_version']!r}. Expected '1.0'."
        )

    if not isinstance(data["oracle_input"], bool):
        raise TraceSchemaError(
            f"oracle_input must be boolean, got {type(data['oracle_input']).__name__}"
        )

    raw_ip = data["instruction_parse"]
    if (
        not isinstance(raw_ip, dict)
        or "status" not in raw_ip
        or "goal_program_hash" not in raw_ip
    ):
        raise TraceSchemaError(
            "instruction_parse must be an object with 'status' and 'goal_program_hash'"
        )
    instruction_parse = InstructionParseRecord(
        status=str(raw_ip["status"]),
        goal_program_hash=str(raw_ip["goal_program_hash"]),
    )

    raw_val = data["validation"]
    if not isinstance(raw_val, dict) or not all(
        k in raw_val for k in ("accepted", "rejected", "uncertain")
    ):
        raise TraceSchemaError(
            "validation must be an object with "
            "'accepted', 'rejected', 'uncertain' arrays"
        )
    validation = ValidationRecord(
        accepted=tuple(raw_val["accepted"]),
        rejected=tuple(raw_val["rejected"]),
        uncertain=tuple(raw_val["uncertain"]),
    )

    raw_outcome = data["episode_outcome"]
    outcome: EpisodeOutcome | None = None
    if raw_outcome is not None:
        try:
            outcome = EpisodeOutcome(raw_outcome)
        except ValueError as exc:
            raise TraceSchemaError(
                f"Invalid typed episode_outcome: {raw_outcome!r}"
            ) from exc

    raw_symbolic = data["symbolic_action"]
    symbolic_action: tuple[str, ...] | None = None
    if raw_symbolic is not None:
        if not isinstance(raw_symbolic, (list, tuple)):
            raise TraceSchemaError("symbolic_action must be a list or tuple")
        symbolic_action = tuple(raw_symbolic)

    return TraceRecord(
        schema_version=data["schema_version"],
        episode_id=data["episode_id"],
        method=data["method"],
        oracle_input=data["oracle_input"],
        step=int(data["step"]),
        manifest_hash=data["manifest_hash"],
        config_hash=data["config_hash"],
        instruction_parse=instruction_parse,
        observation_id=data["observation_id"],
        evidence_ids=tuple(data["evidence_ids"]),
        belief_state_hash=data["belief_state_hash"],
        committed_state_hash=data["committed_state_hash"],
        validation=validation,
        problem_hash=data["problem_hash"],
        plan_status=data["plan_status"],
        symbolic_action=symbolic_action,
        primitive_action=data["primitive_action"],
        action_succeeded=bool(data["action_succeeded"]),
        failure_reason=data["failure_reason"],
        monitor_decision=data["monitor_decision"],
        replan_reason=data["replan_reason"],
        task_success=bool(data["task_success"]),
        episode_outcome=outcome,
    )


def compute_record_hash(record: TraceRecord) -> str:
    """Computes deterministic SHA-256 hash for a canonical TraceRecord."""
    return hashlib.sha256(serialize_record(record).encode("utf-8")).hexdigest()


def compute_decision_hash(record: TraceRecord) -> str:
    """Computes deterministic SHA-256 hash for the action decision and outcome."""
    decision_payload = json.dumps(
        {
            "step": record.step,
            "symbolic_action": record.symbolic_action,
            "primitive_action": record.primitive_action,
            "action_succeeded": record.action_succeeded,
            "failure_reason": record.failure_reason,
            "monitor_decision": record.monitor_decision,
            "replan_reason": record.replan_reason,
            "task_success": record.task_success,
            "episode_outcome": (
                record.episode_outcome.value if record.episode_outcome else None
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(decision_payload.encode("utf-8")).hexdigest()


def verify_replay_consistency(
    original_records: Sequence[TraceRecord],
    replay_records: Sequence[TraceRecord],
    raise_on_error: bool = False,
) -> bool:
    """Verify 100% consistency between original trace records and replay records."""
    if not original_records or not replay_records:
        if raise_on_error:
            raise ReplayMismatchError("Trace records cannot be empty.")
        return False

    if len(original_records) != len(replay_records):
        if raise_on_error:
            raise ReplayMismatchError(
                f"Trace length mismatch: "
                f"original={len(original_records)}, "
                f"replay={len(replay_records)}"
            )
        return False

    critical_fields = (
        "step",
        "belief_state_hash",
        "committed_state_hash",
        "problem_hash",
        "plan_status",
        "symbolic_action",
        "primitive_action",
        "action_succeeded",
        "monitor_decision",
        "replan_reason",
        "task_success",
        "episode_outcome",
    )

    for i, (original, replay) in enumerate(
        zip(original_records, replay_records, strict=True)
    ):
        if original == replay:
            continue

        mismatched_fields = [
            f
            for f in critical_fields
            if getattr(original, f, None) != getattr(replay, f, None)
        ]

        if not mismatched_fields and original != replay:
            mismatched_fields = ["metadata"]

        if raise_on_error:
            details = ", ".join(
                f"{f} (original={getattr(original, f, None)!r} "
                f"vs replay={getattr(replay, f, None)!r})"
                for f in mismatched_fields
            )
            raise ReplayMismatchError(f"Mismatch at step {i}: {details}")

        return False

    return True


def scan_record_for_leakage(
    payload: str | dict[str, Any] | TraceRecord,
) -> list[str]:
    """Scan a trace record or dict for forbidden private data or oracle leakage."""
    if isinstance(payload, TraceRecord):
        data: dict[str, Any] = json.loads(serialize_record(payload))
    elif isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            return [f"Malformed JSON: {exc}"]
    elif isinstance(payload, dict):
        data = payload
    else:
        return [f"Unexpected payload type: {type(payload).__name__}"]

    violations: list[str] = []

    def _check_dict(d: dict[str, Any], path: str = "") -> None:
        for k, v in d.items():
            current_path = f"{path}.{k}" if path else k
            if k in FORBIDDEN_PRIVATE_FIELDS:
                violations.append(f"Forbidden private field found: '{current_path}'")
            if isinstance(v, dict):
                _check_dict(v, current_path)

    _check_dict(data)

    method = data.get("method")
    oracle_input = data.get("oracle_input")
    if method in ("V0R0", "V1R0", "V1R1") and oracle_input is True:
        violations.append(
            f"Oracle leakage: method '{method}' cannot have oracle_input=True"
        )
    if method == "B3" and oracle_input is False:
        violations.append("B3 baseline must have oracle_input=True")

    return violations
