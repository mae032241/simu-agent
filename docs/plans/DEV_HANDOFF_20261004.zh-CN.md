# 2026-10-04 Covshift 当前交接

## 2026-10-05重启交接（当前入口）

- 本轮/tmp下245项Covshift数据已迁至项目根`archive/temporary-covshift-20261005`，约1.21GB，逐文件SHA256/权限/链接校验通过；原/tmp路径现在是链接。归档含认证副本，仅用户可访问且忽略Git。
- 重启后先运行：`python /home/da/project/ai4s/tcad/git_release/scidiscovery-agent/archive/temporary-covshift-20261005/restore_paths.py`。恢复链接、冲突拒绝、0模型；已实测删除一个别名再恢复，安装Python导入成功，两套spec各15关键路径无缺失。
- 真实Native场目录`scid-covshift-direct-2m-20261004-001/native_goal`：909733 tokens、科学阶段933.435s后旧1GB host限制退出；44模型，run44公开val0.9582/audit0.9522、leakage=false，有submitted.json；不标正常完成，不重跑。
- 真实Sci场目录`scid-covshift-auto-13gb-20261004-001/scidiscovery`：自动创建/绑定/预算确认成功，275977 tokens、科学阶段102.223s后因`control_usage_scope_conflict`退出，峰值1.092GB，无模型产物。这个启动器计量归属问题尚未修复，不能宣称重启后科学链路已正常。
- 下一步仅查明并修复`run_covshift_pilot.py`中的control_usage_scope_conflict真实触发项，然后准备新Sci场次。禁止旧结果补验、旧线程恢复与付费合成canary；不重放已提交场次。
- 已授权本任务自动创建绑定实例，2m tokens/1800秒/13GB；默认全角色6.1-sol/high，不fast，运行串行。每次真实费用均保留。用户已取消本次测试入口独审阻塞。

下面2026-10-04记录仅保留当时状态，以本节为准。


状态：**用户已明确终止旧结果补验与旧线程恢复。001–004诊断全部退役，不再是主任务前置；转向Native Goal与SciDiscovery双臂直接Covshift任务入口。** 本文下方诊断段落仅为历史记录，不授予重跑资格。当前不继续Native旧线程，不创建005补验；原预算消费仍保留。

## 可直接接手的状态

- integration：`/tmp/scid-main-integration-20261003-001`；dev：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。两处代码基线 `36cce914af3959020182784377738f720e2c21b4`；integration 本次交接／入口链接已独审，纳入本次文档节点。dev 的用户 `CONTRIBUTING.md`、未跟踪 `DEV_HANDOFF_20261003.zh-CN.md`／`evidence/` 保留，不纳入提交、不 stash/reset。
- 已安装 candidate：`/tmp/scid-covshift-remaining-20261004-candidate`；其干净 source：`/tmp/scid-covshift-remaining-20261004-source`，source commit `f5a709f9ca5c84daf6a187d79633a1fad992ced3`，wheel SHA256 `823336ded79ebd276f58bac5ed7b9c4d2bb94944dee0f2716a2865684c5c8f1a`。36c 只改 host launcher／测试／状态文案，未改产品 core；002 显式加载该安装的 core 与钉定 36c launcher，不冒充旧 snapshot 已含新脚本。
- 环境：`/tmp/scid-covshift-local-20261004-env`；真实公开 exp CLI 工程 smoke 保留于 `...-prepared-001`。正式公开输入为 `/tmp/scid-covshift-remaining-20261004-inputs-001/launch.json`，不是包含 Dockerfile／task.toml 的旧工程包；固定 LHTB `d78f5eb52ad754c5ee9154741af73130a85a65b8`，只交 agent 公开视图、净化 meta 与题面，不带 generator／rawmeta／hidden tests／答案／开发历史。
- 已认证双臂 spec：`/tmp/scid-covshift-remaining-20261004-auth-prepared-001/{native_goal,scidiscovery}/spec.json`。认证／provider 仅私有程序复制，禁止打印正文；旧包／结果不覆盖。当前无可直接继续科学阶段的命令，勿重跑旧 `run`。

## 原授权和实际消耗

