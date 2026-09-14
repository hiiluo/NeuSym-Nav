# Thành viên B — Language, Belief và Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) hoặc `superpowers:executing-plans` để thực hiện tuần tự. Mọi bước dùng checkbox để theo dõi.

**Goal:** Triển khai toàn bộ lane Language–Belief–Planning của causal Neuro-Symbolic VLN 2D PoC trong 20 working days, với typed contracts, test-first steps, frequent commits và handoff rõ cho Thành viên A.

**Architecture:** B sở hữu shared types, instruction parser, EvidenceStore/BeliefMap, validator, committed state, LocationGraph, positive STRIPS/PDDL, pyperplan adapter, execution monitor, bounded replanning, N1 corruption, trace/replay, leakage audit và paired-bootstrap summaries. B không implement MiniGrid environments, controller, evaluator oracle, frontier execution, N2 world interventions hoặc metric runner; các artifacts đó nhận từ A.

**Tech Stack:** Python 3.12, `uv`, pyperplan 2.1, NumPy, PyYAML, pytest, Ruff, strict mypy, GitHub Actions.

**Spec:** `docs/neuro_symbolic_vln_2d_complete_implementation_plan.md`  
**Companion plan:** `docs/member_a_implementation_handbook.md`

## Global Constraints

- Shared types/interfaces là source of truth; không tạo duplicate local dataclasses.
- Positive STRIPS chỉ dùng `:strips :typing`, không negative preconditions, conditional effects, action costs hoặc contingent branches.
- Unknown không được serialize như false/free.
- Normal agent path không import hoặc nhận `EvaluationOracle`/private sidecar.
- Parser chỉ trả deterministic/ambiguous/unsupported, không continuous confidence.
- Clean categorical evidence reliability `1.0`; synthetic scores chỉ xuất hiện trong declared N1 model.
- `V0R0`, `V1R0`, `V1R1` phải khác nhau đúng validation/replanning switches.
- Mọi failure/plan/episode outcome phải typed; không generic `FAILED`.
- Contracts freeze sau Day 5; thay đổi cần joint approval và compatibility note.
- Mỗi code task phải có red→green evidence, targeted tests và A rerun.
- Branch của B dùng prefix `feat/b-`, `test/b-`, `exp/b-` hoặc `docs/b-`.

---

## 1. Lịch riêng của Thành viên B

| Ngày | Task/step của B | Output B phải hoàn thành trong ngày | Handoff cần nhận từ A | Joint checkpoint |
|---|---|---|---|---|
| Day 1 | `B-01.S1–S7` | Shared contracts, strict static/test config và CI | Package paths/dependencies | G0 contract/security decision |
| Day 2 | `B-02.S1–S4` | Failing serializer tests, LocationGraph và PDDL domain skeleton | Native action/verifier semantics checklist | PDDL predicate/action review |
| Day 3 | `B-02.S5–S7` | Serializer, bounded pyperplan adapter, action parser và tests | Native applicability fixtures | Planner/controller contract freeze |
| Day 4 | `B-J01.S1–S3` | B3 problem generation, typed plans và 2+2 sample plan hashes | Controller/oracle-state execution fixtures | Compare plan/native effects |
| Day 5 | `B-J01.S4` | Validate 20 B3 plans, fix planning issues và freeze contracts | Smoke execution traces/outcomes | G1 + interface freeze |
| Day 6 | `B-03.S1–S6` | Grammar, ParseResult variants và 40-case parser suite | Task specs/ambiguity fixtures | Grammar/reason-code freeze |
| Day 7 | `B-04.S1–S4` | EvidenceStore, unknown default, provenance và base merge | Local Evidence/action fixtures | Evidence merge review |
| Day 8 | `B-04.S5–S7` | Conflicts, staleness, invalidation hooks và deterministic hash | Door/motion/carrying transitions | Belief policy freeze |
| Day 9 | `B-05.S1–S7` | Validator, reason codes, committed state và serializer filter | Environment conflict/clean fixtures | Validation/commitment freeze |
| Day 10 | `B-J02` | V0R0/V1R0 switches, symbolic integration và leakage tests | Local adapter/controller/oracle harness | G2 trace + leakage review |
| Day 11 | `B-06.S1–S4` | Execution mismatch model và belief invalidation | StepResult/frontier event fixtures | Monitor reason-code review |
| Day 12 | `B-06.S5–S7` | Replan budget, loop signatures, timeout/error propagation | End-to-end mismatch fixtures | Recovery policy freeze |
| Day 13 | `B-07.S1–S7` | N1-DROP/N1-FLIP, reliability model, private labels và hashes | Decoder visibility/eligible facts | RQ1 protocol freeze |
| Day 14 | `B-08.S1–S7` | Typed outcomes, JSONL schema, canonical hashes và replay | Env/action/verifier events | Trace schema freeze |
| Day 15 | `B-J03` | Full V1R1 belief/planning/recovery/N1/trace diagnostics | Env/frontier/N2 integration | G3 root-cause review |
| Day 16 | `B-09.S1–S3` | Paired/statistics tests, leakage scan và analysis config | Frozen schemas/configs + metric fixtures | G4 pre-freeze |
| Day 17 | `B-09.S4` | Monitor B3/RQ1 runs, validate row pairs/hashes/traces | B3/RQ1 raw rows | RQ1 rerun decision |
| Day 18 | `B-09.S5–S6` | RQ2/V1R1 summaries, 10k bootstrap CIs và audit reports | Full raw matrix/traces | G4 table reconciliation |
| Day 19 | `B-J04.S1–S3` | README corrections, independent rerun, methods/results draft | Reproduction + portability evidence | Reproduction/report review |
| Day 20 | `B-J04.S4–S7` | RQ interpretation, threats/non-claims, Habitat rubric và final validation | Engineering gate evidence | G5 typed decision/final artifact |

