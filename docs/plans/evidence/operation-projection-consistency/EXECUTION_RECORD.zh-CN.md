# Operation 合同投影一致性 R1 实施记录

日期：2026-09-11。状态：源码修复与隔离安装验证完成；生产未部署，E6/E7 未验证，整份计划尚未关闭。

## 对象与文档归属

本记录只证明[获独立复审通过的 R1 计划](../../OPERATION_PROJECTION_CONSISTENCY_REPAIR_PLAN.zh-CN.md)的本轮工程增量。计划 SHA256 为 `6547fbe75d3d7b8a3d257a91e62e0f75688093ef0e39506f042323b40c18c1e1`；HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树实施前已有大量未提交改动，不能用相对 HEAD 的总差异代表本轮改动。

| 材料 | 所有权与处理 |
| --- | --- |
| R1 计划及[独立复审](../../reviews/OPERATION_PROJECTION_CONSISTENCY_PLAN_REVIEW_R1.zh-CN.md) | 冻结送审原文和计划 PASS，不改为实现 PASS |
| [决策索引](../../README.md) | 指向当前实施记录，分别报告工程、部署和现场状态 |
| 本记录、[增量清单](FINAL_CANDIDATE.json)及测试日志 | 本轮实现和验证证据，不代替科学资格或新 Agent 验收 |
| 原 R4、投影审计和 P6 记录 | 保留历史事实；本次没有重新验证或改写其科研结论 |

[FREEZE.json](FREEZE.json)保存初始工作树状态及 325 个相关文件的摘要，[初始 HEAD 差异](BASELINE_HEAD_DIFF.patch)保存既有增量。精确本轮改动分别见[生产差异](PRODUCTION_INCREMENT.patch)和[测试差异](TEST_INCREMENT.patch)。备份位于 `/tmp/scid-projection-r1-baseline`，持久证据不依赖该临时目录继续存在。

## 实现范围

生产代码仅修改计划指定的 15 个现有文件，测试调整 5 个现有所属文件。没有新增 Operation、公共工具、状态机、注册表或 VM runner 协议，也没有修改评分算法、研究资格、数据库历史或生产服务。

| 部分 | 已实现行为 | 主要所有者 |
| --- | --- | --- |
| A 静态合同 | 分析专用类型声明 16 个 comparison、4,096 个采样点和 16 个 operator；通用与 TCAD 评分共同继承。请求字节和实际源数据预算由原执行所有者检查，同源说明可见 | `curve_score/analysis_tool.py` |
| B 消费者交付 | 单一 `operation_tool_contracts` 投影进入 assignment 与 Local/Hardened 打开回复；保留独立 Schema 根和引用。角色提示给出实际读取路径；旧 assignment 只允许同摘要补读 | `operations/tooling.py`、assignment、两种 Worker、Codex profile |
| C 纠错反馈 | 先在原 8 条/4 KiB 预算内定稿安全诊断，再用于回执、回复和日志；无法保留失败原因时明确报告回执工程故障。输出拒绝只记录一次；Hardened 保留类型化错误 | `tool_evidence.py`、Worker、`run_outputs.py`、`runs.py` |
| D 相邻投影 | Root 和内部 preflight 共用空 parameters 类型；目录投影真实输入元数据；区分 runtime、timeout 和 checker 故障，保留明确的 integrity/admission 类别 | `operations/invoke.py`、`operations/spec.py`、Root、`runs.py` |

默认采样点 257、原始请求 JSON、默认值省略方式、公共 attempt 引用与 `ALGORITHM_VERSION` 保持原义。旧回执按原表示引用；未通过放松证据成员关系消除拒绝。故障分类落实了独立复审 N1，未将已有具体类别统一覆盖为 `checker_failure`。

## 验收覆盖

| 编号 | 工程结果与边界 | 证据 |
| --- | --- | --- |
| E1 | 两类评分 Schema/模型正反边界一致；5,000 点错误在读取源文件前明确指出 4,096 上限。旧请求重放；已知两端点计算得到线性 900、log10 1 | `SOURCE_CONTRACT_REGRESSION`、`KNOWN_NUMERIC_AND_TIMEOUT` |
| E2 | 全部已编译 Agent 的 backend 工具投影与实际 MCP 相等，局部引用可解析；两种 backend 实际打开交付；单字段声明修改贯通编译摘要、agent_type、MCP、assignment、打开回复和真实调用 | `SOURCE_CONTRACT_REGRESSION`、`SINGLE_TOOL_DECLARATION` |
| E3 | 长诊断裁剪后的回复、日志、回执一致；同 Run 修正并封存，下一 Run 引用原失败回执；无法写入有效诊断时明确报错；输出拒绝仅一次。真实 Agent 自行纠正部分仍待 E6 | `SOURCE_CONTRACT_REGRESSION`、`RECEIPT_METADATA_EXHAUSTION` |
| E4 | 同摘要旧 assignment 补读且原文件不变，跨摘要恢复拒绝；请求和回执保留，草稿/历史引用边界保持；真实截止时间 CAS 和三类错误验证。扩大历史检查有下列一项原有失败 | `HISTORY_AND_COMPILED_CONSUMERS`、`KNOWN_NUMERIC_AND_TIMEOUT`、`D_CATEGORIES` |
| E5 | 真实 wheel、隔离安装目录、生成 profile、MCP stdio 入口、Local 工具调用与封存、Hardened 打开和类型化错误通过；安装目录与源码编译身份一致。生产安装仍待执行 | `INSTALLED_R1`、`INSTALLED_HARDENED_R1`、`CANDIDATE_IDENTITY_R2` |
| E6 | **未验证**：尚未用新版注册角色派发无父背景的真实 Agent。单元测试和安装探针的已知答案不能替代此项 | 按[安装交接](HANDOFF.zh-CN.md)续接 |
| E7 | **未验证**：未创建或启动当前研究的新分析 Run；原 P6 有限分析不升级为通过 | 按[安装交接](HANDOFF.zh-CN.md)续接 |

