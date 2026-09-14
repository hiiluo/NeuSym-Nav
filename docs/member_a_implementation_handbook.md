# Thành viên A — Environment, Control và Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) hoặc `superpowers:executing-plans` để thực hiện tuần tự. Mọi bước dùng checkbox để theo dõi.

**Goal:** Triển khai toàn bộ lane Environment–Control–Evaluation của causal Neuro-Symbolic VLN 2D PoC trong 20 working days, với test-first evidence, commits nhỏ và handoff rõ cho Thành viên B.

**Architecture:** A sở hữu simulator boundary, core tasks, local observation, primitive execution, exploration, evaluator oracle, manifests, N2 interventions, metrics và experiment runs. A không triển khai parser, BeliefMap, validator, PDDL planner hoặc N1 corruption; các module đó được nhận qua contracts/handoffs từ B.

**Tech Stack:** Python 3.12, `uv`, MiniGrid 3.1.0, NumPy, PyYAML, pytest, Ruff, mypy, GitHub Actions.

**Spec:** `docs/neuro_symbolic_vln_2d_complete_implementation_plan.md`  
**Companion plan:** `docs/member_b_implementation_handbook.md`

## Global Constraints

- Không dùng global MiniGrid state trong normal agent path.
- Chỉ `evaluation/oracle.py`, task generation, verifier và native semantics tests được đọc privileged state.
- `Actions.done` không phải task success.
- `pickup`/`toggle` tác động front cell; GoTo success là adjacent + facing.
- Core tasks chỉ gồm `goto_type_color` và `key_door_goal`.
- Agent-visible sensor là local categorical observation, heading, carrying state và declared actuator feedback.
- `LocationId`, `HeadingId`, `EntityId` là opaque core identifiers.
- Không thay đổi shared contract sau Day 5 nếu chưa có joint approval.
- Mỗi task phải chứng minh red→green test cycle, targeted tests và reviewer rerun.
- Không commit `.claude/`, credentials, `.env`, `runs/` hoặc raw artifacts.
- Branch của A dùng prefix `feat/a-`, `test/a-`, `exp/a-` hoặc `docs/a-`.

---

## 1. Lịch riêng của Thành viên A

| Ngày | Task/step của A | Output A phải hoàn thành trong ngày | Handoff cần nhận từ B | Joint checkpoint |
|---|---|---|---|---|
| Day 1 | `A-01.S1–S8` | Secure scaffold, dependencies, package/CLI skeleton | Shared type-name draft, CI/static config | G0 security/dependency decision |
| Day 2 | `A-02.S1–S3` | Failing native tests và deterministic probe environments | PDDL-required semantics checklist | Chốt front-cell/orientation semantics |
| Day 3 | `A-02.S4–S8` | Adapter, core tasks, verifier và env test suite | Symbolic precondition/effect review | Native mapping freeze |
| Day 4 | `A-J01.S1–S4` | Primitive controller, oracle-state execution và 2+2 integration traces | Typed sample plans + SymbolicAction schema | Compare predicted/native effects |
| Day 5 | `A-J01.S5` | Run/fix 20 B3 smoke episodes và archive traces | Planner validity/problem hashes | G1 + interface freeze |
| Day 6 | `A-03.S1–S4` | Four-heading transform và visible-cell decoder | Evidence/Provenance contract | Decoder fixture review |
| Day 7 | `A-03.S5–S8` | Dead reckoning, carrying và action feedback | Belief input requirements | Observation boundary freeze |
| Day 8 | `A-04.S1–S4` | Exact BFS oracle và hand-built optimum tests | Sidecar isolation requirements | Oracle state-space review |
| Day 9 | `A-04.S5–S7` | Public/private manifests, hashes và smoke/dev generation | Agent/serializer private-field audit | Manifest boundary freeze |
| Day 10 | `A-J02` | Local adapter/decoder/controller integration và V0R0/V1R0 runtime traces | Parser/belief/validator/planner modules | G2 trace + leakage review |
| Day 11 | `A-05.S1–S4` | Frontier extraction, tie-break và route selection | TaskMonitor decision contract | Explorer interface review |
| Day 12 | `A-05.S5–S7` | Heading sweep, visit memory và unseen-target integration | Exhaustion/plan-status transitions | Explorer contract freeze |
| Day 13 | `A-06.S1–S3` | Navigation block intervention + recoverability tests | Initial plan/checkpoint schema | N2 navigation review |
| Day 14 | `A-06.S4–S6` | Door re-lock intervention, sidecars và RQ2 manifests | Trace/replanning event schema | RQ2 protocol freeze |
| Day 15 | `A-J03` | Full V1R1 env/control/frontier/N2 diagnostics | N1, belief/replan/trace integration | G3 root-cause review |
| Day 16 | `A-07.S1–S5` | Metric tests/functions, runner và config/hash freeze | Formula/pairing validation | G4 pre-freeze |
| Day 17 | `A-07.S6` | B3 + RQ1 final runs và infrastructure failure log | Audit monitor + rerun approval | RQ1 raw-row review |
| Day 18 | `A-07.S7` | RQ2 + V1R1 clean runs, row/hash validation | CI/replay/bootstrap summaries | G4 final matrix reconciliation |
| Day 19 | `A-J04` + `A-J05.S1–S2` | Fresh reproduction, fake adapter và portability scan | README corrections + RQ gate draft | Reproduction/portability sign-off |
| Day 20 | `A-J05.S3–S7` | Engineering report, gate evidence và final artifact audit | RQ interpretation/claims/threats | G5 typed Habitat decision |