---

## 2. Shared interface package B phải tạo Day 1

B là owner của `contracts.py`. Các core types tối thiểu:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

LocationId = str
HeadingId = str
EntityId = str
EvidenceId = str


@dataclass(frozen=True)
class EpisodeSpec:
    episode_id: str
    family: str
    instruction: str
    public_action_budget: int
    manifest_hash: str


@dataclass(frozen=True)
class CategoricalCell:
    object_index: int
    color_index: int
    state_index: int
    visible: bool


@dataclass(frozen=True)
class CategoricalView:
    cells_by_x: tuple[tuple[CategoricalCell, ...], ...]


@dataclass(frozen=True)
class ObservationPacket:
    observation_id: str
    step: int
    categorical_view: CategoricalView
    heading: HeadingId
    carried_entity: EntityId | None
    instruction: str


@dataclass(frozen=True)
class PrimitiveAction:
    name: str


@dataclass(frozen=True)
class StepResult:
    observation: ObservationPacket
    action_succeeded: bool
    failure_reason: str | None
    task_success: bool
    terminated: bool
    truncated: bool


class TriValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class PlanStatus(str, Enum):
    FOUND = "found"
    ALREADY_SATISFIED = "already_satisfied"
    NEEDS_INFORMATION = "needs_information"
    NO_PLAN_KNOWN_SPACE = "no_plan_known_space"
    UNSUPPORTED_GOAL = "unsupported_goal"
    TIMEOUT = "timeout"
    SERIALIZATION_ERROR = "serialization_error"
    PLANNER_ERROR = "planner_error"


@dataclass(frozen=True, order=True)
class GroundAtom:
    predicate: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Provenance:
    episode_id: str
    observation_id: str
    sensor_model_id: str
    local_cell: tuple[int, int] | None
    corruption_channel: str | None


@dataclass(frozen=True)
class Evidence:
    evidence_id: EvidenceId
    atom: GroundAtom
    polarity: bool
    reliability: float
    observed_step: int
    stale_after_steps: int | None
    source: str
    provenance: Provenance


@dataclass(frozen=True)
class BeliefRecord:
    value: TriValue
    reliability: float | None
    last_observed_step: int | None
    stale: bool
    evidence_ids: tuple[EvidenceId, ...]
    conflict_reason: str | None = None


@dataclass(frozen=True)
class LocationGraph:
    nodes: frozenset[LocationId]
    directed_edges: frozenset[tuple[LocationId, HeadingId, LocationId]]
    frontier_nodes: frozenset[LocationId]


@dataclass(frozen=True)
class CommittedPlanningState:
    version: int
    state_hash: str
    true_facts: frozenset[GroundAtom]
    unresolved_required_facts: frozenset[GroundAtom]
    provenance_by_fact: Mapping[GroundAtom, tuple[EvidenceId, ...]]
    location_graph: LocationGraph


@dataclass(frozen=True)
class SymbolicAction:
    name: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class PlanResult:
    status: PlanStatus
    actions: tuple[SymbolicAction, ...]
    planning_time_ms: float
    state_hash: str
    problem_hash: str | None
    reason: str | None
```

B phải gửi commit hash của contract cho A trước khi A implement adapters.

---

## Task B-01: Shared contracts, static config và CI

**Lịch:** Day 1, 2 giờ implementation + 0,5 giờ validation  
**Branch:** `feat/b-shared-contracts`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/contracts.py`
- Create: `tests/test_contracts.py`
- Modify: `pyproject.toml` tool sections
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: package structure/dependencies từ A.
- Produces: stable dataclasses/enums và CI commands.

### Step-by-step

- [ ] **Step 1: Viết failing immutability test**

```python
# tests/test_contracts.py
import pytest

from neuro_symbolic_vln.contracts import GroundAtom


def test_ground_atom_is_immutable_and_orderable() -> None:
    atom = GroundAtom("robot-at", ("robot", "loc-1"))
    with pytest.raises(AttributeError):
        atom.predicate = "changed"  # type: ignore[misc]
    assert atom < GroundAtom("wall", ("loc-1",))
```

