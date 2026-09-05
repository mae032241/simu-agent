# R4-D-B 核心审批与科学资格实现第四轮独立复审

## 结论

**打回。**

第三轮冻结的 provider 隔离主问题已经闭合：同一 scientific foundation 在无决定、错误 parameter provider、正确 evidence provider 和 provider 合同摘要变化四阶段始终保持中性 `available`；候选 readiness 与权威 preflight 同步变化，且对象级不再读取审批决定。但 `available` 接入后，现有 qualified-only 解析循环把 foundation 的 payload 校验和 `objective_contract` 结构存在判断一并跳过，导致强制科研目标静默消失，畸形 foundation 也被报告为可用。此外，先构造 `available_kinds`、后修改对象状态会令已经判为 `revision_required` 的畸形目标仍留在 `available_artifacts`。这是第三轮验收条件第 5 项明确要求防止的机械接入回归，因此不允许进入 R4-D-C。

## 审查范围与证据

本轮严格复核第三轮报告冻结的五项验收条件，检查了 ScientificObjectStatus Schema、Root readiness、候选 provider 判定、权威 invoke preflight、ApprovalService、四阶段真实 Root 测试、计划 7.2/7.6、operation 目录和清洁发布候选。

独立执行结果：

- 四阶段 provider 隔离测试与真实通用科学证据链：`2 passed`；
- 第三轮所列五文件命令实际为 `57 passed`，不是计划 7.6 声称的 71 项；
- `tests/operations`：`201 passed`；
- 全仓：`235 passed`；
- `git diff --check` 通过；
- 清洁发布 `/tmp/scid-r4db-round4.4QYBdg/scidiscovery-agent` 无 `pyc`，`MANIFEST.sha256` 含 277 条记录，加 manifest 本身共 278 个文件，`sha256sum --check --quiet` 通过；
- 发布候选与工作树的 `mcp_root.py`、`research_cycle.py` 摘要一致；发布目录编译得到 32 个 Operation，其中三个是 public 科学审批 Operation；两个安装脚本 `bash -n` 通过。

基线不存在 `scripts/validate_architecture_constraints.py`，本报告没有宣称执行该脚本。计划中的“聚焦五文件 71 项”缺少可复现命令且与实际收集的 57 项不符，必须按真实命令和结果更正，但它不是本轮主要代码阻塞。

## 已通过的五项验收主体

### 1. 同一 foundation 的四阶段身份隔离通过

`test_foundation_inventory_stays_neutral_across_provider_decisions` 使用同一个真实 `scidiscovery.scientific-foundation.v1` Artifact、同一个 ResearchInstance 和启动编译的测试插件，通过 Root `operation_invoke` 创建并决定 approval：

1. 无决定时，对象为 `available`，证据消费者不在 `available_actions`，invoke 以 `input_cohort_approval_missing` 拒绝；
2. 只有 parameter provider 决定时，对象仍为 `available`，证据消费者的 readiness 与 preflight 仍同时拒绝；
3. exact evidence provider 决定后，对象仍为 `available`，候选出现且 invoke 创建真实 Task；
4. 保留历史决定但改变 evidence provider question，使 approval contract digest 改变并重新编译目录后，对象仍为 `available`，候选和 preflight 同时失效。

测试位于 `test_r4_approval_operation.py:2203-2399`。既有真实科学链还验证实际 `science.evidence.qualify.v1` 决定前后 foundation 都保持 `available`，而 `science.hypothesis.propose.v1` 只随 exact evidence provider 决定变化。

### 2. provider 权威仍唯一

全仓搜索确认：

- `_artifact_qualification` 已删除；
- provider-less `is_subject_approved`/`are_subjects_approved` 不存在；
- Root 没有遍历整个 Operation catalog 聚合对象资格；
- 没有 provider allowlist、qualification/provider cache 或新资格持久表；
- 生产调用只剩候选级和权威 preflight 两处 `are_subjects_approved_by_provider`。

候选身份仍来自 consumer Operation 已编译的 `approval_providers`，没有回退到 kind/option 全局语义。

### 3. 中性结构缺口方向正确

没有 foundation 时，`unresolved_needs` 只报告 `scientific_foundation`；存在结构有效的 foundation 后不再生成 `approved_scientific_foundation`。provider 缺口只体现在具体候选不可用和精确 preflight，不形成全局审批结论。这与计划 7.2 的候选级语义一致。

### 4. 单目录与轻控制面未回归

`available` 是现有只读投影中的一个状态值，没有新增注册表、状态机、数据库、审批入口或插件特判路由。Operation、Task、Artifact 和 Approval 生命周期仍由原有单一权威承担。

## 唯一阻塞：结构解析与资格消费尚未真正分离

### 现象一：available foundation 的显式目标合同被静默忽略

Root 先把 scientific foundation 标为 `available`（`mcp_root.py:663-724`），但目标解析循环在读取任何对象前执行：

```python
if item.qualification != "qualified":
    continue
```

因此后面的 `ScientificFoundation.model_validate_json` 和 `foundation.objective_contract is not None` 分支对 foundation 永远不可达（`mcp_root.py:772-820`）。`explicit_foundation_contract` 永远保持 false，`research_objective:projection_missing` 门也就不会触发（`mcp_root.py:826-840`）。

