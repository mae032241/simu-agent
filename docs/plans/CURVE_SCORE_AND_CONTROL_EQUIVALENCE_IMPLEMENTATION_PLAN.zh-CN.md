# Curve Score 与 Control Equivalence 实施计划

状态：P0-B/P0-C/P0-D代码完成；首次真实链路暴露“部分comparison spec冒充完整研究评分”的P0资格漏洞，现已增加ValidationPlan覆盖合同并回归验证（2026-08-12）。

本计划替代旧的 Fig.4 专用 scorer 计划。目标不是再开发一个 `Fig.4 scorer`，而是补齐两个
版本化、确定性、可由 Root transform 调用的通用工具：

1. **Curve Score plugin**：把 TCAD 原始结果解析与通用曲线比较组合成一个可部署插件产品；
2. **Control Equivalence**：自动支持单 package 多 case、多 package 单 case及无歧义混合拓扑，
   证明比较实验只改变了预注册允许改变的控制量。

两者都不是 Skill，也不由 diagnostician 临时计算。Skill只负责告诉diagnostician如何解释正式报告。

## 0. 本轮实施快照

| 能力 | 当前状态 | 已验证边界 |
| --- | --- | --- |
| 通用curve schema与算子内核 | 已实现 | finite/linear/log约束、固定均匀evaluation grid、RMS、max abs、signed mean、crossing、width、threshold和fail-closed availability |
| SProcess normalizer | 已实现v1 | 固定`SCID_CURVE_V1` grammar、exact series/count/index、64 MiB输入上限、截断/未知/重复/非有限拒绝 |
| Curve Score组合插件 | 已实现并加固 | 只从唯一的`ExperimentPortfolio.curve_comparison_spec`生成科学`metric_report`；每个阈值operator必须绑定`validation_check_key`并精确覆盖全部确定性计划检查；独立comparison只生成非科学standalone report |
| Control Equivalence | 已实现 | 单package多case、多package单case、混合覆盖、来源冲突、缺binding、locator唯一性、source-value一致性 |
| 普通单case | 已实现 | 生成realization snapshot并返回`not_applicable`，绝不伪造equivalence pass |
| diagnosis交接 | 已实现 | `scidiscovery.diagnosis.tcad-result.v1`只接收plan、runtime attestation、control report和metric report；禁止原始log重算 |
| 当前真实Fig.4执行资格 | 未完成 | execution与parser已跑通，但旧plan只配置了P0可表达的4项pairwise比较，未覆盖原计划全部mask/segment/refinement/curvature/direction/convolution检查；旧metric report不得继续用于科学闭环 |

本轮代码完成不等于科学闭环完成。若当前真实log不包含v1 grammar，优先新增与现有raw格式兼容的
normalizer；只有原始输出确实缺少case/series/单位或点边界时，才提出最小deck输出合同修订。

### 0.1 当前实例只读盘点（2026-08-12）

- 当前实例已有一次 collected 的 solver-only execution；控制面登记的 `solver_log` 为
  `text/plain`、1,902,529 bytes，同时登记了 `tcad_log` 与 `tcad_manifest`；
- exact solver-only project 与独立 reviewer 报告均已注册，reviewer 的正式 verdict 为 `pass`；
- Root scheduler按设计只能读取这些Artifact的清洗后元数据，不能绕过task/transform边界下载原始
  payload，因此这里没有人工打开log并宣称兼容；
- 新插件尚须通过安装/重启进入服务进程，随后用正式transform做compatibility probe；
- 该历史reviewed project生成于`CaseParameterBinding`合同引入前，是否已有足够的逐case locator必须
  由正式control-equivalence输出判定。缺binding时应返回inconclusive，不能从实验计划复制预期值
  冒充实际实现。
- 第一次正式Curve Score调用已证明历史log不含`SCID_CURVE_V1` completion records；为避免人工读取
  Artifact或盲目重跑TCAD，normalizer失败诊断现输出有界、去值的legacy候选行计数与字段布局。
  下一次安装后的probe将据此决定扩展兼容parser还是修改deck输出合同。
- 初版大小写敏感probe还报告“无`CASE/NODE`候选”，但这不足以区分小写/空格/键值格式和真正缺少
  曲线payload；第二版已增加大小写无关marker计数、声明case命中数、分隔符行计数及去值token布局，
  其结果才作为是否重跑的机器依据。