---

## 2. Shared interfaces A phải nhận từ B

Day 1 B phải cung cấp một compiling `contracts.py` với tối thiểu các signatures sau. A không tự đổi tên fields.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

LocationId = str
HeadingId = str
EntityId = str


@dataclass(frozen=True)
class GroundAtom:
    predicate: str
    arguments: tuple[str, ...]


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


@dataclass(frozen=True)
class BeliefRecord:
    value: TriValue
    reliability: float | None
    last_observed_step: int | None
    stale: bool
    evidence_ids: tuple[str, ...]
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
    provenance_by_fact: Mapping[GroundAtom, tuple[str, ...]]
    location_graph: LocationGraph


@dataclass(frozen=True)
class SymbolicAction:
    name: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class PlanResult:
    status: str
    actions: tuple[SymbolicAction, ...]
    planning_time_ms: float
    state_hash: str
    problem_hash: str | None
    reason: str | None
```

Các type `BeliefRecord`, `CommittedPlanningState` và `PlanResult` là consumed interfaces để A viết explorer/controller/integration tests; A không implement symbolic semantics của chúng.

Nếu contract chưa merge, A được phép dùng approved stub với đúng signatures trên; không tạo alternate local types.

---

## Task A-01: Secure fresh scaffold

**Lịch:** Day 1, 2 giờ implementation + 0,5 giờ validation  
**Branch:** `chore/secure-scaffold`  
**Reviewer:** Thành viên B

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `src/neuro_symbolic_vln/__init__.py`
- Create: `src/neuro_symbolic_vln/cli.py`
- Create: `tests/test_package.py`
- Generate: `uv.lock`

**Interfaces:**
- Consumes: dependency/version decisions từ master plan.
- Produces: installable package và `ns-vln` CLI skeleton cho mọi task sau.

### Handoff từ B

- B gửi draft tool config cho Ruff/mypy/pytest và CI command list.
- A xác nhận package paths/entry point trước khi B viết CI.

### Step-by-step

- [ ] **Step 1: Viết failing package test**

```python
# tests/test_package.py
from neuro_symbolic_vln import __version__
from neuro_symbolic_vln.cli import build_parser


def test_package_version_and_cli_parser() -> None:
    assert __version__ == "0.1.0"
    parser = build_parser()
    assert parser.prog == "ns-vln"
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run:

```bash
uv run pytest tests/test_package.py -v
```

Expected: FAIL với `ModuleNotFoundError` hoặc missing `__version__`/`build_parser`.

- [ ] **Step 3: Tạo package implementation tối thiểu**

```python
# src/neuro_symbolic_vln/__init__.py
__version__ = "0.1.0"
```

```python
# src/neuro_symbolic_vln/cli.py
from argparse import ArgumentParser


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="ns-vln")
    parser.add_argument("--version", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    parser.parse_args()
    return 0
```

- [ ] **Step 4: Tạo dependency metadata**

`pyproject.toml` phải pin:

```toml
[project]
name = "neuro-symbolic-vln"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "minigrid==3.1.0",
  "numpy>=1.26,<3",
  "pyperplan==2.1",
  "pyyaml>=6,<7",
]

[project.scripts]
ns-vln = "neuro_symbolic_vln.cli:main"
```

- [ ] **Step 5: Tạo `.gitignore` và xác nhận secret paths**

Tối thiểu ignore `.claude/`, `.env*` ngoại trừ `.env.example`, `.venv/`, caches, `runs/`, `artifacts/` và logs.

- [ ] **Step 6: Sync và chạy targeted test**

```bash
uv sync --all-groups
uv run pytest tests/test_package.py -v
```

Expected: PASS 1 test.

- [ ] **Step 7: Chạy static checks do B định nghĩa**

```bash
uv run ruff check .
uv run mypy src
```

Expected: exit 0.

- [ ] **Step 8: Commit A**

```bash
git add .gitignore .env.example pyproject.toml uv.lock src/neuro_symbolic_vln tests/test_package.py
git commit -m "chore: create secure Python project scaffold"
```

### Test cases bổ sung

