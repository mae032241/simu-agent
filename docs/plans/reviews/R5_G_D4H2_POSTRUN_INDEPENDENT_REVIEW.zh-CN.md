# R5-G D4-H2 最终独立后置复核

## 一、结论

**实现与停止门通过，科学结果未通过，R5-G 停止于假设阶段。**

真实 run `.scidiscovery/r5-e2e-private/replay-live-20260830-03/state-d4-abi8` 中，D4-H2 的完整
portfolio revision 与全新 critic Task 均已 `completed`，三项冻结输入、Operation/digest、Task、
primary output、Artifact ref、task edge 与 exact reviewer subject 全部闭合。新 critic 的密封
scheduler signal 为 `blocked`；followup 报告据此保持 `status=blocked`、
`stage_admissible=false`、`experiment_design_released=false`、
`further_revision_released=false`。现有 Task 全部终态，没有实验设计 Task、D4-H2 之后的第三轮修订
binding 或本轮 solver/external execution。

`blocked` 有科学依据。D4-H change request 要求为 `numerical_realization_replay` 增加能区分
mesh-primary、一般 mesh sensitivity 与 failure unchanged 的预登记规则；H2 完整对象已经给出严格的
fail-to-pass 门，新 critic 对该项三维均判 `pass`。但 H2 仍把 `traceability_binding_gap` 放在竞争机制
集合中，并称当前 failure classification “primarily maintained” by 缺失 closure。approved foundation
只支持这些缺口阻止独立因果归因，并不支持缺口本身产生已观测的局部 residual mismatch；closure 失败
也可与数值或物理原因同时存在，因而不能识别该项为竞争机制。新 critic 对其
`physical_plausibility=fail`、`identifiability=fail` 的判断与密封对象内容一致。

未发现新的架构、上下文或 validator bug。两轮均复用相同的 revise/critic Operation digest；H2 critic
直接获得 exact H2 portfolio 与同一 approved foundation，完整覆盖两个 hypothesis key，并作为独立
reviewer 有权审查完整替代对象而不继承 D4-H 对某一项的旧 `pass`。Schema/validator 已接受并封存两个
完整输出；`blocked` 来自 critic 的科学维度失败，不是 validator 拒绝、上下文缺失或 runner 自造 verdict。

无论对这一科学判断还可作何争论，本轮均不得放行第三轮修订、实验设计、solver 或外部执行；这是本次
最终复核的冻结停止门。审批 UI 的安全写入与精确主体绑定曾真实完成，但其信息架构、可理解性和操作
效率的可用性验收仍然**未通过**，不能因科学链停止或一次成功点击而改写为通过。

## 二、范围与证据纪律

复核基线是当前共享未提交工作树与上述指定真实 state；没有猜测远端 base。完整阅读：

