# NeuSym-Nav

Reproducible 2D neuro-symbolic VLN proof-of-concept using MiniGrid 3.1.0.
The commands below are the canonical operator entrypoint for A-J04. They
must be run from a fresh checkout of the frozen candidate SHA; do not reuse a
virtual environment, cache, local config, private sidecar, or generated
`runs/` directory from another checkout.

## Setup

Requirements: Python 3.12, Git, and `uv`.

After checking out a committed candidate, the evidence harness can capture
the metadata and output of the full sequence into a directory outside the
repository:

```bash
bash scripts/run_a_j04_reproduction.sh /tmp/neusym-nav-a-j04-evidence
```

The harness refuses a dirty checkout and returns non-zero if any command
fails. Copy only the reviewed summary/evidence into the tracked packet; keep
raw logs and private sidecars outside Git.

Record the candidate SHA, OS, Python, `uv`, Git, and lockfile hash before the
first setup command. Then run:

```bash
uv sync --all-groups
uv run ruff check .
uv run mypy src
uv run pytest -q
```

## Pygame presentation demo

For an interactive, hands-free visual demonstration of the V1R1 pipeline:

```bash
uv run python scripts/pygame_demo.py
```

Enter one of the supported instructions and click **Start**. The robot then
executes automatically while the display replays each perception, symbolic
planning action, primitive action, and verification step. It deliberately has
no manual movement controls.

## Manifest and smoke reproduction

Regenerate the deterministic public manifests and evaluator-private sidecars:

```bash
uv run ns-vln generate-manifests --config configs/manifests.yaml
uv run ns-vln evaluate --config configs/smoke.yaml
```

Declared final targets (run to produce the complete 1,120-row evaluation matrix):

```bash
uv run ns-vln evaluate --config configs/b3_test.yaml
uv run ns-vln evaluate --config configs/rq1_test.yaml
uv run ns-vln evaluate --config configs/rq2_test.yaml
uv run ns-vln evaluate --config configs/v1r1_clean.yaml
```

The generated manifest files are written under `data/manifests/`. Evaluation
outputs are written under `runs/final/` (ignored by Git). The frozen final matrix is
validated with:

```bash
uv run ns-vln validate-results \
  --runs runs/final \
  --expected-config reports/expected_rows.yaml
uv run ns-vln validate-traces --runs runs/final
uv run ns-vln audit --runs runs/final
uv run ns-vln summarize --runs runs/final --output reports/month1/
uv run ns-vln audit-portability --src src/neuro_symbolic_vln
uv run ns-vln validate-report --report reports/month1/
uv run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml
```

The final target is the declared matrix in
`reports/expected_rows.yaml` (B3, RQ1, RQ2, and V1R1 clean; 1,120 rows total). A missing,
duplicate, unavailable, hash-mismatched, or non-replayable row is a failed
reproduction condition and must be recorded as a typed deviation; it must not
be silently omitted.

## A-J04 evidence

Member A records command output, timestamps, environment identity, hashes,
fresh-directory assertions, and rerun classification in
`docs/reproduction/a_j04_member_a_evidence.md`. Technical findings intended
for the B-J04 report are in the same file. The deviation log is maintained at
`docs/reproduction/a_j04_deviation_log.md`.

This repository contains no tracked private sidecars, secrets, or raw `runs/`
outputs. Private evaluator artifacts must remain outside the Git tree.
