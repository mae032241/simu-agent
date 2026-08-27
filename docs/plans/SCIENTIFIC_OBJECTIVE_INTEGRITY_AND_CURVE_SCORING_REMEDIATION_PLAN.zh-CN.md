# 科学目标完整性与曲线评分整改计划

状态：P0-A～P0-F 已实现并通过回归；P0-G 正在执行；P0-H 阈值门禁一致性已修复，
其余流程减负项按本计划分批实施
制定日期：2026-08-15
适用范围：SciDiscovery 通用科学闭环、论文曲线证据、实验设计、曲线评分、诊断、TCAD 打包与执行门禁

## 1. 本次事故结论

本次问题不是 PLX 解析错误，也不是粗细网格数据被篡改。已经完成的 provenance audit
证明：原始 PLX、canonical `CurveBundle` 和 metric report 的点值及摘要一致。

真正的问题是以下目标漂移链条在当前架构中全部合法：

```text
原始目标：复现/解释论文 Fig.4 曲线
  -> 论文证据整体 status=unresolved
  -> 所有论文 series 被 normalizer 一并降为 unavailable
  -> 实验计划把论文比较设成 optional/非必需
  -> 内部“粗网格 vs 细网格”成为唯一 required comparison
  -> 固定 x 的 log10 RMS 在尖锐前沿附近被一个点放大
  -> diagnosis 将整个 study 判为 invalid_study
  -> scheduler 又准备了只研究数值收敛的后续实验
```

其中每个局部组件都满足现有 schema，但组合后偏离了研究目标。因此这是
**科学意图完整性缺失**，不是单个 scorer 参数错误。

本次数据还说明，`A_only_P0_vs_refined` 的全域 log10 RMS 不适合判断该尖锐扩散前沿：

- RMS 为约 `0.37964 decade`，几乎全部误差集中在 `0.355–0.365 um`；
- 在 `x=0.365 um`，固定 x 的残差约 `4.817 decade`；
- 但多个浓度水平的前沿位置差仅约 `0.012–2.13 nm`，与 `1–2 nm` 网格尺度同量级；
- 两条曲线从约 `0.37 um` 起共同落到 `1e7 cm^-3` 数值底噪，后段残差恰为零，
  这只是共同 floor，不是有信息量的一致性；
- 论文候选曲线尾部约为 `1e16 cm^-3`，从未参与该内部比较，不能把细网格曲线称为
  论文“真值”。

## 2. 立即处置

在 P0 门禁完成前执行以下约束：

1. 不提交、不审批、不启动当前四 case 数值 follow-up execution；保留其对象用于审计，
   但不得将其解释为 Fig.4 科学闭环的下一阶段。
2. 保留现有 metric、diagnosis、provenance audit 和图像，不删除历史对象；将它们的有效
   作用域限定为“内部数值比较事故复现”。
3. 不再依据当前 `A_only_P0_vs_refined` 固定 x log RMS 修改物理机制或重跑生产 TCAD。
4. 不要求 deck author、deck reviewer 或 runner 修复本问题；它发生在证据—目标—计划—评分—
   诊断边界，不在 solver code 边界。

## 3. 整改原则

1. **目标先于计划。** 实验计划只能实现或细化已批准的研究目标，不能删除、降级或替换目标。
2. **控制面只验证，不选择科学对象。** 目标和比较意图由科学角色提出并经证据审查；控制面验证
   不可变父链、角色、覆盖率和禁止降级规则。
3. **内部对照不能冒充外部真值。** 数值收敛、机制区分和论文拟合必须是不同 comparison purpose。
4. **指标由比较形态和科学目的决定。** 不用一个 RMS 阈值覆盖单点、平滑曲线、尖锐前沿、峰形和
   分布等不同对象。
5. **证据按 series/区间定资格。** 一条模糊曲线不能使同图中身份明确的测量曲线整体失效。
6. **诊断分作用域。** 一个数值 gate 失败可以阻断候选资格，但不能自动改写原始研究目标或冒充
   外部拟合结论。
7. **保持职责边界。** deck 只生成 solver-native 原始结果；scorer 只给确定性值；diagnostician
   解释误差；deck reviewer 只审物理实现与显式代码逻辑 bug。

## 4. 目标数据流

整改后的最小链路为：