- `docs/plans/reviews/R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4H2_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `scripts/r5_g_hypothesis_revision_followup_stage.py`。

另只读检查 exact reviewer 实现、followup/stage runner 测试与现有 UI 现场观察。科学内容只从 SQLite
确认 `completed` 后的 sealed CAS primary outputs 读取：D4-H critic change request、H2 完整 portfolio
和 H2 critic。没有采信 workspace draft、`codex-final.txt`、events、child chat 或 daemon 日志中的科学
内容；没有调度 Agent、调用 solver、访问网络、写审批或修改真实 state。共享工作树的既有改动均未
修改或回退；本报告是本次复核唯一新增文件。

## 三、真实状态机器核验

### 1. D4-H2 三输入与 revision 谱系

`r5g_hypothesis_portfolio_revision_h2` 绑定
`tsk_21f20a98613f4ad5b7f67a42be13e362`，Task descriptor 为
`art_9d29d8cc1dbe46afb6a705562018811d` / SHA-256
`50134bc39661760002554628bcb14a010cce7399690dc2e112ebffcff32db70e`。冻结 authority 为：

```text
operation_id= science.hypothesis.revise.v1
operation_digest=17ee7a2305dbb900ead87ca358b429f00de416255243af6f00e6f21ff52dda93
```

descriptor、Artifact parent links 与输出 envelope 中的三个直接输入精确一致：

| 端口 | Artifact / payload SHA-256 |
| --- | --- |
| `prior_draft` | `art_3932949c418e4103a4964f56f50d5794` / `584bbb2050dfde3acca93c7d5830050d5d020e029f39b242f42d240fd6e6ed5b` |
| `change_request` | `art_4c8436c6be624193b6b2665861d9fffa` / `30b21f05261e64cdd1aa3b52b95989eb9bcb0bf3b02a1ab97d5acd8cfe4f8119` |
| `scientific_foundation` | `art_e83715c2fb404cac8ccf33317ec181d1` / `4f134362942c35608187c995e65756f67145d2c2505c68472244ba42af11939b` |

Task 为 `completed`；primary output
`r5g_hypothesis_portfolio_revision_h2.output` 精确绑定
`art_7c4232dacde248b1b8e5d6aebec67272` / SHA-256
`3bdc1bfc08fb0ead8a636ad61d5cf605925981eb7dcadeee0765aed41d9b5ee4`，其 task edge 回指上述 exact
Task descriptor，CAS bytes 复算一致。

### 2. 全新 critic 与 exact reviewer

`r5g_hypothesis_revision_critic_h2` 绑定
`tsk_6f3830b623604400b3d214f7930906d6`，Task descriptor 为
`art_4d14f9e5843b4f468f268ee01797bdf8` / SHA-256
`f0c91d352779661db558f0011a218e8865138b1b9cd8d8d862c6af3693b79`。冻结 authority 为：

```text
operation_id= science.hypothesis.criticize.v1
operation_digest=fbb97082dd5c6c201e93b452066c7d3a751fa64c9aef06b65ec073c3048f1321
```

critic 的 `hypothesis_portfolio` 端口精确等于上述 H2 output ref，另一个端口精确等于同一 foundation。
Task 为 `completed`；primary output 为
`art_600ad52264e4474cb985dcf6d2a79288` / SHA-256
`f870f20e03dd847a2f8ab9e95c64ad58b7ad920ca607b940bec5840aacb40afd`。output task edge、descriptor
input port/subject ref、reviewer Operation 与 completed task mapping 全部匹配，因此满足
`is_exact_reviewer_output` 的 exact reviewer 条件。

其 scheduler signal 为 `art_4ee108db34cc43d39bae2db9e769beca` / SHA-256
`424dda8371939e1eb0cee6f65494b180c8b2943a802e84dcaddddd62c40c5827`，密封
`verdict=blocked`，并以 H2 critic output 为唯一 parent。critic payload 恰好覆盖 H2 portfolio 的两个
hypothesis key；`traceability_binding_gap` 同时有 physical plausibility 与 identifiability fail，故
signal 与内容相符。

### 3. followup 报告与冻结停止门

`hypothesis-revision-followup-stage-report.r5g_hypothesis_revision_critic_h2.output.json` 的 SHA-256 为
`3cd745b2d996428496ec4b77be317e9c77e1e87d290ac57fc8fe667c1f888d8f`，机器断言如下字段：

```text
status=blocked
revision_task_state=completed
critic_task_state=completed
critic_verdict=blocked
review_contract_admissible=false
stage_admissible=false
experiment_design_released=false
further_revision_released=false
```

真实 state 当前为 `completed=17`、历史 `failed=1`、非终态 `0`。逐个解析全部 Task descriptor，未见
`science.experiment.design.v1`；scheduler binding 未见 H3 或 H2 revision；`executions.sqlite3` 仍只有
2026-08-29 创建的历史 frozen replay `exe_de6927ace24b4d498d99f1be184b2b27`（`collected`），没有本轮
solver/external execution。因此“Task 完成”没有被冒充为“科学通过”，且停止门已真实生效。

## 四、有限科学比较

### 1. D4-H change request 已被 H2 的 mesh 规则解决

D4-H critic 的精确最小动作是把任意局部改善替换为一个预登记门，使 mesh-primary 与一般 sensitivity、
failure unchanged 可区分。H2 完整对象规定：只有单独 mesh state 把同一 closed bundle 从
`pass=false` 翻转为 `pass=true` 才算 mesh-primary；两侧仍 fail 而 failed-gate vector 或既有局部窗口量
变化只算一般 sensitivity；两侧仍 fail 且这些量不变则算 failure unchanged。它没有引入新经验阈值，
沿用 foundation 已有 gate、0.02 decade 阈值与既有窗口。H2 critic 对该项三维均 `pass`，说明本轮
exact change request 已得到实质响应。

### 2. 新 blocked 是独立 critic 发现的另一项科学缺陷

H2 对 `traceability_binding_gap` 保留了 whole-chain closure、三项缺失绑定、两次独立 rescoring 与
clean closure 即 reject 的规则；但仍把它作为 `numerical_realization_replay` 的竞争机制，并写成当前
failure classification 主要由 closure 缺失维持。这里把“不能确认 score 身份/因果归因”的认识论边界
提升成“解释 residual failure 的机制”。即使 closure package 失败，真实 residual 仍可能来自数值或物理
机制；该结果不会在竞争机制之间提供识别。H2 critic 据此阻断具有对象内可核查的科学理由，不依赖未来
数据，也没有把缺失未来观测误判为当前设计失败。

两轮 critic 对 whole-chain 项的判断确有变化，但这不是旧 verdict 继承失败：H2 是完整替代对象，全新
critic 按合同只绑定当前对象与 foundation，独立审查本来就不能继承 D4-H 的逐项 `pass`。其结论没有被
runner、Schema 或 validator 改写。该科学分歧已足以维持失败关闭；冻结门禁止再以第三轮对象优化它。

## 五、最小独立测试

测试严格串行，并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
```

