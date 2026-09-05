# R5-G D4-H2 真实运行前独立审查

## 一、结论

**通过（只放行一次 D4-H2）**

本结论只放行当前脚本 SHA-256、当前真实 state 和下述 immutable request 所定义的一次
`science.hypothesis.revise.v1` 完整对象修订，以及紧随其后的一个全新
`science.hypothesis.criticize.v1`。它不放行实验设计、solver、外部执行、第三轮修订或任何框架扩展。

未发现运行前阻断。当前 D4-H2 是对已失败关闭的 D4-H 科学结果做一次有界直接修订，不需要新增
Operation、Schema、validator、资格权威或核心特判。无论新 critic 的 verdict 为何，runner 都固定
`stage_admissible=false`、`experiment_design_released=false`、
`further_revision_released=false`。

## 二、审查范围与纪律

审查对象是当前未提交工作树中的以下文件及其真实运行绑定：

- `docs/plans/reviews/R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md`；
- `scripts/r5_g_hypothesis_revision_followup_stage.py`；
- `scripts/r5_g_hypothesis_revision_stage.py`；
- `tests/operations/test_r5_g_hypothesis_revision_followup_stage_runner.py`；
- `tests/operations/test_r5_g_hypothesis_revision_stage_runner.py`。

为核验复用边界，另只读检查了现有 revise/critic OperationSpec、通用 direct-revision admission、模型可见
prompt/semantic contract、`_run_agent` 的资源限制与幂等命名路径。没有把本审查扩成全仓审计，也没有猜测
远端 review base。

真实状态为
`.scidiscovery/r5-e2e-private/replay-live-20260830-03/state-d4-abi8`。只执行了 SQLite/CAS/Root
只读查询和 `operation_preflight`；没有调用 `operation_invoke`、没有调度或运行 Agent、没有 claim Worker、
没有运行 solver、没有访问网络、没有审批或其他外部副作用。真实 state 的全部 SQLite 文件在查询前后
SHA-256 清单完全相同。

## 三、逐项核验

### 1. 只复用当前 revise/critic 合同

通过。D4-H2 runner 中仅出现：

- `science.hypothesis.revise.v1`，其既有执行 Agent 为 ideator；
- `science.hypothesis.criticize.v1`，其既有执行 Agent 为 critic。

当前已编译 revise 的三个端口仍为：

| 端口 | usage | Schema |
| --- | --- | --- |
| `prior_draft` | `revision_base` | `scidiscovery.hypothesis-proposal.v1` |
| `change_request` | `change_request` | `scidiscovery.critic-review.v1` |
| `scientific_foundation` | `claim_evidence` | `scidiscovery.scientific-foundation.v1` |

输出仍是完整 `scidiscovery.hypothesis-proposal.v1`，声明的 reviewer 仍是
`science.hypothesis.criticize.v1` 的 `hypothesis_portfolio` 端口。定向检索未发现任何 D4-H2 名称进入
`src/` 或 plugin 声明；D4-H2 名称只存在于专用 runner、runner 测试和审查文档。因此没有新增 Operation、
Schema、validator 或按 D4-H2 名称分支的核心逻辑。

### 2. 资格检查抽取没有削弱首轮 D4-H

通过。首轮 runner 仍经 `_validate_prior_checkpoint` 调用抽取后的
`_validate_qualification_checkpoint`；D4-H2 直接复用同一个函数。该检查仍同时要求：

- exact approval name、revision 与 `approve`；
- 四项 deterministic rebinding 的 exact 集合；
- 新旧 ref 的 payload SHA-256 与 bytes 完全相同；
- ApprovalRequest 的 subject refs 精确等于当前 foundation、intake、六个 frozen source 和 audit。

`_load_qualification_report` 仍要求 ABI 8、当前 qualify Operation/contract digest、未继承旧决定及完整
rebindings。两个 runner 测试文件整体通过，未见为 D4-H2 放松首轮门的旁路。

### 3. D4-H blocked checkpoint 与 exact change request 失败关闭

通过。runner 只接受 science-chain 直属报告，且固定报告 SHA-256 为
`4d6e64e89db11ef23a16c214b9fdba44e6a72f7b376b42402e654b5c1d101444`。报告还必须同时满足
`status=blocked`、`critic_verdict=blocked`、三项 release/admission 为 false、qualification report hash
一致，以及两个 exact Artifact 名：

- `r5g_hypothesis_portfolio_revision.output`；
- `r5g_hypothesis_revision_critic.output`。

随后 runner 要求两项 Task 输出均为 `completed`，critic scheduler signal 为 `blocked`，并调用
`is_exact_reviewer_output` 验证该 critic 是 `science.hypothesis.criticize.v1` 对上述 exact portfolio 的
reviewer 输出。任一身份、终态、verdict 或 subject 关系不一致都会在 invoke 前报错。

### 4. 三个输入与 instruction 范围

通过。真实 preflight 的三个输入精确为：

1. `prior_draft = r5g_hypothesis_portfolio_revision.output`；
2. `change_request = r5g_hypothesis_revision_critic.output`；
3. `scientific_foundation = r5g_d4_intake_split_abi8.scientific_foundation`。

它们分别是当前 D4-H 新 portfolio、对该 exact portfolio 的当前 blocked critic、当前 ABI 8 approved
foundation。真实 preflight 返回：

