# 通用平台与领域适配器边界独立审查

日期：2026-10-16。审查者：独立子审查者；不实施生产修复，不提交 Git。

## 1. 基线与范围

- 仓库：`123/scidiscovery-e5.2`，分支 `dev`，基线 HEAD `6677310b93528fd5a35087493ddcf32b7278265a`。
- 起始工作树已有候选/交付实施者对 `controller.py`、`delivery.py`、`history.py`、`local_experiments.py`、`native.py`、`shortlist.py`、generic_inverse fixture/tests 的未提交改动，以及新增 `generic_delivery.py`、`generic_results.py`。本报告不把这些改动算作已提交行为。另有大量既有未跟踪证据目录，未修改。
- 已读 AGENTS、`scid-cross-boundary-review`、`scid-find-simplifications`、`karpathy-guidelines`，以及现行架构、设计宪章和约束注册表。按真实调用链检查 rootless CLI 与 MCP/Operation 两个入口，不把二者能力互相外推。
- 重点追查执行、观测、科学封存、搜索筛选、候选、交付、归档，以及插件缺失与第三方 executor。科学评分、数据格式、TCAD solver 协议保留在领域插件内是合理边界，不因名称或 import 单独报错。
- 已知 `history` 无 observer 时无候选、delivery 强制专用 resolver/audit 的问题由 `generic_candidate_delivery` 实施中，本报告不重复列为新发现。

本次没有发现新的 P0/P1 级证据。保留两项 P2：一项已声明的非本地执行扩展与科学封存不相容，一项 TCAD 诊断状态对通用归档的全局否决。它们具有共同根因：通用控制消费者读取了一个具体后端的私有事实形状，没有共同的控制回执/所有权契约。

## 2. 新发现

### F1 — P2：非本地 executor 的合法成功在科学封存中被降成 unknown

**证据等级：单一无模型受管反例已复现状态不一致；后续搜索影响由静态调用链证明。** 此问题存在于 HEAD；并发候选/交付改动没有修改下述 terminal 判定。

**最紧定位。** `src/scidiscovery/research_loop/history.py:183`–`:191`；同文件 `:235`–`:244`；`src/scidiscovery/research_loop/worker_delivery.py:37`–`:46`。

**支持契约。** `operations/execution.py:54`–`:68` 的 `ManagedExecutionInterface` 明确允许 opaque job package，并说明 `--script` 只是本地实现便利。其协议要求 `result/status_details/collect_original`，没有要求本地进程、POSIX exit code 或 `terminal.json`。`experiments.Records.state():382`–`:389` 也明确以 canonical completed 为状态真源，把进程观测留给 implementation。

仓库已有非本地反例夹具：`tests/research_loop/execution_fixtures.py:32`–`:64` 的 `DifferentExternalIdentity` 以共同 Records 发布 `completed.json(status=known_success)`，返回不同的 remote execution ID，声明 query/lookup/collect/atomic_admission。`test_registered_experiments.py:191`–`:214` 对真实 CLI run/query/collect/lookup 均要求成功，并显式断言不存在 `process.json` 与 `terminal.json`。因此不能把这种形状事后解释为不支持。

**可复现路径。**

```text
custom launcher / registered remote executor
  -> experiments.configure(..., 'remote_execution:fixture', ...)
  -> scid-experiment run --payload <opaque package>
  -> Records.publish(completed.json: known_success)
  -> query=succeeded; collect returns exact descriptor
  -> contracts.seal_result / history.capture
  -> history.managed_calls
  -> no terminal.json => status=unknown
  -> history.validate_managed accepts that downgraded observation
  -> worker_delivery.capture / search._managed_refs ignore it as known evidence
```

`history.managed_calls` 不调用已冻结 adapter 的终结投影，而重新解释文件：必须有本地 `terminal.json`，且 `cleanup_confirmed=true`、`transport_complete=true`、整数 `returncode`，才能把 completed success/failed 保留为 known。`validate_managed` 和 `worker_delivery._candidate` 又复制同一套本地条件。若一个远程后端没有 POSIX exit code，填写虚构 `returncode=0` 才能通过，这会迫使插件伪造本地执行语义。

**本次行为证据。** 经根协调并确认测试槽空闲，以 `scripts/run_tests.py` 的 `serial_lock/run_one` 执行一个 probe，复用仓库现有 `DifferentExternalIdentity` fixture，真实调用 `python -m scidiscovery.research_loop.experiments` 的 run/query/collect/lookup，再对同一原件执行生产 `history.managed_calls`、`validate_managed` 和 `history.capture`。结果如下：

