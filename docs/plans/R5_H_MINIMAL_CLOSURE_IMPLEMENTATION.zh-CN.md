# R5-H 最小收口实施计划

日期：2026-08-30  
性质：R5-G 结束后的边界、所有权和复杂度收口  
状态权威：本文件说明施工内容；唯一阶段状态仍记录在
`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 26 节。

## 1. 目的

本阶段不继续增加科研流程、状态机或规划抽象，而是修正现有实现已经暴露的四类结构问题：

1. 控制层仍以固定公式替科学 Worker 判断实验优先级；
2. 通用科研 Operation、曲线算法和 TCAD 能力的插件所有权及依赖方向不正确；
3. 运行时仍保留第二套 current 状态、隐藏旧 Worker 工具和两条 Agent 派发候选路径；
4. 审批页面、一次性验收脚本和活动文档仍把历史重量带入当前产品面。

目标不是“重做一个通用科学语义内核”，而是让已经跑通的
`多角色 Agent + OperationSpec + 轻量门禁 + 领域插件` 成为唯一主线。

## 2. 不可退化的边界

本阶段必须保留：

- 不可变、内容绑定的 Artifact 及精确父链；
- 唯一 current 与 qualification 权威；
- Task、Approval、Execution 的既有生命周期、幂等和恢复语义；
- 科学判断由调度 Agent 和专业 Worker 承担；
- 确定性代码只做机械变换和显式 Metric；
- 外部副作用只由领域 adapter 执行，并绑定精确人工授权；
- Agent 之间只通过显式输入文件和封存输出文件通信；
- 一个 `scidiscovery.plugins` 注册入口和一个启动时 `CompiledCatalog`；
- `public`、`support`、`internal`、`all` 只是同一目录的投影；
- 新领域不得要求修改核心、通用调度器、通用 UI 路由或增加插件名 allowlist。

33 项基本架构约束继续作为行为验收矩阵使用，不为每一项新增运行实体、收据或状态。

## 3. 明确不做

- 不增加科学知识图、通用科研规划器或固定阶段 DAG；
- 不增加 `OperationRun`、插件生命周期状态机、数据库表或第二注册表；
- 不把 R5-G/D4-H2 的一次性科研链固化为产品流程；
- 不为历史文件建立在线兼容层；确需读取时只允许一次性离线工具；
- 不用机械拆文件掩盖职责未减少；
- 不把提示词中的原生工具禁用声明宣传为生产级沙箱；
- 不在本阶段接入第二条正式 Agent 派发路径。

## 4. 目标所有权

```text
轻量核心
├── Artifact / Task / Approval / Execution
├── OperationSpec 编译、统一目录、preflight 与 invoke
├── Worker 受控文件生命周期和服务端领域工具门禁
└── 不拥有科研优先级、曲线算法或 TCAD 规则

通用科研插件
├── 证据提取与审查
├── 假设提出、批评与审计
├── 实验设计、修订与设计审查
└── 结果审查和通用诊断

曲线分析插件
├── 曲线数据结构、归一化、对齐和确定性指标
└── 曲线比较及曲线专用诊断；不依赖 TCAD

