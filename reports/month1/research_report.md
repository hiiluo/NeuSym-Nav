# Month 1 Research Report: Neuro-Symbolic Vision-and-Language Navigation

- **Authors:** Member A (System Infrastructure & Environment) & Member B (Evaluation & Statistical Analysis)
- **Candidate Commit SHA:** `b35a862b78d838756768de981c717819d83c7b35`
- **Evaluation Matrix Output Directory:** `runs/final/` (1,120 rows, 5,503 step traces)
- **Evaluation Summaries:** `reports/month1/rq1_summary.json`, `reports/month1/rq2_summary.json`, `reports/month1/rq_summary.md`, `reports/month1/rq_summary.csv`
- **Configuration Profiles:** `configs/b3_test.yaml`, `configs/rq1_test.yaml`, `configs/rq2_test.yaml`, `configs/v1r1_clean.yaml`, `configs/analysis.yaml`
- **Date:** September 15, 2026

---

## 1. Executive Summary

This report documents the Month 1 findings of the Neuro-Symbolic Vision-and-Language Navigation (NeuSym-Nav) project, evaluating a belief-driven, closed-loop architecture featuring explicit belief validation and bounded replanning (V1R1) compared to classical heuristic baselines (B3), validation-only agents (V1R0), and naive forward-execution agents (V0R0). 

All evaluations were executed against the frozen candidate commit `b35a862b78d838756768de981c717819d83c7b35`. The complete evaluation matrix comprises **1,120 evaluation rows** and **5,503 step traces** recorded in `runs/final/` across four test suites:
1. `b3_test` (120 rows): Classical heuristic baseline on clean environments.
2. `v1r1_clean` (120 rows): V1R1 agent operating under clean perceptual conditions.
3. `rq1_test` (720 rows): 6 crossings comparing V1R0 (validator on, recovery off) against V0R0 (validator off, recovery off) under clean and two N1 perceptual corruption channels (`N1-DROP-15` and `N1-FLIP-10`).
4. `rq2_test` (160 rows): 2 crossings comparing V1R1 (validator on, recovery on) against V1R0 (validator on, recovery off) under deterministic N2 environment interventions (`block` and `relock`).

### Core Findings:
- **Baseline Clean Performance:** Both B3 and V1R1 achieved **100% Task Success Rate (SR = 1.00)** and **100% Plan Validity** on clean test splits across both task families (`goto_type_color` and `key_door_goal`), confirming the soundness of the symbolic planning and observation decoding pipeline.
- **RQ1 (Perception Validation Alone):** When perceptual evidence is corrupted by N1 drop or flip noise, validating observations without replanning (V1R0) successfully invalidates false beliefs, but results in a slight decrease in task success on multi-stage tasks (`key_door_goal` Δ = -0.0833, 95% CI [-0.1667, -0.0167]) because the agent conservatively stops when an atom is invalidated rather than blindly attempting forward motion. Overall across all 360 paired episodes, Δ task_success is -0.0278 (95% CI [-0.0528, -0.0028]).
- **RQ2 (Bounded Replanning Recovery):** Bounded replanning (V1R1) under N2 physical interventions achieved an extraordinary recovery improvement over validation-only (V1R0), yielding an overall task success delta of **+0.8750** (95% CI [+0.8000, +0.9375]), with a **100% recovery rate (Δ = +1.0000, 95% CI [+1.0000, +1.0000])** on `key_door_goal`.
- **System Integrity:** Independent audits verify zero oracle leakage (PASS across 14 modules and 5,503 trace records) and strict decoupling of core symbolic modules from MiniGrid dependencies (PASS across 31 source files).

---

## 2. Methods & Experimental Design

