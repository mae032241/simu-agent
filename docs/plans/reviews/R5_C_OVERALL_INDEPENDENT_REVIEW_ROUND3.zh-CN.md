# R5-C 总体完成门第三轮独立审查

日期：2026-08-29  
审查性质：仅复核第二轮 F2 最小修复及其组合退化  
结论：**通过**  
门禁决定：**只放行 R5-D，不提前放行后续阶段**

## 1. 审查边界

本轮不重开已经通过的 core/曲线迁移，只核对第二轮报告第 5 节冻结的四项修复门：公开声明构造面、
跨插件公开组件引用、私有实现别名防回潮、clean-wheel/真实 Worker/生命周期与复杂度回归。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 执行。全部命令均在 `ulimit -v 7340032`、
`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1` 下严格串行运行。本轮没有修改产品代码、测试、
计划或阶段状态；唯一写入是本报告。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 的不可退化约束、R5-C 完成门和复杂度门；SHA-256 `e89a506c36d1011a2ea1126c4721572612af640ca62bc316012cebc29c8926d1`。 |
| S2 | 第二轮报告 `R5_C_OVERALL_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，仅用于冻结 F2 与最小修复请求；SHA-256 `34caa7ea86336993150c2cd5847f7fe5f45352815eef2637bd7abc954c2709dc`。 |
| S3 | 新公开声明面：`src/scidiscovery/operation_declaration.py`，SHA-256 `8868451e1ec4d41a06f148ae744d36c1cd0a672c815895425e716abb14835872`。 |
| S4 | 通用与曲线声明：`general_science_plugin.py`（`63d59b6e...`）、`general_transform_operations.py`（`5e795702...`）、`curve_score/science_operations.py`（`ee77ac72...`）。 |
| S5 | TCAD 声明：`tcad_artifact/plugin.py`（`2b6d7195...`）、`tcad_artifact/parameter_operations.py`（`36fea2f1...`）。 |
| S6 | 编译权威：`operations/catalog.py`（`4e5a5de7...`）、`operations/spec.py`（`f9dae37d...`）及跨插件负例 `test_catalog_negative_cases.py`（`5ec08c2f...`）。 |
| S7 | 所有权、安装态与真实路由测试：`test_curve_score_operation_plugin.py`（`0567a085...`）、`test_tcad_operation_plugin.py`（`257d203...`）、`test_baseline_plugin_discovery.py`（`9b5426dd...`）、`test_catalog_installed_entrypoint.py`（`847d81d2...`）。 |
| S8 | 参数完整链和组合回归：`test_r5_frozen_baselines.py`（`f81fb8aa...`）、既有 Worker/盲插件/preflight/审批测试及本轮全仓运行记录。 |
| S9 | 结构口径：`r5_baseline_metrics.py`（`718eac8e...`）、冻结快照 `r5_structure_inventory.json`（`1b397e2d...`）和本轮当前字节输出。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `public_declaration_surface` | pass | S1, S3, S4 | 新模块只有五个无状态声明 helper/常量，不注册、不发现、不持久化、不导入领域实现；通用与曲线声明共同使用同一构造语义。 |
| `cross_plugin_component_ownership` | pass | S4—S7 | 曲线、TCAD 的共享引用均解析到 `general_science:*`；当前五个生产插件定义没有同一 implementation 的跨 owner 重声明。 |
| `public_surface_minimality` | pass | S3—S6 | `general_science` 只公开一个 workspace、五个 Schema resource 和四个通用 Worker tool；Agent、validator、projector、领域语义合同均保持私有。 |
| `private_alias_negative_gate` | pass | S4, S6, S7 | 曲线源码不再引用两个旧私有声明模块；当前生产插件集合的重复实现门为零，注入私有 workspace 别名会被静态门检出；依赖缺失、非 public、错误组件 id 继续由编译器失败关闭。 |
| `tcad_semantic_ownership` | pass | S4—S8 | TCAD 只复用通用 workspace/文件/PDF/心跳工具；参数 intake、audit、context 与 semantic contract 由 TCAD 薄组件自有，未用通用 validator 代替领域规则。 |
| `worker_and_lifecycle_regression` | pass | S7, S8 | clean-wheel、真实曲线工具路由、参数全链、Worker 最小能力、审批与 Task/Artifact 生命周期组合测试通过。 |
| `complexity_and_occam` | pass | S1, S3—S5, S9 | 新模块有两个生产消费者且只有一个变化原因；未新增目录、注册表、状态机或发现入口，三重结构门仍在界内。 |

## 3. F2 修复核验

### 3.1 公开声明模块是必要且有界的复用面

`operation_declaration.py` 共 166 行，仅公开：

- `schema_resource`；
- `payload_validator`；
- `scientific_agent_operation`；
- `RequiredParentage`；
- `OPERATION_AGENT_PREAMBLE`。

模块没有 entry point、可变容器、缓存、I/O、插件枚举或运行时分派。它把通用插件和曲线插件原先
各自持有的同一类声明构造逻辑集中为一个公开窄面；`RequiredParentage` 同时由通用 Transform 和曲线
Transform 使用。这里新增一个内聚模块比复制 builder 或把 helper 继续暴露在某一插件私有模块中更小，
没有形成新的框架层。

### 3.2 编译目录记录真实组件所有权

独立编译 builtin、general-science、TCAD、curve-score、InGaAs 五个生产插件后检查：

```text
跨 owner 的相同 implementation：{}

