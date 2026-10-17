# P4c2 同宿主冷 checkpoint：实施冻结

状态：实施冻结，交 migrate 独立审查；本节点动态目标尚未运行。依据[短设计](P4C2_COLD_CHECKPOINT_DESIGN_20261017.zh-CN.md)，仅显式 operator enrollment、全 owner 静止、无未知外部调用的同宿主冷转移。不是普通只读包升级、任意路径恢复、跨宿主接管或原生环境复制。

## 精确作者范围与共用接口

生产九文件（`src/scidiscovery/research_loop/`）：

- 新 `instance_owner.py`：外部单一 anchor/generation、共享 effect lease、独占转移、纯历史 receipt 读取与当前转移核验；真正 standalone/未 enrolled 保持原行为。canonical instance execution namespace 必须核原 job/scope/hash。
- `instance_archive.py`：enroll/export/restore，沿原全量流式清单/分块复制/无覆盖目录发布；明确纳入 `instance-owner.json` 和 `host-runtime/restore`，供二次 checkpoint 保留历史桥。
- `protocol.py`：`require_current` 加当前 owner 核验，不把一次检查当成完整 lease。
- `controller.py`：原 `_writer` 内持共享 owner lease；另按 thin 的 P2 合同接 maintenance 分支，不走科学 inactive/renew/dispatch。
- `contracts.py`：build/seal 整段 lease。
- `runtime.py`：spawn/runner/watchdog 整段 lease，非 enrolled 不新增执行规则。
- `delivery.py`：catalogue/freeze/leaf/invoke 实际 effect 整段 lease。
- `instance_control.py`：request_pause 从检查到写入均持同 lease；continue 沿原 controller writer。
- `cli.py`：三个 checkpoint 入口、P2 maintenance query/collect/cancel 参数接线。维护与 replacement request 互斥；恢复不自动继续。

新 `tests/research_loop/test_cold_checkpoint.py`、本实施账和设计，共十二份作者文件。migrate 持有 `experiments.py` 的完整 effects/Records hooks 与 helper freeze；thin 持有 `execution_authority.py`/`budget.py` 的原 writer lease、clock 分段及跨 boot 原调用维护。两组依赖不由本作者重复实现/计入上述文件数，需与真实公共链共同独审。root 持有 CLI 指南和浏览器测试。

`settings-identity.json` 的所有源码消费者已静态核对：contracts.settings 仅用 sha256 验 settings 本体，archive 读取原件而不拒额外控制 metadata。enrollment 在其内增加 `cold_owner`，不改 settings 字节/hash。marker 先落、binding 后落；中断后普通 writer fail closed，只有显式 enroll 重试能从同一原 anchor/root inode/host/active 代次补齐 binding，不建第二 anchor。旧无 marker/binding 的实例不因此升级或冻结。

## 发布、重入与完整性

冷 export 在外部独占下按原顺序锁 controller、native、managed、authority、ledger，复用共同 terminal/retirement/cleanup 校验；原 budget owner 要求原 active clock 最后 paused。先冻结原 generation、复制完整框架原件，再把 wrapper digest 持久绑定外锚后发布。原根不删除。失败仍 frozen，同目标事务可重试。

restore 只允许原绝对 root 缺失。外锚先 restore_pending；stage inode 在 rename 前持久记录，避免发布后崩溃丢失合法根身份。发布后仍禁止普通 effect；完整复核原 manifest 的真实文件 hash/size/mode、目录与额外控制原件，只允许本事务 receipts/binding/pause/由预算 owner 验证的桥。必要当前实现/launcher 缺失则 inactive，不覆盖坏原件来让重试通过。全部通过后新 generation active、默认 paused。原 generation/备份移动根不可写。

checkpoint 与 payload metadata 从同一稳定 fd 解析并取得身份；实际 copy/activation 迭代再次同 fd 流式 hash manifest 到尾，核对原 metadata proof，避免“inspect 一份、重开另一份”。只读历史 `read_transition` 不要求当前代次，首次 `verify_transition` 必须当前 host 线程持独占，且外锚当前代次/事务/inode 完全一致。

已完成事务重复 restore 仅返回当前实际 paused 状态，不写 binding/receipt、不调用预算桥、不回滚后续推进。restore_pending 重试必须先重核原完整 payload；篡改不修复、不激活。

## 最小目标（均未运行）

source 四项，均位于 `test_cold_checkpoint.py`：

1. `test_public_cold_checkpoint_restores_complete_state_twice`：公共 CLI 两次完整恢复、原 seal/settings/host-started/ledger 前缀、科学成果、旧 generation 拒写、receipt 历史复核。第一轮同 boot 账本完全不变，第二轮只改 clock_stamp 的 boot 观察，真实 owner→budget 桥唯一追加且消费不增、elapsed 未测；随后继续控制并重复旧 restore，不能再暂停/改账。
2. `test_cold_transfer_blocks_live_effect_and_rejects_plain_archive`：旧未 enrolled 行为、普通包拒绝、marker-before-binding 中断 fail closed，同一 anchor 重试不增加副本，嵌套 transfer 拒绝。
3. `test_restore_dependency_failure_stays_inactive_then_same_transaction_recovers`：发布后依赖失败保持 fenced；篡改 job 拒绝；原件恢复后同事务继续。
4. `test_cold_restore_wrong_host_missing_anchor_and_tamper_never_advance`：异宿主、失锚、坏 blob 不创建可推进根。

