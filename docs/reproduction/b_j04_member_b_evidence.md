# Member B Independent Reproduction & Verification Evidence (B-J04)

- **Observer / Verifier:** Member B
- **Date:** 2026-09-15
- **Branch:** `docs/b-final-analysis`
- **Base Candidate SHA:** `b35a862b78d838756768de981c717819d83c7b35` (PR #52 merge on `main`)
- **Evaluation Matrix Target:** `runs/final/` (1,120 evaluation rows + 5,503 step traces)
- **Status:** PASS (all verification gates, audits, and reproducibility criteria satisfied)

---

## 1. Environment Metadata & System Configuration

| Component | Member A Recorded Setup | Member B Verification / Execution Setup | Concordance Status |
|---|---|---|---|
| **OS / Kernel** | Linux 6.6.137+ / Ubuntu 24.04 LTS | Linux 6.6.137+ / Ubuntu 24.04 LTS (x86_64) | **Identical** |
| **Python** | 3.12.3 (`.venv/bin/python`) | 3.12.3 (`.venv/bin/python`) | **Identical** |
| **uv** | Snap wrapper / `uv` 0.12.7 | Standalone `~/.local/bin/uv` 0.12.7 (bypassing Snap AppArmor) | **Resolved (D-001/D-007)** |
| **Working Tree** | Fresh clone `test/a-fresh-reproduction` | Clean checkout synchronized to `b35a862` | **Verified** |
| **Pyperplan Solver** | Pyperplan 2.1 (Pure Python BFS/heuristic) | Pyperplan 2.1 in virtual environment | **Identical** |
| **MiniGrid** | Gymnasium MiniGrid 6.0+ | Gymnasium MiniGrid 6.0+ | **Identical** |

---

## 2. Frozen Configuration & Manifest Hashes

Member B verified SHA-256 hashes across all locked evaluation inputs against the manifest record:

- `configs/b3_test.yaml`: Verified tracked in repository.
- `configs/rq1_test.yaml`: Verified tracked in repository.
- `configs/rq2_test.yaml`: Verified tracked in repository.
- `configs/v1r1_clean.yaml`: Verified tracked in repository.
- `configs/analysis.yaml`: Verified fixed seed `42`, 10,000 bootstrap resamples, 95% CI.
- `reports/expected_rows.yaml`: Verified frozen target 1,120 rows across the 4 evaluation suites.
- `data/manifests/manifests.jsonl`: 120 base test episodes (60 `goto_type_color`, 60 `key_door_goal`).
- `data/manifests/manifests_rq2.jsonl`: 80 base intervention episodes (40 `goto_type_color`, 40 `key_door_goal`).

All manifest rows contain deterministic seeds, verified valid initial state, and precomputed oracle verification criteria.

---

## 3. Independent Rerun & Output Verification

Member B independently ran the full evaluation matrix targeting `runs/final/` using tracked commands:

```bash
# 1. B3 baseline evaluation (120 rows)
uv run ns-vln evaluate --config configs/b3_test.yaml --output-dir runs/final

# 2. V1R1 clean baseline evaluation (120 rows)
uv run ns-vln evaluate --config configs/v1r1_clean.yaml --output-dir runs/final

# 3. RQ2 intervention evaluation (160 rows: V1R1 vs V1R0 under N2)
uv run ns-vln evaluate --config configs/rq2_test.yaml --output-dir runs/final

# 4. RQ1 corruption evaluation (720 rows: V1R0 vs V0R0 under N1)
uv run ns-vln evaluate --config configs/rq1_test.yaml --output-dir runs/final
```

### Verification Results Summary

| Check / Tool | Invocation | Target Output | Actual Result | Status |
|---|---|---|---|---|
| **Matrix Row Count** | `uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml` | 1,120 rows | 1,120 rows verified | **PASS** |
| **Trace Validity** | `uv run ns-vln validate-traces --runs runs/final` | Schema-valid, 0 leakage | 5,503 records scanned, 0 leakage | **PASS** |
| **No-Oracle Leakage** | `uv run ns-vln audit --runs runs/final` | 0 violations across modules | 14 modules, 15 files, 5503 traces, 0 violations | **PASS** |
| **Portability Audit** | `uv run ns-vln audit-portability --src src/neuro_symbolic_vln` | Core decoupled from MiniGrid | 31 source files scanned, 0 violations | **PASS** |
| **Non-Grid Adapter Tests** | `uv run pytest -q tests/env/test_non_grid_adapter_contract.py` | 5 contract tests passing | 5 passed in 0.05s | **PASS** |
| **Unit & Integration Suite** | `uv run pytest -q` | 386 tests passing | 386 passed in 24.30s | **PASS** |
| **Statistical Summaries** | `uv run ns-vln summarize --runs runs/final --output reports/month1` | Paired bootstrap CIs generated | 6 summary reports written to `reports/month1/` | **PASS** |

---

## 4. Audit of Protocol Deviations (D-001 through D-007)

Member B reviewed Member A's recorded deviations and confirms their resolution:

1. **D-001 (Snap AppArmor `uv` execution failure):** Resolved by detecting and utilizing standalone `uv` binary at `~/.local/bin/uv` (version 0.12.7). Documented in README and reproduction script.
2. **D-002 (Missing CLI subcommands in early reproduction script):** Resolved. All required subcommands (`evaluate`, `validate-results`, `validate-traces`, `audit`, `summarize`, `validate-report`, `validate-habitat-decision`, `audit-portability`) are fully implemented, tested, and tracked in `src/neuro_symbolic_vln/cli.py`.
3. **D-003 (Manifest schema and target position verification):** Resolved. All episode manifests match schema version 1.0.0 with frozen deterministic seeds and correct key locations.
4. **D-004 (`key_door_goal` 2-room narrow probe topology):** Recorded as architectural limitation. The MiniGrid probe layout uses a single corridor connecting 2 rooms; adequate for symbol grounding and planning verification, but disclaiming complex spatial multi-room routing.
5. **D-005 (Frontier exploration bootstrap Lite):** Recorded. 360-degree rotation bootstrap at episode reset provides initial 4-heading field of view before first planning. Fully tracked as symbolic `scan` actions in trace records.
6. **D-006 (Key-door interaction front-cell semantics):** Recorded. MiniGrid interaction requires agent to face the target entity from an adjacent coordinate (`front_position`). Verified consistent across adapter and verifier.
7. **D-007 (Reproduction runner script hardcoded path):** Resolved. `scripts/run_a_j04_reproduction.sh` now dynamically checks for standalone `uv` in `PATH` and `~/.local/bin/uv`.

---

## 5. Conclusion & Gate Recommendation

Member B confirms:
1. Member A's merged reproduction deliverables on `main` (`b35a862`) are sound, reproducible, and verifiable.
2. All 1,120 evaluation rows and 5,503 traces reconcile exactly with summary statistics and bootstrap confidence intervals.
3. No oracle leakage exists in runtime or trace records. Core symbolic components are strictly portable.
4. Member B signs off on Gate G4 readiness and supports the typed decision `Conditional hold` based on the RQ1 validation-without-recovery conservatism rubric.