TCAD 插件
├── 参数、Deck 编写/审查/调试、工程封装和求解器 Effect
└── 需要曲线分析时由 TCAD 单向依赖曲线插件
```

领域插件可以注册领域专用实验 Operation 和 Artifact 契约，但不能覆盖通用 Operation，不能向核心
注入分支，也不能拥有通用科研角色。

## 5. 施工原则

每个子阶段按同一顺序执行：

1. 用真实注册、安装和调用路径列出生产、动态插件、测试、文档和历史消费者；
2. 冻结修改前正例与负例；
3. 只修改一个可独立验证的责任边界；
4. 运行聚焦测试、安装后入口测试和负向测试；
5. 记录净删除、迁移和新增代码，不把移动伪装成减重；
6. 冻结精确 diff，由未参与实现的独立审查者检查正确性、33 项约束和设计目标；
7. 审查未通过只允许返修当前阶段，不得进入下一阶段。

现有工作树包含未提交的 R1～R5 成果。任何修改必须保留这些成果，不得使用破坏性 Git 命令，
也不得顺手清理 `123/`、`deliverables/`、运行状态或用户资料。

## 6. H0：恢复唯一设计真相和删除清单

### 6.1 改动

- 将主计划第 26 节更新为 D4-H2 已结束、R5-G 工程闭合、科学验收停止、UI 可读性未通过；
- 把 33 项约束恢复为当前活动的精简行为矩阵，并为每项关联实现或测试证据；
- 冻结四组安装矩阵：核心、核心加通用科研、再加曲线、再加 TCAD；
- 调查并分类以下表面的全部消费者：
  - `research_state.py` 与 `research/current.yaml`；
  - `_LEGACY_WORKER_TOOLS` 和旧 Worker 路由；
  - `curve_score` 中的通用科研 Operation；
  - 核心曲线 Schema/算法；
  - `agent_dispatch.py` 与 `codex_worker.py`；
  - R5-G/D4-H2 一次性脚本和测试；
- 修正部署默认插件与安装文档不一致的问题；
- 冻结修改前的目录摘要、导入依赖、生产代码行数、测试集合和干净 wheel 行为。

### 6.2 完成门

- 活动架构、主计划和实际实现状态一致；
- 每个待删除或迁移表面都有真实生产消费者结论；
- 没有运行行为变化；
- 独立审查确认删除清单不会破坏承重不变量。

## 7. H1：把实验优先级判断还给 Agent

### 7.1 改动

- 从通用实验 Schema、物化器和 Validator 删除固定科研优先级公式及按该公式拒绝排序的行为；
- Agent 继续输出候选顺序、理由、依据和不确定性；
- 控制层只验证候选引用存在、排序完整、无重复以及合同字段齐全；
- 如某领域确实需要确定性评分，由该领域注册带版本的 `support` Metric Operation；
- Metric 输出只能成为 Agent 可引用的输入，不能成为核心强制科研结论。

### 7.2 完成门

- 合法的 Agent 自主排序不因固定公式不同而被拒绝；
- 缺项、重复、未知候选和不完整合同仍被拒绝；
- 核心没有新增权重、阈值、Scorer 注册表或隐藏 readiness；
- 独立审查确认科学所有权已恢复。

## 8. H2：修正插件所有权和依赖方向

### 8.1 H2a：迁移 Operation 所有权

- `general_science` 继续作为独立 `PluginDefinition` 由基础 AI 科学家 wheel 发布；不为形式上的
  插件独立性再拆一个只有 entry point 的空壳 wheel；
- 将实验设计、完整对象修订、实验计划审查、目标投影、计划物化和基于通用
  `ValidationReport` 的知识更新从 `curve_score` 迁到 `general_science`；
- 当前 `science.result.diagnose.v1` 实际消费 curve consistency report/bundle，并非通用诊断；H2a
  不把它伪装迁入通用插件，H2b 将其与 curve-error diagnosis 一并收敛为曲线专用 Operation；
- 基于 `LayeredDiagnosisReport` 的知识更新在 H2a 仍由曲线插件声明，因为该报告当前直接嵌入
  曲线分析对象；其确定性 reducer 和通用输出合同由 `general_science` 公开组件提供，不复制实现；
- 曲线插件在 H2a 后只注册仍依赖曲线数据和算法的诊断与确定性 Operation；
- 保持同一 OperationSpec 编译、preflight 和 invoke 路径，不建立代理注册层；
- 先保持数据合同尽可能不变，避免所有权迁移与 Schema 重写同时发生。

完成门：实际基础 wheel（builtin + general_science）即可发现通用实验角色；未安装曲线或 TCAD
时仍能编译目录并运行实验 intent→materialize→独立 review 的结构闭环。

### 8.2 H2b：迁移 Schema 和算法所有权

- 通用实验计划只保留研究问题、假设、干预、观测、判据、成本风险、排序和理由；
- 曲线轴、曲线束、曲线对齐、曲线指标及曲线专用诊断归曲线插件；
- TCAD 求解器证明、设备参数、工程封装和运行 adapter 归 TCAD 插件；
- 删除 `curve_score -> tcad_artifact` 依赖，按需改为 `tcad_artifact -> curve_score`；
- 增加一个最小非曲线盲插件，证明接入不修改核心、通用调度器、UI 和部署代码。

### 8.3 H2 目标安装验收矩阵

`builtin` 与 `general_science` 是同一基础 wheel 发布的两个独立插件定义；这属于发行组合，不是
第二注册表。下表是 H2 目标，不是 H0 当前事实：

| 安装组合 | 必须出现 | 禁止出现 |
| --- | --- | --- |
| 基础 AI 科学家 wheel | builtin 生命周期组件 + general_science 通用角色闭环 | 曲线与 TCAD Operation |
| 基础 wheel + 曲线 wheel | 通用角色 + 纯曲线结构和确定性分析 | TCAD 求解器能力 |
| 基础 wheel + TCAD wheel | 通用角色 + TCAD 参数、Deck、调试和 Effect | curve 插件反向依赖 TCAD |
| 基础 + 曲线 + TCAD | 两个领域插件按声明依赖组合 | 核心中的领域分支 |

H2a 和 H2b 分别独立审查，不允许用全量安装掩盖 core-only 或 general-only 的依赖泄漏。

## 9. H3：删除重复状态和隐藏兼容面

### 9.1 改动

- 删除运行期第二套 `research_state.py` current 权威和部署脚本对 `research/current.yaml` 的校验；
- 仅在确认存在必要输入时保留一个发布包外的一次性离线读取工具；
- 迁移剩余 TCAD 与测试消费者后删除 `_LEGACY_WORKER_TOOLS`、旧路由和旧 capability；
- 旧工具直接调用必须得到“未知工具”，不能只从 `list_tools` 隐藏；
- 删除确认零消费者的旧插件别名和旧数据库兼容迁移；
- 不修改 Artifact、Task、Approval、Execution 的持久化语义。

### 9.2 完成门

- current 只有数据库/绑定服务一个运行权威；
- Worker 只有当前受控文件工具和 Operation 声明的领域工具；
- 生产代码净删除，且没有新转发器代替旧接口；
- 干净 wheel 安装、重启和历史终态读取通过。

## 10. H4：明确 Worker 原型与生产隔离边界

### 10.1 当前版本

- `spawn_agent` 继续作为唯一开发调试派发路径；
- 服务端继续精确拒绝未声明的 Worker MCP 和领域工具；
- 编译提示明确列出允许和禁止的 Codex 原生工具，但文档必须说明这不是技术隔离；
- 调试模式不得加载生产凭证、执行不可逆动作或据此宣称满足生产最小权限。

### 10.2 后续版本基座

- 保留 `agent_dispatch.py` 与 `codex_worker.py`，但从当前正式路径中明确标为实验性；
- 本阶段不把它们接成第二条正式派发路径；
- 后续只有在独立进程完成上下文、原生工具、MCP、网络和文件沙箱验证后，才可成为唯一生产派发路径；
- 一旦成为生产路径，`spawn_agent` 只能保留为明确的开发模式。

### 10.3 完成门

- 代码、配置和文档对“当前能强制什么”给出同一个答案；
- 运行时不存在两个都被称为正式的 dispatcher；
- 独立审查确认没有把提示词约束误当成安全边界。

## 11. H5：审批 UI 可读性

### 11.1 改动

- 首屏显示决策问题、关键结果、限制、来源和待批准事项；
- 编译 projector 产生的安全摘要默认展开；
- 原始 subjects 默认折叠，保留精确查看和下载，不默认展开完整 JSON；
- 插件仍不得提供 HTML、脚本或自行决定安全展示结构；
- 用真实 D4 资格审批数据验证桌面和窄屏。

### 11.2 完成门

- 用户无需阅读原始 JSON 即可判断批准对象、依据和风险；
- UI 决定仍绑定原始精确 cohort，展示重排不改变科学字节；
- DOM 安全测试和真实可读性评审均通过。

## 12. H6：归档一次性验收表面并重新评估巨型文件

### 12.1 改动

- 保留 R5-G/D4-H2 封存输入、结果摘要、指纹和最小复现说明；
- 一次性场景脚本和测试移出默认发布包与默认回归，不泛化成产品工作流；
- 历史计划和审查报告移出活动阅读路径，发布包只带当前架构、当前计划、关键决策和用户文档；
- 完成删除后再重算巨型文件责任；只按内聚责任拆分，不增加服务、状态、表或注册表。

### 12.2 允许的后续拆分

- Worker 输入物化、编辑/快照和 finalize；
- 实例会话、语义绑定/current 和管理清理；
- Agent、Transform、Approval、Effect 的 Root 执行处理器。

### 12.3 完成门

- 活动发布面不再携带一次性科研编排；
- 拆分前后权威数量不变；
- 只有发现经消费者审计证实的死生产表面才要求净删除；否则生产代码不得增加，默认测试/仓库入口
  和发布体积必须有可解释的净下降。

`123/`、`deliverables/`、运行状态和用户数据不在自动删除范围；仓库卫生清理须另获用户授权。

## 13. H7：分层回归和最终审查

按以下顺序串行执行，WSL 进程内存上限不得超过 8 GiB：

1. 静态导入、插件所有权、目录确定性和旧接口负例；
2. 四组安装组合和干净 wheel 启动；
3. Operation preflight/invoke、Worker 文件生命周期、独立 review、Approval 和 Effect 聚焦回归；
4. 真实拉起一个通用 Agent 和一个 TCAD Agent，验证受控输入、获准原生工具、注册领域工具、
   禁止工具拒绝和完整文件 finalize；
5. 最小非曲线盲插件零核心改动验收；
6. 有界 TCAD 假执行结构闭环；
7. 完整测试套件串行回归；
8. 只有在精确 UI 授权后才进行真实外部求解器回归；未授权时合法停止；
9. 最终独立工程审查与独立架构审查。

最终审查必须同时确认：

- 控制层不再替 Agent 做科研判断；
- 通用科研能力不再依赖曲线或 TCAD；
- 新领域不修改核心和通用调度器；
- 只有一个目录、一个 current 权威和一条正式派发路径；
- 经消费者审计存在死生产表面时生产代码净减少；否则生产代码不得增加；任何情况下均不得增加
  针对 D4-H2 的特例，默认测试/仓库入口和发布体积必须净减少；
- 33 项行为约束没有退化；
- 真实安装入口和负例通过，而非仅单元测试通过。

## 14. 状态记录

本节只记录子阶段证据，不是状态权威；状态变更必须同步到主计划第 26 节。

| 子阶段 | 初始状态 | 进入条件 | 完成见证 |
| --- | --- | --- | --- |
| H0 | 通过 | R5-G 工程收口、科学停止门已触发 | `reviews/R5_H_H0_INDEPENDENT_REVIEW.zh-CN.md` 第二轮通过；39项测试与差异检查复核通过 |
| H1 | 通过 | H0 通过 | 固定评分/排序否决已删除；两层六组排列负例关闭；独立六文件89项通过，`reviews/R5_H_H1_INDEPENDENT_REVIEW.zh-CN.md` 第二轮放行 |
| H2a | 通过 | H1 通过 | 第二轮独立审查通过；真实基础 wheel 17项，独立101项测试与结构探针通过；见 `reviews/R5_H_H2A_INDEPENDENT_REVIEW.zh-CN.md` |
| H2b | 通过 | H2a 通过 | 第五轮独立审查通过；离散色带、全色域容差、半像素语义和正式来源绑定均闭合；见 `reviews/R5_H_H2B_FIFTH_INDEPENDENT_REVIEW.zh-CN.md`，放行 H3 |
| H3 | 通过 | H2b 通过 | H3-A/H3-B/H3-C/H3-D 均通过独立审查；唯一 current、唯一 Worker 文件协议、安装重启与发布清单闭合，见 `reviews/R5_H3_D_RELEASE_AND_TOTAL_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`，放行 H4 |
| H4 | 通过 | H3 通过 | 正式路径仍只有 `spawn_agent`；独立进程代码仅标为未启用实验基座，运行逻辑零变化；独立实现审查通过，放行 H5 |
| H5 | 通过 | H4 通过 | 两项阻断返修后第二轮独立实现复审通过；49项聚焦、317项Operation、38项部署/平台/架构约束通过，仅放行H6 |
| H6 | 通过 | H5 通过 | H6-C 第二轮独立复审确认六个零消费者表面删除、唯一发布清单和职责边界均闭合；40项聚焦、292项Operation、38项架构/部署复测通过，见 `reviews/R5_H6_C_RESPONSIBILITY_AND_TOTAL_CLOSURE_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` |
| R5-L | L2 实施中 | L0、L1 第二轮独立实现复审通过；S0/S1保留，旧S2冻结为加固后端候选 | 实现本地可信最小 Run；L2独立审查通过前不得进入L3、S3或H7 |
| H7 | 暂停 | R5-L 通过 | R5-L 逐阶段实现和总审查通过后再恢复 |

## 15. H0 消费者调查冻结

调查基于当前工作树、启动 entry point、部署脚本和生产 import 路径；测试、文档与历史消费者单独列出，
不能用符号搜索直接证明可删除。

| 表面 | 生产消费者结论 | 测试/历史消费者 | H0 处置结论 |
| --- | --- | --- | --- |
| `research_state.py` | 唯一当前入口是 `deploy/install.sh` 在 workspace 存在 `research/current.yaml` 时调用 CLI validate；运行服务无 import | 旧 TCAD 报告与历史计划引用 | H3 删除安装入口和运行包；不做在线兼容 |
| `_LEGACY_WORKER_TOOLS` | Worker router 仍可分派12个隐藏工具；只有 TCAD 插件显式注册 `worker_read_input` | `ARCHITECTURE_TEST_PLUGIN` 夹具注册旧读取工具；baseline/兼容测试及部分现场脚本依赖 | H3 迁移一个生产声明和一个架构夹具，再删除路由；负例必须返回未知工具 |
| 通用科研 Operation | `curve_score.science_operations` 当前拥有实验设计/修订、通用审查、诊断与知识更新 | curve 和 TCAD 测试通过全插件安装掩盖依赖 | H2a 迁入 `general_science`，不增加代理注册层 |
| 核心曲线 Schema/算法 | `schema/experiment.py` 直接导入 curve 类型；`curve_score.py` 与 `curve_analysis.py` 位于核心 | 多个 Operation/测试直接 import | H2b 先切断通用实验合同，再将曲线实现归插件 |
| `curve_score -> tcad_artifact` | wheel 与 PluginDefinition 均声明该反向依赖 | 完整安装测试未暴露 general-only 缺口 | H2b 删除；按需改为 TCAD 单向依赖 curve |
| 独立 Codex 进程 dispatcher | `agent_dispatch.py` 仅由自身引用 `codex_worker.py`，当前生产启动与 Root 路由无调用者 | 专项测试和现场脚本使用 | H4 保留为实验性加固基座，不接成第二正式路径 |
| R5-G/D4-H2 脚本 | 无产品入口，固定实例名、状态路径与冻结摘要 | `test_r5_g_science_chain_runner.py`、`test_r5_g_hypothesis_stage_runner.py`、两个 revision runner、`test_r5_frozen_baselines.py` 和历史评估文档引用 | H6 保存封存证据后移出默认发布/回归 |
| `builtin_plugin.PLUGIN` | 模块级 `PLUGIN = CORE_PLUGIN` 兼容别名无生产消费者 | 未发现当前测试 import 该别名 | H3 与其他零消费者兼容面一并删除 |
| scheduler legacy instance migration | 初始化数据库时仍扫描旧 `current_instances` 并写入 legacy instance | 历史兼容测试间接覆盖 | H3 在确认当前状态根不依赖后删除；本重构明确不兼容历史文件 |

H0 已发现的直接架构缺陷记录在
`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`，状态使用 `known_issue`，未验证项保持
`pending_review`，不得继承 2026-08-24 历史 candidate 的 `conformant` 结论。

### 15.1 H0 冻结基线

- 当前 Git 分支/提交：`baseline/8765-codex` / `404aeb14c6ebc4b08bac599db91eaee54c103f48`；
- `src/ + plugins/` Python 生产代码：59,061 行；
- R0 六项核心责任按当前 successor 聚合：9,642 行，8765 基线为13,657行；
- 重复/待迁移重点表面：`research_state.py` 468行、核心 curve schema/analysis 2,448行、实验性
  独立进程派发基座979行、Worker protocol/dispatch 1,169行；
- 当前真实安装/诊断组合：
  - 仅 builtin：只作编译诊断，当前失败于 `component_unused/builtin/assignment_materialize_tool`，
    不是可安装产品组合；
  - 当前基础 wheel：同一个 `scidiscovery` wheel 发布 builtin + general_science，11个 Operation；
  - 当前基础 wheel + tcad_artifact：28个 Operation；
  - 目标基础 wheel + curve_score：当前无法安装，curve 插件错误依赖 `tcad_artifact`；
  - 当前完整安装：基础 wheel + tcad_artifact + curve_score，共43个 Operation；
  - InGaAs 项目插件是完整安装上的可选项目插件，不属于通用默认组合；
- H0 精确命令 `pytest -q tests/operations/test_architecture_constraint_matrix.py
  tests/artifact_agent/test_deploy_scripts.py tests/operations/test_catalog_installed_entrypoint.py`：39项测试通过；
  `git diff --check` 作为另一个机械检查单独通过。

上述失败是 H2 的待修基线，不得通过测试夹具默认安装完整插件加以隐藏。旧
`r5_baseline_metrics.py` 的领域正则只作为历史趋势，不再作为核心领域中立性的通过证明；H2/H7 改用
真实 import 依赖、wheel 组合和 catalog 所有权断言。

### 15.2 H0 精确文件范围

H0 只新增或修改以下文件；累计工作树中的其他 R1～R5 文件不属于本阶段 diff：

- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第26节；
- `docs/plans/README.md` 当前计划索引；
- `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
- `docs/ARCHITECTURE.md` 与 `docs/ARCHITECTURE.zh-CN.md` 的当前状态入口；
- `docs/INSTALL.md` 与 `docs/INSTALL.zh-CN.md` 的默认插件说明；
- `tests/operations/test_architecture_constraint_matrix.py`。

