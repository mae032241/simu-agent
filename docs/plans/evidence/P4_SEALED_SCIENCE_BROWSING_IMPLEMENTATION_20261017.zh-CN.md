# P4 已封存科学原文与成果浏览：实施账

状态：**实现冻结，待独立审查和 root 串行定向测试。** 基于 root 提供的 `dev@73f57c6` 及[既有 P4b 方案](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md)。此次只补既有实例 UI 的科学读取入口，不新增实例体系、索引、任务、下载任意路径接口或安全部署。未修改 root 持有的计划/README。

## 原缺口和实际入口

原 `InstanceUI._instance_page` 已有节点链接，但 `/nodes/N` 仍只显示角色、状态等控制元数据。现在已封存节点的紧凑页面只增两个按需链接，不嵌入科学 JSON、完整原文或成果字节：

- `GET /nodes/N/science`：同一原 native attempt 已封存的 `science-output.json`，按原字节/JSON流式返回。
- `GET /nodes/N/materials?after=...`：同一 seal 的成果清单，每页20项、明确总数/续页；不截掉后续项，不建立持久索引。
- `GET /nodes/N/materials/I`：由 exact step/一基序号解析同 seal 成员。URL不接收路径或源文件名，合法科学文件名（含字面 percent 编码字符）不继承旧 URL handle 的额外限制。

只读/管理凭据仍来自原 `BrowserAccessService`，在任何新路由前校验实例、boot、read scope 和精确 Host；不扩写权限。现有 CLI `serve-ui` 即可使用，没有新增 CLI。HTML/SVG 等所有成果均 `application/octet-stream`+attachment；HTTP继续 `nosniff`、`no-store`、`no-referrer` 和原 CSP，科学原文为 JSON，不解释作者 HTML。

## 唯一原件身份和只读边界

新 `instance_science` 复用现有 `contracts.settings` 身份核验、`execution.reference`/显式 attempt 的 `execution.record`、`archive_io.check_path` 以及原 SHA/size 约定。每次按需核 seal→job/raw/result 的既有身份，不执行科学 admission、原生工作、插件 query/reconcile 或预算活钟。

没有直接复用 `history._source`：它额外完整验证 managed 观察；它所调用的 `execution.raw→record` 在成功 continuation 分支还可能进入额外终态、预算消费和恢复链校验。当前这些校验本身只读，不声称存在可写投影风险。新读取显式选择已封存 attempt，避免科学字节浏览依赖更大的终态/恢复校验范围；没有为此修改 `history` 或削弱其原科学校验。

成果只允许：

1. `seal.materials` 的唯一逻辑成员，位于本节点 `artifacts` 或已有嵌套科学 `experiments` 的确切 owner 路径。
2. managed 成果通过同 seal 的精确 observation、该 observation 绑定的 raw SHA、同 scope/job、output name/source/SHA/size 及 `retention=archived` 核其现有 `host-history/objects/SHA`。只读既有 snapshot，不创建它；不因此遍历或下载 originals、凭据、native homes/聊天、scratch、job/settings 或任意宿主路径。原 mutable 输出已移除但确切 retained output 仍存在时可读该原件；retained 原件缺失则明确不可用。

`Original` 先拒链接/特殊文件，再以 `O_NOFOLLOW` 打开并验证 fstat identity/size/分块 SHA；HTTP持有同一描述符，核验后 rewind，发送时不按路径重开。发送中核身份/字节，成功或异常均关闭 fd。路径替换不能令旧下载读到新文件。未封存、篡改、缺原件或不适用的身份明确拒绝；读取不创建科学/控制事实，也不使 unknown 执行重放。

## 精确文件

| 文件 | 修改 |
| --- | --- |
| `src/scidiscovery/research_loop/instance_science.py` | 小型 sealed reader、分页成员解析与同 fd 原件校验/传输。 |
| `src/scidiscovery/research_loop/instance_ui.py` | 紧凑节点链接、三个 GET 路由、原 HTTP handler 同 fd 响应/关闭；原控制/审批 owner不变。 |
| `tests/research_loop/test_instance_science.py` | 5个 source 用例：只读/无预算钟/完整分页及合法名字；未封存/篡改/缺失/链接；换路径竞态不读新私件；seal row不能授宿主路径；managed精确 retained output。 |
| `tests/research_loop/test_instance_ui.py` | 原用例保留；加一项direct GET/read-scope/attachment负控和一项真实loopback HTTP定义。 |

## 资源、fixture 与未验收