- 第二版真实probe确认四个目标case共有4,504条统一五字段逗号曲线记录（coarse各751点、fine各
  1,501点），并有4条目标`SOLVE_COMPLETED`/全日志21条完成记录；数据存在，无需重跑TCAD。
  normalizer已增加严格`legacy_case_csv_v1`分支，下一次安装后直接对原Artifact做资格评分。
- 首次legacy解析证明完成行的两个有限摘要字段不是点数/末索引；移除这一未经证据支持的过严假设。
  点数改由zero-based连续索引独立计数并对照source spec，完成行仍是必须的终止边界。
- 第二次legacy解析证明`SOLVE_COMPLETED`早于统一profile导出；它是solver完成而非series END。
  parser改为完整扫描后联合验证completion与points，仍要求两者同时存在。
- 第三次解析已完成CurveBundle构造前的全部legacy合同，但全6 um原始profile远端含零，而新增计划将
  整条raw y轴错误声明为`log10`。通用修复把原始浓度轴声明为`linear`，只在0–0.8 um比较域内执行
  `log10_y`插值与log10指标；域外零允许，域内非正仍明确unavailable，不加epsilon。
- 同一次真实调用暴露并已修复structured revision的前置验证缺口：旧门只检查JSON Pointer作用域，
  可让`{schema_version:1}`空壳patch完成worker lifecycle，虽然后续deterministic apply仍会拒绝。
  新门在worker finalization前将patch应用到exact `prior_draft`并验证完整目标schema。
- 首次端到端调用还暴露更关键的资格漏洞：`CurveComparisonSpec`的operator没有绑定
  `ValidationPlan.check_key`，组合插件也没有检查确定性计划项的完整覆盖，因此4项可计算P0指标被错误
  注册成研究级`metric_report`。修复后，带阈值operator必须一对一声明`validation_check_key`，其并集
  必须与计划中全部`deterministic_threshold`检查完全相等且阈值一致；缺少任一P1算子会在plan/spec
  验证阶段拒绝，而不是进入diagnosis。每项检查还固定evaluator profile和operator kind，禁止只复用
  check key却偷换metric。standalone comparison改为`curve_consistency_report`，无计划
  digest；readiness和diagnostician contextual validator都会拒绝把它当作研究级metric report。
- 同一链路中，旧reviewed package没有逐case realization binding，问题却直到执行后的Control
  Equivalence才变成inconclusive。修复后author/reviewer在拿到exact experiment plan时会交叉验证
  case controls；更关键的是`tcad.reviewed-deck-package.v2` transform强制接收exact
  `experiment_plan`，并在package生成前验证每个case-varying comparison variable逐case存在唯一、
  源码可定位且值/单位/科学路径与计划一致的binding。这样旧Artifact不能绕过新review继续执行。

## 1. 架构决策

### 1.1 科学职责

```text
reviewed experiment plan                 reviewed TCAD package(s)
          |                                         |
          |                              Control Equivalence
          |                                         |
authorized execution -> raw solver output -> Curve Score
                                                  |
                              curve report + control report
                                                  |
                                           diagnostician
```

| 层 | 负责 | 明确不负责 |
| --- | --- | --- |
| Deck | PDE、IC/BC、几何、材料、数值求解和原始solver-native输出 | mask、重采样、指标、阈值、科学结论 |
| Execution bridge | 执行生命周期、原始输出完整性、运行身份 | 曲线计算、控制等价性、物理解释 |
| Curve Score | 解析原始结果、生成规范曲线、执行预注册曲线算子 | 修改deck、机制归因、接受假设 |
| Control Equivalence | 物化实际case控制量并与comparison contract比较 | 曲线评分、PDE代码审查、科学解释 |
| Diagnostician | 联合解释runtime、curve与control报告 | 手算确定性指标、修订代码 |

### 1.2 插件边界

新增独立包 `plugins/curve_score`，通过现有
`scidiscovery.transform_adapters` entry point加载。PLX 格式适配与通用评分分层：

```text
scidiscovery.curve-normalize.sprocess-plx.v1
scidiscovery.curve-bundle.sprocess-plx.v1
scidiscovery.curve-consistency.v1
scidiscovery.curve-score.v1
```

SProcess 层只把一个或多个原生 PLX 转成独立注册的 `CurveBundle`；通用 scorer 再读取 bundle
执行预注册算子。solver log 只用于运行诊断。旧 `sprocess-log` profile 仅作历史兼容，不作为新研究
默认入口。不得只返回不可追溯的总分。

Control Equivalence继续位于 `plugins/tcad_artifact`，新增：

```text
tcad.control-equivalence.v1
```

## 2. 当前支持情况

