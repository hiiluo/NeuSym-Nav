# Task A-J04 / B-J04: Fresh Reproduction, Research Closure & Habitat Decision — Hướng dẫn phối hợp chi tiết

> **Day 19–20 — Phase 2 — Handoff H12 — Gates G4 và G5**
> Kết quả: một frozen candidate được tái lập từ checkout sạch, kết quả RQ được kiểm toán và diễn giải trung thực, báo cáo/final decision liên kết bằng chứng, và artifact chỉ được đóng sau CI cuối.

---

## 1. Tổng quan task

| Thuộc tính | Giá trị |
|---|---|
| **Task ID** | `A-J04` (Member A) / `B-J04` (Member B) |
| **Lịch** | A-J04: Day 19; B-J04: Day 19–20 |
| **Phase** | Phase 2; không phải phần mở rộng của Phase 1 |
| **Handoff** | `H12` — A giao reproduction/portability evidence, B giao RQ/gate analysis/report |
| **Gate** | `G4` (final frozen evaluation) rồi `G5` (reproduction + typed Habitat decision) |
| **Driver** | A vận hành reproduction và evidence kỹ thuật; B vận hành docs, independent rerun, RQ/gate analysis |
| **Branch A** | `test/a-fresh-reproduction` |
| **Branch B** | `docs/b-final-analysis` |
| **Phụ thuộc gần kề** | `A-J05` thực hiện fake-adapter/portability và phần engineering report; B-J04 không được kết luận Habitat khi evidence A-J05 chưa có |

### Nguồn chuẩn được hợp nhất