process 一项：`test_external_owner_lease_fences_cold_checkpoint`，显式 process_e2e。仅一个独立 Python 子进程持真实共享 flock，父 export 拒绝；释放后成功。ready/退出有 timeout，finally 回收；无安装/模型/远端。

静态：九生产与新测试使用 stdlib AST/尾随空白检查，未 import 项目或执行目标。root 的浏览器测试仅核已有 Chrome 的 Cookie/view/manage 和真实 pause，不宣称科学原文导航/执行审批；已只读复核 cleanup nested finally，无自动安装，动态资源由 root 唯一监督。

## 保留的限制

这恢复完整框架状态而非全部宿主环境。历史 sessions/凭据不复制：全 sealed 后缺旧 session 不阻普通科学字节读取；需要同线程续接/执行签名时仍走原精确依赖门禁。外部 code/配置必须保留，原 host key 可由 operator 沿原入口重新绑定，不能换 key 伪签旧决定。未知提交不因恢复重发/退款。

可信同 UID 边界不变，不防删除两份控制 marker、复制整个宿主锚或绕代码直接写盘。跨宿主/锚丢失只读；elapsed 旧实例不能借桥取得新科学秒。源目录不自动搬移/删除，失败 staging 仅清本次创建项；极端磁盘/权限/锚原件破坏明确拒绝，不重建未知身份。

全 manifest 身份复核有重复流式 IO，目录模式清单和原件路径集合使用随记录数增长的内存；不加载大成果 bytes、不新机械容量 cap/持久索引，不声称硬实时 IO/强内存隔离或真实掉电资格。所有动态与资源数据待 root 串行记录，不以静态通过替代验收。

## root 串行验收追加

当前状态：已获[独立静态审查 PASS](P4C2_COLD_CHECKPOINT_IMPLEMENTATION_REVIEW_20261017.zh-CN.md)，root 执行本节点四项 source 与真实进程 lease，**5 个 unique P4 目标全部通过**。前文“未运行”为作者冻结截面；本作者仅只读核下列日志/资源，没有执行或重测。

证据均位于 `.trial/p_finish_20261017/<批次>/batch-001/{pytest.log,resource.json}`：

| 批次 | 结果及范围 | pytest / 监督耗时 | 观察进程树 RSS 高水位 |
| --- | --- | --- | --- |
| `cold_source` | 4 passed，1 process deselected | 1.67 / 1.926 秒 | 60,915,712 B |
| `lease_and_local` | 2 passed：P4 外部 lease + 原 Local process | 2.10 / 2.274 秒 | 70,680,576 B（合批，不归为单独 lease 数值） |

两批 returncode=0、cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]；address_space_limit_enabled=false。覆盖两次完整恢复、真实 owner→跨 boot 预算桥、原账本前缀及消费保留、重试/失败 fenced、旧代次拒写和独立进程真实 flock 排斥。不是跨宿主、真实掉电、模型/远端或全量回归资格。

### 真实浏览器未完成，停止重跑

root 的单个 Chrome 用例仍**未完成、不能记 PASS**：

- `browser` 首次 1 failed，pytest 0.95 秒；监督 1.11 秒、峰值 314,327,040 B，Chrome 早退 EOF，临时 stderr 被监督清理。
- `browser_diagnostic` 加失败时末 4000 B 诊断后 1 failed，pytest 0.93 秒；监督 1.105 秒、峰值 318,308,352 B。日志明确 SingletonSocket 路径过长，并有只读 home config 下 Crashpad 写失败。
- `browser_short_tmp` 仅改 fixture 的短私有 `/tmp`、TMPDIR/XDG_CONFIG_HOME/profile，保留 sandbox 后可启动，但观察 RSS 达 **1,121,267,712 B**，超过 root 既定 768 MiB 阈值；监督 0.838 秒以 `observed_tree_rss_limit` 停止，returncode=-15、cleanup_complete=true。该条 `memory_stop_triggers=[]` 不代表没有止损，实际 stop_reason 为 RSS limit；address-space limit 仍未开启。

以上三次均已清理；未扩大资源、不安装、不继续重跑。测试现以 `SCID_RUN_BROWSER_CHECK=1` 显式 opt-in，默认 process suite 在创建实例/UI/浏览器前 skip，避免意外触发浏览器负载。该两行 gate 已独立静态核对；失败诊断保持有界，生产逻辑未改。真实浏览器 Cookie/表单流程与产品浏览器资格仍未完成，既有 loopback HTTP 通过不能替代它。
