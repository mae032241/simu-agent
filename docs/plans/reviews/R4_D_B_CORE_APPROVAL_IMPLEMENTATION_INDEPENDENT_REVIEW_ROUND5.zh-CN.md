# R4-D-B 核心审批与科学资格实现第五轮独立复审

## 结论

**打回。**

第四轮冻结的六项主体回归已经通过：合法 `available` foundation 的无合同/有合同分支、精确 provider 前后的 objective project、畸形 canonical foundation、目标/覆盖/指标好坏对象并存，以及 provider 权威隔离均有真实代码和测试证据。固定聚焦、Operation 全集、全仓和清洁发布检查也与计划计数一致。

但“只有解析成功且最终为 `available` 的 canonical foundation 才能贡献 `objective_contract` 存在性”尚未闭合。当前实现会让内容合法但已经为 `blocked` 或 `revision_required` 的 foundation 继续制造 `research_objective:projection_missing`。这把一个不可用对象重新变成了隐藏规划事实，违反本轮明确冻结的结构边界，因此不允许进入 R4-D-C。

## 审查范围与方法

本轮只读检查了：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` 的对象状态、结构解析、目标投影、候选 readiness 和权威 preflight；
- `src/scidiscovery/artifact_agent/service/approvals.py` 的精确 provider 查询；
- `src/scidiscovery/operations/{spec.py,catalog.py,invoke.py}` 和通用科学插件的编译身份；
- `tests/operations/test_r4_approval_operation.py` 的真实 Root、审批和好坏对象回归；
- 总计划第 7.2、7.6 节以及指定清洁发布候选。

审查采用跨 Artifact、readiness、Operation、Approval、preflight 边界的同一事实追踪，并按简化原则确认修复不需要新增实体、注册表或状态机。

## 第四轮六项验收结果

### 1. 合法 available foundation、无 objective contract：通过

真实回归 `test_readiness_validates_available_foundations_before_deriving_inventory` 绑定一个合法 canonical foundation。对象保持 `available`，进入 `available_artifacts`，目标状态为 `not_declared`，没有目标缺口。它没有因此获得任何 provider 资格。

### 2. 有 contract、无 projection，且审批前 objective project 拒绝：通过

`test_foundation_inventory_stays_neutral_across_provider_decisions` 使用含真实 `ResearchObjectiveContract` 的同一个 foundation。无审批决定时：

- foundation 保持 `available`；
- 目标状态为 `blocked`；
- 精确缺口为 `research_objective:projection_missing`；
- objective project 不在 `available_actions`；
- 实际 `operation_invoke` 以 `input_cohort_approval_missing` 拒绝。

结构合同存在性没有替代 provider 审批。

### 3. exact evidence provider 后 readiness/preflight 同时成功：通过

同一回归先创建错误 parameter provider 决定，objective project 候选仍缺失；再创建 exact evidence provider 决定后，候选出现且真实 transform invoke 成功产出 `research_objective`。全过程 foundation 对象状态始终是 `available`。

保留历史决定而改变 evidence provider 的审批问题后，compiled operation/approval contract 摘要变化，候选和 preflight 同时重新拒绝，对象结构状态仍不变。

### 4. 畸形 canonical foundation：通过

声明为 `scidiscovery.scientific-foundation.v1`、但内容不是 ScientificFoundation 的对象被判为 `revision_required`，产生明确 blocker，不进入 `available_artifacts`，并恢复结构缺口 `scientific_foundation`。这证明 canonical payload 校验已经从 qualified-only 分支迁出。

### 5. 畸形 objective、coverage、metric 与库存一致：通过

同一实例内同时绑定有效 foundation、有效 objective，以及畸形 objective、coverage、metric：

- 三个坏对象均为 `revision_required`；
- `available_artifacts` 排除坏 coverage 和 metric；
- 同 kind 的有效 objective 仍保留 `research_objective`，没有被坏 sibling 误删；
- 目标投影仍为 `evaluable`。

实现是在对象级校验结束后由最终状态重算 `available_kinds`，与响应中的对象状态一致。

### 6. provider 权威不回流：通过

全仓生产代码搜索确认：

- `_artifact_qualification` 不存在；
- provider-less `is_subject_approved`/`are_subjects_approved` 不存在；
- `approved_scientific_foundation` 全局缺口不存在；
- 没有 provider allowlist、资格缓存或新资格持久表；
- provider 判断只在候选 readiness 和权威 invoke preflight 两处调用 `are_subjects_approved_by_provider`；
- 两处使用的身份均来自 consumer 的 compiled `approval_providers`。

因此本轮阻塞不是审批第二权威回流，而是结构布尔量在错误状态上聚合。

## 唯一阻塞：非 available foundation 仍贡献目标合同存在性

### 代码原因

`mcp_root.py:772-793` 对 canonical foundation 做严格解析后，立即执行：

```python
explicit_foundation_contract = (
    explicit_foundation_contract
    or foundation.objective_contract is not None
)
```

对象的 `qualified` 过滤位于其后。虽然这正确地让 `available` foundation 得到结构解析，却也同时让此前已经因 label、runtime attestation 或 Worker handoff 被判为 `blocked/revision_required` 的 foundation 贡献合同存在性。

### 独立反例

独立构造一个 Schema 合法、含 `ResearchObjectiveContract`、但标签为 `scientific_claim_admissible=false` 的 canonical foundation，并通过真实 Root `scientific_readiness` 查询，得到：

```text
qualification = blocked
available_artifacts = []
unresolved_needs = [problem_frame, scientific_foundation]
objective_status = blocked
mandatory_target_gaps = [research_objective:projection_missing]
```

对象已经不在结构库存，系统却仍从它派生目标投影缺口；同一响应同时表达“foundation 不存在”和“该 foundation 声明的合同必须投影”，语义自相矛盾。`revision_required` 的合法 foundation 经过相同聚合路径，具有同类问题。

这会造成错误阻断和无效修订工作：一个已明确不可用于当前研究的旧对象可以持续控制下一行动。它虽然不会绕过 provider 准入，却违反最小控制面和“控制只校验、不替 Worker 制造科研事实”的设计目标。

## 最小修复口径

只修改现有 readiness 派生顺序，不新增任何类型、状态、表、缓存、注册表或 Operation：

1. canonical foundation 无论初始/最终状态如何都继续严格解析，以便发现畸形 payload；解析失败仍标记 `revision_required`、退出库存并产生 blocker。
2. `objective_contract is not None` 只能在该 payload 解析成功且该对象最终 `qualification == "available"` 时聚合。
3. 合法但为 `blocked` 或 `revision_required` 的 foundation 均不得制造 `research_objective:projection_missing`；若同实例另有一个合法 `available` foundation 声明合同，则只由那个对象贡献存在性。
4. 不改变 objective project 的 exact evidence provider 合同，不把 `available` 加入任何 `effective_kinds`，不恢复对象级 provider 聚合。

## 第六轮复审验收条件

在保留本轮全部回归的基础上，新增并真实通过：

1. 合法、含合同但为 `blocked` 的 canonical foundation：仍执行结构解析，但不贡献合同存在性，不制造 projection gap；
2. 合法、含合同但为 `revision_required` 的 canonical foundation：行为同上；
3. 一个无合同的合法 `available` foundation 与一个含合同但 blocked/revision-required 的 foundation 并存：目标仍为 `not_declared`，证明聚合没有跨对象泄漏；
4. 一个合法 `available` foundation 自身含合同：仍产生精确 `research_objective:projection_missing`，且 objective project 在 exact evidence provider 前后分别与 preflight 同步拒绝/成功；
5. 再次搜索确认 provider-less 查询、对象级审批聚合、全局 allowlist/资格缓存没有回流；复跑相同的 72 项聚焦、202 项 Operation、236 项全仓及重建后的清洁发布检查。

## 独立执行证据

- 固定聚焦命令：`72 passed in 13.77s`；
- `pytest -q tests/operations`：`202 passed in 63.92s`；
- `pytest -q`：`236 passed in 69.32s`；
- `git diff --check`：通过；
- 清洁发布 `/tmp/scid-r4db-round5-review.YSgi5g/scidiscovery-agent`：`MANIFEST.sha256` 278 条记录，连同 manifest 共 279 个文件，逐项摘要校验通过；
- 工作树与发布候选的 Root、研究 Schema、审批服务、Operation spec/catalog/invoke 和通用科学插件摘要一致；
- 发布候选零 `__pycache__`、零 `*.pyc`、零 `.pytest_cache`；
- 从发布候选源码精确编译核心与通用科学插件得到 32 个 Operation，其中 3 个为公开科学资格审批 Operation；
- 发布候选全部 shell 脚本 `bash -n` 通过。

测试全绿说明已有六项修复稳定，但没有覆盖上述“合法而非 available 的合同 foundation”反例，不能抵消该语义缺口。