- [ ] **Step 2: Run expected failure**

```bash
uv run pytest tests/test_contracts.py -v
```

Expected: import/class missing.

- [ ] **Step 3: Implement exact shared types**

Tạo enums/dataclasses từ Section 2, thêm `EpisodeOutcome`, `ParseStatus`, `GroundingStatus`, `ValidationDisposition` từ master plan.

- [ ] **Step 4: Add validation in dataclass post-init nơi cần**

```python
@dataclass(frozen=True)
class Evidence:
    evidence_id: EvidenceId
    atom: GroundAtom
    polarity: bool
    reliability: float
    observed_step: int
    stale_after_steps: int | None
    source: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be in [0, 1]")
        if self.observed_step < 0:
            raise ValueError("observed_step must be non-negative")
```

- [ ] **Step 5: Configure strict mypy/Ruff/pytest and CI**
- [ ] **Step 6: Run test/static checks**

```bash
uv run pytest tests/test_contracts.py -v
uv run ruff check .
uv run mypy src
```

- [ ] **Step 7: Commit B**

```bash
git add src/neuro_symbolic_vln/contracts.py tests/test_contracts.py pyproject.toml .github/workflows/ci.yml
git commit -m "feat(core): define shared neuro-symbolic contracts"
```

### Test cases bổ sung

| ID | Validation | Expected |
|---|---|---|
| `B01-TC01` | Reliability <0 hoặc >1 | `ValueError` |
| `B01-TC02` | Negative observed step | `ValueError` |
| `B01-TC03` | PlanStatus values | Exact stable strings |
| `B01-TC04` | Contracts import without MiniGrid | Exit 0 |
| `B01-TC05` | Ruff/mypy | Exit 0 |

### Handoff cho A

B gửi contract commit hash và short interface table. A chạy `tests/test_contracts.py` trước adapter work.

### Commits

- B: `feat(core): define shared neuro-symbolic contracts`
- B: `ci: add strict static and test workflow`
- A validation: `test(env): consume shared environment contracts` nếu A thêm contract test.
- Joint: `docs: record initial interface decisions`.

### Definition of Done

Contracts compile, 5 cases PASS, A xác nhận package import và no duplicate types.

---

## Task B-02: LocationGraph, positive STRIPS và pyperplan adapter

**Lịch:** Day 2–3, 8 team-hours  
**Branch:** `feat/b-pddl-planner`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/planning/location_graph.py`
- Create: `src/neuro_symbolic_vln/planning/domain.pddl`
- Create: `src/neuro_symbolic_vln/planning/problem_serializer.py`
- Create: `src/neuro_symbolic_vln/planning/pyperplan_adapter.py`
- Create: `tests/planning/test_domain.py`
- Create: `tests/planning/test_serializer.py`
- Create: `tests/planning/test_pyperplan_adapter.py`
- Create: `tests/planning/test_native_action_mapping.py`

**Interfaces:**
- Consumes: A native action/verifier mapping.
- Produces: `CommittedPlanningState → PlanResult`.

### Step-by-step

- [ ] **Step 1: Viết failing unknown-serialization test**

```python
from neuro_symbolic_vln.contracts import CommittedPlanningState, GroundAtom, LocationGraph
from neuro_symbolic_vln.planning.problem_serializer import serialize_problem


def test_serializer_does_not_emit_unknown_as_passable() -> None:
    state = CommittedPlanningState(
        version=1,
        state_hash="state-1",
        true_facts=frozenset({GroundAtom("robot-at", ("robot", "loc-1"))}),
        unresolved_required_facts=frozenset({GroundAtom("passable", ("loc-2",))}),
        provenance_by_fact={},
        location_graph=LocationGraph(
            nodes=frozenset({"loc-1"}),
            directed_edges=frozenset(),
            frontier_nodes=frozenset({"loc-1"}),
        ),
    )
    problem = serialize_problem(state, goal_atom=GroundAtom("task-satisfied", ()))
    assert "(passable loc-2)" not in problem
```

- [ ] **Step 2: Run expected FAIL**.
- [ ] **Step 3: Implement serializer from only `true_facts`**.
- [ ] **Step 4: Viết domain với turn/move/pickup/toggle/confirm actions**.

PDDL sample:

```lisp
(:action move-forward
 :parameters (?r - robot ?from ?to - location ?h - heading)
 :precondition (and
   (robot-at ?r ?from)
   (facing ?r ?h)
   (front-cell ?from ?h ?to)
   (passable ?to))
 :effect (and
   (not (robot-at ?r ?from))
   (robot-at ?r ?to)))
```

- [ ] **Step 5: Add pyperplan bounded worker wrapper**.

```python
from dataclasses import dataclass
from time import perf_counter

from neuro_symbolic_vln.contracts import PlanResult, PlanStatus


@dataclass(frozen=True)
class PlannerConfig:
    timeout_seconds: float = 2.0
    search: str = "bfs"


