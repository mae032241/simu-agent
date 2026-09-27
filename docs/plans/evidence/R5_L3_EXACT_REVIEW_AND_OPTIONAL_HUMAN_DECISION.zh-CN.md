# R5-L3 精确独立审查与可选人工决定证据

日期：2026-09-01  
阶段：L3 独立复审候选

## 1. 实现结论

L3 没有新增 Review 表、审查状态机、全局资格或自动阶段拓扑。实现直接复用已经编译进
`OperationSpec.review` 的审查边、作者输出上的生产合同、Run 冻结输入和
`RunService.is_exact_reviewer_output`。下游准入只回答一个机械问题：当前输入集合中是否存在由声明的
独立 reviewer Operation 对这个精确 Artifact 产生、且 verdict 可接受的审查 Artifact。

普通 Local 探索不会创建 qualification 或 approval。只有 executor 明确为 `approval` 且带编译人工
合同的 Operation 才创建待决 `HumanDecision` 请求；Root 只暴露查询与 URL，不暴露代用户决定工具。

## 2. 精确审查门正反例

自动化测试构造一个仅用于验收的下游消费者，生产核心和盲 CSV 插件均未增加专用分支：

```text
作者结果 A1，无审查          → 拒绝 input_independent_review_missing
A1 + reviewer(A1)=pass       → 放行
作者同名有意修订为 A2
A2 + 旧 reviewer(A1)=pass    → 拒绝 input_independent_review_missing
A2 + reviewer(A2)=pass       → 放行
```

这证明审查绑定精确 Artifact ref，不按逻辑名、latest、父版本或旧 verdict 继承。审查者本身可以读取
待审作者结果，不会被审查门递归阻断；其他消费者必须显式携带审查 Artifact。

## 3. 人工决定边界

Local 默认路径的直接测试证明：

- 普通作者 Run 完成后，approval namespace 和 `approval_list` 都为空；
- 声明为 approval 的 Operation 才创建一个 pending 请求并返回 loopback URL；
- 该行为不创建 Task 或普通 Agent Run；
- Root 工具表不存在 `decide` 或 `record_decision` 类写入口；
- 既有回归继续证明修改审批对象后创建的是 pending 新修订，旧决定不继承。

聊天文本因此不能进入人工决定事实；写决定仍只在 loopback UI 服务边界。

## 4. 真实作者—审查者 Agent 闭环

有效证据保存在仓库 `deliverables/l3-review-agent-probe-20260901/`。流程为：

```text
operation_invoke(author)
→ 无父历史作者子智能体直接启动精确 stdio MCP
→ 作者直接调用 open、注册 CSV 工具、原生写结果、submit
→ Run completed + 不可变 Observation Artifact
→ operation_invoke(reviewer)，精确绑定源 CSV 与 Observation
→ 另一无父历史审查者子智能体直接启动自己的精确 stdio MCP
→ 审查者只读封存输入、原生写审查、直接 submit
→ Run completed + 精确父链 + passing exact-review 判定
```

两个子智能体没有直接通信，父进程没有桥接工具结果或代 submit。聊天只返回“已完成受控提交。”，
科学 verdict 只从封存审查 Artifact 和 Run 收据读取。持久化最终证据：

```json
{
  "author_agent_type": "op_blind_csv_observe_v1_bb23321d26a4",
  "author_registered_tool_succeeded": true,
  "author_state": "completed",
  "bridge_used": false,
  "review_agent_type": "op_blind_csv_review_v1_81a2d8408b07",
  "review_has_exact_subject_parent": true,
  "review_is_exact_and_passing": true,
  "review_state": "completed"
}
```

与 L2 相同，当前协作运行器不能热加载运行中生成的自定义 `agent_type`；在用户批准的第一版原型边界
内，实际 dispatch 使用两个 `fork_turns="none"` 的通用 worker，分别执行各自生成的精确 profile 和
MCP 合同。这里不冒充动态角色已加载，也不关闭 `SEC-002`。

## 5. 回归结果

全部串行并限制为 7 GiB 虚拟内存：

```text
L3 精确审查、普通探索、Local 人工策略及旧决定不继承聚焦回归
5 passed in 2.26s

tests/operations -m 'not live'
317 passed in 121.62s
```

## 6. 候选摘要

```text
L3 review tests            77a093025987f189b214787ca9d3681cf5b9fb814cf05424301a646261f02f88
approval regression       7f59ebdf93e8b4d51208f046aa3e60d572cb796acc274145bb09c4b6061d68b1
live probe harness        9a11563f29a1a45e04250a0ef63bbca7e682c6c09a8b018d711365000fbbd985
author dispatch           c02de80b15fe77a222ff3e02d119c1c84b48da3d15f25155aa421eaae6e02442
reviewer dispatch         02f6871761688854240086675f90f3f4b5e60665ca8883e6cba358ba7c96f14a
final evidence            4b507be76aeba58285838f1424376b042486565cbd6208899fbfceed2b7ee913
Run exact-review logic    1d0e77e9e73081770f24c35a36aa82d0ca68f694ee92c71b25b2b43ca313e0c2
Root admission logic      bd2ebeb0ae2cd93e6760fabf4f1d7393e1b3a8bf1a89284af3906fd45094e487
ReviewSpec                23c83e50cb52c3943af4cd0e6ef0c7087712b2f96af5a31f5a7bd355c53695f1
```

摘要只界定候选，不代替独立审查。