H0 不修改 `src/`、`plugins/`、`deploy/` 或数据库文件，不改变运行行为。

## 16. H2a 实施记录

### 16.1 所有权结果

- 基础 wheel 仍只通过统一 `scidiscovery.plugins` 入口发布 `builtin` 与
  `general_science` 两个 `PluginDefinition`，未新增注册表或代理层；
- `general_science` 现在直接拥有：
  `science.experiment.design.v1`、`science.experiment.revise.v1`、
  `science.object.review.v1`、`science.objective.project.v1`、
  `science.experiment.materialize.v1` 和
  `science.knowledge.update.validation.v1`；
- `curve_score` 的科学 Operation 只剩
  `science.result.diagnose.v1`、`science.result.diagnose.curve-error.v1` 和
  `science.knowledge.update.diagnosis.v1`；前两项消费曲线报告，后一项消费当前仍含曲线对象的
  `LayeredDiagnosisReport`；
- 完整目录仍为43项，迁移没有删除科学能力；基础目录由11项增至17项；
- 曲线诊断跨插件只引用通用插件明确公开的 workspace、工具、实验/审查 Schema 和知识 reducer，
  编译器继续执行依赖与 `public` 边界校验。

### 16.2 文件责任

- `general_science_experiment_operations.py`：只声明三项 Agent Operation 与三项确定性
  support Operation；
