# R5-G rev4 证据审计运行前独立复审

复审日期：2026-08-30  
复审范围：rev3 审计阻断的最小提示修复、真实 Worker/Root 回归、持久 rev1—rev3 只读状态  
复审方式：未参与实现；不修改代码、测试或科学对象，仅新增本报告

## 结论

**通过。**

放行边界严格限定为：

```text
复用精确 r5g_evidence_extract.rev3 密封输出
→ 以相同六项来源和新 instruction 创建独立 r5g_evidence_audit.rev4
→ 仅当 rev4 的全部物质问题检查支持 handoff=pass 时，创建新的 intake split revision
→ 创建新的 evidence qualification Approval revision
→ 等待本地 UI 的新决定
```

**不放行假设阶段，不把 audit pass 当作科学资格，也不宣称 R5-G 或 R5 完成。**

未发现阻断缺陷。新提示修复了 rev3 的唯一语义错误：准确披露的有界未知量可以与“当前对象忠实于
当前六源”的审计通过并存；同时它没有把 `pass` 预先写死，也没有放宽错述、遗漏、伪验证、身份链、
因果或验收越界的失败边界。通用 Schema、上下文 validator、split、资格 projector、ApprovalService
和核心 admission 均未被修改。

## 按影响排序的问题

### 阻断项

无。

### 非阻断改进项

