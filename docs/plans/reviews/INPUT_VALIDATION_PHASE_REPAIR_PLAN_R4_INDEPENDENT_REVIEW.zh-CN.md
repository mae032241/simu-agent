# 输入校验职责修订计划 R4 独立工程复审

日期：2026-09-10。结论：**PASS（计划层）**。R3 唯一阻断 F2-R3 已闭合，未发现需要继续修订计划的阻断。本结论不表示源码已实施、恢复已经成功或发布验收通过。

审查对象：`docs/plans/INPUT_VALIDATION_PHASE_REPAIR_PLAN.zh-CN.md`，SHA256：`c345185ab6c718341da36fd4a23f751e151d45c22204815faec8dcb462b53fd8`。对照 R3 独立报告及其原文快照，聚焦 P3c、跨合同草稿接续和失败保全边界。

## 基线与方法

仓库 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。写入本报告前工作树有 169 项 dirty 状态：89 项已跟踪修改、9 项已跟踪删除、71 项未跟踪；`git diff --stat -- src plugins` 为 50 个文件、2288 行增加、2657 行删除。计划本身为未跟踪文件，故审查以其上述内容摘要为准，不以 HEAD 代表计划或源码现状。

使用上层 `scid-cross-boundary-review`、`scid-find-simplifications` 技能；读取当前架构、科学设计宪章、约束矩阵、当前比较评估和 TCAD 插件说明。历史文档的通过状态不作为当前代码验收证据。复核了 Run 失败与提交、backend 封存清理、Root 请求身份、assignment 草稿提示、TCAD 快照及恢复消费者。本次只新增本报告，未改计划或源码，未运行测试、编译、部署、科学控制工具或子 Agent，未读取科学实例状态。

关键源码读取基线：

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/service/runs.py` | `b51f5e78c51c253ff20b26ef064a28ff2a0269c0af4998abb3bb05adb323b404` |
| `src/scidiscovery/artifact_agent/service/local_workspace.py` | `6ff5aa06f00322c70dab344c88f405d94b5cdfdfd8143552ab2e0c23204363bc` |
| `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` | `b129cbc5e2dd20adc29e3249320291db1e71096aec8b65dc836ea73a1edf01d0` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | `63cfa155d8f63d7d0b68ac311aa56b2031fc649435609e5ed47d9d3f6ce5916f` |

## F2-R3 闭合判断

旧反例有明确源码基础：`runs.py:734` 的预览会调用 finalizer，`:829` 将结果写入 output；author 在 `operation_workspace.py:348` 使用独立的 deck 工作目录。`local_workspace.py:252` 的通用 seal 仅采集 output，`:350` 的 discard 仅复制所选 candidate，`:377` 随后删除整个 quarantine。因此“预览 A → deck 修改为 B → 合同不可用 → output A 封存成功”不能证明 B 已保存。领域原始快照 `operation_workspace.py:728` 与通用 output 快照不等价，`:215` 的恢复消费者确实需要原始 deck。

R4 在计划 `:107` 明确把完整覆盖作为清理前提；`:109` 对合同不可用场景选择保留原工作区或完整隔离副本，并禁止先 discard 后检查覆盖。该规则不依赖是否识别到 deck，也覆盖旧记录。因此即使 A 封存成功，也不能触发删除 B。

`:111` 进一步排除了仅凭 recovery_candidate_digest 或 accepted_candidate_digest 证明覆盖的捷径；必须覆盖当前待保全版本。缺证明就保留，不要求引入自动覆盖推理器。`:113` 允许通用 backend 无安全隔离能力时停止破坏性 discard、保留受控原目录并如实显示隔离未完成。这与当前 discard 把隔离和删除合并的实现相容：实施可先阻止调用，不必在计划阶段另建完整归档系统。

`:119`—`:121` 的验收明确覆盖正常 seal 成功而版本陈旧的路径，以及正式提交、显式失败、预览、重启、空 output、隔离中断。后续旧环境保全后交给新 Run 的对象必须为 B。故本次补充解决了原阻断的文件范围与清理条件决策，并非仅增加异常测试。

## 恢复与职责边界

| 核对项 | 判断及依据 |
| --- | --- |
| 输入准入与输出验收 | 第一准则、P1 提交零调用要求和 P2 保持一致；输出可核对冻结证据，不能重裁输入准入。框架故障保全交付，不要求作者无效改稿。P3c 未引入新的科学验收条件。 |
| pending 与可交接 | P3b 的受控封存要求由 P3c 的完整覆盖条件进一步限定，不是任意局部 seal 成功即 available。P3c 只在完整清单、真实摘要和源绑定验证成功后允许交接；pending 不被当作草稿来源。 |
| 严格 resume 与新合同 draft_from | `runs.py:1096` 现有严格摘要/输入比较被 P3a 保留。draft_from 另做同实例、Operation ID、后端和真实材料检查，再执行新合同准入与验收，不依赖源 Run 当前 `_compiled` 成功，也不继承科学资格。只有材料保全需要旧匹配环境，消费已受控材料不要求旧合同仍安装，二者没有循环依赖。 |
| 实际恢复消费者 | `local_workspace.py:157` 已有只读 recovery-draft 复制，`runs.py:799` 将其作为 provisional_roots 交给 materializer；`operation_workspace.py:215` 可恢复 deck 源码和声明。`run_assignment.py:70` 明确草稿不是科学证据。方案复用这些实际接口。 |
| 请求与次数 | Root `_prepare_local_run:270` 和 Run `request_digest:173` 的双层身份已在 P3a 校正；来源与摘要进入两层请求，混合 resume/draft 链按事务计数和原链冻结上限约束。P3c 补充直接 schedule 的 backend capabilities、目标支持及真实文件验证，不放宽旧保护。 |
| 失败终态与恢复展示 | `runs.py:499` 当前 failed 分支可能因合同缺失直接返回，`:562` 清理仍依赖 `_compiled`；P3b 已要求修正这两个入口。P3c 保持 failed，并从同一恢复记录分别派生完整保全、严格 resume、新合同 draft 可用性，不把 `recovery_available:1022` 的严格恢复布尔值复用为三种含义。 |

## 最小性与实施边界

R4 相对 R3 的实质增量为 P3c 的保留规则、针对性验收和真实请求入口校正。没有新增科学阶段、资格权威、Run 状态、通用草稿服务或自动扫描器。完整覆盖未知时允许 pending，代价是需匹配旧环境或明确工程修复才能完成交接；计划如实承认该限制，没有把“文件尚在”声称为“恢复已完成”。这正是关闭旧反例所需的最小保守方案。

以下仍是实施验收事实，不作为新计划阻断：

1. 在所有失败/重启清理入口证明 coverage 不足不会到达破坏性 discard；旧候选可复用不等于覆盖当前工作文件。对 A/B 用例同时核验 B 源码、声明、pending 投影及后续实际消费版本。
2. 验证 failed 后持久恢复信息与 CAS、并发及重复补救一致；恢复 pending 不得通过查询偷偷推进，也不得对发布不确定状态直接失败重开。R4 已要求终态 fencing 和发布/CAS 分流。
3. 真正重算源材料摘要并核对文件清单，不能沿用当前仅检查摘要字符串/目录存在的行为；验证新合同输入重绑、混合恢复链、实例及后端负例。

这些检查应随既定 P0—P6 最小实现完成。当前源码仍有待修的旧路径，是计划的实施对象，不是要求本轮再次扩张设计的理由。本次 PASS 仅确认 R4 对唯一阻断的决策闭合与相关边界自洽。
