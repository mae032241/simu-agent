# Fig.4 本轮交接、恢复、上下文与可视化整改计划

日期：2026-09-21

状态：**R1／待独立复审。已按绑定旧计划 SHA-256
`92494faae68043aa31d349825114fb89f91993114c581d5561992cb7867fb2bd` 的独立 SOL 审查修订；尚未修改
生产源码，尚未执行本计划，不能据此声称已通过独立复审。**
本计划以当前含未提交修改的实际工作树为基线，不把整个 dirty diff 归为本轮修改，也不要求先清理或
回退其他工作。本计划不改变 Fig.4 科学结果，不授权新的 TCAD 执行。

## 1. 目标与边界

本轮只修复已经由生产流程暴露的四类最小缺口：

1. 从 Root 已知的 prior result/execution result 出发，同时恢复生产 Run 的冻结输入和该结果直接
   recovery manifest 所封存的同 Run 工具证据。科学 Agent 只选择本任务需要的依赖角色；现有控制目录、
   manifest 和绑定机制把唯一匹配的算法、派生数据及来源机械补入 immutable request，避免 Root 手工
   搜索 `tool_evidence_NNN`，也不递归展开完整父链。
2. 在不放宽不可变来源和完整身份校验的前提下，诊断并修复历史分析与其直接
   `recovery_manifest` 的合法配对；让 TDR 声明使用求解器实际产生的文件名，并复用已有终态原文件
   检查/接纳能力，缺少声明文件不得触发求解重跑。
3. 让 Root 的常规读取保持在已有 `poll`、`navigation`、`decision` 紧凑投影上，详细 gates、日志、
   原生记录和父链只按具体问题读取；保留精确错误、遗漏计数和原访问路径。
4. 对所有通用曲线比较分析，在数据和绘图能力可用时默认交付参考/候选叠加图以及科学判断所需的
   残差图，图中包含单位、图例、范围，并由正式结论引用。复用现有 PNG 发布和页面展示通路。

必须保留的边界是：Artifact 字节与父链不可变；current、资格、独立审查和审批仍只有一个控制权威；
科学 Agent 选择方法并解释图，工具只计算、绘图和保存；执行 adapter 只处理副作用；失败执行、
求解状态、日志存在、文件收集和科学成功是不同事实。

本轮不新增图表 Schema、绘图角色、强制提交校验、文件路径/hash 填表、恢复状态机或 Fig.4 专用
控制分支。没有可画数据或绘图失败时，报告原因并保留已有科学结论；可以在后续分析 Run 补图，
不得仅因缺图拒绝一份已成立的受限科学结果。

## 2. 现场证据与源码核查结论

生产事实来自
`docs/plans/evidence/scientific-skeleton-author-20260920/fig4-live-20260921/OBSERVATIONS.zh-CN.md`、
`root-production-breakdown.json` 和 `root-production-final-usage.json`：九组 TCAD 均产生 PLX，
但声明的 TDR 路径没有匹配实际带 `_fps` 后缀的文件；最终只有 1/9 在冻结相对改善门上通过，且绝对
形貌仍未充分对齐。该科学结论和执行 `failed` 记录均保持不变。

### 2.1 已确认实现

- `plugins/tcad_artifact/tcad_artifact/worker.py` 与 `remote_runner_py36.py` 已在单个必需文件缺失后继续
  检查并收集后续产物，分别记录 `solver_exit_code`、`collection_errors` 和 `outputs`。已有回归
  `test_collection_keeps_later_products` 与 `test_worker_preserves_solver_success_and_collection_failure`。
- `plugins/tcad_artifact/tcad_artifact/output_recovery.py` 已提供
  `worker_tcad_inspect_outputs` 和 `worker_tcad_accept_output`：从已绑定终态 `execution_result` 列出/读取
  原目录，以显式 rationale 和证据别名把实际文件映射到一个已声明输出，再次核对字节并封存来源；
  它不运行、编辑或重命名求解器文件。当前 TDR 恢复应复用此路径。