### 2.1 Architectural Framework: V1R1
The system comprises four decoupled functional layers:
1. **Perception & Observation Decoding (`observation_decoder.py`):** Translates local egocentric 7x7 grid perceptions into symbolic ground atoms (e.g. `agent-at`, `object-at`, `door-locked`).
2. **Belief Tracking & Validation (`state.py`, `validator.py`):** Maintains a consistent world state graph and verifies new evidence against physical consistency constraints (e.g., entity mutual exclusion, non-overlapping solid objects, persistent door status).
3. **Symbolic Planning (`pyperplan_adapter.py`, `problem_serializer.py`):** Compiles belief state and goal programs into PDDL problems solved via Pyperplan (A* search with landmark heuristics).
4. **Execution Monitoring & Control (`monitor.py`, `controller.py`):** Executes planned symbolic primitives step-by-step, monitoring preconditions and action outcomes. When an unexpected blockage or action failure occurs, the monitor invalidates inconsistent atoms and requests a bounded replan.

### 2.2 Experimental Matrix Configuration
The evaluation matrix is defined across four frozen YAML profiles in `configs/`:
- `configs/b3_test.yaml`: Baseline B3 method on test split (120 rows).
- `configs/v1r1_clean.yaml`: V1R1 method on clean test split (120 rows).
- `configs/rq1_test.yaml`: Factorial crossing of 2 methods (`V0R0`, `V1R0`) × 3 conditions (`clean`, `N1-DROP-15`, `N1-FLIP-10`) × 120 test episodes (720 rows).
- `configs/rq2_test.yaml`: Factorial crossing of 2 methods (`V1R0`, `V1R1`) × 1 condition (`N2-fixed`) × 80 test episodes (160 rows).

Each row was serialized to JSONL files in `runs/final/` (`b3_test.rows.jsonl`, `v1r1_clean.rows.jsonl`, `rq1_test.rows.jsonl`, `rq2_test.rows.jsonl`), accompanied by structured run summaries (`*.summary.json`) and per-step execution traces (`runs/final/traces/`).

### 2.3 Estimands & Statistical Bootstrap Protocol
In accordance with `configs/analysis.yaml`, all comparisons are paired episode-by-episode between treatment and control under identical random seeds and environment manifests.
We compute the paired difference:
$$\Delta = \frac{1}{N} \sum_{i=1}^N (Y_{\text{treatment}, i} - Y_{\text{control}, i})$$
Non-parametric 95% confidence intervals are estimated using $B = 10,000$ stratified bootstrap resamples with a fixed seed (`seed = 42`).

---

## 3. RQ1 Results: Perception Validation under Corruption (V1R0 vs V0R0)

Research Question 1 asks: *Does symbolic belief validation (V1R0) protect navigation performance and plan validity under perceptual corruptions compared to naive belief acceptance (V0R0)?*

Data source: `reports/month1/rq1_summary.json` and `reports/month1/rq_summary.md`.

### 3.1 Task Success Rate ($\Delta \text{SR}$)
| Family | Condition | $N$ | $\Delta$ (point) | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|
| `goto_type_color` | `clean` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `goto_type_color` | `N1-DROP-15` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `goto_type_color` | `N1-FLIP-10` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `key_door_goal` | `clean` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `key_door_goal` | `N1-DROP-15` | 60 | -0.0833 | -0.1667 | -0.0167 |
| `key_door_goal` | `N1-FLIP-10` | 60 | -0.0833 | -0.2167 | +0.0500 |
| **ALL** | **ALL** | **360** | **-0.0278** | **-0.0528** | **-0.0028** |

### 3.2 Plan Validity ($\Delta \text{PV}$)
| Family | Condition | $N$ | $\Delta$ (point) | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|
| `goto_type_color` | `clean` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `goto_type_color` | `N1-DROP-15` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `goto_type_color` | `N1-FLIP-10` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `key_door_goal` | `clean` | 60 | +0.0000 | +0.0000 | +0.0000 |
| `key_door_goal` | `N1-DROP-15` | 60 | +0.0167 | +0.0000 | +0.0500 |
| `key_door_goal` | `N1-FLIP-10` | 60 | +0.0333 | -0.0833 | +0.1500 |
| **ALL** | **ALL** | **360** | **+0.0083** | **-0.0111** | **+0.0278** |