- `general_science_experiment_components.py`：只实现对应资源、Validator、Guard 和 reducer；
- `curve_score.science_operations`：由1,029行收敛为579行，只保留曲线诊断责任；
- `general_science_plugin.py`：仍是通用插件唯一组合点，不建立子注册表。

### 16.3 已执行验证

- 基础目录、基础加 TCAD、完整目录直接编译分别得到17、34、43项；
- 通用科学、通用变换、曲线插件聚焦回归：37项通过；
- 干净 wheel 目录入口：7项通过；
- TCAD 消费者回归：12项通过；
- 基础 wheel/约束矩阵/InGaAs/R4 审批与执行身份回归：55项通过；
- 以上去重后本阶段聚焦命令共111项通过；`py_compile` 与 `git diff --check` 通过；
- 基础 wheel 不导入任何外置 `curve_score`、`tcad_artifact` 或 `ingaas_fig4` 包；核心内部
  实验 Schema 仍会导入曲线结构，这是 H2b 的已知缺陷，H2a 不据此宣称 Schema 已领域中立。

### 16.4 审查门

H2a 第二轮独立审查已通过，只放行 H2b。报告：
`reviews/R5_H_H2A_INDEPENDENT_REVIEW.zh-CN.md`；SHA-256：
`93cb6d60f2aa497010b30aadc8c7f112fdbc6db29541fb6600c9a935e764f0c7`。核心内部曲线
Schema/算法泄漏和 `curve_score -> tcad_artifact` 反向依赖仍是 H2b 的阻断项。

## 17. H2b 详细执行顺序

H2b 不用一次巨型改写同时改变所有合同，按以下可验证顺序执行，但只有全部完成并经独立审查后
才放行 H3：

1. **通用实验合同去领域化**：`ExperimentDesignIntent` 与 `ExperimentPortfolio` 只保留研究
   目标、假设、干预/变量、案例、观测、可识别性、验证判据、成本风险、排序与理由；删除曲线轴、
   series、对齐、operator 和 floor mask 字段。通用 Validator 只检查结构、上下文和科学父链，
   不校验曲线算子。
2. **曲线合同独立成 Artifact**：曲线插件提供带 `experiment_key` 的
   `CurveExperimentContract`、确定性 Validator，以及问题提出者/独立审查者 Operation；曲线评分、
   覆盖和诊断显式消费该合同，不从通用实验计划中偷取领域字段。
3. **Schema/算法物理归位**：曲线数据结构、评分、残差分析和目标覆盖实现移入
   `plugins/curve_score`；核心不得 import 外置曲线包。通用 `LayeredDiagnosisReport` 不再嵌入曲线
   分析对象，曲线分析以单独的受验证输出存在。
4. **依赖方向修正**：SProcess/TCAD runtime manifest 与 attestation 的适配 Operation 归
   `tcad_artifact`；纯曲线插件不 import 或依赖 TCAD。TCAD 如需曲线能力，只能声明
   `tcad_artifact -> curve_score` 单向依赖。
5. **最小非曲线盲插件**：只用公开 OperationSpec/组件合同注册一个表格型观察分析能力，禁止
   修改核心、调度器、UI、部署或插件 allowlist；验证通用实验设计、物化、独立审查和领域工具
   组合。
6. **分层验证**：先验证基础 wheel 不加载任何曲线模块，再验证基础+曲线、基础+TCAD、完整组合，
   最后执行 TCAD 聚焦回归与非曲线盲插件回归。不得用完整安装掩盖任一独立组合失败。

