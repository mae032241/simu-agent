# 当前生产代码设计冗余评估

日期：2026-09-01  
状态：只读现状评估，不是规范架构、实施计划、迁移授权或阶段通过结论  
评估对象：当前未提交工作树；代码继续变化后，行数、消费者和结论必须重新核验

## 1. 评估目的

本文回答以下问题：

1. 当前生产代码为什么仍然接近五万行；
2. 千行以上文件中哪些是真实科研或安全能力，哪些是设计冗余；
3. 通用控制包、通用科研 Schema、TCAD 插件和曲线插件分别还能裁剪什么；
4. 如何在不破坏 33 项行为约束、通用科研 Agent 目标和 TCAD 闭环的前提下继续减重。

本文遵守[科学研究 Agent 最小设计宪章](../architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md)：

- 保留不可变产物和显式来源；
- 保留唯一 current 权威和必要的比较交换更新；
- 保留科学判断、确定性变换和外部副作用之间的边界；
- 保留有界 Worker、独立审查和精确人工审批；
- 保留外部执行的幂等状态与不确定提交查回；
- 不把 33 项约束实现成 33 个运行实体；
- 不因文件较大就删除真实科学算法或安全规则。

## 2. 规模快照

当前 `src/scidiscovery/` 与 `plugins/` 下生产 Python 代码为：

| 范围 | Python 行数 |
|---|---:|
| 通用包 | 27,260 |
| 插件 | 22,763 |
| 合计 | 50,023 |

其中：

- 43 个文件不少于 400 行，共 33,457 行，占生产代码约 67%；
- 15 个文件不少于 800 行，共 17,340 行，占生产代码约 35%；
- 通用包中 `artifact_agent` 为 21,377 行，`operations` 为 2,139 行，平台适配为 1,027 行；
- TCAD 插件约 13,085 行；
- 曲线插件约 8,926 行。

文件集中度很高，但不能据此直接得出“所有大文件都应删除”。当前冗余主要来自四个来源：

1. 新操作体系已经建立，但旧适配器、旧 profile 和旧数据模型仍在实际链路中；
2. 实例选择、资格准入、下游用途和审批被重复编码在多个层次；
3. 远程执行、加固 Worker、图证据和便携包等可选能力仍常驻默认生产面；
4. 一个领域插件同时承载多套纵向科研产品，依赖边界过宽。

## 3. 结论摘要

当前仍有明显的大幅裁剪空间，但裁剪重点不应放在 `Run/current/Artifact` 三个承重部件上。

优先级应为：

1. 删除无生产消费者的模块、只写不读的事实和无调用者管理接口；
2. 删除新旧变换体系之间的双层适配；
3. 修复公开注册但运行时必然拒绝的 Agent Operation；
4. 简化实例和会话的审批化状态机，同时保留 current；
5. 将端口级资格重复字段收敛为操作级要求；
6. 删除生产者对所有下游用途的预判；
7. 将加固 Worker、远程执行、图证据和便携导入导出迁出默认路径；
8. 最后再合并旧实验、知识和科研流程 Schema。

保守估计，在保留本地 TCAD 闭环、不可变产物、current、独立审查和执行授权的前提下，仍有约
8,000～12,000 行可从生产代码中实际删除。若将可选能力从默认安装面迁出，默认维护和加载表面还可
再减少约 5,000～8,000 行；若只是拆成可选插件而不删除，其代码仍会留在整个仓库中，不能虚报为
物理代码减少。

## 4. 第一类：可以直接删除的确定性冗余

### 4.1 产物审计快照和单事件表

涉及文件：

- `src/scidiscovery/artifact_agent/audit.py`；
- `src/scidiscovery/artifact_agent/storage/sqlite.py`；
- `src/scidiscovery/artifact_agent/storage/migrations/0001_artifacts.sql`；
- `src/scidiscovery/artifact_agent/schema/artifact.py`。

当前事实：

- `audit.py` 没有生产调用者；
- `RegistryAuditSnapshot`、原始 envelope/link/event/idempotency 读取接口只供该模块使用；
- `artifact_events` 只允许 `artifact_registered` 一种事件；
- 每个 Artifact 恰好产生一次注册事件，事件没有表达额外生命周期；
- Artifact envelope、父引用、内容地址和幂等记录已经表达同一事实。

