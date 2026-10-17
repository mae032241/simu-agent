# P3d2-b：迟批后的原 call 有限恢复

状态：**补充候选设计，待独审，未实施。** P3d1 `c03d0c3`、P3d2-a `4399149` 已独审提交。此处仅细化[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)与[已审 TCAD seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)的授权/恢复边界，不增加 session/任务/预算体系。先提交设计独审，再实施。

## 最短公共链与权限

候选在现有 `scid-research` 增加明确副作用子命令：`execution-resume --root <instance> --step <old-W> --call-id <original-call> --max-seconds <finite> --authorization-note <operator-note>`。仅在需要重申过期请求时，额外明确 `--request-valid-seconds <finite>`。调用者是现有 host/operator 信任边界；note 是审计说明，文本本身不是执行决定。现有 approval UI 继续只记录决定，点批准不启动执行。

1. 原 W 已结束并封存；host 沿同一实例 controller writer 验证其 job/native-intent/terminal/cleanup、旧 seal，以及原 allocation/request/payload/interface。原结论记载当时等待，**不恢复或冒充原 W、不重开科研线程、不改旧 job/result/seal**。
2. 通过下述**原 seal 正向完整 pending 集合**证明同 call 从未越过受控 prepare 准入，才允许首次派发恢复；否则只 query/reconcile 原身份。host 在当前原预算剩余内取得一个新的有限**控制操作准入**，有当前 boot、原 call/原件、当前 ceiling/ref 和绝对 deadline，保存操作 receipt。此时尚未发布可能派发的 `resume_intent`。它不复用原 native deadline，不增加总额或另建执行资源池。
3. 当前 exact 决定仍有效且全部绑定未变，直接复用。过期或其他需重新判定的情况，使用下节同一请求/决定协议，返回可用 review_url；本次退出，无 prepare/reserve。**待人类/renewal只保存请求 successor 与有限请求操作receipt，不发布 `resume_intent`，不形成可能派发的 unknown或unknown计费。** policy 可依法直接决定；只有原 policy 要求人类时才进入原 approval UI。以后再次运行同命令，在新的当前有限操作窗口中沿原 call 的显式 successor 链读取该决定，不能搜索“最新通过”，也不会被此前等人的操作receipt误当作已开始派发。
4. 有效 exact 决定、当前权限/资源/机会及剩余调度准入都通过后，才在 writer 内、首次 prepare 之前发布 `resume_intent`；随后 host 沿现有 prepare→Records.accept→submit 执行原 call ID。原 scope/native-attempt 继续作为历史归属，不作新的调度权限。prepare/submit 使用本次调度准入及原有 execution gate；新 admission 的时限同时约束本地操作和 RPC。accept/reservation 原件绑定不重复记一次科研机会。`resume_intent` 已发布后中断，仍按可能派发处理，不重用 fresh lease。
5. 追加原 step/call 的恢复回执，后继 A 读新事实。原 sealed 结论、当时等待与旧观测保持；本次无科学模型结论。再次执行只消费同 recovery intent 的原件/结果，不能重派。

`--max-seconds` 是本次控制推进的操作 deadline，不能当远端 job `wall_time_seconds`。后者保持原 package/request 的资源量，并受当前累计执行 allowance、原 reservation 和当前总体授权约束。长时 job 的 query/collect 也不能沿用“提交操作几秒”的 deadline；需要实际收集时，仍由预算/授权唯一 owner 在当前剩余内给有限 `CollectionContext`，逐块检查，无自动延长旧 collection 授权或把 unknown 退款。

## 合法重申及旧新决定关系

