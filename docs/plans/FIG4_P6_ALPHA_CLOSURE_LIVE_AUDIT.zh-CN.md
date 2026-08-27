# Fig.4 P6 Alpha 科学闭环现场审计

## 目标与边界

- ResearchInstance：`fig4_p6_clean_scientific_closure`
- 目标：从不可变论文证据开始，贯通证据提取、独立证据审计、科学基础审批、最小实验设计、TCAD deck 编写与独立复核、执行审批、仿真执行、结果诊断及适用时的确定性知识更新。
- 隔离要求：不继承旧实例的任务状态、候选结论、被拒绝版本或派生 CSV。
- 本文是控制面与架构现场记录，不制造或替代 worker 的科学输出。

## 当前进度

| 环节 | 状态 | 证据/备注 |
|---|---|---|
| 新实例创建与绑定 | 完成 | `instance_current` 返回 active，实例名称与目标一致 |
| 不可变论文登记 | 完成 | `paper_source` 已绑定，输入为 `inputs/papers/123103_1_5.0242861.pdf` |
| Fig.4 证据提取 | 完成 | `fig4_evidence_extraction.rev2` 于 737.15 s 成功 `worker_finalize_file`；主输出与 11 个附件已注册 |
| 独立证据审计 | 完成 | `fig4_evidence_audit.output` verdict=`pass`，仅接受有明确排除项的 alpha 最小实验 |
| 最终科学基础审批 | 完成 | `fig4_final_scientific_foundation_review` 由本地 UI 记录 `approve`；审批覆盖 foundation、主输出、11 个附件和审计报告 |
| 候选假设与最小实验 | 完成 | `fig4_alpha_hypotheses_revised5`、最终 full critic/audit 与 `fig4_candidate_eligibility` 均通过；`fig4_alpha_experiment_design.output` 覆盖三条候选并定义 21 个 PDE solve 与两个复用后处理 |
| Deck 实现与复核 | 暂停科学修订；reviewer 职责已在源码收窄 | 现有 review 把合理的代码/物理实现检查扩张为 Q 编码、deck-owned solver log 与大规模运行合同，诱导 15 outputs / 45 assertions 及后续新缺陷。所有未完成修订已停止且无新 project 注册。源码中的 reviewer 现只审 hypothesis/experiment→代码映射、显式逻辑 bug、必要 observable 与 invocation 兼容性；不得审科学真值/证据、补造 Q、要求 bridge-owned `tcad_log` 或扩张 output/assertion。完整 artifact-agent 回归 471 项通过；运行态重装前不恢复 review |
| 执行、诊断与知识更新 | 未开始 | exact SProcess capability 已绑定；仍须 revision reviewer=`pass`、确定性 review attestation/package、单独执行审批、production execution 与 diagnosis |

## 缺陷修复优先级（以恢复 alpha 闭环为准）

排序标准依次为：是否可能把 blocked/无效对象投影为可执行科学状态；是否直接阻断当前 deck author；是否会使调试或提交丢失并被迫从头再来；是否仅影响已完成阶段或协议易用性。

### P0：恢复 deck author 前必须完成

| 顺序 | 缺陷 | 本轮最小修复 | 验收门 |
|---|---|---|---|
| P0-1 | D12 blocked sentinel 被标 qualified | blocked handoff 分型注册；readiness/join 排除 blocked/revise 领域输出 | 当前 sentinel 不再开放 reviewer、equivalence、package 或 execution；端到端负例通过 |
| P0-2 | D11 capability 无法进入 author | active adapter 暴露脱敏 capability snapshot；控制面注册、语义绑定并投影 task-local `execution_capability` | author、review、package、production execution 绑定同一 capability digest；无示例 profile 推断 |
| P0-3 | D03 + D13 缺少可复用中间结果与真实调试平面 | 以统一 provisional CAS 保存 workspace snapshots、被拒版本和诊断；加入 task-bound `TCADDebugLease` 与 bounded direct-solver debug run | 同一 author attempt 内至少三轮真实 debug/patch 无逐次人工审批；失败 snapshot 可复用；调试结果不可满足科学 claim gate |
| P0-4 | D09 + D06 大对象内联与末端丢失 | primary 输出统一 file validate/finalize；已进入 finalizing 的验证后对象获得短且不可续期的提交宽限 | 512 KiB 项目不在 tool call 中重复内联；截止附近的已验证文件可完成注册，宽限期不能继续分析 |

P0 必须按上述依赖顺序实现。尤其不能先实现 debug run 再补 capability，也不能在 D12 未修复时继续依赖 ScientificReadiness。

### P0 执行记录

- `P0-1 / D12`（2026-08-10）：已完成。控制面现在以完成任务主输出与其 scheduler signal 的精确关联投影资格；`blocked` 与 `revise` 分别显示为 `blocked`、`revision_required`，对象仍可审计并可作为显式修订上下文，但不能进入 effective scientific kinds、普通 claim task、package/transform 或 execution。未改写历史对象，也不需要数据库迁移；现有 blocked sentinel 会被动态重新分型。聚焦回归 38 项通过，实施方完整测试 396 项通过。
- `P0-2 / D11`（2026-08-10）：已完成代码实现。active adapter 现在提供 `tcad.solver-capability.v2` 脱敏不可变 snapshot；Root 只返回无摘要的选择信息，并通过显式语义绑定冻结所选 snapshot。author、reviewer、reviewed package、job spec 与 production start 贯通同一 private-profile digest，start 前再次发现当前能力并拒绝 drift。私有 executable、environment、完整固定参数和完整 release evidence 永不进入公开 bytes；只允许管理员显式声明的 `public_arguments` 与受限 `public_release_label`，同时提供私有字段的计数/摘要。旧 v1 snapshot fail-closed。实施方聚焦与跨表面回归均通过。
- `P0-3 / D03+D13`（2026-08-10，2026-08-12 收紧）：被拒输出、显式 checkpoint 与有界诊断会冻结到 task-private provisional CAS，retry 时作为只读 prior-attempt context 重新挂载，且标签与调度输入门共同禁止其支持 scientific claim。`TCADJobSpec` 为 fail-closed v2，强制 `production|development_debug` 进入 canonical digest。2026-08-12 起 author 的唯一 runtime 工具要求显式 `mode=preflight|smoke`：控制面依据 exact release 与 solver kind 注入手册规定的参数、清空 scientific expected outputs，并把累计 wall 上限收紧为 360 s。完整 case portfolio 只能经独立 review、专门执行审批与 production bridge 运行；旧的 author-side full-study debug 语义已删除。prepare/submit/poll/collect 均不暴露 external run ID、私有 argv/env/path/credential，也不创建 Approval、ExecutionRequest、execution_result 或 task output。
- `P0-4 / D09+D06`（2026-08-10）：已完成代码实现。公开 worker 协议改为 64 KiB 有界分块写入、原子 commit、文件验证与 file finalization；成功验证先封存精确 CAS bytes，再进入不可续期 finalizing grace，最终注册不读取可变 workspace。已开始的 finalize 受固定 hard cutoff 保护，不能被普通 expiry reconcile 中途抢写；workspace mutation/deletion、token expiry、commit race 与 heartbeat 均有负例。实施方完整回归 409 项通过。

### P0 实施期集成审计补充

独立负例审计在实施过程中继续发现并关闭以下绕过，均归入原 D12/D03/D13 边界，不另造科学阶段：

- collection attachment 现在通过 `task_output_artifacts` 精确回连 producing task 的 scheduler signal；blocked/revise 主输出及其附件具有相同资格，不能把附件重新绑定为 claim、transform、execution 或审批主体。
- Root readiness、task operational resolver 与通用 approval subject resolver 共同拒绝 `scientific_claim_admissible=false`；provisional/debug 对象即使被误绑定也不能进入最终科学审批。
- 调度器不再相信调用者任意改写的 `usage`。非合格可读对象只在 context policy 对该 source 显式钉住同一非 claim usage，或 `additional_usages` 明确列出时可读；initial author/reviewer 全部钉为 `claim_evidence`，`tcad.deck-revision.v1` 才允许 `revision_base + change_request`。
- PDF excerpt/cache 已加入 task deletion 与 orphan retention 引用闭包，避免删除失败或仍被任务引用的 excerpt 被 GC。
- development debug 的输出路径、文件数、单文件与总字节均在 CAS 前验证；job 的 capability/solver/purpose 在 prepare、submit 前重复校验，租约与剩余 wall time在慢 prepare 后再次检查。
- 过期/替换 attempt 的外部 debug run 不能丢失 binding：task/instance delete/close 与 orphan cleanup 在 run 收集/回收前阻塞；worker daemon 的 token-independent bounded reconciler 负责 cancel、poll、collect、登记 development-only snapshot 并清理 exchange。

### P0 最终验证

- 主调度器完整回归：`439 passed in 57.62s`。
- 全树 `git diff --check`、Python `compileall`、`deploy/install.sh` 与 SSH runner 安装脚本 `bash -n` 通过。
- 工具/安装探针一致：Root `34`、Worker `19`、TCAD execution `5`。
- 干净 release builder 在 `/tmp` 成功生成 246 个 tracked source files；生成目录中的 `sha256sum --check MANIFEST.sha256` 通过。
- P0 代码已收口；运行态仍需重新安装/重启 control、worker 与 approval UI，随后从 active adapter 发现并绑定 v2 `sprocess|sdevice` capability，再基于当前 immutable ExperimentPortfolio 新建 deck-author 任务。不得复用此前 blocked sentinel project。

### 2026-08-10 第二轮独立自测

本轮只验证和记录，不继续扩展实现，也不制造 worker 科学输出。结果如下：

| 检查面 | 结果 |
|---|---|
| 完整 artifact-agent 回归 | `439 passed in 58.15s` |
| development-debug 聚焦回归 | 连续 3 轮，每轮 `8 passed` |
| finalizing/expiry/commit race 聚焦回归 | 连续 5 轮，每轮 `4 passed` |
| capability、资格门与 usage relabel 负例 | `14 passed, 72 deselected` |
| 静态与发布检查 | `git diff --check`、`compileall`、两个安装脚本 `bash -n` 均通过；干净 release 的 246 个文件逐项通过 `MANIFEST.sha256` |
| 源码协议面 | Root `34`、Worker `19`、TCAD execution `5`，与当前安装脚本断言一致 |
| 已安装协议面 | Root `32`、Worker `17`；control/worker/UI 从 2026-08-09 22:03 起运行，尚未加载本轮 P0 release |

关键词扫描没有发现可直接判定为未实现的 `TODO/FIXME`。多数 `pass` 是异常类型或有意的 best-effort cleanup；debug reconcile 的吞错路径则形成下述可观察性缺陷。

#### 尚未完成的缺陷与验收缺口