1. 当前 runner 单元测试直接冻结了提示语义与 Approval 实际名称/不可变报告，但没有在一个临时
   Runtime 中单独模拟“已存在 rev3 Task + 新 instruction → `.rev4`”的完整调用。该行为已有三层独立
   证据：通用 `_creation_target`/Agent fingerprint 实现、持久实例中真实 rev1—rev3 递增记录、runner
   始终消费 `operation_invoke` 实际返回名。因此它不阻止本次运行；运行后仍须把实际 rev4 名、Task
   父链、旧 rev3 Artifact/signal 未变列入下一门的只读核验。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "pass",
  "evidence": [
    {
      "source_key": "audit_instruction",
      "source_type": "repository_code",
      "locator": "scripts/r5_g_science_chain.py:38-52,343-374,674-779；SHA-256 e4381571…"
    },
    {
      "source_key": "audit_and_admission_contract",
      "source_type": "repository_code",
      "locator": "src/scidiscovery/general_science_components.py:129-166,575-598,707-736；artifact_agent/interfaces/mcp_root_operation_routes.py:161-204；artifact_agent/interfaces/mcp_root.py:288-335"
    },
    {
      "source_key": "worker_root_regression",
      "source_type": "repository_test",
      "locator": "tests/operations/test_general_science_plugin.py:193-218,424-821；tests/operations/test_r5_g_science_chain_runner.py:23-93"
    },
    {
      "source_key": "persistent_revision_state",
      "source_type": "private_sqlite_and_cas",
      "locator": ".scidiscovery/r5-e2e-private/replay-live-20260830-03：task bindings r5g_evidence_extract rev1-rev3 与 r5g_evidence_audit rev1-rev3；rev3 intake SHA-256 0e09dd8c…；rev3 audit SHA-256 70c21b35…"
    },
    {
      "source_key": "independent_checks",
      "source_type": "independent_test",
      "locator": "7 GiB 严格串行聚焦 11 passed in 48.11s；py_compile、git diff --check、SQLite -readonly 和 CAS 摘要复核通过"
    }
  ],
  "checks": [
    {
      "check_key": "bounded_missingness_semantics",
      "status": "pass",
      "evidence_keys": ["audit_instruction", "audit_and_admission_contract"],
      "subject": "准确披露且未被用于更强主张的三项缺口不再被误判为当前对象事实失败"
    },
    {
      "check_key": "failure_boundary_preserved",
      "status": "pass",
      "evidence_keys": ["audit_instruction", "audit_and_admission_contract"],
      "subject": "缺口错述或遗漏、伪称未供应字节已验证、曲线存在性错述及身份/因果/验收越界仍映射到 fail→blocked，未知仍映射到 inconclusive"
    },
    {
      "check_key": "pass_is_not_qualification",
      "status": "pass",
      "evidence_keys": ["audit_instruction", "worker_root_regression"],
      "subject": "pass 只允许精确 split，假设 Operation 在新的人工资格决定前继续失败关闭"
    },
    {
      "check_key": "exact_review_and_source_lineage",
      "status": "pass",
      "evidence_keys": ["audit_and_admission_contract", "worker_root_regression"],
      "subject": "split 和资格仍要求精确 reviewer、精确 intake、完整冻结来源与对应父链，非 passing 或不相关审计不能绕过"
    },
    {
      "check_key": "revision_isolation",
      "status": "pass",
      "evidence_keys": ["audit_instruction", "audit_and_admission_contract", "persistent_revision_state"],
      "subject": "相同 extraction 指纹复用 rev3，新 audit instruction 进入下一不可变任务修订；旧 rev3 verdict 不被继承或改写"
    },
    {
      "check_key": "minimal_change",
      "status": "pass",
      "evidence_keys": ["audit_instruction", "worker_root_regression", "independent_checks"],
      "subject": "修复只澄清夹具提示并加强既有回归，没有新增实体、注册表、状态机或资格旁路"
    }
  ]
}
```

## 五项回归逐项核对

### 1. `pass + 非空 missing_inputs` 合同

通过。真实测试不是直接调用内部 validator，而是创建 `science.evidence.audit.intake.v1` Task，经过
Worker claim、materialize、受控文件写入、validate、finalize，再读取密封输出。审计的 material check
为 `pass`、handoff 为 `pass`，同时 `missing_inputs` 非空，完整生命周期被接受。

这与生产 validator 一致：`_validate_audit_handoff_and_sources` 只按 material check 将 `fail` 映射为
`blocked`、`unknown` 映射为 `inconclusive`、否则映射为 `pass`；它没有把
`handoff.missing_inputs` 当作失败门。

### 2. 真实 Root split 正例和精确父链

通过。同一回归在 passing audit 完成后真实调用 `operation_invoke(science.intake.split.v1)` 并成功产生
两个输出；前置不相关 audit 被拒绝，passing audit 的父链包含精确 intake。随后资格 projector 再要求
该 split、audit 和冻结来源的完整组合；缺少冻结来源时真实调用以 `approval_projector_failed` 拒绝。

### 3. 负例未被放宽

通过：

- 不相关/错误父对象的 audit 不能满足 exact reviewer；
- 非 passing scheduler signal 不能进入 split；
- 缺少冻结来源不能创建资格 Approval；
- 生产上下文 validator 对任何 `fail` 强制要求 `blocked`，对任何 `unknown` 强制要求
  `inconclusive`；二者都不属于 reviewer 合同接受的 `pass`；
- 新提示明确保留缺口遗漏、缺口错述、未供应字节伪验证、曲线存在性错述以及身份/因果/验收越界的
  `fail→blocked` 边界。

因此修复只去掉了“非空缺口自动失败”，没有把缺口内容正确性或来源完整父链降级。

### 4. rev3/rev4 修订隔离与 runner 实际名称

通过。Agent Task fingerprint 明确编码 Operation 身份、instruction、精确 inputs、output 合同和预算；
同 fingerprint 返回既有对象，不同 fingerprint 且 `create_revision` 才取下一 revision。runner 从
`operation_invoke` 结果读取 `actual_name`，后续 dispatch、binding resolve、Task status、私有任务目录
和完成报告都使用该实际名称，而不是固定逻辑名。

持久实例只读查询确认 extraction 和 audit 各自的 rev1—rev3 都是独立 binding，rev3 Task 均为
`completed`，其密封 Artifact/signal 摘要分别保留。当前仅 audit instruction 改变；因此下一次执行
会复用精确 extract.rev3，并为 audit 取下一修订。split 和 Approval 也都以 audit 实际返回的
`audit_name` 绑定，并使用 `create_revision`；旧决定不能被新 subjects 继承。

### 5. 提示静态门和是否存在诱导

通过。静态门冻结了四条关键语义：

- 准确披露的有界缺口自身不能生成 fail；
- 三项缺口仍必须保留在 `handoff.missing_inputs`；
- 后续环境重放/网格 A/B 是未来实验要求；
- audit pass 不表示潜在来源齐备，也不授予科学资格；同时禁止旧的“必须给 revise”和“才给 pass”
  措辞。

提示没有要求 Agent 给 `pass`。它要求重新检查六项精确来源，只有当前对象的积极陈述、locator、限制
与缺口披露全部正确时才允许 pass，并具体列出仍应 fail/blocked 的错误。给出待审问题、已供应来源
和不可供应边界属于冻结评价合同，不是给出 audit verdict；`unknown/inconclusive` 路径也被保留。

## 资格与阶段边界

审计通过和科学资格仍是两个不同事件：

1. passing audit 只满足 extraction 输出的 exact independent-review admission；
2. split 只是把同一受审 intake 确定性投影为 problem frame 与 foundation；
3. `science.evidence.qualify.v1` 再次验证 producer family、精确 audit 和全部冻结来源，随后只创建
   pending Approval；
4. 未作新的本地 UI 决定前，`science.hypothesis.propose.v1` 的 preflight/invoke 仍以
   `input_cohort_approval_missing` 拒绝；
5. 当前脚本在资格 Approval 后结束，不创建任何假设 Task。

因此本次提示修复没有把“允许带缺口的诚实审计”偷换为“允许未经资格的科学结论”。

## 奥卡姆与架构目标

这是最小且正确的修复：没有为本夹具新增 Schema、Operation、状态、注册表或特例 admission，只把
错误的零缺口语义从一次运行的 instruction 中移除，并复用既有 Everything-is-Operation、Worker 文件
生命周期、精确 reviewer、deterministic split 和本地 UI Approval。它符合轻控制面、最小授权、来源
可追溯及插件化通用科学 Agent 的目标，没有复杂度反噬。

## 独立命令与结果

所有命令严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

- `pytest -q tests/operations/test_r5_g_science_chain_runner.py tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain tests/operations/test_r4_approval_operation.py::test_changed_approval_subject_creates_pending_revision_without_old_decision tests/operations/test_r5_frozen_baselines.py`：`11 passed in 48.11s`；
- `python -m py_compile scripts/r5_g_science_chain.py tests/operations/test_r5_g_science_chain_runner.py tests/operations/test_general_science_plugin.py`：通过；
- `git diff --check --` 三个候选文件：通过；
- SQLite `-readonly`：确认 extraction/audit 各自 rev1—rev3 binding、request fingerprint 互异且 rev3
  Task completed；
- CAS SHA-256：rev3 intake 为 `0e09dd8c16248d8391cddca7d1a0faddef6f06e1bcf420aeea7cbf87ba38fa0f`，
  rev3 audit 为 `70c21b3514be882b464f75a5a14c1ba2f8efc6a91bf7c2d0cc0daa679f7c55bb`；
- 候选 SHA-256：runner `e4381571…`，general-science 回归 `b6565fe5…`，runner 测试
  `dfb0a552…`。

## 后续门禁

真实 rev4 运行后，下一位独立审查者至少必须确认：

1. extraction 实际返回精确 rev3 密封输出，没有创建无内容变化的 rev4；
2. audit 实际名称为 `r5g_evidence_audit.rev4`，其 instruction 父对象、rev3 intake 和六项来源精确；
3. rev3 audit Artifact 与 blocked scheduler signal 的摘要未变；
4. rev4 自己重新声明来源、检查全部物质问题，并把三项缺口同时保留在检查限制与
   `handoff.missing_inputs`；
5. 只有 rev4 实际为 pass 才出现新的 split 与 pending Approval revision，且 Approval 仍须由本地 UI
   独立决定；
6. 在该决定被独立核验前，不得启动假设 Agent。