已核提交后的 d1：allocation 区分 `dispatch_deadline_boottime` 与 `job_deadline_boottime`，request `expires_at` 仍取首次 allocation 的有限有效期。W 结束本身不等于执行决定过期；必须沿现有 `status/decision` 判断。恢复入口不得修改过期 request 或让用户反复点它。若确实过期，候选由同一 `execution_authority` 增加 `renew_unprepared_request(original_request, *, recovery_admission, valid_seconds)`：仅在下述未 prepare 证明成立后，生成**新不可变 request**，显式 `supersedes=old_request_ref`，保留原 call、精确 reviewed subject/payload/来源/目标，重新取得当前 policy/resource/grant 绑定。它使用原 `create_request/record_policy_decision/record_decision` 校验，不另造批准协议。

请求的有限有效期由 operator 明确 `--request-valid-seconds`，与本次操作 deadline 分开；有效期只允许未来在各次实际调度准入内消费决定，不增加可执行秒数/字节或科研总额。不传时不猜 TTL，返回明确修复信息。重试已存在 renewal 不重置 expiry；原过期决定从不继承为新决定。旧 request 页只显示该经验证 successor 链的链接；原 UI 仍拒绝对过期 request 写决定。有效决定无需每次重审；subject/interface/源/target 变化不能借“恢复”换实现，须回原科学选择/正式审查路径，不能改原 allocation。policy 或 resource/grant 变化重新判定，旧决定不覆盖。

## 三种原件状态，单一执行/预算 owner

| 原状态 | 有限恢复可做什么 |
| --- | --- |
| **明确未 prepare** | 原作者 terminal+cleanup+sealed；原 seal 中完整 pending 集合对该 allocation 明确记载 unprepared，原 native/注册代码/host gate 原件完整，且同 recovery owner 无后继派发事件。恢复时若发现与原 snapshot 矛盾的新原件即拒绝；不从当前文件缺失推出未派发。满足时首次恢复原 call；不把该本地证明写成 P2d 永久远端 fence 或 fake completed。 |
| **reserve→prepare-intent 间断** | d1 reserve 在 prepare-intent 前，必须额外读取唯一 ledger：存在 reservation 但 gate 未返回/未跨 prepare 边界时，复用它，不 release 再 reserve。若决定需 renewal，预算 owner 只追加 exact authority 重绑事件，保持同一 reservation ID、金额与累计消费；须验证上述原 gate 原件/无 prepare 证明及旧新 request 链。证明不足保留 reservation/unknown；不由 wrapper 改余额或造永久未提交证据。 |
| **已有 prepare-intent / accepted / dispatch，或身份不确定** | 不得 fresh prepare/submit。按原 prepared/external 身份 query、lookup、既有 reconcile；lookup None/超时/取消请求均 unknown，保留原 reservation。若已经终态，用现有 observation/recovery；P2d permanent fence 仅由原 retire owner取得，只有预算 owner可消费release。此命令不把“迟批”当重跑理由。 |

同 call 并发使用原 controller/authority writer 与现有 call lease；prepare-intent 在授权 writer 内封存后才进入底层。host 调度 receipt 与原执行 authority 分别解释；不能仅为换 deadline 生成另一笔 resource reservation。跨 boot 时旧单调 deadline 不可验证，须当前 boot 的新有限调度准入；原作者死亡/cleanup、无派发证明不完整则 unavailable，不猜 session/PID。所有这些是框架已声明受控路径的软信任边界，不证明任意 native 行为从未发生。

## 收口一：原 seal 的正向无 prepare 证据

候选 `execution_authority.capture_pending(root, job)` 仅在原作者 native-outcome 已 terminal、真实 owner/group cleanup 为 `observed_group_cleaned`、完整 native attempt 链可验证后，在**原 authority writer** 内生成不可变 `native-evidence/<step>/pending-execution-set.json`。由 `contracts.seal_result` 写入原 `seal.pending_executions` ref；seal/后续独审/恢复共用 `verify_pending_set(root, seal, allocation_ref)`。没有该正向 receipt 的旧 seal，或 `complete=False`，不能事后补一个“当时未派发”的证明。

