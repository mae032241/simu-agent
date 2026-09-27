# 新对话接续：Fig.4 路线剪枝验收、P0 生命周期修复与检查点

> 历史交接快照：本文以下记录的是 2026-09-23 早期的阻断与当时待办，不再表示当前安装或 Run 状态。后续正式结果、P0 补审边界及现行待办见[2026-09-23 现场行为验收](evidence/fig4-route-pruning-r2-20260922/FINAL_BEHAVIOR_ACCEPTANCE_20260923.zh-CN.md)和[计划索引](README.md)。

更新：2026-09-23。先读本文件；按下一实际动作懒加载指南，不一次展开历史或全部父件。

## 1. 当前目标与用户定义的验收终点

当前目标是完成 Fig.4 路线剪枝真实行为验收，然后提交 Git checkpoint。

用户定义的分支规则：分析完成后，Root 必须选择下一轮目标；若为**假设重设计**，完成假设重设计及编译合同要求的独立审查；若为实验设计或 author 改进，则停在当前分析节点。不得把 Worker 的 `next_action` 当路由命令。

checkpoint 完成后，再评估用户提出的 Operation 通信方案：8 个科学决策主类，加 action/subject/consequence/required_state/independence/input_schemas/not_for 等正交标签；控制层只机械过滤到少量候选，catalog 仍是唯一行动权限。只有评价合理才启动独立 planner。尚未开始该评价或 planner。

## 2. 已完成的真实科学分析

- 实例：`M7-test0`。
- Run：`fig4_route_pruning_acceptance_20260922_1`，`completed`。
- 输出：`fig4_route_pruning_acceptance_20260922_1.output`。
- Operation：`tcad.result.analyze.v1` version 2。
- 冻结 profile：`gpt-5.6-sol / medium / zh-CN`。
- 输入：从 `fig4_retardation_frozen_metrics_20260921_1.output` 的完整即时 producer 投影恢复 30 项；未重跑 TCAD/solver。

正式结果：`overall_verdict=inconclusive`、`claim_allowed=false`；`objective.fig4_mechanism_discrimination` 为 inconclusive。两个 `N_T*K≈1` 点只支持单终态反事实；继续同类 `N_T/K` 微调不能改变总体机制决定。剩余核心矛盾是平衡体内储量与表面/边界历史不可识别，单一材料、480 s 单工况不足。

精确结果和首次 Root 路由事故见 [部署后科学行为验收](evidence/fig4-route-pruning-r2-20260922/DEPLOYED_SCIENTIFIC_ACCEPTANCE_20260922.zh-CN.md)。

## 3. Root 首次判断错误

Root 最初锚定报告的第二时长/去源再退火建议，只检查“现有假设是否被证伪”，未先检查“正式假设集合是否覆盖表面历史竞争解释”，因而错误归类为实验设计并过早宣布 PASS。

该结论已撤回。`inconclusive` 且无 falsifier 不证明 hypothesis portfolio 充分。持久规则已加入 `roles/scheduler/research.md`：当分析提出决策相关竞争解释时，先恢复精确 hypothesis portfolio；未形式化解释→hypothesis proposal/evolution；已形式化但缺判别观测→experiment design；假设/设计充分但实现缺陷→author work。Worker 提供科学事实，不拥有最终路由权。

## 4. 假设重设计的精确请求

选择的公开 Operation：`science.hypothesis.propose.v1`，当时 invoke digest 为 `c41bc55456e1634a987dfd45e574fd8f6d447dd1f10ffedebc67e35d1b58501c`。部署后必须重新 describe invoke 并使用当前 digest，不能盲用本值。

精确输入：

- `problem_frame`: `fig4_continuation_intake_split_2`
- `scientific_foundation`: `fig4_continuation_intake_split_2.scientific_foundation`
- `experiment_results`: `fig4_retardation_execution_20260921_1.result`
- `result_analysis`: `fig4_route_pruning_acceptance_20260922_1.output`, `fig4_retardation_frozen_metrics_20260921_1.output`
- `current_progress`: `fig4_continuation_objective_2`
- `previous_hypotheses`: `fig4_postfinite_hypothesis_evolution_20260921_1.output`

任务边界：核对既有组合是否把“平衡体内储量”与“表面/边界历史”正式化为可独立反驳的竞争解释；保留仍受支持假设，只在模型集合不足时新增/演化竞争假设，并给出区分预测和反证条件。不得设计实验、改 deck、请求 execution/solver。

## 5. P0 阻断：profile 拒绝后的永久 queued Run

首次 Run `fig4_hypothesis_redesign_20260922_1` 冻结 `gpt-6-Astra/high`，平台 Worker 身份为 `gpt-6-astra/high`。`worker_attach` 成功，但 `worker_open_assignment` 在 gateway profile 精确比较处返回不可修复拒绝；Worker 未打开 assignment、未读科学输入、无草稿/输出。