```text
approved ScientificFoundation + final evidence set
  -> ResearchObjectiveContract（科学内容，批准后不可降级）
  -> per-series/segment qualified reference library
  -> ExperimentPortfolio v2（声明 comparison purpose 和 series role）
  -> objective-coverage deterministic receipt
  -> deck author/reviewer
  -> package gate：objective coverage + reference coverage + reviewed deck
  -> execution
  -> raw CurveBundle
  -> purpose-aware deterministic scorer
  -> scoped diagnosis
  -> objective-scoped claim decision
```

数值收敛可以作为资格检查或独立 diagnostic study，但不能替代 `target_fit`。

## 5. P0-A：冻结事故样本并关闭继续扩散

### 实现

- 将本次 Fig.4 对象链固化为端到端回归 fixture：unresolved figure、optional paper
  comparisons、required coarse/refined RMS、局部残差尖峰、共同 `1e7` floor。
- 给现有数值 follow-up 对象增加只读的 superseded/limited-scope 投影；若现有 schema 无法表达，
  先由 Root readiness 将其列入 blocker，禁止创建 execution request。
- 修复 `worker_curve_analyze({})`：遇到 unavailable comparison 时不得进入空点 residual
  计算并抛出 `list index out of range`；应为每个 comparison 返回
  `available | unavailable | not_selected`，并继续分析其他可用失败项。

### 验收

- 精确事故 fixture 可稳定复现旧错误链。
- 同一 fixture 在新门禁下最晚于 experiment validation/package 前被拒绝。
- `worker_curve_analyze({})` 对 available 与 unavailable 混合输入不崩溃。
- 当前四 case follow-up 不可进入 execution authorization。

## 6. P0-B：引入不可降级的研究目标合同

### 新对象

新增 `scidiscovery.research-objective.v1`，其科学内容由 foundation/evidence 工作流产生，
控制面只验证和绑定。最小字段：

```text
objective_key
intent: external_reproduction | mechanism_discrimination |
        numerical_qualification | engineering
statement
mandatory_targets[]
  target_key
  observable
  evidence_subject / approved reference-library parent
  admissible_support: full_series | qualified_segments
closure_requirements[]
```

对论文复现实例，至少一项 mandatory target 必须绑定经最终 evidence approval 的外部测量曲线。
“论文证据当前 unavailable”是 blocker，不是把目标改为 optional 的依据。

### 生成与修订边界

- 新 foundation schema 显式包含 objective contract；旧 foundation 通过一次有界科学修订迁移，
  不能由控制面从自然语言猜测 target series。
- objective contract 改变 target、删除 target 或降低 closure requirement 时，必须形成新的
  foundation/evidence revision 与最终 evidence approval；普通 experiment-plan revision 无权修改。
- 新增确定性 `scidiscovery.objective-coverage.v1`：输入 exact objective、experiment plan 和
  reference libraries，输出每个 mandatory target 的比较映射、资格和缺口。

### 验收

- `external_reproduction` 没有外部 mandatory target 时 schema/transform 拒绝。
- plan 将 mandatory target 设为 optional、exclude 或删除时 coverage fail。
- 数值 reference 不能满足 experimental target。
- objective 内容变化必须产生新 revision 和新父链，旧对象保持可审计。

## 7. P0-C：重构 series role 与 comparison purpose

### Schema v2

不要继续用无语义的 `reference_series` 表达所有比较。新增受限枚举：

```text
CurveSeriesRole:
  experimental_target
  simulation_candidate
  numerical_reference
  numerical_variant
  analytic_control
  diagnostic_series

CurveComparisonPurpose:
  target_fit
  numerical_convergence
  mechanism_separation
  implementation_sanity
  exploratory_diagnostic
```

`CurveComparison.v2` 使用 `anchor_series + candidate_series + purpose + gate_scope`；
`required` 不再是可随意设置的孤立布尔值，而由 objective coverage 和 validation-plan gate 推导：

- `target_fit` 的 anchor 必须是 `experimental_target`，并匹配 objective mandatory target；
- `numerical_convergence` 必须是 `numerical_reference` 对 `numerical_variant`；
- `mechanism_separation` 比较两个明确的 simulation/control 角色；
- `exploratory_diagnostic` 永远不能单独满足 objective closure。

### UI 与审计

- UI 不再一律显示“reference/真值”；按 purpose 显示“实验目标”“细网格数值参考”
  “仿真候选”“解析控制”。
- diff 必须突出：purpose 变化、series role 变化、mandatory→optional、compare→exclude。
- v1 对象可读取和导出，但若角色无法无歧义迁移，只能作为 revision base，不能直接用于新的
  paper-reproduction execution。

