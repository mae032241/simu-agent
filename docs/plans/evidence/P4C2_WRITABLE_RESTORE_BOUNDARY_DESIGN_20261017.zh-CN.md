# P4c2 可写归档恢复：阻断与现有能力边界

结论：**BLOCKED，未批准实现、未实施。** 静态基线 `dev@71394a3`。本轮只有本文；不增加 restore/material-repair 子命令、owner/key/ledger、目标实例、UI 或生产代码。依据 [P4/P5 notes](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md)与已完成的 [P4c1 只读归档](P4C1_READONLY_ARCHIVE_REVIEW_20261017.zh-CN.md)。独审仅核这一收窄边界，不是可写恢复实施 PASS。

## 1. 为什么现在不能从包生成 live 根

- `protocol.require_current` 只核 settings 身份与 CURRENT；`controller._writer` 只锁所给 root 的 `host-run.lock`。复制 settings/goal_id/hash 后，另一个目录能拥有另一个锁文件。目标目录为空、绝对路径相同、旧 PID 当前不可见或 UI 点击确认，均不证明唯一 owner 或原 owner 永久失效。
- P4c1 包只有 metadata/JSONL/序号 blobs，明确 `restorable=False`，没有 owner 转移证明。`source_stat` 是复制时的文件一致性事实，device/inode/path/hash 不能升级成跨主机、文件系统快照或跨 boot 的执行 owner 证明。旧包不得回填此证明。
- 包是过去的截面。导出以后，原目录可能已经消耗预算、增加 reservation、提交外部 job、撤销决定或追加 recovery。复制旧 ledger/clock 会回滚这些事实，甚至让两份目录各使用同一余额或原 call 权限。缺旧目录不能推“之后没有发生过”。
- 包排除了 native-homes、session/cache/凭据、host key locator，并只登记部分外部依赖；字节完整不等于依赖齐全、可续接平台 session、签名可核或仍获执行许可。跨 boot 的原 clock/deadline 不可通过重设 started/expiry 重新授时。

因此不实现“解包到空目标→继续”、不覆盖/重建原控制状态、不以删除原目录或确认对话框充当 fencing。原实例仍在时补文件的 material-repair 候选也不在本轮实施：它不能解决完整恢复的 owner 缺口，当前没有足够收益支撑另一个恢复表面。

## 2. 当下可复用的入口

| 情况 | 现有路径与限制 |
| --- | --- |
| 只剩归档包，或仅想核对保存内容 | `archive-inspect --package ...`。完整包内验证、分页清单/依赖；不运行包内内容，不创建 live 目录。 |
| 原 live 目录及完整当前控制原件仍在，controller 曾退出 | 原 `run`/`continue`，仍经 `_writer` 和现有 unknown/封存/预算规则。不把 archive 当控制输入，不保证每种退出都可继续。 |
| 原已知失败 native，需要同线程有限续接 | 原 `worker-resume`，要求既有显式 resume 合同、exact session/原件与剩余授权；缺 home/session/身份时仍 unavailable。 |
| 已 seal W 的原 pending call，需要显式有限推进 | 原 `execution-resume`，消费 positive pending-set/seal、原 call/interface/request 与原 ledger；旧 seal 缺该正面证据仍 unsupported。操作窗口不是新增 solver 或共享额度，审批过期按原 owner 换精确请求，不继承旧决定。 |
| 原外部 call 有未知或晚到终态 | 原 query/collect/retire 与 `execution-recover`，复用共同 terminal/fence validator 和原 call；unknown/lookup None/取消请求不退款、不重放。 |
| 原目录跨 boot 仍在 | 原件/已有包继续保留，维护仅限原合同实际允许的路径；当前 status 也可能因 clock 无法核验而拒绝，并不保证所有读取/恢复都成功。不能把错误变为续时、泛称“重启后可恢复”，或因旧进程不可见便新 dispatch。 |
| 原目录被删、空目录重建、异路径/异主机副本 | 只读包检查。当前没有产品提供的 writable restore，不复制 owner、消费状态或执行权。 |

原目录路径本身也不是身份授权。上表只复用既有 live 合同，不声称其 root 内锁已经具有可迁移的唯一物理 owner 证明，也不借只读包改变任一准入结论。现有 CLI/UI 控制已共享 `instance_control`；不需要新调度器来处理这些已支持情况。

## 3. 原 owner 与当前控制状态为什么必须保留

完整恢复若未来实施，至少必须保留并核实**当前**原件，不能取包内较旧版本覆盖：