receipt 含：原 job、全部 attempt 的 intent/outcome/process/cleanup proofs、真实 code/interface/host-gate 合同，以及此 job/attempt 的**完整 allocation 集合**；每项绑定原 call、allocation、完整 request 集合、payload/review/target、原科学 mechanism/grant、当时 authority/reservation（可为 None），并明确记录 `prepare_intent/accepted/dispatch/external` 的 proof 或 None 与 disposition。扫描来源只用现有 authority calls/requests 与 Records，不新建 registry；缺归属、半写/未归属目录、集合歧义或不完整 owner 信息都只令 complete=False，不中断普通科学封存、不授恢复资格。所有已有 call 原件/目录也须列入该完整清单，不能仅挑一条好看的 pending request。

原 gate 已在 authority writer 内先持久写 prepare-intent，才能返回并触达底层 prepare/upload；原 outcome 出现后正常 `_remaining` 已拒绝新 dispatch。snapshot 持同一 writer，原 owner cleanup 已确认，因此 unprepared 是**在原封存时记录的受控路径事实**。恢复跨 boot 复核 snapshot/seal/code/cleanup 与所有显式 refs，绝不拿新 boot 的 PID 缺失或当前目录空白代替该事实。文件/存储掉电的信任前提是这些不可变原件及 seal 已完整持久保存；任何缺失/半写/矛盾都 unavailable。它不证明绕开声明路径的 arbitrary native 行为，也不支持重建遗失原件。

在正常 allocation 时，原 scientific mechanism 选择须以已有 `breadth.admit` 规则冻结到 allocation；迟批不能由恢复者另选机制。恢复准入再次用当前 `search` 的同一 accepted/grant 计数判定该原机会仍可消费，不改原 binding、不新发机会。此时不计 accepted；只有实际原 call accepted 后计一次。

## 收口二：同 recovery owner 追加 pending→terminal

继续唯一 `execution_recovery.py` 与原 `host-history/execution-recoveries/`；保留旧单文件 unknown→terminal 合同。新增事件放 `.../<source-step>/<call-id>/<seq>.json`，每项带显式 `previous` ref、原 source seal、pending-set/allocation/request refs、同一 call/scope，不能覆盖旧文件。`prefix` 同时收旧 receipt 与完整新事件链；已存在 job 继续使用其 `job.history.execution_recoveries` 冻结前缀，后续追加不回溯修改旧 A 的输入/科学结论。

| 新事件阶段 | 必要事实与唯一投影 |
| --- | --- |
| `resume_intent` | 在任何新 prepare 前保存当前有限调度准入、原正向 unprepared 证据及所选 exact request/decision。尚无 accepted，不伪造 managed row，计数仍零；公开为正在恢复/unknown，并阻止同 call 或冲突新 call 重放。中断后的该事件不能当 fresh lease 重用。 |
| `accepted` / `status` | 原 Records accepted 原件出现后立即追加，不能等 terminal：归档原 accepted/prepared/reservation/submission（存在时）及由同冻结 adapter 核身份得到的 query 原件。native queued/running/cancelling 作为原 pending 事实保留；没有 verified observation，普通 managed row仍是 unknown，无 fake completed。此后 call 计数一次，unknown/pending 保留原资源 reservation，阻止冲突新 call。相同事实重读幂等，状态变化只能追加下一 seq。 |
| `terminal` / `not_submitted` | 仅引用现有 `verify_observation` 或 P2d `verify_retirement` 认可的原件；不自造工程终态。更新该 call 的派生投影、清除对应 pending/unknown 阻塞，accepted/机会计数不减少。settle/release 仍仅 budget owner消费原 reservation。 |

统一 `execution_recovery.call_view(root, sources, prefix)` 按完整链取得每个 `(source_step,call_id)` 的最新事实；旧 `resolved` 只返回 verified terminal/not_submitted，**不能把一个 pending key 当已解除 unknown**。`project_records` 对原 unknown row精确替换；对原零 accepted 的 sealed W，在派生 copy 中加入新的真实 accepted row，并单列无 accepted 的 resume-intent。原 observation/seal 不改。`history`/`lineage`/A实验页消费同一 view，pending 不再因无 execution/completed 而被跳过；native originals仍用已有归档原件/明确配额路径，没有第二状态账。

