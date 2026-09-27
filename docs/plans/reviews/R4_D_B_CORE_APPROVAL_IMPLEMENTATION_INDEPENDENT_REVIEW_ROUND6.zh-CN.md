# R4-D-B 核心审批与科学资格实现第六轮独立复审

## 结论

**通过并允许进入 R4-D-C。**

第五轮唯一阻塞已经按最小口径闭合：canonical scientific foundation 无论当前对象状态如何仍先执行严格 Schema 解析；只有解析成功且最终状态精确为 `available` 的对象才贡献 `objective_contract` 存在性。`blocked`、`revision_required` 以及与合法 available sibling 并存的不可用 foundation 均不再制造目标投影缺口。

本轮没有发现 provider 第二权威、全局资格状态、注册表、缓存或新的控制实体回流。固定聚焦、Operation 全集、全仓和指定清洁发布检查全部通过。

## 审查范围与工作树口径

本轮在当前未提交工作树上只读审查，严格限定为第五轮报告冻结的五项验收及其相邻边界，重点检查：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` 的对象初始状态、canonical foundation 解析、合同存在性聚合、结构库存、候选 readiness 和 invoke preflight；
- `src/scidiscovery/artifact_agent/service/approvals.py` 的精确 provider 查询；
- `src/scidiscovery/operations/{spec.py,catalog.py,invoke.py}` 和通用科学插件中的 compiled provider 身份；
- `tests/operations/test_r4_approval_operation.py` 新增的 blocked、revision-required、mixed sibling 和既有 provider 四阶段回归；
- `docs/plans/R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 第 7.6 节；
- 指定清洁发布 `/tmp/scid-r4db-round6-final.7bENM9/scidiscovery-agent`。

由于整个 R1—R4 重构仍处于同一大型未提交工作树，本轮没有虚构远端或提交基线；语义复审以第五轮书面阻塞、当前实现和对应真实回归之间的精确差异为准。

## 五项验收结果

### 1. blocked 合同 foundation 不聚合：通过

`test_readiness_validates_available_foundations_before_deriving_inventory` 创建一个 Schema 合法、含 `ResearchObjectiveContract`、但带 `scientific_claim_admissible=false` 标签的 foundation。真实 Root readiness 结果为：

- 对象状态为 `blocked`；
- `objective_status` 为 `not_declared`；
- `mandatory_target_gaps` 为空。

因此已阻断对象不再制造 `research_objective:projection_missing`。

### 2. revision-required 合同 foundation 不聚合：通过

同一回归对另一个合法合同 foundation 注入精确 `SchedulerSignal(verdict="revise")`。Root 将对象判为 `revision_required`，目标仍为 `not_declared`，目标缺口为空。

代码顺序也与行为一致：`mcp_root.py:774-789` 先按 canonical schema 解析 payload，`mcp_root.py:790-794` 才用 `item.qualification == "available"` 限定合同存在性聚合。合法 revision-required 对象仍被读取和校验，但不再参与规划事实。

### 3. available 与不可用 sibling 并存不泄漏：通过

同一实例同时绑定：

- 一个合法、无 objective contract 的 `available` foundation；
- 一个合法、含 objective contract、但为 `blocked` 的 foundation。

结果仍为 `objective_status=not_declared`、目标缺口为空，同时 `scientific_foundation` 正确保留在结构库存。这证明聚合按对象最终状态进行，没有因同 kind sibling 发生合同事实泄漏，也没有把不可用 sibling 误当作删除整个 kind 的理由。

### 4. available 自身含合同及 exact provider 前后同步：通过

既有 `test_foundation_inventory_stays_neutral_across_provider_decisions` 对同一个真实 foundation 完成四阶段检查：

