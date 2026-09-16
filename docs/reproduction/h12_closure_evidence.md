# H12 — Phase-2 Closure Evidence Packet

This document records the complete closure evidence for Phase-2 of the Neuro-Symbolic VLN project, fulfilling Gates G4 and G5 per `docs/task_b_j04_guide.md`.

---

## H12 — Phase-2 closure evidence

- **Frozen candidate SHA/tag and final SHA:**
  - Base candidate SHA: `b35a862b78d838756768de981c717819d83c7b35` (Merge PR #52 `test/a-fresh-reproduction` into `main`)
  - Verification & Final Analysis branch: `docs/b-final-analysis`

- **Lock/config/manifest/schema/result hashes:**
  - `pyproject.toml`: Tracked, pinned dependencies (`pytest`, `ruff`, `mypy`, `pyperplan`, `minigrid`, `gymnasium`).
  - `configs/analysis.yaml`: Fixed seed `42`, 10,000 bootstrap resamples, 95% CI.
  - `configs/b3_test.yaml`: Baseline config on test split (120 rows).
  - `configs/v1r1_clean.yaml`: V1R1 clean baseline on test split (120 rows).
  - `configs/rq1_test.yaml`: RQ1 matrix config on test split (720 rows).
  - `configs/rq2_test.yaml`: RQ2 intervention matrix config (160 rows).
  - `reports/expected_rows.yaml`: Frozen target matrix: 1,120 rows.
  - Manifest hashes: Verified matching `data/manifests/manifests.jsonl` and `data/manifests/manifests_rq2.jsonl`.

- **A fresh-checkout log (path/link):**
  - Path: `docs/reproduction/a_j04_fresh_clone_log.md`
  - Pull Request: #52 (`test/a-fresh-reproduction`) merged into `main` at `b35a862`.

- **B independent rerun log (path/link):**
  - Path: `docs/reproduction/b_j04_member_b_evidence.md`
  - All 1,120 rows generated and independently verified by Member B on Linux 6.6 / Python 3.12.3 / uv 0.12.7.

- **Final CI link and command results:**
  - `uv run ruff check .`: **PASS** (0 errors).
  - `uv run mypy src`: **PASS** (31 source files checked, 0 issues).
  - `uv run pytest -q`: **PASS** (386/386 passed in 24.30s).
  - `uv run ns-vln audit-portability --src src/neuro_symbolic_vln`: **PASS** (31 source files pure).
  - `uv run ns-vln validate-report --report reports/month1/`: **PASS** (8/8 required sections verified).
  - `uv run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml`: **PASS** (`Conditional hold` validated).

- **Raw-row / trace / summary / CI reconciliation:**
  - `uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml`: **PASS** (1,120 actual / 1,120 expected rows).
  - `b3_test.rows.jsonl`: 120 rows.
  - `v1r1_clean.rows.jsonl`: 120 rows.
  - `rq1_test.rows.jsonl`: 720 rows.
  - `rq2_test.rows.jsonl`: 160 rows.
  - Summaries match row data: `reports/month1/rq1_summary.json`, `reports/month1/rq2_summary.json`, `reports/month1/rq_summary.md`, `reports/month1/rq_summary.csv`.

- **Leakage and replay audit links:**
  - `uv run ns-vln audit --runs runs/final`: **PASS** (14 modules, 15 files, 5,503 traces scanned; 0 violations).
  - `uv run ns-vln validate-traces --runs runs/final`: **PASS** (5,503 traces scanned; schema-valid, typed, zero leakage).

- **Fake-adapter and portability evidence:**
  - Fake adapter: `tests/fakes.py` (`FakeGraphAdapter` implementing non-grid node-graph transition semantics with zero MiniGrid dependencies).
  - Contract test: `tests/env/test_non_grid_adapter_contract.py` (5/5 tests passing).
  - Portability audit: `audit_portability()` in `src/neuro_symbolic_vln/evaluation/report_validator.py` confirmed pure architecture across all 31 source files.

- **RQ1/RQ2 tables, estimands and threats/non-claims:**
  - Documented in `reports/month1/research_report.md` (§3, §4, §5, §6).
  - RQ1: V1R0 vs V0R0 paired difference with 10,000-resample bootstrap 95% CIs. Shows conservative drop under N1 for multi-stage tasks without recovery replanning (Δ = -0.0833 on `key_door_goal`).
  - RQ2: V1R1 vs V1R0 paired difference under N2 interventions. Demonstrates massive recovery benefit (+87.50% overall, 100% on `key_door_goal`).
  - Explicit non-claims: Strictly disclaims continuous 3D Habitat performance, photorealistic generalization, and end-to-end natural VLN.

- **Habitat decision file and exact evidence links:**
  - Decision File: `reports/month1/habitat_decision.yaml`
  - Typed Decision: **`Conditional hold`**
  - Rationale: Architecture and engineering gates PASS (100% clean SR, zero leakage, decoupled adapter), but RQ1 empirical threshold under N1 corruptions demonstrates validation-without-recovery conservatism. Per rubric, project holds migration to complete coupled 2D diagnostics.

- **Deviations, reruns, unresolved limitations and owners:**
  - Deviation log: `docs/reproduction/a_j04_deviation_log.md` (Audited resolutions for D-001 through D-007).
  - Unresolved limitations recorded in `reports/month1/habitat_decision.yaml`:
    - LIM-01: Narrow probe topology (D-004) — Owner: Member A.
    - LIM-02: Validation-only conservatism without recovery (RQ1) — Owner: Member B.
    - LIM-03: Frontier bootstrap heuristic (D-005) — Owner: Member A.
    - LIM-04: Interaction coordinate alignment (D-006) — Owner: Member A.

- **Merge commits / PRs / reviewer approvals:**
  - PR #50: Maintenance, dev container setup, and docs corrections.
  - PR #52: Member A fresh reproduction evidence on `main` (`b35a862`).
  - Final analysis PR: `docs/b-final-analysis` (Member B reproduction verification, statistical summaries, Month 1 research report, Habitat decision record, and H12 packet).
