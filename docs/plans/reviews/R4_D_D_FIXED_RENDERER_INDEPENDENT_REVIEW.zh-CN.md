# R4-D-D 固定安全渲染器独立审查

## 结论

**通过，允许 R4-D 收口。**

本轮没有发现阻塞项。实现已经把审批 UI 从按科学基础、图证据、器件参数和 TCAD Schema 分派的领域工作台，收缩为读取冻结 `ApprovalRequest`、固定 `ReviewDocument` 和精确 subjects 的通用渲染器；非 JSON 内容没有内联预览路径，历史无文档请求不依赖已安装插件，既有人工决定与实例/会话控制面也没有产生第二权威。该实现符合 R4-D-A/B/C 已冻结的轻控制面、最小授权、通专分离和单一 Operation 目录边界。

## 审查范围与方法

本轮只读核验了：

- `src/scidiscovery/artifact_agent/approval_ui/render.py`、`app.py` 及静态 JS/CSS；
- `ReviewDocument`、`ApprovalRequest`、ReviewManifest 和 ApprovalService 的创建、读取、决定路径；
- Root `operation_catalog` 的四种视图投影；
- 三类科学审批、执行审批及固定渲染器测试；
- 计划第 7.4、7.5、7.8 节和已通过的 R4-D-A/B/C 边界。

所有 pytest 均在同一进程串行执行，命令前设置 `ulimit -v 7340032`，没有启用 xdist 或其他并行方式。

## 边界核验

### 1. 核心不再解释领域 Schema

`render.py` 当前为 370 行。入口只从 `ApprovalRequest.review_document` 选择固定文档或固定历史回退（`render.py:45-66`），没有读取 compiled catalog，也没有按 scientific foundation、figure、device parameter、problem 或 TCAD Schema 选择标题、页签或字段。文件内唯一按 kind 区分的 `_CONTROL_KIND_TITLES` 只有实例创建和会话绑定四个兼容名称（`render.py:26-31`），属于计划明确保留的控制面页面，不是领域 renderer。

源码搜索确认旧领域 schema id、`_render_tcad`、`_render_device_parameter`、`_render_figure`、`_render_scientific_foundation` 和 preview 逻辑均不在固定渲染器、JS 或 CSS 中。领域插件只能在审批创建前通过编译合同产生 `ReviewDocument` 数据，不能给 UI 注册 callable 或模板。

### 2. 五种 item、冻结 subject 与严格指针边界闭合

`ReviewDocumentItem.kind` 是精确五值联合：`json_value`、`json_tree`、`status`、`subject_metadata`、`download`（`schema/approval.py:77-93`）。前三种必须带经 `parse_json_pointer` 校验的指针，后二种禁止指针；document 同时限制 64 节、512 项和 512 KiB，request 再限制最多 256 个精确 subject，并验证 item 的 subject index（`schema/approval.py:122-184`）。

审批创建先对冻结 subject 执行 `_verify_review_document`（`service/approvals.py:152-153,935-969`）：指针 subject 必须是 JSON，目标必须存在；严格解析拒绝非法 `~` 转义，数组解析拒绝前导零、越界和标量穿越。渲染时 item 只能通过 `review.subjects[subject_index]` 和该指针读取值（`render.py:129-154,337-354`），不存在另一个对象查找入口。

所有插件可控标题、说明、标签、状态、JSON 值、身份和审批元数据均在写入 HTML 前转义（`render.py:67-89,95-125,129-158,243-325,357-367`）。`ReviewDocument` 没有 HTML、URL、CSS、脚本、模板、媒体源或 disposition 字段。恶意 `<script>`、`<style>`、SVG、iframe、img、`javascript:` 和 `data:` 负例已由真实渲染测试覆盖。

### 3. 非 JSON、下载与历史审计路径正确

