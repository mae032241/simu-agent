# 角色 token 份额进入控制层（2026-10-15）

> 后续修订：默认启用、预算改道、评估版本选择与预留规则以 [审查修复记录](POLICY_REVIEW_FIXES_20261015.zh-CN.md) 为准；本文保留原提交的设计和测试记录。

状态：无模型开发与定向测试完成；未进行真实场。协议仍为16，未新增协议版本。旧实例只读、不迁移。

## 问题

最近成功真实场 `rootless-task-unit-cov-20261014` 观测 4.62M token：H 1.22M（26%）、A 1.29M + 收口A 0.25M（共33%）、W 只有 1.87M（40%），仅2个W阶段；序列 `H001 W002 A003 A004 H005 W006 A007 A008 H009 H010 A011`。H/A 合计约 60% 观测量，其中 H009→H010 是无新证据的同角色连续思考。既有 prose 指导没有改变这一分布，本节点把份额结构放进控制层。

## 设计

新模块 `src/scidiscovery/research_loop/role_share.py`，只读已封存原件计量（各节点 `usage.json`，含 cached input），不新增可写余额库。

1. 冻结策略（`settings.role_budget_policy`，可选字段）：
   `version=1, min_w_share=0.65, max_thinking_share=0.35, thinking_node_target_tokens=250000`。
   `controller.prepare(role_budget_policy=...)` 默认值仅在显式冻结 `node_budget_policy`（真实场配置）时写入新实例；未给节点预算时不写（无节点目标即无 soft 通道）；显式传入却无节点预算则拒绝。传 `None` 关闭。CLI `scid-research prepare --role-budget-policy <json>` 可覆盖（JSON `null` 关闭），不传即默认。旧实例 settings 无该字段，全部行为不变。
2. 份额基数：原始冻结 `max_tokens`（不随后来 `budget_amend` 变化，保证重放确定）。只计步骤 `1..N`（当前被路由的已封存节点及之前）的原件，重放时与首次路由完全一致。
   - thinking = 探索 H + 非收口 A；收口 A 另计，不参与准入（由既有收口预留保护）。
   - "目标"= 拟派发角色的冻结单节点目标 `budget.node_limits(...)`：soft 模式为 `min(节点预算, 250k)`，hard 模式为运营者节点上限。
   - 拒绝条件（任一）：`thinking + 目标 > 0.35×T` → `role_share_thinking_reached`；`thinking + E + 目标 > (1−0.65)×T` → `role_share_w_floor_reached`（保护W下限不被H/A/E侵占）；前缀计量未知 → `role_share_usage_unknown`。
3. 同角色连续：拟派发角色与刚封存节点同为 H 或 A，且非审计回执复核 → `role_repeat_without_evidence`（无论份额是否用尽）。包括 semantic 作者补正（H009→H010 类）和 A 的决策补正。
4. 必需复核不受限（不会死锁）：W 后的 A（新 W 证据的评审）；A 审计后带回执的 A（`candidate_audit.receipt_ref` 存在；保持现有 audit→A 合法，后续节点再合并）；控制纠偏复核 H（`correction_request`）；收口 A（另一路径，未改）。
5. 改道（`role_share.effective_route`，接在 correction/semantic 之后）：被拒的可选 H/A 不派发，依次尝试在当前计划上续 W：
   `current_focus`（最近有效作者焦点）→ `plan_screen`（未完成计划的委托浅筛，与 null label+screen 语义相同）→ `last_stage`（上一 W 的 improve/validate 本地任务）。每个候选都用既有 `search.bind/launch_reason` 预检，第一个可启动的成为 W 任务；都不可启动则：有 delivery_policy 进入既有 `_start_closeout(reason)`；否则 `_finish(status='role_budget_stop', reason=code)`。
   - W 任务冻结 `job.role_budget = {version, reason, source_step, focus_source, thinking_observed_tokens, thinking_cap_tokens}`；`search.bind(redirect=focus_source)` 从冻结状态确定性重算焦点（`contracts._validate_inputs` 用同一参数复核），控制器 `_check_job` 重算并逐字段比较，篡改即 `retained_job_conflict`。
   - 改道 W 不继承作者补正、纠偏请求或审批结论。指令只陈述控制事实（未派发的角色与原因码），不含科学引导文字。
