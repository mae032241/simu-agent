# R5-G 假设阶段最终独立审查

审查日期：2026-08-30  
审查对象：真实 `r5g_hypothesis_portfolio.rev2`、`r5g_hypothesis_critic.rev2`、密封输出、精确证据阶段 checkpoint 与只读控制状态  
审查方式：未参与科学对象生成；不修改生产代码、测试或私有科学对象；在 `/tmp` 的精确状态副本中使用同一运行环境执行 Root/Runtime 只读查询

## 结论

**打回。不得放行 `science.experiment.design.v1`。**

两个 Agent Task 都真实完成，Artifact 完整性、Operation 身份、输入和父链均正确；假设组合也保持了
有界、非因果、非新 solver 和三项缺失绑定边界。阻断原因不是运行失败或对象错绑，而是密封 critic
输出的 scheduler verdict 为 `blocked`，而生产者 `ReviewSpec` 只接受 `pass`。独立调用
`TaskService.is_exact_reviewer_output(...)` 的结果为 `false`，因此控制面会且必须拒绝该组合进入实验。

完成报告
`.scidiscovery/r5-e2e-private/replay-live-20260830-03/science-chain/hypothesis-stage-report.r5g_hypothesis_critic.rev2.output.json`
的 SHA-256 为
`c1928b3c950a4cf3106793b51438c445232abb7a65d40391616acaa8bd17bd16`。其
`status=completed` 只能证明 runner 已得到两个终态输出，不能证明独立评审被接受。该报告没有记录
critic verdict 或实验资格，不能作为下一阶段准入收据。

## 按影响排序的问题

### F1（阻断）：精确 critic 是 `blocked`，不属于生产者接受结论

只读 Root/Task/CAS 复核结果：

- `r5g_hypothesis_portfolio.rev2`：`completed`，Operation 为
  `science.hypothesis.propose.v1`，密封输出为指定 portfolio，handoff 为 `pass`；
- `r5g_hypothesis_critic.rev2`：`completed`，Operation 为
  `science.hypothesis.criticize.v1`，密封输出为指定 critic，handoff 为 **`blocked`**；
- critic 的精确输入是上述 portfolio 和证据报告所指的同一 approved foundation；输出父链同时包含
  这两个精确对象；
- portfolio 的精确输入是 `r5g_intake_split.rev3` problem frame 和同一 foundation；输出父链也同时
  包含它们；
- `science.hypothesis.propose.v1` 的 `ReviewSpec` 指定同一 critic Operation、同一
  `hypothesis_portfolio` 端口，`accepted_verdicts=("pass",)`；
- 对当前 critic 执行精确评审输出判定返回 `false`。

这是权威门禁，不是可由本审查者覆盖的建议。Task 的 `completed` 表示 Worker 生命周期完成，不能把
科学 `blocked` 改写成评审通过。

### F2（阻断）：portfolio 仍有批评者指出的可识别性自由度

portfolio 的基本方向是合理的，但当前形式还不能为 `pass` 提供充分依据：

1. `numerical_realization_replay` 同时容纳 mesh-sensitive discretization 和未枚举的
   “equivalent execution-state differences”。即使 mesh-only A/B 不支持 mesh 解释，后者仍给机制留下
   事后迁移空间。critic 因此要求把数值实现因素收窄到可预登记的单一因素或有限因素集。
2. `traceability_binding_gap` 把历史 PLX 身份、raw `target_metrics` 字节和 scorer 执行状态三个不同
   缺口合为一个“some or all”解释。当前 falsifier 能否排除整个类别是清楚的，但 positive outcome
   没有预先规定哪个精确绑定变化对应哪个有限结论，容易在观察结果后再选择解释。

critic 对两个精确 hypothesis key 都给出物理合理性和可证伪性 `pass`，给出可识别性 `fail`，并为
每项给出最小解决动作；上下文 validator 因此正确地把 handoff 确定性映射为 `blocked`。critic 没有
遗漏 key，也没有重读原始六源或授予证据资格。

三项尚未供应的绑定和未来 replay/mesh A/B 是后续实验要求，**不是本轮必须已经存在的当前观察**。
不能仅因未来数据尚未产生就判定一个假设失败；本轮需要修复的是假设的预登记边界和识别规则，而
不是补造运行结果。即使把 critic 对“当前缺少未来输入”的部分理解为偏严，以上两个自由度问题和
现有密封 `blocked` verdict 仍足以阻止放行。

因此本次打回同时落在两个最小位置，不能只选其中之一：

