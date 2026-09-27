# R5-H5 审批 UI 可读性实施独立审查

日期：2026-08-31  
审查对象：`R5_H5_APPROVAL_UI_READABILITY.zh-CN.md` 当前实施候选  
审查性质：只读、对抗式实施审查；未修改生产代码、测试或计划

## 结论

**打回。**

候选已经从结构上解决了原反馈的主要成因：决策问题和编译视图先出现，raw subjects 默认折叠，
窄屏通过 CSS 把唯一决定栏排到正文之前，历史对象和精确下载仍保留；核心 renderer 也保持固定、
转义且领域中立。两个 TCAD 投影继续由插件通过同一个编译 `OperationSpec` 注册，没有新增状态、
数据库列、路由、注册表、前端状态或第二套展示权威。

但当前实现仍有两个可由合法输入触发的阻断。第一个会直接让合法科学对象失去审批能力；第二个使
本轮顺带修复的通用数组 Pointer 规则并非其声明的严格十进制规则。二者都可局部修正，不需要新增
框架、摘要 DSL、通用领域 Schema、入口校验或状态机。H5 未通过，不放行 H6。

## 阻断项

### B1：合法 256 字符领域 key 会使投影失败，且 eager 构造削弱了 64 项回退

`Identifier` 合法长度上限是 256 字符（`schema/common.py:15`—`21`），
`ReviewDocumentItem.label` 的上限也是 256 字符（`schema/approval.py:77`—`83`）。参数投影却把完整
`parameter_key`/`source_key` 再拼接“：选定值”“：单位”“：认识状态”“：标题”“：来源类别”或
coverage status（`parameter_operations.py:542`—`610`）。因此，一个完全合法的 256 字符 key 会生成
259—261 字符的 label，并在 `ReviewDocumentItem` 构造时被 Pydantic 拒绝。

本审查的只读探针已确认：256 字符 ASCII key 可由 `Identifier` 严格验证接受，而上述三类实际 label
分别以 `string_too_long` 被拒绝。该失败发生在插件 projector 内，随后由真实调用入口包装为
`approval_projector_failed`（`mcp_root_operation_routes.py:244`—`260`），ApprovalRequest 尚未创建，
所以用户没有任何审批或下载入口。

这不只影响 64 项以内的详细路径。`claim_items`、`coverage_items` 和 `source_items` 都先为完整集合
构造全部 item，再在 `len(...) > 64` 时替换成集合子树 Pointer。长 key 会在回退分支执行前失败；
同时最多 512 项的明细被无谓构造后丢弃。现有大输入测试只使用 65 个短 key：参数测试覆盖 claims
和 exception coverage 回退，但来源始终只有 2 项；执行测试覆盖 65 个 resolved inputs。它们没有
覆盖 64 项最坏展开、256 字符合法 key、512 项参数/来源/coverage 或 4096 项 resolved inputs，因而
不能证明“所有合法对象仍可审批”。

最小修复：在三个参数集合上先判断 64 项阈值，再构造详细 item；详细标签使用固定序号短标签，并
通过精确 Pointer 展示完整 key，或用一个现有 `json_tree` item 指向单项子树。不要截断 key，也不要
新增 item kind。把现有测试补成至少一个 256 字符合法 key 的详细路径，以及模型允许的最大集合
回退；测试必须真实构造 `ReviewDocument`。execution 的纯长度分支可继续使用现有局部常量，但应以
4096 项合法输入验证一次。该修复也删除了当前唯一应立即删除的重复工作：超过阈值后仍先构造全部
明细。

### B2：数组 Pointer 使用 Unicode `isdigit()`，不是严格 ASCII 十进制规则

服务端和 renderer 当前都以 `token.isdigit()` 判断数组索引
（`service/approvals.py:1249`—`1267`；`approval_ui/render.py:337`—`353`）。这使二者对常见 ASCII
输入保持一致，并正确接受 `1`、拒绝 `01`、拒绝 ASCII 越界和错误容器类型；但 `isdigit()` 不是
JSON Pointer 数组索引所需的 ASCII `0` 或无前导零 `[1-9][0-9]*`。