用户原授权是每模式各一次 custom 链路 smoke，**全角色合计 200000 tokens／1800s**，模型候选全角色 `gpt-6.1-sol/high`；开发 agent 的 xhigh 不是试验条件。缓存输入不再额外相加，异步 usage 可能有在途计量偏差，不将观察后 stop 称作理论零超额 cap，也不承诺固定美元费用。

| Native 尝试 | 原件根目录 | tokens | phase／supervisor秒 | 实际结果 |
|---|---|---:|---|---|
| 初次 | `/tmp/scid-covshift-write-projection-20261004-auth-prepared-001/native_goal` | 87393 | 33.948／38.238 | canary：helper 模型 Astra 漂移，sidecar 未挂；未进科学 |
| 减额替代 | `/tmp/scid-covshift-remaining-20261004-auth-prepared-001/native_goal` | 79871 | 39.866／43.826 | canary：两实际角色模型正确、OS 十二 checks 成功，旧裸命令比较误拒；未进科学 |

累计 **167264，余额32736**。原 supervisor 合计82.064s；保守逐次向上取整已预留83s，不自动重置墙钟／tokens或退款。替代 spec 原上限112607／1761已被使用，不能再次原样启动。Sci arm 尚未启动，原200000／1800未使用；这不授予此刻自动启动。两组 **science=0、active Goal 未启动、trusted scoring=not_run、launch_ready=false**；原题4h／25次内部实验没有完成，25实验也不等于25 Root任务。

## 已审代码与证据

| 提交 | 本节点范围／审查事实 |
|---|---|
| `19ec2bc` | 独立依赖环境、公开 exp 工程 smoke；无模型 |
| `e77c61f` | 启动时全局任务禁网，默认off；owned native／web／HTTP拒绝，模型API保留，外部plugin/MCP不由flag兜底 |
| `dfec6bd`／`65d0183`／`2490466` | 双臂公开输入、真实Goal/Sci driver、exact named write-root投影；均独审后提交 |
| `af5ad0a` | 两正常宿主零模型preflight通过的限定资格记录，不等于live Worker/helper资格 |
| `35114d7` | exact sidecar只读SHA、真实SubAgentActivity父子绑定、canary实际turn_context模型门禁／真实turn计数 |
| `a019231` | 用户授权不主动施加RLIMIT_AS；保留RSS／CPU线程／超时／日志／UID锁，V8零模型算术成功；历史AS失败保留 |
| `f5a709f` | 每臂更低冻结预算参数；不是跨进程恢复系统，科学prompt明确6.1/high不代表全程强制 |
| `36cce91` | 仅接受裸exact命令或严格三项`/usr/bin/bash,-lc,expected`的回执投影；原status/exit/身份/权限/模型/usage门禁保留 |

36c 独审：`/tmp/scid-covshift-canary-receipt-20261004-independent-review-v1.md`；提交记录：`...-commit.md`。真实红→5项定向绿、受控离线回放只确证两份原OS回执／canary模型事实，**没有补齐当时未执行的 read/resume 权限门禁**，不提供跨run proof复用或跳过canary。

## 001失败与002宿主结果

001：`/tmp/scid-covshift-canary-permissions-20261004-001/result.json` 和 `supervision/resource.json`，return1/exited、0.779s、RSS145768448B。initialize/config通过，之后本地RuntimeError被压成通用reason；实际失败分支不可追溯，不能猜成auth/cold根因，也不能称真实角色权限失败。原pins／state比较为unchanged，原与副本rollout均未变，无新turn／active Goal请求。完整断网阻断模型API；原预算不变。

002：`/tmp/scid-covshift-canary-permissions-20261004-002`。匹配0.159.2官方源码证明：goal/get能读未加载的已封存线程；thread/read不加载，合法状态是notLoaded；原诊断在resume前强求idle是确定契约错误，**不是001实际退出分支的追认**。GoalService读取本地独立`goals_1.sqlite`，该读取链无auth硬前置；当前两个exact线程无Goal行。002一致性备份/pin state和真实Goal DB、两条exact rollout、原配置，保持原逻辑路径，不复制auth、不挂旧control socket、使用私有tmp；整个AppServer unshare-net。先核原终态／inactive Goal，初始只接受notLoaded/idle；无override excludeTurns resume后严格idle／同thread/session／权限，再走原完整门禁并复核Goal。新turn、active/unknown、未知身份／权限仍拒绝。

