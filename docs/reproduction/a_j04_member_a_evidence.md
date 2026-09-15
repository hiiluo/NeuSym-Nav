# A-J04 — Member A reproduction and engineering evidence

Status: **fresh checkout executed; setup blocked by local `uv` infrastructure**.

This packet is intentionally evidence-first. It does not promote G4/G5 or
choose the Habitat decision; those require the joint/B-J04 review.

## Candidate identity

The current worktree contains uncommitted Member A changes, so its current
`HEAD` is not a valid frozen candidate. After commit, record:

| Field | Value |
|---|---|
| Candidate SHA/tag | `e96b82cf64a8233b42ddbdf689e92aa923071c60` |
| Final SHA/tag | `<fill after final CI>` |
| Checkout path | `/tmp/neusym-nav-a-j04-clean` |
| Date/time (UTC) | `2026-09-14T09:03:00Z` |
| OS / Python / uv / Git | Recorded in `/tmp/neusym-nav-a-j04-evidence-clean/environment.txt` |
| `uv.lock` SHA256 | `7208403d6eaaf37db7b45b7df4b32a97bdba3e4ead50e485bc759cb39982c7de` (current worktree) |

## Local engineering validation completed

These checks were run against the current working tree and are not a
substitute for a clean-checkout reproduction:

| Check | Result | Evidence |
|---|---|---|
| Ruff lint | PASS | `.venv/bin/ruff check src tests` |
| Mypy | PASS | `.venv/bin/mypy src` (30 source files) |
| Full pytest | PASS | `.venv/bin/pytest -q`: 372 passed |
| Targeted frontier/leakage regression | PASS | 27 tests passed after final frontier change |
| Manifest generation | PASS | 260 public + 260 sidecars regenerated |
| `git diff --check` | PASS | no whitespace errors |
| Full format check | PARTIAL | 18 legacy files require formatting; lint is clean |

The system `uv` executable is a Snap wrapper that refused to start because
`snapd.apparmor` is unavailable in this environment. The checks above used
the already provisioned `.venv` executables; a fresh-checkout run must use the
tracked `uv.lock` through the README command sequence.

## A-J04 command record

The following sequence is the exact tracked operator sequence and must be
re-run from a clean checkout after the candidate is committed:

The tracked harness `scripts/run_a_j04_reproduction.sh` enforces a clean
worktree, captures environment identity and per-command logs, and exits
non-zero on any failed command. It was smoke-tested in the current dirty
worktree and correctly refused to run with exit status 2; a PASS requires a
committed candidate checkout.

The fresh checkout was actually clean at `e96b82c`, but every `uv` command
returned exit status 1 because the system Snap wrapper refused to start while
`snapd.apparmor` was unavailable. Therefore this is a recorded infrastructure
deviation, not a reproduction PASS. The complete per-command logs are in
`/tmp/neusym-nav-a-j04-evidence-clean/`.

```text
uv sync --all-groups
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run ns-vln generate-manifests --config configs/manifests.yaml
uv run ns-vln evaluate --config configs/smoke.yaml
uv run ns-vln evaluate --config configs/rq1_test.yaml
uv run ns-vln evaluate --config configs/rq2_test.yaml
uv run ns-vln evaluate --config configs/v1r1_clean.yaml
uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml
uv run ns-vln validate-traces --runs runs/final
uv run ns-vln audit --runs runs/final
uv run ns-vln summarize --runs runs/final --output reports/month1/
```

## Technical input for B-J04

- Public manifests now exclude target/distractor coordinates; evaluator
  reconstruction verifies the public layout hash before execution.
- Normal agent imports do not load evaluator/oracle modules; B3 is the only
  `oracle_input=true` method.
- RQ1 conditions are exactly `clean`, `N1-DROP-15`, and `N1-FLIP-10`, with
  corruption applied after categorical decoding and before belief storage.
- Runner traces use an episode/method/condition filename, preventing the
  previous same-episode overwrite.
- Grid-SPL uses successful forward transitions; SOPE uses attempted primitive
  actions and is reported only for key-door rows.
- Frontier selection excludes unreachable locations and returns typed
  `FRONTIER_EXHAUSTED` when no unexplored reachable frontier remains.
- B3 distractor objects are no longer treated as alternative task targets.

The following remain open and must be represented in the B-J04 report rather
than hidden by aggregate results:

1. `key_door_goal` success currently follows the front-cell `GoToVerifier`
   contract, while the master plan describes an overlapable goal. This needs
   a coordinated PDDL/verifier decision with Member B.
2. The generator still uses a narrow fixed probe topology and does not yet
   satisfy the full §15.1 variation requirements.
3. Trace records still contain placeholder evidence/validation/hash values;
   schema validation is not replay-fidelity validation.
4. N2 paired initial-plan hash/prefix checks and the complete 1,120-row matrix
   have not been rerun after the latest semantic/hash changes.
5. `problems/` PDDL artifacts and a fully populated final report packet are
   not present in the current worktree.

## Handoff request to B

B-J04 should independently rerun one declared target from the committed SHA,
compare manifest/config/schema hashes and raw rows, and classify every item
above as resolved, infrastructure-only, or semantic/core. No Habitat decision
should be inferred from this local validation packet alone.
