# 研究纠错与续研实现独立工程审查 R1

结论：**REVISE**。冻结候选存在一项可达的曲线检查引用校验缺口；最小修复只需调整已审定编译器内既有校验的执行顺序，并补充对应空集合边界测试。未发现需要扩大十四个生产文件范围的第二项阻断。本结论属于工程候选审查，不认证科学结论、部署状态或 P5/P6 的真实续研验收。

## 1. 审查对象与身份

- 审定计划：[主计划](../RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md)，SHA256 `9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8`；与冻结 R3 输入相同。
- 候选：[p4-candidate-r1.json](../evidence/research-correction-continuation/p4-candidate-r1.json)，`candidate_digest=97fa16ae9033efe68fcc5c210c2c03f471dd8f7992d28eb005c5a1cb162f64c6`；清单文件本身 SHA256 `da6e0706dc5d9715658f6b68de7d4e72dd922c2773fc0bf39ef74ca009f608be`。
- 冻结补丁：[p4-candidate-r1.patch](../evidence/research-correction-continuation/p4-candidate-r1.patch)，SHA256 `8a7756c24d62fd5663bb5ee3281847df687470f9b03bdd7c2e152b64a03f3856`。范围是十四个生产文件、十二个测试文件、两份架构文档。
- 原有脏工作树基线：[source-baseline-2026-09-08.json](../evidence/research-correction-continuation/source-baseline-2026-09-08.json)，SHA256 `50574bfe11f1fe1caa7649e89d887e44fa0a816cb654c8656ba0f713f760e438`；原始字节目录 `/tmp/scid-continuation-implementation-baseline`。没有把既有未提交修改归入本次实现。
- 本审查在内存中逐项应用冻结补丁，核对全部 28 个文件的 before/after SHA256，全部吻合。报告中的源码行号指 R1 候选；后续工作树已经移动曲线编译器早返回并添加测试，因此当前文件行号可能不同。后续修复不回填本轮 PASS。

依据为适用 AGENTS、`scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks`、Karpathy 指南及现有架构/科学设计约束。审查只读生产与测试；未调用科学 MCP、Worker、平台或 solver，未自行运行 pytest/wheel，也未修改实现。

## 2. 阻断 R1：无适用检查时，显式无效引用被静默删除

**位置。** `plugins/curve_score/curve_score/curve_contract_compiler.py:378` 的 `_bind_curve_score_checks` 在 R1 第 396—397 行发现 `checks` 为空就返回；第 398—405 行的显式检查键集合校验因而无法执行。公开编译入口第 248 行调用该函数；第 272 行的 `validate_compiled_curve_contract` 从已生成 operator 反推引用（第 302 行），不能找回原请求中已经丢失的键。

**可达反例。** 保留合法目标、参考系列、case、单位和阈值，将当前计划的确定性检查 `profile_rms` 的 evaluator 改成另一个合法 evaluator。此时本曲线编译器没有适用的检查。分别提交：

1. `validation_check_keys=[]`：应允许，其他 evaluator 的检查不由曲线 operator 承接。
2. `validation_check_keys=["absent_check"]`：所引检查不存在，应拒绝。
3. `validation_check_keys=["profile_rms"]`：该检查属于另一个 evaluator，应拒绝此曲线绑定。

R1 对后两项均未拒绝，而是输出不含该引用的合同。这是受支持输入模式上的信息丢失，不需要绕过 Root 或伪造对象；设计 Worker 可以提交结构合法的这类编译请求。虽然早返回来自基线，它违反本次已审定计划第 3.2.1 节“参考 series/case/check 存在且关系一致”的明确闭合要求，不能以“原来就存在”为本候选豁免。

**独立定位与执行证据。** 审查者先依据源码报告该反例；父任务随后串行运行新增参数化负控。[修复前日志](../evidence/research-correction-continuation/p4-review-check-binding-before.log) 记录 `2 failed, 1 passed, 24 deselected`，两次失败均为 `DID NOT RAISE SemanticRuleViolation`。测试入口为 `tests/operations/test_m2_curve_analysis_boundary.py::test_curve_contract_without_eligible_checks_rejects_explicit_check_bindings`；审查者未自行执行测试。