建议：

- 删除 `audit.py`；
- 删除 `ArtifactEvent`、`artifact_events` 表、写入逻辑和原始审计快照接口；
- 保留 Artifact envelope、引用关系、内容地址存储和幂等记录。

保持不变的不变量：产物不可变、内容绑定、显式来源和幂等注册。

放弃的能力：一个当前没有生产入口的数据库原始结构自审计工具。若未来确有离线修复需要，应在独立
管理工具中按当时数据库格式重新实现，不应让其长期冻结默认存储接口。

### 4.2 只写不读的审批事件

涉及文件：`src/scidiscovery/artifact_agent/service/approvals.py`。

当前事实：

- `approval_events` 在创建、决定和过期时写入；
- 生产代码没有读取该表；
- 当前审批状态由 `approval_requests` 表维护；
- 终态决定由不可变 HumanDecision Artifact 和 `approval_decisions` 表维护。

建议删除 `approval_events` 表、写入函数和相关删除触发器。不要删除审批请求、决定、防重放 nonce、
决定尝试绑定和精确 subject 校验。

### 4.3 无生产消费者的在线清除接口

涉及符号：

- `ArtifactService.purge_registrations`；
- `SQLiteArtifactRegistry.delete_artifacts`；
- `ApprovalService.delete_requests`；
- `ExecutionService.delete_executions`。

这些接口没有生产调用者，却需要临时拆除只追加表的删除触发器，显著增加存储实现复杂度。建议从在线
服务删除；若将来需要清理废弃实例，应提供停机、显式目标、独立验证的离线维护命令。

### 4.4 无消费者 Schema 和僵尸 Worker 工具

无生产消费者的 Schema 模块：

- `schema/discovery.py`；
- `schema/decision.py`；
- `schema/pdf_excerpt.py`；
- `schema/web_evidence.py`。

`ScientificReadiness`、`ScientificObjectStatus`、`ScientificClosureStatus` 也只在自身定义文件内出现。

Worker 协议声明了 `worker_fetch_web_evidence` 和 `worker_run_analysis`，但没有已安装插件注册它们，
本地和加固 Worker 也没有相应处理器。`web_fetch.py` 因此同样没有生产调用者。

建议删除上述类型、工具声明和 `web_fetch.py`。PDF 提取是已有真实消费者的能力，不在删除范围内。

### 4.5 无消费者运行投影

`operations/spec.py` 中 `RuntimeOperationProjection` 和
`runtime_operation_projection()` 没有生产调用者。实际 Root 目录使用的是
`SchedulerOperationView`。建议删除前者，不建立第二运行目录投影。

## 5. 第二类：新旧变换体系并存

### 5.1 当前重复链路

当前确定性操作的实际调用结构是：

```text
OperationSpec
→ Operation 专用包装函数
→ 旧 profile 分发器
→ 旧 TransformOutput
→ 新 Operation 输出映射
```

具体证据：

- `plugins/tcad_artifact/tcad_artifact/operation_transforms.py::_legacy` 调用
  `TCADProjectTransformAdapter`；
- `plugins/curve_score/curve_score/operation_transforms.py::_legacy` 调用
  `CurveScoreTransformAdapter`；
- `src/scidiscovery/general_science_experiment_components.py::_run_transform` 调用
  `ScientificStateTransformAdapter`；
- InGaAs `InGaAsFig4TransformAdapter` 类没有生产调用者，但评分函数仍被新的 Operation 调用。

### 5.2 建议替换

保留适配器文件中的真实算法，把每项算法直接暴露为窄的 Operation 变换函数。删除：

- profile 分发类；
- `supports_transform_profile`；
- 旧 `required_input_parentage` 适配协议；
- 旧 `TransformOutput` 包装；
- `_legacy()` 桥接；
- 新旧输出标签之间的第二次映射。

通用运行层的 `CompiledTransformAdapter` 当前仍被 Root 调用，不能孤立删除；应在 Root 直接调用编译后
变换组件并完成输出校验时一起收敛。此次替换不删除曲线指标、TCAD 工程物化、运行鉴证或 InGaAs
评分算法。

验收要求：

- 相同输入字节产生相同输出字节；
- 相同父引用和 Operation 摘要；
- 变换重放、集合输出和冲突修订回归不退化；
- 生产源码不再出现插件级 `TransformAdapter` 或 `_legacy`。

