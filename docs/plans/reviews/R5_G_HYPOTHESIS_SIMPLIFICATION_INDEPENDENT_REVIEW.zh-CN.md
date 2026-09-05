# R5-G 假设链简化独立审查

日期：2026-08-30  
审查角色：未参与本阶段实现的独立审查者  
审查结论：**通过**

本结论只放行按当前冻结合同继续执行 R5-G 的假设批评后实验设计；不代表实验结果、UI 可用性、R5-G 或 R5 整体已经通过。

## 1. 审查范围与方法

本轮按跨边界审查、变更范围检查和简化审查三套规则，检查了：

- 通用科学插件的假设提出、独立批评、证据资格和生产者评审合同；
- 曲线插件中的实验设计与确定性实验物化合同；
- Root 的生产者输出准入、Task 完成态和精确评审输出识别；
- R5-G 冻结清单、运行脚本、当前架构/实施计划和相关测试；
- 当前生产目录、动态入口和模型可见提示中的删除残留；
- 单一编译目录、组件所有权、父链、最小上下文和复杂度变化。

审查期间首次读取候选时，发现了一个正常修订路径可达的错绑：评审合同只证明批评者评审了精确假设组合，却不能证明其使用了生成该组合的同一科学基础。候选随后以最小方式增加不可见的 `scientific_foundation` 见证和既有 `RequiredParentage` 守卫。本报告结论基于该修复冻结后的当前字节重新作出，不沿用修复前观察。

## 2. 门禁结论

### 2.1 假设后不再默认重复证据审计：通过

证据审计应审查证据对象和来源，而不是在每个后续科学对象后重复读取同一原始来源。当前链路已经在假设提出前完成：来源冻结、证据提取、独立证据审计和人工科学基础资格。假设提出者只消费精确问题框架和已批准科学基础；批评者只消费精确假设组合和同一已批准科学基础。

批评提示与语义合同明确要求事实前提必须存在于已批准科学基础，推断必须显式；不支持的前提应回到已有证据提取、审计和资格修订路径，批评者不能自己重新审计来源或授予证据资格。因此，删除默认的假设后证据审计没有删除证据质量边界，而是消除了职责重复。出现新来源、新事实或基础变更时仍必须创建新的证据修订和新决定，不能沿用旧资格。

### 2.2 未通过假设不能进入实验：通过

该边界由互补而非重复的三层合同闭合：

1. 假设提出 Operation 的 `ReviewSpec` 唯一声明 `science.hypothesis.criticize.v1` 为独立评审者，评审输入端口为 `hypothesis_portfolio`，接受结论仅为 `pass`。编译器验证评审者是不同 Agent 实现、端口与 Schema 兼容，并把评审者身份纳入 Operation 摘要。
2. Root 的生产者输出准入只接受已完成 Task 的精确评审输出；它同时核对编译 Operation 身份、调度信号属于接受集合，以及评审任务的精确主题输入引用。缺失评审、评审另一组合或非 `pass` 结论均以 `input_independent_review_missing` 失败关闭。批评输出上下文验证器还要求每个假设恰好出现一次，并把任一 `fail`、`unknown` 或 `not_applicable` 维度确定性映射为非 `pass` handoff。
3. 实验设计新增一个对 Worker 不可见、且必须已批准的 `scientific_foundation` cohort 见证。无状态 `experiment_science_cohort` 守卫要求目标、假设组合和批评均直接绑定该同一基础，同时要求批评直接绑定该组合。实验物化再次检查意图、基础、目标、组合和批评的完整父关系。基础见证和批评只参与准入/谱系，不进入旧确定性物化函数。

Task 输出的父引用由控制面从精确任务输入确定性登记，所以这些守卫检查的是不可变 Artifact 身份，不依赖名称、文本相等或调度提示。修复后的 mixed-foundation 负例证明“旧组合 + 新基础批评”被拒绝，同 cohort 正例通过。该实现也没有把科学判断迁入控制层：各维度判断仍由独立批评 Agent 产生，控制层只核对完成态、结论和精确关系。

### 2.3 删除 `CandidateEligibility`：通过

