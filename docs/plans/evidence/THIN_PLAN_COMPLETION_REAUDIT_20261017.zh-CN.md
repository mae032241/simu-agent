# 薄层迁移原计划完成度复审

基线：`dev@73f57c6`，2026-10-17。本次只读源码/文档与既有验收记录，唯一新增文件为本报告；未运行测试、收集、项目 import、CLI、HTTP、安装、模型或远端作业，未改生产/历史证据、未提交。使用 `scid-decision-corpus-maintenance`，按规则归属区分实现、有限验收与仍未支持的能力。

## 1. 结论

**原 P1–P5 不能整体标为完成。** P1–P3 的主要工程接线、R0 及 A2–A4 已实现并有定向验收，但不等于真实 Codex/TCAD/跨 boot/浏览器资格齐全；P4 完成状态控制 UI 和只读归档，未完成可写归档恢复；P5 只完成部分收缩，旧 CLI/MCP/SQL 仍有明确生产消费者。

最小可立即推进项是**处置已失效的 L4 author/review 探针执行胶水及发布清单**，保留独特 debug 证据负控。不是删除通用 curve/API 或整个旧 runtime。P4 科学浏览由 root 另行安排独立实现，不在本审查写入范围；本文对该功能的“未实现”仅指上述基线，不评价在途变更。

另有容易被“只剩真实运行未验”掩盖的 P3 实现缺口：非空 managed observation/history observer 的额外输入来源仍明确 unsupported/unknown，见 §4。不能仅凭 d2a 编译输入链通过就声称所有后继执行来源已闭合。

## 2. 文档归属与证据用法

| 文档 | 本次分类、仍负责的事实 | 处置建议（本次不改） |
| --- | --- | --- |
| [主迁移计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md) | 当前计划 owner：P1–P5 目标、退出条件、最新总状态 | 保留；后续补本报告列出的实现缺口，不把节点提交等同全部退出 |
| [P4/P5 notes](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md) | 已审设计；状态/控制、只读包、退役范围 | 设计继续有效；当时 static-only 不是后来有限验收的否定或新的测试授权 |
| [P5 消费者账](P5_ENTRY_RETIREMENT_LEDGER_20261017.zh-CN.md) | 仍需维护的入口/消费者处置账 | “旧池待提交”与后来的 `6dcf7ac` 不同步；应在当前账补状态和 §6 精确消费者 |
| 各 P 子节点 implementation/review | 绑定当时 revision 的历史实施/独审事实 | 不改“当时未运行/待提交”来伪造当时已通过；当前验收链接到后来的结果 owner |
| [P 分环节结果](P_MIGRATION_TARGETED_TEST_REPORT_20261017.zh-CN.md)及其 JSON | 164 个所选用例最终通过、首次失败/修补/单次 core 安装的范围 | 复用已审结果，不重跑也不声称最终 HEAD 全量通过 |
| [P4c2 边界](P4C2_WRITABLE_RESTORE_BOUNDARY_DESIGN_20261017.zh-CN.md)及[独审](P4C2_WRITABLE_RESTORE_BOUNDARY_REVIEW_20261017.zh-CN.md) | 当前可写恢复 BLOCKED 的理由；边界文档已获认可 | “可写恢复方案未批准”不等于“阻断说明没有独审”；应保持这一区别 |
| [A 修复计划](../THIN_AUTHORITY_REVIEW_REMEDIATION_20261017.zh-CN.md)、[A5 有限验收](A5_AUTHORITY_REMEDIATION_ACCEPTANCE_20261017.zh-CN.md) | 接管授权软边界、不可用审查续行、默认去锚定、调用内检查预留 | 已实现范围由 A5 及其[独审核对](A5_AUTHORITY_REMEDIATION_REVIEW_20261017.zh-CN.md)负责；A1 仍用户后置 |

本报告读既有结果 owner，不重验每份原始运行日志。164 与 A5 的 21 个不同用例不是可相加的全库通过总数；A5 自身也只是增量验收，全部 21 项未在最终 HEAD 再跑一遍。源码、合成进程、安装与真实平台资格分别记账。

## 3. P1–P5 逐项核对

“已实现已验”在下表中均指所列**有限层级**；不意味着同一行所有部署/真实科学情形都已验收。

