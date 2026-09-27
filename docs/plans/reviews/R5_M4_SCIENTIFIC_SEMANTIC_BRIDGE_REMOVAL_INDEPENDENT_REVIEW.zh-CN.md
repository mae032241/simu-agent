# R5-M4 科学语义兼容桥删除独立审查

日期：2026-09-01

结论：**PASS**

阶段门：**M4 通过，仅放行 M5。** 本报告不宣称 R5-M 完成，不改变 M0—M3 的既有独立审查结论，
也不把 33 项约束整体升级为 `conformant`。

## 1. 独立性、范围与基线

本审查者未参与 M4 实现，没有修改生产代码或测试代码；唯一写入是本报告。审查只回答 M4“删除
科学语义兼容桥”的问题，不扩展到 M5 的插件收敛或 R5-M 总验收。

仓库只有基线提交 `404aeb1`，M1—M4 与更早修改共同位于未提交/未跟踪工作树中。因此
`git diff HEAD` 不是 M3→M4 阶段补丁，本报告没有把它当作阶段差异。M4 边界由以下三组可复核事实
共同确定：

- M4 实现证据列出的删改对象；
- `archive/r5-m2-transform-oracle/m2-production-source.tar.gz` 中的冻结生产源码及当前生产树逐文件对照；
- 当前编译目录、生产消费者、Schema、Transform、TCAD 物化路径和可执行回归。

审查完整阅读了 M4 计划第 9 节与第 13 节、M4 实现证据、M3 返工独立复审、当前架构、最小设计
宪章、33 项约束、当前比较评估和 TCAD 插件说明，并按跨边界审查、简化消费者证明、变更范围检查和
最小修改原则核查当前代码。

## 2. 阻断项

**无。** 没有发现误删承重科学路径、重新合成科学判断、隐藏第二状态权威、等价门失真或以生产补丁
迎合测试的实质缺口。

## 3. 两个 knowledge reducer 的消费者与删除决定

冻结 M2 完整生产归档中的相关符号扫描只命中 8 个文件：

```text
src/scidiscovery/artifact_agent/schema/hypothesis.py
src/scidiscovery/artifact_agent/schema/knowledge.py
src/scidiscovery/artifact_agent/schema/validation.py
src/scidiscovery/artifact_agent/transforms.py
src/scidiscovery/general_science_control_operations.py
src/scidiscovery/general_science_experiment_components.py
src/scidiscovery/general_science_experiment_operations.py
plugins/curve_score/curve_score/science_operations.py
```

这 8 个文件恰好是旧 `HypothesisPortfolio`/knowledge Schema、自身 reducer/兼容桥，以及声明 reducer
所需的端口、资源、validator 和组件。两个 Operation 的唯一递归输入是可选的上一份
`knowledge_state`；生产归档中没有第三个 Agent、Transform、Approval、Effect、调度投影、UI、执行
adapter 或领域插件消费 `scidiscovery.knowledge-update.v1` 或
`scidiscovery.knowledge-state-projection.v1`。

旧 `_knowledge_portfolio_view` 还把当前 `HypothesisProposal` 转写为另一个模型，并机械补造：

- `status="testable"`；
- `support_level="unassessed"`；
- 以预测/证伪文字复制出的 rationale；
- 空参数集合和空 missing-input 集合。

这些值不是输入科学事实，且 reducer 的结果没有下游消费者。保留它们会形成一个只对自身循环的第二
科学状态投影；重建新的通用科学图只会增加模型、迁移和 current/资格问题。因此删除两个 reducer、
两个专用状态 Schema 和配套组件，而保留原始诊断与显式 Artifact/current，是物理与架构上更小、
更诚实的选择。

## 4. 承重路径没有被误删

当前编译目录仍包含：

- `science.result.diagnose.v1`；
- `science.result.diagnose.curve-error.v1`；
- `science.experiment.materialize.v1`。

