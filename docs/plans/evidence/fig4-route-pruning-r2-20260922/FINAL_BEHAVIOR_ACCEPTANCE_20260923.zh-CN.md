# Fig.4 路线剪枝：2026-09-23 现场行为验收

- 实例：`M7-test0`；验收范围仅为既有分析之后的分支选择、假设组合提案及编译合同要求的独立审查。
- **行为结论：纠正首次误路由后，本次限定分支验收通过。** 原分析的 `inconclusive` 和首次错误地选择实验设计仍保留为负面历史；本次通过不意味着 Fig.4 机制已识别、绝对形貌合格或总体科研目标完成。
- 当前事实来源是以下 completed Run 的正式输出及 `scheduler_signal`，不是 Worker 聊天或本文件对科学内容的重新判定。早期现场事实见[2026-09-22 部署验收](DEPLOYED_SCIENTIFIC_ACCEPTANCE_20260922.zh-CN.md)，P0 原始事故见[事故记录](P0_WORKER_PROFILE_REJECTION_ORPHAN_RUN_20260922.zh-CN.md)。

## P0 控制生命周期与安装边界

原 `fig4_hypothesis_redesign_20260922_1` 已通过公开 `run_record_failure` 转为 `failed`，reason 为 `Run deadline expired after attached Worker profile mismatch prevented assignment opening; no scientific work or sealed result was produced.`；公开 `run_status` 保存 `framework_failure` / `run_timeout` 诊断，且没有封存科学输出。该历史 Run 不作为 `resume_from` 或 `draft_from` 使用。它的 `run_timeout` 是本次明确超时处置，不冒充一次已在生产触发的新 `worker_profile_mismatch` 诊断。

安装态 `/opt/scidiscovery-m7/site` 含模型 ID canonicalization、attach 后不可修复 profile mismatch 的失败终态、`worker_profile_mismatch` 精确诊断类别，以及控制服务启动前的 expired-active 对账；`scidiscovery-control.service` 和 `scidiscovery-approval-ui.service` 自 2026-09-23 11:01:28 CST active。`/etc/scidiscovery-m7/agent-settings.json` 的 `defaults.model` 为 `gpt-6-sol`。新 Run 能在同 Operation 唯一槽中创建并完成，证明原现场占槽已解除。

最终 P0 补丁的独立只读复审未发现 P0/P1/P2 缺陷：model/effort mismatch 的控制失败、落库诊断、公开 summary/events、未知类别降级和后继槽释放均经定向测试检查；两批共 12 项通过，`git diff --check` 通过。审查者核对了关键安装文件与工作树 SHA-256 一致、文件安装早于服务启动，并经已安装 proxy 读取三工具入口。**边界：**没有在生产实例故意注入新的模型不匹配，真实 daemon 测试使用隔离 catalog，未跑全 dirty worktree 测试或 CI；这些不作为已验证事实。

## 假设分支的正式结果

新 proposal `fig4_hypothesis_redesign_20260923_1` 使用原 handoff 的六组精确输入，未继承旧失败 Run；当前编译 `science.hypothesis.propose.v1` digest 为 `e0bd24c67331347a372f93ff85c83eb09dc2a7a0cb31a98d9a5c558ae08a2d1e`，冻结 profile 为 `gpt-6-astra/high/zh-CN`。Worker 经真实线程 attach 后完成，正式输出为 `fig4_hypothesis_redesign_20260923_1.output`，`state=completed`、`scheduler_signal.verdict=pass`。

proposal 保留三项原 `hypothesis_key`，不凭空新增机制：平衡体内 Langmuir 储量、固定单指数表面供给、近检测限尾部观测地板。它纠正“瞬时平衡储量自带独立历史记忆”的旧表述，分别为储量闭合和固定单指数边界给出不依赖竞争者胜出的反证条件，并把观测地板收窄为局部尾部资格问题。此 `pass` 仅表示提案交付完成，不证明机制、参数或执行资格。

按 compiled `review_edge`，不同 Agent 执行 `science.hypothesis.criticize.v1`：`fig4_hypothesis_critique_20260923_1` 为 `completed`，正式输出 `fig4_hypothesis_critique_20260923_1.output`，冻结 profile `gpt-6-sol/medium/zh-CN`；正式 `disposition=ready_for_experiment`、三项逐项 falsifiability/finite_discriminability/physical_plausibility 均为 `pass`，`scheduler_signal.verdict=pass`。这是对假设陈述和可判别性的独立审查，**不是**实验设计、机制资格、执行审批或外部求解授权。没有启动 experiment design、author、execution 或 solver。

仍未解决的科学问题是单一 InGaAs 终态下平衡储量与一般表面/边界历史不可识别。六掩码复核仅支持一个位于 `N_T` 网格上边界的相对联合收益点；M0 的 b2、width 与 aligned-shape 残差仍在，不能据此选定材料参数。既有单指数表面臂的宽度/形状权衡削弱该具体成员，不排除一般历史；尾部地板不能解释检测限以上联合形貌差距。独立表面历史、另一工况/InAlAs、原始 SIMS 与点级不确定度、检测限标志冲突、离散收敛和成功的完整执行回执尚缺。原 execution `failed` 不因 PLX 后处理或本次 review 被改写。

## 框架评审归属与 token

[R2 计划的独立审查](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_SOL_REVIEW_20260922.zh-CN.md)为计划级 PASS；[R0](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R0_20260922.zh-CN.md)至[R3](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R3_20260922.zh-CN.md)实现复审原件仍各自保留当时的 REVISE，不因本次现场行为通过而追改。后期 `preserve-sqlite` 回滚支线已由用户撤回，见[撤回记录](IMPLEMENTATION_REVIEW_R3_STATE_ROOT_SEPARATION_ROOT_20260922.zh-CN.md)；本次没有重开该支线。

Root、proposal Worker、critic Worker 与工程独立审查 Agent 的精确 token 均无可唯一归属的原生记录，**不可观测，未估算**。未做同模型/同任务的 Root/Worker token A/B，不从耗时、字符数或代理会话换算 token。

## 检查点范围检查（早期记录）

`git diff --check` 通过。按当前源码修正过时测试断言/夹具后，安装脚本 73 项、Agent 合同 130 项、分析来源范围 27 项、case mapping 3 项以及安装态测试文件 12 项分别通过；其中后两组受 768 MiB 进程树采样守卫保护，峰值约 125/230 MiB。全量检查并未完成：先前运行显示更多旧断言，逐项修正后尚未全量重跑；扩大到后续测试文件的受限运行再次被中止，用户报告 WSL 崩溃。该采样守卫不是内核级硬隔离，不能据此宣称后续重跑安全。不得把这些定向结果记为全量测试或 CI 通过。当前尚未创建 Git checkpoint，也未 push。

以上是资源故障后的阶段记录，不代表最终回归状态。后续以单进程、顺序运行、512 MiB 进程树采样守卫完成源码测试：`1731 passed, 1 deselected`，耗时 858.19 秒，采样峰值 481568 KiB；另在一个 pytest 进程中通过 3 项安装态 wheel/MCP 定向检查。首次全量运行的 5 个失败经定位、修正后，上述最终全量运行 0 失败。未运行全部安装态测试矩阵；采样守卫也不是内核级硬隔离，不宣称 CI 或所有安装组合通过。

本文件随本地 Git checkpoint 一同封存；未 push。checkpoint 仅封存工程工作树及其限定验证，不改变科学结论。checkpoint 后才评估用户提出的 Operation 多维分类方案。critic 的 `ready_for_experiment` 是科学建议，不是本轮自动进入实验设计的命令。