| ID | Validation | Expected |
|---|---|---|
| `A01-TC01` | `git check-ignore .claude/settings.local.json` | Exit 0 |
| `A01-TC02` | `uv run python -c "import neuro_symbolic_vln"` | Exit 0 |
| `A01-TC03` | `uv run ns-vln --help` | CLI help, exit 0 |
| `A01-TC04` | Secret scan trên tracked files | No findings |

### Joint checkpoint

A và B chốt dependency versions, CI commands và confirm credential rotation trong Issue. B review không cần empty commit; nếu B sửa config, B dùng `ci: add static and secret checks`.

### Definition of Done

- Targeted test, Ruff và mypy PASS.
- Secret path ignored và owner xác nhận credential rotation.
- PR approved bởi B.

---

## Task A-02: MiniGrid adapter, core tasks và TaskVerifier

**Lịch:** Day 2–3, 8 team-hours  
**Branch:** `feat/a-minigrid-adapter`  
**Reviewer:** Thành viên B

**Files:**
- Create: `src/neuro_symbolic_vln/env/base.py`
- Create: `src/neuro_symbolic_vln/env/minigrid_adapter.py`
- Create: `src/neuro_symbolic_vln/env/tasks.py`
- Create: `src/neuro_symbolic_vln/env/verifier.py`
- Create: `tests/env/test_native_semantics.py`
- Create: `tests/env/test_task_verifier.py`
- Create: `tests/env/test_adapter_contract.py`

**Interfaces:**
- Consumes: `EpisodeSpec`, `ObservationPacket`, `PrimitiveAction`, `StepResult`.
- Produces: `MiniGridAdapter.reset/step`, task factories, `TaskVerifier.evaluate`.

### Handoff từ B

B gửi danh sách symbolic preconditions/effects cần được native tests chứng minh: orientation, front cell, holding, door state, passability và task confirmation.

### Step-by-step

- [ ] **Step 1: Viết failing front-cell test**

```python
# tests/env/test_native_semantics.py
from minigrid.core.actions import Actions

from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env


def test_pickup_targets_front_cell() -> None:
    env = make_locked_door_probe_env()
    env.reset(seed=0)
    assert env.unwrapped.carrying is None

    env.step(Actions.pickup)

    assert env.unwrapped.carrying is not None
    assert env.unwrapped.carrying.type == "key"
```

Run:

```bash
uv run pytest tests/env/test_native_semantics.py::test_pickup_targets_front_cell -v
```

Expected: FAIL vì task factory chưa tồn tại.

- [ ] **Step 2: Implement deterministic probe environment**

```python
# src/neuro_symbolic_vln/env/tasks.py
from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Door, Key
from minigrid.minigrid_env import MiniGridEnv


class LockedDoorProbeEnv(MiniGridEnv):
    def __init__(self) -> None:
        super().__init__(
            mission_space=MissionSpace(mission_func=lambda: "probe"),
            width=6,
            height=5,
            max_steps=32,
        )

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.agent_pos = (1, 1)
        self.agent_dir = 0
        self.put_obj(Key("red"), 2, 1)
        self.put_obj(Door("red", is_locked=True), 3, 1)
        self.mission = "probe"


def make_locked_door_probe_env() -> LockedDoorProbeEnv:
    return LockedDoorProbeEnv()
```

- [ ] **Step 3: Chạy test và bổ sung toggle/blocked/done tests**

Expected targeted tests PASS.

- [ ] **Step 4: Viết failing verifier test**

```python
# tests/env/test_task_verifier.py
from neuro_symbolic_vln.env.verifier import GoToVerifier


def test_goto_requires_adjacent_and_facing() -> None:
    verifier = GoToVerifier(target_position=(2, 1))
    assert not verifier.is_satisfied(agent_position=(1, 1), agent_direction=1)
    assert verifier.is_satisfied(agent_position=(1, 1), agent_direction=0)
```

Expected initial FAIL vì verifier chưa tồn tại.

- [ ] **Step 5: Implement explicit verifier**

```python
# src/neuro_symbolic_vln/env/verifier.py
from dataclasses import dataclass

_DIRECTION_TO_DELTA = {
    0: (1, 0),
    1: (0, 1),
    2: (-1, 0),
    3: (0, -1),
}


@dataclass(frozen=True)
class GoToVerifier:
    target_position: tuple[int, int]

    def is_satisfied(
        self,
        agent_position: tuple[int, int],
        agent_direction: int,
    ) -> bool:
        dx, dy = _DIRECTION_TO_DELTA[agent_direction]
        return (
            agent_position[0] + dx,
            agent_position[1] + dy,
        ) == self.target_position
```

- [ ] **Step 6: Implement adapter public boundary**

`MiniGridAdapter.step` phải trả `StepResult` và tự tính `action_succeeded` bằng allowed before/after actuator state; không expose full grid.

- [ ] **Step 7: Chạy toàn bộ env tests**

```bash
uv run pytest tests/env -v
```

Expected: tất cả PASS.