`LayeredDiagnosisReport` 及其精确 plan/contract/metric/bundle 上下文校验仍在；通用
`ValidationReport`、三维验证、假设 assessment 和 claim 投影也仍在，只删除了专为旧 reducer
切换分支服务的 `knowledge_update_applicability`。删除后的 ValidationReport 仍要求：有假设 assessment
时至少一项实际测试、必须保留 remaining contradiction 和建议行动；没有 assessment 时不得携带这些
转换上下文。因此未知和未测试状态没有被默认 promotion 覆盖。

M4 未修改 Artifact/CAS、父链、SchedulerBinding/current、Run 四态、Approval、Execution、SQLite
迁移或 Root 生命周期。当前专项回归还经真实 Root preflight/invoke 路径检查 retained Transform，
没有以单元级函数调用代替承重入口。

## 5. 控制与 Transform 不再合成科学支持结论

当前生产树对精确构造模式的搜索未发现 `support_level`、`HypothesisStatus`、
`status="testable"`、`support_level="unassessed"` 或空参数科学桥。剩余 `testable` 只出现在“提出可检验
机制”的 Worker 提示语中；剩余 conflict/missing/status 处理属于输入闭合、确定性覆盖/曲线指标或
执行生命周期，并不生成假设支持等级。

控制层仍只校验合同、输入、父链和生命周期；科学 Worker 产生假设、批评、实验选择和诊断；Metric
只产生显式可复算结果。未发现空参数、默认冲突结论、默认支持等级或固定下一科研阶段重新进入 Root、
Transform 或插件组件。

## 6. 实验意图、确定性物化与 TCAD 所有权

当前字段和调用路径形成清楚的三层所有权：

| 层 | 所有内容 | 当前证据 |
|---|---|---|
| `ExperimentDesignIntent` / Worker | 目标与假设选择、基线/对照、变量角色与值、观测量、可辨识性、预测/证伪、验证意图、资源判断、停止条件和优先级 | Agent 输出 validator 要求科学输入闭合，新设计输出不得手写展开后的完整计划 |
| `materialize_experiment_design_inputs` / Transform | 为每个 case 展开 expectation/settings，派生 changed factors、comparison contract、validation check id/applicability、case/变量计数和内容摘要 | `science.experiment.materialize.v1` 是 support Transform，输出完整计划与确定性报告 |
| TCAD 插件 | 把领域中性 `ExperimentPortfolio` 落实为 solver 工程、case/source binding、reviewed package、runtime attestation 和运行结果 | TCAD author/reviewer/package 均消费精确 experiment plan，并在打包前重新验证 case control realization |

`ExperimentPortfolio` 的重复外观主要是“紧凑声明”与“完整、可独立消费的机械展开结果”之间的源/派生
关系；下游曲线与 TCAD 代码真实消费完整 cases、settings、comparison contract 和 validation plans。
直接合并会让 Worker 重复手写这些机械字段，或让 Transform 反向选择科学目标，模型、转换和测试并不
净减。M4 保留此边界符合计划 9.2；没有发现必须在本阶段删除的第三个实验模型。

## 7. 保留 20 个 Transform、M2 oracle 与 9 个 guards

`test_m3_transform_equivalence.py` 没有把目录摘要冒充 callable 等价。它执行以下精确集合关系：

- 冻结 M2 目录必须等于当前 20 个 retained Transform 加两个明确删除的 knowledge reducer；
- 当前目录必须精确等于 retained 20 项，缺少任一项或多出任一项都会失败；
- 两个独立进程分别从 M2 归档和当前生产根加载模块，经真实 Root preflight/invoke 执行 retained 20 项；
- 比较完整输出字节、媒体/Schema、父引用顺序、Operation 身份、幂等、同名异请求拒绝和显式 revision；
- guarded Operation 集合与 9 个正负 guard 场景精确相等。

runner 只允许旧目录额外包含两个固定 id，并不允许任意 Transform 消失。它从行为比较中排除的只有
源码/目录 provenance 字段；没有归一化科学 JSON、PNG、CSV、浮点、父链或错误结果。因此 M4 对 M3
等价测试的调整是删除边界本身，不是针对性放宽 retained 行为。

## 8. 奥卡姆性、插件与 33 项约束

