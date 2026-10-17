# P4c2 同宿主冷 checkpoint 转移：最小实施设计

状态：root 已授权实施，待 migrate 独立设计审查；未测试。承接[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)及[旧阻断](P4C2_WRITABLE_RESTORE_BOUNDARY_DESIGN_20261017.zh-CN.md)，本节点解决其明确的 owner/高水位缺口，不追认旧包。

## 范围与唯一 owner

显式 operator enrollment：`checkpoint-enroll --root --anchor-directory`。anchor 必须在实例外的明确同宿主目录，唯一 owner.json 保存 active/frozen/restore_pending 代次与事务，lock 串行交接；根内 `instance-owner.json` 仅绑定其 exact 引用/代次。未 enrolled 实例沿用原行为。已 enrolled 缺锚、错宿主、错 root/inode、旧 generation 均不得写；不是恶意同 UID/复制整宿主防护。跨宿主或锚丢失只读，不自动建锚补权。

`instance_owner.lease(root)` 持共享 owner lease 覆盖完整 effect；`require_owner(root)` 仅核验，不能替代 lease。checkpoint/restore 持同一外部锁独占，再按现 archive owner 锁顺序锁全部原写者。central hooks：controller writer、contracts build/seal、runtime runner/watchdog、delivery 的实际 side effect；experiments configure/dispatch/query/reconcile/retire 与 Records accept/publish，由 migrate 接线；authority writer/gate、budget ledger owner 由 thin 接线。`lease_for_configuration(config)` 只从 canonical project/nodes/<step>/work/lineage + 原 job/hash/scope 确认实例；真正 standalone 无实例仍 no-op，不能按 parents 层数猜归属。实际 helper/code 必须被既有实现 freeze 覆盖。

## 冷 checkpoint 与恢复顺序

1. `checkpoint-export --root --output`：取得外部独占及全部原锁；复用 `_quiescent`（所有 native/managed/delivery 已有共同 terminal 或永久 retirement、cleanup 可核），不允许 unknown 外部 call/半准备。budget 唯一 owner 冻结最后 phase=paused 的 exact head/原累计摘要。先冻结原 generation，再生成完整 payload，发布后在锚绑定其 exact digest；原 root 保留且不再可写，不自动删除。
2. 新 wrapper 格式 `checkpoint.json` + `payload/`；payload 复用原只读 archive 布局/全量流式清单，其自身仍 restorable=false。只有本次冷事务写出的 wrapper 被外部锚认可，不能给普通只读包加 wrapper 追认。
3. 用户自行备份移出原 root 后，`checkpoint-restore --package --root` 只准原绝对 root，不覆盖任何现存目标。先全量核包与同宿主 frozen anchor，分块复制完整框架目录到 sibling staging，再无替换发布。发布时 anchor 仍 restore_pending，半成品不能科研推进。
4. 在原 root 核 settings/ledger heads/原件与 exact 外部依赖；不运行模型、插件准备/提交、reconcile 或包内程序。缺原 host key/native session/code/input 等实际依赖明确 unsupported，不复制凭据、不改已接受调用期限。budget 恢复核验完成后，写 immutable transfer receipt、新 root binding/新 generation，激活为 paused；恢复本身不继续科研。

发布前失败保 staging/原root与frozen锚；发布后失败保 restore_pending，仅同事务明确重入继续核验。重复成功恢复幂等；不同包/事务/现存外来根拒绝。旧generation永不因异常自动复活。checkpoint 失败可同事务重试，不能通过普通 run 解冻；不增第二调度/预算状态账。

## 原件与预算接口

checkpoint：version/kind、instance_id、settings_ref、original_root、host/anchor identity、source_generation、transaction、payload_ref，以及 `budget.paused_checkpoint(root)` 原返回。transfer：同 transaction/instance/root/anchor、checkpoint_ref、from/to generation、发布后 root dev/ino。根内保留同字节于 `host-runtime/restore/<transaction>/`；外部锚只绑定摘要与唯一当前代次。

`instance_owner.read_transition(root,checkpoint_ref,transfer_ref)` 仅读 immutable refs/exact 关系，不看最新代次、不授权限；`verify_transition(...)` 在其上核当前外部锚的 exact restoring/active 事务。budget 首次 reanchor 用后者，历史事件用前者，防止二次恢复使第一次历史失效。

thin 独占 `budget.paused_checkpoint` / `reanchor_paused_checkpoint`：同 boot 不新授时，跨 boot 仅原 active/paused checkpoint 追加分段事件，host-started、ceiling、grant/reservation/actual/release 保留；暂停间隔标 unmeasured，不假测零秒。elapsed 旧实例、waiting/advance 或无可信 checkpoint 不授恢复科学秒。未知提交不能通过恢复重放/退款。

## 最小验证与预计规模

先独审 owner→checkpoint→restore→实际 writer hooks；测试仅编写，root 串行执行：未enrolled兼容、共享effect阻止转移、冻结原根/复制根/旧代次拒写、移出原根后完整恢复与重复恢复、篡改/缺依赖/发布后崩溃保持inactive、跨宿主/缺锚/普通只读包拒绝。预算跨boot负控由 thin 维护。不安装、不模型、不继承旧全量套件。

预计 owner/archive 主体约 400–600 行，约 9–11 份生产文件的窄 hooks（预算/experiments 两作者另计），新增一个定向测试模块；如实际需要超出该边界先报 root。P5 历史 SQL 语义读取不混本节点，完整框架恢复不冒称环境/session/跨宿主可迁移。