- [ ] **Step 8: Commit theo scope**

```bash
git add tests/env/test_native_semantics.py src/neuro_symbolic_vln/env/tasks.py
git commit -m "test(env): lock MiniGrid native semantics"

git add src/neuro_symbolic_vln/env tests/env
git commit -m "feat(env): add core tasks adapter and explicit verifier"
```

### Test matrix

- front-cell pickup;
- pickup khi front cell empty;
- matching key opens locked door;
- wrong key không mở door;
- blocked forward giữ position;
- `Actions.done` không tạo success;
- GoTo adjacent but wrong facing false;
- GoTo adjacent+facing true;
- ordered key-door-goal success;
- adapter public fields không có global map/object coordinates.

### Handoff cho B

A giao:

```text
- Native action fixtures
- Task verifier conditions
- Symbolic↔primitive mapping table
- Adapter public contract tests
```

B phải rerun `uv run pytest tests/env -v` và dùng fixtures cho planner tests.

### Suggested commits

- A: `test(env): lock MiniGrid native semantics`
- A: `feat(env): add core tasks adapter and explicit verifier`
- B validation: `test(planning): validate native action preconditions` nếu B thêm test.
- Joint: `docs: freeze MiniGrid symbolic action mapping`.

### Definition of Done

10 semantic/contract cases PASS; B approve mapping; no privileged field trong adapter output.

---

## Task A-J01: Primitive controller và B3 vertical slice

**Lịch:** Day 4–5  
**Branch:** `feat/a-b3-controller`  
**Joint driver:** A cho execution, B cho planning

**Files:**
- Create: `src/neuro_symbolic_vln/control/controller.py`
- Modify: `src/neuro_symbolic_vln/agent.py`
- Create: `tests/control/test_controller.py`
- Create: `tests/test_end_to_end_smoke.py`

**Interfaces:**
- Consumes: B `SymbolicAction`, `PlanResult`, pyperplan adapter.
- Produces: primitive actions, execution trace, B3 smoke artifact.

### Step-by-step A

- [ ] Viết failing mapping test:

```python
from neuro_symbolic_vln.contracts import SymbolicAction
from neuro_symbolic_vln.control.controller import MiniGridController


def test_controller_maps_turn_left() -> None:
    controller = MiniGridController()
    assert controller.to_primitive(SymbolicAction("turn-left", ())) == "turn_left"
```

- [ ] Run expected FAIL:

```bash
uv run pytest tests/control/test_controller.py::test_controller_maps_turn_left -v
```

- [ ] Implement explicit mapping:

```python
class MiniGridController:
    _ACTION_MAP = {
        "turn-left": "turn_left",
        "turn-right": "turn_right",
        "move-forward": "move_forward",
        "pickup-key": "pickup",
        "toggle-locked-door": "toggle",
    }

    def to_primitive(self, action: SymbolicAction) -> str:
        try:
            return self._ACTION_MAP[action.name]
        except KeyError as error:
            raise ValueError(f"unsupported symbolic action: {action.name}") from error
```

- [ ] Add confirmation action handling: `confirm-goto` gọi verifier, không emit primitive action.
- [ ] Integrate B3 oracle state provider.
- [ ] Run 2+2 integration episodes trước full smoke.

### Joint integration protocol

B cung cấp plan output và problem hash. A cung cấp execution/result trace. Cả hai compare predicted symbolic effects với native outcomes.

### Validation

```bash
uv run pytest tests/control/test_controller.py -v
uv run pytest tests/test_end_to_end_smoke.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method B3
```

Expected:

- 20/20 B3 smoke success;
- believed-state plan validity 100%;
- no primitive `done`;
- no untyped failure.

### Commits

- A: `feat(control): map symbolic plans to MiniGrid primitives`
- A: `feat(evaluation): add B3 oracle-state execution path`
- B: `feat(planning): expose typed B3 plans and problem hashes`
- Joint: `feat(agent): complete oracle-input planning vertical slice`
- Joint: `docs: freeze runtime interfaces after G1`

### Definition of Done

G1 signed off và contracts frozen.

---

## Task A-03: Local categorical decoder và dead reckoning

**Lịch:** Day 6–7  
**Branch:** `feat/a-local-observation`  
**Reviewer:** B

**Files:**
- Create: `src/neuro_symbolic_vln/perception/observation_decoder.py`
- Modify: `src/neuro_symbolic_vln/env/minigrid_adapter.py`
- Modify: `src/neuro_symbolic_vln/control/controller.py`
- Create: `tests/perception/test_observation_decoder.py`
- Create: `tests/control/test_dead_reckoning.py`

**Interfaces:**
- Consumes: B `Evidence`, `Provenance`, `GroundAtom`.
- Produces: local evidence and internal pose updates.

### Step-by-step

- [ ] Viết failing coordinate transform test:

