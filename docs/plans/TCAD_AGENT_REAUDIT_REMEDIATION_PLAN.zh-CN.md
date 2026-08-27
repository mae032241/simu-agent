# SciDiscovery Agent 新版本复审整改计划（修订版）

## 1. 目标

本计划把 [第二轮复审报告](../TCAD_AGENT_REAUDIT.zh-CN.md) 中确认有效的发现，
以及对初版计划的复核意见，转化为可执行的整改任务。目标不是继续增加控制层复杂度，
而是优先保证：

1. 科学判定不会因单位、状态投影或未经审查的输入而产生错误结论。
2. TCAD 求解器语义、工程实现和执行请求之间具有明确、可机读的合同。
3. 通用框架能够表达多案例研究和 SProcess 到 SDevice 的文件依赖。
4. 安装、升级和工作区初始化具备可验证的失败恢复与路径安全性。
5. 下游工作只在其依赖门槛通过后接入；互不依赖的科学正确性、执行合同和部署工作
   可以并行。

本文只规划工程整改，不改变当前 Fig.4 科学结论，也不授权新的 TCAD 作业。

## 2. 已确认事实与优先级校准

### P0：可能绕过科学审查或产生错误科学结论

- 数值阈值比较没有执行单位一致性检查或换算。
- `layered_diagnosis.claim_allowed=true` 没有正确投影到 readiness。
- 本地 `TCADExecutorAdapter` 仍接受未经 deck review 的裸 `tcad.job-spec.v1`。
- 求解器类型依赖 profile 名称字符串推断，而不是显式 capability。

### P1：通用科学闭环能力缺失

- 控制等价性只有库函数，没有可调度的确定性 transform。
- 多案例实验缺少类型化的执行计划和逐案例结果绑定。
- 文本型 `DeckFile` 无法引用二进制 TDR，不能完整表达 SProcess 到 SDevice
  的输入依赖。
- runtime assertion 只能确认命名输出存在，不能验证内容、解析状态和物理量。
- 安装过程提前激活新 site，缺少失败回滚。
- 运行时依赖、systemd 路径转义和 workspace 权限仍不够可重复、可验证。

### P2：交付与维护问题

- 发布清单与当前工作树不一致。
- 个别报告混淆 solver 原生输出与 transport 派生输出。
- 资格声明、Schema 和文档需要在最终合同确定后同步更新。

多案例和二进制 TDR 是通用 SDevice 闭环的高优先级能力阻塞项，但不阻止
当前单案例 Fig.4 SProcess 基线诊断。因此不将它们与单位错误归为同一种 P0。

## 3. 执行原则

1. 先关闭错误科学判定和执行旁路，再接入通用闭环；部署可靠性作为独立工作流并行
   修复，所有工作流通过后才进行发布冻结。
2. 每个改动只保留一个权威生产实现；TCAD skill 通过版本化合同、共享测试向量或
   明确的包接口验证一致性，不复制一套会独立漂移的规则。
3. 控制面负责不可变对象、生命周期和审批；worker 负责科学内容；TCAD adapter
   只负责执行副作用。
4. 不恢复已经废弃的兼容接口，不为历史垃圾数据增加旁路。
5. 不以 mock 闭环代替至少一次真实 SProcess 资格验证。
6. 使用当前明确选择的 base/Conda Python 解释器，但应用及第三方依赖必须从锁定的
   wheelhouse 安装到版本化 site；服务不得依赖可漂移的 user-site 包。
7. 任何科学结论、执行授权和下游文件依赖都必须绑定精确不可变父对象，不能仅凭
   “最新文件”、profile 名称、路径字符串或自然语言描述建立关系。
8. 对破坏兼容性的 Schema 新建版本，不原地重释已经注册的 v1 Artifact。有效历史
   Bundle 保持只读可审计，但旧裸 JobSpec 不因此获得生产执行旁路。

### 3.1 核心对象关系

整改后的最小对象关系为：

```text
ExperimentCase
  -> CaseRealization
       -> HistoricalArtifact，或
       -> 一个/多个 ExecutionResult

StudyExecutionPlan
  -> ExecutionUnit[]
       -> ReviewedDeckPackage
       -> SolverCapabilityRef
       -> ResolvedProjectInput[]
       -> 上游 ExecutionUnit 依赖

ClaimDecision
  -> 精确 ValidationReport 或 LayeredDiagnosisReport
  -> 对应 experiment / plan / execution-result 父链
```

其中，一个 `ExecutionUnit` 始终等于一次直接调用：