| 同一调用的读取位置 | 实际结果 |
| --- | --- |
| CLI run / completed.json | `known_success` |
| CLI query / lookup | `succeeded` |
| CLI collect | `collected`，1 个精确 descriptor |
| process.json / terminal.json | 均不存在，与该已支持非本地 fixture 约定相符 |
| history.managed_calls / history.capture | 均为 `unknown`，completed 原件仍 archived |
| Worker 已知终结检查 `_candidate` | `false` |
| 将该 history row 标为 known 的负控 | `validate_managed` 拒绝：`Managed terminal originals absent` |

证据保存在 `/tmp/scid-nonlocal-boundary-evidence-20261016/case/probe-result.json`、同目录上层 `pytest.log` 和 `resource.json`；复现脚本 `/tmp/scid-nonlocal-boundary-probe-20261016.py`，监督脚本 `/tmp/scid-nonlocal-boundary-supervise-20261016.py`。退出 0，耗时 1.797 秒，采样 tree RSS 高水位 99,991,552 bytes，`cleanup_complete=true`，未触发资源止损。probe 保存了四个受审文件的 SHA-256 与 HEAD。

probe 通过 `controller.prepare/build_job/configure` 构建独立临时实例，并写入合成的 host acceptance anchor；没有调用 `execute_native/run_native`，没有调度模型或真实远端任务。它证明 CLI→生产历史 capture 的状态矛盾及 Worker 终结谓词，不冒充完整 H→W→A、installed wheel 或真实远程 executor 验收。

**影响。** CLI 层报告已成功、已收集，科学历史却记录未知。对绑定 H mechanism 的调用，`search.py:76` 排除 unknown；`:247` 设置 `opportunity_unknown`；该状态经下一轮 breadth 配置传到 `breadth.py:69`，拒绝新接受。screen 的 W 原件也无法通过 `worker_delivery._candidate` 形成 known observation。此处不会错误授予成功资格，但会阻止本来已明确终结的合法插件继续科研。

此外，`history.py:195`–`:199` 仅在 completed 包含本地 `result` 字段时保留 proofs/outputs/execution；当前 ManagedExecutionInterface 未声明这种输出形状。该 probe 的 collect 返回 1 个原件，但 history row 没有 outputs/originals 字段。不要用 CLI collect 可读来推断其文件已经进入下游科学封存。该点是同一回执契约缺口，未独立计数。

**根因。** 注册与 admission 已经是后端无关的，终结证据的消费者仍以 LocalExecution 的私有文件布局为隐含 ABI。local 与 cov 共用本地 runner，所以二者测试同时通过，掩盖非本地消费者缺口。

**最小修复。** 在已有共同 Records 边界声明一种控制持有、与 accepted/interface/scope/external ID 精确绑定的终结事实。由冻结 adapter 的明确协议投影并验证原始后端终结证据，核心消费这份统一事实；本地 cleanup、日志传输完成及 exit code 可作为该后端证明内容。`history`、`worker_delivery`、search 复用一个验证权威。缺少或冲突的原件仍必须 unknown；不能仅信任任意 `completed.status`，也不能为兼容远程后端删除本地清理保证。

**验收与盲点。** 把现有 DifferentExternalIdentity 夹具延伸至真实 W→history seal→A screen/后继 W admission；断言 completed/status/history 对同一调用一致，原件和 collect descriptor 可追溯，未知和篡改负控仍拒绝。保留没有 process/terminal 的断言。当前非本地测试只到 CLI，一层本地/cov 参数化不足以验证完整插件边界。至少另有一次 wheel entry point 安装验证，不能只依赖 source `PYTHONPATH` 和临时 dist-info。

### F2 — P2：一次 TCAD 本地诊断会让无关通用实例的归档持续不可用

**证据等级：代码与已有测试直接证明当前行为；本次未重跑实际 solver。** 此问题存在于 HEAD，与候选/交付改动无关。

**最紧定位。** `src/scidiscovery/artifact_agent/service/instance_archive_files.py:280`–`:282`。

该代码检查整个 `state_root/local-tcad-debug`：只要目录内存在任意一项，就给当前目标实例添加 `local_debug_ownership_and_writer_unknown`。没有检查目标 instance、run、execution 或当前 writer。`InstanceArchive.preview():166`–`:168` 将任意 unsupported 转成 `ready=false`。

这不是只在人为损坏目录时触发。生产 TCAD runtime 在 `plugins/tcad_artifact/tcad_artifact/runtime_plugin.py:94`–`:97` 为 debug service 选择该全局目录；`local_debug_service.py:209`–`:212` 首次诊断创建持久 `budgets` 子目录，`:715`–`:725` 保留 receipt。即使诊断已经完成，根目录仍非空。插件现有 `experiment_activity` 可以按 run lineage/预算 subject 查询诊断，但归档没有消费这类所有权事实。

**可复现路径。**

```text
instance B: worker_experiment_debug / LocalTCADDebugService.run
  -> state_root/local-tcad-debug/budgets (+ receipts)
  -> B diagnostic completes; persistent directory remains
instance A: no TCAD execution, already quiescent
  -> approval UI archive preview / InstanceArchive.preview(A)
  -> Files.collect(A) inspects global debug root
  -> unsupported local_debug_ownership_and_writer_unknown
  -> ready=false
```

