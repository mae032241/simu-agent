# S1–S3 MVP 实施切片：现有入口与无模型验收准备

日期：2026-10-10。作者：f0_test_debt。性质：**仅设计与夹具；待独立审查；未生产接线**。
核对 HEAD：8e63a0e6eddda17edc4f342eadb0fc6601846710（仅 F3 brief/G2 已收口；helper/support 与安装门当时尚未完成）。父拥有主计划；本文不覆盖其状态。
范围：单题、串行 W、有界短步。没有模型调用、hidden 答案、安装、部署、生产修改或新增科研授权。F4/S4 实验另由父按用户授权调度；历史 60M/三场不是本资产的可用额度。

## 1. 真实接缝与差距（源码事实）

| 需求 | 当前可复用事实 | 首版缺口／拟修改最小接缝 |
|---|---|---|
| S1 机制／目标关联 | `schema/cognitive.py:HypothesisProposal/HypothesisForm`：stage_objective、contradiction、mechanism、scope、predictions、falsifiers、evidence；最多6机制 | 没有可机械核对的筛选承诺、关键机制、分配单位、期限／豁免；不能解析自由文本假装已执行 |
| H 修订 | `general_science_agent_operations.py`：propose 输入 previous_hypotheses、result_analysis、experiment_results；先前 H 是证据而非继承资格 | 复用确切新 H 输出；预算仍原 loop，不以名称或新 H 清零 |
| W 与候选 | `general_science_experiment_task.py:ExperimentReport`：adopted_stages；`StageSubmission`：design/implementation/debug/execution/validity，已有 prediction/comparison 精确原件 | 缺 operator、父实现、评价版本的可校验关联；Run 恢复父链不是候选树，debug stage不自动代表候选/改善 |
| A 全局贡献 | `schema/layered_diagnosis.py`：objective_assessment、hypothesis_assessments、limitations、remaining_contradiction、next_action、progress_assessment；`general_science_result_analysis.py` 已要求盲区、合理未覆盖方向、H修订及全局收口依据 | 首选复用，最小结构化处置用于 S1 消费；不再复制一份全局报告 |
| 原件／恢复 | F2a 纯节点父链与按需精确原件；F2b O/V资格及读取边界 | 候选投影只列精确引用，不 materialize 祖先 indexes，不传播 historical access/qualification，不用 V 作科学原件 |
| 消费／止损 | `research_progress.research_progress`：analysis cycle_key=exact experiment subject digest；`cycle_facts`：H/W仅awaiting，重复A同subject去重；`scientific_progress`已有消费序号及窗口 | A completed不等于Root已确认消费。只在现有confirmed consumption边界更新；保留工程失败/预算独立计数，先用负例查实际漏洞，不能先重写 reducer |
| 选优 | A prompt有 best eligible候选要求；`scientific_current_select`要求artifact.kind等于kind并CAS精确对象 | 该接口没有evaluation分桶，不能把kind当任意版本命名空间。MVP best由已封存A/候选事实按 exact evaluation Ref 投影，Root仅执行A指定精确交付 |

入口链：Root `operation_preflight/operation_invoke` → `science.hypothesis.propose.v1` → `science.experiment.v1`；绑定 actual identity 后 Worker `worker_open_assignment`、`worker_experiment_stage`、既有提交；A `science.result.analyze.v1(subject=exact experiment instance name)` 自动派生 H、目标、材料；Root `run_status(intent=decision)` 路由 A 已封存 next_action。读决策本身不制造消费。历史、进度、材料不足均保留 unknown/omissions。

## 2. S1 最小表单与单一单位（待实施，不冒称已存在）

在 H 同一 payload 添加一个可选、最多6项 `search_allocation`；旧非搜索 H 原行为保留。每项引用本 H hypothesis_key：关键性（H作者判断）、最小判别建议及评价适用范围、最小机会、领先分支新增片上限。处置仅由 A 的同一 LayeredDiagnosisReport 可选 `search_assessment`记录：exact H/机制、tested/deferred/exempted/needs_evidence、精确依据、缺失材料、复核边界、累计延期（控制投影，不信作者自报次数）。重开由A，组合改变交H；不按关键词推关键性。

