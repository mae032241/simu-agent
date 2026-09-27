# R5-H5 审批 UI 可读性实施第二轮独立复审

日期：2026-08-31
审查对象：`R5_H5_APPROVAL_UI_READABILITY.zh-CN.md` 首轮实施审查后的当前返修候选
审查性质：只读、对抗式独立复审；除本报告外未修改生产代码、测试或计划

## 结论

**通过。仅放行 H6，不宣称 R5 完成。**

首轮 B1、B2 均已由局部修复关闭。合法 256 字符领域键、512 项参数/覆盖集合和 4096 项执行输入均
穿过严格模型与实际 projector；大集合不会先构造即将丢弃的展示项，固定短标签也不截断或复制科学
值。服务端和 renderer 的数组 Pointer resolver 现在使用相同 ASCII 索引语义，规定的正负例均受控
失败。整体实现仍是固定 renderer/CSS 的小改和两个 TCAD 插件自有 projector，没有增加展示协议、
状态或第二权威。

本机没有浏览器、Playwright 或 Selenium，因此本复审没有截图或真实浏览器 computed-style 证据。
这是明确的残余人工视觉验收项，但不是本轮阻断：当前视觉变化只依赖原生 `<details>` 的 `open`
属性是否存在，以及一个无 JavaScript 状态的静态 flex `order` 规则；真实参数和执行审批生产路径已
生成并检查 HTML，DOM、CSS 和 renderer 测试又对决定栏唯一性、折叠状态和桌面/窄屏规则作了精确
断言。没有复杂几何、异步布局或脚本重排需要浏览器才能判定实现语义。

## 首轮阻断复核

### B1：合法键、最大集合与 eager 构造——已关闭

1. `parameter_operations.py` 先严格解析 `ScientificIntake`、`ScientificFoundation`、参数要求、
   `DeviceParameterSet`、`EvidenceSourceCatalog`、`DeviceParameterCoverageReport` 和 `EvidenceAudit`，
   并完成输出族、父链、确定性 coverage 重算及独立审计闭包，之后才构造 `ReviewDocument`。
2. 参数主张在 `len(selected.claims) > 64` 时直接生成一个 `/claims` 子树 item；只有不超过 64 项时
   才构造逐项 `ReviewDocumentItem`。coverage 先收集至多 512 个问题项的索引/严格对象引用，阈值判断
   后才构造展示 item；超过 64 个问题项直接退为 `/items`。这不是先构造数百个展示项再丢弃。
3. 参数与来源标签只含固定序号，例如“参数 1：参数键”“来源 1：来源键”。完整
   `parameter_key`/`source_key` 分别由 `/claims/N/parameter_key` 和 `/sources/N/source_key` 从冻结
   subject 读取；`selected_value`、单位、认识状态和来源详情同样只以 Pointer 读取。没有字符串截断，
   `ReviewDocument` 中也没有复制这些科学值。
4. 来源回退分支的删除有严格闭包依据，不是遗漏：`EvidenceAudit.evidence` 最多 32 项且键唯一；资格
   projector 又要求 catalog 的唯一 `source_key` 集合是该 audit 证据键集合的子集。因此能到达展示
   构造的 catalog 来源最多 32 项，永远不会触及 64 项阈值。
5. 256 字符 key 聚焦测试通过严格模型和编译 Operation 的实际 projector。附加只读探针确认两个
   Pointer 均解析出完整 256 字符值、最大展示标签长度为 26，且两段 256 字符值均未出现在
   `ReviewDocument` 的冻结 JSON 中。
6. 512 项 exception projector 的只读调用计数为 18 个 `_review_item`，证明没有 eager 构造 512 组
   明细。最大集合测试实际构造 `ReviewDocument`，因而同时经过其 512 item/512 KiB 模型门。
7. 最坏逐项形态仍闭合：64 个 claim 最多 256 items、64 个 coverage issue、最多 32 个来源的 64
   items，加固定的资格/目标/限制/audit items，总数最多 396，低于 512。标签和 Pointer 均为固定、
   短、有界文本，不含最长科学值，512 KiB 预算保持充足余量。

### B2：严格 ASCII 数组索引——已关闭

`service/approvals.py::_json_pointer_value` 与
`approval_ui/render.py::_json_pointer_value` 使用同一条件：仅接受 `0`，或首字符属于 `1`—`9` 且
其余字符全部属于 ASCII `0`—`9`。两处都先用共同的 `parse_json_pointer` 解码。

聚焦测试同时覆盖：`1` 通过；`01`、越界 `2`、错误数组 token、穿过标量、阿拉伯数字 `١` 和上标
数字 `²` 失败。服务边界统一抛出 `ApprovalError`，renderer 的局部 resolver 统一抛出 `ValueError`；
不再发生 Unicode `isdigit()` 接受或 `int()` 泄漏非预期异常。该修复只严格化两个既有 resolver，
没有新入口校验层。

## 执行 projector 与短集合可读性

`runtime_plugin.py` 在严格解析 `ExecutionRequest` 与最大 4096 项的 `ReviewedDeckPackage` 并核对
compiled identity 后，先检查 `len(package.resolved_inputs)`。超过 64 项时只生成一个指向
`/resolved_inputs` 的 `json_tree` item；不枚举 4096 个展示项。只读调用计数在 4096 项输入上为
24 个 `_review_item`，即固定 23 项决策字段加一个完整集合 item。