### 2.1 可复用基础

- transform adapter发现、唯一profile选择和多输出Artifact注册已经存在；
- 旧 `plugins/ingaas_fig4` 已有PLX解析、有限性检查、log-domain插值、RMS、crossing、width和
  residual region实现，可提取纯数学函数和测试fixture；
- `ComparisonContract`、`RealizationSnapshot`、`ComparisonDifference`、
  `ControlEquivalenceReport`和`evaluate_control_equivalence`已经存在；
- `tcad.realization-snapshot-materialize.v1`已经能够从单case/global `ParameterBinding`生成snapshot；
- reviewed package、solver capability和runtime attestation已具备摘要与父链基础。

### 2.2 必须补齐的缺口

| 缺口 | 影响 | 优先级 |
| --- | --- | --- |
| 没有通用CurveBundle/ComparisonSpec/ScoreReport schema | 每个研究会重新发明输出结构 | P0 |
| 旧scorer把Fig.4身份、公式和文件格式写死 | 无法复用于Fig.7、其他TCAD或实验曲线 | P0 |
| 当前21-case SProcess log没有正式normalizer | 真实执行结果无法进入确定性分析 | P0 |
| 全局`ParameterBinding`不能表达同一deck内不同case的值 | 多casecontrol-equivalence可能错误复用同一个值 | P0 |
| 没有study级control-equivalence transform | readiness可能宣称能力存在，但Root无法调用 | P0 |
| 没有单case/多case统一来源解析 | 两种拓扑可能走不同逻辑、产生不一致报告 | P0 |
| diagnostician输入profile尚未强制两份报告 | 可能绕过确定性门直接解释结果 | P0 |

## 3. 功能一：Curve Score plugin

### 3.1 核心schema

在 `src/scidiscovery/artifact_agent/schema/curve_score.py` 新增严格schema。

#### `CurveBundle`

```text
schema_version
source_profile
source_digests
series[]
  series_key
  case_key
  role
  x_axis{name, unit, scale}
  y_axis{name, unit, scale}
  points[{x, y}]
  valid_intervals
  exclusions
  availability{status, reason_code}
  provenance
```

约束：

- `series_key`、`case_key`唯一且稳定；
- 点值有限，x严格递增，不静默排序、去重或补点；
- `log10`轴值必须严格为正；
- 单位显式，normalizer不能隐式猜单位；
- 大型点列只存在于bundle，不复制到primary报告。

#### `CurveComparisonSpec`

```text
spec_key
required_series
comparisons[]
  comparison_key
  reference_series
  candidate_series
  domain/mask
  interpolation
  operators[]
    validation_check_key
  thresholds[]
  availability_policy
aggregate_rules
```

它由experiment design预注册或严格引用。每个带阈值operator必须绑定一个
`validation_check_key`；组合入口只在这些key精确覆盖对应ValidationPlan全部确定性阈值检查且阈值
一致时生成研究级metric report。P0只允许枚举式算子和参数，不实现任意Python、表达式
求值或脚本执行。Fig.4中的H/L/B、A0 coarse/fine、alpha、Robin和erfc只是spec字段值，不进入
插件源代码。

#### `CurveConsistencyReport`

```text
curve_bundle_sha256
comparison_spec_sha256
normalizer_version
operator_version
checks[]
metrics[]
availability[]
aggregate_status
interpretation_boundary
```

每个metric必须包含operator、输入series、有效域、数值、单位、状态和reason code。报告只输出
`pass|fail|inconclusive|unavailable`，不输出hypothesis verdict。

### 3.2 SProcess结果normalizer

`scidiscovery.curve-normalize.sprocess-log.v1`负责：

1. 读取受64 MiB硬上限约束的原始log，并按行解析；当前Root transform API以`bytes`交付Artifact，
   因此真正的CAS streaming I/O属于P1，不在P0中虚假宣称；
2. 按冻结grammar识别case start/end、node index、depth、concentration和solve completion；
3. 对照source spec检查exact case inventory；
4. 拒绝未知case、重复case、截断、跨case混行、重复node、乱序depth、非有限值和单位缺失；
5. 输出canonical `CurveBundle`和bounded parser audit。

首个source spec针对当前solver-only SProcess日志，但normalizer接口不得包含`Fig.4`或材料专名。后续
PLX/CSV/TDR只增加normalizer profile，不改比较引擎。

### 3.3 通用比较算子

P0已实现当前首轮闭环可用且可复用的最小算子集：