### 验收

- 把 `A_only_refined` 声明为 experimental target 被拒绝。
- 数值收敛通过不能将 objective status 置为 achieved。
- 角色或 purpose 被 revision 偷换时 deterministic diff 和 UI 均可见。
- 控制面不根据 series 名、颜色、文件名或数据形状猜测 role。

## 8. P0-D：证据改为按 series 和区间定资格

### 当前缺陷

`figure_evidence_normalizer._unavailability_reason()` 先检查全局
`manifest.status != qualified`，因此任意 ambiguity 会让所有 series unavailable。当前 Fig.4 中
共享 `D∝C` 分支身份不明确，连带使图例已明确的 measured InGaAs 曲线也无法作为目标。

### 实现

- 发布 `figure-evidence-manifest.v2`：保留 figure 级汇总状态，但资格判定落到
  `(panel_key, series_key, interval)`。
- 每条 series 记录 identity status、observed intervals、occluded/gap intervals、row eligibility、
  uncertainty 和 reason code。
- ambiguity 只影响其引用的 series/interval；图中其他 matched series 不受牵连。
- measured curve 的可见连续段可 qualified；D∝C material identity 继续 unresolved；不跨遮挡段插值。
- 更新 `scientific-paper-evidence` skill、validator 和
  `scidiscovery.curve-bundle.figure-evidence.v2`，使 normalizer 按 series/segment 输出
  `valid_intervals`/`exclusions`，而不是全局清空 points。
- PNG 使用原始点显示离散采样和 gaps，不用连线制造不存在的连续证据。

### 验收

- 同一 manifest 可同时包含 qualified measured series 与 unresolved fitted branch。
- ambiguity 不会污染无关 series。
- gap、occlusion、零值、重复 x 均保留并可视化；不补点、不排序、不 epsilon 化。
- objective target 所需区间不足时为 unavailable/inconclusive，而不是伪造 pass/fail。

## 9. P0-E：目的感知的通用曲线评分

### 分层职责

```text
deterministic curve analyzer
  -> 只计算 support、形态、残差分布、crossing、floor/seam/gap 和 PNG

experiment designer / diagnostician
  -> 基于科学目的选择预注册 metric profile、阈值和解释

deterministic scorer
  -> 执行已注册公式与阈值，不选择目标、不填科学理由
```

### 最小 metric profiles

不建设庞大 DSL，只提供少量稳定模板：

| profile | 适用对象 | 主要确定性输出 |
| --- | --- | --- |
| `point.v1` | 单点/少量标量 | absolute、relative、uncertainty-normalized error |
| `smooth-curve.v1` | 平滑连续曲线 | linear/log RMS、max、signed bias、coverage |
| `sharp-front.v1` | 陡峭扩散前沿 | 多 level crossing shift、front width shift、非前沿幅值误差 |
| `peak-curve.v1` | 单峰/多峰 | peak position/height/width 与区间 residual |
| `curve-geometry.v1` | 轴向错位显著的曲线 | uncertainty-normalized symmetric curve distance |
| `distribution.v1` | 归一化分布 | integral/quantile/distribution distance |

profile 由 agent 在计划中选择，控制面只校验 operator 与 profile 兼容。对于
`sharp-front.v1`，禁止把全域固定 x log RMS 作为唯一 claim gate；至少需要 crossing/width，
并把 transition band、网格间距和参考数字化不确定度显式纳入 tolerance。

### Support 和分段

- log 曲线的精确零区必须显示，但从 log 数值误差中 mask；报告 zero-only/both-zero support。
- 声明的 solver floor 必须显示为 censored/floor support，不能因为两曲线共同 floor 而计作有信息量
  的零误差。自动 floor detection 只能给 diagnostician 一个候选，不得静默改变评分 mask。
- 重复 x 接缝保持原始顺序、标注 seam mask，不删除；接缝本身不触发 fail。
- gaps/occlusions 不插值。
- 分段继续采用自适应 residual/support change point，不固定八段；输出每段误差贡献、符号、support
  和 exact x 范围。
- PNG 同时显示两条原曲线、残差、transition/floor/zero/seam/gap masks、comparison purpose 和
  series roles；返回并持久化可携带的 plot item 名称。

### 当前 Fig.4 的正确比较方式