```python
from neuro_symbolic_vln.perception.observation_decoder import rotate_local_delta


def test_rotate_local_delta_east() -> None:
    assert rotate_local_delta(dx=0, dy=-1, heading="east") == (1, 0)
```

- [ ] Run expected FAIL.
- [ ] Implement transform:

```python
def rotate_local_delta(dx: int, dy: int, heading: str) -> tuple[int, int]:
    transforms = {
        "north": (dx, dy),
        "east": (-dy, dx),
        "south": (-dx, -dy),
        "west": (dy, -dx),
    }
    try:
        return transforms[heading]
    except KeyError as error:
        raise ValueError(f"unsupported heading: {heading}") from error
```

- [ ] Add visibility guard: invisible cells emit no occupancy evidence.
- [ ] Add object/color/door evidence mapping.
- [ ] Write failing blocked-motion test.
- [ ] Implement internal pose update only when `action_succeeded=True`.
- [ ] Map carrying state and action failure reasons.
- [ ] Run targeted and integration tests.

### Validation commands

```bash
uv run pytest tests/perception/test_observation_decoder.py -v
uv run pytest tests/control/test_dead_reckoning.py -v
uv run pytest tests/env/test_adapter_contract.py -v
```

### Expected cases

- four-heading transforms;
- unseen cell emits no free/negative fact;
- successful move advances pose once;
- blocked move leaves pose unchanged;
- carrying/pickup/toggle feedback maps correctly;
- decoder import/access scan contains no global state.

### Handoff cho B

A giao deterministic Evidence fixtures cho:

```text
visible object
visible empty cell
blocked move
successful pickup
door state change
unseen cell
```

B dùng fixtures trong BeliefMap tests.

### Commits

- A: `feat(perception): decode local categorical observations`
- A: `feat(control): add local pose and actuator feedback`
- B validation: `test(belief): consume local evidence fixtures`
- Joint: `docs: freeze observation and evidence boundary`

### Definition of Done

All local-only tests PASS; B approve Evidence compatibility; no `agent_pos`/full-grid access trong normal decoder.

---

## Task A-04: Exact evaluator oracle và immutable manifests

**Lịch:** Day 8–9  
**Branch:** `feat/a-evaluation-oracle`  
**Reviewer:** B

**Files:**
- Create: `src/neuro_symbolic_vln/evaluation/oracle.py`
- Create: `src/neuro_symbolic_vln/evaluation/manifests.py`
- Create: `tests/evaluation/test_oracle.py`
- Create: `tests/evaluation/test_manifests.py`
- Create: `configs/manifests.yaml`

**Interfaces:**
- Consumes: core env/task state.
- Produces: `OracleSolution`, public manifests, private sidecars.

### Step-by-step

- [ ] Write failing exact-cost test:

```python
from neuro_symbolic_vln.evaluation.oracle import shortest_primitive_cost


def test_shortest_primitive_cost_counts_turn_and_forward() -> None:
    cost = shortest_primitive_cost(
        start=(1, 1, "north"),
        goal=(2, 1, "east"),
        passable={(1, 1), (2, 1)},
    )
    assert cost == 2
```

- [ ] Run expected FAIL.
- [ ] Implement BFS over `(location, heading, carrying, door_state)` for core tasks.
- [ ] Add task-specific success predicate.
- [ ] Add canonical layout serialization/hash.
- [ ] Split public manifest/private sidecar dataclasses.
- [ ] Reject duplicate/cross-split layouts.
- [ ] Generate smoke/dev manifests twice and compare hashes.

Minimal hash implementation:

```python
import hashlib
import json


def stable_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
```

### Validation commands

```bash
uv run pytest tests/evaluation/test_oracle.py -v
uv run pytest tests/evaluation/test_manifests.py -v
uv run pytest tests/test_no_oracle_leakage.py -v
uv run ns-vln generate-manifests --config configs/manifests.yaml
```

### Required cases

- hand-built GoTo exact grid/primitive cost;
- hand-built key-door exact primitive cost;
- unsolvable episode false;
- deterministic manifest hash;
- duplicate/cross-split rejection;
- no sidecar fields in EpisodeSpec;
- normal agent import graph excludes oracle.

### Handoff cho B

A giao public manifest schema, sidecar schema và hashes. B chạy no-leakage tests và xác nhận serializer/agent không nhận private fields.

### Commits

- A: `feat(evaluation): add exact task oracle`
- A: `feat(evaluation): generate immutable episode manifests`
- B validation: `test(security): isolate evaluator sidecars from agent input`
- Joint: `docs: freeze manifest and oracle boundary`

### Definition of Done

All generated core episodes solvable; hashes reproducible; B approve sidecar isolation.

---

## Task A-J02: Clean local V0R0/V1R0 integration

**Lịch:** Day 10  
**Branch:** `feat/a-local-integration`  
**Joint driver:** A cho runtime, B cho symbolic pipeline

### A responsibilities

