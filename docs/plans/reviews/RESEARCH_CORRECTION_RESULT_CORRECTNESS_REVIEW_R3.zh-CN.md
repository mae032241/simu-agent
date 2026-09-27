# 研究纠错与续研实施结果独立审查 R3

日期：2026-09-08。

**结论：PASS，仅限冻结的 Local 首版工程候选；未发现需要阻断该候选的实现回归。** 本结论来自本轮重新阅读调用链、实际运行 36 项针对性回归和三个独立探针，不继承实现审查 R1/R2 的放行结论。P5 实际部署和新资格建立、P6 两轮真实研究仍未完成。

**一项已复现的边界必须与 PASS 同时保留：计划审查不机械保证可选 `research_objective` 就是计划父链中的原目标。** 另一份同 key/statement、不同目标约束的原件可以被显式绑定，生成新的 passing review，并通过下游曲线设计预检。第 1 节说明其可达影响与首版不阻断的依据；不能把“查询可以恢复原件”写成“系统自动保证恢复和绑定正确”。

## 1. 按影响排列的发现

### N1：可选原目标的精确选择依赖 Root；不是提交时强制的父链约束——非阻断，已实际复现

**位置。** `src/scidiscovery/general_science_experiment_operations.py:148` 新增端口称其为 exact original research objective；`src/scidiscovery/general_science_experiment_components.py:210` 只比较 `objective_key` 与 `statement`。该 review 声明没有目标父链 guard。`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1372` 及 `src/scidiscovery/artifact_agent/service/runs.py:692` 验证 passing review 的确切计划 subject，没有额外要求 reviewer 使用了哪份可选原目标。

**可达触发及证据。** [独立探针源码](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-probe.py) 经隔离 Local Root→设计提交→materialize 建立正式计划，其直接父件含 `research_objective`。另外登记的目标保持相同 key/statement，改变 `mandatory_targets` 和 `closure_requirements`，且不是计划父件。分别以原目标和替代目标创建两个新 review：二者 preflight 均接纳，Worker 提交均 completed，封存 verdict 均为 pass。以真正原目标、原计划和第二个 review 进入 `science.curve.contract.design.v1`，预检仍接纳。见[完整结果](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-objective-probe.json)。探针使用工程 fixture，mock 的仅是科学基础审批谓词；没有实际审批、模型科学判断或外部执行。

**影响。** 如果调度者主动或错误地绑定替代目标，reviewer 可能依据不同的后续目标/闭合条件判断遗漏是否重要。下游只证明“这个计划已有新的确切独立审查”，不能证明“该审查已经验证计划原始目标的完整约束”。此处并未复用旧 review；改变输入后确实创建了新请求和新审查。

**为何不列为实施阻断。** 这项新端口带来了上述可见行为，但它不是实现偏离 R3 计划。[审定计划](../RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md) 第 251 行明确分配责任：Root 沿精确父链恢复原件，组件核对 key/statement；第 273 行要求实际证明正确恢复及显式文件交付，并未要求新的递归准入规则。原目标端口本来即可不绑定，review PASS 也不是完整研究目标闭合证明。正常恢复路径的无修订/经修订两个分支已在本轮重跑通过。用户最新要求也明确关注首版最小范围，不应仅为主动误绑的可能性新增硬约束。该边界不削弱既有 Artifact 不可变、review subject、审批或执行授权门禁。

**最小处置。** 在首版说明和 P6 验收中保留这一边界，继续使用已有父查询与显式绑定；不得对用户宣传自动原目标绑定保证。当前无需增加生产代码。只有后续把“自动拒绝同文本异约束目标”明确提升为产品要求时，才修订计划第 251/273 行及相应负控，讨论利用既有不可变父链的最小实现；本审查不建议新增目标 ID、状态机、Operation 或服务。

## 2. 审查身份、范围与依据

