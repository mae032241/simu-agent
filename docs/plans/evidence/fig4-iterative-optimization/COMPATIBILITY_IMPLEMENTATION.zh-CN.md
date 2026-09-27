# 历史科学记录兼容性实施记录

2026-09-12。基线 `be5da77acdbf98054e0b096fc4e940de560d4ba1`，可恢复标签 `checkpoint/fig4-before-historical-compatibility-20260912`。当前源码已完成，未部署；原科研停点没有移动。

依照 [修复计划](COMPATIBILITY_REPAIR_PLAN.zh-CN.md) 与 [独立计划审查 PASS](COMPATIBILITY_PLAN_REVIEW_R1.zh-CN.md)，修改限定三个生产文件：

- `service/runs.py`：完成记录按已有 version 与输出端口类型复用；同版本实现摘要变化不撤销原对象的审查。原 Run 的 `_compiled`、resume、draft、submit 逻辑不变。
- `interfaces/mcp_root_operation_routes.py`：同版本历史 claim/change request/review signal 不再因全量 digest 漂移拒绝；保留原类型、审查主体和来源边界。有精确审查但不兼容与没有匹配审查分别诊断，直接修订也适用；诊断查询不提供准入资格。
- `service/approvals.py`：现有 provider 匹配函数默认严格；研究输入可按原 provider id/version/approval_contract_digest 消费原精确对象的已封存人工决定。执行授权不能使用该放宽，也未修改任何人工决定。

只同步双语架构历史复用条款及相关测试。没有新增 Operation、状态机、数据库字段、兼容摘要、输出校验器、自动审批或 VM runner 修改。历史标记、原来源摘要和科学结果保持原样。科学含义不兼容的改动仍须提升已有 Operation version 或 schema；这里不自动判定语义等价。

## 验证

82 项不同用例通过，全部串行。最大进程树 RSS 为 192,790,528 字节（约 184 MiB），低于 512 MiB 上限；没有内存/时间预算中断。每个检查使用 512 MiB 地址空间与进程树 RSS、150 秒墙钟、120 秒 CPU、BLAS 单线程和关闭 pytest 插件自动加载。

| 范围 | 不同通过项 | 证据 |
| --- | ---: | --- |
| 新的真实 completed 审查、原人工决定、claim、直接修订兼容路径 | 9 | `test_completed_science_compatibility.py`；真实 Root preflight/invoke、Worker 打开和提交，临时状态中的真实 UI 决定接口，无准入/审批通过 stub |
| 既有准入、精确审查、背景/非合格状态、同版本输出类型边界 | 39 | `test_m6c_producer_topology_removal.py`（下述基线失败除外）、`test_review_admission_integration.py`、`test_l3_review_and_human_policy.py`、`test_m6b_operation_input_admission.py` |
| 历史来源族、审批和外部执行身份 | 21 | `test_historical_compatibility_paths.py`、`test_r4_execution_approval_identity.py`，包括仅运行 digest 不符也无法授权/提交 |
| Run 合同、恢复、跨合同 draft 和真实 stdio Worker 子进程 | 13 | `test_l2_run_invariants.py` 中计划对应的五组定向用例；原 Run 身份变化仍拒绝，已有跨合同 draft 不被收紧 |

同版本历史兼容后的跨实例引用、新科学修订配旧审查、版本/类型/批准合同变化、未批准新对象均有负例。初次 7 项新测试后补 2 项直接修订；末批重测 3 项时补跨实例断言，计数按不同用例去重，不能把重复运行算成新覆盖。完整命令、日志、运行时间和峰值见 [机器记录](compatibility-verification.json) 与 `checks.jsonl`。

发现一项与本修复无关的旧失败：`test_agent_inventory_exception_has_an_explicit_complete_consumer_inventory` 仍硬编码旧分析端口清单。当前源码失败后，在 `/tmp` 隔离导出的 `be5da77` 上运行同一用例，复现同一差异。该断言不在本轮改动范围，未删改；后续定向集合仅明确排除此项，不声称全量测试通过。原始当前/基线失败日志均保留。

`git diff --check` 通过。没有全量 pytest、wheel 重建、线上原数据迁移、真实 TCAD 求解或新的人工批准。本轮未改打包入口/依赖，真实 stdio 工程路径已覆盖；安装态和真实科研路径仍需部署后验证。

## 恢复和下一步

需要取回修改前源码时，可在另一目录检出标签 `checkpoint/fig4-before-historical-compatibility-20260912`，不必破坏当前工作树。Git 检查点保存源码及已有工程记录，不是线上数据库快照；本轮未修改线上状态。

安装重启后，应对先前失败的 `fig4_iterative_alignment_design_1` 与 `fig4_iterative_alignment_hypothesis_review_1` 的原绑定重新 preflight，区分兼容修复和任何仍需真实科学/人工处理的缺口。不得复用安装前预检成功作为安装后 invoke 的依据。

科研方面仍停在已完成 `fig4_iterative_alignment_scope_review_1`、计划修订仅预检通过的位置。本轮没有设计数值候选或进行仿真，也没有补 hypothesis 结果反馈端口；该已知功能缺口保留为后续工作，不把本轮兼容性修复等同于完整科研闭环。
