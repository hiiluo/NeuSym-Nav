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
