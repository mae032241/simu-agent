# R5-H H5 审批 UI 可读性修复计划

日期：2026-08-31  
状态：第二轮独立实现复审通过；H5 完成，仅放行 H6  
前置门：H4 独立实现审查通过  
目标：让用户先看见决策信息，再按需核对完整冻结对象；不改变审批权威或扩展 UI 协议

## 1. 当前根因

当前固定 renderer 的安全边界正确，但页面存在三项直接可复现的可读性问题：

1. `_render_raw_subjects` 给每个完整对象写入 `open`，所有长 JSON 默认展开；
2. 器件参数资格 projector 又把每个 subject 以根 `json_tree` 全量展开，导致同一对象在“已编译视图”
   和“完整原始对象”重复出现；
3. 窄屏布局按源码顺序先显示全部正文、最后显示决定面板，用户必须滚过长对象才能选择结论。

这些问题不需要新的前端框架或展示 Schema。既有 `ReviewDocument` 已能用固定 item、精确 subject
序号和 JSON Pointer 构造安全摘要；完整字节也已有受控下载和原始树。

## 2. 最小实现

### 2.1 核心固定 renderer

- 删除 raw subject `<details>` 的 `open`，完整冻结对象默认折叠；对象数量、Schema、元数据、下载和
  精确 JSON 树仍可逐项展开；
- 请求技术信息继续默认折叠；已编译 `ReviewDocument` 继续默认展开；
- 在现有窄屏媒体规则中让 `.decision-column` 排在 `.review-main` 前，不移动 DOM、不复制表单、
  不增加 JavaScript 状态；桌面仍保持右侧 sticky 决定栏；
- 不改变 CSP、转义、附件下载、nonce、CSRF、决定提交或刷新行为。

### 2.2 TCAD 器件参数资格摘要

保留现有全部资格、来源、父链和独立审查验证，只替换最后构造 `ReviewDocument` 的展示项：

- “资格结论”：coverage status、confirmed/review/blocking 数；
- “研究目标与参数”：foundation objective/summary，以及每个已验证 claim 的 parameter key、单位、
  认识状态和指向 `selected_value` 的精确 JSON Pointer；
- “限制与待处理项”：foundation missing inputs/open questions，以及 coverage 中非确认项的精确
  子树；
- “来源与独立审查”：每个已验证来源的完整来源键和来源详情指针，以及必需 audit check 的状态指针。

标签只能由已经严格解析的当前对象生成，值仍由核心 renderer 从冻结 subject 的精确 Pointer 读取。
不向 `ReviewDocument` 增加派生科学值，不增加表格类型，也不让核心理解参数 Schema。完整对象仍在
下方折叠 raw 区核对。

参数主张和覆盖明细使用 TCAD projector 内部的固定展示上限64项；标签只使用固定短标签、序号或
有界 `check_key`，完整 `parameter_key`/`source_key` 通过冻结 Pointer 显示。集合超过64项时，
不截断或假装完整，而是用一个既有 `json_tree` item 指向完整 `claims`/`items` 子树。来源数还受
当前独立审计合同32项上限约束，因此直接逐项显示，无需不可达的第二个来源阈值。该规则只决定
展示形态，不拒绝审批、不提高核心512项/512 KiB 上限，也不成为通用摘要协议。

### 2.3 TCAD 外部执行摘要

保留 request/package 的严格解析和 compiled identity 校验，把 project/review/capability/
resolved_inputs 四个整棵树改为直接决策相关指针：

- 执行器、准备合同、Operation、求解器、入口和资源上限；
- 独立审查 verdict、execution-ready、summary、各 fidelity、findings、missing inputs 和 next actions；
- capability 的公开 profile/release/launch 信息与已解析输入绑定。

已解析输入同样最多逐项展示64项；超过时用一个既有 `json_tree` item 指向完整
`/resolved_inputs` 子树，保证原本合法的大工程不会因可读性摘要而无法创建审批。

不展示私有 executable、环境或凭据；不修改 Effect、Approval 或 Execution 合同。

## 3. 验收

1. 固定 renderer 安全、历史回退、二进制下载、一次决定和重复提交测试继续通过；
2. 新的精确测试确认：raw subject 默认无 `open`，技术信息仍折叠，compiled document 默认展开；
3. 窄屏 CSS 中决定栏先于正文，桌面 sticky 行为保留；不增加前端状态；
4. 当前 TCAD 参数 pass/exception projector 不再产生 subject 根指针 `json_pointer=""`，关键
   objective、summary、status、计数、claim、限制、来源和 audit check 都有冻结指针；64项以内逐项
   展示，超限集合退为单个完整子树指针；
