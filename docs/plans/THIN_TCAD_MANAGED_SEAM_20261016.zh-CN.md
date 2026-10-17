# TCAD managed 执行薄接缝建议

状态：**待独立设计审查，未实施**。依据[已审批迁移计划](THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)的 P2/P3；本次仅静态读取代码，不运行 pytest、模型、SSH、许可证检查或 solver，不读取凭据及隐藏评分。P1 的并行实现不由本文修改。

## 1. 唯一状态归属

新实例仍由 `research_loop/{experiments,managed_wait,continuation,budget,history}.py` 拥有 call、节点、预算、等待/唤醒和封存事实。TCAD 服务自己的 `submissions.sqlite3` 只负责远端 job 幂等、进程与 retire 墓碑，不升级成第二份科研实例或预算权威。

复用现有 `ExecutionInterfaceRegistration` / `RuntimePluginFactory`，新增一个 TCAD managed wrapper；它组合现有 socket/command adapter，不复制 SSH 或 solver runner。wrapper 使用 `experiments.Records` 的 accepted/submission/completed/observation；不得导入旧 `RunService`、`ExecutionService` 或 `ExecutionBridge` 来生成影子 Run、Artifact 和预算池。

默认 `terminal_evidence_kind='adapter_result'`、`result_protocol=None`（opaque）。TCAD 原件不是本地 Python 输入快照，不声明 `scidiscovery.local-result.v1`，不填假 `entry/command/snapshot_files`。领域候选、评分、重放和交付映射另列能力/验收，本节点只交接原件与工程状态。

## 2. 复用函数与确切缺口

以下文件均在 `plugins/tcad_artifact/tcad_artifact/`，新层入口为 `src/scidiscovery/research_loop/experiments.py`。

| 接口 | 原函数直接复用 | wrapper / 最小公共接缝 |
| --- | --- | --- |
| 注册、能力 | `runtime_plugin.build_runtime`；两 adapter 的 `capabilities` | 当前 factory 在 `local_worker` 只返回 tool_services，新 `_adapter` 要 execution_adapters；P1 选中的 managed binding 必须返回后者。补 `code_assets` 与真实 `LifecycleCapabilities`，冻结 factory、adapter、packager、transport 代码/公开配置；私密环境不写 W 材料。 |
| prepare | `validate_preparation_payload`、`project_packager.validate_execution_package_json`、`package_execution_package_json`、底层 `prepare` | 新 dispatch 固定传 `research_loop.v1`，旧 adapter 只接受 `tcad.execution-package.v2`；wrapper 明确验证 TCAD package 后转换准备 profile，不将任意脚本当 package。`resolved_inputs` 目前依赖 `materialize_execution_inputs(..., artifacts, ...)`；应抽出“精确原件读取/metadata核验”的窄回调，使用新层已冻结源，保留槽位、类型、哈希、storage quota 检查。无可解析来源即拒绝，不能构造假 Artifact 服务。 |
| 接受、派发 | `Records.accept/bind_external`；底层 `validate_submission_protocol`、`submit(..., authorization=...)` | 补 `acceptance_metadata`、`dispatch_lease`：绑定 call/scope/native_attempt、prepared descriptor、真实授权原件。提交前确认同一 accepted、原准入、授权和一次派发意图；不再 accept 或申请新 grant。生产授权 gate 必须在远端 prepare/upload 前及最终 submit 前生效。 |
| lookup / query | 两 adapter 的 `lookup_submission`、`status_details` | 旧 status 参数是 external_run_id，新 managed status 参数是 call_id。wrapper 只从原 Records 解析，核 returned run_id、prepared digest 与原调用，绝不按目录或“最新 job”查找。lookup 未发现不证明从未提交。恢复沿 `original_configuration/original_adapter`，不用当前 attempt 替换原配置。 |
| 终态、收集 | `status_details`、`collect_with_budget` / `collect`；`TCADRuntimeManifest` | 旧接口缺 `result(call_id)`、`collect_original` 与共同 completed。补精确终态投影，绑定原 call/scope/mechanism/external ID；把 native manifest/日志/outputs 的本地 descriptor 留存后交 `record_observation`。使用新剩余期限构造既有 `CollectionContext`，不套旧 pool。冻结后 history 只读 retained 原件，不 live query。 |
| cancel / retire | `cancel`、`retire_submission`；服务 `tcad_retire_submission` | `cancel_original` 只作用原 external ID；无外部 ID 时用原 prepared digest 原子 retire。retire 返回 found 则绑定原 job 后取消；只有明确 `retired=true` 才可证明未提交结束。新公共契约当前没有 retire seam，需增加一个可选、默认 unavailable 的原调用操作，复用原 call 记录；不能把 lookup None 直接当 abandoned 或退款。 |

`submit` 的 descriptor.name 在旧 prepare 后可能不是 call_id；wrapper 必须保留调用者给出的原 call_id（更名 descriptor 的 name 不改变其字节），不能以底层文件名生成第二个调用身份。 生命周期声明仅在实现对应桥接后启用 lookup/query/cancel/collect/atomic_admission；`resume_original` 默认 false，不把远端 job 能继续运行误报成原生 W 会话可续接，后者仍由冻结 native launcher/session 策略判定。

