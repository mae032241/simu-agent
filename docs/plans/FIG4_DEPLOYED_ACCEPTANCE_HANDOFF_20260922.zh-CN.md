# 新对话接续：Fig4 修复后的真实部署验收

更新：2026-09-22。请先读本文件，按需读取下列原件，不展开全部历史。

## 1. 当前目标与准确状态

用户已安装、重启新版。当前任务是完成本轮修复的真实部署验收，然后按计划测量 token；不要重新规划或重复已完成的代码修复。

- 本轮源码实施、独立验收、两个 P2 修复及另一次独立复审均已完成。
- 已安装代码/角色/指南与最终源码一致；统一 MCP 入口、认证边界及实际安装包的隔离行为验收通过。
- **真实实例的三条链尚未验收：历史 prior/manifest 配对、当次 PNG 发布到轨迹页面、TDR 原产物无重算恢复。**
- matched Root/Worker token A/B 尚未执行，不能宣称 token 收益或全链路通过。
- 独立部署验收者的阻碍是缺少实例接口/认证权限，不是已发现生产代码失败。
- 用户随后清空 memory 并开启新对话；旧线程、functions store、绑定和访问链接都不能当作仍有效。

## 2. 用户约束

- 优先独立 **gpt-5.6-sol** 承担实施、审查和验证，主线程只做必要调度、权限操作并读取短摘要。上轮工程子任务使用 high；科学 Worker 必须遵守 invoke 返回的冻结 profile，不能擅自替换。
- 控制层管理机械身份/依赖/权限，Agent 判断科学用途和结论。禁止新增无用填表、过度校验、角色或状态机。
- 曲线比较默认交付参考/候选叠加图，必要时残差图；用公共提示词和现有图片发布链，UI 只补真实缺口，不增加图表 Schema 或强制提交拒绝。
- 测试串行，**768 MiB 进程树 RSS 守卫、0.1 秒采样**；地址空间限制不能替代 RSS。超限停止，不擅自提限，不跑全量测试或并行模型任务。
- 用户报告另一个任务 OOM 导致重启，不能归因到本任务。部署探针无超限；不因重启自动重跑。
- 当前验收复用已有数据，不重跑 TCAD、不隐式重新拟合。新外部执行仍须精确 UI 审批，不能用历史聊天授权替代。
- 不自动提交 git、部署或改已封存历史。工作树有大量既有修改，不能回滚或将全仓 dirty diff 归为本轮。

## 3. 新对话第一步

1. 遵守工作区 AGENTS.md。MCP 只有 scid_catalog / scid_describe / scid_call；先发现并读取所选接口合同，部署后重新读取必要指南。
2. **Root 调用 instance_current**。上一次返回 unbound，用户尚未在此后确认绑定。若仍未绑定，给出该次返回的原始管理 URL，让用户选 **M7-test0**；不要默认选择、复用旧 capability 或复制令牌给子线程。
3. 已绑定后，从下方明确的节点恢复，禁止全 scientific_inventory 或全目录展开。
4. 独立工程 sol 可以验证已安装代码/隔离接口，但上次该线程没有 scid 工具。不要反复让无权限工程线程尝试真实实例。需要实例操作时 Root 做最小控制调用，并通过正式 operation_invoke / worker_attach 交给 compiled Worker 做科学分析/恢复。不得伪造平台 metadata、共享 Root 凭据或读取控制私有存储绕过接口。

指南目录：`.codex/scidiscovery-guides`（相对仓库根）。选用 inputs.md、results.md、dispatch.md、execution.md、domain-analysis.md；只读相关指南。

## 4. 下一步真实验收（功能优先）

### A. 历史配对

- 历史报告：`fig4_positive_time_analysis_20260920_r4_1.output`
- 其直接 manifest：`fig4_positive_time_analysis_20260920_r4_1.output.recovery_manifest`
- 原问题：`prior_manifest_pair_mismatch`，先前只证明直接父件，后来修复同 Run recovery manifest sibling 的 producer 识别，并增加四维精确诊断。
- 用当前公开合同构造真实的 tcad.result.analyze.v1 输入。此处目标是验证准入、不创建重复工作，可使用 operation_preflight；若随后 invoke，保留并复用返回的 normalized_request。
- 成功标准：真实正确配对通过。失败保留原始 code/path/message，不放宽身份保护、不把错误再解析成 JSON 异常。四维诊断包括 direct_parent / prior_producer / same_producer / recovery_output_port。