| 编号 | 优先级 | 类型 | 可复现证据 | 完成条件 |
|---|---|---|---|---|
| ST2-01 | 已关闭（2026-08-10） | 本地部署版本错位 | 修复前 live Root/Worker 为 32/17，worker 未挂载 command adapter；重新安装并重启后 live 探针为 Root 34 / Worker 19，control 与 worker 均含 `--tcad-command-config /etc/scidiscovery/command-adapter.json` | 已达到；外部 command-adapter 模式下本地 `tcad-control.service` inactive 属预期行为 |
| ST2-02 | 已关闭（2026-08-10） | 真实环境验收缺口 | exact v2 SProcess capability 已绑定；独立 task-bound smoke 已通过正式 worker debug、command/SSH adapter 和远端 runner 完成 prepare→submit→poll→collect，SProcess R-2020.09 在 2 GiB/8 进程资源包络下以 exit 0 结束。未直接 SSH 绕过控制面 | 已达到；该结果只证明真实执行链和最小求解器运行可用，不替代完整 Fig.4 project 的 review、production approval 与科学结果诊断 |
| ST2-03 | P1；若当前 Fig.4 实现需要 solver argv 则升级 P0 | 调试与生产调用不等价 | `TCADDevelopmentDebugBridge.prepare()` 对任何非空 `DeckProjectDraft.arguments` 返回 `development debug does not admit worker-selected solver arguments`；production packager 却执行 `(entrypoint, *project.arguments)`，debug 只执行 entrypoint | 要么为参数化 case 提供受 schema/allowlist 限定且进入 digest 的 debug arguments，要么在 author contract 中明确要求无 argv 的冻结 case entrypoint，并用测试证明 21-case portfolio 可实现 |
| ST2-04 | P1 | debug reaper 可观察性不足 | `TCADDebugService.reconcile()` 对 submit/status/cancel/collect 错误只累计 `pending`；周期线程再用裸 `except Exception: pass` 吞掉整轮错误。外部 binding 会安全保留，但持续故障没有持久化原因 | 为每个 run 持久化有界 `last_error_layer/last_error_at/retry_count`，发出不含 secret 的 lifecycle/health 事件，并测试持续 adapter 失败、恢复与退避 |
| ST2-05 | P1 | production terminal-uncollected 生命周期缺口 | `instance_close` 与实例删除只阻塞 `submitted|running|cancelling`；Execution 已到 `succeeded|failed|cancelled` 但 `adapter.collect()` 尚未成功时仍可关闭/删除，而 `execution_outputs` 只接受 `collected` | 把 terminal-uncollected 纳入 active blocker，或加入 token-independent production reaper；用 collect 暂时失败后重试成功的回归证明外部 binding 和输出不会丢失 |
| ST2-06 | P1 | 科学资格分型仍过宽 | `_NONQUALIFYING_HANDOFF_VERDICTS` 目前只有 `blocked|revise`，所以 `inconclusive` 默认仍投影为 qualified | 按 artifact kind 定义 fail-closed 规则；至少 `tcad.deck-project`、review/package/execution 路径不得把 inconclusive 当可执行通过，同时保留诊断报告的合理可消费性 |
| ST2-07 | P1/P2 | 原子性与维护债务 | sealed output 或 provisional snapshot 的 Artifact/CAS 登记可能先于最终 task-state 事务失败，留下未绑定 registration 或消耗 sequence；资格门安全，但维护依赖后续 orphan GC | 加入故障注入与确定性补偿/GC 回归，证明 registration、task state、snapshot sequence 的最终一致性 |
| ST2-08 | P2 | 兼容协议仍可私下触达 | inline `worker_validate_output`、`worker_write_result`、`worker_finalize` 已从源码公开列表移除，但 router 仍保留 compatibility aliases；当前旧部署还把它们公开列出 | 完成迁移窗口后删除或强制拒绝私有 aliases，并验证所有角色只走 chunk/file 协议 |
| ST2-09 | 已关闭（2026-08-10） | 本地/远端 runner 协议版本错位 | 远端当前 runner 已通过 `install-from-transport` 安装；Root 正式 `execution_capabilities(executor="tcad")` 返回两个脱敏 v2 capability，不再出现 `unknown runner tool` | 已达到；真实 solver smoke 由 ST2-02/ST2-12 跟踪 |
| ST2-10 | 已关闭（2026-08-10） | 远端部署流程曾偏离安装教程 | `install-from-transport` 继续以忽略 Git 的私有配置为权威输入，复用 active transport，候选 runner+config 自检后成对提交且支持失败回滚；正式安装已成功。`upgrade-code` 仅保留为当前 schema 的窄维护模式。所有写 VM 的模式要求显式私有配置并拒绝 tracked example；聚焦回归现为 `38 passed` | 已达到 |
| ST2-11 | 已关闭（2026-08-10） | 远端 v1 私有配置迁移 | VM 旧 profile 的 `arguments/environment` 被原样保留，真实 `sprocess` 与同安装目录 `sdevice` 均在 VM 上验证为可执行普通文件；本地私有配置以 `0600` 原子写入且未打印私有环境值。候选及提交后 capability 自检均通过 | 已达到；release/license 的运行资格由 bounded smoke 继续验证 |
| ST2-12 | Fig.4 所需 SProcess 已关闭；SDevice smoke 与多求解器编排 P1 | SProcess/SDevice 双能力 | VM 私有配置显式登记两个 profile；Root 返回 `sentaurus-sprocess-r2020.09:sprocess` 与 `sentaurus-sdevice-r2020.09:sdevice`。SProcess 已由 task-bound smoke 真实启动并 exit 0；本轮 Fig.4 只绑定 SProcess，因此 SDevice 未实跑不阻塞当前闭环 | 后续 SDevice 研究单独完成 bounded smoke；若研究必须串联 Process→Device，则使用两个 capability-bound project/review/execution 单元，再评估复合项目 schema |
| ST2-13 | adapter preparation 分支已修；真实 smoke P0 | debug preparation 丢失最早失败原因 | capability-bound author rev2 在 adapter prepare 前只得到通用拒绝；固定 allowlist `preparation_reason_code` 已覆盖 adapter preparation 异常并完成重装。rev3 的失败发生在更早的 project-output validation 分支，因此没有进入该映射，也没有证明 adapter/solver 成功 | rev4 的 schema-complete candidate 必须越过 output validation；随后以固定 reason code 或真实 submit→poll→collect 结果验收 adapter preparation 分支 |
| ST2-14 | 已关闭（2026-08-11） | finalized `revise` deck 无法作为下一轮 author 上下文 | `tcad.deck-author.capability-bound.revision.v1` 已安装并在真实链连续工作：每轮 assignment 挂载 exact prior project、同一 capability/plan/hypotheses 与限定审计输入；worker 先原样 replay，再只改最早失败 locator。rev10 最终对象仍完整保留 42/42 realization manifest、48/48 parameter bindings 与 11/11 输出/assertion 合同，下一轮 rev11 直接读取该对象，不再重建证据、实验设计或完整 deck | 已达到；默认 initial author、reviewer、package 与 execution 资格门未放宽，`revise` 仍不能越过独立 reviewer |
| ST2-15 | 运行态已安装；真实 attempt 复验中 | debug 的项目校验拒绝缺少有界可操作诊断 | author rev3 首次 debug 只收到 `staged TCAD project did not pass output validation`，被迫调用会封存候选的最终 validator 才定位 `$.payload.realization_manifest.29`；修正后任务已进入 finalizing，无法再 debug。源码现返回固定 `project_output_validation_failed`、首条 path/type/message 与总错误数，响应限制在 1 KiB 内，完整诊断仍保存在 provisional snapshot；新增真实状态机回归证明拒绝后仍为 claimed，可覆盖修正版并换 run_name collect。debug/adapter/deploy 聚焦 `35 passed`，完整 artifact-agent 回归 `448 passed`。2026-08-10 17:23 CST 重装后 control/worker/UI active，安装树已确认含新 reason code；rev4 attempt 2 已从 provisional context 重试 | 用当前真实 attempt 确认 worker 可在不 seal 的情况下修补并换 run_name 重试；不得再因获取诊断而提前结束 debug 生命周期 |
| ST2-16 | 测试已修；生产语义未改 | 1 秒 session expiry 回归存在亚秒时序抖动 | `test_expired_worker_token_can_only_finish_previously_sealed_bytes` 在完整回归及 5 次复跑中可分别先命中 token `expired` 或 finalizing 状态的 `not the active claimed attempt`；两者都拒绝 seal 后 heartbeat，且 `worker_finalize_file` 仍只提交既有 sealed bytes。原断言只接受前一文案，形成非确定 CI 失败 | 断言接受两种合法 fail-closed 顺序，并继续要求 expired/finalizing 后只能 finalize 已封存 bytes；不得放宽生产状态门 |
| ST2-17 | 源码已修；运行态待安装 | adapter prepare 的未知异常仍退化为泛化码 | rev4 attempt 2 已真实证明 schema-complete candidate 越过 output validation，但 adapter prepare 只返回 `adapter_preparation_rejected`。标准库 probe 排除 USTAR 路径长度（唯一文件 `fig4_alpha.cmd`，14 bytes）；analysis sandbox 未安装 `tcad_artifact`，无法在 worker 内复演 packager。源码现把 capability discovery、exchange setup、project packaging、archive path 与 debug-job materialization 映射为五个固定公开码，原始异常只留作 cause；注入私有 transport/path 文本的负例确认响应不泄漏。development-debug/command-adapter/deploy 联合回归 `41 passed` | 重装 control/worker 后在仍 active 的 rev4 attempt 2 中换 run_name 重试；必须得到具体固定阶段，或进入 submitted/running/collected |
| ST2-18 | 已关闭（2026-08-10） | control/worker systemd 地址族不一致阻断 Windows SSH transport | 独立最小 SProcess smoke 首轮稳定返回 `capability_discovery_failed`；Root/control 同时能发现 exact capability。两服务使用同一 command adapter，但 worker 未允许 WSL Windows `ssh.exe` 所需的 `AF_VSOCK`。模板补齐后，smoke rev2 两个 run_name 均完成 prepare→submit→poll→collect，并实际启动 SProcess R-2020.09 到 syntax check | 已达到；两轮均无 preparation reason code，证明 capability discovery 和 transport 已越过 |
| ST2-19 | 远端已升级；本地源码待下次常规安装 | development debug 丢失 solver 自有 parser log | 远端 runner 已通过官方 `upgrade-code` 路径升级且私有配置摘要保持不变；development debug 会有界合并 solver 自有 `.log`，production 不变。随后 2 GiB/8 进程 smoke 真实 exit 0，因而没有 parser error 可用于验证 token/line 回传；完整 Fig.4 author rev5 将继续验证实际错误诊断。当前本地 command-adapter 只转发远端结果，未重装本地同等实现不阻塞该路径 | 完整 author 若出现 parser/initialization 失败，必须返回可修正的有界 solver 日志；本地下次常规安装同步代码，禁止为补日志改变 production 输出合同 |
| ST2-20 | 源码已修；运行态解释需兼容旧分类 | 成功运行被无害日志文本误分为 parser | smoke rev4 的外部终态为 `succeeded`、exit 0，但旧本地分类器因日志包含 `Checking syntax` 抢先标记 `parser`。源码已改为 terminal/exit 0 优先判定 complete，非零 signal 判为 runtime，再对失败日志分层；聚焦回归 `65 passed`，最新完整 artifact-agent 回归 `459 passed in 59.43s` | 下次本地安装加载新分类器；在此之前 scheduler 以外部 terminal state 与 exit code 为准，不把 exit 0 的语法检查文本伪装成失败 |
| ST2-21 | 被 ST2-32 取代（2026-08-12） | debug 默认资源包络不足且预留计费妨碍双 replay | 此前通过放宽 author debug 到两个完整 21-solve replay 来解决吞吐，虽未放宽 production approval，却令 author 实际执行了完整科学实验并把调试与生产边界混在一起 | 不再为 author 增大 full-study debug 资源；采用手册规定的 preflight/smoke 固定模式，完整 study 只走 review+approval+production execution |
| ST2-22 | P0（当前任务吞吐） | 长 author 没有可强制执行的早期增量持久化门 | `fig4_alpha_tcad_deck_author.rev5` attempt 1 在 1800 s 内完成 121,788 bytes 输入读取并持续 heartbeat，但直到绝对截止只有 `input_read/heartbeat`，无 upload/commit/debug/validation/checkpoint。rev6 attempt 1 按 prompt 在 34 s 冻结 schema skeleton；随后 worker 报告 914 行完整 deck 已在模型内成稿，却在余下约 29 分钟内仍未再次写入/commit，最终同样自动 `timed_out`。attempt 2 确认 prior checkpoint 被正确挂载，但只有 1026-byte envelope、capability/资源字段和占位 `.cmd`；11 outputs、bindings、assertions、manifest 与 914 行正文均未进入 CAS。这证明 retry 机制正确，而仅要求“早期 checkpoint”不能保证后续大段内容被增量持久化 | author 合同/worker lifecycle 应设置可执行阶段门：claim 后 300 s 内 commit schema-valid skeleton，此后每个有界生成阶段（source file、bindings/manifest、outputs/assertions）必须单独写入或刷新 checkpoint；长期仅 heartbeat 无写入时提前停止并封存 workspace。retry 必须挂载并要求先复用 prior checkpoint；不得重跑证据链或改变不可变科学输入 |
| ST2-23 | 资源分类源码已修；Tcl 子层仍 P1 | debug 诊断层把资源终止或 SProcess Tcl 执行错误粗分为 `parser` | rev13 的远端 `wall_time_exceeded` 因 manifest 遗留 exit 99 且日志含 `Checking syntax` 被误分为 parser。源码现令远端 wall/process 超限稳定返回 124/125，并在日志关键词前优先投影 `resource_limit`；聚焦负例与完整回归通过。数组缺键、空字符串算术和 math domain 等 Tcl evaluation 仍统一落入 parser | 安装后以 120 s 旧 candidate 确认公开层为 resource_limit/exit124，再以 480 s 重跑。后续再细分 syntax/parser 与 Tcl evaluation/runtime；不得因细分泄露私有路径/环境 |
| ST2-24 | P1；当前以 revision profile 绕过 | release-matched deck 预检仍不能覆盖高频 Tcl 数据流错误 | 当前 exact capability 的远端 debug 能定位首错，但数组 existence、空 scalar、tag/value 跨 procedure、log-domain 等错误仍需逐次占用真实 solver run。现有静态 validator 只证明 project schema/manifest/合同完整，不能在提交远端前捕获这些版本相关 Tcl 数据流错误 | 为已绑定 SProcess release 提供只读、无许可证副作用的 release-matched Tcl/command preflight 或管理员验证过的最小 helper 库；至少对数组 composite key、finite/log-domain、availability/value 分离和输出 emit 路径做确定性检查。它只能减少工程迭代，不能替代真实 debug、独立 review 或 production execution |
| ST2-25 | 已关闭（2026-08-11） | DeckProjectPatch 无法表达 reviewer 合法要求的 output/assertion 修订 | patch v1 的两个受限完整集合替换字段已安装。完整 reviser 输出通过 worker dry-apply validation；确定性 apply 又以完整 `DeckProjectDraft` validator 复验输出名/路径唯一性、路径安全、assertion→output 引用和 manifest output 引用，并成功生成 complete project+diff。旧部分补丁保持非合格且未被消费 | 已达到；当前 revised project 已进入独立 revision reviewer，后续 package 仍必须依赖 reviewer pass |
| ST2-26 | P1（吞吐）；本轮再次复现 | reviewer/reviser 仍把写入推迟到绝对截止，且 worker 编排环境能力不可预发现 | reviewer 做18次确定性分析并在600 s 截止前约36 s才首次写11 KiB结果；full reviser attempt1 虽构造 137,801-byte 完整补丁，却在三段上传后、commit 前到期，只留下 545-byte skeleton。attempt2 又到第12分钟才 commit；其首次完整上传还因 JS isolate 不提供 `TextEncoder` 在任何 worker write 前失败。去除无关字节探针后，122,355-byte candidate 才成功 commit/checkpoint，并在截止前约2分钟完成 validation/finalization。科学资格始终 fail-closed，但两次重建和临界提交显著增加闭环成本 | 为 reviewer/reviser 增加可执行阶段门：读取完成后180 s内写 schema-valid verdict/patch骨架；完整内容按字段阶段增量写入并 checkpoint。assignment 应公布 worker 编排运行时的可用标准能力或提供官方 UTF-8 byte helper，禁止模型用环境不存在的 `TextEncoder` 做非必要探针。没有完整候选时不得把 skeleton 当完成结果 |
| ST2-27 | P0（当前 revision apply） | worker patch validation 与正式 exact-base transform 不一致 | `fig4_alpha_tcad_deck_revision_patch_review2` 的完整 `DeckProjectPatch` 在 worker 侧返回 valid=true、finalized、scheduler signal=`pass`；随后对同一 frozen base 调用正式 `tcad.deck-project-apply-patch.v1`，完整 `DeckProjectDraft` validator 拒绝：某 implemented realization locator 不存在于替换文件。失败补丁未生成任何 revised project，资格门安全，但已完成 task 的 pass 信号为伪阳性，且新任务无法自动读取该失败 patch，只能从 base+review 重建 | worker finalization 必须调用与 Root transform 同一 `apply_deck_project_patch(base, patch)` 与完整 target validator，并把 assignment 的 exact `revision_base` 绑定到 validator；增加“patch schema 合法但 replacement manifest locator 在 replacement file 中不存在”的 E2E。完成前任何 patch task 的 pass 只能视为候选，必须以正式 transform 成功为准 |
| ST2-28 | 源码已关闭；运行态待安装 | deck reviewer 将代码审查扩张为非来源支持的输出/控制面合同 | 合理检查限于 hypothesis/experiment→代码映射、显式语法/控制流/索引/初始化/data-shape/availability/numerical-guard bug、必要 observable 与 invocation 兼容性。旧 prompt 额外要求逐项 output existence/nonempty/parser/finite/scientific-threshold gate，并宣称替代 physical-model reviewer，实际诱导未定义 Q、deck-owned solver log、15 outputs / 45 assertions。源码现明确禁止 adjudicate 科学真值、审计 evidence provenance、qualify runtime result、新增 outputs/assertions/provenance/Q；`tcad_log` 明确归 execution bridge。requirement review 只覆盖 project 已有、由 supplied design 支持的 manifest，不得新增 reviewer-originated requirement。新增正/负 prompt contract；聚焦37项、完整471项通过 | 重装 control/worker 后，用最后一个真实 exit0 的项目重新派独立 code review；验收要求：仍能捕获 CSV 列冲突、数组/分支/zero-L 物理映射 bug，但未定义 Q、bridge log、额外 provenance/output/assertion 不得单独形成 blocker/major 或扩张 revision scope |
| ST2-29 | 运行态已验证；重试风暴关闭，易用性转 ST2-30 | MCP patch 的绝对行位与 agent 旧快照策略造成 context-mismatch 重试风暴 | 安装后的真实 revision attempt 不再盲目连续重试：2 次 broad patch 被原子拒绝并计入 `worker_file_patch_rejected`，重新读取并缩小 hunk 后 2 次 patch 成功，文件未被错误覆盖。声明位置优先、唯一上下文重定位及拒绝计数均按设计生效 | 已达到安全/可观测目标；错误诊断和首次写入吞吐缺口单列 ST2-30。科学 `revise` 本身不放宽 |
| ST2-30 | 源码已修；运行态待安装 | patch 拒绝诊断过粗且 revision author 首次写入过晚 | `fig4_alpha_tcad_deck_author_revision_filesystem_rev2` claim-to-finalize 824.13 s，前约 10 分钟只有读取/heartbeat；首次 broad patch 直到接近 deadline 才调用，2 次仅得到 context mismatch，最终在人工收紧边界后才以两个小 hunk 成功并完成 valid/finalized，但没有取得 terminal debug，仅完成 B=0 direction 修复。源码现保留严格/原子 patch 语义，在 `context_not_found` 返回 target SHA、声明行、首个 expected/current 差异行，在 `context_ambiguous` 返回有界候选行；每条诊断最多 2048 bytes。revision assignment 新增 `first_checkpoint_seconds=180` 与最小 change 策略，author prompt 要求 180 s 内做一个小 patch+checkpoint，或 unchanged fail-close checkpoint，禁止在内存中规划多问题大补丁 | 重装后从本轮 completed `revise` 输出继续；验收为 180 s 内出现 patch/checkpoint，拒绝信息可直接定位且不得原样重试，必须为 debug/validate/finalize 预留时间 |
| ST2-31 | 源码已关闭（2026-08-12）；运行态待安装 | TCAD skill 缺少 exact-release 官方用户手册，release-specific 语法只能依赖记忆或逐次真实运行 | 已从当前合法 R-2020.09 runner 安装读取 SProcess UG、SDevice UG 与 release notes，放入 `sentaurus-tcad-code/references/manuals/R-2020.09/`；catalog 固定 release、solver kind、页数、字节数与 SHA-256。新增 bounded search/extract helpers，每次先校验完整手册 hash，最多返回20个命中或20页/128 KiB；skill 要求实现理由引用 title/release/PDF page/manual SHA，缺册或 hash 错误时 fail-closed | 已达到源码门：安装/release builder 携带三份 exact manual、catalog 与两个 helper；hash、search、page-bound、安装源和 clean release 回归均包含在本轮聚焦74项、全量494项通过中 |
| ST2-32 | 源码已关闭（2026-08-12）；运行态待安装 | author development debug 错误执行完整 21-case 科学实验，越过 author 的工程预检职责并造成长时间阻塞 | Worker API 新增必填 `mode=preflight|smoke`，run name 与 mode 一次绑定；adapter 不接受 worker argv，按 R-2020.09 手册固定映射 SProcess `-s/-f`、SDevice `-P/-i`，分别限60/180 s并清空 scientific expected outputs；公开 release label 没有 exact R-2020.09 合同时固定返回 `release_mode_unavailable`。`prepare_submission` 重新解析 job 并拒绝任意其他 argv、非空 expected outputs 或非-development purpose；assignment 与 role prompt 不再宣告 generic full debug | 已达到源码门：四个 solver/mode 映射、非 exact release/full-mode 拒绝、空 scientific output 合同、run-name/mode binding、成功无输出 preflight 与生产 job digest 分离回归均通过；完整 case portfolio 只能走独立 reviewer、execution approval 与 production bridge。本轮聚焦74项、全量494项通过 |
| ST2-33 | Deck revision 处理中（2026-08-12） | `shapeWidth` 安全快照只校验键值对外形，空数值仍流入 `finiteValue` | 连续修订后，最新受控文件静态确认 A0/A1 width-comparison block 中直接 `shapeWidth(...)` 复合键读取为 0、`array get shapeWidth <key>` 为 2；真实单次 preflight 不再复现旧 missing-key 错误，而推进为 `finiteValue $coarseWidthValue` 收到空字符串。由此排除旧 workspace/debug 快照假设，并确认 availability/value 契约缺少非空有限数门控 | 当前 bounded revision 只允许在同一 locator 增加 exact-pair + nonempty + finite gate；缺失、空、畸形或非有限值必须走既有 unavailable/reason，禁止 0/NaN/epsilon/imputation。一次 preflight 后无条件 validate/finalize；不得扩张物理、case、mask、threshold、output 或 assertion |
| ST2-34 | P1；运行态行为已复现 | SProcess R-2020.09 `-s` 仍执行 deck 的 Tcl 控制流和结果依赖后处理 | 最新 preflight 虽由控制面固定为 `sprocess -s` 且没有 production output contract，却仍打印全部 `SOLVE_COMPLETED` 路径并进入 shape-width 后处理。它不构成 production scientific execution，但证明“syntax-only”不等于“不执行 deck 级 Tcl 数据流”，因而会放大 author 预检耗时并依赖尚未产生的结果状态 | 为 author 项目提供显式 preflight-friendly 控制路径或最小独立 entrypoint：只解析/初始化必须的命令与 helper，跳过 case portfolio、结果读取和科学后处理；保持 capability-bound 固定 argv，不能由 worker 任意选择参数。增加真实 R-2020.09 回归，证明 preflight 不遍历完整 case portfolio且仍能捕获 Tcl/parser 错误 |
| ST2-35 | 源码已关闭（2026-08-12）；运行态待安装 | author 只能从通用 log 自行猜 locator，且 worker patch 与原生 Codex patch 语法不一致 | 最新 revision 在同一局部修订中出现 4 次成功 patch、2 次 malformed unified-diff 拒绝；debug 只返回 layer/summary/log excerpt，未机器化返回当前 entrypoint、solver-reported line、procedure、首错与 failing command，迫使 scheduler 逐轮翻译诊断。源码现让 collected debug 返回有界 `source_diagnostic`，并让 `worker_file_apply_patch` 原生接受 `*** Begin Patch` / `*** Update File` / count-free `@@`，旧 unified diff 仅兼容保留；target mismatch、stale/ambiguous context 仍原子拒绝。author prompt 要求先按结构化 locator 读取当前文件并自行修最早错误 | 聚焦 worker lifecycle、debug、角色契约与 Codex 配置回归 `90 passed`；重装后用 ST2-33 最新 complete revision 验收：返回 source path/line/procedure/message/command，且同一局部修订不得再出现 hunk-count rejection。结构化 locator 只是可操作提示，patch 前仍必须重读当前 task-private 文件 |
| ST2-36 | P0 源码边界已关闭；运行态迁移待重装 | SProcess deck 承担了确定性 scorer 与控制验证职责，形成 1536 行单体 Tcl | 运行态静态分解：solver setup + 21 cases 约 413 行，profile/resampling 约 262 行，scientific metrics 约 772 行，CSV/readback 约 181 行，traceability/status helpers 约 199 行（共享 helper 导致区段重叠）。连续的数组、catch/value-channel 和 status 错误主要发生在内嵌 scorer/验证层，而非物理求解层。最终 package 暴露唯一 `unsupported` 行 `observable.observed_scope`：它是“eligible-row=0 时禁止观测计算”的科学门禁，却被错误写入 deck manifest；结构 reviewer 先 pass、package 才拒绝 | 新 author 合同对直接 SProcess/SDevice 硬拒绝 unsupported manifest、author runtime assertions 和非 TDR/PLX/PLT/log 输出；revision 只可清除旧越界职责，保留越界项时不得 pass。reviewer finalization 新增 exact-project contextual validator，package 同样拒绝后处理职责。role/scheduler/skill/local validator 均明确：重采样、mask、crossing/width/direction/identifiability、阈值、observed eligibility、CSV/JSON 指标和科学 verdict 属于版本化领域 scorer/diagnosis。重装后须从最后项目做一次职责剥离 revision，冻结原始 solver outputs，再实现/调用外置 scorer；不得继续修内嵌 Tcl scorer |
| ST2-37 | P0 源码已关闭；待重装做真实纵向资格（2026-08-13） | 控制层 SProcess materializer 硬编码材料、状态变量、边界与 PDE 语法，侵入 author/reviewer 职责 | 旧 materializer 生成 `study.cmd` scaffold，解析 `Zinc/InGaAs/pdbSet/EquationProc`，并从命令猜 realization；debug adapter 又重写 production deck 生成初始化 probe。真实 production 因计划中的自定义浓度状态被强制映射为 built-in `Zinc` dopant，触发 `_AlloyCompound::DopantBulk` callback 初始化失败。随后 reviewer 被要求逐项审核控制层生成的 realization rows，无法修正这一本体边界错误。当前已替换为 solver-neutral declared-source v2：author 写完整源码、case anchors、raw output 路径和可选独立 init entrypoint；控制层只做路径/集合/值单位/完整性/资源/收集验证，生成 plan bindings 但不解释 locator；v2 realization manifest 为空；reviewer 做完整代码的整体 fidelity/findings 审查，不填 requirement rows；package 对 exact source/declarations 重物化。生产控制路径的物理 token 负例、author/debug/review/package 聚焦 129 项均通过；全量首轮 559 通过、3 个提示词契约失败已修正 | 重装后从 exact experiment plan 新建 author，不复用旧硬编码项目；先验证 materialization/preflight，再独立 code review、package、production。若 solver 初始化仍失败，只能由 author 根据 exact manual/log 修 solver code，禁止把状态名或方程规则加回控制面 |

