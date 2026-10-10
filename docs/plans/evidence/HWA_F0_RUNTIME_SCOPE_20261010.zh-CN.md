# HWA F0 运行缺陷与改动归属核对

日期：2026-10-10。范围：只读源码与既有脱敏审计；本次仅新增本文，未修改生产、运行测试或模型、恢复 o4。真实后续测试按用户限定只用 cov，本记录不授权任何场次。

## 1. 冻结口径与结论

- 当前开发仓库：`123/scidiscovery-e5.2`，分支 `dev`，HEAD `4e66923bf79ab26ebf27d9f559932b98231b5102`。以下源码行号针对本次读取时工作树。
- o4 冻结快照标识：`369d4795d4949032d8dd4f881cd568603c6fc635`；对应文件来自外层 `.trial/os4`，不是当前开发仓库的 Git 对象（`git diff 369d479...` 返回 bad object）。没有把它当作 HEAD 祖先。
- B1 已有原生日志链条；当前 `codex_progression.py`、`progression.py` 与冻结文件逐字相同，缺陷仍在。
- B5 三道限制在当前生产入口静态可达；没有本次动态复现。“64附件”必须拆为默认附件 `max_files=64` 与工具尝试总数64，不能互相替代。工具尝试已在开始时预检；附件也已在保留事务前及锁内检查，不能概括为全都最终才失败。
- dirty 的 helper release 三文件已包含在 o4 快照，不能当作针对 o4 根因的新修复。另四服务文件的修改属于自动采集的科学来源限制，未改变恢复/轮换顺序或容量数字。

证据分级：**原生日志已证实**表示已有审计引用具体事件，本次未重新打开完整原生日志；**静态可达**表示当前真实入口存在该路径；**需测试**表示尚无本次执行证明。平台内部槽位分配、`pending_init` 内部赋值及释放机制仍未知。

## 2. 证据入口与缺陷责任

外层证据仅按精确文件读取，未全仓扫描；未复制凭据、管理 URL、原始任务内容或私有绑定。

| 问题 | 精确既有证据入口 | 已证实 / 限制 | 责任节点与模块 |
|---|---|---|---|
| B1 已完成线程恢复后容量失败 | `.trial/tokenfix_20261010/native-slot-root-cause.md`；`.trial/covopt_20261009/round4-audit/thread-limit-root-cause.md` | 0.160.0 原生 Root：02:15:15–18 UTC 三个历史完成线程被 resume；另外恢复遭父线程未加载/容量满；02:15:59 新 W2 spawn 失败；interrupt 后仍满；followup 产生额外无工具回合后再次 spawn 成功。实际 Root 轮换未完成。只能证明外部调用、加载与容量失败链条 | F1a；`platforms/codex_progression.py`、`artifact_agent/service/progression.py`；helper 释放合同为相邻边界 |
| B2 凭据传递损坏 | `.trial/tokenfix_20261010/packaging-followup.md` 的 A2 节 | 签发417字符可解析、调用385字符不可解析；具体损坏环节未定，不推定身份错配 | F1b；Worker bootstrap、connections、可信宿主挂接 |
| B3 挂接失败后空等 | 同上 | A2 queued、Root idle、备用挂接未执行；通知唤醒完整因果未核验 | F1b；attention/dispatch/Worker 挂接恢复，需要独立入口用例 |
| B4 路径拒绝 / 二进制不自动保留 | 同上，W1 机械封装节 | 日志与运行 JSON 的任务绝对路径命中路径规则；不是发现密钥；模型/数组 metadata_only，阶段引用拒绝。当前规则仍在 | F2b；`artifact_capture._Guard/_media/_resolve`、attachments/CAS |
| B5 历史容量继承阻断 | 主计划 B5 / F2a，当前源码入口见第4节 | 当前静态可达；没有本次动态复现，不将 R2 的旧结论直接升级为本版验收结果 | F2a；attachments、tool_evidence、reference_proofs、schema/tool_evidence、冻结 settings |
| B6 owner/helper 重复读取 | `packaging-followup.md` 的 A1、W2 节 | 已有读取重叠；W 需编辑源码的读取不能全部记浪费；独立复核也需保留 | F3；helper 材料/读取范围、启动投递及概览 |
| B7 基线失败归类 | 本文没有测试执行；由 F0 总清账接入具体失败列表 | 不根据测试名猜测失败原因；第5节仅列确定需要变更的旧断言与待执行节点 | F0 总清账；各节点按真实失败关闭，本文不宣称完整清账 |

o4 已停止的事实来自既有记录；本文未独立核验进程存活。冻结记录中的 H/W1/A1/W2 封存和 A2 未完成必须保持，不记完整两轮 HWA 或成功验收。