## 6. 第三类：控制面重复治理

### 6.1 实例、会话和 current 被塞入一个 1649 行服务

`service/scheduler_bindings.py` 同时拥有：

- 研究实例；
- 实例创建提案及其审批应用；
- 会话绑定请求、候选及其审批应用；
- 语义名称绑定与修订；
- 当前科学对象选择；
- 状态观察和失败记录。

必须保留：

- 研究实例；
- 会话到实例的明确绑定；
- 语义名称到不可变对象的绑定；
- 修订号和不可覆盖历史；
- `scientific_current_select` 的比较交换语义；
- Run 完成时对递归 current 锚点的原子验证。

建议删除或降级：

- “创建实例”先生成审批对象再应用决定；
- “选择实例”先生成审批对象再应用决定；
- 两类审批的候选表、申请表、决定应用失败表和专用 UI 投影。

本地 UI 或 CLI 可直接执行显式创建和选择。科学资格审批和外部执行授权仍由 ApprovalService 精确
处理。该调整不删除 current，也不影响 checkpoint 恢复。

### 6.2 输入端口重复携带资格合同

`InputPortSpec` 当前同时携带：

- `cohort_id`；
- `approval_kind`；
- `accepted_approval_options`；
- `accepted_approval_operations`。

同一审批合同因此被复制到多个端口，随后又由编译器和 Root 路由重新聚合。建议将其替换为
Operation 级审批要求：

```text
ApprovalRequirement
- subject_ports
- approval_kind
- accepted_options
- accepted_provider_operations
```

端口只保留数据类型、数量、字节上限、可见方式、用途和是否要求 current。一个 Operation 可以声明
多个独立 ApprovalRequirement，因此不会丢失多组精确审批能力。

注意：这是字段替换，不是再增加一层资格注册表。

### 6.3 生产者预判所有下游用途

`OutputPortSpec.allowed_input_usages`、Root 的 `_operation_output_policy` 和
`_validate_producer_output_admission` 共同维护生产者对下游使用方式的预测。它要求每个输出提前声明
以后能否作为 claim evidence、prior signal、change request 等用途，形成新的流程拓扑。

更小的通用规则应是：

- 未审查输出可以交给其编译声明的独立审查者；
- 完整对象修订可以消费被要求修订的对象和精确变更请求；
- 一个需要通过独立审查才能成为结论依据的输出，必须同时绑定其精确审查结果；
- 通过上述边界后，由下游 Operation 的输入类型、用途和科学 Agent 判断其是否适用；
- `explore` 输出不能绕过审查直接晋级为科学结论。

先为当前生产 Operation 建立真实使用矩阵，再删除没有承重作用的用途组合；不能一次性移除所有独立
审查准入。

### 6.4 Effect 调用和审批请求人为断成两个公共步骤

`operation_invoke` 对 Effect 创建 ExecutionRequest，但调度器还必须额外调用
`execution_approval_request_create`，尽管审批合同已经写在同一个 OperationSpec 中。

建议 Effect Operation 调用成功后自动按其编译 ApprovalContract 创建精确审批请求并返回审查
地址。`execution_start` 仍必须在审批接受后显式调用。这样可以删除一个公共调度步骤和一段重复合同
重建逻辑，同时不把执行授权合并进聊天或 Agent 判断。

## 7. 第四类：公开目录与运行能力不一致

当前完整编译目录有三个公开 Agent Operation 声明集合输出：

- `tcad.parameter.evidence.extract.v1`；
- `science.result.diagnose.curve-error.v1`；
- `science.evidence.extract.figure.v1`。

但 `RunService.create()` 对任何 Agent 集合输出直接抛出
“minimal local Run does not yet support output collections”。因此这些能力在 public 目录可见，却在
Local 和 Hardened 运行前必然失败。

建议不扩充 Run 状态机，而先修改三项能力：

1. 参数提取 Agent 只产生一个 `ParameterEvidenceBundle`，确定性支持操作再拆分需求、参数和来源
   目录；
2. 曲线残差分析改为确定性支持操作，普通诊断 Agent 消费分析报告；图像是支持输出，不由 Agent
   集合协议管理；
