# 反复合同阻断：框架级根因审视

2026-09-10。范围为当前未提交工作树及已部署流程的公开控制记录；本轮只读审查生产代码，没有修复源码、运行测试或访问研究数据库/Worker 工作目录。按用户要求停止无效分析重试，将该 Run 显式记录为 failed，保留执行产物。本文不是新的科学结论，也不是已经通过独立审查的实施计划。

## 总判断

系统已经统一了注册入口和一部分结构约束，但尚未统一一条任务从输入成立、可执行到成果可提交的行为合同。OperationSpec 引用了 Python 校验器，不等于 Python 校验器内部的所有前提已经进入输入声明和前置校验。

最近几次失败表面都叫“合同不一致”，实际分布在三条接缝：证明的接收方式、收集结果的证据范围、远端执行协议。共同机制是：局部组件分别满足自己的规则，交接处缺少真实组合验收；矛盾晚到 Agent 提交或正式执行时才暴露。随后输入错误被错误分配给结果作者纠正，Root 又看不到拒绝细节，形成无效重试。

不能归因于 Agent 能力不足，也不能靠削弱证据身份检查或扩大提示词解决。此前将局部测试、独立审查及打包成功表述成整体框架已经充分保障，是验收范围判断过早。

## 已确认的当前事件

- 本轮原研究记录在新部署后成功打包、审批通过。
- 初次正式启动返回 unknown runner tool；同步远端 runner 后，同一请求成功 submitted/running，随后 collected。
- 收集到 solver_log、一个 PLX、tcad_log 和 tcad_manifest；尚未得到六案例完整结果，不能声称求解成功。
- 分析 Run 的预检通过，实际提交 8 次未成功。最后工程拒绝为 tcad.result_analysis.context_binding，路径 $.payload，消息 bound solver output name, media type or bytes differ from manifest。
- 分析者只回报工程诊断，没有给 Root 传递未封存科学结论。已停止重试并通过公开 run_record_failure 将任务记为 failed；没有封存分析结果。

## F1：输入可用性放进输出提交校验，导致本来不可能完成的任务获准创建（严重）

路径：operations/invoke.py 的 preflight_operation、_validate_port_binding、_validate_input_content → result_analysis.analysis_parentage → Agent → result_analysis.analysis_context → _identity_context。

前置检查主要覆盖端口基数、schema 标签、媒体类型、大小、current、部分声明字段/历史结构和元数据父链。TCAD analysis_parentage 检查精确父链，但不检查每个输出是否包含在 manifest 内。

_identity_context 只依赖 sources 与 binding_descriptors，不使用 Agent 的 payload。它却在 analysis_context 的提交阶段才执行，包括输出名、媒体类型、大小、哈希与 manifest 对齐。这些输入一旦绑定便不可变。因此本次任务在创建时就不可能提交成功，改写任何科学报告均不能修复。

结论：preflight 与 invoke 共用入口，只证明二者一致，不能证明它们与 submit 的全部输入前提一致。编译器可验证引用关系与结构，但无法由任意 Python 函数自动证明这个可执行性性质。

## F2：同一个“输出”对应两种证据范围，没有明确交接方式（严重）

远端 remote_runner_py36._collect 先返回 manifest.outputs 的文件，再额外附加 tcad_log 和 tcad_manifest；本地 execution_control.tcad_collect 同样处理。额外诊断也是受控收集物，但不是 manifest.outputs 的成员。

分析入口 solver_outputs 是通配 evidence_inventory，可接收这些字节。_identity_context 又要求该端口中每个带 output_name 的描述都能找到 manifest 记录。Root 把收集器公开返回的 tcad_log 放入 solver_outputs，父链检查通过，提交则必败。

这不是日志内容不好，而是“求解器声明产物”和“运行器附加诊断”被当成同一种对象。目录文字和通配 Schema 不能表达它们的差别，系统将正确选择端口的知识留给了调度者。

必须保留两类文件的身份和可追溯性，但不能把“未列在求解器产物清单”解释成“不是合法诊断”。需要一个明确的收集证据清单或声明的诊断接收方式；二者择一闭合，不叠加新实体。

## F3：错误责任分类依据异常类，未依据 Agent 是否有能力修正（严重）

service/run_outputs.py 将 context checker 抛出的 SemanticRuleViolation 转为 RunOutputError，并统一加 $.payload 与输出规则编号。其他异常才成为 RunCheckerError。service/runs.py 的 submit 遇 RunOutputError 返回 rejected，保持 running；遇 RunCheckerError 才结束失败。

当前输入矛盾由 _identity_context 抛 SemanticRuleViolation，于是程序明确告诉 Agent“这是你可以修的输出”。即使规则编号已展示给 Agent，也没有改变错误对象归属。

框架宪章本来规定 SemanticRuleViolation 只表示 Worker 可修订错误；实现的异常选择违背了这个语义。无需新增一套异常治理平台，应把确定的输入故障放回前置检查，并使遗漏的输入/校验器故障终止而非要求作者重写。科学证据不足可以形成有限报告，与结构性输入矛盾是不同问题。

## F4：控制面知道“发生过活动”，调度者不知道“连续失败”（高）

