# R5-L3 独立实现复审

- 审查日期：2026-09-01
- 审查者：独立实现审查者（未参与本轮实现）
- 审查对象：当前工作树的 R5-L3 候选
- 活动计划摘要：`8067299c714e0b00280a10889f39f42e826262ce2921c89df74e2c095b4e862f`
- L3 证据摘要：`de497b33f68dd2ceaa153e7464d8c45a421eb9218d6b06e8b825f7336d7ab9ab`
- 结论：**PASS（通过）**
- 放行范围：**L3 完成门通过；只允许按活动计划进入 L4，不构成 L5/L6 或发布授权。**

## 一、结论摘要

当前实现达到了 L3 的最小目标：评审仍是 `OperationSpec.review` 声明出来的一条精确关系，运行时只从不可变生产者合同、已完成 reviewer Run、精确输入绑定和调度信号中机械判断是否准入。它没有新增 Review 表、全局资格状态、评审编排器或解释领域负载的控制逻辑。

四段修订语义通过真实 Root `operation_preflight` 复现：无评审拒绝、精确评审通过、作者产生新 revision 后旧评审拒绝、对新 revision 的精确评审通过。普通 Local 探索不创建审批或资格对象；声明为 approval executor 的 Operation 才创建该科学操作对应的人工审批，Root 仅暴露查询，不暴露写决定接口；审批对象换绑新 subject 时创建 pending revision，不继承旧决定。

双 Agent 证据也满足本阶段已批准的原型边界：作者与 reviewer 是两个 `fork_turns=none` 的通用子智能体，各自直接启动精确 stdio MCP 并完成自身调用；没有 bridge 或父进程代调。控制权威来自 completed Run、sealed Artifact、精确父引用和调度信号，而不是子智能体聊天。该证据没有声称 Codex 已支持动态加载生成的 custom `agent_type`，也没有声称 SEC-002 已关闭。

未发现阻断项、第二权限权威、领域分支或为通过测试而增加的生产特判。L3 的主要变化是对既有通用能力补齐跨边界证据，符合奥卡姆原则。

## 二、评审门的职责与边界

### 2.1 唯一声明与编译期闭合

1. `ReviewSpec` 只保存 reviewer Operation、精确 reviewer 输入端口、受审输出和可接受 verdict；它是 `OperationSpec` 内部合同，不是独立注册表（`src/scidiscovery/operations/spec.py:224`）。
2. catalog 编译器确认 reviewer Operation 存在、是 Agent、与作者 Operation/Agent component 不同、端口 Schema/媒体类型/codec/资源摘要兼容，并拒绝不完整或跨未声明插件的关系（`src/scidiscovery/operations/catalog.py:478`）。
3. 生产者输出策略从冻结的旧 Task 合同或当前 compiled catalog 读取；Run Artifact 上的 Operation digest 不一致时失败关闭，不另建运行时评审配置（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1338`）。

### 2.2 运行时只做机械事实判断

`_validate_producer_output_admission` 对声明了 review 的输出只检查：当前候选输入中是否存在一个 Artifact，且该 Artifact 是要求的 reviewer Operation 的 completed 输出、其指定输入端口精确绑定当前 subject ArtifactRef、调度 verdict 属于声明集合；否则统一返回 `input_independent_review_missing`（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1228`）。

底层 `RunService.is_exact_reviewer_output` 是纯读查询，只读取 completed Run 的 Operation 身份、信号和冻结输入绑定（`src/scidiscovery/artifact_agent/service/runs.py:502`）。它不解析 reviewer 的科学 payload、不比较论文内容、不打分，也不创建资格或评审状态。领域 payload 与 handoff 是否自洽仍由插件自己的输出/上下文校验器负责；控制面只消费通用调度信号。

因此，本轮所谓 ReviewGate 是一段由唯一编译合同驱动的准入谓词，不是新增实体或状态机。

## 三、四段精确修订证据

`tests/operations/test_l3_review_and_human_policy.py:206` 使用真实 compiled catalog、Root `operation_invoke`、Local Worker router 和 Root `operation_preflight`，依次验证：

| 场景 | 实际结果 | 结论 |
|---|---|---|
| 作者输出 A1，无评审 | `admissible=false`，`input_independent_review_missing` | 通过 |
| A1 + reviewer(A1)=pass | `admissible=true` | 通过 |
| 作者 revision A2 + reviewer(A1) | `admissible=false`，同一缺失原因 | 通过 |
| A2 + reviewer(A2)=pass | `admissible=true` | 通过 |

测试中的 `blind.csv.consume.v1` 是为验证通用下游准入而构造的测试 Operation，不进入产品插件或生产注册表。它没有引入生产领域分支；相反，它证明同一通用谓词可由任意声明兼容输入端口的消费者复用。

## 四、人工决定与普通 Local 探索

1. 普通作者 Operation 完成后，实例的 approval namespace 为空，`approval_list` 为空，Root 无 `decide`/`record_decision` 工具（`tests/operations/test_l3_review_and_human_policy.py:244`）。这证明普通 Local 科学探索没有默认 qualification/approval 负担。
2. 声明 approval executor 的 Operation 通过同一 `operation_invoke` 创建冻结且幂等的人工请求，绑定 exact subject 和 compiled identity，不创建 Run、Task 或 Execution（`tests/operations/test_r4_approval_operation.py:569`）。
3. Local runtime 中也只有调用该声明 Operation 后才出现对应 pending 请求和 UI URL；Root 仍无写决定接口（`tests/operations/test_r4_approval_operation.py:606`）。
4. subject 改变后，`on_conflict=create_revision` 创建新的 pending approval revision，`selected_option` 为空，旧 approve 决定只留在旧对象（`tests/operations/test_r4_approval_operation.py:633`）。
5. `RootApprovalRoutes` 仅列举和查询状态/URL，不提供决定写入（`src/scidiscovery/artifact_agent/interfaces/mcp_root_approval_routes.py:9`）。实际决定仍由 loopback UI 的受控入口写入。

