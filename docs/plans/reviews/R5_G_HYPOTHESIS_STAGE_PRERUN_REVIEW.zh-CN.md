# R5-G 假设阶段运行前独立审查

审查日期：2026-08-30  
审查对象：`scripts/r5_g_hypothesis_stage.py`、对应 runner 测试、冻结 manifest、R5-G 计划状态及既有通用 Operation 合同  
审查方式：未参与实现；不修改候选代码、测试或科学对象

## 结论

**通过。放行运行三个真实 hypothesis Agent；不放行实验阶段。**

当前候选以固定 SHA-256
`e9470066cce9d7834e28c76fe8eac61c5d06bd8fa133e601c41c0292f699c581`
读取证据阶段最终报告，并在创建第一个假设 Task 前重新核对 exact Approval、rev3 intake Task、rev4
audit Task 和同一 problem frame/foundation 的真实 `operation_preflight`。在当前持久状态的独立副本上，
这条检查真实返回 admissible，且精确定位到：

- `r5g_evidence_extract.rev3.output`；
- `r5g_evidence_audit.rev4.output`；
- `r5g_evidence_qualification.rev2`；
- `r5g_intake_split.rev3` 与其 `scientific_foundation` 输出。

未发现正常运行路径可达的科学错绑、旧审批继承、调度器代写科学内容或隐藏领域 DAG。当前完成门只
证明运行前编排可用；三个 Agent 的实际科学输出仍须在受控运行后独立审查，不能由本报告预判为通过。

## 阻断项

无。

## 1. 证据阶段锚点与准入复核

### 1.1 固定最终报告

`_load_evidence_report()` 只接受 `science-chain` 直属文件，并把实际字节摘要与模块内固定的 e947…
比较。命令行不再允许调用者提供另一个摘要。报告还必须声明 completed、approve、历史重放非新求解，
并包含 Approval、intake、audit、problem frame 和 foundation 名称。

这使正常运行不能误用仍保留在历史中的 rev2 intake/audit 或 Approval.rev1。固定报告的名称字段随后
还要经过当前 Root 状态复核，而不是只凭 JSON 文本继续。

### 1.2 Root 双验与真实预检

`_validate_evidence_checkpoint()` 的顺序为：

1. `approval_status` 必须返回报告中的精确 revision 和 `approve`；
2. intake/audit 对应 Task 必须为 completed，且 sealed output name 与报告逐字一致；
3. 使用报告中的 exact problem frame/foundation、同一 operation name、operation id 和指令调用
   `operation_preflight`，只有 `admissible=true` 才继续。

独立审查在私有状态的临时副本上，用当前 `CompiledCatalog` 和真实 Root facade 重放上述函数，结果为
pass。临时副本已删除，原始状态未被写入。

用户已接受的剩余风险是：本地评估脚本不再额外重复 Approval subject-set 摘要或为报告增加签名/新
状态。固定 e947… 已引用上一关独立核对过的完整对象链；继续复制同一权威会增加控制重量，当前没有
必要。这只作为评估脚本的后续技术债，不阻断快速科学闭环。

## 2. 三个 Agent 的职责与最小上下文

### 2.1 提议 Agent

`science.hypothesis.propose.v1` 只绑定已批准的 problem frame 和 scientific foundation：

- 要求提出两至三个真正不同、可证伪的解释；
- 明确候选解释不是已接受机制；
- 继续保留三项缺失绑定对身份链、执行复核和因果结论的限制；
- 后续实验只能写成预测或反证需求，不能冒充未来观测；
- `HypothesisProposal.evidence` 只能使用两个直接输入别名或明确标为 inference。

TaskService 会对 evidence path 做任务本地来源校验，因此把 foundation 内部的历史来源名冒充直接输入
会被失败关闭；这不是只靠提示词约束。

### 2.2 批评 Agent

`science.hypothesis.criticize.v1` 只读 exact portfolio 与 approved foundation。它逐项判断物理/数值
合理性、可证伪性和可识别性，不承担原始来源审计，也不得选择候选。上下文 validator 要求每个
hypothesis key 恰好被审查一次，并把每个维度状态与 handoff verdict 绑定。

### 2.3 证据审计 Agent

`science.hypothesis.audit.v1` 读取 exact portfolio、同一 foundation 和与证据阶段顺序一致的六源：

1. evaluation contract；
2. typed metric source view；
3. active bundle manifest；
4. historical independent audit；
5. historical deck diff；
6. typed curve CSV source view。

