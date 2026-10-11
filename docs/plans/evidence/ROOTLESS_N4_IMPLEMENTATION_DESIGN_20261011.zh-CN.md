# N4：封存 A 判断驱动的两级纠偏

日期：2026-10-11。设计基线：`1fdb282`，生产增量基线：已独审提交的 N3 `c19498a`。状态：规则及最小接线独审 PASS；生产已实施并双独审 PASS；完整 rootless 门禁 200 passed（73.27s）、容量增量4项及最终独立安装验证通过，详见 ROOTLESS_N4_ACCEPTANCE_20261011.zh-CN.md。原规则审查版 SHA b2219aba9516766f7d9adb4d52ecb96fa6624fd114fd67da066f81d98a956304。真实模型测试已暂停；本文不授权启动、恢复或补跑。

依据：[主计划 N4](../ROOTLESS_SEARCH_AND_LONG_RUN_PLAN.zh-CN.md)、[已审规则草案](ROOTLESS_N3_N4_DESIGN_DRAFT_20261011.zh-CN.md)。生产由独立执行者在 N3 独审提交后实施，两位非作者完成复审。

## 1. 科学接口只复用 N3

H 定机制，W 贡献试验，A 独立判断对原全局目标的贡献。复用 N3 的 `search_plan`、宿主从原 H／条目生成的机制引用、W 的 `screen / improve / repair` 和 A 的处置记录；边界与评估盲区写科学限制，不增加动作枚举。不新增机制 Schema、台账、Root 模型或角色包装职责。

N4 实施时通过新协议加一个 A 科学扩点 `progress_assessment`，根字段或已有 review 内字段按当时严格 validator 的最小改面选定，只有一个权威。N3 不提前实现占位，旧协议包保持原字节：

- `verdict = progress / no_progress / unknown`：A 的科学判断。
- `evidence`：少量当前 job 已绑定的科学原件路径，宿主解析原拥有节点与原字节。全局贡献、适用条件、盲区、未处置机制和下一步依据写现有 `scientific_result / limitations / route_reason`，不重复抄台账。

proxy 最高、A 推荐、实际提交继续分列，都不自动算进展。控制层不判科学正确、语义等价、机制证伪或目标达成，也不从指标大小、文件名或文本相似度改判。

## 2. 哪个 A 可计数，什么依据可清零

每个新的、已验证封存的 A 科学决策只计一次，以原节点及 seal 为身份；重启、重读、重复通知、W 内候选数不增加周期。失败／未封存／执行未知不伪造成完成的 A 判断。

| 来源 | 计数与处理 |
| --- | --- |
| A `next_action=extract / wait` | 延期，不增、不清任何计数；E 本身及 E 等待不计数。E 返回后新的非延期 A 才可计一次 |
| A no_progress | 无进展计数加一；这是 A 判断，不是宿主从 proxy 无提升推断 |
| A unknown，或 progress 缺乏可核对依据 | 未知单列，无进展计数不增、不清；不把不可比或盲区冒称停滞 |
| A progress，带未消费过的已绑定科学依据 | 清零未触发的纠偏计数；有依据负结果也可算进展，无需指标上涨 |

清零依据必须是**此前已封存、当前已绑定的确切科学原件／观察**，不能只引用当前 A 自身新 prose 或当前未封存文件。缺失、歧义、跨实例引用拒绝。同一原件的别名、页切片、复制路径、候选改名只给一次依据信用；原件身份与摘要由宿主计算，角色不写 hash。

新节点／文件／候选 ID、H 改 label／换版本、W repair 本身均不清零。修复如同时产生有效新观察，科学贡献由 A 解释，宿主只核依据身份；新字节存在不等于科学新认识。旧证据的新解释可以科学上合理，但重复依据或无法机械核对时保留 A 原判断、控制投影记需复核，不伪装成无进展，也不要求造新文件取得信用。该规则不能防止有新依据但科学判断错误的 A。

## 3. 两阈值提案及机械处理