6. 单节点软目标：soft 模式下 `budget.node_limits` 对 H/A 取 `min(节点预算, 250k)`，经既有 `write_node_hint`（budget-status.json：near≥80%/reached）与 `publish_review`（`target_tokens_reached`）呈现；不 kill。hard 模式不收紧（避免把软目标变成硬上限）。收口A与W不变。
7. 通用性：核心无 cov 名称；份额判定只用角色、封存计量、搜索状态与既有准入。

## 默认值与标定

来源：`.trial` 下14个有真实用量的实例（排除≤1000 token的假节点），共62个 H/A 非收口节点、32个W、8个收口A（只读统计）。

| 角色 | 节点数 | 中位数 | P25 | P75 | 最大 |
|---|---:|---:|---:|---:|---:|
| H | 26 | 231,836 | 175,261 | 379,617 | 697,658 |
| A（非收口） | 36 | 208,180 | 171,486 | 397,340 | 796,221 |
| H+A 合计 | 62 | 220,932 | — | — | — |
| 收口A | 8 | 169,234 | 163,147 | 246,171 | 246,589 |
| W | 32 | 974,726 | 754,574 | 1,237,865 | 2,363,476 |

- 250k 单节点目标：略高于 H/A 中位（221k），62个节点中34个（55%）不超过；P75 约 380–400k 的长节点将收到 near/reached 软提示。
- 35%/65%：13个有W的实例（排除只跑了H的 u4-1013）H+A 占观测比例为 10%–60%（task-unit 59.5%、t5-audit 57.8%、hwa-live-02 46.7%；U4 18.6%、receipt-c 35.5%）。6M 授权下 thinking 上限 2.1M，约为 9 个中位 H/A 节点（2.1M/221k≈9.5），可容纳首个H、3轮"W后A+审计回执A"及一次可选修订。
- 份额以授权量为基数：W 未用完的授权不会被 H/A 借走；W 的 65% 是保留给W的下限，不保证W一定用到。

## 三个真实场行为卡（只读）

脚本：`python -I scripts/acceptance/behavior_card.py <instance> [--text]`。只读实例原件（jobs、usage、science-output、stage-end、budget-status、review.json、observations、control-ledger），不加锁、不写文件（运行前后 `find -newer` 为0）；公开 val 排名来自 observations 中 status=ok 的 metric，遇 official/hidden/reward 字段即拒绝。"frozen-share replay" 是按默认策略对原序列的反事实分类，仅第一次拒绝有意义（之后历史会改变）。

### rootless-task-unit-cov-20261014

```
rootless-task-unit-cov-20261014: 4.62M observed of 6.0M; H 1.22M (26%), W 1.87M (40%), A 1.29M (28%), A_closeout 0.25M (5%)
sequence H001 W002 A003 A004 H005 W006 A007 A008 H009 H010 A011; W stages 2, W native records 2, registered experiments 40
soft reviews {'stage_end:worker_requested': 1, 'hint:near': 3, 'review:target_tokens_reached': 1, 'hint:reached': 1, 'stage_end:target_tokens_reached': 1, 'review:reserve_reached': 2}; A recommendations 3:run-34 r4/34; 4:run-34 r4/34; 7:run-40 r2/40; 8:run-40 r2/40; 11:run-40 r2/40
frozen-share replay first refusal H009 role_share_thinking_reached; H/A tokens from that node 0.59M
delivered run-40 rank 2/40 (closeout closeout_reserve_seconds); observed submission file run-34 rank 8/40
```