- `src/scidiscovery/operations/input_validation.py::prior_analysis_sources` 已要求 manifest 是 prior
  analysis 的直接父件、同 producer、并带 `operation_output_port=recovery_manifest_output`，随后按完整
  `ArtifactRef` 映射历史来源。保护目标正确，不能改成按同字节、同 schema 或名称猜配。
- `analysis-start.json` 已投影输入索引、端口 description/usage/exposure、有限摘录和原件指针；
  `analysis-bindings.json` 已投影 TCAD 项目、案例矩阵和声明输出。当前 Run 记录本来就保存
  `artifact_name`，但 `run_assignment.assignment_json` 没有把该现有语义名投影给 Worker，分析索引也
  因而无法显示每个同端口来源的具体用途。这与首轮只见机械别名的现象一致。
- Root 已有 `run_status(response_profile=poll|navigation|decision)`，其中 `decision` 只返回请求的原始
  字段和 signal，`poll` 不展开正文，`navigation` 不返回值；`results.md` 和 `inputs.md` 已要求一次读取
  决策字段、用 `producer_inputs` 恢复即时来源、避免递归展开与重复读取。整改应以这些现有机制为
  基线，不再造一套 compact API。
- `producer_inputs` 只投影生产 Run 的冻结输入，不包含该 Run 后来发布的 tool-evidence sibling；主结果
  把 recovery manifest 作为直接父件，manifest 再把输入和本 Run 的脚本、派生表/图等 evidence 作为
  直接父件。因此恢复冻结输入与恢复同 Run 工具证据是互补路径，不能把后者限制在
  `producer_inputs` unavailable 时才执行。
- `plugins/curve_score/curve_score/analysis_files.py` 已允许分析 Agent 发布带来源的脚本、CSV/JSON/文本
  和 PNG；其共享 guidance 同时进入通用分析和 TCAD 分析提示词。当前文字把 plotting 描述为可选，
  尚未要求正常曲线比较默认提供叠加图、必要残差图及单位/图例/范围/结论引用。
- 页面 `presentation.py` 会把 PNG/JPEG Artifact 纳入 `figures`；`presentation_render.py` 已显示缩略图，
  点击在新页打开原图，并显示来源；evidence 路由已支持原件下载。Run 主输出把 recovery manifest
  作为父件，manifest 再绑定已发布图件，因此理论上无需新增图片字段或登记表。尚未用本轮真实分析
  图验证轨迹页是否因 lineage/展示预算遗漏图件。

### 2.2 尚未确认的根因

`prior_manifest_pair_mismatch` 目前只证明以下合取条件至少一项失败：直接父件关系、prior 主结果有
producer、manifest producer 与 prior producer 相同、manifest 输出端口标签正确。公开现场记录只确认
直接父件关系；不能据此宣称 `producer_run_id` 就是已证明根因。

源码中 `RunService.completed_for_output` 已包含通过 `tool_producer_run` 找工具证据 sibling 的逻辑，
但这条逻辑对历史 Operation 合同、旧 evidence manifest 和当前绑定投影的实际结果尚未用该 Fig.4
对象复现。因此实施不得先删除 producer 检查或重写 producer-family；应先做第 3.1 节的只读诊断。

TDR 的 `_fps` 后缀已由分析报告定位，但当前证据不足以概括为所有 SProcess 版本和所有 `struct` 写法
都固定添加该后缀。修复应绑定该项目源码语句、求解器版本和实际终态目录，不能加入全局猜名规则。

### 2.3 实施前仍须关闭的定向诊断

- 先按 §3.1 分解 `prior_manifest_pair_mismatch` 的四个事实；未定位前不得选择 producer、父件或端口修复
  分支。
- 先以一个封存 Fig.4 主结果验证现有直接 parents、manifest 记录和绑定是否已足以返回唯一可绑定名称；
  若页面不完整或有 omission，保持缺失未知并停止，不能以不完整页证明不存在。只有确认投影确实缺字段
  才进入 §3.3 的最窄 route 修改分支。
