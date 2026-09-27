# R5-M2-01 参数证据包实现独立复审

日期：2026-09-01

结论：**PASS（通过）**

阶段门：首轮独立审查的 B1、B2、B3 已全部闭合，**放行 M2-02**。本结论只确认 M2-01；不把
M2-02、M2-03、真实模型科学效果或整个 R5-M 宣称为完成。

## 1. 复审范围与独立性

本复审者未参与 M2-01 实现和首轮审查。复审基线是当前 `baseline/8765-codex` 工作树中的返工候选；
工作树还包含大量早于 M2-01 的未提交修改，因此没有把整棵工作树误称为本阶段精确差异。

完整阅读并交叉核对了：

- `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`；
- 返工后的 `R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
- 首轮 FAIL 报告 `R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 当前最小设计宪章和 33 项约束登记；
- 参数包、展开、覆盖、审计和资格投影实现及两个角色合同；
- 通用 review 编译、输入准入、Run v1 输出登记和 producer-family 投影；
- M2 参数包、目录、安装入口、通用 Transform、后端能力和约束结构测试。

除本报告外，本复审没有修改计划、实现证据、生产代码或测试。

## 2. 首轮阻断项复核

### B1：提取、展开与独立审查拓扑闭环——已闭合

当前提取 Operation 不再声明 review；其单一 `parameter_evidence_package` 可以通过同一个通用
preflight/invoke 进入 `tcad.parameter.evidence.expand.v1`。审查边现在由展开 Operation 的
`ReviewSpec` 声明，精确 subject 是展开后的 `scientific_intake`，reviewer 是
`tcad.parameter.evidence.audit.v1`。审计同时绑定原始包、完整展开族、确定性覆盖和冻结来源，所以
没有把机械展开置于其自身尚不存在的审查之后。

这不是 support Transform 绕过审查的特例。通用编译器原本就对任意生产 Operation 的
`ReviewSpec` 校验 reviewer 存在、独立 Agent 身份、端口 Schema/codec/资源摘要和基数兼容，并把
reviewer 摘要纳入生产 Operation 摘要。返工只令通用 Transform producer family 与 Agent family
一样，从同一 `CompiledOperation.spec.review` 投影 `reviewer_operation` 和
`review_subject_outputs`。核心没有出现 TCAD、参数、Schema 或插件名分支，也没有第二份 review
注册表。

独立真实探针使用 `open_runtime`、`RootToolFacade`、`RootMCPRouter`、`RunService` 和
`LocalWorkerMCPRouter` 完成：

```text
提取 Run completed
  -> 展开 preflight admissible
  -> 展开 invoke 完成四对象登记
  -> 覆盖 Transform 完成
  -> 独立审计 preflight admissible、Run completed
  -> intake split 完成
  -> 参数资格 approval preflight admissible
  -> loopback 审批请求 status=pending
```

另以领域中性的 `blind_producer_fixture` 运行真实 Transform→独立 reviewer Run→approval 路径，观察到
三成员 Transform family 精确投影 reviewer 和 subject output，审批请求进入 `pending`。这证明新增
投影解决的是已有通用合同的不对称，而不是只让 TCAD 测试通过的补丁。

### B2：资格投影解释旧 Task 来源和父链——已闭合

当前资格投影只接受现行 Run v1 的 `source_kind="run_input"`，不再接受或恢复
`task_input`、`web_snapshot`、`pdf_excerpt`，也不假定 instruction 是父 Artifact。真实正例证明：

- 提取 family 只有一个 `parameter_evidence_package` 成员；
- 提取 family 的证据来源来自该 completed Run 的精确输入和 task-local `source_name`；
- 四个展开对象的唯一父引用都是原始包；
- coverage 的父引用精确为需求、参数和来源目录；
- audit 的父引用精确按 OperationSpec 输入顺序绑定包、展开族、可选 checklist、coverage 和全部冻结
  来源；
