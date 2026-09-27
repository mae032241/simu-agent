# R5 端到端前最小范围独立审查

日期：2026-09-04  
审查对象：`docs/plans/R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md` 第三版  
审查口径：真实 Fig.4 科学闭环前的必要修改、奥卡姆剃刀、设计宪章与 33 项约束  
结论：**PASS**  
阻断项：**0**

## 1. 总体判断

第三版已经把范围收敛到当前 Fig.4 闭环确实无法绕过的四项图证据缺陷、一项承重的
preflight/invoke 等价缺陷和一项安装组合修改。审批页面重做、projector 精细诊断、部署协议再开发、
强隔离和通用 Agent 集合输出均已明确移出实现范围。

五个 Operation 不是为了形式完整而拆分出的五层控制面；它们对应三个不能互相替代的边界：

```text
Agent 科学选择请求
→ Transform 确定性物化
→ Agent 形成 ScientificIntake
→ 独立 Agent 审查整个证据族
→ Transform 在审查通过后生成既有 CurveBundle
```

在当前 Run v1、review graph、通用 Intake 资格合同和曲线评分输入均保持不变的前提下，这已经是最小
可组合拓扑。进一步合并会让确定性程序承担科学判断、让生产者审核自己、让未审查曲线进入标准包，
或者迫使核心增加 Agent collection 协议。

本结论只放行第三版计划的最小范围，不证明五个 Operation 已实现，也不放行完整端到端实验。实施仍
必须按 E0—E6 逐段验收和独立审查。

## 2. 六项开跑前工作是否真实必要

