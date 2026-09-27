# 文档归档与清理记录

本目录保存退出当前阅读路径的旧方案。当前工作见[计划首页](../plans/README.md)，当前规范见[文档首页](../README.md)。归档不意味着其中缺口已解决，也不授予科学资格。

## 2026-09-24 第一轮清理

- 计划首页从 298 行旧索引收敛为当前主线，旧状态内容留在[历史索引](../plans/HISTORY.md)。
- 删除 163 个未跟踪的 Python/pytest 缓存文件，共 3,492,482 字节；没有删除科学产物、审查报告或候选包。
- 归档下表 8 份旧文档：正文和 SHA256 保持不变，无当前代码/发布消费者。它们的旧路径可能仍出现在历史基线清单中；这些清单描述当时布局，不改写清单，用本表定位原件。
- 发布脚本、规范或审查仍引用的文档，以及 2 份本轮已审计划和审查报告，保留原路径与字节。
- 证据目录的 PDF、源码快照、压缩候选与日志不是按扩展名可判定的垃圾，本轮保留。

## 静态核验

- 4 个导航文件的 282 个本地链接全部可解析。
- 发布清单的 31 份文档均存在；归档正文、两份已审计划和对应审查报告的 SHA256 未变。
- 除计划首页外，清理前留存文档的正文均未变；仅移除上述缓存。
- `git diff --check -- docs` 通过。按用户要求，没有执行测试、测试收集、安装或构建。

## 路径映射

所有旧路径前缀均为 `docs/plans/`；新位置为本目录的 `legacy-plans/`。

| 文件（新位置） | 归档依据 |
| --- | --- |
| [CURVE_DIAGNOSTIC_ANALYSIS_INTERFACE_PLAN.zh-CN.md](legacy-plans/CURVE_DIAGNOSTIC_ANALYSIS_INTERFACE_PLAN.zh-CN.md) | 文首已声明旧 worker_curve_analyze 方案被 R5-M2-02 取代。 |
| [R1_OPERATION_SPEC_COMPILER_IMPLEMENTATION.zh-CN.md](legacy-plans/R1_OPERATION_SPEC_COMPILER_IMPLEMENTATION.zh-CN.md) | 早期最小编译器阶段实施记录，当前规范已有独立入口。 |
| [R5_E5_5_MINIMAL_FIGURE_EXTRACTION_REUSE_DESIGN.zh-CN.md](legacy-plans/R5_E5_5_MINIMAL_FIGURE_EXTRACTION_REUSE_DESIGN.zh-CN.md) | 已完成的图提取复用阶段设计，保留实现依据。 |
| [SCIENTIFIC_PAPER_EVIDENCE_IMPLEMENTATION_PLAN.zh-CN.md](legacy-plans/SCIENTIFIC_PAPER_EVIDENCE_IMPLEMENTATION_PLAN.zh-CN.md) | 早期论文图证据实现方案，当前插件说明与资格记录另有入口。 |
| [SCIENTIFIC_PAPER_EVIDENCE_OVERDRAW_V1.zh-CN.md](legacy-plans/SCIENTIFIC_PAPER_EVIDENCE_OVERDRAW_V1.zh-CN.md) | 2026-08-15 多色覆盖算法历史设计。 |
| [TCAD_CONTROL_PLANE_PROJECT_MATERIALIZATION_PLAN.zh-CN.md](legacy-plans/TCAD_CONTROL_PLANE_PROJECT_MATERIALIZATION_PLAN.zh-CN.md) | 2026-08-13 物化与审查边界阶段方案。 |
| [TCAD_SKILL_V2_AB_REFACTOR.zh-CN.md](legacy-plans/TCAD_SKILL_V2_AB_REFACTOR.zh-CN.md) | 旧 Skill v2 重构和 A/B 设计，保留评测依据。 |
| [WEEKLY_AGENT_DEVELOPMENT_SUMMARY_2026-09-06.zh-CN.md](legacy-plans/WEEKLY_AGENT_DEVELOPMENT_SUMMARY_2026-09-06.zh-CN.md) | 2026-09-06 周回顾，非当前规范。 |

### 原件摘要

```text
1a9c43b9d206940a03fdebe88e5f9e60d2223e84b913bc50352947b9d6ee3d9a  CURVE_DIAGNOSTIC_ANALYSIS_INTERFACE_PLAN.zh-CN.md
a4756cac9ca804c9c4902e095dce1cdaba8fd8e1e14e5d0fed6ce40506b31ca0  R1_OPERATION_SPEC_COMPILER_IMPLEMENTATION.zh-CN.md
c8a07f251df2093b2e8a388e60e6bedf4269ecce109c276645ed739206388e5a  R5_E5_5_MINIMAL_FIGURE_EXTRACTION_REUSE_DESIGN.zh-CN.md
db0c01d7d3a2029f4db3896f42e47242f600ac0f30546ebc4847bcd63f6aab29  SCIENTIFIC_PAPER_EVIDENCE_IMPLEMENTATION_PLAN.zh-CN.md
c46de05c98ff463b2fa2787c2904956893b48b6bcb86313c0f6ef2dbe0ad069b  SCIENTIFIC_PAPER_EVIDENCE_OVERDRAW_V1.zh-CN.md
9c4cd7e90d63381da7939168e4c2d048fccbf8bdcff21f5efaf917fcb49c44f8  TCAD_CONTROL_PLANE_PROJECT_MATERIALIZATION_PLAN.zh-CN.md
d0f17f136bc9b4e117516695c4d81318ff3076306f79285e752fa9d695cdc326  TCAD_SKILL_V2_AB_REFACTOR.zh-CN.md
fe0aa4c3a482643d422a606b14eec6186b5d95530a20fe87ff3ef3b189885396  WEEKLY_AGENT_DEVELOPMENT_SUMMARY_2026-09-06.zh-CN.md
```

这些正文中的旧路径、代码标识和状态保持历史原文；不将它们自动解释为今天仍存在的入口。