- 先从精确 solver 语句、版本与终态目录确定 `_fps` 来源；不能证明唯一对应时只走 inspect，不 accept。
- 先用整改后真实 Run 检查节点 lineage 和四项图件入口；只有实际复现的展示缺口才进入 UI 修改分支。

这些诊断只决定本计划列出的条件分支，不扩大为全局来源、UI 或 Sentaurus 命名审计。

## 3. 最小实施顺序

### 3.1 先复现并分解历史配对拒绝

修改范围首选：

- `src/scidiscovery/operations/input_validation.py`
- `src/scidiscovery/artifact_agent/service/runs.py`（只有诊断证明 sibling producer 恢复错误时）
- `tests/operations/test_prior_analysis_sources.py`
- `tests/operations/test_analysis_evidence_recovery.py`

步骤：

1. 用现有 Fig.4 封存的 prior analysis 与其 recovery manifest 做只读 preflight/最小测试夹具复现；记录
   四个配对事实的布尔结果和 manifest/primary 的来源类别，日志只保留 artifact 类型、端口标签和
   producer 一致/缺失，不输出私有路径、令牌或完整 payload。
2. 若直接父件或端口标签确实错误，修复产生/恢复该元数据的既有单一写入路径，并为旧对象保留诚实的
   不兼容诊断；不得在消费者端猜配。
3. 若 manifest 的 producer 恢复为 `None` 或错误 Run，而 `tool_producer_run`、完成 Run 和
   `evidence_output_refs` 能共同证明唯一同源，则只修正 `completed_for_output`/descriptor 的 sibling
   识别，使同一既有来源权威贯穿 preflight、Run 冻结和提交校验。不要新增旁路映射表。
4. 若 producer 实际不同，则维持拒绝；Root 绑定正确的同 producer manifest，或把旧报告仅作背景并从
   已绑定原始数据重算。不得把“直接父件”单独降格为全部证明。
5. 无论哪一分支，都给 `prior_analysis_missing`、`prior_manifest_missing`、pair mismatch 和 binding
   mismatch 提供有界、可修正的具体 message，说明冲突维度和应绑定的对象类型；不回显身份值，也不
   全局放宽 `OperationInvocationError` 默认消息。

验收：正确的主结果/同 producer manifest/原始来源组合通过；错误 producer、非父件、错误端口、同字节
不同 Artifact、manifest 声称未绑定来源均继续失败；preflight 与 invoke 返回同 code/path/message；
提交不重算历史评分。

### 3.2 对齐 TDR 实际文件名并验证无重算恢复

最小修改范围：

- 当前 Fig.4 deck 的正常 author-revision 流程所拥有的 `deck/declarations.json` 与对应 solver 源码
  （作为新不可变 project revision，不改旧 Artifact）
- `plugins/tcad_artifact/tcad_artifact/roles/sentaurus_author_contract.md` 或
  `roles/tcad_deck_author.md` 只补一条通用要求：结构输出声明必须以该版本实际写出的完整文件名为准，
  包括求解器生成的后缀；不得根据 `struct` 参数文本猜最终路径
- `tests/operations/test_analysis_evidence_recovery.py`

步骤：

1. 从现有执行 manifest、终态目录清单和产生 TDR 的精确 solver 语句确认九个实际文件名；先判断
   `_fps` 是源语句结果、版本行为还是本项目命名，未确认前不写全局路径变换器。
2. 对未来执行，通过现有 revision 只把 declarations 调整为源代码实际文件名并重新走原审查/打包/
   审批身份边界；旧 failed execution 和旧 package 不改写。本计划验收不启动该未来执行。
3. 对本轮已有执行，在新的受限分析中用 `inspect_outputs` 列目录并逐个读取实际 TDR；只有案例、来源
   语句和其他证据足以建立唯一对应时才用 `accept_output` 映射到声明 output name。映射歧义则报告
   限制，不靠后缀规则自动接纳。
4. 确认恢复后原 execution 仍是 failed，solver/log/collection/scientific verdict 各自保持原值；恢复
   只增加不可变证据，不产生执行成功，也不触发 solver、提交、重试或新的外部副作用。

