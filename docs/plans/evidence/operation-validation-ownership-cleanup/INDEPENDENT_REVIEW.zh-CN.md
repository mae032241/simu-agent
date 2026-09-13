# 校验职责清理独立复审

2026-09-13。结论：**复审不通过，不能认定已清理干净。** 原六份 Fig.4 失败提交的重放结果仍成立；它不能证明所有投影和消费路径都已一致。

## 范围与独立性

- 一名无父会话历史的独立工程审查者检查实际注册的 Operation、模型、上下文校验、来源投影、自动补全和下游消费。主代理另查异常传播与验证记录，并统一进行低资源串行复现。
- 基准为 `/tmp/scid-validation-ownership-baseline-ac2nlb23` 的清理前 Python 快照，保留此前兼容性修改；HEAD 为 `be5da77acdbf98054e0b096fc4e940de560d4ba1`。当前 `SOURCE_MANIFEST.json` 的20项生产文件摘要全部匹配。
- 本轮没有改生产源码，没有部署、操作生产实例或执行求解器。以下 MCP 是隔离测试运行时，科学载荷为既有合成 fixture，不构成生产科学结论。

## R1 / P2：过窄的动态来源枚举仍拒绝合法引用

位置：`src/scidiscovery/operation_contract.py:530`，实际提交入口为 `service/run_outputs.py` 中 `_validate_payload_schema`。

`science.evidence.audit.intake.v1` 的 `scientific_intake` 是实际绑定且可读的被审对象，端口用途为 `prior_signal`。新的 `_evidence_audit_context` 接受对该对象的引用，动态 `/evidence/source_key` Schema 却仅纳入 `evidence_inventory` 和工具来源。

实际 MCP 对照：

1. 提取完成后，审查的 preflight 与 invoke 成功。
2. `checks[].evidence_keys=["scientific_intake"]`，并添加可选的 `evidence` 条目，定位被审对象中的字段。
3. 提交遭拒：`$.payload.evidence[0].source_key`、`runtime.schema`、`Supported values: ["source_material"]`。
4. 同一 Run 仅删除可选 `evidence` 表，保留相同的检查引用，提交 completed。

这会使可选定位信息成为误阻断。`science.evidence.audit.v1` 存在同类声明；其他带 `prior_signal` 被审对象的审查入口也需用实际编译的投影核查，本轮没有逐一动态复现。

最小修正：在现有合同投影与上下文检查间统一可引用的绑定范围，去掉过窄的枚举限制；保留真正未绑定来源的负例。不能要求 Agent 改抄其他来源来绕过问题。

## R2 / P2：引用放宽后，自动补全可能静默选择冲突来源的第一项

位置：`plugins/tcad_artifact/tcad_artifact/analysis_bindings.py:126`、`result_analysis.py:443`；通用分析的相同解析缺口位于 `plugins/curve_score/curve_score/science_operations.py:634`。

分析可合法重复引用一个来源的不同位置。本轮同时删去了旧的重复键限制及 locator 重复别名要求，剩余冲突检查仅比较 `source_references` 表内的条目。

实际 TCAD MCP 对照在两个已绑定、名称分别为 A/B 的输出文件上复现：

- 同一 `raw_evidence` 键，两行均定位 `solver_outputs_001` 的不同位置：completed，符合预期。
- 同一键，两行分别定位 `solver_outputs_001:row1` 和 `solver_outputs_002:row2`：也 completed。封存结果却只有 `raw_evidence → solver_outputs_001 / output A` 一条自动生成的来源映射。

原因：finalizer 根据第一行产生映射，第二行冲突时直接跳过；上下文检查优先采用已生成的映射，后续 locator 指向另一个输出的事实被忽略。此复现证明输出文件身份存在歧义，没有声称这些合成文件属于不同科学案例。不同案例下会有同类风险。

这是删除后暴露的回归。最小修正应消除控制层自动推断的歧义并保留真实来源冲突，继续允许同源多位置、直接绑定引用和局部 locator；不得恢复“重复引用一律拒绝”或强迫 Agent 自建第二张来源表。

