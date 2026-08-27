# SciDiscovery 增量上下文与修订架构整改计划

更新日期：2026-08-09

> 范围说明：本文是总体科学发现路线进入 P6 前插入的“增量上下文整改子计划”。
> 文中的 P0–P4 是子计划内部编号，不替代
> `docs/scientific_discovery_layer.md` 的总体 P1–P6。本文完成只说明增量修订基础设施
> 通过工程回归；不表示总体 P6 的部署和真实 Fig.4 科学闭环已经完成。

## 目标

本计划修复跨科学角色共同存在的四类问题：

1. PDF 文本和已核对引用不能跨任务复用；
2. 被人工退回的版本不能作为下一轮修订基线；
3. 文本型科学输出被迫借助 `worker_run_analysis` 写文件；
4. 小范围修改和审计会退化成全量取证、全量生成和全量复审。

目标不是引入隐藏的 Agent 记忆，而是在现有不可变 Artifact、任务输入策略、
transform 和独立审计边界上增加显式、可验证的增量上下文。

## 不变量

- 控制面继续拥有身份、不可变记录、任务生命周期、审批和结果注册。
- worker 继续拥有科学内容；控制面只缓存、应用确定性 patch、生成 diff 和校验。
- 被拒绝版本可以作为 `revision_base`，但不能作为 `claim_evidence`。
- 旧 Artifact 永不原地修改；修订总是注册新对象并保留父链。
- PDF 缓存和 unchanged-set receipt 不得替代来源或科学审计。
- 独立 critic/auditor 的判断不通过 patch 继承；它们针对 delta 产生新判断。

## 目标数据流

```text
immutable sources
  -> cached PDF text / frozen excerpts
  -> typed task context
       claim_evidence
       revision_base
       change_request
       prior_signal
       cached_excerpt
       unchanged_set_receipt
  -> worker full result or bounded patch
  -> deterministic apply + schema validation + diff
  -> delta review
  -> exact final approval
```

## 阶段与验收

### P0：结构化文本直接写入与失败传播

- 无附件任务允许直接使用现有 `worker_finalize(content)`。
- 带附件任务增加控制面拥有的 `worker_write_result(content)`，原子写入
  `output/result.json`，不再把长科学文本嵌入 Python `code`。
- `worker_run_analysis` 只保留确定性 Python 计算用途；参数拒绝记录
  `deterministic_analysis_rejected`，后续缺失文件不得覆盖根因。
- Codex/role prompt 根据是否存在 collections 选择 finalize 协议。

验收：文本任务不调用 Python 写结果；长中文 JSON 可直接提交；分析工具错误立即可见。

### P1：typed revision context

- 为任务输入增加与 `exposure` 正交的 `usage`：
  `claim_evidence`、`revision_base`、`change_request`、`prior_signal`、
  `cached_excerpt`、`unchanged_set_receipt`。
- 默认保持 `claim_evidence`，兼容现有调用。
- 未审批 foundation 仅在 `usage=revision_base` 时允许非 auditor 读取。
- assignment 明示用途，worker 不得用 revision base 建立新资格。

验收：被退回 foundation 可以修订，但继续不能作为已批准科学输入。

### P2：结构化 patch 与 diff

- 增加 `scidiscovery.structured-revision.v1`。
- worker 输出受限 add/replace/remove 操作；任务声明允许的 JSON Pointer 范围。
- 控制面应用 patch，使用目标对象原 schema 校验，并注册完整新对象和 diff。
- 首批覆盖 ScientificIntake、ScientificFoundation、HypothesisPortfolio、
  ExperimentPortfolio；独立审计输出不 patch。

验收：三字段修订只传 patch，不重新生成整份对象。

### P3：PDF 缓存与 excerpt set

- 以 PDF 内容、提取器 profile/version 和布局参数作为内部缓存键。
- 首次 `pdftotext` 后保存分页文本；后续页段读取复用缓存。
- 把实际引用页段登记为来源绑定的 `pdf-excerpt-set.v1`，供后续角色使用。
- 原 PDF 保留为 on-demand fallback；不自动引入 OCR。

验收：相同 PDF 的多任务只执行一次底层文本提取；来源变化自动失效。

### P4：unchanged evidence receipt 与增量审计

- 控制面为已验证的有序证据集合生成不可变 receipt。
- `evidence_auditor.revision.v1` 只接收新对象、deterministic diff、revision request、
  prior audit、receipt 和必要 excerpts。
- receipt 未变化时不重新暂存源图、overlay 和曲线表；变化时自动退回完整审计。
- 将同一模式推广到 ideator/critic/experiment_designer/diagnostician。

验收：foundation 小修改不再读取完整 PDF 和全部 CSV，且独立判断仍生成新 Artifact。

## 当前失败基线

本计划必须覆盖以下已复现问题：

- `worker_run_analysis` 的 Python `code` 超过 65,536 字符；
- 主错误后又出现 `output/result.json` 不存在，覆盖真实原因；
- 600 秒内完成 PDF 抽取后只剩 heartbeat，调度器无法区分写作与卡死；
- 人工 `revise` 后，旧 foundation 被输入资格门完全阻断；
- 三项元数据/范围修订触发 4.7 MB PDF 重读和完整 ScientificIntake 重建；
- foundation 修改后 auditor 再次读取约 9.3 MB、20 个输入和 12 张表。

## 状态