```text
solver executable + solver-language entrypoint + arguments -> declared outputs
```

SProcess 与 SDevice 必须是不同的执行单元。科学 worker 只使用语义输入名称；
Artifact 引用解析、父关系绑定、staging 和授权均由控制面完成。

## 4. 分阶段实施

### 阶段 A：关闭科学正确性缺口

#### A1. 单位安全的阈值判定

实现内容：

- 为确定性数值阈值和观测值定义受限、可机读的单位合同；优先覆盖项目实际使用的
  电压、长度、时间、电流、电流密度和无量纲指标，不实现无限扩张的通用单位系统。
- 将阈值求值接口改为同时接收观测值及其单位；比较前执行维度检查、规范化和
  确定性换算，不兼容或未知单位必须失败关闭。
- 无量纲数值显式使用规范标识（如 `1`），不允许用空字符串隐式表示。
- `between` 继续使用一套阈值单位，观测值换算到该单位后再比较。
- 单位要求只施加于确定性数值检查；不强迫纯定性文本判断声明伪单位。

测试门槛：

- `1000 mV >= 2 V` 得到 `false`，等价单位表达得到相同结果。
- 长度、时间、电流密度等至少各有一组跨尺度换算测试。
- 电压与长度比较被拒绝。
- 需要量纲的确定性结果缺失单位或使用未知单位时，不能产生 pass/fail 科学结论。
- 显式无量纲阈值可以正常判定；定性检查保持原有行为。

#### A2. 统一 claim 状态投影

实现内容：

- 新增控制面拥有的确定性 `ClaimDecision` 投影函数，同时支持
  `validation_report` 和 `layered_diagnosis`，但每次只消费一个当前有效诊断。
- 修改 `ScientificReadiness` 一致性约束：`accepted` 必须由其中一种合格诊断支持，
  不再硬编码只能存在 `validation_report`。
- 当前诊断通过固定语义槽、revision 以及 experiment、validation plan、execution
  result 的精确父关系选择；禁止按逻辑名称排序或扫描任意历史 passing report。
- readiness、knowledge update 和 UI 状态消费同一个 `ClaimDecision`，不分别解释
  `claim_allowed`。
- 非当前实验、被 supersede、父链不完整或 payload 无效的诊断只形成 blocker，不能
  接受 claim。

测试门槛：

- 通过的 layered diagnosis 使 readiness 为 `accepted`。
- 通过的 validation report 保持现有 accepted 行为。
- 任一必要 gate 失败时不能进入 `accepted`。
- 单独存在 layered diagnosis 时 readiness Schema 仍可合法构造。
- 不同实验的旧 passing report、失效或较旧报告不能覆盖当前修订。
- readiness、knowledge update 和 UI 对同一诊断给出一致状态。

#### A3. 强制 reviewed package 执行边界

实现内容：

- 删除本地 adapter 对裸 `tcad.job-spec.v1` 的执行支持。
- 保持通用 execution bridge 的领域中立性，但要求 adapter 在请求创建前同时验证
  preparation profile 与 payload 的 kind、schema 和规范化内容。
- 所有生产 TCAD adapter 只接受 `tcad.reviewed-deck-package.v2`；v2 package 必须
  绑定精确 review、resolved project 和 solver capability。
- 对所有 adapter 运行同一合同测试，避免本地与 SSH 路径产生策略差异。

测试门槛：

- 裸 JobSpec 在 bridge、local adapter 和 command adapter 三处均被拒绝。
- 现有执行 smoke 迁移到 v2 reviewed package 后继续通过。
- 未经 reviewer 产物不能创建可授权 ExecutionRequest。
- profile 与 payload schema 不匹配时在创建请求阶段失败，而不是人工授权后才失败。
- 历史 v1 package 可读取和导出，但不能自动升级成 v2 执行授权。

#### A4. 显式求解器 capability

实现内容：

- 定义版本化 `SolverCapability`，至少包含枚举型 `solver_kind`、可执行文件身份、
  固定参数、允许的环境注入、发行版证据和 capability 摘要；至少支持 `sprocess`、
  `sdevice` 和明确的非求解器工具类型。
- reviewed package、ExecutionUnit 和 ExecutionRequest 绑定同一个 capability 摘要；
  人工审批页面展示最终可重建的 argv 和 capability 身份。
- packager、reviewer 和 runner 使用同一个生产规则模块；TCAD skill 使用同版本合同
  和共享正反测试向量验证一致性。