验收使用现有 Fig.4 产物：九条 PLX 保持可读；实际 TDR 能被列出并在唯一映射时封存；缺声明路径的
测试仍继续收集后续文件；本地与远端 runner 行为一致；用 spy/负例确认恢复调用次数内 solver 启动为
零。若实际 TDR 超出现有 32 MiB 单文件或 256 MiB Run I/O 预算，明确报告预算限制，本轮不提高上限。

### 3.3 有界补齐同 Run 依赖并把导航语义投影给分析 Worker

最小修改范围：

- `src/scidiscovery/artifact_agent/service/run_assignment.py`
- `plugins/curve_score/curve_score/analysis_workspace.py`
- `.codex/scidiscovery-guides/inputs.md`
- 只有聚焦诊断证明现有 `producer_inputs`、直接 `parents` 视图和 manifest 记录无法返回可绑定语义名时，
  才修改 `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py` 的现有投影；不新增依赖 API
- `tests/operations/test_analysis_continuation.py` 或现有 assignment/workspace 聚焦测试
- `tests/artifact_agent/test_scheduler_guides.py`、`tests/operations/test_root_draft_routes.py` 和
  `tests/operations/test_historical_compatibility_paths.py` 的 producer/parents 聚焦测试

步骤：

1. 输入只给 Root 一个已知 prior result/execution result 语义名。Root 对该结果完整翻完一次
   `producer_inputs` 页，按冻结端口、顺序和精确引用恢复生产 Run 输入；仅当返回的 availability 明确为
   unavailable/historical/cross-instance/ambiguous 时，才按其 `parents_fallback` 恢复这部分输入。
2. 无论第 1 步的 producer 是否可用，只要当前任务需要复算/复核该结果中工具生成的方法或数据，就另做
   一次有界直接父件检查：定位该主结果的直接 recovery manifest，再只查看该 manifest 的受控记录和
   直接父件。禁止递归遍历祖先、按 schema 选较新对象或把 manifest 全部 evidence 自动绑定。
3. 科学 Agent 根据目标和现有报告声明需要的依赖角色，例如“冻结六掩码评分脚本”“该脚本消费的原始
   曲线”“已派生形貌表”；控制层只依据 recovery manifest 已封存的 alias/记录、直接父件和不可变引用，
   为每个角色解析唯一可访问的语义名并检查端口数量、字节和资格边界。缺失或多义时返回具体角色及
   missing/ambiguous 诊断，交给 Agent 缩小选择或报告限制；不得猜科学用途或扩大选择。
4. Root 把第 1—3 步得到且本任务实际需要的原结果、manifest、冻结算法、原数据和派生数据显式放入同一
   immutable request 的既有端口；不读取脚本正文，不把路径、hash、receipt 或 manifest 机械字段写进
   instruction。对于 Fig.4，首次正式指标分析必须含冻结形貌脚本、旧对照脚本、其消费的旧数据和旧
   execution manifest，缺一时不得静默换成固定浓度交点等替代指标。
5. 在 assignment 的每个现有 input 项投影冻结的 `RunInputBinding.artifact_name`，字段固定为
   `artifact_name` 并明确标记为 navigation-only。`analysis-start.json.inputs` 同步显示它，并继续显示
   `source_name`、port、description、usage、exposure、schema、大小和原件路径；端口用途仍只在 `ports`
   去重，不复制 payload、hash 或完整父链。
6. Worker 的工具调用、evidence 记录和正式报告引用仍只使用既有 `source_name`；`artifact_name` 不成为
   第二 alias，不改变权限、来源、精确 ArtifactRef 校验或 original access。Worker 必须实际读取并在
   计算记录中引用所选脚本/数据的 `source_name`，不能只在首屏看见导航名就算交接成功。

这一顺序不授予 Root 或控制层新的科学判断权：Agent 决定依赖角色，控制只解析封存身份、校验边界并
完成绑定；它也不新增调度权威、状态机或跨 Run 依赖台账。