| 节点 | 角色 | 观测token | 其中cached | 秒 | 原生记录 | focus/动作 | next_action | stage结束/停止 | 受管登记 | 新公开run | soft review | hint |
|---|---|---:|---:|---:|---:|---|---|---|---:|---:|---|---|
| 001 | H | 203,155 | 138,496 | 147.1 | 1 | - | experiment | - | 0 | 0 | - | within |
| 002 | W | 651,246 | 574,464 | 537.3 | 1 | h001.m1/screen | - | worker_requested | 34 | 34 | - | within |
| 003 | A | 402,303 | 338,688 | 189.2 | 1 | - | audit | - | 0 | 0 | - | within |
| 004 | A | 330,876 | 276,480 | 227.6 | 1 | - | revise_h | - | 0 | 0 | - | within |
| 005 | H | 426,045 | 355,072 | 297.6 | 1 | - | experiment | - | 0 | 0 | - | near |
| 006 | W | 1,219,734 | 1,100,032 | 756.2 | 1 | h001.m2/improve | - | target_tokens_reached | 6 | 6 | target_tokens_reached | reached |
| 007 | A | 177,453 | 123,776 | 147.6 | 1 | - | audit | - | 0 | 0 | - | within |
| 008 | A | 374,746 | 306,304 | 209.5 | 1 | - | revise_h | - | 0 | 0 | - | within |
| 009 | H | 412,842 | 352,000 | 374.8 | 1 | - | experiment | - | 0 | 0 | - | near |
| 010 | H | 175,261 | 135,424 | 348.5 | 1 | - | experiment | - | 0 | 0 | reserve_reached | near |
| 011 | A_closeout | 246,589 | 189,184 | 103.3 | 1 | - | finish | - | 0 | 0 | reserve_reached | within |

- 最佳公开 run-16（0.9112）；A 推荐 run-34（当时 4/34，最终 8/40）→ run-40（2/40，与 run-37..39 并列 0.9102）；交付 run-40，公开排名 2/40。收口由 `closeout_reserve_seconds` 触发（时间先耗尽）。
- 反事实：A003/A004、A007/A008 为必需复核（W 后 A、审计回执 A）；H005 可选但 thinking 0.94M+0.25M≤2.1M 放行；**H009 被拒**（thinking 1.91M+0.25M>2.1M，`role_share_thinking_reached`），H010 即使到达也会因 `role_repeat_without_evidence` 被拒。可改道的 H 计 0.59M token、约 723 秒。

### rootless-u4-cov-20261014

```
rootless-u4-cov-20261014: 4.59M observed of 5.8M; H 0.27M (6%), W 3.73M (81%), A 0.59M (13%)
sequence H001 W002 A003 A004 W005 A006 W007; W stages 3, W native records 3, registered experiments 0
soft reviews {'review:target_time_reached': 1, 'hint:reached': 2, 'hint:near': 2, 'stage_end:worker_requested': 1, 'review:target_tokens_reached': 1, 'stage_end:target_tokens_reached': 1, 'review:reserve_reached': 1, 'stage_end:reserve_reached': 1}; A recommendations 3:run-2 r1/5; 4:run-2 r1/5; 6:run-2 r6/13
frozen-share replay first refusal none; H/A tokens from that node 0.00M
delivered None rank None/None (closeout delivery_resolver_unavailable); observed submission file run-17 rank 11/26
```

| 节点 | 角色 | 观测token | 其中cached | 秒 | 原生记录 | focus/动作 | next_action | stage结束/停止 | 受管登记 | 新公开run | soft review | hint |
|---|---|---:|---:|---:|---:|---|---|---|---:|---:|---|---|
| 001 | H | 270,432 | 212,480 | 498.8 | 1 | - | experiment | - | 0 | 0 | target_time_reached | reached |
| 002 | W | 992,462 | 918,784 | 381.2 | 1 | h001.m1/screen | - | worker_requested | 0 | 5 | - | near |
| 003 | A | 174,998 | 118,528 | 140.7 | 1 | - | audit | - | 0 | 0 | - | within |
| 004 | A | 150,178 | 108,544 | 86.8 | 1 | - | continue_w | - | 0 | 0 | - | within |
| 005 | W | 1,578,305 | 1,480,832 | 803.9 | 1 | h001.m2/screen | - | target_tokens_reached | 0 | 8 | target_tokens_reached | reached |
| 006 | A | 259,853 | 183,808 | 214.7 | 1 | - | continue_w | - | 0 | 0 | - | within |
| 007 | W | 1,163,889 | 1,063,168 | 783.0 | 1 | h001.m3/screen | - | reserve_reached | 0 | 13 | reserve_reached | near |

