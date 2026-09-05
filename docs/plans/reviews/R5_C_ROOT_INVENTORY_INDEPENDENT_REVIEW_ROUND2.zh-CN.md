# R5-C Root/inventory 第二轮独立复审

日期：2026-08-29  
审查对象：当前共享工作树中 Root/inventory 的第二轮修订候选  
结论：**通过**  
门禁：**上一轮唯一阻塞已闭合，放行 R5-C 的静态拓扑/上下文子环节；本结论不预先批准该后续子环节。**

## 1. 审查边界

本轮只重新核对上一轮发现的 current 资格旁路，以及修复是否把领域解析、第二套 readiness 或重复准入重新带回 Root。未重新审查已经在首轮成立的 Task/debug、Approval、Execution 或插件安装结论，也未重复全仓测试。

审查遵循 `scid-cross-boundary-review`、`scid-find-simplifications` 和 `scid-change-scope-checks`，命令均在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

## 2. EvidenceAudit

### 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 7.2、7.3 节及 R5-C 完成门。 |
| S2 | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`，SHA-256 `7facd5a5869a07b26e29b866954216287b15e46d3a6afebefcf5bfa9cb35f077`。 |
| S3 | `tests/operations/test_r4_approval_operation.py`，SHA-256 `8163f71b13a9725e6fc5d29db6ead2c557c9f262576d0b3be06a7a3d0845d569`。 |
| S4 | `tests/operations/test_invoke_preflight.py`，SHA-256 `dde5da26cd7f4bc15d9fc0d32207d5e5b600e607eb3957de9da44f378bc792d4`；`tests/operations/test_r5_blind_producer_family.py`，SHA-256 `a753f64d9be848796a7bea63535970ba67fbfc839a1da471d3f11f881444b7f4`。 |
| S5 | 本轮命令记录：聚焦 pytest 15 项全部通过；`py_compile`、静态领域词检查和 `git diff --check` 通过。 |

### 检查记录

| 检查键 | 结论 | 证据 | 简要依据 |
| --- | --- | --- | --- |
| `shared_admissibility_authority` | pass | S1, S2 | `_claim_admissible(labels, handoff)` 是唯一共享谓词；current 选择和 exact Operation 的 claim-evidence 准入均调用它。 |
| `unknown_kind_positive_path` | pass | S2, S3, S5 | 未知 `kind` 的不透明 Artifact 经真实 `RootMCPRouter.call_tool` 可进入 inventory 并被选为 current，无 payload/Schema 解析。 |
| `label_negative_path` | pass | S2, S3, S5 | 同一真实 Root 入口拒绝 `scientific_claim_admissible=false`，且没有写入 current。 |
| `handoff_negative_path` | pass | S2, S3, S5 | Root 从 Task 输出信号查询边界取得 `revise` 后拒绝 current；测试替换的是信号查询返回值，受测调用、Artifact、binding 与 current mutation 均为真实生产对象。 |
| `operation_admission_equivalence` | pass | S2, S4, S5 | 非 explore 的 `claim_evidence` 仍在 `_validate_operation_input_admission` 使用同一谓词；producer-family 及原 preflight 正负例未退化。 |
| `domain_neutrality` | pass | S1, S2, S5 | Root 未恢复 `scientific_readiness`，且静态检查未发现 TCAD、runtime-attestation、设备参数或 curve-score 领域分派。 |
| `occam_and_authority` | pass | S1, S2 | 修复只增加一个纯谓词并复用既有 Task 信号、Artifact label 与 current binding；没有新实体、表、注册表、状态机或兼容门面。 |

## 3. 关键核验结果

### 3.1 上一轮旁路已关闭

`scientific_current_select` 在校验最新 revision 和精确 `kind` 后，读取该 Artifact 的生产者 scheduler signal，并在写入 scientific selection 前调用共享 `_claim_admissible`。标签为 `false`，或生产者 handoff 为 `blocked`/`revise`，都会失败关闭。正常未知领域对象仍可选择，因此修复没有把固定科学对象种类重新变成核心白名单。

### 3.2 与 exact Operation 准入共享同一事实

`_validate_operation_input_admission` 没有复制标签/信号布尔表达式，而是在原有边界内调用同一谓词：仅非 `explore` 且端口用途为 `claim_evidence` 时禁止不可采信对象。探索性输入和其他用途的既有语义未被意外收紧。

`scientific_inventory` 继续只公开机械事实：最新 Artifact 摘要、显式 current、label 投影、生产者 handoff 和同一个 compiled public catalog。它不调用该谓词生成候选、排名或下一步判断，也不解释领域 payload；这避免重新建立 readiness 权威。

### 3.3 测试证据

执行：

```text
pytest -q \
  tests/operations/test_r4_approval_operation.py::test_inventory_lists_unknown_domain_records_without_payload_interpretation \
  tests/operations/test_invoke_preflight.py \
  tests/operations/test_r5_blind_producer_family.py
```

结果：`15 passed in 28.18s`。

另执行 `python -m py_compile src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、共享谓词唯一性/领域词静态检查及 `git diff --check`，均通过。

本轮未重复 262 项全仓回归：改动边界局限于共享准入谓词和 current 调用点，上述测试已同时覆盖目标正负例、exact preflight 和 R5-B 盲插件回归；全仓、clean-wheel 与外部运行环境仍由后续冻结候选总门负责。

## 4. 最终判断

未发现阻塞缺陷。上一轮“不可采信 Artifact 仍可成为 current”的控制面旁路已经关闭；修复保持领域无关、失败关闭、单一事实来源和最小复杂度，没有恢复重型 readiness 或领域特判。

**结论：通过。放行 R5-C 的静态拓扑/上下文子环节。**
