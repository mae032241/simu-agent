# 输入校验职责修订计划 R2 独立工程审查

日期：2026-09-10。结论：**REVISE**。

审查对象：`docs/plans/INPUT_VALIDATION_PHASE_REPAIR_PLAN.zh-CN.md`，SHA256 `0a461050b458b7c35c876574cc72817f2c15c3284b781a1bfe090f3c1eee9cf2`。源码参考为当前含大量既有修改的工作树，HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`，不是对该 HEAD 的干净版本审查。本次只新增本报告，未实施、未运行测试、未编译目录、未部署，也未访问科学实例存储。

## 总体判断

R2 已纠正 R1 的根本方向：输入准入与输出验收分离，输出可读冻结证据但不得重判输入；只有改输出能解决的问题才能要求作者改稿；框架故障必须保全交付。P0 全部可达规则分类、P1 单一声明、禁止提交调用 input_validation、评分可选和有限分析可交付，都符合用户第一准则，也符合设计宪章对隐藏规则、插件故障和科学所有权的约束。无需退回 TCAD 特判或新增规则引擎。

但计划仍把两个现存机制当成足以承接目标的基础：修复后恢复、合同失配时封存。源码表明它们存在明确反向门禁。P3 的“缺口同阶段补齐”和 P6 的“兼容矩阵”承认有工作，却尚未作出这些必须先确定的边界决策。以下两项为阻断；另两项为同轮必须校正的工程定位问题。

## 分级发现

### F1 / 高 / 阻断：修复后使用恢复材料与现有精确 resume 条件冲突

**计划位置：**第 1 节 admission_defect 处置、P3“只允许既有受控恢复接口”、P6 旧失败恢复材料。

**源码证据：**`service/runs.py:1096` 的 `_recovery_digest` 同时要求旧新 `operation_digest` 完全相同、按序全部 `input_refs` 完全相同；`recovery_available:1022` 先调用 `_compiled`，后者在 `:994` 拒绝已变化的合同。Root `_prepare_operation_call` 在 `interfaces/mcp_root_operation_routes.py:1074` 调用 `validate_resume`，拒绝映射为 `recovery_source_unavailable`。因此这是实际公开入口门禁，并非只存在于一个辅助函数。同一后端身份和恢复次数也有独立检查。

**可达场景与影响：**旧分析因准入漏检失败，部署迁移了 context checker 的正确新版本，Operation digest 必须改变；或者将已绑定 tcad_log 从 solver_outputs 移到新增 diagnostics，输入序列可能改变。即使旧候选已完整保全，现有接口仍无法将它送入新 Run。未变化合同下的恢复测试不能证明本次目标，作者仍须重新生成或绕过受控输入。P6 明确禁止伪造旧 digest，因此不能靠版本不变解决。

**必要最小修正：**计划必须区分“同合同重试”与“修复后仅复用草稿”，并明确后者如何通过受控现有入口接入新 Run。保留现有 resume 的精确身份匹配，不能放宽或删除摘要/输入比较。对修复后的接续，保留旧记录，显式受控绑定旧草稿来源与摘要，把它当无科学资格的起始材料；新 Run 用真实新合同与精确新输入重新准入、独立验收，明确实例/后端/次数和版本边界。可以窄扩展现有入口的材料绑定能力，不需要新草稿服务或新状态机。若选择不支持跨合同接续，则须撤回“修复后恢复”和“旧记录继续受阻不能完成”的承诺，不能同时声称满足用户目标。

**必须验收：**旧合同失败并保存 → 重启加载真实新 digest → Root 新请求重新准入 → Worker 实际收到旧草稿 → 新候选完成验收；另验旧证据资格不被继承及错误来源被拒绝。必须包含端口重新绑定情形，不能只有新旧 digest 相同的恢复。

### F2 / 高 / 阻断：合同失配恰好发生在封存之前，现有失败链又依赖同一失效合同

**计划位置：**P2“运行合同不匹配……保留恢复材料”、P3“先保全交付”、P6 活跃任务处置。

**源码证据：**`runs.py:734` `_validated_candidate` 第一项是 `_compiled(value)`，之后才 finalize 和 seal；`_compiled:994` 抛 `RunStateConflict`，不是 submit 在 `:463` 捕获的 `RunCheckerError`。`record_failure:510` 也调用 `_compiled`，非 timeout 时直接重抛；已经 failed 的同类记录在 `:502` 返回而不补救工作区。`_finish_failed_workspace:562` 同样先查当前编译合同。因此简单把外层异常改名后转入 record_failure 仍然无法恢复。

`local_workspace.py:319` 的 discard 在没有 preserve_digest 时最终删除隔离目录；故封存失败不能把“failed 已落库”当作保存成功。R2 已识别这一点，但合同不可用时如何取得可信封存预算和候选关联仍未指定。

**可达场景与影响：**运行中服务换版本、Operation 移除，或重启后处理旧合同失败工作区，科学校验尚未运行就抛出状态冲突；可交付文件无法经计划承诺的失败通道被保全。部署前清理活跃任务可减少场景，不能替代合同故障本身的受控处置。

**必要最小修正：**计划应明确合同查找失败的终结/隔离路径不依赖重新获得同一当前 Operation：使用可信冻结运行材料中的预算和关联，保留可恢复原件或明确标为隔离未完成，禁止删除唯一副本；绝不调用新领域 finalizer/checker 处理旧任务。明确 `_compiled`、finalizer、seal、输入读取、验收以及发布后 CAS 各类异常的责任分流，保持 CAS/未知提交原有语义，不能一概吞掉 RunStateConflict。这里只需补现有失败与封存链，不要求新状态机。

**必须验收：**准备好候选后移除/替换 Operation，再分别经正式 submit、实际 Worker 预览入口及显式失败/重启补救处置；文件仍可取回，失败类别正确，无新规则验收旧输出。故障注入须覆盖 seal/discard 失败和已经存在候选的复用。

### F3 / 中 / 必修定位：计划命名的直接服务入口不存在，完整准入也不全在 preflight_operation

**计划位置：**P1 `RunService.create`、验收 4 的直接 create。

**源码证据：**实际入口是 `runs.py:89` 的 `schedule`，Root 在 `mcp_root_operation_routes.py:257` 调用它。它目前接受 BoundOperationCall，验证 Artifact 字节并 freeze current，随后插入 Run；不存在 RunService.create。`_prepare_operation_call:1053` 调用 preflight_operation 后，还在 `:1088` 调用 `_validate_operation_input_admission`；后者覆盖声明 cohort/approval、claim、review、revision 等门禁。因此 preflight_operation 是共享内容/绑定检查层，不等于全部现有准入政策权威。

**风险：**照名增加 create 或仅给新入口写测试，会遗漏可直接调用 schedule 的真实路径。另一方面，若把“执行同一准入检查”理解成把 Root 全部资格逻辑复制进 service，又会制造第二套权威。

**必要最小修正：**将所有直接 create 定位改为 schedule，明确本次共享的是新纯输入检查及构造它所需的权威元数据，现有完整准入政策归属保持单一；在 schedule 的任何 Run/工作区持久副作用前接入。手造 BoundOperationCall 的端口、source alias、媒体、大小和来源不能作为权威。直接 schedule 的坏绑定用例应明确覆盖真实入口，而不需要新增同义 API。

### F4 / 中 / 必修定位：目录投影不由计划列举的两个文件产生，input_admission 已有不同含义

**计划位置：**P1“input_admission 合同”以及“operation_contract.py 和 run_assignment.py 生成目录、assignment 和 schema”。

**源码证据：**目录实际走 `operations/catalog.py:71` → `operations/spec.py:449` `scheduler_operation_view` → Root `_operation_catalog_item:76` 的 model_dump。`SchedulerOperationView.input_admission` 已是 `InputAdmissionSpec`，表达 all-or-none cohort 和可选批准；不是新纯输入验证描述。`operation_contract.py` 生成输出合同/schema，`run_assignment.py` 生成 Worker 指针，两者目前不生成 scheduler catalog。

**风险：**只改计划列出的两个投影文件，会让调度者目录看不到输入规则，或把新字段塞进现有 cohort 合同，混淆内容规则与批准政策。声明已经存在不证明各消费面已投影。

**必要最小修正：**明确在现有 scheduler view 和映射处增加新 input_validation 的派生可见投影；文档“input_admission”若仅指阶段，应说明不替换现有字段语义。说明 Root catalog、Worker assignment、schema 各自可见的内容，复用一个投影 helper 即可，避免第二份描述与状态。installed entrypoint 验收必须断言真实 Root 投影，而不只验离线 schema。

## 已核实可保留的设计与实施注意项

- **current/资格：**`runs.py:935–944` 已在完成收据中将失去 current 的情况标为 `stale_rejected`，仍绑定成果并置 completed；`_validation_inputs:762` 本身不重查 current。应保留这一现有分工，无需再建设资格系统。不要把完成时 head 防护误删为“输入重验”。
- **恢复材料消费：**普通路径已通过 `local_workspace.py:157` 复制只读 recovery-draft，`run_assignment.py:70` 告知 Worker 将其用作非证据的起始稿；author 的 materializer 通过 `runs.py:799` 的 provisional_roots 接收它。不是“完全没有消费路径”，主要缺口是 F1 的准入和 F2 的失配故障保全。复用这些机制比新增发布服务小。
- **诊断来源描述符：**当前 `InputBindingDescriptor`（`run_outputs.py:40`）只有 ref/media/size/sha/output_name，没有 parent_refs 或 execution_id 标签。现有 `analysis_parentage`（`result_analysis.py:36`）则通过 InvocationArtifact 元数据执行父链 guard。P1/P4 实施应明确使用该现有 guard 还是窄扩展受控描述符；不得假定 `(sources)` 现有字段就能证明诊断执行来源，也不得让 checker 自行查任意存储。无需为此给核心添加 TCAD 分支。
- **digest/ABI：**`spec.py::_canonical_value` 对 BaseModel 使用普通 model_dump，新增缺省 None 确会改变规范化字节。P6 要求是必要的，但不能用全局 exclude_none 实现：这也会删去既有 None 字段，改变原摘要。应仅对新可选字段的缺省规范化做窄兼容。`catalog.py:713–726` 还包含组件所属插件版本、reviewer digest、批准 provider 身份；修改插件版本可传播到未直接修改 Operation，影响矩阵必须包含该闭包。不能以“没有提升 ABI”推导“旧资格不受影响”。
- **最小改动：**一处输入声明、一个共享调用层、现有异常分类/活动摘要、复用封存恢复，是合理规模。动态 P0 盘点作为实施产物可接受，不需要为计划评审先加载科学实例。没有理由扩展为规则解释器、全系统重构或 TCAD 特判。
- **资源与测试：**R2 的单进程定向、整棵进程树预算与峰值记录符合明确资源约束。现有 `test_l2_run_invariants` 的显式恢复/后端变更用例及 `test_l2_local_run` 的 current 用例可复用；需加入上述实际缺口的负例，不要求跑全量或求解器。本次仅阅读这些测试入口，未观察其运行通过。

## 复审完成条件

计划先把 F1、F2 的边界决策写成可执行的有限方案，并校正 F3、F4 的真实入口及投影位置；不必在计划阶段实现它们。随后按 P0 冻结迁移表推进代码，保留原计划对有限科研结果、无资格草稿、旧记录不可变与全目录语义覆盖的约束。静态审查支持这一修订方向，但目前不足以批准按原 R2 直接实施并声称覆盖修复后续研闭环。