- 源码根：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`；登记 HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`。审查基线是冻结的既有脏工作树，未用 HEAD diff 冒充本次增量。
- 审定计划 SHA256：`9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8`。
- 最终候选：[p4-candidate-final.json](../evidence/research-correction-continuation/p4-candidate-final.json)，digest `27da282cee930c816f32a0f070153de8516cd8f2b3179429f73bb433984d3bc9`；逐项阅读其冻结补丁及当前调用方。33 文件中的 `scripts/l4_live_tcad_agent_probe.py` 是验证 fixture，计入 17 项验证文件，不额外计作第 15 个生产文件。
- 原字节来源：[基线清单](../evidence/research-correction-continuation/source-baseline-2026-09-08.json)及 `/tmp/scid-continuation-implementation-baseline`。父任务单独确认 33 项候选及 814 项完整发布目录的摘要一致；本报告不以此代替语义审查。
- 规范依据：当前双语架构、科学 Agent 最小设计宪章、33 项约束登记；同时阅读当前比较评估及曲线/TCAD 插件说明。历史评估和既有 PASS 仅作待核查论据。使用 `scid-cross-boundary-review`、`scid-find-simplifications`。
- 本审查只新增本报告；生产代码、测试、冻结计划及既有证据均未改动。隔离探针位于 `/tmp`，最终证据由父任务按原名归档。

## 3. 两条跨边界路径的实际核查

### 3.1 被审项目有缺口，仍可提交有效负面审查