| 阶段 | 状态 | 备注 |
|---|---|---|
| 基线与计划 | 已完成 | 已记录失败轨迹并建立聚焦回归集 |
| P0 | 已完成 | 60 项聚焦回归通过；结果直写不再依赖 Python |
| P1 | 已完成 | 47 项调度/边界回归通过；usage 与 exposure 正交 |
| P2 | 已完成 | 68 项纵向/边界回归通过；完整对象与 diff 确定性生成 |
| P3 | 已完成 | 73 项聚焦回归通过；按 PDF 内容缓存并冻结页段 |
| P4 | 已完成 | 92 项跨角色回归通过；变更证据自动退回全量审计 |
| 增量链路工程 E2E | 已完成 | 全量 394 项测试通过；不含真实 solver/P6 资格 |

## 实施日志

- 2026-08-09：确认 `worker_run_analysis` 是受限 Python 执行器，不是科学推理接口；
  当前 Codex 策略强制所有 worker 使用 `worker_finalize_file`，但系统没有直接写
  `result.json` 的结构化工具。
- 2026-08-09：确认现有 `handoff_only` 只暴露 scheduler signal 且禁止读取正文，不能
  直接承担 `revision_base`。
- 2026-08-09：确认未批准 scientific foundation 在 Root MCP 调度入口被统一拒绝，尚未
  区分“作为主张证据”和“作为待修订草稿”。
- 2026-08-09：完成 P0。新增 `worker_write_result`，按是否存在 collections 分流
  `worker_finalize`/`worker_finalize_file`；修正 envelope 与 payload 大小边界；
  超长分析参数保留原始 MCP 错误并记录活动。聚焦测试 60 项通过。
- 2026-08-09：完成 P1。任务、assignment、物化目录和 context policy 均支持显式
  `usage`；未审批 foundation 仅能以 `revision_base` 绕过 claim gate，旧记录默认
  解码为 `claim_evidence`。聚焦测试 47 项通过。
- 2026-08-09：完成 P2。`structured-revision` 输出 profile 将 revision base、原对象
  schema 和允许的 JSON Pointer 路径写入任务契约；worker 只返回受限 patch。
  `scidiscovery.structured-revision-apply.v1` 验证精确父链、应用 patch、复验完整对象
  schema，并注册完整新对象和 deterministic diff。聚焦测试 68 项通过。
- 2026-08-09：完成 P3。完整 PDF 文本按内容、提取器版本和 layout profile 缓存；
  每次实际使用的页段注册为来源绑定的 `pdf-excerpt-set.v1`，可由
  `task_evidence_sources` 绑定并以 `usage=cached_excerpt` 传给下一任务。相同 PDF
  跨任务仅运行一次 `pdftotext`，内容变化自动失效。聚焦测试 73 项通过。
- 2026-08-09：完成 P4。`unchanged-evidence-receipt.v1` 仅公开本地证据标签和
  changed paths，精确对象集合保留在控制面父链中；生成收据时不读取大型证据
  payload。evidence auditor、critic、diagnostician 获得 revision context profile，
  evidence extractor、ideator、experiment designer 获得结构化修订 profile。证据声明
  变化或父链不匹配时确定性退回全量审计。跨角色聚焦测试 92 项通过。
- 2026-08-09：完成纵向回归。worker patch 提交、确定性 apply/diff、unchanged
  receipt、delta audit、PDF cache/excerpt、旧记录兼容和安装探针全部进入测试；
  全量结果为 394 passed。该结果属于工程控制链证据，不能替代总体 P6 的部署、
  真实 SProcess execution 和最终 KnowledgeUpdate/checkpoint 证据。

## 与总体 P5/P6 的关系

- 总体 P5（KnowledgeUpdate）：Schema、确定性 knowledge transform、状态投影和工程
  回归已经存在；本子计划没有重新实现 P5。它仍需在 P6 的同一真实闭环父链中被实际调用，
  才能形成本轮研究实例的知识更新证据。
- 总体 P6（部署与 Fig.4 闭环）：尚未完成。下一步应部署并重启本轮代码，然后在一个
  明确绑定的 ResearchInstance 中，从冻结 evidence/foundation 连续调度到 reviewed deck、
  execution approval、真实 SProcess、结果收集、diagnosis/validation、KnowledgeUpdate 和
  checkpoint。任何 mock 或本地 394 项测试都不能将 P6 标成完成。

## 已实现的增量操作拓扑

1. 仅修正少数字段时，调度原科学角色，输入使用 `prior_draft` +
   `usage=revision_base`，输出使用 `output_profile=structured-revision`，并声明最小
   `allowed_revision_paths`。
2. worker 通过 `worker_validate_output` / `worker_finalize` 直接提交 patch；不运行
   Python 写 JSON，也不重述未变化字段。
3. scheduler 调用 `artifact_transform` 的
   `scidiscovery.structured-revision-apply.v1`，得到完整新对象及 `.diff`。
4. 如果证据声明未变，scheduler 按 `base_object`、`revised_object`、
   `revision_diff`、排序后的 `evidence_*` 输入创建
   `scidiscovery.unchanged-evidence-receipt.v1`；大型 evidence payload 不会被 transform
   读取。
5. 独立审核角色接收完整新对象、diff、prior signal、receipt 和必要的 cached
   excerpts，产生新的判断。证据声明变化、receipt 父链不匹配或缺少必要摘录时，
   控制面拒绝增量路径，scheduler 改用全量审核。
6. PDF 首次按内容和 `pdftotext-layout-v1` 生成缓存；实际读取页段冻结为
   `pdf-excerpt-set.v1`，通过 `task_evidence_sources` 绑定给后续任务。