## R3 / P2：明确的工程故障分类和原因仍被外层覆盖

位置：`src/scidiscovery/artifact_agent/service/runs.py:966`、`:539`。

TCAD `_input` 与 `_capability_snapshot` 已分别抛出 `integrity_failure`、`admission_defect`。但 `_validated_candidate` 的通用 `except Exception` 把 finalizer 抛出的 `RunCheckerError` 再包装为 `checker_failure`；`submit` 随后将 reason 固定写成 `Run validation framework failure`。

对实际 RunService.submit 进行两项 finalizer 边界故障注入，输入分别为上述两类已声明工程错误，最终均为：

```json
{"state":"failed","reason":"Run validation framework failure","diagnostic":{"category":"checker_failure","code":"checker_failure","repairable_by_output":false}}
```

此次新增测试只直接测试底层三个输入 helper 故障，未覆盖它们经过提交层的传播，因此漏掉此缺陷。最小修正：透传已分类错误，并持久保存其明确、有界的原因；未知异常继续作为工程故障。不要要求科学 Agent 修改输出解决这些故障。

## R4 / P2：TCAD 缺口提交仍丢失具体可纠正原因

位置：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:75`、`:631`。

author 缺口中的 `affected_work[].plan_locator` 指向不存在的计划字段时，底层明确报告 `gap plan_locator must be an existing JSON pointer in experiment_plan`。`_protocol_error` 对无 details 的 SemanticRuleViolation 只保留外层通用消息；最终封装也无法恢复已丢失的信息。

实际 author MCP 提交返回 `$.files`、`TCAD implementation gap is invalid`，没有指出真正的 locator 原因。这条拒绝本身有确定的引用错误依据；缺陷在于丢失纠错信息。最小修正：复用已有有界语义错误投影，保留真实原因及受影响位置，无需新增校验或角色。

## 已核查且未发现本轮删除破坏的边界

独立审查 producer 与精确父链、审批冻结对象集合、TCAD 原 plan/review/package/manifest 对应、输出摘要与声明身份、显式案例映射，以及计算记录的 receipt、请求、来源和结果证明仍有实际消费检查。参数 source catalog 仍承载参数观察所需的科学来源元数据，不能仅因是一张表就删除。

独立审查另记录一个未确认疑点：hypothesis revision 的 `change_request` 可读但未列入来源校验上下文。其是否允许作为科学证据存在声明意图问题，未列入确定缺陷或此次必要修正。

## 复现证据与限制

可重复的探针保存为 `review_probes.py`，仅用于手工指定运行；不会加入默认 pytest 收集。命令形态为：

```bash
python docs/plans/evidence/operation-validation-ownership-cleanup/check.py \
  python -m pytest -q -s -c pyproject.toml \
  docs/plans/evidence/operation-validation-ownership-cleanup/review_probes.py
```

原始运行文件位于 `/tmp/test_validation_cleanup_independent_probe.py`，已将最终版本原样复制至本目录。探针故意断言期望的正确行为，因此修复前预期为5项失败、1项同源重复引用正例通过；没有为得到绿色结果修改生产代码。

- `check-1789256299801734147.log`：R3，两种分类均丢失，2 failed，测试2.38秒。
- `check-1789256440820508767.log`：R1、R4，2 failed，测试2.39秒；R1同 Run 删除可选表后的提交成功。
- `check-1789256587282170845.log`：R2，同源正例通过、异源冲突错误接受，1 passed / 1 failed，测试2.59秒。
- `check-1789256542454245039.log`：首次R2探针漏写已有 fixture 所需 title，导致结构拒绝；已修正探针并保留日志，不计作产品缺陷证据。

所有探针串行，512 MiB地址空间/进程树限额，最高观测121.4 MiB，无超限终止。没有跑全量或压力测试，没有做安装后验收，也没有动态执行全部50项 Operation。

此次结果修正“已清理完成”的范围判断：原内部来源重复登记已删除，动态 Schema、自动补全与异常传播仍有上述确定缺口。
