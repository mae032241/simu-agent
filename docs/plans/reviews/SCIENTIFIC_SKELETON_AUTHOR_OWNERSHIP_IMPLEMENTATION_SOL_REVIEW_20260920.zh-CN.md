# Scientific Skeleton / Author Ownership 实现：独立 SOL 跨边界审查

结论：**需修复后复审。P0：无；P1：2 项；P2：无。** 候选已建立 project 内唯一具体计划、计划变化后的开发证明失效、一次综合 review、package/analysis 新旧分支和历史字段缺省序列化等主要机制；但最终综合 reviewer 仍读不到 exact 原研究目标，且 review 前 plan 投影已能进入真实 legacy claim consumer。两项均与冻结计划的科学上下文和投影资格边界直接冲突。

## 1. 审查绑定与方法

- 计划：[R1 计划](../SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_PLAN_20260920.zh-CN.md)，SHA-256 `4ec9c6af0b921d8c5cc5235a52967c516ed6b278e37c6a8835b5e0010a61e10e`；其独立计划审查为 PASS。
- 实现基线：Git HEAD `943c4626f8490530e9318eb9fbb409d2670908b9` 加保存的既存 dirty 工作树；[baseline-manifest.json](../evidence/scientific-skeleton-author-20260920/baseline-manifest.json) SHA-256 `5e6838d219590cd75f601d79eba526b477b1f5a80f49b2fa42624be4132740ef`。
- 冻结候选：[candidate-manifest.json](../evidence/scientific-skeleton-author-20260920/candidate-manifest.json) SHA-256 `123c859b805c9a8755ababc3ee882a90041383161bbc5b060b451f4ec6225390`；[implementation.patch](../evidence/scientific-skeleton-author-20260920/implementation.patch) SHA-256 `d5c825ef2e5f8604824f2bee6319dfe154442351e37df73aa1a734a64d91753e`；28 个文件，728 行新增、61 行删除。
- 实现交接：[IMPLEMENTATION_REPORT.zh-CN.md](../evidence/scientific-skeleton-author-20260920/IMPLEMENTATION_REPORT.zh-CN.md) SHA-256 `71e0446a2222dd702f9442e7c91b57e818d3576e51ff22591f4dd0b7971026d2`。
- 本审查只针对上述 patch，不把整个 dirty HEAD diff 归入本轮。审查结束时，各 SHA-256 与交接值相同，`git apply --reverse --check implementation.patch` 通过。
- 本轮使用 `scid-cross-boundary-review`、`scid-change-scope-checks` 与 `karpathy-guidelines`，跟踪设计 producer、author/revision/runtime/gap、开发证明、投影、综合 review、package、analysis、安装证据及历史兼容。没有修改实现，没有调用科研 MCP、模型或 solver，没有部署，也没有启动子 Agent。
- 在冻结证据之外，我串行运行两个只读候选的小型 compiled-gateway 复现，均通过 `scripts/compiled_worker_process_guard.py:run_process_group` 的 768 MiB 守卫：投影准入复现峰值 120,932 KiB；真实骨架引用复现峰值 121,488 KiB；均退出 0、未超限。临时复现没有写入候选源码或冻结证据目录。

## 2. Findings

### P1-01：最终综合 reviewer 无法读取 exact 原研究目标；真实骨架 producer 虽保存目标绑定，公共引用路径没有暴露它

**最紧位置：**

- `src/scidiscovery/general_science_experiment_operations.py:347-357` 的真实 skeleton Operation 绑定 `research_objective`、foundation、hypothesis 和 critic；完成 Run 的 tool-evidence manifest 因而保留这些 exact 输入。
- `src/scidiscovery/reference_tools.py:13-30` 的公共引用策略只为 layered diagnosis 声明正文引用规则。`src/scidiscovery/artifact_agent/service/reference_access.py:283-363` 只从匹配策略的正文 alias 建边，并不会把 producer manifest 的全部 input bindings 自动当成可浏览引用。`ExperimentScientificSkeleton` 正文也没有一个可解析的 objective 引用。
- `plugins/tcad_artifact/tcad_artifact/plugin.py:495-532` 的 author/reviewer 输入只有 optional `current_progress` 与 skeleton，没有 exact `research_objective` 端口；`current_progress` 可缺省，也没有把骨架 producer 的 objective 输入转成 reviewer 可读来源。
- `plugins/tcad_artifact/tcad_artifact/plugin.py:639-679` 的 version 3 reviewer 因而可读 skeleton、project、投影计划与 capability，却没有可靠入口恢复 skeleton 所依据的 exact 原目标。