service/runs.py 的 submit 返回错误详情给 Worker，但只用 record_activity(run_id, 'output_rejected') 更新活动时间并记录事件类型。mcp_root_run_routes 的运行态投影有 last_activity_at、state、candidate_accepted，没有最近拒绝规则、原因和次数。

Root 禁止读取未封存科学草稿是正确边界，但不应因此看不到工程故障。现有投影使8次拒绝看起来只是running及新活动。父调度者又把活动更新报告为推进，直到用户指出才检查。这是系统可观测性和调度行为共同的问题。

复用已有 Run/activity 记录即可暴露有界工程摘要：最近拒绝类别/规则/输入或输出位置、次数、是否可在本轮修正。不得暴露草稿或隐藏科学判断。重复拒绝不代表预算内有科学进展；固定输入故障应当直接停止。

## F5：测试验证了局部规则，没有验证真实交接闭合（高）

此前打包测试直接注册没有生产者审查合同的计划，漏掉必需证明；上一轮已用真实producer/reviewer记录修复这一测试路径，但其范围止于打包。

当前 tests/operations/test_tcad_result_analysis.py 的 fixture 手写 manifest 并将计划产物放入 outputs，分析输入也手写为对应文件。它不会自然包含收集器额外返回的 tcad_log。正负测试能够证明这些手写输入一致或错配被拒绝，却不能证明真实收集结果可被分析。

此外，本次静态审查发现一个具体测试调用失配：test_no_contract_author_review_package_execute_preflight 通过 runpy 调用旧 helper 的两个参数，而 test_materialized_sprocess_author_review_package_preserves_case_anchors 已新增必需 produced 参数。该旧调用需要同步，本次未执行因此不报告为实际测试失败。这进一步说明前轮影响检查漏掉了跨文件测试依赖。

需要替换这类自造接缝：小型受控进程/collector → execution_outputs → analysis preflight → 最小有限报告 submit；正例要包括失败执行、附加日志、缺失产物，负例仍覆盖哈希/来源错配。无需跑大求解器或全量测试，也不应让每次科研都支付另一串审查 Run。

## F6：本机合同摘要与远端协议能力的验证范围不同（中高）

execution_bridge.start 会在 submit 前调用 lookup_submission，防止未知提交状态造成重复执行；这是应保留的安全措施。安装/升级 runner 的 probe 只调用 tcad_capabilities，未覆盖 lookup_submission。能力查询成功不能证明正式执行需要的全部协议可用。

本机 Operation 摘要一致证明不了远端进程已经实现这些方法。应由同一部署/探针覆盖实际必需的最小只读协议能力，报告缺失接口，并在获批的正式执行前发现问题。不要删除 lookup 或以聊天授权跳过它。

## 为什么前几轮修复没有从根本消除问题

1. 把“唯一注册入口”扩大解释成“唯一行为语义”。Python validator、collect adapter、端口用途和远端工具仍各有未显式连起来的前提。
2. 规则分类偏向验证结果是否可信，没有同等明确地要求输入组合可用、错误归属可判、失败可交接。
3. 每次从最后一个拒绝点修起，验收也止于该点；不同的失败点被误认为同一个问题已经修完后又复发。
4. 正例多使用与校验器共用假设的fixture，而不是上游真实生成的文件和元数据。
5. 动态输入关系不可能仅凭 Schema 全局推导；把目录诊断升级为硬门禁会误拒绝合法可选/历史调用。R2 将它收窄为诊断是正确的，但同时也意味着它没有、也不能宣称覆盖此次内容语义矛盾。

## 应保留什么，应该归并或前移什么

保留唯一目录、不可变 Artifact、精确父链/哈希、独立审查、人工执行批准、四态 Run 和重复提交查询。它们在本次失败中没有失去必要性。

优先只做三类工程整理：

1. 将确定仅依赖输入的检查归并为消费者的输入校验，由创建 Run 前调用；submit 如需防篡改复核调用同一函数。输出校验保留结果对输入的引用、计算重放及结论一致性。不能把科学方法争议、未来才会产生的输出或可选评分条件前移成阻断。
2. 闭合执行产物与诊断的交接语义。优先沿用已有清单/输入类型表达真实受控来源，保留身份验证；不要同时新增多套平行清单、诊断服务和特殊审批。
3. 使用现有Run记录提供工程拒绝摘要，并将“不可能由本轮输出修正”明确返回调度者。不同错误交给不同责任层；不能把所有非通过都路由到作者重试。

每项整理都必须同时证明：有效原始交接能够完成有限报告；篡改和跨轮错配仍拒绝；固定输入故障不消耗8轮输出重试；会话重启后可以读取失败理由。兼容回滚以新旧合同摘要和原记录可读性为界，不修改旧Artifact或继承旧资格。

## 结论与下一步界限

这是一组接口组合与失败责任的架构缺陷，不能靠再加一句提示、一个孤立端口或更多局部校验解决；但也没有证据要求推倒整个控制框架。应把范围从“修当前错误消息”改成“让真实执行结果能交接到有限分析，且错误落到能处理它的层”。

当前分析Run已标记失败，不重复求解器，不伪造科学输出。下一步需据此制定并审查一次针对上述三项整理的具体方案，再实施；本报告不宣称已修复、已跑新回归或完成科学端到端研究。