def planner_error_result(state_hash: str, reason: str) -> PlanResult:
    return PlanResult(
        status=PlanStatus.PLANNER_ERROR,
        actions=(),
        planning_time_ms=0.0,
        state_hash=state_hash,
        problem_hash=None,
        reason=reason,
    )
```

Worker timeout implementation phải terminate process và trả `TIMEOUT`, không hang.

- [ ] **Step 6: Add exact symbolic action parser**.
- [ ] **Step 7: Run planner tests and A native mapping tests**.

### Validation commands

```bash
uv run pytest tests/planning -v
uv run pytest tests/planning/test_native_action_mapping.py -v
uv run mypy src/neuro_symbolic_vln/planning
```

### Required cases

- PDDL parser supports only `:strips :typing`.
- turn/move plan found.
- key pickup before door toggle/crossing.
- GoTo confirm from adjacent-facing pose.
- unknown not emitted.
- no-plan/timeout/serialization/planner errors typed.
- SymbolicAction parse round-trip exact.
- planning package has no MiniGrid import.

### Handoff từ/cho A

A supplies native action fixtures. B supplies `SymbolicAction` argument schemas and sample plans. A validates every action is executable.

### Commits

- B: `feat(planning): add location graph and positive STRIPS domain`
- B: `feat(planning): serialize committed states to PDDL`
- B: `feat(planning): add bounded pyperplan adapter`
- A validation: `test(planning): validate native action applicability`
- Joint: `docs: freeze planner and controller interfaces`

### Definition of Done

All planning tests PASS, timeout bounded, unknown safe, A approves mapping.

---

## Task B-J01: B3 planning integration và interface freeze

**Lịch:** Day 4–5  
**Branch:** `feat/b-b3-planning-integration`  
**Joint driver:** B planning, A execution

### B responsibilities

- Build B3 PDDL problems from oracle-derived committed states.
- Return typed PlanResult/problem hash/action sequence.
- Independently validate plans against believed state.

### A must provide

- Controller/action mapping, oracle-state provider, task verifier and primitive traces.

### Test-first integration

```python
from neuro_symbolic_vln.contracts import PlanStatus
from neuro_symbolic_vln.testing import run_b3_episode


def test_b3_key_door_plan_executes_successfully() -> None:
    result = run_b3_episode(seed=7, family="key_door_goal")
    assert result.plan.status is PlanStatus.FOUND
    assert result.task_success
    assert not result.untyped_failures
```

Run expected FAIL before wiring. After integration:

```bash
uv run pytest tests/test_end_to_end_smoke.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method B3
```

Expected 20/20 success, plan validity 100%, no primitive `done`.

### Commits

- B: `feat(planning): integrate B3 problem and typed plan handling`
- A: `feat(control): integrate B3 controller and oracle execution`
- Joint: `feat(agent): complete oracle-input planning vertical slice`
- Joint: `docs: freeze runtime interfaces after G1`

### Definition of Done

G1 signed off; contracts frozen and sample traces approved by both.

---

## Task B-03: Deterministic grammar và curated parser suite

**Lịch:** Day 6  
**Branch:** `feat/b-template-parser`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/language/template_parser.py`
- Create: `tests/language/test_template_parser.py`
- Create: `tests/language/test_parser_agent_contract.py`
- Create: parser case fixture YAML/JSON.

### Step-by-step

- [ ] Write failing canonical parse test:

```python
from neuro_symbolic_vln.contracts import GroundAtom
from neuro_symbolic_vln.language.template_parser import parse_instruction


def test_parse_goto_instruction() -> None:
    result = parse_instruction("Go to the green ball.")
    assert result.status.value == "deterministic"
    assert result.goal_program is not None
    assert result.goal_program.ordered_subgoals == (
        GroundAtom("goto-target", ("green", "ball")),
    )
```

- [ ] Implement normalization and explicit regex grammar:

```python
import re

_GOTO = re.compile(
    r"^(?:go to|find|move to) the "
    r"(?P<color>red|green|blue|yellow|purple|grey) "
    r"(?P<object>ball|box|key)$",
    flags=re.IGNORECASE,
)


def normalize_instruction(text: str) -> str:
    return " ".join(text.strip().rstrip(".").split())
```

- [ ] Add key-door ordered grammar.
- [ ] Return typed ambiguous/unsupported reasons; no confidence float.
- [ ] Create 24 supported, 8 ambiguous, 8 unsupported cases.
- [ ] Add agent contract: unsupported parse emits no env action.

### Validation commands

```bash
uv run pytest tests/language/test_template_parser.py -v
uv run pytest tests/language/test_parser_agent_contract.py -v
```

### Expected

40/40 case classifications exact; A confirms GoalProgram matches task specs.

### Commits

- B: `feat(language): parse core grammar and curated paraphrases`
- A validation: `test(language): validate parser against task specifications`
- Joint: `docs: freeze instruction grammar and reason codes`

### Definition of Done