建议显式启用 N4 的新实例冻结两个默认值：**首次 3 个可计 A，H 响应后再 2 个可计 A**。3 给局部方向两次继续机会，第三次重审；修订后 2 防止再次长期精修。它们是待评审默认值，不是经验最优；原预算／节点上限可更早停止，科学角色不能调阈值。

无进展与未知各自计数，未知从不折算成无进展：无进展达到首次阈值要求 H 重审方向；持续未知达到同一首次阈值要求 H 科学复核评估／证据。H 响应后相应问题仍达到第二阈值才停止新研究，原因分别为 `no_progress_unresolved`、`assessment_gap`，不新增第三个配置阈值。已知 A 判断可结束连续未知；等待／E 不清计数，未知不清既有无进展，H 换版本不退款式清历史。

第一阈值只约束**新科研派发**：A 原 `continue_w` 达阈值时，controller 按冻结策略实际派 H 重审，保留原 A result／next_action 字节，H 任务沿确切 trigger lineage 并说明控制约束；原 `revise_h` 仍派 H。不是阻 W 后等待一个没有入口的新 A。原 finish／wait 保留，不额外开 H；原 extract 保留 E 路由，E 不计周期。H→E→H 可补证据，H extract／wait 不视作完成修订；只有封存 H 明确选择 experiment／analyze 响应请求后，才计“响应后的 A”。科学上是否真换机制不由宿主猜。

所有计数／H 响应归属由原 seal、job 父关系和 evidence_return 重放，不新增 episode、交回状态机或祖先附件继承。新建与保留 job 的恢复核对必须共用同一有效派发判据，不能首次派 H、重启又按原 A continue_w 核对成 W。无法唯一核对归属则 unknown／要求修复；不制造 H 结论或授科学资格。

首级请求已由封存 H 的 experiment／analyze 真正响应、且暂停事实尚未发表时，新的可计 A 可以用未消费过的已绑定原件依据判 progress，结束当前首级请求并重新累计。原 trigger 与历史事实保留，重放按当时节点 cutoff 核对旧路由；后来的 progress 或 ack 不改已绑定的 H job。H 响应前，晚到判断或补充说明不能绕过已经派出的 H；已发表的暂停仍只能由确切 ack 有限放行。这是由不可变 trigger／ack 和科学原件推导的处理，不增加可变 episode 状态。

第二阈值在任何新 intent 前刹车。已接受工作仍允许采集、取消和封存，按 N1 的 active／unknown 口径继续计时。已发表的暂停事实不得由后补说明、晚到结果、删缓存或改名自动撤销；重复恢复只得到同一触发。

## 4. 人工 continue：只认一个绑定触发的 ack

复用 host writer 锁和 pause 边界。N4 触发尚未解除时，普通 `continue` 不构成豁免；外部操作者须显式 `continue --ack-correction <status 给出的确切触发标识> --authorization-note <决定说明>`，追加一个**绑定确切触发 A cutoff 的授权 ack**，再允许恢复。过期／错误触发标识拒绝，不把旗标当身份认证。保留原 trigger／历史计数，不退时间／token，不改 ceiling；预算修订仍走 N1 的独立显式入口。角色不能写宿主 ack；权限依赖已验证 launcher，raw Codex 软隔离限制如实说明。

ack 最多覆盖**下一次非延期封存 A 决策周期**，含必要 H/W/E 链，原预算和 N3 范围继续约束；不是任意多个 A 的无限恢复。extract／wait 不消耗科学周期，也不给额外预算。下一可计 A 后授权即用完，按保留的原计数和新判断重算：有依据进展可解决纠偏；问题仍达阈值则由该新 A 再暂停／需复核，不能复用旧 ack。不能核对原触发或 ack 则拒绝新派发。已 finish 的原科学路由不因 continue 自动创造任务。

首版不新增自动解除策略；未来预先批准策略必须另冻结同等范围。控制投影可删除重建，seal／实际触发／外部 ack 是各自事实原件，不并立一套调度状态权威。ack 的实际存储与并发接线留到 N3 提交后的实施审查，不能只删除 pause.request 就绕过权限原因。

## 5. 最小无模型夹具