3. 图证据数字化迁为可选插件，或让 Agent 产生一个单一封装包，再由确定性验证器验证和展开。

验收要求：public 目录中的每个 Agent Operation 必须至少被默认 Local backend 接受；目录不能把
永远失败的能力展示给调度 Agent。

## 8. 第五类：通用科学 Schema 中的固定流程遗留

### 8.1 当前所有权不合理

`artifact_agent/schema` 约 5245 行，混合了：

- 控制协议类型；
- 通用科研对象；
- 固定科研流程中间态；
- 确定性科学算法和验证器。

建议所有权调整为：

```text
控制核心 Schema
├── Artifact / Ref
├── Run signal / Role result
├── Approval
└── Execution

general_science 插件 Schema
├── Evidence / Foundation / Audit
├── Hypothesis / Review
├── Experiment
└── Diagnosis / Knowledge

领域插件 Schema
├── Curve
├── Device parameter
└── TCAD project/runtime
```

这会让控制核心真正不拥有科研产品模型。移动类型本身不减少仓库总行数，因此还必须配合删除以下
重复模型和算法。

### 8.2 实验意图和实验计划双模型

- `schema/experiment_intent.py`：634 行；
- `schema/experiment.py`：579 行。

两者分别表达“实验设计意图”和“物化实验计划”，大量字段一一映射，再通过复杂确定性转换产生
portfolio 和 materialization report。

第一版建议让实验设计 Agent 直接输出完整、可执行、可审查的 ExperimentPlan；确定性代码只做：

- 标识唯一性；
- 引用和变量绑定完整性；
- 资源上限；
- 领域插件需要的机械展开。

科学选择、基线、对照和验证逻辑仍由实验设计 Agent 和独立审查者判断，不由第二套意图 Schema
重新编码。

### 8.3 新旧假设模型之间存在合成转换

`artifact_agent/transforms.py::_knowledge_portfolio_view` 将当前 `HypothesisProposal` 转成旧
`HypothesisPortfolio`，并补造 parameters、support level 和 rationale，才能调用旧知识 reducer。

这说明 `KnowledgeUpdate/KnowledgeStateProjection` 链仍依赖已被替换的数据模型。建议：

- 知识更新直接消费当前 HypothesisProposal、独立审查和诊断；或
- 第一版把诊断、结论和后续动作作为不可变科学输出并由 current 选择，不维护确定性全局知识晋级
  状态。

不得继续增加第三个“通用科学图”来兼容这两套对象。

## 9. 第六类：插件边界过宽

### 9.1 曲线插件不是一个能力，而是四套产品

曲线插件约 8926 行，包含：

1. 曲线数据结构和确定性指标；
2. 曲线实验合同和诊断；
3. 论文图数字化；
4. 图证据校准、来源和验证。

图证据相关模块约三千行，是独立纵向产品，不是曲线评分内核的必要组成。建议拆成：

```text
curve_core
├── CurveBundle
├── comparison contract
└── deterministic metrics

figure_evidence（可选）
├── digitization
├── calibration/provenance
└── deterministic validation
```

`curve_score/schema.py` 的 1667 行中，约一半是 Pydantic 数据模型，另一半是指标算法。应把算法移至
metrics/evaluation 模块，并删除 `unspecified_legacy` 分支；拆文件本身不计为裁剪成果。

### 9.2 TCAD 插件依赖完整曲线插件

TCAD 插件声明依赖 `curve_score`，只是为了消费曲线合同和归一化能力，却连带安装曲线科学 Agent 和
图证据产品。应让 TCAD 只依赖小型 `curve_core`，不要依赖完整曲线科研插件。

### 9.3 TCAD 插件同时拥有多个可独立演进的子产品

TCAD 插件约 13085 行，包含：

- 器件参数研究；
- Deck 编写、修订和审查；
- 工程物化和运行鉴证；
- 本地开发调试；
- 套接字执行守护进程；
- 命令执行适配器；
- SSH 传输和 Python 3.6 远端 Runner；
- 曲线归一化。

推荐默认安装只包含本地闭环需要的 TCAD 核心、一个执行后端和必要归一化器。远程 transport 作为
独立可选插件注册。器件参数研究也可作为 TCAD 科研能力子插件，不应成为每个只想编写和执行 Deck
的用户的强制依赖。

### 9.4 通用 Schema 和文件工具被重复注册

