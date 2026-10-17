# main 与薄层的选择性整合评估

状态：只读评估，已由独立审查者 migrate_install_checks_1017 核对来源与适配边界；尚未合入，不是实现验收报告。

## 比较范围

- dev 基线 `29a7f69`；本地 main `15d2985bf12fa2ba59877b6b87852d9aa6a1e80c`，共同祖先 `30e7e1b`。
- main 工作树另有 44 个已跟踪文件的未提交修改及 6 个未跟踪文件。它们不在 main 提交里，普通 merge 不会包含这些改进。本次只读，不改动或提交该工作树。
- 已跟踪未提交二进制 diff 的 SHA256：`89145d9d996a582667e2195f2a40efd53abf37a86e5bc9794cb293901acab015`；不含未跟踪文件。
- 本轮拉取 github/main 时 SSH 握手失败。因此这里评价本地可见内容，不声称包含远端最新修改。

## 值得移植的内容

| 内容 | 来源 | 处理方式和验证要求 |
| --- | --- | --- |
| 曲线跟踪实际锚点优先、双向生长、半像素镜像及单点坐标修正 | `plugins/curve_figure_evidence/curve_figure_evidence/figure_line_tracker.py` 的未提交修改 | 独立算法节点，可精确移植。先复核实际锚点与 guide 的区别，再选择真实栅格正反例；不用旧安装矩阵。 |
| 独立科学结果页、最佳可用与科学接受/推荐分开、并列结果及精确值 | 旧 `approval_ui/workbench_render.py`、`static/style.css` | 移植展示方式到薄 `instance_ui`，使用现有 `instance_science`、`selection` 原件；不能直接复制 SQL read-model。 |
| 主图优先、其他材料按精确身份去重、来源不明确时显示缺口 | 旧 `presentation.py`、`read_model.py` 及曲线 `instance_views.py` | 复用呈现原则和路径校验，保留原件读取入口。不得按最近结果猜来源，也不得把图片当脚本或放宽成果下载安全策略。 |

冻结的关键源文件 SHA256：

- 曲线跟踪：`aeb6ca7f701624e15bdb83813b6fe4e9f9d2f81fb3330895f993d70d9f03578f`
- 结果渲染：`5411ae6f3697beafc4cdf520b785f0dd7ace3af8737c63fe89f46b9b5a2508db`
- 样式：`2683808df5fc266f45a25f3ed9eb970eed1d25aea7b8f2546eee9d3a2b4e3571`
- 旧 read-model：`5a1c8727e30a1626ba32731926e62e4e8f66533c9906d7b40907ffa8b7f67fb3`

## 不整包合并的内容

1. `15d2985` 引入的 SQL 科学结果模型和 MCP/Root 回执链。薄层已有封存、候选选择及交付状态，不新增第二套权威状态，也不恢复结果原件的 64 KiB / 32 MiB / 16 候选限制。
2. 未提交的 Root 准入、旧任务准备互斥及调试接管。需要逐项证明薄层仍有同样缺陷，不能为了同步文件重新引入旧调度。
3. 类型化 submission rejection 可以单独复核，但不能把“不明确是否提交”转换成“未提交”或据此退还预算；旧 SQL 消费者逻辑不能直接复用。
4. 旧服务安装说明不能覆盖已切换的默认薄 CLI 部署。

## 顺序

先完成当前 P2/P3/P4 增量的独立审查和定向验收，再核对 P5 入口清单。main 的算法与 UI 分开处理；每项实施前重新验证来源 hash，明确依赖，独立审查后提交。UI 验收必须区分真实浏览器、HTTP 接口与静态渲染，不能相互替代。
