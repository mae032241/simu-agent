# N6：所有节点有界与预算内交付——设计草稿

状态：N6a 已验收并提交 `7c6072c`；[N6b 实现、回归及安装验收通过](ROOTLESS_N6B_CLOSEOUT_20261012.zh-CN.md)。首稿：2026-10-11；范围拆分：2026-10-12。
代码基线：`123/scidiscovery-e5.2` 的 `020004b`；依据最新 `docs/plans/ROOTLESS_LINEAGE_ADAPTIVE_SEARCH_PLAN.zh-CN.md` 的 N6/T0 条款。
首轮设计仅读源码和原用量；后续实施状态以上行为准。未调用科研模型、未恢复 N5。N5/live02 全池收尾与本设计独审均已通过；[设计评审记录](ROOTLESS_N6_DESIGN_REVIEW_20261012.md)只授予实施，不代表代码或真实运行通过。

## 1. 根因与可承诺的边界

| 当前路径 | 缺口 | 最小处理 |
| --- | --- | --- |
| `native._usage_event/run_native` | 只有 `turn.completed` 计量；H/A/E 无单节点硬停止策略，W 有 `search_slice` | 所有角色共用一个节点预算锚点及停止函数，保留原 runner/清理/封存规则 |
| `controller._launch_limit/_run` | 新节点仅检查总额度；没有最终 A、提交、确认的预留 | 新节点准入同时检查本节点上限与剩余收口预留；不足就进入交付，不能再探索 |
| `history.rebuild/search.project` 等 | 默认读取连续已封存节点；硬停止留下未封存节点后直接建下一 A 会失败 | closeout job 冻结停止前的已封存前缀，只读取该前缀；停止节点保留为执行事实，不充作科学结论 |
| N2 observer / A recommendation | 观察和推荐已有，但不是提交事务或最终交付决定 | 一个明确的 A 交付任务，加薄的提交/确认适配器；不把旧推荐自动当成最终决定 |

N5 原件的只读重算：17 个节点各仅有一次 `turn.completed`。已观察单次最大值为 H 383,935、W 1,129,054、A 481,576 tokens；E 没有样本。来源为 `.trial/rootless-n5-cov-20261011/instance/{jobs,native-evidence}`，仅读取角色、`usage.json` 和完成事件的数字，未读取隐藏评分用于策略。
这些是已观察成本，**不是未来单次请求上界**。例如 50k 的节点阈值也可能直到一次 481k 的 A 完成事件才被看见。

能保证的是：有限准入、观测后的停止、持久消费不退款、未知执行不重放、明确交付状态。不能保证严格零 token 超额、任何在途请求都留足预留，或一次 A 必然成功。被硬停止的原始输出不能升级为科学成功；留下旧提交也不能伪装成 A 已完成新的选择。

## 2. 冻结策略：宿主配置，无新科学协议

N6a 提供独立的 `prepare --node-budget-policy <json>`，仅启用所有角色的节点预算。N6b 才提供 `prepare --delivery-policy <json>`；启用交付必须同时冻结节点策略，不能仅设预留却没有交付路径。两者是同一份 `settings` 中不同用途的宿主策略，没有该字段的旧实例保持原策略。配置、适配器代码/config 哈希一起进入原 `settings` 身份，不修改既有协议 8 schema、raw、job 或 science-task。T 系列科学字段留到 T0 一次升级。

策略仅可在 prepare 新实例时冻结。N6a 已准备实例不能在 N6b 到来后静默追加 delivery 配置；既有无 delivery 实例的 closeout 只支持本地 `--export-only`，不因此获得新模型或外部执行入口。

两节点的配置边界只含：

- N6a 的 node policy：H/W/A/E 各自 `max_observed_tokens / max_seconds`，必须正数；W 的有效上限取该值与现有 `search_policy` 上限的较小者。
- N6b 的 delivery policy：closeout A 的同类上限；初次 A 加现有最多两次合法作者补正，禁止另建重试额度。
- N6b：零模型 `submit / confirm` 的时间上限；适配器声明不调用科研模型。
- N6b：token 在途余量、时间终止/清理余量，以及具体适配器或无适配器模式。

**不冻结未经验证的生产默认数值。** 参数表须附每角色最大已观察完成用量、计量粒度、时长来源和缺失项；N5 的 E/精确分角色启用时长不足，不能拿文件 mtime 猜测，也不能把 A 平均值乘 1.5 当证明。历史最大单次用量用于保守余量讨论，不当作平台保证。未知项由操作者明确冻结有限试用值并标为假设，或补齐测量后冻结；都不得声称保证交付。

