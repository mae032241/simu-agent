# R5-G 直接完整对象修订方案独立审查

审查对象：

- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md`；
- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/README.md`；
- 对照 `docs/ARCHITECTURE.zh-CN.md`、
  `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 及当前工作树的真实消费者。

审查方式：只读架构与跨边界审查；未修改生产代码、测试、计划或私有科学对象。本报告是本轮唯一
写入。

## 结论

**有条件通过：只认可“专业 Agent 直接产生完整新对象”这一设计方向；当前计划不得进入 D0/D1
实施。**

与 `StructuredRevision → Apply → Diff → Receipt` 相比，直接完整对象修订更符合当前架构：科学内容
仍由原专业 Agent 负责，控制面只冻结完整 Schema、精确输入、父链和新一轮独立审查；同时可以删除
六个支撑 Operation、补丁专用 Task/Worker 合同以及 Root 的递归修订族。它没有要求万能修订 Agent、
第二注册表、新状态机或数据库表，方向上符合 OperationSpec 原子能力、最小上下文与奥卡姆目标。

但计划当前缺少一个防旁路的机器可执行修订形态，阶段顺序还会先删除 curve-score 的在用依赖，再
在后一阶段迁移它；直接修订的控制输入还会被当前生产者族误当成科学证据源。因此它尚不是可实施
计划。以下 F1—F5 必须全部写回计划并再次独立复审。

## 阻断项

### F1（高）：`revision_base` 的免审语义没有被限制为“直接完整对象修订”

计划第 3.1 节要求任何 `usage=revision_base` 只检查实例、Schema、用途、大小和权限，不要求旧评审
通过；同时又明确不增加 `supports_revision` 或新的修订政策字段。按当前文字，一个任意插件可把
普通 Agent、Transform，甚至 Effect 的输入标成 `revision_base`，从而让被打回的生产者输出绕过
普通下游评审门。计划只描述了期望的 hypothesis 形态，没有冻结 catalog/runtime 必须验证的总函数。

最小修订要求：不增加新类型或注册表，直接用现有 OperationSpec 字段冻结以下编译和调用不变量：

1. 使用普通 `revision_base` 的 Operation 必须是 `scientific` Agent；只能有一个必需、单值、非集合
   的 revision base；
2. 它的完整主输出 Schema/codec 必须与 base 端口一致，并且该主输出必须由 OperationSpec 的
   `ReviewSpec` 声明为独立审查 subject；
3. 当旧 base 有冻结 review 合同时，新输出的 reviewer operation、reviewer input port 和接受结论
   不得弱于或漂移于旧合同；否则 preflight 失败；
4. 若调用提供 `change_request`，它必须是旧 base 冻结合同声明的精确 reviewer Operation 对精确
   base 的完成输出；`blocked/revise/inconclusive/pass` 仅能解释修订请求。base 没有 review 合同时，
   提供 `change_request` 必须失败，而不是把任意 Artifact 当请求；
5. 无 `change_request` 只在端口基数允许时成立；它仍只产生待重新审查的新对象；
6. 用未知插件真实 preflight/invoke 负例证明：把 blocked 对象改绑到 Transform、Effect、无 ReviewSpec
   Agent、不同 Schema 输出、弱化 reviewer、另一对象或另一实例时均失败。

这些是已有端口与 review 关系的结构校验，不是 `RevisionPolicy`、第二目录或领域白名单。

### F2（高）：D2/D3 顺序不可执行，并且 D1 尚未闭合直接 intake 与 TCAD 消费者

计划 D2 先删除 `StructuredRevision`、`TaskRevisionSpec`、spec 字段、通用实现和收据协议；D3 才把
curve-score 的 `science.experiment.revise.v1` 从结构化补丁迁为完整对象。当前
`plugins/curve_score/curve_score/science_operations.py` 仍直接导入上述 Schema、profile、validator，
并声明 `revision_base_port`、apply 和 receipt Operation。D2 一旦完成，full catalog 连导入/编译都
不能通过，D3 也失去可迁移基线。

还有两处同类顺序断裂：

- 直接 intake revision 在 D1 产生后，当前科学资格 projector 仍只接受初始 extract/figure 或旧
  apply family，并要求 diff/receipt；计划把 projector 简化放在 D2，故 D1 无法证明“全新 audit →
  全新人工资格 → 普通下游”；
- TCAD author 虽已输出完整项目，但当前 project 输出只声明
  `allowed_input_usages=("claim_evidence",)`，而 revise/runtime-failure 输入使用 `revision_base`；若不
  同步输出用途，通用 admission 在免审判断前仍会以 `input_output_usage_forbidden` 拒绝。

最小顺序调整：

1. D0：只撤销未通过的半修复并冻结旧失败；
2. D1：冻结 F1 的通用形态，迁移 general intake/hypothesis，**同时**改完直接 intake 的 producer
   family/资格 projector，并同步 TCAD project 的 revision-base 用途；完成一次完整 direct-intake
   新审计与新资格正负例；
3. D2：迁移 curve-score experiment revision、盲插件 fixture 和所有 installed consumer；以 `rg`
   证明发布生产代码已无旧协议消费者，但此时可以暂留未引用的旧实现；
4. D3：再删除 spec/catalog/invoke/Task/Worker/Schema/transform/插件旧协议，执行四种 clean-wheel、
   TCAD review-request/runtime-failure 重放和未知插件调用；
5. D4：最后进行真实 R5-G hypothesis 修订与新 critic。

也可以把 D2/D3 合并为一个原子阶段，但不得先删类型再迁最后一个生产消费者。

### F3（高）：直接父链完整，但当前 producer family 会把旧草稿和评审意见误当科学证据源

计划第 2 节正确规定 `revision_base` 不是证据，第 4.5 节又认为直接绑定来源/foundation 后，Agent
producer family 已经完整。当前 Agent family 构造却把 `task.inputs` 的**所有**项都放进
`ProducerOutputFamily.evidence_sources`；资格 projector 再要求 `frozen_sources` 精确等于该集合。
因此 direct intake 的 `revision_base`、`change_request` 和真正 source material 会混为一组，旧草稿
和被打回审查很容易被下一次 audit/qualification 当作证据清单。这违反计划自己的输入用途边界。

最小修订要求：新对象仍保留**全部**直接 Task/Artifact 父链，但 producer family 的科学来源投影
必须按已编译 input usage 生成，只把明确的 evidence-bearing 输入和受控 web/PDF 派生来源放入
`evidence_sources`；`revision_base`、`change_request`、`prior_signal` 不得被提升为 claim source。
不要新增来源表或收据。测试必须同时证明：删掉一个真实冻结来源会使 audit/qualification 失败；删掉
旧 draft/review 的父链也失败；但 draft/review 不出现在可支持事实主张的 source set 中。

### F4（中）：删除清单尚未覆盖全部真实消费者和生成/安装路径

第 4 节列出了主要核心与插件对象，D2 也笼统写了“测试夹具/安装清单”，但当前 `rg` 仍显示以下
必须逐项分类的消费者；没有这张矩阵，极易留下兼容面或误删冻结证据：

- Task/Worker：`artifact_agent/service/task_outputs.py` 的 `_validate_revision_scope` 和专用 import，
  `schema/task.py` 的 Task/Assignment revision 分支，`roles/common.md` 的 Worker 可见补丁协议；
- spec/catalog/invoke：`operations/spec.py`、`catalog.py`、`invoke.py`，以及
  `builtin_plugin.py` 的架构测试 revision Schema；
- general/approval：`general_science_agent_operations.py`、`general_science_resources.py`、
  `general_science_components.py`、`general_science_control_operations.py` 的 projector 端口和修订分支；
- curve/历史 Transform：`curve_score/science_operations.py` 与
  `artifact_agent/transforms.py` 的两个 profile、实现、validator 和导出；
- 真实评估与安装态：`scripts/r5_g_science_chain.py`、`tests/fixtures/r5_e2e_tcad/manifest.json`、
  `test_catalog_installed_entrypoint.py`、`test_operation_invoke_installed.py`；
- 通用性夹具：`producer_family_operation_plugin` 的 plugin/runtime、
  `test_r5_blind_producer_family.py`；该夹具应改成“旧对象 → 完整新对象 → 新 review”的盲插件，而非
  仅删除；
- 结构与专项测试：`r5_structure_inventory.json`、`test_r3_agent_contract.py`、
  `test_catalog_negative_cases.py`、`test_general_transform_operations.py`、
  `test_general_science_plugin.py`、`test_curve_score_operation_plugin.py`、
  `test_r4_approval_operation.py`；
- `scripts/r5_baseline_metrics.py` 是冻结基线生成器，若它的旧 revision 正则只是历史口径，应明确
  保留且不可改；不能为了最终 `rg` 清零而改写冻结证据。

计划应增加“生产/插件/Worker 可见资源/生成配置/测试夹具/安装态/冻结历史”消费者矩阵，并把最终
零命中门限定为发布生产路径和当前生成资源；历史文档、持久旧 Artifact 和冻结基线只读保留，不得
为了清洁统计而重写。

### F5（中）：上位计划和索引尚未真正同步

`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 11.6 节已链接新方案，状态表也诚实写为
待审；但同文件第 13 节仍写“R5-G 不修改框架合同”，与本计划删除 OutputPortSpec、Task/Worker
合同和 Root family 的范围直接矛盾。第 6.2—6.3 节仍把补丁修订族描述为 R5-B 的当前目标模型，
至少应标明：它是已经通过的历史 R5-B 实现事实，其中仅“修订 Transform 递归”分支拟由本计划
D2/D3 取代，其他 Agent/Transform family 完整性与调用指纹不回退。

