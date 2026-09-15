from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import yaml


def audit_portability(src_dir: str | Path = "src/neuro_symbolic_vln") -> dict[str, Any]:
    """Scan source files to verify that core symbolic modules do not import MiniGrid.

    MiniGrid must be strictly isolated to the env/ and evaluation/interventions modules.
    Contracts, belief, planning, control, language, and perception must remain
    pure and portable to non-grid environments (e.g. Habitat).
    """
    root = Path(src_dir)
    violations: list[str] = []
    files_scanned = 0

    # Modules allowed to import minigrid
    allowed_rel_prefixes = ("env/", "evaluation/interventions.py")

    for py_file in sorted(root.rglob("*.py")):
        rel_path = py_file.relative_to(root).as_posix()
        files_scanned += 1

        is_allowed = any(
            rel_path.startswith(prefix) or rel_path == prefix
            for prefix in allowed_rel_prefixes
        )
        if is_allowed:
            continue

        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError as exc:
            violations.append(f"{rel_path}: syntax error: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("minigrid") or alias.name.startswith(
                        "gymnasium"
                    ):
                        violations.append(
                            f"{rel_path}:{node.lineno}: disallowed import "
                            f"'{alias.name}' in portable module"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module.startswith("minigrid")
                    or node.module.startswith("gymnasium")
                ):
                    violations.append(
                        f"{rel_path}:{node.lineno}: disallowed from-import "
                        f"'{node.module}' in portable module"
                    )

    return {
        "ok": len(violations) == 0,
        "files_scanned": files_scanned,
        "violations": violations,
    }


def validate_report(report_path_or_dir: str | Path) -> dict[str, Any]:
    """Validate research closure report for completeness and non-claims."""
    target = Path(report_path_or_dir)
    mismatches: list[str] = []

    report_file: Path | None = None
    if target.is_file():
        report_file = target
        report_dir = target.parent
    elif target.is_dir():
        report_dir = target
        for candidate in (
            "research_report.md",
            "final_report.md",
            "report.md",
            "month1_report.md",
        ):
            p = report_dir / candidate
            if p.exists():
                report_file = p
                break
        if report_file is None:
            # Fall back to any .md file in the directory
            mds = [
                f
                for f in sorted(report_dir.glob("*.md"))
                if not f.name.startswith("rq")
            ]
            if mds:
                report_file = mds[0]
    else:
        return {
            "ok": False,
            "mismatches": [f"path does not exist: {target}"],
            "sections": [],
        }

    if report_file is None or not report_file.exists():
        return {
            "ok": False,
            "mismatches": [f"no report markdown file found in {target}"],
            "sections": [],
        }

    content = report_file.read_text()
    sections_found: list[str] = []

    # Required section patterns
    required_sections = {
        "Executive Summary": [
            r"#+\s+.*executive\s+summary",
            r"#+\s+.*tổng\s+quan",
            r"#+\s+.*summary",
        ],
        "Methods & Experimental Design": [
            r"#+\s+.*method",
            r"#+\s+.*experimental\s+design",
            r"#+\s+.*thiết\s+kế",
        ],
        "RQ1 Results": [r"#+\s+.*rq1", r"#+\s+.*research\s+question\s+1"],
        "RQ2 Results": [r"#+\s+.*rq2", r"#+\s+.*research\s+question\s+2"],
        "Threats to Validity": [
            r"#+\s+.*threat",
            r"#+\s+.*limitation",
            r"#+\s+.*hạn\s+chế",
        ],
        "Explicit Non-Claims": [r"#+\s+.*non-claim", r"#+\s+.*explicit\s+non-claim"],
        "Gate Assessment": [r"#+\s+.*gate", r"#+\s+.*đánh\s+giá\s+gate"],
        "Protocol Deviations": [
            r"#+\s+.*deviation",
            r"#+\s+.*sai\s+lệch\s+giao\s+thức",
        ],
    }

    for section_name, patterns in required_sections.items():
        found = False
        for pat in patterns:
            if re.search(pat, content, re.IGNORECASE):
                found = True
                sections_found.append(section_name)
                break
        if not found:
            mismatches.append(f"missing required section: '{section_name}'")

    # Check evidence links: must reference commit/SHA, configs, summaries
    has_sha = bool(re.search(r"\b[0-9a-f]{7,40}\b", content, re.IGNORECASE))
    has_configs = bool(re.search(r"configs/[\w.-]+\.yaml", content))
    has_summaries = bool(
        re.search(r"(rq[12]_summary|\.jsonl|\.summary\.json)", content)
    )
    if not (has_sha and has_configs and has_summaries):
        mismatches.append(
            "missing evidence links (must cite frozen SHA, configs, "
            "and summary/trace artifacts)"
        )

    # Check for disallowed unhedged claims
    disallowed_claim_patterns = [
        r"proves\s+(?:3d|habitat)\s+performance",
        r"demonstrates\s+photorealistic\s+generalization",
        r"solves\s+natural\s+vln\s+end-to-end",
    ]
    for pat in disallowed_claim_patterns:
        match = re.search(pat, content, re.IGNORECASE)
        if match:
            # Check if this occurrence is under a non-claims section
            lines = content.splitlines()
            for line in lines:
                if re.search(pat, line, re.IGNORECASE):
                    # If line does not contain 'not', 'no', 'cannot', 'non-claim'
                    if not re.search(
                        r"\b(not|no|cannot|non-claim|disclaim|limitation)\b",
                        line,
                        re.IGNORECASE,
                    ):
                        mismatches.append(
                            f"unhedged/disallowed empirical claim: '{line.strip()}'"
                        )

    # Check that protocol deviations D-001 through D-007 are discussed
    for dev_id in ("D-001", "D-002", "D-003", "D-004", "D-005", "D-006", "D-007"):
        if dev_id not in content:
            mismatches.append(
                f"deviation {dev_id} is not listed in report protocol deviations"
            )

    # Numeric verification if summaries are available
    rq1_json = report_dir / "rq1_summary.json"
    if rq1_json.exists():
        try:
            rq1_data = json.loads(rq1_json.read_text())
            # Basic sanity check that data is structured
            if not isinstance(rq1_data, list) or len(rq1_data) == 0:
                mismatches.append("rq1_summary.json is empty or invalid")
        except json.JSONDecodeError as exc:
            mismatches.append(f"corrupt rq1_summary.json: {exc}")

    rq2_json = report_dir / "rq2_summary.json"
    if rq2_json.exists():
        try:
            rq2_data = json.loads(rq2_json.read_text())
            if not isinstance(rq2_data, list) or len(rq2_data) == 0:
                mismatches.append("rq2_summary.json is empty or invalid")
        except json.JSONDecodeError as exc:
            mismatches.append(f"corrupt rq2_summary.json: {exc}")

    return {
        "ok": len(mismatches) == 0,
        "report_file": str(report_file),
        "sections": sections_found,
        "mismatches": mismatches,
    }


