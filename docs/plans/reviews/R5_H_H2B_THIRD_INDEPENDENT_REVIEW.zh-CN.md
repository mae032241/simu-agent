# R5-H H2b 第三轮独立审查报告

日期：2026-08-30  
审查对象：当前未提交工作树中的 H2b 第三轮候选  
审查基线：`404aeb1`（`baseline/8765-codex`）及当前共享工作树  
审查职责：未参与实现的独立架构/代码审查；只审查，不修改生产代码或测试  
报告 SHA-256：待主代理对最终报告字节计算并回填

## 1. 结论

**打回。**

第二轮三项阻断中，控制面的曲线科学解释已经删除；表格真实 Worker 的精确工具收据、未声明工具
服务端拒绝和干净 wheel 安装态领域 handler 实调也已有与声明相符的代码和测试证据。但是曲线图证据
主阻断仍未闭合：新版本化 digitizer 的实际算法可以把不存在目标色像素的位置写成
`observed=1`、`quantitative_measurement_claim_eligible=1`；同时正式 bundle admission 既不把输出重放
绑定到精确 `paper_source`/`figure_request`，也不验证 overlay 是图像或要求 digitizer 的成功收据，
所以受控文件写入仍可绕过注册的生产工具，提交自洽 hash/report 的伪叠图和手工派生曲线。

因此第三轮候选不通过，**不放行 H3**。实现方记录的 `304 passed` 不能覆盖上述反例。

## 2. 阻断项

### 2.1 版本化 digitizer 会把没有像素支撑的插值位置声明为直接观测

影响：阻断；违反第 21.2/22.2 节“不插值缺失支撑”和“完整观测支撑”的候选合同，涉及
`EVD-001`、`DET-001`，并使派生不确定性和 quantitative eligibility 不可信。

`plugins/curve_score/curve_score/figure_digitization.py:143-158` 收集一列内所有容差匹配像素，只检查
最上、最下匹配点的跨度；匹配数为偶数时直接平均中间两个 y。它没有要求匹配像素形成连续色带，也
没有确认平均位置仍有目标色像素。随后 `:180-200` 把该位置无条件写成 `observed=1` 和
`quantitative_measurement_claim_eligible=1`，而 overlay 在 `:205-216` 围绕同一个无支撑位置绘制。

在受限内存下执行的最小独立反例为：8×8 白底图在每个 x 列只放置 y=2 和 y=4 两个红像素，使用
零色差容忍度和允许 4 px 垂向跨度。工具成功生成 6 行曲线；第一行报告
`pixel_y_subpixel=3`，但源图 (x,3) 是白色，真实匹配集合只有 `[2, 4]`。这不是校准误差或合法
可调未知，而是算法凭空插入了一个被标为直接观测的点。

同一实现还在 `:258-278` 只统计相邻已提取点之间的 gap，遗漏轴域起点和终点到首末观测的空段。
独立反例中轴域 x=1..6、仅 x=5..6 有红色支撑，manifest 报告
`visible_fraction=1/3`、`max_gap_px=0`，实际前导空段为 4 列。由此可见完整观测支撑的机械摘要本身
也不正确。

最小修复：把一列内的非连续候选视为显式歧义并失败关闭，或只使用有可证明像素支撑且不确定性覆盖
实际色带的定位；不得把空白中点标成 observed/eligible。同时按完整校准 x 域计入前导、内部和尾随
gap。增加上述两个精确反例，逐行断言源像素支撑和完整域 gap。

### 2.2 正式 validation/finalization 不证明 bundle 由绑定输入和注册 digitizer 产生

影响：阻断；第二轮第 2.1 项的“临时代码不能生成可升格曲线证据”仍未成立，违反 `DET-001`，并
削弱 `EVD-001`、`ROLE-002` 的正式谱系保证。

候选 prompt 确实要求调用 `worker_curve_figure_digitize` 并禁止临时代码，且 OperationSpec 不再授权
`worker_run_analysis`；真实正例也验证该调用被服务端 capability 拒绝。但是这只封闭了一个工具名，
没有封闭正式输出入口：

- `figure_science_operations.py:43-57,404-424` 仍给该 Operation 配置通用 chunked file write 和
  patch，Worker 可以直接创建 `output/collections/**` 与 `output/bundle.json`；prompt 的
  `:60-69` 是行为要求，不是 admission 证据。