### 当前 Deck 实现缺陷（独立 revision review）

- `joint_identifiability.csv` 的写出合同为 8 列，但 readback verifier 使用不兼容的 6 列 schema；这是确定性 runtime-abort 缺陷，不是格式上传或控制面转换错误。
- 当 L mask support 为零时，方向诊断必须整体 unavailable/inconclusive；不得以仅 H mask 的数值方向替代，否则会把缺失比较支持伪装为可评价输出。
- 主数值、输出、support gate 尚未完整覆盖冻结实验计划；修订必须逐条保持适用 gate，并对不适用项给出显式 unavailable reason。
- Q/segment identity 只能来自已有定义；没有合法 Q 编码时必须显式 unavailable，不得临时发明身份。solver-native log 路径必须能从 exact direct-SProcess invocation/output contract 追溯。
- 上述缺陷属于 deck 实现与合同一致性问题。控制面已正确阻止 reviewer=`revise` 的项目进入 package、执行审批和 production execution。
- 第二轮 patch 虽在 worker 侧通过，却因替换后的 manifest locator 不在 `.cmd` 中而被正式 exact-base transform 拒绝；这是 patch validator 集成缺口，已单列 ST2-27。该补丁没有生成 revised project，也未进入后续科学链。
- reviewer 的合理边界不是要求“越多输出越好”。本 alpha 闭环只需要证明预注册判据可计算、运行完整且失败时 fail-closed 的最小数据合同。实验计划未定义的 Q 编码和 execution-bridge 自有日志不得由 deck 补造；宽泛请求诱导的 15 outputs / 45 assertions 扩张已单列 ST2-28。