## 3. 状态映射与等待时序

旧 `TCADExecutionFacade.tcad_submit` 返回 `accepted`；随后 status 也可能继续返回 `accepted`。当前 `managed_wait.before_seal/wait_and_wake` 只识别 running/succeeded/failed，不能靠现有分支直接声称 TCAD 已兼容。

| TCAD 原状态 | 新层行为 |
| --- | --- |
| accepted / 明确 queued | **非终态，保留原状态**。只有原 accepted + external ID + 与原 prepared digest 对应的可信 backend 接受/排队事实，才进入等待；不伪称 running。缺少这份证明仍 unknown。TCAD 当前未显式返回 queued，不凭空合成队列事实。 |
| running | 原身份与后端执行事实核对后等待；不封存最终科学结果，不启动下一 fragment/后继 W。 |
| succeeded / failed | 同 call reconcile，验证并保留终态原件，再唤醒原 W；failed 仅是执行工程状态，不产生科学不合格结论。 |
| cancelled | 明确的工程终态，保留 native state=cancelled 和取消原件。建议在现有公共“执行未成功”状态 `known_failed` 内增加受原件绑定的取消原因；`status_details.state` 仍返回 cancelled，公共终态识别显式接纳它，不由 wrapper 伪造 failed。A/W 看到取消原因，不能将其当科学反例。 |
| cancelling | 有原身份及明确取消处理中事实时保持非终态等待；cancel 请求成功不等于终态或清理完成。 |
| unknown / 响应丢失 / 外部 ID 未知 | 保留 unknown 与原 reservation，只查原 lookup/status/retire；不新 submit、不换 call、不退款、不按“超时”猜 failed。 |

状态判定集中复用公共执行模块；query、progress、waiting、history 以及 `_dispatch_descriptor` 的旧 call 准入扫描使用同一映射，不各写 TCAD 特例。accepted/queued/running/cancelling/unknown 的原调用均阻止新 call；不能只在模型返回后的 waiting 分支拦截，漏放同 turn 或独立 CLI 的第二次 dispatch。公开视图可显示 accepted/queued/cancelling，不能丢掉事实后只显示 running。

正常流程复用 G3：

1. 工具提交前持久化 accepted/派发意图；接收回执后持久化同 call 的 submission，再返回原 W。该事实先于任何控制层等待/释放动作。
2. 原 W 正常结束当前 turn 后，保留现有 native returncode 为整数0、无 stop_reason、usage 已知、raw hash 匹配及原 writer 已退出的 gate；控制在 fragment continuation、最终 seal 或后继 LLM 前核对非终态，停止原 writer，冻结 checkpoint 与 `execution-waiting.json`，然后仅控制进程轮询。现有入口是 `managed_wait.before_seal`；扩展它接纳有证据的 accepted/queued/cancelling，不另建监控账本。
已知失败的原生 Worker 不因远端仍 pending 就自动进入 waiting 或自动 wake；分别报告 native 失败与远端状态，沿既有 qualified 续接及预算流程恢复，不能把失败输出当可封存 checkpoint。

3. 若控制在 turn 完成与 waiting 写入之间退出，重启从同一 native outcome + 原 accepted/submission 补建等待；不重放模型或执行。这里不声称能在尚未返回的 native turn 中强行注入/挂起模型；若 launcher 不能终结该 turn，保留原 runner 并报告能力限制。
4. 已持久化 waiting 后，正常 `run` 有界间隔自动监控，不让用户反复 run。终态 reconcile 只冻结一次，原 session 的 `continuation.wake_start` 先写 intent 再 launch，W 消费 retained proofs/outputs 后才最终 seal。无合格 session 能力时保留 checkpoint 并报告 unsupported。
5. 暂停不发起新 wake，重复通知/控制器重启不重复 launch；已接受但结果未知的 wake 不能补发。等待不花 LLM token、不增 advance_seconds，仍受冻结 active/elapsed 总授权期限及实际执行资源规则约束。同 boot 恢复与跨 boot 限制分开，不扩旧授权。

已 sealed unknown 的旧事实继续走现有 `execution-recover`：追加同 call 恢复事实，新 job 冻结恢复前缀并得到新原件；不改旧 seal、旧 prepared job 或原计数。不能只清 search.prior_unknown 而不挂正式材料。

## 4. P3 必须先完成的规则与存储接缝

P2 可先用无真实远端副作用的 fixture；**真实 TCAD 生产执行必须等待下列 gate 合格**，不因 adapter 已注册而启用。