评分仍是分析内可选工具；输出提交仍不重新判定输入准入。已有相关回归覆盖实现/执行不要求评分合同、失败执行可封存有限分析、精确案例/来源关系以及输入声明与输出声明各自的消费边界。

## 准确测试结果与资源

所有检查串行经过[资源保护器](RESOURCE_GUARD.py)：每次一个测试或构建进程树，地址空间上限 512 MiB，树 RSS 达 448 MiB 提前终止。没有运行全量 pytest、xdist、求解器或八条大 PLX 重放压力测试。

| 最终相关检查 | 结果 | 进程树峰值 |
| --- | --- | --- |
| [源码合同回归](SOURCE_CONTRACT_REGRESSION.log) | 189 passed，1 failed，1 deselected；失败已在修改前复现 | 约 158 MiB |
| [历史与编译消费者](HISTORY_AND_COMPILED_CONSUMERS.log) | 16 passed，1 failed；失败已在修改前复现 | 约 141 MiB |
| [已知数值与真实超时](KNOWN_NUMERIC_AND_TIMEOUT.log) | 2 passed | 见同名 JSON |
| [无法保留有效失败回执](RECEIPT_METADATA_EXHAUSTION.log) | 1 passed | 见同名 JSON |
| [单工具字段变更贯通](SINGLE_TOOL_DECLARATION.log) | 1 passed | 约 133 MiB |
| [隔离安装](INSTALLED_R1.log) | 10 项检查通过；[清单](INSTALLED_CHECKS.json) | 约 213 MiB |
| [追加 Hardened 安装检查](INSTALLED_HARDENED_R1.log) | 1 项通过，复用同一组 wheel | 约 105 MiB |
| [部署 dry-run](DEPLOY_DRY_RUN.log) | 通过，未修改包、状态、服务和平台配置 | 约 103 MiB |
| [当前架构矩阵](ARCHITECTURE_MATRIX.log) | 1 passed，仅验证现有注册结构 | 约 61 MiB |
| [最终增量与链接检查](FINAL_SCOPE_AND_LINKS.log) | 15 个生产文件、5 个测试文件；计划摘要、差异空白和 29 个相对链接通过 | 约 35 MiB |

上述批次存在覆盖重叠，不相加为独立用例总数。每个日志对应 JSON 保存原命令、时间、退出码及峰值；最高约 **213 MiB**，没有触发内存终止。实现过程中的失败和修正记录全部保留，不以最后一次通过覆盖早期日志。

技能中提及的旧架构验证/科学 bench 脚本仅存在于历史快照，不在当前仓库；没有调用历史实现来验证本轮候选。当前架构矩阵只证明结构，实际行为以本轮上述边界检查为准。

两项原有失败未作为本轮回归，也没有顺带改写断言或资格逻辑：

1. `test_review_validates_bound_original_context_and_actual_source_aliases[execution_context]`：旧断言期待 `ValidationError`，实际 preflight 返回 `OperationInvocationError(input_content_incompatible)`，无效输入确实被拒绝。[冻结基线复现](BASELINE_EXECUTION_CONTEXT_EXPECTATION.log)返回相同错误。
2. `test_historical_intake_can_request_new_qualification_after_fresh_audit[pass]`：资格审批缺少冻结生产者来源时，实际返回 `OperationEngineeringError(approval_projector_failed)`，旧断言期待不可准入结果字典。[冻结基线复现 R2](BASELINE_QUALIFICATION_EXPECTATION_R2.log)确认相同失败。第一次基线检查缺少 SQL 资源，随后补回与冻结摘要一致的资源再复现；第一次不作为此缺陷证明。

Hardened 的 TCAD 分析受现有 native/collection 能力限制，未扩展其权限。Hardened 打开/错误运输测试使用隔离的现有 CSV 夹具变体，去除该测试 author 的 review edge；它只证明运输路径，不证明 Hardened 的完整科学审查链。生产声明没有因此改动。

## 安装身份与剩余事项

[INSTALL_BUNDLE.json](INSTALL_BUNDLE.json)保存五个 wheel 的 SHA256 和四个独立虚拟环境；生产相关插件组合为 TCAD、curve_score、figure。安装探针清除源码 `PYTHONPATH`，并核对模块位于对应隔离环境。

[候选身份结果](CANDIDATE_IDENTITY_RESULT.json)核对了 wheel 中 157 个 Python 文件与最终源码的一致性；采用原发布器既有文本规范化，其中一个未修改文件仅有尾随空格差异。最初按逐字节比较失败的[探针](CANDIDATE_IDENTITY.log)保留，规范化复核通过不代表修改了该文件。

- 候选目录摘要：`f6acab6e9e24838caeb090d7a72b94307256559b8e0589e04c68f23658d438d1`。
- 当前生产摘要：`adb285db97177f951626220939864f8b899c3c1a0f62422befb256fcd893ecc8`。

当前会话可用的注册角色和生产服务仍是旧代，不能据此完成 E6/E7。本轮没有写 `/opt`、重启服务或运行生产科研任务。安装后需重新生成/加载角色配置，用新 Run 绑定原有封存记录；旧 Run 不迁移、不绕过摘要校验。平台内部 Schema 简化器的具体转换代码尚未定位，本次提供可读完整合同的补读路径，不能称平台内部问题已修复。

下一步按[交接说明](HANDOFF.zh-CN.md)安装并重启，再串行完成 E6 工程 Agent 验收与 E7 当前研究续接。两项完成前不关闭计划，也不宣称 TCAD 跨轮闭环完成。
