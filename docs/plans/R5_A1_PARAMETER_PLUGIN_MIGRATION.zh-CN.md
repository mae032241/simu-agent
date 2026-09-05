# R5-A1：设备参数纵切面迁移记录

状态：第三轮独立审查通过；只放行 R5-A2，不放行 R5-B。

日期：2026-08-29  
上位计划：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`

本文件只记录 R5-A1 精确候选的实现与验证证据。R5 总体状态仍以上位计划为准。

## 1. 本阶段回答的问题

设备参数曾同时散落在通用 Schema、通用 Transform、通用资格审批、TaskService bundle 特判、
Root legacy role 桥和 TCAD author/reviewer 中。A1 将这一完整领域能力收敛为同一个
`tcad_artifact` 插件闭包，同时继续复用通用 Artifact、Task、Worker 文件生命周期、Approval、
Operation 编译和调用机制。

迁移后的六个 Operation 是：

- `tcad.parameter.evidence.extract.v1`：公开 Agent，产生一个 provisional intake 与三个不可分割
  集合成员；
- `tcad.parameter.evidence.audit.v1`：公开独立审计 Agent，检查完整生产者族、coverage、可选精确
  checklist 与全部冻结来源；
- `science.parameter.coverage.v1`：TCAD 插件拥有的确定性 Transform；
- `science.parameter.uncertainty.v1`：TCAD 插件拥有的确定性 Transform 与谱系 guard；
- `science.parameters.qualify.pass.v1` 与
  `science.parameters.qualify.exception.v1`：TCAD 插件拥有的两项通用审批生命周期投影。

Operation 编号是稳定协议名，不表示其实现仍属于通用核心。上述声明、组件、Schema、算法、提示、
工具引用和 projector 均由一个 `tcad_artifact.PLUGIN` 组装。

## 2. 实现边界

领域插件新增或接管：

- `tcad_artifact/device_parameters.py`：参数需求、来源目录、参数集合、覆盖与不确定性模型及算法；
- `tcad_artifact/parameter_operations.py`：六个 Operation、组件、bundle validator、context
  validator、谱系 guard 与审批 projector；
- `tcad_artifact/roles/parameter_evidence_extractor.md` 和
  `parameter_evidence_auditor.md`：两个 Agent 的领域科学职责；
- `tcad_artifact/project_packager.py` 与 TCAD Operation 声明：只引用插件内参数模型和资格 provider。

通用核心删除：

- `artifact_agent/schema/device_parameters.py` 及其公开导出；
- `general_transform_operations.py` 的参数 Transform、组件与残留导出；
- `general_science_plugin.py` 的参数审批 projector、声明与 Schema 映射；
- `experiment_intent.py` 对设备参数映射的领域解释；
- `TaskService` 的参数集合名和专用 bundle 校验；
- Root、运行时、上下文策略、scheduler 提示中的两个参数 legacy bridge；
- 根 `roles/` 下的参数提取/审计桥角色及通用 auditor 中的参数专用段落。

`platforms/roles.py` 等旧发现基础设施尚未在 A1 删除；其生产删除属于 R5-A2。A1 只保证当前运行时
不再需要设备参数 legacy role。

## 3. 首轮独立审查问题与修复

首轮报告 `reviews/R5_A1_PARAMETER_PLUGIN_MIGRATION_INDEPENDENT_REVIEW.zh-CN.md` 打回四项问题；
本候选只作对应的最小修复：

1. 参数审计的 `source_material` 从仅交接摘要改为按需暴露的精确冻结来源；编译后的 Worker
   可以读取任务内 PDF、图像、文本、表格或结构化来源，但仍看不到未声明对象；
2. 资格 projector 除核对来源目录外，还从提取生产者族推导全部冻结来源，要求审计逐一声明，
   并拒绝重复别名或遗漏来源；
3. 新增仅从已安装 full wheel 启动的整链探针，真实经过提取 Worker、coverage、审计 Worker、
   intake split、回环 Approval UI 决定、uncertainty、实验计划、独立计划复审、带有界假调试
   adapter 的 TCAD author 以及只读 TCAD reviewer；
4. 通用 `science.intake.split.v1` 不再含“参数 legacy bridge”文案，其独立审计输入改为必需。

整链测试还发现并修复两项隐藏断裂：参数审计应引用被审参数集合、科学基础再引用审计；参数需求、
参数值和来源目录在通过资格 cohort 后可以作为 TCAD author 的 `claim_evidence`，而不是被输出用途
合同提前拒绝。两项均由真实谱系和 cohort 守卫约束，没有增加核心领域分支。

第二轮报告
`reviews/R5_A1_PARAMETER_PLUGIN_MIGRATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`
继续打回两项同源问题：PDF 摘录与原 PDF 同名导致合法来源被拒，以及审计来源别名和父引用可以
分别满足两个子集门。修复仍未新增实体：

- PDF 摘录被明确为原 PDF 的受控读取视图，不作为第二个科学来源；提取者和独立审计者都从同一
  原 PDF 各自调用注册工具生成所需页视图；
- 资格 projector 要求审计输出父链在去除指令引用后，与编译端口顺序下的完整审计输入逐项严格
  相等，并据源数量确定性重建 `source_material` 别名；额外输入、重排、同名异引用均失败关闭；
- clean-wheel 整链已改成真实单页 PDF，两个 Worker 均实际调用 PDF 工具，随后完成 UI 决定、
  uncertainty、TCAD author/reviewer；新增 PDF 读取视图正例及额外/替换/重排审计输入负例。

## 4. 精确集合与资格闭合

提取 Operation 的主输出是 `scientific_intake`，集合必须且只能包含：

1. `parameter_requirements/parameter_requirements.json`；
2. `device_parameters/device_parameters.json`；
3. `source_catalog/source_catalog.json`。

bundle validator 在一次完整校验中验证三项均存在、共享同一目标、参数和来源目录闭合、来源类型与
intake foundation 一致。集合仍是 provisional 科学内容，不因 Schema 通过而自动获得资格。

可选 `required_parameter_checklist` 被视为精确冻结输入。若提供，独立审计必须消费它，资格审批
必须绑定生产者族中的同一对象，并确定性比较除纯展示名外的全部科学字段。Worker 擅自改变需求时，
审批 projector 拒绝创建资格请求。参数 coverage 在审批时重新计算并与精确 Transform 输出逐字节
核对；审计必须覆盖四个固定检查与全部来源。完整批准 cohort 后才能生成 uncertainty，并进入
参数感知 TCAD author/reviewer。

## 5. 唯一权威与兼容边界

- 新任务只通过 `operation_invoke` 和已编译 Operation 创建；
- producer identity 使用 Operation id、version 与 digest，不再制造
  `legacy.device-parameter-evidence.v1`；
- Worker 工具、原生工具提示约束、输入端口和输出文件均来自同一 compiled Operation；
- 确定性计算不经过 `artifact_transform` 的参数 profile；
- 资格决定仍只由本地 Approval UI 写入，projector 只构造固定 `ReviewDocument`；
- 没有新增数据库表、运行状态机、entry-point group 或可变注册表。

## 6. 安装态与回归证据

所有命令均串行执行，并使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

当前已获得：

- 完整参数链正例：真实 PDF、`operation_invoke`、Worker claim/materialize、两个 Worker 各自的
  PDF 工具调用、受控文件写入、完整 bundle
  校验/finalize、coverage、独立审计、intake split、Approval UI 决定、uncertainty、计划复审、
  TCAD author 和独立 reviewer 全部闭合；
- 参数 checklist 变更、遗漏任一冻结来源和缺少集合成员负例通过；
- 旧角色桥不可调度，精确派发/恢复测试改用测试专用角色且不再保留生产兼容路径；
- core-only clean wheel 为 28 个 Operation（public 16、support 12），不能导入参数 Schema，也不含
  参数 Operation；
- full clean wheel 为 51 个 Operation（public 25、support 26），full+InGaAs 为 52 个
  Operation（public 25、support 27）；
- A1 跨边界矩阵（含真实 PDF clean-wheel 整链）：`92 passed in 53.67s`；
- 全仓串行回归：`255 passed in 86.26s`；
- `git diff --check`：通过；
- generic core 源码扫描未命中设备参数 Schema、Operation 或 legacy bridge 名称。

R5-0 快照保持不变；当前基线测试把它作为历史参照，并另行验证 A1 的授权目录差值，未重写历史
摘要来掩盖迁移。

## 7. 独立审查结论

第三轮报告
`reviews/R5_A1_PARAMETER_PLUGIN_MIGRATION_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`
已逐项回答：

1. 六个 Operation 是否构成完整能力闭包，是否遗漏真实消费者；
2. core-only 是否真正不含参数领域能力，full clean wheel 是否仍能走完整链；
3. checklist、完整集合、来源、coverage、审计和审批是否绑定同一生产者族；
4. 是否以新的兼容 facade、注册表、状态机或核心领域分支替代了旧桥；
5. 迁移是否保持 Worker 最小上下文、人工决定与副作用边界；
6. 测试是否覆盖真实入口和关键失败路径；
7. 是否符合“先迁移完整纵切面，再在 A2 删除旧发现入口”的阶段边界。

结论为通过。真实 PDF 双 Worker 工具调用、读取视图边界、精确有序审计父链、额外/重排/替换/
遗漏负例、核心无领域泄漏和复杂度边界均获确认。该结论只放行 R5-A2；旧入口删除完成并独立审查
通过前，不得进入 R5-B。
