# TCAD 科学研究 Agent 架构与实现审计报告

> 审计对象：`scidiscovery-agent` 代码库
> 审计日期：2026-08-08
> 审计范围：科学发现工作流、Sentaurus TCAD 工程建模、制品与审批控制、执行隔离、可复现性、测试与可维护性

## 1. 执行摘要

该项目已经形成了较扎实的“科学工作流控制平面”：不可变制品、内容寻址存储、精确审批、任务租约、执行边界、确定性打包和输出限制等基础机制均有较完整的实现。相较于普通的 LLM 工具调用框架，它对审计性、故障恢复和执行授权的重视是明显优势。

但从 TCAD 科学研究助手的目标来看，当前系统更准确的定位仍是：**具备 TCAD 插件的科学控制平面原型**，尚不是一个能够可靠闭环完成 Sentaurus 科学研究的生产级 Agent。核心差距并非单个函数缺陷，而是科学对象模型、仿真执行模型和结论证据链之间尚未贯通。

最关键的阻塞项有四个：

1. 科学层要求多案例实验，但执行层只表达单个 deck 工程，缺少 case 到执行单元的映射和依赖图。
2. SDevice 的典型输入依赖二进制 TDR，而当前 deck 模型只支持文本文件，SProcess → SDevice 链路无法自然表达。
3. 调度拓扑要求控制等价性、指标报告和运行时证明，但缺少完整、可调用的生产适配器，默认科学闭环实际不可达。
4. TCAD 审核主要停留在声明和文件存在性层面，尚未验证求解器语义、输出内容、收敛性和物理有效性。

因此，在完成本报告 P0 项目前，不建议将系统描述为“完整的 TCAD 自动科学发现闭环”，也不建议让它自主批准物理结论或生产级仿真 deck。

## 2. 已具备的优势

### 2.1 控制平面设计方向正确

- 制品采用内容哈希和父引用，适合构建可追踪、可重放的科学证据链。
- worker、审批、控制与执行职责已有明确拆分。
- 任务租约、并发控制、故障注入和输出边界有较全面的测试覆盖。
- 打包过程强调确定性，运行目录采用只读输入并配置资源限制。
- 代码明确区分“程序成功退出”和“物理结果有效”，这是科学计算系统必须保留的边界。

### 2.2 工程基础质量较好

审计期间完成的基础验证结果如下：

| 检查项 | 结果 |
| --- | --- |
| `pytest -q` | 279 项测试通过，用时 33.71 秒 |
| Python `compileall` | 通过 |
| `pip check` | 未发现损坏的依赖关系 |
| `sha256sum -c MANIFEST.sha256` | 全部通过 |

这些结果说明当前代码库内部一致性较好。不过，它们主要证明控制平面与模拟执行路径稳定，不能替代真实 Sentaurus 工具链的资格验证。

## 3. 问题分级总览

| 严重度 | 问题 | 主要影响 |
| --- | --- | --- |
| 阻塞 | 多案例科学模型与单工程执行模型冲突 | 无法可靠执行基线/候选、多阶段研究 |
| 阻塞 | 不支持二进制 TDR 输入及阶段依赖 | 典型 SDevice 和 SProcess → SDevice 流程无法闭环 |
| 阻塞 | 默认科学闭环缺少必要适配器 | 调度器要求的诊断输入无法稳定产生 |
| 阻塞 | TCAD 验证深度不足 | “运行成功”可能被误当成“物理可信” |
| 高 | 跨对象一致性验证未进入生产路径 | 科学对象可分别合法、组合后却不一致 |
| 高 | 单位与参数实现过于宽松 | 阈值判断和参数扫描可能产生静默错误 |
| 高 | 服务身份和 IPC 授权边界不足 | 单服务被攻破后可能横向获得执行或审批能力 |
| 高 | 科学可复现元数据不完整 | 无法严格复现实验生成、求解和结论过程 |
| 中 | 测试缺少真实求解器资格验证 | 生产兼容性和错误处理缺少证据 |
| 中 | 大文件与旧/新模型并存 | 修改风险、认知负担和迁移成本持续上升 |

