# Fig4 作者验证与 token 整改计划：独立工程审查

结论：**REVISE，局部补齐后可进入实现**。无已证实 P0。不要求架构重写；WP2 可按现有设计推进，WP1 的成功诊断交付链和否证验收、WP4 的合同兼容落点需先具体化。本文不代表实现验收或科研通过。

审查对象：`docs/plans/FIG4_AUTHOR_VALIDATION_AND_TOKEN_REMEDIATION_PLAN_20260920.zh-CN.md`，SHA256 `d61575bf921f7c021e609926d2aafbc4ecf9270b7e48f51ee9bfcf65284a4104`。只读检查此候选、三个指定工程证据 JSON、相关源码与测试定义；未扫描全库 diff，未以 HEAD 代替当前基线，未运行测试、模型、科研 MCP、solver 或部署。唯一写入为本报告。使用 scid-cross-boundary-review 与 karpathy-guidelines。

## P1-1：成功项目没有已明确的原始诊断交付路径

位置：计划 §2、WP1；`operation_workspace.py:649–675, 799–807`、`project_packager.py:444–479`、`operation_workspace.py:457–465`。

源码证据：`local_debug_service._finish` 把选中输出写入 `deck/reports/<run>/...`，证明作者本地可读。gap finalizer 才把 `_attempt_files(deck)` 写入正式结果；成功分支只封存 `DeckProjectDraft`，其字段有源码、preflight/initialization attestation，没有诊断文件附件。正常 reviewer 工作区从 `base.files` 恢复源码；gap reviewer 则显式 `_restore_attempt`。`runs.py:740–761` 的 snapshotter 使用位于恢复处理路径，不能据此宣称成功项目 reviewer 已获原始诊断。

影响：作者即使完成短动态试验，reviewer 仍可能只能看到成功证明和作者文字，重演“初始化通过、源码审查通过、生产后才发现行为无效”。计划已意识到此风险，但以“若遗漏才补”留待实施，尚未形成完整工程路径。

最小修订：WP0 明确确认成功链缺口；WP1 指定一个已有工程附件/证据封存入口以及 reviewer 声明输入或受控读取入口，绑定源码、声明、诊断模式与原始输出身份。无需把全部日志塞进项目，也不能借用作者工作区路径作为跨 Run 证据。增加真实 finalizer→封存→新独立 reviewer 工作区的窄集成用例，覆盖成功、gap、源码改变后失效、附件缺失/超限、旧项目仍可读。现有 `test_tcad_initialization_outputs.py:84` 只证明作者工作区输出可读，不能代替此验收。

## P1-2：动态验证改进缺少能击穿旧失败模式的验收

位置：WP1、§5–7。

源码证据：`validate_deck_review_against_project:1578` 检查 manifest、syntax、preflight 等机械关系；不决定动态覆盖，职责是正确的。现有 author 角色第118–125行已经要求生产对应关系、边界和 first solve，reviewer 第70–76行已经要求检查 attestation 和源码对应关系。工程证据仍出现七案 exit 0 后才发现时间边界与 CM/J 问题。

缺口：WP1 优先文案/记录修订，定向测试只列参数、预算、失效和可读性；Worker A/B 固定提供“非初值输出缺口”，能测识别现成缺口，却没有验证作者会选择有区分力的试验。§7 的真实验收被放在部署后，实施验收可能仅证明提示变了。

最小修订：在测试矩阵中加入配对负控：相同 exit 0、preflight/initialization qualified、文件齐全，一份仅初值/不随时更新，一份有适用的演化观察。通过真实交付和 reviewer 输入路径检查前者不能被当成“动态验证完成”。科学覆盖由 Worker/reviewer 判定，禁止给控制层增加非零 J 或 Time 字符串门。确定性测试只证明材料及身份传递；若 native 行为测量受内存阻断，明确“工程链已验证、早发现行为改善未证实”，不能让两者共用一个通过结论。短诊断真实求解能力仍须后续授权验证。

## P2-1：768MiB 硬保证与现有 guard 能力不符

位置：§5、§6；`scripts/compiled_worker_process_guard.py:91–139`。

源码证据：guard 每0.1秒抽样子树 RSS，观察到超过上限后 SIGKILL；自身文档明确是 trusted-local emergency brake，不是 OS isolation boundary。不能保证采样间或守护进程本身计入后的总内存始终≤768MiB。

