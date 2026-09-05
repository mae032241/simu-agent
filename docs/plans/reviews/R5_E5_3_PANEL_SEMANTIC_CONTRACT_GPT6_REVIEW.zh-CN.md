# E5.3 无标签面板语义合同 GPT-6 定向复审

日期：2026-09-06。结论：**PASS；blocker 0、high 0、medium 0、low 0。**

本结论只确认本次 panel 合同修复及其必要源码集成回归。不代表补丁已部署、新合同下真实 Agent 已成功重跑、完整图证链已通过或 E6 已放行。

## 范围与发现

基线为 `893832b66617f340a5715809c5e7e33f8809e198` 之上的五文件未提交 diff：公共模型、公共提示、Fig.4 compiler、语义编译测试和活动账本。已完整读取该 diff，并复用前轮已读的架构、设计宪章与约束边界。现场封存意图 `panel='single panel (no panel label)'` 来自本次审查任务与活动账本；本审查没有读取生产状态库或 Worker 草稿，也没有把临时测试内容称为新的真实模型结果。

未发现需保留的 blocker/high/medium/low。所核对边界如下。

### 1. `panel` 必填且可为 null，Schema 和提示说明一致

[figure_digitization_contract.py:62](../../../plugins/curve_score/curve_score/figure_digitization_contract.py#L62) 使用 `ShortText | None`，没有默认值。实际编译 Schema 的 `required` 仍含 `panel`，`anyOf` 只有非空字符串与 null。省略字段、空字符串、整数均不通过；null 可以通过。

同文件 28—31 行的单一 `PANEL_SELECTION_DESCRIPTION` 明确整图或没有可见面板标签时使用 null，否则复制可见标签；[figure_science_operations.py:65](../../../plugins/curve_score/curve_score/figure_science_operations.py#L65) 直接复用同一文本。未建立提示专用规则表。

已独立复跑实际 `operation_port_json_schema`、Run 落盘 `schema/result.schema.json` 和 `worker_submit_result` 用例：null 面板下，合法选定与合法未决均 completed，原重复标签及非空互斥负例继续 rejected。前轮 H1/M1 的职责收敛没有被撤销。

### 2. compiler 精确接受 null/旧 canonical，不解释任意描述句

[figure_compilation.py:41](../../../plugins/ingaas_fig4/ingaas_fig4/figure_compilation.py#L41) 只接受 `None` 或当前资源的精确 `geometry['panel']`，该值仍为 `whole figure`。没有大小写折叠、去空格匹配、同义词表、通配或忽略 panel 的分支；source hash、figure、series label、PDF 对象及恢复图像检查保持原样。

真实原论文经正式 Worker 提交 null/旧 canonical 两个正例，分别经过 Root support 调用和正式 materialize，精确父链测试均通过。独立补充比较还确认：对于同一来源和系列选择，null 与旧 canonical 产生的内部请求字节完全相同，未改变几何、点数、阈值或抽取算法。

对 `a` 与现场描述句 `single panel (no panel label)`，独立探针先经正式 Worker 完成语义对象，再调用真实 Root support。两者均在 `operation_invoke` 的确定性执行阶段拒绝，没有新增 Run/Artifact 绑定，原语义 Artifact 字节和 completed 状态均不变。函数级负例同时确认错误是 figure/panel 不受支持。

这里的通用 `operation_preflight` 仍报告绑定 admissible；它没有执行源图 compiler，也没有宣称面板已可编译。本补丁没有扩展通用预检职责。不能把这些负例记成“preflight 已拒绝”，但它们确实不能发布编译请求。

### 3. 旧结果可读不等于获得新合同准入

公共模型仍接受原有非空字符串，所以旧意图载荷能够解析；compiler 没有将现场描述句改写或重新解释为 null。临时正式入口负例确认，执行失败后旧封存对象及状态不变；本次代码也没有存储、恢复、迁移或结果重用操作。

Operation ABI 仍为 **16**，公开 schema 标识仍为 `scidiscovery.figure-extraction-intent.v1`；内部数字化请求 v2 未变。这是新读器对旧字符串载荷的读取兼容，不表示未升级旧读器能处理新 null 值。新 Schema 资源和提示进入既有编译摘要；Root 原有 `input_producer_contract_changed` 检查继续阻断跨合同代际直接复用。

活动账本明确保留失败证据，部署后从同一来源创建新的语义意图 revision，再以精确新绑定执行 support。本文没有执行该 revision，也没有修改旧失败记录。新 revision 是现有语义名称/不可变请求机制，不需要新增直接修订 Operation、迁移层或特殊恢复路径。

### 4. Agent/工具职责与奥卡姆边界保持

公共输出仍只有版本、source_sha256、figure、panel、series_labels、unresolved_reasons 六个字段；`additionalProperties=false` 保持。独立实际 Schema 负例确认 pixel_range、min_points、max_gap_px、seeds、csv、overlay 均被拒绝。提示仍把坐标、范围、点数、阈值、CSV 和叠图交给确定性 compiler/materializer。

生产 diff 只有三个既有文件的小改动：一个共享说明文本、一个 nullable 字段和一个精确判定条件。没有新增公共机械字段、alias 表、注册表、状态机、资格层、核心分支或几何事实源。该改动满足本次 AUTH-003、ROLE-001/002、DET-001/002、PLG-001/002 的相关边界，不升级全部 33 项状态。

## 独立验证

- 三文件聚焦集：`test_figure_semantic_compilation.py`、`test_m2_optional_figure_plugin.py`、`test_m5_plugin_ownership_and_default_surface.py`，**27 passed，0 skipped，14.54 s**。这是本审查者实际选择的集合，不将活动账本的另一组三文件 23 项结果混记为本次执行。
- 额外真实 PDF/Root 两个负例：错误标签、现场描述句均不能发布编译请求，旧封存载荷/状态与绑定数量不变。
- 额外实际 Schema 负例及 null/canonical 请求字节等同性验证通过。
- 全部测试串行，`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`、无 xdist、`ulimit -v 8388608`；真实 PDF 使用授权原路径，未复制论文。未采集峰值 RSS。
- `git diff --check` 通过。没有跑全量 suite、重装、部署或新真实科研 Run；没有修改生产代码/测试。本文件是本次复审唯一仓库写入。

本次 panel 定向源码与正式入口集成审查 **PASS**。后续部署和新 revision 的真实 Agent 验收仍按既有流程进行；**不放行 E6**。