预留从配置派生，不存第二份余额：

```text
R_tokens  = 最多 3 个 closeout/合法作者 A 的节点 token 上限 + 在途 token 余量
R_seconds = 最多 3 个 A 的节点时间上限 + submit 时间 + confirm 时间 + 清理余量
R_steps   = 最多 3 个 A 名额 + 1 submit 名额 + 1 confirm 名额
```

无适配器时不预留外部 submit/confirm，直接作本地导出，不派新交付 A；终态是 `exported_unsubmitted`，不声称实际提交确认。真实 N6 交付验收必须覆盖一个配置的适配器。
prepare 校验预留能放入总额度；每次实际补正、执行、失败都消耗原额度。不得把三份预留再加到总额之外。预算修订仍只用原 `budget-amend`，不修改科学 settings 或清空已消费事实；修订总额不自动恢复探索。

## 3. 唯一预算权威与节点准入

复用 `budget.snapshot/transition`、`native.usage` 和原 control ledger。增加少量 `closeout_begin`、宿主 action intent/outcome 事实；同一 host writer 和 ledger 短锁下写入，沿用 seq/parent/settings 身份链。科学决定仍只存在 A 的 sealed raw，账本只引用它，不复制候选表、科学理由或另一套剩余用量。

N6a 新增 `budget.node_admission/accept_node/stop_node`，主控制器与真正 `Popen` 前调用同一函数。节点 intent 只增加一个冻结 `budget_slice`：job 身份、boot/启用时间锚点、角色有效上限及总边界。N6b 按冻结 job 的目的应用交付上限/预留，不另设消费起点。新 N6 的 W 复用该锚点；旧 `search_slice` 仍按原规则恢复，避免同一次 W 有两个消费起点。

探索准入须满足：剩余 tokens/time/steps 能同时覆盖本节点有效上限与尚需的收口预留；上式中的在途/清理余量只计算一次。不足时不缩成一个必然无法完成的小 H/W/E，也不再接受探索 intent；先发表 `closeout_begin`，再建 A。已接受的节点继续按冻结 intent 恢复，不能改成 closeout 或重新启动。

运行中的探索节点除角色上限外，还检查保护预留后的共享观测边界；不是等总额度用完才停止。关闭探索后，A 和适配器仍检查原总上限。token 只在完成事件更新，下一事件可能越过保护边界；越过后如实记录缺额，不承诺还可启动 A。时间按原同 boot `CLOCK_BOOTTIME`/advance 并集，包含 runner、适配器和清理；用户 pause 不给已接受工作退款。

N6 的 `max_steps` 明确覆盖科学节点名额及已接受的 submit/confirm 名额。保持现有科研 job 编号；已准备/占用的 job 不覆盖、不回收名额。宿主动作以账本 action identity 各计一次，重启读取已有 outcome 不重计；一次新的外部确认调用必须接受新名额和有界时间，不能借相同提交 ID 无限查询。首个 confirm 已预留，后续未知查询只在原总额有余量时显式接受。旧无 N6 实例仍保持原节点口径。

## 4. 正常交付与硬停止后的 `closeout`

接口：`scid-research closeout --root ...`；`--export-only` 永不启动模型或外部提交。命令持同一 writer 锁，可写本地收口事实，记录显式操作者请求；命令/说明不是身份认证，科学角色不能写宿主控制目录。`run/continue` 在已发表 closeout 后只返回/恢复交付状态，不自动探索或扩额。

入口顺序：

1. 核验 settings、科学原件、用量和现有 action 身份；任何 live/unknown 本地执行、缺失用量或篡改都阻止新模型/提交。未知外部提交仅可进入同一 operation identity 的有界查询，不可创建 A 或新提交。合法终态但尚待封存的原工作先按原资格恢复封存，不重放。未解除的用户 pause 或已发表科学 pause 仍拦新工作；沿用原 continue/确切 correction ack，closeout 本身不能替代它们。
2. 原任务确已硬停止且无未知执行时，冻结停止前最后一个连续已封存科学前缀。保留未封存节点的 job、intent、raw、outcome、usage；不补出成功 seal。
3. 总额度任何一维不足以容纳合法 A 与必要执行/确认时，返回 `closeout_budget_unavailable` 并零模型导出：最后已确认提交、现有推荐、原停止原因、缺失/未完成目标。N5 已超过名义 token 总额，适用此路径，不会因新命令复活模型。
4. 有剩余已授权额度则发表不可变 `closeout_begin`，创建下一空闲科研编号的 A。已存在准备 job 与该目的冲突则保留并报告；不覆盖旧 H/W，也不偷用它的 intent。