Parser deterministic, finite, typed and integration-safe.

---

## Task B-04: EvidenceStore và tri-valued BeliefMap

**Lịch:** Day 7–8  
**Branch:** `feat/b-tri-valued-belief`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/belief/evidence.py`
- Create: `src/neuro_symbolic_vln/belief/state.py`
- Create: `tests/belief/test_evidence.py`
- Create: `tests/belief/test_state.py`
- Create: `tests/belief/test_action_feedback_integration.py`

### Step-by-step

- [ ] Write failing unknown-default test:

```python
from neuro_symbolic_vln.belief.state import BeliefMap
from neuro_symbolic_vln.contracts import GroundAtom, TriValue


def test_unseen_atom_is_unknown() -> None:
    belief = BeliefMap()
    record = belief.get(GroundAtom("passable", ("loc-9",)))
    assert record.value is TriValue.UNKNOWN
```

- [ ] Implement EvidenceStore append/snapshot:

```python
class EvidenceStore:
    def __init__(self) -> None:
        self._items: list[Evidence] = []

    def append(self, evidence: tuple[Evidence, ...]) -> None:
        self._items.extend(evidence)

    def snapshot(self) -> tuple[Evidence, ...]:
        return tuple(self._items)
```

- [ ] Implement BeliefMap unknown default, positive/negative merge and provenance.
- [ ] Add conflict state preserving all evidence IDs.
- [ ] Add static/mutable staleness policy.
- [ ] Add action-feedback invalidation hooks from A fixtures.
- [ ] Add deterministic state hash.

Example unknown default:

```python
class BeliefMap:
    def __init__(self) -> None:
        self._records: dict[GroundAtom, BeliefRecord] = {}

    def get(self, atom: GroundAtom) -> BeliefRecord:
        return self._records.get(
            atom,
            BeliefRecord(
                value=TriValue.UNKNOWN,
                reliability=None,
                last_observed_step=None,
                stale=False,
                evidence_ids=(),
            ),
        )
```

### Validation commands

```bash
uv run pytest tests/belief/test_evidence.py tests/belief/test_state.py -v
uv run pytest tests/belief/test_action_feedback_integration.py -v
```

### Required cases

- unseen/drop→UNKNOWN;
- accepted positive→TRUE;
- accepted negative→FALSE;
- conflicts preserve both evidence IDs;
- dynamic facts stale after declared steps;
- failed move invalidates affected facts;
- deterministic hash.

### Handoff từ/cho A

A provides local Evidence/action fixtures. B returns BeliefMap snapshot/hash API and staleness table.

### Commits

- B: `feat(belief): add evidence store and provenance`
- B: `feat(belief): add tri-valued temporal state`
- A validation: `test(belief): validate actuator-feedback transitions`
- Joint: `docs: freeze staleness and conflict policy`

### Definition of Done

All seven cases PASS; no evidence loss; A approves environment transition semantics.

---

## Task B-05: Validator và CommittedPlanningState

**Lịch:** Day 9  
**Branch:** `feat/b-validation-commitment`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/belief/validator.py`
- Modify: `src/neuro_symbolic_vln/planning/problem_serializer.py`
- Create: `tests/belief/test_validator.py`
- Create: `tests/belief/test_clean_validation.py`

### Step-by-step

- [ ] Write failing uniqueness test:

```python
from neuro_symbolic_vln.belief.validator import validate_robot_location
from neuro_symbolic_vln.contracts import GroundAtom


def test_two_robot_locations_are_rejected() -> None:
    decisions = validate_robot_location(
        (
            GroundAtom("robot-at", ("robot", "loc-1")),
            GroundAtom("robot-at", ("robot", "loc-2")),
        )
    )
    assert {decision.disposition.value for decision in decisions} == {"uncertain"}
```

- [ ] Implement schema/type/ontology validators.
- [ ] Implement uniqueness/exclusivity: robot location, held object, door state, object location.
- [ ] Implement occupancy/passability conflicts.
- [ ] Implement staleness and threshold decisions.
- [ ] Build CommittedPlanningState only from accepted non-stale TRUE facts.
- [ ] Add clean local validation regression from A fixtures.

Representative commit filter:

```python
def commit_true_facts(
    decisions: tuple[ValidationDecision, ...],
    evidence_by_id: dict[str, Evidence],
) -> frozenset[GroundAtom]:
    return frozenset(
        evidence_by_id[decision.evidence_id].atom
        for decision in decisions
        if decision.disposition is ValidationDisposition.ACCEPTED
        and evidence_by_id[decision.evidence_id].polarity
    )
```

### Validation commands

```bash
uv run pytest tests/belief/test_validator.py -v
uv run pytest tests/belief/test_clean_validation.py -v
uv run pytest tests/planning/test_serializer.py -v
```

### Required cases

invalid arity/type; two robot locations; multiple held objects; open+locked door; passable+wall; stale fact; unknown not serialized; clean exact facts accepted.

### Commits

