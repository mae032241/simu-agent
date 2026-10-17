# P4c1 框架原件只读归档包：实施冻结

状态：**实现冻结，交独立静态审查；未动态验收。** 基线含 P4b `a5c3fbe`、[归档范围设计](P4C1_ARCHIVE_SCOPE_DESIGN_20261017.zh-CN.md)及其[设计独审](P4C1_ARCHIVE_SCOPE_DESIGN_REVIEW_20261017.zh-CN.md)，冻结时 HEAD 为 `7a89800`。本轮只实现导出与包内检查，不实现 P4c2 可写恢复，不声称研究输入或原生环境全部覆盖。

## 公共入口与只读结构

- `scid-research archive-export --root ORIGINAL --output NEW_PACKAGE`：明确原实例与全新独立目标，拒绝覆盖、源/目标包含关系和非 canonical/symlink 路径；目标父目录须已存在。原 controller 当前协议 guard 保留，不迁移旧协议实例。
- `scid-research archive-inspect --package PACKAGE [--section manifest|dependencies] [--after INDEX] [--limit N]`：检查全部包内容，返回有界页和 exact `next_after`。分页不是记录上限，不省略后续页，也不跳过全包验证。
- 顶层只有 `archive.json`、`manifest.jsonl`、`dependencies.jsonl`、`blobs/`；原件使用序号 blob 名，逻辑原路径只在逐行清单中。没有 live 的 `settings.json/jobs` 布局，没有 restore/unpack/推进副本命令；原 `controller.run` 在包上找不到实例身份，不能凭删除 marker 开启写入。
- 复用中立 `scidiscovery.archive_io` 的 canonical、path/special-file/hash、分块 copy、durable JSON 和 fsync 原语，不导入旧 service/SQL/CAS。新 Linux `renameat2(RENAME_NOREPLACE)` 只负责同文件系统 staging→新目录原子发布；不可用即拒绝，无可覆盖 fallback。
- inspect 函数仅使用标准库与 archive_io，不进行插件发现、factory load、backend 查询或包内代码执行；现 CLI 仍有原 core 模块导入。inspect 复核 metadata/schema、两份清单身份/顺序/count、规范逻辑路径、重复项、每个 blob 的 SHA/大小/mode、未列 blob、settings/identity/instance 一致性及 symlink。没有因 `restorable=false` 标记而赋予安全性；不能推进的保证来自布局与现有实例入口本身。

## 生产写入点核对与精确范围

对 `research_loop/*.py` 做静态 root literal AST 扫描，并核对 contracts/controller、runtime/native/continuation、experiments/Records、budget、authority/UI、history/recovery、candidate_audit/audit_recovery/shortlist、delivery、correction 的实际写入及嵌套锁。扫描找出原设计表漏项 **`correction-ledger/`**，已补入设计表和实现。

| 原件范围 | 实际 owner / 本轮处理 |
| --- | --- |
| settings/identity、host-started、pause.request；jobs | controller/contracts/instance_control；原字节与身份，暂停只是历史事实。 |
| project/global、project/nodes | contracts/native/registered managed work；含完整成果、work/lineage/calls、受管输入输出及 d2a compiler 原件，不按附件数裁剪。project 其他子目录记 gap，不扫描。 |
| control-ledger、correction-ledger | 原 budget、correction 追加 owner；保留消费、reservation、触发与 ack，不产生新授权或余额。 |
| native-evidence | runtime/native/execution/continuation/qualification；保留框架已 retained 的 intent/outcome/usage/raw/process/参与者/封存原件。 |
| host-runtime/experiment-control | budget/experiments；interface projection、准入原件；host-runtime 其他子目录记 gap。 |
| host-history | history/qualification/execution_recovery；原观察与追加恢复 refs，不制造 external terminal。 |
| host-delivery | delivery/audit/selection；候选原件及过程/结果；未结束或 cleanup 未确认则拒导出。 |
| source-provenance、qualification | qualification/formal_review；来源与 review 合同/原件。 |
| execution-authority | 原 contract、host-key digest、allocation/request/decision/revoke/call 原件保留；精确排除 host-key-source.json、ui-endpoint.json、ui.lock、writer.lock。不复制密钥或 locator。 |

其他根路径只记录名称、类型事实和 `gap`，不递归、不静默假称完整。`native-homes` 整体仅记排除，避免递归凭据、session、缓存。外部 public_root、launcher、observer/delivery adapter 与已冻结注册代码的 exact references 写入 dependencies JSONL，不读取/扫描外部树；没有 frozen 插件 storage ownership projection 时明确 unsupported gap，不调用旧 archive_storage factory猜范围。未保留的外部 session、代码/资源与密钥都不因同路径/同 hash 获得来源、签名验证或恢复资格。

锁文件只在实际 owner namespace 排除：根 controller/budget 锁、native attempt runner.lock、host-runtime exact digest 下 accept.lock、Records root 的 node/accept 及现有 accepted call 对应的具体 lease 名。**科学材料中同名 `writer.lock` 等正常保留**，没有全树 `*.lock` 删除规则。

## 静止判定与实际锁顺序

全部 exporter 锁在首 inventory 之前完成，以非阻塞方式取得，冲突立即退出，不等待模型、不 cancel 原 owner：

1. 复用 `controller._writer`（原 current-protocol guard）。
2. 原 `execution-authority/ui.lock`，阻止同实例 UI 写者。
3. 各明确 native-intent 所属的原 runner lease。
4. 原 Records node→accept 及各 call 的 TCAD submission→binding→collect、observation、engineering leases；另持 soft admission 的原 host-runtime accept.lock。
5. 原 authority writer→原 control-ledger 锁。