- Wire adapter/decoder/controller/oracle evaluator.
- Run local clean smoke and inspect environment/control failures.
- Verify initially unseen targets require frontier/information status rather than oracle location.

### B must provide

- Parser, BeliefMap, validator, serializer, V0R0/V1R0 switches và planner.

### Validation

```bash
uv run pytest tests/test_no_oracle_leakage.py -v
uv run pytest tests/test_end_to_end_smoke.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method V0R0
uv run ns-vln evaluate --config configs/smoke.yaml --method V1R0
```

Expected:

- clean visible evidence precision/recall 100%;
- unknown required route produces information/exploration decision;
- no oracle import/private field;
- every run typed and traced.

### Commits

- A: `feat(agent): integrate local environment and controller path`
- B: `feat(agent): integrate parser belief validation and planning path`
- Joint: `test(agent): validate clean local pipelines and oracle isolation`

### Definition of Done

G2 signed off; joint trace review per family/method complete.

---

## Task A-05: Deterministic frontier explorer

**Lịch:** Day 11–12  
**Branch:** `feat/a-frontier-explorer`  
**Reviewer:** B

**Files:**
- Create: `src/neuro_symbolic_vln/control/explorer.py`
- Create: `tests/control/test_explorer.py`
- Create: `tests/control/test_explorer_contract.py`

**Interfaces:**
- Consumes: `LocationGraph`, current pose, visited frontiers.
- Produces: frontier target hoặc typed exhaustion.

### Step-by-step

- [ ] Write failing tie-break test:

```python
from neuro_symbolic_vln.control.explorer import FrontierCandidate, select_frontier


def test_select_frontier_prefers_shorter_plan() -> None:
    candidates = (
        FrontierCandidate("loc-b", plan_length=4, discovered_step=1),
        FrontierCandidate("loc-a", plan_length=2, discovered_step=9),
    )
    assert select_frontier(candidates).location_id == "loc-a"
```

- [ ] Implement immutable candidate and deterministic sort:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class FrontierCandidate:
    location_id: str
    plan_length: int
    discovered_step: int


def select_frontier(candidates: tuple[FrontierCandidate, ...]) -> FrontierCandidate:
    if not candidates:
        raise ValueError("frontier set is empty")
    return min(
        candidates,
        key=lambda item: (item.plan_length, item.discovered_step, item.location_id),
    )
```

- [ ] Add frontier extraction from known traversable nodes adjacent to unknown.
- [ ] Add one-sweep-per-visit memory.
- [ ] Add typed `FRONTIER_EXHAUSTED` response through TaskMonitor contract.
- [ ] Run initially unseen target integration case.

### Validation commands

```bash
uv run pytest tests/control/test_explorer.py -v
uv run pytest tests/control/test_explorer_contract.py -v
```

### Cross-validation by B

B verifies TaskMonitor transitions and proves explorer has no oracle distance/target-position input.

### Commits

- A: `feat(control): add deterministic frontier exploration`
- B validation: `test(control): enforce task-monitor explorer boundary`
- Joint: `docs: freeze frontier selection and sweep policy`

### Definition of Done

Tie-break deterministic, no repeated sweep, unseen target discovered và typed exhaustion works.

---

## Task A-06: N2 fixed interventions

**Lịch:** Day 13–14  
**Branch:** `exp/a-rq2-interventions`  
**Reviewer:** B

**Files:**
- Create: `src/neuro_symbolic_vln/evaluation/interventions.py`
- Create: `tests/evaluation/test_interventions.py`
- Generate: `data/manifests/rq2_test.jsonl` và private sidecars.

**Interfaces:**
- Consumes: initial plan hash, environment state, oracle solver.
- Produces: fixed checkpoints và recoverability annotations.

### Step-by-step

- [ ] Write failing navigation intervention test:

```python
from neuro_symbolic_vln.evaluation.interventions import choose_block_intervention


def test_block_intervention_requires_alternate_route() -> None:
    intervention = choose_block_intervention(
        planned_next=(2, 1),
        alternate_route=((1, 2), (2, 2), (3, 2)),
    )
    assert intervention.target == (2, 1)
    assert intervention.recoverable