**独立复现：**我用真实 `science.experiment.skeleton.v1` 完成一个 skeleton Run，再依次完成真实 SProcess author、project plan 投影并启动 `tcad.deck.review.v1`。骨架 producer 的 sealed manifest 明确包含 `['critic_review', 'hypothesis_portfolio', 'research_objective', 'scientific_foundation']`；但 reviewer 对其已绑定 `scientific_skeleton` 调用 `worker_reference_read(action='list')` 得到：

```json
{"action":"list","next_cursor":null,"omitted":0,"references":[],"source":"scientific_skeleton"}
```

这排除了“总体目标已由普通 producer parent/公共引用自然可达”的可能。现有主链测试还直接登记无 producer、无 objective parent 的 schema-valid skeleton，author→review→package→analysis 仍可完成（`tests/operations/test_tcad_scientific_skeleton.py:23-96`）；installed preflight 也接受同类 fixture（`tests/operations/test_catalog_installed_entrypoint.py:1499-1515`）。

**可达影响：**最终 reviewer 能判断具体计划是否符合当前 skeleton，却不能把 skeleton 与 exact 原研究目标比较。若 skeleton 在设计或导入时已缩窄、漂移或错误解释总体目标，后续 `scientific_assessment=pass`、package 和 analysis 会保护这条内部一致但起点错误的链。这正是计划要求综合 reviewer 避免“忠实实现错误要求”的场景。

**所需修复：**给最终 reviewer 一个受控、可读、exact 的原目标来源，例如显式绑定 `research_objective`，或为 skeleton 定义经过验证的目标引用边并允许公共引用读取；同时明确无受支持 producer 的 imported skeleton 如何携带等价的 exact 来源。控制层只需核对身份、来源与可读性，科学一致性继续由 reviewer 判断。**不要求** objective 文本逐字复制进 skeleton，也不要求控制层逐项机械比对 mandatory targets。

最小负例/正例应证明：真实 skeleton producer→author→综合 reviewer 能读取同一 exact objective；无 objective 来源的 standalone skeleton 不能获得新路径最终资格，或必须走明示的 imported-source 合同。

### P1-02：review 前 plan 投影洗掉 author project 的强制 review obligation，真实 legacy claim consumer 已接受该未审投影

**最紧位置：**

