# R5-M4 科学语义兼容桥删除实现证据

日期：2026-09-01

状态：独立审查 PASS；M4 完成，仅放行 M5

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 本阶段回答的问题

M4 不再试图建设一套新的通用科学图。它只判断两个既有边界是否有真实运行价值：

1. 旧知识更新器是否有消费者，还是控制层为了兼容旧模型而自行补造科学状态；
2. 实验设计意图与执行计划是否真的应该合并，还是分别承载智能体科学选择和确定性机械展开。

结论是：知识更新器没有真实消费者，已经删除；实验意图到计划的物化边界有明确所有权，继续保留。

## 2. 消费者账本与删除决定

删除前，完整安装中只有两个 Operation 产生下列对象：

| 生产 Operation | 输出 |
|---|---|
| `science.knowledge.update.diagnosis.v1` | `scidiscovery.knowledge-update.v1`、`scidiscovery.knowledge-state-projection.v1` |
| `science.knowledge.update.validation.v1` | `scidiscovery.knowledge-update.v1`、`scidiscovery.knowledge-state-projection.v1` |

生产代码搜索确认：除两个更新器可选地读取上一份 `knowledge_state` 以形成自循环外，没有 Agent、
Transform、Effect、审批、调度投影、UI、执行适配器或领域插件消费这两个输出。它们没有进入后续科学
行动，也没有承担 current、Artifact 来源或恢复权威。

因此按计划 9.1 采用最小方案：

- 删除两个知识更新 Operation；
- 删除 `KnowledgeUpdate`、`KnowledgeStateProjection`、旧 `HypothesisPortfolio` 及其专用 Schema、
  validator、resource 和组件注册；
- 删除 `_knowledge_portfolio_view`，不再由确定性代码补造 `testable`、`unassessed`、合成理由和空参数；
- 删除 `ValidationReport.knowledge_update_applicability`，报告只约束自身真实存在的假设评估；
- 保留诊断 Agent 输出、验证报告、不可变 Artifact、精确父引用和显式 current。

这里没有建立替代 reducer、科学图、迁移状态机、兼容转发器或第二注册入口。

## 3. 实验意图与执行计划所有权审计

逐字段审计后的所有权如下：

| 所有者 | 当前职责 | 代表字段或结果 |
|---|---|---|
| 实验设计智能体 | 开放式科学判断 | 目标与假设绑定、对照/基线、干预变量、冻结条件、观测量、可辨识性、预测、证伪条件、验证意图、资源判断、停止条件、信息增益、优先级 |
| 确定性物化 | 从已声明意图机械展开 | 每案例的精确设置、changed factor、comparison contract、完整 validation plan、案例/变量计数、输入和输出摘要 |
| 领域插件 | 把领域中性的计划落实为领域工程对象 | TCAD project/case 源文件、打包、运行鉴证、求解器结果和领域后处理 |
| Root 控制面 | 身份与生命周期事实 | 精确输入绑定、Run、Artifact 登记、current、显式审查/审批/副作用门 |

合并 `ExperimentDesignIntent` 与 `ExperimentPortfolio` 会迫使智能体重复产生机械展开字段，或迫使
Transform 反向选择科学目标。两者都不会减少模型、转换和测试的总量。M4 因此保留
“智能体意图 → 确定性物化 → 领域插件工程实现”的边界，没有新增第三种实验状态。

## 4. 生产修改

本阶段删除或收缩：

- `artifact_agent/transforms.py`：只保留目标投影和实验计划物化；
- `general_science_experiment_components.py`：删除知识状态 Schema、validator、resource 和组件；
- `general_science_experiment_operations.py`：删除验证报告知识更新 Operation；
- `general_science_control_operations.py`：删除知识状态端口 Schema 映射；
- `curve_score/science_operations.py`：删除曲线诊断知识更新 Operation；
- 删除 `schema/knowledge.py` 与 `schema/hypothesis.py`；
- `schema/validation.py`：删除只为已移除 reducer 存在的适用性开关。

M3 的历史证据保持不变。M4 的等价门只比较仍然存在的 20 个生产 Transform；M2 精确 oracle 仍证明
历史目录包含被有意删除的两个知识更新器。9 个父链 guard 继续逐项执行正负 preflight。

## 5. 复杂度变化

| 指标 | M3 通过态 | M4 候选 | 变化 |
|---|---:|---:|---:|
| 生产 Python 文件 | 142 | 140 | -2 |
| 生产 Python 行数 | 48,397 | 47,428 | -969 |
| 完整产品 Operation | 46 | 44 | -2 |
| Agent / Transform / Approval / Effect | 20 / 22 / 3 / 1 | 20 / 20 / 3 / 1 | Transform -2 |
| 插件组件 | 216 | 209 | -7 |
| Root 工具、Run 状态、数据库事实 | 不变 | 不变 | 0 |

当前生产树摘要：

```text
4c88fcdaa2d2535df6cc8506cd2fb71796cb7132f7fb02c1a6122348afdb0eab
```

完整目录摘要：

```text
30b3d3db909eddedd34dc1182126056c4e3c3d4f11fc1d668fdc2ccf5f1249f3
```

## 6. 自动化证据

聚焦回归使用 7 GiB 虚拟内存上限和串行执行：

```text
pytest -q \
  tests/operations/test_m2_curve_analysis_boundary.py \
  tests/operations/test_m4_scientific_semantic_bridge_removal.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_m3_transform_adapter_removal.py \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_r5_general_plugin_split.py \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_h2b_domain_boundaries.py
27 passed in 36.78s
```

该组测试证明：

- 删除对象不再出现在目录、端口 Schema 或组件中；
- 生产代码不再保留并行知识状态或默认科学晋级桥；
- 诊断 Operation 与实验计划机械物化仍存在；
- 保留的 20 个 Transform 与精确 M2 oracle 输出等价；
- 9 个父链 guard、插件拆分、目录阶段与领域边界未退化。

完整串行回归与静态检查：

```text
pytest -q
227 passed in 109.69s

python -m py_compile <M4 受影响生产与测试模块>
通过，无输出

git diff --check
通过，无输出
```

## 7. 当前判断

M4 候选符合“删除无消费者，而不是设计替代系统”的奥卡姆原则。控制层不再合成科学支持状态，
未知、不确定性和冲突没有被默认值覆盖；实验的科学判断仍由 Worker 产生，机械关系仍可确定性重放。
独立审查见
`../reviews/R5_M4_SCIENTIFIC_SEMANTIC_BRIDGE_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`，结论 PASS。M4 完成，
仅放行 M5；不宣称 R5-M 完成。