- 该实例早于受管登记（managed_calls 为0，`registered experiments 0` 不代表没有实验；新公开 run 计 26）。A 一直推荐 run-2（第3步 1/5，第6步 6/13，最终 16/26）；未交付（`delivery_resolver_unavailable`），观测到的提交文件为 run-17（11/26）。默认策略下无拒绝：H+A 仅 18.6%。

### rootless-receipt-cov-20261014c

```
rootless-receipt-cov-20261014c: 5.27M observed of 6.0M; H 0.51M (10%), W 3.40M (64%), A 1.15M (22%), A_closeout 0.22M (4%)
sequence H001 W002 A003 A004 H005 W006 A007 W008 A009 A010 H011 A012; W stages 3, W native records 3, registered experiments 7
soft reviews {'stage_end:worker_requested': 2, 'hint:near': 1, 'review:target_tokens_reached': 1, 'hint:reached': 1, 'stage_end:target_tokens_reached': 1, 'review:reserve_reached': 2}; A recommendations 3:run-2 r1/4; 4:run-2 r1/4; 7:run-2 r1/6; 9:run-7 r1/7; 10:run-2 r2/7; 12:run-2 r2/7
frozen-share replay first refusal none; H/A tokens from that node 0.00M
delivered None rank None/None (closeout closeout_reserve_tokens); observed submission file run-2 rank 2/7
```

| 节点 | 角色 | 观测token | 其中cached | 秒 | 原生记录 | focus/动作 | next_action | stage结束/停止 | 受管登记 | 新公开run | soft review | hint |
|---|---|---:|---:|---:|---:|---|---|---|---:|---:|---|---|
| 001 | H | 127,354 | 98,944 | 90.7 | 1 | - | experiment | - | 0 | 0 | - | within |
| 002 | W | 765,823 | 696,320 | 516.8 | 1 | h001.m1/screen | - | worker_requested | 4 | 4 | - | within |
| 003 | A | 395,087 | 341,376 | 168.6 | 1 | - | audit | - | 0 | 0 | - | within |
| 004 | A | 112,801 | 49,920 | 126.0 | 1 | - | revise_h | - | 0 | 0 | - | within |
| 005 | H | 231,581 | 158,336 | 282.0 | 1 | - | experiment | - | 0 | 0 | - | within |
| 006 | W | 1,084,827 | 977,024 | 580.2 | 1 | h001.m1/screen | - | worker_requested | 2 | 2 | - | near |
| 007 | A | 216,964 | 145,280 | 197.4 | 1 | - | continue_w | - | 0 | 0 | - | within |
| 008 | W | 1,549,129 | 1,452,288 | 833.1 | 1 | h001.m2/improve | - | target_tokens_reached | 1 | 1 | target_tokens_reached | reached |
| 009 | A | 223,250 | 167,552 | 149.4 | 1 | - | audit | - | 0 | 0 | - | within |
| 010 | A | 197,812 | 162,432 | 82.7 | 1 | - | revise_h | - | 0 | 0 | - | within |
| 011 | H | 151,428 | 114,560 | 185.1 | 1 | - | experiment | - | 0 | 0 | reserve_reached | within |
| 012 | A_closeout | 217,400 | 166,144 | 124.5 | 1 | - | audit | - | 0 | 0 | reserve_reached | within |

- A 推荐 run-2 → run-7（第9步 1/7）→ 又回到 run-2（2/7）；未确认交付（收口 `closeout_reserve_tokens`），观测提交文件 run-2（2/7）。默认策略下无拒绝：H+A 占观测 35.5%，但其中 A003/A007/A009 为W后必需复核、A004/A010 为审计回执复核，H005/H011 前 thinking 均低于上限。

## 测试

新文件 `tests/research_loop/test_role_budget_share.py`（无模型，假封存节点 + 真实 controller 路由）：