- exact-domain selection与连续段coverage；
- linear/log-domain interpolation，禁止外推和跨gap插值；
- 固定均匀evaluation grid上的signed mean、RMS、max-absolute-error；
- level crossing与front width；

finite-difference slope、五点curvature、局部比值、paired refinement、跨多曲线direction聚合和
离散convolution仍是P1 operator扩展。P0可将解析/实验reference作为独立CurveBundle输入，并用上述
通用pairwise算子比较；不得声称尚未实现的复合算子已经可用。

mask、阈值、case配对和聚合规则全部来自`CurveComparisonSpec`。空mask、coverage不足和reference
缺失必须成为明确`unavailable`，禁止用0、NaN、epsilon、外推或其他case替代。

### 3.4 PLX bundle 与通用评分入口

`scidiscovery.curve-bundle.sprocess-plx.v1`输入：

- `runtime_attestation`；
- 内含唯一`curve_comparison_spec`的`experiment_plan`；
- 每条声明 solver series 一个 `solver_output__<series_key>` 原生 PLX。

输出 canonical `CurveBundle` 与逐 PLX 解析审计。每个 PLX 必须是 exact runtime attestation
的父输入；单 case 与多 case 使用同一协议。

`scidiscovery.curve-score.v1`输入：

- `curve_bundle`；
- `runtime_attestation`；
- `experiment_plan`；
- 可选`reference_curve__*` canonical CurveBundle。

执行顺序：

1. 验证输入schema、canonical bytes、大小和父链；
2. 验证CurveBundle精确覆盖计划声明的solver series；
3. 调用固定版本curve-consistency engine；
4. 输出：
   - `primary`：`scidiscovery.curve-consistency-report.v1`；
   - `curve_bundle`：`scidiscovery.curve-bundle.v1`；
   - `audit`：normalizer/operator审计。

同一输入和插件版本必须产生byte-identical canonical输出。插件不得访问网络、工作区随机文件或
未列入输入的Artifact。

### 3.4.1 论文图像证据 reference bundle

`scidiscovery.curve-bundle.figure-evidence.v1` 输入：

- `figure_manifest`；
- 控制面生成且直接绑定精确 manifest/CSV 的 `validation_report`；
- 含唯一 curve comparison spec 的 `experiment_plan`；
- manifest 中每条 series 一个 `curve_table__<panel_key>__<series_key>`；该 profile 不读取实验计划，输出完整 evidence library。

实验计划由 `experiment_designer` 依据 manifest/report 显式声明候选—reference 映射，并对证据库每条
series 写 `compare|exclude` disposition。`scidiscovery.curve-reference-coverage.v1` 在 TCAD 打包前
校验完整映射；控制面不选择科学目标。

转换器只按 manifest 轴标定把像素转成物理值，series/case/role/单位/点数边界来自实验计划。它不从
文件名、图例文字、颜色或 Fig.4 专用列名推断身份。manifest `unresolved`、binding 未匹配、零合格
行或合格点不足时，输出对应零点 `unavailable` series；哈希、父链、CSV 身份、轴或点序列损坏时
直接拒绝。该 bundle 随后只作为通用 `scidiscovery.curve-score.v1` 的 `reference_curve__*` 输入。

### 3.5 Fig.4迁移方式

- 保留`ingaas.fig4-baseline-recovery.v2`用于旧父链复算，不原地改变其语义；
- 把旧插件的数学函数迁移为通用operator测试，不复制Fig.4身份判断；
- 新增一份冻结`fig4-alpha-curve-comparison-spec.v1`作为首个真实配置；
- 先对当前已注册solver log运行compatibility probe；只有grammar确实缺失必要边界或单位时，才
  提出最小deck output-format revision与重跑，不能为了开发方便主动重跑TCAD。

## 4. 功能二：Control Equivalence

### 4.1 统一realization数据模型

在TCAD project schema中增加向后兼容字段：

```text
CaseParameterBinding
  case_key
  variable_key
  realized_value
  unit
  relative_path
  locator
  requirement_keys
```

唯一性为`(case_key, variable_key)`。locator必须存在于exact solver source并且可无歧义定位。
这是reviewed project元数据，不写入solver代码，也不承担后处理。

物化规则统一支持：

| 输入拓扑 | 物化规则 |
| --- | --- |
| 一个package包含多个case | 按`CaseParameterBinding.case_key`选择 |
| baseline/candidate各一个单case package | 每个package物化一个case后统一比较 |
| 多package、每个package包含若干case | 建立覆盖矩阵后按case选择唯一来源 |
| 真正只有一个case且无比较对象 | 只生成snapshot，不生成equivalence pass |