- `task_outputs.py:335-387` 的正式校验读取 primary 与 bundle 后直接封存候选；没有检查
  `operation_tool_succeeded:worker_curve_figure_digitize`，也没有比较工具运行时冻结的输出摘要。
- `_figure_bundle_validator`（`figure_science_operations.py:72-146`）按文件扩展名推定媒体类型，只校验
  自述 bytes、SHA-256 和可重算 report。它不解码 source/overlay 栅格，不重放 source→CSV/overlay，
  也看不到绑定的 `paper_source`/`figure_request`。manifest 的 `spec_sha256` 和 source hash 因而可由
  手工 bundle 自洽填写。
- `test_real_figure_family_qualification_and_four_omission_boundaries`
  (`test_r4_approval_operation.py:2045-2081`) 是有效正例，并断言两条成功收据；但没有负例证明缺少这些
  收据、替换 source、伪造 overlay 或手写 bundle 会被 validate/finalize 拒绝。

最小独立探针先由当前工具生成合法 bundle，再把
`audit_overlays/p--observed-support.png` 替换为 ASCII `b"not-a-png"`，同步更新 manifest 的字节数与
SHA-256，并用正式 report builder 重算 report。`_figure_bundle_validator` 仍返回成功：

```text
accepted_fake_overlay True
digitizer_receipt_required_by_validator False
```

因此第 22.3 节“临时代码工具被拒绝”本身属实，但不能推出“正式路径必须调用版本化生产工具”；原始
来源字节逐字节保持也只在当前正例调用该 handler 时成立，不是 formal admission 的不变量。

最小修复：复用现有 Operation 和 bundle 生命周期，让正式校验对精确绑定的
`paper_source`/`figure_request` 重放插件 digitizer，并逐字节比较 source、CSV、overlay、manifest 和
report，或提供等价的、不可在工具运行后被 Worker 改写的精确生成收据；同时实际解码 PNG/JPEG/WebP
并验证每个 observed row 的 overlay/source 支撑。不得新增第二 Registry、曲线专用 Task 状态机或
核心插件名分支。必须增加“未调用 digitizer”“伪 PNG”“替换 bound source/request”和工具运行后
篡改 collection 的目标入口负例。

## 3. 第二轮三项阻断逐项复核

### 3.1 曲线插件的确定性生产能力：实现存在，但正式闭环未成立

已成立的部分：

- Schema、validator、digitizer、overlay renderer、Worker adapter、prompt 和两个注册工具均由
  `curve_score` 的同一个 `PluginDefinition` 注册；没有恢复根技能脚本或第二工具注册表。
- `_digitize` 从精确绑定的两个输入读取字节，先在内存中构造并校验全部产物，再进入提交；正常成功
  路径原样保存 PNG/JPEG/WebP 来源字节。
- 真实正例确实走 Root invoke、Task、claim/materialize、两个领域工具、bundle validate、finalize、
  精确工具收据、来源字节比较和独立 audit/qualification omission 负例。
- 假栅格和没有请求颜色像素的单元负例在生成前失败且不留下文件。

未成立的部分：

- 实际提取会制造无像素支撑的 observed 点并错误统计完整域 gap，见 2.1。
- 工具生成不是正式 admission 的必要条件，validator 也不验证 overlay/source/request 的外部对应，
  见 2.2。
- `_commit_bundle` 在临时目录准备文件后逐个 `os.replace` collection，最后才替换 bundle；正常算法
  失败已关闭，但中途 I/O/进程失败的部分提交回滚尚无故障注入证据。

故第二轮第 2.1 阻断仍未关闭。

### 3.2 整个 `src/scidiscovery` 无曲线科学错误解释：关闭

独立全目录 Python 扫描确认第二轮报告指出的四个短语均无命中；源码搜索也未发现核心按 curve、
figure Schema 或插件名分派科学规则。`task_outputs.py` 现在只生成 JSON 语法、必需字段、额外字段、
类型等领域无关的叶级修复提示。没有新增 hint registry、Schema router 或领域回调。

该项通过。核心可以原样返回插件 validator 错误，但不得解释 series role 或 numerical gate；当前
候选遵守这条边界。

