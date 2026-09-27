# R5-G 证据阶段最终独立审查

审查日期：2026-08-30  
审查对象：真实 rev4 证据审计、split.rev3、资格 Approval.rev2、只读 SQLite/CAS/Root 状态与现场 UI 记录  
审查方式：未参与实现或科学对象生成；不修改代码、测试或受控运行状态，仅新增本报告

## 结论

**通过。只放行进入假设阶段。**

本结论不放行实验设计、TCAD author/reviewer、R5-G 总体完成或 R5 发布，也不把已知 UI 可用性缺陷
标成已解决。

完成报告
`.scidiscovery/r5-e2e-private/replay-live-20260830-03/science-chain/evidence-stage-report.r5g_evidence_qualification.rev2.json`
的 SHA-256 为
`e9470066cce9d7834e28c76fe8eac61c5d06bd8fa133e601c41c0292f699c581`。报告声明的 intake、audit、
split 两输出和 Approval 名称均与独立读取的 SQLite binding、CAS payload、父链和 Root 查询一致；本
审查没有把报告自身当作权威来源。

rev4 audit 是新的真实 Operation Agent 输出，不是对 rev3 verdict 的改写。它独立核对了 target 身份、
失败 gate、局部残差、curve CSV 身份/行数、历史 missingness、当前三项缺口和无因果/非新重放边界；
七项 material check 全部为 `pass`，scheduler signal 为 `pass`，同时保留三项
`missing_inputs`。split.rev3 与 Approval.rev2 的精确对象链闭合，Approval.rev2 是新的回环 UI
决定，未继承 Approval.rev1。

## 按影响排序的问题

### 阻断项

无。

### 必须继续公开的未闭合项

#### I1：审批 UI 可用性仍未通过，但不阻断假设阶段

`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` §11.5 和私有现场记录都明确：
审批生命周期、精确对象绑定和唯一写入权威有效，但页面信息架构、可理解性和操作效率未通过。
当前决定的 CAS/SQLite 收据没有显示对象错绑、旧决定继承或聊天代批；本独立审查也再次核对了其
九个精确 subjects。因此，按已冻结计划，该产品缺陷**不阻断继续评价科学链和进入假设阶段**。

它仍阻断以下声明：

- 不得宣称 R5-G 的 UI 验收完成；
- 不得以一次成功点击代替真实用户可用性验收；
- 不得在 R5-G 最终报告或发布清单中把 UI 可用性写成通过。

#### I2：三项来源缺口继续约束下游结论

以下内容仍未供应：原始历史 PLX 加执行绑定、`target_metrics` 原始字节、完整 scorer 执行绑定。
它们不使当前有界 audit 失败，但 hypothesis Worker 必须把它们保留为限制，不能声称原始身份链、
完整 scorer 执行或物理因果已经闭合。下一阶段仍须围绕已有矛盾提出可证伪解释，不能把资格审批
解释成机制接受。

### 非阻断改进项

1. `evidence-approval-ui.log` 保留了一次历史 CLI 启动的 `ModuleNotFoundError`，随后存在成功启动/停止
   记录并产生了新的本地 UI 收据。该失败没有污染决定或科学对象，但最终运行报告可按 §11.4 将其
   归为外部环境/启动配置失败，避免只展示最终成功。