## 4. 详细发现

### 4.1 多案例实验无法映射到执行单元（阻塞）

科学模型中的 `ExperimentPortfolio` 要求至少两个实验案例，见 [experiment.py](../src/scidiscovery/artifact_agent/schema/experiment.py#L370)。这符合对照实验的基本思想，但 TCAD 工程草稿仅表达一个 `tool_profile`、一个入口文件和一组参数，见 [project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L187)。与此同时，Sentaurus 执行契约要求独立案例拆分为独立执行单元，见 [execution-contract.md](../skills/sentaurus-tcad-code/references/execution-contract.md#L51)。

当前缺少以下一等对象：

- `case_id` 到 `DeckProject`/执行单元的确定性绑定；
- baseline、candidate 与具体执行结果之间的关联；
- 多执行单元 DAG，以及 SProcess → SDevice 依赖边；
- 每个案例独立的审批、运行时证明、指标和失败状态；
- 多案例聚合后的比较结果及其父制品关系。

这会使多案例实验在科学层成立，却无法无歧义地下沉到执行层。建议引入 `StudyExecutionPlan`，显式包含案例、执行单元、依赖、输入制品、预期输出和比较关系。

### 4.2 典型 SDevice 工程无法完整打包（阻塞）

`DeckFile` 当前只接受字符串内容，见 [project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L59)。但典型 SDevice deck 会引用 `Grid = "device.tdr"` 等二进制网格/状态输入，相关约束见 [sdevice.md](../skills/sentaurus-tcad-code/references/sdevice.md#L18)。

因此系统目前缺少：

- 二进制输入制品描述和内容哈希；
- 上游执行输出到下游输入的安全注入；
- TDR 元数据检查，例如区域、材料、电极和网格信息；
- SProcess 输出与 SDevice 输入之间的类型化契约；
- 输入文件缺失、版本不兼容或结构不匹配时的前置拒绝。

若只支持文本 deck，能够覆盖的主要是简化示例，而不是常见的器件仿真研究链路。

### 4.3 默认科学闭环在当前拓扑中不可达（阻塞）

调度器要求诊断阶段同时获得 `experiment_portfolio`、`execution_result`、`runtime_attestation`、`control_equivalence_report` 和 `metric_report`，见 [scheduler_topology.py](../src/scidiscovery/scheduler_topology.py#L225)。审计发现：

- 控制等价性存在库级逻辑，但没有完整的可调用 transform adapter；
- 通用 TCAD 插件缺少统一的结果评分器，`metric_report` 只在特定插件路径中可选产生；
- 运行时证明的拓扑输入与 TCAD transform 实际期望的 `runtime_manifest` 存在接口错位；
- diagnostician 已输出 `layered_diagnosis`，见 [diagnostician.md](../roles/diagnostician.md#L4)，但 claim readiness 仍只识别 `validation_report`，见 [mcp_root.py](../src/scidiscovery/artifact_agent/mcp_root.py#L516)。

对适配器注册表的运行时枚举也未发现 `evaluate_control_equivalence`、`scidiscovery.control-equivalence.v1` 或通用 `score_results` 的完整生产适配器。

这不是单纯的命名问题：即使各个角色都能生成自己的制品，调度器仍可能永远等不到满足诊断前置条件的一组对象。应建立一条最小可达的端到端制品链，并在 CI 中通过拓扑遍历或真实工作流测试证明其可达性。

### 4.4 TCAD 审核低于项目自身契约要求（阻塞）

当前生产打包器通过 profile 名称中的字符串推断求解器类型，见 [project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L50)；真正的可执行文件和前缀参数直到提交执行时才映射，见 [execution_control.py](../plugins/tcad_artifact/tcad_artifact/execution_control.py#L225)。因此，审核者看到的工程语义并不等同于最终执行能力映射。

此外，skill 附带的验证器会检测嵌套的 `sprocess` 调用，见 [validate_deck_project.py](../skills/sentaurus-tcad-code/scripts/validate_deck_project.py#L111)，而生产打包器没有等价检查。审计中的最小复现表明：包含 `sprocess child.cmd` 的工程被 skill 验证器拒绝，却被 `DeckProjectDraft` 接受，说明“指导性验证”和“生产准入验证”已经发生分叉。

现有测试还接受极简 SProcess deck，例如只含 `math coord.ucs` 和 `exit`，并声明一个实际不会生成的 `case.log`，见 [test_sentaurus_tcad_code_skill.py](../tests/artifact_agent/test_sentaurus_tcad_code_skill.py#L64)。运行时断言主要检查文件是否存在，见 [project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L857)，尚未系统验证：

- 日志中的 parser error、license error、异常终止和未收敛；
- 偏压扫描是否达到目标点、步长是否异常缩减；
- 电流守恒、KCL、场量范围和接触定义是否合理；
- PLX/PLT/TDR 是否可解析，数据列和单位是否符合预期；
- 预期输出是否确由当前执行产生，而非残留或空壳文件。

建议合并 skill 验证器与生产打包器的规则源，并为日志、PLX、PLT、TDR 建立类型化解析与科学验收层。

### 4.5 跨对象科学一致性验证未进入生产路径（高）

任务 finalize 主要验证单个 payload，见 [tasks.py](../src/scidiscovery/artifact_agent/service/tasks.py#L923)。代码库虽存在 `validate_layered_discovery_chain`，见 [discovery.py](../src/scidiscovery/artifact_agent/schema/discovery.py#L129)，但它仍面向旧的 `HypothesisPortfolio`/`ScientificReview` 模型，而生产 ideator 与 critic 已分别输出 `HypothesisProposal` 和 `CriticReview`，见 [ideator.md](../roles/ideator.md#L4) 与 [critic.md](../roles/critic.md#L4)。

这体现出一次尚未完成的 schema 迁移。当前可能出现以下组合错误：

- 实验选择的假设并非 critic 判定为可执行的候选；
- deck 中的参数、控制变量与实验案例定义不一致；
- 诊断引用的指标不属于对应 execution result；
- evidence locator 或 excerpt 只证明来源键存在，不能证明引用内容和主张一致；
- 新旧角色输出分别通过 schema，却无法形成一条严格父子关系链。

应将跨对象验证设为 finalize 和 claim readiness 的强制门槛，而不是只保留为可选库函数。

### 4.6 单位系统与参数实现可能产生静默科学错误（高）

单位目前主要是任意字符串。确定性阈值判断直接比较数值，没有先验证报告单位与阈值单位是否兼容，见 [validation.py](../src/scidiscovery/artifact_agent/schema/validation.py#L336)。例如 `1000 mV` 和 `1 V` 若未经换算就比较，会得到错误结论。

参数定位也主要依赖文本子串匹配，见 [project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L255)，没有证明该值最终被求解器以预期语义解析。风险包括：

- 同名参数出现多次却没有唯一性约束；
- include 文件或 Tcl 变量覆盖参数；
- 文本中出现目标字符串，但并非有效赋值；
- 单位后缀、默认单位和求解器内部单位发生偏差；
- 扫描参数写入 deck，却未进入实际 solve 路径。

建议引入规范化 quantity 类型、量纲检查和显式换算，并让参数实现产生可验证的“解析后参数清单”，而不是只报告文本命中。

### 4.7 服务身份与执行授权隔离不足（高）

安装脚本将控制、worker、审批和执行服务配置为同一个 `SERVICE_USER`，见 [install.sh](../deploy/install.sh#L7) 及其 systemd 单元渲染逻辑。敏感文件也由同一用户持有。Unix socket broker 主要信任消息中自报的 proxy/worker 标识，见 [mcp_daemon.py](../src/scidiscovery/artifact_agent/mcp_daemon.py#L29) 和 [mcp_worker_daemon.py](../src/scidiscovery/artifact_agent/mcp_worker_daemon.py#L30)，尚未充分利用 peer credentials 或消息级认证。

主要风险是：一旦任一同 UID 服务被攻破，攻击者可能读取共享密钥、连接其他 socket，并伪装成另一个控制面角色。TCAD deck 本身又可能含 Tcl 行为，而执行器为许可证通信允许网络访问，扩大了同身份运行时的影响范围。

另有两个具体问题值得修复：

- worker 的分析网络沙箱可被一个语义容易误解的环境变量关闭，见 [mcp_worker.py](../src/scidiscovery/artifact_agent/mcp_worker.py#L568)；
- web fetch 先解析并检查 DNS，随后 `urllib` 再次解析目标，存在 DNS 重绑定/TOCTOU 型 SSRF 风险。

建议使用不同 OS 用户运行审批、控制、分析 worker 和求解器 executor；按目录和 socket 设置最小权限；使用 Unix peer credentials 或短期签名令牌绑定调用身份；将许可证网络与一般外网访问拆分到可审计的网络策略中。

### 4.8 可复现性元数据不完整（高）

严格复现一项 Agent 驱动的 TCAD 研究，需要同时记录推理过程、代码环境和求解器环境。当前仍缺少：

- LLM 提供方、模型版本、采样参数、工具版本和 token 配置；
- 求解器可执行文件摘要、精确版本、license/capability 快照；
- 依赖锁文件和构建环境摘要；
- 操作系统、CPU、关键环境变量和数值库信息；
- 不可变的执行状态事件序列，而不只是可变生命周期记录。

`AgentTask` 未承载完整的模型生成元数据，见 [task.py](../src/scidiscovery/artifact_agent/schema/task.py#L63)；`ToolProfile` 主要记录路径，见 [execution_control.py](../plugins/tcad_artifact/tcad_artifact/execution_control.py#L94)；worker manifest 也主要包含时间、错误、退出状态和输出，见 [worker.py](../plugins/tcad_artifact/tcad_artifact/worker.py#L87)。此外，[pyproject.toml](../pyproject.toml#L10) 使用较宽的依赖范围，但仓库没有对应的完整锁定策略。

建议将这些信息写入独立、不可变的 provenance 制品，并让最终 claim 必须引用它。

### 4.9 测试通过，但尚未构成 TCAD 生产资格证据（中）

当前 279 项测试通过，覆盖了大量控制平面行为。然而端到端测试使用 `/bin/sh` 夹具模拟求解器，见 [test_process_execution_loop.py](../tests/artifact_agent/e2e/test_process_execution_loop.py#L48)，尚未覆盖：

- 真实 SProcess deck 和真实输出；
- 带二进制 TDR 的真实 SDevice 执行；
- baseline/candidate 成对实验；
- SProcess → SDevice 多阶段链路；
- 求解器 parser、license、收敛和部分输出错误；
- 生产 systemd 权限、socket 访问和服务重启行为；
- 真实 Codex/Claude 角色输出对 schema 与证据链的兼容性。

CI 当前主要运行 pytest，见 [ci.yml](../.github/workflows/ci.yml#L24)，缺少类型检查、lint、覆盖率阈值、安全扫描、构建安装测试和真实求解器资格验证。文档仍保留“156 passed”的旧数据，见 [scientific_discovery_layer.md](scientific_discovery_layer.md#L114)，也说明验证指标尚未自动同步。

建议将测试分为快速单元层、无许可证的 parser/fixture 层、受控真实 Sentaurus qualification 层三档，最后一档可在具备许可证的内部 runner 定期执行。

### 4.10 模块体量和模型分叉增加维护风险（中）

审计时统计约有 24,029 行生产 Python 和 12,949 行测试代码。多个关键模块已经成为高耦合大文件：

| 文件 | 约行数 |
| --- | ---: |
| `service/tasks.py` | 1,801 |
| `mcp_root.py` | 1,502 |
| `render.py` | 1,427 |
| `scheduler_bindings.py` | 1,309 |
| `approvals.py` | 1,080 |
| `project_packager.py` | 991 |

这些文件同时承担状态机、验证、存储、协议适配和错误映射等职责。再叠加旧/新科学 schema 共存、skill 规则与生产规则分叉、文档数据漂移，会让后续修改更容易产生局部正确但系统不一致的问题。

建议按领域拆分：任务状态机、制品验证、角色契约、TCAD 工程分析、执行打包、结果解析和安全策略分别形成边界明确的模块；同时为 schema 迁移设置版本、兼容期和删除期限。

## 5. 建议改造路线

### P0：形成可执行、可验证的 TCAD 最小闭环

1. 新增 `StudyExecutionPlan`：包含 `solver_kind` 枚举、多个 case、case 到执行单元的绑定、DAG、二进制输入、能力快照和逐 case 预期输出。
2. 将跨对象一致性检查接入 finalize 与 readiness：强制验证“假设资格 → 实验 → case 工程 → 审核 → 执行 → 运行时证明 → 指标/控制等价性 → 诊断”的精确父子链。
3. 统一 skill 和生产验证规则；增加 include/输出/Grid 引用追踪、求解器语法预检，以及 log、PLX、PLT、TDR 解析器。
4. 支持内容寻址的二进制输入与上游输出注入，首先打通一条真实 SProcess → SDevice 链路。
5. 分离 OS 身份和 socket 权限，引入可靠的进程身份认证，并限制 solver 网络能力。

### P1：补齐科学可信度与可复现性

1. 建立 quantity/单位系统，对阈值、指标和参数值执行量纲检查与规范化换算。
2. 记录 LLM、求解器、依赖、主机环境和 capability 的完整 provenance。
3. 为 execution 建立追加式不可变事件日志。
4. 建立真实 Sentaurus qualification 测试：SProcess、SDevice、成对案例、多阶段链路以及 parser/收敛失败。

### P2：降低长期维护成本

1. 完成旧科学 schema 的迁移和删除，避免双模型长期并存。
2. 拆分大型服务和适配器模块，减少 God object 与跨层调用。
3. 为 CI 增加类型检查、lint、覆盖率阈值、安全扫描、构建/安装测试。
4. 自动生成测试数量、协议版本和制品类型清单，避免文档漂移。

## 6. 推荐验收标准

完成 P0 后，至少应通过以下端到端场景，才能声称具备 TCAD 科学闭环：

1. 一个实验包含 baseline 和 candidate 两个案例，二者分别生成并审批独立执行单元。
2. SProcess 生成真实 TDR；该 TDR 以内容哈希制品传递给 SDevice，且区域和电极检查通过。
3. SDevice 执行完成后，系统解析日志和结果文件，区分进程成功、数值收敛和物理验收三种状态。
4. 指标报告验证单位、阈值和 execution parentage；控制等价性报告验证非目标变量保持一致。
5. 诊断与最终 claim 只能引用上述精确证据链，任一父对象不匹配时均被拒绝。
6. 重放时能够固定模型配置、deck、二进制输入、求解器版本、运行环境和评估器版本。
7. 任一 worker 身份被模拟入侵时，不能获得审批密钥、控制 socket 或 executor 权限。

## 7. 结论

项目的控制平面基础值得保留，其不可变制品、审批和执行边界为后续演进提供了较好的骨架。当前最大的架构问题是：**科学计划、TCAD 工程、真实求解器执行和结论证据仍是四个相邻但未完全咬合的子系统**。

下一阶段应优先建设一个窄而真实的纵向闭环，而不是继续扩充角色或制品类型。只要先打通“两个实验案例 + SProcess → SDevice + 结果解析 + 单位化指标 + 精确证据链”，系统的科学可信度、架构边界和后续扩展方向都会明显清晰。