**前缀接口是必要的小迁移，不是另一套科学历史。** closeout job 增加宿主 `purpose` 和 `source_cutoff`，`history.bind` 在指定 workspace 冻结该前缀；closeout 不运行探索 `search.bind` 或新增 N4 计数，入口仍核验原科学暂停。该前缀必须逐原 seal 验证且不含未封存节点，后续 closeout A 只通过直接前驱原件读取已完成作者补正。封存/验证/刷新均使用同一冻结前缀，不再无条件 `range(1, 当前编号)` 越过停止节点。不得全局改成“忽略缺失节点”，普通 run 的未知/不连续工作仍硬拒。

A 使用原协议 8：在明确交付问题中，`candidate_recommendation` 指出保留当前确认候选或替换为另一已列候选，`null` 表示无合格选择/无法决定；依据、未知和未完成目标写原 `scientific_result/limitations`。不让 A 填提交路径、SHA、事务表。该语义只适用于新冻结的交付任务；一般 A 推荐仍是推荐，不会自动变成提交决定。A 若要求 H/W/E 或等待，保留其原 action 并报告 `closeout_unresolved`，不会继续探索。

此复用有一个实施前条件：当前已确认候选必须能以原已绑定、可验证的候选 ID 出现在交付选项中。若只有未绑定的外部当前提交，不能为了“保留”伪造候选 ID，或把 `null` 猜成保留；首版如实导出该现状及 `decision_unresolved`，需要新增科学表达时交 T0。

只允许现有白名单语义补正，次数与全部成本计入原 root/reserve；无效显式选择不沿用旧文件。不软化 schema、材料资格、权限或 native failure。closeout A 本身硬失败不自动重复；再运行 closeout 读取同一终态并导出失败。

## 5. 一个薄执行适配器，不让 core 选科学候选

`delivery.py` 首版只提供配置验证、精确 intent/outcome、submit/confirm 调用和状态派生。适配器接受 action identity、A seal 身份与精确候选/合格工件绑定，返回有界的外部操作标识及 `confirmed / failed / unknown`。输入/输出/运行时间有界，源码/config 在 prepare 冻结。cov 实现由公开提交台账、精确模型快照及目标位置完成机械提交/核对；核心不读隐藏评分、不评科学优劣、不在宿主无限制解包科研 pickle。

适配器沿用该实例已验证的隔离/权限范围，不借宿主身份绕过原执行授权；写入目标必须冻结。候选只是 digest-only、模型丢失、审计资格未知或源身份失配时拒替换，不能按文件新旧猜模型。科学 A 的选择不自动获得额外权限。

先持久 submit intent，再执行。已确认同一 intent 不再次提交；控制器在外部成功后崩溃，恢复只允许针对同一 operation identity 的有界 confirm/query，绝不盲目重放 submit。未知 query 没有变成成功，次数/时间/名额也不会重置。模型用量为零不代表时间和动作名额免费。

旧确认记录永久保留，新确认前不删除旧记录。未知替换时 `last_confirmed` 仍可列旧值，但“当前实际提交”必须是 unknown，不能声称旧值仍在目标上。替换明确失败且确认旧值仍在时报告旧实际提交及替换失败；不冒充 A 原替换决定已成功，也不让 host 自行改成“选择保留”。

## 6. 持久化与恢复不变量

- closeout 模式、候选决定和动作结果从原 job/seal 与账本事实派生；没有可变 episode/status 文件作为第二权威。
- `closeout_begin` 发表后，重启、pause/continue、预算修订都不清空消费/预留/补正次数，也不重新打开探索。
- 回收原 runner/outcome 优先于任何新 action；清理未知继续保守计时并拒新工作。外部 action 也纳入 `budget.execution_blocked`。
- closeout A 的直接原件与候选索引固定；若后续外部改模型、历史页或资格记录，验证失败，不换用近似来源。
- 交付完成与科学目标完成分开：即使提交确认，仍 `goal_completion=not_asserted`，原停止条件未满足项必须保留。
- 只有不调用模型或外部适配器的本地导出可以在总额耗尽后执行；此时不能把远端 query/confirm 偷塞进“零模型导出”。

## 7. 最小回归与安装验收

