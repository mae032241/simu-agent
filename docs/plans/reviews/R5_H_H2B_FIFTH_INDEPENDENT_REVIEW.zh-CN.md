# R5-H H2b 第五轮独立审查报告

日期：2026-08-30  
审查对象：当前未提交工作树中的 R5-H/H2b 第五轮候选  
审查基线：`404aeb14`（`baseline/8765-codex`）及当前共享工作树  
审查职责：未参与实现的独立架构与实现审查；只审查，不修改生产代码、测试或既有文档  
报告 SHA-256：由主代理对最终报告字节计算并记录

## 1. 结论

**通过。**

第四轮的两个阻断均已按插件内最小改动关闭：任意同列离散支撑先于带宽门失败，不能再把歧义列
静默改写成缺测；正式 RGB 容差由曲线插件中的单一常量限制为 48，请求模型和 manifest 模型复用
同一上限，441.7 在请求 Schema 处拒绝，纯白图加红色目标和 48 容差不能形成观测。单像素支撑记录
至少 `0.5 px` 不确定度，完整标定域的前导、内部和尾随缺口计算没有退化。

第三轮已经闭合的正式来源边界也保持成立：validator 只从固定 Task 输入取得精确 source/request，
要求当前 task 和当前 attempt 的注册 digitizer 成功事实，在曲线插件内重放确定性算法，并对完整附件
集合逐字节相等比较。手写正确 bundle、同步重算 manifest/report 的伪叠图、替换 source/request、
工具后修改 CSV、借用另一 Task 或旧 attempt 的收据均不能通过正式 validation。

本轮没有新增控制面入口规则、领域分支、表、Task 状态、Registry、专用写入工具或另一条封存流程。
48 是曲线领域 Schema 的可审计上限，不是核心门禁，也不声称自动证明颜色身份。现有独立 figure
audit 和后续 qualification 仍负责判断显式颜色/身份锚点是否符合原图。因此没有发现需要打回的阻断，
H2b 可以放行；本报告只批准 H2b，不替代 H3 自己的实施与独立审查门。

## 2. 审查范围

权威范围为：

- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 第 23—26 节；
- `docs/plans/reviews/R5_H_H2B_FOURTH_INDEPENDENT_REVIEW.zh-CN.md`；
- `plugins/curve_score/curve_score/figure_digitization.py`、`figure_evidence.py`、
  `figure_worker_tool.py`、`figure_science_operations.py`；
- `src/scidiscovery/artifact_agent/service/task_outputs.py`、Worker 注册工具分派、Task 活动事实和受控文件
  validation/finalization 路径；
- 插件单一入口、编译后 Operation 工具授权、干净 wheel 安装态和相关聚焦测试。

工作树包含大量此前 R1—R5 的未提交成果，且本轮候选文件多数相对 `HEAD` 为未跟踪文件，不能从一个
隔离 commit diff 准确重建“第五轮补丁”。本审查按上述冻结范围检查当前字节，没有清理、回滚或改写
其他成果。

## 3. 第四轮阻断重放

### 3.1 大跨度离散同列支撑现在整包失败

位置：`plugins/curve_score/curve_score/figure_digitization.py:145-165`。

当前顺序是：取得本列全部颜色匹配像素；无匹配才跳过；随后立即检查相邻 y 是否连续；只有单一连续
色带才应用 `max_vertical_spread_px`。因此离散支撑不再有“跨度过大先 continue”的旁路。

独立探针重建第四轮反例：12×12 白底，x=1..9 存在 y=3 红线，x=1 另有 y=9 红像素，声明最大跨度
4。实际结果为：

```text
large-discontinuous REJECT ValueError
series s has discontinuous same-column support
```

同一探针中其余八列足以满足 `min_points` 和 `min_visible_fraction`，故失败确实来自歧义列先行拒绝，
不是支撑不足的偶然结果。现有 Worker 测试还断言失败后不留下任何 bundle 文件。

### 3.2 48 足以关闭“全色域容忍度”自由参数

位置：

- `plugins/curve_score/curve_score/figure_evidence.py:23,105-109`；
- `plugins/curve_score/curve_score/figure_digitization.py:38-44,238-242,281-285`。