`docs/plans/README.md` 的 R5 总项仍停在“R5-B 候选待审、不放行 R5-C”，而同一索引和主计划均已
记录 R5-B—R5-F 通过。这会让读者无法判断当前权威状态。

最小修订要求：

1. 把 R5 回退边界改成“R5-G 的直接修订子阶段会修改框架合同，按 D0—D4 独立回退并重过受影响
   的 catalog/Task/Worker/plugin/clean-wheel 门”；
2. 给 R5-B 的旧修订族段落增加明确的“已实现历史、将被本计划局部废止”标注；
3. 把 README 的 R5 状态同步至 R5-F 已通过、R5-G 直接修订计划待审；
4. `docs/ARCHITECTURE*.md` 继续只描述当前已实现事实，不得在 D3 实现和独立审查前把本草案写成
   既成事实；D3 通过后再双语同步。

## 非阻断评价

- “原专业 Agent 直接输出完整对象”比强制补丁链更符合科学所有权；完整对象仍经原 Schema、语义
  validator、资源上限和新 reviewer，删除 diff Artifact 不会删除不可变版本或精确父链。
- 可选 change request 是合理的：没有审查请求时，它只是一个新的未资格版本；有请求时必须满足
  F1 的精确 subject-review 绑定。聊天或调度指令都不能成为资格事实。