本轮结论是：控制面、worker、command/SSH adapter、远端 runner 与 SProcess R-2020.09 已完成一次真实 task-bound 最小运行；当前硬门已从基础设施连通性转移到完整 Fig.4 project 的 author debug、独立 review、生产审批、production execution 与 diagnosis。`tcad-control.service` 在 command-adapter 部署中 inactive、`/run/scidiscovery-tcad/control.sock` 不存在本身不是故障，因为该部署选择的是外部 command/SSH transport。

### P1：P0 后立即修，允许与首次 author/reviewer 回归并行验证

| 缺陷 | 优先级理由 | 验收门 |
|---|---|---|
| D07 structured revision 未 dry-apply | 会注册不可应用的科学 patch，属于对象正确性问题；当前 hypothesis 已绕过，但后续设计修订仍可能复发 | validate/finalize 在 revision base 上 dry-apply 并验证完整目标 schema |
| D10 隐藏跨字段 invariant/canonical 大小 | 已造成 10 次拒绝和 829.75 s 任务；不会阻断现有 final design，但会持续放大新复杂角色输出 | assignment 提供 invariant manifest；file preflight 返回 canonical bytes 与有界错误 |
| D04 末端才首次预检 | 与 D09/D10 叠加会再次耗尽长任务预算 | 主 envelope 早期预检；记录 build/validate/finalize 分段耗时和剩余预算门 |
| D08 delta review 无法合并 | 违背增量上下文目标并迫使全量复核；当前 eligibility 已通过，故不应阻塞 deck author | deterministic review-chain consolidation 验证 parentage 并覆盖 final object 每一项 |

集成审计新增但不阻塞本轮 alpha author 的 P1 项：

- production execution 处于 `succeeded|failed|cancelled` 但尚未 collect 时，`instance_close` 仍可能关闭实例；应把 terminal-uncollected 视为 active，保留可重试 collection。
- `inconclusive` handoff 当前仍按 qualified 投影；需要按 artifact kind 明确规则，至少 operational TCAD project 应 fail-closed，而不是把“未得结论”默认为可执行。
- sealed finalization 在最终 task-state 事务前登记 CAS Artifact；hard cutoff 竞态可能留下未绑定 registration。资格安全不受影响，但应把该窗口纳入确定性 orphan cleanup/补偿事务测试。

### P2：alpha 闭环恢复后处理

| 缺陷 | 延后理由 |
|---|---|
| D01 task input `usage` schema 未显式导出 | 有明确绕过，不改变科学状态，也不阻断当前 author |
| D02 evidence source/attachment 边界示例不足 | evidence 集已合格并审批；属于合同可发现性改进 |
| D05 `worker_run_analysis` 120 s 上限发现过晚 | 单点、低成本修复且有明确绕过；当前 deck 路径不依赖长 analysis call |

集成审计新增 P2：兼容期 inline worker validate/write/finalize 虽已从公开 tool list 移除，仍可由旧调用方触达；alpha 稳定后应正式退役。provisional registration 失败时可能消耗 sequence 并留下待 orphan GC 的 CAS registration，也应在维护轮统一清理。

本轮不顺带扩展通用 SDevice、多机调度、许可证管理或与 Fig.4 alpha 无关的局部安全重构。修复 P0 后继续复用当前 instance 的 final evidence、revised5 hypotheses、candidate eligibility 与 ExperimentPortfolio，不重跑已完成科学阶段。

## 已发现缺陷

### P6-D29：控制面捕获的生产 solver stdout 未进入 runtime-attestation/scorer 父链

- 触发：P0-E 的 exact reviewed package 完成一次真实 production execution；`execution_outputs` 只登记控制面名称 `tcad_log` 与 `tcad_manifest`，而 materializer 将 deck 的原生日志声明为 `solver_log/study.log`。
- 实际行为：runner 的 runtime manifest `outputs=[]`，因此 `tcad.runtime-attestation.v1` 不能以 `output__solver_log`校验日志；不带日志虽可生成 attestation，但 `scidiscovery.curve-score.sprocess-log.v1` 随后以 `runtime_attestation was not produced from the exact solver_output` 拒绝。求解已收集且 control-equivalence 可通过，但确定性评分父链无法闭合。
- 预期行为：materializer 应明确声明 solver log 的捕获模式；production runner 把同一次受限进程 stdout 原子投影为 manifest 中的 solver-native/transport-captured `solver_log`，并继续保留 `tcad_log` 作为控制面诊断副本。runtime attestation 必须以 exact `solver_log` 为父输入，scorer 随后复用该 Artifact，不允许 agent 抄写或重新生成日志。
- 可复现证据：执行 `fig4_alpha_materialized_tcad_execution_p0e` 已 collected；不带 payload 的 runtime attestation 成功，但 curve-score exact-parent gate 拒绝；新回归 `test_production_process_log_is_collected_as_a_declared_output` 在修复前因 collect 仍查找 `work/run.log` 而失败。
- 影响：这是 alpha 科学闭环 P0 阻断项；不是 TCAD 通信、deck 物理实现或 agent 输出问题。若绕过 parentage gate，会让评分报告失去对 exact runtime bytes 的可追溯性。
- 修复：为 `ProjectExpectedOutput/ExpectedOutput` 增加 `capture=workspace_file|process_log`；materializer 的 `solver_log` 固定为 `process_log`；本地及 Python 3.6 远端 runner 对捕获字节执行大小门并原子投影到声明路径，随后沿既有 manifest/collect 登记。90 项 materializer/runner/packager/SSH 聚焦测试通过。
- 迁移：本修复不能回写已收集运行的 immutable manifest；安装新版本后须基于同一 reviewed source/review/capability/plan 重新运行 deterministic package transform，并创建新的 production ExecutionRequest 与独立授权，不能把旧 `tcad_log` 手工重绑定为 `solver_log`。package transform 只允许旧对象默认的 `workspace_file` 到控制层生成的 `process_log` 这一项迁移，输出使用重新物化的 project；任何其他差异仍失败关闭。

