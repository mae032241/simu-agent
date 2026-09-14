# 用户文本接入：安装后的真实接续验收

状态：2026-09-14，A10 通过。两个不继承父会话历史的真实科研 Agent，分别完成设计与独立审查，并封存成果。一次设计输出拒绝在同一 Run 内修正；没有预检或 invoke 拒绝，没有失败或超时 Run。原生命令遥测为 `unobserved`，不声称所有本地命令都无错误。

## 记录归属

当前工程状态由[实施记录](IMPLEMENTATION.zh-CN.md)和[计划索引](../../README.md)承接。本文件及[现场机器记录](live-acceptance-20260914.json)拥有本次安装与科研接续事实。冻结 R2、独立计划/实现审查、先前测试账本和 verification-summary 保留其当时证据；不把本次结果反写为先前已经部署，也不改写科研原件。

## 实际路径

1. 用户安装重启后通过实例管理页重新绑定 `M7-test0`。服务从 11:26:31 UTC 起处于 active；按实际服务 `PYTHONPATH` 核对的 14 个 Python 文件与 scheduler 角色文件全部匹配已审查候选。公开目录的 25 个 Agent 均有 `user_context`。
2. 用 `artifact_ingest_text` 将用户此前关于 Fig4 深度、形状、前后平台和 decade MSE 权重的原话登记为 `fig4_user_profile_shape_priority_1`。返回原文记录 revision 1，199 字节，`source_text/opaque`、UTF-8 媒体类型和 `source_origin=user_via_scheduler`。设计和审查后仍是同一 revision 1；没有另造原文摘要或把原话改写成科学事实。
3. 从 `fig4_dimensionless_initialization_plan_2` 的直接设计意图父件追溯原始 objective、foundation、hypothesis 与 critic；显式绑定原总体目标、历史计划与审查、相关已有结果和分析。设计任务 `fig4_user_context_continuation_design_1` 的原请求先通过 preflight，再以相同请求 invoke；全新编译设计 Agent 打开受控 assignment 并提交。
4. 设计封存为工程设计意图。根据公开支持目录将其确定性展开为 `fig4_user_context_continuation_plan_1`；未由 Root 编写或改动科学计划。
5. 沿该支持 Operation 声明的 review_edge 创建 `fig4_user_context_continuation_review_1`，显式绑定同一用户原文和新计划，并将原总体目标作为相关进展保留。工程计划使用自己的工程目标；原总体研究目标继续作为背景输入，不替代工程目标。新的独立审查 Agent 不继承设计者或父会话历史，完成封存并给出 pass。
6. Root 在两项 Run 都 completed 后，通过受控 `run_status` 读取正式 payload 的所需 JSON Pointer 与 scheduler_signal。审查原件的 `/evidence` 将 `user_context` 标为 `user_statement`，`/findings` 明确评价这份原文的作用与证据边界。验收结束时实例内无 queued/running Run；没有新建 TCAD 执行。

## 封存结果支持的结论

设计的 `/priority_rationale`、`/proposals/0/objectives`、`/proposals/0/value_assessment`，以及审查的 `/summary`、`/findings`、`/global_confounders` 均明确处理了用户补充：保留现有两案例初始化任务；后续 480 s 科学比较优先考虑有证据支持的扩散深度、逐点曲线形状、前平台和具备合格证据的尾平台，整体 decade MSE 只能是辅助诊断。补充说明表达用户优先级，不提供新的定量证据或不确定度模型。

独立审查认为当前两案例任务有足够输入可供 author 实现，且无须为此次说明增加案例。当前结果仍只是计划与审查，不证明初始化成功、480 s 收敛、Fig4 拟合成功或微观机制成立。后续具体评价指标、阈值和不确定度处理仍须在相应科学计划中定义。科学依据以机器记录中的封存结果投影和原始语义成果为准；本文件不另立科学判断。

## 耗时与异常

| 项目 | 新设计 | 独立审查 |
| --- | --- | --- |
| 创建至封存 | 355.225 秒 | 273.684 秒 |
| 打开任务至封存 | 335.973 秒，约 5 分 36 秒 | 251.828 秒，约 4 分 12 秒 |
| 提交次数 | 2 | 1 |
| 输出拒绝 | 1，随后同 Run 修正 | 0 |
| 记录到的 Worker 工具错误、Run 超时 | 0 | 0 |
| 原生命令观测 | unobserved | unobserved |

唯一提交拒绝发生于 11:34:43.640556 UTC，规则 `experiment.design.intent_closure`，phase `output_payload`，正文 `engineering intent requires only an engineering objective`。15 秒后同一 Run 完成，不涉及更换输入、重试新 Run 或增加预算。

源码定位：`src/scidiscovery/artifact_agent/schema/experiment_intent.py` 的 `ExperimentDesignIntent._portfolio_intent_is_complete`。工程分支在 `objective_key` 非空、所选假设非空、或 `engineering_objective` 为空三种情况中任一种发生时，抛出同一个模型级错误。历史 `fig4_solver_feasibility_design_1` 已有相同拒绝，因此不能归因于新增用户原文端口。此次错误发生在输出模型检查；不是提交阶段重新否决已准入输入。

**仍存在诊断精度缺口：**公开记录只给出 `$.payload`，没有指出三项条件中到底哪项冲突。仅凭现有拒绝记录不能断言 Agent 首次写错了哪一个字段，也不能据此宣布这条互斥规则的科学必要性已得到证明。本次保留错误，不为完成验收顺手修改该规则。

Root 安装探针另有一次路径假设错误：首次按解释器 purelib 查询，未找到服务安装文件；改为读取 systemd 单元公开的 `PYTHONPATH` 后 15 文件全部一致。这是核对脚本的定位问题，不是服务缺库或部署失败。初次文件发现命令也使用了不存在的 glob，随后定位到实际 deploy 目录；这些只读探针错误未影响科研任务。

## 验收边界与下一节点

A10 要求的原文登记、历史节点绑定、真实 Agent 完成交付、下一任务显式读取同一原件及独立判断均已观察到。用户意见不替代独立审查或执行批准；原研究对象和旧审查仍保留。两轮串行，没有运行全量测试或新求解器，没有源码变更。

先前 13 项基线测试失败和 Hardened 成果提交限制未在本次复测；此前最大输入边界、失败草稿接续及 Worker 复用仍由原有定向测试承担。本次不能证明 token 总量下降或普遍加速，也不能证明完整本地命令日志覆盖。

当前科学停点为新完整方案及其 pass 审查。下一项科研工作可按目录进入当前两案例项目的 author 和独立实现审查；外部执行仍需其编译审批流程。本轮未自行启动该后续工作。