最小修订：给出实际调用 wrapper 和纳入预算的进程范围；若要求严格上限，在现有环境确有可用内存隔离能力时使用其上限，否则把可执行承诺写成“采样超限即停止”，记录其限制，不声称硬保证。先做串行确定性响应/封存测试；各两对 native A/B 仅在同一约束下能运行时实施，超限停止且不自动重试。计划已有缺测降级规则，应保留；无需新预算调度器。

## P2-2：WP4 必须锁定真实 schema 与历史消费者

位置：WP4；`interfaces/mcp_root.py:173–184, 552–573`；`tests/operations/test_mcp_response_views.py:19–32`。

源码证据：Root router 已将默认 run_status 转成 `/summary`，detail 的现有 schema 承诺完整原件；测试显式要求 execution detail 与原响应相等。`root_response` 的 summary/detail 及 operation_catalog 默认导航已存在。因此“新增默认精简”有相当部分是复用已有能力，不能算本轮新增收益；改变 detail 的日志行为确会改变已测合同。

最小修订：实施清单直接列入 `mcp_root.py` 的输入模型、RootTool description、router 参数处理及对应现有兼容测试。为新的日志索引视图与旧完整 detail 选定一个明确策略，提供可实际调用的完整入口；不同时添加多个近义响应级别。决策字段组合也须说明是 scheduler 显式 output_paths，还是 schema-aware 默认选择，不能给所有科学对象硬套同一字段路径。用安装入口验证全文、精确错误、审批 URL 和分页可达。计划泛称“实施时定位 schema”尚不足以形成可审查接口变更。

## P2-3：引用可用性复用需限定，避免引入第二套状态

位置：WP3；`service/reference_access.py:210–266, 433–464`；`run_assignment.py:23–107`。

源码证据：assignment 目前是冻结输入导航，无可用性查询服务参数；reference_read 先预约预算，再做别名、根、policy/digest 和配对检查。成功读取已有精确 request key 与记录复用；`_reference_pair` 的 manifest 校验会读取字节并收费，不能无成本搬到全部 assignment 根上。

最小修订：优先在已查出的精确错误响应中提供原件路径/alias 与后续动作，并用当前 Run 已有诊断记录复用；未查状态保留 unknown。若确需缓存，明确键至少含实例、Run、精确 root/source、operation/policy digest，权限每次检查，限定只复用确定的配对缺失，不缓存超时/预算/服务错误；写明重启失效、计费语义与观测入口。不给 assignment 增加全根 manifest 扫描，不新建持久缓存表。收益先用无效调用次数证明，再决定是否值得实现。

## 已支持的设计与边界

- WP2 切中真实缺陷：`execution_outputs:486` 丢弃 `_publish_execution_result` 返回值，分页投影又仅保留 execution_name；同时修改两处才能使准确结果名到达 Root。绑定仍由新分析请求完成，冻结后不补绑；无结果保持 null。
- SProcess initialization 直接执行 entrypoint，SDevice 使用 `-i`，见 `debug_adapter:62–80`。计划正确避免把两者等同为动态验证；开发权限是否覆盖短演化、共享生产过程是否可在预算内获得区分观察，仍待明确授权合同与真实后端证据，当前审查不代为批准。
- 六线程344请求、96.8%缓存与 Root净增80893 的口径准确。1258字符 invoke 不是已证实最大来源；优先全文审查、重复日志/合同、大读截断合理。缓存高不证明窗口节约。
- 两版本精确工作树快照、固定任务、各两对、compaction分段、记录峰值和末次增长、缺测不宣称稳定收益，是合理基线。实施前还应固定采样脚本版本、必要决策检查表和唯一计数规则，防止人为挑选较好一对。无需为此扩大科研流水线。
- 不建立科学数值机械门、不迁移旧 Artifact、不继承旧资格、不把 implementation_gap 当物理否定、独立 reviewer 不复用 author 身份，均应保持。

实施前必须补齐：成功诊断的封存及 reviewer 可达链；旧失败模式的负控与验收分层；真实响应合同兼容策略；内存保证措辞/可执行命令。WP3 缓存宜作为有证据再实施的可选小项。上述补齐后应重新审查增量，不能沿用本文为 PASS。
