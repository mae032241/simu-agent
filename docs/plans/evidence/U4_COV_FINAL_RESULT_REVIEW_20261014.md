# U4 cov 真实场终态独立验收

结论：**整体 U4 未通过，科学目标未宣告完成，交付未获资格**。本记录只读核对实际终态和封存原件；未运行测试/模型、修改生产或冻结场次、重试 audit、恢复执行或增加预算。后续 adapter 修复不会改写本场结果。

## 已核对的本场事实

[final-result.json](../../../../../.trial/rootless-u4-cov-20261014/final-result.json) returncode=2、controller.status=`closeout_unresolved`、reason=`delivery_resolver_unavailable`、source_cutoff=7、goal_completion=`not_asserted`。driver_wall_seconds=2919.831；自动错误重试、自动 correction acknowledgement 和 budget increase 均为 false；冻结输入未变。

terminal observed tokens=4590117，由 input4519526+output70591组成；cached_input4086144 已在 input 内，不重复相加。uncached input+output=503973。原 meter unknown_steps=[]，总体 observed_token_overrun=0；这不是对实时硬 cap 或模型费用的额外资格。

七个 sealed 节点均有原 science-output/result-identity、returncode=0 的 native outcome、thread ID 和 observed_group_cleaned：

| 节点 | 原角色/结果 | observed tokens | 注册实验 |
| --- | --- | ---: | ---: |
| 001 | H，新计划四机制 | 270432 | 0 |
| 002 | W，h001.m1，review | 992462 | 5 |
| 003 | A，audit 请求 run-2 | 174998 | 0 |
| 004 | A，接收 audit unknown 后 continue_w | 150178 | 0 |
| 005 | W，h001.m2，review | 1578305 | 8 |
| 006 | A，continue_w，最新 recommendation run-2 | 259853 | 0 |
| 007 | W，h001.m3，review | 1163889 | 13 |

独审核对三 W 的26个 accepted.json 对应 completed.json 均为 `known_success`，各原 scope 绑定 m1/m2/m3；此计数是受管执行成功，不证明26种科学上不同方法、审计通过、目标 shift 泛化或任务整体完成。

## 覆盖及未覆盖项

- 本场真实观察到 current14 sealed H→W 注册实验→A→后续 W/A 的机制推进，原终态未再出现上一场 lineage/order 或 context scope 失败。
- 所有 W 原文均 `stage_intent=review`，七个 stage 均没有 continuation/native-intent 原件。**未观察真实 fragment continue/new_context 切片发生**；此前无模型 namespace 资格不能据此转成真实模型片段验收 PASS，也没有 same_session 资格。
- W002 stage-end reason=`worker_requested`，W005=`target_tokens_reached`，W007=`reserve_reached`；这些 host reason 与原 raw 分开保存。软边界没有承诺单片 token 零超额，本场总体用量仍在声明总预算内。
- H 的四机制分别为 adaptive OMP、convex recovery、operator uncertainty、anchored batch self-calibration。只有 m1–m3 存在 W scope/实验原件；**m4 未探索**。W007 后没有最终 A 评估节点，因此不声称三机制均完成最终科学审查。

## Audit 缺陷与 closeout

A003 [audit outcome](../../../../../.trial/rootless-u4-cov-20261014/instance/native-evidence/003/candidate-audit/outcome.json) accepted=true、run-2、unknown、`delivery_resolver_unavailable`，未获 binding；A004 沿原失败 receipt 继续科学路由，未伪造 audit success。

[control-ledger/000002.json](../../../../../.trial/rootless-u4-cov-20261014/instance/control-ledger/000002.json) 记录 closeout_begin、source_cutoff=7、first_step=8、stop_reason=`delivery_resolver_unavailable`、mode=`export_only`、delivery_sources=null；下一原 ledger 记录 phase=paused/reason=closeout_unresolved。这证明同一 resolver unavailable 已在最终 source preparation 复现，closeout A008/框架交付没有取得合格输入。

[独立 audit 诊断](U4_COV_AUDIT_UNKNOWN_REVIEW_20261014.md) 记录当前 cov_delivery guard 的隔离分支 Path/bytes 类型缺陷，以及框架自动追加 protocol 输入的事实。本场两个阶段的泛化 note 一致；因 `_call` 未保存 leaf stderr，精确 TypeError 仍是代码路径推断，不伪称现场直接保存了同一 traceback。

## 实际 task 提交与 A 推荐不是同一资格

[runs/submitted.json](../../../../../.trial/rootless-u4-cov-20261014/instance/runs/submitted.json) 原 task harness 实际提交 run17、leakage_flag=false。最新 sealed A006 candidate_recommendation 为 run-2。两者不同，必须分别保留；task harness 原提交及其审计字段不能替代框架 audit receipt、最终 A 选择、精确交付 binding/confirm，也不建立不可见 target 测试成功。本次没有读取模型、隐藏测试或 reward 原件。

## 证据冻结与收口

- final-result SHA256：`37591e46058c8e2e741e68c00adb2ccd3ff0c76e5d34658a3e2d335cd5cc56a3`。
- closeout_begin 原 ledger SHA256：`0c7f7fb687cb9feb8576af8f9cfa45c13edb97c5dcdad88936b579eaef04837c`。
- task submitted.json SHA256：`f4e31b21674726843f2bb2e49f489c29d06c4d51c18f6219284ece2fcbaa8e93`。

本场证明部分真实科学/执行链可运行并保留26次受管成功原件，**不能授全 U4 PASS**。fragment、未探索 m4、未获框架 audit/closeout delivery、A 推荐与 task 提交差异均作为限制保留。旧场次停于原终态；修复后的能力需另行取得实际隔离入口资格，任何新真实场或恢复均按后续授权处理。
