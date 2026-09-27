# 研究纠错与续研实现独立工程复审 R2

结论：**PASS，限定于下述冻结的 Local 工程候选。** R1 唯一阻断已按既有规则修复；必要 fixture 迁移没有扩大十四个生产文件的行为范围，未发现新的工程阻断。完整验证结果为 **676 passed、10 failed、0 skipped**，不能表述为全套通过。十项失败的范围处置见第 4 节。P5 部署与资格恢复、P6 真实科学研究尚未完成，均不继承本工程 PASS。

## 1. 冻结身份与复审边界

| 对象 | 身份 |
| --- | --- |
| 审定计划 | [主计划](../RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md)，SHA256 `9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8` |
| 最终候选 | [p4-candidate-final.json](../evidence/research-correction-continuation/p4-candidate-final.json)，`candidate_digest=27da282cee930c816f32a0f070153de8516cd8f2b3179429f73bb433984d3bc9`；文件 SHA256 `b5346f442db476cd6c2afa958b847a473b67e1c8c76fcc149c2d8c15fa9d3a91` |
| 最终补丁 | [p4-candidate-final.patch](../evidence/research-correction-continuation/p4-candidate-final.patch)，SHA256 `66d12c4a7324df35dc9bb5e487ae2c9f58461ef40c4c3b2f1657441f05210a7d` |
| 原脏工作树基线 | [source-baseline-2026-09-08.json](../evidence/research-correction-continuation/source-baseline-2026-09-08.json)，SHA256 `50574bfe11f1fe1caa7649e89d887e44fa0a816cb654c8656ba0f713f760e438`；原字节目录 `/tmp/scid-continuation-implementation-baseline` |
| 上轮报告 | [R1](RESEARCH_CORRECTION_IMPLEMENTATION_REVIEW_R1.zh-CN.md)，SHA256 `27e24bc9e64828ca4867cf8ff502ddf9150141f3545738c0d484c9d9a3586c64`，保持不可变，其原候选结论仍为 REVISE |

最终清单共 33 文件：十四个生产文件、十七个验证 fixture 文件（含 `scripts/l4_live_tcad_agent_probe.py` 的数据构造）、两份架构文档。审查者以冻结基线字节在内存中分别重建 R1 与最终补丁，全部 before/after 摘要吻合，最终 33 文件与工作树逐字一致。相对 R1 只有七个文件不同，其中唯一生产变化是曲线编译器中的两行移动；其余十三个生产文件及双语架构文档未变。

本轮承接 R1 已完成的两条完整调用链审查，只核对修复、fixture 增量、验证结果与失败范围。依据仍为适用 AGENTS、跨边界审查/最小化/变更检查技能及现有架构和审定计划。审查者只读源码、测试及证据，未运行 pytest、wheel、科学 MCP、Worker 或 solver；只新增本报告。

## 2. R1 阻断已经闭合

`plugins/curve_score/curve_score/curve_contract_compiler.py:396` 先建立适用检查键与显式引用集合，第 400 行执行原集合一致性校验，随后第 404 行才处理无适用检查的正常返回。相对 R1 没有新增条件、错误类型或数据模型。

因此，在当前计划仅有其他 evaluator 的确定性检查时：空显式绑定仍可编译；不存在的检查键和指向其他 evaluator 的键都会拒绝。原有当前检查覆盖、单位、阈值与整合同重算规则保持。无效引用不会再通过早返回从原请求中消失。

`tests/operations/test_m2_curve_analysis_boundary.py:970` 的三分支回归通过真实 `compile_curve_contract` 入口表达这个反例。[修复前日志](../evidence/research-correction-continuation/p4-review-check-binding-before.log) 为 `2 failed, 1 passed`；[修复后整文件日志](../evidence/research-correction-continuation/p4-review-check-binding-after.log) 为 `27 passed in 7.30s`。修复后编译器 SHA256 为 `7457469fac768541d9c81dcc748ae0be732e33614d61242f6893dbf8e96344ba`。这解决了原阻断，没有降低引用标准。

## 3. 必要 fixture 迁移与最小范围

| 文件 | 本轮增量及判断 |
| --- | --- |
| `scripts/l4_live_tcad_agent_probe.py:92` | 将旧单目标工程 proposal 迁移为总体目标与本轮目标列表；本轮目标原文不变，总体原文来自既有 portfolio。prepare、launcher、transport 流程未改。 |
| `test_hypothesis_review_routing.py:246` | 将 `b'{}'` 替换为已有合法 `_plan` 的 canonical JSON，以满足正式计划严格解析；原路由/角色断言未改。 |
| `test_l3_review_and_human_policy.py:35` | 临时 consumer 直接复用既有强类型 `prior_signal`，使“消费已独立审查结果”的用途与 ABI 17 一致。只同步用途断言；缺审查、错 revision 拒绝以及精确审查正控全部保留。此临时 consumer 不属于九个生产 inventory 消费者。 |
| `test_r5_catalog_stages.py:145` | 固定 core/general 十五项目录在 ABI 17 与目标/反馈合同下的新 digest 摘要 `eca9324b46e59f93a5d592f712fb021089674f6b133a3cf1d62db9bcf1acd1be`；数量与其他编译一致性断言未改。 |
| `test_spec.py:23` | 将冻结基线 `operations/spec.py:335` 已有的 `complete_transform_family` 纳入字段顺序快照，没有新增生产字段。 |

新增 curve 回归另见第 2 节。上述迁移属于计划第 4.1 节的验证范围；未删除测试、增加 skip、改复杂度阈值，未改变门禁以迎合断言。