- B: `feat(validation): add typed ontology and consistency decisions`
- B: `feat(validation): commit only verified known facts`
- A validation: `test(validation): cover environment conflicts and clean facts`
- Joint: `docs: freeze validation and commitment policy`

### Definition of Done

All cases PASS, stable reason codes, clean visible evidence 100% accepted/accurate.

---

## Task B-J02: Clean local V0R0/V1R0 và leakage integration

**Lịch:** Day 10  
**Branch:** `feat/b-local-agent-integration`

### B responsibilities

- Wire parser→BeliefMap→validator→committed state→planner.
- Implement method switches:
  - V0R0: transport/schema only, no validation/replanning.
  - V1R0: full validation, no replanning.
- Add no-oracle import/constructor/sidecar tests.

### A must provide

Adapter/decoder/controller/oracle evaluation harness và smoke manifests.

### Validation

```bash
uv run pytest tests/test_no_oracle_leakage.py -v
uv run pytest tests/test_end_to_end_smoke.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method V0R0
uv run ns-vln evaluate --config configs/smoke.yaml --method V1R0
```

Expected: local-only traces, unknown safe, no oracle leak, all outcomes typed.

### Commits

- B: `feat(agent): integrate parser belief validation and planning path`
- A: `feat(agent): integrate local environment and controller path`
- Joint: `test(agent): validate clean local pipelines and oracle isolation`

### Definition of Done

G2 signed off and full traces reviewed by both.

---

## Task B-06: Execution monitor và bounded replanning

**Lịch:** Day 11–12  
**Branch:** `feat/b-execution-replanning`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/control/monitor.py`
- Modify: `src/neuro_symbolic_vln/agent.py`
- Create: `tests/control/test_replanning.py`
- Create: `tests/control/test_execution_monitor_integration.py`

### Step-by-step

- [ ] Write failing blocked-move decision test:

```python
from neuro_symbolic_vln.control.monitor import ExecutionMonitor


def test_failed_forward_invalidates_and_requests_replan() -> None:
    monitor = ExecutionMonitor(max_replans=5)
    decision = monitor.observe_action_result(
        symbolic_action="move-forward",
        action_succeeded=False,
        failure_reason="blocked",
    )
    assert decision.reason_code == "execution.predicted_move_failed"
    assert decision.requires_replan
```

- [ ] Implement typed monitor decision:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorDecision:
    reason_code: str
    atoms_to_invalidate: tuple[GroundAtom, ...]
    requires_reobservation: bool
    requires_replan: bool
```

- [ ] Map failed move/toggle/verifier rejection/stale precondition to affected facts.
- [ ] Implement replan counter max 5.
- [ ] Implement no-progress signature counter max 2 repeats.
- [ ] Propagate planner timeout/error typed outcomes.
- [ ] Integrate with A StepResult/frontier events.

### Validation commands

```bash
uv run pytest tests/control/test_replanning.py -v
uv run pytest tests/control/test_execution_monitor_integration.py -v
```

### Required cases

blocked move; re-locked door; stale precondition precheck; sixth replan rejected; third repeated signature loop; planner timeout; new evidence creates new state hash and plan.

### Commits

- B: `feat(replanning): invalidate beliefs from execution mismatch`
- B: `feat(replanning): bound replans and detect no-progress loops`
- A validation: `test(replanning): cover environment and controller mismatches`
- Joint: `docs: freeze recovery triggers and termination order`

### Definition of Done

All cases PASS, no unbounded loop, A reruns environment mismatch tests.

---

## Task B-07: N1 evidence corruption và reliability model

**Lịch:** Day 13  
**Branch:** `exp/b-rq1-corruption`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/evaluation/corruption.py`
- Create: `tests/evaluation/test_corruption.py`
- Create: `tests/evaluation/test_corruption_visibility.py`

### Step-by-step

- [ ] Write failing deterministic-drop test:

```python
from neuro_symbolic_vln.evaluation.corruption import drop_evidence


def test_drop_evidence_is_seeded() -> None:
    evidence = tuple(f"ev-{index}" for index in range(20))
    first = drop_evidence(evidence, rate=0.15, seed=17)
    second = drop_evidence(evidence, rate=0.15, seed=17)
    assert first == second
```

- [ ] Implement seeded selection without mutating input.
- [ ] Implement typed attribute substitutions only for eligible visible evidence.
- [ ] Implement overlapping Beta score model:

```python
import numpy as np


def reliability_score(*, correct: bool, rng: np.random.Generator) -> float:
    alpha, beta = (8.0, 2.0) if correct else (3.0, 5.0)
    return float(np.clip(rng.beta(alpha, beta), 0.05, 0.99))