冻结 manifest 与 runner 的端口和顺序一致。context validator 要求 audit check 的 hypothesis key 并集
等于 portfolio 的完整 key 集，且决定性检查只能引用本任务绑定的来源。提示进一步要求核对 CSV 已
提供、失败 gate、局部残差、target 边界、历史重放非新求解及网格非因果边界。审计不重复 critic
机制判断，也不授予资格。

三个 Agent 都复用已通过的真实 `_run_agent`：外层 Codex 只 spawn 无父上下文子 Agent，科学内容只
能通过 Worker 受控文件、validate 和 finalize 进入密封 Task 输出；聊天仍只是传输信号。

## 3. CandidateEligibility 的失败关闭语义

`science.candidate.eligibility.v1` 是既有 support Transform，不生成假设、不排序，也不读取领域名：

- guard 要求 critic 与 audit 都直接父联 exact portfolio；
- audit 有 `fail` 时整个 portfolio blocked，有 `unknown` 时不能形成通过的证据门；
- critic 的非通过维度只会把对应 hypothesis 标为 revise/blocked，不能把它列入
  `eligible_hypothesis_keys`；
- Transform 只机械拼接 critic dimensions、audit verdict、未解决要求和 payload 摘要。

该合同允许“某个候选未通过、其他候选仍 eligible”的子集语义。这不是隐藏选择：被拒候选不会被
提升，eligible keys 完全由显式评审字段确定。若真实运行最后不足两个仍成立的解释，后续独立科学
审查或冻结量表应据实判失败，不能为了进入实验阶段补造候选。本报告因此不放行实验设计。

runner 无论 critic/audit 科学结果如何都会封存 deterministic eligibility Artifact；其中
`hypothesis-stage-report.status=completed` 只表示机械阶段完成，不等于 `CandidateEligibility.status`
为 ready。后续调度必须读取密封 eligibility 后再决定，不能从运行脚本的 stdout 推断科学通过。

## 4. 是否形成固定核心 DAG

固定顺序仅存在于 `scripts/r5_g_hypothesis_stage.py` 这一冻结 R5-G 评估脚本：proposal → critic →
audit → deterministic eligibility。它没有进入 Root、Task、Scheduler、目录编译器、插件或生产
readiness，也没有新增数据库表、注册表、状态机或 Operation。

每一步仍按当前 compiled operation id 和 exact ports 调用真实 `operation_invoke`/Agent runner。
因此这是一次可复现的小任务拓扑，不是通用框架的手写科学 DAG，也未偏离 Everything-is-Operation
和插件统一入口。

## 5. 复杂度与奥卡姆审查

- 新文件把假设阶段与 808 行证据/UI 运行脚本分开，没有继续扩张证据脚本；
- 它复用 `_runtime`、`_root`、`_prepare_sources`、`_run_agent` 和不可变 JSON 写入，不复制 daemon、
  Codex、Worker 或生命周期实现；
- 没有为一次评估引入通用 stage class、pipeline registry、状态机或新的领域抽象；
- 私有下划线 helper 的跨脚本复用是评估 harness 内部耦合，若 R5-G 后续阶段继续增加，可再折叠为
  一个小的 runner helper 模块；当前为此抽象公共 API 反而更重。

总体复杂度与当前“先跑通最小科学闭环”的优先级相称。

## 6. 测试与独立命令

所有命令严格串行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

独立结果：

- 当前私有状态临时副本上的真实 `_load_evidence_report` + Root
  `_validate_evidence_checkpoint`：通过；
- manifest hypothesis audit 六源及顺序复算：通过；
- `py_compile`：通过；
- 聚焦测试（runner、冻结 baseline、review binding、context/parentage、空 critic、跨 portfolio audit
  负例）：`15 passed in 38.98s`。

新增 runner 测试已经覆盖固定 e947 摘要、直属路径、Approval/Task/preflight 调用顺序和 exact
preflight inputs；既有真实生命周期测试覆盖 Worker contextual validation 与 lineage guard。

没有在运行前伪造三个 Agent 输出，也没有重复全仓回归。真实 Agent 派发、模型输出质量和科学量表
正是下一步被评估对象，不能用 mock 测试替代。

## 7. 放行边界

现在只允许：

1. 以 exact e947… 报告启动 `r5_g_hypothesis_stage.py`；
2. 真实运行 proposal、critic、audit 三个 Agent；
3. 运行 deterministic eligibility join 并保存受控输出和运行证据；
4. 由未参与生成的独立审查者核对 portfolio、逐项 critic、六源 audit、eligibility 和预算。

仍不允许：

- 把本报告当作任何假设的科学认可；
- 因一个候选 eligible 就跳过完整假设阶段独立审查；
- 创建 experiment design、TCAD deck 或新的 solver 结论；
- 宣称 UI 可用性、R5-G 或 R5 已完成。