独立真实 Root 复现创建了一个 Schema 合法、带显式 `ResearchObjectiveContract`、但没有对应 `research_objective` projection 的 foundation。结果为：

```text
foundation_status = available
objective_status = not_declared
mandatory_target_gaps = []
blockers = []
```

正确的结构投影应为 `objective_status=blocked`，并包含 `research_objective:projection_missing`。这里不需要、也不允许把 foundation 的科学主张当作已审批证据；只需解析 canonical foundation Schema，并读取“是否存在 objective_contract”这一结构事实。当前行为会让强制外部目标或闭合要求从调度视图中消失，可能把研究退化成无目标的数值自洽。

### 现象二：available foundation 的 payload 失败未被发现

同一 qualified-only 跳过还使 foundation payload 不再校验。独立真实 Root 复现绑定一个声明为 `scidiscovery.scientific-foundation.v1`、内容为 `{"not":"a foundation"}` 的 Artifact，结果仍为：

```text
qualification = available
available_artifacts = [scientific_foundation]
blockers = []
```

这与 `available` 的冻结定义“结构存在且没有已知 payload/producer failure”直接矛盾。即使正常 Operation 输出会先经过 validator，readiness 仍不能把一个可绑定的畸形 immutable Artifact 当作有效结构事实。

### 现象三：available_kinds 在后续校验失败后没有重算

`available_kinds` 在第一次对象循环中立即加入所有初始 `qualified/available` kind（`mcp_root.py:718-724`）。后续 metric、research objective 或 objective coverage 解析失败时，只会把 `objects[index]` 改为 `revision_required` 并从 `effective_kinds` 移除，没有同步移除或重算 `available_kinds`。

独立真实 Root 复现一个畸形 `research_objective` 得到：对象状态为 `revision_required`、blocker 正确存在，但 `available_artifacts` 仍包含 `research_objective`。因此结构库存与同一响应中的对象状态自相矛盾。`ScientificReadiness` 的 validator 又把 `available_artifacts` 用于目标、诊断和执行一致性判断，所以这不是展示瑕疵。

上述三种现象是同一个根因：实现把“available 不表达 provider 资格”误写成了“available 不需要结构解析”，并在结构校验完成前过早冻结库存。

## 最小修复口径

1. 保持 foundation 对象状态始终不读取 provider 决定；不要恢复 `_artifact_qualification`、全目录 provider 扫描、全局 allowlist 或资格缓存。
2. 对 canonical `scidiscovery.scientific-foundation.v1` 执行结构解析，不以 `qualified` 为前提：
   - 解析失败时把该对象标为 `revision_required`、记录 blocker，且它不能进入 `available_artifacts`；
   - 解析成功时只提取 `objective_contract is not None` 这一结构布尔量；不得把 foundation items、evidence、claim boundary 或任何 scientific statement 纳入已审批 claim/evaluation。
3. 若 available foundation 声明显式 objective contract 而没有当前有效 `research_objective` projection，继续使用既有 `research_objective:projection_missing` 和 objective blocked 语义；生成 projection 的 `science.objective.project.v1` 仍必须由其 exact evidence provider cohort 准入，结构解析不能替代审批。
4. 在所有 payload/metric/objective 校验完成后，从最终 `objects` 状态重算 `available_kinds`；只允许最终状态为 `available` 或 `qualified` 的 kind 进入。若同 kind 存在多个对象，只要至少一个最终有效对象存在即可保留该 kind，不能因一个坏对象错误删除好对象。
5. 不要把 `available` 机械加入 `qualified_portfolios`、诊断 verdict、claim acceptance、execution completion 或其他 `effective_kinds` 消费。当前审查发现 foundation 受 qualified-only 影响的必要分支只有 canonical payload 校验和 `objective_contract` 结构存在判断；其他科学判断仍应保持 qualified-only。
6. 更正计划 7.6 的聚焦命令与真实计数；修复完成后重新生成清洁发布候选。根 `MANIFEST.sha256` 若在复审后更新，将形成新的待发布工作树，应在最终阶段以可复现清单命令再次校验。

## 第五轮复审验收条件

在保留本轮四阶段 provider 回归的基础上，新增并真实通过：

1. 合法 available foundation、无 objective contract：结构可用，不产生目标缺口，也不获得任何 provider 资格；
2. 合法 available foundation、含 objective contract、无 projection：对象仍为 `available`，但 objective 为 blocked，精确缺口是 `research_objective:projection_missing`；证据审批前 `science.objective.project.v1` 的 readiness 和 preflight 仍拒绝；
3. 同一 foundation 获得 exact evidence provider 决定后，objective project 候选和 preflight 同时成功，结构状态仍为 `available`；
4. 畸形 canonical foundation：对象为 `revision_required`，有明确 blocker，不在 `available_artifacts`，结构缺口包含 `scientific_foundation`；
5. 畸形 research objective/coverage/metric：对象状态、`available_artifacts`、`effective_kinds` 派生结果一致；另有同 kind 有效对象时不误删整个 kind；
6. 全仓搜索继续确认 provider 权威未回流，再复跑可复现的聚焦命令、`tests/operations`、全仓、clean release manifest、目录编译和安装脚本语法检查。

这一返工只调整 readiness 的结构解析顺序和派生库存，不需要修改审批合同、Operation 目录、参数/figure/修订链或增加任何控制实体。