`search.fold` 的 opportunity/grant counts 与 unknown 从该同一 call view 推导，按原 accepted identity **去重一次**；terminal/status后继不再加 count，resume-intent 无 accepted 不计机会但保留阻塞。每条已封存科学 source 的 `apply_source` 先使用**该 job 当时冻结的 recovery prefix**恢复机械计数；fold末尾才叠加调用者请求的 prefix供后继准入，不能把迟到 accepted 回填到更早 A 的科学解释。`_managed_refs/_screen_refs` 不自动把旧 W 当时等待改成已完成科学判断；新 A 只读取追加原始事实作自己的结论。旧 W 的 node/slice/repair/portfolio 投入不重新计一次。

`experiments` 新 call准入、`budget.execution_blocked/inactive` 与 `managed_wait` 的只读 clock 分类都消费同 owner 的 pending view：有可能在派发的 unknown继续消耗/阻止退款；已知 remote pending按原 waiting处理；明确 unprepared 且只待人类的 idle不伪装运行。host恢复本身持当前 controller writer，因此不能与另一个活 controller/W 并行派发。没有新的科研调度循环、session管理或预算池。

## 最小文件责任、消费及负控

`cli.py/controller.py` 只新增显式有限恢复入口和现有 writer；CLI 与 P4c owner协调独立 execution-resume parser/dispatch区块，待其提交后串行。`execution_authority.py` 持 pending集合/调度/renewal 原件及共同验证器；`budget.py` 仍唯一检查当前剩余、调度消费与 reservation 重绑，复用现有 ledger/clock 而不是借用 delivery 专属 `accept_action`。`experiments.py` 复用原 prepare/accept/submit 与原 call身份；原注册 factory通过非JSON可信 recovery services消费已验证调度receipt，不能改旧配置、选择另一factory或用 JSON allow/resume 开关。`instance_ui.py` 只补过期请求的已验证 successor 链接，不加执行 HTTP 路由。

`contracts.py` 只在原封存加入/验证正向 pending-set ref；`execution_recovery/history/lineage/search/managed_wait` 仅接上面的同一 view；native/runtime 复用现有 terminal/process/group cleanup原件，不另造跨boot清理证明。对已有 accepted 的 query/reconcile 不触发 prepare/submit；如 terminal 收集所需原操作窗口过期，本次明确有限 host调度可给新的维护 `CollectionContext`，受当前总体剩余、原权限/target/reservation和冻结 runner policy裁剪。它保存新的维护窗口 receipt而不改旧 window，不延长 solver/job grant，不自动刷新collection额度。

`authority.implementation/freeze` 必须从 `verify_pending_set`、`execution_recovery.call_view`、实际恢复准入及其直接原件验证函数的真实 owner module自动取得 code proof（包含 `execution_recovery.py`/实际新增helper）；不能靠插件手列来pin共通准入/计数，不递归扫描整个依赖树或另造注册框架。`status` 仅事实变化才追加事件，同一事实轮询/重复模型输出幂等，不持续重造状态。

只写最小负控：有效决定迟用不重审；过期原 request拒绝且新request链/UI可达、重试不延长TTL；没有原seal完整pending集合/cleanup、篡改或丢原件、活owner/lookupNone禁止派发；reserve窗口重入同reservation不退额不翻倍；原零accepted→resume-intent→queued/cancelling→terminal在同ref链/A/history/search中及时可见、计一次且旧A prefix/原seal字节不变。不得执行动态/安装/模型/solver；本文尚未验证真实跨boot或掉电。设计PASS并提交后再明确实施owner、分块冻结供代码独审；不先编码。