- 不预建 UI diff 协议是合理裁剪。确有界面需求时，可从精确旧/新对象做无状态展示，不能反向成为
  科学证据或准入权威。
- TCAD 的任务私有代码编辑与跨 Artifact 的 StructuredRevision 是不同层次；保留
  `worker_file_*` 和 deck workspace、只删除科学对象补丁协议是正确边界。
- D4 保留原 blocked portfolio/critic 并创建新不可变对象、新独立 critic，符合“不继承旧 verdict”
  和真实科学闭环要求。

## 复审完成门

下一版计划只有同时满足以下条件才可放行 D0：

1. F1 的结构不变量成为明确的 catalog/runtime 总函数和未知插件正负例；
2. 先迁全部生产消费者、后删旧协议，且 direct intake 资格和 TCAD revision 在删除前已闭合；
3. producer family 明确区分完整父链与科学 evidence source；
4. 消费者矩阵覆盖 F4，冻结历史明确只读保留；
5. 主计划和 README 的冲突全部消除；
6. 仍保持零新表、零新状态机、零第二注册表、零领域核心分派，且删除行数大于新增行数。

## 实际检查

在仓库根目录执行，均为只读、严格串行：

```text
wc -l docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md \
  docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md \
  docs/plans/README.md docs/ARCHITECTURE.zh-CN.md \
  docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md

rg -n --hidden --glob '!/.git/**' --glob '!docs/**' \
  'revision_base_port|allowed_revision_paths|unchanged_set_receipt|TaskRevisionSpec|StructuredRevision|StructuredRevisionDiff|UnchangedEvidenceReceipt|structured_revision_apply|_revision_transform_family|revision_diff|revision_patch' \
  src plugins tests deploy scripts

rg -n 'R5-G.*不修改|不修改框架合同|revision_base_port|修订 Transform|直接完整对象修订' \
  docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md docs/plans/README.md

git diff --check -- docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md \
  docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md docs/plans/README.md
```

结果：文档空白检查通过；三个上位链接存在。未运行 pytest、clean-wheel、真实 Worker 或 TCAD，
因为本轮只审查尚未实施的方案；这些是 D1—D4 的实施门，不能用当前旧实现的通过测试代替。