这里必须收窄一句证据文案：**“只有声明 approval Operation 才创建 HumanDecision”只应理解为普通科学 Operation 的人工评审路径。** 系统仍有两个有意保留且精确受控的人工边界：ResearchInstance 注册由 `instance_prepare` 创建实例提案审批（`src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py:15`），外部 Effect 执行由冻结的 compiled Effect 合同创建授权请求（`src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py:195`）。二者不是普通探索的隐式资格门，也不构成本轮阻断。

## 五、双真实子智能体证据

对 `deliverables/l3-review-agent-probe-20260901` 的独立核验结果：

- `author-dispatch.json` 摘要为 `c02de80b15fe77a222ff3e02d119c1c84b48da3d15f25155aa421eaae6e02442`，绑定生成的作者 profile、精确 `blind.csv.observe.v1` digest 和 stdio MCP，要求作者直接调用 open、`worker_csv_summarize`、submit。
- `reviewer-dispatch.json` 摘要为 `02f6871761688854240086675f90f3f4b5e60665ca8883e6cba358ba7c96f14a`，绑定独立 reviewer profile、精确 reviewer digest 和 stdio MCP，只要求 open、submit；其 profile 不含作者领域工具。
- 协作进程树中两个 `fork_turns=none` 子智能体分别完成；两份聊天只报告“已完成受控提交”，未传递科学内容。
- probe 脚本只负责准备/排队/读状态，没有实现 stdio bridge、代替 Agent 调用工具或提交结果；deliverable 中也没有 bridge/exchange 文件。
- 持久 Run 记录显示作者与 reviewer 均为 `completed`；作者 activity 含注册工具成功事件。reviewer Run 的指定输入端口精确绑定作者 Artifact，sealed reviewer Artifact 的 parent 也包含该精确 subject。
- `final-evidence.json` 摘要为 `4b507be76aeba58285838f1424376b042486565cbd6208899fbfceed2b7ee913`，记录 `bridge_used=false`、作者注册工具成功、两个 Run 完成以及 exact passing review。

这些证据足以证明“通用子智能体遵循生成的精确 profile/MCP 合同并直接完成调用”的当前原型能力。它不证明 collaboration runner 能热加载刚生成的 custom `agent_type`；该限制已如实保留为 SEC-002 known issue，不影响已批准的 L3 原型完成门。

## 六、独立测试与回归

审查者在 7 GiB 虚拟内存上限内串行执行：

1. L3 四段准入与三项人工决定聚焦集：**5 passed in 2.29s**。
2. L3 + L2 Local Run/current/恢复不变量 + Hardened 生命周期/精确调度/真实 daemon 恢复 + 平台配置 + deploy：**88 passed in 21.30s**。
3. 实现证据另记录当前非 live Operations 全集：**317 passed in 121.62s**。本轮已用上述聚焦集合复核其关键边界，未无意义重复整套测试。
4. `git diff --check`：通过。

回归未发现 L3 破坏 L2 的 Run 唯一终态权威、Local/Hardened 防腐边界、current 精确绑定、单一 catalog/工具投影或部署选择。

## 七、33 项约束与复杂度判断

- **单一权威**：review 来自唯一 compiled Operation catalog；可接受 verdict、reviewer 身份和端口不在运行时重复登记。
- **不可变与精确绑定**：评审匹配完整 ArtifactRef，不按语义名称或 latest 模糊继承；新 revision 必须有新 exact review。
- **最小权限与角色独立**：作者/reviewer 是不同 Agent component，reviewer 只得到声明输入与生命周期工具。
- **CQRS/失败关闭**：preflight 和 exact-review 查询只读；缺失、旧 revision、错误 Operation/端口/verdict 均失败关闭。
- **人工在环**：Root 只读人工状态和 URL，不能把聊天转成决定；新 subject 不继承旧决定。
- **插件通用性**：核心没有 `blind_csv` 分支；测试消费者和插件仅通过 OperationSpec/端口合同接入。
- **奥卡姆原则**：没有增加 Review 实体、全局资格、第二数据库、队列或状态机；利用已存在的 Artifact、Run、输入绑定与 SchedulerSignal 即可闭合需求。

## 八、阻断项

无。

## 九、非阻断建议

1. 后续文档统一将“approval Operation 是唯一人工对象创建入口”改为“普通科学 Operation 的声明式人工审批入口”，同时明确实例注册和外部 Effect 授权是另外两类系统合同，避免读者误以为应删除这两条必要边界。
2. 继续在发布说明中保留 SEC-002：当前证据使用通用 `fork_turns=none` worker 执行生成合同，并未实现动态 custom `agent_type` 热加载。
3. 若以后允许 `accepted_verdicts` 包含 `inconclusive`，应由插件作者明确说明其科学含义；控制面保持只做集合成员判断，不应为其增加全局解释规则。

## 十、最终裁决

**PASS。R5-L3 已满足活动计划完成门。只放行 L4；不据此授权 L5、L6 或正式发布。**
