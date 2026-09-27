# 科学骨架与 author 实施职责计划：独立工程审查

结论：**PASS（实施计划通过；不是实现、部署或科研资格通过）**。未发现要求退回重写的 P0/P1 缺陷。计划已把职责、写合同、独立审查时点、项目与分析资格作为同一个改动处理；不是仅改提示词或取消审查门。允许进入计划规定的串行实施，不需要为了本次计划通过新增模型或 solver 实验。

## 1. 审查绑定与范围

- 审查对象：[R0 实施计划](../SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_PLAN_20260920.zh-CN.md)。SHA-256：`ba421ba77e789a629c60a7da0d00c48ef403d0d03550db17dbbfd9c56a8e7225`。
- 实际仓库：`123/scidiscovery-e5.2`；HEAD：`943c4626f8490530e9318eb9fbb409d2670908b9`，**加审查时既存 dirty 工作树**。源码结论不归于裸 HEAD，也不代表后续修改后的候选。
- 审查者独立于计划作者。本轮只读取计划、相关源码与局部历史材料，并新增本报告；没有修改计划、源码或现有审查，没有运行测试、模型、solver、科研 MCP 或部署，也没有启动子 Agent。
- 使用跨边界审查、决策文档维护、karpathy-guidelines 技能；本次是工程计划审查，不进行实例选择或科研调度。
- 历史 Fig4 收尾第 20 行确实记载 t0 返工 69 次请求、峰值 101,350 token 及修订科学表述后复用源码。这里仅确认计划引用对应原记录，未独立重做其科学判定或 token 统计。

## 2. Findings

**P0：无。P1：无。**

**P2-01：WP0 的可选审查身份核对可以直接落到已有 native Worker 绑定入口，不需要预设新增 subject guard。**

位置：计划第 104、140、159 行。计划正确地把“没有强制 edge 不等于自动独立”列为检查，但其条件式描述容易让实施者从 review admission 寻找或添加重复检查。

源码证据：`src/scidiscovery/artifact_agent/interfaces/mcp_gateway.py:178` 的 `worker_attach` 最终调用 `WorkerConnections.attach`；`service/worker_connections.py:38` 查询同 session/thread 的前次绑定，`:43-52` 在已有绑定终结后仍要求相同 `operation_id`、`operation_digest`、模型和推理档位，跨 Operation 直接拒绝。该逻辑与 review edge 无关。新骨架设计 Operation 与 `science.object.review.v1` 不同，TCAD author 与 `tcad.deck.review.v1` 也不同，故同 native 线程不能从作者转成 reviewer。`operations/catalog.py:609-614` 的不同 Operation/component 校验则是另一层编译约束，不能把两层混为一谈。

可达影响：若误以为独立性只由 review edge 提供，可能不必要地增加局部身份 guard，甚至把运行线程身份带入纯输入预检；这会扩大实现范围。当前计划已经将新增 guard 写成条件分支，故不是安全缺陷或计划阻断。

最小建议：实施 WP0 记录上述实际入口，沿 `tests/operations/test_unified_mcp.py` 的 attachment 入口增加或复用同线程跨设计/审查 Operation 被拒的负例即可。无需为骨架专设身份状态，也无需重新设计 admission。此处是源码确认，尚未执行该负例；不把推理写成测试通过。

## 3. 两个前置问题的明确答复

### 3.1 没有强制 review edge，可选审查还能否独立？

**能，当前 native Worker 入口有不依赖 edge 的跨 Operation 线程复用限制。** 计划中的可选 `science.object.review.v1` 与新骨架 producer 不同，保留现有 attachment 流程即可。新的 reviewer 输入/输出仍须验证 exact skeleton、review_target 和正式变更依据，这属于科学对象绑定，不需要另一套线程身份检查。

`RunService.is_exact_reviewer_output`（`service/runs.py:1130`）检查的是实际 completed Run、Operation、subject 输入、verdict 与兼容性；它本身不比较 native 线程。实施证据要同时覆盖“正确对象的完成审查”和“独立线程绑定”，不能只展示一个 PASS payload。不能从本结论推导任意外部平台、绕开 gateway 的私有调用都获得同样保证。

### 3.2 现有受控发布能否直接省掉纯投影 Operation？

**本次读取未找到满足计划所需语义、且比薄 Transform 更小的现成发布路径。推荐薄投影有源码依据。**