H2b 禁止新增通用领域扩展注册表、Schema 路由器或 Planner；领域合同就是普通插件 Artifact，
只能通过其 OperationSpec 的显式输入输出进入现有编译、preflight、invoke、review 和文件生命周期。

## 18. H2b 候选实施记录

> 本节记录首轮候选，已被第19节所列独立审查打回；其中17/19项基础目录计数和298项回归数
> 不再代表当前实现。第二轮候选及其重新验证证据以第20节为准。

### 18.1 通用合同与领域合同

- 通用 `ExperimentDesignIntent`、`ExperimentPortfolio`、`ResearchObjectiveContract` 和
  `LayeredDiagnosisReport` 已删除曲线轴、序列、比较算子、曲线目标绑定和曲线分析对象；
- `curve_score` 插件拥有 `CurveExperimentContract`、规范曲线、曲线评价、残差分析和目标覆盖；
- `science.curve.contract.design.v1` 与 `science.curve.contract.review.v1` 分别承担曲线合同提出和
  独立审查，评分、覆盖与诊断均显式消费该合同；
- 通用实验计划与曲线合同之间的确定性校验要求实验身份一致，且每个曲线算子与通用验证检查在
  评价器、指标、阈值、单位和覆盖集合上精确一一对应。

### 18.2 插件所有权和依赖方向

- SProcess log、PLX、runtime manifest 和 attestation 的解析/适配已迁入 `tcad_artifact`；
- 纯曲线插件不再导入或依赖 TCAD；TCAD 通过公开组件引用声明单向 `tcad_artifact -> curve_score`
  依赖，并注册 `tcad.curve-bundle.sprocess-plx.v1` 与
  `tcad.curve-bundle.sprocess-log.v1` 两项适配操作；
- 通用执行服务继续把外部输出登记为 `opaque`，TCAD 适配器在自己的边界内严格解析原始字节，
  没有为领域格式修改通用执行存储；
- 删除了迁移后无消费者的旧曲线组合帮助函数和 TCAD manifest 目录资源，没有建立兼容转发器。

### 18.3 非曲线盲插件

新增 `plugins/table_observation`，它只通过现有 `scidiscovery.plugins` 入口声明两项 Agent
Operation、独立 review 边和一个确定性表格工具。该插件未修改核心、通用调度器、UI、部署脚本
或 allowlist。测试通过编译后的 Operation 工具集合真实调用 `worker_table_summarize`，并验证
受控输入读取、确定性结果和工具活动收据。

### 18.4 候选验证

- 基础目录17项、基础加曲线26项、基础加表格19项、曲线与 TCAD 完整目录45项均从同一个编译器
  生成；纯曲线插件的声明依赖中不存在 TCAD；
- 通用科学、曲线、TCAD、审批、安装入口、目录负例及全部默认 Operation 测试共298项通过；
- H2b 专项4项通过，包括通用合同词汇负例、曲线绑定、四种目录组合和编译后领域工具实调；
- `table_observation` 可独立构建 wheel；`compileall`、`git diff --check` 和曲线反向依赖扫描通过；
- 基础干净 wheel 回归确认不会导入 `curve_score`、`tcad_artifact` 或 `ingaas_fig4`。

本候选状态为“待独立审查”。以上证据不自行宣称 H2b 通过，也不放行 H3。

## 19. H2b 首轮打回后的返工顺序

首轮独立报告为 `reviews/R5_H_H2B_INDEPENDENT_REVIEW.zh-CN.md`，结论“打回”。返工不得
放宽 producer admission，也不得把手工 Artifact 当作生产路径证明，按以下顺序执行：

1. **闭合受审对象链**：所有消费真实 materialized experiment plan 的 Operation 显式绑定
   `experiment_review`；所有消费曲线合同的 Operation 另行绑定 `curve_contract_review`。端口
   使用现有 `ScientificReview` Schema、精确生产者审查准入和上下文校验，不复制资格逻辑。
2. **迁出曲线图证据纵切面**：把 `figure_evidence` 曲线 Schema、曲线图提取/审查 Operation、
   Validator、skill/scripts 和工具实现迁入 `curve_score`；从通用 Worker dispatch 删除按固定
   曲线脚本名挂载的分支。通用层只保留领域无关的文件/PDF/图像访问和受控文件生命周期。
3. **真实非曲线路径**：表格工具复用通用活动或只依赖注册工具收据；测试必须从 Root invoke
   创建 Task，经 WorkerMCP claim/materialize/领域工具调用/受控写入/validate/finalize，并验证
   未声明工具拒绝和精确收据。
4. **干净安装矩阵**：增加基础、基础加曲线、基础加 TCAD（依赖解析安装曲线）、基础加表格和
   完整组合的 wheel 探针；每组校验 entry point、Operation 必须项/禁止项，领域工具至少真实调用
   一次。默认测试入口不得依赖手工 `PYTHONPATH`。
5. **删除死表面并复审**：删除零消费者的曲线 readiness 投影和构建残留；执行生产路径正例、
   缺失/错对象/非通过审查负例、全量 Operation 回归、静态边界扫描和差异检查，再冻结第二轮候选。

只有第二轮独立审查明确“通过”才可把 H2b 改为通过并进入 H3。

## 20. H2b 第二轮候选实施记录

### 20.1 真实审查链与唯一准入权威

- 曲线合同提出/审查、曲线评分、参考覆盖、目标覆盖、两种诊断和两种 TCAD 曲线适配均显式消费
  `experiment_review`；消费曲线合同的后续操作同时显式消费 `curve_contract_review`；
- 表格观察提出/审查显式消费精确计划审查，审查输入为 `handoff_only`，没有向科学 Worker 泄露
  控制身份；
- 控制面仍只使用现有 producer-output admission。`ProducerOutputFamily` 从编译 review 边只携带
  资格投影实际使用的 reviewer operation 和 subject outputs；reviewer input port 仍由现有编译与
  Task 审查准入校验，不在生产者族中重复保存。通用资格 projector 据此核验完整
  生产者族，不再按 figure operation id、普通生产者 id 或固定 `validation_reports` 端口分支；
- 新生产路径测试从 `science.experiment.materialize.v1` 真实输出开始，完成计划 review、曲线合同
  Agent、曲线合同 revise 审查与 pass 审查，并验证缺失、错对象、非 pass 三种审查均失败关闭；
  同一个通过链可放行 SProcess PLX/log 适配、曲线评分、参考覆盖和两种诊断；
- 全目录用途扫描新增生产者 `allowed_input_usages` 与消费者 `usage` 的绝对断路负例。由此发现并
  修正曲线合同、目标合同和 TCAD deck 输入把“既定合同”误标为 `claim_evidence` 的问题，统一为
  `prior_signal`；InGaAs 冻结 scorer 的 project 输入则与真实 deck 生产者统一为
  `claim_evidence`。