2. rev4 的七项检查已经覆盖两类解释边界和下一实验边界；后续独立审查仍应显式逐项检查假设
   portfolio 的每个 hypothesis key，而不能认为本次 evidence audit 已预先认可任何具体机制。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "pass",
  "evidence": [
    {
      "source_key": "sealed_rev4",
      "source_type": "private_sqlite_and_cas",
      "locator": "replay-live-20260830-03：audit Task tsk_72bb…；Task payload SHA-256 b7613f14…；audit Artifact art_bb8b… / f73ddcb5…；signal art_133b… / 53742bc3…"
    },
    {
      "source_key": "exact_six_sources",
      "source_type": "private_cas",
      "locator": "evaluation contract 8c45f32f…；metric 7f3a5fe6…；bundle manifest 684d106d…；historical audit 72a70ea4…；deck diff 452135f0…；curve CSV 0c66052f…"
    },
    {
      "source_key": "split_lineage",
      "source_type": "private_sqlite_and_cas",
      "locator": "problem_frame art_dda5… / b665c432…；foundation art_f61b… / f53a57f0…；两者 parent[0:2] 均为 exact intake art_f8e7… + exact audit art_bb8b…"
    },
    {
      "source_key": "approval_revision",
      "source_type": "private_sqlite_and_cas",
      "locator": "Approval apr_ead5…；request 988d6b27…；review manifest 4735c6a6…；decision 51015a7b…；subject-set SHA-256 60d07a55…；local_ui_session"
    },
    {
      "source_key": "immutable_history",
      "source_type": "private_sqlite_and_cas",
      "locator": "rev3 blocked audit 70c21b35… / signal 18b66a97…；Approval.rev1 request 9ea5b781… / decision e1804aa8…；append-only records and distinct revision bindings"
    },
    {
      "source_key": "ui_boundary",
      "source_type": "plan_and_private_observation",
      "locator": "docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md §11.5；science-chain/ui-usability-observation.zh-CN.md"
    },
    {
      "source_key": "independent_verification",
      "source_type": "independent_test",
      "locator": "7 GiB 串行聚焦 12 passed in 44.73s；原状态只读 SQLite/CAS；状态副本真实 Root query 与 hypothesis preflight admissible=true"
    }
  ],
  "checks": [
    {
      "check_key": "rev4_scientific_content",
      "status": "pass",
      "evidence_keys": ["sealed_rev4", "exact_six_sources"],
      "subject": "rev4 对当前 intake 的 target、gate、残差、curve CSV、三项缺口及因果边界判断与六项来源一致"
    },
    {
      "check_key": "rev4_exact_parentage",
      "status": "pass",
      "evidence_keys": ["sealed_rev4", "exact_six_sources"],
      "subject": "rev4 是独立 pass audit，父链精确包含新 instruction、rev3 intake 和同六源"
    },
    {
      "check_key": "split_exact_parentage",
      "status": "pass",
      "evidence_keys": ["split_lineage", "sealed_rev4"],
      "subject": "split.rev3 两输出均精确绑定 rev3 intake 与 rev4 audit，内容为 intake 的确定性投影"
    },
    {
      "check_key": "approval_exact_revision",
      "status": "pass",
      "evidence_keys": ["approval_revision", "split_lineage", "exact_six_sources"],
      "subject": "Approval.rev2 绑定 foundation、intake、六源和 rev4 audit，并由新的回环 UI 会话决定 approve"
    },
    {
      "check_key": "history_not_inherited",
      "status": "pass",
      "evidence_keys": ["immutable_history", "approval_revision", "sealed_rev4"],
      "subject": "rev3 blocked audit、失败准入边界和 Approval.rev1 保持不可变，新决定未继承旧 subject set 或 old decision"
    },
    {
      "check_key": "ui_status_is_honest",
      "status": "pass",
      "evidence_keys": ["ui_boundary", "approval_revision"],
      "subject": "审批权威有效和 UI 可用性未通过被分别陈述，未用一次点击掩盖产品缺陷"
    },
    {
      "check_key": "hypothesis_gate",
      "status": "pass",
      "evidence_keys": ["approval_revision", "independent_verification"],
      "subject": "资格完成后 exact problem_frame+foundation 的真实 Root preflight 可进入假设阶段，且尚无假设 Task 被提前创建"
    }
  ]
}
```

## 1. rev4 科学内容核验

### 1.1 target 与禁止结论

`source_material_001` 把 frozen Fig.4 target 定义为本回归的用户给定比较目标，并明确禁止把它提升为
独立合格论文证据。rev3 intake 保留了同一边界；rev4 的
`target_identity_boundary` 检查明确审计这一点，没有把 target、InAlAs、candidate 或 Fig.7 提升为
当前结论来源。

### 1.2 失败 gate 与局部残差

metric 源的精确字节 SHA-256 为 `7f3a5fe6…`，同时也是 typed metric Artifact 与只读 science view
的 payload：

- `baseline_recovery.pass=false`；
- `crossings=false`、`full_rms=false`、`lower_width=false`、
  `max_abs_residual=false`、`target_front_rms=true`；
- 唯一登记的局部 residual region 为 `0.366337–0.386139 µm`；
- 共 21 点，峰值深度 `0.380198 µm`，signed residual
  `-1.0786323340881445 decade`。

rev4 对这些字段逐项给出 exact locator 和 source key，没有重新计算或改变确定性指标，也没有把失败
归因于物理机制。

### 1.3 curve CSV

独立复算确认 source view 与 typed curve Artifact 字节相同，SHA-256 均为 `0c66052f…`，大小
106766 字节：

- 文件 1505 行，其中一行为 header、1504 行数据；
- `ingaas` 803 行，`inalas` 701 行；
- 全文件深度范围 `0.002970–0.797030 µm`；
- active bundle manifest 和 metric `input_digests.curve_bundle` 记录同一摘要。

因此 rev4 的 `curve_csv_presence_identity_counts` 及其 locator 正确。它没有把 historical replay
描述为新 solver，也没有用 CSV 自身补造原始 PLX/执行绑定。

### 1.4 三项缺口和无越界结论

rev4 scheduler signal 保留且仅保留三项 `missing_inputs`：

1. 用于独立复算原始 PLX→curve-bundle 身份链的历史 PLX 与执行绑定；
2. raw `target_metrics` bytes；
3. 绑定实现、参数、输入、输出和终态的完整 scorer execution。

所有七项 audit check 为 `pass`，但 summary 明确把判断限定为六源内的事实、locator、限制和缺口披露。
它没有宣称三项链已闭合，没有把 deck diff 的 mesh 变化当作因果证据，也没有把未来 replay/mesh
A/B 冒充当前观察。

## 2. rev4 任务与父链

只读 Task/CAS 核验：

- Task `tsk_72bb…` 状态为 `completed`、attempt=1；
- Operation 为 `science.evidence.audit.intake.v1`，digest `62826938…`；
- Task input 顺序为 exact rev3 intake，随后六项来源；
- output Artifact `art_bb8b…` 的 parent 0 是新 instruction `49754f25…`，parent 1 是 rev3 intake
  `0e09dd8c…`，parent 2—7 是上述六项来源；
- output 还以 `task` 关系绑定 exact rev4 Task；
- signal `53742bc3…` 为 `pass`，含三项 missing_inputs。

Agent 运行报告记录 `invoke_state=created`、`task_state=completed`、Codex return code 0；父进程只
spawn 并返回固定传输信号，子 Agent 通过 exact Worker server 执行 claim、materialize、受控写入、
validate 和 finalize。科学结论来自密封 Artifact，不来自聊天。

## 3. split.rev3

`r5g_intake_split.rev3` 两个输出分别为：

- problem frame：`art_dda5…` / payload `b665c432…`；
- scientific foundation：`art_f61b…` / payload `f53a57f0…`。

两者的 parent 0/1 都严格为 rev3 intake `art_f8e7…` 与 rev4 audit `art_bb8b…`，没有 rev3 blocked
audit 或旧 intake。独立结构比较确认 problem frame 与 intake 对应对象相同；foundation 的差异仅为
Schema 默认字段的显式规范化，Pydantic 语义对象相同，未增加科学判断。

## 4. Approval.rev2

### 4.1 精确 subjects

Approval request `988d6b27…`、review manifest `4735c6a6…`、human decision `51015a7b…` 的
subject 顺序一致，共九项：

1. split.rev3 foundation；
2. rev3 intake；
3. evaluation contract；
4. metric source view；
5. active bundle manifest；
6. historical audit；
7. deck diff；
8. curve CSV source view；
9. rev4 audit。

subject-set SHA-256 为 `60d07a55…`。Approval request、review manifest、decision 及 Artifact parent
links 均绑定这组对象；没有额外对象、遗漏来源或重排。

### 4.2 新 UI 决定与旧决定隔离

Approval.rev2 使用新的 approval id、request、nonce、review manifest、decision id、UI session 和
subject-set SHA。决定记录为：

- `selected_option=approve`；
- `decided_by.authentication_method=local_ui_session`；
- `previous_decision_ref=null`；
- rationale 为空；
- 决定父链为新的 Approval request 加同一九项 subjects。

数据库中的 `decision_attempts` 记录独立 `ui_*` session；没有聊天消息字段或调度器代批路径。私有
human-action 文件只声明 `local_loopback_ui_only` 和必须显式 UI 决定。由此可确认新决定未继承
Approval.rev1，也不是把聊天文字转换为批准。

## 5. 历史不可变性

- rev3 blocked audit payload 仍为 `70c21b35…`，其 blocked signal 仍为 `18b66a97…`；
- rev4 使用不同 Task、instruction、output 和 signal，没有 supersede 或覆盖 rev3；
- rev3 blocked audit 未产生一个错误的新 split binding；当前 split.rev3 只在 rev4 pass 后创建；
- Approval.rev1 request 仍为 `9ea5b781…`，旧 decision 仍为 `e1804aa8…`，旧 subject-set
  `fd1555cc…`；
- Approval.rev2 是独立 binding/revision 2，new request/decision 均没有 previous decision；
- Artifact 与 Approval 数据表具有 append-only 触发器，当前只读查询未发现更新或删除历史记录。

因此 rev3 失败结论和旧批准仍是可审计历史，没有被新通过结果重写。

## 6. 是否放行假设阶段

在私有状态的临时副本上，用当前实际 CompiledCatalog 和真实 Root facade 执行：

- `task_status(r5g_evidence_audit.rev4)` 返回 completed 及 exact output；
- `approval_status(r5g_evidence_qualification.rev2)` 返回 revision 2、decided、approve；
- exact `problem_frame=r5g_intake_split.rev3` 与
  `scientific_foundation=r5g_intake_split.rev3.scientific_foundation` 的
  `operation_preflight(science.hypothesis.propose.v1)` 返回 `admissible=true`。

原始实例中尚无 hypothesis/idea Task binding，说明本阶段没有提前创建下游科学对象。因此现在只放行
调度一个最短、受当前矛盾和三项缺口约束的 `science.hypothesis.propose.v1`；其输出仍须经过独立
critic/audit 门，不能跳到实验或 TCAD。

## 7. 独立命令与结果

所有测试与 Python 查询均严格串行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDWRITEBYTECODE=1
```

