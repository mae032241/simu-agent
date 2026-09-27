# 假设反馈收尾独立审查

日期：2026-09-16。结论：**两处控制层收尾增量 PASS；B1/B2/B3 的既定有限行为验收 PASS；科学产物存在两个数值问题，科学质量不能据此判为 PASS；生产部署与真实研究闭环未验收。**

本次只读审查代码、已有测试日志、Root 受控读取后保存的状态快照与启动收据，仅新增本报告；未运行测试、构建、模型或生产操作。科学内容仅取自 `state=completed` 的 `sealed_output` 与同一响应的 `scheduler_signal`，不采用 Worker 聊天。

## 范围与文档归属

本报告是绑定下列源码与证据的审查账本，承接[独立实现审查](HYPOTHESIS_FEEDBACK_IMPLEMENTATION_REVIEW.zh-CN.md)后的两个收尾点。此前 A/B 实施和原工作台改动不重新纳入本轮增量，也不因本报告获得额外资格。[计划](../HYPOTHESIS_EXPERIMENT_FEEDBACK_PLAN.zh-CN.md)保留验收标准；[CLOSEOUT](../evidence/hypothesis-feedback-closeout/CLOSEOUT.zh-CN.md)拥有实施过程、失败与资源记录；本报告拥有独立复核结论。保留原审查，不改写历史；本报告补充最后的有限行为结果，不替代生产资格记录。索引与 CLOSEOUT 的进度文字由其维护者同步，本次仅写本报告。

## 控制层源码：PASS

- `result_materialization.py:95` 为 ScientificReview 增加 `blocked -> blocked`。`research_cycle.py:71` 原本已允许该 verdict；没有放宽 Schema，也没有改写科学结论。
- `materialize_summary_handoff` 只从正式 payload 投影运输字段。`runs.py:1126` 的精确 reviewer 匹配仍检查 completed、原 reviewer、精确 subject、兼容输出与 accepted verdict；`blocked` 不满足 `accepted_verdicts=("pass",)`。Root 的下游 admission 继续调用该判断。
- `test_agent_contract_alignment.py:815` 不再手填 handoff，经过 Worker 提交、Root 正式读取，确认 blocked 精确匹配为真、pass 匹配为假，并将原件作为下一轮 `current_progress` 读取。可选 objective/context 组合覆盖五种合法 verdict。
- `general_science_components.py:477` 将 finalizer identity 改为 `general.result-finalizer.v3:blocked-review`。可达 ComponentSpec 进入 Operation 编译摘要，记录中共有 [16 个摘要变化](../evidence/hypothesis-feedback-closeout/digest-changes.json)。已封存输出仍按既有 Operation version/输出类型兼容读取；旧在途 Run 和原样恢复不能静默换用新摘要。这是明确的契约变更，不能称为在途无缝升级。

已读取现有日志：[源码定向](../evidence/hypothesis-feedback-implementation/check-1789541989950594729.log)为 `45 passed in 36.62s`；[隔离 wheel](../evidence/hypothesis-feedback-implementation/check-1789542717703608083.log)为 `12 passed in 58.53s`。审查者未重跑；这些结果不能扩展成全套回归或全部安装环境通过。

## 行为证据与隔离边界

[live_probe.py](../evidence/hypothesis-feedback-closeout/live_probe.py) 在独立 `/tmp/scid-feedback-closeout` project/state 中登记人工合成历史输入。foundation approval fixture 仅接受本实例精确 foundation、`scientific_foundation` kind、`approve` option 和 `science.evidence.qualify.v1` provider operation；没有写入人工决定，没有调用生产审批或外部执行。该 fixture 不是审批安全性的验收证据。新 proposal/critic/design 没有预制为 fixture。

请求经过 preflight 的 normalized request 再 invoke；真实 CLI 按返回的 compiled agent_type 和请求 profile 运行。[launch_probe.py](../evidence/hypothesis-feedback-closeout/launch_probe.py)采用目录声明的 Run timeout 与既有 1 GiB 进程树守卫。请求配置是 `gpt-5.6-sol / medium / zh-CN`；这不是服务端实际模型或 reasoning 消耗的观测证明。

[Run 矩阵](../evidence/hypothesis-feedback-closeout/records/run-matrix.json)对应 8 个 Run：7 completed、1 failed。B1 design 的 `diagnostic_events` 保留一次 output_context 拒绝：新设计须使用 `validation_intent`；随后同 Run 修正完成。其余六个 completed Run 的 rejection_count 为 0。初次 B1 proposal 因外层 165 秒测试限制中止而 failed，不能计为科学成果；后续精确 resume 的预检显式 `max_attempts=2`，没有改写原失败记录或原 Run 时间预算。

读取的 9 份 [launcher receipts](../evidence/hypothesis-feedback-closeout/records/launch-receipts/)含一次领取前启动失败、一次外层终止及七次成功启动完成；起止区间不重叠。最大记录 RSS 为 835,932 KiB，即 816.34 MiB，所有 `memory_limit_exceeded=false`，且 `externally_sandboxed_debug=false`。该遥测说明本地进程资源，不证明远程模型耗时、科学成功或无原生命令错误。