- `operation_contract.py:326-343` 的直接修订识别要求一个非 collection 主输出，并排除 `recovery_manifest_output` 之外的 collection。因此把 Portfolio 加为第二主输出或普通证据 collection 都不是无成本替代。
- `service/run_outputs.py:68-92` 验证单主结果；`service/runs.py:164-165` 也明确限制一般 collection。不能只增加一个 output 声明就声称发布链已可用。
- 现有 `service/analysis_artifacts.py:16` → `service/tool_evidence.py:375-435` 的受控工具证据，必须在 Run 仍 running 且未接收最终 candidate 时登记；其 parents 来自当前输入和已登记派生来源。当前 Run 最终 project 尚未成为可绑定输入，不能原样得到“exact final project 是 parent”的计划产物。该路径还使用工具证据 port 的 kind/schema，而非任意嵌套模型的科学输出合同。
- `service/result_materialization.py:12` 的 finalizer 只改待封存 envelope 中机械重复字段，不是额外科学 Artifact 的发布器。

为了省一个薄 Transform 而改发布、collection 或直接修订框架，会扩大底座改动。计划第 62 行保留“若发现真正等价机制则优先复用”的取舍是合理的，但无需反复进行开放式机制搜索。投影只提取已封存 project 的唯一 Portfolio，不能创作内容；其无审查读取例外只属于纯提取，不能迁移到 package/execution。

## 4. producer—consumer 路径核对

| 边界 | 源码所示约束 | 对计划的判断与实施落点 |
|---|---|---|
| 假设、设计、修订与物化 | `schema/experiment_intent.py:138-166` 仍必需具体 cases 与 validation_intent；`:320` 是完整 Portfolio 的确定物化。`general_science_experiment_operations.py:55`、`:190`、`:330` 分别定义 design、完整修订及 materialize 审查边。 | 新轻量骨架必须有独立 Schema，不能只改 prompt 或让旧物化填假默认值。保留旧入口避免非 TCAD 强迁移；新骨架按普通输入做精确修订，避免冒用直接修订特权。计划已覆盖。 |
| author 初建、review 修订、runtime-failure | `tcad_artifact/plugin.py:461-496` 的 INITIAL/REVISION/RUNTIME/REVIEW 共用详细 plan；runtime 分支另有失败 attestation 输入验证。 | 必须同步改 exact-one、上下文 validator 与正式绑定恢复；只改 initial 会断链。计划 WP2 明确覆盖四类路径和恢复，不能把 runtime-failure 当作改科学标准的快捷通道。 |
| 工作区与开发验证 | `operation_workspace.py:367-382` 从 plan/capability 判定物化路线；`:616` 限定文件编辑面；`:687-745` 的 finalize 与 gap 仍直接取 experiment_plan。 | author 可编辑计划文件需要进入现有工作区声明/权限、物化、诊断、finalize 和恢复快照同一链。计划中的“工作区计划是编辑入口、project 内 Portfolio 是封存事实”足够明确；新增文件策略是 WP2 实施细节，不另升计划阻断。 |
| gap 与支持范围 | `project_packager.py:782-800` 校验 gap locator 的 plan；workspace deterministic 路线还依赖受支持 solver 类型。 | 计划第 147-149 行明确无完整计划时仍可交 gap，且 skeleton locator 必须显式适配；不能为通过 Schema 编假 cases，也不宣称自动支持所有 solver。范围适当。 |
| 项目序列化与证明身份 | `project_packager.py:707-712` 计算 debug identity 时序列化 project；`:1233-1244` 要求 reviewed package 的规范 JSON 等于模型序列化字节。 | 可缺省字段并不天然向后兼容；即使只是新增 `null` 也可能改变历史字节或证明摘要。计划第 80、82、156 行已要求缺字段不注入旧对象、计划变化按身份规则处理，实施须在这些实际函数验证。无需新证明系统。 |
| 综合审查 | `plugin.py:599` 起的 review Operation 当前强调 fidelity；`project_packager.py:804`、`:1355`、`:1591` 分别拥有报告、上下文和项目一致性。 | 科学充分性应加入正式 Schema、模型合同与输入绑定，不能只加一句 reviewer prompt。计划要求一个总 verdict、科学部分一致性、新合同完成 Run 与 exact project/plan/skeleton，覆盖充分。 |
| 纯投影与 review admission | `operations/review_admission.py:16-29` 区分 background、direct revision、review subject、witness；Root `mcp_root_operation_routes.py:1510-1540` 按生产者冻结 edge 分支。 | 计划避免 project→投影→review 的环，且禁止把 evidence_inventory 广泛当绕门用途。薄投影的 exact parent/内容一致性须局部核验，随后 package 仍要求项目审查。 |
| 打包、执行审批 | `operation_transforms.py:100-105` 的 package adapter 实参是四个基础 payload；`:191` 要求 review 绑定 project/capability/plan。 | optional experiment_review 是准入 witness，不是 adapter 参数 bug。计划已正确区分，并要求新综合审查与 legacy witness 分支在同一发布候选闭合。原执行请求、sealed UI 审批和恢复底座无需重写。 |
| 原执行分析 | `result_analysis.py:86-108` 固定原 plan/review/package/manifest parent；`:330-340` 当前要求 ScientificReview 的 experiment_portfolio PASS；`:556-557` 历史 plan/review 使用 evidence_inventory。 | 新 analysis 分支必须基于真实 package/project producer，而非任选一个 PASS；历史分析仍可读取原链，新骨架不能替换原执行计划。计划对两分支、错 lineage、receipt 与失效输出的要求充分。 |
| 同 Run 评分和非 TCAD | `result_analysis.py:223-280` 的 TCAD 工具取原 Portfolio/package、源绑定和 case mapping；未在该段发现再次要求独立 ScientificReview 的硬锁。 | 保留 Portfolio 投影有实际消费价值。可以先限定 `tcad.result.analyze.v1` 与既有工具闭环；无需本轮迁移 curve_score 全部独立 Operations。此处只做静态追踪，不宣称评分实测通过。 |

