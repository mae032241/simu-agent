# R5-G 证据阶段第二修订独立跨边界审查

审查日期：2026-08-30  
审查范围：R5-G 证据阶段第二修订的精确工作树、持久私有运行证据和同一实例的只读数据库/CAS  
审查方式：未参与实现；只读源码、会话、数据库和冻结字节，仅新增本报告

## 结论

**打回。不放行后续假设阶段。**

控制面链路本身已经真实闭合：两个第二修订任务均由外层 Codex 只调用一次
`spawn_agent`，实际参数为 `fork_context=false`；子智能体无父对话历史，只在精确
Operation Worker 中领取任务、物化 assignment、读取六项任务输入，并经受控写入、校验和
finalize 完成。第二修订的六项来源、两个字节不变来源视图、split 父链和本地 UI 决定也都可由
SQLite/CAS 独立复核。插件只从 `scidiscovery.plugins` 进入同一 CompiledCatalog，未发现通用核心
领域分派、第二注册表或新增状态机。

但已批准的第二修订科学对象存在一项直接与精确输入冲突的事实错误：提取结果和独立审计都把
`curve_bundle` 列为未提供，而其第六项精确来源正是该 `frozen_curve_bundle` 的字节不变视图。
独立审计没有消解历史审计中的旧缺口，仍给出 `pass`，随后 split 和人工资格审批把这个错误固化
进了当前 scientific foundation。该问题属于科学证据正确性，不是未来观察项，不能用生命周期、
Schema 校验或一次人工点击替代。