| 边界与生产文件 | 本轮检查结果 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/plugin.py:463` → Root 准入 | `project` 改为 `prior_signal`，避免把被审对象先当成通过的 claim。它不适用 inventory 例外；当前 producer digest、三个 author 对应的同一精确 review edge 仍检查，退休 producer 仍拒绝。 |
| `plugin.py:108`、`project_packager.py:1220` → Worker 可见合同及提交 | 先验证结构和正式报告，再按 verdict 要求实现。revise/blocked 可以报告 case 缺失、参数值/单位错误、uncertainty 未 ready；原项目、计划和参数上下文仍须可解析，approved keys/coverage、报告 subject、handoff 和 capability 一致性没有取消。 |
| `roles/tcad_deck_reviewer.md:79` → 科学责任 | 提示明确负面报告须 `execution_ready=false`，不得修改冻结输入。语义规则与上述分支一致，没有把未来目标覆盖变成隐藏的 submission 要求。 |
| `project_packager.py:1310`、`:1442`、`:746` → pass、package | passing review 仍检查 case realization、批准的值与单位、uncertainty readiness、源绑定 preflight 和不支持的任务；ReviewedDeckPackage 仍只接受 passing、execution-ready 的 review。负面报告本身不产生执行资格。 |
| `transform_adapter.py:191` → 重物化及证明 | 从确切被审项目复制 initialization attestation，重新严格解析后仍比较完整重建对象。原 source/project digest 校验仍执行；原证明缺席仍为 null，不生成替代证明。 |
| package → Effect → UI | 后续执行的既有 producer/review、精确 package、execution approval 路径未修改；未增加能将负面结果升级为执行许可的入口。这里只审查源码和既有工程证据，未启动生产 Effect。 |

本轮实际运行了“假 pass 拒绝→同 Run 改负面报告→completed”的 Local 路由测试，以及包含两个真实声明 case 的工程 author→review→package 测试。后者使用模拟 debug adapter，验证初始化证明保留、源/项目摘要篡改拒绝和重建差异拒绝，**不是运行了 Sentaurus 的科学实验**。八种负面 verdict/实现缺口组合另行通过。

同 Run 纠错仍由已有 `run_outputs.py` 和 Run 生命周期处理：声明的 `SemanticRuleViolation` 产生可修订输出诊断；非声明 checker 异常为终止性的 checker 故障。此次没有更改错误分类、重试状态或预算。对不能通过结构/身份检查的冻结输入，Worker 仍不能靠改报告绕过。

### 3.2 本轮目标及历史原件贯穿设计、审查与恢复

| 边界与生产文件 | 本轮检查结果 |
| --- | --- |
| `schema/experiment_intent.py:137`、`schema/experiment.py:205` | 完整目标与 current 列表有数量/长度/唯一性上限，current 是非空精确字符串子集；每个完整 proposal 须含 portfolio 总目标。没有新增目标实体或阶段标志。 |
| `experiment_intent.py:417` → materialize | 精确总目标置首并去重，其余目标及 current 子集逐字保留；case/变量来自已声明 intent，不为后续目标合成执行占位项。两层模型保证直接完整提交和 revise 也受子集约束。 |
| `schema/experiment.py:560`、`general_science_experiment_components.py:59` | 移除总体 mandatory observable 全覆盖循环；保留目标身份及本轮 case、comparison、validation 一致性。覆盖理由、后续条件和本轮选择仍是正式 rationale 内容，由设计者/独立审查者判断，程序不把整份目标列表永久冻结。 |
| `general_science_experiment_operations.py:34`、`:145` | design/review 可选绑定三组原件，每组 0—4 项、每项 8 MiB、总输入 32 MiB；review 另有可选 typed objective/context。revise 保留原两个精确输入，不另造 continuation 操作。 |
| `operations/spec.py:115`、`mcp_root_operation_routes.py:1327` | wildcard 仍要求 schema/media 成对、inventory 用途且 exposure 仅允许 handoff_only/on_demand；跳过 producer 资格只限 Agent inventory。其它实例、计数、大小、重复、显式 current、family、cohort、review、claim 和 Effect 规则仍在原路径。 |
| Run assignment → 只读输入 → output | `runs.py:235` 和 `run_assignment.py:39` 实际物化非 handoff_only 原字节；on_demand 没有自动全文注入新包装。输入源别名来自本次绑定；`run_outputs.py:189` 按声明 context_sources 传入实际别名，object reviewer 的 evidence 引用只接受确实绑定的别名。输入变动进入请求指纹和输出父链。 |
| `general_science_experiment_components.py:168` → revise | 必须是对应计划的 ScientificReview 和完整新 Portfolio；总体身份/选择假设/实验身份保留，支持有理由地调整本轮目标。新输出不继承旧 review。 |
| `curve_contract_compiler.py:112`、`:396`、`science_operations.py:387` | target_bindings 选择本轮目标，允许同 observable 下只选一部分；目标必须存在、observable 必须属本实验，case/reference/check/metric/threshold 关系仍检查。显式坏 check key 在无适用检查时也先拒绝，不再被早返回吞掉。设计和 review 都用同一编译重算。 |
| `mcp_root_instance_routes.py:246`、`roles/scheduler.md:31` → 冷恢复 | 查询按精确父 Artifact 身份找本实例名称，保持顺序；无父项为空、未映射为 null、超过 4096 直接父件明确失败。无递归存储扫描或写状态。Root 按 typed parents 沿 revise 回到 materialized plan，再显式绑定原件。实际无修订/经修订的冷 Root 测试均交付了正确原目标文件，未误选同型历史反馈。N1 是这条正常路径之外的已确认边界。 |

“保留未来目标及条件”在首版中由结构保存加科学判断承担：模型能防止非法 current 引用，但不能机械证明一段 rationale 已涵盖全部必要后续条件。现有提示要求解释遗漏对有效性、可辨识性和结论边界的影响；对文字理由的科学正确性必须留给 P6。为此再增加目标状态机或把所有总体目标变成必执行 case，反而违背本次要求。

已有总体 coverage evaluator 未改。此次重跑的同/不同 observable 目标子集测试中，局部合同可生成及受审，未选 future target 的总体 coverage 仍为 fail；不能从局部 diagnosis/pass 推导整个研究闭合。

### 3.3 inventory 例外的全部现有消费者

不是只检查新增 design/review 两个消费者。根据当前编译声明和实际调用方逐一检查了原有九个 Agent 消费者：

| 消费者 | inventory 内容与仍保留的后续义务 |
| --- | --- |
| `science.curve.contract.design.v1`、`science.curve.contract.review.v1` | reference_bundle；参考内容受曲线编译重算和独立审查。后续 Transform 使用历史 bundle 时仍执行 producer 校验，读取它不恢复其资格。 |
| `science.evidence.audit.intake.v1`、`science.evidence.audit.v1` | source_material；intake/foundation 审查 subject 仍是 typed prior_signal，来源引用仍由上下文验证，后续 qualify 的来源/生产者/审查集合检查未变。 |
| `science.evidence.extract.figure.v2`、`science.figure.evidence.audit.v1` | paper/request/manifest/report/panels/overlays/tables；`complete_transform_family` 在共享例外之后仍单独验证完整、同源 family，不能把拼接的任意历史文件当新 figure family。 |
| `science.figure.request.prepare.v1` | paper_source；仅有来源读取例外，不产生证据资格；optional objective 仍是 prior_signal。 |
| `tcad.parameter.evidence.extract.v1` | source_material；输出需自己的严格参数合同和独立审查，资格仍单独建立。 |
| `tcad.parameter.evidence.audit.v1` | required checklist、requirements、parameters、source catalog、source_material；提取主件/审查精确绑定及后续参数 qualification 的完整来源与主体检查未删。 |

未找到其中依赖该 producer gate 承担独立资格、又在变更后失去所有后续保护的现实消费者。原件可读与其资格可重用仍是不同事实。此判断依据生产声明和校验链，不仅依据 `test_m6c...` 中跳过某个私有方法的 mock 断言。

## 4. 测试结果、失败归因与最小范围

[独立汇总探针](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-evidence-audit.py) 对照实际 collection nodeids、逐批原日志及每个文件最终批次，复算得到 **686 个唯一 nodeid、52 个文件、676 passed / 10 failed / 0 skipped，无漏列文件**。见[复算结果](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-evidence-audit.json)。早期失败批次没有计入最终成功总数；复用的四文件 212 项、冷查询 13 项、兼容 5 项和曲线 27 项依据其现存日志计入，未伪称本轮重新全跑。

十项剩余失败不能改写为全绿，但未发现被误归类为基线的新增行为失败：

- 六项 L5 Hardened 和一项 installed Hardened 在所需 reviewer 的前置能力门失败，尚未到目标 Worker 行为。本轮在冻结 ABI 16 与候选 ABI 17 **分别实际执行同一隔离 Root preflight**：author 的 backend requirements 为空，reviewer 均为 `native_shell` 不支持，结果同为 `operation_runtime_unavailable`，零 Run。见[基线](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-frozen-baseline.json)、[候选](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-current-baseline-check.json)、[源码](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-baseline-probe.py)。这增强了原先仅源码等同性的归因；仍不声称重跑了七个完整失败用例或 wheel。被前置 gate 遮住的 Hardened 负控也仍未通过。
- 两项结构快照失败：冻结/候选都为 63 components，均有 public execution_context_schema；旧测试期待 61 及旧 public 集合。这两点由本轮双源码独立导入再确认。
- 一项结构行数 ceiling 失败：本轮按实际后继文件重新计数，plugin 1148→1193，transform 1197→1270，合计 2345→2463；原 combined ceiling 为 2310，基线已超 35 行，本轮确实另增 118 行。增长没有被说成零，也没有提高阈值。逐段核对后，这 118 行用于已审定的私有共享反馈端口、目标提示/语义和上下文检查，没有增加组件注册数、第二控制权威或生命周期状态。

因此可以接受首版 Local 工程候选的范围放行；七项非默认 Hardened 缺口不构成改造默认 Local 流程的理由，三项结构检查也不能通过无意义压行或提高阈值来掩盖。已观察到的 Local installed 正控与 source/installed 49 项目录一致性来自原 P4 wheel 批证据；本轮未重建 wheel。

### 本轮实际执行命令

工作目录为源码根，Python 为 `/home/da/miniconda3/bin/python`；两批串行，执行前已与父任务协调，无其它 pytest/wheel 并跑。

```bash
/home/da/miniconda3/bin/python -m pytest -q -p no:cacheprovider \
  tests/operations/test_l4_local_tcad.py::test_negative_deck_review_can_report_implementation_defects \
  tests/operations/test_m2_curve_analysis_boundary.py::test_curve_contract_without_eligible_checks_rejects_explicit_check_bindings \
  tests/operations/test_m6a_direct_instance_management.py::test_cold_root_recovers_original_plan_context_and_delivers_exact_files \
  tests/operations/test_agent_contract_alignment.py::test_exact_optional_feedback_reaches_root_run_local_worker_and_output_parentage