- `plugins/tcad_artifact/tcad_artifact/operation_transforms.py:108-128` 允许从完成的 version 3 author project 提取计划；`:443-450` 把 project 端口声明为 `usage="evidence_inventory"`，因此可在综合 review 前读取。
- 该 public scientific Transform 没有 review edge，也没有给输出设置 `scientific_claim_admissible=false`。
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1484-1514` 对 evidence-inventory/background 输入跳过 producer review admission；`:990-1012` 仅在上游已 nonqualifying 或 Operation 为 explore/internal 时给 transform 输出写 false。`src/scidiscovery/artifact_agent/interfaces/mcp_root_shared.py:41-65` 因此把 projection 当普通 claim-admissible 产物。
- `plugins/curve_score/curve_score/operation_transforms.py:427-445` 的 `scidiscovery.curve-reference-coverage.v1` 把 `experiment_plan` 声明为 claim evidence；其 transform `:111-119` 不读取 `experiment_review`。legacy 路径原本依赖 plan producer 的 review edge 将 exact review 与 plan 配对，projection producer 没有该 edge。

**独立复现：**我通过真实 author Run 完成一个带内嵌 plan 的 project，但没有启动 `tcad.deck.review.v1`；随后调用 `tcad.execution-plan.project.v1`。投影 artifact 的 `scientific_claim_admissible` label 为缺省（不是 `false`）。将该投影绑定到 `scidiscovery.curve-reference-coverage.v1.experiment_plan`，另绑定结构有效但与该计划无 exact reviewer provenance 的 review/contract/reference fixture 后，真实 compiled `operation_preflight` 返回：

```json
{"admissible":true,"executor_kind":"transform","port":null,"reason_code":null}
```

因此这不是只缺一个标签的理论问题：project 尚无综合 review 时，投影已经通过一个现存 claim consumer 的真实准入。候选测试只覆盖“投影不能重新作为 TCAD author 的 legacy 设计”和 package/TCAD analysis 的局部 exact checks，没有覆盖这一跨插件负例。

**可达影响：**project→plan 派生边切断了 author project 的 review edge。package 与 `tcad.result.analyze.v1` 的新增局部检查仍能保护自身，但其他 Portfolio claim consumer 会收到表面合格、实际尚未综合审查的计划。这违反计划 §3.3“投影不授予执行或科学 claim 权限”，也使计划声明保留的 legacy curve-score review 依赖失效。

**所需修复：**使 projection 在控制元数据上明确 nonclaiming，并仅由 project review、package 和 TCAD analysis 的 exact-lineage 局部合同按材料用途读取；或提供等价的通用 producer-family 准入限制。新增一个真实 compiled admission 负例：未综合审查 project 的 projected plan 不能进入 legacy claim consumer；同时保留 review 前可投影以解除 review 循环，以及综合 review/package/TCAD analysis 的正路径。只修改 Operation 描述不会改变当前准入。

## 3. 已确认成立的实现部分

- `DeckProjectDraft.execution_plan` 是新路径唯一封存的具体计划；投影原样规范化提取，exact project 是其唯一业务 parent。没有增加第二 Agent 主输出或新状态机。
- 旧 project/review 缺省字段通过 serializer 省略；legacy detailed-plan producer、review witness、SDevice 旧入口及历史 analysis 分支保留。新 skeleton 分支限定 SProcess。
- author 初建、review revision、runtime-failure 与 gap 共用 exact-one/原 skeleton 约束；gap 无需编造 Portfolio，且不能投影或打包。
- `project_debug_sha256` 包含 `execution_plan`；工作区诊断和提交从当前计划重新物化。旧 proof 在 revision/retry 中被清理或移入 history，trusted record 核对当前 project/declarations digest，计划变化不能沿用旧开发证明。
- 新 `scientific_assessment` 对历史 review 可缺省；新 project 的 output context、package admission 与 TCAD analysis 要求 passing scientific assessment。复制 labels 或给旧 report 加字段不能伪造完成的 version 3 reviewer Run。
- package 与 TCAD analysis 新分支核对 exact project、project-derived plan、skeleton、review Run inputs、package parents 和 runtime manifest；legacy 分支仍要求原 ScientificReview。审批 UI、external Effect、执行器和 recovery receipt 底座未放宽。
- author/reviewer/scheduler 合同已表达：科学等价实现选择留在 author；语义冲突先判断对科学决策的影响；gap 不自动扩大任务；早期骨架 review 不替代综合 review。没有新增逐项科学签名表或硬编码 t0 verdict。

## 4. 冻结证据支持范围与遗漏

冻结证据支持这些工程事实：定向 pytest 和隔离安装由 768 MiB guard 串行运行，记录峰值最高 230,712 KiB；主链 fixture 覆盖 author→受控开发诊断→submit→projection→综合 review→package→TCAD analysis，以及错误 plan origin、缺 scientific assessment、复制 project labels、计划变化使 proof stale、gap 不可投影和同线程跨 Operation attachment 拒绝等负例。`git diff --check` 与冻结 patch 反向检查通过。保存基线独立复现一项既存 fixture 编译失败，没有把它计为候选通过。

证据仍不能支持以下结论：

- 冻结主链使用手工登记 skeleton，未验证真实 producer 的 objective 对最终 reviewer 的可读性；本次独立复现确认该引用列表为空，因此构成 P1-01，而不是单纯覆盖遗漏。
- 没有“投影保持 nonclaiming”或“legacy claim consumer 拒绝 projected plan”的负例；本次独立复现确认现有 consumer 实际准入，因此构成 P1-02。
- runtime-failure、review revision、同 Run retry/重开恢复没有逐项运行；共享代码静态闭合不能替代完整恢复矩阵。当前未另报独立缺陷，但修复若触及共同 admission/lineage，应把这些分支纳入复审。
- 最后一轮 installed wheel 后又修改了 legacy 目录/reviewer 描述；实施报告已说明最终 prompt 字节未再建 wheel。安装结构证据可复用，不能声称最终 packaged prompt 候选已逐字验证。
- 没有运行原生模型、真实 solver、Fig4 恢复或生产浏览器/审批流。现有 fixture 不能证明模型会提前识别 t0 语义冲突、区分 callback 动态缺陷，也不能证明任务数、69 次请求或 token 百分比改善。

修复两项 P1 后，最小复审应先运行对应的 objective-reference 与 projection-admission 正负例，再串行重跑现有 skeleton 主链、legacy plan/review 重启准入和 final installed probe。真实模型/solver 行为属于另行授权的行为验收，不应由单元通过代替，也不影响本次工程合同“需修复”的结论。