002异常也保留stage、last RPC／标准code、有限本地reason、脱敏status和调用序列／原件hash；不吐raw response、error.message、config／provider／URL／会话。20项**纯本地注入**通过（0 RPC／daemon／模型，默认guard0.298s、RSS38973440B），不等于真实补验通过。

002 曾经独立审查通过，随后用户在普通宿主执行。实际结果见 `/tmp/scid-covshift-canary-permissions-20261004-002/result.json`：`preload_thread` 阶段，`thread/read` 返回 `notLoaded`、空 turns，按现有终态校验拒绝。监督 return1/exited、0.653s、RSS130678784B，无内存止损、无新 turn／active Goal 请求，原件 pins 均未变化。这不是 OOM，也不是科学任务失败。

独立只读核查发现：两份原 rollout 均使用 paginated history；002 只备份 state／goals 库，遗漏 `thread_history_1.sqlite`。原历史 turns/items/projection 为 2/12/2，副本为 0/0/0。原两线程各有一个 completed turn，rollout 与持久投影身份、尾偏移一致。003 将补齐历史库的一致性副本和冻结检查，保留非空 completed turns 与完整权限门禁，不将空历史视为成功。现有源码快照标识 0.159.2，但其精确下载 tag／commit 与二进制的对应尚未独立证明。

003 由独立执行者修复并经另一位审查者独审通过；37项纯本地注入检查通过（0 RPC／模型；0.329s、RSS45113344B，无内存止损），包括002缺历史库复现与补齐副本后原门禁通过。此结果不是宿主权限资格；003后来已在宿主失败，下面只保留历史说明；002／003均不重复执行。原001／002证据保持不变。开发执行与审查使用 `gpt-6.1-sol/high`，不主动启用 fast；本地测试串行，不启动付费模型。

## 003历史命令（已失败，不重跑）

[003独立审查](/tmp/scid-covshift-canary-permissions-20261004-003/independent-review.md)核对备份、原件pins、exact身份与完整权限门禁，未发现阻断。诊断冻结见同目录 `freeze.json`，其中记录文档的是审查前版本；本节为审查后的入口更新。003随后已执行，宿主结果失败；此前本地测试与独审未覆盖真实嵌套沙箱目录创建需求。

003原命令入口为该目录 `check.py`；已失败退役，不提供重跑命令。此前独审的通过范围只覆盖当时的代码和本地证据，未覆盖真实嵌套沙箱初始化。

## 003宿主失败与004修复

003真实结果：`thread/read`已返回completed，`thread/resume`返回RPC -32603。监督1.049s、RSS269078528B、return1/exited，无内存止损、无新turn／active Goal，原pins不变。私有日志与冻结绑定表只读核对确认：sandbox helper在submission逻辑目录内mkdir `.git`时遇到只读文件系统；该目录原是write grant／`--bind`，003却将其改为`--ro-bind`。这是诊断自己的外层挂载与恢复初始化冲突，不是科学任务失败。

004已修正为对精确原可写绑定使用私有副本并保留原逻辑目标和`--bind`。原目录不放开写权限，冻结named grants不变；原历史库修复与完整终态／权限门禁保留。48项纯本地回归通过（0.293s、RSS49094656B；0 native／RPC／模型），其中mkdir正例是在私有副本执行Python操作，并非真实sandbox运行。独审已通过，使用下面唯一004入口，不重复003。原费用和科学资格不变。

## 004退役

004已实际执行并失败在helper冷读的`sealed_session_changed`。用户明确表示旧结果无需补齐，已停止诊断执行者和协议调查者；不再发布该命令或修复恢复路径。原件保留。

## 当前推进路线

- 修改实际新任务入口，取消把付费合成role canary作为本轮科学smoke的必经任务；新任务不引用旧资格证明。
- 两臂使用相同公开题面和gpt-6.1-sol/high；用户已授权本次每臂2000000 tokens，墙钟沿用1800秒；旧Native消耗单独保留。串行监督、原文件隔离和用量采集保持。
- 人工在管理页选择实例和授权loop；按实际科学任务评估产出，未观测的角色隔离或隐藏评分如实记为未验证。
- 用户取消本次测试入口的独审阻塞；入口及定向测试已完成（29 passed，5.021s、RSS131117056B）。两臂不再调用付费role_canary；新鲜任务仍进行现有无模型路径隔离检查，完整角色资格标未验证。Native剩余额度32736不重置。
- 新目录`/tmp/scid-covshift-direct-20261004-001`已准备（2.058s、RSS93212672B，0模型）。两臂spec暂存200000／1800，尚未获得新Native预算确认，不得直接启动；如选择沿用余额，需另建等额32736的双臂输入。

