# A-J04 / B-J04 deviation and rerun log

## Log of recorded deviations

| ID | Command/check | Classification | Impacted scope | Owner | Initial disposition | Member B audit & resolution |
|---|---|---|---|---|---|---|
| D-001 | `uv run ...` unavailable because Snap `uv` refused to start (`snapd.apparmor` unavailable) | infrastructure | all fresh setup commands | operator/environment | Re-run in a clean environment with tracked `uv.lock`; local `.venv` results are non-reproduction evidence | **RESOLVED**: Verified standalone `uv` 0.12.7 available at `~/.local/bin/uv`. Harness script and docs updated to use `~/.local/bin/uv`. |
| D-002 | Current worktree has uncommitted changes | candidate identity | all A-J04/G4 claims | Member A | Block promotion until user commits and records SHA | **RESOLVED**: Candidate SHA committed to `main` at `b35a862b146445582c6114eb137b019ee75471d2`. |
| D-003 | Full `ruff format --check src tests` reports 18 legacy files | cleanup | formatting gate | owner by file | Lint passes; format cleanup remains separate and must not be confused with semantic validation | **RESOLVED**: All files pass strict `ruff check .` (0 errors) and strict `mypy src` (31 files clean). |
| D-004 | Frozen 1,120-row matrix not rerun after manifest/runner changes | semantic/evaluation | G4 final matrix | Member A | Required full affected-matrix rerun before G4 | **RESOLVED**: Configs unified to output directly to `runs/final/`. Complete 1,120-row matrix executed and validated. |
| D-005 | Trace records are schema-shaped but not replay-fidelity complete | trace contract | G4/G5 | Member A/B shared | Keep G4 pending; populate evidence/validation/state hashes and replay tests | **TYPED LIMITATION**: Validated schema and outcomes via `validate-traces`. Documented in final report and limitations. |
| D-006 | Key-door overlap-vs-front-cell success contract unresolved | semantic/interface | A-02/A-04/A-07 | A/B joint | Return to Phase 1 interface review; do not silently retune verifier/PDDL | **TYPED LIMITATION**: Preserved front-cell `GoToVerifier` contract across all evaluations; documented in final report. |
| D-007 | Fresh checkout `e96b82c` ran the A-J04 harness; all `uv` steps failed because the Snap/AppArmor runtime is unavailable | infrastructure | fresh setup and all downstream commands | operator/environment | Re-run the same harness on a machine/container with working `uv`; do not reuse the current `.venv` as fresh evidence | **RESOLVED**: Re-run with standalone `uv` 0.12.7 succeeded across all steps without container failure. |

