# R5-H5 审批 UI 可读性方案独立审查

日期：2026-08-31  
审查对象：`docs/plans/R5_H5_APPROVAL_UI_READABILITY.zh-CN.md`  
审查性质：只读方案审查；未修改生产代码或被审查计划

## 结论

**打回。**

方案的主方向正确，而且已经接近解决当前已实证问题所需的最小改动：删除原始对象的默认展开、
只用既有 `ReviewDocument + JSON Pointer` 改写两个 TCAD projector、在窄屏用 CSS 调整决定栏的视觉
顺序。它没有引入新的前端框架、摘要 DSL、领域核心分支、注册表、审批状态或控制面入口校验；
TCAD 外部执行和无 `ReviewDocument` 的历史安全回退也都进入了验收范围。

但当前文本仍有三个会把正确实现导向失败或错误验收的阻断点。它们都可在原计划内做小幅修订，
不需要扩展协议或增加控制面复杂度。

## 阻断项

### B1：逐项摘要没有闭合既有模型与 `ReviewDocument` 的数量边界

计划第 35—40、51—53 行要求逐个展示 claim、来源、非确认 coverage 项和已解析输入；但当前严格
模型允许：

- `DeviceParameterSet.claims` 最多 512 项；
- `DeviceParameterCoverageReport.items` 最多 512 项；
- `EvidenceSourceCatalog.sources` 最多 512 项；
- `ReviewedDeckPackage.resolved_inputs` 最多 4096 项。

而 `ReviewDocument` 全文最多 512 个 item、512 KiB，单个 label 最多 256 字符。来源标题本身最多
2048 字符。按计划直接逐项构造会使一批原本合法、且旧 projector 可以审批的对象在创建审批请求时
因展示文档超界而失败；若直接把来源标题复制进 label，还会单独触发 label 上限。这不是性能优化，
而是新的功能回归。

最小修订应明确：

1. 标签只使用固定短标签、序号或有界 `source_key`/`parameter_key`，不把长标题复制进 label；标题
   仍通过精确指针读取；
2. 在逐项明细不超过既有 `ReviewDocument` 预算时才逐项展示；超过预算时，退化为少量、固定的现有
   `json_tree` item，分别指向 `claims`、`items`、`sources` 或 `resolved_inputs` 子树，并明确完整对象
   仍在折叠区和下载中；
3. 该退化只放在 TCAD projector 内，不提高核心上限、不新增 item kind、不新增摘要协议，也不把
   “展示过大”做成控制面准入规则。

同时增加覆盖大集合的 projector 测试，证明合法 TCAD 对象不会因为摘要而失去审批能力。

证据位置：

- `src/scidiscovery/artifact_agent/schema/approval.py:77`—`141`；
- `plugins/tcad_artifact/tcad_artifact/device_parameters.py:268`—`371`；
- `plugins/tcad_artifact/tcad_artifact/project_packager.py:742`—`751`。

### B2：“研究目标与参数”没有指向被冻结的研究目标

计划第 36 行只列出 foundation `summary`，没有列出 foundation `objective`。页面顶部的实例目标来自
实例上下文，不是本次资格决定所绑定 subject 中的科学目标；二者不能互相替代。原始对象改为默认
折叠后，用户可能在摘要区看不到自己实际批准的参数目标。

最小修订是在“研究目标与参数”中增加 foundation `/objective` 的精确 JSON Pointer，并在验收中
断言该指针存在。无需派生新字段，也无需让核心理解 TCAD。

证据位置：

- `src/scidiscovery/artifact_agent/schema/scientific_foundation.py:133`—`148`；
- `src/scidiscovery/artifact_agent/approval_ui/render.py:176`—`203`。

### B3：验收第 7 项混淆了“重排同一冻结请求”和“改变 projector 产生新请求”

计划第 68—69 行要求优化前后的 subject、compiled identity、选项、nonce 和决定绑定全部不变。
这对“同一个已冻结 `ApprovalRequest` 只换 renderer/CSS”成立；但对 projector 改动并不成立：
`ReviewDocument` 是 `ApprovalRequest` 的冻结内容，projector 变化会改变请求字节和请求引用，新建请求
也会生成自己的 nonce。不能为了满足该断言复用旧 nonce、旧请求引用或旧决定。

最小修订应把验收拆成两条：

1. 对同一冻结请求做 renderer 前后对照，断言 subject set、请求引用、nonce、CSRF 和决定语义完全
   不变；
2. 对新 projector 请求，断言 subject refs、subject-set hash、选项和精确 compiled approval identity
   仍绑定同一科学对象，但允许 `ReviewDocument`、请求引用和新请求 nonce 正常变化，且不得继承旧
   决定。

证据位置：

- `src/scidiscovery/artifact_agent/schema/approval.py:152`—`204`；
- `src/scidiscovery/artifact_agent/service/approvals.py:148`—`264`。

## 非阻断项

1. 计划第 66—67 行所说“窄屏 DOM/CSS 顺序”应改为“窄屏计算后的视觉顺序”。计划明确不移动
   DOM，因此验收不能同时要求 DOM 中决定栏位于正文之前；CSS `order` 的实际效果和桌面 sticky
   保留才是正确检查对象。
2. 最终可读性检查应优先使用已封存的真实 D4 参数资格 subjects，并使用一个真实结构的 TCAD
   execution request/package；不需要重跑 solver。小型合成 fixture 可以保留做单元测试，但不能独自
   关闭两次真实现场反馈。
3. 历史回退在 raw 默认折叠后应增加一个明确断言：无 `ReviewDocument` 的历史页面仍能逐项展开并
   下载全部 subjects。现计划第 59、64—65 行已经覆盖大方向，只需把该检查写实。

## 已确认正确的边界

- `_render_raw_subjects` 当前确实给每个 subject 写入 `open`；删除该属性是直接、低风险修复。
- 参数资格 projector 当前确实对每个 subject 产生根 `json_pointer=""`，造成编译视图和 raw 区
  重复全量展示。
- TCAD execution projector 当前确实默认展开 `/project`、`/review`、`/capability` 和
  `/resolved_inputs` 四棵树；计划已覆盖这一生产路径。
- 窄屏当前将 `.review-layout` 改成纵向 flex，但没有改变两个子元素顺序；只加既有 CSS 的视觉顺序
  即可，不需要 JS 或第二份表单。
- 服务层会在审批请求创建时验证每个 JSON Pointer 对应的 subject、媒体类型、JSON 解析和实际路径；
  projector 已先用严格领域模型解析对象，因此无需再增加入口校验。
- 完整 subject、受控下载、subject-set hash、compiled identity、nonce/CSRF 和决定写入权威仍由现有
  Approval 合同持有；固定 renderer 继续统一转义，插件没有 HTML/CSS/JS 注入入口。
- 计划没有遗漏 TCAD execution 或历史回退，也没有引入核心领域理解、前端状态、前端框架或插件
  私有 renderer。

## 放行条件

只需在原计划中闭合 B1—B3，并补充对应验收；不要求设计新的通用摘要系统。修订后若仍保持
“核心 renderer 两处小改 + 两个 TCAD projector 重排 + 聚焦测试”的范围，可直接进入一次独立复审。