- [Handbook A — A-J04/A-J05](member_a_implementation_handbook.md#task-a-j04-fresh-checkout-reproduction): operator reproduction, portability và engineering evidence.
- [Handbook B — B-J04](member_b_implementation_handbook.md#task-b-j04-reproduction-docs-rq-interpretation-và-final-habitat-decision): docs correction, independent rerun, RQ/report validation.
- [Master plan — Phase 2](neuro_symbolic_vln_2d_complete_implementation_plan.md#24-phase-2-post-core-integration-evaluation-và-closure), [reproduction contract](neuro_symbolic_vln_2d_complete_implementation_plan.md#173-reproduction-acceptance-contract), [H12](neuro_symbolic_vln_2d_complete_implementation_plan.md#223-mandatory-handoffs) và [Habitat rubric](neuro_symbolic_vln_2d_complete_implementation_plan.md#26-practical-habitat-go-no-go-rubric).

Khi wording trong handbook và master khác nhau, master plan là nguồn ưu tiên; discrepancy phải được sửa trước downstream merge.

### Mục tiêu chính

Đây không phải chỉ là một README review. Hai thành viên phải chứng minh candidate đã đóng băng có thể được một operator tái lập **chỉ bằng tracked repository state**, sau đó đối chiếu raw rows, traces, summaries, CIs, claims, threats và engineering evidence để chọn đúng một quyết định `Advance`, `Conditional hold` hoặc `No-go`.

### Khác với J03

| | J03 (Day 15) | J04 (Day 19–20) |
|---|---|---|
| **Đầu vào** | Các lane runtime/symbolic đang tích hợp | Một `G4-ready` freeze candidate và H01–H11 đã audit |
| **Trọng tâm** | V1R1 closed loop, N1/N2, bound, trace | Fresh clone, final matrix, reports, evidence-to-claim, G5 |
| **Thay đổi được phép** | Root-cause integration fix | Chỉ docs/config/setup fixes trước reproduction; semantic/core fix phải quay lại Phase 1 |
| **Rerun** | Diagnostic matrix | Fresh reproduction sau mỗi docs/setup fix; semantic rerun theo toàn bộ affected cells |
| **Kết quả** | `G3`, H10 | `G4`, H12, `G5`, final SHA/tag/snapshot |

---

## 2. Điều kiện vào Phase 2 — phải PASS trước khi mở A-J04/B-J04

Không bắt đầu work closure chỉ vì Day 19 đã đến. Joint Issue phải link bằng chứng cho **tất cả** điều kiện sau:

- [ ] A-01–A-07, A-J01–A-J03, B-01–B-09 và B-J01–B-J03 đạt DoD.
- [ ] H01–H11 đều có producer artifact, consumer validation, commit/PR link, version và deadline phù hợp.
- [ ] G0–G3 PASS và `G4-ready` PASS trên **cùng một candidate SHA**.
- [ ] Candidate có frozen code SHA, lockfile, public manifests, evaluator sidecars, configs, thresholds, budgets, seeds và result schema; hash/version đã ghi trong freeze record.
- [ ] Candidate row plan, paired-unit plan, expected row count, leakage checks, trace targets, metrics và raw-result hashes đã được A/B đối chiếu ở H11.
- [ ] Mọi contract/schema deviation đã merge + version hoặc rollback; không còn lane-local branch chứa Phase-1 output bắt buộc chưa mở PR.
- [ ] Issues A-J04, A-J05 và B-J04 nêu driver, support, reviewer và merge order.

**Không đạt entry criterion:** Issue ở trạng thái `Blocked`, quay lại đúng Phase-1 task/Issue gây lỗi. Không sửa trực tiếp trong Phase 2 nhằm che một core task, và không coi final checklist/G5 là prerequisite để vào Phase 2.

### Freeze boundary và phân loại phát hiện

| Phát hiện trong Phase 2 | Owner ban đầu | Hành động bắt buộc | Ảnh hưởng gate |
|---|---|---|---|
| README sai, lệnh thiếu, config path/setup metadata sai nhưng không đổi semantics | B sửa qua PR, A re-run | Merge PR rồi clone/checkout sạch lại; không tái dùng `.venv`, cache hay config local | H12 chưa hoàn tất đến khi run mới PASS |
| CI/static/test fail do regression kỹ thuật không đổi contract/semantics | Owner root cause | Fix qua PR, chạy lại affected validation và reproduction | Giữ candidate pending; cập nhật evidence |
| Contract, schema, metric, manifest, threshold, budget, seed, evaluator hoặc core-runtime semantics sai | A/B theo root cause | Invalidate `G4-ready`, version bump, quay lại Phase 1/gate phù hợp; rerun toàn bộ affected cells | Không được promote `G4` hoặc kết luận G5 |
| Missing/duplicate row, hash mismatch, leak, replay failure, untyped outcome hoặc bound violation | A/B theo audit | Không suy diễn từ partial data; ghi typed disposition, sửa/audit/rerun theo scope | `G4`/`G5` blocked nếu unresolved |
| Kết quả RQ không đạt threshold nhưng artifacts hợp lệ | B diễn giải, A xác nhận kỹ thuật | Báo negative/partial result và non-claim; không retune threshold sau khi thấy result | Có thể là `Conditional hold`, không phải tự động test failure |

---

## 3. Trình tự phối hợp và merge order

```mermaid
sequenceDiagram
    participant A as Member A<br/>(Reproduction operator)
    participant GH as GitHub Issue / PRs
    participant B as Member B<br/>(Docs & RQ auditor)

    Note over A,B: Entry: G4-ready PASS on one frozen candidate SHA; H01–H11 audited
    A->>GH: Record candidate SHA, lock/config/manifest/schema hashes; open Phase-2 joint issue
    A->>A: Fresh clone/checkout; follow README only
    B->>B: Observe command/config mismatch; independently inspect frozen results

    alt README/config/setup defect found
        B->>GH: PR: docs/config correction with failing command and expected correction
        GH-->>A: PR merged to candidate lineage
        A->>A: Repeat from a new fresh checkout
    end

    A->>GH: A-J04 evidence: commands, versions, hashes, outputs, deviations
    B->>B: Independently rerun one declared representative evaluation
    B->>GH: B-J04 docs/reproduction correction + independent-rerun evidence

    rect rgb(230, 245, 255)
        Note over A,B: Final evaluation / report reconciliation
        A->>A: Reconcile raw rows, traces, runner, oracle and engineering evidence
        B->>B: Reconcile estimands, pairs, CIs, tables, claims, threats/non-claims
        A->>B: A-J05 portability/fake-adapter/engineering-gate evidence
        B->>A: RQ/gate interpretation and draft typed decision
    end

    alt Semantic/core change discovered
        A->>GH: Invalidate G4-ready; version bump; return to owning Phase-1 gate
    else All evidence agrees
        A->>GH: Promote final matrix / G4 evidence
        B->>GH: Validate report/results/decision
        A->>B: Jointly sign H12 and exactly one Habitat decision
        A->>GH: Final CI, final SHA/tag/snapshot, deliverable index, G5 sign-off
    end
```

### Thứ tự merge bắt buộc

1. Khóa và record `G4-ready` candidate; chạy integration audit (contract/integration checks, full static/test suite, leakage, trace replay, bounded-loop, end-to-end smoke).
2. A chạy A-J04 từ checkout sạch. B chỉ đưa README/config/setup fix qua PR reviewable.
3. Sau mỗi PR docs/config/setup, A phải làm lại A-J04 từ **fresh state**; log cũ không thể chứng minh candidate mới.
4. A chạy A-J05 fake non-grid adapter và portability checks. Nếu sửa code-contract, merge trước khi dùng kết quả portability.
5. A/B reconcile final matrix và reports; chỉ lúc này promote `G4` trên final SHA.
6. B hoàn thiện RQ interpretation, threats/non-claims và typed decision; A xác minh engineering mapping không bị overclaim.
7. Chạy validators + CI trên final commit. Chỉ sau đó tạo signed/annotated tag hoặc immutable snapshot theo policy.

Không squash nhiều protocol changes chưa quyết định trong một closure commit. Một lane pass độc lập, checkbox riêng, hay README “có vẻ đúng” không đủ để close H12/G5.

---

## 4. Chi tiết công việc Member A — A-J04 và input cho B-J04

**Branch:** `test/a-fresh-reproduction`
**Vai trò:** operator của reproducibility; reviewer kỹ thuật cho data/report/decision.

### 4.1. Chuẩn bị fresh checkout

A tạo một thư mục mới ngoài working tree hiện hữu, clone đúng remote và checkout **frozen SHA/tag** ghi trong Phase-2 Issue. Không được dùng:

- `.venv` từ checkout khác;
- package/dependency cache, untracked config, local patch hoặc generated artifact làm input;
- raw private sidecar ngoài policy; hoặc
- knowledge/lệnh chưa được ghi trong README.

Trước lệnh setup đầu tiên, log phải ghi remote URL (đã sanitize nếu cần), candidate SHA/tag, ngày/giờ, OS, Python, `uv`, Git và dependency/lockfile identity. Nếu operator phải đoán path, biến môi trường hay lệnh, đó là reproduction failure chứ không phải “manual note”.

### 4.2. A-J04 execution record

A chạy README như operator entrypoint, theo thứ tự tối thiểu sau (exact spelling hiện hành phải là spelling trong README):

```bash
uv sync --all-groups
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run ns-vln generate-manifests --config configs/manifests.yaml
uv run ns-vln evaluate --config configs/smoke.yaml
```

Ngoài baseline trên, record phải chứng minh các acceptance conditions của master:

- public manifests regenerate/verify theo frozen config và hash policy;
- smoke **và ít nhất một declared reproduction target** chạy được; README phải expose entrypoint RQ1/RQ2, không chỉ smoke;
- result schema, artifact paths và trace replay được kiểm tra;
- summaries bắt nguồn từ raw rows/traces, không đọc agent-forbidden sidecars;
- output/hash/result schema khớp frozen artifact, hoặc deviation có typed disposition.

Với CLI hiện tại, A/B phải dùng chính command/options đã được tracked. Các commands mục tiêu trong handbook như `validate-report`, `validate-habitat-decision` hay `audit-portability` không được ghi là PASS nếu CLI/script tương ứng chưa tồn tại, chưa được test và chưa được documented trong README. Khi cần thêm chúng, đó là scoped closure work có test/PR/evidence, không phải một lệnh giả định.

### 4.3. Artifact A giao ở H12

| Artifact | Nội dung tối thiểu | B validation |
|---|---|---|
| Fresh-clone log | SHA/tag, clean directory assertion, full commands, exit status, stdout/stderr location, timestamps, OS/Python/uv/Git metadata | Kiểm tra lệnh chỉ dùng tracked instructions; xác nhận no local knowledge |
| Freeze manifest/config record | SHA256/identity của lockfile, configs, public manifests, result schema và expected-row config | So sánh với H11/G4-ready; chặn hash drift |
| Reproduction outputs | static/test results, manifest verification, smoke + representative target, rows/summary/trace paths | Independently rerun một declared target và compare schema/hash where applicable |
| Deviation/rerun log | command fail, error, classification, owner, PR/commit, impacted cells và re-run result | Xác nhận infrastructure vs semantic classification hợp lệ |
| A-J05 technical evidence | fake adapter pass, portability scan, runtime/metrics/oracle/engineering gate links | Dùng làm nguồn duy nhất cho engineering claims và Habitat rubric |

### 4.4. A review duties sau reproduction

- Spot-check raw episode rows ↔ traces ↔ summaries; không chỉ đọc aggregate table.
- Xác nhận result rows có `oracle_input`, local methods không có normal-path oracle/sidecar leak, B3 exception được ghi đúng protocol.
- Xác nhận paired methods dùng identical episode units, controller, verifier và budgets; missing/duplicate rows có disposition.
- Xác nhận RQ1 chỉ dùng N1 với replanning off; RQ2 chỉ dùng clean evidence + fixed N2 interventions.
- Xác nhận report không biến MiniGrid/fake adapter pass thành Habitat/RGB/VLM performance claim.
- Xác nhận failed threshold/RQ và protocol deviations hiện diện trong final report, không bị qualitative success case ghi đè.

**A commit:**

```text
test(repro): record fresh-checkout reproduction evidence
```

Commit này chỉ chứa evidence/docs/tests thuộc reproduction; không gộp semantic runtime fix. A không approve final B-J04 PR nếu report không thể truy về frozen SHA, raw summary và evidence kỹ thuật.

---

## 5. Chi tiết công việc Member B — B-J04

**Branch:** `docs/b-final-analysis`
**Vai trò:** observer/reviewer của fresh reproduction; owner docs/RQ analysis; đồng-signatory của decision.

### 5.1. Quan sát A-J04 và sửa docs có kiểm soát

B quan sát A chạy ở clean checkout, ghi chính xác command/path/config mismatch thay vì tự nhắc A chạy “lệnh đúng”. Với mỗi docs/config/setup defect:

1. Link failing command/output vào Phase-2 Issue.
2. Tạo PR riêng với README/config docs correction và expected operator behavior.
3. Không thay đổi frozen threshold/budget/seed/semantic option để biến run thành PASS.
4. Khi PR merge, yêu cầu A chạy lại toàn bộ sequence từ fresh checkout mới.
5. Chỉ mark correction done khi new log chứng minh defect đã biến mất.

B cũng independently rerun **một evaluation target đã khai báo trong README** (ưu tiên đại diện cho final artifact, không phải ad-hoc demo) từ tracked state. B ghi environment metadata, config/manifests/hashes, command, output row/schema and trace checks; compare với A record và report mọi mismatch.

### 5.2. RQ/report audit

B hoàn thiện/kiểm tra methods, estimands, paired contrasts, per-family/per-condition tables, fixed-seed bootstrap CIs, validity analysis, threats và explicit non-claims. Mỗi number trong report phải truy ngược được tới frozen raw rows/summaries/config/manifests; mỗi claim phải chỉ đến table/CI/gate evidence cụ thể.

Checklist phân tích bắt buộc:

- [ ] `RQ1`: contrast chính là V1R0 − V0R0 dưới N1, replanning off; không dùng RQ2 recovery để suy diễn causal RQ1.
- [ ] `RQ2`: clean evidence + fixed/recoverable N2 interventions; pairing dựa checkpoint từ shared initial plan và identical prefix.
- [ ] CIs paired, episode IDs, denominators, family/condition strata, missing/duplicate disposition và hashes khớp B-09 audit.
- [ ] Leakage, trace completeness/replay, planner timeout/bound and clean feasibility evidence được nói rõ; không selection/cherry-pick qualitative case.
- [ ] Failed threshold/RQ, limitations và protocol deviations được ghi trung thực; không thay threshold sau khi xem results.
- [ ] External-validity boundaries được nêu: sprites/2D, synthetic corruption, template grammar, simple dead reckoning, 3D re-identification. Không claim natural VLN, RGB/VLM, photorealistic, generalization hoặc Habitat performance.

### 5.3. Validation report trước sign-off

Handbook đặt các validation entrypoints sau làm target interface:

```bash
uv run ns-vln validate-report --report reports/month1/
uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml
uv run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml
```

`validate-results` phải nhận options đúng với CLI đã track (ở candidate hiện tại là `--expected-config`; không dùng `--report` nếu parser không định nghĩa option đó). `validate-report` và `validate-habitat-decision` chỉ là gate evidence sau khi implementation/test/README của chính entrypoint đó đã tồn tại. Validator cuối cùng phải reject tối thiểu:

- report thiếu required sections hoặc evidence links;
- giá trị report lệch summaries/raw results;
- thiếu hoặc có hơn một Habitat decision;
- RGB/Habitat/generalization claim không có evidence hợp lệ;
- protocol deviation không được liệt kê.

**B commits:**

```text
docs: correct setup and reproduction instructions
docs: add RQ statistics and validity analysis
```

B không approve A-J04 evidence nếu independent rerun dùng state khác candidate, không verify representative target, hoặc reproduction log không nêu deviations.

---

## 6. Joint finalization — G4, H12, G5

### 6.1. G4: promote final frozen evaluation

Sau A-J04 và A-J05 evidence, A/B thực hiện final matrix reconciliation trên candidate lineage:

```bash
# Targeted integration checks, followed by the full candidate suite.
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml
uv run ns-vln validate-traces --runs runs/final
uv run ns-vln audit --runs runs/final
uv run ns-vln summarize --runs runs/final --output reports/month1/
```

Expected G4 evidence:

- all B3/RQ1/RQ2/V1R1-clean rows complete (plan target xấp xỉ 1.120 core rows), với missing/duplicate row chỉ được chấp nhận khi có typed disposition;
- raw rows ↔ traces ↔ summaries ↔ paired CIs reconcile exactly;
- final SHA/config/manifest/schema hashes match record; no unversioned semantic changes;
- leakage and trace replay/completeness audits pass; bounds and task outcome taxonomy remain valid;
- final candidate is no longer merely `G4-ready` and is eligible for `G4` promotion.

### 6.2. H12 evidence packet

H12 chỉ complete khi Issue chứa một packet reviewable gồm:

```markdown
## H12 — Phase-2 closure evidence
- Frozen candidate SHA/tag and final SHA:
- Lock/config/manifest/schema/result hashes:
- A fresh-checkout log (path/link):
- B independent rerun log (path/link):
- Final CI link and command results:
- Raw-row / trace / summary / CI reconciliation:
- Leakage and replay audit links:
- Fake-adapter and portability evidence:
- RQ1/RQ2 tables, estimands and threats/non-claims:
- Habitat decision file and exact evidence links:
- Deviations, reruns, unresolved limitations and owners:
- Merge commits / PRs / reviewer approvals:
```

### 6.3. G5 typed Habitat decision

A chứng minh engineering/planning/control/portability evidence; B áp dụng report/RQ gates; cả hai chọn **chính xác một** class bên dưới. Decision YAML/report phải link frozen SHA/config/manifests, gate evidence, exact table/CI and unresolved limitations.

| Decision | Điều kiện |
|---|---|
| `Advance` | Tất cả engineering, planning/control, clean-feasibility, RQ1 và RQ2 gates PASS. Có thể bắt đầu Habitat semantic-navigation adapter phase. |
| `Conditional hold` | Architecture/engineering gates PASS nhưng RQ1 hoặc RQ2 thiếu practical support. Báo negative/partial result và tiếp tục diagnosis trong 2D. |
| `No-go` | B3, leakage, verifier, bounded execution, trace integrity hoặc fresh reproduction fail. Không migrate Habitat. |

Các gates phải xét trước decision gồm:

- Engineering: no tracked credential; zero normal-path oracle leak; typed outcomes; action/replan/loop/planner bounds; trace completeness/replay ≥99%; planner timeout <1%, p95 <2 s; fresh checkout; fake non-grid adapter; no core MiniGrid/grid-coordinate dependency.
- Planning/control: B3 clean SR ≥95% mỗi core family; believed-state plan validity 100%; oracle-state plan validity ≥98%.
- Local-input clean: V1R1 ≥85% `goto_type_color`, ≥75% `key_door_goal`, oracle-state plan validity ≥95% for found plans, invalid primitive action ≤5%.
- RQ1: ≥20% relative V1R0 improvement vs V0R0 under N1 for oracle plan validity hoặc invalid-action rate; accepted precision ≥90% at coverage ≥50%; clean-success loss ≤5 pp; CI không cho material adverse effect dưới −2 pp.
- RQ2: V1R1 recovery ≥50%; ≥15 pp over V1R0; ≥90% detection trước hai additional invalid primitives; median replans/recovered episode ≤3; no recovery vượt public action budget.

Không được đổi threshold sau result, và không được dùng một successful demo để override gate định lượng fail. Stretch failure không ảnh hưởng decision, nhưng core failure không được che bằng stretch work.

---

## 7. Tổng hợp file/artifact ownership

| File/artifact | Action | Owner | Reviewer | Mục đích |
|---|---|---|---|---|
| `README.md` | Modify if reproduction proves defect | B | A | Canonical operator sequence, prerequisites, expected outputs/deviations |
| `configs/*.yaml`, lock/tracked metadata | Modify only through reviewed fix/version policy | Owner theo root cause | Cả hai | Setup/reproduction/frozen evaluation identity |
| `reports/month1/` | Create/modify | B (RQ/docs), A (engineering inputs) | Cả hai | Tables, CIs, methods, results, threats, audit/reproduction index |
| `reports/expected_rows.yaml` | Already frozen or versioned if semantic change | A | B | Expected row-matrix validation |
| `reports/month1/habitat_decision.yaml` | Create/modify | Joint | Cả hai | Exactly one typed decision with evidence links |
| `tests/env/test_non_grid_adapter_contract.py` and test-only fake adapter | Create/modify in A-J05 | A | B | Non-grid portability/conformance evidence |
| Reproduction and independent-rerun logs | Create tracked/reviewable record | A / B respectively | Other member | H12 reproducibility evidence |
| Final tag/snapshot + deliverable index | Create only after final CI | Joint/release owner | Cả hai | Immutable closure pointer to reproduced final SHA |

`runs/`, raw `artifacts/`, local secrets và evaluator-private sidecars remain subject to ignore/storage policy. Reviewed aggregate tables can be intentionally copied to tracked `reports/`; never track raw/private data merely to make review convenient.

---

## 8. Commit plan và reviewer protocol

| # | Who | Branch | Commit message | Merge precondition |
|---|---|---|---|---|
| 1 | A | `test/a-fresh-reproduction` | `test(repro): record fresh-checkout reproduction evidence` | Candidate identity recorded; log uses clean state |
| 2 | B | `docs/b-final-analysis` | `docs: correct setup and reproduction instructions` | Failing A-J04 command linked; A re-run required after merge |
| 3 | B | `docs/b-final-analysis` | `docs: add RQ statistics and validity analysis` | Tables/CIs reconcile with frozen summaries and raw evidence |
| 4 | A | A-J05 branch | `docs: add environment control and evaluation results` | Fake-adapter/portability and engineering gates evidence-linked |
| 5 | Joint | integration/final branch | `docs: record Habitat migration go-no-go decision` | G4 evidence, H12 packet and exactly one decision validated |
| 6 | Joint | final branch | `docs: finalize month-one neuro-symbolic VLN artifact` | CI PASS; G5 criteria, deliverable index and reviewer approvals complete |

Mỗi PR/Issue update phải ghi theo template:

```markdown
## A-J04 / B-J04 joint checkpoint
- Frozen SHA/tag and phase status:
- A input commit/artifact:
- B input commit/artifact:
- Command(s), exact config(s), and exit status:
- Hash/schema/row-count evidence:
- Reproduction state assertion (fresh directory; no reused venv/cache/local config):
- Root-cause owner and classification (docs/setup | infrastructure | semantic):
- Required rerun scope and outcome:
- Claim/table/CI or engineering-gate link:
- Decision / unresolved limitation:
- Reviewer evidence and merge order:
```

Nếu một task fail ba fix attempts khác nhau, dừng patching và tổ chức joint architecture/interface review. Issue phải giữ failing test/command, root-cause owner và `Blocked` status cho đến khi safe to proceed.

---

## 9. G4/G5 acceptance checklist

### 9.1. G4 — Final frozen evaluation artifact

- [ ] Final matrix có expected rows; missing/duplicate/unavailable cells có typed disposition.
- [ ] Pair IDs, formula denominators, configs, hashes, seeds, controller, verifier và budgets khớp frozen protocol.
- [ ] Raw rows ↔ traces ↔ summaries ↔ CIs reconcile; report values match reviewed summaries.
- [ ] Leakage audit, trace schema/replay and bounded execution evidence PASS on final SHA.
- [ ] Semantic changes, nếu có, được versioned và affected matrix rerun; không còn core change chưa version.
- [ ] Final SHA được promote chỉ sau integration audit và final matrix reconciliation.

### 9.2. G5 — Reproduction and 3D decision

- [ ] A fresh checkout PASS theo README, without reused environment/cache/untracked configuration.
- [ ] B independent representative rerun PASS hoặc discrepancy được resolved/typed.
- [ ] README, lock/config, CI và handbook command/schema changes cùng được cập nhật.
- [ ] CI PASS trên final commit.
- [ ] Fake non-grid adapter contract và portability scan PASS.
- [ ] Report có methods/results/RQ tables/CIs/threats/non-claims, protocol deviations and evidence links.
- [ ] Không overclaim Habitat/RGB/natural-VLN/generalization performance.
- [ ] `habitat_decision.yaml` có đúng một `Advance` / `Conditional hold` / `No-go` backed by fixed rubric.
- [ ] H12 evidence packet, final tag/snapshot and deliverable index complete; A và B sign off.

---

## 10. Sau khi hoàn thành A-J04/B-J04

Khi `G4` và `G5` được sign-off:

1. Merge README/reproduction, methods/results/threats và Habitat decision.
2. Confirm repository không có tracked secret, private sidecar hay accidental raw run output.
3. Publish/archive reviewed aggregate tables, configs, hashes, reports; giữ raw/private artifacts theo storage policy.
4. Tạo signed/annotated final tag hoặc immutable research snapshot trỏ đúng **final SHA đã reproduce**.
5. Đóng completed Issues; mọi limitation/unresolved work phải chuyển thành follow-up milestone với owner và scope.
6. Ghi final gate table `R0`, `G0`–`G5`, protocol deviations và deliverable index.

**Definition of Done:** H12 complete; fresh reproduction, final CI, fake-adapter portability, final report and exactly one evidence-linked Habitat decision all pass the checks above. Mọi failed threshold/RQ hoặc protocol deviation vẫn phải xuất hiện trung thực trong artifact cuối.