### 3.3 干净 wheel 实调、表格收据与拒绝：关闭

- `tests/operations/conftest.py` 从发布源构建 wheel，在 wheel 外工作目录运行，删除 `PYTHONPATH` 和
  role 环境变量，并断言 core/domain 包来自 venv prefix。
- curve 安装态探针从编译后的 figure Operation 取出并实调
  `worker_curve_figure_digitize`；table 探针实调 `worker_table_summarize`；`tcad_resolved` 和 full
  从安装目录取得 `worker_tcad_debug_run` 并用显式假 service 调用 handler。后者只证明安装态
  handler/service seam，不冒充求解器科研生命周期；第 22.3 节对此范围表述准确。
- 表格源码态测试真实经过 Root→Task→WorkerMCP→受控文件→validate/finalize→独立 review，精确断言
  唯一成功收据 `operation_tool_succeeded:worker_table_summarize`，并实调未声明
  `worker_curve_analyze` 获得服务端 `unknown worker tool` 拒绝。
- `TaskService.require_worker_capability` 同时校验 capability 与精确 tool name，拒绝不只是客户端列表
  隐藏。

该项通过。安装态测试的证明范围是 wheel、entry point、组件导入和 handler 组合；完整 figure/table
生命周期仍由源码态测试承担。

## 4. 目录、控制面与复杂度审查

### 4.1 单一权威保持成立

- 生产代码只有 `src/scidiscovery/operations/catalog.py:696` 构造 `CompiledCatalog`；installed loader
  在 `:708-722` 只读取 `scidiscovery.plugins`。`public/support/internal/all` 仍是同一目录投影。
- core、general_science、curve_score、table、TCAD、InGaAs 都只用这一 entry-point group；未发现旧
  role/transform/operation 第二发现入口。
- 第三轮没有修改 Operation 编译器、Root preflight/invoke、Approval、Execution、调度器或持久化
  Schema；控制面变更是删除 5 行领域解释，没有以通用实体补洞。

### 4.2 算法/Worker 拆分基本内聚，但不能补偿算法错误

`figure_digitization.py` 负责纯内存图像读取、提取、换算、CSV、overlay、manifest/report；
`figure_worker_tool.py` 负责绑定输入、受控输出目录、活动和 bundle 提交。这个拆分符合奥卡姆原则，
没有第二服务/状态/Registry。实施记录称纯算法“320行”，当前文件实际为 336 行；这是文档计数偏差，
不是独立架构阻断，但冻结证据应按真实字节修正。

插件内聚和代码较少不能使错误的观测语义或可旁路 admission 合格。

## 5. 33 项约束与通用 AI 科学家目标

仓库仍没有“33/33 自动验证器”，且约束矩阵本身明确保留 H3/H4/H5 的 known issues。本报告不把
H2b 聚焦测试或历史审计夸大为当前工作树 33/33 conformant，只检查本候选相关行为是否退化。

| 约束族 | 本轮判断 | 证据/限制 |
|---|---|---|
| `PLG-001/002` | H2b 所涉所有权与依赖方向通过 | curve Schema/算法/工具/角色由插件一次注册；core 不含曲线科学分支；`tcad_artifact -> curve_score`，无反向 TCAD 依赖 |
| `AUTH-003`, `SEC-002` | 未声明工具服务端拒绝通过；正式生成要求未闭合 | 精确 capability/tool name 门有效，但 Operation 授权“可调用工具”没有证明正式 bundle 确实由该工具生成；原生工具限制仍只是已披露的提示约束 |
| `ROLE-001/002` | 控制面科学解释已关闭；输出生命周期仍有缺口 | core 不生成科学修复建议；但 validate/finalize 不消费 digitizer 的精确生成事实 |
| `DET-001` | **失败** | 实际算法制造无支撑 observed 点；手工/临时代码 bundle 可绕过版本化 producer |
| `DET-002` | 有风险，不单独重复阻断 | 工具对任意非空 `visible_label` 自动写 `binding.status=matched`、`confidence=1.0` 和 manifest `qualified`；独立 audit 必须继续拥有科学判断，不能把机械成功当资格 |
| `EVD-001` | **失败** | 正常 handler 保留来源字节，但 formal validator 不把 source/report/overlay 绑定到精确输入，且接受伪 PNG overlay |
| `TOP-001/002` | 未发现本轮退化 | 没有新增固定阶段 DAG；真实计划审查和 figure/table review 仍通过已有 producer/reviewer 准入 |
| `MIG-002` | 本轮安装态范围通过 | clean wheel 和安装 handler 实调成立；不等于重启、失败恢复、回滚或真实求解器已由 H2b 证明 |
| `AUTH-001/002`, `IMM-*`, `LIN-*`, `HIL-*`, `CQRS-*`, `EFF-*`, `RES-*`, `UI-*`, `MIG-001` | 未发现由第三轮曲线补丁引入的新退化；不宣称全量关闭 | 当前矩阵中已有后续阶段事项仍按原计划保留，不能由本报告提前批准 |