拒绝后 Run 仍为 `queued`。规范化新请求因 `RunSlotBusy` / `UNIQUE constraint failed: runs.operation_digest` 未创建。deadline `2026-09-22T12:58:02Z` 之后 status 仍为 queued；错误路径在 `Runs.open` 前被拒绝，因此 timeout 代码不可达。完整 P0 证据与验收条件见 [P0 记录](evidence/fig4-route-pruning-r2-20260922/P0_WORKER_PROFILE_REJECTION_ORPHAN_RUN_20260922.zh-CN.md)。

## 6. 本地 P0 候选与安装状态

本地候选涉及：

- `src/scidiscovery/agent_execution_settings.py`：模型 ID casefold canonicalization。
- `src/scidiscovery/artifact_agent/interfaces/mcp_gateway.py`：canonical 比较；新 attach 后不可修复 mismatch 立即 `record_failure`。
- `src/scidiscovery/artifact_agent/service/worker_connections.py`：复用比较使用 canonical model ID。
- `tests/operations/test_agent_execution_settings.py`, `tests/operations/test_unified_mcp.py`：大小写 alias、真实 model/effort mismatch、failed 状态与槽释放。

证据：两个拥有者测试文件 `29 passed in 13.22s`；相关 `py_compile` 和全工作树 `git diff --check` 通过；M7 安装 dry-run 通过。

但候选仍不完整：它能防止未来 mismatch 形成孤儿 Run，却不能回收数据库中已经存在、已过 deadline 且绑定死线程的 queued Run。必须增加控制服务启动或显式生命周期协调点的 expired-active reconciliation；不得让只读 `run_status` 偷偷写状态，不得直接改数据库。

2026-09-23 只读核对：`/opt/scidiscovery-m7/site` 不含 `canonical_model_id/worker_profile_mismatch` 候选；`scidiscovery-control.service` active，启动时间仍为 `2026-09-22 20:12:34 CST`。用户尚未确认重新安装。不要把 dry-run 当部署。

## 7. 下一步严格顺序

1. 完成 P0 候选：加入启动/生命周期 reconciliation，覆盖现存过期 queued/running Run，保留失败审计并释放唯一槽。
2. 运行窄测试、真实 proxy/daemon 生命周期测试、安装态验证及独立审查；P0 不通过不得部署。
3. 用户用既有 M7 参数安装并完全重启 Codex；新会话先 `instance_current`，若 unbound 给出原始管理 URL，由用户选择 `M7-test0`。
4. 验证旧 `fig4_hypothesis_redesign_20260922_1` 已转为 failed、精确 reason/diagnostic 可读、同 Operation 槽已释放。不得删除旧 Run。
5. 用上节六组相同科学输入和 canonical `gpt-6-astra/high/zh-CN` 创建新 hypothesis proposal Run；不使用旧 Run 的 `resume_from`/`draft_from`。
6. 按新 Run 返回的 agent_type/profile 启动新 Worker、真实 thread attach、完成封存 hypothesis portfolio。
7. 遵循编译 `review_edge`，使用不同 Agent 完成 `science.hypothesis.criticize.v1`；若正式 verdict 为 revise，只按合同执行限定 revision 和必要复审。
8. 读取正式结果，完成 Fig.4 行为验收记录和 token 报告；不自动进入 experiment design/author/execution。
9. 做最小可信检查并创建 Git checkpoint，不 push、不改写历史。
10. checkpoint 后再评估 Operation 多维分类方案；合理才开独立 planner。

## 8. Git 与文档状态

尚未创建用户要求的 checkpoint。工作树包含大量此前累积的用户/任务改动；提交前必须精确 `git status`、`git diff --check` 和范围测试，checkpoint 将覆盖当前候选与本轮记录，不得把所有 dirty 文件归因于 P0。

当前权威状态入口：

- `docs/plans/README.md`
- `docs/plans/evidence/fig4-route-pruning-r2-20260922/DEPLOYED_SCIENTIFIC_ACCEPTANCE_20260922.zh-CN.md`
- `docs/plans/evidence/fig4-route-pruning-r2-20260922/P0_WORKER_PROFILE_REJECTION_ORPHAN_RUN_20260922.zh-CN.md`
- `roles/scheduler.md` 与 `roles/scheduler/research.md`

历史安装回滚支线已由用户剪枝；不要恢复 `preserve-sqlite`、状态根结构隔离或相关复审。

## 9. Agent 与 token

- `fig4_route_pruning_acceptance_worker`：已完成并正式提交分析；聊天不是科学证据。
- `fig4_hypothesis_redesign_worker`：因 profile mismatch 在 assignment 前被拒绝并已停止；不可复用为新 Run 的科学完成证明。
- Root 精确 token：平台未暴露，**不可观测，未估算**。
- 首个分析 Worker 精确 token：**不可观测，未估算**。
- 被拒绝的 GPT-6 Worker 精确 token：**不可观测，未估算**；未打开 assignment，不把协调调用计作科学分析 token。
- 已知 Root 上下文浪费：一次性预读五份指南、过宽返回 29 项 producer 明细。已在 `roles/scheduler.md` 登记指南按动作懒加载；同一安装版本不重复读取。

不要从旧聊天、functions store、子 Agent completion 文本或隐藏 workspace 恢复科学事实；新会话只从正式 Run、Artifact、绑定和本 handoff 的定位符继续。
