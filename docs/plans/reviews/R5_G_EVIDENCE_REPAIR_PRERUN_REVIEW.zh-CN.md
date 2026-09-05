# R5-G 证据阶段修复运行前独立复审

审查日期：2026-08-30  
审查对象：第一次证据阶段审查的 F1/F2 最小修复候选  
审查方式：未参与实现；只读代码、合同、测试与既有 UI 观察，仅新增本报告

## 结论

**通过。放行启动真实 rev3 证据提取与独立审计 Agent；不放行假设阶段，也不宣称 R5-G 或 R5 完成。**

第一次审查的两个阻断均已闭合：

- F1：Worker 不再接收完整评估 manifest。新建的 1798 字节 `evidence_contract.json` 只冻结科学问题、
  用户定义 target、允许/禁止结论和当前来源边界；脚本在注册前校验 manifest 记录的精确 SHA-256。
  合同明确曲线 CSV 已提供，区分了当前真正未供应的原始字节/执行绑定与未来实验，没有预设具体
  机制、因果结论或下一实验答案。
- F2：证据资格调用使用既有 `create_revision`，随后只使用调用实际返回的审批名和 revision；轮询、
  human-action 记录及 completed 报告均按该实际名称分修订保存，内容不一致时失败关闭。底层回归证明
  旧审批决定不会进入新 subjects；runner 回归证明上层不会退回固定名称或陈旧报告。

已知审批 UI 的安全/决定权威与可用性结论仍被明确分开：本修复没有改写 UI、ApprovalService 或决定
路径，也没有把既有“基本不可读”现场反馈改成通过。该产品缺口仍按主计划 §11.5 后续处理，不阻止
本次真实 rev3 科学对象的重新产生与再次独立审查。

## EvidenceAudit

```json
{
  "schema_version": 1,
  "verdict": "pass",
  "evidence": [
    {
      "source_key": "repair_implementation",
      "source_type": "repository_files",
      "locator": "scripts/r5_g_science_chain.py SHA-256 00f68ce4…；tests/fixtures/r5_e2e_tcad/manifest.json SHA-256 64792dac…；tests/fixtures/r5_e2e_tcad/evidence_contract.json SHA-256 8c45f32f…"
    },
    {
      "source_key": "revision_contract",
      "source_type": "repository_code",
      "locator": "scripts/r5_g_science_chain.py:209、274、306、651、659、687、713、736；src/scidiscovery/general_science_agent_operations.py:323"
    },
    {
      "source_key": "regression_evidence",
      "source_type": "independent_test",
      "locator": "tests/operations/test_r5_g_science_chain_runner.py；test_r4_approval_operation.py::test_changed_approval_subject_creates_pending_revision_without_old_decision；test_r5_frozen_baselines.py；7 GiB 串行复跑 9 passed in 37.67s"
    },
    {
      "source_key": "ui_boundary",
      "source_type": "plan_and_private_observation",
      "locator": "docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md §11.5；.scidiscovery/r5-e2e-private/replay-live-20260830-03/science-chain/ui-usability-observation.zh-CN.md"
    }
  ],
  "checks": [
    {
      "check_key": "evaluation_contract_scope",
      "status": "pass",
      "evidence_keys": ["repair_implementation", "revision_contract"],
      "subject": "有界评价合同精确定位问题和用户定义 target，且不暴露运行拓扑、预算、路径或控制元数据"
    },
    {
      "check_key": "current_evidence_boundary",
      "status": "pass",
      "evidence_keys": ["repair_implementation"],
      "subject": "曲线 CSV 已供应、历史审计为旧集合、当前真实缺口和未来实验被明确区分"
    },
    {
      "check_key": "approval_revision_isolation",
      "status": "pass",
      "evidence_keys": ["revision_contract", "regression_evidence"],
      "subject": "资格审批由 create_revision 产生，新 subjects 不继承旧决定"
    },
    {
      "check_key": "exact_poll_and_immutable_records",
      "status": "pass",
      "evidence_keys": ["revision_contract", "regression_evidence"],
      "subject": "实际返回的审批名/revision 驱动精确轮询及分修订不可变 action/report"
    },
    {
      "check_key": "repair_test_coverage",
      "status": "pass",
      "evidence_keys": ["regression_evidence"],
      "subject": "冻结合同完整性、底层决定隔离和 runner 名称/记录行为形成互补回归"
    },
    {
      "check_key": "ui_authority_and_usability",
      "status": "pass",
      "evidence_keys": ["ui_boundary", "revision_contract"],
      "subject": "决定仍只来自本地 UI，同时界面可用性未通过仍被诚实保留"
    },
    {
      "check_key": "minimal_architecture_change",
      "status": "pass",
      "evidence_keys": ["repair_implementation", "revision_contract"],
      "subject": "修复复用已有 Artifact、Operation revision 和 Approval 权威，未新增注册表、服务、表或状态机"
    }
  ]
}
```

