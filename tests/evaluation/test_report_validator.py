from __future__ import annotations

from pathlib import Path

import yaml

from neuro_symbolic_vln.evaluation.report_validator import (
    audit_portability,
    validate_habitat_decision,
    validate_report,
)


def test_audit_portability_clean() -> None:
    result = audit_portability("src/neuro_symbolic_vln")
    assert result["ok"] is True
    assert result["violations"] == []
    assert result["files_scanned"] > 20


def test_audit_portability_detects_violation(tmp_path: Path) -> None:
    bad_file = tmp_path / "planning" / "bad_module.py"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text("import minigrid\n")

    result = audit_portability(tmp_path)
    assert result["ok"] is False
    assert len(result["violations"]) == 1
    assert "disallowed import 'minigrid'" in result["violations"][0]


def test_validate_habitat_decision_accepts_valid_decision(tmp_path: Path) -> None:
    decision_file = tmp_path / "habitat_decision.yaml"
    decision_content = {
        "decision": "Conditional hold",
        "candidate_sha": "b35a862b1234567890abcdef1234567890abcdef",
        "gates": {
            "engineering_gates": "PASS",
            "planning_control_gates": "PASS",
            "local_clean_gates": "PASS",
            "rq1_gates": "HOLD (practical gain not demonstrated in all strata)",
            "rq2_gates": "PASS",
        },
        "evidence_links": [
            "runs/final/rq1_test.summary.json",
            "reports/month1/rq_summary.md",
        ],
        "unresolved_limitations": [
            "Narrow probe topology in generation",
            "Key-door overlap vs front-cell semantics",
        ],
    }
    decision_file.write_text(yaml.safe_dump(decision_content))

    result = validate_habitat_decision(decision_file)
    assert result["ok"] is True
    assert result["decision"] == "Conditional hold"
    assert result["mismatches"] == []


def test_validate_habitat_decision_rejects_invalid_values(tmp_path: Path) -> None:
    decision_file = tmp_path / "invalid_decision.yaml"
    # Invalid decision type
    decision_file.write_text(
        yaml.safe_dump({"decision": "Maybe", "candidate_sha": "1234567"})
    )

    result = validate_habitat_decision(decision_file)
    assert result["ok"] is False
    assert any("decision must be exactly one of" in m for m in result["mismatches"])


def test_validate_habitat_decision_rejects_advance_with_failing_gate(
    tmp_path: Path,
) -> None:
    decision_file = tmp_path / "premature_advance.yaml"
    decision_content = {
        "decision": "Advance",
        "candidate_sha": "b35a862b1234567890abcdef1234567890abcdef",
        "gates": {
            "engineering_gates": "PASS",
            "planning_control_gates": "PASS",
            "local_clean_gates": "PASS",
            "rq1_gates": "FAIL (underperforming baseline)",
            "rq2_gates": "PASS",
        },
        "evidence_links": ["runs/final"],
        "unresolved_limitations": [],
    }
    decision_file.write_text(yaml.safe_dump(decision_content))

    result = validate_habitat_decision(decision_file)
    assert result["ok"] is False
    assert any("requires PASS" in m for m in result["mismatches"])


def test_validate_report_accepts_compliant_report(tmp_path: Path) -> None:
    report_file = tmp_path / "research_report.md"
    report_text = """# Final Month 1 Neuro-Symbolic VLN Report

## Executive Summary
This report summarizes the month-one evaluation on candidate SHA b35a862.

## Methods & Experimental Design
We evaluate V0R0, V1R0, V1R1 and B3 with configs in
configs/smoke.yaml and configs/rq1_test.yaml.

## RQ1 Results
Results under N1 corruption show trade-offs recorded in rq1_summary.json.

## RQ2 Results
Recovery rates under N2 interventions are detailed in rq2_summary.json.

## Threats to Validity
Simulated noise and 2D grid discrete actions limit external validity.

## Explicit Non-Claims
We make NO claims that this 2D proof of concept demonstrates
photorealistic generalization or proves 3D continuous Habitat performance.

## Gate Assessment
Evaluated against gates G0 through G5.

## Protocol Deviations
All deviations D-001, D-002, D-003, D-004, D-005, D-006, and D-007
are tracked and documented.
"""
    report_file.write_text(report_text)

    result = validate_report(report_file)
    assert result["ok"] is True
    assert len(result["sections"]) == 8
    assert result["mismatches"] == []


def test_validate_report_rejects_missing_sections(tmp_path: Path) -> None:
    report_file = tmp_path / "short_report.md"
    report_file.write_text("# Report\nJust a short note.\n")

    result = validate_report(report_file)
    assert result["ok"] is False
    assert len(result["mismatches"]) > 0
