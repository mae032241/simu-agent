# R5-B 领域无关审批生产者族第二轮独立复审

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-B 第一轮 F1 修订候选  
结论：**通过**  
门禁决定：**放行 R5-C**

## 1. 范围与精确对象

本轮未参与 F1 修复，只复核第一轮唯一阻塞：同 Schema 附件能否被错误提升为修订族主对象；同时
检查合法主对象修订、未知插件安装态入口、既有审批边界和最小复杂度是否退化。本轮遵循
`scid-cross-boundary-review`、`scid-find-simplifications` 和 `scid-change-scope-checks`，没有修改
生产实现、测试、实施计划或阶段状态，唯一写入是本报告。

本结论只约束审查时的精确字节：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `879d87b13485beeace6a44aec49de47e7b0c98d4e72cd57946a504ed493ed5ce` |
| `src/scidiscovery/operations/invoke.py` | `0a54429982e11a795d8457cbedd1eb627a704b0bd49c55f7d8fd110381c77ffe` |
| `tests/operations/test_r5_blind_producer_family.py` | `a753f64d9be848796a7bea63535970ba67fbfc839a1da471d3f11f881444b7f4` |
| 盲插件 `plugin.py` | `873afc30a1b2101e39c7346158d0de96b0ece207b6ea0743138ef73c41ab20cb` |
| 盲插件 `runtime.py` | `9c78fb21212dfb9e892a27bba5512e3ae408762dfa4e616e220a0073730c162c` |
| `R5_B_GENERIC_PRODUCER_FAMILY_IMPLEMENTATION.zh-CN.md` | `66ca06d54dd1ecc9d1a22ef2253f60947ec0aff2165eeefbd6fc909a25ef557e` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 6 节 |
| S2 | 第一轮独立报告及本轮 R5-B 实施记录 |
| S3 | `mcp_root.py`、`operations/invoke.py` 的上述精确生产字节 |
| S4 | 盲插件 Operation 声明、runtime 投影器和 R5-B 测试的上述精确字节 |
| S5 | 本轮独立串行运行的 43 项聚焦测试、编译检查、结构计数和静态扫描 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `revision_primary_binding` | 通过：递归得到 base family 后精确要求 base 引用等于其主引用，否则失败关闭 | S1—S4 |
| `same_schema_negative_path` | 通过：同 Schema 附件经过真实 Agent Worker 与修订 Transform 后不能创建审批绑定 | S2、S4、S5 |
| `legal_primary_revision` | 通过：原族主对象的修订仍能形成完整族并创建待审批请求 | S3—S5 |
| `unknown_plugin_installation` | 通过：clean-wheel 仍经唯一插件发现与真实 `operation_invoke` 完成正向审批 | S1、S4、S5 |
| `authority_and_scope` | 通过：没有增加附件修订协议、领域分派、注册表、持久状态或审批生命周期 | S2—S5 |
| `occam_and_constraints` | 通过：修复是一个精确谱系守卫与一个永久反例，未扩大 R5-B 语义 | S1—S5 |

## 3. 第一轮 F1 已真实关闭

`_revision_transform_family()` 仍先完成 patch OperationAuthority、输出合同、
`revision_base_port`、Task 精确输入、目标 Schema、实例 binding 和递归生产者族校验；在构造修订
族之前新增了唯一必要条件：

```python
if base_family is None or base_envelope.ref != base_family.primary_ref:
    return None
```

因此，能够被修订 Agent 和 Transform 的输入 Schema 接受，并不再等价于能够成为生产者族主
对象。只有原族主输出可以被替换；集合附件即使与主输出共享完全相同的 Schema，也只能递归得到
一个 `primary_ref` 不相等的族，随后失败关闭。

新增永久负例不是私有函数或字符串模拟。它真实执行：未知插件生产 Transform → 选择
`notes_001` → patch Agent 的 claim/materialize/write/validate/finalize 文件闭环 → 修订 Transform
→ Approval Operation。盲插件已经固定让 `specimen` 和 `notes` 同用 `blind.object.v1` 及同一
validator。最终 Approval 调用抛出 `approval_projector_failed`，并断言实例的 approval namespace
不存在 `attachment_promotion_approval` binding，覆盖了第一轮反例的可见副作用边界。

同一测试文件的合法正例仍以原 `specimen` 为 ancestor，通过相同 patch Worker 和修订 Transform，
并成功得到 `pending` 审批。这证明修复没有粗暴禁用通用修订链。clean-wheel 正例也继续通过。

## 4. 未引入新权威或复杂度反弹

本轮静态核验未在生产 `src/`、插件或部署代码中找到盲插件 Operation、fixture 名或附件修订专用
分派。第一轮记录的 `ProducerOutputFamily` 数据结构字节摘要保持不变；没有新增字段、provider
表、附件状态机或第二套 revision authority。审批仍由现有 Operation projector 和唯一
`ApprovalService` 创建，修复没有复制 Approval/Task/Artifact 生命周期。

`src/scidiscovery/operations/` 仍为 7 个 Python 文件、2060 行。R5-B 相对 R5-0 的阶段性总体增量
仍需在 R5-D 最终净删除门统一结算，但本轮修复本身没有以压行、搬移或新抽象掩盖复杂度。核心族
解析窗口也未出现 TCAD、参数、固定角色、盲插件端口或 Schema 分支。按单一编译权威、不可变精确
谱系、实例隔离、Worker 受控输出、人工审批和失败关闭等 33 项约束族复核，未见第一轮 F1 之外的
新退化。

## 5. 独立运行证据

所有命令严格串行，且每个命令前设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q \
  tests/operations/test_r5_blind_producer_family.py::test_revision_cannot_promote_a_same_schema_attachment_to_family_primary \
  tests/operations/test_r5_blind_producer_family.py::test_unknown_plugin_family_and_revision_are_resolved_without_core_changes \
  tests/operations/test_r5_blind_producer_family.py::test_unknown_plugin_is_discovered_and_invoked_from_a_clean_wheel
# 3 passed in 26.45s

pytest -q \
  tests/operations/test_r5_blind_producer_family.py \
  tests/operations/test_r4_approval_operation.py
# 43 passed in 34.89s

python -m py_compile \
  src/scidiscovery/artifact_agent/interfaces/mcp_root.py \
  src/scidiscovery/operations/invoke.py \
  tests/fixtures/plugins/producer_family_operation_plugin/blind_producer_plugin/plugin.py \
  tests/fixtures/plugins/producer_family_operation_plugin/blind_producer_plugin/runtime.py
# 通过

git diff --check
# 通过
```

本轮没有重复全仓 262 项；候选的新增风险被精确包含在上述真实负例、合法正例、clean-wheel 和既有
审批族测试中。实现方的全仓结果仅作为记录，没有被继承为本轮批准依据。

## 6. 最终结论

**通过。**

第一轮 F1 已按最小边界真实关闭：附件不能再被解释为主对象修订基线；真实 Approval 路径失败且
不留下审批 binding；合法主对象修订和未知插件安装态链路均未退化。修复没有扩张成附件修订协议，
也没有新增注册表、状态机、持久实体、领域硬编码或生命周期权威。

因此，本轮**放行 R5-C**。该放行只表示 R5-B 门闭合，不预先批准 R5-C 的设计、实现或最终 R5-D
复杂度结算。
