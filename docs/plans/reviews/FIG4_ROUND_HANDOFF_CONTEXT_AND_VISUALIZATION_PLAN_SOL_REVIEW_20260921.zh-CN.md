# Fig.4 本轮交接、恢复、上下文与可视化整改计划独立 SOL 审查

日期：2026-09-21  
审查结论：**需修订**  
阻断项：**3 个 P1**  

## 1. 审查对象与边界

- 所审计划：`docs/plans/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_REMEDIATION_PLAN_20260921.zh-CN.md`
- SHA-256：`92494faae68043aa31d349825114fb89f91993114c581d5561992cb7867fb2bd`
- 工作树包含大量既有未提交/未跟踪内容；本审查没有把总 diff 归为本计划，也没有回退任何修改。
- 本轮只做计划与定向源码/冻结证据审查；没有修改计划或生产源码，没有运行测试、模型、科研 Operation、TCAD、部署或审批。
- 审查采用 `scid-cross-boundary-review`，并用 `scid-find-simplifications` 检查是否新增第二权威、机械填表或不必要状态。当前架构、设计宪章、约束表和调度权威文件仅用于核对本计划涉及的边界，没有扩展为全局框架审计。

## 2. 阻断发现

### P1-1：首轮依赖补齐仍可能停在 `producer_inputs`，无法保证取得同 Run 的算法脚本和派生数据

位置：计划 §3.3 第 3—4 步及验收（第 155—164 行）；现有指南 `.codex/scidiscovery-guides/inputs.md:3-18`；`mcp_root_instance_routes.py:352-435`；`runs.py:1384-1402`；`tool_evidence.py:535-558`。

计划正确识别了两个不同缺口：Root 第一轮没有绑定必要的冻结算法/旧数据，Worker 对已绑定的同端口来源又只看到 `reference_material_003` 等机械别名。但当前修复顺序主要落在给 Worker 增加语义显示名，并规定“优先 `producer_inputs`，仅 unavailable/historical/ambiguous 才走 `parents_fallback`”。这不能闭合前一个缺口。

源码中 `producer_inputs` 只返回生产 Run 的冻结输入端口、顺序和引用；它不返回该 Run 产生的 tool-evidence sibling。分析主结果在完成时把 recovery manifest 作为直接父件，manifest 再以冻结算法脚本、派生表/图和原输入为父件。也就是说，在 producer 完全可用时，计划要求的 fallback 条件不会成立，但本轮实际缺少的 `tool_evidence_029`、`tool_evidence_001` 恰好位于这条直接 manifest 路径，而不在 `producer_inputs` 中。现场记录 `OBSERVATIONS.zh-CN.md:48-50` 也证明：Root 已经绑定了可辨认语义名仍漏掉算法，第二 Run 只有在显式补入两份脚本和旧 execution manifest 后才完成冻结指标复核。

可达后果是实施可以通过“语义名显示”测试，却在真实首轮再次让 Worker 只拿到报告/曲线而拿不到生成报告所依赖的算法或数据；随后仍会采用替代指标并返工。验收若预先硬编码 `tool_evidence_029` 也不能证明 Root 能从一个已知结果恢复所需依赖。

最小修订：把输入恢复明确写成两条互补、有界路径，而不是互斥 fallback：

1. 对所选主结果读取一次 `producer_inputs`，恢复其冻结输入；
2. 当任务要复算/复核主结果中由工具生成的方法或数据时，另外检查该主结果的**直接** recovery manifest，并从该 manifest 的受控记录/直接父件中只选择任务需要的算法、派生数据和来源；不递归整条父链；
3. 把该顺序落实到 `inputs.md` 的分析交接规则。Root 只负责选择并绑定语义 Artifact 名称，不把 hash、路径、receipt 或 manifest 机械字段抄入 instruction；Worker 仍以 `source_name` 作为工具/引用别名；
4. 验收 fixture 必须只给 Root 已知的 prior result/execution result 名称，不能预先给 `tool_evidence_NNN`。它应证明首次 invoke 前已绑定所需脚本、原数据和 manifest，漏绑依赖的负例可观察，未绑定对象仍不可读，端口数量/字节上限不被绕过。

这项修订复用现有 producer 投影、直接父件和 recovery manifest，不需要新增依赖 schema、来源台账、递归预装或控制状态。

