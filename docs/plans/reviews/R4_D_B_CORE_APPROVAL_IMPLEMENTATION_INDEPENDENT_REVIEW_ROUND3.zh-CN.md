# R4-D-B 核心审批与科学资格实现第三轮独立复审

## 结论

**打回。**

第二轮打回的参数、figure 和 typed revision 三条生产链均已按要求闭合，两个 provider-less 旧查询也已删除；但 readiness 的返工以“扫描当前目录中同 kind 的全部 approval provider，任意一个决定即可把对象标为全局 qualified”替代了旧查询。这仍然聚合了候选无关的 provider 权威，并能在真实链路中产生“对象已 qualified、全局审批缺口消失，但精确候选仍不可用且 preflight 拒绝”的矛盾。本轮不允许进入执行审批身份阶段。

## 独立证据

本轮只读核验并复跑：

- 三条关键纵向测试：真实通用证据/八层修订、真实 metadata-only 参数 bridge、真实 figure bundle，共 `4 passed`；
- 聚焦五文件：`56 passed`；
- `tests/operations`：`200 passed`；
- 全仓：首次因本审查诊断导入产生的一个源码 `pyc` 缓存触发部署洁净测试失败；只删除该次诊断生成的精确缓存后，失败项 `1 passed`，全仓重新执行为 `234 passed`；
- `git diff --check` 通过；
- 清洁发布 `/tmp/scid-r4db-round3.mBBpOj/scidiscovery-agent` 的 `MANIFEST.sha256` 为 280 条受控文件记录，加 manifest 本身共 281 个非缓存发布文件；`sha256sum --check --quiet`、核心/通用科学目录编译和两个安装脚本 `bash -n` 均通过。目录编译得到 32 个 Operation，其中三个 public approval Operation 正确存在。

基线没有 `scripts/validate_architecture_constraints.py`，本报告未宣称执行该脚本。

## 已闭合项

### 1. provider-less 旧方法已删除

`ApprovalService.is_subject_approved` 和 `are_subjects_approved` 已不存在；全仓也没有对应调用或同名替代。权威准入仍只调用 `are_subjects_approved_by_provider`，没有增加资格缓存、持久表或独立注册表。

### 2. metadata-only 参数来源已穿过真实生产链

`TaskService` 已将错误的来源集合全等改为 observation keys 是 catalog keys 的子集，同时要求每个 catalog source 出现在 intake evidence，并且是冻结 Task 输入或冻结 web source。真实测试经过 legacy 提取 Task 的 Worker validate/finalize、split、deterministic coverage、真实参数 audit Task 和 pass approval invoke。

独立负向诊断进一步确认：

- observation 引用未知 source 时，Worker validation 以 `parameter observation references an unknown source` 失败；
- catalog/intake 新增但未作为 Task 输入或 web snapshot 冻结的 source，以 `unknown task-local input source` 失败；
- 一个 value source 加一个 metadata-only source 时，最小独立来源要求为 1 得到 `pass + independent_source_count=1`，要求为 2 得到 `review_required + independent_source_count=1`。metadata-only 项没有贡献数值比较、coverage 或独立来源计数。

建议把上述两个负向诊断固化为真实 bridge 回归测试，但当前生产实现本身已失败关闭，不单独构成第二个代码阻塞项。

### 3. figure 完整族完成门已真实化

测试从 `science.evidence.extract.figure.v1` 的真实 Task/Worker collection 开始，封存 manifest、panel、overlay、curve table 和 deterministic validation report；随后真实运行 figure audit Task、split 和 qualifier 正例。遗漏一个 collection item、validation、frozen source 或 extraction primary 的四次调用均从 Root `operation_invoke` 失败，不再只验证人工 projector 快照。

### 4. 八层 typed revision 已经过真实 Root 边界

测试从已资格化 intake 连续产生八层 revise Task、patch、deterministic apply 和独立 audit，并为最终层生成 exact diff、receipt 和 split；最终 qualifier 在真实 family resolver 深度边界失败。普通 transform、缺 diff 等原有反例仍保留。

### 5. 架构形态没有扩张

参数、figure 和修订返工仍使用同一 compiled Operation catalog、既有 Task/Artifact/Approval 生命周期和即时 family snapshot；没有新增状态机、资格表、领域注册表或第二调用入口。

## 唯一阻塞：对象级 readiness 仍形成全局 provider 聚合

