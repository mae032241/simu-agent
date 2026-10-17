# P3d2-b 迟批原 call 恢复独立静态审查

结论：**静态 PASS，可按本节点精确文件组提交。** 这是代码边界结论，不是动态、远端或生产资格验收。基线为 `799036e`，只审 P3d2-b 工作树变化及其必要消费链；不重审已提交 P3d1/P3d2-a/P4b/P4c1，不批准可写归档恢复。

## 可达链与判定

| 边界 | 核对事实及证据 |
| --- | --- |
| 真实入口及唯一 owner | `cli.py:75` 的 `execution-resume` 调 `controller.py:1096`，持原 controller writer 后进入 `execution_resume.py:353`；不是 helper 独立成功，也不启动新 W/native、队列或任务库。有限 operation receipt 与原调用身份绑定。 |
| 原正向证明 | `execution_resume.py:14`、`:106` 在原 seal 留 pending-set，核原 allocation/request/call namespace 与各 attempt cleanup 原件。缺失、半写或旧 seal 不补猜 fresh 资格；可选采集失败只留 incomplete，原科学封存主校验保留。当前文件不存在、lookup None 或 PID 不存在均不能证明未派发。 |
| 原决定复用与续期 | `execution_resume.py:280` 沿精确 successor 链复用有效决定；过期或 policy/grant 改变须显式有限 request validity，旧决定/原件不改，重复读取不刷新 TTL。等待人时只有 request/operation 原件，没有不可重放 intent。UI 仅链接共同验证的 successor。 |
| 确定拒绝先于 intent | `execution_authority.py:696` 的实际顺序是累计 reserve/同 ID rebind → `remaining()` → `recovery.begin` → prepare-intent → 原 wrapper prepare → 原 Records.accept → accepted 投影 → 一次 fresh submit。缺决定、拒绝政策、余额不足、机会不符均在 intent 前。reserve 成功不证明派发；reserve→intent 中断保留占用，正向无准备证明允许同 reservation 续接。 |
| 不确定状态不重发 | `execution_resume.py:353` 的既有 intent/possibly-prepared 分支只加载实际 accepted 后 lookup/query；无 accepted 继续 unknown。`sealed_preparation_unknown` 不调用 fresh prepare/submit，只消费同 allocation/call 的可信 accepted/status/统一终态或永久 fence。共同 validator 再核 native/interface/target/authority/script/prepared，不能由缺文件制造 not_submitted。 |
| 同预算、分离期限 | `budget.py:132`、`:237` 保留原 ledger owner，resource_rebind 不另发余额、不退款，不改变原 token/time 事件语义。operation 的绝对 deadline 映射只用当前剩余，锁等待、实际新 copy/hash 和 RPC 重试不重授整段 seconds。solver wall 与操作窗口分开；collection 用明确当前有限维护窗口，不扩大 solver grant。 |
| 原 seal 与一次计数 | `execution_recovery.py:61`、`:153` 是原 recovery 目录内 seq/previous 原件链；发布前共同验证当前事件。`search.py:227` 逐科学 source 使用该 job 冻结 prefix，最后叠 caller prefix；`lineage.py:212` 只改派生投影。intent 不伪造 accepted，迟到 accepted 计一次，terminal 不退科学机会；旧 W/A seal/raw/prefix 不回写。 |

原件可信条件仍是既有软宿主边界。来源/review/执行权限继续由原 owner 核验，operator note 和 operation receipt 不代替人类决定或 solver 额度。新辅助模块通过 `execution_authority.py:36` 的实际 owner 自动纳入 code proof。

本次 `execution-resume` 要求当前原共享科学授权仍有剩余；它不是零余额管理员维护入口。原 query/cancel/retire 维护路径仍保留，不因新派发的 live W/决定期限门限被自动撤销。

## 最后两项局部收口

1. `execution_resume.py:426` → `history.managed_calls(context=...)` → `history.py:87` 的首次 host-history hash/copy 传同 operation context；`_managed_proof`、当前 `validate_managed`/observation verifier 延续该参数，默认 None 保持旧调用。受限 copy 用本次独有 partial，超时不发布完整 snapshot，也不使后续明确操作永远撞同一临时文件；原 None 路径保持旧语义。
2. `execution_recovery.py:153` 对已发布 prefix 只核不可变 event/ref 链；prospective 当前事件仍走共同完整 validator，带 context 核当前 source job/raw/result/seal、pending、accepted、实际 prepared 与 query 身份，然后才发布。没有为节省 IO 取消新事件原件验证。

旧科学 history 的完整只读验证默认仍在。既有 `experiments.retirement` 对 prepared/receipt 的只读完整 hash/JSON 核验没有新增 copy 或远端副作用，按本节点范围不再扩展整树 deadline 改造。

## 最小负控能证伪什么

仅静态读新增五项，全部**未运行**，位于 `tests/research_loop/test_native_execution_inputs.py`：

- `test_late_decision_public_resume_preserves_call_pending_prefix_and_cancelled`：若真实公共 CLI/gate/factory/Records 链换 call、重复 submit、漏 pending/cancelled、重复计数或改旧 prefix，会失败。
- `test_expired_request_requires_explicit_successor_without_retry_ttl_refresh`：若过期决定仍可执行、自动续 TTL 或换 successor，会失败。
- `test_missing_positive_cleanup_and_contradictory_prepare_never_dispatch`：若缺/坏原证明、活 owner 或矛盾 prepare 仍准入，会失败。
- `test_interrupted_resume_intent_never_regains_fresh_dispatch`：若 prepare 响应未知后重获 fresh 并重发，会失败。
- `test_reservation_gap_renews_authority_without_second_reservation_or_refund`：注入 reserve 后 begin 故障；若同 call 续批重复扣额、退款或提前留未知 intent，会失败。

这些用例复用既有小 compile/review fixture；backend、native 身份/cleanup 是合成可信边界。真实 controller/CLI/冻结原件/ledger 消费路径仍在，但这不证明模型独立性、实际远端协议、solver 或真实掉电语义。没有新增安装或环境矩阵。

## 检查与未覆盖范围

独立执行仅源码/差异阅读及 **19 个相关 Python 文件 stdlib AST 解析**；最后三 helper 增量再次 AST 解析及限定 diff 空白检查通过，无项目 import。未运行 pytest/collect、业务 CLI、进程/线程测试、UI、模型、SSH/solver、构建、安装或环境创建。作者提供的空白/diff 静态证据另见[实施账](P3D2B_LATE_DECISION_RECOVERY_IMPLEMENTATION_20261017.zh-CN.md)。

本次未动态覆盖真实跨 boot、并发/掉电窗口、live owner RPC、`sealed_preparation_unknown` 后来补齐终态、真实大日志及超时行为。完整 JSON、显式原件的重复 hash、单次阻塞文件 IO/系统调用仍有成本，context 不构成全链硬实时保证。clock/新 call 使用控制元数据，ledger fold 不递归审实验大原件；科学完整验证仍可能读取大原件。没有资源实测，也不能据此确定或排除此前 OOM 的根因。

建议顺序：精确提交本节点及其设计补充/实施账/独审；公开进度只标静态闭环已接，真实平台与远端验收资格保持未授。P4c2 可写恢复仍待独立设计与原 owner 独占证明。