`MAX_FORMAL_RGB_DISTANCE = 48.0` 是曲线插件中的唯一正式上限；请求的
`FigureDigitizationSeries.color_tolerance` 与 manifest 的
`FigureSeriesDescriptor.color_tolerance` 都直接复用该常量。模型 Schema 独立探针得到：

```text
constant = 48.0
request maximum = 48.0
manifest maximum = 48.0
```

8 位 RGB 立方体对角线约 441.67，半径 48 仅为其约 10.9%，不可能再让任意声明目标颜色匹配整个
色域。请求实际值同时存在于冻结请求、manifest descriptor 和请求规范摘要，正式 admission 又重放
精确请求，所以它是显式可审计参数，不是 validator 或控制面的隐藏自由度。

独立重放纯白图和红色目标得到：

```text
white-red-441.7 REJECT ValidationError
white-red-48 REJECT ValueError: series s has insufficient visible support
```

441.7 在 bundle 构造前即被 Schema 拒绝，内存构造函数不产生正式附件；48 下没有红色支撑，CSV 中
不存在 `observed=1` 或 `quantitative_measurement_claim_eligible=1`，所以不存在第四轮的“纯背景制造
红曲线”路径。

48 不是、也不应被解释为无需科学审查的通用图像分割证明。独立附加探针发现：纯白背景、声明
`#e5e5e5`、容差 48 且把允许色带宽度放到 100 时，背景与目标距离约 45.03，机械提取会得到支撑。
这不重开“全色域容忍度”阻断：目标颜色已被请求者改成与背景近似，参数和值均可见，且正式流程还
必须经过精确 source/request/overlay 的独立 figure audit，之后 qualification 才能等待审批。任何非零
全局阈值都无法机械保证与所有可能背景分离；为了消灭这个命题而在控制面增加背景实体、颜色校准状态
或入口分支，会把领域科学判断错误搬入控制面。该边界应保留给插件领域合同和审查者。

### 3.3 半像素不确定度与完整域缺口

连续色带逐点不确定度现在取声明值与 `(末像素中心-首像素中心+1)/2` 的较大者。独立探针只在
x=5..9、y=3 放置单像素红支撑，标定 x 域为 1..9，得到：

```text
status = qualified
point_count = 5
max_gap_px = 4
all point uncertainty_px = 0.5
```

这同时证明单像素按像素单元边界给出半像素下限，并且首个观测之前的四列进入最大缺口。代码还显式
把尾随空列和相邻观测之间的内部空列纳入同一个 `max(gaps)`，没有退回只看相邻点的实现。

## 4. 第三轮正式来源边界没有回退

### 4.1 精确输入、收据和附件重放

正式路径仍是：

```text
冻结 paper_source / figure_request
  -> Operation invoke 固定 Task.inputs
  -> 当前 Worker 调用已注册 digitizer
  -> dispatcher 成功返回后记录 task_id + attempt 活动事实
  -> 通用输出校验构造瞬时只读 context
  -> curve bundle validator 以精确输入重放
  -> 全部附件名称集合和字节相等
  -> 通用 sealed-output finalization
```

`task_outputs.py:321-353` 的 SQL 同时限定 `task_id` 和 `attempt`，只选
`operation_tool_succeeded:*`。独立 SQLite 探针预置 task-a/attempt-1 和 task-b/attempt-2 的成功记录，
查询 task-a/attempt-2 得到空 tuple；只有写入 task-a/attempt-2 的成功事实后才返回 digitizer。对
`context["inputs"]` 赋值抛出 `TypeError`，两层映射保持只读。

`figure_science_operations.py:75-106` 要求精确一个 `paper_source`、精确一个 `figure_request` 和当前
attempt 的 digitizer 成功工具名，重放后以完整 `items != expected_items` 比较 source panel、每个
CSV、overlay、manifest 和 report 的名称及字节。其后才复核 provenance、确定性 report 和 primary
handoff fingerprint。

聚焦测试及真实 Root→Task→Worker 测试重放了以下攻击：