通用 AI 科学家目标中的“领域插件一次注册”“最小输入绑定”“文件通信”“问题提出/独立审查”“控制
面不解释科学”均保持；figure 和 table 的真实链也没有让 Agent 通过聊天传递隐藏身份。失败点恰在
通用目标的另一半：证据必须可重放且正式输出必须能证明来自精确来源。若允许自洽 hash 的手工 bundle
替代注册算法，新增领域仍然是形式可插拔、科学上不可审计。

## 6. 测试真实性与独立命令证据

在串行、`ulimit -v 7340032`、`MALLOC_ARENA_MAX=2` 下独立运行：

```text
pytest -q \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_r4_approval_operation.py::test_real_figure_family_qualification_and_four_omission_boundaries \
  tests/operations/test_h2b_domain_boundaries.py::test_table_plugin_runs_through_real_root_task_worker_and_review_chain \
  tests/operations/test_h2b_domain_boundaries.py::test_generic_contracts_have_no_curve_vocabulary
git diff --check
```

结果：`5 passed in 3.79s`；`git diff --check` 通过。这证明现有正例、两个生成前失败负例、表格链和
核心静态负扫描可运行，不证明 2.1/2.2 的反例不存在。

另执行三个不写仓库的最小确定性探针：

```text
noncontiguous source matching y = [2, 4]
reported pixel_y_subpixel = 3
source pixel at reported y = white

visible_fraction = 0.3333333333333333
reported max_gap_px = 0
actual leading gap = 4

accepted_fake_overlay = True
digitizer_receipt_required_by_validator = False
```

实施记录所称 `tests/operations: 304 passed`、安装态 9 项和部署/平台 37 项是本轮提供的冻结证据；
本审查没有重复全量运行，也不把测试计数当作语义审查替代品。

## 7. 非阻断建议

- 为 `_commit_bundle` 增加逐文件 replace 中途失败的故障注入，证明无 bundle 的残留 collection 会被
  可靠清理或永不成为正式输出。
- 为 5 个以上系列的 overlay 提供不复用且可读的系列身份映射；当前 4 色循环会降低人工 audit 的
  可辨识性。
- 收紧或给出 `color_tolerance <= 441.7`、`max_vertical_spread_px <= 100`、可为零的
  `uncertainty_px` 的科学依据。接近全 RGB 距离的容忍度可使“颜色匹配”失去区分力；合法可调未知应
  有依据和可审计范围，不能成为绕过无匹配失败的自由度。
- 修正第 22.2 节算法行数，并在下轮报告中区分“handler 成功”“正式 admission 必须使用 handler”
  和“独立审查通过”三个不同事实。

## 8. 下次复审门

下次复审必须同时满足：

1. 非连续同列色像素不再产生无支撑 observed/eligible 中点，完整域 gap 指标正确；
2. 正式 bundle validation 对 bound source/request 可重放，伪 PNG、替换输入、未调用注册工具和工具后
   篡改均在 finalize 前失败关闭；
3. 保持整个 `src/scidiscovery` 无曲线科学解释、单一 `CompiledCatalog`/entry point、无核心插件名
   分支；
4. 重新通过真实 figure/table Worker 链、精确收据与服务端拒绝、clean wheel 安装态 handler、producer
   family/reviewer admission、依赖方向和 `git diff --check`。

只有新的独立审查明确“通过”，才可进入 H3；H2b 通过也不等于 R5 或 33 项约束全部完成。
