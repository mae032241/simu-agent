# 控制层候选短名单、smoke 与预注册默认（2026-10-15）

> 后续修订：默认启用、预算改道、评估版本选择与预留规则以 [审查修复记录](POLICY_REVIEW_FIXES_20261015.zh-CN.md) 为准；本文保留原提交的设计和测试记录。

状态：无模型开发、定向测试与上线前门禁完成；未进行真实场。协议仍为16，未新增协议版本。旧实例只读、不迁移。

## 问题

候选选择原先只由 A 自由判断加 prose 指导：多次真实场里 A 反复推荐早期 incumbent run-2；u4 中 A006 只评估到 run-13，W007 之后产出的 run-14..26 从未进入 A 的比较；task-unit 中公开 val 最高的 run-16 在隔离环境里根本无法加载预测。本节点把"候选集合、默认选择、机械可用性检查"放进控制层，A 只在固定对称表上判断保留/替换，偏离默认必须给出结构化、绑定证据步的理由。

## 设计

新模块 `src/scidiscovery/research_loop/shortlist.py`（控制执行）与 `selection.py` 中两个纯函数 `shortlist()`、`default_choice()`（只用公开封存事实）。

1. 冻结策略 `settings.selection_policy = {version:1, shortlist_k:3, smoke_seconds:20}`（可选字段）。
   - `controller.prepare(selection_policy=...)` 默认值只在同时冻结 history observer（插件声明的公开指标）、`candidate_audit_policy` 与隔离 delivery adapter（即生产配置）时写入；缺任一则不写。显式传入但缺 observer 或 adapter → 拒绝。传 `None` 关闭。CLI `prepare --selection-policy <json>`（JSON `null` 关闭），不传即默认。
   - 旧实例 settings 无该字段：收口流程、A schema、job 字段全部不变。
2. 短名单（收口边界处计算一次，`host-delivery/selection/shortlist.json`，0400 不可改）：
   - 输入：`history.rebuild(source_cutoff)` → `selection.public_inputs` → 与 `selection.project` 相同的公开校验（hidden/reward 字段拒绝、候选身份不可变）。
   - 评估版本：完成候选数最多的 `(evaluation_key, direction)`；并列取包含最新观测候选的版本。
   - 排名：插件声明的公开指标；**同分时后观测者在前**（明确不偏好最早的 incumbent）。
   - 成员：top-k、A 当前推荐（最近一个非 audit A 的 recommendation，即使不在同版本也列入但不可默认）、"最近一次 A 评估（含 audit 请求）步及之后首次观测"的最佳候选（`unassessed_best`）。记录 `unassessed_count`、`boundary_ties_omitted`。
3. smoke 插件能力：
   - delivery 插件 resolve 回复可选 `capabilities: ["smoke"]`（`delivery.CAPABILITIES`）；核心只在声明时调用 leaf phase `smoke`，否则记 `unavailable`，从不当作 ok。核心只认 `ok/failed/unknown`（+`unavailable`）。
   - cov 实现（`cov_delivery.SMOKE`/`smoke_status`）：隔离 leaf 内以冻结 task Python 加载该候选的精确 artifact（cloudpickle）、用公开 harness `runner.split_X_y` 对公开 val 输入预测，检查形状与有限值。harness 自身不可用记 `unknown`，artifact 加载/预测失败记 `failed`。smoke phase 只挂 inputs 与可写 scratch，不挂目标目录。
   - leaf 输出与既有 leaf 调用同样保留在 `host-delivery/leaf-output`（含 `/scratch/smoke.{stdout,stderr}` 尾部），仅 host 可见，receipt 引用其索引与 SHA。
4. 控制筛选（`shortlist.screen`，首个收口 A 建任务之前）：
   - 每个调用先写 intent 再调用再写 outcome（`<kind>-NN.{intent,outcome,process}.json`，0400）；intent 无 outcome 视为不确定，**永不重放**（返回 `selection_smoke_unknown` / `selection_audit_unknown`），并进入 `budget.execution_blocked`。每个已接受调用计入 `used_steps`。无新账本、无可变指针。
   - smoke：所有成员（原件 audit_pending 且插件声明）；准入：剩余秒 > smoke_seconds + 收口执行底线（hard 模式另保留收口 A 秒数），步数保留收口 A + submit/confirm。
   - audit（已配置 candidate_audit 时）：按排名只审 smoke ok 的可比成员，**审到第一个通过即止**（其下者 `below_audited_default`）；A 先前对同一 artifact 字节的审计回执直接复用（passed/failed）；准入同 candidate audit 收口但额外保护收口 A 秒数。预算不足记 `not_run: selection_reserve_unavailable`。未改变 `delivery_reserve`，探索停止时点不变。
   - 结果冻结为 `screen.json`（行 + receipt SHA + 默认）。