正向验收 fixture 只给 Root prior result/execution result 名称，不预告任何 `tool_evidence_NNN`：首次
invoke 前 immutable request 已包含所需脚本、原数据、派生数据和直接 manifest；Worker 读取记录与正式
报告通过 `source_name` 指向这些绑定，并使用冻结六掩码算法。负向验收分别删除一个 manifest 记录、
制造同角色两项候选、只把 navigation-only `artifact_name` 当工具 alias、请求未绑定对象和触发端口/
字节上限；必须得到有界 missing/ambiguous/alias/permission/budget 诊断，不能自动全绑、换算法或读取
未绑定对象。两个同为 `reference_material` 的输入仍可由 `artifact_name` 和端口用途辨认；不新增“采纳
证明”字段。

### 3.4 收紧 Root 的读取行为而不再造协议

最小修改范围首选：

- `.codex/scidiscovery-guides/results.md`
- `.codex/scidiscovery-guides/inputs.md`
- `AGENTS.md`/`roles/scheduler.md` 仅在现有规则缺一句可执行顺序时同步；避免复制整段指南
- 只有聚焦实测证明默认实现仍返回多余字段时，才修改
  `src/scidiscovery/artifact_agent/interfaces/mcp_response_views.py` 或
  `mcp_root_run_routes.py`

把现有规则收敛成一次决策读取顺序：已知报告 schema 直接一次 `decision` 请求正式结论、限制、剩余
矛盾、下一动作理由和 signal；未知 schema 先取一次 `navigation` 索引，再取一次 `decision`；等待只
响应完成通知，必要轮询用 `poll`；详细 gates、native/tool records、日志和父链只有在它们能改变当前
科学决策或解释具体失败时读取。合同在同一安装版本和未丢失上下文时复用，不能重复 catalog/describe；
MCP `isError` 必须先于 JSON payload 解析处理。

不改变 `compat` 的旧客户端语义，除非调用者清单证明可以安全迁移；本轮不以改默认值制造兼容破坏。
不得截掉错误 code/path/message、missing/null/omitted 区别、分页游标或原访问路径。等待结果字符少不代表
请求免费，完成通知可用时应消除无意义的短轮询。

功能验收以与本轮同结构的单路模型实测为准：正常完成节点最多一次 decision 正文读取；同一合同、指南
和已读字段不重复；未知结构最多一次导航；没有父链全量 dump；错误分支仍返回原诊断。token 收益只按
第 5 节分别对 Root/Worker 做 matched A/B；本节单次实测不能证明收益。

### 3.5 通用曲线比较默认生成可审阅图件

最小修改范围：

- `plugins/curve_score/curve_score/analysis_files.py` 的共享 `GUIDANCE`
- 相应 prompt 投影/安装态测试；通常无需分别修改通用和 TCAD prompt，因为两者已经复用该 guidance
- 只有真实轨迹验收证明图件未显示时，才修改
  `src/scidiscovery/artifact_agent/approval_ui/read_model.py`、`presentation.py` 或
  `presentation_render.py` 中最窄的遗漏点

提示词要求：凡任务的科学判断涉及参考曲线与候选曲线比较，且绑定数据和可用绘图实现足够，默认保存
一张参考/候选叠加图；当残差分布会影响结论时再保存残差图。坐标必须带单位，图例必须绑定曲线身份，
图中范围必须与实际比较域一致，正式报告引用返回的图片 evidence alias 并说明图支持或限制哪条结论。
Agent 决定尺度、残差形式和是否需要第二张图；工具/本地脚本绘图并通过既有
`worker_analysis_publish_files` 保存 PNG。图不替代数值记录、来源或正式结论。

沿用现有失败语义：无数据、绘图库不可用、超时或渲染失败时保存已完成数字和错误，报告缺图原因；
允许 plot-only continuation 复用输入、方法和参数一致的已存数字；不得为补图重跑 TCAD 或隐式重拟合。

