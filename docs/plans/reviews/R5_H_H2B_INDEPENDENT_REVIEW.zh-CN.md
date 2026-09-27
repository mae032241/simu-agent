# R5-H H2b 独立审查报告

日期：2026-08-30  
审查对象：当前未提交工作树中的 H2b 候选  
审查依据：`R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 第 8、17、18 节、
`SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`、33 项架构约束，以及真实
Operation、Task、Worker 和安装入口  
审查者职责：只审查，不参与实现

## 1. 结论

**打回。**

H2b 已完成若干正确的物理迁移：`CurveExperimentContract` 已成为曲线插件中的普通
Artifact 合同，曲线插件不再依赖 TCAD，TCAD 改为单向依赖曲线插件，表格插件也能构建并从
统一 entry point 编译。但是候选尚未形成可运行的真实纵向链路，且通用核心仍实质拥有曲线
Schema、曲线 Operation 和曲线工具注入逻辑。因此不能把 H2b 标记为完成，也不能进入 H3。

## 2. 阻断项

### 2.1 受审实验计划和曲线合同在真实准入路径中断裂

影响：阻断；违反 `AUTH-003`、`ROLE-002`、`TOP-002`、`PLG-002`。

`science.experiment.materialize.v1` 的 `experiment_plan` 带有
`science.object.review.v1` 独立审查合同。控制面在消费该输出时会检查同一次调用是否同时绑定了
精确审查结果；这是正确且承重的规则，见
`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1085` 至 `1134`。

但 `science.curve.contract.design.v1` 只声明 `research_objective` 与
`experiment_plan` 两个输入，没有 `experiment_review`，见
`plugins/curve_score/curve_score/science_operations.py:425` 至 `474`。对真实 materialize 输出执行
Root preflight，复现结果为：

```text
plan-output plan
{'admissible': False,
 'reason_code': 'input_independent_review_missing',
 'port': 'experiment_plan',
 'executor_kind': None}