| 项目 | 判定 | 最小性依据 |
|---|---|---|
| `FIGURE-RUN-001` | 必须修 | 旧提取 Agent 声明一个主结果和五组集合输出（`plugins/curve_score/curve_score/figure_science_operations.py:316-365,438-464`），而 `LocalTrustedBackend.unsupported_requirements` 明确拒绝任何 Agent collection output（`src/scidiscovery/artifact_agent/service/local_workspace.py:97-109`）。保持核心 Run 不变、把机械集合改由 Transform 产生，比实现通用集合生命周期更小。 |
| `FIGURE-CONTRACT-001` | 必须修 | 当前 `figure_request` 端口是 `opaque`（`figure_science_operations.py:448-450`），实际字段藏在 `FigureDigitizationRequest`（`figure_digitization.py:38-74`），且目录没有请求生产 Operation。调度器不能制造轴标定、身份锚点和遮挡等科学字段；一个单输出请求 Agent 和同源 JSON Schema 是最小闭合。 |
| `FIGURE-SOURCE-001` | 必须修 | 当前数字化函数只接受有界栅格（`figure_digitization.py:101-120`），真实实例来源是 PDF。历史资格又证明该论文应按 PDF 页和 embedded image object 恢复并绑定哈希，而不能使用来源不明截图（`docs/SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md:21-37,77-79`）。窄 PDF 检查工具加同一步骤的 Transform 重放是所需最小来源链。 |
| `FIGURE-FIDELITY-001` | 必须修 | 当前实现逐列颜色匹配、同列不连续即异常、支持不足整序列失败，并把成功点全部标为 eligible（`figure_digitization.py:123-169,172-207`）；manifest 又固定 `matched/qualified`（同文件第 268—337 行）。这与真实 Fig.4 的红线可用、黑线因遮挡保持 unresolved 的冻结边界冲突，入口接通但科学含义错误不能算闭环。 |
| `PREFLIGHT-PROJECTOR-001` | 必须修，但只能修一处 | Approval 的 preflight 当前不执行 projector，而 invoke 才执行（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:168-220,326-380`）。这违反 TOP-002 和设计宪章中“readiness 与 invoke 使用同一 preflight”的承重不变量。第三版只允许抽取一个私有只读准备函数，不增加错误体系或 UI，范围合理。 |
| `FIG4-PROFILE-001` | 必须改配置 | `deploy/apply_ingaas_fig4_profile.sh:7` 当前只选择 `tcad_artifact,curve_score,ingaas_fig4`。图插件完成 E1—E3 后不加入安装组合，安装态目录仍不会出现新能力。这里只需改一个现有 profile 值并走既有安装入口，不是部署架构工作。 |

六项中前四项是科学证据生产链阻断，第五项是 33 项约束中的调用权威阻断，第六项是发布配置门。
没有发现可以在保持真实 PDF 来源、独立审查、现有资格链和安装态运行的同时直接删除的项目。

## 3. 非阻断范围是否仍被混入

没有发现下列工作被重新混入实现：

- **审批页可读性**：第三版第 67—74、225—233、303—314 行明确只保留 `UI-READ-002` 记录，不改
  projector 展示、UI item、前端框架或领域 HTML。E5 的人工决定是现有 HIL-001 必经门，不等于
  UI 改版或可读性验收。
- **精细诊断**：E3 只复用同一 projector 准备函数，明确不增加 reason code 和端口诊断；
  `PROJECTOR-DIAG-001` 延期。
- **部署协议**：E4 使用已有 dry-run、事务和重装入口。当前 `deploy/reinstall.sh:62-86` 已显式透传
  安装环境，`deploy/install.sh` 已有 dry-run 与事务回滚。除非真实安装复现缺陷，不得以“验证”为由
  修改部署协议或重新实现回滚。
- **强隔离**：`SEC-002` 保持 trusted-local known issue；E5 的内存熔断和关闭父历史只是现有原型运行
  约束，不是 Hardened 后端开发。
- **通用集合输出**：集合只在既有 Transform 输出路径使用。核心仍拒绝 Agent collection，不新增
  OutputBundle、数据库状态或恢复协议。
- **通用科学图和固定工作流**：E0—E6 是一次验收顺序，不是运行时 Scheduler DAG；计划第 290—301
  行继续要求调度 Agent 从唯一 public 目录按当前矛盾选择行为。

实施范围还必须遵守两个解释边界：

1. E4 的“验证回滚”只核对现有事务保护仍在且真实安装失败会落入它；不得为了本轮另写回滚机制。
2. 请求 Operation 允许保留现有栅格媒体兼容性，但本轮新增实现和资格只针对冻结 PDF 中的 Fig.4；
   不得顺带开发任意栅格图、marker、拟合段、箱线图或自动图表理解。

这两个边界已经能从第三版的明确延期和复杂度停止条件推出，不构成计划返工项。

## 4. 五 Operation 是否还能合并

### 4.1 请求 Agent 与物化 Transform 不能合并

轴标定、曲线身份、种子走廊和遮挡声明是基于图像的科学选择，应由 Worker 输出；像素跟踪、误差传播、
叠图和 CSV 是给定请求后的可重放机械结果，应由 Transform 输出。合并将违反 ROLE-001、DET-001 和
DET-002，或者重新引入不可运行的 Agent attachment collection。

### 4.2 物化 Transform 与 Intake Agent 不能合并

`ScientificIntake` 不是机械附件清单，它包含问题框定和来源约束的科学基础。让 Transform 自动生成
Intake 会把科学摘要和来源取舍写进确定性代码；让 Intake Agent 同时正式生成全部附件则回到
`FIGURE-RUN-001`。因此两者必须分开。

### 4.3 Intake Agent 与审查 Agent 不能合并

现有资格 projector 要求 producer family 有编译 review edge，并要求 passing audit 精确覆盖主项、
成员和冻结来源（`src/scidiscovery/general_science_components.py:325-387`）。编译器又禁止 producer 与
reviewer 使用同一个 Agent component（`src/scidiscovery/operations/catalog.py:527-567`）。合并会直接
破坏独立审查。

### 4.4 物化 Transform 与打包 Transform 不能合并

最终 `CurveBundle` 必须在独立审计之后生成；审计本身又必须读取物化附件。把两个 Transform 合并会
形成审计依赖环，或提前发布未审查标准曲线包。现有打包 Transform 已经消费 Intake、Audit、manifest、
report 和 tables，并以 parentage guard 关闭该边界（`plugins/curve_score/curve_score/operation_transforms.py:117-143,187-204,491-508`）。保留它比修改下游评分端口更小。

### 4.5 不应增加第六个请求审查 Agent

请求只是尚未获得资格的中间方法配置，只能进入 support 物化；最终图审查 Agent 会把精确请求、来源、
全部物化附件和 Intake 作为同一审查集合，打包 guard 与资格 projector 再要求该完整审查。它不能单独
成为已资格 evidence 或绕开后续 audit。

因此计划第 294—295 行“每个科学生产者的结果由精确 review edge 审查”应按最终可消费科学结果理解：
不能据此给请求 Agent 新增独立 reviewer。若实施者发现请求能脱离完整图审查被下游消费，应收紧现有
端口/guard，而不是新增第六个 Agent 或通用晋级状态。

## 5. E0—E6 与负控范围

E0—E6 没有需要删除的阶段：

- E0 冻结真实 PDF、Fig.4 条件和历史 oracle，防止再次选择论文不存在的温度或从旧 CSV 反推请求；
- E1 只改图插件的声明、Schema、工具、Transform 和审查边，不改核心 Run；
- E2 只恢复真实 Fig.4 连续线曾经证明必需的跟踪与未决语义；
- E3 只关闭一个核心 preflight/invoke 等价缺口；
- E4 只把已可运行插件加入现有 profile 并验证真实安装入口；
- E5 证明真实 Agent、领域工具、原生图像能力、Transform 多输出、sealed result 和资格调用能够组合；
- E6 由未参与实现者确认没有为了闭环扩大核心。

计划中的负控数量虽多，但都对应已发生过或当前可达的不同失真路径：来源错配、轴/同色物误跟踪、
未声明断裂、遮挡身份、伪 eligible、旧 CSV 绕源、缺附件、错审计和混合 family。它们是单元或
preflight 负控，不要求为每个负例启动 Agent，也不要求新增产品机制。

为避免测试本身膨胀，实施时应按以下最小分层执行：

- Schema/算法负例在插件级串行测试中覆盖；
- lineage、完整 family 和独立审查负例在 Root preflight 覆盖；
- 安装态真实探针每个信任边界保留一个代表性失败即可；
- 不为测试新增生产 Operation、公开 MCP、状态、注册表或兼容路由。

现有 4 GiB 单进程树和 8 GiB WSL 上限也只是对既有 OOM 事故的运行约束，不是新资源调度系统。

## 6. 33 项约束复核

第三版涉及或保护的承重约束如下：

- AUTH-003：请求、物化、Intake、审查和打包均从同一插件 OperationSpec 编译；
- ROLE-001/002：Agent 拥有科学选择，Transform 拥有机械结果，生命周期消费同一合同；
- DET-001/002：图像恢复和数字化可重放，但不替代轴、身份和遮挡判断；
- TOP-002：Approval preflight 与 invoke 复用同一只读投影准备；
- EVD-001：PDF、页、对象、恢复图像和附件父链精确冻结；
- HIL-001：资格决定仍只来自精确 UI；
- PLG-001/002：图 Schema、工具、算法、角色和 Operation 留在可选插件，通过唯一入口组合；
- RES-002：Agent 和测试串行、有界，不恢复通用集合生命周期；
- SEC-002：软隔离限制如实保留，不冒充已关闭。

HIL-002、UI-001/002 的未完成状态不因临时人工点击而改变。第三版没有把 33 项验收矩阵转换成新的
运行实体，也没有要求在本轮重验与修改无关的全部控制面。

## 7. 独立检查证据

审查实际读取了：

- 第三版计划、当前中文架构、最小设计宪章、33 项约束；
- 首轮 FAIL 与第二轮 PASS 审查；
- 当前图 Agent/数字化/打包源码、Local 后端能力判断、review graph 编译器、资格 projector；
- 当前 Fig.4 profile 与已有安装 dry-run/事务路径；
- 历史论文图证据资格记录。

在当前工作树串行执行：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m2_parameter_package.py
```

结果：**11 passed in 3.07s**。

另执行：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_architecture_constraint_matrix.py
```

结果：**1 passed in 0.05s**。计划、约束矩阵和计划索引的 `git diff --check` 通过。

这些测试只确认当前缺陷和合同边界，不能替代 E1—E5 的新实现证据。

## 8. 最终裁决

**PASS，阻断项 0。**

第三版没有扩大到 UI 改版、精细诊断、部署重构、强隔离、通用集合或新调度体系；六项工作均与真实
Fig.4 闭环或 33 项承重约束直接相关，五 Operation 已是当前 ABI 下的最小可组合拓扑。

放行范围仅为 E0/E1。任何实现若出现以下情况，应立即停止并重新审查，而不是继续补丁化开发：

- 修改 Agent collection、Run 生命周期、Scheduler、current、Execution 或数据库 Schema；
- 新增第六个请求审查 Agent、第二注册入口、第二校验规则源或 Fig.4 核心分支；
- 为本轮重写 UI、错误分类、安装事务、Hardened 后端或任意图表能力；
- 同时保留旧 v1 数字化生产路径和新五 Operation 路径。