TCAD 已依赖 `general_science`，却重新生成并注册 ExperimentPortfolio、ScientificReview、
ScientificFoundation 和 EvidenceAudit Schema。曲线插件也重新注册通用实验和研究目标 Schema。

Builtin 当前只公开三项分块写入工具；通用科研插件公开补丁和 PDF 工具；TCAD 又从控制包内部 Python
路径重新注册 JSON patch、delete 和 move 工具。

建议：

- Builtin 一次性拥有全部通用文件工具；
- 通用科研插件拥有 PDF 等通用科研读取工具；
- 领域插件只通过公开 `ComponentRef(plugin_id=...)` 引用；
- 领域插件不得引用控制包私有实现路径重新注册同一工具；
- 已依赖 general_science 的插件直接引用其公开 Schema 资源，不重新生成相同 `$id` 的副本。

## 10. 第七类：执行和 Worker 可选后端常驻

### 10.1 TCAD 存在两套执行传输栈

套接字栈：

- `execution_control.py`；
- `worker.py`；
- `execution_adapter.py`；
- `execution_daemon.py`；
- `execution_mcp.py`。

命令和远程栈：

- `command_adapter.py`；
- `ssh_transport.py`；
- `remote_runner_py36.py`。

两套都实现 capabilities、prepare、submit、status、cancel、collect，并重复描述符校验、能力快照和
执行状态处理。第一版应只保留真实本地闭环使用的一套；另一套迁为可选远程执行插件。

`project_packager.py` 的 `ProjectResourceLimits/ProjectExpectedOutput` 与
`execution_control.py` 的 `ResourceLimits/ExpectedOutput` 字段几乎相同，也应共享一份领域执行合同，
在工程合同到 JobSpec 的边界只做显式转换。

### 10.2 开发调试又包装了一次执行生命周期

`debug_adapter.py` 自己实现 prepare、submit、status、cancel、collect，并维护 submission binding。
开发调试的资源上限和输出诊断有真实价值，但它应是同一 TCAD adapter 的开发模式，而不是第三套
生命周期。

### 10.3 Hardened Worker 对当前公开 Agent 为零覆盖

当前完整目录有 22 个 public Agent Operation。HardenedWorkerBackend 对这 22 个全部报告不支持，
原因包括原生 shell、view_image、缺少服务端文件创建工具或 Agent 集合输出。

加固后端、加固 MCP、文件代理和共享编辑辅助代码约 1600～2000 行。建议第一版：

- 默认仅保留 LocalTrustedBackend；
- 将 Hardened 后端移出默认安装和默认运行时分支；
- 保留其设计和测试证据；
- 至少有一个真实端到端 Agent Operation 可运行后，再以独立可选后端恢复。

这不改变当前事实：Local 模式对 Codex 原生工具只有提示约束，不是强文件系统沙箱，不能携带生产
凭证或执行不可逆副作用。

### 10.4 便携包属于管理功能

`portable_bundle.py` 有真实 CLI 消费者，不能归类为死代码。但它依赖 CAS、Artifact 数据库、
Scheduler binding 和 current 的内部布局，约 590 行。建议移至独立管理包或可选命令扩展，不在每次
普通 `scid` 启动时加载。

## 11. 大文件逐项判定