5. 预注册默认（`selection.default_choice`）：在可比、smoke=ok、audit≠failed 的成员中按排名取最佳；优先 audit passed（或未配置 audit）；若无一通过审计，取最佳 smoke ok 且审计未失败者，`basis=submit_audit_pending`（交付 submit 本身的强制审计仍决定能否 promote）；都不满足则 `none_qualified`（无默认）。smoke failed/unknown/unavailable 与 audit failed 永远不是默认。
   - 与任务描述的差异（有意）：严格的"必须 audit 通过"在真实场几乎总会因收口时预算只剩预留而无默认；故设第二档并在 basis 中显式标注。
6. A 结构化比较（仅收口 A 且 job 带 `selection` 标记时 schema 增加一个可空字段 `candidate_comparison`）：
   - `rows`：必须按 `closeout.comparison.rows` 顺序覆盖每个成员，字段相同：`candidate_id, key_risk, decision(keep|replace)`；公开指标、评估版本、audit/smoke 状态、默认标记由控制在 `closeout.comparison` 中给出，不让 A 抄写。
   - `override`：选择非默认时必填 `default_candidate, chosen_candidate, reason, evidence_steps`（必须是冻结前缀内的精确节点步）；选默认时必须为 null。
   - `candidate_recommendation=null` + finish 即交付控制默认。
   - 校验在 `delivery.binding` → `shortlist.choice`：缺表 `selection_comparison_missing`、不对称 `selection_comparison_asymmetric`、keep 不一致 `selection_keep_mismatch`、多余 override `selection_override_unneeded`、override 未绑定 `selection_override_unbound`，都走既有收口作者补正（最多3次）；无默认且 A 不选 → `delivery_no_decision`。
   - 收口 A 仍可 `audit`（表可为 null）。job 冻结 `selection={version, sha256(screen.json)}`，`_validate_inputs` 复核，receipt 被改即硬失败。
7. 通用性：核心无 cov 名称；smoke 语义只在 `cov_delivery`。`guidance.py` 未改，表字段说明只在 schema description 与 `closeout.comparison.fields`。

## 协议

协议16冻结，未升版本。schema 增量只在带 `selection` 标记的新收口 A job 出现（与 `role_budget` 标记同类门控），旧实例与无短名单的收口不变。

## 上线前门禁

- `scripts/acceptance/prelive_gate.py`：kwargs 透传 `selection_policy`；源 settings 若早于该字段（task-unit 即如此），门禁采用新实例 prepare 会冻结的默认值，并在 verdict `adopted_defaults=['/selection_policy']` 中如实报告，仅豁免该路径的相等检查（其余差异仍为空）。
- 链路形状不变（8步）；收口前控制筛选实际经 bwrap leaf 做 4 次 smoke + 1 次 audit；收口 A 先 audit 控制默认，再 `finish` 且 `candidate_recommendation=null`，交付控制默认。新增检查：`selection_shortlist_frozen`、`selection_smoke_ok_with_leaf_output`、`selection_default_audited`、`selection_comparison_sealed`、`delivered_closeout_choice`（=默认且 A 未点名）、leaf phase 含 `smoke`。
- 实测：task-unit 冻结 settings 下 PASS，`delivery_confirmed`，约 73s，models_called=0；默认 run-2（公开第1，A 原推荐 run-4 第4名）。

## 三个真实场只读重放（公开数据）

脚本 `scripts/acceptance/selection_replay.py <trial>... [--smoke <fresh scratch>]`：只读 instance 下 jobs、A science-output、observations、A 请求的 candidate-audit 公开回执与 launcher.json（task_python、public_root）；拒绝任何 hidden/official/reward 字段；未读取任何 `*-rewards-*` 目录、final-result 或 qualification 文件。smoke 把成员的精确归档 artifact（observations contexts 中 `host-history/objects` 快照，SHA 校验）与公开 harness 复制到 scratch，在 bwrap 内（无网络、不挂实例）用冻结 task Python 运行与 cov adapter 相同的 SMOKE 代码。审计只取既有 A 回执（同 artifact SHA），其余记 not_run——真实收口会在预算允许时补审。运行前后 `.trial` 三个场 `find -newer` 为空。