```

同一断裂继续出现在后续边界：

- 曲线合同 review 自身也消费受审计划，却没有计划审查输入；
- `scidiscovery.curve-score.v1`、reference coverage、objective coverage 只接收曲线合同，
  没有曲线合同审查输入，见
  `plugins/curve_score/curve_score/operation_transforms.py:491` 至 `552`；
- 两个 diagnosis 只有名为 `experiment_review` 的一个审查端口，不能同时证明计划审查和曲线
  合同审查；其上下文校验也没有验证该端口对应哪一个受审对象；
- 两个 TCAD 曲线适配 Operation 只有 `experiment_plan` 与 `curve_contract`，没有各自的审查
  输入，见 `plugins/tcad_artifact/tcad_artifact/curve_operations.py:322` 至 `392`；
- 表格 analyze/review 同样消费 materialized plan，却没有 `experiment_review`。

现有 H2b 测试以手工注册、没有 producer output contract 的计划和曲线合同直接调用算法，因此
绕过了生产者审查准入，无法发现上述断路。

最小架构修复方向：不增加注册表、资格实体或特殊路由。所有消费受审 Artifact 的 Operation 必须
在同一个 OperationSpec 中显式声明相应 `ScientificReview` 输入：曲线合同提出/审查和表格
analyze/review 绑定精确 `experiment_review`；评分、覆盖、诊断和 TCAD 曲线适配分别绑定精确
`experiment_review` 与 `curve_contract_review`。继续复用现有 producer-output admission，禁止在
插件中复制审查判断。增加从 materialize 的真实输出开始的正例，以及缺失、错对象、非 pass 审查
三个 Root preflight 负例。

### 2.2 非曲线工具测试绕过 Worker 路由，真实调用会失败

影响：阻断；违反 `AUTH-003`、`ROLE-002`，且第 18.3、18.4 节的完成声明不成立。

专项测试在 `tests/operations/test_h2b_domain_boundaries.py:203` 至 `237` 构造假
`_TableTask`，然后直接调用 `WorkerToolDefinition.contextual_handler`。它没有经过
Root → Task → `WorkerMCPRouter` 的 capability 检查、任务输入读取和工具收据路径。

独立审查用真实编译目录创建 Operation Task，再经 `WorkerMCPRouter` 调用
`worker_table_summarize`。preflight 与 claim 成功，但工具失败：

```text
preflight {'admissible': True, ...}
claim {'state': 'claimed'}
ValueError: unknown worker activity
WorkerToolError: registered worker tool failed
```

根因是 `table_observation/worker_tool.py` 记录了
`deterministic_table_summary_completed`，但 Task 权威只接受
`tasks.py:782` 至 `809` 中的通用有界活动名。假 Task 无条件接受任意字符串，掩盖了错误。

最小架构修复方向：不要向核心追加表格专用活动名。领域工具应复用已有通用活动
`deterministic_analysis_completed`，或只依赖控制面已经生成的
`operation_tool_succeeded:worker_table_summarize` 注册工具收据。测试必须走真实 Root、Task、
WorkerMCP 路径，并同时验证获准工具成功、未声明工具拒绝、精确输入读取和正式工具收据。

### 2.3 通用核心和 general_science 仍实质拥有曲线能力

影响：阻断；违反 `PLG-001`、`AUTH-003`，未达到 H2b 的所有权目标。

这不是词名残留，而是可执行领域责任仍在通用层：

- `src/scidiscovery/artifact_agent/schema/figure_evidence.py` 定义曲线表路径、
  `series_key`、曲线像素支撑、曲线行数和曲线资格规则；
- `src/scidiscovery/general_science_agent_operations.py:454` 至 `518` 声明
  `curve_tables` 输出，`523` 至 `647` 声明曲线图提取和审查 Operation；
- `src/scidiscovery/general_science_components.py:134` 至 `188` 实现曲线 bundle 的确定性校验；
- 更关键的是，通用 Worker 路由在
  `src/scidiscovery/artifact_agent/interfaces/mcp_worker_dispatch.py:732` 至 `923` 按固定文件名查找并
  挂载 `digitize_plot.py`、`render_curve_support.py` 和
  `validate_evidence_bundle.py`。任何具有 collection 输出目录的通用 analysis 工具调用都可能获得
  这组曲线工具；能力不是由曲线 OperationSpec 授权；
- 基础 wheel 和通用部署仍直接分发 `scientific-paper-evidence` 曲线 skill 与脚本。

因此当前“基础 wheel 不导入 curve_score”只证明没有 Python 包 import，并不能证明基础层没有曲线
科学语义或领域工具。H2b 的专项词汇负例只扫描四个手选 Schema 文件，检查范围不足。

最小所有权修复方向：将曲线图数字化的 Schema、Validator、Agent Operation、skill/scripts 和工具
实现整体迁入 `curve_score`，或迁入一个由 `curve_score` 单向依赖的窄“曲线图证据”插件；
general_science 只保留领域无关的来源冻结、PDF/图像输入和普通证据审查。曲线脚本应由曲线插件的
已注册 Worker tool 执行并通过现有受控输出目录产出附件；从通用 Worker dispatch 删除按曲线文件名
查找和挂载的分支。不得为此新增脚本注册表或 Schema 路由器。

### 2.4 安装与回归证据没有覆盖声明的组合

影响：阻断完成声明；代码中的单向依赖本身经检查是正确的。

`tests/operations/test_h2b_domain_boundaries.py:187` 至 `200` 直接把 Python
`PluginDefinition` 对象传给 `compile_catalog`，没有经过 wheel entry point。现有
`tests/operations/conftest.py:54` 至 `126` 只创建 core 与 full 等环境，没有 curve-only、
TCAD 依赖组合或 table 环境。默认从仓库根运行 H2b 测试还会在 collection 阶段失败，因为
`pyproject.toml:47` 的测试路径没有 `plugins/table_observation`：

```text
ModuleNotFoundError: No module named 'table_observation'
```

独立审查补充验证了表格 wheel 本身可以构建、安装并从唯一 entry point 编译，结果为 19 个
Operation，故这不是插件包装实现失败；问题是正式测试和第 18.4 节“默认 Operation 测试通过”的
声明与仓库真实默认入口不一致。

最小修复方向：在安装探针中增加 base+curve、base+TCAD（由依赖解析安装 curve）、base+table 和
full 四个干净环境；不要依靠源码 `PYTHONPATH`。表格插件的源码测试应位于可独立运行的插件测试
入口，或由安装探针运行。每个环境同时断言 entry point 集合、Operation 集合、禁止项和实际
Worker 工具调用。

## 3. 已确认正确的部分

- `CurveExperimentContract` 位于曲线插件，通用 `ExperimentPortfolio` 不再内嵌曲线比较字段；
- `validate_curve_experiment_contract` 对实验身份、case、确定性检查、指标、阈值、单位和评价器做了
  一一绑定；
- Python 与发行依赖方向为 `tcad_artifact -> curve_score`，未发现
  `curve_score -> tcad_artifact` import 或声明依赖；
- base、base+curve、base+table 和 full 的直接目录编译分别可得到 17、26、19、45 项；
- 表格 wheel 经独立构建、安装后，可由唯一 `scidiscovery.plugins` entry point 发现并编译；
- H2b 新代码未增加第二注册表、Schema 路由器、Planner、current 权威或任务状态机；
- 47 项通用科学、曲线、TCAD 和 H2b 聚焦测试在显式源码路径下通过；7 项现有干净安装目录测试
  通过；`git diff --check` 通过。这些绿色结果不能覆盖上述真实边界阻断。

## 4. 复杂度与简化审查

`curve_score.objective.project_objective_readiness` 及其投影类型当前只有定义和导出，没有生产、动态
插件、测试或文档消费者。它不是本轮打回的主因，但属于高置信度死表面。完成所有权修复时应直接
删除，而不是保留一个无消费者的领域 readiness 入口；显式 objective coverage Operation 已保护
所需的确定性关系。

生成的 `plugins/table_observation/*.egg-info` 和 `__pycache__` 也不应成为候选源文件或发布依据。

## 5. 复审通过门

复审前必须同时满足：

1. 从真实 `science.experiment.materialize.v1` 输出开始，计划审查 → 曲线合同提出 → 曲线合同审查
   → TCAD/规范曲线 → score/coverage → diagnosis 的每个 preflight 都可通过；错审查必须在同一
   入口失败关闭；
2. 表格插件从真实 materialized plan 和 plan review 开始，经 Root/Task/WorkerMCP 成功调用领域
   工具，并留下正式注册工具收据；
3. 基础核心和 general_science 不再包含曲线 Schema、曲线 Operation、曲线 skill/script 分发或
   Worker 路由硬编码；
4. 四个干净 wheel 组合及其禁止项通过，默认仓库测试无需额外手工 `PYTHONPATH` 即可收集；
5. 继续保持单一 `scidiscovery.plugins`、单一 `CompiledCatalog`、单一 producer admission 和
   `tcad_artifact -> curve_score` 依赖，不用兼容转发器掩盖迁移。

在这些门闭合前，H2b 状态必须保持“待修复”，H3 不得开始。
