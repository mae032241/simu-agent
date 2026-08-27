# SciDiscovery 开发计划索引

本目录统一存放尚未完成或正在执行的工程整改计划。审计报告、安装说明、
架构说明和科学结果不放在这里。

## 当前计划

- [科学资格内核 v2 重构实施计划与进度记录（当前 P0/P1）](SCIENTIFIC_QUALIFICATION_KERNEL_V2_IMPLEMENTATION_PLAN.zh-CN.md)：
  在现有 Artifact、任务、审批和确定性 transform 之上增加 OperationIntent/Receipt、实例级
  QualificationReceipt、精确 ActiveHead 和外部 effect outbox；关闭 latest-current、全局审批、
  label/parent producer、长任务陈旧激活和重复外部提交边界。该文件也是本轮持续开发进度的
  权威记录；旧科学操作契约 handoff 保留为 v1 实施历史。
- [科学操作契约与知识闭环整改实施交接（待实施）](SCIENTIFIC_OPERATION_CONTRACT_AND_KNOWLEDGE_CLOSURE_HANDOFF.zh-CN.md)：
  针对默认 profile 降级、别名绕过 current、部分审批、修订父链断裂、参数感知修订死锁、
  knowledge kind 不一致与陈旧状态分叉等跨层缺陷，引入最小操作契约核、受控语义 lineage、
  完整科学审批束和 selection generation/CAS，并以两条协议级 E2E 完成闭环验收。
- [科学目标完整性与曲线评分整改计划（当前 P0）](SCIENTIFIC_OBJECTIVE_INTEGRITY_AND_CURVE_SCORING_REMEDIATION_PLAN.zh-CN.md)：
  修复论文目标在 evidence unresolved 后被静默降级、内部粗细网格比较冒充外部真值、固定 x RMS
  误判尖锐前沿以及 diagnosis 作用域混淆的问题；引入不可降级 objective contract、comparison
  purpose/series role、按 series/区间证据资格、目的感知 scorer 和执行前 objective coverage 门禁。
  P0-A～P0-F 已实现并通过 641 项回归；下一步是 P0-G 历史对象迁移与真实 Fig.4 闭环。
- [Worker 科学输出文件沙箱重构记录](WORKER_FILESYSTEM_OUTPUT_REFACTOR.zh-CN.md)：
  所有 Codex 科学角色直接写受控 `output/result.json`，长文本 begin/append/commit 工具退出
  公共 MCP；控制面仍独占校验、冻结、完成和跨角色 Artifact 物化。
- [TCAD Deck 文件沙箱重构计划与实施记录](TCAD_DECK_FILESYSTEM_SANDBOX_REFACTOR.zh-CN.md)：
  author 合并首次编写与修订并直接编辑受控 `deck/files/`；reviewer 只读代码并输出审查报告，
  控制面负责规范对象重建、校验、冻结与注册。旧 patch 接口退出主流程，仅保留迁移兼容。
- [TCAD 项目确定性物化与审查边界重构计划](TCAD_CONTROL_PLANE_PROJECT_MATERIALIZATION_PLAN.zh-CN.md)：
  将 capability、case/global bindings、realization manifest、源码 locator、raw output 合同和
  revision diff 等机械字段全部移交 TCAD 控制层生成；author 只写 solver 源码和少量科学决策，
  reviewer 只审物理忠实性与显式代码逻辑 bug。本计划是当前 Alpha 闭环的 P0 前置修复。
- [科研论文复杂曲线证据提取实施计划](SCIENTIFIC_PAPER_EVIDENCE_IMPLEMENTATION_PLAN.zh-CN.md)：
  为 `evidence_extractor` 增加有界多 Artifact 输出和配置驱动的曲线/图例解析 skill，并以
  Fig.7、Fig.10、Fig.13 作为真实资格矩阵；Fig.4 只保留为冒烟测试。真实曲线门结果见
  [科研论文曲线证据能力资格记录](../SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md)。
- [Alpha 科学闭环架构复审与修复计划（当前主计划）](TCAD_ALPHA_SCIENTIFIC_LOOP_PLAN.zh-CN.md)：
  先离线闭合现有真实 Fig.4 证据的 diagnosis/checkpoint，再贯通单案例 SProcess 的
  reviewed package → execution → attestation → scorer → diagnosis → knowledge/checkpoint
  纵向链；局部生产安全和通用化不再阻塞 alpha。
- [Curve Score 与 Control Equivalence 实施计划](CURVE_SCORE_AND_CONTROL_EQUIVALENCE_IMPLEMENTATION_PLAN.zh-CN.md)：
  开发通用Curve Score确定性插件，以及自动兼容单package多case和多package单case的
  Control Equivalence transform；以当前solver-only真实执行作为首个资格测试，不按图号开发scorer。
- [新版本复审整改计划（完整工程 backlog）](TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md)：
  已完成成果继续保留；SDevice/TDR、部署资格和发布冻结等未完成项按 Alpha 主计划重新排序。

## 维护规则

1. 每份计划必须说明问题来源、范围、优先级、依赖关系和验收标准。
2. 一个阶段只有在对应自动化测试和人工审查门槛都满足后才能标记完成。
3. 计划不替代审计证据；原始发现保留在 `docs/TCAD_AGENT_REAUDIT.zh-CN.md`。
4. 功能冻结后再更新发布清单、版本号和交付文档。
5. 当前 alpha 是否完成，以同一 case/revision 的纵向父链、权威 checkpoint 和重启恢复为准，
   不以分散单元测试数量或局部生产加固项数量代替。