首版候选计量单位提案：**新 `science.experiment.v1` Run admission**（task slice），使用现有 Run+admission事实、原 loop 时间/token预算，不新账本。Root operation_invoke目前有scheduling_lock与_create_lock，但这不构成搜索配额+Run事实的单一原子事务。未来gate须进入真实 `runs.schedule` admission/CAS边界，在其连接内按权威事实重查并与新Run提交一致；preflight只能预测。identical请求的既有early-return不扣；新恢复child Run是新slice，同Run的native恢复不扣；仍允许 collect/cancel/dependency/failure和已有Run收尾。这个单位只能约束新增 W task slices，**不约束 Run 内的 native shell 数量或实际算力**；一Run里几次实验另报 observed，不由 seal数冒充执行数。

重要审查阻断：该单位对 covshift 的 native内环是否足够，需F4实际分片后判断。若不能在实际新内环入口核对深挖上限，MVP配额只获得观察资格，不能声称已满足S1强制配额出口。禁止为补保证新建shell监控/状态机；选择已存在受控执行入口的单位需另审并证明计量。延期到期拒绝自动复用旧理由；有效豁免须有已封存A精确依据，科学依据质量留独立人工抽查。

## 3. S2 一套确定性策略与有界候选（待实施）

策略函数是一个纯选择器，不启动执行、不作科学判断；输入已授权H/allocation、控制记录的剩余额度、candidate facts、exact evaluation Ref；输出 operator+合法父候选集合或return_A/等待。优先级固定：
1. H冲突、评价盲区/版本不可比、所需信息越界、片结束 → return_A（A决定是否H修订）。
2. 未处置关键机制缺初始候选 → generate；不创建H外机制。
3. 当前候选工程失败且 debug_depth<冻结上限 → debug同科学意图；到上限→return_A或授权的其他候选；失败不证伪机制。
4. 有可运行、同 exact评价版本可比的父候选，S1允许且预算足 → improve；多父若H/A未预授权机械排名则交W/A，不自行按单一代理择优。
5. 无可靠指标/无新可改变决策证据 → return_A/等待；不补随机分支、不重试未知外部提交。

在既有 stage 可选 candidate 关联中只让W填 operator、parent的当前exact alias、改动目的、评价alias；控制将它们解析为 immutable Ref、同H/同instance与原producer证据并封入原tool receipt。候选身份取真实implementation receipt/ArtifactRef，**不是名称、Run父或助手ID**。generate无父；debug/improve必须有合法父且验证 exact H与科学边界；科学引用可图状，实现派生首版单父，不新增图数据库。

W工作集只有目标/H/评价入口、最多6机制、当前候选+最近8次变更；历史按现有 reference/history分页。200节点夹具验证长度不随历史增长，omitted/next保留。单次有意义改动/小批实验可直接W或一个串行 native helper；复用 prepared helper合同、无父历史、同权限、release清理。助手/默认降级不能改变科学预算或“另开一个W”。阶段封存和 task recovery沿现有Run关系；新节点仅新payload/CAS，不继承旧indexes/read access；parent reference只赋予已授权按需读取，不赋新资格。

## 4. S3 分层评价、best与消费

搜索评价：声明精确评价 ArtifactRef、合法输入数据Refs、指标/方向/适用范围；变指标/数据/阈值生成新 immutable版本。候选 metric值是观测非全局成功；只在同 exact评价Ref 且可比条件内按预先H/A排序投影 best；跨版本并列保留，不覆写旧胜负。A指定 exact implementation/result与条件；提交使用既有精确文件入口，对最终hash/producer进行比对，Root不自行选best。

首版选择评价缺严格隔离通道时禁用，明确 `not_available`，保留搜索best+受限结论。未给W提示不等于隔离；sharedUID非严格未见。若将来 selection结果/排名/建议回流，按 exact数据 identity记录用于搜索，换event/protocol名称不清除曝光；不得把外部hidden评分当A反馈。首版不实现保密服务或隐藏数据夹具。