### 3.3 RQ1 Analytical Assessment
In `goto_type_color`, the goal entity is immediately detectable within the agent's localized surroundings, so neither drop nor flip corruptions altered plan validity or success. 
In `key_door_goal`, which requires sequentially acquiring a key, navigating to a locked door, unlocking it, and reaching the final goal, the belief validator correctly caught corrupted tokens and invalidated false beliefs. However, because recovery replanning was disabled in R0, invalidating a subgoal atom caused V1R0 to safely abort execution, while the naive V0R0 agent occasionally stumbled forward and succeeded if the corrupted token did not completely sever the navigation path. Consequently, validation without recovery demonstrates a conservative bias ($\Delta \text{SR} = -0.0833$ on `key_door_goal`). This provides a crucial insight: **belief validation and recovery replanning must operate as a coupled pair** in dynamic navigation tasks.

---

## 4. RQ2 Results: Bounded Replanning Recovery (V1R1 vs V1R0)

Research Question 2 asks: *Does bounded symbolic replanning (V1R1) reliably recover from unexpected environmental interventions (door relocking and corridor blocking) compared to non-replanning agents (V1R0)?*

Data source: `reports/month1/rq2_summary.json` and `reports/month1/rq_summary.md`.

### 4.1 Task Success & Recovery Rate under N2 Interventions
| Family | Condition | $N$ | Metric | $\Delta$ (point) | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|---|
| `goto_type_color` | `N2-fixed` | 40 | `task_success` | +0.7500 | +0.6000 | +0.8750 |
| `goto_type_color` | `N2-fixed` | 40 | `recovery_rate` | +0.7500 | +0.6000 | +0.8750 |
| `key_door_goal` | `N2-fixed` | 40 | `task_success` | +1.0000 | +1.0000 | +1.0000 |
| `key_door_goal` | `N2-fixed` | 40 | `recovery_rate` | +1.0000 | +1.0000 | +1.0000 |
| **ALL** | **ALL** | **80** | **`task_success`** | **+0.8750** | **+0.8000** | **+0.9375** |
| **ALL** | **ALL** | **80** | **`recovery_rate`** | **+0.8750** | **+0.8000** | **+0.9375** |

### 4.2 Path Efficiency under Interventions ($\Delta \text{Efficiency}$)
| Family | Condition | $N$ | $\Delta$ (point) | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|
| `goto_type_color` | `N2-fixed` | 40 | +0.4167 | +0.3083 | +0.5333 |
| `key_door_goal` | `N2-fixed` | 40 | +0.4523 | +0.4411 | +0.4632 |
| **ALL** | **ALL** | **80** | **+0.4345** | **+0.3789** | **+0.4919** |

### 4.3 RQ2 Analytical Assessment
Bounded replanning (V1R1) proves extraordinarily effective at recovering from unmodeled physical interventions. While V1R0 experienced a 0% recovery rate upon discovering a re-locked door or blocked waypoint, V1R1 achieved a **100% recovery rate on `key_door_goal`** (40/40 episodes recovered) and **75% recovery on `goto_type_color`** (30/40 episodes recovered; the remaining 10 were geometrically unrecoverable due to complete corridor obstruction). Replan counts remained strictly bounded (median = 1 replan per episode), and zero executions exceeded the public action budget.

---

## 5. Threats to Validity

### 5.1 Internal Validity
- **Probe Environment Bias (D-004):** The MiniGrid evaluation layouts use narrow, 2-room corridor configurations. While ideal for evaluating discrete symbolic state transitions and action precondition monitoring, this creates high corridor sensitivity where an intervention block can completely partition the topological graph.
- **Front-Cell Interaction Semantics (D-006):** In MiniGrid, door manipulation and object pickup depend on orientation-relative front-cell coordinates rather than agent co-location. While the adapter contract accommodates this, edge-case alignment failures can cause false invalidation if not precisely synchronized.
- **Frontier Bootstrap Heuristic (D-005):** The current implementation initializes belief using a 4-turn 360° scan bootstrap at reset. While deterministic and recorded in traces, future work should incorporate full continuous frontier-exploration algorithms.