真实生产嵌套依据：Records.accept 为 node→accept；TCAD submit 为 submission→authority→ledger，绑定 lease 在 submission 内；runner 完成仍持 runner lease但只非阻塞探测 controller。exporter 同样全部非阻塞，不会反向等待。它只创建/持有原控制锁文件，不追加科学/资源事件；这些自建锁均在初始清单前建立并精确排除。

持锁后不调用 snapshot、reconcile、execution.record、factory、query 或维护。明确路径读取原 chain：

- native 必须绑定 exact job，有 outcome；已启动 native 必须有整数 returncode 与 `observed_group_cleaned`。实际 retained runner/native/watchdog process 仍活跃、身份不完整、watchdog cleanup unknown、无 intent 的 process 或缺 outcome 均拒绝。
- managed call 必须通过唯一 `verify_observation` 或 `verify_retirement`，仅原件 loader + accepted 原 interface；再核 exact call/scope/accepted proof。没有 terminal/fence 原件、临时 `.prepared-*`、工程 replay 缺 outcome/cleanup 或 authority prepare-intent 无 accepted 均拒绝，不从缺文件推“没提交”。
- 原 `budget.closeout_state` 只读折叠既有 ledger，无当前 clock 或 lock 重入；未完成/unknown delivery、未完 audit/selection、source preparation cleanup 未确认均拒绝。检查 retained delivery/replay process 的实际身份，不调用后端刷新事实。

这里判断的是框架已有合同与 retained owner 事实。已知终态外部 job 仍依赖原可信 adapter 终态合同；不能证明任意 detached 同 uid shell 或未声明插件存储也静止。未知被拒绝或明确属于缺口，不被改为 terminal。

## 流式复制、一致性与资源边界

- 首次逐文件流式 hash/copy，保存 SHA/大小/mode/device/inode/mtime/ctime；目录也有身份，空目录不丢。清单按规范路径组件顺序逐行写，未把全内容/全文件清单拼成一个 JSON。
- staging 位于目标同文件系统。每个 blob 沿 archive_io 验证；发布前重新遍历完整已声明 scope，逐行比较全清单与身份/hash；新增、删除、内容或 metadata 改动均不发布。失败清理 staging，保留原实例/已有包；不回滚并发原写者自己的变更。
- 没有隐含文件数、总字节或科学材料 cap；显式磁盘/OS/FD 限制失败只影响导出。此版没有新磁盘额度或资源预算 owner。
- JSONL 是逐行处理，**每行 JSON、固定 metadata、原 settings、必要 terminal JSON 和原 ledger fold 仍完整解析**；每个目录的排序、原 call/intent 集合和持锁 FD 也消耗资源。不是零内存或恒定 IO。
- export 会多次读取文件以做 hash、copy、目标验证和最终源身份核对；inspect 每一页仍全验两份清单与全部 blobs，分页只限制返回。没有动态性能/OOM 结论，没有另建缓存或第二状态库。

## 最小负控（仅写，未运行）

`tests/research_loop/test_instance_archive.py` 四条小 fixture：

1. 真实 prepare 后归档静态字节：correction-ledger 纳入、科学 `writer.lock` 保留、native credentials/key locator 排除、未知存储 gap、public_root 缺失如实登记；验证序号 blob 原字节、分页及实际 inspect CLI消费、已有目标不覆盖；真实 controller.run 不能把包认作 live root。人为 correction/locator 字节只作归档内容，不声称科学/审批有效。
2. 真实 controller writer、UI host lock、Records lease 冲突分别拒绝；实际 build_job 的 native intent 缺 outcome 时拒绝；原材料不改，无包发布。不启动 native/后台任务。
3. copy 后由 fixture 联合修改已有内容并新增原件，发布前整 scope 重扫拒绝；保留该并发修改且 staging 清理。此例是**联合扰动**，不声称动态独立证明新增/修改两个分支。
4. 改清单后重算外层 manifest proof，再检查 traversal/重复逻辑路径确由语义 validator 拒绝；坏 blob 恢复原 mode 后仍因内容 SHA 不符拒绝，避免仅 mode 差异自证；symlink blob 拒绝。

这些断言不写“成功后端 JSON”，不安装环境、不递归启动 pytest。真实大记录、full native/TCAD、并发交付、跨进程发布竞争、磁盘满及 Linux renameat2 行为尚未动态验收。

## 精确冻结清单与检查

生产 2 文件：新 `src/scidiscovery/research_loop/instance_archive.py`；改 `src/scidiscovery/research_loop/cli.py`。测试 1 文件：新 `tests/research_loop/test_instance_archive.py`。文档 2 文件：设计补表 `P4C1_ARCHIVE_SCOPE_DESIGN_20261017.zh-CN.md`；本实施记录。独审报告由 reviewer 单独持有。

未改并行 d2a/d2b 的 experiments/authority/contracts/adapter/compiler，未新增 UI/secret/server、执行授权、预算或恢复 dispatcher。未 git add/commit。

3 个自有 Python 文件已标准库 `ast.parse`；tracked/new 自有文件 whitespace 检查未报错。没有运行项目 import、CLI/HTTP、pytest/collect、build/install、业务子进程、模型/solver。只读包内部一致性不等于来源真实性、科学资格、完整研究环境或可写恢复；P4c2 仍未批准/未实施。
