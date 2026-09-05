# R5-H H2b 第四轮独立审查报告

日期：2026-08-30  
审查对象：当前未提交工作树中的 R5-H/H2b 第四轮候选  
审查基线：`404aeb14`（`baseline/8765-codex`）及当前共享工作树  
审查职责：未参与实现的独立架构与实现审查；只审查，不修改生产代码、测试或既有文档  
报告 SHA-256：由主代理对最终报告字节计算并记录

## 1. 结论

**打回。**

第三轮的正式 bundle admission 阻断已经以足够小且领域无关的控制面变化真实关闭：当前 Task attempt
必须有注册 digitizer 的成功活动，validator 从固定 Task 输入读取精确 `paper_source` 和
`figure_request`，在曲线插件内重放同一确定性算法，并对全部正式附件的名称集合和字节逐一相等比较。
无 digitizer 收据的手写正确 bundle、工具后修改 CSV、自洽伪 overlay、替换 source/request 以及其他
task/attempt 的旧收据均不能通过正式 validation；没有新增 Registry、曲线专用写入工具、Task 状态或
另一条 finalization 生命周期。

但是第一个原阻断没有完整关闭。`_extract_series` 在检查同列候选是否连续之前，先把总跨度超过
`max_vertical_spread_px` 的列静默跳过。因而同列两个离散色带在跨度较大时不触发歧义失败；只要其他列
仍满足点数和可见比例，manifest 仍被标为 `qualified`。独立反例实际得到 8/9 个点、
`visible_fraction=0.8888888888888888` 和 `status=qualified`。这直接违反第 23.1 节“两个或更多离散
色带按身份/定位歧义失败关闭”，也说明现有 y=2/4 反例只覆盖分支的一侧。

此外，允许的 `color_tolerance=441.7` 已覆盖整个 8-bit RGB 立方体。独立探针用纯白图、红色目标、
该容忍度及允许的 100 px 垂向跨度，仍生成 9/9 个 `observed=1`、`eligible=1` 点并标为
`qualified`。此时颜色 observable 不能区分目标曲线与背景；该自由参数没有来源绑定的校准依据，不能
视为合法的可调未知。故本轮不能通过，**不得放行 H3**。

## 2. 审查范围与基线限制

权威输入为：

- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 第 23、24 节；
- `docs/plans/reviews/R5_H_H2B_THIRD_INDEPENDENT_REVIEW.zh-CN.md`；
- 当前工作树中的曲线数字化算法、Worker 适配、Figure Operation 声明、Task bundle 校验路径、Worker
  工具分派/文件生命周期、Operation 编译与插件入口；
- 第四轮新增/修改的聚焦、真实 Root→Task→Worker、clean-wheel、部署与平台测试。

相关候选文件相对 `HEAD` 均为未跟踪文件，且工作树含大量其他阶段和用户成果，因此无法从一个隔离
commit diff 推断“第四轮补丁”。本审查按上述权威章节限定语义范围，直接检查当前字节；没有清理、
回滚或改写任何既有成果。

## 3. 阻断项

### 3.1 大跨度离散同列支撑被静默省略，bundle 仍可 qualified

位置：`plugins/curve_score/curve_score/figure_digitization.py:143-167`。

实现先在 `:152-153` 对 `matches[-1] - matches[0] > max_vertical_spread_px` 执行 `continue`，然后才在
`:154-157` 检查相邻匹配 y 是否连续。该顺序使“大跨度且不连续”的候选永远到不了歧义检查。

独立探针构造 12×12 白底图：x=1..9 有 y=3 的红线，并在 x=1 额外放置 y=9 红像素；请求声明
`max_vertical_spread_px=4`。x=1 的两个候选离散且跨度为 6，当前实现跳过这一列；其余八列足够满足
门槛，最终结果为：

```text
status = qualified
point_count = 8
visible_fraction = 0.8888888888888888
max_gap_px = 1
```

这不是“保守地拒绝一个歧义 bundle”，而是把已观测到的身份/定位冲突改写成普通缺测后继续升格。
如果图中同色标注、另一条同色轨迹或噪点仅影响少数列，正式证据仍可通过；观察量不能证明剩余点属于
所声明系列。

最小修复：先检查 `matches` 是否为单个连续色带，出现任意离散段立即失败；仅对已经连续的色带再应用
宽度门。新增“离散跨度大于阈值且其他列仍足够”的反例，并断言整个生成失败且不留下 bundle，而不是
只测试跨度恰好落在阈值内的 y=2/4。

### 3.2 颜色容忍度是无依据的隐藏自由度，极值可从纯背景制造曲线

位置：`plugins/curve_score/curve_score/figure_digitization.py:38-49,139-163`。

