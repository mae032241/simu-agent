# 用户文本接入：工程实施与验收

状态：已按冻结 R2 实施，独立生产实现静态审查 PASS，40 项最终核心检查与隔离 wheel/stdio 验收通过。**用户已安装重启；[A10 真实历史节点接续验收通过](LIVE_ACCEPTANCE_20260914.zh-CN.md)。** 两个全新科研 Agent 完成设计和独立审查，同一原文显式传入两轮；一次输出拒绝在同 Run 修正。未执行新 TCAD 求解，不宣称全量测试通过、Hardened 成果提交通过或 Fig4 科学目标完成。

## 范围和依据

- [R2 计划](../../USER_TEXT_CONTEXT_INGRESS_PLAN.zh-CN.md) SHA256：`7b4f194326912bc3c697cbfec5d8dc9f3d8cba461ee0bcd82217962ab6d543c0`。正文保留送审字节，实施状态由本记录及索引负责。
- R1 独立审查的唯一阻断为调度重建丢失 producer_inputs；R2 补齐后获得[独立计划 PASS](../../reviews/USER_TEXT_CONTEXT_INGRESS_PLAN_R2_REVIEW_20260914.md)。[独立实现审查](../../reviews/USER_TEXT_CONTEXT_INGRESS_IMPLEMENTATION_REVIEW_20260914.md)另行评价本候选。
- 基线为 HEAD `096a13fd89aacf2d4e73f77e87ab3174e5f89ec3` 加本轮开始时的既有工作树，不能将此前 handoff 改动混入增量。[基线文件摘要](baseline-files.json)及本机 `/tmp/scid-user-text-impl-20260914/baseline` 保留原文件；没有从 HEAD 覆盖源码或新建 git 提交。
- 生产增量为 14 个 Python 文件和 `roles/scheduler.md`。其中 12 个 Python 是计划明列模块，另两个 `curve_score/science_operations.py`、`tcad_artifact/result_analysis.py` 仅同步受影响 materializer 的 configuration_identity，落实计划的组件身份要求，没有新增业务逻辑。
- 同步双语 ARCHITECTURE 对应段落。旧审查原文、先前源码改动和两份用户 Fig4 文档保持。

## 实际交付

1. Root 新增 `artifact_ingest_text(name, text, on_conflict)`。1—8,192 个有效 Unicode 码点原样存为 UTF-8，不裁剪空白、改变换行、生成摘要或创建项目临时文件。使用现有名称锁、指纹、幂等及修订流程，保留实际 creator；`source_origin=user_via_scheduler` 存于元数据。登记不创建 Run 或改变 current。
2. 共同声明在 25 个公开 Agent 中增加独立可选 user_context，最多四条、每条 32,768 字节；其余 25 个 Operation 的 spec 不变。原 current_progress 等端口逐项不变，Agent 总输入预算增加 131,072 字节。输出仅扩展已有引用检查的可选来源，不新增“必须引用或采纳用户意见”的检查。
3. 文本用 prior_signal/on_demand，不自动成为正式来源。参数 source_catalog 依据已保存的 source_material 端口别名检查；一般说明引用可引用 user_context。Root 和 RunService.schedule 均从已经读取的精确 completed 主输出生产者投影原有序输入，资格投影使用同一保存记录。保留全部父件追溯，没有新的持久化表、来源登记或状态机。
4. assignment 与 analysis-start 展示原文路径和真实来源标记；没有标签的旧记录不冒称用户输入。满索引沿原 assignment 导航可读，不复制原文。所有相关角色共享“科学意义由角色判断”的说明。
5. 完成节点创建新 Run；改变输入的失败接续用 draft_from，原样 resume_from 仍需相同输入和合同。复用 Worker 重新打开新 assignment，旧成果和失败状态不改写。用户文本不替代独立审查、change_request 或 UI 批准。
6. 沿用原数量/大小拒绝，仅为三处诊断补充实际值与编译声明上限。未新增门槛。新文本模型采用同一 Pydantic 声明的一次 strict model_validate，使非法 surrogate 在 JSON 解码抹掉字段位置前定位至 text；其他 Root 工具保留原解析路径。

[50 项声明前后比较](catalog-comparison.json)确认原端口、原输出约束、非输入预算及所有 Operation.version 保持；无需 VM runner 改动。

## 验收结果