- 删除通过 profile 名称包含 `sprocess`/`sdevice` 来猜测语义的代码。
- runner 在提交前重新计算受保护配置摘要；review 后 executable、固定参数或环境
  发生变化时失败关闭。不得假设 `-V`/`--version` 等探测参数存在。

测试门槛：

- 任意 profile 名称都不能改变显式 solver kind。
- SProcess/SDevice 的入口文件、参数和输出合同分别通过正反测试。
- 配置 capability 与 deck 内容冲突时构建失败。
- review 后替换 executable、固定参数或允许环境时，旧执行请求被拒绝。
- 实际提交 argv 与审批页面展示的 argv 完全一致。
- shell runner 不得以 SProcess/SDevice capability 执行。

阶段 A 完成条件：四项均通过单元测试、集成测试和现有 Fig.4 fixture 回归。
B2/B3 的生产接入以 A3/A4 完成为前置条件；不依赖它们的 Schema 设计和部署修复
可以并行开展。

### 阶段 B：补齐确定性科学闭环

#### B1. 控制等价性生产 transform

实现内容：

- 先实现确定性的 `realization_snapshot` materializer，再注册
  `control_equivalence` comparator；不能只自动化 comparator。
- materializer 从精确 experiment contract、resolved project、reviewed package、
  solver capability 和已验证的运行元数据提取 realized values，并把这些输入注册为
  snapshot 的不可变父对象。
- 不尝试实现一个猜测任意 Sentaurus Tcl/命令语义的完整 parser；优先验证受审查的
  realization manifest、精确 locator、允许的 patch/diff 和 capability。无法静态解析
  的动态表达式必须进入 reviewed/inconclusive 路径。
- 历史 baseline 必须绑定已注册 Artifact 和其提取/审查证据；不能由 worker 仅用
  `source_description` 自我声明已实现参数。
- comparator 输入为完整、来源可验证的对照与候选 snapshots，输出类型化报告。
- 比较几何、材料、掺杂、模型、网格、边界、求解器和所有声明的非目标变量；
  无法从可信来源提取的字段必须是 inconclusive，不能默认为相等。
- transform 只做确定性比较，不替代 critic 的物理判断。

测试门槛：

- 只改变声明的实验变量时通过。
- 任一未声明的材料、网格或求解器变化均失败并给出字段级差异。
- worker 省略实际发生变化的字段时，materializer 仍能发现差异或失败关闭。
- snapshot 缺失可信父链、历史 Artifact 或 capability 绑定时被拒绝。
- 产物能直接被 layered diagnosis 消费。

#### B2. 类型化 StudyExecutionPlan

实现内容：

- 新增 `CaseRealization`，把每个 experiment case 表达为历史证据 realization，或
  一个/多个新 ExecutionResult 的有序组合。
- 新增 `ExecutionUnit`；每个单元只表达一次直接求解器调用，并显式绑定 case、
  reviewed project、solver capability、资源限制、上游依赖和预期输出。
- `StudyExecutionPlan` 同时约束 cases、realizations 和 execution units 的覆盖关系，
  但不强制 case 数量等于 execution unit 数量。
- 定义串行、并行及失败传播规则，但不把科学 workflow 固化成静态流程图。

测试门槛：

- 单案例保持简单路径。
- 历史 baseline + 新 candidate 表达为两个 realizations、一个新执行单元。
- 一个 case 的 SProcess→SDevice 表达为一个 realization、两个有向依赖执行单元。
- 两个都需重新仿真的 cases 生成至少两个不可混淆的直接执行单元和结果绑定。
- 缺失案例、重复绑定或跨案例串线均被拒绝。
- SProcess/SDevice 被塞进同一 entrypoint、执行单元形成环或上游失败后仍启动下游时
  均被拒绝。

#### B3. 文件 Artifact 引用和执行 DAG

实现内容：

- `DeckFile` 只承载 UTF-8 文本源码；复用现有 `ArtifactRef`，新增项目输入槽与解析后
  的 `ResolvedProjectInput`，承载目标相对路径、不可变引用和期望媒体类型。
- 科学 worker 在 draft 中只声明语义输入名称和目标相对路径。控制面将语义名称解析
  为精确 ArtifactRef，生成 `ResolvedDeckProject` 后再进入独立 review。
- reviewed package 同时绑定 resolved project、passing review 和 solver capability；
  其 Artifact envelope 父关系覆盖全部文本、二进制输入和审查对象。