### P1-2：§4 无依据把近轮 768 MiB RSS 守卫扩大为 6 GiB 地址空间上限，并混合两种不同度量

位置：计划 §4 第 229—231 行；`scripts/compiled_worker_process_guard.py:87-140`；`FIG4_AUTHOR_VALIDATION_AND_TOKEN_PLAN_R3_SNAPSHOT_20260920.zh-CN.md:118-133`；其实施审查第 45—51 行。

计划称“延续现有 6 GiB 进程地址空间上限”，但与本项目最近一轮 Fig.4 工程/模型验收的明确规则不一致：该轮要求所有 pytest 和独立模型探针经 `run_process_group(... aggregate_memory_limit_mib=768, sample_interval_seconds=0.1)` 串行启动，超限立即停止后续模型，不自动提限。真实首个 Root-before 探针已在 791,796 KiB（773.24 MiB）触发守卫并停止，稳定 token 收益因此保持未证实。

源码守卫采样可追踪进程树的 RSS，超过阈值后终止进程组；它自己也明确不是 OS 隔离边界。`ulimit -v` 一类 6 GiB 限制约束虚拟地址空间，既不等于该 RSS 观测，也不能替代 768 MiB 的近轮 OOM 应急纪律。计划没有给出用户批准的资源预算变化，不能把较老的 6 GiB 外层做法写成“延续现有”并据此放大本轮预算。

最小修订：工程批次和每个独立模型探针继续使用现有 768 MiB、0.1 s 的进程树 RSS 守卫并记录命令、峰值、退出码和超限标志；如同时保留地址空间限制，要单独说明它的数值、作用对象和非 RSS 语义，且不得高于/替代已批准的实际守卫来获得通过。模型探针超限时停止后续模型并把原生行为/token A/B 标为缺测或未证实；只有用户明确改变资源预算后才能另记新测量，不能在本计划内自动提到 6 GiB。

### P1-3：token 验收没有形成同生产边界的 Root/Worker matched A/B

位置：计划 §3.4 验收（第 187—189 行）、§4 第 230 行、§5 第 235—253 行及完成定义第 281—282 行；`root-production-breakdown.json:$.model_contexts`；`OBSERVATIONS.zh-CN.md:49-57`；`ROOT_CONTEXT_BOUNDARY_REMEDIATION_IMPLEMENTATION_SOL_REVIEW_20260921.zh-CN.md:19-48`。

计划已正确区分压缩前后区间、累计 cached input、可见字符和 token，也没有把两个 Worker Run 的峰值相加。但它把三类不可直接配对的材料放入同一效率结论：已有 Root 长线程/中途 compaction 的 68 请求观测（`gpt-6-astra/medium`）、同一 `sol/medium` Worker 的两 Run 返工流程，以及整改后“只用一条通用曲线比较任务”的新测量。单条 Worker 曲线任务不能验证 Root 的合同、父链、`run_status` 和 wait 读取改进；长线程历史起点也不能与干净的新线程直接构成 matched before/after。

计划还没有冻结实施前精确 dirty 工作树、计量脚本、请求生产边界和两组起止事件，也没有规定重复次数、交替顺序或波动判据。现有 compact 实施独立审查已经证明，裁剪后的旧响应与没有经过新 route 的投影会产生不可比较的字符收益；因此“同一计量器”本身不足以保证同边界。当前文字最多支持一次探索性观察，不能满足完成定义中的可比 token 验收。

最小修订：

1. 编码前冻结实际工作树/安装入口、依赖、计量脚本和非敏感 fixture 哈希；候选保存同类快照；
2. 分开定义 Root 组和 Worker 组。Root 组覆盖从目录/合同读取、精确结果读取、必要来源绑定到创建分析请求；Worker 组覆盖同一曲线目标从已绑定输入到正式结论和图件。两侧固定模型、effort、工具、后端、初始线程状态、输入、预算和起止事件；
3. 每组至少两对 before/after 并交替顺序，报告每对差值与重复间波动；若只能完成单对、发生 compaction 或 768 MiB 守卫超限，只能报告探索性结果/收益未证实；
4. 计数必须来自两版本相同的真实生产入口和完整 model-visible 响应，保留合同身份、诊断、遗漏和来源字段；现有历史 Root/Worker 数据只能作为生产问题背景或未经配对的流程基线；
5. 分别报告 Root 与 Worker 的首次/末次/峰值、峰值增长、末次净增长、请求数、重复读取和工具可见字节。只有功能、来源、诊断和图件结果等价后才判断收益。

