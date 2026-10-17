# main 选择性整合记录

起点：dev `326b573`。本轮只移植经过审查的功能，不整包恢复旧 SQL/Root/MCP 调度。

## 来源核实

2026-10-17 执行有界 `git fetch github main` 成功。远端 `github/main` 为
`e27352a7f0efec6c8100a3d0036ec0e4d11a6577`，是 dev 的祖先，
`git rev-list --count HEAD..github/main` 为 0。因此远端没有待合提交。
此前评估中的 fetch 失败为当时事实，本次已重新核实。

实际待整合来源为本地 `123/main`：提交 `15d2985` 及其未提交改动。
源工作树保持只读；采用文件的指纹分别记录在各节点证据中。
不以本次选择性移植声称整个本地 main 已合并。

## 节点

1. 曲线追踪：实际锚点优先、断段保留、双向半像素及歧义处理。
   详见 [移植记录](MAIN_CURVE_ANCHOR_MIGRATION_20261017.zh-CN.md)。
2. 薄 UI：用现有封存原件和节点输入快照展示科学结果；保留原文与附件入口。
   不把代理最高、A 推荐、实际交付或机械封存混为一谈。

## 验收边界

只执行独立审查后的最小源测试和 HTTP 行为测试，单进程串行、受内存监督；
不运行安装矩阵或全量回归。浏览器资格仍未完成：此前 Chrome 超过既定 RSS 止损，
本轮不提升上限或重跑浏览器。源测试/HTTP 通过不能替代浏览器或真实科学运行。

状态：本轮两个功能节点已实施、独审、定向验收并提交。

- `6fa5f9b`：曲线修复，6项通过，RSS峰值68,874,240B。
- `6eaf319`：薄结果UI，2项source + 1项HTTP通过，峰值分别66,510,848B与67,137,536B。
- 共9项不同目标通过，三批串行，监督总时长3.154秒；均退出0、清理完成、无内存止损。
- 最终再次核对main HEAD仍15d2985，tracked WIP diff hash仍为
  `89145d9d996a582667e2195f2a40efd53abf37a86e5bc9794cb293901acab015`。
- 未推送；没有制造整包main merge。详情见[UI实施](MAIN_THIN_RESULTS_UI_IMPLEMENTATION_20261017.zh-CN.md)、
  [UI独审](MAIN_THIN_RESULTS_UI_REVIEW_20261017.zh-CN.md)与[完整handoff](../DEV_HANDOFF_20261017.zh-CN.md)。