科研轮次以**已完成A对exact实验的判断，并在现有confirmed消费边界结算**为单位。A生成、派发、Root读状态、helper完成不单独增加；同subject A修订/重启只一次；H修订、改名字或阈值不恢复loop额度。工程失败保留独立故障事实、awaiting/unknown，不能误计 mechanism refutation或科学improvement；不移除现有刹车。先复用 cycle_facts+真实delivery ledger；如fixture揭示standalone失败窗口与A计数冲突，另作最小修复设计并保留旧强制停机。A在当前H与既有数据权限内改进目标代理、可识别性检验或验证设计，可以直接交W并封存独立评价新版；只有改变科学边界或预承诺指标才交H显式修订，再由W绑定新H。不得为普通评价改进新增审查/审批关卡。early return由A/W科学信号不是Root判断。

## 5. 最小实施文件与测试入口提案（本轮不编辑）

阶段A（F4前只准备/评审）：当前外层native-payloads.json、cases.json、acceptance.json；无生产、无pytest。
阶段B（F4后一次最小实施审查）：
- `schema/cognitive.py` + H现semantic/context validator、H prompt：可选allocation；`schema/layered_diagnosis.py` + `general_science_result_analysis.py`：最小A处置/既有全局字段，不重做progress schema。
- `general_science_experiment_task.py`：stage candidate字段及exact receipt上下文校验；仅需一个纯策略函数时放同模块，不另建loop engine。
- Rootroute只作预测/转交；未来准入 gate须在 `service/runs.py:RunService.schedule` 真实admission/CAS连接内重查，gate+新Run事实原子提交；证实可靠计量后再确定最小函数，不预先修改runs/progression/helper/support（当前由F3作者拥有）。
- read投影复用existing budgets/history/read，不全祖先hydrate；必要变更具体入口审查后才批准。

拟新增精确文件：`tests/operations/test_search_mvp_contracts.py`，需父批准才创建。复用 `test_experiment_goal_origin._setup`真实RootFacade、`worker_fixtures.attached_worker`和现 sealed stage fixture；通过Root preflight/invoke、actualWorker stage/submit、A operation→submit→confirmed consumption验证。新策略纯函数测试仅对前述固定输入，不能代替生命周期入口。
现有可关联回归：test_experiment_material_delivery中prediction/comparison；test_scientific_progress中terminal_delivery_settles_once、goal_completion_requires_exact_analysis、terminal_consumption_survives_goal_revision；test_r4_internal_helpers中身份/release串行事实；test_reference_access/test_tool_evidence节点已验证纯父链/无继承。届时只选择涉及实际diff的精确节点，共享runner，不预先全跑。

## 6. 冻结验收判据与资格

见 acceptance.json（30个确定性场景，输入/expected/no-claim各分离）。native-payloads.json是真实当前schema可表达材料；cases.json里的 proposed_search fields **不是当前API请求**，不能宣称当前消费/拒绝PASS。
F4前可验证：JSON结构/当前H,A payload本地schema；源码接缝/精确命名；策略输入预期无随机；夹具无hidden字段。此轮只进行了资产结构和原生payload schema检查，没运行生产生命周期/pytest，不给30测试PASS。
F4后/生产接线后才可验证：实际cap事务、O/hash/qualification、candidate父子准入、read恢复/预算、重复A消费、真实best交付身份、serial helper成本。真实行为/质量还须模型场验证：有依据的豁免质量、A转向完整性、shortstep可行性、评价代表性、上下文峰值与cached/input/output成本。搜索/选择严格隔离仍未取得资格；hidden只停止后独立评估，不为开发反馈。

阻断实施的设计确认：单一slice计量单位的可靠边界；可选新字段最小schema/消费者一致性；控制owning transactions路径；现reducer是否已满足不重复消费（不得叠第二账本）。不得以外层oracle/文本存在代替真实机械入口。父独立审查这些资产后，再按F4顺序决定实施。

## 7. 独立review修订与F4前现合同测试

本修订处理真实F3状态、A同H评价改进→W权限、schedule准入计量/CAS三项。新增S3_09同H评价新版，不新增门禁。未来配额可靠性未证仍只观察；新恢复child不可算免额。
F4前新增tests/operations/test_search_mvp_contracts.py仅验证当前H/A可表达、有未来字段明确extra_forbidden拒绝、现A合同sameH评价/边界修订路由与exact H binding；不实现allocation或策略。现消费真实entry的三个节点复用既有测试，避免重复造账本/fixture。生产/schema禁止修改。