`color_tolerance` 允许到 441.7，略高于 RGB 立方体的最大欧氏距离
`sqrt(3*255^2)≈441.673`。因此在允许上界时，每个像素都与每个声明颜色匹配。配合同样允许的
`max_vertical_spread_px=100`，一个高度不超过 101 px 的完整标定域形成“连续色带”，不会触发当前
任何失败关闭条件。

独立探针使用没有任何红像素的纯白图，目标为 `#ff0000`、`color_tolerance=441.7`、
`max_vertical_spread_px=100`。实现输出：

```text
status = qualified
point_count = 9
visible_fraction = 1.0
pixel_y_subpixel = 5
uncertainty_px = 4
observed = 1
quantitative_measurement_claim_eligible = 1
```

颜色容忍度本可作为可校准未知，但前提是请求给出来源可审计的颜色/背景分离依据或实现施加可证明的
判别裕量。当前只有一个无依据自由数值，没有背景/ROI 对照或容忍度校准锚点；在上界处 observable
数学上失去区分能力。这是缺少关键判别输入/约束，不是合法校准误差。

最小解决动作：在曲线插件内冻结一个来源可审计的 tolerance 判别合同，使允许范围不可能覆盖完整
颜色空间，并增加“纯背景不得产生目标系列”的负例。具体上界不能由控制面发明；应由领域合同给出
物理/图像依据。不要为此新增核心 Schema 路由、资格状态或插件专用控制入口。

同一参数面还有一个需同步澄清的问题：请求允许 `uncertainty_px=0`，而单像素色带按当前
`(last-first)/2` 得到零宽；若像素被视为面积采样，至少还存在半像素量化宽度。应在领域合同中明确
“色带半宽”采用像素中心跨度还是像素单元边界，并保证 CSV 的逐点不确定度覆盖该定义。该问题不重复
计为第三个阻断，归入本项的参数/观测可辨识性缺口。

## 4. 第二个原阻断：正式 bundle admission 已关闭

### 4.1 跨边界数据流

```text
固定 Artifact 输入 paper_source / figure_request
  -> Operation invoke 冻结 Task.inputs
  -> 注册 worker_curve_figure_digitize 读取同一 Task 输入并提交 collection
  -> Worker dispatcher 在 handler 成功返回后记录 operation_tool_succeeded
  -> worker_validate_output_file 读取 primary + bundle + 全部 collection 字节
  -> TaskService 以 task_id + 当前 attempt 查询成功工具，并从 Task.inputs 读取精确字节
  -> 编译后的三参数 bundle validator
  -> curve_score 重放 build_digitized_figure_bundle(source, request)
  -> 全部附件字典逐字节相等 + report/handoff fingerprint 一致
  -> 冻结 finalization snapshot，Task 进入 finalizing
  -> finalize 只登记已封存字节
```

`src/scidiscovery/artifact_agent/service/task_outputs.py:321-353` 构造的 context 只含按输入端口分组的
`tuple[bytes, ...]` 与成功工具名 tuple；两层 Mapping 均为 `MappingProxyType`，不含 task/artifact
身份、路径、令牌、hash authority 或领域字段。它在 validation 调用内即时创建，不产生新表或新持久
状态；成功工具事实复用既有 `task_activity_events`。

SQL 在 `:339-346` 同时限定 `task_id` 和 `attempt`。独立探针在真实方法上放入 task-a/attempt-1 与
task-b/attempt-2 两条成功记录，查询 task-a/attempt-2 得到空 tuple；只有加入 task-a/attempt-2 后才
看见 digitizer。context 的精确输入映射也拒绝赋值。

`plugins/curve_score/curve_score/figure_science_operations.py:75-106` 先要求本 attempt 的 digitizer
收据，再要求精确两个单项输入，重放后以 `items != expected_items` 拒绝任何键或字节差异。这覆盖
source panel、每个 CSV、overlay、manifest 和 report；后续 `:107-178` 再验证 provenance、机械
report 和 handoff fingerprint。通用文件工具可以写候选，但不能制造收据，也不能让非重放字节通过
正式 admission。

### 4.2 指定攻击探针结果

