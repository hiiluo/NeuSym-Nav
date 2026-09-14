# Kế hoạch hoàn chỉnh triển khai Neuro-Symbolic VLN 2D

> **Trạng thái:** `Authoritative month-one master plan`  
> **Ngày cập nhật:** 2026-09-07  
> **Nhân sự:** Thành viên A và Thành viên B  
> **Năng lực tối thiểu:** 4 tuần × 15 giờ/người/tuần = khoảng 120 team-hours  
> **Đích chuyển tiếp:** Habitat-Lab sau khi vượt qua các `go/no-go gates`

Tài liệu này là source of truth cho **research scope, shared technical contracts, repository governance, cross-member integration, evaluation protocol và final acceptance** của giai đoạn 2D. Nó bao bọc hai execution handbook: master quy định việc phải chuẩn bị trước khi bắt đầu, các ràng buộc chung trong Phase 1 và lifecycle phải hoàn tất trong Phase 2; handbook quy định exact files, tests, commands và commits của từng thành viên, gồm cả ba closure runbooks được Phase 2 gọi.

File `docs/neuro_symbolic_vln_2d_implementation_plan.md` được giữ làm historical input. Không dùng historical plan để ghi đè quyết định trong master hiện tại.

---

## Mục lục

0. [Start here: vai trò tài liệu và luồng ba phase](#0-start-here-vai-trò-tài-liệu-và-luồng-ba-phase)
1. [Mục tiêu và kết luận ngắn](#1-mục-tiêu-và-kết-luận-ngắn)
2. [Các bài học bắt buộc từ kế hoạch trước](#2-các-bài-học-bắt-buộc-từ-kế-hoạch-trước)
3. [Decision log](#3-decision-log)
4. [Research questions, hypotheses và estimands](#4-research-questions-hypotheses-và-estimands)
5. [Phạm vi, non-claims và Definition of Success](#5-phạm-vi-non-claims-và-definition-of-success)
6. [Phase 0: repository, environment, security và readiness](#6-phase-0-repository-environment-security-và-readiness)
7. [Trust boundary và kiến trúc end-to-end](#7-trust-boundary-và-kiến-trúc-end-to-end)
8. [Typed contracts và symbolic data model](#8-typed-contracts-và-symbolic-data-model)
9. [Instruction grammar và grounding](#9-instruction-grammar-và-grounding)
10. [Local observation, evidence và tri-valued belief](#10-local-observation-evidence-và-tri-valued-belief)
11. [MiniGrid semantics, positive STRIPS và pyperplan](#11-minigrid-semantics-positive-strips-và-pyperplan)
12. [Exploration, re-observation và execution-aware replanning](#12-exploration-re-observation-và-execution-aware-replanning)
13. [Hai benchmark channels độc lập](#13-hai-benchmark-channels-độc-lập)
14. [Baselines và causal method matrix](#14-baselines-và-causal-method-matrix)
15. [Episode generation, manifests và oracle](#15-episode-generation-manifests-và-oracle)
16. [Metrics và statistical protocol](#16-metrics-và-statistical-protocol)
17. [Traceability và reproducibility](#17-traceability-và-reproducibility)
18. [Shared module boundaries và source layout](#18-shared-module-boundaries-và-source-layout)
19. [Phase 1: GitHub workflow và execution governance](#19-phase-1-github-workflow-và-execution-governance)
20. [Ownership, capacity và milestone cadence](#20-ownership-capacity-và-milestone-cadence)
21. [Shared quality bar](#21-shared-quality-bar)
22. [Execution handbook index và handoff matrix](#22-execution-handbook-index-và-handoff-matrix)
23. [Weekly gates, integration và contingency cuts](#23-weekly-gates-integration-và-contingency-cuts)
24. [Phase 2: post-core integration, evaluation và closure](#24-phase-2-post-core-integration-evaluation-và-closure)
25. [Habitat migration seam](#25-habitat-migration-seam)
26. [Practical Habitat go/no-go rubric](#26-practical-habitat-gono-go-rubric)
27. [Rủi ro, threats to validity và mitigations](#27-rủi-ro-threats-to-validity-và-mitigations)
28. [Final deliverables và Definition of Done](#28-final-deliverables-và-definition-of-done)
29. [Appendices](#29-appendices)

---

## 0. Start here: vai trò tài liệu và luồng ba phase

### 0.1. Ba tài liệu và phạm vi thẩm quyền

| Tài liệu | Quyết định thuộc tài liệu | Không nên chứa |
|---|---|---|
| Master plan này | Scope, RQ, security/readiness, shared contracts, trust boundary, ownership, handoffs, gates, evaluation, reproduction và final DoD | Exact step-by-step implementation lặp lại handbook |
| [Handbook Thành viên A](member_a_implementation_handbook.md) | Environment–Control–Evaluation: files, tests, commands, commits và cross-validation cụ thể | Tự ý thay shared contract, scope hoặc gate |
| [Handbook Thành viên B](member_b_implementation_handbook.md) | Language–Belief–Planning: files, tests, commands, commits và cross-validation cụ thể | Tự ý thay shared contract, scope hoặc gate |

Quy tắc ngắn: **master quyết định “làm gì, vì sao và đạt tiêu chuẩn nào”; handbook quyết định “ai làm bằng file, test, command và commit nào”.**

Nếu có mâu thuẫn:

1. scope, trust boundary, contracts, experiment semantics và gates trong master ưu tiên;
2. implementation sequence/files/tests trong handbook ưu tiên khi không vi phạm master;
3. không tự chọn một phía khi mâu thuẫn chưa giải quyết; tạo `status:decision-needed` Issue, ghi impact và cần cả hai thành viên approve;
4. thay đổi shared interface sau freeze phải version schema/contract và rerun toàn bộ affected tests/matrix.

### 0.2. Luồng bắt buộc ba phase

```text
PHASE 0 — PRE-HANDBOOK READINESS
GitHub repository + access + security + local toolchain + tracked docs + work board
                         |
                         v
                 R0 readiness PASS
                         |
                         v
PHASE 1 — CORE HANDBOOK EXECUTION
A-01…A-07/A-J01…A-J03 <--- H01–H11 ---> B-01…B-09/B-J01…B-J03
                         |
                         v
             G0–G3 PASS → G4-ready
                         |
                         v
PHASE 2 — COMPLETION RUNBOOKS
A-J04 + A-J05 <---------- H12 ----------> B-J04
Integration audit + fresh clone + RQ decision + release/archive
                         |
                         v
                  G5 + final DoD
```

- **Không mở task implementation trong handbook trước `R0`.**
- `A-01`/`B-01` là task đầu tiên sau `R0`; chúng tạo và kiểm chứng tracked project scaffold/CI/contracts để đóng `G0`.
- Phase cut nằm tại `G4-ready`: các task core/experiment đến A-07, B-09 và joint J03 thuộc Phase 1; Phase 1 chưa tuyên bố final evaluation `G4`.
- `A-J04`, `A-J05` và `B-J04` nằm trong handbook để cung cấp exact Phase-2 runbook; chúng **không phải prerequisite để vào Phase 2**.
- Final evaluation `G4`, final checklist của A/B và `G5` là exit criteria của Phase 2.

### 0.3. Reading order

1. Cả hai đọc Section 0–24 ít nhất một lần trước kickoff; Section 9–12 là normative semantics chứ không phải optional implementation detail.
2. Member A đọc [handbook A](member_a_implementation_handbook.md), đặc biệt lane schedule và cross-validation duties.
3. Member B đọc [handbook B](member_b_implementation_handbook.md), đặc biệt lane schedule và cross-validation duties.
4. Trước mỗi joint checkpoint, cả hai quay lại Section 22–23.
5. Sau `G4-ready`, dừng tạo feature mới, vào Section 24 và dùng `A-J04`/`A-J05`/`B-J04` làm exact Phase-2 runbooks; chỉ sign off final handbook checklists sau final `G4` và `G5`.

### 0.4. Source-of-truth hygiene

Master và hai handbook là authoritative artifacts nên **phải được Git track**. Trước `R0`, ba lệnh sau phải exit `0`:

```bash
git ls-files --error-unmatch docs/neuro_symbolic_vln_2d_complete_implementation_plan.md
git ls-files --error-unmatch docs/member_a_implementation_handbook.md
git ls-files --error-unmatch docs/member_b_implementation_handbook.md
```

`git check-ignore -v` không được báo rule ignore cho bất kỳ file nào ở trên. Nếu hiện tại chúng bị ignore, sửa `.gitignore`, review thay đổi và add ba file bằng quy trình bình thường; không dùng `git add -f` như giải pháp lâu dài.

---

> **PHẦN I — RESEARCH SCOPE, TECHNICAL CONSTRAINTS VÀ SYSTEM DESIGN**  
> Section 1–18 định nghĩa mục tiêu, phạm vi, kiến trúc, data contracts, experiment protocol và ràng buộc kỹ thuật chung. Exact implementation steps nằm trong hai handbook.

## 1. Mục tiêu và kết luận ngắn

### 1.1. Mục tiêu một câu

Xây dựng và đánh giá một causal PoC có thể tái lập, trong đó robot nhận instruction và local categorical observation của MiniGrid, tạo explicit symbolic belief có `TRUE/FALSE/UNKNOWN`, validation trước planning, lập kế hoạch bằng positive STRIPS/PDDL với pyperplan, thực thi theo MiniGrid-native semantics, rồi cập nhật belief và replanning có giới hạn khi execution feedback làm plan mất hiệu lực.

### 1.2. Câu hỏi mà tháng đầu phải trả lời

1. **RQ1 — Validation before planning:** validation có giảm symbolic commitments sai, oracle-invalid plans, invalid primitive actions và task failures khi evidence bị corruption hay không?
2. **RQ2 — Execution-aware replanning:** belief invalidation, re-observation và replanning có phục hồi tốt hơn khi một initially valid plan bị fixed world/execution intervention làm mất hiệu lực hay không?

### 1.3. Kết luận thiết kế

- Dùng **MiniGrid 2D** để cô lập planning/validation/recovery khỏi chi phí perception 3D.
- Dùng **local categorical observation**, không dùng global state trong normal agent path.
- Giữ **pyperplan** làm online PDDL planner; exact BFS-style solver chỉ làm evaluator oracle.
- Core chỉ gồm `goto_type_color` và `key_door_goal`.
- Xử lý unknown bằng **tri-valued belief + conservative known-space planning + deterministic frontier exploration**.
- Tách RQ1 và RQ2 thành hai experiment channels khác nhau để tránh causal confounding.
- Chỉ chuyển sang Habitat khi engineering gates, RQ1 và RQ2 đạt practical thresholds đã pre-register.

---

## 2. Các bài học bắt buộc từ kế hoạch trước

### 2.1. Điểm mạnh cần giữ

| Điểm mạnh | Giá trị | Cách giữ trong kế hoạch mới |
|---|---|---|
| Oracle-first sequence | Tách lỗi domain/planner/controller khỏi perception và belief | `G1` bắt buộc B3 chạy đúng trước local-input pipeline |
| Modular pipeline | Hỗ trợ unit tests, ablations và thay module | Khóa typed interfaces trong Week 1 |
| Predicate validation | Phù hợp đóng góp neuro-symbolic | Đưa thành RQ1 với causal contrast riêng |
| Execution feedback/replanning | Phù hợp closed-loop embodied system | Đưa thành RQ2 với fixed interventions |
| Provenance và trace | Hỗ trợ explainability, debugging và audit | Mọi primitive action phải nối tới evidence, belief, plan và outcome |
| B3/B4/B5 intent | Có cơ sở tách oracle/local/full system | Chuyển thành factorial `B3`, `V0R0`, `V1R0`, `V1R1` |
| Metrics ngoài Success Rate | Tránh đánh giá một chiều | Định nghĩa exact denominators, SPL/SOPE và plan-validity levels |
| Không overclaim novelty | Giữ claim nghiên cứu thận trọng | Ghi explicit permitted claim và non-claims |
| Reproducibility intent | Seeds/config/logs đã được nhận diện | Bổ sung immutable manifests, hashes, sidecars và fresh-checkout gate |

### 2.2. Blockers và gaps bắt buộc sửa

#### A. MiniGrid/PDDL action semantics chưa đúng

- `pickup` và `toggle` tác động lên **front cell**, không phải cell robot đang đứng.
- Non-overlap object như ball/key/box không thể dùng goal `at(robot, object_cell)`.
- `GoTo` object thành công khi robot **adjacent and facing** target.
- `Actions.done` là no-op trong base MiniGrid; không thể dùng làm task success.
- Matching carried key có thể mở locked door bằng native `toggle`.
- Nếu orientation chỉ được controller sửa ngầm, PDDL plan validity và primitive efficiency không còn đồng nhất.

**Sửa:** model orientation trong PDDL, thêm explicit `TaskVerifier`, không map symbolic stop sang `Actions.done`, và khóa semantics bằng regression tests.

#### B. Partial observability mâu thuẫn với classical closed-world planning

Bản cũ yêu cầu local observation nhưng không định nghĩa `unknown`. Trong PDDL, fact vắng mặt bị hiểu như false; điều này không tương đương “chưa quan sát”. Không có policy khi goal/path chưa thấy hoặc planner trả no-plan vì known map thiếu.

**Sửa:** dùng ba tầng `Evidence → BeliefMap → CommittedPlanningState`; only known-true validated facts vào PDDL; frontier/re-observation nằm ngoài PDDL.

#### C. Domain vượt phạm vi pyperplan

Pyperplan phù hợp positive STRIPS, không cung cấp contingent planning, conditional effects, negative preconditions, action costs hoặc derived predicates. Conditional instruction không thể được biểu diễn như một branching policy trong domain hiện tại.

**Sửa:** compile domain về `:strips :typing`, dùng explicit positive predicates như `handempty`, `door-closed`, `door-locked`; conditional instruction là post-core `TaskMonitor` micro-benchmark.

#### D. Confidence chưa có nguồn hợp lệ

MiniGrid categorical observation là exact encoding. Gán confidence 0.70 tùy ý không mang ý nghĩa xác suất. Template parser cũng không nên tự báo confidence liên tục.

**Sửa:** clean evidence có reliability `1.0`; corrupted evidence dùng declared synthetic score model có seed và được đánh giá như PoC-only mechanism; parser trả `Deterministic/Ambiguous/Unsupported`.

#### E. B4/B5 bị confounded

Nếu B5 đồng thời thêm validation và replanning, chênh lệch B5−B4 không chỉ ra cơ chế nào tạo lợi ích.

**Sửa:** dùng `V0R0`, `V1R0`, `V1R1` và hai primary contrasts riêng.

#### F. Metrics chưa có exact semantics

- SPL không phù hợp trực tiếp cho key-door interaction.
- Predicate F1 chưa xác định observable universe và unknown handling.
- Valid Plan Rate chưa phân biệt believed-state và oracle-state.
- Validation rejection rate có thể “tốt” giả tạo bằng cách reject mọi fact.
- Explanation Coverage chỉ đo có log, không đo replay fidelity.

**Sửa:** dùng grid SPL chỉ cho navigation; dùng SOPE cho key-door; báo accepted precision/risk/coverage; tách plan validity ở hai state levels; yêu cầu trace replay fidelity.

#### G. Chưa có research và transfer gates

“Phần lớn episode” hoặc “một phần đáng kể” không falsifiable. Không có tiêu chí nào buộc validation/replanning tạo practical signal trước khi sang 3D.

**Sửa:** pre-register engineering, clean-feasibility, RQ1, RQ2 và Habitat go/no-go thresholds.

#### H. 2D→3D seam chưa đủ cụ thể

`cell_x_y`, exact global object IDs và MiniGrid enums sẽ rò rỉ vào core nếu không khóa boundary. Habitat và AI2-THOR cũng không phải hai đích thay thế cho nhau.

**Sửa:** chọn Habitat-Lab; dùng opaque IDs, `LocationGraph`, `EnvironmentAdapter`, fake non-grid conformance adapter và separate evaluator oracle.

#### I. Scope chưa phù hợp với 120 team-hours

Bản cũ bao gồm navigation, relations, doors, conditionals, RGB/VLM, multiple baselines và 500–2.000 episodes. Với hai người half-time, scope này làm giảm cả implementation quality lẫn research validity.

**Sửa:** hai core task, bốn core methods, khoảng 1.120 final runs; stretch không có scheduled hours.

#### J. Repository hygiene

Bootstrap cũ đã bị xóa có chủ ý. Tại thời điểm master được tối ưu, `.gitignore` hiện hữu nhưng đang ignore cả master và hai handbook, nên `git status/diff` không bảo vệ được ba authoritative artifacts; local `.claude` configuration cũng từng được phát hiện có credential plaintext.

**Sửa:** không restore bootstrap cũ; Phase 0 phải rotate/revoke credential, ignore local secret paths, bỏ rule ignore ba tài liệu, track/review chúng bằng Git và chỉ sau `R0` mới tạo fresh scaffold qua `A-01`/`B-01`.

### 2.3. Kết luận audit

Bản cũ là một architecture memo và backlog định hướng tốt, nhưng chưa phải executable research protocol. Kế hoạch mới giữ kiến trúc mô-đun, oracle-first development và traceability, đồng thời khóa semantics, interfaces, causal comparisons, workload, tests, reproducibility và decision gates.

---

## 3. Decision log

| ID | Quyết định đã chốt | Lý do |
|---|---|---|
| D01 | Mục tiêu là research + PoC | Cần cả hệ thống chạy được và bằng chứng định lượng |
| D02 | 4 tuần, 2 người, tối thiểu 15 giờ/người/tuần | Scope phải dựa trên 120 team-hours bảo đảm |
| D03 | MiniGrid categorical local observation là core sensor | Cô lập validation/planning/recovery; RGB/VLM deferred |
| D04 | `goto_type_color` và `key_door_goal` là core | Một task grounding cơ bản và một task multi-step symbolic |
| D05 | Spatial relation và conditional instruction là post-core | Không làm loãng causal evidence trong tháng đầu |
| D06 | Tri-valued belief và conservative known-space PDDL | Không collapse unknown thành false |
| D07 | Frontier exploration nằm ngoài PDDL | Pyperplan không phải contingent planner |
| D08 | Orientation nằm trong PDDL | Đúng front-cell semantics và primitive plan trace |
| D09 | Pyperplan là online planner | Phù hợp small deterministic positive STRIPS PoC |
| D10 | Exact BFS-style solver chỉ là evaluator oracle | Tính solvability/optimum mà không thay online method |
| D11 | Grammar xác định + 40-case curated suite | Có language contract nhưng không overclaim NL generalization |
| D12 | RQ1 và RQ2 là hai axes riêng | Tránh attribution sai giữa validation và replanning |
| D13 | N1 và N2 là hai benchmark channels riêng | Tách perception/evidence error khỏi world/execution change |
| D14 | Habitat-Lab là 3D target đầu tiên | Phù hợp navigation/VLN và có dataset/sensor/measure abstractions |
| D15 | Habitat phase đầu vẫn semantic/categorical | Không thay simulator và perception cùng lúc |
| D16 | GitHub là collaboration channel chính | Hỗ trợ async ownership/review cho hai người |
| D17 | Tạo file kế hoạch mới, giữ nguyên file cũ | Bảo tồn historical input và tránh overwrite |
| D18 | Bootstrap được tạo lại từ fresh decisions | Các deletions hiện tại là chủ ý |
| D19 | Tài liệu viết bằng tiếng Việt; terminology/code giữ English | Đúng nhu cầu nhóm và tránh dịch sai thuật ngữ chuẩn |

---

## 4. Research questions, hypotheses và estimands

### 4.1. RQ1 — Validation before planning

> Trong điều kiện local evidence bị corruption có kiểm soát, validation về reliability, type/ontology, staleness và consistency trước khi tạo PDDL problem có giảm incorrect commitments, oracle-invalid plans, invalid primitive actions và task failures so với planning từ unvalidated evidence hay không?

#### Treatment và comparator

- Comparator: `V0R0` — không reliability/consistency validation, không replanning.
- Treatment: `V1R0` — validation trước commitment/planning, không replanning.
- Giữ cố định instruction parser, local decoder, frozen evidence checkpoint, PDDL domain, pyperplan search, controller, task verifier, action budget và episode/corruption seed.

#### Primary mechanistic estimand

\[
\Delta_{RQ1}^{plan}
=
OracleValidPlanRate(V1R0)
-
OracleValidPlanRate(V0R0)
\]

#### Primary system estimand

\[
\Delta_{RQ1}^{eff}
=
TaskEfficiency(V1R0)
-
TaskEfficiency(V0R0)
\]

`TaskEfficiency` là grid SPL cho `goto_type_color` và SOPE cho `key_door_goal`; không pool hai metric thành một con số duy nhất.

#### Secondary endpoints

- Accepted predicate precision/risk/coverage.
- Believed-state plan validity.
- Invalid primitive action rate.
- Plan status distribution.
- Clean success non-inferiority.

#### Practical support signal

RQ1 được xem là có practical support nếu trên N1 test:

1. `V1R0` cải thiện oracle-state valid-plan rate **hoặc** giảm invalid-action rate ít nhất 20% tương đối so với `V0R0`;
2. accepted precision ≥90% tại coverage ≥50%;
3. clean success giảm không quá 5 percentage points;
4. paired confidence interval không cho thấy adverse effect nhỏ hơn −2 percentage points trên primary system endpoint.

Không yêu cầu mọi metric cùng tăng. Nếu validation tăng precision nhưng làm plan coverage quá thấp, RQ1 không được coi là đã hỗ trợ đầy đủ.

### 4.2. RQ2 — Execution-aware replanning

> Sau một fixed, recoverable world/execution intervention làm initially valid plan mất hiệu lực, execution mismatch detection, belief invalidation, re-observation và bounded replanning có tăng recovery so với cùng pipeline nhưng không replanning hay không?

#### Treatment và comparator

- Comparator: `V1R0` — full validation, không replanning sau intervention.
- Treatment: `V1R1` — full validation + execution-aware replanning.
- Evidence sạch; initial belief và initial plan giống nhau; intervention checkpoint được pre-register và oracle xác nhận recoverable.

#### Primary estimand

\[
\Delta_{RQ2}^{recovery}
=
RecoveryRate(V1R1)
-
RecoveryRate(V1R0)
\]

#### Secondary endpoints

- Detection before additional invalid actions.
- Additional primitive actions so với post-intervention optimum.
- Replans per recovered episode.
- Planner wall-clock cost.
- Loop/budget termination rate.
- Intervention→belief update→replan trace fidelity.

#### Practical support signal

RQ2 được xem là có practical support nếu:

1. `V1R1` recovery ≥50% trên oracle-confirmed recoverable interventions;
2. cao hơn `V1R0` ít nhất 15 percentage points;
3. median replans ≤3;
4. mọi run nằm trong action/replan/loop/planner-time bounds.

### 4.3. Secondary system question

So sánh `V1R1−V0R0` được báo cáo như full-system result, nhưng không dùng riêng contrast này để kết luận validation hoặc replanning là nguyên nhân.

---

## 5. Phạm vi, non-claims và Definition of Success

### 5.1. Core scope bắt buộc

| Nhóm | Nội dung |
|---|---|
| Tasks | `goto_type_color`, `key_door_goal` |
| Sensor | MiniGrid local categorical observation, heading, carrying state, declared action feedback |
| Language | Deterministic grammar + 24 supported paraphrases + 8 ambiguous + 8 unsupported |
| State | EvidenceStore, tri-valued BeliefMap, staleness, provenance, committed known-true state |
| Validation | Schema/type, ontology, reliability, uniqueness/exclusivity, contradiction, staleness |
| Planning | Orientation-aware positive STRIPS, pyperplan online planner |
| Exploration | Deterministic frontier + bounded heading sweep |
| Execution | Primitive controller, explicit task verifier, execution monitor |
| Recovery | Belief invalidation, re-observation, bounded replanning, loop detection |
| Methods | `B3`, `V0R0`, `V1R0`, `V1R1` |
| Experiments | N1 evidence corruption, N2 fixed interventions |
| Evaluation | Immutable manifests, exact evaluator oracle, metrics, paired bootstrap CIs |
| Engineering | Typed contracts, CI, tests, JSONL trace, fresh reproduction |
| Transfer | Habitat adapter mapping + practical go/no-go decision |

### 5.2. Post-core conditional scope

Các mục sau chỉ được mở sau `G5`, không có scheduled hours trong 120 team-hours:

1. `confidence-only` và `consistency-only` component ablations;
2. object-relative spatial grounding micro-benchmark;
3. conditional-instruction `TaskMonitor` micro-benchmark;
4. Habitat runtime installation smoke test;
5. RGB local observation adapter smoke test.

### 5.3. Explicitly excluded trong tháng đầu

- Fine-tune hoặc evaluate VLM lớn.
- Direct LLM planner/reactive LLM baseline.
- PPO/DRL training.
- ASP hoặc contingent planner.
- Plan cache.
- `PutNext`, `drop`, multi-object manipulation.
- Multi-agent navigation.
- ROS/robot thật/sim-to-real.
- Habitat production integration.
- So sánh trực tiếp SR với benchmark 3D khác protocol.

### 5.4. Permitted claim

> Giai đoạn 2D đánh giá tính khả thi, failure modes và practical effect của validation-before-planning cùng execution-aware replanning trong một neuro-symbolic VLN architecture sử dụng local semantic observations.

### 5.5. Non-claims

Kết quả tháng đầu không chứng minh:

- RGB/VLM perception hoạt động;
- confidence đã calibrated cho real visual models;
- open-vocabulary hoặc natural-language generalization;
- explanation hữu ích với con người;
- contingent planning;
- performance trong Habitat;
- 2D→3D transfer đã thành công.

---

## 6. Phase 0: repository, environment, security và readiness

Phase 0 diễn ra **trước khi Member A hoặc B bắt đầu task implementation trong handbook**. Mục tiêu là tạo một nơi làm việc an toàn, có thể review và có cùng toolchain; Phase 0 không thay thế `A-01`/`B-01`, vốn tạo tracked package scaffold, shared contracts và CI để đóng `G0`.

### 6.1. Ranh giới `R0` và `G0`

| Gate | Thời điểm | Chứng minh điều gì |
|---|---|---|
| `R0 — Pre-handbook readiness` | Trước Day 1 | Remote/access/protection/security/toolchain/docs/work board đã sẵn sàng để hai người bắt đầu |
| `G0 — Secure reproducible scaffold` | Sau `A-01` + `B-01` | Package metadata, lockfile, contracts, CI và skeleton tests thực sự hoạt động |

Không đưa việc viết feature code vào `R0`; không hạ `G0` thành checklist hành chính.

### 6.2. Chuẩn bị GitHub repository

Repository owner và cả hai thành viên thực hiện joint checkpoint sau:

1. Xác nhận đúng GitHub remote, default branch và quyền `read/write/review` của A/B.
2. Dùng `main` làm protected integration branch cho fresh remote; nếu remote chủ ý dùng `master`, áp dụng cùng protection và ghi ADR, không rename tùy tiện.
3. Cấm direct push vào integration branch; yêu cầu PR, một approval từ thành viên còn lại và required CI checks trước merge.
4. Bật GitHub Actions. Bật secret scanning/Dependabot nếu account/repository hỗ trợ; nếu không, ghi công cụ local/CI tương đương.
5. Tạo milestones `M0`–`M5`, labels tối thiểu và Issue cho mọi task trong hai handbook trước khi task chuyển `In Progress`.
6. Ghi owner/reviewer/dependencies/handoff ID trên từng Issue; joint task phải có driver/support và merge order.
7. Tạo baseline tag hoặc ghi baseline commit SHA trước implementation; không tag trạng thái chứa secret.
8. Xác nhận master và hai handbook được Git track, không bị `.gitignore` che như quy định ở Section 0.4.

Minimum verification:

```bash
git remote -v
git branch --show-current
git status --short
git ls-files --error-unmatch docs/neuro_symbolic_vln_2d_complete_implementation_plan.md
git ls-files --error-unmatch docs/member_a_implementation_handbook.md
git ls-files --error-unmatch docs/member_b_implementation_handbook.md
```

Nếu dùng GitHub CLI, `gh repo view` và `gh api` có thể dùng để lưu evidence về default branch/protection. Không coi local branch name là bằng chứng remote protection.

### 6.3. Blocking security actions

Trước khi clone/config được dùng cho development:

1. Owner revoke/rotate mọi credential đã từng nằm plaintext trong local project configuration.
2. Không chép credential value, private endpoint hoặc local config vào issue, PR, commit, log hay tài liệu.
3. Kiểm tra credential có từng được track bằng history/path scan; chỉ history-rewrite khi có evidence và owner phê duyệt.
4. `.gitignore` tối thiểu phải loại `.claude/`, `.env*` trừ `.env.example`, `.venv/`, Python/tool caches, coverage, `runs/`, `artifacts/` và logs; **không được ignore ba tài liệu authoritative**.
5. Repository chỉ chứa `.env.example` với key names/placeholders, không chứa secret value.
6. Chạy secret scan trên tracked files và history phù hợp trước kickoff.
7. Oracle-only sidecars, privileged state và raw experiment outputs không được đưa vào normal agent input hoặc public artifact ngoài policy.

### 6.4. Chuẩn bị local toolchain

Cả hai máy phát triển phải có:

- Git và quyền truy cập remote;
- Python `>=3.12,<3.13`;
- `uv` phù hợp lock/sync workflow;
- khả năng chạy GitHub-required checks cục bộ;
- đủ disk/runtime cho MiniGrid smoke runs và khoảng 1.120 final core rows;
- không dựa vào global site-packages hoặc untracked local patches.

Chốt các quyết định scaffold dùng trong `A-01`/`B-01`:

- `hatchling` + `src/` package layout;
- `minigrid==3.1.0` và `pyperplan==2.1`;
- pytest/pytest-cov, Ruff và strict mypy;
- CLI `ns-vln` và GitHub Actions CI;
- exact dependency lock do `A-01`/`B-01` tạo và review.

Preflight không yêu cầu package đã tồn tại. Nó chỉ yêu cầu toolchain nền có thể gọi được:

```bash
python --version
uv --version
git --version
```

Nếu một thành viên chưa thể cài dependency do platform/network, Issue phải chuyển `Blocked` trước Day 1; không để họ phát triển dựa trên environment khác protocol.

### 6.5. Chuẩn bị collaboration board và kickoff

A/B phải **đọc** handbook và tạo planning Issues trước `R0`; lệnh cấm trước `R0` chỉ áp dụng cho việc chuyển implementation task sang `In Progress` hoặc sửa functional code.

Trước `R0`, cả hai phải:

1. Tạo/link Issues cho `A-01`…`A-J05` và `B-01`…`B-J04` từ handbook.
2. Gắn handoff `H01`–`H12`, milestone, owner, reviewer và dependency.
3. Chốt shared working hours/checkpoint tối thiểu cho Day 1, Day 5, Day 10, Day 15, Day 18 và Day 20.
4. Đọc Section 7–12 và xác nhận không có unresolved disagreement về trust boundary, canonical Protocols, statuses, evidence/commitment, semantics hoặc oracle separation.
5. Reconcile mọi contract/code excerpt lặp trong handbook với master: `PlanResult.status: PlanStatus`; A nhận đủ `Evidence`/`Provenance`; `EnvironmentAdapter.reset(EpisodeSpec)`; `TaskVerifier.evaluate() -> VerificationResult`; exact commitment/staleness/loop rules; SPL/SOPE denominator semantics; và full trace DTO gồm `oracle_input`. Handbook sample chỉ là implementation aid, không được làm yếu contract.
6. Lập config ownership map trước lần dùng đầu tiên: smoke config phải thuộc `H01/G0`; diagnostic config trước `G3`; final RQ configs trước `G4`.
7. Xác nhận phase cut: tasks qua A-07/B-09/J03 kết thúc Phase 1; A-J04/A-J05/B-J04 là Phase-2 runbooks.
8. Chốt nơi lưu ADR, validation evidence và immutable experiment hashes.
9. Tạo một `status:decision-needed` Issue cho mọi điểm chưa chốt; blocker về docs/contracts/config/security không được defer sang sau implementation.

### 6.6. `R0` pass criteria — được phép mở handbook

`R0` chỉ PASS khi toàn bộ điều sau có evidence:

- A/B truy cập được remote và review PR.
- Integration branch có protection policy đã xác nhận.
- Credential cần thiết đã rotate/revoke; secret scan không phát hiện tracked secret chưa xử lý.
- `.gitignore` loại local secrets/outputs nhưng không loại master hoặc hai handbook.
- Ba authoritative docs được Git track và có reviewable baseline commit.
- Python/uv/Git preflight chạy trên cả hai máy.
- Task Issues, owners, reviewers, milestones và handoff dependencies đã tồn tại; `A-01`/`B-01` Issues ghi explicit dependency `R0`.
- Handbook contract excerpts đã reconcile với canonical master Protocols; không còn `PlanStatus`/adapter/verifier/trace schema discrepancy chưa có resolution.
- Smoke/diagnostic/RQ config ownership đã có producer, consumer và required gate.
- Không còn unresolved security, docs, shared-contract hoặc config blocker.

Sau `R0`, mỗi thành viên mới mở handbook của mình và bắt đầu:

- A: [`Task A-01 — Secure fresh scaffold`](member_a_implementation_handbook.md#task-a-01-secure-fresh-scaffold)
- B: [`Task B-01 — Shared contracts, static config và CI`](member_b_implementation_handbook.md#task-b-01-shared-contracts-static-config-và-ci)

### 6.7. `G0` pass criteria — scaffold sau hai task đầu

`G0` PASS khi `A-01` và `B-01` đã integration-review và:

- fresh project metadata, `uv.lock`, README, package skeleton và CI tồn tại;
- shared contracts compile/import và contract tests pass;
- tracked config schema/defaults và smoke config tồn tại trước A-J01/B-J01; diagnostic/RQ config owners đã được ghi;
- `uv sync`, Ruff, strict mypy và skeleton pytest pass trên fresh checkout;
- CI dùng cùng commands/lockfile với local verification;
- không restore bootstrap cũ hoặc native probes bằng copy mù; mọi regression probe được viết lại và review;
- `H01` hoàn tất với commit/artifact links.

Không bắt đầu `A-02`/`B-02` hoặc feature work downstream trước `G0`.

---

## 7. Trust boundary và kiến trúc end-to-end

### 7.1. Agent-visible path

```text
Instruction ───────────────> InstructionParser ──────> GoalProgram
Local categorical view ───> ObservationDecoder ─────> Evidence
Action/proprioception ──────────────────────────────> EvidenceStore
                                                        |
                                                        v
                                                   BeliefMap
                                           TRUE / FALSE / UNKNOWN
                                    reliability + staleness + provenance
                                                        |
                                                        v
                                                   Validator
                                                        |
                                                        v
                                           CommittedPlanningState
                                                        |
                         missing information? ----------+---------- sufficient?
                                  |                                 |
                                  v                                 v
                    TaskMonitor / FrontierExplorer          PDDLSerializer
                                  |                                 |
                         exploration/re-observation                 v
                                  |                          PyperplanAdapter
                                  |                                 |
                                  +--------------------------> PlanResult
                                                                    |
                                                                    v
                                                               Controller
                                                                    |
                                                                    v
                                                         EnvironmentAdapter
                                                                    |
                                                         ExecutionMonitor
                                                                    |
                                            belief update / re-observe / replan
```

### 7.2. Evaluation-only path

```text
EvaluationOracle
  ├── inspect full simulator state
  ├── verify task solvability
  ├── compute optimal grid/primitive costs
  ├── annotate oracle predicates
  ├── validate plans against true state
  ├── pre-generate recoverable interventions
  └── provide oracle-derived committed state to B3 only
```

### 7.3. Trust rules

- Normal agent constructor không nhận `EvaluationOracle`.
- Core agent modules không import `evaluation.oracle`.
- `B3` là deliberate, tagged exception; B3 logs phải ghi `oracle_input=true`.
- Agent-visible `StepResult` được phép chứa actuator feedback như moved/blocked/pickup/toggle success, nhưng không chứa hidden object positions hoặc full grid.
- `TaskVerifier` có thể dùng authoritative environment state để quyết định terminal success, nhưng chỉ trả verifier result; nó không cung cấp planning facts.
- Evaluation-only sidecar không được nằm trong normal episode input object.

---

## 8. Typed contracts và symbolic data model

Code dưới đây là contract skeleton để hai thành viên thống nhất interfaces. Implementation có thể chia file nhưng không được tự ý đổi tên/signature sau interface freeze nếu chưa có cross-review.

### 8.1. Core identifiers và enums

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

LocationId = str
HeadingId = str
EntityId = str
EvidenceId = str


class TriValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class ParseStatus(str, Enum):
    DETERMINISTIC = "deterministic"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class GroundingStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class PlanStatus(str, Enum):
    FOUND = "found"
    ALREADY_SATISFIED = "already_satisfied"
    NEEDS_INFORMATION = "needs_information"
    NO_PLAN_KNOWN_SPACE = "no_plan_known_space"
    UNSUPPORTED_GOAL = "unsupported_goal"
    TIMEOUT = "timeout"
    SERIALIZATION_ERROR = "serialization_error"
    PLANNER_ERROR = "planner_error"


class EpisodeOutcome(str, Enum):
    SUCCESS = "success"
    UNSUPPORTED_INSTRUCTION = "unsupported_instruction"
    AMBIGUOUS_GROUNDING = "ambiguous_grounding"
    FRONTIER_EXHAUSTED = "frontier_exhausted"
    KNOWN_SPACE_DISCONNECTED = "known_space_disconnected"
    BELIEF_CONFLICT_UNRESOLVED = "belief_conflict_unresolved"
    PLANNER_TIMEOUT = "planner_timeout"
    PLANNER_ERROR = "planner_error"
    REPLAN_BUDGET_EXHAUSTED = "replan_budget_exhausted"
    LOOP_DETECTED = "loop_detected"
    ACTION_BUDGET_EXHAUSTED = "action_budget_exhausted"
    ENVIRONMENT_TERMINATED_FAILURE = "environment_terminated_failure"
```

Không dùng catch-all `FAILED`.

### 8.2. Atoms, evidence và belief

```python
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
```

Commitment rule:

```text
BeliefRecord.value == TRUE
AND stale == False
AND validator decision == ACCEPTED
AND all required arguments are grounded
→ fact may enter CommittedPlanningState.true_facts
```

`FALSE` và `UNKNOWN` không bị xóa khỏi belief; chúng chỉ không được serialize như true PDDL facts.

### 8.3. Environment/evaluator boundary

```python
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
    # MiniGrid axes are preserved explicitly as [x][y].
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


class EnvironmentAdapter(Protocol):
    def reset(self, episode: EpisodeSpec) -> ObservationPacket: ...
    def step(self, action: PrimitiveAction) -> StepResult: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class PerturbationSpec:
    intervention_id: str
    checkpoint: str


@dataclass(frozen=True)
class OracleSolution:
    solvable: bool
    optimal_primitive_actions: int | None
    optimal_grid_distance: int | None


@dataclass(frozen=True)
class EpisodeTrace:
    episode_id: str
    method: str
    records: tuple[Mapping[str, object], ...]
    terminal_outcome: EpisodeOutcome


@dataclass(frozen=True)
class OracleAnnotations:
    oracle_plan_valid: bool | None
    oracle_predicate_labels: Mapping[EvidenceId, bool]
    recovery_eligible: bool
    optimal_primitive_actions: int | None


class EvaluationOracle(Protocol):
    def solve(
        self,
        episode: EpisodeSpec,
        perturbation: PerturbationSpec | None = None,
    ) -> OracleSolution: ...

    def score_trace(self, trace: "EpisodeTrace") -> "OracleAnnotations": ...
```

### 8.4. Parser, validator và planner contracts

```python
@dataclass(frozen=True)
class GoalProgram:
    family: str
    ordered_subgoals: tuple[GroundAtom, ...]


@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    goal_program: GoalProgram | None
    alternatives: tuple[GoalProgram, ...]
    reason: str | None


class InstructionParser(Protocol):
    def parse(self, instruction: str) -> ParseResult: ...


class ValidationDisposition(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ValidationDecision:
    evidence_id: EvidenceId
    disposition: ValidationDisposition
    reason_code: str
    supporting_evidence_ids: tuple[EvidenceId, ...]
    conflicting_evidence_ids: tuple[EvidenceId, ...]


class Validator(Protocol):
    def validate(
        self,
        evidence: tuple[Evidence, ...],
        belief: Mapping[GroundAtom, BeliefRecord],
        current_step: int,
    ) -> tuple[ValidationDecision, ...]: ...


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


class PlannerAdapter(Protocol):
    def plan(
        self,
        state: CommittedPlanningState,
        goal: GoalProgram,
    ) -> PlanResult: ...
```

### 8.5. Decoder, EvidenceStore, TaskMonitor và TaskVerifier

```python
@dataclass(frozen=True)
class SensorModelSpec:
    sensor_model_id: str
    corruption_channel: str | None


class ObservationDecoder(Protocol):
    def decode(
        self,
        observation: ObservationPacket,
        sensor_model: SensorModelSpec,
    ) -> tuple[Evidence, ...]: ...


class EvidenceStore(Protocol):
    def append(self, evidence: tuple[Evidence, ...]) -> None: ...
    def snapshot(self) -> tuple[Evidence, ...]: ...


class AgentDecisionType(str, Enum):
    PLAN = "plan"
    EXPLORE = "explore"
    REOBSERVE = "reobserve"
    REPLAN = "replan"
    VERIFY = "verify"
    TERMINATE = "terminate"


@dataclass(frozen=True)
class AgentDecision:
    decision_type: AgentDecisionType
    reason_code: str
    target_location: LocationId | None = None
    terminal_outcome: EpisodeOutcome | None = None


class TaskMonitor(Protocol):
    def decide(
        self,
        goal: GoalProgram,
        grounding_status: GroundingStatus,
        state: CommittedPlanningState,
        last_plan: PlanResult | None,
        last_step: StepResult | None,
    ) -> AgentDecision: ...


@dataclass(frozen=True)
class VerificationResult:
    task_success: bool
    terminated: bool
    reason_code: str


class TaskVerifier(Protocol):
    def evaluate(self) -> VerificationResult: ...
```

- `TaskMonitor` là agent-side believed progress; nó chọn parse/ground/plan/explore/re-observe/replan/verify/terminate.
- `TaskVerifier` là authoritative environment-side success contract; nó chỉ trả verifier result, không cung cấp planning facts.
- `ObservationDecoder` chỉ nhận `ObservationPacket`; `EvaluationOracle` không xuất hiện trong signature.

Gộp `TaskMonitor` và `TaskVerifier` sẽ tạo oracle leakage hoặc làm believed progress bị nhầm với true task completion.

---

## 9. Instruction grammar và grounding

### 9.1. Core grammar

```ebnf
instruction        = goto_instruction | key_door_instruction ;

goto_instruction   = goto_verb, " the ", color, " ", object_type ;
goto_verb          = "go to" | "find" | "move to" ;

key_door_instruction
                   = pickup_clause, ", ", open_clause, ", then ", goal_clause ;
pickup_clause       = "pick up the ", color, " key" ;
open_clause         = "open the ", color, " door" ;
goal_clause         = "go to the goal" | "reach the goal" ;

color               = "red" | "green" | "blue" | "yellow" | "purple" | "grey" ;
object_type         = "ball" | "box" | "key" ;
```

Punctuation/case normalization được phép nhưng phải deterministic và test được.

### 9.2. Parser output

- `DeterministicParse`: duy nhất một `GoalProgram`.
- `AmbiguousParse`: nhiều grounding candidates hoặc ordered clauses mâu thuẫn.
- `UnsupportedParse`: ngoài grammar hoặc yêu cầu action/task không hỗ trợ.
- Không có parser confidence float.

### 9.3. Curated 40-case suite

| Loại | Số lượng | Kỳ vọng |
|---|---:|---|
| Supported paraphrases cho GoTo | 12 | Cùng canonical GoalProgram |
| Supported paraphrases cho key-door | 12 | Cùng ordered GoalProgram |
| Deliberately ambiguous | 8 | `AMBIGUOUS` đúng reason code |
| Unsupported/malformed | 8 | `UNSUPPORTED` đúng reason code |

Ví dụ ambiguous:

- “Go to the key” khi có nhiều key khác màu.
- “Open the red door then open the blue door” trong core task chỉ hỗ trợ một door sequence.
- “Pick up the red key and the blue key” khi agent chỉ carry một object.

Ví dụ unsupported:

- “Go to the object left of the yellow box.”
- “If you see a blue door, use it; otherwise use the red door.”
- “Put the green ball next to the box.”

Các unsupported examples không được tính là navigation failure; chúng là parser/component outcomes.

### 9.4. Grounding rules

- Core generator bảo đảm unique type-color target.
- Object identity không dùng descriptor string như `red_key` làm unique ID; dùng `EntityId` riêng.
- Grounding trả `RESOLVED`, `AMBIGUOUS` hoặc `UNRESOLVED`.
- Khi target chưa quan sát, goal semantics vẫn được biết từ instruction nhưng entity binding ở trạng thái `UNRESOLVED`; `TaskMonitor` phải explore, không fabricate target location.

---

## 10. Local observation, evidence và tri-valued belief

### 10.1. Sensor regimes

| Regime | Ai được dùng | Ý nghĩa |
|---|---|---|
| `oracle_state` | B3/evaluator only | Full simulator truth; không phải perception result |
| `categorical_partial` | Core local methods | Exact egocentric object/color/state encoding trước N1 |
| `rgb_partial` | Post-core only | Rendered RGB pixels; không nằm trong primary results |

Không dùng `FullyObsWrapper`, `SymbolicObsWrapper`, hidden object positions hoặc global map trong `V0R0/V1R0/V1R1`.

### 10.2. Local frame và dead reckoning

- Tại reset, agent tạo internal origin `loc_0`; đây không phải simulator global coordinate.
- Heading từ observation/proprioception được phép dùng.
- Internal pose cập nhật khi `StepResult.action_succeeded` xác nhận move.
- Blocked move giữ internal location, đồng thời tạo negative/uncertain evidence cho predicted traversability tùy visibility.
- Egocentric cells được transform vào episode-local frame.
- Trong core static world, entity identity có thể gắn với internal location + first-seen track ID; tài liệu thừa nhận data association 3D chưa được giải quyết.

### 10.3. Tri-valued semantics

| Trạng thái | Nghĩa | PDDL behavior |
|---|---|---|
| `TRUE` | Có accepted evidence hiện hành | Có thể serialize như positive fact |
| `FALSE` | Có accepted negative evidence trong observed coverage | Không serialize như true; dùng positive complement predicate khi domain cần |
| `UNKNOWN` | Chưa thấy, evidence bị drop, stale hoặc conflict chưa giải quyết | Không được hiểu là false/free; trigger information policy nếu required |

### 10.4. Staleness policy tháng đầu

- Static wall topology và immutable type/color: không expire trừ khi contradicted bởi observed coverage.
- Agent pose và carrying state: cập nhật mỗi action feedback.
- Door state và mutable traversability: stale sau 3 steps ngoài field of view.
- Unexpected action outcome: affected facts chuyển `UNKNOWN` ngay, sau đó re-observe.
- Stale evidence vẫn giữ provenance nhưng không được commit.

### 10.5. Validator layers

1. **Transport/schema:** arity, parseable identifiers, finite reliability range; dùng chung cho mọi method để pipeline không crash.
2. **Type/ontology:** predicate arguments đúng types; không `open(ball)`.
3. **Uniqueness/exclusivity:** một robot location, tối đa một held object, một door state, immutable type/color.
4. **Spatial/occupancy:** `passable` không cùng thời điểm với wall/closed door/non-overlap blocker.
5. **Temporal/staleness:** dynamic fact quá hạn không được commit.
6. **Reliability:** threshold dev-frozen.
7. **Conflict resolution:** reject/uncertain dựa trên evidence order, reliability và reason codes; không silently keep cả hai facts.

### 10.6. Baseline pass-through policy

`V0R0` vẫn dùng transport/schema checks để tránh invalid serialization, nhưng:

- bỏ qua reliability threshold;
- không chạy ontology/consistency rules ngoài typing tối thiểu của serializer;
- latest well-typed observation wins cho singular dynamic attributes;
- unknown vẫn là unknown;
- không dùng execution-aware replanning.

Điều này là “no validation-before-planning” theo research definition, không phải “cho phép malformed PDDL”.

---

## 11. MiniGrid semantics, positive STRIPS và pyperplan

### 11.1. Primitive actions

Core primitive actions:

- `turn_left`
- `turn_right`
- `move_forward`
- `pickup`
- `toggle`

Không dùng `Actions.done` làm success action.

### 11.2. Native semantics contract

1. `pickup` tác động front cell.
2. `toggle` tác động front cell.
3. Matching carried key unlock/open locked door.
4. Forward vào blocker không đổi position.
5. `Actions.done` không tự tạo reward/termination/success.
6. `GoTo` non-overlap object thành công khi adjacent + facing.
7. Overlap goal tile thành công khi agent ở goal location.
8. Key-door task verifier yêu cầu pickup matching key → open matching door → reach goal.

### 11.3. PDDL feature constraints

Domain chỉ dùng:

```lisp
(:requirements :strips :typing)
```

Không dùng negative preconditions, disjunction, conditional effects, derived predicates, numeric fluents/action costs, quantified effects hoặc sensing/contingent branches. Delete effects được phép và bắt buộc.

### 11.4. Minimal predicates

```text
robot-at(robot, location)
facing(robot, heading)
turn-left-of(heading_from, heading_to)
turn-right-of(heading_from, heading_to)
front-cell(location_from, heading, location_to)
passable(location)
key-at(key, location)
door-at(door, location)
goal-at(goal, location)
handempty(robot)
holding(robot, key)
door-locked(door)
door-open(door)
key-opens(key, door)
target-at(target, location)
task-satisfied()
```

### 11.5. Normative action requirements

Master chỉ khóa semantics chung; exact PDDL implementation và failing tests thuộc [`B-02`](member_b_implementation_handbook.md#task-b-02-locationgraph-positive-strips-và-pyperplan-adapter), còn native execution validation thuộc [`A-02`](member_a_implementation_handbook.md#task-a-02-minigrid-adapter-core-tasks-và-taskverifier).

| Action | Preconditions bắt buộc | Effects/invariants bắt buộc |
|---|---|---|
| `turn-left` / `turn-right` | Robot ở một location và có heading hiện hành | Chỉ heading đổi theo declared relation; location giữ nguyên |
| `move-forward` | `front-cell(from, heading, to)` và `passable(to)` | Xóa `robot-at(from)`, thêm `robot-at(to)` |
| `pickup-key` | Key ở front cell, robot `handempty` | Key rời location, `handempty` bị xóa, `holding` được thêm |
| `toggle-locked-door` | Matching carried key, locked door ở front cell | `door-locked` bị xóa, `door-open` và `passable` được thêm |
| `confirm-goto` | Robot adjacent + facing đúng target | Chỉ tạo symbolic `task-satisfied`; không map thành primitive action |

Mọi domain variant phải giữ orientation, front-cell semantics và delete effects; không được rút gọn bằng hidden controller correction.

### 11.6. GoTo goal compilation

Positive STRIPS không biểu diễn tiện một existential goal “đứng ở bất kỳ approach pose nào”. Dùng non-primitive confirmation action:

```lisp
(:action confirm-goto
 :parameters (?r - robot ?t - target ?from ?target-loc - location ?h - heading)
 :precondition (and
   (robot-at ?r ?from)
   (facing ?r ?h)
   (front-cell ?from ?h ?target-loc)
   (target-at ?t ?target-loc))
 :effect (task-satisfied))
```

- PDDL goal là `(task-satisfied)`.
- `confirm-goto` không map sang MiniGrid primitive action.
- Khi plan tới confirmation step, controller gọi `TaskVerifier`.
- Confirmation action không tính vào primitive action count/SOPE.

Key-door goal có thể dùng tương tự hoặc goal condition `robot-at(goal_location)`; verifier vẫn là authoritative source.

### 11.7. Pyperplan policy

- Search core: breadth-first search cho small unit-cost state spaces.
- Planner call chạy trong isolated worker/process với timeout 2 giây.
- Trả typed `PlanStatus`, không biến timeout/parse/grounding error thành no-plan.
- Online PDDL plan không được gọi là global optimum; exact evaluator optimum là metric-only.

### 11.8. Regression contract

Exact test code nằm trong [`A-02`](member_a_implementation_handbook.md#task-a-02-minigrid-adapter-core-tasks-và-taskverifier) và được B cross-validate với [`B-02`](member_b_implementation_handbook.md#task-b-02-locationgraph-positive-strips-và-pyperplan-adapter). Bộ regression tối thiểu phải chứng minh:

1. pickup/toggle tác động front cell;
2. blocked forward không đổi pose;
3. matching key unlock/open đúng door;
4. non-overlap GoTo dùng adjacent + facing;
5. overlap goal dùng exact occupied location;
6. `Actions.done` không được coi là success;
7. symbolic action mapping executable bằng native controller;
8. normal agent path không đọc `env.unwrapped` hoặc privileged state.

Deterministic probe/evaluator tests được phép dùng `env.unwrapped`; normal-path unit/integration tests thì không.

---

## 12. Exploration, re-observation và execution-aware replanning

### 12.1. Frontier definition

Một frontier là known traversable `LocationId` kề ít nhất một unknown location trong internal map.

### 12.2. Deterministic frontier selection

Tie-break theo thứ tự:

1. shortest known primitive plan tới frontier;
2. earliest discovery step;
3. lexicographic `LocationId`.

Tại frontier, agent thực hiện một heading sweep bao phủ các heading bins chưa quan sát. Không lặp sweep nếu không có state change.

### 12.3. Planning/exploration decision

```text
Goal unresolved or required route unknown
  ├── frontier exists -> navigate/explore/re-observe
  └── no frontier -> FRONTIER_EXHAUSTED

Goal resolved and known-space plan exists
  └── execute plan

Goal resolved but no known-space plan
  ├── frontier exists -> explore
  └── no frontier -> KNOWN_SPACE_DISCONNECTED
```

### 12.4. Replanning triggers

- New accepted evidence invalidates unexecuted precondition.
- `StepResult.action_succeeded` khác predicted effect.
- Door/traversability/carrying fact trở stale hoặc contradicted.
- Target grounding thay đổi.
- TaskVerifier bác expected confirmation.
- Planned action không còn applicable trong committed state.

### 12.5. Recovery sequence

1. Record failed action, expected effect và implicated facts.
2. Mark implicated mutable facts `UNKNOWN` hoặc conflicted.
3. Re-observe current/front cells; nếu chưa đủ, chọn bounded observation action.
4. Run validator.
5. Build new `CommittedPlanningState` với incremented version/hash.
6. Call pyperplan từ current believed pose.
7. Resume execution hoặc terminate bằng typed outcome.

### 12.6. Hard bounds

- Maximum replans: 5/episode.
- Planner timeout: 2 seconds/call.
- Maximum identical no-progress signatures: 2.
- Signature: `(active_goal, committed_state_hash, pose, plan_status)`.
- Maximum heading sweeps: 1/frontier visit.
- Public primitive action budget:

\[
Budget_i=\min(4A_i^*+20,256)
\]

`A_i^*` nằm trong evaluation-only sidecar; agent chỉ nhận public integer budget giống nhau cho all methods.

---

## 13. Hai benchmark channels độc lập

### 13.1. N1 — Evidence corruption cho RQ1

#### Injection point

Corruption được áp dụng **sau exact categorical decoding, trước EvidenceStore**. World không đổi. Frozen planning checkpoint và uncorrupted evidence hash được lưu trong sidecar.

#### Conditions

| Condition | Quy tắc | Semantics |
|---|---|---|
| `clean` | Không thay đổi evidence | reliability `1.0` |
| `N1-DROP-15` | Drop 15% eligible records | Record vắng mặt; corresponding belief là unknown nếu không có support khác |
| `N1-FLIP-10` | Attribute/predicate substitution trên 10% eligible records | Có thể tạo false fact hoặc conflict |

Eligible facts:

- visible object type/color;
- visible occupancy/traversability;
- visible door state;
- visible object location trong internal map.

Không corrupt parser output trong primary RQ1.

#### Synthetic reliability score model

Đây là declared PoC mechanism, không phải claim về calibration của real perception:

- clean condition: score `1.0`;
- trong `N1-FLIP-10`, evaluator tạo score bằng seeded overlapping distributions:
  - correct retained record: `Beta(8, 2)`;
  - flipped record: `Beta(3, 5)`;
- clip score vào `[0.05, 0.99]`;
- seed và distribution version được lưu manifest;
- agent thấy score nhưng không thấy hidden correctness label.

Threshold chỉ chọn từ `{0.50, 0.70, 0.90}` trên dev. Báo cáo calibration/risk-coverage chỉ có ý nghĩa trong declared synthetic model.

#### Primary RQ1 execution

- Compare `V0R0` và `V1R0`.
- Replanning off.
- Cho phép một-shot execution của returned plan trong unchanged world.
- `NEEDS_INFORMATION` và `NO_PLAN_KNOWN_SPACE` là valid statuses, không tự động coi là crash.

### 13.2. N2 — Fixed world/execution interventions cho RQ2

Evidence sạch trước intervention. Mỗi intervention được pre-generate và oracle xác nhận post-intervention solvable.

#### Navigation intervention

- Sau initial plan, ngay trước một manifest-designated `move-forward`, next planned location bị chuyển thành blocked.
- Alternate route phải tồn tại.
- `V1R0` và `V1R1` có cùng initial plan hash và execution prefix.

#### Key-door intervention

- Sau successful door toggle, ngay trước first crossing của door cell, evaluator close/re-lock door.
- Matching key vẫn được carried.
- Task vẫn recoverable.

#### Rules

- Không chọn intervention adaptively theo later method behavior.
- Không trộn evidence corruption.
- Intervention target/checkpoint/seed nằm trong sidecar.
- Oracle lưu pre/post optimum và recoverability.

---

## 14. Baselines và causal method matrix

| ID | Input | Validation | Frontier trước first plan | Replanning sau mismatch | Vai trò |
|---|---|---:|---:|---:|---|
| `B3` | Oracle-derived committed state | N/A | Không cần cho known full map | Off | Planner/controller feasibility baseline |
| `B4 / V0R0` | Local evidence | Off | On | Off | Minimal local symbolic baseline |
| `B5-no-replan / V1R0` | Local evidence | On | On | Off | RQ1 treatment, RQ2 comparator |
| `B5 / V1R1` | Local evidence | On | On | On | Full proposed architecture |

Tất cả methods dùng chung:

- instruction parser;
- task generator/verifier;
- PDDL domain và pyperplan adapter;
- primitive controller;
- episode/action budgets;
- manifest seeds;
- success semantics;
- trace schema.

`B3` phải gọi là **oracle-input planning baseline**, không gọi là upper bound. Nó vẫn chịu domain/controller/verifier errors.

---

## 15. Episode generation, manifests và oracle

### 15.1. Core family: `goto_type_color`

- Unique type-color target.
- Có distractors khác type/color.
- Target là non-overlap object.
- Success: target ở front cell tại current pose.
- Vary grid size, target type/color, distractor count, initial heading, initial visibility và topology.
- Generator phải reject ambiguous references và unsolvable layouts.

### 15.2. Core family: `key_door_goal`

- Một matching key và một locked door ngăn start khỏi goal.
- Có thể thêm non-matching distractor key/object nhưng không làm reference ambiguous.
- Topology bắt buộc pickup key và open door.
- Success sequence: carry matching key → door opened → agent reaches overlapable goal.
- Exact evaluator xác nhận task solvable và tính primitive optimum.

### 15.3. Public manifest

```yaml
schema_version: "1.0"
episode_id: "goto-test-0042"
family: "goto_type_color"
split: "rq1_test"
generator_version: "minigrid-core-v1"
seed: 420042
layout_hash: "sha256:PUBLIC_LAYOUT_HASH"
instruction: "Go to the green ball."
task_spec:
  target_type: "ball"
  target_color: "green"
condition:
  channel: "N1-FLIP-10"
  seed: 990042
public_action_budget: 84
config_hash: "sha256:PUBLIC_CONFIG_HASH"
```

### 15.4. Evaluation-only sidecar

```yaml
schema_version: "1.0"
episode_id: "goto-test-0042"
solvable: true
optimal_grid_distance: 11
optimal_primitive_actions: 17
oracle_target_entity_id: "entity-7"
observable_predicate_universe_hash: "sha256:PRIVATE_UNIVERSE_HASH"
uncorrupted_evidence_hash: "sha256:PRIVATE_EVIDENCE_HASH"
intervention: null
```

Sidecar không được load bởi B4/B5 constructors hoặc CLI config của normal runs.

### 15.5. Split và run matrix

| Suite | Base episodes | Crossings | Runs chính |
|---|---:|---|---:|
| Smoke | 10/family = 20 | Clean | CI/gates |
| Dev | 20/family = 40 | Declared dev conditions | Config selection |
| RQ1 test | 60/family = 120 | 3 N1 conditions × V0R0/V1R0 | 720 |
| B3 test | 120 | Clean oracle input | 120 |
| RQ2 test | 40/family = 80 | Fixed N2 × V1R0/V1R1 | 160 |
| Full V1R1 clean | 120 | Clean | 120 |
| Diagnostic | 24 targeted cases | Timeout/conflict/loop/no-plan | Engineering only |
| Parser | 40 strings | Component suite | Engineering only |

Final core experiment runs: khoảng **1.120**, chưa tính smoke/dev/diagnostic.

### 15.6. Manifest quality gates

- Canonical `layout_hash` không cross split.
- Mọi core episode solvable.
- Instruction phù hợp layout và unique reference.
- Oracle optimum nằm trong declared action budget.
- N2 post-intervention state vẫn solvable.
- Same episode-condition pair dùng cùng corruption/intervention seed giữa methods.
- Test manifests frozen trước final runs; semantic change yêu cầu version bump và rerun affected matrix.

---

## 16. Metrics và statistical protocol

### 16.1. Success Rate

\[
SR=\frac{\text{số episode thành công}}{\text{tổng episode}}
\]

Report theo method × family × condition, không chỉ pooled.

### 16.2. Grid SPL cho `goto_type_color`

\[
SPL_i=S_i\frac{L_i^*}{\max(L_i^*,L_i)}
\]

- `L_i^*`: oracle shortest grid-edge distance tới một valid adjacent-facing approach pose.
- `L_i`: executed successful forward transitions.
- Turns/interactions không tính vào grid distance.
- Primitive action count báo riêng để penalize spinning.

### 16.3. SOPE cho `key_door_goal`

\[
SOPE_i=S_i\frac{A_i^*}{\max(A_i^*,A_i)}
\]

- `A_i^*`: exact BFS optimum gồm turns, forward, pickup, toggle.
- `A_i`: tất cả attempted primitive actions.
- Confirmation actions không tính.
- Không báo SPL cho key-door.

### 16.4. Predicate metrics

Tại mỗi frozen RQ1 checkpoint, observable predicate universe chỉ gồm facts mà local sensor có quyền quan sát tới thời điểm đó.

- `Accepted Precision = accepted true facts / all accepted facts`.
- `Accepted Risk = 1 - Accepted Precision`.
- `Accepted Coverage = all accepted facts / eligible evidence-supported facts`.
- Predicate recall/F1 báo theo predicate family, không để `free/adjacent` facts áp đảo object/door facts.
- Unknown không tính là false positive hoặc true negative.

### 16.5. Plan validity

- **Believed-state plan validity:** simulate symbolic action preconditions/effects trên committed planning state.
- **Oracle-state plan validity:** map/simulate same plan trên true state tại checkpoint.
- Báo cả hai; chênh lệch phản ánh belief/model mismatch.

### 16.6. RQ2 metrics

- Recovery success trên oracle-confirmed recoverable interventions.
- Detection latency: số primitive actions từ intervention tới belief invalidation.
- Obsolete-plan safety: tỷ lệ intervention được phát hiện trước hai additional invalid actions.
- Replans per recovered episode.
- Planner latency p50/p95.
- Additional actions so với post-intervention optimum và paired unperturbed run.
- Loop/replan/action-budget termination rates.

### 16.7. Trace metrics

- Schema completeness: required fields present/valid.
- Replay fidelity: replay produces same decision, state/problem hashes và outcome classification.
- Không gọi metric này là human explainability score.

### 16.8. Statistical protocol

- Identical paired episode-condition units giữa methods.
- 10.000 stratified paired bootstrap resamples theo episode ID, stratify theo family/condition.
- Báo method value, paired delta và 95% percentile CI.
- Không retune threshold/budgets trên test.
- Không chỉ báo pooled result; luôn có per-family/per-condition tables.
- Không dùng một aggregate headline score.
- Practical thresholds đã pre-register quan trọng hơn post-hoc p-value hunting.

### 16.9. Dev selection

Chỉ tune:

- reliability threshold trong `{0.50, 0.70, 0.90}`;
- maximum re-observation attempts trong `{1, 2}`.

Selection rule:

1. accepted precision ≥90%;
2. invalid action rate ≤5%;
3. trong candidates đạt constraints, chọn accepted coverage cao nhất;
4. tie-break bằng key-door SOPE, sau đó ít primitive actions/replans hơn.

Nếu không configuration nào đạt constraints, ghi calibration gate failure và chọn highest accepted precision để hoàn tất diagnostic report; không sửa test protocol.

---

## 17. Traceability và reproducibility

### 17.1. JSONL trace contract

Mỗi primitive action record phải chứa:

```json
{
  "schema_version": "1.0",
  "episode_id": "goto-test-0042",
  "method": "V1R1",
  "oracle_input": false,
  "step": 17,
  "manifest_hash": "sha256:PUBLIC_MANIFEST_HASH",
  "config_hash": "sha256:PUBLIC_CONFIG_HASH",
  "instruction_parse": {
    "status": "deterministic",
    "goal_program_hash": "sha256:GOAL_HASH"
  },
  "observation_id": "obs-17",
  "evidence_ids": ["ev-101", "ev-102"],
  "belief_state_hash": "sha256:BELIEF_HASH",
  "committed_state_hash": "sha256:STATE_HASH",
  "validation": {
    "accepted": ["ev-101"],
    "rejected": [],
    "uncertain": ["ev-102"]
  },
  "problem_hash": "sha256:PDDL_HASH",
  "plan_status": "found",
  "symbolic_action": ["move-forward", "robot", "loc-3", "loc-4", "east"],
  "primitive_action": "move_forward",
  "action_succeeded": false,
  "failure_reason": "blocked",
  "monitor_decision": "invalidate_and_reobserve",
  "replan_reason": "predicted_move_failed",
  "task_success": false,
  "episode_outcome": null
}
```

`oracle_input` là required boolean trên mọi primitive record: `true` chỉ cho tagged B3 oracle-input runs, `false` cho V0R0/V1R0/V1R1. Thiếu field hoặc B3/local mismatch là schema/leakage failure, không được suy luận từ method name hậu kỳ.

Exact frozen DTO/serializer tests trong `B-08` phải bao phủ toàn bộ fields của contract này; sample rút gọn không được dùng làm schema thay thế.

### 17.2. Run artifact layout

```text
runs/<run_id>/
├── resolved_config.yaml
├── manifest_hashes.json
├── results.csv
├── summary.json
├── traces/
│   └── <episode_id>.jsonl
├── problems/
│   └── <problem_hash>.pddl
└── environment.json
```

`runs/` bị ignore; aggregate result tables cần publication thì copy có chủ ý sang tracked `reports/` sau review.

### 17.3. Reproduction acceptance contract

Master không khóa exact CLI sequence; exact commands được implementation và review trong [`A-07`](member_a_implementation_handbook.md#task-a-07-metrics-experiment-runner-và-frozen-runs), [`A-J04`](member_a_implementation_handbook.md#task-a-j04-fresh-checkout-reproduction) và [`B-J04`](member_b_implementation_handbook.md#task-b-j04-reproduction-docs-rq-interpretation-và-final-habitat-decision), rồi README trở thành operator entrypoint.

Bất kể CLI spelling thay đổi, reproduction phải có một documented sequence chứng minh:

1. sync từ tracked metadata/lock trong fresh environment;
2. static checks và full test suite PASS;
3. public manifests có thể generate/verify bằng frozen config và hash;
4. smoke, RQ1 và RQ2 evaluation entrypoints tồn tại;
5. summaries được tạo từ raw rows/traces mà không đọc agent-forbidden sidecars;
6. command/config/schema changes được update đồng thời trong README, CI và affected handbook task;
7. Phase-2 fresh-clone operator có thể chạy sequence mà không dùng untracked local knowledge.

Config ownership phải có trước lần dùng đầu tiên: smoke config thuộc `H01/G0`; diagnostic và final RQ configs phải được producer/consumer handoff trước `G3/G4`. Không cho validation command tham chiếu một config chưa có named owner và tracked schema.

---

## 18. Shared module boundaries và source layout

Master chỉ khóa **module boundaries** để ngăn coupling/oracle leakage. Exact files cần tạo cho từng task nằm trong hai handbook và được phép thay đổi qua cross-reviewed PR nếu không phá boundary.

### 18.1. Required repository roots

```text
.github/workflows/   # CI only
docs/                # master + A/B handbooks + ADR/research docs
configs/             # smoke/dev/frozen experiment configs
data/manifests/      # tracked public immutable manifests
reports/             # reviewed aggregate research artifacts
src/neuro_symbolic_vln/
tests/
```

`runs/`, raw `artifacts/`, local secrets và evaluator-private sidecars tuân theo ignore/publication policy; không copy chúng vào tracked paths chỉ để tiện review.

### 18.2. Normative boundaries

| Boundary | Trách nhiệm | Cấm |
|---|---|---|
| `contracts` | Stable shared IDs, dataclasses, enums và Protocols | MiniGrid implementation hoặc privileged evaluator fields |
| `env` | Environment adapter, task definitions và authoritative verifier | Xuất hidden state thành planning facts |
| `perception` | Local `ObservationPacket` → `Evidence` | Đọc simulator internals/oracle |
| `language` | Deterministic instruction → typed parse/goal | Fabricate grounding/location chưa quan sát |
| `belief` | EvidenceStore, tri-valued state, validation/commitment | Serialize raw observation trực tiếp thành PDDL |
| `planning` | LocationGraph, positive STRIPS, serializer, pyperplan adapter | Import MiniGrid hoặc dùng global coordinates |
| `control` | Frontier, primitive mapping, expected-vs-observed monitor | Inspect global state hoặc sửa belief không qua contract |
| `evaluation` | Oracle, manifests, N1/N2, metrics và runner | Được import/construct từ normal agent path |
| `agent` | Orchestration qua interfaces | Chứa domain-specific parser/validator/oracle shortcuts |
| `trace` | Append-only schema, hashes và replay | Silent schema mutation hoặc untyped catch-all failure |

### 18.3. Ownership routing

- Environment/Control/Evaluation exact layout: xem [handbook A](member_a_implementation_handbook.md).
- Language/Belief/Planning exact layout: xem [handbook B](member_b_implementation_handbook.md).
- Shared `contracts`, `agent`, CI, manifests/config freeze và final report tuân theo joint protocol ở Section 22.
- Khi một handbook đề xuất path khác bảng trên, reviewer kiểm tra boundary chứ không ép giữ tên file chỉ vì master từng dự kiến.

---

## 19. Phase 1: GitHub workflow và execution governance

> **PHẦN II — HANDBOOK EXECUTION VÀ CROSS-MEMBER INTEGRATION**  
> Section 19–23 quy định governance, ownership, handoffs và gates trong lúc A/B thực hiện handbook. Exact day-by-day steps, file contents, failing tests và suggested commits chỉ nằm trong handbook.

### 19.1. Governance boundary

- Mỗi handbook task tương ứng một GitHub Issue có owner, reviewer, dependencies, validation evidence và DoD.
- Master không lặp task steps; Section 22 chỉ giữ ownership/handoff index cần cho phối hợp xuyên lane.
- Reviewer phải chạy hoặc kiểm tra validation cụ thể; “A owner, B reviewer” không đủ nếu không nêu evidence.
- Không tạo empty commit để thể hiện participation; review evidence nằm trong PR/Issue, code/test fixes mang commit của người thực sự sửa.
- Shared contract/schema/experiment changes cần cả hai approve và tuân theo freeze/version rule.

### 19.2. Kênh phối hợp qua GitHub

GitHub là source of truth cho trạng thái công việc:

```text
Backlog → Ready → In Progress → Review → Blocked → Done
```

Mỗi task trong Section 22 tương ứng một GitHub Issue. Mỗi Issue phải có:

- Task ID và ngày dự kiến;
- owner thực thi;
- reviewer/validator;
- dependencies;
- files/interfaces;
- test case IDs;
- validation commands;
- pass criteria;
- commit plan;
- joint checkpoint;
- Definition of Done.

Async update cuối ngày:

```text
Done:
Validation evidence:
Next:
Blocked:
Decision needed:
```

### 19.3. Integration branch và review policy

- Dùng GitHub default branch làm protected integration branch; ưu tiên `main` cho fresh remote.
- Nếu repository chủ ý giữ `master`, áp dụng cùng protections mà không rename chỉ vì convention.
- Không push trực tiếp vào integration branch.
- Mỗi PR cần một approval từ thành viên còn lại.
- CI checks bắt buộc trước merge.
- PR thay interface/schema phải được cả hai approve.
- PR không được chứa unrelated refactor, raw run outputs, secret hoặc local `.claude/` configuration.
- Sau `G4-ready`, mọi thay đổi semantic/config/manifest làm candidate mất hiệu lực, cần version bump và rerun toàn bộ affected cells; sau final `G4`, cùng loại thay đổi mở một follow-up snapshot mới, không sửa ngầm final artifact.

### 19.4. Labels và milestones

Labels:

```text
area:env
area:perception
area:language
area:belief
area:planning
area:control
area:evaluation
area:docs
rq:RQ1
rq:RQ2
priority:blocker
priority:core
scope:post-core
type:feature
type:test
type:experiment
type:docs
status:decision-needed
```

Milestones:

- `M0 Secure Scaffold`
- `M1 Oracle Pipeline`
- `M2 Local Belief Pipeline`
- `M3 Closed-Loop Recovery`
- `M4 Frozen Evaluation`
- `M5 Habitat Decision`

### 19.5. Branch và commit conventions

- Tại `R0`, repository owner freeze một branch convention duy nhất cho cả master/handbooks; hỗ trợ tối thiểu `chore/feat/fix/test/exp/docs`, nhận diện task/owner-or-joint và link đúng Issue. Mọi handbook branch suggestion lệch convention phải sửa trước khi task bắt đầu.
- A/B commit chỉ chứa output người đó chịu trách nhiệm; không trộn unrelated refactor.
- Joint integration commit chỉ dùng cho wiring/ADR/config/report thực sự cần cả hai, không dùng để gom lane work chưa review.
- Reviewer không tạo empty commit; nếu họ bổ sung test/fix thì dùng commit mang scope thực tế.
- Squash merge title dùng Conventional Commit; release/freeze commit phải ghi config/schema version hoặc artifact hashes liên quan.

### 19.6. Pull request checklist

```markdown
- [ ] PR link tới đúng Task ID/Issue.
- [ ] Phần “A thực hiện”, “B thực hiện” và “Joint checkpoint” đã hoàn tất.
- [ ] Tất cả test case IDs của task có evidence PASS.
- [ ] Test mới đã được chứng minh fail trước implementation khi task là code task.
- [ ] Ruff, mypy và relevant pytest commands pass.
- [ ] Pass criteria định lượng đạt.
- [ ] Interface changes được mô tả và cross-reviewed.
- [ ] Không thêm normal-path oracle import hoặc privileged field.
- [ ] Typed statuses/outcomes và schema version được giữ.
- [ ] Không chứa secret, raw output hoặc local config.
- [ ] README/reproduction command được cập nhật nếu CLI đổi.
- [ ] Suggested commits có scope rõ và không trộn unrelated work.
```

---

## 20. Ownership, capacity và milestone cadence

### 20.1. Ownership cố định

#### Thành viên A — Environment, Control và Evaluation

A chịu trách nhiệm chính cho:

- secure scaffold và CI;
- MiniGrid environment adapter và core task environments;
- local categorical observation decoder;
- primitive controller và dead reckoning;
- deterministic frontier explorer;
- authoritative `TaskVerifier`;
- exact evaluator oracle và manifests;
- N2 fixed interventions;
- metrics, experiment runner và final run execution.

#### Thành viên B — Language, Belief và Planning

B chịu trách nhiệm chính cho:

- shared contracts/type vocabulary;
- deterministic grammar và parser suite;
- EvidenceStore, tri-valued BeliefMap và staleness;
- validator và committed planning state;
- `LocationGraph`, positive STRIPS domain, serializer và pyperplan adapter;
- execution monitor và bounded replanning;
- N1 evidence corruption;
- typed failure taxonomy, trace lineage và bootstrap summaries.

#### Joint ownership

Hai người phải làm chung hoặc đồng thuận tại:

- Day-0 security decisions;
- interface freeze;
- PDDL↔MiniGrid action mapping;
- `agent.py` orchestration;
- trust-boundary/oracle-leakage review;
- experiment config/manifest freeze;
- full integration gates `G1`–`G5`;
- fresh-checkout reproduction;
- Habitat go/no-go decision;
- final research artifact.

### 20.2. Capacity model

- Mỗi người: tối thiểu 15 giờ/tuần.
- Scheduled implementation: khoảng 12 giờ/người/tuần.
- Review/integration/debug/documentation buffer: khoảng 3 giờ/người/tuần.
- Trung bình mỗi working day: 2,4 giờ scheduled + 0,6 giờ buffer/người.
- Tổng: 96 scheduled team-hours + 24 buffer team-hours.
- Post-core scope không được lấy trước buffer.

### 20.3. Weekly summary

| Tuần | Mục tiêu A | Mục tiêu B | Joint milestone |
|---|---|---|---|
| Week 1 | Secure scaffold, MiniGrid adapter/tasks/verifier/controller | Contracts, LocationGraph, STRIPS domain, serializer, pyperplan | `G0`, B3 vertical slice, `G1`, interface freeze |
| Week 2 | Local decoder, dead reckoning, exact oracle, manifests | Grammar, EvidenceStore, BeliefMap, validator | Clean local V0R0/V1R0, leakage audit, `G2` |
| Week 3 | Frontier explorer, N2 interventions, evaluator integration | Execution monitor, bounded replanning, N1, trace | Full V1R1 diagnostics, `G3` |
| Week 4 | Metrics/frozen candidate, rồi A-J04/A-J05 | Leakage/replay/summaries, rồi B-J04 | `G4-ready` → Phase 2/H12 → final `G4`, reproduction, Habitat decision, `G5` |

### 20.4. Daily execution nằm trong handbook

Master không duy trì bảng 20 ngày thứ hai vì sẽ drift với exact steps. Nguồn lịch duy nhất:

- [Lịch riêng Thành viên A](member_a_implementation_handbook.md#1-lịch-riêng-của-thành-viên-a)
- [Lịch riêng Thành viên B](member_b_implementation_handbook.md#1-lịch-riêng-của-thành-viên-b)

Weekly table ở Section 20.3 chỉ khóa milestone và dependency boundary. Nếu lịch handbook thay đổi nhưng vẫn giữ gate/dependency/capacity, cập nhật handbook. Nếu thay đổi ảnh hưởng scope, shared contract, handoff deadline hoặc gate, cập nhật master qua joint approval.

### 20.5. Daily operating rules

- A và B không cùng sửa một implementation file trong cùng ngày nếu chưa phân driver/reviewer.
- Joint checkpoint phải có GitHub comment/ADR, không chỉ trao đổi miệng.
- Cuối mỗi ngày, owner attach command output hoặc report path vào Issue.
- Task chưa đạt pass criteria ở ngày dự kiến chuyển `Blocked`, không được đánh dấu `Done` vì “code đã viết xong”.
- Công việc ngày sau chỉ bắt đầu nếu dependency bắt buộc đã merge hoặc có approved interface stub.

---

## 21. Shared quality bar

Exact task templates, failing-test snippets, commands và commits nằm trong handbook tương ứng. Master chỉ khóa quality bar dùng chung để reviewer không thể hạ tiêu chuẩn giữa hai lane.

### 21.1. Minimum task evidence

Mỗi Issue/handbook task phải nêu:

- task ID, owner, reviewer, dependencies, handoff và affected gate;
- exact output/files/interfaces trong handbook;
- ít nhất một happy-path và một negative/boundary case;
- contract/integration case nếu task tạo hoặc consume interface;
- validation command, expected typed/quantitative result và artifact/hash path;
- joint checkpoint nếu output đi qua lane boundary;
- DoD và protocol deviations.

### 21.2. Validation standard

Đối với code task:

1. chứng minh test mới fail vì behavior thiếu/sai;
2. implement minimal behavior;
3. chạy targeted tests và affected suite;
4. chạy static checks liên quan;
5. reviewer rerun ít nhất targeted command độc lập.

Đối với experiment/documentation task, dùng schema/hash/row-count/replay/link/reproduction checks; “đọc thấy hợp lý” không phải pass criterion duy nhất.

### 21.3. Shared task DoD

Task chỉ `Done` khi responsibilities và handoff đã hoàn tất, mọi required check PASS, reviewer evidence tồn tại, commit/PR đúng scope, contract/docs liên quan được cập nhật và không còn blocker hoặc silent protocol deviation.

Validation evidence tối thiểu trong Issue:

```markdown
- Test/check IDs:
- Command and exit code:
- Passed/failed counts or typed outcome:
- Artifact/hash/result path:
- Reviewer rerun:
- Deviations and downstream impact:
```

Không tạo empty commit. Reviewer không sửa file thì PR approval kèm evidence là đủ.

---

## 22. Execution handbook index và handoff matrix

Section 22 không lặp implementation steps. Hai file dưới đây là source of truth cho công việc cụ thể của từng người:

| Thành viên | Execution handbook | Nội dung sở hữu |
|---|---|---|
| A | [`docs/member_a_implementation_handbook.md`](member_a_implementation_handbook.md) | Environment, Control, Evaluation; exact code/test/commit steps; cross-validation duties đối với B |
| B | [`docs/member_b_implementation_handbook.md`](member_b_implementation_handbook.md) | Language, Belief, Planning; exact code/test/commit steps; cross-validation duties đối với A |

### 22.1. Cách sử dụng ba tài liệu

1. Hoàn tất Phase 0 và `R0`; chưa đạt `R0` thì không mở implementation task.
2. Mỗi thành viên thực hiện exact steps/tests/commits trong handbook của mình; master không có daily schedule thay thế.
3. Trước khi consume output của lane kia, kiểm tra handoff tương ứng H01–H12 và gate hiện hành.
4. Joint task phải được đối chiếu ở cả hai handbook; không merge nếu driver/support commits, artifacts hoặc validation evidence chưa khớp.
5. Shared scope/contracts/gates/freeze rules của master luôn áp dụng; unresolved conflict dùng `status:decision-needed`.
6. Khi core tasks đạt `G4-ready`, chuyển sang Phase 2 ở Section 24 và thực hiện các task closure `A-J04`/`A-J05`/`B-J04`; final evaluation `G4` và final handbook checklist là Phase-2 exit evidence, không phải entry prerequisite.

### 22.2. Task ownership index

| Master task | A handbook | B handbook | Driver | Support/validator | Gate / prerequisite |
|---|---|---|---|---|---|
| Secure scaffold | [`A-01`](member_a_implementation_handbook.md#task-a-01-secure-fresh-scaffold) | [`B-01`](member_b_implementation_handbook.md#task-b-01-shared-contracts-static-config-và-ci) | A package/deps; B contracts/CI | Joint security decision | `R0 → G0`, `H01` |
| Native MiniGrid semantics | [`A-02`](member_a_implementation_handbook.md#task-a-02-minigrid-adapter-core-tasks-và-taskverifier) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates symbolic semantics | before `G1`, `H02` |
| PDDL/pyperplan foundation | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-02`](member_b_implementation_handbook.md#task-b-02-locationgraph-positive-strips-và-pyperplan-adapter) | B | A validates executability | before `G1`, `H02` |
| B3 vertical slice | [`A-J01`](member_a_implementation_handbook.md#task-a-j01-primitive-controller-và-b3-vertical-slice) | [`B-J01`](member_b_implementation_handbook.md#task-b-j01-b3-planning-integration-và-interface-freeze) | Joint | A execution, B planning | `G1`, `H03–H04` |
| Local observation | [`A-03`](member_a_implementation_handbook.md#task-a-03-local-categorical-decoder-và-dead-reckoning) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates Evidence contract | before `G2`, `H05` |
| Parser | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-03`](member_b_implementation_handbook.md#task-b-03-deterministic-grammar-và-curated-parser-suite) | B | A validates task-spec mapping | before `G2`, `H05` |
| Evidence/Belief | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-04`](member_b_implementation_handbook.md#task-b-04-evidencestore-và-tri-valued-beliefmap) | B | A supplies action fixtures | before `G2`, `H06` |
| Oracle/manifests | [`A-04`](member_a_implementation_handbook.md#task-a-04-exact-evaluator-oracle-và-immutable-manifests) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates leakage/hash | before `G2`, `H06` |
| Validator/commitment | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-05`](member_b_implementation_handbook.md#task-b-05-validator-và-committedplanningstate) | B | A validates env conflicts/clean facts | `G2`, `H06` |
| Clean local integration | [`A-J02`](member_a_implementation_handbook.md#task-a-j02-clean-local-v0r0v1r0-integration) | [`B-J02`](member_b_implementation_handbook.md#task-b-j02-clean-local-v0r0v1r0-và-leakage-integration) | Joint | A runtime, B symbolic path | `G2`, `H07` |
| Frontier explorer | [`A-05`](member_a_implementation_handbook.md#task-a-05-deterministic-frontier-explorer) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates TaskMonitor boundary | before `G3`, `H08` |
| Monitor/replanning | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-06`](member_b_implementation_handbook.md#task-b-06-execution-monitor-và-bounded-replanning) | B | A validates environment mismatches | before `G3`, `H08` |
| N2 interventions | [`A-06`](member_a_implementation_handbook.md#task-a-06-n2-fixed-interventions) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates pairing/sidecar | before `G3`, `H09` |
| N1 corruption | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-07`](member_b_implementation_handbook.md#task-b-07-n1-evidence-corruption-và-reliability-model) | B | A validates visibility eligibility | before `G3`, `H09` |
| Trace/replay | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-08`](member_b_implementation_handbook.md#task-b-08-typed-outcomes-trace-lineage-và-replay) | B | A validates env/private fields | before `G3`, `H09` |
| Full V1R1 diagnostics | [`A-J03`](member_a_implementation_handbook.md#task-a-j03-full-v1r1-diagnostic-integration) | [`B-J03`](member_b_implementation_handbook.md#task-b-j03-full-v1r1-diagnostic-integration) | Joint | A runtime, B symbolic/trace | `G3`, `H10` |
| Metrics/final runs | [`A-07`](member_a_implementation_handbook.md#task-a-07-metrics-experiment-runner-và-frozen-runs) | [B cross-validation](member_b_implementation_handbook.md#3-cross-validation-duties-của-b-đối-với-a-owned-tasks) | A | B validates formulas/pairing/hashes | `G4-ready`, `H11` |
| Audit/bootstrap/summaries | [A cross-validation](member_a_implementation_handbook.md#3-cross-validation-duties-của-a-đối-với-b-owned-tasks) | [`B-09`](member_b_implementation_handbook.md#task-b-09-leakage-audit-paired-bootstrap-và-summaries) | B | A spot-checks raw results | `G4-ready`, `H11` |
| Fresh reproduction | [`A-J04`](member_a_implementation_handbook.md#task-a-j04-fresh-checkout-reproduction) | [`B-J04`](member_b_implementation_handbook.md#task-b-j04-reproduction-docs-rq-interpretation-và-final-habitat-decision) | Joint | A reproduces, B fixes docs/reruns | Phase 2, `H12` |
| Habitat/final report | [`A-J05`](member_a_implementation_handbook.md#task-a-j05-fake-adapter-habitat-mapping-và-final-engineering-report) | [`B-J04`](member_b_implementation_handbook.md#task-b-j04-reproduction-docs-rq-interpretation-và-final-habitat-decision) | Joint | A engineering, B research interpretation | `G5`, `H12` |

### 22.3. Mandatory handoffs

| Handoff | A giao | B giao | Deadline | Validation trước khi downstream bắt đầu |
|---|---|---|---|---|
| `H01` | Package paths/dependencies + tracked smoke config | Full canonical contracts + CI/static config schema | Day 1 | Import/static/config checks PASS; A consumes shared package, không tạo divergent stub |
| `H02` | Native action/verifier fixtures | Symbolic action schema/PDDL predicates | Day 3 | Native mapping + planning tests PASS |
| `H03` | Controller/oracle execution traces | Typed B3 plans/problem hashes | Day 4 | 2+2 integration episodes PASS |
| `H04` | G1 smoke artifact | Frozen contracts/ADR | Day 5 | B3 20/20, both approve |
| `H05` | Local Evidence/action fixtures | GoalProgram/parser outputs | Day 7 | Decoder/parser contract tests PASS |
| `H06` | Oracle/manifests/sidecar schema | Belief/validator/committed state APIs | Day 9 | No-leakage + unknown-not-false PASS |
| `H07` | Local runtime traces | V0R0/V1R0 symbolic path | Day 10 | G2 smoke/audit PASS |
| `H08` | Frontier events/primitive feedback | Monitor/replan decisions | Day 12 | Recovery unit/integration tests PASS |
| `H09` | N2 checkpoints/events + tracked diagnostic config | N1 checkpoint + full trace schemas | Day 14 | Config/determinism/pairing/security tests PASS |
| `H10` | V1R1 runtime diagnostics | Symbolic/replay diagnostics | Day 15 | G3 all typed/bounded |
| `H11` | Frozen candidate configs/raw results | Audit/bootstrap summaries | Day 18 | `G4-ready` row/hash/pair checks PASS; final `G4` remains Phase 2 output |
| `H12` | Reproduction/portability evidence | RQ/gate analysis/report | Day 20 | G5 rubric + final validation PASS |

Handoff invariants:

- `contracts.py`/shared package từ B là canonical; A import nó thay vì duy trì bản chép tay.
- `H01` phải giao đầy đủ shared dataclasses/enums/Protocols trong Section 8, không chỉ một subset types.
- `PlanResult.status` luôn là `PlanStatus`, không hạ thành `str` tại consumer boundary.
- `Evidence` và `Provenance` là một phần bắt buộc của `H01/H05` vì local decoder và belief lane cùng consume.
- `H09` trace schema phải chứa toàn bộ Section 17 fields, gồm `oracle_input`; round-trip fixture rút gọn không phải frozen contract.
- Config dùng ở một gate phải có tracked producer/schema trong handoff trước gate đó.
- Nếu handbook excerpt khác master, master ưu tiên và discrepancy phải được sửa trước downstream merge.

### 22.4. Joint task protocol

Mỗi joint task phải ghi trong GitHub Issue:

```markdown
## Joint task
- Driver:
- Support:
- A input commit/artifact:
- B input commit/artifact:
- Joint decision:
- Integration commit:
- Validation commands:
- Expected output:
- Reviewer evidence:
- Merge order:
```

Joint task không hoàn tất nếu chỉ một handbook đánh dấu xong. Cả hai phải link cùng integration commit/artifact và cùng gate evidence.

### 22.5. Handbook completeness contract

Mỗi A/B-owned task trong handbook phải có:

- exact day/timebox/branch/reviewer;
- exact files và interface contracts;
- checkbox implementation steps;
- actual code sample;
- failing test code và expected initial failure;
- passing command và expected result;
- additional edge/integration cases;
- A/B/joint commit guidance;
- handoff artifact;
- Definition of Done.

Nếu task không đáp ứng checklist này, handbook task được xem là incomplete dù ownership/handoff index đã liệt kê.

---

## 23. Weekly gates, integration và contingency cuts

### 23.1. Weekly integration checkpoints

| Checkpoint | Thời điểm | A phải mang tới | B phải mang tới | Joint validation |
|---|---|---|---|---|
| `R0` | Trước Day 1 | Remote/toolchain readiness | Access/contracts-readiness review | Repo protection, security, tracked docs và work board PASS |
| `G0` | Cuối Day 1 | Secure scaffold/dependencies | Shared contracts/CI/static checks | Fresh setup, import, tests và `H01` PASS |
| `G1` | Day 5 | Adapter/tasks/verifier/controller | Contracts/PDDL/planner/statuses | B3 20/20 smoke; interface freeze |
| `G2` | Day 10 | Local decoder/feedback/oracle/manifests | Parser/belief/validator/serializer | V0R0/V1R0 clean + no leakage |
| `G3` | Day 15 | Frontier/N2/evaluator integration | Monitor/replan/N1/trace | Full V1R1 diagnostics bounded |
| `G4-ready` | Day 18 | Metrics/runner/frozen candidate | Audit/replay/bootstrap/tables | Candidate rows/hashes/pairs complete; no final claim yet |
| `G4` | Sau final matrix và Phase-2 audit | Final results/reconciled rows | Final audit/CIs/report inputs | Frozen results complete; final SHA promoted |
| `G5` | Sau reproduction + research decision | Reproduction/portability evidence | RQ/gate interpretation/report | Typed Habitat decision + final artifact |

### 23.2. Gate acceptance criteria

#### R0 — Pre-handbook readiness

- A/B có remote access và review permission.
- Integration branch protection/PR policy được xác nhận.
- Credentials đã rotate/revoke; tracked secret scan clean.
- Master và hai handbook được Git track, không bị ignore.
- Python/uv/Git preflight PASS trên cả hai máy.
- Issues/milestones/owners/reviewers/handoffs đã tạo.
- Không còn security/shared-contract blocker.

#### G0 — Secure reproducible scaffold

- `A-01` và `B-01` hoàn tất, `H01` có evidence.
- Secret paths ignored; tracked secret scan clean.
- Fresh package/lock/README/CI, shared contracts, config schema/defaults và smoke config tồn tại.
- `uv sync`, import, Ruff, mypy, pytest và smoke-config validation PASS cục bộ/CI.

#### G1 — Oracle-input planning baseline

- Native semantics tests PASS.
- PDDL parses với supported STRIPS features.
- B3 20/20 smoke success.
- Believed-state plans 100% valid.
- No primitive `Actions.done`, no untyped outcome.
- Interfaces frozen.

#### G2 — Clean local pipeline

- Parser 40/40 expected categories.
- Clean visible facts precision/recall 100% trong encoded regime.
- Unknown không serialize như false/free.
- Initially unseen targets được discover bằng frontier.
- V0R0/V1R0 clean smoke chạy với typed outcomes.
- No oracle import/constructor/sidecar leak.

#### G3 — Full bounded closed loop

- V1R1 xử lý declared N1/N2 diagnostics.
- Replan/loop/action/planner bounds enforce.
- Deliberate loop kết thúc `LOOP_DETECTED`.
- All diagnostic traces schema-valid/replayable.
- No unclassified outcome.

#### G4-ready — Frozen evaluation candidate

- Dev/test manifests/config hashes và thresholds/budgets đã freeze cho candidate.
- All core episodes solvable; N2 interventions recoverable.
- Methods dùng identical episode units/controller/verifier/budgets.
- Candidate row plan, paired-unit plan, leakage checks và trace targets đã pass.
- Candidate có thể được đưa vào Phase 2; chưa được dùng để tuyên bố final result.

#### G4 — Final frozen evaluation artifact

- Candidate đã được Phase 2 integration audit và final matrix reconciliation.
- Khoảng 1.120 expected core rows đầy đủ, không missing/duplicate chưa có typed disposition.
- Paired CIs, leakage và trace audits hoàn tất trên final SHA/config/manifest hashes.
- Không còn semantic change chưa version hoặc affected rerun.

#### G5 — Reproduction và 3D decision

- Fresh-checkout reproduction PASS.
- CI PASS.
- Fake non-grid adapter conformance PASS.
- Claim/non-claim đúng evidence.
- Habitat rubric có đúng một typed decision.

### 23.3. Khi task trễ hoặc validation fail

- Issue chuyển `Blocked`; ghi failing test ID, command và root-cause owner.
- Không chuyển công việc downstream nếu dependency contract chưa pass.
- Buffer ưu tiên theo thứ tự: security → semantic correctness → trust boundary → bounded execution → experiment integrity → docs polish.
- Nếu một task fail ba fix attempts khác nhau, dừng và joint-review architecture/interface thay vì tiếp tục patch.

### 23.4. Contingency cut order

1. Conditional-instruction micro-benchmark.
2. Object-relative spatial micro-benchmark.
3. Confidence-only/consistency-only secondary ablations.
4. Optional visualizations và nonessential report polish.

Không cắt:

- B3/V0R0/V1R0/V1R1;
- two core tasks;
- local-only trust boundary;
- tri-valued unknown;
- RQ1/N1 và RQ2/N2;
- explicit verifier;
- immutable manifests;
- typed outcomes;
- per-task validation cases;
- fresh reproduction.

Nếu G1/G2/G3 trễ quá một weekly boundary, không chạy final test matrix bằng partial pipeline. Nhóm phải giảm post-core scope hoặc kết luận month-one incomplete thay vì báo kết quả không đáng tin cậy.

---

> **PHẦN III — POST-HANDBOOK COMPLETION, HABITAT DECISION VÀ FINAL DoD**  
> Section 24–29 bắt đầu sau khi core handbook execution đạt `G4-ready`. Chúng gọi các closure runbooks còn lại, tích hợp/freeze/reproduce, quyết định bước tiếp theo và đóng project; không lặp exact implementation steps.

## 24. Phase 2: post-core integration, evaluation và closure

Phase 2 là wrapper bắt buộc sau **core handbook execution tại `G4-ready`**. Ba task closure vẫn nằm trong handbook để giữ exact steps, nhưng được gọi từ Phase 2: [`A-J04`](member_a_implementation_handbook.md#task-a-j04-fresh-checkout-reproduction), [`A-J05`](member_a_implementation_handbook.md#task-a-j05-fake-adapter-habitat-mapping-và-final-engineering-report) và [`B-J04`](member_b_implementation_handbook.md#task-b-j04-reproduction-docs-rq-interpretation-và-final-habitat-decision).

### 24.1. Entry criteria

Chỉ bắt đầu Phase 2 khi:

- Phase-1 tasks `A-01`–`A-07`, `A-J01`–`A-J03`, `B-01`–`B-09` và `B-J01`–`B-J03` đã đạt task DoD;
- `H01`–`H11` có producer artifact, consumer validation và commit links;
- `G0`–`G3` PASS và `G4-ready` PASS trên cùng freeze candidate SHA;
- mọi shared contract/schema deviation đã được merge, versioned hoặc rollback;
- không còn lane-local branch chứa required Phase-1 output chưa mở PR;
- Phase-2 Issues cho `A-J04`/`A-J05`/`B-J04` đã có driver/support và merge order.

Final checklist của A/B và `G5` là **exit criteria**, không phải entry criteria. Nếu entry criterion fail, quay lại đúng Phase-1 handbook task/Issue; không sửa trực tiếp trong Phase 2 để che một lane chưa hoàn tất.

### 24.2. Lane completion và handoff audit

Hai thành viên thực hiện joint audit theo thứ tự:

1. Đối chiếu task ownership index với merged PRs, không chỉ checkbox trong Markdown.
2. Kiểm tra H01–H11 có producer artifact, consumer validation và đúng deadline/version.
3. Xác nhận không còn approved stub, placeholder, skipped test hoặc unclassified outcome ngoài danh sách deviation.
4. So sánh canonical contracts với consumers/producers; đặc biệt `PlanStatus`, `Evidence`, `Provenance`, `CommittedPlanningState`, trace schema và reason codes.
5. Chạy cross-validation tables của cả hai handbook và lưu reviewer rerun evidence.
6. Lập closure list cho failures: `must-fix-before-freeze`, `reported-limitation` hoặc `post-core`; không để unlabeled TODO.

### 24.3. Integration audit và closure merge order

1. Xác nhận `G4-ready` candidate đã chứa mọi H01–H11 producer/consumer merge, shared contracts và `agent.py` wiring.
2. Chạy targeted contract/integration checks, sau đó full static/test suite, no-oracle-leakage, trace replay, bounded-loop và end-to-end smoke trên candidate SHA.
3. Thực hiện `A-J04` reproduction; docs/config/setup fix được merge qua PR rồi reproduction chạy lại từ fresh state.
4. Thực hiện `A-J05` portability/fake-adapter; merge code-contract fix trước khi kết luận portability.
5. Nếu Phase 2 phát hiện semantic/core runtime change, invalidate `G4-ready`, version bump và quay lại Phase 1/gate tương ứng; không patch âm thầm trên candidate.
6. Chỉ promote candidate thành final SHA sau khi final matrix, reproduction và research report đã được kiểm tra; final snapshot/tag tạo ở Section 24.7 sau CI cuối.

Một lane pass riêng hoặc final-checklist checkbox không đủ. Không squash nhiều unresolved protocol changes vào một closure commit không audit được.

### 24.4. Final evaluation và promote `G4`

- freeze code SHA, lockfile, public manifests, evaluator sidecars, configs, thresholds, budgets, seeds và result schema từ `G4-ready` candidate;
- ghi hash/version vào freeze record;
- chạy B3/RQ1/RQ2/V1R1-clean matrix theo Section 13–16;
- phân biệt infrastructure rerun với semantic rerun; semantic change phải version bump và rerun toàn bộ affected cells, đồng thời invalidates candidate;
- đối chiếu raw rows ↔ traces ↔ summaries ↔ paired CIs; mọi missing/duplicate row phải có typed disposition;
- xác nhận solvability, recoverable N2, paired units, row count, leakage, trace và metric regression;
- chỉ khi toàn bộ final checks pass mới promote candidate thành final SHA và đánh dấu `G4`.

Không chạy hoặc báo final matrix từ partial pipeline nếu G1/G2/G3 chưa pass. Nếu final checks fail, giữ trạng thái `G4-ready`/`Blocked`, sửa qua PR và lặp lại affected validation; không gọi đó là `G4`.

### 24.5. Fresh-clone reproduction

Reproduction phải dùng checkout/directory mới, không tái sử dụng `.venv`, caches, untracked configs hoặc raw local patches:

1. clone đúng remote và checkout frozen SHA/tag;
2. làm theo README từ environment sạch;
3. `uv sync --all-groups` từ tracked metadata/lock;
4. chạy Ruff, mypy và full pytest;
5. regenerate/verify manifest hashes theo policy;
6. chạy smoke evaluation và ít nhất một declared reproduction target;
7. xác nhận result schema, trace replay và artifact paths;
8. ghi OS/Python/uv/dependency metadata và mọi deviation.

A là reproduction operator mặc định; B theo dõi docs/config mismatch và chỉ sửa qua PR. Sau fix, reproduction phải chạy lại từ fresh state. Output này hoàn tất `H12`, không chỉ là README review.

### 24.6. Research audit và typed decision

- B đối chiếu estimands, paired contrasts, CIs, per-family/per-condition tables và claims.
- A đối chiếu runtime, metrics, oracle, portability và engineering gates.
- Cả hai xác nhận failed threshold/RQ được báo trung thực và non-claims không bị vượt quá.
- Áp dụng Section 26 để chọn đúng một: `Advance`, `Conditional hold` hoặc `No-go`.
- Decision phải link frozen SHA/config/manifests, gate evidence, exact result tables và unresolved limitations.

Không đổi threshold sau khi xem test result. Không dùng qualitative success case để ghi đè failed quantitative gate.

### 24.7. Repository closure và research snapshot

Trước khi đóng milestone:

- merge README/reproduction, methods/results/threats và Habitat decision;
- bảo đảm CI PASS trên final commit sau khi `G4`, reproduction và research decision đã pass;
- kiểm tra repository không chứa secrets, raw private sidecars hoặc accidental run outputs;
- chỉ lúc này tạo signed/annotated final tag hoặc immutable research snapshot theo policy của nhóm; tag phải trỏ đúng final SHA đã được reproduce;
- publish/archive reviewed aggregate tables, configs, hashes và report; raw/private artifacts theo storage policy riêng;
- đóng Issues đã Done, chuyển unresolved work sang follow-up milestone với owner/scope;
- ghi final gate table `R0`, `G0`–`G5` và protocol deviations;
- xác nhận Definition of Done ở Section 28.

### 24.8. Phase 2 exit evidence

Phase 2 chỉ kết thúc khi có:

1. integration audit record;
2. frozen SHA/config/manifest/schema hashes;
3. expected final row-count reconciliation;
4. trace/leakage/replay audit;
5. fresh-clone reproduction record;
6. RQ1/RQ2 results và threats/non-claims;
7. typed Habitat decision;
8. final CI link, tag/snapshot và deliverable index;
9. final checklist A/B cùng `A-J04`/`A-J05`/`B-J04` DoD đã sign off.

## 25. Habitat migration seam

### 25.1. Enforced month-one invariants

- Không MiniGrid import ngoài adapter, MiniGrid task definitions, native tests và evaluator oracle.
- Core contracts không chứa MiniGrid Action enum.
- Core planning không phụ thuộc integer `(x, y)` coordinates.
- `LocationId`, `HeadingId`, `EntityId` opaque.
- `LocationGraph` cung cấp topology/approach poses.
- Fake non-grid graph adapter chạy cùng adapter contract tests.
- Evaluator oracle tách khỏi agent.

### 25.2. Mapping sang Habitat-Lab

| Month-one abstraction | Habitat target |
|---|---|
| `EpisodeSpec` | Habitat dataset episode |
| `EnvironmentAdapter` | Wrapper quanh Habitat Env/task APIs |
| `ObservationPacket` | Selected semantic/depth/odometry sensors + instruction |
| `LocationGraph` | Navmesh waypoints hoặc semantic-region graph |
| `HeadingId` | Discrete yaw bin hoặc local-controller pose class |
| `PrimitiveAction` | Habitat task action/controller command |
| `TaskVerifier` | Habitat success measure/task measure |
| `EvaluationOracle` | Geodesic distance, shortest path và privileged measures |
| `goto_type_color` | Semantic ObjectNav/VLN-style target |
| `key_door_goal` | Deferred custom interaction/rearrangement task |

### 25.3. Migration order

1. Cài Habitat trong separate optional environment/lock.
2. Implement semantic local navigation adapter trước.
3. Run adapter conformance và small smoke episodes.
4. Reproduce belief/planner/controller behavior với semantic inputs.
5. Chỉ sau đó thêm natural VLN instructions.
6. RGB/VLM perception là phase riêng; không gộp vào first Habitat migration.
7. Key-door interaction chỉ sau navigation adapter ổn định.

---

## 26. Practical Habitat go/no-go rubric

### 26.1. Mandatory engineering gates

Tất cả phải pass:

- Không tracked credential.
- Zero detected normal-path oracle access.
- Không unclassified episode outcome.
- Không run vượt action/replan/loop/planner-time bounds.
- Trace schema completeness ≥99%.
- Trace replay fidelity ≥99%.
- Planner timeout rate <1%.
- Planner p95 wall-clock <2 seconds.
- Fresh-checkout reproduction pass.
- Fake non-grid adapter contract pass.
- Core modules không import MiniGrid types hoặc assume grid coordinates.

### 26.2. Planning/control gates

- B3 clean SR ≥95% trong từng core family.
- B3 believed-state plan validity =100%.
- B3 oracle-state plan validity ≥98%.

Nếu B3 thấp hơn, lỗi nằm ở domain/serializer/controller/verifier; Habitat là `No-go`.

### 26.3. End-to-end local-input gates

- V1R1 clean SR ≥85% cho `goto_type_color`.
- V1R1 clean SR ≥75% cho `key_door_goal`.
- V1R1 clean oracle-state plan validity ≥95% trên found plans.
- Clean invalid primitive action rate ≤5%.

### 26.4. RQ1 gates

- V1R0 cải thiện oracle plan validity hoặc invalid-action rate ≥20% tương đối so với V0R0 trên N1.
- Accepted precision ≥90% tại coverage ≥50%.
- Clean success giảm không quá 5 percentage points.
- CI không cho thấy material adverse effect dưới −2 percentage points.

### 26.5. RQ2 gates

- V1R1 recovery ≥50%.
- V1R1 cao hơn V1R0 ≥15 percentage points.
- ≥90% interventions được detect trước hai additional invalid primitive actions.
- Median replans/recovered episode ≤3.
- Không recovery nào phụ thuộc vượt public action budget.

### 26.6. Decision classes

#### `Advance`

Engineering, planning/control, clean feasibility, RQ1 và RQ2 đều pass. Bắt đầu Habitat semantic-navigation adapter phase.

#### `Conditional hold`

Architecture gates pass nhưng RQ1 hoặc RQ2 không có practical support. Báo negative/partial result trung thực và tiếp tục diagnosis trong 2D trước khi migration.

#### `No-go`

B3, leakage, verifier, bounded execution, trace integrity hoặc fresh reproduction fail.

Post-core stretch failure không ảnh hưởng decision.

---

## 27. Rủi ro, threats to validity và mitigations

| Rủi ro/threat | Hệ quả | Mitigation |
|---|---|---|
| Plaintext credential bị commit | Security incident | Rotate Day 0, ignore `.claude/`, secret scan, no direct push |
| Unknown bị xem là false | Unsafe/unsound planning | Tri-valued BeliefMap, serializer regression, frontier policy |
| Oracle leakage | Inflated results | Separate protocols, forbidden-import test, sidecar isolation |
| MiniGrid semantics model sai | PDDL plan không executable | Native regression tests và explicit verifier |
| Synthetic confidence quá dễ | Overstate validation | Overlapping score distributions, risk-coverage report, explicit non-claim |
| Validator reject mọi fact | Precision cao giả tạo | Coverage/plan-found/task metrics và minimum coverage gate |
| RQ1 bị replanning confound | Sai causal attribution | Primary contrast V1R0−V0R0, replanning off |
| RQ2 bị perception confound | Không biết recovery từ đâu | Clean evidence và fixed interventions |
| Intervention baseline-specific | Pairing không công bằng | Pre-register checkpoint từ shared initial plan, identical prefix |
| SPL sai cho interaction | Efficiency misleading | SOPE với exact primitive optimum |
| Test tuning | Optimistic bias | Dev-only selection, frozen hashes/configs |
| Small sample/heterogeneity | CI rộng | Paired design, stratification, báo per-family/condition |
| Template parser overclaim | Không phản ánh natural language | Curated finite suite và explicit non-claim |
| Grid-specific abstractions | 3D rewrite lớn | Opaque IDs, LocationGraph, fake adapter tests |
| Half-time integration drift | Merge conflicts/contract mismatch | Interface freeze, issue/PR workflow, 24h buffer |
| Planner timeout/loop | Unbounded episodes | Worker timeout, typed outcomes, loop signatures, hard budgets |
| Qualitative cherry-pick | Misleading examples | Predefine failure categories; link all cases tới replay traces |
| MiniGrid version drift | Reproduction fail | Exact pins, lockfile, manifest generator version |
| Negative result bị che giấu | Research integrity issue | Definition of Done yêu cầu báo failed RQ/gates và protocol deviations |

### 27.1. External validity giới hạn

- Categorical sprites không đại diện photorealistic scenes.
- Synthetic corruption không đại diện đầy đủ correlated VLM errors.
- Template grammar không đại diện long-horizon natural VLN instructions.
- Grid dead reckoning đơn giản hơn 3D pose uncertainty.
- Stable 2D entity tracking không chứng minh 3D re-identification.

Những giới hạn này không làm PoC vô nghĩa; chúng xác định chính xác câu hỏi nào được kiểm chứng và điều gì phải kiểm tra lại trong Habitat/RGB phases.

---

## 28. Final deliverables và Definition of Done

### 28.1. Deliverables

1. Secure, locked Python project và CI.
2. Hai deterministic MiniGrid core task families.
3. B3/V0R0/V1R0/V1R1 implementations.
4. Local categorical evidence, tri-valued belief và validator.
5. Orientation-aware positive STRIPS + pyperplan.
6. Deterministic frontier explorer và bounded replanning.
7. Explicit task verifier và typed outcome taxonomy.
8. Immutable smoke/dev/RQ1/RQ2/diagnostic manifests.
9. Exact evaluator oracle và leakage audit.
10. Approximately 1.120 final core result rows.
11. Metrics, paired bootstrap CIs và per-stratum tables.
12. Replayable JSONL traces.
13. README fresh-checkout reproduction và independent reproduction record.
14. RQ1/RQ2 report, threats/non-claims và Habitat decision.
15. Habitat mapping seam và fake non-grid adapter conformance result.
16. Tracked master/A/B handbooks, gate evidence index và final tag/research snapshot.

### 28.2. Definition of Done

Month-one PoC hoàn thành khi:

- `R0` và `G0`–`G5` đã được đánh giá, không bỏ gate.
- Hai handbook hoàn tất và Phase 2 exit evidence ở Section 24.8 đầy đủ.
- Mọi method/task/metric có exact semantics.
- Không unclassified outcomes hoặc unbounded runs.
- Code SHA, configs, results, manifests, schemas và traces có version/hash.
- Bất kỳ failed threshold/RQ hoặc protocol deviation nào được báo trung thực.
- Fresh clone tái tạo được environment, manifest hashes, smoke output và result schema.
- Habitat decision là `Advance`, `Conditional hold` hoặc `No-go` với evidence links.
- Final CI PASS; tag/research snapshot và deliverable index tồn tại.
- Repository không chứa tracked secret, private sidecar hoặc accidental raw run outputs.
- Stretch không được dùng để che core chưa hoàn tất.

---

## 29. Appendices

### Appendix A — Plan và outcome status list

```text
PlanStatus:
  FOUND
  ALREADY_SATISFIED
  NEEDS_INFORMATION
  NO_PLAN_KNOWN_SPACE
  UNSUPPORTED_GOAL
  TIMEOUT
  SERIALIZATION_ERROR
  PLANNER_ERROR

EpisodeOutcome:
  SUCCESS
  UNSUPPORTED_INSTRUCTION
  AMBIGUOUS_GROUNDING
  FRONTIER_EXHAUSTED
  KNOWN_SPACE_DISCONNECTED
  BELIEF_CONFLICT_UNRESOLVED
  PLANNER_TIMEOUT
  PLANNER_ERROR
  REPLAN_BUDGET_EXHAUSTED
  LOOP_DETECTED
  ACTION_BUDGET_EXHAUSTED
  ENVIRONMENT_TERMINATED_FAILURE
```

### Appendix B — Result table schema

```csv
run_id,episode_id,family,condition,method,oracle_input,manifest_hash,config_hash,
success,episode_outcome,grid_spl,sope,primitive_actions,invalid_actions,
plan_status,believed_plan_valid,oracle_plan_valid,accepted_precision,
accepted_coverage,recovery_success,replans,planner_time_ms,trace_complete,
trace_replay_fidelity
```

### Appendix C — Minimum reason codes

```text
schema.invalid_arity
schema.invalid_identifier
ontology.invalid_argument_type
ontology.unsupported_predicate
consistency.multiple_robot_locations
consistency.multiple_held_objects
consistency.exclusive_door_state
consistency.object_location_conflict
consistency.passable_blocked_conflict
temporal.stale_dynamic_fact
reliability.below_threshold
grounding.unresolved_target
grounding.ambiguous_reference
execution.predicted_move_failed
execution.toggle_failed
execution.verifier_rejected
planning.no_known_space_route
planning.timeout
planning.serializer_error
```

### Appendix D — Master change-history policy

Master/handbook changes phải đi qua reviewable documentation PR với Conventional Commit title phù hợp repository policy. PR description phải nêu:

- section/contracts/gates bị thay đổi;
- handbook tasks và handoffs bị ảnh hưởng;
- schema/config/version bump nếu có;
- tests/matrix/artifacts cần rerun;
- migration hoặc conflict-resolution note.

Exact branch và commit messages thuộc Issue/handbook task; master không duy trì danh sách message thứ hai.

### Appendix E — Review checklist trước final test freeze

```markdown
- [ ] Core method matrix đúng B3/V0R0/V1R0/V1R1.
- [ ] Mọi trace/result row có `oracle_input`; chỉ B3 là `true`.
- [ ] RQ1 chỉ dùng N1 và replanning off.
- [ ] RQ2 chỉ dùng clean evidence + N2.
- [ ] Test manifests và config hashes đã freeze.
- [ ] Threshold/re-observation choices chỉ dùng dev.
- [ ] Same seeds/budgets/verifier/controller giữa paired methods.
- [ ] Oracle sidecar không nằm trong agent input.
- [ ] Unknown-not-false regression pass.
- [ ] No unclassified outcome trong smoke/diagnostic.
- [ ] Trace schema/replay tests pass.
- [ ] Planned result row count khớp matrix.
```

### Appendix F — Reading/reference pointers

- MiniGrid 3.1.0 primitive semantics và wrappers.
- BabyAI verifier semantics cho GoTo/task completion.
- pyperplan supported positive STRIPS subset.
- SPL definition cho embodied navigation.
- Habitat-Lab episode/sensor/action/measure abstractions.

Exact URLs/versions nên được pin trong README hoặc research report khi implementation bắt đầu; dependency behavior phải được xác minh bằng tests, không chỉ dựa vào documentation.

---

## Kết lời

Kế hoạch này ưu tiên một causal PoC nhỏ nhưng đáng tin cậy hơn một demo rộng khó diễn giải. Thành công tháng đầu không được định nghĩa bằng việc “pipeline chạy một vài lần”, mà bằng việc semantics đúng, trust boundary không bị vi phạm, RQ1/RQ2 được đánh giá tách biệt, mọi run có typed outcome và kết quả đủ reproducible để quyết định có nên đầu tư vào Habitat hay tiếp tục chẩn đoán trong 2D.
