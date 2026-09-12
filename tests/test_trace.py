"""Tests for TraceRecord serialization, schema validation, hashing, and replay."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pytest

from neuro_symbolic_vln.contracts import EpisodeOutcome
from neuro_symbolic_vln.trace import (
    REQUIRED_TRACE_FIELDS,
    InstructionParseRecord,
    ReplayMismatchError,
    TraceRecord,
    TraceSchemaError,
    ValidationRecord,
    compute_decision_hash,
    compute_record_hash,
    deserialize_record,
    serialize_record,
    verify_replay_consistency,
)


@pytest.fixture
def sample_intermediate_record() -> TraceRecord:
    return TraceRecord(
        schema_version="1.0",
        episode_id="goto-test-0042",
        method="V1R1",
        oracle_input=False,
        step=17,
        manifest_hash="sha256:PUBLIC_MANIFEST_HASH",
        config_hash="sha256:PUBLIC_CONFIG_HASH",
        instruction_parse=InstructionParseRecord(
            status="deterministic",
            goal_program_hash="sha256:GOAL_HASH",
        ),
        observation_id="obs-17",
        evidence_ids=("ev-101", "ev-102"),
        belief_state_hash="sha256:BELIEF_HASH",
        committed_state_hash="sha256:STATE_HASH",
        validation=ValidationRecord(
            accepted=("ev-101",),
            rejected=(),
            uncertain=("ev-102",),
        ),
        problem_hash="sha256:PDDL_HASH",
        plan_status="found",
        symbolic_action=("move-forward", "robot", "loc-3", "loc-4", "east"),
        primitive_action="move_forward",
        action_succeeded=False,
        failure_reason="blocked",
        monitor_decision="invalidate_and_reobserve",
        replan_reason="predicted_move_failed",
        task_success=False,
        episode_outcome=None,
    )


@pytest.fixture
def sample_terminal_record(sample_intermediate_record: TraceRecord) -> TraceRecord:
    record_dict = asdict(sample_intermediate_record)
    record_dict["step"] = 18
    record_dict["action_succeeded"] = True
    record_dict["task_success"] = True
    record_dict["episode_outcome"] = EpisodeOutcome.SUCCESS
    record_dict["monitor_decision"] = None
    record_dict["replan_reason"] = None
    record_dict["failure_reason"] = None
    return deserialize_record(record_dict)


def test_trace_record_round_trip_intermediate(
    sample_intermediate_record: TraceRecord,
) -> None:
    serialized = serialize_record(sample_intermediate_record)
    deserialized = deserialize_record(serialized)
    assert deserialized == sample_intermediate_record


def test_trace_record_round_trip_terminal(
    sample_terminal_record: TraceRecord,
) -> None:
    serialized = serialize_record(sample_terminal_record)
    deserialized = deserialize_record(serialized)
    assert deserialized == sample_terminal_record
    assert deserialized.episode_outcome == EpisodeOutcome.SUCCESS


def test_serialize_record_canonical_format(
    sample_intermediate_record: TraceRecord,
) -> None:
    serialized = serialize_record(sample_intermediate_record)
    # Check that keys are sorted alphabetically
    parsed: dict[str, Any] = json.loads(serialized)
    expected_keys = sorted(parsed.keys())
    assert list(parsed.keys()) == expected_keys

    # Check that separators have no extraneous whitespace
    assert ": " not in serialized
    assert ", " not in serialized


def test_deserialize_rejects_missing_required_fields(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    for field in REQUIRED_TRACE_FIELDS:
        corrupted = dict(base_dict)
        del corrupted[field]
        with pytest.raises(TraceSchemaError, match="Missing required fields"):
            deserialize_record(corrupted)


def test_deserialize_rejects_unsupported_schema_version(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    base_dict["schema_version"] = "2.0"
    with pytest.raises(TraceSchemaError, match="Unsupported schema_version"):
        deserialize_record(base_dict)


def test_deserialize_rejects_non_boolean_oracle_input(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    base_dict["oracle_input"] = "false"
    with pytest.raises(TraceSchemaError, match="oracle_input must be boolean"):
        deserialize_record(base_dict)


def test_deserialize_rejects_invalid_instruction_parse(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    base_dict["instruction_parse"] = {"status": "deterministic"}
    with pytest.raises(TraceSchemaError, match="instruction_parse"):
        deserialize_record(base_dict)


def test_deserialize_rejects_invalid_validation(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    base_dict["validation"] = {"accepted": []}
    with pytest.raises(TraceSchemaError, match="validation"):
        deserialize_record(base_dict)


def test_deserialize_rejects_invalid_json() -> None:
    with pytest.raises(TraceSchemaError, match="Malformed JSON payload"):
        deserialize_record("{broken-json")


def test_deserialize_rejects_invalid_payload_type() -> None:
    with pytest.raises(TraceSchemaError, match="Expected str or dict"):
        deserialize_record(123)  # type: ignore[arg-type]


def test_all_typed_episode_outcomes_serializable(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    for outcome in EpisodeOutcome:
        base_dict["episode_outcome"] = outcome.value
        record = deserialize_record(base_dict)
        assert record.episode_outcome == outcome

        serialized = serialize_record(record)
        round_tripped = deserialize_record(serialized)
        assert round_tripped.episode_outcome == outcome


def test_deserialize_rejects_untyped_episode_outcome(
    sample_intermediate_record: TraceRecord,
) -> None:
    base_dict = asdict(sample_intermediate_record)
    base_dict["episode_outcome"] = "FAILED"
    with pytest.raises(TraceSchemaError, match="Invalid typed episode_outcome"):
        deserialize_record(base_dict)


def test_record_hash_stability(sample_intermediate_record: TraceRecord) -> None:
    h1 = compute_record_hash(sample_intermediate_record)
    h2 = compute_record_hash(sample_intermediate_record)
    assert h1 == h2
    assert len(h1) == 64


def test_record_hash_sensitivity(sample_intermediate_record: TraceRecord) -> None:
    h_orig = compute_record_hash(sample_intermediate_record)
    record_dict = asdict(sample_intermediate_record)
    record_dict["step"] = 18
    modified_record = deserialize_record(record_dict)
    assert compute_record_hash(modified_record) != h_orig


def test_decision_hash_stability_and_sensitivity(
    sample_intermediate_record: TraceRecord,
) -> None:
    d1 = compute_decision_hash(sample_intermediate_record)
    d2 = compute_decision_hash(sample_intermediate_record)
    assert d1 == d2

    # Changing observation_id (not part of decision) preserves decision hash
    record_dict = asdict(sample_intermediate_record)
    record_dict["observation_id"] = "obs-different"
    obs_modified = deserialize_record(record_dict)
    assert compute_decision_hash(obs_modified) == d1

    # Changing primitive action changes decision hash
    record_dict["primitive_action"] = "turn_left"
    action_modified = deserialize_record(record_dict)
    assert compute_decision_hash(action_modified) != d1


def test_verify_replay_consistency_success(
    sample_intermediate_record: TraceRecord,
    sample_terminal_record: TraceRecord,
) -> None:
    original = [sample_intermediate_record, sample_terminal_record]
    replay = [sample_intermediate_record, sample_terminal_record]
    assert verify_replay_consistency(original, replay) is True


def test_verify_replay_consistency_length_mismatch(
    sample_intermediate_record: TraceRecord,
    sample_terminal_record: TraceRecord,
) -> None:
    original = [sample_intermediate_record, sample_terminal_record]
    replay = [sample_intermediate_record]
    assert verify_replay_consistency(original, replay) is False
    with pytest.raises(ReplayMismatchError, match="Trace length mismatch"):
        verify_replay_consistency(original, replay, raise_on_error=True)


def test_verify_replay_consistency_step_mismatch(
    sample_intermediate_record: TraceRecord,
) -> None:
    record_dict = asdict(sample_intermediate_record)
    record_dict["primitive_action"] = "turn_right"
    mismatched = deserialize_record(record_dict)

    original = [sample_intermediate_record]
    replay = [mismatched]
    assert verify_replay_consistency(original, replay) is False
    with pytest.raises(ReplayMismatchError, match="primitive_action"):
        verify_replay_consistency(original, replay, raise_on_error=True)


def test_verify_replay_consistency_state_hash_mismatch(
    sample_intermediate_record: TraceRecord,
) -> None:
    record_dict = asdict(sample_intermediate_record)
    record_dict["belief_state_hash"] = "sha256:DIFFERENT_HASH"
    mismatched = deserialize_record(record_dict)

    original = [sample_intermediate_record]
    replay = [mismatched]
    assert verify_replay_consistency(original, replay) is False
    with pytest.raises(ReplayMismatchError, match="belief_state_hash"):
        verify_replay_consistency(original, replay, raise_on_error=True)


def test_verify_replay_consistency_empty_traces() -> None:
    assert verify_replay_consistency([], []) is False
    with pytest.raises(ReplayMismatchError, match="cannot be empty"):
        verify_replay_consistency([], [], raise_on_error=True)
