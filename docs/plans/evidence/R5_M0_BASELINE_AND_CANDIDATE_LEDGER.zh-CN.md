# R5-M0 基线与候选账本

日期：2026-09-01

状态：独立设计审查通过，仅放行 M1；审查时未修改生产代码

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 证据边界

本账本冻结的是当前未提交工作树，而不是 `HEAD` 的历史版本：

- 分支：`baseline/8765-codex`；
- `HEAD`：`404aeb14c6ebc4b08bac599db91eaee54c103f48`；
- 当前 L 系列实现仍包含大量已修改和未跟踪文件，不能用 `git diff HEAD` 单独代表运行候选；
- 生产源码以 `src/scidiscovery/**/*.py` 与 `plugins/**/*.py` 的排序内容摘要为准；
- 本阶段只新增计划和证据文档，没有修改 `src/`、`plugins/`、部署代码、数据库或运行状态。

可复算生产树摘要命令：

```bash
find src/scidiscovery plugins -type f -name '*.py' \
  -not -path '*/__pycache__/*' -print0 \
  | sort -z | xargs -0 sha256sum | sha256sum
```

结果：

```text
fc97aa3277e0e9a5144049f95e806b1eb5ad95cd7156069ebcc68162cded6c41
```

该摘要只绑定生产 Python 内容和路径。计划、审查报告和测试变化另行由工作树状态与阶段证据绑定。

## 2. 生产规模基线

| 范围 | Python 文件 | 物理行数 |
|---|---:|---:|
| `src/scidiscovery` | 101 | 27,260 |
| `plugins` | 45 | 22,763 |
| 合计 | 146 | 50,023 |

当前体积最大的责任集中在：TCAD 工程打包、曲线 Schema、scheduler binding、审批、Root Operation
路由、参数操作、旧 TransformAdapter、Operation 编译、TCAD 执行控制、Run 和图证据验证。文件大小
只用于寻找审计入口，不构成删除结论。

## 3. 唯一目录和插件基线

从 builtin、general_science、curve_score、tcad_artifact、ingaas_fig4 五个当前插件定义，经同一个
`compile_catalog()` 编译：

| 指标 | 当前值 |
|---|---:|
| 插件定义 | 5 |
| 已注册组件 | 220 |
| Operation | 46 |
| public | 26 |
| support | 20 |
| Agent | 22 |
| Transform | 20 |
| Approval | 3 |
| Effect | 1 |

插件组件/Operation 数：

| 插件 | 组件 | Operation |
|---|---:|---:|
| builtin | 3 | 0 |
| general_science | 63 | 15 |
| curve_score | 58 | 11 |
| tcad_artifact | 87 | 19 |
| ingaas_fig4 | 9 | 1 |

完整目录摘要：

```text
4c17c856ba4249d400d8d1455139b2e39588759e16ee1c31e5122b4e97dbb57e
```

该结果证明当前仍是一个入口、一个编译目录；组件多不等于注册表多，但重复组件会增加插件接入和
合同维护成本。

## 4. 后端能力基线

### 4.1 LocalTrustedBackend

22 个公开 Agent 中 19 个可启动，3 个在 Run 创建前因 `agent_collection_outputs` 失败关闭：

- `tcad.parameter.evidence.extract.v1`；
- `science.result.diagnose.curve-error.v1`；
- `science.evidence.extract.figure.v1`。

这不是安全绕过：目录和 preflight 会报告不可用。但它仍是产品表面问题，因为默认公开目录包含三个
默认 Local 永远不能执行的科学行为。

### 4.2 HardenedWorkerBackend

22 个公开 Agent 当前支持数为 0：

- 大多数声明 `native_shell=inherited_prototype`；
- 图像相关操作还声明 `view_image`；
- 上述三项另有 Agent 集合输出；
- Hardened v1 只允许纯 MCP、服务端文件工具完备的 Operation。