## 后续边界

即使后续补验通过，也只补齐这些exact旧线程的权限门禁。现有`run`会无条件再次付费canary，然后新建科学线程；没有继续旧run／跳canary／跨进程复用proof入口。剩32736不能新开200k；任何下一paid尝试先定具体预算处置及真实可消费入口，不能靠本交接假造恢复能力。

真实Sci Worker/helper继承、全角色科学阶段模型／计量与停止、Native/Sci正式双驱动效果、trusted评分仍未取得资格。pickle不得在有隐藏labels/metric/results权限的宿主直接加载；原评分隔离代理尚未实现，不能自造等价分数。不要读hidden verifier／solution／参考解；不要让被测线程继承本交接或开发对话。002先前已独审但宿主失败；004及本次交接更新独审通过后本地提交，不push。

## 新双臂200万预算入口

用户已将新场每臂预算授权为2000000 tokens，时间沿用1800秒。新目录`/tmp/scid-covshift-direct-2m-20261004-001`已准备，两个spec均核对该预算。入口默认仍200000，显式参数可到2000000；旧spec不变。定向源码测试通过，未启动模型；顺序Native Goal后SciDiscovery，不并发。新目录取代之前未启动的20万目录。

## 13GB内存配置

Native新场实际在909733 observed tokens、933.435秒科学阶段后触发原1GB host resource_limit；已有44模型及公开submitted记录，异常结束，不重放。用户授权放开内存，现以scripts/acceptance/covshift_resources_13gb.json显式配置两臂树RSS/AppServer/后台Root为13000000000 bytes，最小系统可用1000000000，下降止损13000000000；无AS限制。新目录`/tmp/scid-covshift-direct-13gb-20261004-001`已准备，两臂settings/spec核对一致，尚无模型调用。优先运行未执行Sci臂；不自动重跑Native，原成本/异常终态保留。两臂内存条件不同须在比较里说明。

## control_usage_scope_conflict定位结论（2026-10-05，只读复现）

真实失败账本可确定性复现启动器错误，无模型请求。账本两条：root归属实例与loop正确；另一条role=unattributed、owner=null、thread/loop正确。该线程原生session_meta.parent_thread_id精确指向已记账Root，Root原生SubAgentActivity确认started；runs仅1个queued、worker_connections=0。子线程已观察16218输入+59输出=16277 tokens，尚无attach记录。

生产progression_budget.apply_usage_observation明确支持用量先于绑定到达：未归属时暂存当前loop、owner=null，后续通过原绑定reconcile；codex_usage.ROLES也明确含unattributed。启动器run_covshift_pilot.reconcile_control却强制owner==instance且role仅root/worker/helper，并立即抛control_usage_scope_conflict。因此这是启动器把正常spawn→首usage→attach时序的暂态当最终冲突。异常导致外层关闭daemon/host，queued任务无机会完成attach，不是OOM/额度耗尽/科学失败。

修复方向：本loop未归属用量持续计入总额并标pending attribution，保持时长/token止损；绑定出现后精确核对实例/loop/role，不猜角色，不丢成本。真正错loop/错已绑定owner仍拒绝；停机最终仍未归属应保留partial，不报完整覆盖。补spawn usage-before-attach→attach的定向回归及错误归属负例。本次仅定位，代码尚未修改。

## 计量待归属修复（2026-10-05）

启动器reconcile_control现接受本loop中role=unattributed且owner=null的暂态，照常累计成本并输出pending_attribution；后续正式绑定仍严格核实例/loop/角色，结束未归属则coverage=partial。用量/墙钟止损保留，未删除归属校验。定向测试通过；真实失败账本只读回放已不再抛control_usage_scope_conflict，无模型/无重跑。测试证据位于项目根archive/temporary-covshift-20261005/covshift-attribution-fix-20261005。此前“尚未修复”描述为历史状态；仍未取得新真实场次通过证据。
