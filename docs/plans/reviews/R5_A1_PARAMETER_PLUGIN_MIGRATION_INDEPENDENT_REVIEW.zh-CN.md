# R5-A1 设备参数插件迁移独立审查

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A1 精确候选  
结论：**打回**  
门禁决定：**不放行 R5-A2**

## 1. 审查口径

本轮完整阅读了：

- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 的不可退化约束、5.1 节和 R5-A1 内部门；
- `docs/plans/R5_A1_PARAMETER_PLUGIN_MIGRATION.zh-CN.md`；
- 当前中英文架构文档；
- `scid-cross-boundary-review` 与 `scid-find-simplifications` 两项审查技能。

审查沿真实调用路径核对了编译目录、Operation 输入输出、Worker 物化、集合封存、确定性 Transform、审批投影、资格 cohort 及 TCAD author/reviewer 消费者，并单独核对 clean-wheel 和核心泄漏。文件大小本身不作为拆分依据。

## 2. 阻塞问题

### F1（阻塞）：独立参数审查者看不到它被要求审查的任何原始来源

证据：

- `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:690`—`708` 把审查 Operation 的 `source_material` 声明为 `exposure="handoff_only"`；同文件 `866`—`893` 又声明该 Agent 要独立审查全部冻结来源。
- `plugins/tcad_artifact/tcad_artifact/roles/parameter_evidence_auditor.md:1`—`10` 明确要求检查每个冻结来源、精确定位、数值、单位、条件和来源独立性。
- `src/scidiscovery/artifact_agent/service/tasks.py:1503`—`1506` 明确拒绝 Worker 读取 handoff-only 输入，`1557`—`1559` 明确拒绝对其提取 PDF，`1796`—`1808` 明确不把其物化为输入文件。
- `src/scidiscovery/operations/invoke.py:334`—`340` 同样从可交给执行器的 payload 输入中排除 handoff-only 项。

这不是“最小上下文”，而是把完成科学审查所必需的证据从审查者上下文中删除。审查者只能看到摘要/身份，无法验证论文页码、表格数值、图像、单位、条件或来源是否为镜像，因此四项通过检查没有科学依据。

现有正例没有发现该问题：`tests/operations/test_r4_approval_operation.py:1522`—`1565` 在 materialize 后不检查 assignment 或来源可读性，直接由测试写入“已审查两个来源”的通过结果；验证器只确认所写来源键属于任务绑定，不能证明审查实际发生。

最小修复：

1. 将参数审查的 `source_material` 改为 `on_demand`（或确有必要时 `full`），同时修正当前把 wildcard 描述成“payload 永不暴露”的资源说明；审批 Operation 的 `frozen_sources` 仍可保持 handoff-only。
2. 增加真实 Worker 负/正例：materialize 后每个审查来源都有受控只读路径，文本/图像可由原生只读能力检查，PDF 可由已声明 PDF 工具读取；跨任务或未绑定来源仍不可读。
3. 正例必须根据实际可读来源形成审查输出，不能只在测试中直接写入未经检查的通过结论。

### F2（高）：资格 projector 没有强制审查结果覆盖“每个冻结来源”

证据：

- `parameter_operations.py:358`—`366` 只用 producer family 检查审批输入中的冻结 Artifact 引用是否完整。
- `parameter_operations.py:429`—`437` 只要求审查 `evidence` 覆盖 `source_catalog.sources`，没有要求覆盖 producer family 中全部 `source_material` 的任务本地别名。
- `validate_parameter_bundle` 在同文件 `183`—`232` 只要求 catalog 是 intake foundation 的子集；它不能证明每个提取输入都进入 catalog 或被审查。

因此一个绑定给提取 Operation、随后也作为 `frozen_sources` 展示的来源，只要没有进入 catalog，审查结果就可以完全不声明它，资格 projector 仍可能通过。这与上位计划第 5.1 节和角色提示中的“每个冻结来源”不一致。

最小修复：在 TCAD 插件的参数审查 context validator 或资格 projector 中，从精确 producer family 的 `source_name` 集合得到预期来源键，并要求审查证据覆盖全部冻结 `source_material`；保留 catalog 来源覆盖检查。增加“额外冻结来源未被审查时资格创建失败”的负例。

### F3（高）：没有满足 A1 门所要求的 TCAD clean-wheel 整条参数链证明

证据：

- `tests/operations/test_r5_frozen_baselines.py:102`—`138` 的 clean-wheel 参数检查只核对 core/full/full+InGaAs 的目录数量和摘要变化。
- `tests/operations/test_r4_approval_operation.py:1280`—`1626` 的源码态参数链到“资格审批请求 pending”即结束，没有经本地 Approval UI 形成决定，也没有继续 uncertainty、TCAD author 和 reviewer。
- `tests/operations/test_tcad_operation_plugin.py:1222`—`1477` 分段验证 cohort、uncertainty 和 author 准入，但通过直接调用 ApprovalService 构造合成批准，未从六个迁移 Operation 的同一生产者族贯通，也没有运行 author/reviewer Worker 文件闭环。
- 上位计划 `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:181`—`184` 明确要求 TCAD clean-wheel 编译并运行整条参数链；`236`—`246` 又要求安装态正负例。

现有分段测试支持大部分局部合同，但不能替代安装产物中的完整纵向闭包证明。