## 3. B1 的当前生产接线

1. `progression.py:1368` 在下一 Root 回合开始前调用 `_rotate_if_due`；`:840–850` 使用累计 input/rounds 及 Root 终态/未知提交/请求/admission 检查。`:854` 取整个绑定 cohort，并非只取 queued/running Run。
2. `codex_progression.py:79–85` 的终态缓存有效性要求当前连接、精确 binding、connection、event_version，且 `native_subscriptions` 命中。该字典只能由 `:87–95` 的 `_subscribe_native` 经 `thread/resume` 写入。
3. `rotation_boundary :169–224` 对未知/失效证明的成员先 resume (`:186`)、后 read (`:198`)。完成成员也走此路；恢复成功后若其他成员失败、检查预算不足或整体 unsafe，没有撤回已加载线程的动作。`progression.py:875` 直接放弃本次轮换。
4. 活动 Run 检查在 `progression.py:883` 的锁内 prepare，晚于 `:869` 的全部探测。因此活动任务已经足以阻止轮换时，仍可加载历史线程。锁内活动/cohort/证明复核有必要，前置检查可减少副作用，不能取代它。
5. 重连另一入口：`progression.py:829–838` 以 owner Run queued/running 判断，对该 Run 的 worker/helper 调用 `restore_worker`；`codex_progression.py:237–254` 先 resume 后 read，允许 helper 已终态。owner 活跃并不证明 helper 活跃。此路径静态可达；o4 已知原生日志定位的是 rotation probe，不能写成已证实重连触发。
6. 当前 dirty `worker_connections.py:243–252` 返回 `native_action=interrupt` 和未知原生状态；`helper_tool.py:32` 要求释放后执行。控制层没有执行平台动作或证明槽位回收。o4 已含此改动，实际 interrupt 未解除 pending_init 容量满；其正确可用结论仍只是撤权与操作指令。

F1a 最小实施切片：复用现有 binding、connection/event_version、终态 proof、usage ledger 和锁，不增加另一代理状态库。先在 `_rotate_if_due` 探测前查活动 Run，锁内保留原复核。观察路径改为精确只读 thread/read 与本连接真实终态事件；读失败、身份不一致、零turn未证实、读中活动变化、连接变化都保持 unsafe。对恢复入口先 read，仅确需继续执行者 resume；已完成 helper 保留计量身份而不加载。完成读取的缓存安全和 late usage 处理须一并评审，不能只删除 subscription 条件。

F1a 无模型最小复现设计：在已存在的真实 coordinator→Codex host→AppServer 管道夹具下保存一个 completed owner/helper，再重建 host/coordinator，让 Root 达到轮换阈值；记录所有 RPC，断言历史完成参与者只有 thread/read、无 thread/resume。另设 queued/running Run，断言调用轮换探测前即返回且无参与者 RPC；锁内插入新活动依旧阻止轮换。恢复用例包括 owner 活跃/helper 已完成与真实 inProgress，后一项才 resume。失败、identity/session 不符、零turn、读中 turn/started、断线、重连、late usage 均保留安全栅栏。

原生容量验收仍待 F1a/F4：隔离新候选、同生产入口、串行锁下观测“任务完成→轮换检查→下一任务派发”；不启动已停止 o4，不把 fake 无 resume 断言或 interrupt 返回当原生名额已回收，不用付费空 followup 作修复。

## 4. B5 的三道限制与恢复口径

| 限制 | 当前真入口与事务边界 | 恢复影响 / 后续用例 |
|---|---|---|
| 附件 `max_files` | `agent_execution_settings.py:116–121` 默认64、允许1–128；冻结到 `run.recovery_policy.attachments`。公开 `worker_publish_files`→`attachment_tools.py`→`ToolEvidenceMixin.publish_attachments :248`→`attachments.publish_attachments :237`→`retain_attachments :104`。`:116–128` 注册前预检，`:197–202` 写事务中复核；相同 publication_key 不重复扣数。自动采集调用同 retain 路径 | `tool_evidence.adopt_tool_evidence :899–905` 对旧附件按同 max_files 验证，`:990–992` 将适用旧回执插入新 Run 当前表；因此后续 retain 会把历史附件算现有附件。满64旧附件 + 1个新文件静态可达拒绝，需生产入口复现；自动采集还会生成 inventory 附件，必须纳入边界数 |
| 非 reference_access 证据总数128 | `attachments.py:122`；`tool_evidence.accept_tool_evidence :492`；reuse `:599`；`schema/tool_evidence.py` 的 `records max_length=128`；`reference_proofs.encode_snapshot :22–35` 再校验完整 wire。reference_access 另有 accesses32，不能当附件数 | adoption 的完整 union 在 `tool_evidence.py:969–992` 编码后才提交；继承插入当前表会占当前128集合。测试 127/128 + 新记录、reference_access 不扣记录数、相同key重试不重复扣额、失败原子回滚 |
| 当前+恢复 origins 工具尝试64 | 真实公开 Worker工具执行的 `mcp_local_worker.py:270`→`begin_tool_attempt :300–318`，事务中 count + `_recovery_attempt_count` 达64即拒绝，发生在 handler 之前。`_encode_evidence_snapshot :627–635` 再查合计；schema 的 attempts64/ancestors64；`reference_proofs.material_snapshot :122` 查所选闭包合计 | `recovery_tool_proof :648–688` 从 draft_from/resume_from 原 sealed DB 递归重建后展平 origins，不接受 Worker 副本；满64祖先 + 零当前可以新增不带尝试的附件（若另外两项及字节允许），不能发第65次受控工具调用。不得断言“64工具回执会阻止任意新附件”；超过64全证明会在附件编码阶段阻止提交 |

