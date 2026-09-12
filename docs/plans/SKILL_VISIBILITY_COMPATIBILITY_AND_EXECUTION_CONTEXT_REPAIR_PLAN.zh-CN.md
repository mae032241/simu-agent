# Skill 可见性兼容与 execution_context 合同最小修复计划

状态更新（2026-09-08）：S0—S3 已实施并经独立复审通过；原修复已部署，四个过期旧 Run 已受控终结，S5 design 已 completed。S6 初次 author 及随后 recovery 均 failed，无 accepted project，Fig.4 受控执行仍未放行。下一轮以 [TCAD author 失败最小修复与重新验收计划](TCAD_AUTHOR_FAILURE_MINIMAL_REPAIR_PLAN.zh-CN.md)为执行入口；其生产修复、重新部署和新 Run 验收尚未完成。

本文保留原修复范围和阶段验收记录；以下基线事实、S4 部署冻结记录与末尾 S3 复审结论属于各自当时的证据，不再表示当前仍“尚未安装”。新计划仅补充 author 失败修复范围及 S6 前置条件；本计划的科学上游复用、双证明门、不使用 `resume_from` 和独立审查要求继续有效。

基线日期：2026-09-07。源码根：`123/scidiscovery-e5.2`；分支：`refactor/m7-pre-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。文中未注明绝对位置的文件路径均相对源码根。

本计划按 `scid-cross-boundary-review` 跟踪声明、摘要、Root admission、Run、Worker、输出注册、插件安装和回滚的真实路径，按 `karpathy-guidelines` 限制改动范围，并把先失败后通过的负控作为验收依据。计划编写期间只读核查了这些路径，只新增本文；既有 Figure/Curve、P2/P3、Skill 改动属于其他工作。

## 1. 目标、非目标与停止条件

唯一修复路线：恢复稳定科学前言 → 隔离 design/revise 提示资源 → 增加一个通用执行上下文合同和一个 TCAD 确定性投影 → 证明旧科学上游可复用、旧 TCAD author/review 仍退役 → 安装后以新 design Run 验证 Skill 轨迹，再从新 TCAD author 继续 Fig.4。

完成目标是解除三个已确认 P1，同时保留 P2 对当前源码、调用入口和声明的 preflight/initialization 证明门。旧数据无需迁移，旧上游无需为平台读取策略重做科学工作。

明确非目标：不增加 Agent、角色、public Operation、控制状态、注册表、UI、Hardened 能力、多租户、通用候选规划、Skill 内容寻址、全局 current、历史迁移或资格继承机制；不修改 producer gate、wildcard/opaque 含义、摘要算法或旧摘要白名单；不通过 Skill 推断机器环境事实；不重新整理 Figure/Curve 或 P2/P3；不删除旧科学对象。

复杂度预算：最多新增一个生产模型文件、一个测试文件、一个 support transform；新增 SchemaModel 一种，复用 JSON codec、schema_resource、ComponentSpec、现有 transform factory 和 Root 注册/父链；无新依赖。生产行为改动集中在八个文件；已正确承载 Skill 策略的 `platforms/codex.py` 只读核验、零修改。`service/runs.py` 只做两项协议一致性小修：在既有 `_validate_resume` 补齐 backend id/version/capabilities 的精确比较；允许已过 deadline 的退役合同 Run 通过既有 CAS 终结为 failed，但不读取旧输出、不生成 recovery draft、不删除工作区。未超时的退役 Run 仍拒绝。不扩展 recovery 工程、不引入恢复状态、迁移或旧 draft 支持。测试补充放在现有相关文件中。不得为一个投影添加通用映射引擎、能力探测器或可配置字段转换框架。

以下任一项出现即停在当前阶段，不进入安装或科学续跑：

- 无法从版本化源码确认恢复前言/旧 experiment prompt 的精确字节；只能猜测旧摘要。
- 任一声称可复用的 producer 摘要仍不相等，且差异不能归因于已确认的真实科学合同变化。
- 需要放宽 admission、修改数据库、复制旧 verdict 或给旧 project 补写证明才能通过。
- 新投影引入环境探测、私有配置读取、命令执行、控制身份透传或第二注册入口。
- 聚焦测试、安装态负控、独立审查或事务回滚证据失败。
- pytest、wheel 构建或其子进程并发执行，第三方 pytest 插件被自动加载，或受测进程树接近 8 GiB 内存而未停止。
- 新 design 未完成受控提交或没有所要求的 Skill 阅读轨迹；author 不能获得当前 qualified preflight/initialization；独立 deck review 未通过。

未知能力本身不是 Schema 错误，也不自动要求重做全部计划；Worker 必须在既有 resource judgment/handoff 中标明未知。若未知项阻止当前实现，依封存结果停止该有界任务，不由调度器补造环境支持。

## 2. 已核实事实与证据边界

| 事实 | 核查位置与含义 |
| --- | --- |
| 当前工作树有大量未提交改动 | `git status --short`；本修复只能按行处理重叠文件，不能整文件还原到 HEAD。 |
| 公共前言发生纯 Skill 策略改写 | `operation_declaration.py:OPERATION_AGENT_PREAMBLE` 的当前 diff；旧字节可从上述 HEAD 同路径取得。 |
| 前言影响科学摘要 | `operations/catalog.py:operation_digest` 将可达 ComponentSpec/resource_digest、reviewer digest、approval provider identities 纳入摘要；故共享提示能向 reviewer/transform 传播。编译器不是错误修复对象。 |
| design/revise 共用资源 | `general_science_experiment_operations.py` 两者均引用 `experiment_prompt`；`general_science_experiment_components.py` 的同一 EXPERIMENT_PROMPT 新增了 design 专属 execution_context/Skill 文字。 |
| opaque 是精确 schema | `operations/invoke.py:_validate_port_binding` 比较 schema_id；`operations/spec.py` 仅允许严格限定的 lineage inventory wildcard。 |
| 当前测试漏掉真实组合 | `test_agent_contract_alignment.py:test_experiment_execution_context_is_optional_and_read_only` 使用手造 opaque JSON，并检查其 readonly，未证明真实 capability producer 到 Root 的 admission。 |
| 安装态确为问题版本 | 只读运行 `/opt/scidiscovery-m7/site` 的 `compile_installed_catalog()`：48 Operations，design.execution_context=`opaque`，media_types 为 JSON/plain/markdown。`runtime_identity verify` 成功；control 和 approval UI 均 active。 |
| 真实 preflight 已失败 | 任务提供的独立复现：真实 `tcad.solver-capability.v2` 绑定 design 得 `input_schema_mismatch`；旧最新上游绑定新版 author 得 `input_producer_contract_changed`；均未创建 Run。本文未读取生产数据库或再创建 Run。 |
| backend 身份机制已存在 | `service/local_workspace.py:LocalTrustedBackend.backend_version` 当前为 `"1"`；`service/runs.py` 的 request_digest 包含 backend id/version/capabilities，并保存到 Run；recovery_available 查询比较这些字段。直接 resume_from admission 的差异见第 6.3 节。 |
| P2 已落在真实提交路径 | `local_debug_service.py` 生成 control-owned 报告；`operation_workspace.py` 提交时验证缺失、失败、过期及 source/project/declarations 绑定；`project_packager.py` 定义并核验两类 attestation。 |
| 插件和安装单入口已具备 | `tcad_artifact/pyproject.toml` 仅从 `scidiscovery.plugins` 暴露 `tcad_artifact.plugin:PLUGIN`；PLUGIN 已拼接 TRANSFORM_COMPONENT_SPECS/TRANSFORM_OPERATIONS，并依赖 general_science。 |

“19 个 Operation 及传播对象受纯前言影响”与下述对象复用边界来自已完成的独立审查；实施时必须生成逐 Operation 的实际摘要比较证据，不能把数量写成运行时白名单或硬编码测试总数。

P2 保留对象按真实名称表达：`source_tree_sha256`、`project_sha256`、`declarations_sha256`、`preflight_attestation`、`initialization_attestation`。`project_debug_sha256()` 绑定 source、invocation 和 materialized declarations，并排除报告自身，避免自引用。未发现独立的 `lobg`/`logb` 合同字段，不引入该猜测名称。solver log 继续是既有受控诊断输入/输出。现有测试确认 SDevice 初始化参数为 `-i initialize.cmd`，不在本修复中调整 solver 模式。

## 3. 逐文件修改表

下表是后续实施的全部计划修改面；本次只创建本文。所有“新增”路径均是明确要新建的文件，不是声称仓库中已经存在。

| 文件 | 修改量与唯一用途 |
| --- | --- |
| `src/scidiscovery/operation_declaration.py` | 仅恢复 OPERATION_AGENT_PREAMBLE 为 HEAD `2edac5d` 的原字节，包括换行/空格；保留其余现有内容。不要 git checkout 整文件。 |
| `src/scidiscovery/artifact_agent/service/local_workspace.py` | 仅将 LocalTrustedBackend.backend_version 从 `"1"` 递增为 `"2"`，标识现有 Skill 读取政策；不改 capabilities 或权限。现有 Run request/recovery 已承载版本，无需新身份系统。 |
| `src/scidiscovery/artifact_agent/service/runs.py` | 仅在既有 `_validate_resume` 入口对 source.backend_id/backend_version/backend_capabilities 与当前 backend 做同一精确比较，不一致则 RunStateConflict；复用 recovery_available 的事实/规则，补齐显式 resume_from admission 与 service 调用，约一个条件块。其余现有 dirty 改动不动。 |
| `src/scidiscovery/general_science_experiment_components.py` | 恢复旧 EXPERIMENT_PROMPT 原字节及旧 `experiment_prompt` 资源绑定；新增 EXPERIMENT_DESIGN_PROMPT/`experiment_design_prompt`，只为 design 加入执行上下文和 Skill 可行性要求；新增公共 `execution_context_schema` 资源并在现有 component_specs 中注册。旧 review/revise semantic resources 不动。 |
| `src/scidiscovery/general_science_experiment_operations.py` | design 改引用 `experiment_design_prompt`；execution_context 改为 `scidiscovery.execution-context.v1`、仅 JSON。保持 optional 0..1、64 KiB、full、prior_signal；revise 保持旧 `experiment_prompt` 及其精确端口/上下文。 |
| `src/scidiscovery/general_science_agent_operations.py` | `_schema_component` 字典增加一行通用 execution-context 到 execution_context_schema 的映射；不加入 TCAD 名字，不改其他 schema、codec 或 helper 行为。 |
| **新增** `src/scidiscovery/artifact_agent/schema/execution_context.py` | 一个严格不可变的 ExecutionContext 模型，复用 SchemaModel；字段按第 4 节。无 I/O、探测、插件导入、资格/状态逻辑。 |
| `plugins/tcad_artifact/tcad_artifact/operation_transforms.py` | 增加一个纯 projection 函数、CallableComponent、ComponentSpec 和 support OperationSpec；复用 `_one`/`_input`/`_operation`，使用 general_science 公共 schema 和 JSON codec。新 Operation 的跨插件输出端口直接内联构造一个 `OutputPortSpec`；不修改共享 `_output` 辅助函数及其他 transform 声明。 |
| **新增** `tests/operations/test_skill_policy_producer_compatibility.py` | 保存有源码来源的旧提示字节 fixture，比较真实 catalog 摘要和 Root producer admission；测试 design/revise 隔离及真实合同变化负控。不得保存“允许旧摘要列表”。 |
| `tests/operations/test_agent_contract_alignment.py` | 改掉 opaque 假正例；检查新 schema 的 optional/readonly、缺上下文路径、design 专属 prompt 和既有 output contract。 |
| `tests/operations/test_general_transform_operations.py` | 加真实 Snapshot → support → Artifact → design Root preflight/invoke 正例，以及未知、错误 schema、确定性/父链/幂等负控；复用现有 runtime/Root fixtures。 |
| `tests/operations/test_catalog_installed_entrypoint.py` | 用现有 installed_probe 验证 wheel 中 schema/投影、core-only 与 full/figure 目录差异，以及无源码导入的真实组合；仅修正受新增 support 影响的精确集合断言。 |
| `tests/artifact_agent/test_platform_configuration.py` | 验证 Local Skill 指令与科学 prompt 身份分离、author/reviewer 工具面仍与 compiled contract 相同；不引入 role.skills 或 Skill 新 MCP 工具。 |
| `tests/operations/test_l2_run_invariants.py` | 增加 backend version 对 Run request_digest、recovery_available、Root 显式 resume_from preflight/invoke 与 service gate 的正反测试；使用既有 runtime，不改变“completed scientific producer 由 operation digest 判断”的规则。 |

以下文件只读并运行已有检查，默认零改动：`platforms/codex.py`、`operations/catalog.py`、`operations/invoke.py`、`operations/spec.py`、Root operation routes、`general_science_plugin.py`、TCAD `plugin.py`/`project_packager.py`/`operation_workspace.py`/`local_debug_service.py`/`roles/*`、`deploy/install.sh`/`install_transaction.py`/`reinstall.sh`、两份 INSTALL 文档、Skill 完整目录、`test_l4_local_tcad.py`、`test_tcad_knowledge_closure.py`、`test_deploy_scripts.py`、`test_m6c_producer_topology_removal.py`。`platforms/codex.py` 当前已经明确给出 Skill 只读例外、scratch 边界和禁止扩权规则，恢复科学前言后不得再追加澄清文字。旧测试若对新增 catalog 成员作精确枚举，只修正该断言；若需要生产改动，先向独立审查说明证据，不能自动扩面。

不递增 general_science/TCAD PluginDefinition.version，不修改 OperationSpec 框架 ABI，也不改变既有 operation_id。编译器把 plugin version 纳入可达 component digest；对本次局部变更做全插件升级会再次退役无关对象。新合同有独立 schema id，design 的输入合同及可达资源发生真实变化，其 operation digest 必须改变；旧 initial design intent 因此不复用。新 support 有独立 id；revise 及无关 Operation 的摘要必须保持不变。

## 4. 最小 `scidiscovery.execution-context.v1` 数据合同

通用合同描述“该不可变来源明确声明了什么”，不证明 license 可用、程序可运行或科学可行。它不携带命令执行权限、批准、current 指针、Run/Artifact 控制身份、宿主路径、环境变量或私有配置。

`SolverCapabilitySnapshot` 的真实字段为：schema_version=2、profile_id、solver_kind、launch_name、public_arguments、public_release_label、private_fixed_argument_count、private_fixed_arguments_sha256、private_release_evidence_bytes、private_release_evidence_sha256、capability_sha256。没有 supported_models、controls、observables、resource_limits，也没有可独立认证的 solver release 字段。`public_release_label` 还可能由 profile_id 回退生成，不能把它当成验证过的版本号。

选择以下一个扁平模型，不嵌套新的“能力框架”：

| 字段 | 类型/边界 | TCAD v2 的唯一映射 |
| --- | --- | --- |
| `schema_version` | Literal[1]，继承 SchemaModel | 1 |
| `domain` | 非空字符串，最多 256 字符 | `tcad`；这是投影所属领域，不是 core 的领域枚举。 |
| `implementation_backend` | 非空字符串或 null，最多 256 字符 | 原样复制 launch_name；`bash` 等名称仍只是启动实现，不能升级为 Sentaurus 声明。 |
| `implementation_kind` | 非空字符串或 null，最多 256 字符 | 原样复制 solver_kind；这是来源声明的实现种类，不是 core 的 solver 枚举。shell_runner/deterministic_tool 也照实表达，不根据脚本名或参数猜测 sprocess/sdevice。 |
| `release_label` | 非空字符串或 null，最多 256 字符 | 原样复制 public_release_label，仅是来源公开标签；不解析/补全 release。 |
| `public_arguments` | 字符串 tuple 或 null，最多 256 项；完整对象受 64 KiB 限制 | 原样复制 public_arguments；空数组表示来源明确没有公开参数，不表示没有私有固定参数。不得据此拼接执行命令。 |
| `capability_statements` | null 或最多 32 条、每条 1024 字符的非空字符串 tuple | 固定为 null；Snapshot 没有可转换的模型/controls/observables 能力陈述。 |
| `limitations` | null 或同上界的陈述 tuple | 固定为 null；Snapshot 没有资源/实现限制合同。不能从未公开参数数量或 Skill 推算限制。 |

所有 nullable 字段应在输出中显式出现；模型允许未知，禁止额外字段。通用字段不枚举 TCAD solver，不导入 TCAD model。投影先 strict 解析 SolverCapabilitySnapshot，然后创建 ExecutionContext，用 canonical_json 序列化。Snapshot 的必填字段缺失是输入损坏，应失败；通用能力缺失是合法未知，不应制造默认“支持”。

确切输入 Schema、ArtifactRef、内容摘要和 instance parentage 只由 Operation 输入合同及 Root 的 Artifact envelope 承载，不复制进科学 payload，不建立第二份来源事实。无需把 profile_id、私有摘要、内部 Artifact id 或新 provenance 对象复制给 design。模型字段与 schema descriptions 必须明确 null=未声明，空集合=来源明确空；不得把 null 读成“无约束”。

`execution_context_schema` 使用现有 schema_resource 生成并作为 general_science 的 public resource 暴露。结构和字段语义可以由 JSON Schema/description 表达；投影无 Worker 科学作者，不借 scientific_semantic_contract 的“Worker 作者”通则造一个不适用的 transform semantic layer。design 保留现有语义验证器：能力匹配属于 Worker/独立 review 的科学判断，不能新增隐藏 Python 规则把可选 context 变成必填。

design 专属提示要求：先读已绑定 context；按原标签和明确声明判断实现背景；读描述匹配的已安装 Skill 的必要资源；Skill 说明方法，context 才声明环境；任何未声明能力/缺失 Skill 写进现有 resource judgment 与 handoff。通用提示不出现 TCAD、Sentaurus、固定 Operation id 或 solver 命令。

## 5. TCAD support 投影的完整声明

拟注册 id：`tcad.execution-context.project.v1`。这是实施期新增声明的名称；真实调度必须从启动编译后的 support catalog 发现并读取其端口，不能从本文名称直接绕过 catalog。

| OperationSpec 部分 | 精确设计 |
| --- | --- |
| plugin/scope/version | tcad_artifact；support；version=`1`。 |
| description | 把一个明确公开的 TCAD capability snapshot 确定性投影为通用执行背景；适用于所选通用设计需要该背景；不用于探测环境、推断科学可行性或执行 solver。 |
| executor | kind=transform，component=`execution_context_project`，无 agent/workspace/tools/network/effect。 |
| input | `capability`，schema=`tcad.solver-capability.v2`，schema resource=`capability_schema`，general_science json_codec，JSON，1..1，64 KiB，full，prior_signal。 |
| output | `execution_context`，kind=`execution_context`，schema=`scidiscovery.execution-context.v1`，schema resource=`ComponentRef("execution_context_schema", plugin_id="general_science")`，JSON codec，同上，1..1，64 KiB，payload_schema_version=1。它是唯一 primary output。 |
| limits | 复用现有 `_operation`：timeout=300 秒，max_input_bytes=64 KiB，max_output_bytes=64 KiB，max_files=1；纯变换无需额外超时框架。 |
| admission/review/effect | 不新增 approval/review/guards；现有 exact schema/producer/instance/name gates 全部生效。consequence 继承工厂的 scientific，仅表明正式派生 Artifact，不授予科学 verdict。 |
| component identity | 现有 ComponentSpec/CallableComponent；为这个新 transform 声明明确 configuration_identity=`tcad.execution-context-project.v1`，其资源闭包绑定通用输出 schema 与输入 capability schema；将来映射行为变化必须改变此身份或已声明资源。 |
| 父链/幂等 | Root `_operation_transform` 以该 exact capability Artifact 为唯一直接 parent，自动记录 operation digest/output port/invocation fingerprint；重复完整请求同名幂等，换来源或内容用新名/显式 revision。投影函数不自行注册 Artifact。 |

注册只追加到现有 `operation_transforms.py` 的 COMPONENT_SPECS/OPERATIONS；TCAD PLUGIN 已在单入口拼接二者，无需新 entry point、runtime factory 或 service。general_science 无 TCAD 依赖；core-only 环境保有通用 schema/design，缺少 TCAD 插件时没有这个 support helper。

调度规则：Root 根据当前问题先选择有科学价值的 public design；若该调用拟绑定执行背景而只有真实 capability snapshot 可用，才从 support catalog 选择匹配投影、绑定 exact artifact_name、preflight 后 invoke。已有相同来源的合格投影则直接复用；design 的 context 仍可省略。不得把 helper 自动挂成固定阶段、后台依赖执行或新 Agent Run；不得为此次 author 续跑强制重新 materialize 实验计划。

## 6. 摘要恢复与对象复用证明

### 6.1 字节恢复方法

先固定修复前工作树快照及 `git diff --binary` 证据到隔离测试目录，不提交/整理其他人的改动。用 `git show 2edac5d317a74056869a567bd0daa7f556ecbc85:src/scidiscovery/operation_declaration.py` 取原前言，以 Python AST 字面量提取或人工精确取值，保留原 bytes；旧 EXPERIMENT_PROMPT 同理取自该提交的 `general_science_experiment_components.py`。只恢复这两个字符串以及 revise 既有资源指向。

新 design prompt 可以独立组合稳定 EXPERIMENT_PROMPT 加 design 专属补充；不能重新格式化旧 experiment_prompt，也不能改它的 ComponentSpec/import_path/configuration_identity。新增资源只进入 design 可达闭包，新增 Operation 不应改变任何既有 Operation 的全局身份。

### 6.2 无生产数据库、无旧摘要白名单的证明

新增兼容性测试保存上述原字符串及版本化来源说明，运行时不需要 `.git`。用同一编译器、同一 OperationSpec/ComponentSpec 路径和同一科学资源构造配对 catalog：

1. **稳定科学基线**：所有无关 Figure/Curve/P2 资源保持相同；只有两个有来源的共享旧字符串作为基线资源值。测试替换实际资源属性值，不能换 import_path 或改摘要算法，否则不是同一身份比较。
2. **污染负控**：只加入已审查的全局 Skill 前言文字，编译真实可达依赖闭包；确认受影响 producer 与 reviewer/transform 摘要发生变化。再只把 design 专属文字放进旧 experiment_prompt，确认 revise 摘要改变。
3. **修复候选**：原前言、原 experiment_prompt、新 design 专用资源和通用端口；全部“仅因前言/共用提示受损”的 producer 必须与稳定科学基线逐项 `digest == digest`。不从当前候选反向生成“期望旧文本”。
4. **历史准确性**：对声称复用的现有科学合同，额外以版本化历史声明/资源构造实际历史 catalog，核对其可达闭包与稳定科学基线。已有其他工作使某个历史 schema/语义确实不同的，不能为了匹配而还原那些科学变化；该对象按真实变化退役，并阻断不实的复用结论。
5. **真正合同变化负控**：改变一个受消费输出 schema/semantic rule 或 TCAD P2 workspace configuration_identity；真实 Root admission 必须仍报 `input_producer_contract_changed`。旧 initial design 与当前 design 摘要应不同；旧 TCAD author/review 的真实前 P2 声明/资源在 fixture 中动态编译，其旧标签仍拒绝。

所有旧 producer 标签由基线 catalog 现场生成，不手填 hash。`test_m6c_producer_topology_removal.py` 已有 `_produced_artifact`/Root producer admission 的写法可参照；新增测试不能只模拟 `_operation_output_contract` 为通过。补一条临时 instance/runtime 的 Root facade 路径：以旧 catalog/合法 fixture 生成完整输入和批准/审核关联，切换同一临时状态到修复 catalog 后 exact preflight；生产数据库、M7-test0 私有输出不参与测试。

记录 operation_id、基线/污染/修复 digest、差异来源、可绑定/拒绝结果。测试可覆盖编译目录中所有 Agent/review 引用以发现传播；运行时不得出现“十九个允许值”的列表。显式枚举复用期望是测试案例，不能成为兼容 bypass。

### 6.3 复用边界

| 保留并可按既有资格绑定 | 保留但不作为当前资格复用 |
| --- | --- |
| 原始来源、完整 Fig.4 图证据族、reference bundle、intake split/foundation、research objective | 旧 initial experiment intent，因为 design 本次确实改变执行背景合同。 |
| 稳定前言恢复后的最新 intake/audits、hypothesis/critic | 早期 curve contracts 2/3 与 review1；不能以新契约资格覆盖它们。 |
| curve contracts 6/7；reviews 2/3/4 | 所有旧 TCAD author outputs/review；P2/知识使用属于真实 author/review 合同变化。 |
| experiment reviews 1–9、materialized plan | 任何内容、输入、review subject 或 execution payload 已改变的旧 approval/review，不能继承。 |
| 拆提示后 experiment plan revisions 1–5；solver capability snapshot | 若实际 compile/admission 与左侧预期冲突，先停下核对 exact 版本；不能强制“最新”等于可用。 |

backend version 的递增改变新 Run 请求身份，并使旧 backend 的 recovery_available 查询返回 false。已完成科学输出继续以 operation id/version/digest 和精确绑定判断；不会为了 Local policy version 重签旧科学 Artifact。测试必须分别证明这两个层面。

只读追踪发现需要在同一修复中闭合的直接协议差异：Root 的显式 resume_from 路径调用 validate_resume → _validate_resume，后者检查 operation/input/draft/次数，当前没有重复 recovery_available 的 backend 比较。在 `_validate_resume` 入口加入 `source.backend_id != self.backend.backend_id`、`source.backend_version != self.backend.backend_version`、`source.backend_capabilities != self.backend.capabilities` 的同一精确判定，不一致即 RunStateConflict。这样 Root 的 preflight/invoke 和 service schedule 都通过同一个既有 gate，Root 原有异常映射继续给出 recovery_source_unavailable，无需改 Root 或新增恢复协议。

先失败测试分别只改变 backend id、version、capabilities，保持 operation digest/inputs/draft/预算相同：修复前 recovery_available=false 但显式 resume 仍可能通过；修复后两条入口都拒绝、无新 Run。正例是 backend 三元组完全相同且既有 operation/input/预算条件均满足时仍允许受控 recovery。此测试不承诺旧 draft 可以迁移。本次 Fig.4 生产验收全部创建新 Run，不绑定 resume_from，也不恢复旧隐藏会话。

## 7. 分阶段实施与不可跨越的验收

### S0：锁定失败基线

保存当前 HEAD、精确 dirty diff、安装目录 identity 验证结果、所选插件集合和服务参数；只记录配置位置，不收集 secret。所有测试数据在临时目录，生产无写入。

先写出可重复失败测试：真实 Snapshot 直接绑定 design 报 schema mismatch；纯前言改变退役无关 producer；共用提示改变 retire revise；backend 身份改变时 recovery 查询与显式 resume admission 不一致。新增投影缺失时，所需正例应明确失败于缺少声明/合同，而不是以 skip 混过去。现有 opaque 假正例不作为失败基线证据。

通过：三个 P1 及 backend identity 的 admission 差异可由具体测试和受影响闭包重现，同时 P2/Skill 现有检查基线通过或已有失败单独归因。失败：旧字节/实际历史声明无法定位、工作树有不能隔离的并发变化，或测试错在环境缺依赖。未通过不得改生产源码。

### S1：实施最小源码修复

依次恢复前言及旧 EXPERIMENT_PROMPT；拆出 design 提示；加通用模型/schema 映射与 port；加 TCAD support；使用现有 backend_version 标识策略，并补齐 `_validate_resume` 同一身份 gate。逐项记录预期 digest 差异，所有新增资源进入声明闭包。

通过：catalog 可编译，design 与投影接口完全一致，revise 无新资源可达；production diff 只在第 3 节范围；没有 plugin/ABI 全局版本变化。失败：新增资源使未消费它的旧 Operation 退役、投影必须访问外部状态或出现 hidden validation。未通过不得做安装测试。

### S2：聚焦测试和完整闭环证据

从源码根使用部署同代 Python。所有 pytest 必须严格串行，不使用 xdist，不与 wheel 构建、真实 Agent、OCR 或第二个审查任务并发。每个测试文件使用新的 pytest 进程，前一进程退出并确认内存释放后才能启动下一项。统一禁用第三方插件自动加载、pytest cache 和多线程数值库；以既有监测方式统计 pytest 及其全部子进程的进程树内存，接近 8 GiB 时立即终止该批并保留失败证据，不能依赖 swap 掩盖。以下是实际存在的检查入口；新增测试文件在 S1 才创建：

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export MALLOC_ARENA_MAX=2
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
ulimit -v 7340032

for test_file in \
  tests/operations/test_skill_policy_producer_compatibility.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_tcad_knowledge_closure.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
do
  /home/da/miniconda3/bin/python -m pytest -q -p no:cacheprovider "$test_file" || exit 1
done

/home/da/miniconda3/bin/python -m pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_installed_entrypoint.py
```

最后一条 installed-entrypoint 检查必须在前述进程全部退出后单独运行，并使用现有 installed_environments/installed_probe：它通过 `scripts/build_git_release.py` 从当前源码生成隔离 release，构建 wheels，在不继承系统 site-packages 的 venv 安装，并从与源码无关目录运行。不能以 tests/conftest.py 的 source metadata monkeypatch 代替真实 entry point 证据；确认新 model 和未提交新增文件确实进入 release/wheel。

通过：第 8 节矩阵全部具备通过输出，负控按预期拒绝；测试未接触生产 DB/Run/外部 solver，完整 Skill helpers 没有写全局目录。失败：一项依赖测试被 skip、仅只读路径绿而真实 Root 绑定红、只有源码 catalog 绿而 wheel 失败。未通过不得进入部署。

### S3：独立审查

独立审查者读取精确最终 diff、双向接口、完整 prompt/schema/tool surface、配对 catalog 证据、P2 留存证据与安装事务测试。审查对象是这次修复及它与现有工作组合后的行为，不把所有 dirty diff 当成本次作者的变更。

必答问题：旧字符串是否逐字节恢复；历史对象复用是否证明到了 Root 而非假标签；执行上下文是否只含科学设计所需的公开声明而不复制 Root 来源事实；unknown 是否被过度解释；新增 support 是否唯一注册且无副作用；backend version 是否只影响 Run/recovery，查询/显式 resume/service gate 是否精确一致；P2 和 reviewer 权限是否完整保留；部署回滚是否保护新旧科学对象。

通过：无未解决 P1/P2 阻断，审查证据与最终文件快照一致。失败后只做有界修订并重跑受影响检查，再复审；不能因测试全绿跳过独立审查。

### S4：事务安装、服务重启与新会话加载

先确认没有 queued/running 科学 Run 或活动外部 execution 正在使用被升级合同；用受控状态查询确认，不直接改状态表。若存在则等待既有受控生命周期完成/失败，不能热换正在工作的 compiled worker。部署需要由已有授权且具备系统写入权限的维护入口执行；本计划不自行改变沙箱权限。

本次冻结查询的实际结果是：没有外部 execution、没有待审批，但残留四个已过截止时间且 `recovery_available=false` 的旧 Run。旧服务因其 Operation 合同已经退役而拒绝 `run_record_failure`。为避免永久阻塞部署，只允许 `timed_out=true`、deadline 已过且既有 CAS 前提精确匹配的退役 Run 在新服务中转为 failed；其工作区保持原样且不成为恢复来源。实现后相关定向测试 6 项和完整 L2 测试 21 项通过，独立审查 PASS，峰值内存约 150 MiB。冻结条件持续成立时，先完成既有事务安装、健康检查和 seal，再由新 Root 以最新状态及 activity 值逐一 CAS 终结；进入 S5 前必须确认 queued/running 和外部 execution 均为空。任一 CAS 失败就重新查询，绝不直接编辑 SQLite；成功 seal 并产生生命周期更新后不得恢复旧数据库快照。

已只读核实的当前参数：

| 参数 | 值/处理 |
| --- | --- |
| SCID_INSTALL_ROOT / SCID_STATE_ROOT / SCID_CONFIG_ROOT | `/opt/scidiscovery-m7` / `/var/lib/scidiscovery-m7` / `/etc/scidiscovery-m7` |
| SCID_WORKSPACE | `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector` |
| SCID_CODEX_LAUNCH_ROOT | 本次交互根 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`；实施前核对实际启动位置，并同时生成源码根/workspace/launch-root 的受管配置。 |
| SCID_PYTHON / backend / platform | `/home/da/miniconda3/bin/python` / local / codex |
| SCID_PLUGINS | 保留当前 `tcad_artifact,curve_score,curve_figure_evidence` 集合；installed catalog 当前 48 是观察值。 |
| SCID_TCAD_COMMAND_CONFIG | `/etc/scidiscovery/command-adapter.json`；来自 `/etc/scidiscovery-m7/tcad-plugin.json` 的已配置 command transport。不能遗漏后回退成本地 smoke profile。 |
| Skill root | 服务用户已有的 `/home/da/.codex/skills`；保留完整 sentaurus-tcad-code 目录，不只复制 SKILL.md。 |
| backup root / service user/group / TCAD_STATE_ROOT | 从现有部署参数精确复用；本文未核实的值不得自行改成脚本默认值。 |

先以这些参数执行 `deploy/reinstall.sh --dry-run` 并核对输出，再执行同一环境下的 `deploy/reinstall.sh reinstall`。`reinstall.sh` 会调用既有 sudo/install 入口。不要绕过入口手工覆盖 `/opt`、生成配置或数据库。

安装器既有顺序是：源/依赖校验和包构建 → begin transaction → 停旧服务 → 激活包/完整 Skill/受管配置 → 启动 control/UI → MCP、UI、installed profile 验证 → seal transaction。保留该顺序与故障 trap；不新增部署流程。应保留平台的原始错误与回滚证据，不把失败重新描述为安装成功。

通过：runtime identity 校验、服务/MCP/UI 健康、compiled installed profile、完整 Skill 校验全部通过；新增 support 可从 support 目录发现；Agent 集合不新增（数量依 catalog 动态计算），全目录净增一个 support 时观察值应为 49，但不把 49 写成框架恒定约束。core-only 无 TCAD helper。然后关闭旧 Codex 会话并创建新会话加载同代定义。

失败：部分服务/平台定义仍为旧版、helper 缺席、Skill 缺资源、installed digest 与审查版本不一致。自动回滚完成之前不派发 Run；重新安装后必须重新新建会话。

### S5：新会话真实 preflight 与 Skill 轨迹

先 `instance_current`，只按用户明确继续的 M7-test0 绑定工作；未绑定时给 exact local management URL，由 UI 选择实例，不用默认实例。读取当前 catalog 与 immutable semantic inventory，按确切名称填写每个声明端口。

先选择新的 design 公共动作作为有界 Skill/执行背景验证：复用已审查的 objective/hypothesis/critic/foundation；如缺对应投影，先对 exact capability 做 support preflight/invoke，读取其受控输出。该次验收任务必须包含一个确实需要查询手册 helper 才能回答的、边界明确的实现可行性问题；不能为制造轨迹而调用与任务无关的工具。对 design 使用独立新语义名和明确指令，要求按需阅读匹配 Skill 的 SKILL.md 及必要手册 helper，报告已声明与未知能力；不要求它写出“可行”的预定结论，也不把此次 helper 要求推广成所有实验设计的固定流程。

设计动作 preflight 成功后，用同一 immutable request invoke；只 dispatch 返回的 agent_type，`spawn_agent` 使用 `fork_turns="none"`，消息只要求完成已排队 assignment。Root 不调用 worker_*，不把历史 draft/路径/控制信息转交给子 Agent。

通过条件必须同时满足：

- 新 Run completed，Root 的 run_status.sealed_output 与 scheduler_signal 可读，context 绑定正确；未知能力保留在既有资源判断/交接中。
- 实际工具轨迹显示读取发现的全局 Skill/SKILL.md 及任务所需资源，并为上述确有需要的验收问题至少运行一次对应手册 helper；仅 prompt 含有“可读 Skill”或无关的仪式性工具调用不算证明。
- helper 每次显式设置 TMPDIR、XDG_CACHE_HOME 为该 Run scratch，PYTHONDONTWRITEBYTECODE=1；Skill 前后内容一致，无 repo/historical-run/其他 workspace 访问，无 debug/网络/安装/执行扩权。
- Root/design/TCAD reviewer 的工具允许集合与编译声明一致；soft isolation 只是可信本地边界，不能宣称已证明技术级隔离。
- 对旧最新上游执行当前 author 的真实 preflight 可通过；对旧 TCAD project 的当前 review/revision 绑定仍以 producer contract changed 拒绝。这些 preflight 本身不得创建 Run。

轨迹审查是维护者对该新 Run 的执行证据核验；不得把日志/隐藏对话作为下一科学 Worker 的上下文。科学结论仍只读封存输出。failed/timed-out Run 明确记录，重试是新 Run；不得用旧聊天声称完成。

本次 Skill 轨迹只使用现有 Codex 会话可见的子智能体工具活动、运行前后的 Skill 内容摘要和 workspace/scratch 中留下的任务相关结果作为开发验收证据。不得为此新增生产追踪协议、日志实体、审计注册表或 Operation 字段；这些运维证据不是科学 Artifact，也不能进入后续 Worker 输入。若现有界面无法观察到必要调用，则该项验收未完成，不能通过新增自报字段替代。

这个新 design intent 是验证结果，**不自动 materialize、取代已有 reviewed plan、刷新 curve contract 或启动新研究链**。本次 Fig.4 续跑复用既定计划；若验证揭示真实计划不可实现的科学阻断，停下记录 bounded gap，另由当前 contradiction 和 catalog 决定后续动作。

### S6：从新 TCAD author 开始继续 Fig.4

使用第 6.3 节可复用上游的 exact artifact_name，选择当前 catalog 的 initial TCAD author，执行 preflight → invoke → 无 parent history spawn。不要重跑来源、Fig.4 evidence、intake、hypothesis、experiment revision 或 contract。

author 阅读完整全局 Skill 的相关资源，编写新 project，并通过本 Operation 已声明的 worker_tcad_debug_run 获得当前 qualified preflight，再在同一未改变的 source/invocation/declarations 上获得 qualified initialization。任何后续源码/入口/声明更改都要求相应新诊断；两项都成功且受控提交完成后才有新可审核 project。

按当前 catalog 的 review_edge 选择新独立 deck review，绑定新 project 和精确既有上下文。reviewer 读取封存的两个 attestation，不得到 debug tool/runtime plugin config，不以文字补造或继承证明。读 completed run_status 的 sealed verdict；有阻断按声明 review/revision 边界修订并重新 author 诊断、重新独立 review，不扩大任务。

新 review 通过后，才可称“可以继续 Fig.4 E2E 的受控执行部分”。后续 package/执行仍从当前 catalog 选择；正式外部 execution 的 operation_invoke 返回 exact loopback review URL，交给用户在 UI 决策；仅 approval_status 读到 sealed decision 后才 execution_start/bounded execution_sync。聊天不等于审批，development debug 不等于科学执行证据。

## 8. 最小测试矩阵与先失败后通过证据

| 场景 | 修复前/负控应看到 | 修复后验收证据 |
| --- | --- | --- |
| 真实 capability → 通用 design | 直接绑定 v2 Snapshot 到 opaque 得 input_schema_mismatch，无 Run。 | Root support invoke 注册 v1 context，随后同一临时实例 design preflight/invoke、readonly assignment、正常封存；wheel 与新会话均验证。 |
| 完全省略 context | 无该输入时原科学设计仍可建任务。 | 保持 0..1，输出校验不强制 context；不存在隐含 capability/Skill 必填规则。 |
| 未知能力/未知 release | 不得用 opaque 手造 supported_models。 | public label 原样保留；implementation_kind=`shell_runner` 时不推导 sprocess；capability_statements/limitations 为 null；无能力推断。 |
| Snapshot 必填字段缺失 | 应是损坏输入。 | strict Snapshot/既有 schema 验证失败，不输出“默认支持”context，不注册半成品。 |
| 错误 schema/media | 原始 capability、opaque JSON、错误版本不得直接冒充 context。 | exact schema/media 拒绝；同 schema 非法 JSON/多余字段经真实验证路径失败；wildcard 限制原样。 |
| 投影确定性与父链 | 仅测试函数返回 dict 不足以通过。 | 同语义输入得同 canonical 输出；Root output 唯一 parent=exact capability，来源摘要只存在于 Root envelope；来源换成同值但不同 bytes 时由 Root 请求身份和父链区分，科学 payload 不复制该机械差异；同一完整请求幂等，不覆盖旧对象。 |
| 旧最新上游绑定 | 污染前言/共用提示导致 producer changed。 | 动态基线 catalog 标签通过真实 Root producer/review/cohort gates；第 6.3 节复用集合逐项有记录。 |
| 旧 TCAD project | 旧 author/review contract 不满足 P2。 | 历史合同现场编译标签仍拒绝，不从 old project 创建新合格 review；不得因为前言恢复而复活全部历史。 |
| design/revise 摘要隔离 | design 专属文字改动同时改变 revise。 | 仅修改新 design prompt/port，design digest 变、revise/旧 experiment_prompt digest 不变；旧 initial intent 不被错误复用。 |
| 真合同变化 | 修改 schema/semantic/workspace identity。 | producer gate 继续明确拒绝；测试不 mock 掉 gate，不维护旧 digest 列表。 |
| backend policy 身份 | backend 三元组之一改变，查询不可恢复但显式 resume 仍可进入。 | version=2 改变 request_digest；旧 recovery_available=false、显式 preflight/invoke/service schedule 拒绝且无新 Run；同 backend 正例通过。completed 未改科学 producer 仍按原 operation identity 可用，本次 Fig.4 全部使用新 Run。 |
| Local Skill 可读/不扩权 | 只检索 prompt 文本不足以证明运行。 | platform unit 断言 + helper scratch 内容/只读检查 + 新 design 真实轨迹；enabled_tools、native policy 不增权。 |
| reviewer 无 debug | 不能因“Skill 可以读”而获得调试能力。 | `test_local_tcad_author_debug_and_independent_review_share_one_operation_path` 与 platform config 验证 reviewer 无 worker_tcad_debug_run/command config。 |
| P2 当前证明门 | 缺失、失败、source 改动、entrypoint 改动、declaration 改动、initialization missing/failed/stale。 | `test_author_submission_requires_current_control_diagnostics` 各分支拒绝；重新诊断后通过，materialized SProcess 两报告 declarations hash 相同。 |
| 完整 Skill/安装事务 | helper 可执行不代表完整 Skill 安装/回滚正确。 | `test_tcad_knowledge_closure.py` 手册查询与 scratch；`test_complete_tcad_skill_install_integrity_removal_and_rollback`；部署事务/完整目录/symlink/回滚检查通过。 |
| 安装边界与插件消失 | 源码手装 catalog 绿不算。 | installed_probe full/figure/core-only、单 entry point、运行 identity/profile 同代；禁用 TCAD 时 support 缺席但通用 design 可省略 context，无残留权威。 |

矩阵中的新正例必须在 S0 有可定位的失败或缺失断言，S2 有对应通过输出；负控必须始终按指定 gate 失败。保留命令、退出码、短失败原因和 catalog 对照，不将 pytest 总数/覆盖率当成放行理由。

## 9. 最小回滚与证据留存

源码未安装时，只以逐文件/逐 hunk 的补丁反向撤销本次改动；保留实施前原样快照。重叠文件不得整文件还原，不动既有 Figure/Curve/P2/Skill 修改，不运行 git reset/clean。新增文件若需撤回，移入本次隔离备份供恢复，不删除其他工作。

安装失败且 transaction 仍 prepared 时，沿用 install.sh 的 rollback_install 和 install_transaction.py：恢复该事务精确覆盖的包、完整 Skill、受管配置、服务状态及数据库一致快照。安装窗口必须没有并发科学写入，这样既有数据库回滚不会抹去新科学对象。失败测试在临时文件/数据库验证，不对 M7-test0 演练破坏性回滚。

成功 seal 后不能把历史事务改回 prepared 或直接恢复其旧数据库快照；现有 rollback_transaction 也只接受 prepared。尤其 S5/S6 已产生新 Artifact/Run 后，退回代码应是**新一次安装事务中的文件版本回退**，保留当前科学数据库和对象；新版本产生的对象可以在旧 catalog 下 contract_retired，但不能删除、重写或把旧摘要塞入它们。记录部署回退后哪些合同不再可调用，重新创建会话。

留存证据限定为：精确修复 diff/版本、测试结果、catalog 摘要对照、安装事务证据位置、运行 identity/profile 结果、受控 preflight 拒绝/通过、新 Run 完成状态、必要的工具轨迹合规核验与 UI 决策状态。不把生产秘密、child 草稿、隐藏聊天或工作区路径复制进科学输入。

## 10. 最终“可以继续 Fig.4 E2E”的放行清单

只有下列条件全满足，才能放行受控执行部分：

1. 三个 P1 各有先失败后通过证据；稳定前言/revise 字节和 producer digest 恢复，真实科学变化仍退役；backend policy 的现有 Run 身份和显式 recovery gate 一致。
2. 通用 v1 合同与 TCAD v2 support 投影已通过 Root/wheel/new-session 正反例，未知能力无虚构，父链/来源绑定可追溯。
3. 独立审查无未解决阻断，安装事务成功封存，control/UI/插件/新 Codex 会话/完整 Skill 同代。
4. 新 design Run 已完成受控提交，有实际 Skill 只读/helper scratch 轨迹，工具面未扩张，未替换既有 Fig.4 计划链。
5. 已审查的旧最新上游可绑定；旧 TCAD project/review 仍不能作为当前资格；证据/假设/计划未重跑。
6. 新 TCAD author completed，当前 source/invocation/declarations 的 preflight 和 initialization 都 qualified 且封存；新独立 reviewer 无 debug 并已完成通过。
7. 正式外部执行继续等待该精确执行请求的 UI 审批；放行此计划不继承任何旧 execution approval，也不等于 Fig.4 科学结果已经成立。

S3 独立复审结论为 `PASS`：当前 reviewer 摘要正例通过，精确历史摘要负例仅因 producer contract 变化而拒绝；聚焦测试文件 `5 passed`，进程树峰值约 185.3 MiB，`git diff --check` 通过，且本次补充修正没有修改生产文件。安装事务、新会话与真实科学运行仍必须由 S4—S6 的实施证据回答，不能由该测试结论提前替代。
