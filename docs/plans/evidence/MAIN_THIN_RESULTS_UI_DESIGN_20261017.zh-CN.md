# main 科学结果呈现选择性迁移：薄 UI 短设计

状态：候选设计，待 thin 独立审查后实施；未运行测试/浏览器。依据[整合评估](MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md)，main 工作树只读。已用 stdlib SHA256 重核 `workbench_render.py` 为 `5411ae6f3697beafc4cdf520b785f0dd7ace3af8737c63fe89f46b9b5a2508db`，`static/style.css` 为 `2683808df5fc266f45a25f3ed9eb970eed1d25aea7b8f2546eee9d3a2b4e3571`，与评估一致。

## 路由与权威数据

- `/results?after=N`：已封存节点入口分页，一页20条；仅检查编号/封存记录存在，不读全历史科学原件，不默认选择最近结果。列表标明打开后才核验。
- `/results/<step>`：精确节点结果页，复用 `instance_science._sealed/Original` 同 fd 验真 raw scientific JSON，再以同 seal 的 job SHA 读取 frozen job。不依赖 `control.status`/live budget，不重算历史/selection、不写缓存或新结果状态。
- 比较栏直接消费已封存 job 的 `history.view.candidates` 公共 selection 摘要，显著标“截至该节点输入时的观测范围”，不冒称包含该节点之后的发现。`proxy_highest` 仅“最佳可用观测/代理指标组”，不是 target optimum、科学 accepted 或作者推荐；方向、并列候选、exact metric、遗漏数均原样解释。无法排序/缺投影保留 unknown/gap。
- 独立科学推荐栏只取该节点 normal A 的 exact raw `candidate_recommendation`；null/audit/formal review 明确没有该推荐。原 frozen projection 的较早 A 判断另标历史，不冒充当前节点观点。控制运行/预算/交付状态不成为科学达成。
- 保留 `/nodes/N/science` 原始 JSON 与 `/nodes/N/materials[/index]` 原附件路径。结果页给 exact 链接，不默认载入成果 bytes/主图、不提供 caller path。没有确切声明的主图不猜图；HTML/SVG 继续 attachment。

## 展示与安全

仅新增小 `instance_render.py`（纯 HTML/CSS），`instance_ui.py` 接线。借鉴 main 的独立结果页、分栏卡片、`details` 折叠及数值原值；不搬 SQL read-model/旧 Root/MCP、LLM表单或领域硬编码指标。所有科学文本/标签 HTML escape；数值完整 str/repr，不以四舍五入值替代原值。长文本仅摘要，明确 omitted characters，完整科学原文链接保留。

CSS 常量随 Python 模块打包，以固定 SHA256 CSP `style-src` 授权，无 JS/CDN/额外静态资源目录和安装改动。原 Host/read Cookie/Origin/CSRF/attachment/nosniff 边界继续有效。新页面只渲染 public selection 白名单和科学字段，绝不整份输出 host job/config、私有聊天或凭据。

## 最小检查与限制

新增定向 renderer/UI tests：原值、并列/遗漏、unknown vs empty、A 清推荐/正式review、XSS、wrong Cookie/Host、封存篡改/未封存、live clock与history rebuild哨兵、只读字节不变；一个小 loopback HTTP检查结果路由/CSP/附件保持。只编写，由root串行执行；不装包、不模型、不再尝试Chrome。单节点 JSON仍需解析本节点完整原件，默认列表/首页只给链接；不自动扫描/重验所有历史logs。真实浏览器资格仍未完成。
