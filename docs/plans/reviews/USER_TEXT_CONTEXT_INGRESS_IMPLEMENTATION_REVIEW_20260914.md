# 用户文本接入独立实现审查

结论：**PASS（工程实现静态审查及最终验证证据复核）**。本轮未发现需要修订生产实现的剩余阻断。40项最终核心检查和一次隔离wheel/stdio验证的完成证据可信，支持本候选进入部署及现场验证。此结论不表示部署完成，也不表示R2的A10现场最小闭环已经验收；不宣称全量测试通过或Hardened成果提交通过。

日期：2026-09-14。

## 对象与方法

- 对象：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2` 当前工作树相对 `/tmp/scid-user-text-impl-20260914/baseline` 的用户文本功能增量。未将 HEAD 之后上一轮尚未提交的 handoff 改动混入本轮。
- 依据：冻结 R2 计划 `docs/plans/USER_TEXT_CONTEXT_INGRESS_PLAN.zh-CN.md`，SHA256 `7b4f194326912bc3c697cbfec5d8dc9f3d8cba461ee0bcd82217962ab6d543c0`，及其独立 R2 PASS 报告。审查时重新读取并核对计划哈希。
- 按 `scid-cross-boundary-review` 与 `karpathy-guidelines`，静态逐项比较 14 个生产 Python 文件及调度角色资源，并追踪相邻调用者、消费者、编译 Schema、真实 Root 调度与 Worker 提交路径；阅读双语架构、设计宪章、相关测试源码和实施方有界检查日志。
- 最终复核重新计算了报告所列15个生产文件的SHA256，全部与原受审快照相同；只补记完成后的日志、JUnit、安装probe及基线失败证据，未重复审查未变生产代码。
- 本审查者未运行测试、构建、安装或求解器；未调用生产控制/科学工具，未读取生产 state 或 Worker 私有目录，未修改仓库、未派生 Agent。唯一写入为此 `/tmp` 报告。

## 关键核对

| 边界 | 核对结果 |
| --- | --- |
| 原文与登记身份 | `mcp_root.py` 的公开 `IngestTextInput` 仅接受 name/text/on_conflict，1—8192 码点；非法 surrogate 定位到 text。`mcp_root_instance_routes.py` 直接 UTF-8 编码并把固定 kind/schema/media/origin 和原文字节摘要纳入原有名称指纹、创建锁、revision 机制。`intake.py` 保留原字节和实际服务调用者，来源标记在元数据中；没有临时项目文件、摘要、Run 或 current 写入。 |
| 单一声明及容量 | 静态比较实施方前后完整 50 项目录快照，25 个公开 Agent 均恰好增加一个可选 `user_context`，0—4 项、32768 字节/项、`prior_signal`/`on_demand`，使用明确的 general_science opaque 组件；各聚合预算增加131072字节，原输入和其他限制保持。其余25项非 Agent 的 spec 未改变，所有 Operation.version 保持。 |
| 引用与正式来源 | 共同助手只向已有 context_validator 的 context_sources 加别名，不新增校验器或修改 evidence inventory 枚举触发规则；原 hypothesis 的 foundation 内来源键支持保留。参数提取依据 `ValidationSources.binding_descriptors.port_name == source_material` 限定 source_catalog，普通引用仍可引用说明；其他校验器按既有命名输入解析，不把新增文本当 JSON 或参数值。 |
| 两次预检 | Root 输入解析与 `RunService.schedule` 的权威重建各自从精确 producer 查询投影有序端口绑定，仅对 completed 且 output_ref 精确相等的主输出提供 `producer_inputs`；None 与空序列保留区别。调度层继续独立重建并再次 preflight，没有信任上游缓存或绕过准入。 |
| 来源与资格 | `_evidence_revision_cohort` 只从原 intake audit 的 source_material 取得正式来源集，保留原 intake/foundation/portfolio/critic 关系与审查 verdict；未知元数据明确定位。参数资格分别核对提取及审查的精确有序输入、完整父链和过滤后的正式成员；existing evidence_sources 用途筛选未扩大，Transform 家族原实现保留。新增背景不成为资格或批准新前提。 |
| 模型可见性 | assignment 只投影 user_context 对应记录的固定 origin，未暴露完整 labels 或新增内部身份。原文依既有输入文件路径可达。分析入口先索引原件再节选，携带同样来源字段，索引省略时通过 omission_source 回到完整 assignment；不复制用户全文。无该标签的历史记录不会冒称 user_via_scheduler。通用、figure、curve、TCAD及参数角色均接入共享职责提示。 |
| 历史与恢复 | 新说明进入普通新 Run 的原绑定/指纹/父链。新增文字或合同变化采用现有 draft_from；原样 resume_from 仍校验原摘要和有序输入。恢复算法、尝试预算、实例及后端检查未改。Local 新实例或同角色复用都重新 open assignment；既有活动Run合同检查与同版本已封存成果兼容消费仍分开。 |
| 职责与独立审查 | 文案明确角色自行判断用户要求、建议和事实主张的意义与力度；未添加采纳证明、阅读回执或科学真假分类。文本不能取代正式 change_request、匹配独立审查、UI 决策或直接改执行输入。原 review/approval/effect 声明不变。 |
| 最小范围及身份 | `science_operations.py` 和 `result_analysis.py` 两个额外生产文件仅给实际受影响的 analysis materializer 记录 configuration_identity；来源 guard、参数 context/projector 的现有身份也已更新。没有数据库迁移、第二套来源持久化、通用依赖图或运行状态机。 |

## 审查中发现并闭合的事项

R2 要求越界反馈给出实际值和公开上限。初版实现保留了既有泛化错误文字，条数/字节/总量的拒绝虽正确，却未直接显示上限。本审查反馈后，实施方在已列入范围的 `operations/invoke.py` 三个原有拒绝点补充动态 message；复查确认未更改条件、门槛或错误类型，分别显示数量范围、max_item_bytes及max_input_bytes。没有新增控制分支。

历史兼容测试曾在 blind fixture 的克隆 consumer 编译时漏掉新增 context_sources 对应的输入，报 output_context_invalid。实施方仅在测试克隆中保留 user_context，生产25角色声明没有该缺陷。其余旧声明精确枚举、纯preflight map及聚合阈值夹具已按新增合同作最小调整；最终复核确认没有放宽生产binder，容量负控仍要求越界拒绝并核对动态上限文字。

## 最终验证证据复核

最终证据已归档于 `docs/plans/evidence/user-text-context/`。本审查逐项读取实施记录、核心JUnit、原始日志和安装probe，并核对归档副本与 `/tmp/scid-user-text-impl-20260914/` 原件的字节摘要一致。下述通过结论来自已完成执行记录；本审查没有重跑检查。

| 证据 | 独立复核结果 |
| --- | --- |
| 最终核心批次 | `check-1789380221233193748.log` 为40 passed；`final-core-tests.xml` 有40个testcase、tests=40、failures=0、errors=0、skipped=0，与账本exit_code=0一致。覆盖文本6项、交接4项、上下文合同6项、参数10项、假设路由9项、容量/重复/跨实例5项。执行账本21.87秒、峰值153948160字节（146.8MiB）、无中止。 |
| 原文与交接 | 已完成用例覆盖Unicode/CRLF/空白、8192码点边界、非法编码及类型、幂等/revision/重启；Local新/复用Worker原件读取与正式提交；Hardened assignment和原件读取；分析满索引导航、旧无标签记录不伪造origin。 |
| 来源、资格与恢复 | 完整提取→audit→fixture UI资格→hypothesis→critic→evidence revision的Root preflight及invoke，在无说明、仅audit有说明两种情况下均排队；保留替换/遗漏来源及缺生产元数据负控。参数提取有说明、仅审查有说明均到资格请求；背景可引用但不能成为source_catalog正式来源，纠正后同Run提交完成。四项progress加四条最大原文可用；越界消息有声明上限；新增输入draft完成，strict resume改变输入仍拒绝。 |
| 实际安装 | `installed-build.log` 记录scidiscovery、tcad-artifact、curve-score、curve-figure-evidence四个wheel成功构建和安装。probe在不继承系统site packages的临时venv中断言实际生产模块位置，编译installed catalog的25个Agent；实际生成并解析配置，断言enabled_tools等于SCHEDULER_TOOLS及ROOT_TOOLS。 |
| stdio完成路径 | `check-1789380152258612310.log`、`installed-probe.stdout`及probe源码相符：Root和Worker都经 `python -I` stdio proxy完成两轮精确原文绑定、读取和封存；第二轮复用同一Worker，显式绑定上一成果及同一原说明。每次提交后Root查询completed及正式选定摘要。账本exit_code=0、12.3秒、峰值418791424字节（399.4MiB）、无中止，处于300秒/512MiB限制内。 |
| 历史失败归属 | `preexisting-failures.json` 列13个保留nodeid，全部在所指基线日志的FAILED摘要中存在，具体错误与当前观察吻合：981日志2项run_list分页旧断言；0002102577728日志9项blocked review、revision诊断/预算及execution-context已有问题；0115420942527日志2项input_content_reader_missing。直接受影响夹具适配后暴露的后两项也在改前失败，没有据此修改生产行为。 |

跨边界验证具有可信依据：正例经过实际Root预检/调用、Worker受控提交和保存状态；必要负控仍在对应入口拒绝；安装模块与stdio入口经过实际执行，未用源树PYTHONPATH替代安装。测试克隆端口和额度的调整与声明变更一一对应，没有把无效输入改成被生产规则默许。最终40项通过不覆盖或消除另外13项基线失败；其他包含失败的批次不能整体称为通过。

这些是确定性测试控制生命周期及夹具科学正文，不是真实科研Agent的推理结果。Hardened用例只证明声明/assignment/可读原件一致；既有blind finalizer写入策略问题未纳入本轮，不以该测试冒称Hardened正式提交已通过。Local正式提交有源树和安装入口覆盖。A8工程安装验证已完成；A10真实现场科研任务未执行。

## 后续限定

1. A10仍待实际部署后由真实用户原说明、精确历史节点、新科研Agent封存结果及下一任务显式复绑同一说明验证；保留正式结论、实际拒绝/错误和耗时。不以fixture、登记成功或接口出现宣布功能全部完成，不为验收强跑TCAD。
2. 部署和回退按R2先处理原合同下活动Run；本报告没有执行部署、审批或生产任务。旧已封存成果不因新增端口的同版本digest变化统一退役。若此后生产代码改变，应核对新的增量；无需为本功能扩修已归属的历史问题。

## 精确受审生产快照

下表14个Python文件与1个角色资源的“路径→SHA256”映射，以按键排序且无多余空白的JSON编码计算总摘要：`8926a4d33bd5799c149f67208a0b23fa5ebd2718a50134f744a13792243b5ea9`。

| 文件 | SHA256 |
| --- | --- |
| `plugins/curve_score/curve_score/analysis_workspace.py` | `d743a6e14b641f1979572c3315073be43cb1caff1a2c03277b9b741b908b089f` |
| `plugins/curve_score/curve_score/science_operations.py` | `834d8ea6bd067b8c85e9ca357b4e8a5f8ff8fa8127eca45552b280572c68f9e8` |
| `plugins/tcad_artifact/tcad_artifact/parameter_operations.py` | `5f61e8f788a8ba032eb51f0773d98e6810f4afae7cd3ed07b28b11dd5be20567` |
| `plugins/tcad_artifact/tcad_artifact/plugin.py` | `4e02338b32bf0a5b4ebbe2908a733d160a8d25ae4ca87a40a246615cd461b8df` |
| `plugins/tcad_artifact/tcad_artifact/result_analysis.py` | `26f00479e1f3117fa30996a1d29158748c5db37f81103848c93f014081d7b43c` |
| `roles/scheduler.md` | `2f0ea28ecda62662c3b255ba1dd9bd11d47a2a28212cfa9d7d03e75454c43c17` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `aabf9ada566ddf88370a32b3476b38a8682c7ad38de8f46c798aa0409dd15b2b` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py` | `4845d638ef70add1acdccf74553c30aabe9c14f87dd4d5c08c63898ca9a19266` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | `94a74950df3d6443759ae68484ee08851d501fd66c23f24ca9138f1e42ef73cd` |
| `src/scidiscovery/artifact_agent/service/intake.py` | `f908a46d30d192ede190b84caab5d0421a471a0669ba2b42c7f63261ca579354` |
| `src/scidiscovery/artifact_agent/service/run_assignment.py` | `5623a57ad5eb5bba2fee38fb128eb4a2bf5eadd4018c07c876ac1b2011ce7ca1` |
| `src/scidiscovery/artifact_agent/service/runs.py` | `f78aa19124659041447237fd17a7168af510d2bb7e224b5b103907a284e6d877` |
| `src/scidiscovery/general_science_components.py` | `69308d3762d35c4f1db5dad5534a9c42e8efad368b4d1044e0b03fdca52149c5` |
| `src/scidiscovery/operation_declaration.py` | `2d4f5ae72a04378c226a12df73cc5ea394ebf0af17617c87f8b9fda804411705` |
| `src/scidiscovery/operations/invoke.py` | `9a1f8262ac303b4b492828f59dd6f64604cac4aa7354704f105b3293fa749aa6` |