- `A_only_P0 vs A_only_refined`：`purpose=numerical_convergence`，优先
  `sharp-front.v1`，报告多个浓度水平的 crossing shift 和 front width；共同 `1e7` floor 不计入
  通过证据。
- `solver candidate vs measured InGaAs`：`purpose=target_fit`，以 evidence 的 qualified
  visible segments 为 anchor；其结果与数值收敛分别汇总。
- 如果 measured segment 仍 unavailable，objective 状态应为 blocked/unavailable，不能退化为
  内部曲线 pass 或 fail。

### 验收

- 当前粗细网格 fixture 能同时报告“大 fixed-x log residual”和“纳米级 front shift”，诊断所见事实
  完整但不再被错误单指标归并。
- 共同 floor 区显示在报告和 PNG 中，但不贡献 informative agreement。
- point、smooth、front 三种 profile 至少各有独立正反例。
- 同一输入与 profile 得到 byte-identical report/PNG；agent 篡改数值时 final validation 拒绝。

## 10. P0-F：readiness、package、execution 和 diagnosis 门禁

### ScientificReadiness v2

增加：

```text
objective_status: satisfied | evaluable | blocked | unavailable
mandatory_target_gaps[]
objective_coverage_receipt
subordinate_gate_statuses[]
```

能力排序先展示原始 objective blocker，再展示数值诊断建议。内部 gate 失败可以建议
`numerical_diagnostic`，但不得把它显示成“研究闭环下一阶段”或自动覆盖 target fit。

### Package / execution

- `tcad.reviewed-deck-package.v2` 对 scientific external-reproduction study 必须同时绑定：
  exact objective、exact plan、passing objective coverage、passing reference coverage、reviewed deck。
- coverage unavailable 时可以保存计划和 deck，但不能创建代表 objective closure 的 execution。
  若确需执行纯数值诊断，必须创建明确的 `numerical_qualification` objective/revision，不能暗中复用
  paper-reproduction 名称和 claim scope。
- execution approval UI 展示 objective、comparison purposes、mandatory target coverage 和所有被排除
  的 evidence series。

### Scoped diagnosis

扩展 diagnosis/claim projection，至少区分：

```text
objective_assessment
numerical_qualification_assessment
mechanism_assessments[]
comparison_assessments[]
```

`invalid_study` 必须指出 invalid 的 scope。只有 objective-scoped、父链完整的 assessment 才能更新
objective claim；数值 gate 失败不能自动生成“论文不符合”结论。

### Reviewer 边界

- deck reviewer 继续只审 manifest 所声明物理实现与显式代码逻辑 bug。
- 不把 objective coverage 或 metric 选择责任转嫁给 deck reviewer。
- objective/plan 一致性由实验设计输出加确定性 coverage gate 在 author 前检查；避免 author/reviewer
  花费时间实现一个已经偏离目标的局部合法计划。

### 验收

- 缺失 mandatory paper target 时 author 可以被阻断在调度前，至少 package/execution 必须拒绝。
- numerical convergence 报告不能满足 external reproduction objective。
- approval UI 明确显示目标缺口和 required→optional 漂移。
- deck review 测试继续证明其没有承担 scorer、诊断或目标裁决职责。

## 11. P0-G：迁移、回归与 Fig.4 恢复

### 迁移策略

- v1 Artifact 永久只读，不原地重释。
- v1 plan 若用于新的 external-reproduction execution，必须经 bounded revision 生成 v2 plan 和
  passing objective coverage；禁止按 series 名启发式迁移 role/purpose。
- 旧 metric/diagnosis 保留原摘要，但 UI 标记 legacy comparison semantics，不能作为新 objective
  claim 的当前报告。

### 必测端到端矩阵

1. paper objective + unresolved target + plan optional target：拒绝。
2. plan 删除 target、改 exclude 或把 refined numerical curve 伪装成 target：拒绝。
3. internal convergence fail 不会替代 target fit，也不会改写 objective。
4. mixed available/unavailable comparisons 调用 `worker_curve_analyze({})` 不崩溃。
5. sharp-front fixture：固定 x RMS 很大但 crossing shift 在网格容差内，两个事实同时保留。
6. 共同 `1e7` floor 可视化、被标注、不给予 informative zero-error credit。
7. measured series 可按 visible segment qualified，同时 D∝C ambiguous branch unresolved。
8. repeated x、zero、gap、occlusion 均不删除、不伪造 fail。
9. package、execution、readiness、approval UI 对 objective coverage 给出一致结果。
10. 角色/purpose/requiredness revision drift 在 deterministic diff 中可见。