| 规则来源 | 可复用内容 | 不可直接复用的状态依赖 |
| --- | --- | --- |
| `service/scientific_usage.py:output_sources/scientific_use_restricted`；`reference_proofs.py:material_snapshot` | 精确引用、declared derivation、工具 receipt/输入 digest 的依赖闭包；受限来源传递、缺失/歧义 fail closed；reading view 不取得科学证据资格。 | 现函数依赖 Run SQL、Artifact envelope、工具 records；提取纯遍历/校验规则，由新 immutable 输入/成果/执行原件供边，不能调用旧库同步镜像。新输出自动继承绑定源限制，不能由模型清标签；无精确边时保守处理。 |
| `operation_origins.py:review_author_runs`；`worker_connections.py:review_authors/_require_independent` | 作者集合来自精确 producer/声明的作者继承；所有参与作者的实际 session/thread 都须排除；身份未知不授资格。 | 旧 Run lineage、worker_connections 表与 MCP attach 不能搬来。新层从原 native session/participant 证明与 sealed subject 解析；角色名=A、不同节点号或模型自称独立都不足够。 |
| `experiment_execution.py:_required_review/_review_payload` | exact subject、当前审查合同、已封存 pass；普通分析不等价正式审查；修改实现需新 review；预算授权不覆盖审查失败。 | `latest_subject_review` 的旧 Run 查询不复用；新层显式绑定所消费的 qualification receipt 及其精确 subject，不能运行时全局取“最新通过”。`validate_execution_package_eligibility` 目前只校验结构，package 内 pass 文本不能代替该 gate。 |
| `schema/approval.py:subject_set_sha256/execution_decision_authorizes`；`service/executions.py:authorize` | 精确 request+payload subjects、request/decision互绑、执行授权专用选项、合同身份、过期/撤销规则；`approvals.record_ui_decision` 的 nonce/幂等/仅 UI 写决策规则。 | 复用判断，不复用旧 ExecutionService/approval Artifact 表作为第二权威。P3 在新实例拥有不可变请求与人类决策原件，复用既有 UI 展示原语；聊天、A结论、任意 approval JSON 均不授权。 |
| `execution_policy.py:ExecutionPolicySnapshot.admission/execution_admission`；`collection_context` | 管理员策略、单次资源/runner能力、policy digest、明确 policy/require_human_approval/deny；收集 deadline 裁剪。 | `execution_admission` 当前 budget_key 是请求指纹，旧 bridge 随后替换为科学 budget owner。新层必须用原实例/科学授权累计；不能每个修订 package 获得新池，也不能把未知用量当0。累计 solver 资源 reservation/settlement 接到新 budget，未完成前真实执行 blocked。 |

最小授权顺序：来源/资格核验 → 精确 request/payload 与 policy/资源预算冻结 → policy 明确允许或人审授权 → 远端 prepare/upload → 原件/策略复核 → accepted+派发 lease → submit。lookup/reconcile 已接受原调用不申请新执行授权，读取/取消按原权限处理。改变源、subject、请求、预算或目标须重新判定，不继承旧 grant；合法 budget-amend 也不改旧 receipt。

底层 `tcad_submit` 只比较 `ExecutionAdmission` 与当前管理员策略；它本身不验证 UI 人类决策。wrapper 必须消费可信宿主 gate，不能从 W 参数构造 authorization。受管控制保证与任意 shell 权限边界分别报告；现有 host-only control socket/私密 transport 配置须在真实 launcher 下证明不泄露，不能把普通原生软隔离声称为恶意代码安全边界。

## 5. 实施边界与最小验收

拟修改范围先经设计审查：TCAD wrapper/factory/插件 entry point、packager 原件 resolver；公共 execution 仅补 pending/cancelled 终态识别和可选 retire；沿用现有 Records/managed_wait/continuation。P3 的来源、资格、授权规则独立小提交，不先恢复旧完整操作编排。

无模型安装 fixture 分两组：

- **P2 控制闭环**：真实 registered CLI + 独立假远端进程；accepted/queued→running→success/failed/cancelled 均原状态保真；一次 run 自动等待→原 W 消费 native proof/output→seal；等待期间无第二 submit/LLM；同 turn/独立 CLI 在 queued/cancelling 时请求新 call 也拒绝；native Worker 已知失败不自动 wake。collect=false不调用collect，不支持原session时明确unsupported。
- **P2 恢复负控**：提交响应丢失/lookup None不重派；原 digest retire 与 submit 并发只有一个结果；重复收集/通知/wake、同 boot 控制器重启、原配置或 proof 篡改、取消处理中、已 sealed unknown 恢复前缀；复用既有 G3/原call测试，仅新增 TCAD 映射断点。
- **P3 gate**：受限材料经 H/W/E、reading view、计算/成果复制仍受限；自审/共同作者/身份未知拒绝；subject或合同/预算/目标改变使旧授权失效；UI重复决定幂等、过期/撤销拒绝；policy累计余额不足与未知用量不放行；普通无资格要求任务仍可完成。

另列未验收：真实 SSH、许可证、solver、跨 boot、真实平台同session唤醒、领域候选/重放/交付映射。设计只读核查发现的完整 transport/manifest 机械容量漏项已单列[容量补修及证据](evidence/FULL_TRANSPORT_RECORD_CAPACITY_FIX_20261016.zh-CN.md)，不作为可延后到P2的领域限制；该修复须独立审查，不包含在本文设计PASS中。管理员显式执行/传输policy与紧凑预览另行保留。

只读设计准备不授予远端执行权限；实施前先独立审查本接口及 P3 gate 的确切绑定。