执行：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_r5_g_hypothesis_revision_followup_stage_runner.py \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_general_science_plugin.py::test_reviewer_operation_binding_retains_exact_subject_parent \
  tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain \
  tests/operations/test_general_science_plugin.py::test_unknown_plugin_direct_revision_shape_is_total_and_fails_closed
```

结果：`17 passed in 2.83s`，process exit `0`，max RSS `104348 KiB`。该集合覆盖 followup exact blocked
checkpoint、三输入、不可释放实验/第三轮、完整对象 revision、exact reviewer subject parent、通用
direct-revision parent chain 与未知插件失败关闭。另以 `mode=ro&immutable=1` SQLite、Artifact registry
和 CAS SHA-256 对真实状态执行机器断言，全部通过。

未运行全仓测试、浏览器自动化、真实 Agent、网络、solver 或新外部执行。它们不是确认本次已封存
D4-H2 谱系、科学 blocked 与停止门的最小必要证据，也不能替代仍未通过的真实审批 UI 可用性验收。

## 六、冻结指纹

```text
edb7e290744db43279a92e2dbc130ca758b8a125575d436f1b628533eba99b8c  R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md
e2b2495e55aedbb43f9f77875ecfa38471192e456018b34c09c9c9f62a59ee68  R5_G_D4H2_PRERUN_INDEPENDENT_REVIEW.zh-CN.md
d582833f10562f2696b16e795dba1583bce92d291b8ac507c060be1d6d988355  r5_g_hypothesis_revision_followup_stage.py
3cd745b2d996428496ec4b77be317e9c77e1e87d290ac57fc8fe667c1f888d8f  hypothesis-revision-followup-stage-report.r5g_hypothesis_revision_critic_h2.output.json
```

最终边界不可被后续解释扩张：**R5-G 到此停止于假设阶段；不得第三轮修订，不得进入实验设计或
solver。审批 UI 可用性仍未通过。**