| 用例 | 必须观察到 |
| --- | --- |
| H/W/A/E 参数化实际 fake launcher | 各角色的时间与 completed-usage 节点阈值生效；不成功封存硬停止输出 |
| 完成事件前无用量、一个事件大幅越限 | 如实记录缺量/超量；不声称零超额或剩余预留必足，不强造 A 成功 |
| token/time/steps 各触预留边界 | 无新的探索 intent；真正有界 A 可完成决定，非杀 W 后仅显示“已交 A” |
| 两次合法补正及 E/重启 | 原 author root/count 与全局消费保留，预留不重复发放 |
| 已知硬停止造成一个未封存洞 | closeout 只读截止前 qualified science；停止节点全包不变，普通 run 仍不跳洞 |
| 总额耗尽/缺量/unknown/cleanup_unknown | 不启动模型或提交；只输出有界现状/缺失报告 |
| 保留/替换失败/未知提交 | A 原选择保持；旧 receipt 不抹除；未知不自动重试，确认后才更新 actual |
| submit 成功后宿主崩溃 | 同身份 query；无重复提交、无第二份消费或凭空确认 |
| 无候选/无适配器/科学 pause/schema或资格失配 | 如实 no_candidate/exported_unsubmitted/blocked，不解除硬资格或原暂停规则 |
| installed CLI 整链 | 实际 wheel 的 prepare→reserve handoff/explicit closeout→A→fake submit→confirm→restart，0 模型；旧实例恢复与 frozen schema/view 哈希不变 |

不重开原 N5。真实交付用另行授权并冻结的一场或 T5，模型偏好沿用 gpt-6.1-sol/high、非 fast。

## 8. 两个可独立提交的范围与退出条件

两节点均由本设计负责人承担实施责任，独审由另一人执行；这里的 ownership 是待设计通过后的职责分配，不是当前生产编辑许可。共享文件只串行修改：N6a 独审/提交后，N6b 以该提交为基线。其他工作者的改动不得回退。

### N6a：所有角色的节点预算，可独立启用

**用户可用范围：** prepare 显式冻结四角色 node policy；run/status/continue 真实执行节点上限并如实展示观测、停止与未知。它只承诺节点预算防护，不承诺完成 A 或提交。原科学 route、补正与总额度仍生效。没有预留切换、交付模式、closeout job 或 adapter。

| 实施 ownership | 此节点改动 |
| --- | --- |
| `src/research_loop/budget.py` | 节点策略校验、共享准入/停止判断，复用消费与同 boot 时钟；不写 closeout/action 事件 |
| `src/research_loop/native.py` | 全角色冻结 budget_slice、真 Popen 二次检查、运行中观测停止，W 复用同一锚点 |
| `src/research_loop/controller.py`、`cli.py` | prepare 冻结 node policy、主准入与 status；未知/终态恢复及原路由保留 |
| `tests/research_loop/test_node_budget.py`（新）及必要现有 budget/native/controller/CLI 测试 | 全角色实际 fake process、恢复和兼容；不增加仅镜像实现的断言 |
| `docs/ROOTLESS_CLI.zh-CN.md`、N6a 验收证据 | 明确无交付保证、token 滞后与操作边界 |

**必须同时满足的退出条件：**

1. H/W/A/E 参数化 fake launcher 的 token/time 上限均进入实际执行路径；已停止 raw 不封存为成功。相同 runner 重接使用原锚点，没有重复提交或退款。
2. 原总额度、W 上限取较小值、作者补正成本、缺量/unknown/cleanup_unknown、UTC 校正与 boot 边界均保留；旧冻结实例无字段时原字节与行为不变。
3. 已安装 wheel 的 CLI 用新 node policy 可运行正常 fake 节点，并观察一个真实超时/超量停止；0 模型。prepare 不接受 delivery 配置，CLI 不出现可启动交付的半接线入口。
4. status/文档不能把停止写成“已交 A”或“已交付”，不宣称严格 token 零超额。独审通过后才提交 N6a。

N6a 不实现闲置的 reserve planner、前缀迁移或 closeout CLI，以免留下能启用却只会停机的中间状态。

### N6b：预留、完整交付及显式硬停收口，一次接通

**用户可用范围：** 只有 N6b 完整通过时，prepare 才接受 delivery policy，run 才可因预留边界派发真正的有界交付 A，CLI 才开放 closeout。新实例同时冻结 node/delivery 策略；没有适配器的已冻结模式如实以本地导出结束。