### Fig.4 恢复顺序

P0-A～P0-F 通过后，才恢复当前科学闭环：

1. 用 evidence v2 重新资格化 measured InGaAs 的可见区间，D∝C 未决身份继续 unresolved。
2. 将已批准 Fig.4 foundation 有界修订为带 mandatory target 的 objective contract，并完成最终证据审查。
3. 修订 experiment plan：保留数值收敛 gate，但恢复独立、必需的 `target_fit` comparison；
   使用 `sharp-front`/合适的通用 profile，不把固定 x RMS 当唯一判据。
4. 生成 objective coverage 与 reference coverage。
5. 优先复用已有五 case 原始 PLX 做重新评分和诊断；只有诊断给出新的物理或数值需求时才重跑 TCAD。
6. 一次端到端闭环必须同时报告 target-fit、numerical qualification 和 mechanism assessment，且作用域清晰。

## 12. 代码改动位置

| 模块 | 主要文件 |
| --- | --- |
| objective schema/claim scope | `src/scidiscovery/artifact_agent/schema/scientific_objective.py`、`scientific_foundation.py`、`research_cycle.py`、`layered_diagnosis.py` |
| experiment/curve schema v2 | `src/scidiscovery/artifact_agent/schema/experiment.py`、`curve_score.py` |
| evidence per-series qualification | `src/scidiscovery/artifact_agent/schema/figure_evidence.py`、`plugins/curve_score/curve_score/figure_evidence_normalizer.py`、`scientific-paper-evidence` skill/validator |
| scorer/analyzer | `plugins/curve_score/curve_score/transform_adapter.py`、`src/scidiscovery/artifact_agent/schema/curve_analysis.py`、`interfaces/mcp_worker.py` |
| readiness/gates | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、`src/scidiscovery/scheduler_topology.py`、`plugins/tcad_artifact/tcad_artifact/transform_adapter.py`、`project_packager.py` |
| role contracts | `src/scidiscovery/platforms/roles/experiment_designer.md`、`diagnostician.md`、共享调度提示 |
| UI | approval/readiness renderer、plan diff renderer、curve plot renderer |
| tests | `test_experiment_portfolio.py`、`test_curve_score_schema.py`、`test_curve_score_plugin.py`、`test_curve_analysis.py`、`test_figure_evidence_*`、`test_dynamic_readiness.py`、`test_approval_ui.py`、scientific-loop E2E |

路径以实施时仓库现状为准；若角色模板位置不同，先定位权威文件，不复制第二份规则。

## 13. 实施顺序与完成门槛

```text
P0-A 事故冻结/停止扩散
  -> P0-B objective contract
  -> P0-C purpose/role schema
  -> P0-D per-series evidence
  -> P0-E purpose-aware scorer/analyzer
  -> P0-F readiness/package/execution/diagnosis gates
  -> P0-G migration + Fig.4 end-to-end qualification
```

P0-B/C 可并行设计，但合并时必须由同一组 incident tests 验证。P0-D/E 可并行实现，P0-F 必须消费
它们的最终 schema，不允许先用字符串或临时布尔值搭旁路。

本计划完成的判据不是“新增字段已存在”，而是：

1. 旧事故链在 author 前或最晚 package 前确定性失败；
2. 无任何内部 numerical comparison 能被解释成论文真值；
3. Fig.4 measured target 与 coarse/refined numerical reference 在 UI、report 和 diagnosis 中明确区分；
4. 旧五 case 原始输出可在不重跑 solver 的前提下得到新的 purpose-aware report；
5. 完成一次带 objective-scoped claim 的真实 Fig.4 科学闭环；
6. 全仓单元、集成、安装探针和真实纵向资格测试通过。

## 14. 非目标

P0 不做以下事情：

- 不把 scorer 或论文目标逻辑重新塞回 deck；
- 不让 deck reviewer 审核实验计划的科学目标；
- 不让控制面根据名字、颜色或数值自动选择论文真值；
- 不把 agent 的科学判断替换成一个万能自动 metric；
- 不跨 evidence gaps 插值，不删除 zero/repeated-x 观测；
- 不删除历史 subagent、plan、metric、diagnosis 或 execution 对象；
- 不先重跑四 case 来掩盖架构缺口。

一句话验收原则：**系统必须证明“正在评分的对象就是批准的研究目标”，再讨论这个分数是否通过。**