| 文件 | 行数 | 判定 | 推荐动作 |
|---|---:|---|---|
| `tcad/project_packager.py` | 1848 | 大部分是真实 TCAD 合同和打包逻辑，夹杂重复模型与历史格式 | 先删历史分支和重复合同，再按工程、审查、运行鉴证拆分 |
| `curve/schema.py` | 1667 | Schema、领域策略和指标算法混合 | 模型与算法分离，删除 legacy；不要删除真实指标 |
| `scheduler_bindings.py` | 1649 | 高设计冗余 | 保留实例、绑定、修订、current；删除实例/会话审批状态机 |
| `approvals.py` | 1291 | 核心安全合同有价值，事件和清除冗余 | 删除只写事件和在线清除，保留精确 subject、防重放和决定事实 |
| `mcp_root_operation_routes.py` | 1231 | 高设计冗余 | 收敛端口资格、下游用途和 Effect 审批断点 |
| `tcad/parameter_operations.py` | 1203 | 声明、资格判定、审批渲染混合，且主 Agent 当前不可运行 | 单一参数 bundle、确定性拆分；projector 只投影不重做整个资格器 |
| `tcad/transform_adapter.py` | 1152 | 新旧双层 | 保留算法，删除 adapter/profile/旧输出包装 |
| `curve/analysis.py` | 989 | 大部分是真实确定性分析和绘图 | 改成 Transform；从不可运行的 Agent 集合工具路径移出 |
| `curve/science_operations.py` | 983 | 重复声明和专用诊断链过重 | 复用声明构造器，普通诊断消费确定性分析报告 |
| `tcad/execution_control.py` | 976 | 与命令/远程栈存在重复 | 默认只保留一套执行 transport |
| `runs.py` | 919 | 承重模块，四状态单权威 | 不作为大砍目标；只做局部职责整理 |
| `storage/sqlite.py` | 897 | 核心存储有价值，审计快照和清除冗余 | 删除事件、原始审计和在线删除 |
| `figure_evidence_validation.py` | 893 | 真实图证据质量能力 | 迁到可选图证据插件，不用文件大小判断删除 |
| `remote_runner_py36.py` | 828 | 远端兼容产品 | 随远程 transport 迁为可选插件 |
| `device_parameters.py` | 814 | Schema 与覆盖算法混合 | 类型与算法分离；保留 TCAD 参数科学能力 |
| `platforms/codex.py` | 797 | 生成和验证重复编码同一配置合同 | 从同一纯渲染结果生成与比较，删除手写双份判断 |
| `tcad/debug_adapter.py` | 729 | 真实调试能力加重复执行包装 | 合并为 TCAD adapter 的开发模式 |
| `local_workspace.py` | 727 | 工作区、封存、恢复承重；服务端编辑偏可选 | 保留本地核心，将 Hardened 文件代理迁出 |
| `curve/transform_adapter.py` | 727 | 新旧双层 | 保留算法，删除 adapter/profile |
| `approval_ui/app.py` | 693 | HTTP 安全和渲染有价值，实例审批流程使其膨胀 | 删除实例/会话审批页面路径，保留通用 ReviewDocument 渲染 |
| `tcad/plugin.py` | 658 | 大量重复 Operation 声明和通用资源副本 | 引用公共组件，增加小型声明构造器，不增加新 DSL |
| `tcad/operation_workspace.py` | 654 | TCAD 工作区和无效草稿恢复有价值 | 保留；删除历史 v1 后再按物化/文件策略/终结拆分 |
| `experiment_intent.py` | 634 | 与 ExperimentPlan 重复 | 合并为一个可执行实验计划合同 |
| `tcad/project_materializer.py` | 627 | 真实确定性 TCAD 物化 | 保留，和 packager 明确边界 |
| `executions.py` | 611 | 外部副作用生命周期承重 | 保留；删除无消费者 purge |
| `curve/operation_transforms.py` | 598 | 声明重复且桥接旧 adapter | 直接调用算法并复用通用声明构造器 |
| `portable_bundle.py` | 590 | 有消费者但非默认核心 | 迁为管理扩展 |
| `figure_evidence.py` | 580 | 真实可选领域合同 | 迁到图证据插件 |
| `experiment.py` | 579 | 与 intent 双模型 | 与实验意图合并 |
| `figure_evidence_normalizer.py` | 546 | 真实可选领域算法 | 迁到图证据插件 |
| `general_science_agent_operations.py` | 545 | 多角色机制有价值，声明重复 | 保留角色，复用端口和 executor 构造器 |
| `mcp_root.py` | 540 | 根工具面偏宽，路由本身简单 | 随实例审批和 Effect 断点删除减少工具数量 |
| `mcp_root_execution_routes.py` | 501 | 真实外部执行能力，审批合同重复重建 | Effect invoke 自动创建审批，删除额外公共步骤 |
| `ssh_transport.py` | 495 | 可选远程能力 | 随远程执行插件迁出默认路径 |
| `curve_normalizer.py` | 481 | 有真实归一化，约一半是历史 CSV 分支 | 冻结当前格式后删除 legacy parser |
| `knowledge.py` | 472 | 旧知识 reducer 和状态投影 | 直接消费当前对象或由 current 管理结论 |
| `figure_science_operations.py` | 462 | 可选纵向图证据 Agent 产品 | 随图证据插件迁出；先解决 Agent 集合不可运行 |
| `tcad/operation_transforms.py` | 442 | 新包装旧 adapter | 直接变换后会自然缩小 |
| `audit.py` | 437 | 无生产消费者 | 删除 |
| `operations/spec.py` | 430 | 核心原子有价值，字段承担过多下游治理 | 删除死投影，收敛端口资格字段 |
| `general_science_components.py` | 416 | 真实通用角色组件加重复资源注册 | 统一 builtin 工具和通用 Schema 所有权 |
| `operations/invoke.py` | 407 | 预检核心有价值，旧 adapter 形状残留 | Root 直接调用编译变换后删除旧适配协议 |