- source fixture复用 `test_execution_authority.prepare(enabled=False)` 和 `test_history_handoff.finish`：仅准备小型临时实例，写 synthetic native intent/outcome/usage 并经原 seal 代码封存；无launcher执行、solver、安装或模型。managed reader fixture仅构造封存读取边界，不冒称 backend/terminal 资格。
- 唯一新增 `process_e2e` 用例复用真实 `instance_ui.serve`，仅一个 loopback server/thread、短 HTTPConnection，finally shutdown/join；不新增环境、子进程或浏览器安装。它验证 read-token交换、未授权403、SVG附件/响应头及完整字节。这里只定义，未运行。
- 默认状态/节点页不新增科学原件 hash 或完整解析。按需响应按页/1MiB块有界；完整 seal/job/observer 元数据仍使用现有 JSON全量解析，原文/成果做完整流式 hash/传输。分页不能冒称总读取量或元数据内存恒定；没有新增容量 cap、缓存或索引。
- 同 fd 防路径重开竞态，检测常见文件改变；这不是文件系统快照、Python IO硬抢占或抵抗任意同UID恶意写者的隔离保证。传输已开始后的检测失败会中断该响应，不能撤回已发送字节。被作者主动写入已封存科学内容的敏感字节无法由文件归属规则语义识别。
- 展示 sealed byte identity，不重新授科学资格/公开来源资格/执行权限；完整科研有效性、真实浏览器交互及长期并发仍未验收。读取路径不依赖当前预算活钟，可在原目录重启后只读，不等于从归档复制出可推进 owner。

静态仅标准库 AST/逐行空白检查4个 Python 文件；未运行测试、HTTP、项目 import、安装、模型或 Git 命令。待独审后建议 root 最小source目标为 `test_instance_science.py`（5项）及 `test_instance_ui.py::test_read_cookie_opens_only_sealed_science_and_attachment_members`；原 UI状态/权限项可按变动风险一起检查。loopback项 `test_loopback_science_download_uses_existing_browser_scope_and_safe_headers` 单独列process，资源审后由 root 唯一串行执行。

## 2026-10-17：root 串行验收追加

当前状态更新：已获[独立静态审查 PASS](P4_SEALED_SCIENCE_BROWSING_REVIEW_20261017.zh-CN.md)；root 完成最小 source 与真实 loopback HTTP 验证，**7个 unique 增量用例最终通过，待 root 独立提交**。上文“未运行”记录作者冻结阶段，不替代此次追加结果。作者仅只读日志、补本文档，没有运行测试或改动代码。

| 批次 | 实际结果 | pytest / 监管耗时 | 采样进程树 RSS 峰值 | 原始证据 |
| --- | --- | --- | --- | --- |
| `p4-source` | 首轮5通过、1失败 | 0.91s / 1.096s | 65,744,896 bytes（62.70 MiB） | [pytest.log](../../../.trial/functional_reaudit_20261017/p4-source/batch-001/pytest.log)、[resource.json](../../../.trial/functional_reaudit_20261017/p4-source/batch-001/resource.json) |
| `p4-retest` | 仅修复项1通过 | 0.50s / 0.689s | 65,101,824 bytes（62.09 MiB） | [pytest.log](../../../.trial/functional_reaudit_20261017/p4-retest/batch-001/pytest.log)、[resource.json](../../../.trial/functional_reaudit_20261017/p4-retest/batch-001/resource.json) |
| `p4-http` | loopback HTTP 1通过 | 0.97s / 1.167s | 65,925,120 bytes（62.87 MiB） | [pytest.log](../../../.trial/functional_reaudit_20261017/p4-http/batch-001/pytest.log)、[resource.json](../../../.trial/functional_reaudit_20261017/p4-http/batch-001/resource.json) |

首次失败是测试预期的拒绝层级错误：symlink 被 `artifact` 的源 canonical owner 检查更早拒绝，实际为 `ValueError('Scientific deliverable source escaped its exact output owner')`；测试原先等待更深的 archive 路径检查 `RuntimeError('symbolic...')`。生产安全拒绝已成立，未改生产、未放宽规则或 fixture；只将该断言改为准确的 ValueError 类型及拒绝原因，独审定点 PASS 后 root 单项复测通过。

去重计数为 source 的6个目标（首轮5通过加该单项复测通过）与1个独立 HTTP目标，共 **7 unique**；复测不是第8个独立保护。三个监管记录均 `cleanup_complete=true`、`memory_stop_triggers=[]`、`received_signals=[]`，系统可用内存末值均高于13.60 GiB。记录的 `address_space_limit_enabled=false`，采样结果不等于 OS 硬隔离或最坏内存保证。

此次验证了小型 sealed reader、只读 Cookie/API边界、完整附件字节和真实 loopback HTTP响应头。**没有运行浏览器，也不等于真实浏览器验证**；没有安装、模型、solver、大容量/长期并发或归档可写恢复验收。前述完整 JSON元数据读取、单次IO和同UID权限限制继续保留；这7项不是全套回归或完整产品资格声明。日志保存在仓内 `.trial`，不把私有原始日志纳入本节点提交。