先用整改后同一条真实通用曲线比较 Run 做纵向验收：它用现有 Fig.4 封存数据生成带单位、图例和实际
比较范围的 PNG，通过既有发布工具返回 evidence alias，正式结论引用该 alias；Run 完成后主结果封存
直接 recovery manifest，manifest 绑定这张 PNG。随后打开**该 Run 所属节点的轨迹页**，核对缩略预览、
点击原图、下载所得字节与发布原件一致，以及来源链接可回到该 Run/manifest 链。旧 PNG 页面 fixture
只作确定性回归，不能代替这条真实纵向验收。若四项均满足，只补端到端测试、不改 UI；若仅下载入口
缺失，在现有 figure card 增加指向同一 evidence route 的下载链接；若 lineage 预算漏图，只修已绑定
tool-evidence 父链的最窄展示选择，不能创建图片登记表。

## 4. 定向验证与低内存纪律

按依赖顺序串行执行，每批独立进程、不开 pytest 并行；先跑功能，再做单路模型实测，最后才计量。
建议批次如下：

1. `tests/operations/test_prior_analysis_sources.py` 中配对正负例，随后只跑
   `test_analysis_evidence_recovery.py` 的历史配对、继续收集、inspect/accept、solver/collection 状态
   相关用例。
2. assignment 与 `analysis-start.json` 的聚焦测试，验证 navigation-only `artifact_name`/用途显示、
   `source_name` 引用和未授权读取负例。
3. `test_root_context_boundary.py` 与安装态 Root reading 的紧凑 profile/错误保真用例。
4. 分析文件发布、通用/TCAD prompt 投影、PNG 来源与 plot-only failure 用例；再跑 instance
   presentation/workbench/evidence 的图片预览、原图、下载、来源用例，最后执行第 3.5 节同一真实 Run
   的生成→发布→结论引用→所属节点轨迹预览/原图/下载/来源纵向验收。
5. 若生产文件发生变化，使用 `scid-change-scope-checks` 重新按最终 diff 选择最小可信回归；只有跨
   边界风险仍未覆盖时才扩大，不能直接运行整个 `tests/operations` 或全仓测试。

每个 pytest 批次和每一个独立模型探针都经
`scripts/compiled_worker_process_guard.py::run_process_group` 串行启动，固定
`aggregate_memory_limit_mib=768`、`sample_interval_seconds=0.1`，记录实际命令、环境、进程树 RSS
峰值、退出码和 `memory_limit_exceeded`。该守卫采样可追踪进程树的 resident set，属于应急观测/终止
机制，不是 OS 隔离；虚拟地址空间（如 `ulimit -v`）是不同指标，不能以 6 GiB VA 限制替代、放宽或
解释 768 MiB RSS 结果。本轮不新设 6 GiB 限制；若环境已有外层 VA/cgroup 限制，只单列其数值、作用
对象和语义。

测试或探针达到 RSS 限制时保留原始记录并报告该批未完成；模型探针超限后停止后续模型启动，把对应
Root/Worker A/B 标为缺测或收益未证实，不自动提限、换入口或用不受守卫覆盖的协作 Agent 重试。只有
用户明确改变资源预算后才可另记新测量，且不得覆盖失败记录。真实模型验证全程低资源单路，复用现有
Fig.4 已封存 PLX/指标，不启动 TCAD、不并发 Root/Worker、不制造新的审批或外部执行。

## 5. Root/Worker matched A/B 与历史观察边界

本节不要求修改生产计量协议：复用现有守卫与生产入口，只在
`docs/plans/evidence/fig4-round-handoff-context-visualization-20260921/matched-ab/` 保存 before/after 候选
快照、测量驱动和结果。候选 hash/清单只界定本次 A/B 证据，不进入 Artifact schema、Worker handoff、
运行时校验或路径/hash 台账。