主要结果：

- `sha256sum evidence-stage-report.r5g_evidence_qualification.rev2.json`：
  `e9470066cce9d7834e28c76fe8eac61c5d06bd8fa133e601c41c0292f699c581`；
- SQLite `-readonly` 查询 scheduler bindings、Tasks、Artifacts、parent links、Approval request/
  decision/events/nonces：通过；
- CAS 逐项读取 rev3 intake、rev4 audit/signal、六源、split 两输出、Approval request/manifest/decision：
  通过；
- curve CSV `sha256sum`、`wc` 与串行 `awk`：1505 行、1504 data rows、803 InGaAs、701 InAlAs、
  深度范围 0.002970–0.797030 µm；
- Pydantic 严格解析 rev4 EvidenceAudit 与 SchedulerSignal：7 checks、6 sources、all pass、signal pass、
  3 missing inputs；
- 临时状态副本的真实 Root sanitized query/preflight：audit completed、Approval.rev2 decided/approve、
  hypothesis preflight admissible；临时副本随后删除；
- `pytest -q tests/operations/test_r5_g_science_chain_runner.py tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain tests/operations/test_r4_approval_operation.py::test_changed_approval_subject_creates_pending_revision_without_old_decision tests/operations/test_r5_frozen_baselines.py tests/operations/test_baseline_approval_ui.py::test_installed_approval_ui_seals_exact_subject_and_one_decision`：
  `12 passed in 44.73s`。

未运行全仓测试：本门没有修改共享生产合同，当前目标是复核一组已生成的密封运行对象；上述聚焦
测试覆盖了 exact reviewer、split、资格隔离、冻结 fixture、真实 installed UI 和 Root admission。全仓
回归不能替代这些对象级只读证据，且本阶段无需重复已有 R5-F 全仓证据。

## 后续门禁

本报告只允许进入假设阶段。下一阶段至少应满足：

1. hypothesis Agent 只读取本次批准的 problem frame/foundation，不直接读取控制身份或把旧 audit
   当成新证据；
2. portfolio 至少保留两个可证伪解释，同时显式说明三项来源缺口；
3. 不把网格 prior、历史 replay、用户 target 或资格 Approval 解释成物理机制证据；
4. independent critic 和 evidence audit 分别检查可识别性与来源支持，任何旧 verdict 不继承；
5. 在 portfolio 独立门通过前，不放行 experiment design 或 TCAD authoring。