这证明 Hardened 不是当前公开科研 Agent 的默认后端，但不能据此删除它：L5 已有盲 CSV 纯 MCP
Operation 的真实消费者和恢复/围栏测试。M5 只能将其惰性加载或可选安装。

## 5. Root 和持久化事实基线

### 5.1 Root 公共工具

当前 Local/Hardened 共用 30 个 Root 工具：

```text
instance_prepare instance_status instance_select instance_current
instance_list instance_close
scientific_inventory scientific_current scientific_current_select lifecycle_events
artifact_ingest_file artifact_catalog
operation_catalog operation_preflight operation_invoke
run_list run_status run_record_failure
approval_list approval_status
execution_capabilities execution_capability_bind execution_approval_request_create
execution_abandon execution_cancel execution_list execution_status execution_outputs
execution_start execution_sync
```

M6 的目标不是追求固定数量，而是删除实例审批化和 Effect 审批断点后不再有生产消费者的入口。

### 5.2 新建本地运行时数据库

使用当前完整目录和一次性临时状态目录真实初始化，临时目录退出后删除；冻结结果写在本文件：

| 数据库 | 表 |
|---|---|
| artifact_agent | `artifact_envelopes`、`artifact_events`、`artifact_links`、`idempotency_records` |
| scheduler-bindings | `scheduler_bindings`、`scheduler_instance_proposals`、`scheduler_instances`、`scheduler_observations`、`scheduler_scientific_selections`、`scheduler_session_binding_candidates`、`scheduler_session_binding_requests`、`scheduler_sessions` |
| runs | `run_activity`、`runs` |
| approvals | `approval_decisions`、`approval_events`、`approval_requests`、`decision_attempts`、`used_nonces` |
| executions | `executions` |
| Hardened 私有 dispatch | `active_transport` |

合计 21 张通用/后端表。显式启用 TCAD socket 执行产品还会增加插件自有 `submissions` 表。

M1 预期只减少 `artifact_events` 和 `approval_events`；M6 只有完成行为替换后才能减少实例提案和会话
候选表。`runs`、Artifact、current、审批决定、Execution 与 Hardened 私有 transport 不在直接删除
范围。

## 6. 测试和安装基线

在 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2`、无 pytest 并行下执行：

```text
python -m pytest -q
200 passed in 79.98s
```

该集合包含当前 clean-wheel、插件组合、目录编译、Local/Hardened、Run/current、审批、Effect、部署
回滚、通用 Agent 与 TCAD 本地闭环的自动化证据；它不等于真实浏览器、远程求解器或科学准确率
资格。

以下检查也通过：

```text
bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh

git diff --check
```

## 7. M1 候选：零消费者和重复日志

### M1-01：无生产消费者 Schema 与科研周期状态

- **表面**：`schema/discovery.py`、`schema/decision.py`、`schema/pdf_excerpt.py`、
  `schema/web_evidence.py`；`ScientificReadiness`、`ScientificObjectStatus`、
  `ScientificClosureStatus`。
- **消费者**：前四个模块没有生产、动态入口或当前运行消费者；科研周期状态只有自身定义和
  `test_l6_domain_neutral_core.py` 的领域中性测试。
- **处置**：删除；将领域中性测试改为使用真实当前对象，而不是保留无消费者类型。
- **保留不变量**：外部证据冻结、PDF 工具、当前目录和科学调度均由其他当前实现承担。
- **放弃行为**：旧 Python 导入和旧科研闭环 Schema。
- **验证**：Schema 导入负例、当前通用/领域目录编译、证据/PDF 聚焦测试。
- **风险/回滚**：低；每个模块可单独回退。

### M1-02：僵尸网页与分析 Worker 工具

- **表面**：`worker_fetch_web_evidence`、`worker_run_analysis`、`web_fetch.py`。
- **消费者**：协议声明存在；已安装 builtin/general/curve/TCAD 没有注册两个工具，本地和 Hardened
  router 没有对应处理器。测试 entry-point 夹具
  `architecture_operation_test_plugin/plugin.py` 导入 `RUN_ANALYSIS_TOOL` 后只赋给未注册变量，未进入
  `PluginDefinition.components` 或任何 Operation，属于测试夹具的无效导入而非运行消费者。当前科学
  论文资格文档仍提到旧 analysis 路径，属于需同步的陈旧说明。
- **处置**：删除声明、组件常量和无消费者模块；修正当前文档，不能把旧历史审计改写为当前通过。
- **保留不变量**：网络默认拒绝、已注册 PDF/图像/领域工具和来源冻结。
- **放弃行为**：无法实际调用的协议名称。
- **验证**：Worker 工具投影、网络策略负例、clean-wheel 目录。
- **风险/回滚**：低；若 M0 审查发现动态插件真实引用，整项撤回。

### M1-03：测试专用运行投影

- **表面**：`RuntimeOperationProjection`、`runtime_operation_projection()`、
  `CompiledCatalog.runtime_projection()`。
- **消费者**：生产只定义和导出；实际 Root/调度使用 `CompiledOperation` 与
  `SchedulerOperationView`。四个 L1/L5 测试消费该投影。
- **处置**：删除并让测试直接验证唯一编译 Operation 的可选策略；不创建替代运行投影。
- **保留不变量**：一个目录、一个摘要、一个 preflight/invoke。
- **放弃行为**：测试便利 API。
- **验证**：目录摘要、策略按 Operation 启用、平台 profile、preflight/invoke。
- **风险/回滚**：低。

### M1-04：无调用者在线清除

- **表面**：`purge_registrations`、`delete_artifacts`、`delete_requests`、
  `delete_executions`。
- **消费者**：仅方法间自调用；无 Root、CLI、部署、插件或测试产品入口。
- **处置**：删除，不预建离线清理器。
- **保留不变量**：只追加 Artifact/审批/执行事实更清晰。
- **放弃行为**：未公开的在线删除能力。
- **验证**：Artifact、Approval、Execution 创建/读取/幂等与只追加负例。
- **风险/回滚**：低。

### M1-05：重复事件与离线完整性检查

- **表面**：`artifact_events`、`approval_events`、`audit.py`、原始审计 snapshot。
- **消费者**：事件只有写入和 audit 原始读取；approval event 没有读取者；`audit.py` 无在线入口，
  但实际校验 CAS、Envelope、父链、幂等记录和孤儿内容。
- **处置**：删除两个事件表及写入；缩小或迁移离线 audit，不能整体删除完整性校验。
- **保留不变量**：IMM-001、显式来源、内容寻址和幂等注册。
- **放弃行为**：一 Artifact 一注册事件和审批状态变化的重复日志。
- **验证**：新数据库表清单；人工损坏 CAS/Envelope/父链/幂等记录的离线检测；审批决定和
  HumanDecision Artifact 精确性。
- **风险/回滚**：中；事件删除和 audit 缩小必须是两个独立提交。

## 8. M2 候选：公开能力与后端能力

### M2-01：TCAD 参数证据集合输出

- **表面**：`tcad.parameter.evidence.extract.v1` 和 `parameter_operations.py` 三个集合输出。
- **消费者**：真实插件目录、参数提取/审计/资格链和安装测试；默认 Local 在 Run 创建前拒绝。
- **处置**：行为替换，不是删除。Agent 输出一个领域数据包，确定性 support Operation 验证并展开。
- **保留不变量**：参数未知量、来源、缺口和不确定性由 Agent 决定；机械展开由版本化程序完成。
- **放弃行为**：Agent 直接提交多集合。
- **验证**：真实参数 Agent、来源/audit/qualification、集合 Transform 重放、TCAD author 消费。
- **风险/回滚**：高；独立子提交。

### M2-02：曲线分析集合输出

- **表面**：`science.result.diagnose.curve-error.v1`、`analysis.py`、worker tool 和图集合。
- **消费者**：曲线诊断真实插件和测试；默认 Local 拒绝。
- **处置**：确定性分析/绘图成为 support Transform；普通诊断 Agent 消费单一报告。
- **保留不变量**：Metric 与科学诊断分离，图表有父链。
- **放弃行为**：诊断 Agent 同时拥有分析执行和多集合提交。
- **验证**：曲线指标、残差区间、图像字节/父链、真实诊断 Agent。
- **风险/回滚**：高。

### M2-03：论文图证据集合输出

- **表面**：`science.evidence.extract.figure.v1` 及 figure 纵向产品。
- **消费者**：curve_score 默认插件、TCAD 对完整 curve_score 的间接依赖和图证据专项测试；TCAD
  本地 Deck 闭环不依赖该 Agent 启动。
- **处置**：优先迁为可选插件；若保留 Agent，则单一清单包加确定性验证/展开。
- **保留不变量**：校准、图例身份、来源、不确定性和失败关闭验证。
- **放弃行为**：默认 TCAD 安装自动携带图证据 Agent。
- **验证**：图证据专项、缺插件目录、curve/TCAD 安装组合。
- **风险/回滚**：中高。

## 9. M3 候选：旧 TransformAdapter 双层

### M3-01：领域旧 adapter/profile 桥

- **表面**：`TCADProjectTransformAdapter`、`CurveScoreTransformAdapter`、
  `ScientificStateTransformAdapter`、`InGaAsFig4TransformAdapter`、`_legacy()` 和旧
  `TransformOutput` 包装。
- **消费者**：TCAD/曲线/通用 Operation 包装函数仍在生产调用前三个；InGaAs 旧类无生产调用，
  其评分函数由新 Operation 使用；通用 `CompiledTransformAdapter` 仍被 Root 使用。
- **处置**：折叠而非直接删除。算法成为窄注册函数；保留一个通用编译 Transform 调用器。
- **保留不变量**：DET-001/002、相同父链、可重放字节和领域所有权。
- **放弃行为**：profile 分发、旧 adapter 导出、双重输出映射。
- **验证**：每个生产 Transform 的冻结输入字节等价矩阵。
- **风险/回滚**：高；TCAD、曲线、通用、InGaAs 分四个提交。

## 10. M4 候选：科学语义兼容桥

### M4-01：旧知识 portfolio 合成

- **表面**：`_knowledge_portfolio_view`、旧 `HypothesisPortfolio` 到知识 reducer 的桥。
- **消费者**：当前 knowledge transform 真实调用；桥补造空 parameters、合成 rationale、
  `testable/unassessed` 等科学字段。
- **处置**：知识更新直接消费当前 Proposal、独立审查和诊断；无消费者时删除全局 reducer。
- **保留不变量**：Worker 拥有科学内容，控制/Transform 不补科学判断。
- **放弃行为**：旧知识状态对旧 HypothesisPortfolio 的兼容。
- **验证**：假设—审查—诊断—知识/current 正负链；无默认支持状态。
- **风险/回滚**：高。

### M4-02：实验意图与计划

- **表面**：`experiment_intent.py` 与 `experiment.py`。
- **消费者**：不是死代码；ExperimentPortfolio 被 TCAD、曲线、盲表插件、打包和物化广泛消费；
  ExperimentDesignIntent 被通用实验设计 Operation 和确定性 materializer 消费。
- **处置**：M4 只做字段所有权审计。证据未证明可整体合并，因此当前分类为“不修改”；只在净减少
  且不让 Agent 手工机械展开时抽取共享类型或删除重复字段。
- **保留不变量**：Agent 科学选择与确定性案例展开分离。
- **放弃行为**：无预设放弃。
- **验证**：实验设计、对照辨识、TCAD/曲线消费者和重放。
- **风险/回滚**：高；允许以不改代码结束。

## 11. M5 候选：插件和可选产品面

### M5-01：通用资源和文件工具重复注册

- **表面**：TCAD/curve 重复的通用 Schema、codec、文件 patch/delete/move 组件。
- **消费者**：真实 Operation 使用，但同一合同由多个插件重新生成或从控制包私有路径注册。
- **处置**：折叠到 builtin/general_science 公共组件，领域插件只用显式跨插件引用。
- **保留不变量**：每个 Operation 仍显式授权工具；公共注册不自动扩权。
- **放弃行为**：领域插件可独立复制通用组件的内部便利。
- **验证**：五插件安装组合、组件摘要、精确工具白名单、盲插件接入。
- **风险/回滚**：中。

### M5-02：curve 核心与图证据纵向产品

- **表面**：curve_score 同时拥有合同/Metric、诊断、数字化和图证据验证；TCAD 依赖完整 curve_score。
- **消费者**：曲线核心与图证据均有真实消费者，但默认 TCAD 只需前者。
- **处置**：归位/可选化；仅当新增插件胶水小于默认依赖减量时拆分。
- **保留不变量**：只有一个插件入口组和一个编译目录，图证据科学算法不删除。
- **放弃行为**：安装 curve 核心自动得到完整图证据产品。
- **验证**：core/general/curve/figure/TCAD 组合和图证据专项。
- **风险/回滚**：中高。

### M5-03：TCAD 多执行 transport 与调试包装

- **表面**：socket daemon/MCP、command adapter、SSH/Python 3.6 runner、debug adapter。
- **消费者**：均有生产配置、部署或运行插件消费者，不是死代码；runtime plugin 当前按配置在 socket
  adapter 与 command adapter 间选择，SSH 有独立安装脚本。
- **处置**：可选化，不直接删除。默认只加载本地闭环选定的一套；其他 transport 独立安装。调试
  复用同一 adapter 生命周期。
- **保留不变量**：Effect 幂等、未知提交查回、远端配置和输出收集。
- **放弃行为**：默认 TCAD wheel/启动无条件加载所有 transport。
- **验证**：本地闭环、socket/command/SSH 各自专项和缺可选 transport 负例。
- **风险/回滚**：高。

### M5-04：Hardened 与 portable bundle 默认加载

- **表面**：`runtime.py` 顶层导入 Hardened；CLI 顶层导入 `portable_bundle`。
- **消费者**：Hardened 有真实纯 MCP 测试消费者；portable bundle 有真实 CLI 命令消费者。
- **处置**：惰性导入或可选安装，不删除能力。
- **保留不变量**：Hardened 安全边界和便携数据完整性。
- **放弃行为**：普通 Local/普通 CLI 启动自动加载这些模块。
- **验证**：模块加载探针、Local/Hardened、portable CLI、clean wheel。
- **风险/回滚**：中。

## 12. M6 候选：重复治理

### M6-01：实例/会话审批化状态机

- **表面**：`scheduler_instance_proposals`、`scheduler_session_binding_requests/candidates`、相关
  Root/UI 路由；`scheduler_bindings.py` 同时承载实例、绑定、修订和 current。
- **消费者**：当前 Root 和 loopback UI 真实消费，不能当死代码删。
- **处置**：行为替换。UI 直接执行显式创建/选择；保留实例、会话绑定、修订、current CAS。
- **保留不变量**：调度 Agent/聊天/Worker 无权切换实例；current 和 checkpoint 唯一。
- **放弃行为**：把实例管理伪装成科学 Approval 的多阶段申请。
- **验证**：未绑定、创建、选择、重启、并发 CAS、聊天不能决定、scientific approval 不受影响。
- **风险/回滚**：高。

### M6-02：端口级资格合同重复

- **表面**：每个 `InputPortSpec` 的 cohort、approval kind/options/providers 四字段，以及编译/Root
  再聚合。
- **消费者**：通用实验、假设、TCAD 参数和 Deck 输入真实使用；是重复合同，不是死字段。
- **处置**：折叠为 Operation 级不可变输入准入值，支持多组精确 subject ports；不建表/注册表。
- **保留不变量**：完整 cohort、精确 provider/option、revision 不继承资格。
- **放弃行为**：每个端口重复写同一审批合同。
- **验证**：混合 cohort、部分审批、错误 provider/option、编译漂移与 TCAD 参数门。
- **风险/回滚**：高。

### M6-03：生产者下游用途预测

- **表面**：`allowed_input_usages`、编译器检查、Root producer admission。
- **消费者**：全体生产 Operation 和审查/修订准入真实使用，不能直接删除。
- **处置**：先冻结真实使用矩阵，再由下游输入、review edge、direct revision 和可选资格表达；禁止
  新建全局用途图。
- **保留不变量**：未审查输出不能成为需审查的 claim evidence；精确 reviewer/revision 继续可达。
- **放弃行为**：生产者预测所有未来消费者。
- **验证**：所有生产边、绝对断路、审查绕过、修订和非 TCAD 盲插件。
- **风险/回滚**：最高；最后实施。

### M6-04：Effect 审批公共断点

- **表面**：`operation_invoke` 创建 Execution 后，调度器还要调用
  `execution_approval_request_create`；执行路由重新构造同一编译合同。
- **消费者**：Root、scheduler 提示、Effect 和部署测试真实使用。
- **处置**：invoke 只自动创建精确审批请求并返回 UI 地址；用户决定和 `execution_start` 仍分离。
- **保留不变量**：HIL-001/002、CQRS、合同漂移、未知提交和显式 start。
- **放弃行为**：调度器手工重建审批请求的额外公共步骤。
- **验证**：聊天确认无效、错误 subject/revision/插件卸载/合同漂移、批准前 start 拒绝、拒绝后拒绝。
- **风险/回滚**：高。

## 13. 文档所有权

| 文档 | 角色 | M0 处置 |
|---|---|---|
| `docs/ARCHITECTURE*.md`、设计宪章、33 项 YAML | 当前规范 | 保持，不因 M0 改写 |
| `R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` | 已完成历史计划与实施记录 | 保持历史通过结论 |
| `CURRENT_PRODUCTION_CODE_REDUNDANCY_ASSESSMENT.zh-CN.md` | 当前工作树只读审计 | 保持，不能作为实施授权 |
| `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` | 活动提案 | M0 审查后才可放行 M1 |
| 本文件 | M0 当前审查候选证据 | 绑定本节摘要和命令结果 |
| 旧 R0—R5 审查 | 历史证据 | 不继承 verdict，不重写 |

当前科学论文资格说明仍引用已经没有注册/处理器的 `worker_run_analysis`，若 M1-02 通过，应将当前说明
改为真实现行图证据插件/工具路径；历史报告原文保留。

## 14. M0 结论候选

M0 已完成计划要求的基线、能力矩阵、消费者分类、保护不变量、放弃行为、验证和回滚边界。结论为：

1. M1-01—04 是高置信度删除候选；
2. M1-05 只能“删事件、保留审计”，不能整体删除 `audit.py`；
3. M2/M3/M4-01/M6 是真实行为替换，必须逐项实施，不能伪装成死代码删除；
4. M4-02 当前证据不支持整体合并实验意图和计划；
5. M5 的真实能力只可归位或退出默认加载，不能用默认消费者少作为物理删除依据；
6. M0 没有新增运行实体、注册表、状态或兼容层；
7. 账本共 19 个候选：M1 五项、M2 三项、M3 一项、M4 两项、M5 四项、M6 四项；
8. 独立审查结论为 PASS，仅放行 M1。报告见
   `../reviews/R5_M0_BASELINE_AND_CANDIDATE_LEDGER_INDEPENDENT_REVIEW.zh-CN.md`；M2—M7 未放行。