此外，当前脚本不能安全完成这项必要修订：Agent 和 split 使用了 `create_revision`，但资格 Approval
仍固定使用原名且未请求修订，轮询也硬编码原名；顶层 human-action/report 文件又只在不存在时写入。
因此，直接重跑会发生 Approval 指纹冲突，或留下仍指向第二修订的陈旧“completed”报告。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "revise",
  "evidence": [
    {
      "source_key": "implementation_contract",
      "source_type": "repository_files",
      "locator": "scripts/r5_g_science_chain.py；tests/fixtures/plugins/r5_e2e_tcad_plugin/；tests/fixtures/r5_e2e_tcad/manifest.json；tests/operations/test_r5_frozen_baselines.py"
    },
    {
      "source_key": "live_agent_sessions",
      "source_type": "private_runtime_trace",
      "locator": ".scidiscovery/r5-e2e-private/replay-live-20260830-03/science-chain/r5g_evidence_{extract,audit}.rev2/ 的 agent-run-report、codex-events、两份 codex-sessions 和 runtime summaries"
    },
    {
      "source_key": "immutable_state",
      "source_type": "sqlite_and_cas",
      "locator": ".scidiscovery/r5-e2e-private/replay-live-20260830-03/state/database/ 与 state/artifacts/sha256/；只读查询第二修订 Task、Artifact、binding、Approval、父链和 scheduler signal"
    },
    {
      "source_key": "sealed_science_outputs",
      "source_type": "runtime_artifact",
      "locator": "rev2 intake SHA-256 e62ddeda…、rev2 audit SHA-256 39314681…、metric source SHA-256 7f3a5fe6…、curve source SHA-256 0c66052f…"
    },
    {
      "source_key": "ui_observation",
      "source_type": "private_observation_and_plan",
      "locator": "science-chain/ui-usability-observation.zh-CN.md、evidence-stage-report.json、approval SQLite；docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md §11.5"
    },
    {
      "source_key": "focused_verification",
      "source_type": "independent_test",
      "locator": "7 GiB 限制下串行 pytest tests/operations/test_r5_frozen_baselines.py：7 passed in 38.33s；相关 py_compile、hash、diff-check 和静态 rg"
    }
  ],
  "checks": [
    {
      "check_key": "real_spawn_and_worker_lifecycle",
      "status": "pass",
      "evidence_keys": ["live_agent_sessions", "immutable_state"],
      "subject": "真实外层 spawn、无父上下文、受控 Worker 文件生命周期和聊天非科学权威"
    },
    {
      "check_key": "six_sources_and_revision_lineage",
      "status": "pass",
      "evidence_keys": ["implementation_contract", "immutable_state"],
      "subject": "六项精确来源、两个字节不变来源视图、第二修订父链以及第一修订不可变保留"
    },
    {
      "check_key": "scientific_content_consistency",
      "status": "revise",
      "evidence_keys": ["sealed_science_outputs", "immutable_state"],
      "subject": "审计错误地把已供应的精确 curve bundle 声明为缺失并给出 pass"
    },
    {
      "check_key": "split_and_human_qualification",
      "status": "pass",
      "evidence_keys": ["immutable_state", "ui_observation"],
      "subject": "当前运行的 split 与资格审批精确绑定第二修订 producer family，决定只由本地 UI 写入"
    },
    {
      "check_key": "ui_authority_vs_usability",
      "status": "pass",
      "evidence_keys": ["ui_observation"],
      "subject": "安全/写入权威通过和界面可用性未通过被诚实分开"
    },
    {
      "check_key": "manifest_plugin_and_negative_gates",
      "status": "pass",
      "evidence_keys": ["implementation_contract", "focused_verification"],
      "subject": "manifest、插件闭包、Operation digest、clean-wheel 入口和已有负例"
    },
    {
      "check_key": "core_plugin_boundary",
      "status": "pass",
      "evidence_keys": ["implementation_contract", "focused_verification"],
      "subject": "科学来源视图逻辑留在评估插件，无核心领域分派、第二 registry 或状态机"
    },
    {
      "check_key": "revision_retry_closure",
      "status": "revise",
      "evidence_keys": ["implementation_contract", "immutable_state"],
      "subject": "固定 Approval 名和只写一次的顶层报告不能承载必要的下一修订"
    }
  ]
}
```

## 阻断问题

### F1 — 已批准 foundation 对精确曲线来源作出相反陈述

严重度：阻断。

持久状态证明：

- `frozen_curve_bundle` 是 `ingaas.fig4-frozen-curve-table.v1`，大小 106766 字节，
  SHA-256 为 `0c66052f…`；
- `r5.fixture.fig4-science-source-view.v1` 产生的 `curve_source` 是 `source_material/opaque`
  且字节摘要仍为 `0c66052f…`；两个视图各自的父链都精确包含 metric report 和 curve bundle；
- 第二修订提取、第二修订审计及资格审批的父链/subjects 都包含该 `curve_source`；
- 实际 CSV 有 803 行 InGaAs 数据，范围 0.00297–0.79703 µm；目标残差区间有 21 点并包含
  0.380198 µm。提取和审计报告的确定性数值与 metric/CSV 一致。

与此相反，第二修订 intake 的 `missing_inputs`、`traceability_gap`、
`exclude_simple_staged_file_mismatch` 和 handoff 都声称不可变 curve bundle 字节未提供；独立审计也
重复“仍缺失”并给出 `pass`。这是把历史独立审计的旧 `missing_inputs` 原样继承到了已经新增
curve source 的新证据集合，而不是对完整六项来源重新审计。

同一科学对象还有一处关联的来源定位不严谨：其 `task_boundary` 把“target 不是独立论文证据”归到
`source_material_001`，但冻结 task 文件只声明网格、重放和通用性边界；target 的用户定义位于外层
manifest/本次 Operation instruction。该边界本身是正确的用户约束，但不能把未包含它的 source 001
写成支持定位。

最小修复：

1. 保留第二修订、原人工决定和全部旧对象不可变；以同一六项精确来源创建新的提取、独立审计、
   split 和资格审批修订。
2. 新 intake 必须从当前完整来源集合重新计算缺口：删除“curve bundle 未提供”，把未能独立复算
   raw-PLX→bundle 身份的原因准确写成未供应 raw historical PLX/相应执行绑定；仍可保留确实未供应的
   `target_metrics` 与 scorer execution binding。
3. 新 audit 必须逐项核对更新后的缺口，不能继承旧 verdict；只有所有 changed statements 与六项
   来源一致时才可 `pass`。
4. target 身份边界应明确标成任务给定的用户约束，不得引用未包含该陈述的 source locator；若输出
   合同要求证据键，应先提供包含该定义的有界冻结来源，再运行 Agent。

### F2 — 当前 runner 不能安全提交上述必要修订

严重度：阻断。

`scripts/r5_g_science_chain.py` 对两个 Agent 和 `science.intake.split.v1` 使用现有 revision 机制，
但 `science.evidence.qualify.v1` 仍使用固定名字 `r5g_evidence_qualification`，没有
`on_conflict="create_revision"`，并用同一固定名查询 `approval_status`。不同 subjects 的新审批不是
原审批的幂等重试，按当前合同应失败关闭。

同时，`human-action-evidence-qualification.json` 与 `evidence-stage-report.json` 均只在文件不存在
时写入。即使从别处手工创建新审批，顶层记录仍会继续把第二修订报告成当前完成对象，破坏运行证据
的可复核性。

最小修复：

1. 只复用既有 scheduler revision：资格 Approval 明确请求 `create_revision`，捕获调用结果返回的
   实际审批名，并只按该名字查询状态；不得新增 Approval 服务、表或状态机。
2. 私有运行记录按实际 revision 使用新文件名，或在已有文件与当前结果不一致时失败关闭；不得静默
   保留旧“completed”作为新运行证据。
3. 增加一个受控修订回归：先存在已决定的旧 qualification，再以不同精确 subjects 创建新修订；
   断言旧决定不被继承，新决定只经 UI，最终报告只指向新 revision。

## 已通过的边界

- 两份外层 Codex 会话各只有 `spawn_agent` 与 `wait_agent`；实际调用记录为
  `fork_context=false`，子会话元数据为 `thread_source=subagent`，父历史未注入。
- 子 Worker 会话只领取对应 Operation assignment；数据库活动链包含 dispatched、claimed、
  materialized、validated、finalized。父进程最终文本是固定传输信号，没有复制科学 payload。
- 第一修订的错误媒体类型 Artifact、Task 和输出仍在 append-only 状态中；第二修订使用新的任务、
  正确的 `text/plain` 来源和不同请求指纹，split/Approval 没有绑定第一修订输出。
- 审计 handoff 的机械 verdict 确为 `pass`；其余重要边界没有越界：历史回放没有被称为新 solver，
  target 没有被称为独立论文证据，网格差异只作为待检验数值先验，失败门和残差数值与冻结指标一致。
- 本地 UI 的最终决定记录显示 `local_ui_session` 写入 `approve`；聊天未成为决定。计划 §11.5 和现场
  观察都明确写出 UI 信息架构、可理解性和效率**未通过**，没有用安全性结论掩盖用户反馈。
- 当前 manifest SHA-256 为 `6f0df8a6…`；四个插件闭包文件摘要与 manifest 一致；support Operation
  digest `4b30b634…` 与 clean-wheel catalog 一致。源码静态搜索未在 `src/` 或生产插件发现该评估
  Operation/组件标识。

## 测试未覆盖但应保留的风险

1. 当前聚焦测试验证 source view 字节不变、父链和一个非法 metric 负例，但不验证 Agent 对
   “历史审计旧缺口 + 新增来源”的集合消解；F1 正是这种语义盲区。
2. CSV source view 的局部 validator 只检查非空、逗号和换行。当前持久绑定由 exact CAS/hash 证明
   正确，因此不构成本次额外阻断；若该 Operation 将来脱离冻结 manifest 复用，应增加错误表头、
   非法行/材料和内容漂移负例，或把用途继续严格限制在本夹具。
3. Agent 真实日志记录了只读 `exec_command`/Python 分析，但 `agent-run-report.json` 只汇总模型、
   时长和会话摘要，未结构化记录实际原生工具集合与 token。R5-G 最终与单 Agent 比较前仍需从
   会话证据生成可复核的实际预算/工具收据；这是后续验收要求，不是本阶段当前科学错误之外的新
   失败。
4. UI 可用性未通过是已观察到的产品缺口，不是推测风险。按 §11.5 可在不改变当前决定权威的前提下
   后续重构，但 R5-G/R5 最终报告不得宣称 UI 完成。

## 独立命令记录

所有测试命令均先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

- `pytest -q tests/operations/test_r5_frozen_baselines.py`：`7 passed in 38.33s`；
- `python -m py_compile scripts/r5_g_science_chain.py`：通过；
- 相关路径 `git diff --check`：通过；
- manifest/插件文件/CAS 逐文件 SHA-256：一致；
- SQLite 只读查询、CAS 字节检查、session JSONL 工具调用审计：完成。

测试通过只证明既有机械合同；它不能推翻 F1 的原始科学对象与精确来源矛盾。
