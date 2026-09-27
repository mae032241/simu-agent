# R5-D4 通用科学插件声明拆分独立审查

日期：2026-08-29  
审查性质：未参与实现的跨边界、简化性与变更范围审查  
结论：**通过并只放行 D5**  
门禁决定：不提前放行 R5-D 总审、R5-E 或后续阶段

## 1. 审查范围

本轮审查通用科学插件的唯一入口、资源、组件、Agent Operation、Transform/Approval Operation
声明及其安装态和运行态消费者；同时核对删除的 `general_transform_operations.py`、当前复杂度聚合和
相关测试调整。审查没有修改生产代码、测试、计划或阶段状态；唯一写入是本报告。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行，覆盖 compiled catalog、跨插件公开组件、真实 Transform、审批、
Worker、clean-wheel 和全仓组合路径。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 权威计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；使用第 3 节、第 8.4 节和 R5-D 复杂度门。 |
| S2 | 当前架构 `docs/ARCHITECTURE.zh-CN.md`，SHA-256 `570d811adb87a7add86bc85057fba5214145f215bc58f95845c7ce20b8a0dfad`；最小重构权威 `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`，SHA-256 `77bb5c36ee71a683b0ffed5adec55968ba0be35d88af5ff0af5f2d7d951b0494`。 |
| S3 | 唯一入口 `general_science_plugin.py`（SHA-256 `4b6de413...`）及资源、组件、Agent、控制声明四模块（依次为 `09482dcc...`、`4cde3bc...`、`1cf128d2...`、`5fb18ca1...`）；旧 `general_transform_operations.py` 不存在。 |
| S4 | `pyproject.toml` 中 `scidiscovery.plugins` 入口、builtin/general/curve/TCAD/InGaAs 插件声明、catalog compiler、Operation invoke、Approval projector、Worker tool 与安装态消费者。 |
| S5 | D4 结构门 `tests/operations/test_r5_general_plugin_split.py`，SHA-256 `924ef6ba...`；通用 Agent、Transform、Approval、curve 跨插件所有权、installed entrypoint 和 TCAD 插件测试。 |
| S6 | 当前计量脚本 `scripts/r5_current_metrics.py`，SHA-256 `453b6e51...`；本轮输出 SHA-256 `6caba73bd0631fd9041f71f4a69f6ed84be1b34745ebd7fe610c5d8aef74b1d2`。 |
| S7 | 冻结生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；冻结快照 `tests/fixtures/r5_structure_inventory.json`，SHA-256 `1b397e2dfea1bc579b2597caf5d3a37f5ef44e40d66b92f509b349b51b77983a`。 |
| S8 | 实施记录 `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`，SHA-256 `ff8bd5b3...`。 |
| S9 | 本轮独立命令记录：61 项聚焦测试、284 项全仓测试、组件导入/种类/目录编译、AST、全局 successor、当前计量和 `git diff --check`。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `single_plugin_authority` | pass | S1—S5, S9 | `pyproject.toml` 只有 `general_science = scidiscovery.general_science_plugin:PLUGIN`；仅入口模块构造一个 `PluginDefinition`，并组装唯一 `COMPONENTS`、`AGENT_OPERATIONS` 和 `CONTROL_OPERATIONS`。 |
| `declaration_responsibilities` | pass | S1—S5, S9 | resources 只持有 Schema/提示/语义合同；components 持有无状态 codec、validator、guard、projector、transform、workspace 与唯一组件元组；Agent/control 模块只声明各自 Operation。子模块没有目录编译、entry-point 扫描、PLUGIN、服务、缓存或状态。 |
| `catalog_shape` | pass | S3—S5, S9 | 插件保持 66 个唯一组件与 17 个唯一 Operation：public/support 为 11/6，Agent/Transform/Approval 为 10/6/1；builtin+general 可由同一 compiler 完整编译，Operation 集合无增减或重复。 |
| `public_cross_plugin_contract` | pass | S3—S5, S9 | 公开组件精确为 workspace、四个 Worker 工具和五个通用 Schema，共十项；curve 与 TCAD 通过显式 PluginDependency/ComponentRef 使用这些公开对象，未直接导入 general 私有源码，也没有跨 owner 重复 implementation。 |
| `implementation_ownership` | pass | S3—S5, S9 | 资源路径全部指向 resources，workspace 与 callable 组件指向 components；每个实现均能从声明路径导入且 kind 匹配。四个 Worker 组件继续解析到 Worker 公共接口中 protocol 所定义的同一对象，没有第二 handler。生产代码不再引用已删除 transform 模块。 |
| `agent_worker_path` | pass | S3—S5, S9 | 十个 Agent Operation 仍从 compiled contract 获得精确 workspace、提示、输入、输出、工具和审查关系；PDF、分析、受控 patch、heartbeat、validate/finalize 继续走唯一 Worker Router/TaskService。 |
| `transform_approval_path` | pass | S3—S5, S9 | 六个 Transform 仍经 `operation_invoke`、精确 guard/validator、Artifact 父链和当前目录执行；证据资格 Approval 仍使用同一 compiled projector/contract、完整 producer family、审计与 UI 决定边界，没有复制 ApprovalService 或专用 UI 分派。 |
| `real_entry_and_installation` | pass | S4, S5, S9 | core clean-wheel 只从标准插件组发现 general 入口；完整组合、daemon/Codex 配置、曲线与 TCAD 编译消费者通过。删除旧模块后无安装态导入、workspace 或动态 loader 残留。 |
| `metrics_and_integrity` | pass | S1, S3, S6—S9 | 原 plugin owner 聚合入口+资源+Agent=1009 行；原 transform owner 聚合组件+control=1333 行；两组及全量 25 个 successor 均无交叠，总计 2342/2551，净减 209。R0 六职责 9776/13657，operations 2056/2060，全生产 60259/62533。 |
| `occam_and_constraints` | pass | S1—S5, S9 | 四个模块对应四个真实变化原因；没有为每个 Schema、Operation 或函数建类/服务/注册表。身份、谱系、最小 Worker 上下文、人工审批、唯一目录和失败关闭边界未退化，未新增科研实体或领域拓扑。 |