最小修复：在 full clean-wheel 环境新增一个有界整链测试，至少真实经过：

`checklist/source → extract Worker/bundle → coverage → audit Worker → intake split → Approval Operation → 本地 Approval UI 决定 → uncertainty → author Worker → reviewer Worker`

测试必须断言同一生产者族、Operation id/version/digest、父引用、批准 provider、全有或全无 cohort 和最终 reviewer 结果；另保留缺成员、来源不可读/未审查、错误批准 provider、阻塞 uncertainty 和混入另一生产者族的负例。

## 3. 非阻塞但必须随本轮修正清理的问题

### F4（一般）：通用核心仍保留明确的参数 legacy 例外说明

`src/scidiscovery/general_transform_operations.py:484`—`490` 的通用 `science.intake.split.v1` 仍写着“legacy parameter bridge splits provisionally”，并把 `evidence_audit` 保持为可选。这与迁移记录中“generic core 扫描未命中 legacy bridge 名称”的陈述不一致，也把已经迁出的领域历史留在通用 Operation 的模型可见描述中。

真实 compiled producer 目前仍受通用独立审查准入检查保护，所以本项不是 F1 同等级旁路；但它属于参数桥未清尽的核心债务。若所有现行 compiled intake 均已先审查，应删除该例外并把端口改为必需；若仍有非参数承重消费者，至少应去除参数专名、精确记录通用兼容理由并增加对应测试，不得继续以已迁移参数桥为理由。

## 4. 已确认成立的部分

- 六个参数 Operation 由单一 `tcad_artifact.PLUGIN` 组装；两个 Agent、coverage、uncertainty 和两个 Approval Operation 均能从同一编译目录解析。
- core 生产源码扫描未发现设备参数 Schema、参数 Operation id、批准 cohort 或参数算法引用；core-only clean-wheel 为 28 个 Operation，full 为 51 个，full+InGaAs 为 52 个，目录门可信。
- 提取主输出和三个固定集合成员由 bundle validator 原子校验；缺集合成员失败关闭。
- coverage 在资格 projector 中被确定性重算；checklist 科学字段、生产者族、Transform 父链、审查父链和批准 provider 均有精确绑定。
- uncertainty 要求精确批准的 requirements/parameters/coverage，并有 coverage 父链 guard；参数感知 author/reviewer 端口属于同一全有或全无 cohort，阻塞型 uncertainty 不能进入输出验证。
- 人工决定仍由既有 ApprovalService/UI 生命周期承担；插件 projector 只构造 ReviewDocument。未发现插件复制审批数据库、任务状态机、执行权威、第二注册表或 entry-point group。
- 本次迁移复用了通用 Artifact、Task、Worker 文件生命周期、Approval、Operation 编译器和既有 scientific Schema。814 行参数模型和 970 行纵切面声明虽大，但当前分别以“参数科学模型/算法”和“参数 Operation 闭包”为单一变化原因；在没有更独立消费者前，不建议仅按行数继续分层。

上述优点说明总体迁移方向符合“通用核心轻量、领域能力插件闭包、Worker 最小授权”的目标；F1/F2 是局部但承重的科学证据边界错误，不需要新增实体、注册表或状态机即可修复。

## 5. 独立复核命令

所有命令均在串行、7 GiB 虚拟内存上限下运行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1

pytest -q tests/operations/test_r5_frozen_baselines.py
# 6 passed in 31.38s

pytest -q \
  tests/operations/test_general_transform_operations.py::test_parameter_uncertainty_projection_blocks_unbounded_and_preserves_bounded_tuning \
  tests/operations/test_tcad_operation_plugin.py::test_parameter_bundle_validator_rejects_an_incomplete_family \
  tests/operations/test_tcad_operation_plugin.py::test_parameter_cohort_is_all_or_none_and_approved_together \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_projectors_preserve_metadata_only_sources \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_rejects_a_changed_supplied_checklist \
  tests/operations/test_r4_approval_operation.py::test_metadata_only_parameter_source_crosses_the_compiled_tcad_operations \
  tests/operations/test_r3_catalog_authority.py::test_device_parameter_audit_is_owned_only_by_the_compiled_tcad_plugin
# 8 passed in 2.73s

git diff --check
# 通过
```

另启动了全仓串行回归，运行至约 57% 未出现失败；在阻塞事实已经确定且上级要求不再重复等待全仓测试后中止。本轮不把该部分运行写成“251 项独立通过”，迁移记录中的全仓数字仍是实现方证据。

## 6. 最终结论

**打回。**

R5-A1 的插件归属、目录闭包和大部分确定性/资格谱系设计正确，也没有明显复杂度反噬；但当前独立审查 Agent 无法读取原始来源，且资格闭包没有强制其覆盖全部冻结来源。这使“独立参数证据审核通过”可以在没有科学检查能力的情况下产生，直接违反来源可追溯、Worker 精确上下文和审查门禁三项承重约束。与此同时，TCAD clean-wheel 尚未运行到批准后的 uncertainty 与 author/reviewer，未满足 A1 冻结门。

完成 F1—F3 的最小修复、清理 F4、更新不再成立的实施记录并通过聚焦测试、clean-wheel 整链和全仓串行回归后，才能重新独立审查；当前不得开始 R5-A2。
