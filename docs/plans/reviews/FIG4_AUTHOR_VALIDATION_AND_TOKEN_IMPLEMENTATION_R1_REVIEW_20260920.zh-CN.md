# Fig4 作者诊断交付与 token 整改：实施 R1 独立增量复审

结论：**PASS（本次工程源码审查范围）**。上一实施审查唯一 P2 已关闭：作者修订工作区的历史附件导航与实际恢复路径使用同一规则，历史/当前报告隔离和只读属性保留，独立 reviewer 路径未退化。原 [REVISE 报告](FIG4_AUTHOR_VALIDATION_AND_TOKEN_IMPLEMENTATION_REVIEW_20260920.zh-CN.md)保持原结论和字节，适用于其历史候选。

本次只复核该 P2 的两文件增量，不重新扩大 WP1–WP4 审查；读取适用既有审查技能与上下文。未运行测试、模型、科研 MCP、solver 或部署，唯一写入为本报告。

## 精确版本

证据目录：`docs/plans/evidence/author-token-r4-20260920/`。

- `revision1.patch` SHA256：`bd9bc4494fa1a9afd5d7312c014ca3c552f3bbc222329dcabbb75ad0b1934e15`。
- `revision1-files.json` SHA256：`24de9de357c30a5294e1f36fe280aac455cee1ebda962545a9bfa8a624c89e0f`。
- 累计 `revision1-incremental.patch` SHA256：`d42a9a74a25186637a2874da70ba5b49247ee3c28bf25ec59e4586d0d802fc40`。
- 累计 `revision1-incremental-files.json` SHA256：`d629a295d36075151b0be1b0f05ff3c608bded91f256dd0565e2e9ecc63b339d`。

独立核验上述 hash；两文件 reviewed-before hash 与上一冻结清单一致，当前源码/测试字节与 revision1-after hash 一致。改动只有 `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` 和 `tests/operations/test_tcad_development_delivery.py`。

## P2 关闭依据

`operation_workspace.py:274–278` 提取既有改名规则为 `_restored_report_path`：作者的非 history 报告仍进入 `reports/history/{内容hash}_{basename}`；已有 history 路径及 reviewer 路径保持原样。恢复写入 `:297–298` 和 manifest 导航 `:543–546` 现在共用相同路径、原编码内容和 author 标志，不再分别计算不同目的地。

附件恢复仍使用 `item.raw_bytes()`，没有变更 UTF-8/base64 内容；报告路径的 `editable` 仍为 false，reviewer 原有整树只读处理不变。作者历史报告没有回填 `reports/preflight.json` 或 `reports/initialization.json`，当前 Run 生成模式报告不会重定向历史导航。reviewer 的 `author=False` 返回原路径，原跨 Run 读取语义保留。

新增定向测试通过实际已封存项目、独立 reviewer 的 revise 结果和新 author revision Run，断言返回入口均存在、原字节一致、无写权限，并在建立当前 initialization 报告后再次核对历史原件。另回归原独立 reviewer 跨 Run 封存与读取测试，覆盖上一报告指出的未测分支，没有新增机制。

## 已有验证与继续保留的限制

读取 `revision1-navigation-final.json` 和修订状态报告：两个指定用例通过，exit 0；守卫总时长 3.2196 秒，观测峰值 123132 KiB（120.25 MiB），`exceeded=false`。这是实施者已有验证证据，本 reviewer 未重跑测试。前两次新增测试设置错误及失败记录继续保留。

本 PASS 关闭上一报告唯一源码问题，不把此前不相关失败写成通过，不补齐完整安装工作流或原生测量证据。原生首个测量超限后停止的事实不变；**作者行为/token 收益未证实，真实 solver、Fig4 连续边界及 J 未验证**。不授予部署、提限重试或科研执行授权。