只读探针证明，`/items/١` 被服务端和 renderer 同时接受为索引 1；`/items/²` 又在 `int()` 处泄漏
未归一化的 `ValueError`。现有测试 `test_review_document_array_pointer_rejects_leading_zero_at_service_boundary`
只覆盖 `0`、`1` 和 `01`，没有覆盖越界、错误容器或 Unicode 数字。因此，本轮“1—9 修复”方向虽
最小，却尚不是严格且封闭的正确修复。

最小修复：在现有两个局部 resolver 中使用完全相同的 ASCII 数组索引条件，并扩展现有单个测试
覆盖 `1`、`01`、越界、错误容器、阿拉伯数字和上标数字。服务层继续把失败归一化为
`ApprovalError`。这只是修正既有 resolver，不增加第二层入口校验或新协议。

## 逐项审查

### 1. 可读性、历史回退和下载

- `render.py:80`—`89` 的顺序是审批问题、编译文档、折叠 raw、唯一决定栏；编译文档不是
  `<details>`，默认可见。
- raw subject 在 `render.py:225` 不再带 `open`；请求技术信息在 `render.py:316` 仍默认折叠。
- CSS 桌面保留 330 px 右栏和 sticky（`style.css:85`—`92`），窄屏用 flex 与 `order: -1` 把决定栏
  放在正文前（`style.css:215`—`220`），没有移动 DOM 或复制表单。
- 无 ReviewDocument 的历史请求仍显示固定回退和全部 raw；每个对象仍含精确元数据、完整 JSON
  树和受控 `/subject/...` 下载。HTTP 测试也核对二进制不内联、下载字节相同、旧 preview 路由关闭。

当前环境没有 Chromium/Firefox，也没有 Playwright/Selenium；本报告只有 HTML 结构、CSS 规则和
HTTP 字节证据，没有真实浏览器计算样式、首屏截图或窄屏视觉证据。实施记录所述真实页面检查没有
提供可由本审查复核的原始截图或浏览器输出，不能把上游摘要当成独立视觉证据。B1/B2 修复后仍应
用真实参数与 execution 页面完成计划要求的桌面和窄屏人工检查。

### 2. 固定核心与插件所有权

核心 `render.py` 只理解五种固定 `ReviewDocumentItem`、subject 序号、JSON Pointer、转义、下载和
通用 compiled identity；没有 TCAD、插件名、Operation ID 或领域 Schema 分支。其控制面 kind 标题
只是既有通用控制审批回退，不解释科学对象。参数 pass/exception projector 位于
`tcad_artifact.parameter_operations`，execution projector 位于 `tcad_artifact.runtime_plugin`；两者
分别通过 TCAD 插件的 `ComponentSpec` 和 `ApprovalContract.projector` 注册
（`parameter_operations.py:1020`—`1077`、`1170`—`1197`；`plugin.py:514`—`517`、`599`—`640`）。

### 3. 状态、注册表、Schema、路由和展示权威

本候选没有新增 ReviewDocument kind、Schema 字段、数据库表/列、HTTP 路由、JavaScript 存储、用户
偏好或 UI 状态机。`app.js` 仍只切换理由必填并在提交时禁用按钮。两个 64 项常量仅存在于 TCAD
插件局部，不参与 catalog、admission 或核心 Schema。ReviewDocument 只冻结标签、subject 序号和
Pointer；值由固定 renderer 从同一冻结 subject 读取，因此没有第二份科学值权威。

### 4. 64 项退化、对象完整性和预算

对于普通短 key，参数最坏详细形态为 396 项：4 个结论、2 个 foundation 字段、192 个 claim 字段、
2 个限制字段、64 个 coverage issue、128 个来源字段和 4 个 audit status，低于 512 项；execution
在 64 个 resolved inputs 时为 87 项。ReviewDocument 不复制被指向的科学值，正常情况下也远低于
512 KiB。超过阈值时使用 `/claims`、`/items`、`/sources` 或 `/resolved_inputs` 完整子树，raw 和
下载字节均不变，没有截断 subject。

但 B1 证明标签边界和 eager 构造会在合法对象上先失败，故该维度当前不通过。测试也只证明第 65
项触发分支，没有覆盖来源回退、64 项最坏字节形态和模型最大集合。