| 节点/能力 | 真实入口与 owner | 状态与验收范围 | 尚欠退出条件 |
| --- | --- | --- | --- |
| R0 + A4 提前工程检查 | `experiments` 接受原 call → `replay_check.acceptance/complete`；Cov 可选 `isolated_replay`，Local 原窗口 deadline hook | **已实现已验：**R0 依赖补齐后 5 项通过；A4 8 项覆盖原窗口预留/不足/未知不重放/公开反馈 | 只支持声明方；sample replay 不证明完整科学训练复跑或审计。IO/清理可耗尽预留，无保证必查、无调用后续时 |
| P1 注册与配置 | CLI `prepare --execution-config` → `controller.prepare/experiments.operator_configuration`；`native.run_native` 调同一 `experiments.configure`；原 factory/能力注册 | **已实现已验：**27 项定向；两个不同实现、默认 local、配置冻结/拒 host 注入、实现替换与 native 自动接线 | 本轮 core 安装只验打包入口；没有在安装环境重跑全功能，也没有 TCAD cohort 解析资格 |
| P2a 共通异步/观察 | `operations.execution` 生命周期、`experiments.dispatch/reconcile`、`managed_wait`、`history` | **已实现已验：**P2 所选 84 项包括等待/唤醒、组合结果、非本地观察及原配置 | 合成 backend/进程不证明真实远端持久性、SSH、许可证或 solver |
| P2b/c TCAD 输入与 managed 注册 | `managed_execution.build_managed_runtime`，底层 command/socket adapter、P2b materializer；`scid-experiment run --payload` | **已实现已验：**callbacks/gate/retire 14 项等有限检查；缺可信 gate/输入 resolver 不能执行 | opaque 结果、候选/通用交付等只有声明能力可用；不能把 local entry/snapshot 协议套给 TCAD |
| P2d 永久未提交证明 | `experiments.verify_retirement`；同原 call 的独立 fence receipt；history/recovery/ledger 共同消费 | **已实现已验：**所选 retirement/原件负控 | lookup None/取消请求不是退款证据；真实 backend 的原子持久 fence 未验证 |
| P3a 声明来源与继承 | `prepare --source-restrictions` → `qualification.source_configuration/freeze_sources`；`contracts` 绑定/封存，纯规则三态 | **已实现已验：**9 项覆盖声明、错 origin、受限继承、材料摘要、普通科研不被阻断 | 非空 managed observation/外部 observer 来源适配**未实现**；任意 native 外读不在保证范围，见 §4 |
| P3b + A2/A3 正式独审 | 普通 A 显式 `formal_review` → 原 `_route/native/seal_review/return_route`；精确 subject 和实际参与者原件；A2 原有限补正，A3 专用默认输入 | **已实现已验：**原 5 项及后续 A2/A3 定向，A5 明确交叠；普通 A/pass 不授资格，缺身份仍可合法科研改道 | 合成 session 不是实际 Codex/所有 context/helpers 身份验收；默认去锚定不是盲评；专属 reviewer profile/受控披露观测后置 |
| P3c 人工/策略决定 | `serve-ui` 同一 `InstanceUI` → authority request/decision/revoke；exact subject/review/policy/target；共享 `execution_security` | **已实现已验：**5 项限定 HMAC/Origin/boot/绑定等路径；真实 request 原件消费 | 真实 HTTP/浏览器未验；同 UID 可信进程软边界，A1 不支持恶意 Worker 隔离 |
| P3d1 唯一执行资源 owner | `execution_authority.host_services/_gate` 唯一可信 factory 注入；`budget` 原 ledger grant/reserve/bind/settle/release；CLI `budget-amend` | **已实现已验：**3 项交错 clock/资源事件、旧 factory 拒绝、旧 W config 禁新派发，及后继集成用例 | 不把缺失投影当实际消耗 0；真实并发/跨 boot/掉电窗口未全面验证。首次原件校验仍有 IO 成本 |
| P3d2a 精确非空输入 | `scid-experiment compile` → `execution_inputs.NativeInputHost` → W seal → exact formal review → 后继 `run` 同一 package → 原 P2b 回调 | **已实现已验：**非空编译/迟批文件共 8 项；A3 后又定向补测 compile→review→同包执行 | 编译 slot 来源已接，不等于运行后所有 observation 来源已接；不重编译已审包，不造 ArtifactRef/storage 身份 |
| P3d2b 原 call 迟批 | CLI `execution-resume` → controller 原 writer → `execution_resume.resume`、positive pending-set、authority/原 ledger | **已实现已验：**8 项中的迟批/过期 successor/intent 中断/预留 gap 等；fresh calls 目录真实生命周期缺陷已修补并复测 | 旧 seal 缺正面 pending/cleanup 原件仍 unsupported；未知不重放；不保证实际 session/跨 boot/远端掉电恢复 |
| P4a/b UI 状态控制 | `serve-ui` → 同一 host；`instance_control.status/request_pause/continue_instance` 与 CLI 共用；普通无 authority 实例也可用 | **已实现已验：**2 项直接 GET/POST 方法与 writer/后台 Event 控制负控 | **实现未验：**真实 HTTP/浏览器、服务退出时 live 科学 owner、跨进程重复点击/重启流程；节点页原基线只有状态元数据 |
| P4 科学原文浏览 | 原基线 `/nodes/<step>` 复用 `_instance_page/_node_view`，只显示 step/role/state/stop 等字段 | **原基线未实现；root 已另行安排独立实施** | 不将状态页/文件系统上存在原件算作产品科学浏览，不抢在途验收结论 |
| P4c1 包导出/只读 inspect | CLI `archive-export/archive-inspect` → `instance_archive`；原 owner 锁、静止原件证明、`archive_io` 分块复制/哈希 | **已实现已验：**4 项包范围、锁、竞态、语义/hash/symlink 拒绝；`restorable=False` | **实现未验：**真实大包/磁盘满/跨进程发布竞争、活 native/远端归档；包外插件存储/平台环境并非全量覆盖 |
| P4c2 可写归档恢复 | 没有 restore/material-repair CLI 或新 owner | **未实现；有依据保留 BLOCKED。**边界文档已审，不是恢复实现 PASS | 唯一 owner 转移/旧 owner fencing、账本最新高水位、外部依赖、所有写者共同准入尚无协议；不应为进度另造平行 owner 库 |
| P5 已完成收缩 | 中立 browser/archive/security/provenance/review 原语；TCAD 导入收缩；安装与功能分组；旧 live 池删除 `6dcf7ac` | **已实现已验（有限）：**原 live mock 1 项及 core 安装冒烟 1 项；无第二环境/全功能 installed 重跑 | 旧生产入口整体退役**未实现**；TCAD 安装解析/live all_domains 等仍不能由 core 冒烟代替 |
| A0/A1、A5 | 可信 Worker 边界说明；A5 原日志/机器摘要核对 | **文档已审；A2–A4 21 个不同用例增量通过。A1 强隔离用户明确后置** | 不新增付费模型/真实 solver 授权；采样 RSS 不是硬 cgroup 或绝对防 OOM 保证 |