- split 的 foundation 精确绑定展开主对象和同一个 passing audit；
- 资格 projector 同时核对提取 family、展开 family、上述父链和冻结来源集合后，才创建审批请求。

没有为兼容插件向核心恢复旧 Task 表、旧来源类型、instruction Artifact 或双写父链。

### B3：来源别名与 revision 审查隔离——已闭合

提取主输出的既有 context validator 现在要求包内 `source_catalog.source_key` 集合精确等于当前 Run
中所有 `source_material` 的 task-local 别名；可选 checklist 不被误算为证据来源。独立 Local Worker
提交含 `invented_source` 的完整合法包时，`worker_submit_result` 返回 `rejected`，错误发生在提交
边界，不能先成为 provisional Artifact 再等后续审计发现。

新参数包 revision 经新的提取 Run 和新的展开 family 产生后，将旧 audit 与新展开主对象绑定到
`science.intake.split.v1`，真实 preflight 返回
`input_independent_review_missing`。旧 audit 没有因语义名称、Operation 或旧 revision 相同而被继承。

## 3. 独立负向验证

下列反例均通过真实 Root/Run/Local Worker 或资格 projector 入口执行，没有直接调用数据库改写结论：

| 反例 | 实际结果 | 判定 |
|---|---|---|
| 用另一来源替换提取 family 的精确 frozen source | `approval_projector_failed` | 缺少预期来源并增加错误来源，失败关闭 |
| 在精确 frozen source 之外增加一个来源 | `approval_projector_failed` | 额外来源失败关闭 |
| 用相同字节但不属于展开 producer family 的需求 Artifact 替换成员 | `approval_projector_failed` | 错误 producer family 失败关闭 |
| 绑定 handoff=`blocked` 且含失败检查的 audit | `input_independent_review_missing` | 非通过审查不能满足独立审查准入 |
| 参数包声明未绑定的 `invented_source` | Worker 提交 `rejected` | 来源别名在提交边界失败关闭 |
| 新包 revision、新展开主对象绑定旧 passing audit | `input_independent_review_missing` | revision 不继承旧审查 |
| 展开对象与包的规范化字节不同 | context validator 拒绝 | Transform/审计之间不能静默改写 |

首个组合探针在预期拒绝的别名造假 Run 仍占用同一 Operation 活跃槽后继续调度 revision，得到
`local_run_creation_failed`；这属于探针顺序错误，并符合单 Operation 活跃槽约束。将 revision 反例置于
新的独立临时运行时、并把造假提交放在末尾后，两项均得到上表预期结果，没有修改实现或放宽测试。

## 4. 通用性、所有权与奥卡姆判断

返工保持了正确所有权：Agent 决定来源取舍、参数值、冲突、缺失项和不确定性；
`expand_parameter_evidence` 只验证一个完整包并复制四个规范化对象；coverage 只产生确定性覆盖；audit
由独立 Agent 给出科学 verdict；资格仍需精确人工决定。控制层和 Transform 没有补写参数、来源或
结论。

独立复算当前物理表面：

| 指标 | 结果 |
|---|---:|
| `src/scidiscovery` Python | 96 文件 / 26,126 行 |
| 插件 Python | 45 文件 / 22,875 行 |
| 完整目录 | 47 个 Operation |
| Agent / Transform / Approval / Effect | 22 / 21 / 3 / 1 |
| public / support / internal | 26 / 21 / 0 |
| Root 公共工具 | 30 个且名称唯一 |
| 新建 Local 数据库通用表 | 18 个 |
| Run 状态 | `queued/running/completed/failed` 四态 |

相对 M1，只有一个有真实消费者的 support Transform 和包/展开两个窄组件；没有新增 Run 状态、集合
提交协议、表、Root 工具、守护进程、第二目录、第二 Registry、第二 preflight/invoke、兼容 adapter
或领域专用生命周期。该净增加消除了一个公开但默认必失败的 Agent 路径，符合本阶段奥卡姆门。