5. 当前 TCAD execution projector 不再默认展开 project/review/capability 整棵树，但完整 raw subject
   仍可展开/下载；
6. 用最大合法集合覆盖 projector 退化路径，证明原本合法的参数/coverage/已解析输入不会因
   `ReviewDocument` 的512项或512 KiB 上限失去审批能力；
7. 实际用当前 TCAD 资格与执行 projector 生成两张待审批页面，检查首屏信息和窄屏 CSS 计算后的
   视觉顺序；DOM 仍保持唯一表单和原有语义顺序，不要求真实求解器或重新执行科学闭环；
8. 对同一个已冻结 ApprovalRequest，只替换 renderer/CSS 前后对照，subject set、请求引用、nonce、
   CSRF 和决定语义保持不变；历史无 ReviewDocument 页面仍可逐项展开和下载全部 subjects；
9. 对新 projector 创建的请求，subject refs、subject-set hash、选项和 compiled approval identity
   仍绑定同一科学对象；允许 ReviewDocument、请求引用和新 nonce 正常变化，且不得继承旧决定；
10. 聚焦 UI/Approval/TCAD projector 测试、安装态审批测试、`git diff --check` 与独立审查通过。

## 4. 明确不做

- 不新增 ReviewDocument item kind、Schema 字段、数据库列、UI 路由、API 或前端框架；
- 不允许插件提供 HTML、CSS、JavaScript 或模板；
- 不在核心按插件名、Operation、领域 Schema 或 JSON 字段分支；
- 不用 JavaScript 保存展开状态，不增加用户偏好或 UI 状态机；
- 不截断、删除或替换精确冻结对象，不改变下载字节；
- 不把“页面更易读”解释为科学资格自动通过，也不修改人工审批门；
- 不顺手重做 dashboard、实例管理、颜色主题或无关视觉样式。

## 5. 停止条件

如果实现需要核心理解 TCAD、增加通用摘要 DSL、持久化 UI 状态或修改审批生命周期，立即停止并
重新审视。H5 只利用现有固定 `ReviewDocument + JSON Pointer + 折叠 raw` 能力消除信息重复。

方案独立审查通过前不修改生产 UI 或领域 projector；实现完成后必须由新的独立审查者同时检查可读
性、安全边界和轻量化目标，未通过不进入 H6。

首轮独立方案审查见
`reviews/R5_H5_APPROVAL_UI_READABILITY_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告 SHA-256
为 `18f47282fc4881225503dc878d10a968b34c4964cd6dd85149b513cf8736c6ed`，结论“打回”。第二轮候选只
闭合大集合展示预算、冻结 objective 和新旧请求身份语义，不扩大实现范围。

第二轮独立方案复审见
`reviews/R5_H5_APPROVAL_UI_READABILITY_PLAN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，主代理核验报告
SHA-256 为 `51084eea56552e3db96fac9c12d45b8449fe3023fe0a6a69f43362727d31036b`，结论“通过”。

## 6. 实施候选记录

- 核心 renderer 只删除原始 subject 的默认展开；窄屏 CSS 只把唯一决定栏排到正文之前，桌面
  sticky、表单、脚本、CSP、下载和审批生命周期均未改变；
- TCAD 参数资格和外部执行 projector 改用已有 `ReviewDocumentItem + JSON Pointer` 显式列出
  决策字段，参数、覆盖和执行输入的64项展示阈值只存在于两个插件模块，超过时退为完整集合子树；
- 真实参数审批首次暴露通用审批服务把数组索引1至9误判为非法的旧缺陷；修复只统一为渲染器已经
  使用的“十进制且无前导零”规则，并增加索引1正例和01负例，没有新增入口校验；
- 真实参数和执行审批页面、固定 renderer、历史回退与领域 projector 聚焦47项通过；包含一次决定
  与执行身份的较完整审批回归53项通过；
- 首轮全量 Operation 回归为314项通过、1项因 H3 冻结生产行数过期而失败。重复构造随后收敛为
  两个插件局部小函数，生产增量由240行降至177行；复杂度哨兵更新为150个文件/59305行，文件数、
  `operations/` 规模和唯一 catalog 均未变化；
