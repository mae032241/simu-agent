# R5-G D4-H blocked 结果独立诊断

## 一、结论

**结论：实现通过但科学结果阻断，可进行一次有界 D4-H2 修订。**

真实 run `.scidiscovery/r5-e2e-private/replay-live-20260830-03` 的 D4-H 控制链按设计失败关闭：完整
portfolio revision 与新 critic Task 均为 `completed`，新 critic 是
`science.hypothesis.criticize.v1` 对新 portfolio 的精确 reviewer 输出，其密封 scheduler signal 为
`blocked`；阶段报告据此写入 `status=blocked`、`review_contract_admissible=false`、
`stage_admissible=false`、`experiment_design_released=false`。没有实验设计、solver 或其他下游被
放行。

主要归因是 **A：修订 Agent 的科学判断没有完全解决原审查指出的可识别性缺陷**。新对象已经把
第二项“复合且不可分别判定的追踪性解释”收敛为单一 whole-chain closure 假设，并被新 critic 判为
三维 `pass`；但第一项 numerical-realization 假设仍以“任一局部指标下降”为 mesh-primary 支持，
没有预登记足以区分“主要原因”与“一般 mesh sensitivity/偶然局部改善”的阈值或分类规则。这仍是
原“未封闭的事后解释自由度”的残留，不是新的框架问题。

没有证据支持 B（instruction/context/Schema/validator/OperationSpec 使任务不可解或误判）、C（critic
不合理）或 D（数据/证据不足导致本次设计任务无法完成）为主要原因。当前 OperationSpec 已拥有再做
一次直接完整修订所需的精确 `prior_draft`、`change_request` 和 approved
`scientific_foundation` 端口；无需修改核心、Schema、validator、OperationSpec 或资格机制。

本结论只允许考虑一次有界 D4-H2 完整对象修订及全新独立 critic。它不放行实验设计、solver、
外部执行、R5 发布冻结或把当前 blocked 转换为 pass。

## 二、范围与证据纪律

审查对象是当前未提交工作树和真实状态
`.scidiscovery/r5-e2e-private/replay-live-20260830-03/state-d4-abi8`。完整阅读并交叉核验：

