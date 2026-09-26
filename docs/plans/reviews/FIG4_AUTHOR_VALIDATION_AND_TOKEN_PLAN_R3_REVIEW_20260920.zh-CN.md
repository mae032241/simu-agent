# Fig4 作者验证与 token 整改计划 R3：独立工程复审

结论：**REVISE（仅 §2.3 的一处 P2 预算分支）**。未发现 P0 或剩余 P1。来源锚与身份投影的上轮设计问题已关闭；预算方案已明确选集和编码计算，但“宽松合同上界超限即拒绝”的分支会挡住常规小诊断。只需调整该分支，无需增加框架、字段表、持久账本或提前运行科研。

审查对象：`docs/plans/FIG4_AUTHOR_VALIDATION_AND_TOKEN_REMEDIATION_PLAN_20260920.zh-CN.md`。

核实 SHA256：`0fffa19fe9b47c76e3d38d908cc3ef1e2cc461af2015318a1f36651e60eb8bfc`。

本次为新的独立工程 reviewer。读取适用 AGENTS、scid-cross-boundary-review 与 karpathy-guidelines，比较 R2 快照和 R3，核对 R2 报告、指定工程证据及下列实际源码路径。未修改计划或源码，未运行测试、模型、科研 MCP、solver 或部署；唯一写入是本报告。工程证据只作历史背景，不转述为新的科学结论。以下路径均相对本仓库。

## 唯一剩余问题：P2，合同上界不能代替本次诊断必需字节量

位置：计划 §2.3 的“已知所选上界不能装入时，在启动求解前返回……缩小诊断输出的现有入口”；下一句仅在“缺少可靠上界”时收紧本次选定收集额度。

源码依据：