```

- [ ] Store hidden correctness labels only in evaluator sidecar.
- [ ] Add corruption model version and deterministic hash.
- [ ] Generate clean/DROP/FLIP checkpoints.

### Validation commands

```bash
uv run pytest tests/evaluation/test_corruption.py -v
uv run pytest tests/evaluation/test_corruption_visibility.py -v
```

### Expected

same seed same output; dropped evidence absent→unknown; only visible eligible records altered; public agent input has no correctness label; scores bounded/versioned.

### Handoff từ/cho A

A provides decoder visibility/eligible evidence fixtures. B returns corrupted evidence/checkpoint hashes for RQ1 runs.

### Commits

- B: `feat(evaluation): add reproducible RQ1 evidence corruption`
- A validation: `test(evaluation): enforce local visibility corruption boundary`
- Joint: `docs: freeze RQ1 corruption and score model`

### Definition of Done

All corruption tests PASS, deterministic and no hidden-label leak.

---

## Task B-08: Typed outcomes, trace lineage và replay

**Lịch:** Day 14  
**Branch:** `feat/b-trace-replay`  
**Reviewer:** A

**Files:**
- Create: `src/neuro_symbolic_vln/trace.py`
- Create: `tests/test_trace.py`
- Create: `tests/test_trace_security.py`

### Step-by-step

- [ ] Write failing trace round-trip test:

```python
from neuro_symbolic_vln.trace import TraceRecord, deserialize_record, serialize_record


def test_trace_record_round_trip() -> None:
    record = TraceRecord(
        episode_id="ep-1",
        method="V1R1",
        step=3,
        belief_state_hash="belief-3",
        committed_state_hash="state-3",
        primitive_action="move_forward",
        action_succeeded=False,
        reason_code="execution.predicted_move_failed",
    )
    assert deserialize_record(serialize_record(record)) == record
```

- [ ] Implement frozen `TraceRecord` and canonical JSON serialization.
- [ ] Reject missing required fields/unsupported schema version.
- [ ] Add deterministic evidence/state/problem/decision hashes.
- [ ] Add typed terminal outcome requirement.
- [ ] Add replay function comparing decision/outcome hashes.
- [ ] Add security scan excluding private sidecar/full grid.

Canonical serializer:

```python
import json
from dataclasses import asdict


def serialize_record(record: TraceRecord) -> str:
    return json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))
```

### Validation commands

```bash
uv run pytest tests/test_trace.py -v
uv run pytest tests/test_trace_security.py -v
```

### Required cases

round-trip; missing field rejected; stable hash; replay same decision; no private data; all failure paths typed.

### Commits

- B: `feat(trace): record evidence-to-action lineage and replay hashes`
- A validation: `test(trace): validate environment fields and private-data exclusion`
- Joint: `docs: freeze trace schema version one`

### Definition of Done

Diagnostic fixtures replay at 100%, A validates environment/action fields.

---

## Task B-J03: Full V1R1 diagnostic integration

**Lịch:** Day 15  
**Branch:** `feat/b-closed-loop-integration`

### B responsibilities

- Integrate N1, BeliefMap, validation, planner, monitor, replanning and trace.
- Diagnose symbolic failures only after reproducing failing test.
- Validate typed outcomes and bounds.

### A must provide

Frontier explorer, N2 interventions, env/controller/evaluator integration.

### Validation

```bash
uv run pytest tests/test_end_to_end_smoke.py tests/control/test_replanning.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method V1R1
uv run ns-vln evaluate --config configs/diagnostic.yaml --method V1R1
uv run ns-vln validate-traces --runs runs/diagnostic
```

Expected: all diagnostics success hoặc exact typed terminal outcome; no unbounded run; trace replay pass.

### Commits

- B: `fix(agent): resolve belief planning and recovery integration failures`
- A: `fix(agent): resolve environment frontier and controller integration failures`
- Joint: `feat(agent): complete bounded neuro-symbolic closed loop`

### Definition of Done

G3 signed off and no unclassified outcome.

---

## Task B-09: Leakage audit, paired bootstrap và summaries

**Lịch:** Day 16–18  
**Branch:** `feat/b-result-audit`  
**Reviewer:** A

**Files:**
- Create/modify: audit utilities, summary command, tests.
- Create: `reports/month1/` tables and audit reports.

### Step-by-step

- [ ] Write failing paired-delta test:

```python
from neuro_symbolic_vln.evaluation.statistics import paired_delta


def test_paired_delta_uses_matching_episode_ids() -> None:
    treatment = {"ep-1": 1.0, "ep-2": 0.5}
    control = {"ep-1": 0.5, "ep-2": 0.0}
    assert paired_delta(treatment, control) == 0.5
```

- [ ] Implement strict paired ID validation.
- [ ] Implement stratified 10.000-resample bootstrap with fixed analysis seed.
- [ ] Implement import/sidecar leakage audit.
- [ ] Implement trace completeness/replay summaries.
- [ ] Generate per-family/per-condition RQ tables.
- [ ] Reject missing/duplicate pairs or hash mismatch.

Minimal paired function:

```python
def paired_delta(
    treatment: dict[str, float],
    control: dict[str, float],
) -> float:
    if treatment.keys() != control.keys():
        raise ValueError("paired episode IDs must match")
    deltas = [treatment[key] - control[key] for key in sorted(treatment)]
    return sum(deltas) / len(deltas)