旧详细设计、旧 materialize、旧 plan review 与已执行历史链应继续保留；它们不能被标为已获得新骨架资格。必须更新的是新 producer 声明/Schema、author 所有入口与工作区、review 科学合同、package/analysis 双分支以及 source-owned scheduler/安装投影。计划准确区分了两类，不需要让 Artifact、Run、审批与恢复状态机承担新的科学决策。

## 5. 目标、最小性与验收判断

职责符合用户目标：假设保留竞争解释和全局路线；设计冻结科学对照、保持/改变条件、观察量、判据和边界；author 决定具体方案、实现及受控开发验证。数值值是否属于科学变量按语义判断，避免把所有 mesh/time-step 都一律放开或一律上移。review 不仅检查忠实实现，也能指出原要求本身不支持研究判断。

计划第 126-132 行约束的是**下一动作的科学价值**，而非仅把多次小任务合并成一次大 author：已有证据能回答则复用；语义冲突先形成有界正式科学判断；科学等价实现由 author 局部解决；改变成功标准必须修订骨架；不自动追加预算或同义重试。t0 验收与“callback 不更新时间”的反例成对，能避免把所有故障都推回设计。没有把 t0 科学结论写成通用硬编码。

验收具备计划所需粒度：真实 compiled invoke/assignment/submit 与 package/analysis 准入；同 Agent、旧 review 新字段伪装、错 plan parent、科学阈值擅改、历史分析、允许开发但生产仍需 UI 审批；之后另获授权再做一个有界串行行为试验。不能用单元测试数量证明避免了 69 次请求，也不能把未做的真实行为试验变成已通过；计划已经明确这些限制。

不要求本轮额外覆盖所有插件、所有执行异常或全量性能 A/B。资源串行、预算不足停下、保留未验证范围，符合最小可信验收。建议把 P2 所述 gateway attachment 负例并入既有检查，而非新增审查工作流。

## 6. 文档归属与剩余前置项

| 材料 | 归属及处理 |
|---|---|
| 本计划 | 未实施 active proposal；本报告只给其工程计划 PASS。 |
| 本报告 | 绑定上列 hash 的独立审查记录；计划改动后不能自动继承本结论。 |
| ARCHITECTURE 中英文与编译声明/Schema | 当前规范，实施时按受影响职责局部更新，不能以本提案取代在线事实。 |
| Fig4 author 验证计划及 R4 收尾 | 保留原开发证据/失败历史；新职责仅部分承接，不修改历史 verdict。 |
| 根因交接方案、plans README | 机械交接不属本轮；入口整合按既有授权另做，本次不修改。 |

剩余项是实施与验收前置，并非要求再写一轮计划：冻结实施候选及既存 dirty 差异；落实新合同与上述实际入口；证明旧对象序列化和 proof identity 未破坏；工程路径及反例通过后才评估部署候选。实际任务浪费是否减少、t0 类语义冲突能否在继续实现搜索前被识别，仍须计划规定的有界行为证据。当前没有需要用户补科学参数才能判断计划是否可实施的问题。