既有数据只作生产问题背景：压缩前 `211069 -> 217709`，净增 6,640 input tokens；压缩后
`47742 -> 81013`，净增 33,271。压缩造成的 `217709 -> 47742` 下降不是收益。68 次请求、约
100,450 个可见工具返回字符为本轮总观察；合同/目录约 17k 字符、指南约 13k、一次配对故障诊断约
13.5k、两次报告约 13.8k，父链存在重复展开。18 次等待只返回约 833 字符，但请求次数本身仍有成本。
Root 生成的调用参数、指令和回复也计入新增上下文。分析同线程两 Run 的 62 请求、峰值 146,849 仅
说明“首轮缺算法导致第二 Run”的历史流程，不能把两 Run 峰值相加，也不能与新单 Run 配成收益 A/B。

编码前冻结 before candidate，实施完成后冻结 after candidate；各自记录仓库 HEAD、实际 dirty 状态与
候选补丁摘要，并封存本计划相关源码/配置的精确字节、安装入口与依赖版本、Operation 合同、共享
guidance、完整任务文字、现有 Fig.4 非敏感 fixture 清单及 hash、模型/effort、预算、工具后端、计量脚本
hash 和守卫参数。两版本必须从同类全新
线程启动，经相同真实生产入口接收完整 model-visible 响应，不能用裁剪后的旧响应或绕过新 route 的
投影回放冒充 before。除候选实现外，上述任一项变化都使该对不可比较。

分开执行两组低资源单路实验，每组至少两对，并交替版本顺序（第 1 对 before→after，第 2 对
after→before），所有运行串行且每次使用全新初始线程：

- Root 组从相同已知 prior result/execution result 名称开始，覆盖目录/合同读取、精确正式结果读取、
  `producer_inputs` 与直接 recovery manifest 的必要来源补齐，止于同一分析 Operation 的成功
  preflight 和 immutable invoke request 创建；不得实际派发 Worker，以隔离 Root 边界。
- Worker 组给定两版本内容等价的冻结 assignment，覆盖同一曲线目标从读取已绑定输入到正式结论、
  数值记录、PNG 发布和结果提交；固定输入顺序及 `source_name`，不得用旧 PNG 代替当次图件。

两组都重复同一个冻结问题，不引入新的科学假设。第 3.5 节只选择 after candidate 中一条完整、未压缩且
功能等价的 canonical Run 做页面纵向验收，其余重复仅用于波动估计。

每次记录首次/末次/峰值 input tokens、峰值增长、末次净增长、请求数、重复目录/合同/指南/正文读取、
工具可见字节分类、输出/reasoning 回流；Root 另记 parent/manifest 页数、decision/wait/无状态轮询，Worker
另记所消费脚本/数据 `source_name` 与是否返工。计量窗口严格使用上述组的起止事件；若发生 compaction，
该次从 matched 结论排除并只报告为探索观察，不把压缩降幅算收益。

先逐对验证功能、错误/遗漏诊断、权限/来源、正式数值和图件语义等价，再报告 token。预先采用保守判据：
两对 after 相对各自 before 的主要指标方向一致，且配对改善量大于两版本重复间的波动范围，才可称为
已观察到 matched 收益；方向不一致或改善落在波动内则报告“波动内、收益未证实”，不得挑选较好一对。
只有一对完成、任何候选发生 compaction、输出不等价或 768 MiB 守卫超限时，也只能报告探索性结果/
缺测。`summed_cached_input_tokens` 单列为跨请求累计计费/缓存量，不能当上下文体积；可见字符减少、等待
字符少和历史压缩前后区间均不得单独宣称收益。

## 6. 回归风险、停止条件与非目标

主要风险：放宽 manifest 配对会让错误历史计算进入新报告；错误的 TDR 自动猜名会跨案例接错文件；
暴露导航语义名时若把它误作第二 alias 或连内部路径/标识一起输出，会扩大权限面；manifest 机械补齐若
越过 Agent 所选依赖角色，会退化成自动全绑；强制图校验会把可用的科学结果变成
格式失败；更改 `compat` 默认值会破坏旧调用者；为节省 token 截断诊断会使故障不可修复。

相应停止条件：配对唯一性不能证明则保持拒绝；TDR 对应歧义则只报告限制；来源语义若不能从既有
Run 绑定安全投影则先不显示；manifest 角色映射不唯一则不猜用途并报告缺口；图片展示通路已满足则
不改 UI；任一 A/B 冻结项变化、输出不等价、compaction、样本不足或 RSS 超限，都只报告观察/缺测，
不宣称收益。