- 新增控制面 packaging service，从 CAS 读取已绑定输入，复核摘要、大小、媒体类型
  和目标路径，再生成密封 archive；不让纯 transform 或执行 adapter 自行查询任意
  Artifact。
- 执行 DAG 只允许把上游已 collected 且 runtime qualification 通过的精确输出
  Artifact 绑定到下游输入槽。
- 二进制内容不内嵌到 JSON，也不由 Agent 抄写路径、对象 ID 或摘要。

测试门槛：

- 二进制文件摘要、大小和媒体类型在打包前后保持一致。
- 未声明、被替换或越界路径的输入被拒绝。
- 同一语义名称被重新绑定后，旧 review/package 不能用于新内容。
- 上游未收集、runtime gate 失败或输出不合格时，下游 SDevice 不得进入授权状态。
- 最小 SProcess 到 SDevice fixture 能构造、解析输入、独立审查和确定性打包。
- 打包后的 SDevice `Grid` 文件名与 deck 引用完全一致，且 TDR 字节保持不变。

#### B4. 结果解析与可执行断言

实现内容：

- 将“输出存在”“格式可解析”“数值完整”“科学阈值”拆成不同 gate。
- 为 PLX、PLT、solver log 和 TDR 元数据建立按 solver kind、发行版和 media type
  选择的版本化 parser provider 接口。
- PLX/PLT 优先使用固化真实样本资格验证；TDR 元数据只通过已经声明并验证的
  Synopsys 工具 capability 或合格 provider 提取，不臆造通用二进制解析器。
- runtime assertion 支持文件非空、终止状态、列/变量存在、有限数值和采样覆盖。
- 科学阈值仍由验证计划管理，不塞进 transport。
- transport 只报告传输描述符；solver 原生输出、parser 派生元数据和 scorer 结果
  使用不同 artifact kind 和计数口径。

测试门槛：

- 空文件、截断文件、错误终止但文件存在等情况不得通过。
- parser 失败不能被降级为成功执行。
- PLT 缺失偏压点、重复支路、非有限电流或不满足声明的收敛/KCL 检查时失败关闭。
- 没有合格 TDR provider 时明确报告 capability unavailable，而不是猜测内容有效。
- solver 原生输出和 transport 派生描述符在报告中分别计数。

阶段 B 完成条件：使用固化 fixture 覆盖“历史+新执行”“双新执行”和
“单 case 的 SProcess→SDevice”三种拓扑，并至少完成一次经审批的真实 SProcess
执行、收集、解析、诊断闭环。SDevice 仅在具备许可证、合格 TDR fixture 和匹配
capability 时进行真实资格验证；缺少外部能力不阻止 Schema/fixture 工程验收，但
必须保留为明确未资格化边界。

### 阶段 C：部署可靠性和可迁移性

#### C1. 事务化安装与回滚

实现内容：

- 将 package build/probe 与 deployment activation 分离。
- 在临时目录生成并验证新 site、依赖、CLI 启动器、配置、systemd units 和平台
  skills，形成带摘要的 `InstallTransactionManifest`，之后才停止服务。
- 对所有将被替换的目标建立同文件系统 staging 或可恢复备份；按明确顺序切换
  site、启动器、配置、units 和 skills，再执行 daemon reload、服务启动和 MCP
  健康检查。
- 保留 previous release 和事务日志直到全部健康检查通过；任一步失败恢复全部目标
  及安装前服务状态，而不只恢复 Python site。
- 数据库 Schema 变更必须先证明向后兼容，或提供经故障注入验证的备份/恢复步骤；
  未具备回滚能力的迁移不能混入普通安装。

测试门槛：

- 在构建、停止服务、site/配置/unit/skill 切换、启动和健康检查处分别注入失败，
  均能恢复文件摘要和原服务状态。
- dry-run 不写系统路径，也不停止服务。
- 重复安装保持幂等。
- 回滚后使用旧 release 执行 CLI、MCP 和 state validator smoke。
- 模拟不兼容数据库迁移时安装在修改状态前失败关闭。

#### C2. 运行时依赖身份

实现内容：

- 安装时记录 Python 可执行文件真实路径、版本和关键依赖版本；应用依赖从带摘要的
  锁文件/wheelhouse 安装到版本化 site，base/Conda 只提供解释器和标准库。
- 使用标准 PEP 440 解析，不维护自定义版本正则。
- 服务启动前验证运行时身份；漂移时失败关闭并给出修复命令。
- 禁用 user-site 和在线依赖解析；安装前校验每个 wheel 摘要，离线缺包直接失败。

测试门槛：