## 3. 结构与运行边界判断

### 3.1 单一组装点和一个 compiled catalog

`general_science_plugin.py` 的 19 行只做一次冻结组装；它不复制组件，也不按 Operation id 分派。
resources、components、agent declarations 和 control declarations 都不能独立发布插件或编译目录。
`component_specs()` 仅在组件所有者导入时构造一次不可变元组，不读取环境、entry point 或运行状态，
因此不是第二注册表。

依赖方向是单向的：入口依赖三个声明输出；components 依赖 resources 的实现字符串但不导入其私有
对象；Agent/control 声明只引用 component id；compiler 才统一解析闭包。curve 和 TCAD 插件只使用
显式公开 ComponentRef，未知插件仍须通过同一 compile 门，核心没有新增插件名或领域 Operation 分支。

### 3.2 真实行为没有变成声明副本

资源迁移没有复制 Schema 或提示的运行权威：66 个 ComponentSpec 中的资源实现路径都指向唯一
resources 模块。validator、guard、projector、transform 和 workspace 都指向 components 的唯一实现。
四个 Worker 工具使用稳定 Worker 公共接口路径，但导入结果与 protocol 中定义的对象逐项同一，既不
代理调用也不保留旧 handler。

Agent、Transform 和 Approval 三类 Operation 仍只是数据声明。运行时分别复用 TaskService/Worker
文件生命周期、通用 Transform invoke/Artifact 谱系以及 ApprovalService/固定 ReviewDocument；本次
拆分没有把科学判断放入 projector、把审批写入聊天或建立另一个执行入口。

### 3.3 删除旧模块是实际删除

旧 `general_transform_operations.py` 已不存在，生产及动态入口无引用。相关测试改为从当前 control
declarations 获取公开常量，catalog 负例改指 workspace 的真实 components 所有者；没有增加同名
兼容模块、`sys.modules` 别名、转发函数或双发布 entry point。历史文档中的名称仍作为历史证据保留，
不属于当前运行权威。

## 4. 复杂度与奥卡姆判断

拆分前两个职责总计 2551 行；当前五个文件合计 2342 行，净减 209 行。计量没有把新文件排除：
入口、资源、Agent 声明聚合为 1009 行，组件、Transform/Approval 聚合为 1333 行，所有 successor
在全计量中唯一。全生产也由 D3 的 60468 行降至 60259 行，差值同为 209；因此不是只移动文件。

减量主要来自合并原 Agent/Transform 两侧重复的 codec、Schema 资源和声明辅助，而非多语句压行。
五个文件没有分号串联语句或超长单行数据块。`general_science_components.py` 仍有 862 行，但其中的
validator、guard、projector 和 transform 都共享同一无状态组件 ABI 和冻结元组；继续为每种组件建立
service/factory 会增加装配面，当前没有独立状态或替换边界支持这种扩张。

## 5. 独立运行记录

全部命令在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

```text
pytest -q \
  tests/operations/test_r5_general_plugin_split.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_r4_approval_operation.py \
  tests/operations/test_general_science_plugin.py \
  tests/operations/test_catalog_installed_entrypoint.py
# 61 passed in 40.51s

pytest -q
# 284 passed in 89.32s

PYTHONPATH=src:plugins/curve_score:plugins/tcad_artifact:plugins/ingaas_fig4 \
  python <66 个组件实现导入、kind、十项公开面和 17 个 Operation 编译检查>
# 通过

PYTHONPATH=src:scripts python <两 owner 与全量 successor 唯一性、计量重算>
# 1009 + 1333 = 2342；25 个 successor 全局唯一；全生产 143 文件 / 60259 行

python <五模块 AST/compile 与无第二发现权威检查>
git diff --check
# 均通过
```

未运行真实 Sentaurus、公网抓取或浏览器人工点击：D4 只改变通用插件声明的源码归属，没有修改 solver
adapter、HTTP 算法或 UI 决定写入口；真实审批/Transform/Worker 控制路径、安装态入口和失败关闭负例
已由上述测试覆盖。这些外部未来观测不是当前声明拆分缺失的证据。

## 6. 最终结论

未发现阻断缺陷。通用科学插件仍只有一个入口、一个 PluginDefinition 和一个 compiled catalog；四个
声明模块按真实变化原因解耦，组件与 Operation 数量、公开跨插件合同、审批/Transform/Worker 路径
均未退化。净减 209 行可复现且没有通过搬移或压行制造。

**结论：通过并只放行 D5。**