R1 已追踪的 negative deck review→workspace→submit→package/Effect 及 feedback→正式目标→materialize→review/revise→精确父链查询→新显式输入两条链，其生产实现除本项编译顺序外完全一致。Agent inventory 例外仍仅跳过 producer-output 资格检查；主审对象、claim、revision、current、完整 family/cohort、独立 review/approval 和 Effect 门禁没有新豁免。目标遗漏仍交科学设计者与独立审查者判断，总体缺项 evaluator 没有改成通过。初始化证明仍来自精确原件，经严格解析后整对象比较；没有合成 qualified 证明。

## 4. 完整验证及十项保留失败

[完整记录](../evidence/research-correction-continuation/p4-checks.json) SHA256 `450a2d3a106e8fee0773ef393f6e92dbd392c8b083b1ba35216424482682a884`；[收集清单](../evidence/research-correction-continuation/p4-collection.log) SHA256 `fbc195ef33740ee9d7c8f433a54682e0e251c3158745069455f26285d8549b76`。

审查者独立解析收集 nodeid、复用文件摘要与各文件最终批次摘要：52 文件、686 项全部有证据，缺失/额外文件均为零；复用 257 项，其余按最终批次汇总后为 676 通过、10 失败、0 跳过。修复前失败日志保留，但统计不重复计入已经完成迁移后重跑的同一用例。历史合同五项复用自混合日志；该日志仅两项父链上限 fixture 失败，后者由独立最终父链日志的十三项通过承接，未把混合日志整体称为通过。

执行命令及退出码逐批记于 `p4-checks.json`，例如父任务串行执行：

```text
/home/da/miniconda3/bin/python -m pytest -q tests/operations/test_l4_local_tcad.py
```

该最终 Local TCAD 文件为 84 passed，覆盖负面报告、假 pass 拒绝以及完整科学 case binding 的 Root 包装正控。它仍是工程 fixture。

| 保留失败 | 源码依据与处置 |
| --- | --- |
| Hardened 源码六项 + 安装态一项 | [归因证据](../evidence/research-correction-continuation/p4-hardened-baseline-analysis.json) 核对测试、blind plugin/tool/contracts 与 Hardened backend 的基线字节一致，Root availability/prepare 相关 AST 一致。`blind_csv_plugin/plugin.py:163` 要求 reviewer；第 184 行 reviewer 需要 inherited native shell；`hardened_workspace.py:74` 拒绝此能力，Root 第 984 行在目标行为前返回 `operation_runtime_unavailable`。安装日志实际出现同一诊断，未新增另一归因。源码等同性支持这是基线限制的推论；没有声称运行过冻结基线 pytest。 |
| general plugin 结构三项 | [结构证据](../evidence/research-correction-continuation/p4-structure-baseline-analysis.json) 表明基线已有 63 components、公开 execution_context_schema，而旧断言固定 61 并漏该公开项。旧行数阈值为 1140/1180、合计 2310；基线已为 1148/1197、合计 2345。当前为 1193/1270、合计 2463，本次另增 118 行，仅来自已审定的 experiment operations +45 与 components +73。新增端口、提示、语义与严格输入校验已审查，不把这 118 行冒充基线变化；没有新增 Operation、owner 或服务。保留失败，不抬阈值或压缩格式。 |

这些失败不构成本轮 Local 放行阻断：架构中文版第 183、218 行已明确 Hardened 是非默认实现，本阶段不补齐且不以其通过为完成条件；此次拒绝也没有扩大到默认 Local。六项及安装态一项目标行为仍未得到验证，不能改 shell 声明伪造 reviewer 可执行性。结构失败保留为旧快照/阈值问题，本候选的实际增长已单独审查；无需为了此任务顺带重建旧复杂度基准。计划第 6 节要求完整清单覆盖、失败调查与如实报告，本轮满足该要求，没有以“全套通过”为名掩盖例外。

## 5. 安装身份与剩余验收边界

唯一一次隔离 wheel 批次覆盖六个文件，命令文件列表为 `test_baseline_effect_lifecycle.py`、`test_baseline_role_contracts.py`、`test_baseline_transform_lifecycle.py`、`test_catalog_installed_entrypoint.py`、`test_l1_minimal_runtime_projection.py`、`test_m7_effect_fixture.py`，共同使用 `/home/da/miniconda3/bin/python -m pytest -q`。结果 [35 passed、1 failed](../evidence/research-correction-continuation/p4-installed-wheel-batch-1.log)，日志 SHA256 `66c62749c40e6756593e8e6a950de2af7b2264415f955149a05f3170674f4863`；唯一失败属于上节 Hardened。已覆盖安装 loader、profile、Schema/资源和 Local TCAD 正控，不能把该批次写成 36 项全过。

父任务复用同一批 `all_domains` 隔离环境，以 `-I` 和 `/tmp` 工作目录调用安装 loader，无重建 wheel。[安装目录](../evidence/research-correction-continuation/p4-installed-catalog.json) SHA256 `665de616981f89ec13619c44c9f7fd3d7b823e1154756107d3cee196ed302f82`。审查者逐项比较其与[源码目录](../evidence/research-correction-continuation/p4-source-catalog.json)：49 个唯一 Operation 的 id、version、digest、executor、scope 完全相同，ABI 均为 17。这支持候选的安装身份一致性，不代表生产服务已部署。

本轮只读 `git diff --check` 退出码为 0；双语架构增量与 R1 完全相同。后续须按计划继续：P5 建立真实案例的必要资格恢复清单、确认可接纳的来源与已注册建立路径、完成一次部署；P6 经实际 completed Run 的 sealed_output 与 scheduler_signal 验收负面审查、科学范围判断及无聊天新会话续研。工程 fixture、安装身份相同或本报告 PASS 均不能替代这些证据。