```

- [ ] Implement immutable intervention spec and eligibility checks.
- [ ] Add exact oracle post-state solvability test.
- [ ] Add door re-lock intervention after successful toggle/before crossing.
- [ ] Store pre/post optimum only in sidecar.
- [ ] Validate identical prefix/checkpoint giữa V1R0/V1R1.
- [ ] Generate 40/family intervention manifests.

### Validation commands

```bash
uv run pytest tests/evaluation/test_interventions.py -v
uv run pytest tests/test_no_oracle_leakage.py -v
uv run ns-vln generate-manifests --config configs/rq2_test.yaml
```

### Required expected results

- alternate-route case accepted;
- unsolvable block rejected;
- re-lock with carried key recoverable;
- same seed produces same intervention hash;
- public input excludes target/effect/optimum labels.

### Handoff cho B

A giao checkpoint schema và event fixtures. B uses them in execution monitor/replanning/trace tests.

### Commits

- A: `feat(evaluation): add fixed recoverable RQ2 interventions`
- B validation: `test(evaluation): validate paired checkpoints and sidecar isolation`
- Joint: `docs: freeze RQ2 intervention protocol`

### Definition of Done

80 paired interventions oracle-confirmed recoverable, deterministic và no sidecar leak.

---

## Task A-J03: Full V1R1 diagnostic integration

**Lịch:** Day 15  
**Branch:** `feat/a-closed-loop-integration`

### A responsibilities

- Run env/controller/frontier/N2 diagnostics.
- Fix only root-caused adapter/control issues.
- Confirm public action/replan bounds.

### B responsibilities

- Integrate N1, BeliefMap, validator, monitor, replanner và trace.
- Fix symbolic issues and typed outcomes.

### Validation matrix

```bash
uv run pytest tests/test_end_to_end_smoke.py tests/control/test_replanning.py -v
uv run ns-vln evaluate --config configs/smoke.yaml --method V1R1
uv run ns-vln evaluate --config configs/diagnostic.yaml --method V1R1
uv run ns-vln validate-traces --runs runs/diagnostic
```

Expected: unseen target, N1, N2 blocked route, re-locked door, timeout và deliberate loop đều success hoặc đúng typed terminal status; no unbounded run.

### Commits

- A: `fix(agent): resolve environment frontier and controller integration failures`
- B: `fix(agent): resolve belief planning and recovery integration failures`
- Joint: `feat(agent): complete bounded neuro-symbolic closed loop`

### Definition of Done

G3 signed off và every diagnostic trace schema-valid/replayable.

---

## Task A-07: Metrics, experiment runner và frozen runs

**Lịch:** Day 16–18  
**Branch:** `exp/a-final-evaluation`  
**Reviewer:** B

**Files:**
- Create: `src/neuro_symbolic_vln/evaluation/metrics.py`
- Create: `src/neuro_symbolic_vln/evaluation/runner.py`
- Create: `tests/evaluation/test_metrics.py`
- Create: final configs/result artifacts.

### Step-by-step

- [ ] Write failing SPL test:

```python
from neuro_symbolic_vln.evaluation.metrics import grid_spl


def test_grid_spl_success() -> None:
    assert grid_spl(success=True, optimal_distance=4, executed_distance=8) == 0.5
```

- [ ] Write failing SOPE test:

```python
from neuro_symbolic_vln.evaluation.metrics import sope


def test_sope_counts_primitive_actions() -> None:
    assert sope(success=True, optimal_actions=5, attempted_actions=10) == 0.5
```

- [ ] Implement exact functions:

```python
def grid_spl(success: bool, optimal_distance: int, executed_distance: int) -> float:
    if not success:
        return 0.0
    return optimal_distance / max(optimal_distance, executed_distance)


def sope(success: bool, optimal_actions: int, attempted_actions: int) -> float:
    if not success:
        return 0.0
    return optimal_actions / max(optimal_actions, attempted_actions)
```

- [ ] Add SR, invalid-action rate, recovery denominator, plan validity fields.
- [ ] Add runner with frozen config/manifest hash checks.
- [ ] Day 16 joint freeze configs and expected row matrix.
- [ ] Day 17 run B3 + RQ1.
- [ ] Day 18 run RQ2 + V1R1 clean.
- [ ] Validate ~1.120 expected rows and document infrastructure-only reruns.

### Validation commands

```bash
uv run pytest tests/evaluation/test_metrics.py -v
uv run ns-vln evaluate --config configs/rq1_test.yaml
uv run ns-vln evaluate --config configs/rq2_test.yaml
uv run ns-vln evaluate --config configs/v1r1_clean.yaml
uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml
```

### Cross-validation by B

B verifies hand calculations, paired IDs, hashes, trace availability and no retuning.

### Commits

- A: `feat(evaluation): implement navigation recovery and plan metrics`
- A: `feat(evaluation): add frozen experiment runner`
- A: `exp: run frozen RQ1 RQ2 and clean matrices`
- B validation: `test(evaluation): verify metric denominators and paired units`
- Joint: `chore(experiment): freeze final manifests configs and schema`

### Definition of Done

Expected rows complete, hashes frozen, reruns documented, B approves denominators/pairing.

---

## Task A-J04: Fresh-checkout reproduction

**Lịch:** Day 19  
**Branch:** `test/a-fresh-reproduction`

### A responsibilities

- Clone repository vào clean path.
- Chạy full setup/CI/manifest/smoke commands chỉ theo README.
- Ghi exact commands, versions, hashes và failures.

### B responsibilities

- Observe run, sửa README/config docs trên branch riêng.
- Independently rerun one representative evaluation.

### Validation

```bash
uv sync --all-groups
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run ns-vln generate-manifests --config configs/manifests.yaml
uv run ns-vln evaluate --config configs/smoke.yaml
```

Expected: all exit 0; hashes và result schema khớp frozen artifact; no private `.claude` dependency.

### Commits

- A: `test(repro): record fresh-checkout reproduction evidence`
- B: `docs: correct setup and reproduction instructions`
- Joint: `docs: sign off reproducible month-one artifact`

### Definition of Done

Reproduction log linked in G5 Issue và both members approve.

---

## Task A-J05: Fake adapter, Habitat mapping và final engineering report

**Lịch:** Day 19–20  
**Branch:** `docs/a-habitat-technical-mapping`

**Files:**
- Create: `tests/env/test_non_grid_adapter_contract.py`
- Create/modify: `reports/month1/habitat_decision.yaml`
- Modify: final report methods/results sections.

### Step-by-step

- [ ] Write fake adapter contract test with opaque string locations.
- [ ] Implement test-only fake graph adapter without MiniGrid imports.
- [ ] Run portability import/coordinate scan.
- [ ] Fill engineering gates with evidence links.
- [ ] Write environment/control/evaluation methods and results.
- [ ] Resolve report values against raw summaries.
- [ ] Jointly choose `Advance`, `Conditional hold` hoặc `No-go`.

Example fake adapter test:

```python
from neuro_symbolic_vln.contracts import PrimitiveAction
from tests.fakes import FakeGraphAdapter