独立复算当前生产 Python 为 **140 文件、47,428 行**，与实现证据一致；相对 M3 通过态净减 2 个
生产文件和 969 行。当前完整目录为 44 个 Operation，其中 Agent/Transform/Approval/Effect 为
20/20/3/1；组件由 216 减至 209。M4 没有增加插件 entry point、Registry、Root 工具、Run 状态、
数据库表、常驻服务、preflight、invoke 或兼容 adapter。

当前 33 项约束登记仍为 33 个唯一 id，状态保持 7 `conformant`、25 `pending_review`、1
`known_issue`。与 M4 直接相关的 LIN、EVD、UNC、ROLE 和 DET 约束没有因本轮绿测被虚假晋级；
`SEC-002` 仍诚实保持 `known_issue`。本次 PASS 只证明 M4 删除及其相邻边界成立。

## 9. 独立执行记录

所有 pytest 串行运行，设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`，禁用 pytest cache 和 Python
bytecode 写入。

1. M4、诊断边界、通用 Transform、M3 结构与精确 oracle、插件拆分、目录阶段和领域边界聚焦集合：

   ```text
   pytest -q -p no:cacheprovider \
     tests/operations/test_m2_curve_analysis_boundary.py \
     tests/operations/test_m4_scientific_semantic_bridge_removal.py \
     tests/operations/test_general_transform_operations.py \
     tests/operations/test_m3_transform_adapter_removal.py \
     tests/operations/test_m3_transform_equivalence.py \
     tests/operations/test_r5_general_plugin_split.py \
     tests/operations/test_r5_catalog_stages.py \
     tests/operations/test_h2b_domain_boundaries.py

   27 passed in 37.01s
   ELAPSED=37.42 MAXRSS_KB=105388 EXIT=0
   ```

2. 冻结 M2 生产消费者扫描：遍历归档中全部生产 `.py`，按 Operation id、Schema id、类型和桥符号
   搜索，只命中第 3 节列出的 8 个所有者文件。

3. 冻结 M2 与当前相关文件的逐行 `diff -u`：确认两个 Operation、两个 Schema、bridge、组件、端口
   映射和 applicability 分支被删除；诊断与实验物化窄函数保留。

4. `python scripts/r5_current_metrics.py` 的独立投影：

   ```text
   production_python: files=140, lines=47428
   operations_package: files=8, lines=2080
   ```

5. `git diff --check`：通过，无输出。

实现证据报告全量串行回归 `227 passed in 109.69s` 和受影响模块 `py_compile` 通过。本审查按变更范围
skill 选择了能直接证明删除、真实消费者、retained callable 等价和 guard 的 27 项集合，没有重复
无关全量，也没有运行实时模型 Agent、浏览器或真实 solver；这些不属于 M4 reducer 删除的替代证据，
本报告也不宣称验证它们。

## 10. 非阻断观察

1. `plugins/curve_score/README.md` 和 `README.zh-CN.md` 仍各有一条
   `science.knowledge.update.diagnosis.v1` 的陈旧说明。它不进入编译目录或生产执行，故不阻断 M4；
   M5 前宜删除该句，避免安装包文档误导使用者。
2. `ExperimentProposalIntent` 仍允许嵌入完整 `validation_plan`，而新设计 Agent 的上下文 validator
   强制使用紧凑 `validation_intent`。现有证据不足以证明已持久化/直接摄入的 typed intent 不需要前者，
   因此本审查没有把字段级猜测升级为 M4 必删项；若后续要删，应单独建立序列化消费者账本和负控，
   不应借 M4 顺手修改。

## 11. 最终判定

**PASS。** 两个 knowledge reducer 只有自循环而没有真实科学或产品消费者；删除它们比建立替代知识图
更小，并消除了控制/Transform 补造 `testable`、`unassessed`、空参数和合成理由的路径。诊断、
ValidationReport、不可变 Artifact/current、实验确定性物化与 TCAD 工程承重链保持；retained 20 个
Transform 对精确 M2 oracle 的可执行行为等价，9 个 guards 仍有真实正负例；插件、Root、Run 和数据
库没有新增复杂度。

**因此 M4 完成，仅放行 M5；R5-M 仍未完成。**