`scientific_readiness` 对每个对象调用 `_artifact_qualification`（`mcp_root.py:663-709`）。该函数遍历整个 compiled catalog，收集所有 `approval contract.kind == envelope.kind` 的 provider；只要其中任一 provider 的接受决定包含该对象 ref，就返回 `qualified`（`mcp_root.py:966-1017`）。随后该 kind 进入 `effective_kinds`，`approved_scientific_foundation` 从全局 unresolved 中消失（`mcp_root.py:844-848`）。

这不是静态 allowlist或缓存，但在语义上仍是**由全目录动态形成的全局 provider 集合**。它忽略消费候选冻结的 `accepted_approval_operations`。候选级 `_approval_cohorts_ready` 则正确使用该候选自己的 provider identity（`mcp_root.py:1019-1075`），因此两层投影会互相矛盾。

独立复现使用了真实 metadata-only 参数链和真实 `science.parameters.qualify.pass.v1` 审批决定。决定后结果为：

```text
foundation.qualification = qualified
unresolved_needs = []
science.hypothesis.propose.v1 in available_actions = false
```

这是可达场景，不是理论误报：参数 provider 的完整决定包含 foundation ref，所以对象被全局提升；但 hypothesis consumer 只接受 `science.evidence.qualify.v1`，其 readiness 和 preflight 正确拒绝参数 provider。当前 provider A/B 测试只断言 `available_actions` 与 preflight，并且测试 Artifact kind 与 provider kind 不相等，因此没有覆盖对象状态这个断口（`test_r4_approval_operation.py:1959-2098`）。

该行为直接违反冻结计划 7.2：对象库存最多报告存在 provider 决定，不能升级为对所有候选有效的全局 qualified（计划 `530-534`）。计划 7.6 新写的“任一精确 provider 决定后恢复 qualified”（`741-744`）与 7.2 自相矛盾，应以 7.2 和候选精确身份原则为准。

## 最小修复口径

1. 在 `ScientificObjectStatus.qualification` 增加中性 `available`，表示对象结构存在、payload/producer 没有已知失败，但不表达任何候选的审批资格。
2. 对存在多 provider 语义的 kind（当前明确是 `scientific_foundation`），对象级始终使用 `available`，不因任何 provider 决定变成 `qualified`；删除 `_artifact_qualification` 对全目录 provider 的扫描。不要增加 allowlist、provider 聚合缓存、资格状态或新表。
3. provider 决定只在候选级 `_approval_cohorts_ready` 和 authoritative invoke preflight 中解释，二者继续使用消费 Operation 已编译的 exact provider identities。
4. `unresolved_needs` 改成纯结构语义：没有 foundation 时报告 `scientific_foundation`；有 foundation 后不再报告全局 `approved_scientific_foundation`。不同候选缺哪个 provider 只体现在该候选不可用及其精确 preflight，不能聚合成全局审批结论。
5. 内部 readiness 计算应明确区分“结构可用 kind”和“候选资格”：`available` foundation 可以满足结构存在判断，但不得绕过候选 approval cohort。不要简单把所有依赖 `effective_kinds` 的判断机械改成接受 `available`，须确认 claim/evaluation 等消费的是结构事实还是资格事实。
6. 修订计划 7.6，删除“决定后恢复全局 qualified”的陈述，使其与 7.2 一致。

## 第四轮复审验收条件

必须使用同一个真实科学 foundation 覆盖以下序列：

1. 无审批决定：对象为 `available`，结构缺口中没有虚构的全局 approval 结论；仅接受 evidence provider 的 hypothesis 候选不可用，invoke preflight 拒绝。
2. 只有 parameter pass/exception provider 决定：对象仍为 `available`；hypothesis 仍不可用且 preflight 拒绝；接受参数 provider 的精确 TCAD/参数候选按自己的完整 cohort 决定是否 ready。
3. exact evidence provider 决定：对象仍为 `available`；hypothesis available action 与 invoke preflight 同时成功。
4. provider disable/upgrade 或合同摘要变化：对象结构状态不变，但相应候选 readiness 和 preflight 同时失效。
5. 全仓搜索确认没有对象级全 provider 扫描、provider-less 查询、全局 allowlist、资格缓存或新状态；随后复跑聚焦五文件、`tests/operations`、全仓、clean release manifest 和安装脚本检查。

完成这一处收缩后，参数、figure、修订和 Operation 单目录边界无需再次重构，只需防回归复核。