旧全局`ParameterBinding`兼容规则：

- 单case package可以直接使用；
- 多case package仅能将它用于合同中所有case预期完全相同的`frozen`变量；
- intended/permitted变量在不同case有不同预期时必须提供case级binding；
- 不得从`ExperimentCase.settings`复制预期值作为实际实现值。

### 4.2 自动case来源解析

`tcad.control-equivalence.v1`接受：

- `experiment_plan`；
- 一个或多个`reviewed_package__*`；
- 执行后可选/应必需的对应`runtime_attestation__*`。

聚合器先建立：

```text
case_key -> package_digest -> bindings -> source locators
```

规则：

- 每个合同case正好一个可用来源；
-相同canonical package重复输入可去重；
- 同一case出现两个不同package来源时拒绝为ambiguous；
- 缺case或缺binding生成`missing_realization/inconclusive`；
- 多case单package与单case多package若物化出的snapshots相同，报告必须byte-identical；
- 选择不能依赖输入顺序。

### 4.3 检查项

#### 合同结构

- baseline/comparison case完整且唯一；
- intended变量实际发生变化；
- frozen变量预期完全相同；
- permitted difference具有明确规则；
- exact/absolute-tolerance/reviewed规则与值类型一致；
- 每个变量覆盖exact compared cases。

#### 实现物化

- case、variable、scientific path、unit与合同一致；
- locator文件存在、定位唯一且绑定到reviewed source摘要；
- realized value可按合同类型严格解析；
- declared变量无缺失，额外实现变量被纳入snapshot；
- snapshot来源package、case binding和capability摘要完整。

#### 控制比较

- intended change符合每个case的预注册值；
- frozen invariant逐case相同且符合预注册值；
- permitted difference满足exact或absolute tolerance；
- 未声明但实际不同的变量为`unexpected_difference/fail`；
- `reviewed`规则没有变量级结构化receipt时保持`inconclusive`，不能继承全局deck-review pass。

#### 实现与运行身份

- solver kind、tool profile、capability digest；
- entrypoint、arguments、resource limits、raw expected outputs；
- solver文件归一化摘要；
- runtime attestation属于exact reviewed package；
- 实际执行capability没有漂移。

### 4.4 输出

新增`StudyControlEquivalenceReport`：

```text
experiment_reports[]
  experiment_key
  baseline_case_key
  comparison_case_keys
  realization_snapshot_refs
  differences[]
  status
overall_status
physical_claim_evaluable
```

transform输出：

- `primary`：study级报告；
- `snapshot__<case_key>`：规范化case snapshot；
- `audit`：coverage matrix、输入摘要、缺失/冲突来源。

状态严格派生：任一fail→fail；无fail但存在inconclusive→inconclusive；全部pass→pass。只有全部pass
才能设置`physical_claim_evaluable=true`。

## 5. 实施阶段

### P0-A：兼容性探测与合同冻结（部分完成）

任务：

- 用当前真实solver log验证case grammar、单位、记录边界和21-case completeness；
- 审计当前reviewed package是否已经足以物化case-specific controls；
- 固定三个curve schema和study control report schema；
- 固定输入大小、case数、series数、point数和输出大小边界。

完成门：给出机器可复核的compatibility report，明确当前执行能否直接复用；不得以人工判断代替。

### P0-B：实现Curve Score schema和纯函数内核（完成：最小P0算子集）

任务：

- 新增`schema/curve_score.py`；
- 实现CurveBundle验证、comparison spec验证和operator registry；
- 从旧Fig.4插件迁移纯数学函数并去除领域硬编码；
- 增加synthetic/golden/negative测试。

完成门：同一内核通过Fig.4配置和至少一个非Fig.4合成配置，证明没有图号/材料硬编码。

### P0-C：实现Curve Score插件（代码完成，真实输出资格待P0-E）

任务：

- 新建`plugins/curve_score`及entry point；
- 实现SProcess streaming normalizer、curve-consistency和组合profile；
- 增加输入父链、canonical output与边界测试；
- 更新安装探针，确保profile只由一个adapter提供。

完成门：Root可直接对当前注册的raw output生成CurveBundle和CurveConsistencyReport。

### P0-D：实现统一Control Equivalence（完成）

任务：

- 为project schema增加`CaseParameterBinding`；
- 扩展realization materializer的global/case-specific兼容规则；
- 实现package coverage resolver和study aggregate；
- 注册`tcad.control-equivalence.v1`；
- 修复readiness宣称能力但无adapter的假阳性。

