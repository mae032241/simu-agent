# Fig.4 本轮交接、恢复、上下文与可视化整改计划 R1 独立 SOL 复审

日期：2026-09-21  
复审结论：**PASS／可进入实施；本结论不授权自动实施。**  
新增阻断项：**无。**

## 1. 复审对象与边界

- R1 计划：`docs/plans/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_REMEDIATION_PLAN_20260921.zh-CN.md`
- 实际 SHA-256：`37bbbb240fd64f61b3d4f6d24a6de81a79d3390d430b42709f69f840d51861d3`，与复审委托预期一致。
- 旧独立审查：`docs/plans/reviews/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_PLAN_SOL_REVIEW_20260921.zh-CN.md`，绑定旧计划 hash `92494faae68043aa31d349825114fb89f91993114c581d5561992cb7867fb2bd`；本报告不改写旧结论。
- 工作树含大量既有未提交和未跟踪内容；本复审没有把总 dirty diff 归为本计划，也没有回退或修改他人内容。
- 本轮只复审 R1 计划，并定向核对相关生产路径；没有修改计划或生产源码，没有运行测试、模型、科研任务、TCAD、部署、恢复接纳或审批。

复审采用 `scid-cross-boundary-review`，重点检查来源权威、模型可见合同、Root/Worker 科学职责、恢复边界、真实 UI 路径和有界验证。没有扩大为全局架构审计。

## 2. 原 3 个 P1 的闭合判断

### P1-1：PASS——冻结输入与同 Run 工具证据已改为互补路径

R1 §2.1、§3.3 和 §7.3 已明确区分两条路径：

1. 对已知主结果分页读取一次 `producer_inputs`，恢复生产 Run 的冻结输入；仅这部分在 producer 不可用等明确状态下使用返回的 `parents_fallback`。
2. 只要任务需要复算或复核工具生成的方法/数据，无论 producer 是否可用，都另行定位该主结果的**直接** recovery manifest，只检查该 manifest 的受控 records 和直接父件，不递归祖先，不自动全绑 manifest 全部 evidence。

这与现有拓扑一致：`mcp_root_instance_routes.py::_producer_inputs_catalog` 只投影冻结输入；`runs.py::_register_candidate` 把 recovery manifest 作为主结果直接父件；`tool_evidence.py::_evidence_manifest` 又把 Run 输入和已登记工具证据作为 manifest 直接父件。`accept_tool_evidence` 的 record 已封存 alias、精确 `artifact_ref`、metadata、tool name、媒体类型和大小，Run 完成时既有绑定服务为工具证据及 manifest 建立当前实例语义名。因此控制层可以从 Agent 已选中的 record/精确引用机械解析当前可访问名，无需以 schema、较新对象或 semantic name 猜科学用途。

计划也正确划分职责：科学 Agent 根据目标和报告选择需要的算法、原始曲线或派生数据；控制只核对 manifest record、直接父件、精确引用、端口/字节/资格边界并完成绑定。Root 不读脚本正文，不把路径、hash、receipt 或 manifest 机械字段抄入 instruction；Worker 最终仍以 `source_name` 读取和引用。正向验收只给 prior result/execution result 名称，不预告 `tool_evidence_NNN`，并要求首次 invoke 前已补齐脚本、原/派生数据和直接 manifest；缺记录、多义、未绑定及超预算负例均明确停止。这足以防止再次以替代指标静默返工，也没有新增依赖 schema、来源台账或状态机。

当前 `artifact_catalog(view="parents")` 只显示直接父件名称、schema/kind 和有限 producer 信息，未直接投影 manifest record metadata。R1 已在 §2.3 和 §3.3 把此项保留为先诊断、后条件分支：若现有 manifest 记录和 parents 视图不能返回唯一可绑定名称，只修改既有 Root route 的最窄投影。实施时该投影只能把 Agent 选中的精确 record/ref 对应到可访问名；自由文本依赖角色不能成为控制层的科学语义匹配规则。计划已有 ambiguity 停止条件、无 Fig.4 特例和只给主结果名称的真实验收，故这属于实施时应核对的边界，不是 R1 阻断。

### P1-2：PASS——768 MiB 进程树 RSS 与 VA 已分离

R1 §4 固定所有 pytest 批次和独立模型探针通过 `run_process_group` 串行执行，使用 `aggregate_memory_limit_mib=768`、`sample_interval_seconds=0.1`，并记录命令、环境、进程树 RSS 峰值、退出码和 `memory_limit_exceeded`。源码 `scripts/compiled_worker_process_guard.py:87-140` 确实按 `/proc` 采样可追踪进程树的 resident set，并在超限后终止进程组。

计划已明确 VA/cgroup 是不同指标，不能用 6 GiB VA 替代、放宽或解释 768 MiB RSS；本轮不新设 6 GiB 限制。探针超限后停止后续模型、保留原始失败并把 A/B 标为缺测或收益未证实，不自动提限或绕过守卫。原 P1-2 已闭合。

### P1-3：PASS——Root/Worker 已形成同生产边界的 matched A/B

R1 §5 已分别定义 Root 与 Worker 两组真实生产入口实验，并冻结候选源码/配置、dirty 状态、安装入口、依赖、合同、guidance、完整任务、输入 fixture、模型/effort、预算、工具后端、计量脚本及守卫参数。每组至少两对，顺序为 before→after、after→before，全部串行并使用同类全新线程。