| 攻击 | 结果 |
|---|---|
| 未调用 digitizer，用通用文件工具写出字节正确 bundle | 当前 attempt 无收据，拒绝 |
| 先调用 digitizer，再用已授权文本 patch 修改 CSV | 重放字节不等，拒绝 |
| 伪造 overlay，并同步 manifest hash、重算 report 与 primary fingerprint | 重放字节不等，拒绝 |
| 用改变后的 request 校验原 bundle | 重放不等，拒绝 |
| 用替换后的纯白 source 校验原 bundle | 重放先因无支撑失败 |
| 前一成功 Task 的收据供后一手写 Task 使用 | SQL 按 Task 隔离，后一 validation 拒绝 |
| 旧 attempt 或另一 Task 的成功活动 | 精确 task+attempt 查询不可见 |

validation 成功后 Task 进入既有 `finalizing`，通用文件写入/patch 只接受 active claimed attempt；未见
校验后再改写或另一条 finalize 旁路。

### 4.2 工具授权与安装态

Figure producer 的编译工具集合只包含通用 assignment/file/validate/finalize/heartbeat、曲线
digitize/validate 两个领域工具，并声明原生 `view_image`；没有 `worker_run_analysis`、PDF extraction
或网络。真实 Worker 测试确认调用未授权 `worker_run_analysis` 被服务器 capability 拒绝，而两个注册
曲线工具都能实际运行并留下精确收据。

干净 wheel 测试从 `scidiscovery.plugins` entry point 编译目录，确认曲线 Schema、算法、工具、
validator、prompt 和 Operations 只由 `curve_score.plugin:PLUGIN` 一次登记，并实调安装后的 handler。
未发现第二插件目录、手工旁路或源码态才能工作的隐式注册。

## 5. 控制面复杂度与奥卡姆检查

### 5.1 核心没有领域科学分支

对 `src/scidiscovery/**/*.py` 扫描 `curve_score`、`figure_evidence`、`paper_source`、`worker_curve` 和
`digitiz`，唯一语义相关命中仍是 `general_science_agent_operations.py` 中说明某通用操作“不用于定量
栅格图数字化”的描述；没有按插件名、Operation id、collection 名、曲线 Schema 或颜色字段执行的
核心分支。

三参数 bundle validator 仍只有一个统一调用位置；architecture fixture、曲线诊断图、figure bundle
和 TCAD parameter bundle 四个生产 validator 都接受
`(primary_envelope, items, validation_context)`，非 figure validator 明确忽略第三参。旧非 Operation
兼容路径没有取得该 context，也没有成为正式 compiled Operation 的旁路。

### 5.2 validator context 是瞬时事实，不是新控制实体

context 只含按声明输入端口分组的精确字节 tuple 和当前 attempt 已成功的注册 Worker 工具名 tuple；
不含 Artifact/Task 身份、路径、令牌、哈希权威、插件名或科学字段。它在一次 validation 调用中构造，
没有新表、状态列、持久收据对象、资格规则、入口 Schema 或 Registry。

成功工具事实复用既有 `task_activity_events`，并只能由注册工具 dispatcher 在 handler 成功返回后通过
`record_registered_tool_use` 记录。普通 `record_activity` 的允许集合不接受伪造的
`operation_tool_succeeded:*`。这是一项闭合既有 validator 输入缺口的最小通用事实投影，不是第二
控制面。

### 5.3 注册和文件拆分

- 生产插件只使用一个 `scidiscovery.plugins` entry-point group；生产 catalog 只在
  `operations/catalog.py` 一处构造 `CompiledCatalog`；
- curve plugin 只有一个 `PluginDefinition`，且依赖方向为 `curve_score -> builtin/general_science`，
  没有反向依赖 TCAD；
- `figure_digitization.py` 354 行，负责纯确定性像素、CSV、overlay、manifest/report 构造；
  `figure_worker_tool.py` 186 行，只负责 Worker 输入、受控输出目录和提交/复算适配。职责边界清楚，
  未形成巨型 Operation 类，也没有必要为行数再拆；