- prepare 默认只随节点预算冻结；非法份额/版本/目标/多余键拒绝。
- soft H/A 目标 250k，W 不变，hard 模式不收紧。
- 只计封存前缀、按角色分账。
- 份额拒绝、同角色重复、W后A/纠偏H豁免；E 计入W下限。
- 旧实例（无策略）路由不变。
- controller 端到端：A revise_h 份额用尽 → W004（`plan_screen`，标记字段精确），W004 原件可复核，重跑不新增任务；H 修复焦点不可启动导致的 H→H 补正改道为 W 浅筛；篡改 `role_budget` → `retained_job_conflict`；无可启动 W 时无 delivery → `role_budget_stop`，有 delivery → 既有 `_start_closeout(reason)`；审计回执 A 合法、无回执的 A→A 拒绝。
- 行为卡只读（前后文件树字节相同）、公开排名正确、反事实首拒、非公开字段拒绝。
- CLI `prepare`：默认冻结、`--role-budget-policy` 覆盖、JSON `null` 关闭。

### 结果

- 新测试：`python -m pytest -q tests/research_loop/test_role_budget_share.py` → **14 passed**。
- 回归对照（不跑全量；逐文件串行，`-p no:cacheprovider`）：`tests/research_loop/test_*.py` 56 个既有文件，在 HEAD `e7106eb` 的干净导出副本与“HEAD + 本节点文件”副本上各跑一次，逐文件计数完全一致：既有 659 passed / 230 failed / 10 skipped（失败为另一代理正在清理的既有测试债务，本节点未新增失败）；加入新文件后 673 passed / 230 failed / 10 skipped。
- 预上线闸门（`a3e47f2`，另一代理所有，本节点未改）：在 scratch 中把 HEAD + 本节点源码非可编辑安装到临时 venv，按其脚本对 task-unit 冻结 settings 重放（bwrap、真实 launcher、假 native、零模型）。链路 `H→W→A(audit)→A→W(2片段)→A finish→收口A audit→收口A finish` 与交付 `delivery_confirmed` 均不变；唯一失败项是 `settings_equal_except_rebound`，差异 `['/role_budget_policy']`（旧 settings 无该字段，新 prepare 默认写入）。仅在 scratch 副本中把 `role_budget_policy` 加入其 kwargs 透传列表后，闸门 `passed=True`、差异为空。需由闸门维护方合入这一透传（旧来源得 `None`，新来源得其冻结值）。
- 过程中发现并修正：若投影固定用 250k，小预算夹具（如 `max_tokens=100000`）里任何可选 H→A 都会被拒（`test_node_budget` 2 个用例由此失败）；改为投影"拟派发角色的冻结单节点目标"后对照恢复一致，且与真实场 soft 配置数值相同（min(500k/550k, 250k)=250k）。

## 限制

- 只约束 token；task-unit 实际先耗尽的是时间（H+A 1942 秒 vs W 1294 秒）。时间份额未实现。
- 份额基数为原始 `max_tokens`；运营者 `budget_amend` 不改变 thinking 上限（保守，保证重放确定）。
- 必需复核（W后A、审计回执A）不受份额限制；receipt-c 显示 H+A 35.5% 主要来自必需复核，本节点无法降低。合并 audit→A 留给后续节点。
- 改道 W 的焦点由控制按冻结计划选择（作者有效焦点/未完成浅筛/上一本地任务），不是科学作者对新问题的判断；同角色补正（semantic 作者补正、A 决策补正、组合复核补正）被 W 或收口取代，这些补正机制在新实例中实际只在跨角色时生效。
- 单节点目标仅在 soft 模式经提示/复核通道呈现，模型可以忽略；W ≥65% 是保留下限，不能强制 W 实际用满。
- 无默认策略的情形：未冻结节点预算的实例不启用（多数旧单元测试场景）。
- 预上线闸门需透传 `role_budget_policy` 才能对旧来源保持“设置相等”检查（见测试节）。
- 未经真实模型验证，不能宣称科研效果或 token 分布已改善。