### 5. 通用数组索引修复

ASCII `1` 修复与 renderer 当前行为一致，`01`、ASCII 越界和错误类型在代码路径上会失败；B2 所述
Unicode 接受/异常说明实现还不满足严格十进制语义，且负例不足，因此该维度不通过。

### 6. 复杂度与局部辅助函数

独立运行 `scripts/r5_current_metrics.py` 得到生产 Python 150 文件/59,305 行；H3 冻结值为 150 文件/
59,128 行，净增 177 行且文件数不变。`operations/` 仍为 7 文件/2,064 行，catalog 仍只有一个
`CompiledCatalog` 构造点。新增行主要是两个明确的领域投影，规模对可读性目标本身合理，不能仅因
行数打回。

两个 `_review_item` 都只是局部四参数构造器，没有条件分派、注册或组合语义，不构成小型 DSL，也
不值得提取成通用抽象。应立即删除的是 B1 指出的“先构造全量明细、再丢弃”路径；未发现其他必须
立即删除的生产重复或针对单一断言的补丁。

### 7. 不可变身份、一次决定和旧决定

ReviewDocument 和 compiled identity 都进入创建输入与 ApprovalRequest 冻结字节；subject refs 与
subject-set hash 不变。决定仍绑定 request ref、完整 subject refs/hash、nonce、CSRF 和 UI session，
SQLite 仍以 pending compare-and-set、唯一 nonce 和 append-only 决定表保证一次决定
（`approvals.py:136`—`276`、`583`—`740`）。本轮 renderer/CSS 没有接触这些路径。

聚焦测试证明改变 subject 会创建 pending revision 且不带旧 selected option，compiled provider
identity 漂移或插件移除不能授权执行，installed UI 重复提交只返回同一决定。未发现 H5 代码把旧
decision ref、nonce 或 CSRF 写入新请求的路径。现有测试没有单独构造“同 subjects、仅新
ReviewDocument”的 H5 对照；修复后可在既有 revision 测试中补一个精确断言，但当前没有证据表明
生产代码已发生旧决定继承。

### 8. 独立复测和上游证据归属

所有命令均先执行 `ulimit -v 7340032; export MALLOC_ARENA_MAX=2`，串行运行：

1. H5 三个相关测试文件：47 passed，10.75 s；
2. `test_r4_execution_approval_identity.py`：5 passed，3.10 s；
3. installed `test_baseline_approval_ui.py`：1 passed，42.05 s；
4. `test_r5_catalog_stages.py` 加架构约束矩阵：5 passed，1.51 s；
5. 四个目标 Python 模块 `compileall -q`：通过；
6. `git diff --check`：通过。

前 3 组精确复现实施记录中的 53 项审批/身份/一次决定证据。未重跑 315 项完整 Operation suite；其
`315 passed` 仅作为主代理实施记录复用。部署、平台配置与约束矩阵已确认恰好收集 38 项，本审查
只在第 4 组重跑了其中的约束矩阵；`38 passed` 其余部分同样属于复用证据。当前相关插件和测试文件
在工作树中仍是 untracked，普通 `git diff --check` 不覆盖这些文件；本报告的结论以直接源码审查、
导入/测试执行和上述反例探针为准，不把机械差异检查扩大成发布资格。

### 9. 33 项约束、OperationSpec 中心和奥卡姆目标

33 项矩阵结构仍完整；H5 直接相关的 HIL、IMM、PLG、UI、SEC 和 RES 边界未出现新状态或权威。
projector 仍由一次插件注册进入唯一启动编译目录，核心不新增领域分支，Approval/Execution 生命周期
也未加重。整体实现符合轻控制面和奥卡姆方向。

当前偏离集中于 UI-001/UI-002 与“合法对象不得因展示失去审批能力”：B1 使某些合法 key 无法形成
页面，B2 使固定安全 Pointer 合同不够严格。最小局部修复并补足边界测试后，应由独立审查重新核对
这两个阻断和真实浏览器视觉证据；通过时也只能放行 H6，不能宣称 R5 完成。