不超过 64 项时仍逐项显示完整输入子树。真实执行审批路径测试检查工程/资源、独立审查、求解能力与
输入四类可读区；参数审批生产路径测试检查冻结目标、资格结论、研究目标与参数、来源与独立审查。
两者都确认 raw subjects 不再默认展开。

## 整体边界与安全语义

- `render.py` 的 compiled `ReviewDocument` 是普通可见 section；raw subject `<details>` 无 `open`；
  请求技术信息仍为折叠 `<details>`。历史无 `ReviewDocument` 页面仍显示全部 raw、精确元数据和受控
  下载，二进制字节不内联，旧 preview 路由仍关闭。
- 桌面仍为 330 px 右侧 sticky 决定栏；`max-width: 780px` 下父容器变为纵向 flex，唯一
  `.decision-column` 以 `order: -1; position: static` 排在 `.review-main` 前。DOM 没有移动或复制表单，
  `app.js` 仍只处理理由必填和提交按钮禁用，没有展开状态、偏好或 UI 状态机。
- 固定核心只理解 `ReviewDocumentItem`、subject 序号、JSON Pointer、统一转义和下载；源码没有
  TCAD Schema、插件名或 Operation 特判。参数与执行字段理解分别留在
  `tcad_artifact.parameter_operations` 和 `tcad_artifact.runtime_plugin`，继续由编译
  `ApprovalContract.projector` 注册。
- H5 没有新增 item kind、Schema 字段、数据库表/列、路由、注册表、前端状态、入口校验或第二
  renderer。`CompiledCatalog(` 仍只有 `operations/catalog.py` 的一个构造点；两个 64 项常量只存在于
  TCAD 插件局部。
- subject refs/set hash、冻结 `ApprovalRequest`、compiled approval identity、nonce、CSRF、UI session
  和 pending compare-and-set 路径未被本轮改动。聚焦回归确认 subject 改变会创建新的 pending
  revision 且不继承旧决定，provider qualification 仍要求精确 compiled identity。一次决定和重复
  提交语义也由主代理的完整 Operation 回归继续覆盖。

## 复杂度与奥卡姆复核

独立运行 `scripts/r5_current_metrics.py` 得到：

- 生产 Python：150 文件、59,317 行；
- `src/scidiscovery/operations/`：7 文件、2,064 行；
- R0 核心责任聚合：9,518 行；
- Task 责任聚合：6,031 行。

H3 冻结值为 150 文件/59,128 行，所以净增精确为 189 行。该增量对应两个领域 projector 的显式决策
字段、raw/窄屏可读性调整和两个既有 Pointer resolver 的 ASCII 严格化；没有新增生产文件或通用层。
两个 `_review_item` 只是各模块局部的固定构造器，没有分派、注册、组合或扩展语义，不是小型 DSL，
也不应抽成通用摘要层。返修已删除来源不可达分支，并消除了参数/执行大集合的 eager 展示构造；未
发现其他不可达 H5 分支、为单一测试写入的生产特例或应立即删除的重复工作。

## 独立复测

每组命令均先执行 `ulimit -v 7340032`、`export MALLOC_ARENA_MAX=2`，并禁用 checkout 内 pytest
缓存和 `.pyc` 写入；全部串行运行：

1. 256 字符 key、512 参数/coverage、4096 resolved input：**4 passed，1.36 s**；
2. service 与 renderer ASCII resolver：**2 passed，1.24 s**；
3. 真实参数与执行审批生产路径页面：**2 passed，2.57 s**；
4. 生产规模、Operation 包、R0/Task 聚合及 33 项约束结构：**3 passed，2.69 s**；
5. 固定转义、历史回退、下载、pending revision 和 compiled provider identity：
   **5 passed，2.76 s**；
6. `scripts/r5_current_metrics.py`：得到上述 `150/59317`、`7/2064`、`9518`、`6031`；
7. `git diff --check`：通过。

本复审实际运行 16 个 pytest case。返修记录中的 `tests/operations` **317 passed / 106.91 s** 与部署、
平台配置、33 项架构约束 **38 passed / 5.57 s** 是主代理提供并由本复审复用的证据，不冒充本复审
重跑结果。当前工作树含大量 untracked R5 文件，普通 `git diff --check` 不覆盖它们；本结论因此以
直接源码审查、严格导入/模型执行、真实 projector 路径和上述聚焦测试为主要依据。

## 残余限制

本机 `chromium`、`chromium-browser`、`google-chrome`、`firefox` 均不可用，Python 环境也没有
Playwright/Selenium。本报告没有虚构截图，也不把上游“实际页面检查”摘要当作独立浏览器证据。
在 H6 前补一次真实 D4 数据的桌面/窄屏人工视觉检查仍有价值，但只验证字体、滚动距离和视觉舒适度；
它不再阻断 H5 的实现语义，因为决定栏顺序、唯一表单、折叠状态、完整下载和精确冻结对象绑定已经
由确定性的 HTML/CSS/服务路径证据闭合。