## 3. 非阻断修订

### P2-1：把图件验收收紧为同一真实 Run 的“生成—封存—轨迹展示”纵向路径

位置：计划 §3.5 第 201—212 行、§4 第 224—225 行、完成定义第 278—280 行；`runs.py:1391-1402`；`tool_evidence.py:541-547`；`approval_ui/read_model.py:228-285`；`presentation.py:311-353`；`presentation_render.py:479-492`。

图表方案本身符合最小边界：共享 prompt 要求正常曲线比较默认提供叠加图、必要时提供残差图；Agent 选择尺度/残差，既有工具保存 PNG；绘图失败不否决已有科学结果；没有新增图表 schema、绘图角色、提交 validator 或路径/hash 填表。现有代码也确有主结果→recovery manifest→PNG 的来源链，以及节点 context、PNG fallback 和点击原图的渲染通路。

但当前测试文字可以被实现为三段互不相连的证据：prompt 投影测试、旧的已发布 PNG 页面测试、单条模型任务。最小收紧是要求整改后的那一条真实通用曲线比较 Run 自己发布带单位/图例/范围并被正式结论引用的 PNG，完成封存后打开**该 Run 的节点轨迹页**，逐项验证缩略预览、点击原图、下载原始字节和来源链接。若这一条纵向验收全过，UI 保持零修改；只有实际缺哪一项才改最窄展示点。该验收不得启动 TCAD，也不能用测试 fixture 的旧 PNG 冒充真实模型交付。

### P2-2：语义名应明确为导航显示名，不能成为第二引用别名

位置：计划 §3.3 第 149—154、162—164 行；`run_assignment.py:63-85`；`analysis_workspace.py:179-192`。

投影冻结的 `RunInputBinding.artifact_name` 是合理的只读显示，不增加资格或来源权威。不过计划允许字段名在 `artifact_name`/`semantic_name` 中任选，尚未明确模型可用于工具调用和报告引用的仍是现有 `source_name`。最小修订是固定一个显示语义（例如 `display_name` 或明确标注 navigation-only 的 `artifact_name`），在 assignment/`analysis-start.json` 说明“用于辨认来源；工具、evidence 和报告引用继续使用 `source_name`”，并增加一个负例证明显示名不能访问未绑定对象或绕过 alias 校验。无需新增持久字段或采纳证明。

## 4. 已确认合理且不应扩大之处

- §2.2 与 §3.1 正确把 `prior_manifest_pair_mismatch` 保持为四个条件中至少一个失败，先做只读分解；当前证据不足以把 `producer_run_id` 宣称为根因。保持 producer、直接父件、端口和完整 `ArtifactRef` 校验是必要的，不能盲删来源保护。
- §3.2 正确复用现有 `worker_tcad_inspect_outputs`/`worker_tcad_accept_output`，按唯一证据映射实际 `_fps` 文件，不猜全局后缀、不重命名、不重跑 solver，并保持旧 execution `failed`、solver exit、collection 和科学 verdict 为不同事实。
- §3.4 正确复用 `poll/navigation/decision`，保留默认 `compat`、错误 code/path/message、missing/null/omitted、分页和原访问路径；没有依据再造 compact API。
- §3.5 的图件方案和失败语义正确，UI 也被限定为真实缺口驱动。没有证据支持新增图表 schema、强制提交门、绘图角色、图片登记表或第二状态机。
- 测试总体采用定向批次而非全仓回归，且把 UI 修改、`runs.py` 修改和兼容变化设为证据触发，符合最小改动原则。修订资源守卫和 matched A/B 后，该范围可以继续使用。

## 5. 最终判定

**需修订。** 阻断实施放行的是 P1-1、P1-2、P1-3：当前计划尚不能保证首轮取得同 Run 的必要算法/数据，资源纪律无授权扩大且混淆 VA/RSS，token 验收也没有形成可复现的 Root/Worker matched A/B。P2-1、P2-2 是验收和模型可见合同的收紧，不要求扩大产品机制。

本审查只给出计划结论，不授权实施、部署、科研 Run、TCAD、恢复接纳或审批。完成上述修订后，应以新计划 SHA-256 进行一次有界复审；无需重开已确认正确的历史配对保护、inspect/accept 复用和无强制图表 schema 结论。
