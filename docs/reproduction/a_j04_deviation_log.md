# A-J04 deviation and rerun log

| ID | Command/check | Classification | Impacted scope | Owner | Disposition |
|---|---|---|---|---|---|
| D-001 | `uv run ...` unavailable because Snap `uv` refused to start (`snapd.apparmor` unavailable) | infrastructure | all fresh setup commands | operator/environment | Re-run in a clean environment with tracked `uv.lock`; local `.venv` results are non-reproduction evidence |
| D-002 | Current worktree has uncommitted changes | candidate identity | all A-J04/G4 claims | Member A | Block promotion until user commits and records SHA |
| D-003 | Full `ruff format --check src tests` reports 18 legacy files | cleanup | formatting gate | owner by file | Lint passes; format cleanup remains separate and must not be confused with semantic validation |
| D-004 | Frozen 1,120-row matrix not rerun after manifest/runner changes | semantic/evaluation | G4 final matrix | Member A | Required full affected-matrix rerun before G4 |
| D-005 | Trace records are schema-shaped but not replay-fidelity complete | trace contract | G4/G5 | Member A/B shared | Keep G4 pending; populate evidence/validation/state hashes and replay tests |
| D-006 | Key-door overlap-vs-front-cell success contract unresolved | semantic/interface | A-02/A-04/A-07 | A/B joint | Return to Phase 1 interface review; do not silently retune verifier/PDDL |
| D-007 | Fresh checkout `e96b82c` ran the A-J04 harness; all `uv` steps failed because the Snap/AppArmor runtime is unavailable | infrastructure | fresh setup and all downstream commands | operator/environment | Re-run the same harness on a machine/container with working `uv`; do not reuse the current `.venv` as fresh evidence |
