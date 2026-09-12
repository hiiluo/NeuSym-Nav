"""Security and anti-leakage tests for TraceRecord and JSONL traces."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from neuro_symbolic_vln.trace import (
    FORBIDDEN_PRIVATE_FIELDS,
    InstructionParseRecord,
    TraceRecord,
    ValidationRecord,
    scan_record_for_leakage,
    serialize_record,
)


@pytest.fixture
def clean_trace_record() -> TraceRecord:
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


def test_trace_record_has_no_forbidden_private_fields() -> None:
    record_fields = set(TraceRecord.__dataclass_fields__.keys())
    leaked = record_fields & FORBIDDEN_PRIVATE_FIELDS
    assert not leaked, f"TraceRecord definition contains forbidden fields: {leaked}"


def test_clean_record_passes_security_scan(clean_trace_record: TraceRecord) -> None:
    violations = scan_record_for_leakage(clean_trace_record)
    assert violations == [], f"Unexpected violations on clean record: {violations}"


def test_scan_detects_forbidden_sidecar_fields(clean_trace_record: TraceRecord) -> None:
    base_dict = asdict(clean_trace_record)

    forbidden_samples = [
        ("optimal_grid_distance", 5),
        ("optimal_primitive_actions", 8),
        ("oracle_target_entity_id", "target-green-ball"),
        ("solvable", True),
        ("uncorrupted_evidence_hash", "sha256:SECRET_HASH"),
        ("intervention", {"type": "door_relock", "recoverable": True}),
        ("grid", [[0, 1], [1, 0]]),
        ("full_grid", {"width": 10, "height": 10}),
    ]

    for key, value in forbidden_samples:
        leaked_dict = dict(base_dict)
        leaked_dict[key] = value
        violations = scan_record_for_leakage(leaked_dict)
        assert any(key in v for v in violations), (
            f"Failed to detect forbidden field '{key}' in trace record"
        )


def test_scan_detects_nested_forbidden_fields(clean_trace_record: TraceRecord) -> None:
    base_dict = asdict(clean_trace_record)
    base_dict["instruction_parse"]["oracle_target_entity_id"] = "secret_target"
    violations = scan_record_for_leakage(base_dict)
    assert any("oracle_target_entity_id" in v for v in violations)


def test_oracle_input_flag_enforcement_for_normal_methods(
    clean_trace_record: TraceRecord,
) -> None:
    base_dict = asdict(clean_trace_record)

    for method in ("V0R0", "V1R0", "V1R1"):
        base_dict["method"] = method
        base_dict["oracle_input"] = True
        violations = scan_record_for_leakage(base_dict)
        assert any("Oracle leakage" in v for v in violations), (
            f"Expected oracle leakage violation for {method} with oracle_input=True"
        )

        base_dict["oracle_input"] = False
        violations_clean = scan_record_for_leakage(base_dict)
        assert not any("Oracle leakage" in v for v in violations_clean)


def test_oracle_input_flag_enforcement_for_b3(
    clean_trace_record: TraceRecord,
) -> None:
    base_dict = asdict(clean_trace_record)
    base_dict["method"] = "B3"
    base_dict["oracle_input"] = False
    violations = scan_record_for_leakage(base_dict)
    assert any("B3 baseline must have oracle_input=True" in v for v in violations)

    base_dict["oracle_input"] = True
    violations_clean = scan_record_for_leakage(base_dict)
    assert not any("B3" in v for v in violations_clean)


def test_serialized_json_contains_no_forbidden_substrings(
    clean_trace_record: TraceRecord,
) -> None:
    serialized = serialize_record(clean_trace_record)
    for forbidden in FORBIDDEN_PRIVATE_FIELDS:
        assert f'"{forbidden}"' not in serialized