| 夹具 | 预期 |
| --- | --- |
| 三个 no_progress A，W 内多候选／微调 | 每 A 一次；第三次促 H，不立刻强制暂停 |
| H 响应后两个 no_progress A | 第二次暂停；H label／版本、repair 不清零 |
| H→E→H 与 A→E→A、合法 wait | E／延期不计；只有 H 完成响应、A 作出非延期判断才推进对应计数 |
| 新文件／改名／重复依据／自报 progress | 不由新 ID 自动清零；同一依据不重复给信用；当前 A 自身 prose 不当依据 |
| 新证据上的有效负结果 | A 可判 progress；未触发前清零，proxy 不必提升，不授目标资格 |
| 不可比、盲区、持续 unknown | 未知单列、无进展不变；3→H 科学复核，响应后2→未解暂停，不称科学停滞 |
| 恢复／重复通知／删除投影／旧实例 | 不重复计数，原件重建；旧未启用实例及旧 job/schema/seal 字节不变，缺字段不推断无进展 |
| 触发时工作已接受、随后才完成 | 继续采集封存、阻新 intent；active／未知消费不中断，后到判断不自动抹触发 |
| 普通 continue／错误触发 ack／同 ack 重试／下个 A | 普通恢复不豁免 N4；确切 ack 只一次有限授权，新 A 后按原计数再判，不退预算，不永久绕过 |
| 原 seal／依据／ack 篡改或跨实例 | fail closed，无模型新派发，无伪造科学结论 |

实施退出条件：复用已提交 N3 引用，冻结 N4 新协议 A 扩点、两阈值、证据去重和 ack cutoff，经独审后另授权 production ownership；必要小 gate 通过共享串行 scripts/run_tests.py。没有真实模型效果、hidden score、资格继承或自动补跑声明。

## 6. 已冻结的最小接线与使用方式

`prepare --correction-policy <JSON 文件>` 显式启用；默认值可写为 `{"review_after":3,"pause_after":2}`，未指定不迁移、不启用旧实例。要求同时冻结 N3 search policy。协议 6 的 A 根字段 `progress_assessment` 为 required nullable 严格对象，例如 `{"verdict":"progress","evidence":["inputs/parents/009/conclusion.json"]}`；verdict 只取 progress / no_progress / unknown，null 计未知。协议 1..5 保持原 schema/view/job/seal 字节，不补字段。

首版依据仅接受当前绑定的父科学结论或历史科学页，统一回到原 raw SHA；不同节点的相同原字节不再给信用。裸候选 ID、附件名、当前 A 输出和未封存工作文件均不构成此入口，不新增 N2 观察权威。权限由 qualified launcher 保障，raw Codex 仍为软隔离；操作者说明不是认证。

`correction.py` 重放原件，`correction-ledger/000001.json` 起仅追加 trigger/ack，带 settings 绑定、序号与前件摘要。整个发布或授权区间持同一个 host writer 锁。发布每次只取当前 sealed cutoff 投影中最早未发表触发，追加一条后立即在同 cutoff 重放，再选择仍成立的下一事实；不批量发表旧预测，崩溃从持久前缀继续，无效已发表链拒绝并保留。

H job 的 `correction_request` 绑定原 review trigger；统一 effective-route 按每个历史节点自己的 cutoff 计算，后续 progress/ack 不改变旧 H 任务。H→E→H 通过原 evidence_return 继承请求，不增加交回状态机。已接受 intent 的恢复／采集／封存在新派发门禁之前。

暂停返回 `status=correction_paused`、`correction_trigger.trigger_id`；只读 `status` 提供 `correction.current_pause` 和有限 `permit`。继续命令为 `continue --root <实例> --ack-correction <该 trigger_id> --authorization-note <决定>`；错误／过期触发在删除 user pause 前拒绝。重复 ack 保留原 cutoff，不延长授权。首次非延期 A 已封存即消费授权，然后复判**所有**未解决问题；unknown 不增加 no_progress，也不能解除其既有暂停。有效 progress 可清原问题；已知判断可结束连续未知。用量与 ceiling 仍完全沿 N1 原规则。