science.experiment.design.v1:
  general_science:workspace
  general_science:hypothesis_schema
  general_science:candidate_eligibility_schema
  general_science:critic_review_schema
  general_science:file_apply_patch_tool
  general_science:heartbeat_tool

tcad.parameter.evidence.extract.v1:
  general_science:workspace
  general_science:pdf_extract_tool
  general_science:file_apply_patch_tool
  general_science:heartbeat_tool
```

曲线目录不再出现伪造的 `curve_score:workspace` 或 `curve_score:hypothesis_schema`。调用方仍必须显式
声明 `PluginDependency("general_science", "0.1.0")`；编译器对 dependency、`public=True` 和精确
component id 三项分别失败关闭。

### 3.3 公开面没有扩大 Worker 权限

`general_science` 公开组件精确为十项：一个标准 workspace，五个共享科学 Schema resource，以及
PDF 提取、受限分析、文件 patch、心跳四个通用 Worker tool。公开只允许依赖插件在自己的
OperationSpec 中引用；Worker 的实际工具集合仍由该精确 CompiledOperation、任务 capability 与
服务端路由共同限制。没有公开 Agent、领域 validator、projector、runtime factory 或副作用 adapter，
因此不会因组件可复用而自动授予模型能力。

### 3.4 TCAD 本地薄组件是诚实所有权

TCAD deck Agent 把 patch/heartbeat 改为公开跨插件引用；参数 Agent 另复用标准 workspace 和 PDF
工具。参数 `intake_validator`、`audit_validator`、`evidence_audit_context` 与
`parameter_semantic_contract` 继续由 TCAD 插件声明，原因是其完整输出族、四项审计检查、冻结来源和
handoff 一致性具有参数专用语义。它们直接调用通用数据模型的公开验证函数，但不冒充通用插件组件，
也没有复制 Task、Approval 或 Artifact 生命周期。

## 4. 静态别名门为何足够

第二轮要求的是当前产品插件的架构防回潮，不是把 Python entry point 当作不可信代码沙箱。插件入口
在目录编译前已经可以执行 Python；单靠 implementation 字符串归属检查无法构成安全隔离，并会误伤
有意复用公共 SDK 实现的 builtin、测试插件和安全反例。

当前组合采用两层最小门：

1. 编译器对显式跨插件 `ComponentRef` 强制 dependency、public export 和精确 id；
2. 静态生产插件测试拒绝同一 implementation 被多个 owner 重声明，并用注入的私有 workspace
   别名证明该门确实会触发。

这足以关闭 F2 的真实故障方式，又没有把模块路径约定升级为第二套运行时所有权注册表。未来新增生产
插件仍须进入同一静态集合与 clean-wheel 门；这属于插件接入验收，不是当前 R5-C 的缺失运行状态。

## 5. 独立测试与复杂度记录

本轮执行：

```text
# 跨插件组件、真实曲线 Worker、TCAD 编译、core/full/InGaAs clean-wheel
# 8 passed in 28.83s

# 参数 clean-wheel 全链、审批、cohort 与 uncertainty
# 5 passed in 32.11s

pytest -q
# 270 passed in 84.43s

git diff --check
# 通过
```

当前机器口径：R0 聚合 `9485/13657` 行；operations 包 `7` 文件、`2056/2060` 行；生产 Python
`128` 文件、`60149/62533` 行；`deploy/install.sh` `1021/1026` 行；通用 core 领域 token 仍为
`4/112`。新增公开模块计入全生产代码口径，未靠移出目录宣称为删除；总体生产代码仍净减少 2384 行。

没有运行真实 Sentaurus solver 或浏览器人工点击，因为本轮没有改变外部执行 adapter、科学数值、UI
决定或审批写入路径；相关生命周期负例由当前 270 项组合回归覆盖。本轮没有缺失的 R5-C 门禁证据。

## 6. 最终结论

第二轮 F2 已按冻结的最小边界关闭：私有源码耦合消失，共享组件通过唯一编译目录的公开跨插件引用
消费，TCAD 领域 validator 保持插件自有，静态别名门与编译失败关闭相互补充。修复没有恢复旧权威，
也没有新增注册表、状态机、领域分派或不必要抽象。

**结论：通过。只放行 R5-D。**

本结论不批准 R5-E、R5-F、R5-G 或最终端到端科学效果门；R5-D 仍须按其独立复杂度与职责拆分门另行
实现和审查。