**最小修复。** 将 `if not checks: return comparisons` 移至现有 `explicitly_bound` 集合校验之后；保留原错误规则、当前检查覆盖约束和合法空绑定返回。不新增校验框架、公共 Operation、包装对象或文件。补充上述三分支测试，并跑受影响曲线文件；最终候选需收录这两个文件的新摘要，再执行增量独立复审。父任务已开始此修复，其结果属于 R2。

## 3. 两条主要链路及保留门禁

| 链路 | 已核实的落点与结论 |
| --- | --- |
| 负面 deck 审查准入 | `tcad_artifact/plugin.py:466` 将精确主审 project 声明为 `prior_signal`，没有将其改成 inventory。第 108 行只对 pass 要求 uncertainty ready；author 默认严格条件仍在第 129 行。 |
| 负面报告提交 | `project_packager.py:1218` 仍严格解析唯一 project、计划及报告；仅按 verdict 区分 case 实现和参数值/单位一致性。第 1280 行起仍校验参数集、coverage、approved key 与可用状态；负面结论不豁免对象身份、handoff、来源和报告覆盖。`service/runs.py:453` 的可纠正输出错误与系统检查异常路径未改。 |
| 假 pass、包装与 Effect | `project_packager.py:1236` 对 pass 保留 case controls，第 1299 行保留值/单位实现检查。`transform_adapter.py:195` 从精确原件保留初始化证明，严格重解析后第 204 行仍整对象比较，第 214 行仍检查 case controls，再构造原 ReviewedDeckPackage。证明不从文字合成，缺席仍为 None；source/project 摘要绑定由现有 DeckProjectDraft 检查。Root 的 compiled admission、review/approval 和 Effect 路径未因背景例外放宽。 |
| 正常包装正控 | `test_l4_local_tcad.py:1813` 使用完整科学两 case、每 case deck binding，经实际本地 Root author→review→package；第 1888 行核对双 binding，第 1890 行核对初始化证明 canonical 字节相同。第 1903 行起拒绝错 source/project proof，第 1912 行起拒绝重建字段改变。该工程 fixture 证明调用可达，不是科学 Agent 或真实 solver 的验收。 |
| feedback→Worker 文件 | `general_science_experiment_operations.py:35` 的三组可选输入仅用于 design/review，明确 wildcard、on_demand、inventory、每组数量与每项/总字节限额；`runs.py:235` 与 `local_workspace.py:150` 沿原路径交付精确内容和 0400 文件。没有隐式聊天上下文、进展数据库或新的输入包装层。 |
| 正式目标→物化→review/revise | `experiment_intent.py:140`、`experiment.py:208` 声明必填目标列表及精确非空子集；物化第 420 行放入原总体目标并保留本轮目标和既有 rationale。`general_science_experiment_components.py:197` 严格读取正式计划、核对可选原目标 key/statement，第 226 行把引用限制为实际可见 alias。revise 仍接收完整前稿与独立修改要求。没有用总体未覆盖自动阻断每轮设计；总体 objective evaluator 的缺项判断未修改。 |
| 精确父链→新显式绑定 | `mcp_root_instance_routes.py:246` 按已存 parent_refs 顺序查询当前实例中精确对象名，使用既有 `scheduler_bindings.py:516` 的 find_name；无父件为空、未映射为 null、超过 4096 明确失败，不写状态、不找 latest。物化计划的强类型直接父件含原目标；revise 先沿唯一前稿父项回到物化计划。`test_m6a_direct_instance_management.py:717` 覆盖首轮/revise 冷 Root，加入同 key/同文本但约束不同的新目标反馈，仍找回并交付精确原件。 |

独立 review 的可选原目标端口本身只做 key/statement 对照，并不声称对任意深度父链做核心认证。精确原件选择由可读父链、scheduler 指令及显式绑定实现；新增冷启动正控对应这个已审定职责划分，没有以新别名存储或递归服务代替它。