### P6-D30：runner 把求解器内部子进程误判为资源违规

- 触发：带 `capture=process_log` 的新 production ExecutionRequest 到达远端 SProcess R-2020.09；控制物化器为作业生成兼容字段 `max_processes=1`。
- 实际行为：SProcess 已正常启动并到达 `Checking syntax of study.cmd:`，但 runner 扫描整个进程组，发现正常求解器子进程后主动终止作业；manifest 为 `terminal_state=failed`、`exit_code=125`、`error=process_limit_exceeded`，声明的 `solver_log` 尚未来得及投影。
- 预期行为：runner 负责启动、等待、超时/取消时终止整个进程组，以及采集返回码和声明输出；它不解释 SProcess 的内部进程拓扑，也不根据子进程数拒绝合法求解器运行。
- 影响：这是继 D29 后暴露的 production-only P0 阻断项。author preflight 已通过不矛盾，因为 preflight 与 production 使用不同执行生命周期；该误杀不构成 deck 代码或 TCAD 通信失败证据。
- 修复：本地 worker 与 Python 3.6 远端 runner 均删除进程组计数和 `process_limit_exceeded` 分支，只保留墙钟/CPU/内存/文件大小限制及进程组级取消清理。`max_processes` 为避免 wire schema 迁移暂作兼容占位，明确不再执行。
- 验证：新增本地及远端回归，均在 `max_processes=1` 时启动一个子进程并要求成功；完整 artifact-agent suite 为 562 passed。旧失败 execution 保持 immutable，升级远端 runner 后必须创建新的 production ExecutionRequest 复演。

### P6-D01：`task_schedule.inputs` 的 MCP schema 未暴露 `usage` 枚举

- 触发：调度器按科学语义提交 `usage="primary_source"`。
- 实际行为：Root MCP 在运行期拒绝，错误才列出允许值 `claim_evidence | revision_base | change_request | prior_signal | cached_excerpt | unchanged_set_receipt`。
- 预期行为：MCP 工具声明应把 input item 暴露为具名结构和枚举，调用前即可校验；不应显示为 `inputs: Array<unknown>`。
- 影响：模型只能试错发现协议，增加无效 tool call，也容易把参数错误误判为控制面故障。
- 当前绕过：改用 `usage="claim_evidence"` 后成功创建任务。
- 建议：为 Root MCP 的任务输入导出完整 JSON Schema，并增加契约快照测试。

### P6-D02：ScientificFoundation 证据源键与运行时附件引用边界不够显式

- 触发：evidence extractor 在主输出 `ScientificFoundation.evidence` 中使用 runtime attachment alias。
- 实际行为：`worker_write_result` 拒绝；`source_key` 只允许任务声明的输入别名。本次合法输入只有 `paper_source`。
- 预期行为：role contract、assignment 以及输出错误都应明确区分：证据声明只能引用 task-local input alias；collection attachment 只能作为运行观察/附件路径引用，不能升级为声明源。
- 影响：科学附件束已经通过 validator，但主输出在 attempt 绝对截止前约 0.27 秒才被拒绝，随后整个 attempt 超时。
- 当前绕过：主输出只声明 `paper_source`，附件通过 collection paths 引用。
- 建议：在 worker 领取任务时提供一个小型合法示例；增加 evidence extractor 真实 bundle 集成测试。

### P6-D03：通过验证的 collection bundle 未跨 attempt 保留

- 触发：attempt 1 的 figure bundle 已通过 mounted evidence validator，但主输出 schema 拒绝导致未 finalization；随后对同一任务执行 `task_retry`。
- 实际行为：attempt 2 的 materialized `/outputs` 为空，未提供上一 attempt 的 validated collection package。仅因共享 `/tmp/scidiscovery_fig4_work` 偶然仍在，子 agent 才能复用 PDF 内嵌 Fig.4 栅格。
- 预期行为：被拒 attempt 的只读修订上下文至少应包含主输出草稿、validator 结果、已验证附件束或其内容寻址引用；新 attempt 不应依赖宿主 `/tmp` 偶然残留。
- 影响：重新组装附件包，浪费时间；换机、清理 `/tmp` 或隔离 worker 后将退化为从头重做。
- 建议：在输出拒绝时冻结 attempt workspace 或登记 provisional bundle CAS；retry assignment 以 `revision_base`/只读挂载方式暴露，成功后再正式注册。

### P6-D04：文件级证据任务缺少“尽早预检、末端只提交”的时限保护

- 触发：attempt 1 在完成 PDF 恢复、两次确定性分析和 bundle validator 后，直到绝对截止前才首次调用 `worker_write_result`。
- 实际行为：一次可快速修复的 schema 错误直接变成 `timed_out`；状态证据为 `output_rejected` 时间 `2026-08-09T14:18:37.738382Z`，绝对截止 `2026-08-09T14:18:38.012805Z`。
- 预期行为：主输出 envelope 应在早期以小对象预检；collection 构建与主输出 schema 校验并行或分阶段进行；接近截止时 worker 应优先提交已验证的 bounded result。
- 影响：600 秒任务边界被包组装吞噬，重试成本显著放大。
- 建议：增加 `worker_validate_result` 或 dry-run；role 指令加入剩余时限门限；记录 package/validate/finalize 分段耗时供调度器测量后调参。

### P6-D05：`worker_run_analysis` 的超时上限未被子 agent 正确约束

- 触发：attempt 2 调用 `worker_run_analysis(timeout_seconds=240)`。
- 实际行为：工具拒绝，精确错误为 `timeout_seconds Input should be less than or equal to 120`；改为 120 后确定性分析成功。
- 预期行为：worker MCP schema 和 role/assignment 应让调用方在生成 tool call 前清楚感知 120 s 上限；长确定性步骤应主动拆分。
- 影响：在 attempt 绝对截止前约 99 秒产生一次完全可避免的拒绝，压缩了 bundle finalization 窗口。
- 当前绕过：intentional revision 明确限制所有单次 analysis 不超过 120 s。
- 建议：为 worker 工具参数保留标准 JSON Schema `maximum: 120`，并在 agent role contract 中给出拆分规则；增加越界调用的模型侧契约测试。

### P6-D06：任务已准备完整合法输出时，绝对截止不提供有界提交宽限

- 触发：attempt 2 已完成确定性分析，mounted validator 返回 rc 0，`bundle.json`、四个 collection（含五个 CSV）及修正后的 `ScientificIntake` 都已准备；随后调用 `worker_write_result`。
- 实际行为：控制面直接返回 `task session has expired`，未写入 `result.json`，也无法 file finalization。
- 预期行为：不能允许无限延期，但应把“科学计算截止”和“已验证结果提交截止”分开，或在截止前进入 `finalizing` 状态后提供很短且不可续期的提交窗口。
- 影响：完整且已验证的附件束再次未注册，迫使创建任务修订并重复包构建。
- 建议：引入有严格前置条件的 bounded finalization grace（例如仅允许已开始的 validate/write/finalize 操作），同时禁止在宽限期继续分析或修改附件。

### P6-D07：Structured revision 在 worker finalization 前未验证“应用后的完整目标对象”

- 触发：`fig4_alpha_hypotheses_revision2` 的 `StructuredRevision` 已通过 `worker_validate_output` 并成功 finalization，随后调用 `scidiscovery.structured-revision-apply.v1`。
- 实际行为：确定性 apply 才报告 8 个目标 schema 错误：7 个 `ParameterForm.range_description` 超过 512 字符；一个 hypothesis 的 falsifiers 为 5 项而目标上限为 4。该 patch 自身结构和 allowed paths 合法，但不可生成合法 `HypothesisProposal`。
- 预期行为：worker validation/finalization 应在只读 revision base 上试应用 patch，并用 assignment 声明的 target schema 验证完整结果；只有可应用且目标对象合法时才允许任务完成。
- 影响：控制面注册了不可应用的 structured revision，必须再派发一次纯压缩/合并修订；如果调度器未执行 apply gate，可能误把 `pass` patch 当成有效科学对象。
- 当前绕过：把不可应用 patch 作为 `prior_signal` 传给新的 bounded correction；明确 `range_description<=512`、predictions/falsifiers 各不超过 4，并保持同一 base 与 allowed paths。
- 建议：在 `worker_validate_output` 与 `worker_finalize` 中共用 deterministic dry-apply validator；assignment 应暴露目标字段限制，增加“patch 合法但 apply 后目标非法”的端到端回归测试。
- 再现：`fig4_alpha_hypotheses_revision3` 在任务指令已明确要求遵守 `HypothesisProposal` 上限后仍通过 worker validation/finalization；apply 再次因 6 个 `range_description>512` 失败。该重复证实控制面不能依赖 prompt 代替完整目标 schema gate。

### P6-D08：Candidate eligibility join 不理解 critic 的增量复核链

- 触发：最终 `fig4_alpha_hypotheses_revised4` 的两路径 delta 已由 `fig4_alpha_hypotheses_revision4_critic.output` 与对应 evidence audit 独立 `pass`；随后以最终 portfolio、最终 delta critic、最终 delta audit 执行 `scidiscovery.candidate-eligibility.v1`。
- 实际行为：确定性 transform 拒绝：`critic review must cover every portfolio hypothesis exactly once`。delta critic 按协议只覆盖改变的 `A_only_null`，无法单独满足下游全 portfolio join。
- 预期行为：下游 join 应能验证并合并“最近一次完整 review + 有 parentage 的有序 delta reviews”，或由确定性 transform 产生 consolidated review；每条 hypothesis 取覆盖其最新语义版本的最新独立 verdict，且绝不能简单继承旧 verdict。
- 影响：前面多轮 bounded critic 的科学结果虽有效，下游仍迫使再次全量 critic；增量上下文节省在 stage boundary 被抵消。EvidenceAudit 也需要对 delta-chain coverage 给出同样显式的合并/完整性规则。
- 当前绕过：并行派发一次对最终 portfolio 的 fresh full-coverage critic 和 full evidence audit，再把这两个单一完整报告交给 eligibility transform。
- 建议：新增 `scidiscovery.review-chain-consolidate.v1`，输入 final object、deterministic diffs、prior full review、ordered delta reviews 与 receipts；输出带逐对象/逐检查 provenance 的 consolidated critic/evidence report，并让 candidate eligibility 强制验证其 parentage。
- 绕过进展：fresh full evidence audit 对 `revised4` 给出 `pass`，fresh full critic 完整覆盖三条候选后发现 `hybrid_A_plus_B` 的 `B_unnecessary` 仍可在低浓度观测门缺失时误拒 B。该问题已通过 `revision5` 的单路径 structured revision 修正并成功 deterministic apply；由于 eligibility 仍不能合并“full review + 最新 delta”，修正后仍需再次生成完整覆盖 critic，进一步验证了重复全量复核不是偶发现象。

### P6-D09：Primary-only 任务把完整结果重复内联到 validate/finalize tool call