恢复的真实接线是 `runs.py:865` 调 `adopt_tool_evidence`，不是只在最终输出读取旧清单；该接线可把历史证据物化为当前记录。来源不适用的回执在 `tool_evidence.py:959–962` 跳过，只留原 draft/proof，不当当前科学证据。按选择材料生成 `material_snapshot` 已能缩小必须依赖闭包（`:49` 起），但全任务恢复证明仍累计64；不能把已有“选源 proof 修复”当历史执行预算/新增记录容量已经分离。

另有单次表单边界：`attachment_tools.PublishFiles.files` 最多64项，是单次输入数组限制，不等于整任务 `max_files`；`source_aliases` 最多128。`operations/tooling.py:35` 的 `record_attempts` 默认 False，公开 publish_files 没有开启该字段；`mcp_local_worker.py:269` 仅对开启者 begin_tool_attempt。因此“64尝试阻止任何附件”不是当前入口语义。完整 proof 还有1MiB编码上限与冻结旧合同兼容检查（`reference_proofs.py:19–35`、`tool_evidence.py:698–706`），放宽单个数值不能绕过这些界限。

阶段入口 `mcp_local_worker.py:808` 的 capture_science 与最终 `runs.py:2266–2267` 的 capture_candidate 均进入 retain；`artifact_capture.py:639–641` 的最终 capture 新内容，以及 inventory 生成，需同时覆盖。已封存同 key 复用存在；这不证明并发、恢复或大批引用能完整续接。

F2a 最小复现设计（当前未执行）：通过公开 operation_invoke / attached Worker（或已安装通用插件夹具）分别造 64 附件、128非access记录、64受控工具尝试的原 Run，合法失败封存后用 draft_from 续接相同准确输入。区分①新增附件②新增受控工具调用③阶段后最终原样复用；记录拒绝位置、remaining口径和失败后回执数。64尝试且附件未满时新增文件应作为负向混淆对照；64附件和128记录分别有各自独立阻断。保存旧 receipt bytes/hash，身份不变，不通过改名或新任务重置 loop 已授权预算。额外验证自动采集 index、直接publish、阶段/最终、重试及恢复消费者。未完成这些用例前，F2a“可续接满额历史”验收保持阻断。

B4 静态仍在：`artifact_capture.py:64–65` 将 `_SECRET` 与 `_MACHINE_PATH` 一起拒绝；`:106–111` 自动 media 不包含 pkl/npz。dirty 来源限制不改变这些逻辑。F2b 须保留原件哈希、读/执行分离及越界/秘密负例，不能通过 Worker 改写模型规避。

## 5. 现有测试位置与应调整断言

以下只是可执行节点定位，本次均未运行，不能标 PASS。

