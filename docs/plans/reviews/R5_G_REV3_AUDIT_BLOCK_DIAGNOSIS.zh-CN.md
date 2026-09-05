# R5-G rev3 证据审计阻断独立诊断

诊断日期：2026-08-30  
诊断范围：真实 rev3 intake/audit 密封对象、同一实例只读 SQLite/CAS、当前 OperationSpec/Schema/角色提示、split 与资格语义  
诊断方式：未参与实现；不修改代码或科学对象，仅新增本报告

## 结论

**结论为 B，当前 rev3 audit 需要修订。**

三项缺口是真实的，但它们只阻止三类更强结论：独立重算原始 PLX→curve-bundle 身份链、独立复核
target_metrics 原始输入，以及完整重放 scorer 执行。rev3 intake 没有声称这些链已经独立闭合；它把
三项缺口逐项列入 `missing_inputs`、限制和停止边界，并据此拒绝物理因果与单变量归因。因此，缺口
不是当前 intake 的未披露事实错误，而是被正确保存的研究不确定性。

rev3 audit 前七项检查已经证明当前有界陈述与六项来源一致。第八项
`pass_grade_traceability_not_met` 的事实部分——三项输入尚未供应——正确，但它额外引入了
“审计通过必须所有潜在来源齐备”的资格门。该门不属于 `science.evidence.audit.intake.v1`：证据审计
负责检查当前对象是否忠实于精确来源，不能代替后续人工资格决定，也不能把未来观测本身当作当前
错误。它还与第五项已通过检查重复使用同一事实：第五项认可 intake 已正确披露三项缺口，第八项又
仅因这种正确披露而失败。