### B. 当次曲线图完整链

- 正式当前报告：`fig4_retardation_frozen_metrics_20260921_1.output`。
- 从该报告 producer_inputs 恢复冻结输入，再查询其直接 parents 选直接 recovery manifest，仅查询该 manifest 的直接 parents 来找同 Run 算法/派生数字。
- 新投影按精确 record/ref 连接访问名；Agent 选择所需科学材料，控制机械解析。不得全父链递归/全绑/按名称猜用途。artifact_name 用于 Root 导航与绑定；Worker 工具、证据及报告引用仍用 assignment source_name。
- 按当前 Operation 合同创建一条有界真实曲线分析/补图任务，复用已封存算法和数字。默认候选/参考叠加图，坐标单位、图例、比较域和结论引用齐全；必要时残差图。不重新做昂贵拟合或仿真。
- 必须核对 **同一当次 Run**：PNG 生成 → worker_analysis_publish_files → 正式报告引用 alias / manifest 留存 → 所属轨迹节点预览 → 原图/下载字节 → 来源回到该 Run。旧 PNG 演示或静态夹具不能替代。
- 缺图可解释并补交，不能新增校验否定已有科学结果。若 UI 已具备能力，不再改 UI。

### C. 原 TDR 恢复

- Execution：`fig4_retardation_execution_20260921_1`。
- 已收集九条 PLX，实际 TDR 带 `_fps` 后缀但声明无后缀，导致原 execution failed。
- 使用既有 inspect_outputs / accept_output（以当前 describe 的准确工具名/合同为准），仅在实际路径、案例和源语句唯一对应时封存原文件。不得全局猜后缀、改名造证据或新启动 solver。
- 验证没有新的 execution / solver 重跑，旧 failed 保持，PLX 与日志不变。歧义、权限或大小限制就记录缺口，不提预算。
- 新 Run 若需要上述能力必须核实 compiled 权限；不要假定每个 Worker 都有恢复工具。

### D. 功能完成后计量

遵循 R1 的 matched Root/Worker A/B：固定 before/after 代码、配置、输入、任务、模型和计量边界，分别至少两对交替、串行执行，处理波动。历史长会话仅观察基线，不能对比新会话直接声称收益。区分请求数、窗口峰值/新增、输出、cached 累计及压缩。

## 5. 精确科学记录与已有结论

这些是历史封存结论，不因工程验收改写：

- 当前 reviewed package：`fig4_retardation_package_20260921_1`
- 原执行计划：`fig4_retardation_execution_plan_20260921_2`
- 科学骨架：`fig4_retardation_skeleton_20260921_1.output`
- 综合审查：`fig4_retardation_comprehensive_review_20260921_2.output`（pass）
- 执行：`fig4_retardation_execution_20260921_1`，已收集，solver_state failed；约107.819秒，九案例日志闭合，失败定位在TDR命名/收集。
- 初步分析：`fig4_retardation_analysis_20260921_1.output`（曾用固定浓度交点替代冻结指标，不作为最终正式评分）。
- 最终冻结指标分析：`fig4_retardation_frozen_metrics_20260921_1.output`（completed, inconclusive）。
- 九点中仅 N_T=1e20 cm^-3、K=1e-20 cm3 在六掩码全通过相对联合改善：深度误差减少约27%，宽度约15%；前后平台明显改善。
- M0剩余误差：b2 0.15446 μm、width 0.16139 μm、前平台0.03840 decade、尾平台0.02016 decade、aligned-shape RMS 1.20011 decade。
- **未充分对齐实测**；唯一通过点处于网格边界，缺数值收敛、独立材料参数与第二工况，不能确认机制或断言整个模型族无法对齐。不将守恒闭合当完整数值收敛。
- 科学后续建议是有界数值收敛核查，不盲扩粗网格；当前先完成工程部署验收，不自动启动该科学下一轮。

按需绑定的历史原件（访问名必须通过当前实例接口确认）：