- `tests/operations/test_progression_rotation.py::test_active_worker_defers_rotation_and_can_finish_under_original_binding`：扩充无参与者探测 RPC 断言；现有只证明没有 Root start。
- 同文件 `test_rebuilt_coordinator_resubscribes_terminal_cohort_and_rotates_without_new_turn`（`:865`）、`test_new_app_server_rechecks_persisted_terminal_proof_without_loading_old_history`（`:983`，`:1002` 仍要求一个 resume）、`test_fast_complete_task_subscribes_on_production_rotation_without_new_turn_or_permission_override`（`:1015`）：这些当前测试明确要求完成成员 resume。F1a 应按新的只读观察合同更新；不能保留旧断言再声称回归通过。它们不是本次发现的测试执行失败。
- 同文件 `test_production_started_notification_during_other_read_invalidates_rotation_fence`、`test_terminal_cache_binding_expires_when_actual_worker_thread_is_reused`、`test_protocol_empty_thread_requires_closed_never_started_task`、`test_protocol_1500_cached_terminal_bindings_need_no_rpc_and_unknown_cohort_is_batched`：复用事件变化、binding失效、零turn及有界分页/计量防线。
- `tests/operations/test_scientific_attachments.py::test_attachment_recovery_reuses_exact_receipts`、`test_reference_access_does_not_consume_attachment_receipt_allowance`、`test_attachment_publication_and_retry_allow_large_binding_aggregate`：扩展真实满额继承边界。
- `tests/operations/test_reference_proof_transactions.py::test_legacy_large_recovery_proof_allows_tool_call_and_finalization`、`test_new_receipt_checks_complete_snapshot_budget_before_commit`、`test_final_submission_reports_control_proof_limit_and_retains_draft`；`tests/operations/test_contract_attempts.py::test_attempt_limit_and_interrupted_calls_preserve_existing_receipts`：核对完整 proof 与开始预检，新增满64恢复/新增文件对照。
- `tests/operations/test_artifact_capture.py::test_stage_versions_scoped_paths_native_completion_and_receipt_reuse`、`tests/operations/test_candidate_attachment_recovery.py::test_actual_stage_and_final_candidate_correction_preserves_frozen_roots_and_original`：覆盖阶段/最终复用及既有修表单边界，不把修表单当容量设计修复。

## 6. dirty 归属与可复用提交范围

逐字比较使用 SHA256 与 HEAD git-show，未依赖不可用的冻结 Git 对象。外层 `retest-source.json` 的三项散列与当前和冻结文件都相符：

| 文件 / 行为 | 当前与 o4 frozen | 当前与 HEAD | 提交归属 |
|---|---|---|---|
| `platforms/codex_progression.py` / `service/progression.py` | 相同 | 相同 | B1 未修；F1a 独立拥有观察/恢复/前置活动检查及相应测试 |
| `service/worker_connections.py` | 相同；SHA256 `c47fa6c6c4a157042060563e8ec312ec70db9f1e1db93ac056d7ed45001282b8` | dirty | 已有 release 中断指令，可复用合同，保留未知状态；不能声称回收成功 |
| `helper_tool.py` | 相同；SHA256 `6f8ae5d8c52a9c714fb35608c3268fc905c2162c75d27c343aca97d993aa938e` | dirty | 与上一项及下项作为一个 helper释放合同候选切片，须独立验证/评审 |
| `tests/operations/test_r4_internal_helpers.py` | 相同；SHA256 `1351c50ed92ba3306e179307904ce55050e4eb364b8e65c400306b7497f3edd1` | dirty | 配套释放幂等和未绑定不猜身份；不证明 native slots |
| `service/artifact_capture.py`、`attachments.py`、`scientific_usage.py`、`tool_evidence.py` | 不同；冻结均等于 HEAD | dirty | 同一科学来源限制行为：保守按任务输入限制、task_inputs_v1、provenance_basis、旧 markerless fail closed、恢复限制传播；不是 F2a 容量或 F2b路径/二进制修复 |
| `tests/operations/test_capture_scope_restrictions.py`（untracked）与 `docs/PLUGIN_RUNTIME_API.md`、`CONTRIBUTING.md` | 未作为冻结运行差异完整核验 | 当前新增/dirty | 上一来源限制切片的候选测试/迁移说明，应一起独立审查；不能因本文阅读而记验收通过 |
| 两旧计划、README、DEV_HANDOFF及新主计划/evidence | 独立文档改动 | dirty/untracked | F0/文档协调拥有；不能夹带进入 F1a 生产修复提交 |

不可混合：F1a 与 F1b挂接、F2a容量、F2b封装、来源限制改动；helper释放合同如一起提交，须说明它对同一F1a行为的必要性并完成生产动作证据，不能仅靠提示语扩成槽位回收修复。来源限制四服务文件及配套测试/合同说明应保持原作者改动，不撤回、不拆断其行为。

当前观察中，F1a最小生产范围是 `codex_progression.py`、`progression.py` 和定向 rotation/reconnect 测试；真实原生容量验证是独立待验证项。本文可以交独立 F0 审查，但不替代 B2/B3 全挂接链审计、B7全失败清账或进程停止核验。

## 7. Root补充：本轮停止与工作区核对

本轮Root通过可读`/proc/*/environ`核对CODEX_HOME准确指向o4的进程，未发现匹配。时点、不可读/退出进程数见外层`.trial/hwa_revision_20261010/f0/o4-stop-check.json`；这不是全机不可见进程证明，不把DB旧active/心跳状态改写为成功完成。工作区归属快照见同目录`working-tree-before.json`，含HEAD、分支、dirty路径和文件摘要；未改他人生产文件。