| 攻击 | 入口/证据 | 结果 |
|---|---|---|
| 未调用 digitizer，手写完全正确 bundle | 真实 Root→Task→Worker 文件接口；收据为空 | validation 拒绝 |
| 调用 digitizer 后修改 CSV | 真实 Worker `worker_file_apply_patch` | validation 拒绝 |
| 替换 overlay 为伪内容并同步 hash、重算旧 report/fingerprint | 直接调用编译组件的确定性负例 | 重放字节比较拒绝 |
| 替换 request | validator context 使用不同冻结请求 | 原 bundle 与重放结果不同，拒绝 |
| 替换 source | validator context 使用无目标像素的来源 | 重放先失败，原 bundle不能通过 |
| 其他 task 或旧 attempt 的成功收据 | 实际 context 方法 + SQLite 活动表探针 | 当前 task+attempt 看不到旧收据 |
| y=2/4 离散同列像素，跨度在阈值内 | 领域 Worker 负例 | 正确失败且不留 bundle |
| 只在域尾部 x=5..9 观测 | 领域 Worker/manifest 探针 | `max_gap_px=4`，正确计入前导缺口 |
| 离散同列像素，跨度超过阈值 | 独立新增探针 | **错误通过并 qualified**，见 3.1 |

正式 validation 成功后 Task 进入 `finalizing`；所有通用文件变更仍要求 active `claimed` attempt，
因此不能在封存后再通过工具修改。封存 snapshot 与 finalize 也同时检查当前 attempt。未发现隐藏的
同协议旁路。

## 5. 控制面、注册、接口和奥卡姆审查

### 5.1 核心仍不解释曲线科学

对 `src/scidiscovery/**/*.py` 扫描 `curve`、`digitiz`、`figure_evidence`、`paper_source` 和
`worker_curve`，唯一相关命中是 `general_science_agent_operations.py:332` 的通用 `not_for` 描述
“Quantitative raster-figure digitization”；它不是执行分支、Schema 字段、插件 allowlist 或错误
解释。Task 核心没有图像解码、像素/色差/曲线规则或按插件/Operation/collection 名分派。

新增 validator context 是领域无关、只读、非持久化的瞬时事实。它解决了插件 validator 此前看不到
固定输入和当前工具成功事实的精确缺口；没有引入通用科学 callback registry、第二权威或入口 Schema
推理。每个 bundle-enabled Operation 都走同一调用，非曲线 validator 显式丢弃 context。相对问题
规模，这一变化是必要且基本最小的；未见复杂度反噬或把科学准入复制到 preflight/invoke。

### 5.2 单一插件与无重复生命周期

- 生产代码只有 `src/scidiscovery/operations/catalog.py:696` 构造 `CompiledCatalog`；安装发现只读取
  `scidiscovery.plugins`；
- curve 的 Schema、算法、两个 Worker 工具、validator、prompt 和 Operations 都由
  `curve_score.plugin:PLUGIN` 的同一个 `PluginDefinition` 登记；
- 没有曲线专用文件写入工具。Figure producer 复用通用 result/bundle/collection 文件生命周期，并只
  增加注册 digitize/validate 工具；
- 没有新数据库表、收据表、哈希协议、Task 状态、资格状态或第二 finalization 路径；
- `record_registered_tool_use` 只能由 Worker dispatcher 在注册 handler 返回后写入，并验证工具属于
  当前 Operation；普通 `record_activity` 的允许集合不能伪造 `operation_tool_succeeded:*`。

### 5.3 三参数 validator 接口与工具最小授权

检查到四个生产 bundle validator：core architecture fixture、TCAD parameter bundle、curve plot bundle
和 figure bundle，均接受 `(primary_envelope, items, validation_context)`；非 figure 实现显式忽略第三
参数。Task 只在一个统一位置调用三参数接口，编译器仍只解析普通 `ComponentRef`，相关合同测试通过。

Figure producer 的工具集合是通用 materialize/write/patch/validate/finalize/heartbeat 加两个曲线领域
工具，并保留原生看图；不再授权 PDF extraction。Figure audit 仍允许 PDF extraction，因为它的
`paper_source` 输入明确可以是 PDF，这不是 producer 授权泄漏。未见通过删除 PDF 工具反而增设另一
写入或解析入口。

### 5.4 文件拆分

当前 `figure_digitization.py` 352 行，负责纯确定性图像解码、提取、CSV、overlay、manifest/report；
`figure_worker_tool.py` 186 行，负责绑定输入、输出目录、提交和重算适配。职责边界清楚，没有必要为
行数机械拆分。核心 `task_outputs.py` 较大属于既有 Task 输出职责聚合；第四轮增加的是约 40 行通用
context 构造与一次调用，不构成新的服务/规划器，但后续仍应由已有 R5-D/H3 责任计划治理，而不是在
本缺陷修复中扩大重构。

## 6. 实际命令与结果

所有命令串行执行，先设置 `ulimit -v 7340032` 和 `MALLOC_ARENA_MAX=2`；Python/pytest 命令还设置
`PYTHONDONTWRITEBYTECODE=1`。