### 20.2 曲线图证据纵切面归位

- `figure_evidence` Schema、bundle validator、曲线图提取/独立审查 Operation、prompt 和确定性
  `worker_curve_figure_validate` 工具均由 `curve_score` 插件一次注册；
- 通用 `general_science` 只公开领域无关的 JSON/opaque codec、通用 intake/audit Agent、Schema、
  prompt、workspace、PDF 和受控分析原语；基础目录不再包含两项 figure Operation；
- 通用 Worker dispatch 已删除按 `digitize_plot.py`、`render_curve_support.py`、
  `validate_evidence_bundle.py` 文件名查找、挂载和授权的全部分支；根技能、基础 wheel、安装器和
  发布构建器不再分发 `scientific-paper-evidence`；
- 图证据 Agent 先暂存 manifest 与附件，再调用已注册工具生成精确 validation report；最终 bundle
  validator 独立重算并逐字节比对。真实 Worker 测试经过 claim、materialize、领域工具调用、受控
  文件写入、validate 和 finalize，而不是直接调用 handler。

### 20.3 非曲线纵向路径与安装矩阵

- 表格插件真实测试从 materialized plan 与 pass review 开始，经 Root invoke 创建 Task，随后由
  `WorkerMCPRouter` claim/materialize，调用 `worker_table_summarize`，写入、校验并 finalize 主
  输出，再创建并完成独立表格审查；工具复用通用活动
  `deterministic_analysis_completed`，不向核心增加领域活动名；
- 干净 wheel 探针覆盖基础、基础加曲线、基础加表格、基础加 TCAD（只指定 TCAD wheel，由依赖
  解析安装 curve）和完整组合；每组从唯一 `scidiscovery.plugins` entry point 编译并检查必需项、
  禁止项，领域工具在安装态真实调用；
- 当前目录计数为基础15项、基础加曲线26项、基础加表格17项、曲线加 TCAD 完整组合45项；
  `public/support/internal/all` 仍是同一 `CompiledCatalog` 的投影，不存在第二注册表。

### 20.4 删除与复杂度说明

- 已删除零消费者的 `project_objective_readiness` 及两个投影类型、旧论文曲线技能、核心曲线图
  Schema/validator 和构建残留；静态扫描确认通用 `src`、基础 `pyproject`、部署与发布脚本没有
  figure operation id、figure Schema、旧脚本名或旧技能分发；
- 第二轮候选生产 Python 为150个文件、59632行；相对首轮候选增加2个文件、125行，增量对应
  插件自有的 figure Operation 声明和一个真实注册校验工具，不是新注册表、路由器、状态机或
  兼容转发器。`operations/` 仍为7个文件、2064行，通用科学两组职责聚合由2536行下降为2212行；
- 全工作树相对8765基线的 `src + plugins` 仍为大幅净删除。禁止为保持候选快照而压行或把实现
  移出统计范围；第二轮精确规模已由结构测试重新冻结。

### 20.5 当前门状态

第二轮候选状态为“待独立审查”，不是“通过”。冻结验证证据如下：

- `tests/operations`：302项全部通过，包含五种干净 wheel 组合、真实计划/曲线合同审查链、真实
  表格 Worker 链和插件注册图证据工具；
- 部署与平台配置：37项全部通过；减法后的资格/目录/Root/Task 聚焦复核51项通过，后续54项结构
  与运行时复核通过；
- `git diff --check` 通过；通用边界、旧图证据脚本/技能分发和死 readiness 静态扫描无命中；
  `src + plugins` 相对8765基线增加2557行、删除25356行，净删除22799行；
- 生产代码150个文件、59632行，`operations/` 7个文件、2064行，Root 聚合2959行；为遵守减法
  原则，已从生产者族删除未参与判定的重复 `reviewer_input_port` 字段。

只有新的独立审查报告明确“通过”，才可把 H2b 标记为通过并进入 H3。

## 21. H2b 第二轮打回后的最小修复计划

第二轮独立报告为 `reviews/R5_H_H2B_SECOND_INDEPENDENT_REVIEW.zh-CN.md`，报告摘要
SHA-256 为 `9e0d928c94bbc6325c9c4b09602d0f8b5f9dea1066e8ba4b3589375defc3cb31`，结论“打回”。
本轮只关闭报告指出的三条生产缺口，不借机增加控制面概念。

### 21.1 删除控制面的曲线解释

- 删除通用 Task 输出错误提示中对曲线绑定和系列角色的字符串判断；
- 通用层只保留 JSON、必需字段、类型和受控文件生命周期等领域无关提示；
- 对整个 `src/scidiscovery` 增加已知曲线科学语句的负扫描；不新建提示注册表、错误路由器或
  插件回调接口。

### 21.2 在曲线插件内补齐最小、确定性的图证据生产工具

- 保留现有成品 bundle 校验工具，同时在 `curve_score` 插件的同一 Worker 工具组件中注册一个
  配置驱动的曲线数字化工具；图像读取、显式色彩系列提取、坐标换算、CSV、来源图、完整观测
  支撑叠图、manifest 和校验报告均由该插件实现；
- 工具只接受显式面板坐标、轴标定、系列颜色和身份绑定，不做 OCR、不猜标签、不推断缺失单位；
  假图像、无匹配像素、点数不足或身份未绑定均在写入正式集合前失败关闭；
- 图证据 Agent 的正式路径必须调用该版本化注册工具，不得用临时 `worker_run_analysis` 代码产生
  可升格的曲线证据；最终仍由现有 bundle validator 独立重算；
- 实现复用现有 Worker 输入读取、输出目录、collection、注册工具收据和 finalize，不增加
  Registry、Schema Router、Task 状态、控制面分支或第二条文件生命周期。

### 21.3 补足真实调用证据

- 源码态增加真实 PNG 到 CSV/来源图/支撑叠图/manifest/报告，再到 validate/finalize 的
  Root/Task/Worker 正例；假 PNG 和像素不匹配验证失败且不留下正式科学集合；
- 表格真实 Worker 路径断言精确注册工具收据，并实调一个未声明领域工具，确认服务端拒绝；
- 五种干净 wheel 环境除编译目录外，至少直接调用各自已安装的曲线、表格和已解析 TCAD
  注册工具实现。安装态探针只证明打包与注册实现可调用，不冒充完整科研生命周期；完整
  生命周期由对应源码态生产测试证明；
- 通过聚焦测试、全部 Operation 测试、部署/平台测试、静态扫描和差异检查后，冻结第三轮候选，
  再交给未参与实现的独立审查者。第三轮明确通过前，H3 继续保持未开始。

### 21.4 复杂度硬边界

