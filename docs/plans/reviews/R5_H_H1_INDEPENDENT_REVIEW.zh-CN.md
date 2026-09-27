# R5-H H1 第二轮独立审查

日期：2026-08-30  
性质：独立实现复审  
结论：**通过，只放行 H2a**

## 1. 审查范围

本轮只审查 H1“把实验优先级判断还给 Agent”的精确候选：

- `src/scidiscovery/artifact_agent/schema/experiment.py`；
- `src/scidiscovery/artifact_agent/schema/experiment_intent.py`；
- `tests/operations/test_general_science_plugin.py` 中的实验优先级正反例；
- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 的 H1 设计和候选记录；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第26节的候选状态；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 中与 H1 直接相关的约束。

本轮不审查 H2 的插件迁移设计，也不把累计工作树中的其他 R1～R5 变更纳入 H1 候选。

审查时上述六个文件的 SHA-256 为：

```text
5bbd75a40063ed4c6ce30252391b75dff3ea5cb7b097fa32c55a2293e1f507f3  src/scidiscovery/artifact_agent/schema/experiment.py
e19a240af7216e21653e80fdbf6f9910f1010ae7ff8fae5fe43f35ecefce6b42  src/scidiscovery/artifact_agent/schema/experiment_intent.py
615d3609724822f5e67a834205e60205d889308d037ef07653bfa4e93553ab16  tests/operations/test_general_science_plugin.py
d00aa7e62f3be19cf141d0a303293245011c96b627cc9bb048ca52b5b5bf535b  docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md
cf52210e7c1184450329bd700b17445157c018694fb7ab5e197b5de62a9355eb  docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md
e3b24af3d05b94caee4f1a2dbde8a6ac44ab7897557ef95618653b07ff420e38  docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

## 2. 首轮唯一条件及返修结果

首轮审查确认生产实现已经正确，但负向测试只覆盖意图 Schema 的缺项情形，没有持久化证明意图层
和物化后 `ExperimentPortfolio` 层都对缺项、重复和未知候选失败关闭，也没有直接断言排序理由与
价值评估原样保留，因此结论为“有条件通过，不放行 H2”。

返修没有修改生产代码，只调整测试：

- `_two_proposal_engineering_intent` 建立一个 Agent 明确优先高成本、低机械评分实验的固定输入；
- 正例先通过 `ExperimentDesignIntent`，再通过 `materialize_experiment_design_intent` 和
  `ExperimentPortfolio`，并断言 `priority_order`、`priority_rationale` 及两个
  `value_assessment` 原样保留；
- 意图层分别增加 `missing`、`duplicate`、`unknown` 三个参数化负例；
- 物化后组合 Schema 层分别增加同样三个参数化负例。

这六个负例互不借用成功路径：意图层直接验证 Worker 输出合同，组合层先生成合法完整计划，再只
改变 `priority_order` 并直接调用 `ExperimentPortfolio` 的严格 Schema。首轮条件已经关闭。

## 3. 生产实现判断

### 3.1 固定科研价值公式已完整删除

生产代码中不再存在：

- `_LEVEL_SCORE`；
- `experiment_value_score`；
- “按确定性价值分数非递增”的 Schema 拒绝；
- materializer 对候选重新排序或以分数冲突拒绝 Agent 顺序。

对 `src/`、`plugins/` 和 `tests/` 搜索上述符号与两条旧错误消息均无命中。也未发现由
`evidence_support`、`discrimination_power`、`information_gain`、`cost` 和
`added_free_parameters` 组成的等价隐藏公式或阈值。

### 3.2 科学内容仍由 Agent 拥有

- `ExperimentDesignIntent` 仍要求 Agent 给出完整 `priority_order` 和非空
  `priority_rationale`；
- 每个 `ExperimentProposalIntent` 仍要求 `value_assessment`；
- materializer 将三者原样写入 `ExperimentPortfolio`，不选择目标、不改顺序、不改理由；
- `ExperimentPortfolio` 只校验顺序是 proposal key 的完整排列，不评价该顺序在科学上是否正确。

因此，价值评估字段仍可承载 Agent 判断和后续审查依据，但不再成为控制层的普适评分函数。

### 3.3 承重机械门禁未削弱

本轮保留了：

- proposal、validation plan、selected hypothesis 和 priority 引用的唯一性及集合闭合；
- 科学实验的假设、对照、干预因素、可观测量、预测检验和 validation plan 结构；
- 目标与假设组合的精确内容校验；
- 编译 Operation 中的 approved foundation cohort、独立 critic 输入和精确父链 guard；
- curve 声明、TCAD materialized-plan 准入、Approval 精确身份和冻结基线。

H1 没有新增状态、数据库表、注册表、readiness、Scorer 或 Operation，也没有把确定性 Metric
变成科学 verdict。

## 4. 33项约束判断

- `ROLE-001`：通过。候选排序、理由和价值评估均由 Worker 生成，控制层不再覆盖排序。
- `DET-001`：通过。materializer 仍只展开机械结构并执行可重放 Schema 校验。
- `DET-002`：通过。已删除 materializer 与 Schema 中的自动科研排序及排序否决。
- `TOP-001`：通过。H1 没有增加固定阶段、角色状态推进或隐藏规划拓扑。
- `AUTH-003`：通过。H1 没有增加 OperationSpec 之外的能力白名单或调用路径。

因此，H1 关闭了 `ROLE-001` 与 `DET-002` 所记录的实验排序缺陷，同时没有使其他四项承重边界退化。

## 5. 独立重放

在 7 GiB 进程虚拟内存上限内执行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_general_science_plugin.py \
  tests/operations/test_curve_score_operation_plugin.py \
  tests/operations/test_tcad_operation_plugin.py \
  tests/operations/test_r4_approval_operation.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_r5_frozen_baselines.py
```

结果：

```text
89 passed in 56.32s
```

该独立命令包含 execution approval identity，不包含另一条本地候选命令中的 general transform
文件，因此其89项不得与另一命令的90项合并为同一个测试数字。

另行对 H1 精确文件执行 `git diff --check`，结果通过，无输出。

## 6. 剩余风险和边界

本报告只证明通用实验优先级的科学所有权和机械排列门已经闭合。实验 Operation 当前仍由
`curve_score.science_operations` 拥有、通用实验 Schema 仍含曲线字段等插件所有权问题属于 H2，
不能因 H1 通过而视为解决。H2a 必须另行实现和独立审查，且不得重新引入评分器、代理注册层或
第二目录。

## 7. 最终结论

**通过。允许进入 H2a。**

首轮唯一条件已经由最小测试返修关闭；生产实现没有追加补丁式分支或新实体。H1 达成“把科研
优先级判断还给 Agent、控制层只保留机械门禁”的目标。
