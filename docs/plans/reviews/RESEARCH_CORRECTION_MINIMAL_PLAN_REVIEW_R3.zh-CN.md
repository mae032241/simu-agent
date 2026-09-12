# 校验纠错与跨轮续研计划 R3 单文件增量复审

日期：2026-09-08。结论：**PASS（计划增量）**。完整科学 case 包装正控已给出必要路径上的具体反例；新增 `transform_adapter.py`，保留原项目已封存的初始化证明并重新严格校验，是可实施的最小落点。可按本次冻结增量修复和验证；本报告不认证当前 P1 实现或整个源码候选通过。

## 1. 冻结对象与边界

- 审查对象：[R3 冻结计划](../evidence/research-correction-continuation/plan-review-r3-input.md)，SHA256 `9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8`；主计划摘要一致。
- 比较对象：[R2 冻结计划](../evidence/research-correction-continuation/plan-review-r2-input.md)，SHA256 `acc011a04ff2b6b0d7b7b2383f921c56faafe1e360cc53fdbe13f9bc1f01c93c`。本次只审两版差异及初始化证明在 package 重建中的直接调用链。
- 仓库为 `123/scidiscovery-e5.2`。P1 的三个 TCAD 文件和相关测试已经形成活动修改，**不能声称整个源码未漂移**。本次核对的 `transform_adapter.py` 和 `project_materializer.py` 尚未修改，仍分别为冻结基线摘要 `9050ff406bb833019dd887c231e8e063abde55174f56f15bacc176eb8aebeb8c`、`5cdbc87c4701f790b94d01a433ba8a6f70a4c1ff381b0511856632268c35699f`。
- 读取时现有 `project_packager.py` 摘要为 `a07b962632824919750d9281defcc5b3e7613f8c5f5d7e070144718fd72f196a`；以下严格校验判断针对其中的直接相关模型，不构成对其余 P1 修改的审查。
- 沿用已读的适用 AGENTS、跨边界/最小化/范围检查技能及科学设计宪章。仅写本报告；未修改计划、源码或运行状态，未执行 pytest、wheel、平台、solver 或科学 MCP。

## 2. 本次扩大一文件范围有具体依据

[科学包装失败日志](../evidence/research-correction-continuation/p1-scientific-package-pytest.txt)（SHA256 `ba5b160a5dcb1a08e5e013f5b01c7b569bf2a9eae46d59b2f7ce51b1cc85ac39`）记录完整科学 case 的 Root package invoke 在整对象比较失败。

[冻结基线及字段差异日志](../evidence/research-correction-continuation/p1-package-baseline-differences-pytest.txt)（SHA256 `0fbc75997d164d7c7c3d42887ff03e5ec267071f8844010408ce418d8b172a50`）核验了冻结 plugin.py/project_packager.py 的加载摘要；其中完整科学 case 分支同样失败，并记录唯一字段差异为 `initialization_attestation` 从原 qualified 证明变为 None。该日志另有工程单 case 的 missing anchor 失败，两者保持区分。本审查没有重跑这些测试，也未把 fixture 当作 Fig.4 科学结果。

这满足 [前次包装范围审查](RESEARCH_CORRECTION_P1_PACKAGE_SCOPE_REVIEW.zh-CN.md) 的升级条件：完整 binding 的当前正常包装路径仍不能完成，不能再以“原来就有问题”跳过。R3 暂停后续工作并增补一个文件，符合已经批准的范围变更规则。

## 3. 最小落点与严格校验可实施

| 直接源码位置 | 事实及对方案的支持 |
| --- | --- |
| `transform_adapter.py:124` | package 已把精确输入解析为 DeckProjectDraft，原初始化证明来自被审项目，不能从其他来源替换。 |
| `transform_adapter.py:138`—`:194` | declared-source.v2 分支重建声明并调用 materializer；只有 preflight_attestation 被显式传入。拟议修改在本次重建之后、原比较之前即可落地。 |
| `project_materializer.py:479`、`:488`—`:524` | materializer 解析并传递 preflight，但创建 DeckProjectDraft 时没有传 initialization_attestation，因此该字段采用 None。恢复既有证明不需要扩展函数签名或让 materializer产生新证明。 |
| `project_packager.py:644`—`:649` | DeckProjectDraft 对 preflight 和 initialization 两项原证明分别检查 source_tree_sha256，并在 project_sha256 非空时核对 project_debug_sha256。重新严格解析补回证明的重建对象会执行这些既有检查。 |
| `project_packager.py:653`—`:658` | project_debug_sha256 排除两项证明及 materialization_report，因而补回原初始化证明本身不会改变它绑定的项目摘要，不存在自引用校验问题。 |
| `project_packager.py:329`、`:341` | 初始化证明继承 terminal_state/exit_code/diagnostic_layer 与 qualified 的一致性校验；方案保留原值，不增加另一项资格计算。 |
| `transform_adapter.py:195`—`:212` | 补回之后仍执行原整对象比较、既有受限日志迁移、case controls 和 ReviewedDeckPackage。`project_packager.py:784`—`:786` 保留确切报告校验及 pass/execution_ready 条件。 |

计划明确“使用既有 DeckProjectDraft 严格校验”是承重要求。实现可将重建对象与**原输入中的同一初始化证明**组织为 JSON 数据，再调用现有 `model_validate_json(..., strict=True)`。不能只调用未验证的 `model_copy(update=...)` 就把它当作已执行校验；也不能用整份原项目覆盖重建结果来消除比较差异。

现有模型对 project_sha256 的检查有非空条件；本增量保持原合同，不凭空升级旧 None 为完整证明。declarations_sha256 应随原证明原值保留，不宣称通用模型已经重新核对了独立 declaration 文件。当前 author 的冻结证明、项目 source/project 绑定和 package 全对象比较继续承担各自职责；没有证据要求为本次丢字段缺陷增设新的校验框架。

## 4. 增量范围与验收足够明确

R3 第 2.3.1 节、Operation 表、第 4.1 节和 P1 退出条件一致：生产范围从 13 文件增至 14 文件，唯一新增文件为现有 transform_adapter.py。没有扩展 author/debug/materializer 接口，没有生成新 qualified 证明，也没有放宽原 preflight、review、case、Effect 授权或整对象比较。

计划要求当前 declared-source.v2 完整科学 case 经 Root author→review→package 实际完成，包装中的初始化证明与原输入一致；同时保留 source/project 证明错配、重建字段差异、假 pass、负面报告包装及执行拒绝负控。这些检查能够证伪“只复制字段但误放行项目”的实现；不能仅以 preflight 接纳或直接构造 ReviewedDeckPackage 代替。

无 comparison binding 的工程单 case anchor 丢失仍有单独证据与适用范围，R3 没有顺带修它，也没有称其已经恢复。实际必要计划若再次触及该缺陷，仍须根据具体反例修订范围；当前不预建 anchor 存储符合最小化原则。

本次 diff 的其余变化为状态、索引与相应执行要求同步。R2 的目标选择、父链查询、feedback、ABI 及资格恢复规则没有被无关扩展。未发现新的计划阻断；不用再增加生产文件。

## 5. 验证与结论边界

本轮完成冻结计划 diff/摘要核对、两个直接故障文件与基线摘要比较、失败日志及相关模型/包装代码只读审查、报告链接和空白检查。未运行测试或实际执行。所有实现正负控仍由后续候选证据证明，P1 退出条件尚未完成。

**PASS 只绑定上述 R3 一文件计划增量。** 初始化证明保留后的真实 package 成功、负控及 P1 独立实现复核通过，才可登记对应工程步骤完成；本次不授予科学资格或部署/执行批准。