## 12. 建议实施顺序与阶段门

### 阶段一：零产品争议删除

- 删除无消费者 Schema、web 工具、audit 和 runtime projection；
- 删除只写 approval event；
- 删除在线 purge；
- 运行 Artifact、Approval、Execution、目录编译和 clean-wheel 回归。

通过条件：行为不变，生产文件和数据库表实际减少，没有用新兼容层补回。

### 阶段二：关闭不可运行公开能力

- 参数提取改为单一 bundle；
- 曲线分析改为确定性 Transform；
- 图证据能力迁为可选或改成单包；
- public Agent Operation 在 Local backend 下全部可启动。

通过条件：目录能力与运行能力一致，调度器不会选中必然失败的操作。

### 阶段三：删除迁移双层和重复注册

- 删除 TCAD、曲线、通用科学旧 TransformAdapter；
- builtin 统一通用文件工具；
- 插件引用公共 Schema 资源；
- 引入很小的 Python 声明构造器，禁止建立第二 DSL 或第二注册表。

通过条件：一个新小领域插件只需一个入口、少量组件和 Operation 声明，不引用控制包私有路径。

### 阶段四：简化控制面

- 删除实例创建和会话选择审批状态机；
- 保留 current 和递归 current 检查；
- 端口资格字段替换为 Operation 级要求；
- 删除生产者预判下游用途；
- Effect invoke 自动创建精确审批请求。

通过条件：Artifact、Run、current、Approval、Execution 各只有一个权威；独立审查和人工审批负例仍
失败关闭。

### 阶段五：收窄默认插件产品面

- TCAD 只保留一个默认执行后端；
- 远程执行、Hardened Worker、图证据和 portable bundle 迁为可选模块；
- TCAD 依赖 curve_core，不依赖完整 curve_score；
- 实验意图/计划和旧知识状态最后合并。

通过条件：默认本地 TCAD 闭环和多角色科研链完整通过；可选模块缺失时目录中不出现相应能力。

## 13. 不应误删的承重部分

本次评估明确不建议为了行数直接删除：

- `RunService` 的 queued/running/completed/failed 四状态；
- Run 截止时间、失败记录、恢复草稿和封存输出；
- current 的唯一权威、比较交换和 Run 完成原子检查；
- Artifact 内容寻址、不可变 envelope、父引用和幂等注册；
- 人工审批的精确 subjects、决定绑定、防重放和 UI 安全；
- Execution 的授权后提交、状态同步、未知提交查回和输出收集；
- TCAD 工程物化、独立 Deck 审查、调试诊断和求解结果鉴证；
- 曲线确定性指标和图证据校准中的真实科学算法。

这些模块可以在删除外围责任后重新拆分，但机械拆文件不算复杂度减少。

## 14. 回滚与验证原则

每个候选应单独实施，不得把多类删除混在一次不可审查的大提交中。每项至少满足：

1. 删除前列出生产消费者、动态插件消费者、测试消费者和文档消费者；
2. 删除后运行最小相关测试和安装态目录编译；
3. 对 Artifact、current、独立审查、审批和外部执行运行目标负例；
4. 比较生产文件数、行数、数据库表、公开 Root 工具和 public Operation 数；
5. 不以新增兼容层、迁移适配器或第二注册表抵消删除；
6. 独立审查同时判断实现正确性、33 项约束和通用科研 Agent 目标是否退化；
7. 回滚边界应是一个候选一个提交，不回滚其他并行工作树修改。

本文只证明当前代码中存在上述简化机会，不授权自动实施，也不宣称当前端到端科学效果已经通过。
