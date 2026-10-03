# S3-R：长 loop 控制与记忆设计

状态：P0、P1a 及 P4a 已实施部分通过定向验证和独立评审，未部署；本轮已修复科学暂停作用范围、无效人工观察和轮询/时间预算缺陷，逐项独立复核通过。P4a 功能与结构收口完成；用户已明确将代码净减少目标转为后续待办，不再阻断 main 合并。其余生产改动与运行验收待实施。
P1c 已拆为串行独立评审的子节点：P1c-1 复审通过、已提交 `2f735b0`，未部署；P1c-2a 实施研究／精确独立审查分额和观察去重，恢复阻断修复后独立复审通过、已提交 `74c6120`；P1c-2b 首审拒绝一项历史判断入口缺口，修复和定向验证完成、独立复审通过，已提交 `a59e5c5`，未部署。P1d-1 首评 3 个 P1 与追加暂停遥测 1 个 P1 均经独立复核关闭，已提交 `cc2affd`，未部署。P1d-2 首评拒绝 1 个 P1，修复与定向验证完成、独立复审通过，随本节点提交，未部署。完整前台原生遥测单列后续实测能力，有限策略创建仍不可用；完整 P1c 未完成。
基于 `6e85a31` 的结构简化增量已完成定向验证与独立评审：共享控制准入、UI 身份／转移、终态结算和明细写入，移除旧采样缓存及无生产调用入口。固定 22 文件仍为物理行 +128、非空非注释行 +127，原双口径净减少目标尚未达到，按用户决定列为后续待办；准确计数和验证由[主计划 S3-R 状态](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#s3-r长-loop-记忆可靠唤醒与强制刹车)维护。main `ff451e9` 合并候选已完成冲突处理和源码验证，独立复审通过；不把局部净减解释为整体达标。
本文拥有 S3-R 的预算/授权、通知、记忆、轮换、刹车与验收规则；[主计划](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md)只维护实施节点、状态和退出条件。历史源码与验收结论不因本设计变化而改判。本文不进入 Agent 启动材料。

基线为 `dev de3a63c`。本设计承接用户要求：保留自动强制刹车，长 loop 中保留早期尝试与失败经验，避免重复弯路。范围为同一研究 loop 的持续上下文，不建设跨项目通用经验库。本设计替代此前 R1–R5 实施顺序，并覆盖第 4–5 节、旧 S3 与第 7–8 节中科研专用一次复判/交回许可、“精修仅提示”“新引用加 Root advance 可清零”的未来安排；旧代码与验收仍作为基线历史。

## 目标规模与计量单位（本轮新增，尚未实施）

产品目标是支持一个研究 loop 持续 3–7 天、完成 100–300 个完整研究任务；先执行 4–6 个任务、约 2 小时的 P6s 小型验收，通过后再取得 30 个任务／24 小时资格。这里是可承载规模，实际启动额度由用户或已授权策略明确确认，不能把容量目标直接变成默认的一周无人值守授权。研究已完成、材料不足或刹车触发时正常停止，不为凑数量派发无价值任务。

| 单位 | 计数对象与责任 |
|---|---|
| 研究 loop | 控制层创建的稳定预算作用域，可跨目标修订、Root 线程和人工/后台切换；暂停、停止后恢复均沿用原身份与剩余额度 |
| 完整研究任务 | 一次 Worker 负责的探索、实验等完整任务；精确独立审查另计，Root 决策轮数另计；任务内可能有多次实验、诊断与求解器提交 |
| 精确独立审查 | 控制层按已编译审查合同、确切被审对象及审查者独立性识别，使用单独审查额度，不占研究任务名额 |
| Root 回合、Worker、helper | 各自记录身份和 usage，全部归属实际授权 loop；助手不成为 Root 任务，但其消耗不能漏算 |
| 实例执行池 | 求解器机时、存储等确需跨 loop 累计的执行约束继续保留；不因新 loop 或新目标清零 |

新 loop 仅由管理界面的用户明确创建并授权，或由控制层执行用户事先授权的有限策略创建。UI 复用既有身份绑定、capability、CSRF 和审计；策略必须限定适用实例、总预算池、创建次数/频率及有效期，创建时原子预留共享额度。Root 可以提出建议，但不能签发或扩大策略；普通 MCP start、恢复、目标修订及人工继续均只作用于已有 loop，不能新建 loop 或自动续额。用户与策略入口复用同一创建服务，并发或重复请求不能重复授额。新 loop 可引用旧研究历史，历史连续与预算身份分开；原 loop 已接受/结果未知的工作继续归原账本，不能借新 loop 重放提交。控制层填充身份、时间和来源，Agent 只提供有价值的科学内容。独立人工任务必须显示其实际预算作用域；进入同一 loop 的人工任务计入该 loop，不能保留隐形免额旁路，也不能把既有独立人工记录追溯混算。

当前限制核查（`de3a63c`，不是目标行为）：max_tasks 默认 8、字段上限 100；max_rounds 默认 12、上限 100。`max_tasks * (1 + helpers.max_calls) + max_rounds > 64` 的旧 usage 容量检查在默认 helper=4、rounds=12 时把任务数实际卡到 10。max_probes=720、poll_seconds=5 在持续空闲探测下约一小时即耗尽；max_elapsed_seconds=3600 从 started_at 计算，人工暂停也占用。max_attempts=2 不代表普通失败自动重试两次：普通 Root 回合失败当前会直接停，恢复尝试另受限制。后台 checkpoint 可跨目标延续，独立人工任务又被排除，所以当前也不是“实例全部任务统一终身限 8 次”。这些限制须逐项替换，不只放大两个数值。

## P1c / P1d：Loop 预算、时间与恢复

首批交付顺序：先固定 loop 身份与预算归属，将 P1d 的统一推进时长计量前移到 P1c 首批，再扩研究/审查额度和长跑容量；P1d 后续收口自然期限、停机恢复和时钟异常。服务预算检查、人工恢复和 UI 必须共用同一时间口径，不能只给恢复入口免计暂停。main 同步与 P4a 收口前置条件保持不变。

现有调度会话的时间缺陷已先行修复：`enabled_seconds`、`enabled_at`、`time_high_water` 共用一个控制层计量函数；`started_at` 仅保留历史时间。明确暂停/独立人工关表，正常等待、同预算人工继续与原宿主的已接受审查收尾计时；活动失联保守计入，已记用量不因回拨、重启或首次宿主连接而退款。宿主 deadline、准入和 UI 使用相同余额；确认旧回合的同宿主恢复在首次 RPC 前同步。`max_probes` 配置及额度判定已退役，probes 仅作诊断，轮询限频仍在。控制 schema 4 明确拒绝旧库/归档，不做账本回填；这尚不是按 loop 计账、新自然期限或跨天运行资格。

### P1c-1 提交边界（2026-10-02，复审通过，`2f735b0`，未部署）

- 管理页使用既有 capability、CSRF、实例选择与精确确认绑定，明确授权一个冻结预算的 loop；确认后保持暂停，再由 MCP/UI 启动。重复与并发的同一确认只授一次额。Root/MCP、恢复、目标修改、人工继续均不能创建或续额，有限策略入口未实现。额度授权保留科学暂停，仍须原有人工缺口确认。
- 未加入 managed loop 的普通交互和第三方任务保持原权限及实例执行预算。一旦加入，后续交互、后台、人工接管、RunService 直调及独立执行沿当前 loop；暂停、停止、改目标、重启和归档恢复不刷新预算。原实例执行池不重置，旧未 managed 工作不追溯绑定。
- `loop_authorizations` 使用现有控制明细表，任务录入和 loop 归属在同一控制／Run 事务内；native 线程归属复用任务、Worker/helper 连接与 usage，不另建账本。已有 accepted/unknown 工作不得换 loop 重放；跨 loop 禁止复用原 native 线程。结清后可由 UI 明确创建下一 loop；迟到累计用量更新原退休 loop 的消耗及余额，不侵占新 loop。
- 控制 schema 5 显式拒绝旧 state／归档，无静默迁移。保留旧 `max_tasks`、`max_rounds` 和 64 身份组合保护；`max_loop_scopes`（默认 8，上限 64）仅限制仍整体加载的授权历史，达到容量明确停止，不增加默认任务授权。P2 尚未提供全面历史分页／聚合，此子节点不声明长期无限续建或 300 任务资格。
- 后台原生 Root、Worker/helper 已知用量按原线程累计；身份预登记不作为真实缺测样本，首个完整 cumulative 可结清，真实缺测／回拨保留。前台 Root、Worker 和 helper 均尚未接入原生宿主遥测：控制按真实准入模式冻结 `usage_source`，managed 人工工作仍计任务、已知 tokens 和推进启用时间，UI 明示 `missing/partial`。现有 `strict` 拒绝不完整用量的新工作；`bounded_fallback` 依已知 tokens、任务及时间额度推进，已结清的前台任务可继续下一任务和由 UI 明确授权下一 loop，不声称所有角色 token 硬封顶。旧缺测事实及已知消耗永久保留，不能抹成零；活动／未知工作及原生宿主的真实计量缺口仍阻断授额。
- 同目标的后续授权扩展有限观察读取容量，保留旧科学窗口、触发和历史，不把审查 pass 当探索或清零依据。研究／审查仍共享旧任务名额；分额与审查观察语义收口、完整前台各角色计量、300 容量、有限策略、自然期限／分故障恢复、历史 memory／rotation 和科学判据均未由 P1c-1 完成。
- 本轮只运行受监督、串行 source 夹具与真实本地 HTTP/MCP 路由，不运行模型、TCAD、安装或长场。旧 live `accept_progression`／B6 运行器的直接后台 start 不再足以启动，须接入显式管理页预算确认；运行器适配与真实运行留 P1b，不能将旧命令声称为开箱可跑，也不由脚本秘密代授额。

P1c-1 首轮定向证据：17 个 source 文件去重 254 项通过、1 项按 lane 排除；人工继续文件原 32 项通过加 3 项已修负例精确复测，不将中间旧夹具失败豁免。最后六文件 103 项全部通过，目录 `/tmp/scid-p1c1-final-r19-20261002`；授权历史／分页／归档 10 项通过，目录 `/tmp/scid-p1c1-records-recovery-r18-20261002` 的 batch-001。汇总 `/tmp/scid-p1c1-source-rollup-20261002.json` 包含全部选用目标、日志和监督数据；选用证据累计 332.417 秒、最高 RSS 181788672 字节，无超时或内存止损。首轮独立评审仍发现三处可达缺口，不能以这些通过项代替语义评审。

首轮拒绝后的修复证据：共用原 loop 归属检查贯穿只读恢复／草稿 preflight 与 schedule，真实合法 failed recovery 稿跨 loop 的两个 MCP 拒绝均不留下 prepared；前台无 usage 注入完成首 Worker 后可在 fallback 下续任务及授权下一预算，原 missing／partial 和真实已知消耗保留，strict、活动／未知工作和原生真实缺测仍阻断；direct RunService.schedule 与 UI 授额在既有调度锁下共享事务次序，受控线程竞争无未 managed 活动漏入或死锁。最终六个定向目标 89 项全部通过（23+1+13+14+32+6），命令与日志在 `/tmp/scid-p1c1-review-fixes-r21-20261002`；监督合计 87.425 秒、RSS 峰值 152092672 字节，无超时、内存止损或未结束的锁等待。只读／提交链、前台真实缺测路径和锁竞争覆盖本次三项修复；管理页遥测说明及本计划补录晚于最后测试。同一独立评审者已复核真实入口与负例，三项阻断关闭，允许提交源码节点；不代表完整套件、process／browser／live／安装或完整 P1c 资格。

### P1c-2a 实现边界（2026-10-02，恢复阻断修复后独立复审通过、已提交 `74c6120`，未部署）

控制用同一分类函数读取当前 compiled `independent_review_ports`、确切封存主体及 `review_authors` 的可验证参与作者；native 附着仍验证 reviewer 与每个作者独立。只有真实主体及可验证作者的合格 Agent 审查使用审查名额；Operation／任务名称、Root 自报、scientific intent 和 helper 均不授予豁免。普通审查与 accepted owner 的精确 review_dependency 同规则，研究修订仍计研究。

分类冻结在现有 Run recovery_policy 和准入明细，preflight、RunService 直调、准备／提交及原稿恢复共用规则。Agent Run 的准备与 accepted 录入合入原 Run/control 同事务，保留 target 名称、logical_name、revision、fingerprint 与 semantic_binding_pending 核清；晚拒回滚未接受记录，未知及已接受提交仍不能换名重放。未改变 Transform／Approval／Effect 的提交协议。

研究 `max_tasks` 默认 8、Root `max_rounds` 默认 12 不变；新增 `max_reviews` 默认 2（可配置为 0），随 UI 授额冻结。64 身份保护为 `(max_tasks + max_reviews) * (1 + helpers.max_calls) + max_rounds`，默认 62，审查 helper 同样占容量。两类名额分别拒绝，各角色可测 tokens、推进时长、Root 回合及恢复共享 loop 总预算，实例求解器池不变。通用启停／人工继续不因仅一类名额耗尽而阻止另一类；精确 accepted review 可沿科学暂停原权限续接，人工 pause、未知和总预算不豁免。

审查保留交付／判断／历史；控制冻结分类将其从探索计数中排除，审查 pass 或对审查的 advance 不单独清科学停滞。研究成果的判断仍遵循既有确切证据规则。有限观察读取容量包含研究与审查，保留历史窗口及旧触发。控制 schema 6 显式拒绝 schema 5 库／归档，不猜测旧分类。300 容量、完整前台各角色原生遥测、有限策略及 P1d/P2/P3b/P4b 均未由本子节点完成。

P1c-2a 定向证据：13 个 source 文件去重 214 项通过；人工文件 34 项通过及已修 admission 负例 1 项精确复测，不将其失败批次声明为文件全过。选用通过证据为 r8 前六 batch、r9 第一 batch、r10 五个 batch 的通过项及 r11 两个精确目标；汇总 `/tmp/scid-p1c2a-source-rollup-20261002.json` 记录目标、日志、监督结果和排除范围。监督合计 199.795 秒、RSS 峰值 151318528 字节，无超时或内存止损。新名额语义下的观察容量、纯研究分页预算和人工未决记录夹具已适配，未豁免中间失败。覆盖真实 MCP 分额／修订／幂等、直接 RunService 原子录入／晚拒回滚、精确科学暂停续接、审查交付去重及 helper 总用量；未运行完整套件、process/browser、模型、安装或 TCAD。首轮独立评审仍拒绝一项同 loop 跨合同原稿恢复回归。

P1c-2a 恢复修复：核验原 Run 分类与同 loop 唯一 accepted 控制准入的冻结分类一致，不再要求旧 compiled 合同能从当前 catalog 加载；新任务仍按当前合同分类。保留原稿字节／manifest、原始输入、原科学生成及原恢复次数预算，未扩大 reviewer 独立性或角色迁移权限。修前 managed 精确用例在 `/tmp/scid-p1c2a-recovery-negative-r12-20261002` 失败；修后 `/tmp/scid-p1c2a-recovery-final-r14-20261002` 前三 batch 共 19 项通过，覆盖真实 MCP 同 loop 跨 digest preflight／invoke、原预算、未知／篡改分类及跨 loop 拒绝且无 prepared 残留。共享审查文件在 `/tmp/scid-p1c2a-recovery-adjacent-r15-20261002/batch-002` 14 项通过。

邻近恢复证据单列：r14 的实验继续文件 12 项通过、1 项在既有 debug 夹具断言 `7200 <= 7199` 失败；该精确用例 r15 的 batch-001 重跑 1 项通过。原失败仍保留，不能据一次重跑认定时间波动已解决或豁免；只静态确认返回值取每次调用的 `context.remaining_seconds`，尚未确认是夹具断言还是生产 timer 风险，复审未发现由本次差异引入的证据，不新增源码提交阻断；时长稳定性及完整实验继续文件资格仍未取得。r14／r15 共监督 60.358 秒，RSS 峰值 145182720 字节，无超时／内存止损；不扩展执行源码或资格范围，同一独立评审者已复核并关闭恢复阻断，允许提交源码节点，未授予真实运行资格。

### P1c-2b 源码冻结边界

2026-10-02，基线 `74c6120`：首审拒绝一项 P1，历史判断入口修复后独立复审通过，已提交 `a59e5c5`，未部署。

- 复用现有明细表与 loop／Run／序列／目标索引；正常读取只解码当前 loop，迟到 usage 按确切 thread 补原 loop，最多两个作用域，在同一事务内归约并结算原余额。未读历史的行与余额保留。保存必须带完整 metadata 和引用 map；raw refs、缺 metadata／map／行均拒写，显式空 map 仅删除已读作用域。完整替换须明确使用维护全读、初始化或导入。schema 7 拒绝旧库／归档。
- 冻结 `detail_capacity` 与实际字节限制承接旧 64／100 保护：默认 4096 身份、单条 64 KiB、读取 64 MiB，每 loop 实际明细最多占其读取额度一半，超限整事务回滚。研究／审查／Root 默认仍为 8／2／12；300 配置须 UI 明确授权，不自动续额。
- 原生身份沿 loop SQL 或确切 thread 查询，同线程保留全部 `run_ids`，前台复用不能隐去原生缺测。Run 本页按 exact name／Run 绑定读旧目标；后台历史页受 `related_source_limit` 限制并显示遗漏，确切封存 `run_status` 原生回执才消费。前台遥测继续沿 strict／bounded_fallback。
- 唯一生产 `prepared` 入口在 Run／control 同事务保存前填 loop／分类；原有未 managed 未知任务及旧 loop 未决工作阻止新 loop 授额，scoped 读取不隐去合法未知工作。closeout 保留该未知身份与 Root 预登记未测事实；P1c-2a 同 loop 跨 digest 原稿恢复继续核验原 Run／accepted 分类，不加载旧 compiled。

P1c-2b 首评前定向证据：10 个 source 文件去重 107 项通过；原汇总保留为 `/tmp/scid-p1c2b-source-rollup-pre-review-20261002.json`。覆盖 10／30／100／300 容量、历史不解码／写保留、raw／缺 map 拒写、真实 24 主体超过旧 4 KiB、runtime 总字节回滚、native 查询计划／复用缺测及恢复收尾。选用证据所在 batch 监督 221.500 秒、RSS 峰值 178069504 字节，无超时／内存止损；混合失败 batch 仅计明确通过项，精确复测去重，不声明整文件全过。

首审修复：判断、Run 目录及原生回执共用确切任务名称的单条 accepted 准入核验，完整冻结目标与实际名称／Run 绑定一致才补入旧 loop 成员，不全量 hydrate。修前真实 UI 两 loop／MCP 首次判断在 r11 失败；修后 r13 的 5 个精确目标、6 项通过，含首次／修订、错误目标拒绝、预算／历史归属保留及相邻判断／目录／回执。修复证据 `/tmp/scid-p1c2b-review-fix-rollup-20261002.json`；监督 49.102 秒、RSS 峰值 169918464 字节，无超时／内存止损。3 项与首轮重叠不叠加，累计 11 文件去重 110 项，当前汇总 `/tmp/scid-p1c2b-source-rollup-20261002.json`；保留修前及 fixture 修正失败，源码独立复审通过，原 P1 阻断关闭。

300 场景是有限明细及准入夹具；完整套件、process/browser、模型、安装、TCAD 和长跑资格未取得。`max_loop_scopes` 仍有限，完整前台遥测、有限策略、P1d deadline／retry、P2 历史 memory／分页和 P3 rotation 留后续。既有 timer `7200 <= 7199` 风险未关闭，本轮未重跑／修改；源码净减少继续作为用户已列待办。

### P1d-1 自然期限与统一时间口径（独立复核通过）

2026-10-02，基线 `a59e5c5`：新增管理员配置 `max_calendar_seconds`，默认 3600，不扩大启用时长及任务默认授权。管理页明确确认自然寿命、启用时长和有效时间上限；控制用授权时钟冻结 `authorized_at`／`deadline_at`，所有准入、宿主截止、恢复、UI/status 和归档读取共同使用自然余额与启用余额较小值。schema 8 拒绝旧库／归档，无期限回填。

退出证据覆盖暂停、正常等待、服务离线、回拨、重启、目标／配置变化不续额，只有新 UI 授权取得新期限；自动时间止损保留确切已接受 Run 的首次附着、审查交付与已提交执行取消／收集。已知到期在 poll 前落库，关闭本地连接保留原 writer 未决；poll 内到期竞态仍保守记未知，显式用户暂停不自动复活。证据与失败历史见 `/tmp/scid-p1d1-source-rollup-20261002.json`；未运行完整套件、process/browser、安装、模型、TCAD 或长场，收集入口使用有界 coordinator 夹具，不代表实际下载资格。既有 debug timer 风险未关闭。有限故障分类／自动恢复由 P1d-2 承接；本源码节点已提交 `cc2affd`，未部署。

首评拒绝 3 个 P1：到期覆盖原停止权威、保留连接的 pending resume 仍先 poll、已有确切终态未沿生产收尾释放。修前真实 guard／tick 负例 7 项失败、未确认 writer 对照 1 项通过；修后统一原停止原因与纯时间事实核验，在全部 native 入口前处理到期，确切终态沿原收尾释放，其余 writer 保留。原 156 项证据保留；第一轮修复去重 91 项及失败位置见 `/tmp/scid-p1d1-review-fix-rollup-20261002.json`，复审关闭原 3 个阻断，不把混合失败 batch 写成整文件全绿。

复审追加暂停遥测 1 个 P1：确切 Root 终态后跳过 poll，已附着 Worker 的暂停／最终 usage 未消费。生产修复仅两行，恢复既有截止同步与一次有界非阻塞 poll，保持暂停与原 loop 归属；真实 AppServer／pipe／生产 tick 修前 2 项失败，修后与原边界精确重测共 17 项通过。证据 `/tmp/scid-p1d1-review2-fix-rollup-20261002.json` 单列，不与原 156／91 项重复累计；最终独立复核通过，原三项及追加 P1 全部关闭，原运行资格与 timer 限制不变。

### P1d-2 有限故障恢复（独立复审通过）

基线 `cc2affd`。恢复只接已有 Coordinator／control 事务，不增循环引擎、数据库或原生通用错误分类框架。管理员配置随管理页完整预算确认冻结：`max_recoveries=8`、`recovery_failure_threshold=3`、`recovery_backoff_seconds=1`、`recovery_backoff_max_seconds=60`；`recover_failed_turns=false`，确认失败的 Root 自动恢复默认关闭。原 `max_attempts=2` 仍限制原生 host／回合恢复累计尝试；原生自动恢复同时受两个累计上限与连续失败阈值约束，8 次恢复配置不扩大原 2 次限制。科学刹车、disabled、用户停止和各总预算仍先行。

| 实际调用边界 | 本节点行为 |
|---|---|
| `_observation` 内本地 SQL BUSY/LOCKED（明确错误码）或 maintenance 拒绝／事务回滚 | 复用原单次调用短重试；耗尽后经 control 事务安排持久退避，次数用尽或连续失败到阈值则停止；其他 SQL 错误不归为瞬态 |
| 同一 native thread／当前 turn 的明确 `failed` 终态 | 仅冻结策略启用时，原子消费原 turn、计恢复与原生尝试，退避后重新形成受剩余 rounds／tokens／time 约束的 Root 决策；不重放旧提示、Worker 派发或 effect 提交 |
| 重连后精确原 turn 的确认 `interrupted` | 保留既有下一决策权限，纳入同一恢复额度及持久退避；普通暂停／未重连的 interruption 不获得自动恢复 |
| `thread/start`／`thread/resume` 创建或恢复窗口、`turn/start` 超时／断连、writer poll 失联、原生回调内存储失联、外部提交未知 | 保留未知及原绑定，先核对；无自动重发。factory 在开始 native open 后的失败显式保留未知，客户端关闭不证明未提交 |

当前 loop 的原 checkpoint 保存累计 `used`、分类累计 `by_kind`、连续失败、`next_at`、待恢复类型与最近失败来源；退休 loop 授权余额保存这些计数／来源。仅新 UI loop 授权初始化，新目标、人工继续及重启均不退款。健康观察／确切自然完成只清连续计数，累计不清；exact 当前 turn、消费边界及事件身份防止重复／迟到扣费。安排恢复时核同 generation／loop，DB 不可写时只保留待落库故障，不能宣称已扣额或安排；用户 pause 抢先后不自动复活。schema 9 明确拒绝旧控制库／归档，避免旧冻结配置隐式获得恢复策略。

定向证据：11 个 source 文件去重 275 项通过，4 项按 lane 排除；恢复文件 28 项加新增首次 activation 后 BUSY 1 项精测，控制文件 22 项通过加旧 schema 断言修正后的 1 项精测，不将中间失败 batch 写成整文件全绿。选用证据监督合计 201.908 秒，RSS 峰值 158892032 字节，无超时／内存止损；命令、日志、版本及中间失败根因在 `/tmp/scid-p1d2-source-rollup-20261002.json`。真实 Coordinator/MCP/UI、AppServer pipe 的失败／迟到／foreign 终态组合、accepted dispatch 不增、已提交 effect 的 adapter 提交仍一次；原 P1d-1 时间入口、终态释放及暂停 Worker 遥测负例继续保留。未运行完整套件、process/browser、模型、安装、TCAD 或长场；native 只读连接恢复缺少可靠生产边界，本节点不授予该能力。既有 debug timer 风险仍未关闭。

首评拒绝 1 个 P1：终态释放后的全局选择故障被旧 host 缓存错误归属，DB 恢复后仍卡在旧 pending fault。修前 BUSY／LOCKED 两负例均失败；修后未选 subject 的读取故障不写旧 loop、不沿旧 deadline，成功 release 清缓存，unknown close 保原 writer。追加 13 source 项通过（2 新负例、11 原边界复测），22.957 秒／RSS 135794688 B，证据 `/tmp/scid-p1d2-review-fix-rollup-20261002.json` 单列；原 275 项及失败历史保留，不重复累计，原 reviewer 独立复审通过。

- **P1c 计账与容量**：在现有控制库中建立 loop 身份和关联，使用已有任务/用量明细及增量计数，不增加独立数据库或一套科研许可状态机。任务、回合、token、恢复次数归 loop；实例执行池仍为外层约束。后台、交互、人工继续、重启、归档恢复及 RunService 准入使用同一规则；剩余额度、停止原因在 UI/简报中一致。
- **科研任务与审查分别计数**：保留研究任务额度，增加可配置的独立审查额度；精确审查依赖及通过普通入口发起的合格独立审查使用同一分类。分类由控制层依据冻结合同和精确主体生成，名称含 review、Root 自报类型或 helper 不能取得豁免。研究修订/重新实验仍计研究任务。审查的 token、模型回合、运行时间及执行消耗计入 loop 总预算，独立额度用尽时明确报告“审查额度耗尽”，不挪用研究名额，也不自动扩额。
- 审查与研究准入使用同一原子预留/幂等/结算规则，失败或未知提交不能靠重命名退款；总预算停止时两类均停止新增派发。自动科学暂停仅阻止新的研究与独立执行；已接受任务冻结的精确审查依赖、原 Worker 附着及执行收尾沿同一调度权限判定继续，仍计原预算。原宿主可完成该依赖的派发和终态通知，用户主动暂停、禁用客户端及未知提交仍阻断；不添加专门解锁生命周期。科研进展按被审研究成果计一次；同一成果的审查不重复增加探索次数，也不能仅靠审查成功清零，合格判断可更新该成果的证据状态。
- P1c 负例覆盖：研究额度耗尽而独立审查额度/总预算尚足时可审已封存对象；审查额度耗尽不占用剩余研究额度；伪装审查、重复提交、并发创建 loop、Root 直接请求新 loop 或修改策略均不得获得额外预算。
- 放开 max_tasks/max_rounds 的旧小规模上限，使配置可表达 300 个任务及其所需回合；容量范围与真实授权值分开。先验证有界用量归属和持久明细，再删除 64 身份组合限制，以分页、聚合和完整性检查承接原责任。任务数保留为辅助硬上限，不再承担存储容量保护。
- 普通无变化轮询不消耗研究任务、模型回合或恢复次数；max_probes 从研究寿命限制退役或明确改为诊断指标。轮询频率、退避及无变化不唤醒继续受控，服务故障有独立有界恢复策略，不能变成无限忙等。
- **P1d 时间口径**：分别冻结自然截止时间、推进启用时长、外部作业执行额度。自然截止时间经过人工暂停和服务停机仍继续；推进启用时长按控制层 active 区间累计，包含正常等待外部作业的时间，排除明确人工暂停，不等于 Root 模型计算时间。这样“实际运行时间”有可执行定义，不凭 Agent 声称在等待减免额度。Root/Worker 实际活动时长另作遥测；每个 TCAD 作业的运行时限独立，研究 loop 一周不意味着单作业可跑一周。
- 时间口径在后台检查、人工继续、连接截止时间、UI 及归档恢复中一起替换。持久化区间边界与累积值；重启/时钟回拨不能退款。失联期间的活动区间保守保留为待核对或继续计入，不能凭进程重启把它认作零成本。P1a 先冻结等待、暂停、服务离线和未决外部作业的处理表。
- 故障恢复分开处理：安全的只读/连接瞬时故障按配置退避；已确认失败的原生回合按明确策略有限恢复；未知原生/外部提交先核对结果，不自动重发。连续故障阈值和 loop 累计恢复预算分开，确认健康可清连续计数但不退还累计次数；认证失效和需要用户决定的故障明确暂停。
- Token 分别呈现总输入、缓存输入、非缓存输入、输出与各角色归属，费用仅在明确价格和计量覆盖时估算。closeout 预留、迟到 usage、跨线程高水位和缺测均纳入同一 loop；遥测滞后时停止新增工作并报告不确定性，不声称精确账单硬封顶。历史每任务 20–30 万 token 的假设不作为 300 任务预算依据。
- 所有额度、时间、恢复与轮换阈值进入现有 config 并随 loop 冻结，普通 UI 展示本 loop 的额度/余量与预计停止原因；Agent 不填写机械账本。新身份/时间语义若要求破坏性状态升级，按现有格式防护显式拒绝旧状态，不默默重置。

## 共同事实、三个用途

唯一来源仍是冻结目标、完整任务、封存结果、失败事实、引用及既有消费记录。通知、历史目录与刹车共享这些来源，各自只持有必要投影：

| 用途 | 所回答的问题 | 约束 |
|---|---|---|
| 事件通知 | 有什么新内容值得启动一轮 Root？ | 相同遗漏不是新事件；已通知不等于已消费 |
| Loop 分层记忆 | 早期尝试过什么，哪些经验仍适用？ | 摘要用于导航和上下文，不授予证据资格、执行权限或进展清零 |
| 探索刹车 | 是否还允许沿当前方向继续投入？ | 调度控制是唯一暂停/恢复/准入权威；提示投递不是阻止新任务的前提 |

保留原生 host/turn、未知提交核对、预算、幂等、独立取消和终态消费去重。退役科研专用 episode 七态、一次调整任务许可、human_handoff 许可生命周期及仅为绕过它们而存在的人工豁免。普通投递、结果回读和人工接管仍由既有控制流程承担。全程不新增循环引擎、独立数据库、固定科研 DAG 或 Agent 机械填表。

## P0：先消除省略结果导致的重复唤醒

- 将“同一结果及其读取入口已经通知”与“科学终态已经交付/消费”分开，使用精确结果版本和既有原生投递证据，不因一次查询或提交前准备就声称通知成功。
- 通知成功后，相同且仍放不下的结果不再单独触发下一轮；待读引用和遗漏数量持续保留。新的任务结果、用户消息、有效控制变化、明确继续或下一批确有可交付的新内容才允许唤醒；正常分页推进不能被一把通知水位遮蔽。
- 只有摘要/读取指引被发送时，不推进科学消费或进展计数。code-mode 未提供可观测回执时如实保留未确认，不解析任意工具文本，也不靠反复开模型轮次弥补观察缺口。
- 不引入“连续省略 N 次”的新生命周期。提交结果未知仍沿原恢复协议，不因通知去重而重放或丢弃；停机重启后保留准确通知位置。

## P1a：P4a 行为与计数基线

本节为 P4a 冻结规则；本轮源码与定向验证已通过独立复核，实现范围和限制见下方“P4a 实现事实”。P4a 只收敛控制流程，保留 `reduce_shadow` 的现有 no_progress、coverage_gap、unchanged_evidence、repeated_failure 信号、阈值及 refinement 提示；其科学识别限制继续保留。更强判据及“新字节加 Root advance 不能清零”的实现属于 P4b，不以改名或删除既有信号代替。off/shadow/assist 与默认 shadow 保留，assist 达现有强制条件直接暂停，无一次专门复判或调整任务许可。

### 暂停、恢复与准入真相表

调度权威仍为 `SchedulingControl` 及其同库控制事务。科研触发冻结在既有进展事实/触发记录中；当前观察窗口只保存已消费序号的起点。科学暂停原因必须跨普通命令、模式/目标修订和重启保留，不能只靠可被 report 覆盖的显示 reason。所有创建/派发入口读取同一规则，界面、Root 自报和通知回执均不能成为第二套解锁权威。

| 已确认情况或动作 | 新任务准入与控制结果 | 保留的事实与责任 |
|---|---|---|
| 正常活动或等待已接受任务/外部作业 | 在既有权限、预算和串行规则内准入；等待本身不增也不清观察计数 | Run/执行服务继续拥有已接受工作；精确审查依赖沿既有合同处理，P4a 不新增审查免额 |
| assist 科学触发达到阈值 | 统一调度入口立即暂停新派发，不以提示发送、已读或专门复判成功为前提 | 冻结原因、消费序号及证据；材料读取和说明不授予新任务权限，已接受工作不被连带取消 |
| 普通 MCP `start`/`resume`/`takeover`，包括切换模式/目标 | 只能处理普通调度状态/所有者；存在未解除科学暂停时仍拒绝新准入 | 不改观察起点、旧触发、预算或实际工作归属；旧人工确认也不能被命令重用 |
| UI 对当前科学暂停明确“继续” | 核对实例、目标、当前触发及消费水位后，在同一事务记录决定，从该消费序号开始下一观察窗口 | 复用 capability、CSRF、精确确认绑定及控制 generation；旧判断/触发/投递历史不改，所有额度不退款。后续窗口照常强制刹车，不设免检 flag 或许可生命周期 |
| 已接受材料后来提供符合当前冻结规则的恢复事实 | 只有既有已接受结果的真实消费/判断可经同一入口解除对应科学暂停；其他暂停仍成立 | P4a 沿现有信号的恢复条件，不另派解锁任务；迟到修正、摘要、通知或自报方向变化不单独刷新窗口 |
| 用户暂停/停止，或预算/资源止损 | 停止新调度；普通恢复仅在未决原生状态核清且原额度仍足时有效 | 科学暂停不随用户恢复消失；读原件、收束及已接受作业的原权限保留，取消仍为独立动作 |
| 原生提交未知、活动 writer 或未决 admission | 先按既有原生协议核对，不重发、不跳过；UI 继续和另起人工范围均不能清掉未决事实 | `host_json`、phase/turn ID、故障事实、admission 与 dispatch generation 保留；客户端退出不证明原生终止 |

这里的“科学暂停解除”只解除它自己的原因，不能解开时间、token、资源、人工停止或未决提交。只读查询不消费科学结果；暂停中的说明沿既有实例/作者授权记录，不能通过放宽调度 guard 获得创建/派发权限。显示报告不能覆盖持久控制原因。

时间规则沿用前文 P1d 的目标定义；P4a 不先改计量：

| 情况 | P0 后现状 | P1d 承接 |
|---|---|---|
| 活动计算、正常等待外部工作 | `started_at` 墙钟继续累计 | 自然截止及推进启用时长都继续；外部作业独立计时 |
| 明确人工暂停/停止 | 原墙钟仍继续，UI 继续不退款 | 自然截止继续，明确暂停区间不计推进启用时长 |
| 服务离线/失联或提交未知 | 不重置 `started_at`、usage 高水位或提交归属 | 自然截止继续；活动区间保守保留为继续计入或待核对，不推定为免费暂停 |

### 退役清单与责任承接

| P4a 删除的职责/消费者 | 既有责任承接及最小保留 |
|---|---|
| `scientific_progress.assist_transition` 的 prepared、submitted_unknown、delivered、awaiting_result、exhausted、resolved、withdrawn 七态；一次复判/一次调整任务计数、候选版本和 `adjusted_task` 许可 | 现有事实 reducer/触发快照提供原因，`SchedulingControl._pause_progress`、准入与 UI 明确继续控制暂停/观察水位；不将七态搬进新函数或新文件 |
| `refresh_shadow` 的 episode 解决逻辑、`assist_view` 的许可投影，以及 Coordinator `progress_notice` prepare/submit/confirm 许可接线 | 保留消费事实、不可变触发/处置历史与有界原件导航；当前暂停由同一控制投影展示。P0 `notification_snapshot`/`notified_snapshot` 与科学消费水位不退役 |
| `prepare_human_handoff`、`human_handoff` 的 consumption-only/提交/投递/完成/失败许可生命周期及专用 INSTRUCTION | `goal_bound_runs`、admissions、`terminal_delivery`、`progression_status.closeout` 和原件读取继续承担结果交回；普通通知使用 P0。当前目标成员识别、遗漏数和 `run_list` 精确续页保留为只读导航，不依赖 handoff 许可 |
| `human_continuation_active` 在 episode 准入中的免检分支；人工确认中的 `episode_id`/`reassessments` 解锁绑定 | 保留真实 UI 确认边界、预算检查及决定审计，改为观察起点记录；后续准入始终使用同一暂停规则 |
| `independent_interactive_active` 仅用于绕过 episode 的分支，以及 handoff 状态的人工 deferred 操作 | 旧独立人工预算归属与身份绑定必须保留到 P1c 替换，见下表；不得把记账用途当死代码删除，也不得凭普通命令创建该范围 |
| `progress_reassessment_limit`、`progress_pause_on_persistent_gap` 及对应 Root 描述/UI 文案和专用测试 | 用既有 progress_mode 决定 off/shadow/assist；assist 的阈值刹车直接生效，不增加一个绕过强制停止的替代开关。阈值、读取预算和科学作者字段保留 |
| 旧 episode/handoff 数据的运行时许可解释 | 原纪实与归档内容保留为历史；旧快照标签可只用于兼容读取，不参与准入。不能删除字段后把未决提交认成已解决；不兼容状态按既有格式/版本防护显式拒绝，不默默清空或重置 |

保留 `observe_deliveries`、`terminal_fact`/`delivery_coverage`、不可变 assessments、`require_resolved_control` 的原生/未决 admission 检查、调度锁/generation、原生恢复和所有预算/消费高水位。科研 episode 的 submitted_unknown 可以退役，原生提交未知保护不能退役。

### P1c 前的人工范围与授权边界

| 既有范围/入口 | P4a 过渡规则 | P1c 才实施的替换 |
|---|---|---|
| 同目标 UI 人工继续 | 使用同一原预算；保留 `human_continuations` 的决定审计与精确 UI 绑定，退役 episode 豁免，继续只开启下一观察窗口 | 决定、任务与 usage 显式归属已有 loop；不新建 loop、不续额 |
| UI 明确授权的独立人工工作 | 保留 `interactive_sessions`、admission 的 `interactive_session_id`、对应 usage 归属/高水位和 `background_task_count` 的旧分账语义；这是现有独立作用域，不能改称旧后台范围的恢复或退款。原范围的科学暂停/旧触发仍保留，返回原范围不能自动清掉 | loop 分类和明确新 loop 授权实现后替换旧分账；历史独立人工记录不追溯混入旧 loop |
| 普通交互、后台 start/resume/takeover | 不能伪造上述 UI 记录、复用过期 generation 或借目标改名领取额度；同范围交互/后台使用同一科学暂停判断 | 人工进入已有 loop 时统一计账与准入 |
| 管理 UI/事先授权有限策略创建新 loop | P4a 不增加此能力，也不把独立人工入口当作已授权新 loop；当前 UI 独立工作用途和实例执行池约束保留 | 按前文规则冻结范围、总预算池/次数/期限并原子预留；普通 Root 无创建/扩额权限 |

当前独立人工范围尚未具备 P1c 的统一 loop 任务/token/时间硬额度，不能据旧 UI 分账声称已满足该能力。P4a 删除其记账字段会丢失历史归属，直接并入后台额度会改变已授权用途；因此仅保留上述最小身份、预算归属和 UI 授权职责，不保留科研许可例外。独立人工工作的授权不解除原作用域的科学暂停，不隐式授权新后台工作。

独立人工工作只保留 UI 授权、`interactive_session_id` 任务及用量归属，不维护科学观察窗口或触发；其成功与失败记录保留为历史，均排除后台科学计数。后台按目标保留单一消费水位和不可变触发。有效人工授权允许该人工工作，但不会解除后台触发；普通 start/resume/takeover 仍检查后台暂停，恢复由 UI 对精确目标确认。人工前台尚无可靠消费回执，不宣称人工工作的自动观察或刹车。以上归属不提供 P1c 的新 loop/API/预算授权。

本轮修复后的完整责任范围扩至 22 文件：在原 19 文件基础上加入 `artifact_agent/interfaces/mcp_gateway.py`、`artifact_agent/interfaces/mcp_root_execution_routes.py` 和 `platforms/codex_progression.py`（统一位于 `src/scidiscovery/` 下）。相对各文件的同一 P0 基线，物理行 13443→13628（+185）、非空非注释行 12325→12514（+189）；结构净减少门槛仍未达到。不得以人工观察节点净减 34 行代替完整范围核算。

### P4a 生产代码计数范围

基线为 2026-10-01 P0 独立评审通过后的 `dev` 工作树：HEAD `de3a63cbcfe36ca796efea6dbf5adf48fba5e25c` 加 P0 的两文件生产差异（`progression.py` +14/-2、`progression_records.py` +2/-1），未部署。下表为仓库相对路径，统一加 `src/scidiscovery/`；按整文件计数，列出的符号界定责任入口，不以裁剪函数片段降低分母。

| 文件 | P4a 责任入口/保留边界 | 物理行 | 非空非注释行 |
|---|---|---:|---:|
| `agent_execution_settings.py` | `ProgressionSettings`、冻结配置/退休字段消费者 | 305 | 248 |
| `artifact_agent/schema/scientific_progress.py` | `ScientificIntent`、`ProgressAssessment`：保留科学作者字段 | 21 | 16 |
| `artifact_agent/service/scientific_progress.py` | 事实/消费、`reduce_shadow`、`refresh_shadow`、`assist_transition`/`assist_view`、两种人工范围判断 | 699 | 626 |
| `artifact_agent/service/scheduling_control.py` | 控制命令/guard、准入、暂停/UI 继续、handoff、dispatch/host/observe 及状态投影 | 883 | 810 |
| `artifact_agent/service/progression.py` | INSTRUCTION、事件/回执、brief/tick、预算及原生恢复 | 825 | 736 |
| `artifact_agent/service/progression_records.py` | `COLLECTIONS`/`SNAPSHOTS`、同事务 hydrate/store | 104 | 94 |
| `artifact_agent/service/progression_budget.py` | `token_budget`/`require_task_budget`：不退款/closeout reserve | 34 | 29 |
| `artifact_agent/service/progression_read.py` | `progression_read_view`/`external_work_view`：待读结果与活动作业 | 143 | 136 |
| `artifact_agent/service/run_admission.py` | `RunAdmissionMixin.validate_admission`：预检/创建同一判断、审查依赖 | 142 | 132 |
| `artifact_agent/service/runs.py` | `RunService.schedule` 实际准入事务及既有 Run/恢复责任 | 2229 | 2096 |
| `artifact_agent/interfaces/mcp_root.py` | progression DTO/`RootTool.input_model`/`ROOT_TOOLS`、facade/router 的 mutation guard | 756 | 636 |
| `artifact_agent/interfaces/mcp_root_operation_routes.py` | preflight/invoke、`_prepare_local_run`/`_invoke_local_run` 实际创建链 | 1519 | 1445 |
| `artifact_agent/interfaces/mcp_root_run_routes.py` | `run_list` 成员/续页、`run_status`、受控 mutation | 180 | 160 |
| `artifact_agent/approval_ui/app.py` | `ApprovalUI._handle_home`/`_handle_instance_post`：capability/CSRF/确认绑定后调用服务 | 1676 | 1592 |
| `artifact_agent/approval_ui/home_render.py` | `session_controls` 的真实 human_continue/independent_interactive 表单 | 179 | 162 |
| `artifact_agent/approval_ui/progression_render.py` | 控制原因、人工范围及进展投影的显示消费者 | 151 | 146 |
| `artifact_agent/service/scheduler_bindings.py` | `SchedulerBindingService` 控制存储/初始化与格式版本拒绝 | 1281 | 1171 |
| `artifact_agent/service/instance_archive_records.py` | 控制表/明细与归档版本兼容：不丢未决、预算或历史 | 896 | 783 |
| **合计（18 文件）** | **P0 后冻结基线** | **12023** | **11018** |

计数口径：物理行用 UTF-8 源码 `splitlines()` 的长度；非空非注释行先用 Python `tokenize` 仅移除 COMMENT token，再计剩余非空物理行。docstring、SQL、提示及其他字符串属于生产源码，继续计入；不能因含 `#` 的字符串误删正文。排除测试、文档、fixture、生成文件。表序组成清单，逐项记录 `path`（完整仓库相对路径）、`physical`、`nonempty_noncomment`、`sha256`（原文件字节）；以 `json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()` 的 SHA256 绑定：`af6fd8936f0270a5fedf500d84ef873d203512159d869f932ac5394d415348da`。P0 两文件字节 SHA256 分别为 `bc0854c6a0eaf22a4444e120d1d8cadf625c1b8019f8ef8465848a7fc8bdd791`、`132b5fc55281019cf7070c2ebe9e03d0cdb93aa8cf933156bd11ed2eeb8cee1a`，其余文件取上述 HEAD。

P4a 验收同时报告两种口径的新增、删除、净变化。用户在 `47961d8` 后明确将净减少转为后续待办，保留原基线与未达目标的事实，不再作为本节点或 main 合并的阻断条件。移出/拆分/改名后的实现仍计入同一责任范围；新增承接文件基线为零，已有范围外文件承接职责时补入其上述 HEAD 基线及最终文件，不能只报原文件变短。旧路径与新路径一起对账；不得靠搬家、压行、删注释或删除无关生产能力达标。结构退出条件仍要求七态/专用 handoff 许可真正退役、唯一控制权与安全负例通过；行为或权限不满足时继续阻断后续开发。

### P4a 必要负例与退出证据

仅围绕下列实际入口选最小反例，不展开所有字段/模式的全组合；P1a 本次不执行测试。

| 场景 | 必须保持的可观察结果 |
|---|---|
| 科学暂停后分别走交互/后台普通 MCP 命令，改模式/目标，再走 preflight/invoke/RunService 实际创建 | 不解科学暂停、不刷新窗口/额度、不创建任务；预检与提交理由一致 |
| UI 明确继续、重复/过期确认、第二观察窗口再次达阈值 | 当前绑定的有效决定开新窗口；旧触发/投递和额度不改；过期/重复确认不再次开窗，下一窗口仍强制停 |
| 原生提交未知、活动 writer、prepared admission，以及早/晚/错误 thread/turn/generation 事件 | 不解锁、不重放、不退款、不猜终态；精确已确认终态按既有恢复边界结算一次 |
| 科学/人工/预算暂停时仍有已接受 Worker、审查或外部执行 | 保留实际接受身份和既有执行/读取/取消权限；新增任务仍受统一准入，任务终态不冒充外部作业终态 |
| P0 旧通知、摘要、全遗漏、正常下一批与真实原生读取回执 | 已通知不等于消费/进展或许可；同遗漏不误醒，下一批可展示仍交付，确切回执只消费对应材料一次 |
| UI 独立人工范围、返回原范围、预算耗尽/迟到 usage、旧状态/归档恢复 | 保留旧分账/暂停原因/高水位；普通命令不能伪造独立范围；继续不增额度；兼容读取不恢复旧许可或吞掉未决状态 |
| off/shadow/assist 的原有信号 | off/shadow 不变成强制准入刹车；assist 自动强制停；不以移除弱信号或声称已科学验证达标 |

### P4a 实现事实（功能与结构收口，净减少列为待办，未部署）

| 已实现边界 | 实际承接与限制 |
|---|---|
| 直接暂停与统一准入 | 删除七态 episode、一次复判/调整任务许可和专用 handoff 生命周期；既有触发/处置记录由 `scientific_pause` 共用读取，SchedulingControl 与 RunService 实际创建均拒绝未解除的科学暂停。普通命令、改目标/模式、报告完成及重启不清原因 |
| UI 后续观察窗口 | 既有 capability/CSRF、精确实例/目标/generation/控制快照确认在同事务开启对应已消费水位后的窗口；原触发/投递不回写，原额度不退。真实后台 Coordinator 的第二个三结果窗口再次暂停，不新增免检许可 |
| 独立人工返回后台 | 管理页从未解除的后台触发和不可变交付引用列出精确目标；复用人工确认，绑定目标、后台范围、触发与消费水位。有效确认只开启所选后台窗口，恢复原后台预算，保留人工记录和其他目标的暂停；原件或名称绑定缺失时展示诊断，未知提交、活动工作及预算耗尽继续阻断。后台范围内仍可逐个确认其他未解除目标，不批量解除；当前暂停/独立人工期间仍计入时间额度，UI 和耗尽拒绝明确说明，活动工作拒绝列出首个工作类型和实例绑定名称（无绑定时才显示标识）；页面明确人工继续转交互模式，后台继续切换到所选目标，最后确认的目标成为当前目标 |
| 原件与分页 | P0 通知确认/消费分离保留；`run_list.current_goal_tasks` 从精确目标绑定派生只读成员，沿既有 `next_before` 精确续页；不解释 handoff 许可 |
| 旧状态/归档 | 现有 `CONTROL_VERSION` 从 2 升至 3。启动的 `SchedulerBindingService._initialize` 检查 SQLite `PRAGMA user_version`；恢复的 `execution_settings_restore_view` 检查归档 `schema.user_version`。旧 2 均明确拒绝，未配置退休字段但存有旧 submitted_unknown episode/handoff 也不能静默采用新规则；不提供迁移或清空未知提交 |
| 消费与自动恢复 | 保留实际原生 turn/投递/消费归属与当前 reducer 恢复判据。暂停态没有可靠后续消费时保守保持暂停，不另开解锁回合；原因后来真正解除仍不自动解开其他暂停。前台 code-mode/独立交互未接入可靠原生回执时不计消费，不能保证其新科学阈值触发；范围事实夹具只证明存储/投影隔离，后台再次刹车以真实 Coordinator 验证 |
| 原生与预算 | 原生 outcome_unknown、活动 writer、prepared admission、精确 turn/thread/generation、旧人工任务/usage 分账和所有原额度仍保留。poll 回调及终态结算后复读控制状态，已确认暂停沿既有宿主清理，不误报 host_fault 或遗留 writer；活动/未知宿主仍保留。turn/start 返回前的实际早到 MCP 准入不冒充消费或已知提交失败；明确 outcome_unknown 则拒绝重放。独立审查依赖的完整提示保留 |

`67bcd4d` 节点的冻结 18 文件均保留在计数范围，该节点没有新增或移出承接生产文件。下表保留该节点历史计数；`8b299c6` 恢复入口将 `runtime.py` 也纳入责任范围，共 19 文件：相对扩展后的 P0 基线，该节点物理行 12225→12214（−11），非空非注释行 11203→11204（+1）。`fbe291c` 多目标恢复及诊断补丁节点为物理行 12224（−1）、非空非注释行 11214（+11）；双口径净减少仍待收口。逐文件按本节基线与最终源码对账，新增/删除使用 `difflib.SequenceMatcher(autojunk=False)` 的 insert/delete/replace 数量；第二口径先移除 COMMENT 并过滤空行，docstring/SQL/提示仍计入。

| 口径 | P0 后基线 | P4a 最终 | 新增 | 删除 | 净变化 |
|---|---:|---:|---:|---:|---:|
| 物理行 | 12023 | 11914 | 240 | 349 | -109 |
| 非空非注释行 | 11018 | 10922 | 238 | 334 | -96 |

最终按同一 18 文件序列、同一四字段清单格式得到 SHA256 `e4f25244a5689e75a5766c509de3119627edd3fda790ef776a1de7f897485009`。未合入 main、未部署；P1c/P4b 等后续能力不由此次收敛代替。

## P2–P3：首版两层记忆与按需读取

首版只做有界总览和按时间排列的一句话尝试索引；原件继续使用现有读取入口。四层探索段目录、科学分支自动归类和递归摘要归并后置，P5 证明收益且实际导航困难后再决定。以 100–300 个完整任务、跨天和跨 Root 线程为设计容量；这一规模要求分页与长期经验可达，仍不直接要求多层探索树。历史默认 8 个后台任务及独立人工例外由 P1c 的显式预算作用域取代。

| 层级 | 内容 | 读取方式 |
|---|---|---|
| L0 loop 总览 | 当前目标、已有认识/未决矛盾、重要失败边界、最近少量尝试及索引入口 | Root 继续/恢复与 Worker 派发时提供有界版本 |
| L2 尝试索引 | 按时间排列，每个完整任务一句话，保留条件、改动、结果性质、限制和原件入口 | 在同一冻结历史范围内按页读，可追到原有封存结果和诊断 |

- 条目复用已有 Worker 交付和不可变判断，终态变化时增量更新；工程失败只概括已确认事实，不推断机制被否定。缺失、冲突、适用条件、后续推翻和原件引用均保留，一句话摘要不作为原件已消费或科学进展的证明。
- L0 优先使用有来源的现成结论和确定性摘录；首版不增加后台模型摘要任务。新的科学综合仍由普通科研任务承担，不让 Root 每轮整理目录。无法无损压缩时给保守说明和原件入口，不以字符截断掩盖限制。
- 启动内容只含有界总览、最近记录及按当前绑定来源/修订谱系找到的少量旧记录。无可靠关联时给时间索引，不声称找到全部相关经验；不把所有历史各压一句灌入上下文。
- Root/Worker 复用现有读取能力；控制层冻结本任务可读的历史范围并生成语义导航，完整合同说明新读取能力。Agent 不填写目录、内部键、版本或游标绑定。跨实例隔离、修订来源、冷启动/归档恢复和历史原件可达性保留。
- P2 只处理本路径实际需要的热点：状态读取不物化不相关历史集合，尝试索引在 SQL/原件层分页；避免为了展示索引重写全部历史。保留权威预算账本，不建设全仓通用查询框架。首版以 30、100、300 个任务夹具验证分页、跨页找回和增量写入，并覆盖每任务多次执行、helper 与 Root 轮换带来的额外明细；比较读取行数、启动字节与峰值内存，不能只测物理 checkpoint 大小。万条研究任务/递归目录不作为当前退出门。

P2-1 实现边界：既有 `run_list` 在 SQL 中按实例、绑定时间／名称、状态和语义游标选页，再读取本页完整 Run；默认摘要的诊断计数与最近记录在 SQL 内聚合／限量。恢复资格仍沿原有精确读取路径，不能把附加读取计成零；稀疏状态的 SQL 扫描、当前 loop 控制投影和审批计时账本没有取得恒定读取资格。该节点不提供冻结历史索引或 L0/L2 记忆，状态与证据仅由主计划节点表维护。

历史分页沿用 `run_list(view="history")`，旧任务从 `run_status(intent="navigation")` 返回确切入口。同一目标的尝试可跨 loop 查阅；首次读取冻结终态上界，后续页不混入新完成任务。控制层在不落库的加密游标中保存完整绑定，Agent 只沿返回入口读取。更换本地密钥后须重新打开导航；归档保留历史和原件，不承诺跨密钥沿用旧游标。摘要或导航均不授予预算、审查资格或原件消费证明。

状态交接将全范围机械核对与详情展示分开：同一只读快照核对已接受任务的身份、终态和用量缺口，只加载有界详情；页面外活动／缺失记录仍影响汇总结论，省略项保留读取入口。当前授权 scope 的预算仍从完整权威账本核对，不把分页展示作为预算输入。明细写入批量校验 loop 身份，仅更新发生变化的记录；未读历史、原子回滚及迟到用量归属保持不变。

Worker 的 `worker_read_history` 只读取本任务冻结的索引；具备 `reference.read` 的 Operation 通过既有 `worker_reference_read` 预算和来源回执读取确切历史原件。未声明该能力的插件明确显示原件读取不可用，不暗中扩大权限；索引不提供 Root 专用假入口，也不成为可引用证据。首次受控打开任务在 Run 元数据中冻结终态与判断上界，重开沿用，不改写已冻结执行策略。旧任务的 `original_name` 只作导航，实际读取才返回当前引用别名；同名不能代替同一原件。可选记忆缺损明确标未知，不阻塞身份、输入及预算有效的已接受任务；所有机械身份由控制层保存。 首版 Worker 对工程失败只提供已确认的类别和旧输入，完整诊断仍由 Root 使用既有诊断入口读取；这不等于 Worker 已找回失败原因。历史任务提供读取授权，原件生产者及配对证明仍按实际来源解析，不能把消费原件的任务当作生产者。

R3 追加修复（源码、末版 35 项定向验证及独立增量复审通过，未部署；冻结 `/tmp/scid-r3-freeze-v2-20261003.json`）：独立审查合同使用共享的中性历史导航，不自动附加作者摘要、裁决、Root 判断或科学摘录；确切被审原件仍由原科学输入与原件读取能力提供。普通任务沿明确的 `supersedes_ref` 冻结有界目标祖先，须有同实例确切绑定；无修订关系时不按名字、类型或共同来源扩展。Root 与 Worker 共用该范围，既有冻结范围不追补祖先或新结果，旧目标判断保留其原目标归属。谱系超出既有游标容量时明确报告覆盖不足。

L0 从少量封存结果摘取已有认识和未决矛盾；明确的假设否定作为带来源、适用条件与限制的 Worker 科学负结果，工程失败和通用 blocked/revise 不替代科学否定，也不授予已核验进展资格。读取候选有界，不宣称找到全部重要失败。单条可选内容损坏局部标未知并保留健康条目；可选 Root 判断引用和历史输入 JSON 的启动／分页解析共用这一边界，不吞数据库或锁错误；范围授权或确切绑定损坏仍拒绝相关历史访问，严格原件来源、证明和预算规则不变。

## P3b：Root 安全轮换

实现沿现有 coordinator、可信原生工厂与调度 owner/generation 接线。`root_rotate_after_rounds` 默认 8 轮，`root_rotate_after_input_tokens` 默认 500000；各项设为 0 可关闭该触发，随 loop 冻结；累计输入用量包括缓存，不作为当前上下文长度。只在安全边界替换线程，旧 loop 未冻结轮换字段时保持原授权而不启用轮换；新完整配置的阈值变化仍须重新授权。

- 控制层按配置的回合数、上下文/用量信号在安全边界换新 Root 线程，默认仍使用 gpt-5.6-sol/high。不能依赖无限自动压缩保留早期经验，也不能每轮无条件换线程。
- 轮换时旧回合须终止且无未决提交；有活跃原生子任务时先核对平台归属/通知能力，未证明能安全接续则延后轮换，不猜线程身份或把旧 Worker 重派一遍。外部已接受求解作业继续由执行服务跟踪。
- 新线程收到冻结目标、L0 总览、最近少量尝试、历史索引入口、未读结果/活动工作及剩余额度；精确绑定由控制层恢复。不拷贝旧线程全文，也不把摘要当作消费回执或进展证明。
- loop 身份、任务/用量高水位、已通知与已消费位置全部继承，旧线程历史可追溯；轮换失败和新线程启动结果未知沿原生恢复协议处理，不允许两个 Root 同时调度。原生适配仅在已验证能力内实施，不预设跨线程子任务自动转移可用。
- 退出证据包含：新线程找回早期失败，旧线程停止写入，未消费结果不丢、不重复派发、无预算退款、跨线程 usage 不漏记。先模拟，再做小规模真实边界验证；真实成本计入另行明确的预算。

R2 追加修复（源码与 48 项定向验证完成，独立增量复审通过，未部署；冻结 `/tmp/scid-r2-freeze-v2-20261003.json`）：新 Root 的用户上下文投递按真实线程登记，首次简报重新提供当前目标已保存的指示；长原文沿既有状态索引／原文分页读取，后续同线程仍增量投递。消息保存沿既有每目标 16 条硬上限，超额明确拒绝；这不覆盖目标修订谱系。审批补读既有列表的待处理与近期决定并保留分页，文本和导航不授予审批。确认投递后才记线程已收到，结果消费位置不因上下文重送改变。

轮换的原生终态证明保存于既有用量明细，绑定真实 session、thread、Run、附着代次、宿主连接代次与原生事件版本；新连接不直接授信旧证明。当前连接已核验且有订阅依据的终态线程可复用缓存；未知身份依 loop 冻结的批量上限核查，订阅与读取 RPC 合计计入上限。只为本连接新绑定或仍活跃的确切参与者沿原恢复协议订阅，不启动 turn 或改权限；不批量恢复历史终态线程。冷启动的未订阅旧终态、不可读／可能活跃者明确延后轮换，这一场景尚无任意恢复后必能轮换的资格。空线程仅在从未打开且所属任务已关闭时可结算；最终接管在调度锁内按当前全部确切绑定复核终态证明，通知失效后不得继续撤权。小简报仅在可完整保留结果或消息时降级可选观察摘要，预算、实际消费及遗漏语义不变。此修复尚无真实原生宿主资格，不承诺原生子任务跨线程转移。

## P4：强制刹车保留，科学控制流程变小

- 资源刹车与探索刹车分别保留。已消费完整任务是科研计数单位；等待不增也不清零，未展示/未确认材料不能算已消费。首次范围为 Root 跨完整任务的反复优化，Worker 单任务内循环仍受任务/调试预算约束。
- 增加配置化“连续未取得可核验进展”的探索窗口，覆盖沉默、unknown、改写意图及每轮新文件加自报 advance；局部优化与同类工程失败作为有依据的提前触发信号。历史记忆可以显示同条件旧尝试，语义近似只提供线索，不机械宣称已证明重复或科学失败。
- 明确两种能力：有可比较标准时按证据判定是否改善；无标准且无合格独立判断时，未核验窗口实质为“每 N 个完整任务后要求确认方向”，这是强制探索检查点，不宣传为科学停滞识别。unknown 不改写为 no_progress，两类触发及误停分别统计。未声明标准的任务仍可正常执行/交付，不强制补表。
- 指标的科学作者是负责实验设计的完整实验 Worker（用户已明确给出的判据可直接作为来源），Root 不填机械绑定。首版优先复用 ExperimentPortfolio.validation_plans 中 ValidationCheck 的 metric、evaluation_mode、threshold、acceptance_condition、basis；相对改善确有需要时，仅给该检查增加可选的 progress_comparison（基准材料的科学别名、比较方向、最小有效变化与适用条件），由对应 authoring form 完整提供。控制层解析确切引用并冻结版本。判据须先于待评价结果封存，后来改判据不能重判旧触发。ResearchObjectiveContract 的目标覆盖/存在性要求本身不等于数值改善标准，不能从这些字段猜出容差。普通/第三方任务未提供这一能力时使用上述确认检查点。
- 新字节、Root advance、目录归并、历史摘要或自报换方向不能清零。可比较指标必须事先冻结方向、容差与必要约束；有效负结果需要冻结检验依据或对确切结论的合格独立判断。没有标准时保留未知，不给普通任务强加数值字段/逐轮审查。
- 达阈值直接经统一调度入口暂停新派发，冻结原因与证据，保留已接受工作；不先运行一次专门复判，也不设置“只准一个调整任务”的第二套许可。Root 可以读取材料和写说明，不能用另一个入口绕过暂停。
- 人工明确继续可从当前消费序号开启下一观察窗口，保留旧判断和触发历史，不增加累计时间/token/任务/执行池额度。自动恢复只消费已存在且满足冻结规则的合格成果，沿同一入口执行；不为解锁再启动专用审查状态机。目标 revision、自报方向变化或重启不能自动刷新额度或观察窗口。
- off/shadow/assist 保留；效果资格取得前默认 shadow，assist 中刹车实际阻止准入。阈值、读取/摘要预算及容差进入现有配置；有价值的新科学字段必须在合同中明确，机械字段全部由控制层生成。删除固定一次复判等退休配置和专用测试。

P4b 首版实现范围：`unverified_progress_threshold` 默认 3，随 loop 冻结；未冻结该字段的旧授权不自动启用新策略。跨目标修订的实际消费沿同一实例探索窗口累计，新的资源 loop 不抹去科研触发；旧逐目标判断继续保留。新字节和 Root 自报判断均不清零，只有同科学检查／适用条件的首次可信解决才计进展，同规则重新封存或重复审查不成为新解决。

消费位置与交付分页位置分开：仅在真实确认边界生成首次消费位置；同任务跨目标重复交付先去重再应用读取上限，遗漏状态依据完整候选。待消费记录不占观察窗口位置，人工开窗后才消费的任务仍进入新窗口。当前状态格式为 v5：在 v4 的真实消费位置基础上，加入首次背景终态上界及不含阈值微调的首解家族语义。v4 及更旧状态、不具备同一格式标记的旧归档明确拒绝，不回填或推测旧消费顺序；新归档保留精确消费事实。

启动前已结束且未进入观察／接受集合的任务属于背景，依实例首启冻结的终态事件位置分类，不受 16 条展示上限影响；跨目标不能把已经观察的任务重新标为背景。背景证明只用于识别已知检查家族，省略或损坏时新颖性明确为未知，不伪造消费、不阻止已接受工作。核验仍使用确切先验阈值，但仅改变 cutoff 不取得新的家族首解；相同指标／执行配置／结构化实验条件下重复 pass 或 fail 均不清零。真正可比较的实验条件变化可构成不同家族，无指标的定性检查采用保守合并。

核验路径限定为两类：注册计算工具可通过既有公共 `CalculationResult.validation` 提供可选结构化投影，控制层核对精确读取来源、配对回执和 manifest、事前封存的检查及适用条件、有限数值和单位；首个具体适配是匹配事前曲线合同的受控计算。独立定性判断使用审查者可选的 `scientific_test`，仅对确切已完成 diagnosis 中事前唯一的定性检查生效，仍须验证原件与独立身份。整体质量 pass 不替代明确科学检验判断。未带这些能力的普通工具和第三方任务照常执行，进展保持未知。首版不实现相对改善、任意分数／语义漂移及恢复计算的核验投影，不增加未使用的 `progress_comparison` 字段。模型效果与长跑资格由 P5/P6 验证。

## 实施责任与收敛检查点

实施顺序、工作量、状态和各节点退出条件统一维护在[主计划 S3-R](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#s3-r长-loop-记忆可靠唤醒与强制刹车)。各节点串行执行并独立评审；独立评审可直接检查差异和最小退出证据，不要求另建一份过程文档。

P1a 冻结科研控制层生产文件/符号清单和计数口径；P4a 完成后在同一责任范围核算新增、删除及净变化，包括拆出、移入和重命名的实现，排除测试/文档/生成文件，不以代码搬家或压行制造缩减。退出要求是科研专用 episode/handoff 许可退役、暂停/恢复/准入权威唯一，原生未知提交与活动作业保护仍通过。净减少按用户决定作为后续工程待办；保持固定口径记录，不因数量目标删除必要保护。重复状态或行为保护未解决时，仍须先调整 P4a。该检查是开发节点验收，不增加科学任务 gate。

main 未获准合入时可完成 P0/P1a/P4a 与后续无模型夹具设计；共同执行语义稳定后再接入长程计账并冻结效果基线。

## P1b-prepare：基线准备边界

修复源码基线冻结为 `e07d6f080efbd56d3f01f0245c2d42deba602935`，控制 schema 9；本节点只适配现有 `accept_b6.py init/prepare/run/report` 与 `accept_progression.py` 前台及恢复场次，首审阻断及报告遗漏均修复，独立复审通过，已提交 `e625a04`。`baseline_digest` 继续绑定原 state/project 原件；`conditions_digest` 继续绑定程序、材料、题目与配置。`freeze_identity` 独立记录 candidate/state 源码 commit、runner commit/digest、实际 installed schema/config API 及 Codex 版本/执行文件哈希。rollback 单独冻结实际旧构建 head/installed contract 与所复制 managed state 的来源，旧 schema 在复制前拒绝，不继承新构建 head。新 runner 的提交不冒充旧源码基线，`c00706f`、S0 和已有失败原件保留；source 通过不表示真实基线、S0 或 S5a 退出。

新场次只使用独立 schema 9、尚无控制记录的 state；旧库拒绝，不迁移或清空旧余额。`prepare` 沿既有 `prepare-upgrade` 复制/生成配置路径，它不启动 daemon、native host 或模型。运行前冻结完整有效设置并用实际 installed interpreter 核对；Root 为 `gpt-5.6-sol/high`，Worker/helper 按冻结配置。人工选择/授额等待单列 900 秒；短场自然期限和启用时长各 1200 秒，研究/审查、Root 回合、tokens 及恢复字段均明确冻结。监督总时限包含启动、人工等待和执行；报告保留全程资源与用量证据，执行计费时间单列，不把人工等待扣入模型场次，也不把缺测换成零。

`run` 先通过实际 native thread/session 的公开 MCP `instance_current` 输出本候选的精确管理 URL。仅用户页面选择或创建配置中的确切实例；runner 绑定已冻结目标原文。随后用户在同一管理页明确执行两步：①暂停本次无模型 bootstrap 交互调度；②刷新页面，以打印的确切目标名明确确认完整 loop 预算。runner 不自动暂停；等待期间改绑实例或换所有者立即拒绝且不请求模型。runner 用既有公开 `progression_status` 核对 loop/目标/预算，完整有效配置只在 harness 内只读核验，不向 Agent 新增内部字段。确认后 `paused/loop_authorized` 合法，前台自动继续；自然 deadline 始终从原 `authorized_at` 起算，普通继续、恢复和换目标不续额。选择已有活动/未知实例拒绝且不摄入、不暂停；原一次性 attempt、共享锁、未知不重放和 stop 信号保留。`report` 只读；旧通用 probe `start/continue` 不作为新 P1b 资格入口。

隔离安装候选已准备并独立核验通过。后续在确认新的真实运行预算后，用 **源码来自上述 commit 的 schema 9 安装候选** 执行以下既有命令；本准备节点未执行这些场次命令，不挪用 S0/P5/P6 余额。命令中的 `python` 须来自已按 [README Development](../../README.md#development) 准备的 runner 开发环境（含测试依赖及相同冻结插件），从本仓库执行；它与候选 `candidate.json` 内核验 installed contract 的独立解释器各负其责，本节点不补装依赖：

```bash
python scripts/accept_b6.py init --suite /tmp/scid-p1b-baseline --config scripts/acceptance/scientific_progress.json --source /tmp/scid-p1b-e07-install --installed /tmp/scid-p1b-e07-install
python scripts/accept_b6.py prepare manual-stagnation-1 --suite /tmp/scid-p1b-baseline
python scripts/accept_b6.py run manual-stagnation-1 --suite /tmp/scid-p1b-baseline
python scripts/accept_b6.py report --suite /tmp/scid-p1b-baseline
```

`/tmp/scid-p1b-e07-install` 已从干净 `e07d6f0` 构建；准备 runner 为 `e625a04`。实际 installed core-only、控制 schema 9、实例/会话/任务/执行均为空，源码/安装字节和摘要经独立只读核验一致。Root 为 `gpt-5.6-sol/high`，Worker 沿本机配置为 `gpt-6-astra/high`，作为新的明确比较条件，不声称与旧 S0 相同。构建与空库初始化串行 5.226 秒、峰值 RSS 157908992 B，无资源止损；2 GB 地址空间限制与 1.5 GB 采样 RSS 止损生效，无进程树 cgroup 硬限。准备证据 `/tmp/scid-p1b-e07-prepare-evidence-20261002/rollup.json` 及 `freeze.json`；未调用 Codex/native/模型，未运行 suite init/prepare/run。候选准备核验通过，真实预算和模型场次仍待确认；执行时 runner 身份继续单独冻结。后续 P2/P3/P4b 候选复用同一材料/题目/预算/插件/平台与执行控制条件，变化须同步对照或逐项声明，不能将差异直接归因于记忆。源码准备退出条件已满足：UI/MCP 正负例、准备与监督/报告夹具及相关锁/未知/恢复回归通过，独立复审通过。首审发现的误暂停竞态、回滚身份与未启动报告遗漏均已修复；原 108 项、修复 18 项和报告修复 3 项证据分别保留，不重复累计。最终冻结与证据为 `/tmp/scid-p1b-entry-report-fix-freeze-20261002.json`、`/tmp/scid-p1b-entry-report-fix-rollup-20261002.json`；真实运行和用户评分继续保持待授权/待评。

### P1b 当前状态

最新场次的执行、核账和质量状态以[主计划 P1b 节点](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#s3-r长-loop-记忆可靠唤醒与强制刹车)为准。`ee7fd40` 场次已封存成果；`bf987f1` 修复验收读取后只读核账通过，原失败与全部原件保留，不重复运行本题。该结果不是完整基线、科研效果或发布资格；下述旧普通终端命令仅为历史交接记录，不再执行。

### P1b 单场授权与普通终端交接（历史记录，2026-10-02）

用户已授权仅 `auto-stagnation-1` 一场，并指定 Worker 改为 `gpt-6.1-sol`；实际冻结 Root `gpt-5.6-sol/high`、Worker `gpt-6.1-sol/high`、helper 默认继承。套件仅含本场，总/单场预算均为输入加输出 200 万 token、非缓存输入加输出 20 万、执行 1200 秒，人工等待另列 900 秒；去掉不存在的配对元信息，科学题目不变，不宣称人工/自主对比。原安装准备的 Astra 配置证据保留为历史，新配置与 actual installed readback 记录于 `/tmp/scid-p1b-one-case-prepare-evidence-20261002/freeze.json`；init/prepare 与独立核验通过，串行 3.650 秒、峰值 RSS 202194944 B。

本会话启动在环境检查被 `native_daemon_directory_blocked` 拦住，模型请求/派发为零，原 attempt/exit/startup-check 均保留在 `/tmp/scid-p1b-baseline`，未修改 Codex 权限或重放提交。此前 runner 导入路径缺失发生在 attempt 创建前，已修正为准备阶段相同的显式 PYTHONPATH。只读复核通过的普通终端入口为 `bash /tmp/scid-p1b-start.sh`：先核环境和已授权单场条件，再建立独立 `/tmp/scid-p1b-host`；已存在即拒绝重复运行，仍由用户页面选实例、暂停 bootstrap、确认原目标预算。交接记录为上述证据目录的 `launch-blocked.json`。这是同一场尚未发生的模型执行，未扩大额度；真实场次、token 结果和人工评分仍待完成。

后续 host2 在人工等待 900 秒后退出，已建 `b0a-calibration` 和 `acceptance.objective`，仍无模型提交、授额或已接受/未知工作。显式 `resume-wait --from-evidence` 仅允许这种已确认模型前超时；复用原实例及冻结题目字节，新原生会话沿既有 `thread/start`，旧空线程身份只保留为来源证据，不尝试恢复空 rollout。用户在新精确管理 URL 选择原实例，必要时明确接管，再暂停并确认原 loop 预算；脚本不代选、接管、暂停或授额。人工窗口是正整数配置，本轮显式 3600 秒，父/子监督同源，人工轮询沿冻结 `progression.poll_seconds=5`；原 case/host-resources 与科学 1200 秒、200 万/20 万 token 条件不改，授权后沿原 deadline，不续额。新关联记录保留原件 SHA、旧/新 harness 身份和重新核验的套件余额，报告仅读取该精确关联输出；失败清除活 URL，重复/未知/已启动工作拒绝。

原 16 项定向 source 验证及真实 host2 只读 eligibility/余额证据保留于 `/tmp/scid-p1b-wait-recovery-rollup-20261002.json`、`/tmp/scid-p1b-wait-recovery-freeze-20261002.json`。独立复审发现 status 读取后 UI 授额可与下一次本地读取交错；修复仅对已核验无工作/精确题目/配置/所有者的合法 managed 转换重新读公开状态并沿原 `confirm_loop`，不吞其他拒绝。修前失败保留，修后 12 项精测通过（含首次/循环 status 后真实 HTTP 授额、错误所有者/题目/配置/未知工作及既有正常路径），deadline 不重置；新证据 `/tmp/scid-p1b-wait-recovery-review-fix-rollup-20261002.json`、`/tmp/scid-p1b-wait-recovery-review-fix-freeze-20261002.json`，独立复审通过、原授额竞态阻断已关闭，随本节点提交；未启动 native/模型或执行接续。使用 README 开发环境解释器的既有 wrapper `bash /tmp/scid-p1b-resume-wait.sh`，准确参数为 `resume-wait auto-stagnation-1 --suite /tmp/scid-p1b-host2 --from-evidence /tmp/scid-p1b-host2/auto-stagnation-1/journey-1790919037924275143 --human-wait-seconds 3600`；这仍是原授权单场，P1b/S0/S5a 与用户评分均未完成。

真实接续场次后来已运行至 Worker completed、Root 一轮，随后以 `host_fault/OperationalError/configuration_or_runtime` 退出，恢复次数 0；原 SQL 消息/栈未保留。现场副本及已安装 e07 代码的锁竞争能确定复现 `_brief` 后纯读组合未纳入有限观察的缺陷，不能据此确认历史原查询。基线 `11bd34d` 上本次仅修复该 post-brief 组合，沿原有限锁重试/恢复预算，不重放整 tick 或 native 提交；故障 checkpoint 增存有界阶段、SQLite code/name 与可信模块函数/行号，不存异常全文、SQL、路径或 locals。8 项精确 source 验证通过（真实 SQLite 短/长锁、永久错误、安全诊断、原恢复额度及未知 native 不重试），11.552 秒／RSS 129146880 B；夹具失败原件单列保留。证据 `/tmp/scid-p1b-host-fault-source-rollup-20261002.json`、`/tmp/scid-p1b-host-fault-source-freeze-20261002.json`，独立审查通过、随本节点提交，未更新安装候选或重跑模型，原失败及预算不改，P1b/S0/S5a 未完成。

新一轮 P1b 已获用户明确授权：干净 `f64cd7e` source/runner，隔离安装与空 schema 9 单场已准备，190 个安装文件与 wheel/source 一致，独立只读核验通过。Root 5.6-sol/high、Worker 6.1-sol/high、helpers inherit；题目不变，科研 1200 秒／200 万总／20 万非缓存 token，人工等待 3600 秒。验收器查询间隔由 0.5 改为 5 秒并显式冻结，生产推进轮询仍为 5 秒；新样本不得把这一条件变化隐去。原失败、用量缺测和原件单独保留，不复制旧科学结果。准备累计 8.837 秒／RSS 206508032 B（包含一次核验字段错误，日志保留），证据 `/tmp/scid-p1b-f64-prepare-evidence-20261002/{freeze,rollup,actual-readback}.json`。当前会话原生目录不可访问；普通终端入口 `bash /tmp/scid-p1b-f64-run.sh` 仅读取冻结候选并启动已准备的唯一场次，用户页面创建/选择 `b0a-calibration`、暂停 bootstrap 并确认 `acceptance.objective` 预算；已有 attempt 则拒绝重跑。本准备节点未运行 native/模型，P1b 结果和评分待完成。

2026-10-02 后续真实 `f64cd7e` 场次再次失败：有界诊断确认 `_check_budget → _identities → native_loop_identities` 的 `SQLITE_BUSY`，Worker 当时仍为 running，恢复次数 0。当前源码改用统一控制数据库短等待（管理员参数 `progression.sqlite_busy_wait_seconds`，默认 0.1 秒），每次语句/提交按观察绝对期限、原目标剩余时间及存储自身期限收紧；文件锁继续非阻塞。纯读和原子观测复用既有有限恢复，未知原生提交不重放；DELETE journal 与原冻结授额保留。最终 17 项新增及 28 项既有精确 source 回归通过，46.874 秒／RSS 131796992 B，证据 `/tmp/scid-bounded-sqlite-regression-20261002-02`、`/tmp/scid-bounded-sqlite-existing-20261002-01`；前一版 15 项与最终组重叠，不重复累计。独立只读评审通过（无 P1/P2 阻断）；原失败、候选、状态与预算不改，未运行安装/native/模型或全套，P1b、科学效果及 live 安全资格仍未完成。

## P5 样本与成本上限（提议预留，未获新的运行预算授权）

首批仅 3 个场景 × 基线/候选各 1 场，共 6 场：①已有早期失败、跨若干无关尝试后的重复优化倾向；②关键条件变化后应允许有理由重试；③有冻结判据的有效负结果应推进。缺判据的定期确认、真实准入刹车与等待/未知负例先用确定性回放验证。两组使用相同冻结历史原件，不让模型重新生成整个长 loop；候选改变记忆投影/指定策略，差异逐项列出。短场两组固定一致的线程轮换条件，轮换收益单独验证；若轮换改变某组行为，必须单列变量或同步对照，不把综合差异归因于记忆。真实样本只作冻结历史检索与短场决策的探索性结果，不证明历史在真实运行中形成后仍能跨天、跨线程生效；后者由 P6a 验证。不替代主计划第 8 节原 24 场资格，也不声称统计显著或独立分离每项改动收益。

| 成本项 | 首批上限草案 |
|---|---|
| 单场 | 总输入+输出 150 万 token，非缓存输入+输出 12 万，执行墙钟 20 分钟；达到任一限制停止，不自动重跑 |
| 全部 6 场 | 总输入+输出 900 万 token，非缓存工作量 72 万，执行墙钟 2 小时；失败、摘要/助手、预演和缺测预留均计入，不另开额外校准场 |
| 人工评分 | 用户按冻结 rubric 评分，最多预留 3 人时；无人评分/超时保留待评 |

这些是结合历史单场约 100 万总 token / 7.6 万非缓存工作量制定的停止上限，不是预计必然花费或货币承诺。Root 固定 gpt-5.6-sol/high；Worker/helper 配置两组一致并冻结。Token 通知可能滞后，属于观测止损，不保证账单硬封顶；缺测停止新增场次并保留未归属成本。先排第一对场次检查成本可行性；若剩余额度不足后续配对，则报告不足并停止，不提高上限或挑选成功场。现有 S0 余额不自动转用，开始真实场次前必须另行确认可用预留；未获预算可继续代码/确定性验证，但不得宣布科研效果完成。

P5 证明最小记忆确有收益、且时间索引出现可复现的导航瓶颈后，再评估 L1 探索段/递归目录。S4 holdout 独立保持后置。净增删规模以 P1a 清单核算；控制层应减少重复许可，新增记忆责任必须有首版实际消费者。

## P6 长跑验收与预算（独立于 P5，尚未授权运行）

先执行 [P6s 小型任务](HOURLY_LOOP_MEMORY_BENCHMARK.zh-CN.md)：四批合成观测驱动预计 4–6 个完整任务，约 2 小时、硬上限草案 3 小时，包含安全轮换、等待恢复及真实早期经验再次使用。先构造材料、冻结评分并接入既有 runner，不立即启动 30 任务/24 小时或一周运行；P6s 的任务数据、预算和评分以该任务文档为唯一来源。小时级通过不替代下述跨天资格。

1. **先验逻辑与容量**：用虚拟时钟和持久夹具覆盖 300 个完整任务、跨周截止时间、暂停/恢复、用量迟到、轮换与并发 writer 拒绝。这只证明规则和容量，不证明宿主实际稳定运行一周。
2. **P6a：30 任务／24 小时**。串行运行一条受控研究链，验证有工作时推进、纯等待不烧模型回合、实际跨天恢复及至少一次安全轮换。必须加入真实形成的早期失败经验：本场前段产生并封存一项带适用条件的失败，经历跨天、至少一次 Root 安全轮换及后续尝试后，新 Root 能通过有界总览/分页索引找到确切原件，在派发前避免同条件重复；条件改变时能说明依据并允许合理重试。保留原件引用、读取与调度轨迹，由用户按事先冻结的 rubric 评价，不以“摘要里出现过”判通过。单条轨迹通过仅证明该条件下可用，不宣称普遍降低重复率。跨天或换线程任一未发生，或早期记录只来自预置历史，记忆项均记未验证，P6a 不算完整退出。任务容量和持续时长分别记录；若科学目标提前结束，可另做低成本等待/故障恢复实验，报告为组合证据，不能写成“真实研究连续完成了 30 个任务”。禁止靠无效精修凑场次。
3. **P6b：100–300 任务／3–7 天**。P6a 的身份、预算、恢复和内存无未决问题后，再分档扩大；每档冻结任务数、自然期限、推进启用时长及 token 上限。观测认证过期、宿主/守护进程重启、外部长等待、人工接管、早期失败记忆找回与硬停止。不人为制造真实未知外部提交，以安全适配器验证高风险故障。
4. **运行预算另定**：P5 的单场 20 分钟仅用于短场对照，不是产品 loop 上限，也不能挪给跨天运行。P6 根据最近同模型、同任务粒度的实测 Root/Worker/helper 用量，计算任务工作量 + 轮换/恢复/收尾预留；同时列总 token 和非缓存工作量，提供上界与缺测说明。先确认每档预留再启动；未获得预算仅完成源码/夹具资格，不自动申请或消耗 6,000–9,000 万 token。
5. **强制止损和人机交互**：资源上限、未核验进展窗口及可配置的定期方向确认共同生效，复用同一个暂停/继续入口。按任务数或自然时间到达检查点时给有界进展报告；有价值字段来自已有交付，不增加另一份 Agent 表单。等待用户期间不唤醒模型；自然期限和已接受外部作业的额度仍有效。达到上限暂停新增任务并保存交接，不自动取消已接受作业。
6. **退出声明分开**：P5 报告科研质量/重复弯路/成本；P6 报告容量、真实持续时间、恢复、Root 轮换、峰值资源和干预次数。短场、夹具、合成实验及真实 TCAD 的资格分别列示；任何未测范围明确保留，不用一项通过覆盖其余项。