| 计划项 | 工程证据及边界 |
| --- | --- |
| A1 原文 | 实际 Root/runtime 的中文、CRLF、空白、组合字符、最大补充平面字符、非法 Unicode、严格类型、幂等、修订与重启旧文均通过；Schema 与生成工具清单一致。 |
| A2 无说明 | 25 个声明编译覆盖；原 hypothesis 可引用 foundation 内来源键并实际提交，原参数资格、代表性设计/审查/分析/历史兼容路径回归。并非 25 个真实科研 Agent 各运行一次。 |
| A3/A4 来源 | 实际提取→审查→测试 UI 资格→假设→批评→证据修订，通过完整 preflight/invoke 验证无说明和仅审查有说明均排队。参数提取有说明、仅参数审查有说明均能到资格请求。遗漏/替换正式来源仍失败；生产输入未知返回 intake_audit 定位。user_context 可被引用，但放入正式参数 source_catalog 被定位拒绝，修正后同 Run 完成。 |
| A5 容量 | 四条原 current_progress 加四条最大 Unicode 原文可用，说明合计 131,072 字节没有被挤掉；第五条、单项大小和总大小拒绝包含对应公开上限。 |
| A6 交接 | Local 新建/复用均读取新 assignment 原文并完成提交；旧无标签不伪造来源；满 12 KiB 索引仍沿原件导航可达。Hardened 仅验证支持的测试 transport 的声明、assignment 与原件，不声称成果提交。 |
| A7 恢复 | 实际失败后增加说明走 draft_from，保存文件进入新工作区并完成；改变输入的 resume_from 拒绝，原样 resume 预检通过。旧 failed 状态保留。已有跨版本原件/审查兼容与草稿回归另有定向覆盖。 |
| A8 安装 | 四个 wheel 在不继承系统 site packages 的临时环境安装；模块位置验证来自 wheel，installed catalog 编译25角色，实际生成 enabled_tools 一致。Root 与 Worker 经 `python -I` stdio proxy 完成两轮原文登记/读取/提交，同一 Worker 第二轮显式绑定上一封存结果和同一说明。 |
| A9 职责 | 角色可以引用说明或保持原结论；没有采纳证明门禁。正式参数来源、独立审查及原恢复/执行授权条件保留。这里只验证程序边界，不把夹具文本当成真实科学推理。 |
| A10 现场 | **已通过[安装后真实验收](LIVE_ACCEPTANCE_20260914.zh-CN.md)。** 15个安装文件匹配，25个公开Agent具备原文端口；两个全新Agent从精确Fig4历史节点完成设计和独立pass审查，显式读取同一原件。一次既有输出互斥规则拒绝在同Run修正；原生命令未观测及字段诊断精度缺口单列。没有新TCAD执行，不宣称科学目标完成。 |

最终[40 项核心检查](final-core-tests.xml)全部通过；其他共享合同、分析、历史及恢复批次的原始结果见[串行检查账本](checks.jsonl)。这些批次包含通过项及下述已归属失败，不能将它们整体写成通过。

隔离安装完整成功，见[安装构建日志](installed-build.log)、[stdio 结果](installed-probe.stdout)和[探针](install_probe.py)。两轮封存使用确定性测试正文，不是真实科研 Agent。所有执行串行，BLAS/OMP 单线程，进程树 RSS 硬中止阈值 512 MiB，测试批次150秒、单次构建安装300秒。最终核心测试峰值约146.8 MiB；隔离构建/安装含其两个测试服务峰值约399.4 MiB、12.3秒；无内存/时间中止。未运行全量 suite。技能提及的 `validate_architecture_constraints.py`、`run_science_control_bench.py` 不在本次实际子仓库中，未虚报执行。

## 检查中的失败与处置

- 新回归的中间夹具问题：缺少 instruction、错误猜测 Transform 主输出语义名、缺少来源 title、错误断言恢复错误码，均在测试中修正。最后40项通过，未据此放宽生产检查。
- 直接受影响的旧夹具：纯 preflight 手建 map 缺可选 user_context、克隆输出保留新上下文而输入漏掉端口、完整端口枚举、原总预算边界，按编译声明适配。原根级来源连续性测试只伪造元数据/信号，且在改前已经失败；以有真实生产记录和测试 UI 资格的完整链路替代，源码完整性要求没有放松。
- [13 个仍存在的既有失败](preexisting-failures.json)已逐项在实施前源码快照复现。包括旧 run_list 分页形状断言2项、blocked review 相关提交/诊断假设5项、revision诊断与恢复预算错误码断言2项、execution-context参数错误分类及设计输入夹具4项。每个 nodeid 链接到对应 baseline 日志。保留记录，不改 unrelated 生产行为，也不声称这些功能问题已关闭。
- Hardened transport 在尝试旧 `_write_result` helper 时发现其 general workspace 挂有 finalizer、却没有可写文件策略的夹具限制。依计划将本项验收限定为声明/原文文件一致，Local成果提交有独立实测；本轮未修改 Hardened 文件准入或为其造新策略。
- 编译快照脚本最初使用不存在的 catalog.operations，随后改用现有 operation_ids/operation；包裹参数声明时一处括号错误在编译立即发现并修正。旧基线副本第一次缺 SQL 静态资源，补齐未修改资源后才做实际归因。所有中间日志保留，没有用这些探针失败冒充生产科研故障。

## 部署与现场收尾

部署前让已有活动 Run 在旧合同下完成，或明确停止并确认草稿保存，再更新控制端及生成角色配置并重启。本功能改变输入声明与角色摘要，不支持让活动 Run 穿过升级继续提交；旧已封存的同版本兼容记录仍沿原规则消费。无需同步 VM runner。

安装后 A10 已按上述现场记录完成，当前停在封存方案及独立 pass 审查。下一次科学执行仍沿既有 author、实现审查和执行审批流程进行；此次验收不替代那些条件。回退只恢复实施前代码/配置，不删除原文或研究记录、不改写 Run 状态。
