# 分析续接最小增量：独立实施符合性检查

日期：2026-09-12。结论：**PASS（当前源码的有界符合性检查）**。审查发现的一项新增输入上限已修正，当前没有未关闭的必要正确性问题。该结论不替代仍在完成的测试、安装 smoke 或真实 Agent 性能验收。

## 1. 精确范围

依据通过的 `PLAN_R1.zh-CN.md`，SHA256 为 `e30e39e1e476b5e3ae7d90a7ef2e011f69ec95c4fc8ef78a2cd23c626f20b1ed`，只检查本轮 `implementation.patch` 与必要相邻调用代码，没有开展新的系统审计。

初始送审 patch SHA256：`9374946374197b593da16b31d39d8e34b45e99104fa4b77c1d6958d04dee0270`。该 patch 尚含下述已修正的 2 MiB 上限；最终 patch 由实施方刷新。此次 PASS 精确对应以下核对后的七个生产文件：

| 文件 | SHA256 |
| --- | --- |
| `plugins/curve_score/curve_score/analysis_workspace.py` | `8bedc0244580362eeb4d1c50872826ba51f6f798baeab1bd6864a881c1aa6b51` |
| `plugins/curve_score/curve_score/science_operations.py` | `54cfaecf383b7bb66af760a9dbcc4d6d4e19b77cd926f62cd1d52238f01bf041` |
| `plugins/tcad_artifact/tcad_artifact/result_analysis.py` | `e66a3ae8f70cdb816187cc5f69f973de0bb7a0379929d85620747a2ff7099210` |
| `plugins/tcad_artifact/tcad_artifact/analysis_bindings.py` | `b0ea086e9fd4c4792ad8be86bd0272c1cbdcbb84e0d6b2d8b05021f96d4a940f` |
| `src/scidiscovery/operations/workspace.py` | `bc03bebf64c108a342af41ec3ae7ad1feee2ad357682736511a6d17930cccef4` |
| `src/scidiscovery/artifact_agent/service/runs.py` | `7befaa99e2074f34a47f16584e57b4aaa20c619eba7839663e4c454735e52f45` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` | `c8ed978cf49ce5625154fbbb1496183b908e358bcb93034987020469e8f95f5d` |

测试增量为计划已允许的 `test_analysis_continuation.py` 和现有 installed 工具投影断言更新，另有计划索引更新。没有新增生产角色、状态机、工具、科学必填字段或收据协议。

## 2. 唯一发现及关闭依据

**已关闭：workspace_sources 的 2 MiB 隐性门槛。** 初始 `analysis_bindings.workspace_sources:92` 对所有 JSON 输入固定使用 2 MiB 上限，而 `result_analysis.INPUTS` 的 reviewed_package 允许 64 MiB。此读取位于新工作区 materializer 和 finalizer 的必经路径，会使已准入的大项目在准备或提交时失败。

已向实施方立即反馈，当前源码改为 `max_bytes=request.binding_descriptors[alias].size_bytes`。这复用已冻结的输入大小，仍经现有 no-follow 有界读取，只读取 `JSON_PORTS`，没有重新读取 raw 全集或新增准入规则；七文件生产范围不变。代码问题已关闭。实施方正在补充大于 2 MiB 合法 package 的实际 preflight→open→submit 回归，其结果应进入最终实施记录。

## 3. 重点路径判断

- **历史映射不覆盖新科学 basis。** `source_bindings` 从现有 `prior_analysis_sources` 取得完整身份映射，并要求原 plan/package cohort 精确匹配；不同案例候选保留为不可继承。`materialize_references` 只在案例兼容且 `case_mapping_basis is None` 时复制旧案例及依据，显式新 basis 不改写，明确错误 output/alias 仍留给输出校验。`resolve_case_mapping` 只在原 basis 缺省且案例对一致时使用派生依据，未把历史主张升级为资格结论。
- **工具原请求和收据保持。** `_check_score_sources` 只构造描述符/关系视图，在需要历史依据时通过现有 context 读取相关来源；没有赋值 `_raw_request`、修改 CalculationRecord.request 或 attempt 摘要。score/diagnostic 仍进入原执行与保存收据路径。新测试按实际工具调用核对原 request 与 request_digest，并把记录提交封存。
- **恢复只写新副本。** `_restore_scratch` 使用既有 snapshot 白名单和预算，从只读 provisional scratch 读取，经 `write_control_workspace_file(... replace=False, mode=0o600, create_parents=True)` 写新 workspace；目录由该方法创建为 0700。它没有 chmod 恢复原件，并跳过整个既有 RECORD_DIR。权限、复制后修改脚本/建目录、launcher 新观测与旧日志保留均有新增组合用例。
- **简明入口与隐藏输入边界一致。** `RunService._materialize_workspace` 按可见 `workspace.input_paths` 提供 descriptors；`_start_file` 从已过滤的 assignment.inputs 索引/摘取，不序列化 ArtifactRef、内部标签或隐藏描述符。可增长的输入、摘录、恢复文件索引均在追加时按 UTF-8 字节核对，预留 512 字节供 TCAD 添加固定映射指针；长文本明确 omitted 并指向原文件。完整工具合同仍存于 assignment，映射详情单独引用，没有把完整合同重新内联进入入口。
- **非分析和旧 workspace 返回兼容。** `LocalWorkerProtocol._open` 只有在已存在的 domain manifest 提供 start_here、文件通过有界安全读取且 assignment 实际含 tool_contracts 时才返回入口/合同路径，否则沿用 `_assignment_tool_contracts`。不重写旧 assignment 或输出 schema。TCAD 用 ComponentSpec 连接自身 wrapper，通用分析仍使用共享 workspace 和原 finalizer；其他角色无需新的入口。
- **提交仍检查明确主张。** `analysis_context` 删除了重复 evidence 同名行门槛，保留 source_key 唯一性、bound alias/输出/案例冲突和受控计算证明。新增字段诊断使用固定原因和索引路径，不回显任意 alias。`materialize_references` 的 64 条上限及 128 KiB payload 检查与原 source_references/schema 和 `run_outputs` 的 payload 字节边界一致；不能容纳的自动补全不会截断 Agent 原文。

上述实现沿用现有身份、文件生命周期与输出检查，没有发现为本次修复增加第二份状态权威或普遍校验系统的必要性或实际扩张。

## 4. 证据与验收边界

审查者没有运行测试、构建、solver 或科学 Agent，避免与实施方串行验证叠加资源。已只读检查新增测试和 `checks.jsonl`：单独续接测试、恢复/映射/descriptor 组合、TCAD/评分/观测/请求合同组合均有退出码 0 的已完成记录；实施中早先失败也保留在同一记录中。

本结论是源码有界审查通过。最终交付仍须绑定刷新后的 patch、上限修复回归、剩余受限资源检查及隔离安装 smoke。真实 Agent 的读取量、首项动作时间和续接耗时只在用户安装后按既定计划验收，本审查没有推定这些效果已经发生。

## 5. 最终合同兼容补丁复核

结论：**PASS，未新增阻断**。此次仅核对 `analysis_workspace._start_file` 和 `LocalWorkerProtocol._open` 的追加修改，以及既有 `test_agent_contract_alignment.py` 两处断言迁移；第 1 节已更新两文件哈希，另外五个生产文件哈希与前次审查完全一致。

- 简明 open 现在确认冻结 assignment 确实包含 tool_contracts 才返回该文件的合同指针；缺字段时继续调用原 `_assignment_tool_contracts`，保留同一 compiled 身份下的旧 inline/fallback 行为。新 start 文件对这种 legacy 情形使用 open_reply_pointer，不产生指向缺失 assignment 字段的索引。
- 控制生成 assignment 的读取上限改为当前文件实际大小，随后仍经过 `read_control_workspace_file` 的 regular-file/no-follow 边界；取消的是新增的 4 MiB 隐性门槛，没有扩大可读路径或取消 analysis-start 的 24 KiB 输出边界。
- 既有合同测试按 local 新入口、local legacy 和 hardened 原行为分别取合同，继续检查完整 inputSchema、同身份回退、重开和 assignment 字节不变；领域声明变更测试改从实际合同文件读取。修改属于计划允许的通用合同测试范围，无新增生产文件或协议。

本次复核未运行测试或构建。实施方报告前次三包安装 smoke 已通过，并将对此最终小补丁串行复跑；新一轮 smoke 结果由最终实施记录绑定。