- 本轮不修改 Operation 编译器、统一调用入口、准入算法、Approval、Execution 或调度器；
- 不增加“图证据状态”、专用审批、专用资格表或阶段 DAG；
- 若一个缺口只能通过新增通用控制实体关闭，先停止并重新审视插件边界，不以补丁继续扩张。

## 22. H2b 第三轮候选实施记录

### 22.1 控制面减法

- 通用 Task 输出校验已删除对“阈值化数值资格绑定”和“曲线系列角色冲突”的字符串解释；保留
  JSON 语法、必需字段、额外字段和基础类型等通用叶级修复提示；
- 对整个 `src/scidiscovery` 的曲线科学语句负扫描无命中；未新增错误提示注册表、领域回调、
  Schema 路由器或新的入口校验；
- Operation 编译器、统一 preflight/invoke、producer admission、Approval、Execution、调度器和
  持久化 Schema 均未改动。

### 22.2 曲线插件内的最小正式生产能力

- `science.evidence.extract.figure.v1` 新增且只新增已编译的
  `worker_curve_figure_digitize`，继续配套 `worker_curve_figure_validate`；该 OperationSpec 不再
  声明临时代码分析工具，原型 Worker 即使显示旧通用工具，服务端能力检查也会拒绝实调；
- 数字化工具只读取精确绑定的 `paper_source` 和 `figure_request`。请求必须显式声明一块面板的
  轴标定、系列颜色、可见标签及其 legend/annotation/caption 身份来源；工具不做 OCR、不猜身份、
  不插值缺失支撑；
- 所有科学字节先在内存中完成并通过同一个插件的严格 manifest/bundle validator，再写入正式
  collection。源 PNG/JPEG/WebP 原始字节和哈希保持不变；输出包括逐系列 CSV、覆盖每个被采用
  观测像素的 PNG 支撑叠图、manifest、报告和 bundle；
- 假栅格、标定越界、无匹配像素、点数/可见比例不足或跨系列像素支撑歧义均失败关闭。失败测试
  确认不留下正式集合或 bundle；
- 实现按既有责任拆成320行纯确定性算法和186行 Worker 适配/提交/重算，没有增加运行时实体、
  注册表、服务或状态。相比第二轮候选，生产 Python 为151个文件、60073行；新增量是被误删的
  领域生产能力，Task 核心职责反而减少5行，R0 核心责任聚合由9652行降为9647行。

### 22.3 真实纵向与安装态证据

- 图证据生产测试从 Root invoke 创建真实 Task，经 claim/materialize 后实调数字化工具和重算
  工具，确认临时代码工具被服务端拒绝，再完成 primary、bundle validate、finalize、精确工具
  收据和独立审查；还逐字节确认登记的来源图等于原始输入；
- 表格生产测试断言唯一成功收据为
  `operation_tool_succeeded:worker_table_summarize`，并实调未声明曲线工具确认“未知工具”拒绝；
- 干净 curve wheel 实调已安装的图数字化实现，干净 table wheel 实调表格总结实现；
  `tcad_resolved` 和 full wheel 都从编译后 TCAD author Operation 取得注册调试工具并通过假服务
  实调其已安装 handler。安装态测试没有使用源码 `PYTHONPATH`；
- 安装态实调只证明 wheel/entry point/组件导入/handler 组合可用，完整 Root/Task/Worker 科研
  生命周期仍由上述源码态生产测试承担，未夸大证据范围。

### 22.4 冻结验证与当前门状态

- 聚焦边界、曲线失败关闭、通用科学合同和真实 figure/table 纵向测试：26项通过；
- 干净安装 entry point、目录所有权和领域工具实调：9项通过；
- `tests/operations`：304项全部通过，用时107.80秒；
- 部署与平台配置：37项全部通过；
- `git diff --check` 通过；核心曲线科学语句、旧固定图脚本/技能分发和核心图证据标识扫描无命中；
- 生产 Python 151个文件、60073行；`operations/` 保持7个文件、2064行；R0 核心责任聚合9647行。

第三轮候选状态为“待独立审查”，不是“通过”。只有未参与实现的独立审查者明确确认三项阻断
均关闭、没有新增控制面复杂度或科学旁路，才可把 H2b 改为通过并进入 H3。

## 23. H2b 第三轮打回后的最小修复计划

第三轮独立报告为 `reviews/R5_H_H2B_THIRD_INDEPENDENT_REVIEW.zh-CN.md`；主代理对审查者冻结报告
字节计算的 SHA-256 为 `e8d7920b3c1ed90873fbbf11bc9da073eb983dfe1b18f20a31ce6975de865d60`，
结论“打回”。本轮不扩展到 H3，也不增加曲线专用控制状态。

### 23.1 修正观测像素语义

- 每个 x 列的匹配像素必须构成一个连续色带；出现两个或更多离散色带时判为身份/定位歧义并
  失败关闭，不得对离散候选取中点；
- 连续色带允许用带宽中心作为亚像素定位，但 `uncertainty_px` 至少覆盖实际半带宽和声明的不确定性；
- `max_gap_px` 计算必须覆盖完整标定 x 域的前导、内部和尾随空列；
- 新增精确反例：y=2/4 离散同色像素不得生成 y=3 observed 点；只在域末端出现支撑时，前导缺口
  必须进入 manifest。

### 23.2 复用现有 bundle validator 闭合正式来源

- 现有 Operation bundle validator 调用增加一个领域无关、只读、非持久化的上下文参数，只包含
  按输入端口分组的精确绑定字节和本次 Task attempt 已成功的注册 Worker 工具名；不包含 Artifact/
  Task 身份、路径、令牌、哈希权威或插件专用字段；
- 所有现有 bundle validator 使用同一三参数接口；非曲线 validator 可明确忽略上下文。不得按
  插件名、Operation id、collection 名或科学 Schema 在 Task 控制面分支；
- 曲线插件 validator 要求本次 attempt 存在 `worker_curve_figure_digitize` 成功收据，使用精确
  `paper_source` 和 `figure_request` 重放插件数字化算法，并逐字节比较来源图、CSV、支撑叠图、
  manifest 和报告；
- 由此关闭未调用工具、替换绑定输入、工具调用后篡改 collection、自洽重算伪 PNG/伪 manifest
  四类旁路。PNG/JPEG/WebP 解码和逐像素科学判定仍只在曲线插件内，控制面只调用已编译 validator；
- 不新增 Registry、Task 状态、数据库表、签名/哈希协议、专用资格规则或另一条文件生命周期。

### 23.3 最小授权与复审门

- 图证据提取只保留当前 primary/collection 受控文件生命周期、原生看图、数字化和重算工具；删除
  对栅格输入无用的 PDF 提取授权，但不为单个文件另造写入工具；
- 新增正式 Worker 入口负例：无数字化收据、伪叠图、替换 source/request、工具后篡改均必须在
  validate/finalize 前失败；