完成门：当前多case package与合成的多package单case研究都能生成结构化报告，并通过同一evaluator。

### P0-E：真实闭环资格测试（未完成）

任务：

1. 对当前solver-only execution运行Curve Score；
2. 对exact experiment plan/reviewed package运行Control Equivalence；
3. 确认两份报告与runtime attestation处于同一不可变父链；
4. 仅在三项均有效后调度diagnostician；
5. diagnosis明确允许时才执行knowledge update。

完成门：至少完成一次
`reviewed package -> authorized execution -> runtime attestation -> curve report -> control report -> diagnosis`
真实链路，不接受mock或人工填数作为最终资格。

## 6. 测试矩阵

### 6.1 Curve Score

- 当前真实log的冻结fixture：exact case count、point count和canonical digest；
- 缺case、重复case、未知case、截断、乱序、重复node、非有限和单位缺失全部fail-closed；
- 空mask、短segment、coverage不足和reference缺失输出明确unavailable；
- P0的linear/log插值、signed mean、crossing、width、RMS和max-absolute使用解析解；
- P1再为curvature、convergence、direction aggregate和convolution增加解析解资格矩阵；
- comparison spec未知operator、未知series、单位不兼容和任意表达式输入必须拒绝；
- standalone normalize + compare与组合score输出一致；
- 输入顺序变化不改变canonical输出。

### 6.2 Control Equivalence

- 单package多case正常通过；
- baseline/candidate各一个package正常通过；
- 无歧义混合package产生同构snapshot；
- 同一case冲突来源拒绝且不依赖输入顺序；
- intended/frozen/permitted变量分别覆盖pass/fail；
- 缺case binding、缺locator、类型/单位不符为inconclusive或fail；
- 未声明变化、file digest、entrypoint、arguments和capability drift为fail；
- reviewed rule无变量级receipt为inconclusive；
- 真正单case无比较对象只生成snapshot；
- 多proposal aggregate稳定且byte-deterministic。

### 6.3 控制面集成

- 每个advertised deterministic capability解析到唯一adapter/profile；
- 动态多package输入均经过资格和父链检查；
- transform输出全部注册并可按semantic name绑定；
- 重启后同一请求幂等返回原结果；
- diagnostician缺任一报告时不可调度为科学解释任务。

## 7. 计划修改文件

| 路径 | 变更 |
| --- | --- |
| `src/scidiscovery/artifact_agent/schema/curve_score.py` | 新增通用曲线schema |
| `src/scidiscovery/artifact_agent/schema/comparison.py` | study aggregate与locator审计字段 |
| `src/scidiscovery/artifact_agent/schema/experiment.py` | 引用curve comparison spec所需合同字段 |
| `plugins/curve_score/` | 新增Curve Score插件、normalizer和operators |
| `plugins/tcad_artifact/tcad_artifact/project_packager.py` | case-specific binding schema |
| `plugins/tcad_artifact/tcad_artifact/transform_adapter.py` | coverage resolver、materializer和aggregate profile |
| `src/scidiscovery/scheduler_topology.py`、`schema/research_cycle.py`与`interfaces/mcp_root.py` | capability与输入资格一致性 |
| `tests/artifact_agent/` | schema、transform、拓扑、parentage与真实fixture回归 |
| `deploy/install.sh`及插件安装配置 | 安装Curve Score entry point并更新探针 |

## 8. 非目标

- 不把曲线后处理重新塞回SProcess/SDevice deck；
- 不让subagent或diagnostician手工填写metric和case值；
- 不实现任意用户表达式或在scorer中执行Python脚本；
- 不让Curve Score输出机制归因或hypothesis verdict；
- 不让Control Equivalence代替deck代码审查；
- 不删除旧Fig.4 scorer，旧父链继续使用原profile复算；
- 不因开发新插件而默认重跑已经完成的TCAD执行。

## 9. 最终验收标准

功能完成必须同时满足：

1. Curve Score对当前真实原始输出产生可复算的CurveBundle与CurveConsistencyReport；
2. 同一Curve Score内核通过非Fig.4合成配置；
3. Control Equivalence自动支持多case单package和单case多package；
4. 当前研究产生逐变量、逐locator、逐case可追溯的control report；
5. 所有结果由deterministic transform注册，无Agent手填数字；
6. diagnosis只能消费正式runtime、curve和control报告；
7. 完整真实科学链在服务重启后仍可按semantic names恢复和复核。