## 4. 背景例外、ABI 与范围判断

`mcp_root_operation_routes.py:1326` 的例外只跳过 **Agent + evidence_inventory** 的 producer-output 资格检查。第 1114 行外层 family、revision、compiled approval 和 claim 检查仍依序执行；实例解析、输入数量/大小、current 和 cohort 准入在此前原路径中完成。Transform/Effect、主审对象、claim_evidence、prior_signal 和 revision 主输入没有获得这个例外。完整清点为九个既有 Agent inventory 消费者加本次 design/review；相关枚举及非 inventory/Transform 负控位于 `test_m6c_producer_topology_removal.py:273`。没有发现需要再增加通用“历史对象模式”的具体反例。

ABI 16→17 是共享 admission 语义变化；旧 compiled producer 资格不会被背景读取恢复。`test_skill_policy_producer_compatibility.py:426` 将旧记录与新记录分开，验证旧合同拒绝、新独立审查与当前 author 路径。该 fixture 只证明资格规则，实际安装版本、全目录身份、旧资格恢复清单和生产重新审查仍须 P4 后续证据及 P5 承接。

原 R1 范围内新增 curve 两文件各自承担既有目标选择规则与 Agent 语义同步，未改数值算法、端口或总体评分。初始化证明修复恰落在 R3 审定包装文件；不需要改 materializer、author/debug 签名，也不需要同时修复已记录的无 comparison 单 case anchor 基线缺陷。中英文架构文本表达一致，没有新公共 Operation 或状态机。

下列三项后续迁移属于计划第 4.1 节已允许的测试 fixture 范围，需纳入后续最终候选清单，但无须扩大十四个生产文件的行为范围：

- `test_hypothesis_review_routing.py` 把旧的 `b'{}'` 计划替换为已有合法 `_plan` fixture，以适配正式计划解析；保留原 review 路由断言。
- `scripts/l4_live_tcad_agent_probe.py:92` 的 `_portfolio` 将单目标 fixture 迁移为总体/本轮两个正式列表，原总体目标不变；不改变 prepare、launcher、transport 或部署行为。脚本名含 live 不把这项数据构造迁移变成一次真实 Agent/solver 验收。
- `test_l3_review_and_human_policy.py:35` 临时构造的 `blind.csv.consume.v1` 声明消费已独立审查的 observation，却将其强类型输入覆盖为 inventory。ABI 17 下 missing-review 正控因这个旧 fixture 用途冲突失败。最小迁移是直接复用原 `REVIEWER.inputs[1]` 的 `prior_signal` 并同步第 224 行用途断言；第 236/253 行缺审查、错 revision 拒绝与第 242/259 行精确审查正控全部保留。它不在生产注册的九个 inventory 消费者中，不构成生产用途例外或删除 review 负控的理由。

## 5. 测试状态与下一轮边界

P1/P2/P3 聚焦证据已由父任务执行并保存，包括 P1 94 pass、P2 generic 198 与 curve 24 pass、P3 四文件 212 pass、父链查询 13 pass、历史合同 5 pass。它们支持上面的对应工程行为；不能覆盖 R1 新发现的空适用检查分支。此前父链边界 fixture 的失败日志保留，最终修复结果另存，没有以删除失败记录替代验证。

本报告提交时，P4 全收集后的逐文件串行验证仍在进行，`p4-checks.json` 仍会更新；原收集为 683 项，新增三项反例后为 686 项。已出现正式 Schema 迁移相关 fixture 失败并由父任务调查，尚无最终冻结的全套/安装态结果。本报告不写“全套通过”，不将滚动日志归入原 R1 候选的 PASS 证据。

下一轮只需核对本项编译器顺序修复、必要 fixture 迁移、最终候选身份与完整串行/安装证据；若出现新的具体失败再沿其实际调用链判断。P5 的部署/资格恢复以及 P6 的真实负面审查、科学范围判断、无聊天续研仍是后续验收，不能从离线模板或工程正控推导完成。