- 重新运行聚焦、干净 wheel、完整 Operation、部署/平台、静态边界和差异检查，冻结第四轮候选；
- 只有新的独立审查明确“通过”才可进入 H3。

## 24. H2b 第四轮候选实施记录

### 24.1 科学像素语义只在曲线插件内修正

- 同一 x 列的匹配像素只有构成单个连续色带时才可形成一个观测点；两个离散色带不再取中点，
  而是按身份或定位歧义失败关闭；
- 连续色带的中心仍可作为亚像素位置，但逐点不确定度至少覆盖色带半宽；
- 最大缺口按完整标定 x 域计算，包含首个观测之前和末个观测之后的空列；
- 精确反例已验证 y=2/4 的离散同色像素不会制造 y=3 观测，且仅在域末端出现观测时会报告
  前导缺口。以上逻辑全部位于 `curve_score` 的纯确定性算法，不进入通用控制面。

### 24.2 复用既有 validator，而不扩张入口契约

- 组合输出 validator 统一接收一个只读、非持久化上下文，只包含按端口分组的精确输入字节和
  当前 attempt 已成功的注册 Worker 工具名；它不保存身份、路径、令牌或新的生命周期状态；
- 上下文由现有 Task 输出校验路径直接构造，所有插件使用同一三参数调用。核心没有曲线、图证据、
  collection 或插件名分支，非曲线 validator 明确忽略该上下文；
- 曲线 validator 要求本 attempt 的数字化工具成功收据，从精确 `paper_source` 和
  `figure_request` 重放插件算法，并逐字节比较来源图、CSV、支撑叠图、manifest 和报告；
- 未调用数字化工具但通过通用文件接口写出正确 bundle、调用工具后篡改 CSV、自洽改写伪叠图、
  替换请求或来源图都在正式 validate/finalize 前失败。现有文件工具本身已拒绝二进制补丁，未为
  曲线另造写入接口或重复限制；
- 栅格图提取 Operation 删除了无用的 PDF 提取工具授权。Operation 编译器、preflight/invoke、
  producer admission、数据库 Schema、Approval、Execution 和调度器均未修改。

### 24.3 冻结验证与复杂度边界

- 第四轮专项与安装态冻结测试16项通过；包含唯一目录、规模哨兵和干净 wheel 注册工具实调；
- `tests/operations` 307项全部通过；部署与平台配置37项全部通过；
- `git diff --check` 通过；`src/scidiscovery` 中曲线、图数字化和图证据领域标识扫描无命中；
- 生产 Python 151个文件、60171行，`operations/` 保持7个文件、2064行；Task 职责聚合6205行，
  R0 核心责任聚合9687行。相对第三轮增加的核心40行只构造上述通用瞬时上下文，没有新实体、
  注册表、数据库表、科学规则或第二条文件生命周期；
- 曲线纯算法352行、Worker 适配186行，职责仍按“确定性算法/受控 Worker 适配”拆分，未形成巨型
  独立 Operation 类。

第四轮候选随后由
`reviews/R5_H_H2B_FOURTH_INDEPENDENT_REVIEW.zh-CN.md` 独立审查并打回；主代理对最终报告字节
计算的 SHA-256 为 `ad7c67fca202b0247092fb84918f1365a4489f3dc62c01f13c7864db30014a7d`。
报告确认正式来源绑定阻断已关闭，但发现大跨度离散色带可绕过歧义检查，以及颜色容差可覆盖整个
RGB 空间两项领域算法阻断，因此 H3 未放行。

## 25. H2b 第四轮打回后的最小修复计划

- 把同列连续性检查移到带宽检查之前；任意离散色带都按身份/定位歧义失败，不得静默降格为缺测；
- 在曲线插件的 manifest Schema 中建立唯一正式 RGB 容差常量，数字化请求复用同一常量；容差是
  请求与 manifest 都记录的 8 位 RGB 欧氏距离，超过领域上限的宽搜索只可用于探索，不得形成正式
  evidence；不把颜色规则放入核心 validator context；
- 连续色带的不确定度按像素单元边界计算，半宽为 `(末像素中心-首像素中心+1)/2`；因此单像素
  支撑至少有半像素定位不确定度；
- 增加“大跨度离散但其余列足以通过”“纯背景加全色域容差”“最大正式容差下纯背景”和单像素
  半宽反例；保持第三、第四轮已闭合的来源重放、当前 attempt 收据和完整域缺口语义；
- 只修改曲线插件算法、领域 Schema、测试和说明。不得修改 Operation 编译器、Task 状态、数据库、
  资格、审批、统一调用入口或再增加校验层。

## 26. H2b 第五轮候选实施记录

### 26.1 插件内的最小修正

- `_extract_series` 现在先检查同列像素是否为单个连续色带，再应用声明的最大带宽；大跨度离散
  支撑不再被静默省略；
- 正式 8 位 RGB 欧氏容差上限冻结为曲线 Schema 中唯一的 `MAX_FORMAL_RGB_DISTANCE = 48.0`，
  请求模型直接复用，manifest 继续记录实际值。该上限约为完整 RGB 立方体对角线的 11%，保留
  抗锯齿容差而不允许全色域匹配；冻结的红色目标在最大允许值下不能从纯白背景产生观测；任一
  其他目标色与背景是否可分，仍由显式请求、支撑叠图和独立 evidence audit 判断；
- 连续色带半宽按像素单元边界计算，单像素带至少记录 `0.5 px`。没有新增背景实体、校准状态或
  核心科学规则；更复杂的颜色分离继续由领域独立审查判定，而不是塞进入口门禁。

### 26.2 冻结验证与当前门

- 新增两项精确负例，并在完整域缺口正例中同时冻结单像素半宽；曲线专项、真实 Figure 链、曲线
  插件和安装态工具聚焦23项通过；
- 规模哨兵、全部干净 wheel、部署与平台组合57项通过；`tests/operations` 309项全部通过，用时
  108.23秒；部署与平台37项包含在上述57项中并通过；
- `git diff --check` 通过；生产 Python 151个文件、60177行，`operations/` 仍为7个文件、2064行；
- 相对第四轮只在曲线插件净增6行生产代码，没有改动通用 validator context、OperationSpec、
  preflight/invoke、持久化或 Worker 文件生命周期。

第五轮候选随后由
`reviews/R5_H_H2B_FIFTH_INDEPENDENT_REVIEW.zh-CN.md` 独立审查并明确“通过”；主代理对最终
报告字节计算的 SHA-256 为
`ac6ddaa3f9822e994a2d1fa032b04341b4760657c1f6d7eb59c66f2e27f7cfe5`。审查独立重放两条失败探针、
半像素/完整域缺口和 task+attempt 来源攻击，并确认没有新增控制面权威。H2b 至此通过，只放行 H3；
不宣称实际论文数字化精度已经得到科学资格。