现有 `tests/operations/test_instance_archive.py:19`–`:29` 的 archive fixture 只创建两个通用实例；`:304`–`:312` 在全局 debug 树加入一个文件，明确断言第一个实例归档被阻断。该测试验证了保守拒绝，未检验另实例已完成诊断是否应影响当前实例。

**影响。** 共用部署中，一次领域诊断可让所有无关实例的通用归档功能持续不可用。禁用/卸载 TCAD 也不自动清除原目录；手工删掉控制预算/receipt 不能作为正常修复，因为会破坏恢复与预算事实。

**根因。** 插件状态没有接入通用归档的所有权与写者静止协议，核心以 TCAD 专用目录的全局否决补偿。对另一新领域插件，既没有同等的状态贡献接口，也不能由此保证其状态被正确归档；本报告不把未观测的其他插件数据损失当作已发生事实。

**最小修复。** 将诊断的 instance/run/恢复家族所有权与 writer lease 接入现有通用 inventory/maintenance 边界；先支持准确识别“与目标无关且保留原位”的目录，再支持目标独占状态的迁移。未知所属、活动/无法确认静止的 writer 继续阻断相关范围。不要直接删掉此 guard；也不要让核心为每个领域增加新的目录名分支。

**验收与盲点。** 至少三组目标区分：B 的已完成 TCAD debug 不阻断无关 A；A 自己的活动/未知 debug 仍阻断；A 归档/恢复后预算与原 receipt 不重置、不丢失。用无 solver 的已封存 debug 状态即可验证，不需要启动 TCAD 场。现有测试只有全局拒绝，没有跨实例隔离正控。

## 3. 已检查而不列为新缺陷的边界

| 边界 | 当前证据和判断 |
| --- | --- |
| 无领域插件的完整 MCP 实验 | `operations/catalog.py:1001`–`:1004` 支持 provider=`none`；`general_science_experiment_task.py:137`–`:146` 封存 native_execution 并明确 `execution_attestation=unavailable`。这是声明的原生执行限制，不等于无实验功能。 |
| local/cov 执行 | 共用 Records/本地 runner、冻结 payload/snapshot/argv，lookup/query/collect 均有声明。cov 的独立 runner receipt、模型 predict、泄漏审计属于合理领域职责；F1 是核心消费者硬编码本地终结，与 cov 解析职责不同。 |
| 可选 smoke/audit | `shortlist.py:198` 起缺 smoke 返回 not_provided，文案明确不是 passed；audit 默认未配置返回 unavailable。正在实施的 generic delivery capabilities/audit_required 改动仍属未提交，不能据此宣称已通过验收。 |
| cancel/resume | `local_experiments.py` 明确不声明 cancel/resume；CLI 先查 LifecycleCapabilities。没有把命令枚举本身当支持承诺。长期 unknown/跨 boot 正常恢复入口不足已记录于既有 PROJECT_DEFECT_AUDIT G3，不重复计算。 |
| 输入与来源 | 精确实验目录快照、符号链接拒绝、原件 hash 校验是真实机制。public_root/外部库/解释器环境未完整冻结已记录于既有审查 G4；没有把软隔离宣称成完整可复现或安全沙箱。 |
| 运行中事件/日志/预算 | rootless feedback 明确没有 mid-turn notification，MCP 另有 activity/SSE/collection 状态。两入口不共享全部 UI/实例的 G2 是已知迁移缺口；未误报为领域插件硬编码。native 日志/普通 artifacts 总量边界不足已记录于 G5。 |
| CLI/UI/发现与安装 | pyproject 发布了 local/cov execution_interfaces，scientific plugins 另有单独注册；部署默认不装领域插件。UI 中少量 TCAD 标题有通用 fallback，不构成只有 TCAD 才能导航。TCAD 仍只有旧完整实验 capability，不能拿旧验收替 rootless 资格。 |
| 领域评分与格式 | curve/TCAD 的算法、schema、solver capability 和科学判断合理留插件。`calculation_proof.py` 的算法前缀兼容投影是耦合点，但本次没有证明新的可达错误，未列发现。 |

## 4. 检查限制与后续顺序

本次审查是高风险边界追链，不是全库逐行证明。仅运行上述一个无模型受管 probe；没有运行模型、solver、全量测试、真实浏览器、daemon 重启或 installed wheel 任务。现有测试的断言作为可复现路径证据；没有把未重跑测试写成通过。

建议先修 F1 的共同终结事实消费者，避免接入另一个真实 executor 时再次复制本地 terminal ABI；F2 先补跨实例 ownership/quiescence 契约。两者都不需要把领域科学规则搬进核心，也不需要新建第二套状态账本。