- 触发：`experiment_designer` 对完整 `RoleResultEnvelope` 调用 `worker_validate_output`；UI 中显示很长的 `content` 字符串，成功后还需把同一对象再次传给 `worker_finalize`。
- 实际行为：验证响应本身通常只有 `valid`、`size_bytes` 和结构化 `errors`，且 `_validation_details` 不回显 Pydantic 的完整 input；真正的膨胀来自 tool-call 请求内联整份科学对象。随着角色输出上限增至 64–512 KiB，同一内容至少穿越模型/工具边界两次。
- 预期行为：所有角色都应能先把主输出原子地暂存为 `output/result.json`，再用短调用执行 file validation 与 finalization；模型上下文只保留路径、大小、摘要和有界错误，不重复承载完整对象。
- 影响：浪费上下文与传输时间，降低长任务末端提交的可靠性，并与已出现的 `text too long` 风险叠加。它不直接改变 schema 判定，但会降低 alpha 闭环的可完成性。
- 现有不一致：服务层已有 `worker_validate_output_file` / `worker_finalize_file`，materialization 也总是提供 output path；但调度契约仍要求 primary-only task 使用内联 `worker_finalize`，而 `worker_write_result` 本身同样接收内联 content。
- 建议：提供受 assignment 限制、原子写入且带大小门的主结果文件接口，或允许 worker 的受控分析过程写入既定 result path；随后统一所有角色走 `validate_output_file -> finalize_file`。错误数组另设总条数和总字节上限，超出时返回计数与前 N 条，而不是无限扩张。
- 实测：`fig4_alpha_experiment_design` 最终输出 62,698 bytes，claim-to-finalize 829.75 s；性能计数显示 `output_rejected=10`。每次 retry 均重传完整 envelope，草稿约 58.2–81 KiB，最终合法对象也在 finalize 时再次完整传输。

### P6-D10：ExperimentPortfolio 的关键跨字段不变量与 canonical 大小不可预发现

- 触发：`fig4_alpha_experiment_design` 在 900 s 边界内连续 10 次 validation rejection。
- 实际行为：除明确的 drafting error 外，多条决定合法性的规则只在运行期 validator 中暴露：comparison observables 必须与 proposal observables 精确相等；identifiability claim 只能引用 canonical observable；缩减后的 comparison-variable expectations 必须覆盖每个 compared case；comparison-variable keys 必须与 changed-factor keys 精确相等。JSON Schema 未声明这些跨字段不变量。
- 大小问题：assignment 给出 65,536-byte 上限，但 worker 的 63,596 和 61,183 raw-character 草稿仍因 canonical encoding 膨胀而超限；调用前无法获得 canonical byte estimate。最终接受的 canonical 输出为 62,698 bytes。
- 影响：worker 只能用“提交整份对象—读取首批错误—修改—再次整份提交”的方式探索隐藏契约，十次拒绝把任务推到绝对截止前约 71 s；这同时放大 P6-D09。
- 归因边界：extra `handoff.schema_version`、未声明 factor、两次明显超限属于 worker drafting error；semantic unit whitelist、上述精确集合/覆盖关系及 canonical-size 差异属于契约可发现性不足。
- 建议：在 assignment 中附加机器可读 invariant manifest（集合相等、引用完整性、case coverage、unit vocabulary）；提供本地同版本 preflight validator 或 `worker_validate_output_file`；返回 canonical byte estimate 和各顶层字段大小分解；支持按 JSON Pointer 校验局部 patch，但 finalization 前仍执行一次完整对象校验。

### P6-D11：执行 adapter 的 exact SolverCapability 无法进入 deck-author 上下文

- 触发：`fig4_alpha_tcad_deck_author` 接收最终 ExperimentPortfolio、假设、eligibility、foundation 与审计，但没有管理员冻结的 solver capability。
- 实际行为：author 无法合法选择 `solver_kind`、`tool_profile`、executable/release、固定 argv 和 solver 输出命名，因而 verdict=`blocked`。当前 Root MCP 无 capability discovery/register 工具；活跃 control service 使用 `/etc/scidiscovery/command-adapter.json` 指向 SSH transport，而该 transport 只支持 `prepare/submit/status/cancel/collect`。本机 `/etc/scidiscovery/tcad-policy.json` 仅有 `deployment_smoke` deterministic tool，且本地 `tcad-control.service` 为 inactive，不能代表远端 Sentaurus 能力。
- 通信判定：`scidiscovery-control`、worker 与 approval UI 均 active，外部 command adapter 已配置；但当前实例 `execution_list=[]`，本轮没有创建 ExecutionRequest，也没有调用 prepare/submit，因此没有证据表明 SSH/Sentaurus 通信失败，同样也尚未完成一次真实连通性资格验证。
- 预期行为：实例开始 TCAD authoring 前，控制面应从活动 adapter 获得管理员签名或内容寻址的 `tcad.solver-capability.v1` snapshot，并以 task-local `execution_capability` 输入交给 author；review、package、approval 和 execution 必须绑定同一摘要。
- 影响：科学设计已经 ready 仍无法生成 runnable deck；若 worker自行采用仓库示例中的 `sentaurus-sprocess-r2020.09`，会把文档示例冒充实际执行能力，破坏可追溯性。
- 当前处理：不读取旧研究对象推断能力，不直接 SSH 绕过控制面，不把 deployment-smoke profile 当 Sentaurus；等待管理员能力通过正式控制面进入实例后，以同一科学输入创建 author revision。
- 建议：为 Root MCP 增加只读 `execution_capabilities` 与 `execution_capability_bind`（或在 instance prepare 时自动绑定 adapter snapshot）；SSH transport/remote runner 增加 bounded `capabilities` operation，只返回脱敏后的 immutable capability 与摘要，不泄露许可证 secret 值。
- 最小接口闭环：active adapter 提供 `capabilities` -> control 注册 canonical `tcad.solver-capability.v1` -> scheduler 以稳定语义名选择并绑定 -> deck author assignment 只见 task-local `execution_capability` -> reviewer/package/approval/execution 验证同一 capability 摘要。执行状态接口本身无需重造。

### P6-D12：blocked role output 被强制伪装成合法 TCAD project，readiness 又将其标为 qualified

- 触发：deck author 需要报告缺失 capability，但 `RoleResultEnvelope[DeckProjectDraft]` 没有 blocked payload variant。
- 实际行为：为满足 payload schema，worker 被迫写入 `solver_kind=deterministic_tool` 与一单位 `resource_limits` sentinel；任务 handoff verdict 明确为 `blocked`，summary 也声明不可执行，但控制面仍注册 `tcad.deck-project.v1`。随后 ScientificReadiness 将 `fig4_alpha_tcad_deck_author.output` 列为 `qualification=qualified`，blockers 为空，并开放 `tcad_deck_reviewer` 与 `evaluate_control_equivalence`。
- 预期行为：blocked handoff 不应注册可消费的领域 payload，或应注册独立 `role-blocker-report.v1`；任何 inventory/readiness join 都必须将 scheduler signal verdict 纳入 qualification，blocked/revise 不能升级为 qualified project。
- 影响：如果 scheduler 只依赖 readiness，sentinel 假项目可能进入 review、package 甚至 execution approval，是比普通缺字段更危险的伪阳性路径。
- 当前绕过：调度器同时检查 task scheduler signal，拒绝消费该 artifact，尽管 readiness 建议继续。
- 建议：让 task finalization 根据 verdict 分型注册；至少在 artifact qualification projection 中将 `blocked` 标为 blocked 并从 downstream capability join 排除。新增端到端回归：blocked deck author 输出不得开放 reviewer、equivalence、packager 或 execution。

### P6-D13：deck author 缺少 capability-matched 的受控预检环境

- 触发：author 在没有 exact solver capability、同版本静态 validator、argv/output convention 或 parser preflight 的条件下被要求直接产出 runnable Sentaurus project。
- 实际行为：author 只能依赖通用 skill 与 JSON schema；若继续写 deck，求解器语法、版本差异、许可证启动、参数顺序和输出命名问题只能在正式 execution 后暴露。本次 author 选择在写代码前 fail-closed。
- 预期行为：author assignment 应提供脱敏 capability projection、与生产版本一致的离线 validator/grammar、最小合法模板及输出合同。需要调用真实 Sentaurus 的 parser/smoke 必须经过 execution bridge，在隔离临时目录、严格资源/输出限额和完整日志下运行，不能给 author 不受控的远端 shell。
- 影响：缺少预检会把低成本工程错误推迟到高成本执行审批后；若反过来给 author 直接运行权限，又会绕过 execution approval 与 immutable payload 边界。
- 原方案修正：不能把 author 的每次 parser/初始化调试都建模为一份新的生产 ExecutionRequest 并要求逐次人工审批；这会把正常的编译—修订循环退化为低效审批队列。
- 最小构建分两层：
  1. 离线 author sandbox：只挂载 task inputs、脱敏 `DeckAuthoringCapability`、release-matched 规则/最小模板与 `validate_deck_project.py`；无远端凭据、无许可证变量、无网络，输出限定为 project bundle、静态报告和 include/output graph。
  2. 真实 preflight execution unit：由生产 runner 在临时隔离目录中使用同一 capability digest、direct argv、固定环境和已审核 bundle 运行；不得臆造跨版本的 `--check`/`-V`。若求解器没有管理员确认的 parse-only 模式，就执行设计中声明的最小初始化 smoke，并把它设为所有科学 cases 的 DAG 前置门。
- preflight 产物应为有界 `tcad.preflight-report.v1`：精确 argv 投影、capability digest、project/package digest、退出码、第一条 parser 错误及文件/行、parser/初始化到达状态、所需输出的新鲜度/大小/可解析性和最小修复建议。层 1–7 未通过时 `physical_claim_evaluable=false`。
- 安全与一致性：完整 executable/environment/许可证配置只留在 control/runner；author 只见非敏感投影与摘要。生产 capability、project、review 任一摘要变化都必须使旧 production execution authorization 失效。
- 调试平面应独立于生产执行平面：控制面在 deck-author task 开始时授予一次 `TCADDebugLease`，绑定 task attempt、solver profile、总时长、最大调用次数、CPU/内存/输出配额和允许的 direct-solver 操作。租约内 `worker_tcad_debug_run` 可反复运行当前 workspace snapshot，无需每次人工审批；禁止 shell、任意 argv/environment、后台进程、跨 workspace 读取和网络访问。
- 调试输出可以包含 parser/log、残差、最小 TDR/PLX/PLT 与文件清单，以支持真实语法、初始化和收敛调试；但必须进入隔离的 provisional CAS，标记 `development_only` / `scientific_claim_admissible=false`。与最终 snapshot 精确绑定的 debug report 可供 deck reviewer 作为实现证据，但不能满足科学 claim gate、替代 production execution，或进入 scientific diagnosis/knowledge update。被拒版本及其诊断应作为下一次 patch 的只读上下文保留。
- 最终流程改为：一次调试租约授权 -> author 在租约内多轮 `snapshot -> debug run -> bounded diagnostics -> patch` -> 静态 validator -> finalization -> independent reviewer -> 对冻结 project/review/capability 创建一次精确生产执行审批 -> production run。生产结果仍不可复用调试结果冒充。

## 科学证据边界观察

### P6-D31：失败 runtime attestation 被 readiness 误投影为 qualified