## 4. P3 仍有代码可见的来源缺口

`qualification.py:_output` 当前对原 seal 绑定的小 observation 原件核路径/SHA，然后只读 `managed_calls` 是否非空；存在实际 call 或 `history_observer` 时，写 `additional_input_restriction='unknown'`、`missing_reason='observation_input_provenance_unsupported'`。零 call 不额外变 unknown。这是保守且明确的 **unsupported 实现边界**，不是待跑一个测试就能补齐的资格。

`execution_inputs.py` 解决的是真实 compiler 输入/producer/member 及同包执行，不解释 managed backend 读过哪些其他输入。`execution_authority._selected_subject` 同时要求 exact subject 的 `q.output_status` 和当前任务 `q.status` 为 clear，因此含这类未知来源的后继成果不会自动获得新执行准入。普通科研仍可封存；known restricted 仍优先，不能把此 unknown 删成 clear 来“跑通”多轮 TCAD。

若需要声明完整多轮执行链，应另做窄设计：由既有 observation owner/注册 adapter 给出完整直接输入来源映射，消费其已验证原件；无完整映射保持 unknown。不另解析一套 accepted、不复制祖先列表、不按相同 hash 或 work 路径猜同源。该项先设计与独审，不在本报告实施。

## 5. P4 三种“恢复”必须分开

| 用户情形 | 当前确有入口 | 不能据此声称的能力 |
| --- | --- | --- |
| 原 live 根和最新 ledger/身份/实现仍在 | `run/continue`；已知失败 native 用原 `worker-resume`；未知/晚到原 call 用 `execution-recover`；sealed pending call 用显式有限 `execution-resume` | 不是从包重建 owner；缺 session、原实现或 positive pending-set、跨 boot 期限不明时仍可能拒绝 |
| 只剩只读包 | `archive-inspect --package` 验全部包内 blobs/清单并分页；依赖页只报告冻结引用/缺口 | 不加载插件运行、不创建 live settings/jobs，不续预算、签名或原调用 |
| 需要从备份在新/同路径推进 | 无产品可写 restore | 目标为空、同 path/goal_id/hash、root 内 flock 或旧 PID 不可见不证明旧 owner 已永久不能新增副作用 |

包外 `public_root`、launcher/runtime、注册代码/adapter、插件存储、native sessions、批准 key 等由 `instance_archive._dependencies` **登记范围**，不是 export 已复制/inspect 已验证其当前存在与可用。key locator/native-homes 不复制；未知拥有根只记 gap。旧 archive 的 SQL/CAS reader 又是另一种格式，不能把新包视作旧库或反向导入旧记录。