| 实施 ownership | 此节点改动 |
| --- | --- |
| `budget.py` | 派生剩余预留与动作名额、原 ledger 扩展的不可变事实、外部执行阻断；不建第二余额 |
| `controller.py`、`cli.py` | 正常预留切换、显式 closeout、完整状态/恢复接线及入口资格；不能解除原 pause/ack |
| `contracts.py`、`history.py` | 仅 closeout 目的的 frozen source_cutoff、A 任务、验证与封存刷新；普通连续历史规则不变 |
| `delivery.py`（新）、一个外部 cov adapter | 有界 intent→submit→confirm、精确来源/原授权、未知查询及不可重复提交 |
| `semantic.py`、`correction.py` | 仅确有必要的 closeout 目的校验与原补正/暂停复用；不新建 episode 或清零计数 |
| `tests/research_loop/test_closeout.py`、`test_delivery.py`（新）及必要现有接线测试 | 预留、硬停洞、A 决定、确认恢复、未知与拒绝分支；使用共享串行测试入口 |
| CLI 文档及 N6b 验收证据 | 实际交付状态、预算内恢复限制、已测/缺测参数来源 |

**必须同时满足的退出条件：**

1. tokens/time/steps 分别触及预留边界的已安装 fake 链，完成 qualified A 的真实封存与保留/替换决定，再完成 fake submit/confirm；不能仅停 W 或打印交付状态作成功证据。
2. 一个已知硬停未封存洞可用剩余授权额度完成同一链，停止节点原件不变；普通 run 仍拒跳洞。总额耗尽仅本地导出，未知执行、缺量、资格和原科学 pause 仍阻断新动作。
3. A 两次合法补正、提交成功后崩溃、确认未知、重启、预算修订均不重发额度或重放提交；confirmed/failed/unknown 与旧 receipt 如实并置。
4. 候选未绑定/工件不可回读、无 adapter 和 A 无决定均不能声称提交成功。旧协议/实例保留，N6a 独立 node policy 继续工作。
5. 参数均由操作者显式冻结且注明证据/假设，无虚构默认常数；独立源码审查与 installed 0-model 完整链通过后才提交。真实模型验收另行授权，不用于填补当前接线验收。

N6b 任一完整交付门禁未过，不能提前单独开放 `--delivery-policy`、自动 reserve handoff 或非导出 closeout；要么继续完成此节点，要么删去可启用入口保持 N6a 的可用范围。

## 9. 工作量、风险与待评审决定

建议 N6a 和 N6b 两个提交，范围/退出条件以上节为准。粗估合计生产 450–700 行、定向测试 300–450 行；其中 N6a 约 120–200 行生产改动，N6b 承担完整交付接线，不能按行数拆成可启用的半功能提交。若超过范围先回设计评审，不叠加模型 Root、发布引擎或候选账本。
高风险是停止节点后的前缀读取与 native 在途计量；次风险为外部提交未知和 public adapter 权限。源改动落点：`budget` 的单一节点/动作准入；`native` 真 Popen 与轮询；`controller` 目的切换；`contracts/history` 的冻结前缀；`cli` 新命令；一个 `delivery.py` 加一个 cov 实现。`semantic` 只复用原补正身份，`correction` 保留原科学暂停/ack，不建第二状态机。

独审需确认：前缀字段及 all-actions 步数口径是否足够薄；closeout 对科学 pause 必须仍要求原 exact ack，不能借交付免除；参数缺测时是否仅接受明确标注的试用冻结值；适配器的实例原授权与隔离证明；A 原字段在新交付目的下的明确解释是否可用。若确需新增科学输出字段，停止此替代接口，交 T0 统一升级设计后再实施。

## 10. N6b实施接缝补充：普通候选的冻结与提交审计

2026-10-12独立设计复核通过，源码资格待实施验收。已封存候选台账中的status=ok不等于有审计资格。

- 构造交付A任务前，领域resolver从已封存台账的确切run行、冻结的runs路径映射取得model/script；有界快照并绑定来源、哈希与公开审计harness/data版本，标为audit_pending。身份可回读不等于通过审计。补正和重启复用同份快照，不事后改绑。
- A选定后在隔离scratch执行公开诚信审计；fail/skip/timeout/malformed均不更新实际提交，不能只凭leakage_flag=false判断完整审计。源及模型身份前后核对。
- scratch没有真实提交目标写权限，也不挂载隐藏数据；核心宿主不解包科学pickle。完整审计通过后才由适配器更新目标。
- 更新前持久化同operation意图；崩溃或半写产生unknown，只对同一身份做有界confirm。resolver、audit、submit、confirm均计入原时间预算，live或未知执行阻止新动作。旧目标在审计失败时保持。

本补充不新增科学输出schema，不新增平行账本；执行器权限保持原冻结范围。

实际实施超出初稿行数估算，原因与独立范围复审见 N6b 验收记录；保留一份控制账本，不以省略资格或恢复检查控制行数。Worker 原线程断点续接不在本 N6b 验收范围。