**不需要重跑 extraction。** 保留 rev3 intake、rev3 audit 和失败的 split 尝试不可变；只澄清本夹具
的 audit instruction，以精确 rev3 intake 和原六项来源创建独立 `r5g_evidence_audit.rev4`。rev4 不得
继承或覆盖 rev3 verdict。只有 rev4 独立核对全部陈述后给出 `pass`，才可创建新的 split revision 和
新的本地 UI 资格审批 revision。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "revise",
  "evidence": [
    {
      "source_key": "sealed_rev3",
      "source_type": "private_sqlite_and_cas",
      "locator": "replay-live-20260830-03：intake Artifact art_f8e727… / SHA-256 0e09dd8c…；audit Artifact art_528793… / SHA-256 70c21b35…；对应 scheduler signals 与完整父链"
    },
    {
      "source_key": "audit_contract",
      "source_type": "repository_contract",
      "locator": "roles/evidence_auditor.md；src/scidiscovery/general_science_resources.py:53-61,125-129；general_science_agent_operations.py:280-314；artifact_agent/schema/cognitive.py:155-190"
    },
    {
      "source_key": "admission_contract",
      "source_type": "repository_contract",
      "locator": "src/scidiscovery/general_science_control_operations.py:145-175；general_science_components.py:130-166,575-598,715-736；operations/spec.py:226-230；mcp_root_operation_routes.py:1200-1254"
    },
    {
      "source_key": "frozen_objective",
      "source_type": "frozen_fixture",
      "locator": "tests/fixtures/r5_e2e_tcad/task.zh-CN.md；evidence_contract.json SHA-256 8c45f32f…；scripts/r5_g_science_chain.py:699-707"
    },
    {
      "source_key": "focused_verification",
      "source_type": "independent_check",
      "locator": "7 GiB 串行：pass handoff + 非空 missing_inputs 的 `_evidence_audit_context` 直接核验通过；general science 精确 reviewer/split 生命周期测试 1 passed in 5.92s；SQLite/CAS 只读父链复核"
    }
  ],
  "checks": [
    {
      "check_key": "rev3_claim_support",
      "status": "pass",
      "evidence_keys": ["sealed_rev3", "frozen_objective"],
      "subject": "rev3 intake 的当前事实、数值、curve CSV 存在性和限制与六项来源一致"
    },
    {
      "check_key": "missing_input_scope",
      "status": "pass",
      "evidence_keys": ["sealed_rev3", "frozen_objective"],
      "subject": "三项缺口被准确披露，并只限制更强身份链、执行复核和因果结论"
    },
    {
      "check_key": "audit_purpose",
      "status": "fail",
      "evidence_keys": ["sealed_rev3", "audit_contract"],
      "subject": "rev3 最后一项把完整来源集合资格误作当前对象事实支持审计"
    },
    {
      "check_key": "pass_with_bounded_missingness",
      "status": "pass",
      "evidence_keys": ["audit_contract", "admission_contract", "focused_verification"],
      "subject": "当前 Schema/上下文验证允许 pass handoff 保留非空 missing_inputs"
    },
    {
      "check_key": "split_gate_behavior",
      "status": "pass",
      "evidence_keys": ["admission_contract", "sealed_rev3"],
      "subject": "split 对 blocked review 的拒绝正确，错误在上游 verdict 语义而非 admission"
    },
    {
      "check_key": "qualification_separation",
      "status": "pass",
      "evidence_keys": ["admission_contract"],
      "subject": "审计 pass 只放行精确 split，科学资格仍须独立 compiled Approval 和本地 UI 决定"
    },
    {
      "check_key": "minimal_recovery_path",
      "status": "pass",
      "evidence_keys": ["audit_contract", "admission_contract", "frozen_objective"],
      "subject": "复用 rev3 intake 与六源创建独立 audit rev4 即可，无需补造来源、重跑 extraction 或放宽核心门"
    }
  ]
}
```

## 诊断依据

### 1. 缺口真实，但不等于当前对象错误

只读 CAS 复核显示：

- rev3 intake SHA-256 为 `0e09dd8c16248d8391cddca7d1a0faddef6f06e1bcf420aeea7cbf87ba38fa0f`；
- rev3 audit SHA-256 为 `70c21b3514be882b464f75a5a14c1ba2f8efc6a91bf7c2d0cc0daa679f7c55bb`；
- intake 父链为任务 instruction 加六项精确来源；audit 父链为自身 instruction、该 intake 和同六项来源；
- 第六项来源摘要为 `0c66052f…`，审计正确复核 1504 条数据、其中 803 条 InGaAs、701 条
  InAlAs、深度范围 0.00297–0.79703 µm；
- 残差区 0.366337–0.386139 µm、峰值深度 0.380198 µm、21 点和 signed residual
  -1.0786323340881445 decade 与确定性指标一致。

intake 的三项缺口没有被用来支撑已闭合身份或因果主张。相反，其 summary、
`remaining_missing_bindings`、claim boundary 和 stop conditions 都说明：当前数据可定位失败、排除若干
错误表述并提出下一项检验，但不能独立闭合原始 PLX/target/scorer 链，也不能证明物理原因。

### 2. 第八项检查越过了 Audit 的职责

当前审计角色与编译提示要求核对“精确对象的事实、数值、条件、结构和结论是否受来源支持”，并明确
“不授予资格”。`EvidenceAudit` Schema 只要求检查项、来源和局部闭合；`RoleHandoff` 允许
`verdict="pass"` 与非空 `missing_inputs` 同时存在。上下文 validator 的机械映射是：存在 `fail` 才
`blocked`，存在 `unknown` 才 `inconclusive`，否则 `pass`；它没有“missing_inputs 非空则失败”的
规则。独立直接调用已验证 `pass + missing_inputs` 是合法合同。

`science.intake.split.v1` 要求精确 reviewer 的 handoff 为 `pass`，这是正确的 fail-closed 门：它防止
未经独立审查或存在不受支持陈述的 intake 进入下游。`science.evidence.qualify.v1` 随后再次要求精确
passing audit、完整父链和来源键，最后仍由本地 UI 的人决定是否把这组**有界证据**批准为研究基础。
因此 audit pass 不是科学资格，也不承诺所有未来证据已齐备。

rev3 的 `pass_grade_traceability_not_met` 把“是否批准为足以作任何更强结论的完整基础”提前塞入了
审计。它既不是 intake 中被断言为真的事实，也不是当前 OperationSpec 的必做资格标准。其 basis
确认 intake 已准确披露三项缺口，却以缺口存在本身给 `fail`，与
`historical_missingness_recomputed_for_current_sources=pass` 构成重复且相反的判断。

### 3. 当前 runner instruction 是触发点

通用 Auditor prompt 没有要求零缺口；当前 R5-G 专用 instruction 末句却写成“只有完整可追溯且无越界
结论才给 pass”。在同一 instruction 前文又要求审计必须保留当前三项不可用输入。这很容易被解释成
“已按要求准确披露缺口，但只要缺口存在就不能 pass”，从而使冻结任务设计成不可达闭环。

该 instruction 还写有“若仍声称曲线缺失，必须给 revise”，而当前 contextual validator 对审计的
实际映射是 `fail→blocked`、`unknown→inconclusive`、其余→`pass`，并不接受一个与检查状态无对应的
`revise` handoff。rev4 指令应使用编译合同的实际语义，不再给模型互相冲突的 verdict 要求。

## 最小修复

只修改本冻结运行的 audit instruction，不改通用 Schema、OperationSpec、split、资格 projector 或
ApprovalService。建议把判定边界写成：

1. `pass` 表示 intake 对**当前精确六源**的积极陈述、来源定位、限制和缺口披露均正确；不表示所有
   潜在来源已经存在，也不授予人工资格。
2. 三项不可用输入应继续出现在 rev4 `handoff.missing_inputs` 和相应 limitation check 中；如果 intake
   没有用它们支撑更强身份/执行/因果结论，它们的存在本身不能生成 `fail`。
3. 只有 intake 遗漏或错述这些缺口，声称未供应的字节已经验证，或据此宣称身份链闭合、物理因果、
   验收通过时，才记录 `fail` 并按当前编译语义给 `blocked`；不要求一个 validator 无法表达的
   `revise` handoff。
4. 当前环境重放和网格 A/B 是后续实验要求，不是当前 audit failure。

执行时：

```text
精确 rev3 intake + 原六项来源
→ science.evidence.audit.intake.v1（改变 instruction，create_revision）
→ 独立 audit rev4
→ 若 rev4 handoff=pass，science.intake.split.v1 创建新 revision
→ science.evidence.qualify.v1 创建新的 Approval revision
→ 仅本地 UI 决定
```

rev3 audit 的 `blocked` 必须保留；不能重标、覆盖或当作 rev4 的先验批准。

## 是否重跑 extraction

**不需要。** 本次唯一阻断来自 audit 对已正确披露缺口的状态解释；rev3 intake 的字节、来源、父链和
三项限制正是 rev4 应重新独立审查的对象。重跑 extraction 不增加证据，也不会消除三项有意保留的
缺口，只会制造无科学变化的冗余 producer revision。

本结论仅说明“不因三项已披露缺口而重跑 extraction”。rev4 仍必须独立检查 rev3 intake 的全部事实和
角色边界；若它发现另一项实质错引或越界陈述，应诚实 `blocked`，不能因本报告预设通过。

## 所需回归

1. **合同回归**：构造全部检查为 pass、`handoff.verdict=pass` 且
   `handoff.missing_inputs` 非空的 intake audit，断言 Worker contextual validator 接受。
2. **真实 admission 正例**：用精确 intake、六源和上述 passing audit 走 Root
   `operation_invoke(science.intake.split.v1)`，断言 split 成功且两个输出父链精确绑定 intake+audit。
3. **负例不放宽**：任一 material check 为 fail/blocked、unknown/inconclusive、review 绑定另一 intake、
   遗漏来源或父链漂移时，split 仍返回 `input_independent_review_missing`。
4. **runner 修订回归**：相同 rev3 intake/六源、不同 audit instruction 必须创建实际 `.rev4`；精确轮询
   该任务，rev3 Artifact/signal 保持不变，split/Approval 使用 rev4 的实际返回名。
5. **提示静态门**：R5-G audit instruction 明确“准确披露的有界缺口可与 pass 共存”，且不再包含
   “所有潜在证据齐备才 pass”或要求无法由当前 validator 映射的 `revise` verdict。

## 独立命令与结果

所有执行均严格串行，并使用 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1`：

- SQLite `-readonly` 查询 rev1—rev3 Task/Artifact/binding：完成；确认 rev3 Task 均 completed，split 仅有
  既有 rev1/rev2，无错误创建的新 revision；
- CAS 复算 rev3 intake/audit/scheduler-signal SHA-256、解析八项 checks、核对完整父链：通过；
- `PYTHONPATH=src python` 直接调用 `_evidence_audit_context`，输入 all-pass audit 与非空
  `handoff.missing_inputs`：通过，输出 `pass-with-missing accepted`；
- `pytest -q tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain`：`1 passed in 5.92s`。