如果未来确需可写恢复，必须证明不回滚旧消费/撤销/reservation/外部提交，不复制第二份执行权；fencing 只禁止旧 owner 再制造重复新副作用，不要求销毁既有远端成果或取消原 query/cancel/collect 维护权限。当前没有必要为处理原目录恢复再建新调度/owner 系统。

## 6. P5：仍活跃的旧链，不可整删

以下是可执行源码/配置消费者，不靠旧测试数量推断活性；不证明当前外部部署已运行这些文件。

| 被保留链 | 可见消费者/公开注册 | 为什么薄层不能直接代替 |
| --- | --- | --- |
| `artifact_agent.interfaces.cli` | `pyproject.toml:27` 的 `scid`；init/progression/instance/ingest/approval/active-bundle/旧 UI 子命令 | 新 CLI 不消费旧 SQL/Artifact/命名空间，不是同协议替换 |
| `RootToolFacade/RootMCPRouter` | 旧 CLI；`interfaces/mcp.py:build_root_router`；`interfaces.__init__`；L2/L3/M7/live/cov pilot 脚本 | 当前包仍公开这些入口；不能为了删 L4 一并删除其他有效 consumers |
| MCP daemon/proxy/gateway 与平台安装 | `platforms/codex.py` 生成 `mcp_proxy` 配置并使用 gateway；`deploy/systemd/scidiscovery-control.service.in` 启 daemon；`deploy/install.sh` probe proxy/root contract | 这不是仅测试遗留。必须先明确旧部署/平台初始化的保留或替代，不能只改新 README 就称消费者退出 |
| 旧 `ApprovalUI/TrajectoryStore/InstanceReadModel` | 旧 CLI `serve-approval-ui`；approval-ui systemd 模板；`probe_root_host_live.py`、M7/cov pilot | 新实例页与旧实例/归档身份不互换；完整旧档案 reader 仍需其 SQL/CAS |
| 旧 runtime/SQL/CAS | `artifact_agent/runtime.py:open_runtime` 装配 artifact/run/approval/execution/scheduler 五类数据库；旧 UI/archive reader 读这些表和 CAS | 删除 writer owner 前必须保留可用的旧只读/导出路径，不能用新包 reader 顶替 |
| 旧 TCAD transport/debug 与共享 schema | managed wrapper、authority 使用中立 ExecutionAdmission 的旧 schema 路径；runtime local_worker 仍构造 debug service；packager 保留 v2 | 有旧路径不代表旧 Root 依赖可以整搬或整删。纯类型/adapter/调试证据仍是当前共享能力 |
| 原 fixture 包源码 | `tests/operations/conftest.py:source_catalog` 使用 broken/invalid_unicode/m7/blind 等；architecture 被源码测试/发布清单显式引用 | wheel 环境池已删不等于这些独特负控也无消费者；本轮不删除其源码 |

现有中立 re-export 也不自动是死层：旧 `approval_ui.access` 的存在服务旧路径；`service/instance_archive_files.py` 除共享文件原语外仍有 SQL/CAS 清理归属逻辑。新链不应 import 这些 package 的聚合入口，但“不应新依赖”不是“旧消费者已不存在”。

## 7. 可立即执行的窄 P5 节点：失效 L4 探针

### 7.1 注册、调用、故障的精确证据