1. 无决定时，foundation 为 `available`，产生精确 `research_objective:projection_missing`；objective project 不在候选中，invoke preflight 以 `input_cohort_approval_missing` 拒绝；
2. 只有错误 parameter provider 决定时，objective project 仍不可用；
3. exact evidence provider 决定后，候选出现且真实 transform invoke 成功生成 `research_objective`；
4. evidence provider 审批合同摘要变化后，历史决定不再满足候选身份，readiness 再次拒绝。

全过程 foundation 的对象级状态保持中性 `available`。结构合同只说明必须产生投影，不能替代消费 Operation 的精确 provider 审批。

### 5. provider 权威无回流：通过

生产代码搜索确认：

- `_artifact_qualification` 不存在；
- provider-less `is_subject_approved`/`are_subjects_approved` 不存在；
- `approved_scientific_foundation` 全局缺口不存在；
- 没有 provider allowlist、qualification/provider cache 或新增资格持久状态；
- provider 查询仅由候选 readiness 和权威 invoke preflight 调用 `are_subjects_approved_by_provider`；
- 两处 accepted provider 身份都来自 consumer 的 compiled `approval_providers`。

`available` 在生产 readiness 中只有两个用途：canonical foundation 的合同存在性判断，以及完成全部校验后的结构库存投影。ExperimentPortfolio、Metric、ResearchObjective、ObjectiveCoverage、ProblemFrame、诊断和其他 `effective_kinds` 消费仍为 `qualified`-only，没有机械扩大 `available` 的权限。

## canonical payload 解析没有被修复条件短路

除代码顺序检查外，本轮独立通过真实 Root 构造了两个畸形 canonical payload：

1. 初始因 `scientific_claim_admissible=false` 应为 blocked 的对象；
2. 初始因 `SchedulerSignal(verdict="revise")` 应为 revision-required 的对象。

两者都仍触发 `invalid scientific_foundation payload`，最终为 `revision_required`，退出 `available_artifacts`，恢复结构缺口 `scientific_foundation`，且均不产生目标投影缺口。这证明修复只限制合同布尔量聚合，没有把 canonical payload 校验重新放回资格分支。

## 跨边界与简化审计

修复只在现有 readiness 派生中增加一个精确状态条件，并在同一个既有测试函数中补回归：

```python
if item.qualification == "available":
    explicit_foundation_contract = (
        explicit_foundation_contract
        or foundation.objective_contract is not None
    )
```

它没有新增 Operation、Schema、数据库表、审批入口、生命周期、缓存或注册表，也没有复制 provider 判断。Artifact 的不可变内容、对象结构状态、候选级 provider readiness 和 invoke preflight 仍各自只有一个职责。该实现符合轻控制面、最小授权和单目录 Operation 闭包目标；继续扩张为独立合同注册表或对象级审批状态反而会重新引入已经删除的复杂度。

## 独立执行证据

- 两个核心真实 Root 回归：`2 passed in 1.38s`；
- 固定聚焦命令：`72 passed in 14.08s`；
- `pytest -q tests/operations`：`202 passed in 70.82s`；
- `pytest -q`：`236 passed in 69.32s`；
- `git diff --check`：通过；
- 清洁发布 `MANIFEST.sha256`：279 条记录，连同 manifest 共 280 个文件，`sha256sum --check --quiet` 通过；
- 清洁发布零 `__pycache__`、零 `*.pyc`、零 `.pytest_cache`；
- 从发布候选源码编译核心与通用科学插件得到 32 个 Operation，其中 3 个为公开科学资格审批 Operation；
- 发布候选全部 shell 脚本 `bash -n` 通过；
- 工作树与发布候选的 Root、研究 Schema、审批服务、Operation spec/catalog/invoke 和通用科学插件 SHA-256 摘要逐项一致。

本阶段未执行真实浏览器审批、外部 TCAD solver 或 live Worker；这些不属于第五轮阻塞的结构派生修复，也不影响进入下一阶段实现执行审批身份。R4-D-C 仍需按其自身阶段门独立验证相应真实入口。