- 解释器或关键依赖漂移可被检测。
- 当前 Conda base 安装路径可通过。
- 离线安装不访问网络。
- 临时修改 base 中同名依赖时，服务仍使用 release site 的锁定版本。
- previous release 的依赖保留到事务提交，回滚后可正常导入。

#### C3. systemd 路径和 workspace 安全

实现内容：

- 拒绝换行、控制字符、不规范路径和符号链接 workspace 根。
- 使用 systemd 兼容的参数生成方式，不直接替换未转义字符串。
- dry-run 实际渲染 unit，并运行 `systemd-analyze verify`。
- workspace 初始化使用 `umask 027`/显式 `0750`，并检查每一级既有路径。

测试门槛：

- 含空格的合法路径可正确安装，恶意路径被拒绝。
- symlink workspace 和 group/world writable 敏感目录被拒绝。
- 生成 unit 全部通过 systemd 静态验证。

阶段 C 完成条件：干净 WSL/Linux 环境安装、升级、故障回滚、卸载和重新安装测试
全部通过；VM 关闭时控制面仍能启动，并将 TCAD 执行明确报告为不可用。C1–C3
可以与阶段 B 的科学能力开发并行，但发布冻结必须同时满足 B、C。

### 阶段 D：发布冻结

实现内容：

- 修正报告中的 solver 输出与 transport 输出术语。
- 更新中英文 README、安装文档、Schema 说明和资格边界。
- 运行全量测试和真实资格 smoke。
- 最后重新生成 `MANIFEST.sha256`，确认 Git 工作树只含预期交付内容。

测试门槛：

- 全量 pytest、部署脚本测试、离线 package build 和 state validator 通过。
- Codex 配置通过；Claude 配置至少完成静态生成与 Schema 检查，并明确未验证项。
- `sha256sum -c MANIFEST.sha256` 无失配。
- 没有 workspace、数据库、日志、密钥、审批记录或仿真结果进入 Git。

## 5. 测试分层

每个阶段按以下顺序测试，失败后停止进入下一层：

1. Schema/纯函数单元测试。
2. adapter、transform、readiness 和 packager 组件测试。
3. 不启动服务的进程内集成测试。
4. 临时目录和临时 socket 的服务集成测试。
5. 安装/升级/回滚部署测试。
6. 固化 fixture 的工程闭环。
7. 经人工审批的真实 TCAD 资格验证。

测试 fixture 必须固定输入、预期输出和失败原因。mock 只验证协议和状态机，不能
用来声明 Sentaurus 或科学模型合格。

fixture 分为两类：协议测试使用可公开的合成文本和二进制哨兵；真实 Sentaurus
PLX/PLT/TDR/log 保留在 Git 外的资格 Bundle 中，以内容摘要和预期检查结果绑定。
CI 中的合成 `.tdr` 只能证明二进制 staging，不得据此宣称 TDR parser 或 SDevice
科学链路已经合格。

### 5.1 必须保留的缺陷回归

开始实现前先把本轮最小复现固化为失败测试：

1. `1000 mV` 与 `2 V` 被错误直接比较。
2. 仅有 passing layered diagnosis 时 readiness 不能 accepted。
3. 本地 adapter 接受裸 `tcad.job-spec.v1`。
4. profile 名称影响 solver kind，且 review 后 capability 可被替换。
5. worker 自报 realization snapshot 可遗漏真实 deck 差异。
6. 历史 baseline + 新 candidate 无法用一个新执行表达。
7. 文本工程无法绑定 SDevice TDR。
8. 空或截断输出仅因“文件存在”通过 runtime assertion。
9. 安装失败后 site、unit、skill 或启动器处于混合版本。
10. 含空格 workspace 被 systemd 拆分，或默认权限为 `0755`。

每项整改必须先使对应测试由红转绿，再运行全量回归。
失败测试与对应修复在同一工作分支交付，主分支不长期保留非预期红灯。

## 6. 实施顺序与依赖

采用依赖驱动的工作流，不把所有工作机械串行化：

| 工作流 | 内容 | 前置条件 | 退出条件 |
|---|---|---|---|
| W0 | 固化 10 个缺陷复现、Schema 版本策略 | 无 | 测试能稳定复现当前问题 |
| W1 | A1 单位、A2 claim 投影 | W0 | 科学判定 P0 全部关闭 |
| W2 | A3 review 边界、A4 capability | W0 | 未审查或能力漂移请求无法授权 |
| W3 | B1 snapshot、B2 execution plan | W1/W2 的合同确定 | 三种 case/执行拓扑 fixture 通过 |
| W4 | B3 二进制 staging、B4 parser gates | W2、B2 | SProcess→SDevice fixture 打包及结果 gate 通过 |
| W5 | C1–C3 部署整改 | W0，可与 W1–W4 并行 | 安装故障矩阵全部可恢复 |
| W6 | D 发布冻结 | W1–W5 | 全量门槛、真实资格边界和 manifest 通过 |