| 案例 | 已读正式证据 | 有限结论 |
| --- | --- | --- |
| B1 有效反例 | [proposal_retry](../evidence/hypothesis-feedback-closeout/records/b1-proposal_retry-status.json)、[critic](../evidence/hypothesis-feedback-closeout/records/b1-critic-status.json)、[design](../evidence/hypothesis-feedback-closeout/records/b1-design-status.json) | **PASS**。旧 `y=2x` 因约 1 的偏差被淘汰；新仿射与阶梯候选在整数点仍不可区分。critic 保留此限制，design 转向 `x=0.25` 的 1.5/1.0 差异预测与同轮控制，未机械重复无判别力扫描。 |
| B2 数值失败 | [proposal](../evidence/hypothesis-feedback-closeout/records/b2-proposal-status.json)、[critic](../evidence/hypothesis-feedback-closeout/records/b2-critic-status.json) | **PASS**。明确有效 points/reference_measurements 为空、陈旧预览无效；保留线性候选，不把 Newton 失败当物理反证。饱和候选明确为待检验竞争解释，critic 要求有效独立观测；没有强制进入 design。 |
| B3 现有观测不可辨识 | [proposal](../evidence/hypothesis-feedback-closeout/records/b3-proposal-status.json)、[critic](../evidence/hypothesis-feedback-closeout/records/b3-critic-status.json) | **PASS**。保留 `y=2x` 与 `y=x+x²`，明确 x=0、1 的观测不能选赢家，指出 x=2 的 4/6 差异预测作为补充条件。未把历史 analysis 当新增测量。 |

以上只覆盖计划要求的 B1 三步和 B2/B3 两步。单次合成实例不证明开放研究可靠性或生产 Fig4 闭环。三个 critic 的 `ready_for_experiment` 也不等于候选已被观测确立。

## 科学内容问题：须单列，不能归因于控制层补丁

**S1：B1 设计漏计控制端输入误差。** 位置：`b1-design-status.json` 的 `/sealed_output/payload/proposals/0/prediction_tests/0/expected_result`，并重复进入 identifiability 与 validation 条件。设计允许两端 x 各有 ±0.005 误差，但写 `U_D=0.02+0.02+2*0.005=0.05`。对固定仿射模型，`D=2(x₁-x₀)+ε₁-ε₀`；没有误差抵消契约时，最坏界为 `0.02+0.02+2*(0.005+0.005)=0.06`，应覆盖 `[0.44,0.56]`。例如实际 x₁=0.255、x₀=-0.005，读数误差分别 +0.02/-0.02，可得 y₁=1.53、D=0.56：均符合门槛却被原 D 区间错误排除。未来若消费该设计，应由匹配的独立科学审查/修订处理；本报告不改封存产物。

**S2：B2 饱和候选 contrast 区间遗漏内部极值，critic 未指出。** 位置：`b2-proposal-status.json` 的 `/sealed_output/payload/hypotheses/1/predictions/1/expected_outcome`。模型给出 `C(s)=y(2)-2y(1)=-4s/((1+s)(1+2s))`，s∈[0.25,1]。导数符号取决于 `-(1-2s²)`，最小值在 s=1/√2，而不是端点；精确模型区间为 `[8√2-12,-8/15]≈[-0.686292,-0.533333]`，原文 `[-0.667,-0.533]` 过窄。叠加原文正确给出的 ±0.06 观测 contrast 误差后仍与线性的 `[-0.06,0.06]` 分离，因此不推翻 B2“数值失败不作机制反证”的行为验收，也不消除该科学数值缺陷。

两个问题由 Worker 科学内容产生；本次机械 handoff 映射与 identity 不生成这些数值。不能以控制层测试通过宣称全部预测和误差预算正确，也不应在控制层增设专用科学裁决来掩盖问题。本轮未进行广泛科学审查；未列出的问题不等于不存在。

## 部署与资格结论

**未部署、未完成生产现场验收。** 隔离 wheel 日志只支持该安装路径的定向工程检查。没有新测量、solver 执行、生产人工审批或 Fig4 接续证据。B1 是尚未经过 object review 的 design intent，且其 signal 明确缺 execution_context 与匹配方法能力确认；不能视为可执行计划或执行授权。B2/B3 停于 critic 符合本轮验收范围。

## 审查时源码指纹

SHA-256 为读取到的整个文件字节，限定本报告所审快照；重叠文件仍可能包含此前 A/B 或工作台变更，指纹不扩大增量范围。

| 文件 | SHA-256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/service/result_materialization.py` | `c166e16f39bb8d38628c7fd4f4c8178f044a116372ab9855e598741035f3cb6d` |
| `src/scidiscovery/general_science_components.py` | `b38b342d02c4104dc03fc22c3717e506634dcd6ad4124cf1c992cdbd3e945bcc` |
| `tests/operations/test_agent_contract_alignment.py` | `2a4ec6c4bcc7658aaf7352c2ebc89b736bdac304ae82b4856a3d03107e72451b` |
| `docs/plans/evidence/hypothesis-feedback-closeout/live_probe.py` | `ef593d5f5bd93af1694ba13055408b73035f94bc330cad4189ee132c468537f5` |
| `docs/plans/evidence/hypothesis-feedback-closeout/launch_probe.py` | `223acf278523870e53adc43c1dd4e471e9b477e854c50d9d96dd68c240f57227` |
