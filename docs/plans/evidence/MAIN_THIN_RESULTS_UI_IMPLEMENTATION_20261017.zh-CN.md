# main 结果呈现选择性迁移：薄 UI 实施账

状态：实现冻结，待独立静态审查和 root 串行定向验证；作者未运行测试/HTTP/浏览器/import/安装/模型或 Git。依据[短设计](MAIN_THIN_RESULTS_UI_DESIGN_20261017.zh-CN.md)与[整合评估](MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md)。main 为只读来源，未修改；workbench renderer/CSS 源 SHA256 已按设计页核对，与评估一致。

## 精确文件与接口

生产：`research_loop/instance_ui.py` 新增 `/results?after=N` 分页入口、`/results/<step>` 精确结果页，以及现首页/封存节点的结果链接；新 `instance_render.py` 提供无状态 escaped HTML/CSS。`execution_authority.py` 仅既有 implementation paths tuple 追加 `instance_render.py`，使实际 UI helper 被原冻结代码合同覆盖，不新增资源注册系统。没有静态目录/JS/CDN/打包元数据变更。

测试：新 `tests/research_loop/test_instance_results.py` 两个 source；既有 `test_instance_ui.py` 仅原 loopback download case 增加结果页/CSP 检查。文档：设计、本实施账。总计3生产+2测试+2证据，共7作者文件；独审报告另归 reviewer。

新结果入口先沿原 Host/read Cookie 验证。列表仅枚举 exact 编号及 seal 记录存在，一页20条并保 continuation；打开时才验证科学原件，不自动选最新结果，也不默认解析全部科学历史。精确结果页复用 `instance_science._sealed/Original`，同 fd 核该 raw scientific JSON，job 同原 seal job SHA 验证；不调用 status、预算活钟、history rebuild、selection 重投影或缓存写入。

最佳观测卡消费原 `job.history.view.candidates`，明确冻结于该节点输入边界，后续数据不含；原 metric 不四舍五入，ties、遗漏、unknown/failed 和 coverage 保留。当前 ordinary A raw recommendation 独立展示；null 不被早期 A 顶替，audit/formal review 不当普通推荐。科学接受/target optimum 不从 proxy、执行成功或系统状态推断。缺排名/缺字段展示缺口。折叠范围仅白名单公共投影，绝不渲染完整 host job/config、凭据或私有聊天。

原 `/nodes/N/science` 科学 JSON、`materials` 清单及 exact index 附件下载保持原 owner；HTML/SVG 不内嵌，仍 application/octet-stream + attachment。科学长文本只显示有明确省略数的摘要，完整原文链接保留。CSS 为 Python 常量，CSP 固定 SHA256 仅允许该样式；没有 unsafe-inline、script 或新外部资源许可。

## 最小验收目标（未运行）

source：

- `tests/research_loop/test_instance_results.py::test_result_cards_preserve_exact_ties_and_do_not_replace_empty_a_recommendation`：真实 selection 纯投影输入到 renderer，原值/并列/遗漏/unknown、空 A 清推荐、formal gap、XSS、私有 job 字段不泄露、CSS hash。
- `tests/research_loop/test_instance_results.py::test_result_routes_are_read_only_exact_and_independent_of_live_clock`：真实 prepare/seal/reader/readcookie，分页 continuation、原 JSON/附件不变、未封存/坏 job/raw拒绝、Host/cookie/路径负控、budget/status/history/selection 重算哨兵、原件字节不变。

process：`tests/research_loop/test_instance_ui.py::test_loopback_science_download_uses_existing_browser_scope_and_safe_headers`。复用原小 loopback HTTP case，追加结果响应、固定 CSP hash 及无 active SVG/script；附件仍 exact bytes/attachment/nosniff。无模型、外部服务、安装或 Chrome。

三生产两测试已用 stdlib AST/尾空白静态检查。浏览器前次 RSS 止损的限制继续保留，本节点不扩内存、不重复尝试，不用 HTTP/rendering PASS 冒充真实浏览器资格。

## 资源与剩余限制

精确结果页仍完整解析该节点 raw JSON 和 frozen job 后再摘录，内存随这两份 JSON 增长；同 fd 身份核验有流式 hash IO。分页首页不全量解析节点内容，不重核全部大日志。折叠为原生 HTML details，非延迟服务器读取；没有声称 bounded JSON parse、完整候选原件浏览或跨 producer 去重。

本轮呈现已有冻结摘要，不新增比较合同、阈值/accepted 模型、排序决策或新科学状态。未明确绑定主图时不猜图、不自动读取图件 bytes；原附件入口保留。历史摘要的省略和输入时间范围不是当前全局最优证明；科学 JSON 原值与来源限制由原 owner 保留。本节点不能授予执行/交付/预算资格。

## Root 唯一动态验收

作者冻结、独立静态 PASS 后，使用既定768MiB采样止损配置串行执行：

- `--lane source --output .trial/main_ui_source_20261017`：本记录的两个精确 result tests，2 passed in 0.64s；监督0.861s，RSS66,510,848B。
- `--lane process --output .trial/main_ui_http_20261017`：原精确 loopback HTTP test，1 passed in 1.02s；监督1.239s，RSS67,137,536B。

均由 `/home/da/miniconda3/bin/python scripts/run_tests.py --config .trial/p_migration_validation_20261017/resources.json` 执行，returncode=0、cleanup_complete=true、无内存止损。`git diff --check` 通过。
动态前作者与独审发现列表缺少execution import，已补正并冻结；上述检查为补正后首次运行。
没有运行安装/模型/浏览器；HTTP与HTML正确性不升级为真实浏览器视觉或交互资格。
