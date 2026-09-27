# SciDiscovery 文档入口

当前行为以编译合同和下列实现文档为准。验证结论必须绑定具体源码与环境；历史通过记录不自动证明当前部署或科学模型有效。

| 用途 | 文档 |
| --- | --- |
| 架构与责任边界 | [中文](ARCHITECTURE.zh-CN.md) · [English](ARCHITECTURE.md) |
| 设计原则与待复核约束 | [设计宪章](architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md) · [约束登记](architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml) |
| 安装 | [中文](INSTALL.zh-CN.md) · [English](INSTALL.md) |
| 发布与验证边界 | [中文](RELEASE.zh-CN.md) · [English](RELEASE.md) |
| 插件接口 | [Plugin runtime API](PLUGIN_RUNTIME_API.md) |
| Worker 文件交付 | [角色结果 JSON 协议](role-result-json-protocol-v1.md) |
| TCAD 执行与调试 | [传输合同](tcad_transport_contract.md) · [插件说明](../plugins/tcad_artifact/README.zh-CN.md) |
| 图证据与评分 | [图插件](../plugins/curve_figure_evidence/README.zh-CN.md) · [评分插件](../plugins/curve_score/README.zh-CN.md) |
| 后续工作 | [当前待办](plans/README.md) |

## 有独立价值的研究与资格记录

- [TCAD 历史资格记录（中文）](TCAD_QUALIFICATION_STATUS.zh-CN.md) / [English](TCAD_QUALIFICATION_STATUS.md)：仅适用于记录时的候选与环境。
- [论文图证据资格记录](SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md)：结论限于声明的样本与实现。
- [Fig.4 模型评估](FIG4_DIFFUSION_MODEL_ASSESSMENT_2026-09-14.zh-CN.md)：保留模型适用性讨论及其直接引用的两份原始快照，不作为新执行授权。

## 历史材料

实施流水、过期计划、重复审查、原始日志、截图和源码备份已退出当前树；不再另外维护一份 archive。
清理前完整树为 `5a90f3fa33135c8b151a547e2eceed0d102eea95`，可用
`git show 5a90f3f:docs/plans/HISTORY.md` 查旧索引，再按原路径读取具体记录。
删除过程文件不表示其中未关闭问题已经解决。未来原始验收输出写入仓库外，当前文档只保留结论、候选身份、验证范围和必要引用。