完整原始对象始终显示。声明为 JSON 的 subject 只在解析后以转义后的 `<pre>` 展示；其他媒体类型只显示冻结元数据和下载按钮，字节不会内联（`render.py:207-240`）。HTTP 层只有固定 `/subject/<approval>/<index>` 路由，先通过 ApprovalService 的 token 和精确 request/manifest 校验，再固定返回 `application/octet-stream`、`Content-Disposition: attachment; filename=subject-{index}.bin`（`approval_ui/app.py:245-260`）。响应统一带 `nosniff`、CSP、`frame-ancestors 'none'`、`base-uri 'none'` 和 `no-store`（`app.py:623-647`）。旧 `/preview` 路由及 raster helper 已删除，真实 HTTP 负例返回 404。

没有 `ReviewDocument` 的请求只进入固定 raw fallback（`render.py:161-173`）。该路径只读取 CAS 中的不可变 request、manifest 和 subjects；`render.py` 不导入插件或 Operation catalog，因此插件卸载后不会为了历史显示重跑 projector。测试使用历史 TCAD schema 证明其只显示通用历史标题、固定回退和完整 raw tree，不恢复 TCAD 专用页面。

### 4. 既有控制面与唯一决定权威保持不变

实例归属上下文仍由既有 SchedulerBinding 查询后作为只读 `ReviewContext` 传入，实例创建和会话绑定保留固定控制面标题及完整原始对象。决定表单仍提交到原有 `/review/<id>/decision`，携带既有 access token、CSRF、nonce 和本地身份（`render.py:255-299`）；决定写入继续由 ApprovalService 执行 nonce、CSRF、精确 subjects 和唯一终态检查，没有新增 UI 决定状态或写入路径。

静态脚本只有 17 行，仅切换“理由是否必填”及提交后禁用按钮；没有 `innerHTML`、动态请求、URL 跳转、脚本执行或插件扩展点。CSS 为 231 行固定布局，没有 `url()`、`@import` 或领域对象选择器，未把旧 Python renderer 的复杂度转移到浏览器层。

### 5. 四种目录视图仍是同一目录投影

`OperationCatalogInput.scope` 只允许 `public`、`support`、`internal`、`all`（`mcp_root.py:105-106`）。`operation_catalog` 每次只取得一次同一 `CompiledCatalog.scheduler_projection()`，再按 `catalog_scope` 过滤；`all` 仅返回同一投影全集（`mcp_root.py:1187-1195`）。R4-D-D 没有增加 UI 目录副本、renderer registry、状态表、权限表或摘要分叉。

安装态测试继续确认 public 只包含 public Agent/approval，support 只包含同一目录中的 transform，internal 只含内部自检 Operation，all 是其同源全集；各视图不暴露实现身份或另建调用路径。

## 可复现验证

精确复现计划中的 46 项聚焦检查：

```bash
ulimit -v 7340032
PYTHONDONTWRITEBYTECODE=1 pytest -q \
  tests/operations/test_r4_approval_operation.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_operation_invoke_installed.py \
  tests/operations/test_runtime_plugin_configuration.py
```

结果：`46 passed in 32.01s`。

另外独立得到：

- 在上述组合上再加入基线审批 UI 和通用科学插件测试：`56 passed in 38.61s`；
- `pytest -q tests/operations`：`211 passed in 66.97s`；
- `pytest -q`：`245 passed in 72.00s`；
- `git diff --check`：通过；
- `render.py`、`app.py`、审批 schema/service 和专项测试五文件内存编译：通过；
- 领域 schema/旧 renderer、preview、危险 DOM API、外链 CSS/JS、渲染注册表与新增状态搜索：无命中；唯一 `state` 命中是 JS 的局部理由提示元素。

## 简化性与收口判断

这次变化是删除领域 UI 解释层，而不是增加一个更抽象的渲染框架：核心只保留五种数据 item、严格 pointer、完整 raw 审计、固定附件下载和既有决定表单。插件负责声明“显示冻结 subject 的哪个位置”，核心负责边界与安全，不负责理解科学内容。没有新增实体、注册表、权限维度或生命周期，因而没有发现复杂度反噬。

根发布清单按计划须在本独立报告纳入后再统一冻结；该机械步骤不构成本轮实现阻塞，也不应在报告落盘前被误称为已经完成。
