# 实例研究工作台计划 R3 有界补充审查

日期：2026-09-14。结论：**PASS（实施计划补充通过）**。

审查对象：[INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md](../INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md)，精确 SHA256：

```text
f2d917995069e161dccd87897d17659a1095e5ec87a175e35919c0852a175fdf
```

前次通过版本为 [R2](INSTANCE_RESEARCH_WORKBENCH_PLAN_R2_REVIEW_20260914.zh-CN.md)，SHA256 `3bb73975c075a81312dc8e2fb651e08be0715cb1d574713faa1cc930f18dc7ad`，源码基线 `da220ce31c8cc9f9a60542a018b279e2f331f4c0`。本次只审查已绑定会话的管理 URL 补发，不重新审查已通过的全计划或审查尚在实施中的生产代码。

## 差异与必要性

核验了 R3 标题、第 12—15 行补充范围、第 136—137 行管理凭据入口及第 357 行 P1 交付。将这四处差异在内存中还原后，完整文件摘要与已审 R2 完全一致，确认没有其他计划变更。

源码 `interfaces/mcp_root_instance_routes.py:16` 当前只向 unbound 会话返回 `management_url`，已绑定时仅返回实例字段；`:60` 已有绑定到相同 session 的限时 capability 生成方法。用户的新浏览器没有读取凭据或旧 capability 到期后，确实需要可重新到达的管理入口。

**补发已有 URL 是必要且兼容的最小修复。** 生成 capability 本身不改变实例或会话绑定，`approval_ui/app.py` 的管理动作仍须通过现有 capability、CSRF 和明确 POST；科学审批继续采用原审批对象与决定机制。

## 接受的影响边界

- 只在 `instance_current` 已绑定响应中增加 `management_url`，并且仅在 session、UI secret 和 base URL 配置完整时调用原生成方法。
- 不修改共用 `_instance_value`，不连带改变 instance list/close 等响应；无 UI 配置保留原成功响应。
- 不创建实例、绑定、Run 或决定，不改变 Root 工具 inputSchema、Operation 身份、原 capability 格式或科学审批权限，不新增登录流程。
- 实施时验证已绑定会话可获得新入口、旧 capability 过期后可换新、无 UI 配置兼容，以及读取前后控制记录不变。原 R2 的来源、权限、归档和恢复验收要求继续有效。

本次未修改计划或生产代码，未调用科研/Worker 工具，未运行测试或构建；仅执行了文件摘要和精确差异核验。

**最终结论：PASS。无必需修订，可以实施该 Root 入口补充；R2 的计划通过结论保持。** 本结论不替代完成后的实现审查。
