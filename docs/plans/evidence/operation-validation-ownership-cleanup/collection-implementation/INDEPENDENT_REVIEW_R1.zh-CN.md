# 执行收集与全局 Agent 框架独立工程审查 R1

日期：2026-09-13。结论：**REVISE，初审版本不具备部署通过条件。**

本报告由未参与本轮实现的独立工程审查者完成。已确认一项本轮引入的 P1 进程所有权缺陷，以及预算、诊断、观测策略和安装验证缺口；另确认一个既有 Hardened 工作区合同组合问题。不得将定向测试通过或隔离 wheel 导入通过写成整轮工程闭合。主代理在收到发现后已开始修复，**本报告保留初审结论，不为审查期间的新修改背书**；修订版须提供新的精确清单及匹配复审。

## 1. 精确输入与审查边界

- 仓库：`123/scidiscovery-e5.2`。Git HEAD 为 `be5da77acdbf98054e0b096fc4e940de560d4ba1`，不是本轮改前基线。
- 改前内容来自 [baseline.json](baseline.json) 指定的 `/tmp/scid-collection-baseline-1789276126341295526`。初审逐项核对 [incremental-manifest.json](incremental-manifest.json) 的 **44 个文件**：所有可用的 before/after SHA-256 均匹配；其中 `docs/tcad_transport_contract.md` 为 `current_only_no_baseline`，不能声称已核验其改前差异。
- 冻结计划为 [EXECUTION_COLLECTION_DIAGNOSTICS_REPAIR_PLAN.zh-CN.md](../../../EXECUTION_COLLECTION_DIAGNOSTICS_REPAIR_PLAN.zh-CN.md)，核对 SHA-256 为 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`。计划正文中的旧状态是历史字节；R2 计划审查是主代理复核，不是本次独立审查。
- 本文源码行号针对上述初审增量；新文件原文可由 [incremental.diff](incremental.diff) 还原。主代理修复后行号可能移动，应按函数与初审摘要定位。
- 使用 `scid-cross-boundary-review` 技能，检查实际实现和两侧调用者；没有操作科研实例、Worker MCP、审批、VM、部署或求解器，没有读取原 Fig.4 科学存储，也没有运行全量、并发或 xdist 测试。
- 独立动态验证仅有下述串行小探针，通过本目录 `check.py` 的 512 MiB 进程树 / 150 秒边界运行。其余测试为读取已有代码与日志，不能冒称独立重跑。

## 2. 必须修复的发现

### R1 — P1：嵌套 command 进程逃出收集所有权，锁释放后仍可写入缓存

**归属：本轮引入，动态确认；阻断部署。**

位置：`src/scidiscovery/artifact_agent/service/execution_collection.py:34`、`:143`、`:300`、`:354`；`plugins/tcad_artifact/tcad_artifact/command_adapter.py:279`；`plugins/tcad_artifact/tcad_artifact/debug_collection.py:26`。

收集协调器以独立进程组启动 collector，停止时只处理该组。collector 内的 command 适配器调用 `run_bounded`，其默认值又执行 `start_new_session=True`，从而另建不属于 collector 的进程组。父服务死亡触发 `watch_parent` 强停 collector，或外层在停止余量内强杀 collector 时，内层 Python 清理逻辑可能来不及执行。collector 已退出并释放执行锁，不等于嵌套 command/SSH 已停止。

独立探针通过真实 `CommandTCADExecutorAdapter.collect_with_budget` 和真实 `run_bounded` 启动临时传输命令；外层仅用最小夹具模拟 collector 的进程组及执行锁。杀死外层进程组后，可重新取得同一锁，同时嵌套命令仍在稍后写入文件。观察值为：

```json
{"groups_differ":true,"collector_reaped":true,"execution_lock_reacquired":true,"nested_transport_late_write":true}
```

证据：[check-1789281711430930810.log](check-1789281711430930810.log)，2.58 秒、峰值 78,409,728 字节。所有探针产生的存活进程均显式清理。先前探针因子进程未设置源码 `PYTHONPATH` 而未启动目标，失败原样留于 [check-1789281677602999342.log](check-1789281677602999342.log)，不计为缺陷复现。

影响：重启后的第二次收集可与旧传输同时修改同一 `.download` / 完整缓存，单槽、同执行互斥和“确认停止后恢复”的保证失效。作者 debug 外层私有进程也使用 `run_bounded`，其内部再启动 command，具有同类强停窗口。该探针证明本地所有权机制缺陷，未证明远端求解被重启，也未运行真实 SSH/VM。

最小修复：为受 collector/debug 私有进程管理的嵌套命令保留同一停止范围，或建立可验证的子组回收及所有权协议；独立查询仍可拥有自己的进程组。不能只等待直接子进程或检查其 PID 消失。补充真实嵌套 command 的父死亡、外层超时、关闭及再次收集负向对照。初审的父死亡测试在单个睡眠 collector 上验证，未覆盖此嵌套边界。

### R2 — P2：socket 分析读取的服务端没有消费传入的绝对截止点

**归属：本轮预算接口实现不完整，底层旧行为仍存在；源码确认，未独立运行慢存储探针。**

位置：`plugins/tcad_artifact/tcad_artifact/execution_control.py:728`、`:734`；`plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py:1009`、`:1047`。

`tcad_inspect_outputs` 接受新的 `deadline_monotonic`，但只在整个 `_inspect_directory` 调用前后检查。helper 列目录时另建 `now + 10` 秒时钟，单文件读取/哈希循环根本不检查调用方截止点。触发条件是剩余 IO/Run 时间小于目录处理时间，或受限文件的读取/哈希耗时超过该剩余时间。客户端可以按时退出，服务端仍占用连接处理槽并继续读取；不能据客户端 `TimeoutError` 宣称服务端工作已停止。

此外，`output_recovery.py:94` 的本地重读/哈希及证据登记位于 `_inspect` 的 IO 结算之后。初审实现不能支持“所有连接和读取步骤都消费同一截止点”的完整表述。

最小修复：让本地调用把原绝对截止点传入目录遍历和哈希循环，并将后续本地读取纳入同一有效截止点及记账范围；保留旧调用默认值。主代理提出仅给共享 helper 加可选参数、远端 RPC 不传该字段且 VM 无需更新，是合理的最小方向。因文件名属于原计划限制的 VM runner 源码，应单独记录“仅本地共享 helper 兼容修订”的范围澄清，保留冻结计划原字节。复审须验证服务端实际停止继续遍历/读取，不能仅断言新参数存在。

### R3 — P2：分析可选工具正常返回“不可用”时绕过共享工程诊断

**归属：既有吞错路径未被本轮 B4 修复；源码确认。**

位置：`plugins/tcad_artifact/tcad_artifact/output_recovery.py:103`、`:133`；共同边界为 `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:118`。

`inspect_tool` / `accept_tool` 将实际传输、解析或本地 IO 异常转换为普通返回值，仅留下异常类型和 `str(error)[:1024]`。共同 Worker 边界随后按成功返回处理，不生成共享 `engineering` 详情、异常链和诊断引用。command 超时已经被包装成“collection/transport unavailable”时，底层触发时限和根因继续丢失；顶层字符串还可能携带私有日志路径。已有 Run 工具计时并不能恢复这些信息。

影响：同一次分析中的工程不可用与科学结论限制虽然仍可分开表达，但 Worker 无法据已有接口获得原始工程事实；Root 也不能按本轮新入口追踪该失败。该缺口与本轮要修复的“错误可读、空日志也能解释超时”直接相关。

最小修复：保持工具可返回有限的 `unavailable`，同时通过受控工程记录能力保存异常链并返回有界、脱敏的引用或摘要；不要为得到诊断而把可选评分/读取失败升级成科学 Run 的强制失败。用实际 Worker 工具入口注入空 stderr 超时，并验证 Worker 工作区报告、Root 摘要及诊断引用可读。

### R4 — P2：新角色的观测入口继承了分析专用的 120 秒提交保留额

**归属：本轮公共化引入的行为偏差；源码确认，未独立运行短 Run 命令探针。**

位置：`src/scidiscovery/artifact_agent/service/local_process_observation.py:202`、`:222`、`:325`；截止时间计算在 `:74`。

虽然 `policy="inherit"` 不再强加 512 MiB 与单线程设置，函数和 CLI 的 `submission_reserve=120` 仍对所有角色适用。新角色在 Run 剩余不超过 120 秒时，经默认观测入口执行原本允许的短命令会直接返回 124；在稍长剩余时间下也被额外缩短。控制生成的策略文件只选择 analysis/inherit，未声明这项新增时间保留额。

初审的 `test_common_launcher_preserves_environment_and_full_stdout` 在 `test_execution_collection.py:214` 显式传 `--submission-reserve 0`，且没有真实 assignment deadline，因此无法发现默认行为差异。

最小修复：analysis 保留其既有 120 秒默认值，inherit 使用 0 或角色已声明值，并由控制选择。补短 Run、默认 CLI 参数的对照；继续验证旧分析策略、stdin、完整 stdout/stderr 和退出行为。观测保持可选，不能因此新增提交门禁。

### R5 — P2：公共 general_science 工作区的 finalizer 与 Hardened 写入合同不兼容

**归属：既有全局框架组合缺陷；源码与改前快照一致，不是本轮回归。**

位置：`src/scidiscovery/artifact_agent/service/hardened_files.py:209`；`src/scidiscovery/general_science_components.py:465`；`src/scidiscovery/artifact_agent/service/result_materialization.py:12`；支持性判断在 `src/scidiscovery/artifact_agent/service/hardened_workspace.py:60`。

公共 `general_science:workspace` 声明 `workspace_finalizer`，没有 `workspace_file_policy`。Hardened 默认规则仅在**没有** finalizer 时允许 `output/result.json`；实际 general finalizer 又必须读取这个文件。满足 Hardened 原生工具和文件工具要求、且没有不支持的 review 依赖的合法 Operation，只要复用该公共 workspace，就可能被判定可运行，却无法创建其唯一最终结果文件。模型可见合同明确要求提交该文件，修补科学 payload 不能解决这个工程拒绝。

需要区分两件事：

- 默认 blind.csv 正向夹具的 reviewer 声明 `native_shell="inherited_prototype"`，在 Hardened 下预检拒绝 `operation_runtime_unavailable` 符合当前声明。改前基线的同一测试也失败，证据见 [check-1789279853442855254.log](check-1789279853442855254.log)。这是既有测试夹具与 backend 配置漂移，不应删 review 边或放宽准入来换取绿色。
- 在支持的 Operation 组合中，finalizer 与写入准入冲突是独立、真实的公共组件兼容问题。主代理临时去 review 边的探针只暴露了后续问题，不是合格的最终正向测试；该临时修改已还原。本审查独立核对上述四个源码文件与改前快照逐字相同，未独立重跑此修改夹具。

最小修复：由公共 workspace 声明精确的结果文件写入 policy，或使通用编辑合同能明确表达“finalizer 消费此文件”，并增加真正受支持的组合测试。不要扩大目录写入范围或更改科学审查资格。此项阻止宣称 Hardened 通用兼容已闭合；**不能据此声称采用 local_trusted 的原 Fig.4 现场失败。**

### R6 — P2：安装 smoke 绕过真实适配器重开，尚不满足计划中的安装全链路验收

**归属：本轮验证缺口；不是已证实的安装运行故障。**

位置：`collection-implementation/installed_smoke.py:74`；`tests/operations/test_baseline_effect_lifecycle.py:244`、`:247`。

四个 wheel 的隔离 venv、源目录独立导入、Root 新 Schema、旧配置默认值、精确 UI 决策和后台登记证据有效。但安装 smoke 调用的夹具在启动 collector 前预写 `outputs.json`。子进程因此直接进入 checkpoint 登记分支，绕过 `compile_installed_catalog → runtime plugin load → command/socket collect`。Root 调用也直接经过 Python router，不是安装后 stdio/proxy → daemon 的完整路径。

影响：模块可导入不等于新私有入口在实际运行环境、配置、目录权限和子进程所有权下可用；R1 正是该边界中可以逃过现有正向测试的缺陷。不能把 [installed-smoke.json](installed-smoke.json) 的 pass 延伸为所有安装路径已验证。

最小补充：增加一个安装环境中不预置 checkpoint 的真实适配器重开测试，经过生成配置与实际代理/daemon 入口完成显式 collect、状态查询、登记和 outputs；传输使用受控本地夹具，不需要 VM 或求解器。保留原 smoke 的有效结论与证据。

## 3. 计划完整性与已检查的正确边界

冻结计划总体上已把科学所有权与工程恢复分开，未要求新增科研 Operation、科学 Schema 或 Agent 机械填表。初审实现的主要方向成立，但 P1—P4 的验收尚不完整。

| 目标 | 实际核对 | 初审判断 |
| --- | --- | --- |
| 日志与产物分离 | `ExecutionBridge.sync` 不调用 collect/ingest；终态重读不重放状态转换；查询失败保存 observation_error | 主路径成立；自定义旧 status 调用和本地存储故障下的短查询总界限未穷尽 |
| daemon 单槽 / 同执行互斥 | daemon 共享协调器、执行锁与全局锁、busy 不排队、重复请求不延长冻结预算 | 直接子进程情形成立；R1 阻断完整生命周期结论 |
| 登记恢复 | outputs checkpoint 固定描述符及 collected_at；Artifact 幂等键；输出登记、manifest 登记和最终事务提交分开处理 | 现有真实子进程故障注入证据有意义；未证明所有文件系统/事务中途断电组合 |
| 完整文件缓存 | SSH 按执行目录、名称、大小和摘要核对；临时下载完成后发布；43 文件夹具验证前序文件复用 | 已覆盖主要恢复语义；不等于任意字节网络断点续传 |
| 分层预算 | Root 总预算、停止余量、command/socket 的绝对值传递、数据库连接等待裁剪 | 主体有实际消费方；R2 仍缺服务内读取；调试工具预算见下一节待决项 |
| 诊断 | Root/Worker/代理共享工程格式，限制详情读取范围；记录失败不替代原错误；异常链可跨包装 | 新机制成立；R3 留下真实调用路径缺口；未穷尽所有敏感内容编码和文件系统故障 |
| 可选 native 观测 | 公共 launcher、缺失/损坏原因、analysis/inherit 环境分离、共同工具计时 | 无观测不阻止合法提交；R4 是资源行为偏差；裸平台命令仍属覆盖空白 |
| 科学与身份边界 | 原 Operation/Run/执行 Schema、精确审批合同、分析输入/执行来源检查未被本轮删除 | 未发现本轮以工程诊断替代科学判断或以聊天替代 UI 决策的修改 |
| 安装与调用者 | 检查 Root schemas、两种 TCAD 适配器、SSH bridge、debug 私有进程、analysis inspection、脚本新 collect 顺序与 wheel smoke | R6 说明安装证据的实际边界，不能按全组合通过处理 |

## 4. 全局设计判断与明确未验证项

1. **模型合同与执行准入仍需做组合一致性检查。** R5 表明单个 workspace hook、backend 能力检查和结果 finalizer 各自合法，组合后却可能无可执行写入路径。修复应归属工作区合同，不能让科学 Agent 反复改输出文本、删除独立审查或要求调度器手填额外运行证明。
2. **工程失败不能只靠最外层异常捕获。** 可选工具的有限返回是合理设计，但 R3 表明正常返回也可携带工程失败。应保留有限分析的通道，同时使诊断与工具结果组成一致合同，避免把“文件不可读/工具超时”说成“模型无法拟合”。
3. **原生观测不是完整执行证明。** 检查到现有机制保持 `scientific_evidence=False`、缺文件/损坏记录有差别。未经过 launcher 的 shell、平台未暴露的错误、Agent 推理时间均不在此观测保证内。不能由没有错误记录推导没有实际错误。
4. **作者调试的工具预算仍需明确验收。** `local_debug_service.py:127` 终态收集只取 Run 剩余时间并扣本次经过时间；原 360 秒账本在 `_start` 约束求解预留。冻结计划要求终态收集同时服从“工具已授权剩余预算”，但初审没有见到独立收集预算消费或对应对照。360 秒原文是 solver reserved wall time，不应直接把它偷换成新的 IO 门禁。此处列为计划合同待闭合项，未宣称已复现越权求解或已确认应如何分摊预算。
5. **配置报告目前主要是默认值投影。** 自定义 command 查询预算大于默认 10 秒 proxy 等待时，服务/代理预算关系及真实有效值报告没有得到本次验证。SQLite/本地文件系统等待、配置重载、不同插件安装/禁用/升级、维护锁被其他进程持有时的所有组合，也未被一次 wheel smoke 覆盖。
6. **恢复与资格不能混同。** 本轮 checkpoint 可恢复工程登记，现有 tool evidence 仍区分已保留和已采用的记录；没有看到用下载缓存自动更新科学资格的修改。未重新审核所有 Operation 的 revision/current/qualification 路径，不能据此报告全框架科学恢复合同均通过。

## 5. 验证记账与部署判定

[checks.jsonl](checks.jsonl) 保留了失败及通过。初审读取的最后一批收集测试为 [check-1789281444461983267.log](check-1789281444461983267.log)，23 passed、17.50 秒、峰值 277,598,208 字节；最新初审安装 smoke 为 [check-1789281470204729876.log](check-1789281470204729876.log)，11.26 秒、峰值 177,516,544 字节。另读取了分析恢复/native 观测、socket inspection、审批身份、平台配置和部署脚本相关证据。这些是有范围的有效测试，不是全量通过证明。

例如 [check-1789280835597390230.log](check-1789280835597390230.log) 的合批仍为 97 passed / 2 failed；随后相应平台/部署用例通过的记录与 Hardened 失败记录应分开解释。后续两项 Hardened 测试仍失败，见 [check-1789280962586934432.log](check-1789280962586934432.log)，不能以别的 23 pass 抹去。

初审版**不应部署为本计划已完成的修复**。至少 R1—R4 的实际缺口及 R6 所需安装路径证据应修复并独立复审；R5 应保持为明确的既有全局问题，若本轮暂不修复，必须限定所支持的 backend/组件组合，不能宣称 Hardened 已全闭合。审查期间主代理启动的修复、共享 helper 范围澄清和后续测试属于新的修订输入，本报告不自动变更为 PASS。

本次工程证据不能证明 Fig.4 拟合已经改善、平台与尾部目标均覆盖、科学机制得到唯一识别、有限实验族可以拟合全部曲线，或原科学目标已完成。部署后仍须恢复**同一次已批准执行**的产物并由匹配分析 Operation 形成 completed 的封存分析，才能给出对应科学结论及局限。