Root 组从相同已知结果名开始，覆盖合同/结果读取、`producer_inputs`、直接 manifest 来源补齐，止于成功 preflight 和 immutable invoke request 创建；现有 `operation_invoke` 只调度 queued Run，Worker 获取与执行是后续边界，因此可以隔离 Root 计量。Worker 组从内容等价的冻结 assignment 到正式结论、数值记录、当次 PNG 发布和提交，固定输入顺序及 `source_name`。

计划要求逐对先证明功能、诊断、权限/来源、数值和图件语义等价，再报告 token；记录首次/末次/峰值、增长、请求数、重复读取及工具可见字节。compaction、单对、输出不等价或 RSS 超限均只能报告探索性/缺测；`summed_cached_input_tokens` 单列，历史长线程、可见字符和压缩下降均不得冒充收益。原 P1-3 已闭合，且不要求为计量新增生产协议或运行时 hash 台账。

## 3. 原 2 个 P2 的闭合判断

### P2-1：PASS——图件验收已贯通同一真实 Run

R1 §3.5、§4.4 和 §7.5 要求整改后的同一条真实通用曲线比较 Run 使用现有 Fig.4 封存数据生成 PNG、通过既有工具发布、由正式结论引用、随主结果和 recovery manifest 封存，再打开**该 Run 所属节点**的轨迹页验证缩略预览、点击原图、原字节下载和来源链。旧 PNG fixture 只能作确定性回归，不能代替该纵向验收，也不启动 TCAD。

现有路径支持该条件式方案：共享 `analysis_files.GUIDANCE` 同时进入通用与 TCAD 分析；`worker_analysis_publish_files` 已发布有来源的 PNG；Run 主结果直接绑定 recovery manifest；节点 `node_context` 从完成 Run 输出沿父链构建展示 cohort；presentation 会把 PNG/JPEG 纳入 figures；渲染已有缩略图和原图入口；evidence route 已支持 `format=download`。当前 figure card 未单列图片下载链接，R1 没有预判为必须改 UI，而是要求先用真实 Run 验证四项，缺哪一项只改最窄展示点。该边界正确且可执行。

共享提示词范围也是通用曲线比较：数据和绘图能力足够时默认参考/候选叠加图，仅在残差会影响判断时增加残差图；Agent 决定尺度、残差形式和是否需要第二图，工具负责绘图和保存。图失败可说明原因并补交，不否定已经成立的受限科学结论，不新增图表 schema、图表角色、提交拒绝或路径/hash 登记。

### P2-2：PASS——`artifact_name` 仅作导航，引用权限仍由 `source_name` 统一

`RunInputBinding` 已冻结 `artifact_name`，而当前 `assignment_json` 的 input 只投影 `source_name` 等字段，`analysis-start.json` 又从 assignment 建索引。R1 §3.3 的修改点与该真实路径一致：把既有 `artifact_name` 投影到 assignment 和 analysis start，并明确标记 navigation-only；工具调用、evidence 和正式报告继续只接受现有 `source_name`。

计划明确 `artifact_name` 不成为第二 alias，不改变权限、来源、精确 ArtifactRef 或 original access，并加入把它误作工具 alias、访问未绑定对象等负例。原 P2-2 已闭合，无需新增持久字段或“采纳证明”。

## 4. 最小性、职责与保留风险

R1 保持此前已确认的正确边界：`prior_manifest_pair_mismatch` 先分解直接父件、prior producer、同 producer 和输出端口四项事实；未定位前不删除保护，也不伪造单一运行态根因。`input_validation.py::prior_analysis_sources` 当前确实同时检查这四项并按完整 ref 映射来源。TDR 恢复继续复用 inspect/accept，不猜全局 `_fps` 规则、不重跑 solver、不改写旧 failed execution。

生产修改均由诊断触发：Root route、`runs.py` 和 UI 只有在真实缺口成立时才进入；否则以指南、assignment、共享 guidance 和聚焦测试闭合。计划明确排除 Fig.4 专用分支、新角色、新 Operation、新 Artifact 类型、恢复状态机、阶段 DAG、机械来源表、全父链递归和强制绘图门。未发现控制层代替科学 Agent 选择方法、解释图或决定证据权重的要求。

仍待实施证据确认的是：历史四身份失败的具体维度、`_fps` 的项目/版本来源、manifest record 到当前访问名是否需要最窄投影，以及真实节点页面究竟缺少哪一项图件入口。R1 对这些均设了清晰的诊断前置条件和停止条件；规划阶段无需伪造运行态答案。

## 5. 最终判定

**PASS。** 原 3 个 P1 和 2 个 P2 均已闭合；计划与现有 producer/manifest、assignment、来源校验、进程守卫、queued Run、PNG 发布和轨迹展示路径相容。其验收可以区分科学选择与机械身份解析，能在不递归全父链、不预告机械别名、不放宽权限和不新建状态机的前提下验证首轮依赖交接、低资源纪律、matched A/B 和真实图件纵向路径。

本报告只放行计划进入实施，不代表源码已实施、测试已通过、模型收益已证实、Fig.4 科学结论改变或任何新的 TCAD/外部执行获得授权。