## 15. 2026-08-15 实施记录

### 已完成

- 修复混合 available/unavailable comparison 的曲线分析崩溃；不可用项现在返回有界状态，
  不再对空残差集合取索引。
- 新增不可降级的 `ResearchObjectiveContract`、确定性 objective coverage/readiness 投影，
  并将 external reproduction 的 mandatory target 绑定到 foundation、plan、package 和 diagnosis
  父链。
- 为曲线 series/comparison 增加显式 scientific role、purpose、gate scope 和 metric profile；
  `target_fit`、`numerical_convergence` 与 mechanism/diagnostic 比较不能相互冒充。
- 发布 `scidiscovery.curve-bundle.figure-evidence.v2`：历史 v1 保留 figure-global 语义，v2
  按 exact series identity 和 CSV 行资格独立判定；所有可见点保留用于审计，连续合格行段投影为
  `valid_intervals`，断裂段不能被静默插值。现有 v1 manifest 可作为不可变输入经 v2 normalizer
  迁移，不原地重释。
- 曲线评分支持 point、smooth-curve 和 sharp-front 目的感知约束；zero/floor/repeated-x seam
  保持可见并从不适用的数值误差中 mask。尖锐前沿的固定 x 全域 RMS 不能作为唯一 claim gate。
- readiness、scheduler、TCAD package、execution approval UI 和 scoped diagnosis 已消费 objective
  coverage；内部数值失败只能影响 numerical qualification，不能自动改写论文拟合目标。
- experiment designer 与 diagnostician 提示词已明确：数值参考不是论文真值；deck author/reviewer
  不承担 objective 选择、scoring 或科学裁决。

### 自动化验证

- `python -m compileall -q src plugins/curve_score plugins/tcad_artifact`：通过。
- `scientific-paper-evidence` skill quick validation：通过。
- `git diff --check`：通过。
- `pytest -q tests/artifact_agent`：`641 passed`；仅保留 6 条既有
  `datetime.utcnow()` 弃用警告。

### 尚未完成（P0-G）

- 现有 Fig.4 foundation/evidence/plan 仍是历史对象，不会被控制面自动猜测或原地升级。
- 需要在重新安装并重启服务后，按第 11 节顺序完成 foundation 有界修订、evidence v2
  normalization、purpose-aware plan revision、objective/reference coverage、旧 PLX 重评分与
  objective-scoped diagnosis。
- 优先复用已注册的五 case 原始 PLX；只有新诊断明确提出 solver 需求时才重新执行 TCAD。
- 完成上述迁移和一次真实 objective-scoped Fig.4 纵向闭环后，才能把本计划标为全部完成。

## 16. 2026-08-16 实验目标—设计目标一致性加固

本轮复审确认，禁止 `convergence` case 直接充当 `target_fit` 只能挡住一个具体症状，仍不足以
保证一般性的目标一致性。控制层现增加以下确定性门禁：

- `changed_factors`、每个 case 的完整 settings、intended comparison expectations 必须在类型、
  单位和值上形成同一张精确控制表；agent 不能用一份“看起来不变”的 expectation 隐藏实际
  mesh、时间步、物理或实现设置变化。
- scientific experiment design 必须同时绑定 exact `research_objective`、输入 hypothesis portfolio
  和机器生成的 candidate eligibility；selected hypothesis 必须真实存在且为 eligible。
- 每个 scientific portfolio 都必须声明 objective key，不再只对含外部曲线的计划生效；TCAD
  package 一律要求 exact passing objective coverage。engineering 单 case 仍保持豁免。
- closure requirement 具有 `target_coverage`、`comparison_present` 或
  `validation_check_present` 的可判定类型，并逐项进入 objective coverage；自然语言描述不再
  单独关闭目标。
- readiness 同时出现多个当前 experiment plan 时 fail closed。同一 semantic logical name 的
  历史 revision 仍由现有 binding 层自动排除，只保留最新 revision；不同 logical name 的竞争
  当前计划不能被静默挑选。

职责边界不变：experiment designer 仍决定科学假设、case 与比较目的；控制层只验证这些声明
彼此一致并绑定批准目标；deck reviewer 仍只审查物理实现和显式代码逻辑，不承担计划裁决。

## 17. 2026-08-16 无证据阈值与实验设计吞吐审计（P0-H）

### 17.1 事故与根因