```

### Validation commands

```bash
uv run pytest tests/evaluation/test_statistics.py -v
uv run pytest tests/test_no_oracle_leakage.py tests/test_trace.py -v
uv run ns-vln audit --runs runs/final
uv run ns-vln summarize --runs runs/final --output reports/month1/
uv run ns-vln validate-traces --runs runs/final
```

### Expected

zero leak; no missing/duplicate pair; trace completeness/replay ≥99%; CIs per stratum; raw-summary spot checks exact.

### Handoff từ/cho A

A provides frozen raw rows/traces/hashes. B returns audited tables/CIs and rerun list limited to infrastructure failures.

### Commits

- B: `test(security): audit oracle and sidecar boundaries`
- B: `feat(evaluation): add paired bootstrap and trace summaries`
- A validation: `test(evaluation): spot-check summaries against raw results`
- Joint: `docs: freeze RQ1 and RQ2 result tables`

### Definition of Done

G4 audit package complete and A approves summary/raw agreement.

---

## Task B-J04: Reproduction docs, RQ interpretation và final Habitat decision

**Lịch:** Day 19–20  
**Branch:** `docs/b-final-analysis`

### B responsibilities

- Observe A fresh-clone reproduction; sửa README/config docs.
- Independently rerun representative evaluation.
- Write RQ1/RQ2 methods, estimands, tables, CIs and threats.
- Fill empirical gates and explicit non-claims.
- Validate final report against result summaries.

### A must provide

Reproduction log, portability audit, fake adapter results, engineering gates and environment/control/evaluation methods.

### Test-first documentation validation

Create validation command/script that rejects report missing required sections or mismatched values:

```bash
uv run ns-vln validate-report --report reports/month1/
uv run ns-vln validate-results --runs runs/final --report reports/month1/
uv run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml
```

Expected:

- all required sections present;
- result values match summaries;
- one typed Habitat decision;
- no unsupported RGB/Habitat/generalization claims;
- all protocol deviations listed.

### Commits

- B: `docs: correct setup and reproduction instructions`
- B: `docs: add RQ statistics and validity analysis`
- A: `docs: add environment control and evaluation results`
- Joint: `docs: record Habitat migration go-no-go decision`
- Joint: `docs: finalize month-one neuro-symbolic VLN artifact`

### Definition of Done

G5 complete, final report evidence-linked và both members approve.

---

## 3. Cross-validation duties của B đối với A-owned tasks

| Ngày | A artifact B phải validate | B validation command/evidence |
|---|---|---|
| Day 1 | Scaffold/dependencies/package | Ruff/mypy/pytest/secret checks in CI |
| Day 2–3 | Adapter/tasks/verifier | `uv run pytest tests/env -v`; symbolic semantics mapping |
| Day 4–5 | Controller/B3 execution | Compare plan effects vs primitive traces |
| Day 6–7 | Observation decoder | Local-only import/access and Evidence contract tests |
| Day 8–9 | Oracle/manifests | Sidecar leakage and deterministic hash tests |
| Day 11–12 | Frontier explorer | TaskMonitor boundary/no-oracle tests |
| Day 13–14 | N2 interventions | Paired checkpoint/recoverability/sidecar tests |
| Day 16–18 | Metrics/runner/raw runs | Hand formulas, paired IDs, frozen hashes |
| Day 19 | Fresh reproduction | Independent representative rerun |
| Day 20 | Portability/engineering report | Verify empirical claims use audited evidence |

B không approve PR nếu typed status, test evidence hoặc interface handoff thiếu.

---

## 4. Daily handoff checklist

Cuối mỗi ngày B cập nhật Issue:

```markdown
## B daily handoff
- Completed task/step IDs:
- Files/commits:
- Tests run and counts:
- Contract/schema/hash delivered:
- Input needed from A tomorrow:
- Interface/decision question:
- Blocker:
```

Joint handoff chỉ hoàn tất khi A acknowledge trong Issue hoặc PR.

---

## 5. Final checklist cho Thành viên B

- [ ] Shared contracts stable và strict-type clean.
- [ ] Positive STRIPS/serializer/pyperplan tests pass.
- [ ] B3 planner integration 20/20 smoke.
- [ ] Parser suite 40/40.
- [ ] Belief unknown/staleness/conflict semantics pass.
- [ ] Validator/commitment clean and conflict tests pass.
- [ ] V0R0/V1R0 switch semantics verified.
- [ ] Monitor/replanning bounded.
- [ ] N1 deterministic/no hidden-label leak.
- [ ] Trace completeness/replay infrastructure pass.
- [ ] Leakage audit and paired bootstrap complete.
- [ ] RQ tables/claims match raw results.
- [ ] Habitat empirical gates and final decision validated.
- [ ] All B commits and PRs reviewed by A.