| 项目 | 当前事实 |
| --- | --- |
| 探针固定 Operation | `scripts/l4_live_tcad_agent_probe.py:55–56` 固定 `tcad.deck.author.initial.v1`、`tcad.deck.review.v1`；`l4_live_tcad_revision_probe.py:33` 固定 `tcad.deck.author.revise.v1` |
| 实际注册来源 | agent `_catalog()` 只编 CORE/SCIENCE/CURVE/TCAD 四个当前声明；当前 `src/plugins` 中无上述三项注册；TCAD `plugin.py` 组合 parameter/result/transform 与现有 experiment 组件，不再声明这些 deck author/review Operation |
| 用户可达路径 | agent `main` 公开 prepare/queue-review/status；prepare 会先建 project、旧 runtime/实例及原件，然后对固定 author 发 preflight/invoke。即使前置旧 schema 仍可构造，该固定请求也没有现行 Operation；不能得到它宣称的 author/debug/review 闭环。revision CLI 同样依赖旧 author/reviewer Run/Operation |
| 错误性质 | 静态可达的失效入口；不是误删仍在注册的 adapter。没有运行脚本复现，不承诺第一条运行报错一定发生在 preflight，也不声称新 TCAD 调试失效 |
| revision 对 base 的依赖 | `from scripts import l4_live_tcad_agent_probe as base`；复用 `_control/_runtime/_root/_verify_operation_launch/_write_control/_write_dispatch` 和旧 author/review 常量，属于该失效探针的专属胶水 |
| 唯一独特测试消费者 | `tests/operations/test_l4_live_tcad_revision_evidence.py` 只导入 `_is_qualified_debug_report`，3 条检查 exact initialization、不能拿 preflight 冒充 initialization、错 source SHA 拒绝；没有运行旧 author/review CLI |
| 专属 transport | `scripts/l4_tcad_transport_fixture.py` 声明只供 persistent L4；当前执行调用来自 agent 的 command config，另外只是发布清单/检查收录。它是固定成功的假 transport，不能作为真实 solver 资格 |
| 发行与源码包消费者 | `scripts/build_git_release.py:102–104` 收录两 probe + transport；`tests/installation/check_source_release.py:152–153` 独立要求三文件存在。只删脚本不改这两处会使发布检查失败 |
| 其他残留 | `scripts/run_root_invoke_ab.py` 的 `tcad_revision` case 也引用已失效 Operation；不据此整删 A/B 的其他分支，另列相同消费者处置 |
| 文档 | plans README 已列“失效 L4 探针待清除”；未发现当前 README/ROOTLESS_CLI 的有效运行教程依赖这三脚本。历史 evidence 仍引用旧名称/原结果，必须保留原貌 |

### 7.2 最小实施范围与停止点

推荐先冻结独特证据归属，再删除专属执行胶水：

1. 保留上述三个 debug 证据断言。优先对接现有 `ProjectPreflightAttestation/ProjectInitializationAttestation` 与 source-bound debug 生产验证；若缺少等价的精确 source/mode 判定，仅抽取现有小纯 predicate 到 TCAD 现有证据 owner，不为保留千行脚本再造通用框架。不能用测试内固定成功 JSON/本地同实现相等替代这些拒绝条件。
2. 在仓内 consumer 闭包确认后，删除两 probe 的 author/reviewer queue、Root/runtime/profile/dispatch/封存胶水；sole-consumer transport 可同节点删除。同步 release allowlist 与 source-release required 清单；历史报告不改。
3. 只运行获准的相关 debug/source-release 最小检查，不启动模型、L4 假 solver、SSH 或安装矩阵。此报告本轮只给范围，未实施/未运行。
4. 保留通用 `run_compiled_codex_worker.py`、P2/P3 当前 managed wrapper、真实 command/socket adapter、`debug_adapter/local_debug_service`、存储/来源/授权规则，以及其他有效 Root/MCP/旧档案消费者。完整旧入口退役不能由此小节点冒称完成。

此前发现 `_single_crossing` 无仓内调用、`OutputBundle` 仅自身声明，但依 root 本轮范围**不建议为删除量动通用 curve/API**；不是本次 P5 首选，也不授删除批准。broken/invalid 等源 fixture 仍使用，更不能按旧 wheel source 名单清空。

## 8. 建议后续顺序与验收边界

1. **立即：P5-L4 窄退役。**范围和保留断言见 §7，先独审，再独占串行最小检查，修发布清单；不依赖新的真实 TCAD 资格，因为删除的是已失效 Operation 探针，不是当前生产 adapter。
2. **由其 owner 收口 P4 科学浏览及既有 UI 的有限真实 HTTP/浏览器验收。**没有浏览器时只能明确 HTTP/控制接口层级；不靠扩大模拟断言把 P4 全部置绿，不另建 server/secret/调度队列。
3. **有多轮执行需求时：P3 managed observation 来源适配窄设计。**先证明额外输入映射完备，保留未知，不扩大作者/来源准入；不以真实 solver 试跑替代缺失的来源契约。
4. **保留阻断：P4c2 与 A1。**当前原目录维护与包内只读核验已有明确收益；不为“完成 P4”自动新增分布式 owner、可写克隆或同 UID 假隔离。用户明确后置强隔离。
5. **单列真实资格：**真实 native 身份/同 session 续接、TCAD 持久 fence/异步恢复/资源投影、TCAD 安装依赖解析，须有确切部署/资源授权后再安排。现有通过组不重复安装/整套重跑，也不在此审查启动付费工作。

本次完成的是**计划完成度与下一节点边界复核**，不是全仓语义/安全审计、全部历史用例重新执行或新生产资格授予。当前 owner 文档的状态文字可按上述归属同步，历史审计中的当时失败、未运行、限制和科学结论不改。