- 更新复杂度哨兵后，`tests/operations` 315项全部通过，用时109.27秒；部署、平台配置与33项架构
  约束38项全部通过，用时6.84秒；`git diff --check` 通过。当前候选尚未独立实现审查，不自行
  宣称 H5 通过，也不放行 H6。

首轮独立实施审查见
`reviews/R5_H5_APPROVAL_UI_READABILITY_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告
SHA-256 为 `e37bd7704480bfea022ccd566540e4e5f5fe50c3aff5a946c6b536808e69bd25`，结论“打回”。报告确认总体
边界正确，但发现合法256字符领域键会把展示标签撑过上限，以及数组 Pointer 错把 Unicode 数字
当作索引。

## 7. 首轮实施审查后的最小返修

- 参数、覆盖和执行输入均改为先判断64项阈值，再决定构造逐项视图或一个完整集合子树；合法大集合
  不再先创建数千个即将丢弃的展示项；
- 参数与来源标签只使用固定序号，完整 `parameter_key`/`source_key` 由精确 Pointer 从冻结对象
  显示，不截断领域键、不复制科学值、不新增 item kind；来源明细不存在超过64项的可达路径，因为
  当前独立审计合同最多容纳32个来源，故删除了无效的来源回退分支；
- 服务端和固定 renderer 的既有数组 resolver 均限定为 ASCII `0` 或无前导零的十进制索引；继续
  拒绝01、越界、错误容器、阿拉伯数字和上标数字，不增加新校验层；
- 新边界测试覆盖256字符参数键和来源键、512个参数/覆盖项、4096个已解析执行输入及上述 Pointer
  正负例；H5 三个文件聚焦49项全部通过；
- 当前生产 Python 仍为150个文件，59317行；相对 H3 净增189行，`operations/` 仍为7个文件/
  2064行，唯一 catalog 不变；R0 核心职责因两个既有 Pointer resolver 的严格化净增5行至9518行，
  Task 职责仍为6031行；
- 返修后 `tests/operations` 317项全部通过，用时106.91秒；部署、平台配置与33项架构约束38项全部
  通过，用时5.57秒；`git diff --check` 通过。候选待新的独立复审，H6 仍未放行。

第二轮独立实现复审见
`reviews/R5_H5_APPROVAL_UI_READABILITY_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，主代理核验
报告 SHA-256 为 `ad4d776df01bf4be5c60fa2b189783d3177adbdd70d8840dd601f514e308a4b7`，结论“通过，仅放行
H6”。复审独立运行16个聚焦用例，确认首轮两项阻断、轻控制面、插件所有权和复杂度边界均闭合；
本机缺少浏览器的桌面/窄屏视觉舒适度检查保留为非阻断人工项，不虚构截图证据。

## 8. 真实完整闭环暴露的未闭合问题

2026-09-03，在最新 M7 代码、独立调试服务和真实 Fig.4 科学闭环中，用户实际查看证据资格审批页后
确认：**审批内容几乎完全不可读**。因此，H5 的结构测试和独立复审只能证明 renderer、冻结对象、
指针与决定语义没有破坏，不能证明页面已经达到人工决策可用性；先前“审批 UI 可读性修复完成”的
产品层结论应降级为“安全与结构改进完成，真实可用性未验收”。

本轮用户为跑完一次调试闭环而暂时作出的通过决定，不得作为 UI 可读性验收证据，也不得掩盖该
缺陷。后续必须基于真实审批样本重新处理以下最小问题：

- 首屏先回答“正在决定什么、关键证据是什么、主要风险/缺口是什么、通过会允许什么”；
- 隐藏控制身份、摘要、父链和大段原始 JSON 等默认不影响决定的技术噪声，仍保留按需核查入口；
- 对长列表、嵌套对象、空值和机器字段提供可扫描的层级、表格或摘要，不要求用户理解内部 Schema；
- 用真实桌面浏览器和真实 TCAD 审批对象进行人工可读性测试，不能再以 DOM/CSS/单元测试替代；
- 不改变封存事实、审批权威或 OperationSpec 边界，不为修 UI 新增控制状态机或通用展示语言。

该问题记为后续产品缺陷 `UI-READ-002`，优先级 P1；不阻断本次调试闭环，但阻断将当前审批界面宣称
为可供常规科研使用的完成态。