目标一致性修复后，Fig.4 实验设计正确地保留了 required `target_fit`，并因论文没有给出
absolute fit tolerance 而把 crossing/width operator 保持为无阈值。实际运行暴露出四层不一致：

1. `CurveComparison` 已允许 objective target fit 无阈值；
2. `ExperimentPortfolio.curve_validation_check_keys()` 仍要求每个 required comparison 必须绑定
   thresholded deterministic check；
3. curve-score adapter 要求 deterministic evaluator profile 集合必须非空；
4. complete-plan metric report 与 Root coverage helper 也要求 covered check keys 非空。

这会强迫 agent 在“编造论文容差”和“永远无法通过 schema”之间二选一。正确语义是：

- required 表示比较不得被删除，不等于已存在自动 pass/fail 阈值；
- `gate_scope=numerical_qualification` 的 required comparison 必须绑定阈值；
- objective target fit 在无证据容差时可无阈值，scorer 仍计算指标并返回 `inconclusive`；
- validation plan 可以只有 reviewed checks。此时 complete-plan report 以 plan digest 和空的 exact
  deterministic-check 集合证明完整覆盖，不能伪装为 `pass`。

### 17.2 本轮已完成的 P0 修复

- 统一 required threshold gate：只有 required `numerical_qualification` comparison 强制
  threshold/check binding；target fit、mechanism 和 diagnostic 不再被错误套用该门禁。
- `curve_validation_check_keys()` 接受空 deterministic-check 集合，同时继续要求非空集合时一一
  精确覆盖、profile/operator/threshold/unit 完全一致。
- curve-score adapter 接受空 evaluator-profile 集合；若集合非空，仍必须全部匹配所调用 profile。
- `CurveConsistencyReport` 和 Root complete-plan coverage 接受空 covered keys，但必须有 exact plan
  digest；结果保持 `inconclusive`，不会成为自动科学通过。
- 回归覆盖：无阈值 sharp-front objective + 有阈值 numerical gate；无阈值 objective + 纯 reviewed
  validation；required numerical comparison 无阈值仍拒绝；complete-plan 空 check 集合可重算且
  coverage 成立。

### 17.3 全局审计发现并已关闭的流程缺陷

#### H1（P0，agent 机械负担）：compact intent 仍不够 compact

`ExperimentDesignIntent` 目前仍要求 agent 手写完整 `CurveComparisonSpec` 和 `ValidationPlan`。
v7 的 15 次 validation rejection 中，大部分来自可确定性生成的字段：series role 重复、线性
level 被序列化为整数、`value_space`、check key、evaluator profile、threshold unit 和绑定关系。

已修复：新增更小的 comparison/validation intent，只保留科学选择（目标 identity、candidate case、
purpose、domain、operator、可选 evidence-backed threshold 及 provenance）。控制层从 case、raw output
声明和 profile registry 确定性生成 series declarations、唯一 check keys、evaluator fields 和完整
ValidationPlan。materializer 输出 diff/report；控制层不得选择 target、purpose 或阈值。

验收：同一 Fig.4 intent 首次写入小于 32 KiB；agent 不再填写 evaluator profile/check key；完整
plan 仍逐字段严格；目标 identity 或 purpose 改变必须体现在 agent intent 和 deterministic diff 中。

#### H2（P0，文件协议）：JSON 修改没有路径级原子操作

当前 worker 只有文本 `worker_file_apply_patch`。它适合 solver 源码，但修改嵌套 JSON 时依赖易重复
的文本上下文。v7 记录了 8 次 patch rejection；一次 block 删除还制造了 trailing comma。现有协议
没有已经承诺过的路径级 JSON set/remove/test 能力。

已修复：增加 task-bound `worker_file_json_patch`，接受有界 RFC-6902 子集 `test/add/replace/remove`；
以当前文件 SHA 或逐 operation `test` 作为 CAS 前提；一次调用内 parse、apply、schema-independent
JSON serialize、大小检查和 `os.replace` 原子提交。禁止 move/copy、数组通配符和整文件 root replace。
文本/solver 文件继续使用原生 Codex patch。

验收：科学计数法数值语义不因 JSON round-trip 变成 strict integer；任一 test/path 失败时零字节
变化并返回 exact pointer/current value；10 个离散字段更新一次提交；并发陈旧 patch fail closed。

#### H3（P1，任务吞吐）：首次持久化门与角色/模型不匹配