- `plugins/tcad_artifact/tcad_artifact/project_materializer.py:179–183` 明确 `max_bytes` 是控制生成字段；作者 raw_outputs 只声明名称、路径和媒体类型。
- 同文件 `:494–510,524–534` 将各输出上限取项目输出限额与 64 MiB 的较小者，默认项目限额为 64 MiB。该上限并不是对本次实际输出大小的预测。
- `plugins/tcad_artifact/tcad_artifact/debug_adapter.py:264–290` 将 initialization 总限额和所选单文件上限再夹至 8 MiB。一个通常声明的输出因此具有已知、可靠、但宽松的 8 MiB 合同上界。
- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:431–465,608–611` 中 deterministic 项目的 project.json 是控制生成的只读元数据；直接手改控制上限不是应推荐的常规修复入口。
- `plugins/tcad_artifact/tcad_artifact/plugin.py:390,405` 成功成果仅有 8 MiB；AttemptFile 编码见 `project_packager.py:719–735`。

可达场景：作者选择一个实际仅数 KiB 的原始输出，但其控制生成上界仍是 8 MiB。二进制按上界编码约 10.67 MiB；文本按保守转义上界同样可能超限。依 R3 的第一分支，启动会直接被拒绝。作者把网格、演化时长或输出采样缩小，仍不会改变这个控制上界。第二分支的收集夹紧仅针对未知上界，不能覆盖此常规情况。于是原本要支持的有界动态诊断可能被新增字节检查挡住，或者被迫改动生产资源声明来满足开发附件预算。

这不表示编码预算应取消；问题是将“最大许可量装不下”误当成“选定诊断无法在更小限额下运行”。也不能把真实大小尚未知的输出报成肯定可交付。

最小修订：将本次 development 收集额度的局部收紧同时用于未知实际大小和宽松合同上界超过剩余量的情形。在现有 prepare 构造 development job 的位置，按成果剩余预算、编码和控制报告开销计算可交付收集上限，保持生产项目/生产限额不变，公开有效额度及超限的明确结果。仅当固定已知必要字节已超限、没有可用余额或该所选诊断无法接受更小额度时，在启动前拒绝。实际输出超限仍保留准确事实，不截断原件、不静默删证据、不自动重跑。无需新增作者填写大小预测或额度表。

相应窄验收：一份控制上界为 8 MiB、实际很小的 fixture 能在收紧额度后启动并完整封存；超过该有效额度时准确报告缺口；真正已知不可容纳的固定请求仍在 solver 启动和预约前拒绝。新增预算计算只用于首次启动，不应改变同名轮询、已预约时间或失败不退款的既有语义。

## 上轮逐项状态

| R2 复审项 | R3 计划层状态 | 理由 |
|---|---|---|
| P1-1 工作区之外的来源锚 | **关闭** | 明确 collector 字节先建立身份，工具进程内记录为锚，内部参数传至 finalizer；报告只是副本，缺锚不恢复信任。 |
| P2-1 诊断 hash 排除项及历史兼容 | **关闭** | 显式排除附件，完整对象身份包含附件，旧缺省 canonical 字节及 attestation 兼容明确；不继承旧 review。 |
| P2-2 成功成果字节预算 | **部分关闭** | 已确定证明调用/output_names 选集、完整编码预算及不静默删证据；剩余上述宽松上界分支。 |
| 更早 P1 成功诊断跨 Run 原件可达 | **部分关闭** | 附件、只读恢复、来源和身份方案均成立；预算分支修正后即可在计划层关闭，不要求先运行科研。 |
| 更早 P1 动态验证负控不足 | **保持关闭** | §5.1 保留同 exit 0/齐全输出的正负观察，author 自主选择诊断、独立 reviewer 判断。 |
| 更早 P2 768 MiB 硬隔离表述 | **保持关闭** | §5 保留采样边界、超限停止、缺测分层；未扩张为全系统硬保证。 |
| 更早 P2 summary/detail 与 invoke 兼容 | **保持关闭** | §4 保留 detail 原件及各 executor kind 必需字段，只裁剪 summary。 |
| 更早 P2 引用缓存/全根扫描 | **保持关闭** | 本轮无缓存、无全根扫描，保留 unknown、精确错误、当前权限及计费语义。 |

“关闭”仅是计划设计已回答，不代表已实现或通过运行验收。

## 来源链的实际可实施性

`mcp_local_worker.py:609` 将每个工具的 `_tool_state` 作为 OperationToolContext.state 交给领域工具。`local_debug_service.py:119–171,211–224` 在其中保留调用、选择和响应；`:226–340` 已能直接取得 collector 的 bytes。先对这些 bytes 与控制生成报告计算身份、再写工作区副本，是局部修改。

正常提交路径是 `mcp_local_worker.py:315–316` → `RunService.submit`（`service/runs.py:615–622`）→ `_validated_candidate`（`:1160–1168`）→ `_finalize_workspace`（`:1309–1330`）。这些是同进程同步调用。`operations/workspace.py:86–102` 当前没有来源记录参数，R3 明确要新增可缺省内部参数，并穿过上述调用链；不是误称已有接口。

统一网关 `mcp_gateway.py:103–129` 按 session/thread/Run 缓存 LocalWorkerMCPRouter，并直接使用 facade.runs；独立 stdio 入口 `mcp_local_worker.py:637–674` 同样在本地构造 RunService 和 router。正常 submit 前没有 clear。清理位于打开/重附着路径 `:185,391`，重启也会失去内存；这些情况与 R3 明确的缺锚处理一致。完成结果重复提交沿既有 completed 分支返回，不必重新证明已封存对象。

同 UID native shell 不构成强敌对隔离。R3 已诚实限定为 trusted-local 控制内存与工作区文件的分离，明确不防管理员、调试器或任意进程内存攻击；这足以解决报告与输出同时被替换的本轮目标，不能包装成抵抗恶意宿主的完整证明。无须新增签名或数据库。

## 身份及交付的可实施性

`project_packager.py:668–682` 现有诊断 hash 排除 attestation/materialization；新增附件排除即可避免自引用，且要覆盖空缺省。`:1139–1145` 完整 project/package hash 与 `:1149–1177` tar/job 生成本就分开；保持前者完整身份、后者不加入诊断文件可行。package 目录身份会随完整项目改变，不能把验收误写为 job 的全部路径字节必须完全相同。

R3 已要求旧缺省序列化省略新增字段，不能只对最终 JSON 临时剔除；实现应同时覆盖 model_dump 的 python/json 及 envelope 嵌套序列化消费者。旧历史对象可读不意味着旧 review 对新附件对象有效。gap 仍只用 attempt_files，历史附件只作只读导航。这些设计已经充分，无需再增加新身份层。

## 实现验收事项，不另列计划阻断

1. `local_debug_service._candidate:343–352` 会先调用 candidate_snapshot；`mcp_local_worker.py:580–588` 又调用 validate_candidate；`runs.py:648` 使用 final_submission=False。实现来源校验时必须保留该开发快照路径：尚无完成记录不能阻止首次诊断，旧记录缺失不能阻止有意义的新诊断。可在非最终快照不封存新附件，或传入适用内部记录；不得要求作者先提交 handoff/来源表。最终提交仍按 R3 核验。
2. 模式报告目前不含准确调用名，完成响应可能因后续文件写入错误未进入 collected。实现应把被采用的模式证明与独立完成记录对应起来；只在收集和记录完整后可作来源，不能从工作区 qualified 自证。这是 R3 已声明的“准确调用/收集完成”落实点。
3. 保持 `local_debug_service.py:119–133` 同名调用绑定与轮询缓存；预算拒绝发生在 `:202` submit 和 `:211` 时间预约之前。不要在轮询时按增长后的源码重新拒绝已提交调用，也不要重置重启前的预算事实或自动恢复求解。
4. 多证明合并预算、报告/日志各自上界、文本转义、最终 handoff 与源码增长、附件正文不进入默认 metadata、reviewer 按需只读恢复，均需窄集成验收。实际超限与缺原件不能伪装完整交付，但保留诚实 implementation_gap，不建立科学数值机械门。

作者自主动态验证、独立 review、控制层权限/身份职责与生产网页审批仍分离。fixture 和工程封存通过均不证明连续边界或 J 已有效；计划也未授权部署或生产执行。本次不要求重新开展 WP2–WP4 审查或提前执行模型、solver。修正唯一预算分支后，对该文字增量复核即可。