- 总体目标 `fig4_continuation_objective_2`
- 用户优先级 `fig4_user_profile_shape_priority_1`
- 参考 bundle `fig4_continuation_reference_bundle_1`
- 实测 CSV `fig4_continuation_figure_materialized_1.curve_tables_002`
- 形貌旧报告 `fig4_morphology_closure_2.output`；原算法 `fig4_morphology_closure_2.output.tool_evidence_029`
- 旧对照复算脚本 `fig4_positive_time_analysis_20260920_r4_1.output.tool_evidence_001`
- 旧对照执行 manifest `fig4_positive_time_execution_20260920_r4_1.output.tcad_manifest`
- 三条旧PLX：同一 `fig4_positive_time_execution_20260920_r4_1.output.` 前缀下 `fig4_shared_contract_baseline_t480s_plx`、`fig4_finite_tau_568p53_t480s_plx`、`fig4_finite_tau_568p53_history_refined_t480s_plx`。

优先恢复已成功Run的准确输入，而不是照抄本清单全量绑定。新执行的结果/文件名通过 execution_outputs 获取。

## 6. 工程证据入口（相对项目 123/scidiscovery-e5.2）

按需读，不一次全展开：

| 文件 | 状态与用途 |
|---|---|
| `docs/plans/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_REMEDIATION_PLAN_20260921.zh-CN.md` | R1权威计划；SHA256 `37bbbb240fd64f61b3d4f6d24a6de81a79d3390d430b42709f69f840d51861d3` |
| `docs/plans/reviews/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_PLAN_R1_SOL_REREVIEW_20260921.zh-CN.md` | 计划独立PASS |
| `docs/plans/evidence/fig4-round-remediation-20260921/IMPLEMENTATION_REPORT.zh-CN.md` | 原18文件实施；同目录RELATIVE_BASELINE_DIFF.patch与BASELINE_FINAL_SHA256.txt |
| `docs/plans/reviews/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_IMPLEMENTATION_SOL_ACCEPTANCE_20260921.zh-CN.md` | 原18文件本地PASS；独立42项，峰193424KiB；原88项无原日志仅自报 |
| `docs/plans/evidence/fig4-round-remediation-20260921/p2-closeout/P2_CLOSEOUT_REPORT.zh-CN.md` | 仅3测试文件：分支合同与author v3旧断言、review负例；3+1通过，日志保留，峰169428KiB |
| `docs/plans/reviews/FIG4_ROUND_P2_CLOSEOUT_SOL_REREVIEW_20260922.zh-CN.md` | P2独立PASS；负例精确命中缺review，正例保留，无新增P1/P2 |
| `docs/plans/evidence/fig4-round-remediation-20260921/deployed-acceptance/DEPLOYED_ACCEPTANCE_SOL_REPORT_20260922.zh-CN.md` | **优先读**：部署边界PASS、三条真实链未验；同目录探针与记录 |
| `docs/plans/evidence/scientific-skeleton-author-20260920/fig4-live-20260921/OBSERVATIONS.zh-CN.md` | 科研/错误/Token过程记录；非科学原件替代品 |

部署探针：live control/approval UI active、三MCP入口正确、缺metadata拒绝；12组安装代码/角色/指南匹配；实际安装包隔离compact、配对四维诊断、semantic和manifest投影通过。峰110752KiB。

**证据限定：**部署probe/guard/hash JSON是在重启后依据子线程保留的实际functions.exec stdout转录，标记post_restart_transcription；不是当时直接落盘的原始日志。不得删除标记、伪造原日志或无理由重跑。P2原测试失败日志也保留；88项历史自报不追认。

## 7. Root 上下文与交接纪律

- 上轮Root本任务68请求，首211069/峰217709；压缩前新增6640，压缩后47742→81013（新增33271），不是压缩优化收益。分析同一Worker两Run共62请求、峰146849，峰值不能相加。
- 已知浪费：合同/指南重读、大量父链诊断展开、首轮缺算法导致第二次分析、报告多字段重复、等待更新频繁。新对话不要复现。
- 保存完整MCP响应但只输出决策字段；先处理isError再解析JSON。structuredContent优先，文本只解析一次，不两份都打印。
- run_status优先已知decision路径一次读取结论/限制/矛盾/建议及signal，completed后才解释。不要先空poll再读正文；不要读取报告全部gates只为转交。
- 工程子任务返回短结论和证据路径；不用其聊天作为科学证据。科学结果从已封存Run读取。
- 等完成通知；必要轮询有明确理由，避免重复等待播报。不要全git status、全日志、全目录输出。

## 8. 本轮接续完成标准

三条真实链逐项给出可追溯PASS或精确阻碍；同Run图表可在浏览器审阅；无TCAD重算或权限越界；随后才完成可比token测量。未验明确保留未验，不把安装PASS、本地单测PASS或单点相对改善写成整体科学/工程闭环成功。