- settings/job/seal、直接来源/review/作者与 exact implementation/target，保持原 subject；不能改路径后假称同源，或用同 hash 替代 origin。
- 最新 control/correction ledger 链、科学 clock、显式 ceiling 修订、resource grant/reserve/bind/actual/release 高水位；不清消费、不制造第二 reservation，也不复用过去余额。
- 原 accepted/prepared/dispatch/submission/external ID、pending-set、永久未提交 fence 与 append-only recovery；远端已接受 job 必须继续原调用身份，不因本地缺文件再 submit。
- 当前 decision/revoke、原 host key 身份、boot-bound 浏览凭据与有限操作期限。包内历史决定是证据字节，不是新 grant；恢复不复制浏览授权或私钥。

若这些原件丢失，当前包不能证明“没有更晚事件”。新预算池、重新签原决定、用模板补 accepted 或忽略 unknown 都不能填补这个缺口。

## 4. 真正完整恢复还缺什么

**缺的不是解压函数，而是唯一 owner 交接与所有写者共同消费的证据。** 未来设计至少要给出：原 owner 的可验证非复制锚；旧 owner/原生写者/外部提交永久 fencing；当前账本高水位不回滚；恢复失败不留下能推进的半成品根。这里的 fencing 指阻止旧 owner 继续重复发起新副作用，不要求销毁既有外部作业或成果；原身份的 query/cancel/collect 维护仍依原合同。跨 host/boot 或原锚丢失时不能猜测完成转移。当前没有批准这些协议，也不为本轮增加分布式 owner 服务、私有凭据库或第二任务/预算数据库。

不能只在将来的 restore CLI 检查一次。真实写入/launch 边界至少包括：

| 现有精确接缝 | 未来 owner 判定必须覆盖的行为；本轮不修改 |
| --- | --- |
| controller `_writer` / `run` / `closeout` / `worker_resume` / `execution_resume`；instance_control | 科学推进、清 pause、原调用恢复；不能为副本新开另一把锁便允许。 |
| protocol `require_current/require_scope` 与 contracts `build_job/seal` | 兼容性仍只作兼容性；需另有统一身份准入，不能把 CURRENT 当执行权限。 |
| native/runtime `_spawn/_run/_watch`、continuation、checkpoint/worker_delivery | 原生与 watchdog 后台写回、续接、封存。不能只检查前台 CLI 而放过已启动进程或后续回包。 |
| experiments configure/dispatch、Records `accept/publish/bind_external/lease`、插件实际 prepare/submit/collect | 同一个 owner 的原 call、target 和 lease；query 产生终态原件时也须同源，不凭公开 config 复制赋权。 |
| budget `_ledger_writer/_append` 及 reservation/settlement | 科学时钟与资源事实共用原唯一 owner，保持消费和修订，不重建余额。 |
| execution_authority writer/gate、UI decision/revoke/bind_secret | 执行批准、撤销和 key namespace；浏览管理 scope 不成为 owner 迁移批准。 |
| execution_recovery/execution_resume、history/qualification/compiled-original 封存 | 原恢复链、来源和 compiler/review 原件追加；不能补写另一套可消费身份。 |
| delivery 的 durable action intent/process/outcome 及实际 adapter 副作用 | 原提交/确认/清理与外部目标，不漏掉 controller 锁外的残留 owner。 |

这是一张后续设计的必须覆盖账，不是本轮已完成的全局 owner 实现。只读 `archive-inspect` 保持不接 clock/owner 写入；不让“读不合格副本”变成 grant、reconcile 或缓存状态权威。

外部依赖也不能以包内 checksum 替代验证：未来消费者必须逐项核 exact 原声明/路径/版本/行为代码与来源；缺插件、原 session、secret、输入或外部 job 绑定则保留 unknown/unsupported。禁止扫描 home/public_root 抄齐环境、自动安装或另跑模型来制造恢复证据。当前 dependencies JSONL 足以说明包没有复制什么，尚不足以完成上述资格。

## 5. 本轮交付与未实施账

唯一文件：`docs/plans/evidence/P4C2_WRITABLE_RESTORE_BOUNDARY_DESIGN_20261017.zh-CN.md`。没有生产、CLI/UI、schema、测试或凭据文件变更；没有 restore/material-repair API，也没有为旧包补 owner 字段。未 git add/commit。

仅阅读源码、已审设计/报告及静态 text/git；没有项目 import、pytest/collect、业务 CLI、安装/build、模型、服务器或远端运行。P4c2 真实阻断保留，P4c1 与原目录恢复的既有能力不受影响；后续可转向有独立收益的 P5 消费者退役，不以新子系统或“部分恢复”标记完整可写恢复完成。