- **提示合同需澄清**：design-time identifiability 判断的是能否定义一个有界、预登记、可区分候选的
  未来观察和确定性结果规则。该观察尚未产生只应成为 `missing_inputs`/`next_actions`，不能自动生成
  `fail`；只有假设把未来观察伪装成当前事实、没有任何区分性观察，或结果规则允许事后迁移时才应
  判定不可识别。通用 critic 语义合同和本夹具 `_CRITIC_INSTRUCTION` 必须一致表达这一点。
- **portfolio 仍需有意修订**：本次不是纯提示误判。H1 未枚举的 realization 兜底和 H2 的
  “some or all”结果后解释空间都是真实的预登记缺口；直接用新提示重跑同一 portfolio 不能证明这些
  缺口已经消失。

### F3（阻断记录缺陷）：阶段报告把终态写成 `completed`，但没有表示资格

`scripts/r5_g_hypothesis_stage.py` 在 `_run_agent` 返回任意 completed Task 输出后，无条件写入
`status=completed`；它没有读取 critic scheduler signal，也没有调用精确 reviewer admission。因此本次
报告和真实评审资格发生语义分离。

Root 的下游 admission 仍会失败关闭，所以这不是核心旁路；但 R5-G 评估脚本和人工门禁若只读取该
报告，会把“运行完成”误认为“阶段通过”。当前历史文件必须保留不可变，不能覆盖成 pass。

## 科学内容核验

### 1. 假设组合

portfolio 含两个完整且不同的候选类别：

- 数值/实现 realization：以 byte-exact replay 和后续 mesh-only A/B 为预测及反证路径；
- scorer/target/PLX traceability：以恢复精确绑定并在同一字节上重算为预测及反证路径。

两者的证据声明只引用本任务直接可见的 `problem_frame`、`scientific_foundation` 和显式 inference；
没有伪造 foundation 内嵌六源为直接输入。每项都有机制、范围、参数、预测、falsifier 和竞争关系，
Schema 引用闭合。

portfolio 没有把历史重放称为本任务的新 solver 运行，没有把历史 mesh 差异称为已经证明的原因，
没有声称任何物理模型失效，也完整保留：历史 PLX/执行绑定、raw `target_metrics`、完整 scorer 执行
绑定三项缺口。局部尾区残差只作为已批准 foundation 中的确定性观察和后续检验目标。

### 2. 独立批评

critic 对两个 hypothesis key 各审一次，无重复或遗漏；引用只来自精确 portfolio、同一 foundation
和显式 inference。它没有再次读取或复判六项原始来源，也没有把证据审计职责带回假设阶段。

critic 的物理合理性和可证伪性判断与当前 foundation 边界一致；对可识别性的两类反对意见分别指向
未登记数值自由度和复合 traceability 假设，属于假设质量审查，而非新的来源事实。其 summary、三项
missing inputs 和下一动作与 payload 一致。

## 最小修复边界

无需重跑证据提取、证据审计、intake split 或资格 Approval；精确 rev3 problem frame、foundation 和
Approval.rev2 可继续复用。不得覆盖 portfolio.rev2、critic.rev2 或当前 stage report。

最小科学修复为：

1. 在通用 critic 模型可见语义合同和 R5-G `_CRITIC_INSTRUCTION` 中增加上述 design-time
   identifiability 边界；只改提示/语义说明和相应静态门，不新增 Schema、Operation、状态或准入特判；
2. 用现有 `science.hypothesis.revise.v1` 对 exact portfolio.rev2 创建有意修订，再经匹配的 typed
   apply Operation 产生完整新 portfolio；
3. 收窄 H1 的“equivalent execution-state differences”，只保留一个可预登记的数值实现因素，或列出
   有界、互斥且可分别判定的因素；
4. 将 H2 改为一个带确定性 decision table 的 traceability null：预先规定三个绑定各自的 identity
   检查、失败含义及允许结论；若无法保持单一机制，则在总计不超过三个候选的边界内拆分，不使用
   “some or all”作为结果后的解释自由度；
5. 对完整新 portfolio 和同一 exact foundation 创建新的独立 critic revision。只有新 critic 的每个
   维度均为 `pass`、handoff 为 `pass`，且 `is_exact_reviewer_output` 对新组合返回 true，才可放行
   `science.experiment.design.v1`；
6. R5-G runner 在下一修订中必须区分 `task_state` 与 `review_verdict`/`eligible_for_experiment`。非
   accepted critic 应写新的 blocked 记录或停止，不得再生成容易被解释为阶段合格的 completed 报告。

