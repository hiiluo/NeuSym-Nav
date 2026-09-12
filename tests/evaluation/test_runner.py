from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuro_symbolic_vln.evaluation.manifests import (
    generate_manifests,
    stable_hash,
    write_manifests,
)
from neuro_symbolic_vln.evaluation.runner import (
    ConfigHashMismatchError,
    ManifestHashMismatchError,
    load_manifests,
    run_config,
    validate_results,
)


def _generator_config() -> dict:
    return {
        "generator_version": "minigrid-core-v1",
        "public_action_budget": 32,
        "splits": {
            "smoke": {"combo_start": 0, "combo_count": 2},
        },
    }


def _write_smoke_manifests(tmp_path: Path) -> Path:
    result = generate_manifests(_generator_config())
    manifests_dir = tmp_path / "manifests"
    write_manifests(manifests_dir, result)
    return manifests_dir


def _run_config(
    tmp_path: Path,
    manifests_dir: Path,
    method: str = "B3",
    run_id: str = "smoke-b3",
) -> dict:
    return {
        "run_id": run_id,
        "method": method,
        "manifests_dir": str(manifests_dir),
        "output_dir": str(tmp_path / "runs"),
        "splits": ["smoke"],
    }


def test_load_manifests_verifies_frozen_hashes(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    loaded = load_manifests(manifests_dir)
    assert len(loaded.publics) == 4
    assert len(loaded.sidecars) == 4


def test_load_manifests_detects_drift(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    smoke_path = manifests_dir / "smoke.jsonl"
    original = smoke_path.read_text().splitlines()
    tampered = []
    for line in original:
        payload = json.loads(line)
        payload["instruction"] = payload["instruction"] + " tampered"
        tampered.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    smoke_path.write_text("\n".join(tampered) + "\n")

    with pytest.raises(ManifestHashMismatchError):
        load_manifests(manifests_dir)


def test_run_config_b3_produces_rows_and_summary(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = _run_config(tmp_path, manifests_dir)

    report = run_config(config)

    assert report.n_rows == 4
    assert report.n_executed == 4
    assert report.n_skipped == 0
    assert report.summary is not None
    assert report.rows_path.exists()
    assert report.summary_path.exists()

    rows = [
        json.loads(line)
        for line in report.rows_path.read_text().splitlines()
    ]
    assert len(rows) == 4
    for row in rows:
        assert row["status"] == "ok"
        assert row["config_hash"] == report.config_hash
        assert isinstance(row["success"], bool)


def test_run_config_v1r1_now_executes(tmp_path: Path) -> None:
    """V1R1 was a stub in A-07 skeleton; the full runner treats it as
    executable alongside B3 once the closed-loop wiring lands."""
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = _run_config(
        tmp_path, manifests_dir, method="V1R1", run_id="smoke-v1r1"
    )

    report = run_config(config)

    assert report.n_executed == 4
    assert report.n_skipped == 0
    rows = [
        json.loads(line)
        for line in report.rows_path.read_text().splitlines()
    ]
    assert all(row["status"] == "ok" for row in rows)
    assert all(row["method"] == "V1R1" for row in rows)


def test_run_config_matrix_produces_row_per_crossing(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = {
        "run_id": "smoke-matrix",
        "matrix": [
            {"method": "B3", "condition": "clean"},
            {"method": "V1R1", "condition": "clean"},
        ],
        "manifests_dir": str(manifests_dir),
        "output_dir": str(tmp_path / "runs"),
        "splits": ["smoke"],
    }
    report = run_config(config)

    assert report.n_rows == 8  # 4 episodes × 2 crossings
    rows = [
        json.loads(line)
        for line in report.rows_path.read_text().splitlines()
    ]
    methods = {row["method"] for row in rows}
    assert methods == {"B3", "V1R1"}
    assert {row["condition"] for row in rows} == {"clean"}


def test_run_config_unknown_method_marks_skipped(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = _run_config(
        tmp_path, manifests_dir, method="B4", run_id="smoke-b4"
    )
    report = run_config(config)
    assert report.n_executed == 0
    assert report.n_skipped == 4
    rows = [
        json.loads(line)
        for line in report.rows_path.read_text().splitlines()
    ]
    assert all(row["status"] == "method_unavailable" for row in rows)


def test_run_config_rejects_config_hash_drift(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = _run_config(tmp_path, manifests_dir)
    config["config_hash_expected"] = "sha256:deadbeef"

    with pytest.raises(ConfigHashMismatchError):
        run_config(config)


def test_run_config_accepts_matching_config_hash(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    config = _run_config(tmp_path, manifests_dir)
    # Freeze the hash by computing it before assignment.
    excluded = {"config_hash_expected", "notes"}
    computed = stable_hash({k: v for k, v in config.items() if k not in excluded})
    config["config_hash_expected"] = computed

    report = run_config(config)
    assert report.config_hash == computed


def test_validate_results_flags_row_count_and_missing_runs(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    run_config(_run_config(tmp_path, manifests_dir, run_id="smoke-b3"))

    runs_dir = tmp_path / "runs"
    expected = {
        "smoke-b3": {"row_count": 4, "method": "B3"},
        "rq1-b3": {"row_count": 999, "method": "B3"},
    }
    report = validate_results(runs_dir, expected)

    assert not report["ok"]
    reasons = {m["reason"] for m in report["mismatches"]}
    assert "artifacts_missing" in reasons
    assert report["total_expected_rows"] == 4 + 999


def test_validate_results_passes_on_match(tmp_path: Path) -> None:
    manifests_dir = _write_smoke_manifests(tmp_path)
    report_exec = run_config(_run_config(tmp_path, manifests_dir, run_id="smoke-b3"))

    runs_dir = tmp_path / "runs"
    expected = {
        "smoke-b3": {
            "row_count": 4,
            "method": "B3",
            "config_hash_expected": report_exec.config_hash,
        },
    }
    report = validate_results(runs_dir, expected)

    assert report["ok"]
    assert report["mismatches"] == []
    assert report["total_expected_rows"] == report["total_actual_rows"] == 4