## 关键核验

### 1. F1：科学来源与提示边界

`_prepare_sources` 只读取 `manifest["evidence_contract"]` 指定的文件，先验证其 SHA-256，再把该文件
字节登记为 `evaluation_contract`。当前合同顶层只有：

- `schema_version`、`fixture_id`；
- `scientific_question`、`required_result`；
- `scientific_scope`；
- `evidence_boundary`。

其中没有 `operation_contract`、比较预算、运行适配器、插件闭包、完整文件清单或私有运行根。它把
target 明确限定为用户给定比较目标，并禁止将其提升为独立论文证据；把已供应的冻结曲线 CSV 与
仍未供应的原始历史 PLX/执行绑定、target_metrics 原始字节、完整 scorer 执行绑定分开；把环境重放
和网格 A/B 明确列为下一实验而非当前缺失来源。这些都是任务/来源集合边界，不是预先指定某个物理
机制或因果结论。

提取和审计指令与合同一致：第六项来源被明确识别为曲线 CSV；历史审计的 `missing_inputs` 只能作为
旧输入集合的记录；审计仍须独立逐项核对，并在 intake 错引时给 `revise`，没有被指令要求给 `pass`。

### 2. F2：修订身份、决定隔离与不可变记录

资格 Operation 明确使用 `on_conflict="create_revision"`。`_await_local_approval` 从调用结果捕获
`name` 和 `revision`，只以该名称查询 `approval_status`，并把这两个值写入
`human-action-evidence-qualification.<actual-name>.json`。最终报告同样写入
`evidence-stage-report.<actual-name>.json`；同名文件存在但字节不同会抛错，不会覆盖或继续使用旧
completed 记录。

测试覆盖分成两层，范围合理：

- 通用真实 Runtime/Root 测试先决定旧审批，再用不同 subject 创建修订，断言旧名称仍为 approve，
  新名称为 `.rev2`、revision 为 2、状态 pending 且没有 selected option；
- runner 测试以实际 `.rev3` 返回值驱动一次精确轮询，核对 action/report 文件名和内容，并验证同一
  revision 的不同报告无法覆盖。

因此无需为本次修复新增 Approval 服务、专用状态机或领域注册表。真实 rev3 的 UI 点击、受控 Agent
输出及新科学内容仍是下一次运行要产生和审查的未来证据，不应在运行前伪造为已完成。

## 非阻断改进项

1. 冻结测试已校验 `evidence_contract` 的路径和 SHA-256。后续若该合同会频繁演进，可再加一条精确
   顶层键集合/禁止控制字段断言，降低人工更新 hash 时重新引入控制元数据的风险；当前冻结字节本身
   已经有界，不影响 rev3 启动。
2. runner 测试有意不启动真实 Agent 或替用户点击 UI。真实 rev3 运行后仍须复核：新 intake 不再把
   curve CSV 列为缺失、新 audit 的 handoff 为 pass、资格审批 subjects 精确绑定 rev3 producer family，
   且决定确实由本地 UI 写入。它们是放行假设阶段前的必需证据，不是本次运行前缺陷。

## 独立命令与结果

所有命令均严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

- `pytest -q tests/operations/test_r5_g_science_chain_runner.py tests/operations/test_r4_approval_operation.py::test_changed_approval_subject_creates_pending_revision_without_old_decision tests/operations/test_r5_frozen_baselines.py`：`9 passed in 37.67s`；
- `python -m py_compile scripts/r5_g_science_chain.py tests/operations/test_r5_g_science_chain_runner.py`：通过；
- 精确候选 `git diff --check`：通过；
- 独立复算 `evidence_contract.json` SHA-256：`8c45f32fc550ac5e67b3848ba9aceb60f3dbf5ecf6726edfd2c3d65d9b1ad8a8`，与 manifest 一致；
- 静态结构核验：评价合同 1798 字节，未包含评估 topology、budget、runtime/plugin、完整文件清单或私有根字段。