同一 62,229-byte 输入上，默认 worker 两个 attempt 均在 300 s 内只有 heartbeat、零写入；
`sol medium` 在约 3 min 内完成首次写入。当前 gate 还把任意字节写入视为 progress，既可能误杀
慢但有效的设计，也可被无效 JSON 轻易绕过。

已修复：按本轮实测把 experiment designer 首次可解析 checkpoint 门从 300 s 校准到 420 s；
普通字节写入不再续租，只有可解析 `output/result.json` 才关闭首进度门。超时诊断区分
`no_persisted_bytes` 与 `unparseable_checkpoint`；schema 是否前进继续由 validation rejection
统计，不用无效 JSON 冒充进度，也不放开完整 900 s 绝对预算。

#### H4（P1，验证反馈）：错误串行暴露且存在 cascade 噪声

嵌套 proposal 失败后，Pydantic 会再报 proposals `too_short`；worker 往往一次只看到一个可行动
错误并连续重验。已修复：控制层对同一完整候选返回所有非派生 leaf errors，抑制由父节点丢失
产生的 cascade；每项提供稳定 reason code、JSON pointer、expected contract 和是否可机械修复。

#### H5（P1，多 proposal 语义）：设计层允许多个 proposal，scorer/reference coverage 只接受一个 spec

当前 intent 最多 16 个 proposal，但 curve-score、curve analysis 和 TCAD reference coverage 都要求
exactly one curve comparison spec。这可以支持“一个 proposal 内多 case”，却会让“多个各自有
curve spec 的 proposal”在执行后晚失败。

已修复：alpha 期在 intent 与 complete portfolio schema 同时限制最多一个 executable curve
comparison spec；仍允许多个不含 curve spec 的 proposal。这样 scorer/coverage 的单-spec 合同
在设计期即显式成立，不再执行后晚拒绝。

### 17.4 P0-H 验收矩阵与实施顺序

```text
H0 threshold gate consistency（完成）
  -> H1 compact comparison/validation intent（完成）
  -> H2 atomic JSON patch（完成）
  -> H3 calibrated progress gate（完成）
  -> H4 aggregated actionable validation（完成）
  -> H5 explicit multi-proposal policy（完成）
  -> 重派 Fig.4 intent，materialize complete plan，生成 objective/reference coverage
```

必须保留的反例：

1. target fit 无证据阈值：合法、required、scorer 输出指标和 `inconclusive`；
2. numerical qualification 无阈值：schema 拒绝；
3. deterministic check 与 operator/profile/unit 不一致：schema/transform 拒绝；
4. empty deterministic checks 的 complete-plan report：exact digest + empty keys 合法，standalone 不得
   声称 coverage；
5. coarse/refined numerical series 不能成为 experimental target；
6. 无阈值 target 指标不得被 objective/diagnosis 投影成自动 `pass`。

### 17.5 全局流程复核结论

本轮同时复核 intent 输出、materializer、complete portfolio、reference coverage、curve-score、
curve analysis、worker 文件生命周期、任务租约、安装探针和角色提示词，结论如下：

- 新 experiment-designer task 的 context validator 明确拒绝 legacy 完整
  `ValidationPlan`/`CurveComparisonSpec`；旧模型只保留给历史对象读取和确定性 transform，不能再
  由新 worker 选作省事路径。
- intent 与 complete portfolio 都在执行前限制最多一个 executable curve spec；scorer、coverage
  和 analysis 的单-spec 假设已经前移为同一显式 invariant。多 proposal 仍可用于不含曲线评分的
  判别设计。
- JSON 路径 patch 已进入公共 worker tool、assignment 写协议、Codex/Claude tool allowlist 和安装
  探针；installer 的 worker tool 数量同步更新，避免“源码有工具、安装后未暴露”的漂移。
- 首进度只由可解析 JSON 关闭，invalid/minified partial bytes 与 heartbeat 均不能伪造完成；绝对
  900 s 上限和 final validation/finalization 仍保持不变。
- validation diagnostics 仅压缩同一完整 Pydantic validation pass 中的派生父级错误；科学跨字段
  validator 仍保持 fail closed，不由控制层自动修改 target、purpose、operator 或 threshold。

因此本轮没有发现新的 P0 目标偏移路径。后续重新派发 Fig.4 时，预期 worker 输出的是小于
32 KiB 的 compact intent，随后由 transform 生成 complete plan；若仍失败，应按新的 leaf
reason code 定位具体科学声明，而不是再手工维护 evaluator/check/role 字段。