/home/da/miniconda3/bin/python -m pytest -q -p no:cacheprovider \
  tests/operations/test_l4_local_tcad.py::test_local_review_rejects_false_pass_then_seals_missing_case_report \
  tests/operations/test_l4_local_tcad.py::test_materialized_sprocess_author_review_package_preserves_case_anchors \
  tests/operations/test_m2_curve_analysis_boundary.py::test_curve_contract_worker_tool_writes_the_compiled_result \
  tests/operations/test_m2_curve_analysis_boundary.py::test_partial_curve_scope_keeps_exact_binding_checks
```

退出码均为 0，参数展开后分别 **25 passed in 6.10s** 和 **11 passed in 1.89s**。原日志：[第一批](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-targeted-pytest.log)、[第二批](../evidence/research-correction-continuation/independent-result-r3/scid-result-r3-gate-pytest.log)。它们是重新验证的 36 项子集，不应与 676 累加成新的全套通过数。

三个独立脚本均用上述 Python 执行；objective/evidence 脚本的唯一参数为源码根，baseline 脚本分别以冻结副本根和源码根为参数；四次最终执行退出码均为 0。探针仅使用临时工程数据库及文件，不读取或修改生产控制库。

## 5. 发布、资格退役及尚未验证的边界

ABI 16→17 进入 `operations/catalog.py:725` 的目录身份计算，因而所有旧编译身份退役。这不是只退休 design/review 的兼容修改。历史原字节可以作为显式 inventory 阅读；它们不能因此成为新版 review subject、revision base 或恢复原审批。必要科学对象应重新建立，各类资格/执行决定仍需新的确切 UI 决定。

[P5 交接](../evidence/research-correction-continuation/P5_DEPLOYMENT_HANDOFF.zh-CN.md)给出的建立路线在源码声明层面可行：原 PDF 没有旧 producer 标签；figure request 可仅绑定论文；新 materialized figure family→新 extraction/精确 audit→split foundation→qualify/project objective 的声明连接存在；原 PDF 加完整新 family/intake/audit 可建立新 reference bundle。旧 capability 的 active_adapter 快照与有旧 producer 的 execution_context 区别正确。没有发现必须先消费一份已退役合格对象才能从该原 PDF 启动所有新建立路径的声明死循环。

但上述判断**只证明来源和已注册建立能力存在**。它不证明科学 Worker 会生成合格结果，不证明所有具体绑定通过新 ABI preflight，不证明用户会批准，也不证明原 Fig.4 科学资格已经恢复。N1 所述原目标选择责任也仍存在。部署后逐项使用实际目录及精确预检的要求必须保留。

交接中的 reinstall 命令与 `deploy/reinstall.sh` 实际参数路径一致：保留 m7 install/state/config 根、原工作区和 command adapter，wrapper 以服务用户启动后自行调用 sudo，并将配置传给既有 install 事务。父任务核对当前 adapter 确为 command transport。已有 dry-run 退出码 0 支持命令准备可用；本轮没有运行安装，也没有借 dry-run 声称服务已换代。systemd 权限提示、状态快照时效和目标系统目录写权限不能由报告消除。

以下仍不在本 PASS 证明范围内：生产服务新目录加载与 profile 重启、生产新 ABI 的实际完整资格恢复、真实模型对目标/遗漏的判断、真实 Sentaurus 输出和两轮无聊天续研。现有 P5/P6“尚未完成”的表述准确。当前审定计划正文作为冻结审查输入保留原状态，最新执行状态由 EXECUTION_RECORD/README 拥有，不能改写旧正文来假继承 PASS。

## 6. 首版最小化判断

未发现需要新增生产文件才能完成已审定行为的必要缺口，也没有发现此次新增第二 registry/current、进展对象、后台服务或阶段状态机。三组反馈使用同一个私有声明；原件读取复用既有 Run 文件机制；恢复只扩展现有查询；目标选择继续由科学 Agent 和独立审查者负责。保留这些已有责任，比再为 N1 增加一套强制递归目标绑定协议更符合用户当前的首版取舍。

放行条件是继续准确使用这份有限工程结论：可以推进部署准备和受控真实验收，不能宣布科研目标已经达成，不能将负面报告包装成通过，也不能把同文本目标绑定说成已被程序自动证明。