- `scripts/r5_g_hypothesis_revision_stage.py`；
- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4Q_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4Q_POSTRUN_INDEPENDENT_REVIEW.zh-CN.md`；
- hypothesis revise/critic 的当前 OperationSpec、prompt、Schema、semantic/context validator 和最小相关
  测试。

科学内容只从 SQLite 确认的 `completed` Task 所登记的 sealed primary Artifact 读取，并逐项复算
CAS payload SHA-256。没有采信 `codex-final.txt`、`codex-events.jsonl`、session rollout、child chat、
工作区 draft 或 daemon 日志中的科学内容；没有调用 Root/Worker MCP，没有 claim Worker，没有调度
Agent，没有访问网络，没有运行 solver，也没有修改真实状态或审批。

## 三、机器核验

### 1. 精确 completed 输出与谱系

SQLite、Artifact registry 和 CAS 给出以下闭合关系：

| 对象 | Task / Artifact | 终态 / payload SHA-256 |
| --- | --- | --- |
| 旧 portfolio | `tsk_ab9ae01b42ea4ad29b9fc3d3b6abbf93` / `art_80d377aac57f44788267fc4f2cde49bc` | `completed` / `55b2713ef5afd60369d8604026e81d1e05206b44943929f1abe4d29c8cdb8c7c` |
| 旧 blocked critic | `tsk_63417f8241664c6ead14e5ce15eda91c` / `art_dd8573afa6b149a3a33575122cb8566e` | `completed` / `165d219ffd6f4a749e8b57e3fcf40d0cbea7a984176ee20550d86424f9a48295` |
| 新 portfolio revision | `tsk_c90638bdaf0b41a89a64123e2bcd43aa` / `art_3932949c418e4103a4964f56f50d5794` | `completed` / `584bbb2050dfde3acca93c7d5830050d5d020e029f39b242f42d240fd6e6ed5b` |
| 新 critic | `tsk_18b1ffed024345c39e5fc03f7a5219ff` / `art_4c8436c6be624193b6b2665861d9fffa` | `completed` / `30b21f05261e64cdd1aa3b52b95989eb9bcb0bf3b02a1ab97d5acd8cfe4f8119` |
| 当前 foundation | — / `art_e83715c2fb404cac8ccf33317ec181d1` | approved / `4f134362942c35608187c995e65756f67145d2c2505c68472244ba42af11939b` |

修订 Task 的冻结 authority 为 `science.hypothesis.revise.v1`，三个直接输入按端口精确为旧 portfolio、
旧 blocked critic、当前 foundation；Task 与新输出的 parent 链均保持这三个对象及密封 instruction。
新 critic 的冻结 authority 为 `science.hypothesis.criticize.v1`，其
`hypothesis_portfolio` 输入精确等于新 revision Artifact，另一个输入精确等于同一当前 foundation；
新 critic output 的 task edge 回指该 exact critic descriptor。

新 critic scheduler signal Artifact 为 `art_05b55eb0f06a4fc0ae8e6a0934e94c82`，payload SHA-256
为 `54df8738a9b2c36df871295290b3dd92915727eaf60cfa71610a320caac750fc`，密封 verdict 为
`blocked`。critic payload 恰好逐项覆盖新 portfolio 的两个 hypothesis key；其中一个
`identifiability=fail`，因此与当前 context validator 的 `blocked` 映射一致。这满足
`is_exact_reviewer_output` 的四个机械条件：completed operation output、正确 reviewer operation、
精确 reviewer input port/subject ref、存在且匹配的 scheduler signal。

当前 foundation 仍是 `r5g_evidence_qualification_abi8` 的九对象 ApprovalRequest 首项；Approval 数据库
记录 request 为 `decided`、HumanDecision option 为 `approve`。D4-H 没有替换或继承旧 ABI 6 决定。

### 2. 阶段报告没有把完成态冒充科学通过

`hypothesis-revision-stage-report.r5g_hypothesis_revision_critic.output.json` 的 SHA-256 为
`4d6e64e89db11ef23a16c214b9fdba44e6a72f7b376b42402e654b5c1d101444`。其关键字段为：

```text
status=blocked
revision_task_state=completed
critic_task_state=completed
critic_verdict=blocked
review_contract_admissible=false
independent_scientific_review=not_released
stage_admissible=false
experiment_design_released=false
```

因此 runner 正确区分了“任务完成”和“科学通过”，D4-H blocked 不是控制层误报。

## 四、旧 change request、新完整对象与新 critic 的逐项比较

### 1. `numerical_realization_replay`：部分修正，但关键缺陷仍在

旧 critic 指出两点：该解释在三项绑定闭合前无法与 comparison-chain 问题区分；机制还用
`equivalent execution-state differences` 保留了未登记的兜底自由度。其最小动作是先闭合三项绑定并
恢复 byte-exact replay，只有成功后才执行唯一的 mesh-only A/B。

新 portfolio 已作出真实改进：

- 明确删除 generic execution-state drift，只保留 replay 恢复后的 mesh-only 对比；
- 把三项绑定、历史 replay prerequisite、两种固定 mesh state、同一 scorer/target 和 front RMS 保持
  pass 写入完整新对象；
- 保持原范围、两项假设和三项缺失绑定，没有把未来 replay/A-B 写成已发生观察。

但新 support/rejection 规则仍过弱。它把“一侧相对另一侧降低局部 peak residual 和点数”写为支持，
而 rejection 仅覆盖 failed-gate vector 不变且两个局部量都不下降的情况。这样，任意微小下降、数值
噪声或普通 mesh sensitivity 都可避免 rejection，却不足以支持“mesh 是主要原因”。该结果仍可在
观察后通过解释口径移动而存活，未完成本次指令要求的“有界、可预登记的决策规则”。

新 critic 因此给出 `physical_plausibility=pass`、`falsifiability=pass`、
`identifiability=fail`，最小动作是预登记一个能区分 mesh-primary、普通 sensitivity 和 unchanged
failure 的精确 recovery threshold 或 failure-vector 分类门。这是对旧第一项缺陷的连续、合理审查，
不是扩大到新科学框架。

### 2. `traceability_binding_gap`：旧缺陷已被完整对象修订解决

旧对象把 historical PLX identity、raw target_metrics bytes、scorer execution state 三种潜在差异捆绑
成一个解释，并允许“some or all”改变或重分类结果；旧 critic 因无法分别归因和事后自由度给出
`identifiability=fail`。

新对象没有为三个 sub-binding 分别编造新因果假设，而是把主张收窄为一个 end-to-end closure
package：三项必须全部存在，同一 bound bytes 上两次独立 rescoring 必须复现同一 classification；若
整包 cleanly closes 且结果复现，则该假设直接 rejected，不再事后拆解或重解释。新 critic 对该项的
physical plausibility、falsifiability、identifiability 均给出 `pass`。

这证明“旧完整对象 + exact change request + approved foundation → 完整替代对象 → 原 reviewer
重审”的机制正常工作；blocked 不能反推直接修订架构失败。

### 3. 证据语言清理是有界附带问题，不是 blocked 根因

新 portfolio 将 `prior_draft`、`change_request` 和 `scientific_foundation` 都列为 `frozen_input`
evidence。前两者确实是 revision Task 的直接输入，因而通过当前 source-binding validator；但它们是
待修对象和评审请求，不是已批准事实来源，而且新 critic 只直接绑定新 portfolio 与 foundation。
新 critic 要求把只来自旧稿/旧评审的事实性措辞删除或显式标成 inference，这与计划中
`revision_base`/`change_request` 不提升为 claim evidence 的边界一致。

这项措辞清理可在同一次有界修订中完成。它没有造成当前 blocked verdict——机械 blocked 来自
`numerical_realization_replay.identifiability=fail`——也不要求给 critic 追加旧输入或修改 validator。

## 五、A/B/C/D 归因

| 类别 | 判断 | 理由 |
| --- | --- | --- |
| A 修订 Agent 科学判断未解决缺陷 | **是，主要原因** | 第一项假设虽去掉 generic fallback，却仍用无最小效应量/分类门的方向性改善支持 mesh-primary；旧事后自由度只被缩小，未闭合。 |
| B instruction/context/Schema/validator/OperationSpec 不可解或误判 | 否 | instruction 明确要求只修两项缺陷、完整对象、保留三项缺失绑定及有界可预登记决策规则；三个必要输入均完整暴露。Schema 的 prediction/falsifier/parameter 字段足以表达固定分类门，OperationSpec 也已支持 exact blocked change request。 |
| C critic 不合理 | 否 | critic 没有因未来观察尚未产生而失败，也没有重审原始来源；它接受已闭合的 whole-chain 假设，只对 mesh-primary 与一般 sensitivity 不可区分给出 fail，并给出单一最小修订动作。 |
| D 数据/证据不足 | 否（仍有既有缺口） | 三项缺失绑定仍真实存在，但当前阶段只需设计未来可识别的假设和 decision rule。approved foundation 已给出 failed-gate vector、局部窗口、现有阈值语义和 replay→mesh A/B 顺序，足以预登记判定规则；不需要先生成未来数据。 |

因此本阶段是在检验并部分证明直接完整修订根因已消除，没有把架构断裂移到 reviewer；剩余阻断是
一个具体、可由同一专业 Agent 再修一次的科学对象质量问题。

## 六、最小正确下一步与停止门

若当前调度资格允许一次新 revision，最小下一步是一次 **D4-H2**：

1. `science.hypothesis.revise.v1` 的 `prior_draft` 绑定当前新 portfolio
   `r5g_hypothesis_portfolio_revision.output`；
2. `change_request` 绑定对该精确对象的当前 blocked critic
   `r5g_hypothesis_revision_critic.output`；
3. `scientific_foundation` 继续绑定当前 approved
   `r5g_d4_intake_split_abi8.scientific_foundation`；
4. 修订范围只限于 critic 已指出的 mesh-primary 决策门和证据语言清理；保留已通过的 whole-chain
   假设、两项假设上限、三项缺失绑定、既有范围和非因果边界；
5. 输出完整替代 portfolio，再由新的 `science.hypothesis.criticize.v1` 独立审查，不继承任何 verdict。

以上三个输入和 exact reviewer 关系都已由当前 OperationSpec 表达，**无需核心修改**，也无需新增
Schema 字段、validator 特判、Operation、资格权威、状态或修订框架。若 D4-H2 preflight 对这组 exact
绑定不再 admissible，应停止并诊断该精确准入失败，不得绕过；若新 critic 仍非 `pass`，立即停止，
不得继续多轮优化或放行实验。即使新 critic 为 `pass`，仍须保持 `stage_admissible=false`，等待新的
独立科学复审。

## 七、最小测试证据

所有测试严格串行并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
```

执行：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_general_science_plugin.py::test_general_science_manifest_compiles_exact_role_and_variant_operations \
  tests/operations/test_general_science_plugin.py::test_valid_critic_context_checks_the_worker_handoff \
  tests/operations/test_general_science_plugin.py::test_worker_visible_semantics_are_specific_and_parentage_is_fail_closed \
  tests/operations/test_general_science_plugin.py::test_reviewer_operation_binding_retains_exact_subject_parent
```

结果：`14 passed in 0.42s`。

该集合覆盖 D4 runner 的完整对象/blocked 报告门、ABI 8 checkpoint、直接修订结构与端口用途、critic
handoff/context 映射、模型可见 semantic constraints 和精确 reviewer subject 合同。另以只读
SQLite/CAS 对真实四个 completed Task、输出 ref、parent/task edge、scheduler signal、当前 foundation
Approval 与 payload SHA-256 作了机器复核。

没有运行全仓测试、浏览器、Agent、网络或 solver；它们不是本次“blocked 科学结果归因与一次有界
revision 是否需要核心修改”的最小必要证据。
