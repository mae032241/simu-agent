# SciDiscovery 文档入口

先按用途选文档。当前实现、实施提案和历史证据分开阅读；历史文档中的 PASS、待办和机器能力只适用于其记录时的候选与环境。

## 当前实现与使用

| 用途 | 文档 |
| --- | --- |
| 架构与责任边界 | [中文](ARCHITECTURE.zh-CN.md) · [English](ARCHITECTURE.md) |
| 设计原则 | [设计宪章](architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md) · [33 项约束与核验状态](architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml) |
| 安装 | [中文](INSTALL.zh-CN.md) · [English](INSTALL.md) |
| 发布 | [中文](RELEASE.zh-CN.md) · [English](RELEASE.md) |
| Worker 文件交付 | [角色结果 JSON 协议](role-result-json-protocol-v1.md) |
| TCAD 执行与开发调试 | [传输合同](tcad_transport_contract.md) · [插件说明](../plugins/tcad_artifact/README.zh-CN.md) |
| 图证据与评分 | [图插件](../plugins/curve_figure_evidence/README.zh-CN.md) · [评分插件](../plugins/curve_score/README.zh-CN.md) |

## 本轮实施入口

[R4：按完整研究任务重构](plans/RESEARCH_TASK_REFACTOR_R4.zh-CN.md)：通用实验任务、阶段交付与 UI、Root 自包含接口、按需审查及内部 Agent 工具。**已开始实施，尚未完成**；允许串行受限定向源码验证，其他运行未恢复。R3 的通过项是已有工程基线，不代表完整任务架构或真实 Agent 闭环已通过。

### R3 已有工程验收

[Agent 架构重构 R3](plans/README.md)：四阶段已串行实施并完成独立静态审查；受限源码 29 例、runner 边界 15 例、隔离构建安装、安装态协议和独占 512MB 本地流式传输均通过。详见[最终验收记录](plans/FOUR_MODULE_R3_FINAL_ACCEPTANCE_20260925.zh-CN.md)及[实施记录](plans/FOUR_MODULE_R3_IMPLEMENTATION_STATUS_20260925.zh-CN.md)。**用户提供可达地址后，真实短 SProcess / SDevice 与原生产物流式收集亦已通过，本轮约定范围验收完成。** 本地及远端临时目录已删除，现有服务未改，未运行全套测试；512MB 是本地传输实测，真实SSH验证使用小产物，未测2GB或完整外部LLM科研流程。旧计划的 PASS 仅适用于原候选。

## 历史、研究与资格记录

- [历史计划、实施和审查索引](plans/HISTORY.md)：保留旧状态和未关闭事项，不自动形成当前待办。
- [归档目录与清理说明](archive/README.md)：旧方案正文及路径映射。
- [2026-08-08 TCAD 首审](TCAD_AGENT_AUDIT.zh-CN.md)、[复审](TCAD_AGENT_REAUDIT.zh-CN.md)：历史发现，不是当前缺陷清单。
- [2026-08-08 TCAD 资格记录（中文）](TCAD_QUALIFICATION_STATUS.zh-CN.md) / [English](TCAD_QUALIFICATION_STATUS.md)：保留当时证据和环境边界，不据此判断今天的安装或许可证状态。
- [论文图证据资格记录](SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md)：结论限于文内声明的样本和实现。
- [科学发现层早期设计](scientific_discovery_layer.md)：2026-08-04 的阶段实现记录；当前结构以架构说明和代码为准。
- [Fig.4 模型评估](FIG4_DIFFUSION_MODEL_ASSESSMENT_2026-09-14.zh-CN.md)、[2026-09-08 至 09-14 回顾](FIG4_RESEARCH_AND_FRAMEWORK_RECAP_2026-09-08_TO_2026-09-14.zh-CN.md)：研究历史，不作为新执行授权。

审查报告和证据包保留在 `plans/reviews/`、`plans/evidence/`。发布脚本仍使用的历史文档保留原路径，不因本轮整理改写其结论或发布范围。