本轮明确不做：改变 1/9 科学 verdict 或把相对改善写成充分对齐；重跑九组 TCAD；提高恢复预算；
新增角色、Operation、审批、Artifact 类型、图表 schema、路径/hash 台账、阶段 DAG 或第二状态机；
恢复已删除的机械 gates/来源表；递归预装全父链；把日志、文件存在或进程退出码解释为科学成功；
清理当前工作树的无关修改或顺带重构大型模块。

## 7. 完成定义

只有以下条件全部满足，本计划对应整改才可提交独立审查：

1. 合法历史 analysis/manifest/原来源组合可复用，错误组合继续精确拒绝，且根因与修复分支有证据；
2. 现有 Fig.4 TDR 可在不启动 solver 的情况下检查并在唯一对应时封存，未来 revision 声明精确实际
   文件名，旧 failed 状态不变；
3. 只给已知 prior result/execution result 时，Root 能通过 producer 输入加直接 recovery manifest 两条
   互补路径，在首次 invoke 前有界补齐所需冻结算法、原/派生数据；Worker 以 `source_name` 实际消费，
   未绑定/多义/超预算负例精确失败，且不展开完整父链或自动全绑；
4. 通用曲线比较正常路径产生带单位、图例、范围和结论引用的叠加图，必要时有残差图；绘图失败不
   否决已有科学结果；
5. 同一条真实曲线 Run 完成 PNG 生成、发布、结论引用和封存后，其所属节点轨迹页经既有来源链提供
   预览、原图、原字节下载和来源；若原实现已满足，生产 UI 零修改；
6. 所有定向测试和独立模型探针均在串行 768 MiB 进程树 RSS 守卫内；达到限制即如实报告并停止后续
   模型，不自动提限；
7. Root/Worker 各自完成至少两对交替顺序的 matched A/B，或按第 5 节明确报告探索性/缺测/收益未证实；
   历史观察、compaction、累计 cached input 和可见字符不冒充 A/B 收益；
8. 最终 diff 仍是上述最小文件集合，没有 Fig.4 特例、无用校验、机械填表、新角色或第二状态机。

## 8. 独立审查发现到 R1 修订的对应

| 审查项 | R1 具体修订 | 复审状态 |
|---|---|---|
| P1-1：`producer_inputs` 漏同 Run manifest/tool-evidence | §2.1 新增来源拓扑事实；§3.3 改为 producer 输入与直接 recovery manifest 两条互补、有界路径，加入角色选择、机械唯一解析、实际 `source_name` 消费及正负验收；§7.3 收紧完成条件 | 待独立复审 |
| P1-2：6 GiB VA 混淆/放大 768 MiB RSS | §4 固定 768 MiB、0.1 s 的进程树 RSS 守卫，分离 VA/cgroup 语义，规定超限停止、缺测和不得自动提限；§7.6 收紧完成条件 | 待独立复审 |
| P1-3：缺少 matched Root/Worker A/B | §3.4 将单路实测降为功能验收；§5 冻结 code/config/task/input/model/计量边界，分组做至少两对交替实验并定义波动、compaction、cached 累计与失败处理；§7.7 收紧完成条件 | 待独立复审 |
| P2-1：图件证据未纵向贯通同一真实 Run | §3.5 与 §4.4 固定同一真实曲线 Run 的生成→发布→结论引用→封存→所属节点预览/原图/下载/来源验收；§7.5 收紧完成条件 | 待独立复审 |
| P2-2：语义名可能成为第二 alias | §3.3 固定 `artifact_name` 为 navigation-only，工具/evidence/报告继续使用 `source_name`，加入 alias/权限负例 | 待独立复审 |

旧独立审查继续只对其记录的旧计划 hash 生效，不改写、不宣称被本 R1 取代为通过结论；R1 必须以新的
SHA-256 单独提交一次有界复审。
