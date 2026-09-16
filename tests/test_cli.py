from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import asdict
from pathlib import Path

from neuro_symbolic_vln.cli import _run_validate_traces
from neuro_symbolic_vln.contracts import EpisodeOutcome
from neuro_symbolic_vln.trace import (
    InstructionParseRecord,
    TraceRecord,
    ValidationRecord,
    serialize_record,
)


def _terminal_record() -> TraceRecord:
    return TraceRecord(
        schema_version="1.0",
        episode_id="diagnostic-episode",
        method="V1R1",
        oracle_input=False,
        step=0,
        manifest_hash="manifest",
        config_hash="config",
        instruction_parse=InstructionParseRecord(
            status="deterministic", goal_program_hash="goal"
        ),
        observation_id="observation-0",
        evidence_ids=(),
        belief_state_hash="belief",
        committed_state_hash="committed",
        validation=ValidationRecord(accepted=(), rejected=(), uncertain=()),
        problem_hash="problem",
        plan_status="found",
        symbolic_action=None,
        primitive_action=None,
        action_succeeded=True,
        failure_reason=None,
        monitor_decision=None,
        replan_reason=None,
        task_success=True,
        episode_outcome=EpisodeOutcome.SUCCESS,
    )


def test_validate_traces_accepts_typed_trace_without_leakage(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "episode.jsonl").write_text(serialize_record(_terminal_record()) + "\n")

    assert _run_validate_traces(Namespace(runs=str(tmp_path), episodes=None)) == 0
    assert "1 records scanned" in capsys.readouterr().out


def test_validate_traces_rejects_private_field_even_when_schema_parses(
    tmp_path: Path,
    capsys,
) -> None:
    payload = asdict(_terminal_record())
    payload["grid"] = "private simulator state"
    (tmp_path / "episode.jsonl").write_text(json.dumps(payload) + "\n")

    assert _run_validate_traces(Namespace(runs=str(tmp_path), episodes=None)) == 6
    captured = capsys.readouterr()
    assert "Forbidden private field" in captured.err


def test_cli_audit_portability(capsys) -> None:
    from neuro_symbolic_vln.cli import _run_audit_portability

    status = _run_audit_portability(Namespace(src="src/neuro_symbolic_vln"))
    assert status == 0
    captured = capsys.readouterr()
    assert "PASS — core modules decoupled from MiniGrid" in captured.out


def test_cli_validate_habitat_decision(tmp_path: Path, capsys) -> None:
    import yaml

    from neuro_symbolic_vln.cli import _run_validate_habitat_decision

    dec_file = tmp_path / "decision.yaml"
    dec_file.write_text(
        yaml.safe_dump(
            {
                "decision": "Conditional hold",
                "candidate_sha": "b35a862b1234567890abcdef1234567890abcdef",
                "gates": {
                    "engineering_gates": "PASS",
                    "planning_control_gates": "PASS",
                    "local_clean_gates": "PASS",
                    "rq1_gates": "HOLD",
                    "rq2_gates": "PASS",
                },
                "evidence_links": ["runs/final"],
                "unresolved_limitations": ["probe topology"],
            }
        )
    )

    status = _run_validate_habitat_decision(Namespace(report=str(dec_file)))
    assert status == 0
    captured = capsys.readouterr()
    assert "PASS — decision 'Conditional hold' is valid" in captured.out
