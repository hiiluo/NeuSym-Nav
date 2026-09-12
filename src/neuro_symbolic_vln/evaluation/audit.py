"""Oracle / sidecar leakage audit for B-09.

Scans the agent import graph, source files, and trace outputs to detect
forbidden oracle access. This module lives in the evaluation package and
must NOT be imported by the normal agent path.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neuro_symbolic_vln.trace import scan_record_for_leakage

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class AuditViolation:
    """A single leakage violation."""

    category: str  # "import", "source", "trace", "constructor"
    location: str  # file:line or module name
    detail: str


@dataclass
class AuditReport:
    """Aggregated audit results across all scan categories."""

    violations: list[AuditViolation] = field(default_factory=list)
    scanned_modules: int = 0
    scanned_source_files: int = 0
    scanned_trace_records: int = 0

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        lines = [
            "Leakage Audit Report",
            f"  Modules scanned:       {self.scanned_modules}",
            f"  Source files scanned:   {self.scanned_source_files}",
            f"  Trace records scanned:  {self.scanned_trace_records}",
            f"  Violations:            {len(self.violations)}",
        ]
        if self.violations:
            lines.append("")
            for v in self.violations:
                lines.append(f"  [{v.category}] {v.location}: {v.detail}")
        else:
            lines.append("  Status: PASS — zero leakage detected")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 1. Import-graph scan
# ---------------------------------------------------------------------------

# Agent-path modules that must NEVER import evaluation code.
AGENT_MODULES = (
    "neuro_symbolic_vln.agent",
    "neuro_symbolic_vln.belief.evidence",
    "neuro_symbolic_vln.belief.state",
    "neuro_symbolic_vln.belief.validator",
    "neuro_symbolic_vln.control.controller",
    "neuro_symbolic_vln.control.monitor",
    "neuro_symbolic_vln.language.template_parser",
    "neuro_symbolic_vln.perception.observation_decoder",
    "neuro_symbolic_vln.planning.pyperplan_adapter",
    "neuro_symbolic_vln.planning.problem_serializer",
    "neuro_symbolic_vln.planning.location_graph",
    "neuro_symbolic_vln.trace",
    "neuro_symbolic_vln.contracts",
)

# Forbidden import targets for agent-path modules.
FORBIDDEN_IMPORT_PREFIXES = (
    "neuro_symbolic_vln.evaluation",
)


def scan_import_graph(report: AuditReport) -> None:
    """Import agent modules in a subprocess and check for evaluation leaks.

    This reproduces the test from test_no_oracle_leakage.py but captures
    granular violation details into the audit report.
    """
    importable = [m for m in AGENT_MODULES if _module_exists(m)]
    report.scanned_modules = len(importable)

    if not importable:
        return

    import_lines = "\n".join(f"import {m}" for m in importable)
    check_code = (
        f"{import_lines}\n"
        "import json, sys\n"
        "leaked = [\n"
        "    name for name in sys.modules\n"
        "    if name.startswith('neuro_symbolic_vln.evaluation')\n"
        "]\n"
        "print(json.dumps(leaked))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", check_code],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        report.violations.append(AuditViolation(
            category="import",
            location="subprocess",
            detail=f"import scan failed: {result.stderr.strip()[:200]}",
        ))
        return

    try:
        leaked = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return

    for module_name in leaked:
        report.violations.append(AuditViolation(
            category="import",
            location=module_name,
            detail=(
                f"evaluation module '{module_name}' was imported "
                f"via agent-path modules"
            ),
        ))


def _module_exists(module_name: str) -> bool:
    """Check if a module can be found without importing it."""
    from importlib.util import find_spec

    try:
        return find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 2. Source-level import/constructor scan
# ---------------------------------------------------------------------------


def scan_source_files(
    src_dir: Path,
    report: AuditReport,
) -> None:
    """AST-scan agent-path .py files for forbidden imports and constructor args.

    Detects:
    - ``import neuro_symbolic_vln.evaluation.*``
    - ``from neuro_symbolic_vln.evaluation import ...``
    - Constructor parameters named 'oracle', 'sidecar', 'ground_truth',
      'hidden_labels', 'evaluator'.
    """
    # Directories that are part of the agent path (not evaluation).
    agent_subdirs = {"belief", "control", "language", "perception", "planning"}
    forbidden_param_names = {
        "oracle", "sidecar", "ground_truth", "hidden_labels",
        "evaluator", "evaluation_oracle", "private_labels",
    }
    # Entry points and test helpers are not agent-path modules.
    excluded_files = {"cli.py", "testing.py"}

    files_scanned = 0

    # Scan top-level agent modules
    for py_file in sorted(src_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name in excluded_files:
            continue
        files_scanned += 1
        _scan_single_file(py_file, forbidden_param_names, report)

    # Scan agent subdirectories
    for subdir_name in sorted(agent_subdirs):
        subdir = src_dir / subdir_name
        if not subdir.is_dir():
            continue
        for py_file in sorted(subdir.rglob("*.py")):
            files_scanned += 1
            _scan_single_file(py_file, forbidden_param_names, report)

    report.scanned_source_files = files_scanned


def _scan_single_file(
    py_file: Path,
    forbidden_params: set[str],
    report: AuditReport,
) -> None:
    """Scan a single Python file for forbidden imports and constructor params."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError):
        return

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    alias.name.startswith(prefix)
                    for prefix in FORBIDDEN_IMPORT_PREFIXES
                ):
                    report.violations.append(AuditViolation(
                        category="source",
                        location=f"{py_file.name}:{node.lineno}",
                        detail=f"forbidden import: {alias.name}",
                    ))

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(
                module.startswith(prefix)
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                names = ", ".join(a.name for a in node.names)
                report.violations.append(AuditViolation(
                    category="source",
                    location=f"{py_file.name}:{node.lineno}",
                    detail=f"forbidden from-import: from {module} import {names}",
                ))

        # Check __init__ constructor params
        elif isinstance(node, ast.FunctionDef) and node.name == "__init__":
            for arg in node.args.args:
                if arg.arg in forbidden_params:
                    report.violations.append(AuditViolation(
                        category="constructor",
                        location=f"{py_file.name}:{node.lineno}",
                        detail=(
                            f"forbidden constructor param '{arg.arg}' "
                            f"in __init__"
                        ),
                    ))


# ---------------------------------------------------------------------------
# 3. Trace field scan
# ---------------------------------------------------------------------------


def scan_traces(
    trace_dir: Path,
    report: AuditReport,
) -> None:
    """Scan all JSONL trace files for forbidden private data.

    Uses scan_record_for_leakage from trace.py for per-record checks
    and adds method/oracle_input consistency checks.
    """
    records_scanned = 0

    for trace_file in sorted(trace_dir.glob("*.jsonl")):
        for line_num, line in enumerate(
            trace_file.read_text().strip().splitlines(), 1
        ):
            if not line.strip():
                continue

            records_scanned += 1

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                report.violations.append(AuditViolation(
                    category="trace",
                    location=f"{trace_file.name}:{line_num}",
                    detail="malformed JSON in trace record",
                ))
                continue

            # Use the existing scan_record_for_leakage from trace.py
            violations = scan_record_for_leakage(data)
            for detail in violations:
                report.violations.append(AuditViolation(
                    category="trace",
                    location=f"{trace_file.name}:{line_num}",
                    detail=detail,
                ))

    report.scanned_trace_records = records_scanned


# ---------------------------------------------------------------------------
# 4. Combined audit
# ---------------------------------------------------------------------------


def run_leakage_audit(
    *,
    src_dir: Path | None = None,
    trace_dir: Path | None = None,
    skip_import_scan: bool = False,
) -> AuditReport:
    """Run all leakage audit scans and return a combined report.

    Args:
        src_dir: Path to ``src/neuro_symbolic_vln/``. If None, import-graph
            and source scans are still attempted via the subprocess approach.
        trace_dir: Path to the runs directory containing JSONL traces.
            If None, trace scan is skipped.
        skip_import_scan: If True, skip the subprocess import-graph scan
            (useful in environments where subprocess is restricted).
    """
    report = AuditReport()

    # 1. Import-graph scan
    if not skip_import_scan:
        scan_import_graph(report)

    # 2. Source-level scan
    if src_dir is not None and src_dir.is_dir():
        scan_source_files(src_dir, report)

    # 3. Trace field scan
    if trace_dir is not None and trace_dir.is_dir():
        scan_traces(trace_dir, report)

    return report


def write_audit_report(report: AuditReport, output_path: Path) -> None:
    """Write audit report as both human-readable text and machine-readable JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Text report
    output_path.write_text(report.summary() + "\n")

    # JSON report alongside
    json_path = output_path.with_suffix(".json")
    json_data: dict[str, Any] = {
        "ok": report.ok,
        "scanned_modules": report.scanned_modules,
        "scanned_source_files": report.scanned_source_files,
        "scanned_trace_records": report.scanned_trace_records,
        "violation_count": len(report.violations),
        "violations": [
            {
                "category": v.category,
                "location": v.location,
                "detail": v.detail,
            }
            for v in report.violations
        ],
    }
    json_path.write_text(
        json.dumps(json_data, indent=2, sort_keys=True) + "\n"
    )