- 触发：真实 SProcess production execution 在首个 `diffuse` 初始化阶段退出 1，确定性 runtime attestation 明确 `verdict=fail`；随后读取 `scientific_readiness`。
- 实际行为：readiness 过去只检查 producing-task handoff 和 provisional 标签，没有读取 deterministic attestation verdict，因而把该 artifact 列为 `qualified`；curve scorer 到真正执行时才再次 fail-closed。
- 预期行为：`fail` attestation 只能作为 implementation revision/diagnosis 的 `prior_signal`，不得成为 qualified runtime inventory 或评分入口。
- 修复：readiness 和普通 operational resolver 现在对 `tcad.runtime-attestation.v1` 读取 bounded `verdict`；非 `pass` 投影为 `revision_required` 并从 `available_artifacts` 排除。允许非合格输入的权限仍必须由精确 context policy/usage 显式授予。
- 回归：新增失败 attestation inventory 负例；scorer 原有 runtime gate 保留为第二道确定性防线。

### P6-D32：SProcess `-s/-f` 无法覆盖首个 diffusion initialization

- 触发：author 的 exact-source R-2020.09 preflight `-s` 成功，production 正常 argv 随后在首个 `diffuse` 报 `initialization procedure won't run` / `list must have an even number of elements`。
- 根因：手册明确 `-s` 只检查语法，`-f` 跳过 diffusion/PDE；原 development API 没有进入结构/模型/首步 process initialization 的受控模式。author 的已执行检查没有测试到失败层。
- 修复：新增 `initialization` development mode。控制面只接受已通过 deterministic materialization 的 SProcess project，从精确 experiment plan 选最高优先 proposal 的 baseline case，机械移除其他 direct dispatch，并把 baseline duration 缩短为同一 case 已声明的 `max_timestep`；使用正常 solver argv，清空科学 expected outputs，限制 120 s。派生 project 清除 materialization/preflight/realization/binding 元数据，永远 development-only、不可注册为 reviewed scientific project。
- 边界：agent 不能选 argv、case 或时长，不能自己删 case；该 probe 不执行完整 portfolio，也不产生可用于科学结论的结果。

### P6-D33：production solver log 未成为精确的 author 修订上下文

- 触发：runtime attestation 已绑定 exact reviewed package 和 solver log，但既有 author revision profile 只接受 reviewer change request；scheduler 只能人工转述日志或重新走一次 reviewer。
- 修复：新增 `tcad.deck-author.runtime-failure-revision.v1`，必需输入为 exact prior source project、失败 runtime attestation、其 parent-bound 原始 solver log、execution capability 和 experiment plan。调度时验证 attestation=`fail`、log 是其精确 parent、且 reviewed package 的 source files/invocation/capability 与 prior project 一致；只允许 earliest concrete runtime error 支持的最小实现修订，之后仍需 fresh reviewer 与 production approval。
- 兼容性：允许 packager 对非源码的 legacy solver-log capture 字段做确定性迁移；源码树、input slots、entrypoint、arguments 和 capability 三元组必须保持精确一致。

### P6-D34：必需科学输出缺失时 runner 丢弃已捕获的 process log descriptor

- 触发：`fig4_alpha_tcad_solver_neutral_v2_case_isolation_execution` 已运行并生成 process log，但五个必需 PLX 中首项缺失。
- 实际行为：local worker 与远端 Python 3.6 runner 的输出收集器先把 control-owned `solver_log` 加入函数内局部列表，随后因必需 PLX 缺失抛错；调用方的 `outputs` 变量没有接收到这个局部列表，最终 runtime manifest 写成 `outputs=[]`。Root 仍注册 transport `tcad_log`，但它不在 manifest 中，故 `tcad.runtime-attestation.v1` 不能把日志作为 `output__solver_log` 纳入精确父链；`tcad.deck-author.runtime-failure-revision.v1` 随后正确拒绝非同源 attestation/log 组合。
- 预期行为：缺失必需科学输出仍必须令执行失败，但在失败发生前已通过大小、哈希和路径检查的 process log descriptor 必须保留在 runtime manifest 中；失败不能抹掉最早诊断证据。
- 修复：输出收集器改为向调用方持有的 records 列表增量追加；后续输出检查抛错时，manifest 保留此前已验证 descriptor，同时继续记录 terminal failure 和 missing-output error。没有放宽输出合同、成功判定、大小上限或科学资格。
- 回归：本地执行边界与 dependency-free 远端 runner 均新增“process log 成功、随后必需 PLX 缺失”负例；断言 terminal=`failed`、错误保持精确、manifest 仍含且仅含 `solver_log`。相关执行/SSH transport 测试 `51 passed`。
- 运维要求：本地 control/worker 和实际远端 runner 必须同时升级；仅重启本地 MCP 不会替换远端 `scidiscovery-tcad-ssh-runner`。

### P6-D35：通用曲线评分与 SProcess log 载体错误耦合

- 触发：修订后的五 case production 在约 5 分钟内成功收集五个原生 PLX；runtime attestation 与 control equivalence 均通过。随后 `scidiscovery.curve-score.sprocess-log.v1` 只读取 solver log，并因不存在内嵌 `SCID_CURVE_V1` 记录而报告五条 series 全缺失。
- 实际行为：deck 已按职责边界只输出原生 PLX，scorer 却把 log 同时当运行诊断和曲线载体；通用实验 schema 还曾固定一个 SProcess-log evaluator 名，造成 solver、传输格式和通用曲线算子三层耦合。
- 预期行为：log 只用于 terminal/parser/initialization/convergence 诊断；SProcess PLX normalizer 严格解析每个已注册 PLX，生成通用 `CurveBundle`；通用 scorer 只消费 `CurveBundle + ExperimentPortfolio`，不认识 SProcess、PLX 或 log。单 case 与多 case 只体现在 bundle 中 series 数量，不产生 Fig.4 特例。
- 修复：新增严格 `scidiscovery.curve-normalize.sprocess-plx.v1` 与多输入 `scidiscovery.curve-bundle.sprocess-plx.v1`；新增 transport-neutral `scidiscovery.curve-score.v1`。Root 对每个 `solver_output__<series_key>` 动态验证其属于同一 runtime attestation，并验证 bundle 同时来自精确 plan 和 attestation。通用 experiment schema 只检查 evaluator metric 与 operator kind，不枚举任何插件 profile；具体 transform 执行时才核对计划声明的 evaluator profile。
- 解析边界：PLX 必须是严格 UTF-8、一行单字段引号表头、随后每行恰好两个有限数值列，x 严格递增且点数满足计划声明；不排序、不补点、不猜单位/series/case。旧 log composite profile仅保留历史兼容，不作为新研究默认入口。
- 回归：单 PLX、双 PLX→通用 score、缺失/额外 series、坏表头、多列、非有限值、非单调 x、错误 runtime parentage 和错误 evaluator profile 均有正/负例；首轮相关回归 59 项通过。
- 现场补充：五个真实 PLX 每个只在 `x=6.0 µm` 的 InGaAs/Oxide 远端界面出现一组重复 x（左右值 0 与 `1e7`），0–0.8 µm 的全部预注册评分域内无倒序/重复。不能全局排序或任选一侧去重；normalizer 现从 comparison spec 合并每条 series 的必需连续域，只保留域内点和必要插值支撑点。必需域或其支撑点内的重复仍 fail closed，域外界面重复只在 audit 中计数为 ignored；新增域内/域外重复正负回归。

### P6-D36：通用 scorer 缺少 validated figure evidence 的 reference bridge

- 触发：真实五条 PLX 已成功生成 canonical solver `CurveBundle`，通用 scorer 随后正确拒绝“计划声明了 reference series，但没有 reference CurveBundle”的输入。
- 根因：scientific-paper-evidence 已有 manifest、曲线 CSV 和控制面 validation report，但没有确定性转换把这组三者投影为通用 `CurveBundle`；直接把 CSV 交给 scorer 会重新耦合文件格式与比较算子，手工填参考值则破坏证据父链。
- 首版修复：新增 `scidiscovery.curve-bundle.figure-evidence.v1`，建立 manifest/report/CSV 到 canonical curve 的确定性桥。首版仍错误依赖实验计划并只接受计划声明的 reference；该循环依赖已由 P6-D37 的独立完整 evidence library 设计取代。
- fail-closed：当前 Fig.4 manifest 为 `unresolved` 且曲线为零 quantitative-eligible rows，因此输出应是序列集合完整但 points 为空的 `unavailable` reference bundle；后续 metric report 应为 `unavailable`，不得为了完成 alpha 闭环伪造数值。哈希、计数、父链、别名、轴或单调性错误则 transform 直接拒绝。
- 回归：qualified 标准 CSV、扩展像素 CSV、unresolved、零合格行、CSV/hash 错配、reference alias 精确覆盖、动态父链、unavailable reference 到通用 score 的传递均有正负例。

### P6-D37：figure evidence 与实验计划循环依赖，缺失目标映射仍可执行

- 触发：D36 bridge 实际导入五条 Fig.4 曲线时，旧 transform 要求这些 CSV 与实验计划中声明的 reference series 精确相等；当前计划只声明解析控制 `B_erfc_analytic_profile`，因此五条论文曲线全部被视为 unexpected。此前 experiment designer 输入中又没有 manifest/report，无法编写候选曲线到论文曲线的映射。
- 根因：证据清单错误地由计划裁剪，scorer 又要求 reference bundle 与计划全集相等；同时 reviewed-deck packaging 只校验 TCAD case controls，不校验外部 reference 覆盖。执行授权只授权 side effect，并不证明实验计划的科学目标完整，所以该缺口可以一路通过到生产执行后才暴露。
- 修复：figure-evidence bundle 现完全独立于计划，并以 `curve_table__<panel>__<series>` 输入保留 manifest 中全部 series；通用 scorer 只从完整库中选择 agent 显式声明的 reference 子集，额外曲线不报错也不参与评分。experiment designer 可读取 manifest/report，并必须为证据库每条 series 写 `compare|exclude` disposition。新增 `scidiscovery.curve-reference-coverage.v1`，确定性验证映射、缺失、陈旧和重复 series；含外部 reference 的 `tcad.reviewed-deck-package.v2` 必须绑定 exact-plan 的 passing coverage report，否则执行前拒绝。
- 边界：控制面不依据标签、颜色、材料名或文件名选择目标；映射和排除理由属于 experiment designer 的科学输出。unresolved/零 eligible 的论文曲线可以完成身份映射，但后续 metric 必须保持 unavailable。
- 回归：完整 evidence library、未映射 series、显式排除、缺失声明 reference、scorer 子集选择、package 缺失 coverage 和 exact parentage 均有正/负例。

### P6-D38：未参与 comparison 的 solver series 被错误解释为“整域必需”

- 触发：实验计划移除不存在的 `B_erfc_analytic_profile` 比较后，仍保留已执行的 `B_erfc_P0_profile` solver 输出声明；该 series 不再属于任何 comparison。
- 实际行为：PLX bundler 对该 series 得到空 `required_intervals`，normalizer 又把空区间解释为保留整条 PLX，因而重新读入 x=6 µm InGaAs/Oxide 接缝的双值坐标并报 `ambiguous duplicate x`。此前 D35 的域外接缝修复只覆盖“存在评分域”的路径。
- 预期行为：comparison domain 就是评分 mask。参与 comparison 的 solver series 只在这些域及必要插值支撑点内归一化；未参与任何 comparison 的 solver 输出仍保留为注册的原始执行产物，但不进入 scorer bundle，也不能因非评分区间的接缝阻断其他比较。
- 修复：PLX bundler 只归一化 comparison 实际引用的 solver series；调用方可继续提供完整的已声明 solver 输出集合，审计新增 `ignored_uncompared_solver_inputs`。缺失任一被比较 series 或提供未声明 series 仍 fail closed。generic scorer 的 bundle declaration gate 同步要求“exact compared solver series”，不再要求未评分输出。
- 回归：新增一条已声明但未参与比较、且 PLX 内含域内双值 x 的控制输出；bundler 必须忽略它、记录审计，同时其余两条比较曲线完成确定性评分。相关曲线/插件/readiness 测试 66 项通过，全套测试 594 项通过。