| 场 | 前缀 | 短名单（rank/公开 val/理由/smoke/audit） | 控制默认 | A 实际 |
|---|---|---|---|---|
| rootless-task-unit-cov-20261014 | H001..H010（40 run，A 最后评估 A008） | run-16 1/0.9112 top_k **smoke failed**（`ModuleNotFoundError: recovery`）；run-40 2/0.9102 top_k+A推荐 ok passed；run-39 3/0.9102 top_k **smoke failed**（`recovery_choice`）；同分 run-37/38 越界省略2个 | **run-40**（audit_passed） | 交付 run-40 |
| rootless-u4-cov-20261014 | H001..W007（26 run，A006 后 13 个未评估） | run-26 1/0.9320 top_k+unassessed_best ok；run-24 2/0.9317 ok；run-25 3/0.9315 ok；run-2 16/0.9069 A推荐 ok；均无回执 | **run-26**（submit_audit_pending） | A 推荐 run-2（16/26），未交付 |
| rootless-receipt-cov-20261014c | H001..H011（7 run） | run-7 1/0.9099 ok passed（A009 回执）；run-2 2/0.9081 top_k+A推荐 ok passed；run-5 3/0.9063 ok | **run-7**（audit_passed） | A 回到 run-2，未确认交付 |

要点：
- task-unit：公开最高 run-16 被 smoke 机械排除（保存的模型引用了 W 本地模块 `recovery`，隔离加载失败），不需要 A 发现；默认与 A 最终交付一致。
- u4：A006 之后产出的 run-14..26 进入短名单（run-26 同时是 top-1 与 unassessed_best）；A 一直坚持的 run-2 作为 A 推荐列入表中对称比较，偏离默认需要 override 理由。
- receipt-c：A 先推荐 run-7（A009 审计通过）又回到 run-2；控制默认为 run-7，A 若保留 run-2 必须给出 override 证据步。
- 以上只说明控制规则的选择，不涉及目标/隐藏得分，不声称更好。

## 测试

全部在 scratch venv（`python -m venv --system-site-packages`，fresh wheel 非可编辑安装）中逐文件运行，未跑全量。

- 新文件 `tests/research_loop/test_control_selection.py`：**36 passed**。覆盖：同版本 top-k 与同分后者优先、A 推荐与未评估最佳入表、非公开/变动字段拒绝、默认分档（smoke failed/unknown/unavailable 排除、passed 优先、submit_audit_pending、none_qualified）、比较表对称/keep/override 各错误码、无默认时须命名选择、篡改 screen 拒绝、schema 只增一个字段、prepare 默认条件与非法策略、CLI 覆盖与 null；真实 bwrap + 冻结 task Python 集成：不可加载的公开最佳被 smoke 排除、默认被审计、null 交付默认且 submission 字节一致、重跑无新调用；asymmetric 表经补正后合法 override 交付；插件不声明 smoke → 全部 unavailable、无默认、`delivery_no_decision`；不确定 smoke 不重放且阻塞执行；关闭策略时原流程不变；receipt 篡改使收口 job 校验失败。集成用例在无 bwrap 或无含 numpy/pandas 的 task Python 时 skip。
- 门禁：`<scratch>/v/bin/python -m pytest -q tests/research_loop/test_prelive_production_chain.py` → **8 passed**（85s）。
- 回归对照（HEAD `77dea43` 干净导出 + 同法安装 vs 本节点），逐文件计数且失败用例 ID 完全相同：test_delivery 13p/2s，test_cov_delivery_lineage 8p，test_cov_delivery_isolation 8p，test_closeout 2f/11p，test_closeout_search_replay 10p，test_candidate_audit 3f/10p，test_audit_handoff 9f，test_role_budget_share 14p，test_soft_admission 3f/4p，test_soft_node_budget 3f/9p，test_worker_resume 6f/43p，test_selection 30p，test_public_selection_replay 1f/13p，test_selection_binding 2f/5p，test_result_schema 9f/3p，test_controller 2f/44p，test_symmetric_candidate_guidance 10p，test_current_protocol 40p，test_native_cli 7f/3p，test_budget 24p。失败均为既有遗留债务，未新增。未修改任何既有测试文件。

## 限制

- 未经真实模型验证；不声称科研效果或目标得分改善。
- smoke 与 audit 均为机会性：未加入 `delivery_reserve`。真实场收口通常在预留耗尽时触发，soft 模式下 smoke 只保留执行底线（不保留收口 A 秒数），audit 额外保护收口 A；预算不足时记 unknown/not_run，默认可能落到 `submit_audit_pending` 或 `none_qualified`。
- 审计"审到第一个通过即止"，较低排名成员的审计状态为 not_run；A 想替换为它们需自行请求 audit 或依赖 submit 审计。
- submit 审计失败时不会自动改投下一个候选（`delivery_failed`）。
- 评估版本选择（候选数最多）与同分规则（后观测优先）是声明的确定性约定，不是科学判断。
- smoke 只检查加载与公开输入预测的形状/有限值，不复现公开分数、不代表目标泛化。
- 门禁对早于该字段的源 settings 采用默认值（`adopted_defaults` 报告）；若某个新源显式关闭了该策略，门禁同样会启用并报告。
- 重放的审计状态只来自既有 A 回执；未在重放中执行公开 audit。