1. 聚焦算法、H2b 边界、真实 figure family 与通用 bundle 合同：

   ```text
   pytest -q tests/operations/test_curve_figure_digitization_tool.py \
     tests/operations/test_h2b_domain_boundaries.py \
     tests/operations/test_r4_approval_operation.py::test_real_figure_family_qualification_and_four_omission_boundaries \
     tests/operations/test_r3_agent_contract.py
   13 passed in 5.71s
   ```

2. clean-wheel 单一目录所有权与已安装领域 handler 实调：

   ```text
   pytest -q \
     tests/operations/test_catalog_installed_entrypoint.py::test_clean_domain_wheel_matrix_has_exact_plugin_ownership \
     tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_domain_tools_execute_the_packaged_implementations
   2 passed in 39.42s
   ```

3. 部署与平台配置：

   ```text
   pytest -q tests/artifact_agent/test_deploy_scripts.py \
     tests/artifact_agent/test_platform_configuration.py
   37 passed in 5.60s
   ```

4. 约束矩阵：

   ```text
   pytest -q tests/operations/test_architecture_constraint_matrix.py
   1 passed in 0.04s
   ```

5. 收集完整 Operation suite 得到 `307 tests collected in 0.81s`，与第 24.3 节计数一致。由于独立
   科学反例已经失败，且本轮无需重复实现方的全量门，本审查没有重跑 307 项；因此只把“307 passed”
   视为候选实施记录，不冒充本审查的独立执行证据。

6. `git diff --check` 通过；静态扫描确认单一 `CompiledCatalog` 构造、单一
   `scidiscovery.plugins` 安装组、核心无曲线执行分支以及全部生产 bundle validator 的三参数接口。

7. 技能建议的 `scripts/validate_architecture_constraints.py` 在当前仓库不存在，命令以“文件不存在”
   退出 2；没有把它误报为产品失败，改用仓库现有的约束矩阵测试。该替代测试通过。

8. 三组不写仓库的独立确定性探针分别验证：像素分支顺序/完整域 gap/RGB 极值、Task+attempt 收据
   查询与 context 只读性、全部附件重放攻击。结果见第 3、4 节。

## 7. 生产链、安装态与文档状态

- 源码态真实链确实经过 Root invoke、Task claim/materialize、注册领域工具、通用受控文件、正式
  validate/finalize、Root output 和独立 audit；攻击负例在同一正式入口失败，不是只调 helper；
- clean wheel 测试从编译后 Operation 取出并实调已安装 handler，且目录所有权矩阵通过。它证明
  wheel/entry point/组件导入/handler 组合，不夸大为真实论文或 Agent 科研资格；
- 当前工作树可收集 307 项 Operation tests，部署/平台 37 项由本审查重跑通过；独立反例说明绿色
  回归集合仍缺一条分支负例，不能据测试总数覆盖科学错误；
- 主计划阶段表仍写 H2b“待独立审查”、H3“未开始”，第 24 节也明确没有自行批准，状态诚实。由于
  本报告打回，后续不得把这些文字更新为通过。

## 8. 非阻断债务与剩余风险

- `_commit_bundle` 逐文件 `os.replace` 后最后替换 bundle；若中途 I/O/进程失败，尚无故障注入证明
  已移动 collection 的清理行为。没有 bundle 时这些文件不能正式 finalization，但可能成为同 attempt
  的重试障碍。可增加一个局部故障注入，不需要新状态机。
- validate 先把附件读入并重放，随后 snapshotter 再读工作区。正式 MCP 调用串行，成功后立即进入
  `finalizing` 并禁止文件工具，所以本轮已授权路径不存在后篡改；但并发的协议外原生写入竞态未由
  H2b 测试证明。它不改变本轮结论，也不应以新增曲线专用锁补洞；若平台安全模型未来允许并发原生
  写，应在通用 sealed-output 生命周期统一处理。
- overlay 四色循环在超过四个系列时复用颜色，可能降低人工 audit 可辨识性；机械 replay 不受影响。

## 9. 下次复审门

1. 任意同列离散色带都在跨度门之前失败，新增“大跨度离散 + 其余列足够”的精确负例；
2. 冻结有来源依据且保持颜色判别力的 tolerance 合同，纯背景/全色域容忍度不能产生 qualified 系列；
   明确单像素与连续色带的 uncertainty 半宽约定；
3. 保持当前已正确闭合的 exact source/request 重放、全部附件逐字节比较、当前 task+attempt 收据和
   封存 finalization；
4. 保持核心无曲线科学分支、单一 PluginDefinition/CompiledCatalog、无专用写入工具或新控制状态；
5. 重跑上述聚焦攻击、clean wheel、完整 Operation、部署/平台和差异检查，再由新的独立审查确认。

只有新的独立审查明确“通过”，H2b 才可放行；本报告不批准 H3。