def test_fake_graph_adapter_satisfies_step_contract() -> None:
    adapter = FakeGraphAdapter()
    observation = adapter.reset()
    result = adapter.step(PrimitiveAction("move_forward"))
    assert observation.heading in {"north", "east", "south", "west"}
    assert isinstance(result.action_succeeded, bool)
```

### Validation commands

```bash
uv run pytest tests/env/test_non_grid_adapter_contract.py -v
uv run ns-vln audit-portability --src src/neuro_symbolic_vln
uv run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml
uv run ns-vln validate-report --report reports/month1/
```

### Handoff từ/cho B

- A giao portability audit và engineering gate evidence.
- B giao RQ1/RQ2 gate interpretation, claims/non-claims và threats.
- Joint decision phải link exact evidence.

### Commits

- A: `test(portability): add fake non-grid adapter conformance`
- A: `docs: add environment control and evaluation results`
- B: `docs: add RQ statistics and validity analysis`
- Joint: `docs: record Habitat migration go-no-go decision`
- Joint: `docs: finalize month-one neuro-symbolic VLN artifact`

### Definition of Done

G5 complete; final report reproducible, evidence-linked và không claim Habitat/RGB performance.

---

## 3. Cross-validation duties của A đối với B-owned tasks

| Ngày | B artifact A phải validate | A validation command/evidence |
|---|---|---|
| Day 2–3 | PDDL domain/serializer/planner | `uv run pytest tests/planning/test_native_action_mapping.py -v` |
| Day 6 | Parser GoalProgram | Run parser→task-spec integration tests |
| Day 7–8 | EvidenceStore/BeliefMap | Run action-feedback fixtures against belief tests |
| Day 9 | Validator/committed state | Run clean environment facts + conflict fixtures |
| Day 11–12 | Monitor/replanner | Run blocked move/re-locked door end-to-end tests |
| Day 13 | N1 corruption | Check visibility eligibility/no hidden-world injection |
| Day 14 | Trace/replay | Check env/action/verifier fields and private-data exclusion |
| Day 16–18 | Bootstrap/audit summaries | Spot-check raw episode rows against summary values |
| Day 20 | RQ claims/report | Confirm engineering evidence is represented accurately |

A không approve PR nếu validation evidence thiếu hoặc expected results không rõ.

---

## 4. Daily handoff checklist

Cuối mỗi ngày A cập nhật Issue:

```markdown
## A daily handoff
- Completed task/step IDs:
- Files/commits:
- Tests run and counts:
- Artifact/hash:
- Input needed from B tomorrow:
- Interface/decision question:
- Blocker:
```

Joint handoff chỉ hoàn tất khi B acknowledge trong Issue hoặc PR.

---

## 5. Final checklist cho Thành viên A

- [ ] G0 secure scaffold evidence complete.
- [ ] Native semantics and verifier tests complete.
- [ ] B3 smoke 20/20.
- [ ] Local decoder/pose/feedback local-only.
- [ ] Oracle/manifests deterministic and isolated.
- [ ] Frontier deterministic and bounded.
- [ ] N2 interventions paired and recoverable.
- [ ] Metrics validated against hand calculations.
- [ ] Final row matrix complete.
- [ ] Fresh reproduction pass.
- [ ] Fake adapter/portability audit pass.
- [ ] Engineering sections of final report evidence-linked.
- [ ] All A commits and PRs reviewed by B.