当前阶段真正缺少的资格证据只有：**一个绑定同一 approved foundation、精确审查完整新 portfolio、
且被 ReviewSpec 接受的密封 `pass` critic 输出**。三项原始绑定和未来 TCAD 观察是后续实验的输入与
结果，不是为本轮报告补写的当前证据。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "blocked",
  "evidence": [
    {
      "source_key": "sealed_portfolio",
      "source_type": "private_sqlite_and_cas",
      "locator": "replay-live-20260830-03：r5g_hypothesis_portfolio.rev2 completed；密封 output 9320 bytes；CAS size/SHA 与 Artifact envelope 一致"
    },
    {
      "source_key": "sealed_critic",
      "source_type": "private_sqlite_and_cas",
      "locator": "replay-live-20260830-03：r5g_hypothesis_critic.rev2 completed；密封 output 3129 bytes；scheduler verdict=blocked；CAS size/SHA 与 Artifact envelope 一致"
    },
    {
      "source_key": "approved_foundation",
      "source_type": "private_sqlite_and_cas",
      "locator": "evidence-stage report e9470066…；r5g_intake_split.rev3 problem frame + scientific_foundation；Approval.rev2=approve；foundation 13297 bytes且完整性匹配"
    },
    {
      "source_key": "review_contract",
      "source_type": "compiled_operation_and_root",
      "locator": "science.hypothesis.propose.v1 ReviewSpec：reviewer=science.hypothesis.criticize.v1，subject port=hypothesis_portfolio，accepted verdict=pass；当前 exact reviewer check=false"
    },
    {
      "source_key": "stage_report",
      "source_type": "private_run_record",
      "locator": "hypothesis-stage-report.r5g_hypothesis_critic.rev2.output.json；SHA-256 c1928b3c…；status=completed但未记录critic verdict或实验资格"
    },
    {
      "source_key": "independent_checks",
      "source_type": "isolated_runtime_and_test",
      "locator": "7 GiB 串行：精确状态副本 Root/Task/CAS 父链及 reviewer 判定；聚焦 7 passed in 0.84s"
    }
  ],
  "checks": [
    {
      "check_key": "task_and_artifact_integrity",
      "status": "pass",
      "evidence_keys": ["sealed_portfolio", "sealed_critic"],
      "subject": "两任务真实完成，密封输出与 Artifact 大小/摘要一致"
    },
    {
      "check_key": "foundation_and_subject_lineage",
      "status": "pass",
      "evidence_keys": ["sealed_portfolio", "sealed_critic", "approved_foundation"],
      "subject": "portfolio、critic 和 problem frame 精确绑定同一已批准 foundation，critic 精确绑定该 portfolio"
    },
    {
      "check_key": "hypothesis_scope_and_testability",
      "status": "fail",
      "evidence_keys": ["sealed_portfolio", "sealed_critic", "approved_foundation"],
      "subject": "两个类别有界且可证伪，但 H1 的未枚举 realization 自由度和 H2 的复合 some-or-all 规则尚未达到独立 critic 的可识别性通过门"
    },
    {
      "check_key": "critic_completeness_and_scope",
      "status": "pass",
      "evidence_keys": ["sealed_critic", "sealed_portfolio", "approved_foundation"],
      "subject": "critic 覆盖所有 key，保留证据和未来观察边界，未重复原始来源审计"
    },
    {
      "check_key": "review_admission",
      "status": "fail",
      "evidence_keys": ["sealed_critic", "review_contract"],
      "subject": "blocked critic 不属于唯一 ReviewSpec 接受的 pass，实验设计准入未成立"
    },
    {
      "check_key": "stage_report_honesty",
      "status": "fail",
      "evidence_keys": ["stage_report", "sealed_critic", "review_contract"],
      "subject": "completed 报告仅表达任务终态，遗漏 blocked verdict 和实验资格，不能作为阶段通过证明"
    }
  ]
}
```

## 独立命令与结果

所有命令严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

- 将原运行的 `state/`、`project/` 和本地密钥复制到 `/tmp` 隔离目录；所有 Root/Runtime 查询只针对
  该副本，原私有状态未写入；
- 使用该运行自带 `runtime-venv` 查询两个 `task_status`、四个 `artifact_catalog`、Approval 状态、
  Task Operation authority、精确输入和输出父链：通过；
- 对 portfolio、critic、foundation 的密封字节复算大小和 SHA-256，并与 Artifact envelope 对比：
  三者均匹配；
- 调用生产 `is_exact_reviewer_output`：当前 critic 返回 `false`；
- `pytest -q` 聚焦 critic handoff、模型可见语义、mixed-foundation 守卫和 R5-G runner：
  `7 passed in 0.84s`。

未运行全仓测试：当前阻断来自真实密封 verdict 和精确生产准入判定，重复全仓测试不能把该科学结论
变成 `pass`。