- 第五轮只改变曲线插件中的常量和确定性算法语义，没有改 OperationSpec、preflight/invoke、Task 状态、
  数据库、Approval、Execution、通用文件生命周期或调度器。

该实现满足奥卡姆边界：它为已证实的两个领域算法漏洞各增加一个局部、可测试约束，没有用新的实体、
校验层或控制面注册表包裹问题。

## 6. 实际命令与结果

所有命令均串行执行，设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`；Python/pytest 还设置
`PYTHONDONTWRITEBYTECODE=1`。

1. 曲线算法、H2b 领域边界、真实 Figure 链和 Agent 工具合同：

   ```text
   pytest -q tests/operations/test_curve_figure_digitization_tool.py \
     tests/operations/test_h2b_domain_boundaries.py \
     tests/operations/test_r4_approval_operation.py::test_real_figure_family_qualification_and_four_omission_boundaries \
     tests/operations/test_r3_agent_contract.py
   15 passed in 5.77s
   ```

2. 干净 wheel 目录所有权和已安装领域 handler 实调：

   ```text
   pytest -q \
     tests/operations/test_catalog_installed_entrypoint.py::test_clean_domain_wheel_matrix_has_exact_plugin_ownership \
     tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_domain_tools_execute_the_packaged_implementations
   2 passed in 39.20s
   ```

3. 33 项约束矩阵、规模哨兵和职责拆分哨兵：

   ```text
   pytest -q tests/operations/test_architecture_constraint_matrix.py \
     tests/operations/test_r5_catalog_stages.py \
     tests/operations/test_r5_task_responsibility_split.py
   8 passed in 2.63s
   ```

4. 部署与平台配置：

   ```text
   pytest -q tests/artifact_agent/test_deploy_scripts.py \
     tests/artifact_agent/test_platform_configuration.py
   37 passed in 5.84s
   ```

5. 完整 Operation suite 仅收集、不重复实现方的全量回归：

   ```text
   pytest --collect-only -q tests/operations
   309 tests collected in 0.75s
   ```

6. 两个不写仓库的独立 Python 探针分别重放像素/颜色/半像素/完整域缺口，以及 task+attempt 收据与
   context 只读性；结果见第 3、4 节。

7. `git diff --check` 通过；静态扫描确认核心无曲线执行分支、单一 catalog/entry-point group、四个
   生产 bundle validator 的统一三参数接口，以及没有本轮新增表或状态。

## 7. 非阻断债务与剩余风险

1. 第 26.1 节“纯白背景对白色以外目标在最大允许值下不能产生观测”字面范围过大。`#e5e5e5` 与
   白色距离约 45.03，独立探针可以机械匹配。准确表述应是：48 关闭覆盖全 RGB 空间的容忍度，且
   冻结的红目标负例不能从白背景制造支撑；任一具体目标与背景是否可分仍由请求锚点、overlay 和独立
   audit 审查。该文字不改变当前代码权威和 H2b 验收，但后续维护计划时应收窄，避免把领域阈值描述成
   普适分割定理。
2. `figure_request` 仍是 Operation 层的 opaque 输入，其 Pydantic 约束在已注册 digitizer/replay 中
   执行，而不是作为另一个公开 Schema 组件重复注册。当前正式路径没有绕过它，且这保持注册面最小；
   若未来出现其他正式 producer 消费同一请求，再考虑把现有模型资源公开，不能预先新增第二 Schema
   路由。
3. 第四轮报告提到的 `_commit_bundle` 中途 I/O 故障残留、协议外并发原生写入竞态和超过四色时 overlay
   颜色复用仍未在第五轮处理。这些不是本轮科学阻断，也不应通过曲线专用锁或新 Task 状态修补；只在
   通用文件生命周期出现真实故障证据时统一治理。

## 8. 放行边界

H2b 可以标记为通过。放行依据只包括：曲线领域 Schema/算法从核心迁出、正式图证据边界闭合、插件
单一注册和本报告验证的第五轮缺陷关闭。它不证明实际论文数字化精度、不替代独立科学审查，也不批准
H3 的实现质量。H3 开始后仍须按主计划单独实施、回归并由新的独立审查者裁决。