### 5.2 External Validity
- **Gridworld Abstraction:** The current evaluation takes place entirely in discrete 2D gridworlds with discrete turn and step actions.
- **Synthetically Injected Noise:** Perceptual corruptions (N1 drop and flip) are modeled as Bernoulli noise on decoded tokens rather than raw sensor noise, visual occlusion, or VLM hallucination.

---

## 6. Explicit Non-Claims

To ensure absolute scientific integrity and avoid overclaiming:
1. **No Claims on 3D Habitat Navigation:** We do not claim that this study proves 3D Habitat performance or that the discrete MiniGrid results directly transfer to continuous 3D environments without further embodiment adaptation.
2. **No Claims on Photorealistic Generalization:** This evaluation does not demonstrate photorealistic generalization or robustness to complex visual textures, real-world lighting, or sensor blur.
3. **No Claims on Natural VLN End-to-End Solving:** Our symbolic system does not solve natural VLN end-to-end; instructions are processed via structured template grammars rather than unrestricted natural language or open-vocabulary LLM decoders.

---

## 7. Gate Assessment (Gates G0 through G5)

| Gate | Description | Criteria | Status | Empirical Rationale |
|---|---|---|---|---|
| **G0** | Infrastructure & Repro | Clean checkout, reproducible CLI, lockfile integrity | **PASS** | Independent reproduction on `main` (`b35a862`) passed cleanly. |
| **G1** | Smoke Evaluation | 20-episode smoke suite execution | **PASS** | 20/20 smoke episodes executed with zero runtime exceptions. |
| **G2** | Oracle Leakage Guard | Zero evaluation modules in agent runtime | **PASS** | `ns-vln audit` scanned 14 modules, 15 files, 5,503 traces: 0 violations. |
| **G3** | Non-Grid Portability | Core modules decoupled from MiniGrid | **PASS** | `audit-portability` scanned 31 files: 0 violations. `FakeGraphAdapter` passes contract tests. |
| **G4** | Final Matrix Promotion | 1,120 rows reconciled, trace replay ≥99% | **PASS** | `validate-results` verified 1,120/1,120 rows. `validate-traces` verified 5,503 traces. |
| **G5** | Typed Habitat Decision | Rubric-based transition decision | **CONDITIONAL HOLD** | All engineering, planning, clean, and RQ2 gates PASS; RQ1 shows validation-without-recovery conservatism ($\Delta \text{SR} < -2\text{ pp}$). |

---

## 8. Protocol Deviations (D-001 through D-007)

During Month 1 development and independent reproduction, seven protocol deviations were identified, tracked, and audited:

1. **D-001 (Snap AppArmor `uv` execution failure):** The Snap distribution of `uv` failed under AppArmor confinement during subprocess invocations. Fixed by establishing standalone `uv` 0.12.7 at `~/.local/bin/uv`.
2. **D-002 (Missing CLI subcommands):** Initial reproduction scripts lacked explicit subcommands (`validate-report`, `validate-habitat-decision`, `audit-portability`). These entrypoints were fully implemented in `src/neuro_symbolic_vln/cli.py` and validated by unit tests.
3. **D-003 (Manifest schema and target coordinate verification):** Addressed discrepancies between manifest keys and evaluator expectations by standardizing on schema 1.0.0 with frozen target tuples.
4. **D-004 (`key_door_goal` narrow probe topology):** The 2-room corridor topology in MiniGrid presents unavoidable topological bottlenecks. Documented as a known validity threat.
5. **D-005 (Frontier exploration bootstrap Lite):** Implemented an initial 360-degree rotation bootstrap at episode reset to populate the 4-heading field of view, recorded as symbolic `scan` actions in trace files.
6. **D-006 (Key-door interaction front-cell semantics):** MiniGrid interaction dynamics require facing the front cell adjacent to locked doors. Synchronized adapter and verifier coordinate offsets.
7. **D-007 (Reproduction runner script hardcoded path):** Resolved rigid environment assumptions in `scripts/run_a_j04_reproduction.sh` by adding path detection for local `uv` installations.