```text
admissible=true
executor_kind=agent
reason_code=null
port=null
```

instruction 只允许两项修正：为 `numerical_realization_replay` 预登记能区分 mesh-primary、一般 mesh
sensitivity 与 failure 未改变的无歧义分类/阈值门；清理把 prior draft/change request 当作事实证据的
措辞。它明确禁止发明观测或经验常数，并保留已经通过的 whole-chain closure、两项假设上限、三项缺失
绑定、适用范围和非因果边界；同时要求输出完整替代对象而非 patch/delta/receipt。这与 blocked 独立诊断
给出的最小动作一致，没有扩大科学问题。

### 5. 新 critic、停止门与资源继承

通过。新 portfolio 完成后，runner 只创建一个新 critic，输入精确为新 portfolio 与同一 approved
foundation。`_review_admission` 仅在 critic 是 exact reviewer 且密封 verdict 为 `pass` 时返回
admissible；缺失 signal、非 exact subject、错误 Operation 或非 pass 均失败关闭。

无论该判断结果如何，报告中的三个停止字段恒为 false；不存在
`science.experiment.design.v1` 调用。`_run_agent` 在 invoke 前要求当前进程的 `RLIMIT_AS` 不高于
7 GiB，并把该进程限制继承给 control daemon、Worker daemon 和 Codex 子进程；本次测试也使用相同
`ulimit -v 7340032`。

### 6. 恢复、幂等与“不得第三轮”

通过。真实 state 目前恰好 16 个 Task：15 个 `completed`、1 个历史 `failed`，没有非终态 Task，也没有
任何 `*_h2` task binding。第一次运行因此只能占用固定 H2 semantic names。若同一 immutable request
在中断后重入，request fingerprint 命中原 binding，`_run_agent` 会复用原 Task 或已完成输出，不创建
新 revision；critic 同理。报告又固定 `revision_round=2` 与
`further_revision_released=false`。

本放行不覆盖修改 instruction、Operation digest、输入 ref 或脚本后再运行；这类变化会使本审查失效，
不得借 `on_conflict=create_revision` 产生第三轮。

### 7. 对约 302 行专用 runner 的奥卡姆判断

通过。302 行中多数是固定身份/checkpoint 验证、复用两个既有 Operation 的显式编排、不可放行报告、
CLI 和真实运行资源/路径参数；科学 Schema、validator、admission 与 Agent 执行均复用现有实现。它已从
首轮 runner 复用资格、completed output、Artifact ref 和 exact review admission 等公共函数。

还可抽取更多“双 Agent + 报告”机械代码，但这会同时修改已真实运行的首轮 runner、扩大运行前 diff
和回归面；在本次一次性、固定哈希的恢复门上不是必要阻断。当前没有证据支持为了减少行数而扩框架或
在运行前再做共享重构。

## 四、最小测试与只读证据

测试环境统一设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
```

执行两个 runner 测试文件及四个 revise/critic 合同测试：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_r5_g_hypothesis_revision_followup_stage_runner.py \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_general_science_plugin.py::test_general_science_manifest_compiles_exact_role_and_variant_operations \
  tests/operations/test_general_science_plugin.py::test_valid_critic_context_checks_the_worker_handoff \
  tests/operations/test_general_science_plugin.py::test_worker_visible_semantics_are_specific_and_parentage_is_fail_closed \
  tests/operations/test_general_science_plugin.py::test_reviewer_operation_binding_retains_exact_subject_parent
```

结果：`18 passed in 0.54s`，wall clock `1.20s`，max RSS `66464 KiB`。

另运行两个通用 negative/generic direct-revision 测试：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain \
  tests/operations/test_general_science_plugin.py::test_unknown_plugin_direct_revision_shape_is_total_and_fails_closed
```

结果：`2 passed in 2.54s`，wall clock `2.99s`，max RSS `103116 KiB`。该组包含 unrelated change
request 与 reviewer-contract mismatch 的失败关闭，并证明通用 direct-revision 形状不依赖已知 plugin
名称。

真实状态核验使用 installed D4 runtime 执行完整 qualification checkpoint、blocked checkpoint 和同一
request 的 `operation_preflight`，返回 admissible；没有 invoke。查询前后数据库 SHA-256 清单无差异。

## 五、冻结文件指纹与放行条件

本审查所见关键文件 SHA-256：

```text
edb7e290744db43279a92e2dbc130ca758b8a125575d436f1b628533eba99b8c  R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md
d582833f10562f2696b16e795dba1583bce92d291b8ac507c060be1d6d988355  r5_g_hypothesis_revision_followup_stage.py
7f548247279f262c930e5cc7f393ba8e3b3ee8d0b1bd580aa579f6c172096197  r5_g_hypothesis_revision_stage.py
134d62a18d56e7441e714c45cc3c63ac13e116af2bc358e83ee264d9f03d19ed  test_r5_g_hypothesis_revision_followup_stage_runner.py
58f0e39502255873ebce4d63f43b7fd83dfd0a653e941c5aacd133189d4a1a1d  test_r5_g_hypothesis_revision_stage_runner.py
```

只在这些指纹、D4-H blocked report 指纹、当前 16-Task 全终态和上述 exact preflight 绑定保持不变时，
允许执行一次 D4-H2。任一条件变化都必须停止并重新审查；本结论不能继承给 revision、第三轮或下游
实验。