旧对象把假设组合、批评和一次重复审计重新汇总为专属准入实体，并承担逐候选过滤。这与生产者 `ReviewSpec` 的唯一评审权威重叠，也让确定性控制层隐式选择可进入实验的候选。

删除后采用更清楚的组合级规则：只有组合中所有假设的三个批评维度全部通过，完整组合才可进入实验；否则修订原组合并重新独立批评。系统不再静默裁剪或排序候选，也没有丢失资格信号。对于需要比较多个仍成立机制的研究，实验设计 Agent仍可在完整已通过组合上设计最小区分实验；对于部分不合格组合，先修订比由控制面创建一个新的选择对象更可审查。

### 2.4 单一目录、轻控制面和奥卡姆原则：通过

- `science.hypothesis.audit.v1`、`science.candidate.eligibility.v1`、`CandidateEligibility` 及其专属 Schema/转换/组件已从生产源码、插件、部署、角色提示、脚本和动态入口删除；未发现兼容 facade 或第二发现入口。
- 当前保留引用只有删除防回潮断言、R5 当前决策说明和冻结历史结构证据，不是生产消费者。
- 新增内容只是一项既有 `RequiredParentage` 类型的无状态守卫和一个 handoff-only 见证端口；没有新增表、缓存、状态机、注册表、科学实体或 Operation。
- `general_science` 与 `curve_score` 仍经同一 `scidiscovery.plugins` 入口和同一 `CompiledCatalog` 组装；跨插件组件引用保持公开、单一所有者。
- 当前 clean-wheel 目录为 core 15、full 49、full+InGaAs 50 个 Operation；`operations` 包仍为 7 文件、2053 行，生产 Python 为 143 文件、60248 行。此次方向是删除两个 Operation 和一个专属实体，不是横向搬移复杂度。

该设计符合“控制面只验证身份、权限、完成态、准入和谱系；Agent 负责科学内容”的边界，也没有违反当前 33 项约束族中的单一权威、不可变谱系、最小上下文、独立评审、失败关闭和插件所有权要求。

## 3. 测试与可复核证据

所有命令均严格串行执行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

独立结果：

- `pytest -q tests/operations/test_general_transform_operations.py tests/operations/test_curve_score_operation_plugin.py tests/operations/test_r5_frozen_baselines.py tests/operations/test_r5_g_hypothesis_stage_runner.py`：30 项通过；
- `pytest -q tests/operations/test_general_science_plugin.py`：9 项通过；
- `pytest -q tests/operations/test_catalog_installed_entrypoint.py tests/operations/test_operation_invoke_installed.py`：9 项通过；
- `python scripts/r5_current_metrics.py`：成功复算上述目录和复杂度数据；
- 对 `src/`、`plugins/`、`deploy/`、`roles/`、`scripts/`、`AGENTS.md` 与入口配置执行删除符号搜索：无生产或模型可见残留；
- `git diff --check`：通过。

当前覆盖已经触及真实编译目录、真实 Root/Task/Worker 生命周期、通用独立评审失败关闭、批评 Worker 输出验证、实验设计/物化守卫、clean-wheel 端口清单和安装态统一调用入口。没有必要为本次删除重跑已由实现方完成的全 `tests/operations` 套件。

## 4. 非阻断改进项

当前测试通过“通用 Root 精确评审生命周期测试 + 当前真实编译守卫测试”组合覆盖假设到实验的边界，语义上已经充分。为降低以后修改通用 ReviewSpec 或曲线插件守卫时的组合回归风险，可补一个小型真实 Root 测试，直接覆盖同一科学基础的 `pass` critic 被实验设计接受，以及错误基础、另一组合和非 `pass` critic 被拒绝。该测试不应引入新的 fixture 插件、状态、Schema 或专属准入对象；它不是本轮放行阻断。

## 5. 最终结论

**通过。**

最新冻结候选已经解决复审中发现的 foundation cohort 错绑，删除重复审计和 `CandidateEligibility` 后没有形成科学选择或资格缺口。当前方案比旧链更短、更清楚，并保留了必要的证据审计、假设独立批评、实验计划独立审查以及精确失败关闭边界。