## 5. 33 项约束判断

本复审不把结构测试或 215 项回归夸大为 33/33 全部语义符合。当前登记仍是 33 个唯一约束，既有
`pending_review` 和 `SEC-002 known_issue` 没有被本阶段自动晋级。

与 M2-01 直接相关的结论：

- AUTH-001、AUTH-003、PLG-001、PLG-002：仍只有唯一编译目录和准入权威，核心无领域分支；不退化；
- ROLE-001、DET-001、DET-002：Agent 科学判断与机械展开边界清楚，父链可重放；通过本阶段门；
- TOP-002、ROLE-002：真实目录、preflight、invoke、Run、submit、review 和 approval 已沿同一合同闭合；
  首轮阶段缺口已解除；
- EVD-001：来源先冻结，且参数包在提交时绑定精确 Run 别名；首轮阶段缺口已解除；
- IMM-001、IMM-002、LIN-002：对象和父链不可变，新 revision 不能复用旧 audit；本阶段负例通过；
- SEC-002：Local Codex 原生工具隔离仍是既有已知问题，本阶段没有掩盖或扩大它。

## 6. 独立执行证据

所有 pytest 串行运行，设置 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2`，未使用并行：

1. M2 参数包、目录、安装入口、通用 Transform、后端能力和 33 项结构聚焦集合：
   **30 passed in 46.15s**；
2. 全量回归：**215 passed in 64.02s**；
3. 独立真实参数纵向探针：正向链到审批 `pending`，六类负向绑定按第 3 节失败关闭；
4. 独立领域中性 Transform review 探针：三成员 family、精确 reviewer/subject 投影和审批 `pending`；
5. `git diff --check`：通过，无输出；
6. 新建 Local 运行时表清单、Root 工具、完整目录、Run 四态和生产行数均在临时进程中独立复算。

复审时关键对象 SHA-256：

```text
fc457a0e46906a7fae06c4d977ddeecfad1fa1bcc2783acb0e2d67b191fdfdba  R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md
c564fb4ddf474d171dc049b659a60448096b8bf39630b2d8429c7f90abb641f8  R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_EVIDENCE.zh-CN.md
921daa8e323f2f27782a7f1142be1c40239da2240a76d265603a75387f855b8d  R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
0680c58f38e7719f22c0267aab6e6bb7f543c699f2369e6cd69e6e755f18dc45  parameter_operations.py
347670fe2cb8abad438a0e0bb8c24905774bccc805727ccfdebc7c9c428b25d2  mcp_root_operation_routes.py
b92e12b6a7282dc6a6c80238ed863aa92d459667fb2da549f0c361c53c634ea6  test_m2_parameter_package.py
```

## 7. 未被本阶段证明的事项

- 本轮使用确定性科学 fixture 驱动真实 Run 生命周期，没有重新评价真实论文参数的科学准确率；
- M2 整阶段要求的真实通用模型 Agent 与 TCAD 模型 Agent 启动测试尚未到本子阶段完成门；
- 曲线诊断集合输出和论文图证据默认产品面分别属于 M2-02、M2-03；
- 本轮实际创建了精确 loopback 审批请求，但没有做浏览器视觉验收；既有 UI 排版缺陷不因此关闭。

这些是后续阶段或产品验收要求，不构成 M2-01 返工阻断。

## 8. 最终结论

**PASS。** 首轮 B1 的审查拓扑闭环、B2 的旧 Task 来源/父链解释、B3 的来源别名和 revision 审查隔离
均已由当前代码及真实入口正负证据关闭。返工没有通过 TCAD 特例或新增控制实体换取通过，反而补齐
了既有 Transform review 在通用 producer-family 投影中的缺失对称性。

因此，M2-01 可以标记完成，M2-02 可以开始；M2 和 R5-M 仍未完成。