W1/W2 可以并行；W5 不必等待科学闭环开发。任何工作流完成只表示其退出条件通过，
不代表整个版本已经可发布。

## 7. 交付物

- 单位安全的验证合同和回归测试。
- 带精确父链的统一 `ClaimDecision` 投影。
- 显式、不可替换的 solver capability 和统一 TCAD 项目执行合同。
- 可信 realization snapshot materializer 与 control equivalence comparator。
- `CaseRealization`、`StudyExecutionPlan`、复用 ArtifactRef 的二进制输入绑定和执行 DAG。
- 版本化结果 parser 与分层 runtime/scientific gates。
- 覆盖 site、配置、unit、skill、启动器和数据库边界的事务安装器。
- 路径安全初始化器、锁定 wheelhouse 和运行时身份清单。
- 更新后的中英文文档、发布清单和资格报告。

## 8. 明确不在本轮处理的事项

- 不借工程整改改变或接受 Fig.4、暗电流或光响应物理模型。
- 不重新引入旧 `tcad_control` 交互入口。
- 不把 Agent 身份、Artifact ID 或执行 ID重新暴露给科学 worker。
- 不为了兼容历史 workspace 中的垃圾对象而增加旁路。
- 不在阶段 A 到 C 完成前宣称通用 SDevice 科学闭环已经合格。
- 不在没有合格 Synopsys capability 时自行猜测 TDR 二进制格式或发行版参数。
- 不把所有 TCAD 科学 workflow 固化为一个中央静态状态机。

## 9. 进度记录

| 阶段 | 状态 | 完成门槛 |
|---|---|---|
| A 科学正确性 | 已完成 | A1-A4 单元、adapter、runner、审批和全量回归通过 |
| B 科学闭环能力 | 工程 fixture 已完成；真实资格待外部能力 | 类型化 DAG、materializer、二进制 staging 和 parser gate 已通过；真实 SProcess/SDevice 未资格化 |
| C 部署可靠性 | 部分完成 | 事务回滚、路径、权限和运行时身份已通过；锁定 wheelhouse 与真实 root/systemd 故障矩阵待目标机验证 |
| D 发布冻结 | 阻塞于外部门禁 | hermetic 全量测试与文档已更新；真实 SProcess、许可证决策和目标机部署 smoke 尚缺 |

状态只能在对应门槛满足后更新，不以“代码已写”代替“阶段完成”。

### 9.1 2026-08-08 执行记录

- W0/W1：固化并关闭单位误比较、layered diagnosis claim 投影等 P0 回归。
- W2：生产 adapter 只接受 `tcad.reviewed-deck-package.v2`；package/JobSpec/
  local runner/remote runner 绑定同一 `SolverCapability` 摘要，审批页展示 release
  证据、capability 摘要和最终 argv。
- W3：新增 `CaseRealization`、`ExecutionUnit`、`StudyExecutionPlan`，支持历史
  baseline + 新 candidate、双新 case 和单 case SProcess→SDevice，拒绝遗漏、重复、
  环和跨 case 串线；新增控制面 realization snapshot materializer。
- W4：新增语义 input slot、`ResolvedProjectInput` 和 ArtifactRef 二进制 staging；
  拆分 transport、format、numeric、runtime gate，并对无合格 TDR provider 失败关闭。
- W5：安装器先构建后激活；事务快照覆盖 site、launcher、unit、policy/secret、
  workspace 配置、Codex/Claude skill 和 SQLite，失败时恢复安装前服务状态；systemd
  路径支持空格，workspace 默认为 `0750`，服务启动前校验 runtime identity。
- 全量结果：`322 passed`。本机未发现 `sprocess`/`sdevice`，资格状态见
  [TCAD_QUALIFICATION_STATUS.zh-CN.md](../TCAD_QUALIFICATION_STATUS.zh-CN.md)。

尚不能把 B/C/D 标为完成：仓库内没有带摘要 wheelhouse，当前机器没有真实
Sentaurus capability/许可证，且公开发布许可证必须由项目所有者选择。