def validate_habitat_decision(decision_file_path: str | Path) -> dict[str, Any]:
    """Validate habitat migration decision file against rubric and criteria."""
    path = Path(decision_file_path)
    mismatches: list[str] = []

    if not path.exists():
        return {
            "ok": False,
            "decision": "None",
            "mismatches": [f"file not found: {path}"],
        }

    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return {
            "ok": False,
            "decision": "None",
            "mismatches": [f"yaml syntax error: {exc}"],
        }

    if not isinstance(data, dict):
        return {
            "ok": False,
            "decision": "None",
            "mismatches": ["decision file must be a YAML mapping"],
        }

    decision = data.get("decision")
    allowed_decisions = {"Advance", "Conditional hold", "No-go"}
    if decision not in allowed_decisions:
        mismatches.append(
            f"decision must be exactly one of {sorted(allowed_decisions)}, "
            f"got: {decision}"
        )

    # Check candidate/frozen sha
    sha = data.get("candidate_sha") or data.get("frozen_sha")
    if not sha or not re.match(r"^[0-9a-f]{7,40}$", str(sha), re.IGNORECASE):
        mismatches.append(f"missing or invalid candidate_sha: {sha}")

    # Check required gates
    gates = data.get("gates", {})
    required_gate_keys = (
        "engineering_gates",
        "planning_control_gates",
        "local_clean_gates",
        "rq1_gates",
        "rq2_gates",
    )
    for gate_key in required_gate_keys:
        if gate_key not in gates:
            mismatches.append(f"missing gate breakdown: '{gate_key}'")

    # Rubric consistency checks
    if decision == "Advance":
        for gate_key in required_gate_keys:
            gate_val = str(gates.get(gate_key, "")).upper()
            if "PASS" not in gate_val:
                mismatches.append(
                    f"decision is 'Advance' but gate '{gate_key}' is "
                    f"'{gates.get(gate_key)}' (requires PASS)"
                )

    evidence_links = data.get("evidence_links")
    if not evidence_links or not isinstance(evidence_links, (list, dict)):
        mismatches.append("missing 'evidence_links' list or mapping")

    limitations = data.get("unresolved_limitations")
    if limitations is None:
        mismatches.append("missing 'unresolved_limitations' section")

    return {
        "ok": len(mismatches) == 0,
        "decision": str(decision),
        "mismatches": mismatches,
    }