### P6-D39：reference coverage 元数据缺口及单位别名的字符串比较

- 触发：实验设计已把 `ingaas_measured` 映射到完整论文曲线库，coverage 报告生成，但 scorer 随后拒绝 `reference bundle series differs from declaration`。
- 根因一：旧 coverage 只比较 series key 与 compare/exclude disposition，没有比较 x/y axis unit/scale、点数/availability 合同。根因二：补上声明检查后仍以字符串判断单位，把单位表中已登记为同一数值语义的 ASCII `um` 与 Unicode `µm` 错判为不一致；这又使已把 reference 声明修订为 `µm` 的计划无法与保持 `um` 的 comparison domain/solver series 共存。
- 修复：coverage report 新增 `declaration_mismatch_series`，并复用 scorer 的 reference declaration 检查；任一真实声明元数据不一致时 coverage 必须 fail。所有 curve declaration、coverage、scorer 输入 gate 和 threshold gate 统一改为“完整单位定义相等”（维度、SI scale、offset 均相等），因此 `µm == um`，但 `cm != um`、`decade != 1`。crossing/width metric 规范化为 comparison domain 的单位标签，避免同值别名在 threshold gate 再次被字符串拒绝；相同但尚未登记的自定义标签仍只与自身兼容。
- 现场修订：此前 bounded revision 只把 `ingaas_measured.x_axis.unit` 从 `um` 改为 manifest 的 `µm`，其他计划字段冻结；现在该对象可直接与 `um` domain/solver 声明组成合法比较，不需要再次改写 evidence identity 或数值。
- 回归：声明合同、运行时 scorer、reference coverage 均新增 `µm`/`um` 正例；`nm`/`um` 元数据不一致与 `decade`/`1` 阈值不一致继续 fail closed。

### P6-D40：log10 metric 单位与 ValidationPlan 单位词汇自相矛盾

- 触发：scorer 成功计算三个 log10 residual metric，metric unit 为 `decade`；计划中的 operator 与 validation threshold unit 为 `1`，因此三项 threshold 均 `threshold_unit_mismatch`/unavailable。尝试结构化修订为 `decade` 时，`MetricThreshold` 又以 unsupported unit 拒绝。
- 根因：CurveComparisonSpec 未在计划创建时验证 operator 产出单位与 threshold 单位；通用单位表也未登记 scorer 已公开使用的 `decade`。
- 修复：experiment output/revision validator 与所有 curve transforms 在存在 series declarations 时调用同一确定性 declaration-contract 检查，验证 domain/x-axis、两侧 y-axis 与 operator threshold unit；log10 residual 必须使用 `decade`，crossing/width 使用 domain unit，linear residual 使用 y-axis unit。单位表增加独立 `log10_ratio` 维度的 `decade`，不得与普通无量纲 `1` 相互转换。基础 Pydantic 解析保持向后兼容，使旧错误对象仍可作为 immutable revision base；补丁应用后的完整对象必须通过新检查，避免 schema 升级后无法修订的死锁。
- 影响：旧错误计划需要一次 bounded experiment-design revision；新计划会在 author/package/执行之前 fail fast。

### P6-D41：`equivalence_rule=reviewed` 在 passing reviewed package 中仍永久 inconclusive

- 触发：production runtime 与输出合同均通过，但 `tcad.control-equivalence.v1` 把每个 reviewed comparison variable 固定写成 `requires_review`；diagnostician 因而判定 implementation fidelity 未闭合。
- 根因：transform 输入已经是 `ReviewedDeckPackage`，其 schema 强制 exact project/capability、passing review 与 `execution_ready=true`，但底层 evaluator 对 `reviewed` 规则无条件返回 `None`，从未消费该已存在的独立 review 判定。
- 修复：通用 evaluator 默认仍 fail closed；只有 reviewed-package transform 显式传入已经由 exact passing review 覆盖的 variable key，才可满足 `reviewed` 规则。存在性、scientific path、unit、未声明额外差异和所有 deterministic controls 仍独立校验，不能由 review 跳过。
- 回归：同一 reviewed multi-case package 的 `reviewed` intended-change 必须形成 `expected_change/pass`；没有显式 review coverage 的直接 evaluator 调用仍保持 inconclusive。

### P6-D42：figure-evidence 最终附件与早期 handoff 可跨轮次错配

- 触发：Fig.4 红色 measured trace 的早期 package-r1 存在三个 source-column gap，后续 package-r2 至 r4 已形成连续 808 列、`max_gap_px=0`；正式 task signal 仍沿用“red trace retains source-column gaps”并要求重提取。
- 根因：`validate_output_file` 先把 RoleResultEnvelope 归一化为纯 payload，再把纯 payload 交给 bundle validator；bundle 层完全看不到 handoff。最终 manifest/CSV/overlay 虽有严格 provenance 和控制生成 report，但 handoff 没有绑定 report 的 `bundle_fingerprint_sha256`，scheduler signal 又直接复制 worker 的早期文字。
- 修复：RoleHandoff 新增可选 `evidence_bundle_fingerprint_sha256`；scientific-paper-evidence profile 强制 worker 对 exact staged collections 重跑 validator、最后写 result 并填入指纹。控制面同时接收 payload 与完整 envelope，缺失/陈旧指纹、worker 自填 figure `assumptions`/`missing_inputs`/`next_actions` 均在 seal 前拒绝。最终 task signal 的摘要、manifest ambiguity 和固定 audit 动作由 exact registered manifest/report 投影，自由文本旧摘要不再成为调度事实。
- 审计边界：机器校验只证明 handoff 与最终字节版本一致，并投影机械事实；可见连续性、遮挡/源缺口性质和 claim scope 仍必须由独立 evidence_auditor 对原图、overlay、CSV、manifest、report 全集审核。新增 figure-extraction audit/revision context profiles 允许读取 fail-closed primary 与附件，但不会把它们提升为 claim evidence。
- 回归：缺失指纹、错误指纹、陈旧 handoff assumptions/gap action 均拒绝；陈旧 free-text summary 不进入 task status；普通角色、curve-analysis 附件和 sealed finalize 生命周期保持兼容。聚焦 63 项、跨生命周期 66 项、完整 artifact-agent 654 项通过。

### P6-D43：figure-evidence 身份资格与定量行资格语义混淆

- 触发：红色 measured trace 局部重提取后，独立审计确认 806/806 source columns 连续且像素残差不超过 0.5 px；但 manifest 的 `qualified_series_count=3`、CSV 缺少 eligibility 字段、validation report 的 aggregate eligible rows 为 0，而 support renderer 又把缺失字段默认显示为 eligible。
- 根因：`qualified_series_count` 实际只统计无歧义 identity binding，并不表示 quantitative claim eligibility；旧 digitizer 不写显式 eligibility，validator 又允许字段缺失，renderer/normalizer 则把缺失解释为 observed rows 可用，导致同一 bundle 在审计、可视化与下游归一化中出现三种表述。
- 修复：digitizer 为每条曲线确定性写出 `quantitative_measurement_claim_eligible` 与 detection-limit flag，默认 eligibility 为 false；spec 以一个紧凑的 series-local `eligibility` 块声明默认资格、局部 ineligible 区间与 below-limit 区间。validator v2 拒绝缺失 eligibility、未观测却 eligible、below-limit 却 eligible 的任何行。Skill、reference 与 evidence_extractor role 同步明确：manifest identity qualification 不能替代定量行资格。
- 边界：控制面仍不选择科学 target 或自动把 matched line 视为 measured truth；agent 必须依据可见身份和 claim scope 设置 spec。两条 D∝C 与 erfc fit 可保留完整可视数据，但必须显式 ineligible；真实零区、below-limit、接缝和遮挡仍显示在 support PNG，不因 mask 自动形成失败阈值。
- 回归：Fig.7/10/13、多 panel、marker、partial-domain、gap/overlay 与 PDF provenance 聚焦 19 项通过；figure schema、normalizer、task bundle、scheduler signal 联动 140 项通过；完整 artifact-agent 657 项通过（仅 6 条既有 UTC deprecation warning）；Skill quick validation、compileall 与 diff-check 通过。

- worker 从论文第 6 页恢复了 PDF 内嵌的 1000×815 Fig.4 栅格，而非使用旧 targets CSV。
- 当前可见标定：Depth 0–0.8 µm（线性）；Zn concentration 10^15–10^20 cm^-3（log10）。
- 图例可绑定黑色 In0.83Al0.17As、红色 In0.83Ga0.17As、蓝色点线 D∝C fit、蓝色虚线 erfc fit。
- 两条同标签蓝色点线路径没有材料级图例区分，因此 material-specific assignment 必须保持 unresolved；不得为了闭环而强行消除歧义。
- rev2 最终性能：claim-to-finalize 737.15 s，created-to-finalize 782.76 s，主输出 15,984 bytes；900 s 边界有实测依据。
- rev2 注册附件：figure manifest 1、source panels 2、audit overlays 2、curve CSV 5、validation report 1；最终 evidence approval 必须保持整组有序主体，不得只批摘要。

## 2026-08-14 Alpha 科学闭环终态

- 已完成一次不重跑 TCAD 的完整后执行闭环：在既有 passing runtime attestation 和五个已注册 PLX 上，依次生成 exact-plan solver curve bundle、passing reference coverage、passing control-equivalence report、complete-plan curve metric report，并由独立 diagnostician 完成正式 finalization。
- 计划修订仅把三个 log10 `residual_rms` operator threshold 及其三个精确绑定的 ValidationPlan threshold 从错误的 `1` 改为 `decade`；确定性 apply 产出完整计划和 diff，其他机制、case、domain、series/evidence mapping 与阈值数值均未改变。
- 最终科学判定为 fail-closed `invalid_study` / handoff `revise`：execution identity 与 realized controls 通过，但 `num_A_refinement=0.3796432753751781 decade`，显著超过预注册上限 `0.02 decade`。因此 A-only 与 hybrid 的物理机制差异不可解释，不能形成 hypothesis assessment 或 knowledge update。
- 论文 Fig.4 比较继续因零 quantitative-eligible rows 而 deterministic unavailable；这是证据限制，不是 solver failure，也不能当作通过。B-erfc control 尚无注册的 analytic erfc reference，因此本轮 complete-plan metric report 没有 B-control score。
- 最小科学后续不是重复当前五 case 或继续修改 scorer，而是预注册一个只拆分 A-only 空间细化与时间细化的 numerical follow-up，沿用相同 whole-domain `residual_rms`，先定位 0.3796-decade refinement failure 的来源。该后续将需要新的 reviewed plan/deck 与独立 execution authorization；不属于本次“闭环跑通一次”的必需条件。
- 闭环工程结论：本轮从已有 production outputs 到确定性 bundle/coverage/equivalence/score/diagnosis 已完整跑通；没有把 unavailable evidence、未评分 B-control 或失败 numerical gate 伪装为科学成功，且正确停止在知识更新之前。

## 后续记录规则

每个新缺陷必须记录触发条件、实际行为、预期行为、可复现证据、科学/工程影响、临时绕过和建议修复。科学上的 `revise` 或 `unresolved` 不自动视为架构缺陷；只有系统错误丢失上下文、诱导伪结论、阻塞可辩护闭环或造成不必要全量重做时才记为实现缺陷。
