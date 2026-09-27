# R5-L2 最小本地 Run 实现第二轮独立复审

日期：2026-09-01  
审查者：`r5s_s0_independent_review`（未参与实现）  
结论：**不通过（FAIL）；L2 继续冻结，不得放行 L3—L6**

## 1. 审查对象与方法

本轮重新检查当前工作树，不继承首轮结论，也不把实现方报告的测试通过数当作语义通过。候选关键
摘要如下：

- 活动计划：`fa1052b518605d2fc25923bb7577c6ef76199abfdcc42b58d422de50cf0a2bfb`；
- L2 证据说明：`b1815ba13fb3649afa5d27906b038f0c3b91969bd325671212a5776ebe33d5cb`；
- `runs.py`：`69fd8f61a0c2c69e45096a5ad98a499a8ff116af49267c2bbcde320c7b8dcd2f`；
- `run_current.py`：`585431894d766e4a7c080dc9f33472d4e0cb8ac7213cb6f8be6350c1996751ae`；
- `local_workspace.py`：`7f17d6b180a7cbce11b1efa0959250950e45617659b097404eceeefad1b4a57b`；
- `mcp_local_worker.py`：`2d08fad6c7836d3d67d95918daea984c81a4eb898f6e08e6ddbcd3b55d3cb504`；
- `mcp_root_run_routes.py`：`0ec157eb612fa94f274d38fb03831473e4f1377956fa4144c749ccbbb7e8945e`；
- `mcp_root_instance_routes.py`：`34fa2da78ce4dcb9c114c1df28290395497a11fbbf64560955fef9c3f55a9338`；
- Local 工具投影：`2ea812f1fb58990cdc3117553e8f187cf287521587ae05d4257210e4bd2bb670`；
- Codex 配置生成：`453a39d588734ca1d97445a32c1d07f3bd354f353cd6953f59a2fe15ceaa9a21`；
- live 探针脚本：`7fe22177e9563a8358de7ba5866e9a828f6f20a4c2b017fe20af28c4600bd9e3`。

审查覆盖首轮 B1—B8、当前真实 Root/Worker/Codex/部署路径、33 项约束和奥卡姆边界。独立串行运行：

```text
PYTHONPATH=src:tests/fixtures/plugins/blind_csv_operation_plugin \
python -m pytest -q \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_l2_run_invariants.py \
  tests/artifact_agent/test_platform_configuration.py

16 passed in 4.15s
```

`git diff --check` 通过。测试通过只证明其实际覆盖的路径，不能覆盖下述跨边界反例。

## 2. 首轮 B1—B8 复核表

| 项 | 第二轮判断 | 说明 |
| --- | --- | --- |
| B1 current 递归、事务重检和 CAS | **未闭合** | Run 内递归锚点和完成事务重检已实现；真实 Root 更新 current 仍无预期旧 ref，并继续把 current 与资格、latest 捆绑 |
| B2 候选、收据和恢复 | **未闭合** | 候选摘要、Artifact 幂等键、完成收据已实现；失败 CAS 到工作区隔离之间仍有不可恢复崩溃窗，进程级故障证据也缺失 |
| B3 查询纯读 | **未闭合** | `RunService.status/list` 已纯读，但 Root `run_status/run_list` 在查询路径首次绑定输出 Artifact |
| B4 Local/Hardened 边界 | **闭合** | Local 默认只实例化 Run；Task 工具隐藏，旧 Worker daemon 默认禁用；Hardened 在接入 Run 前显式拒绝生产配置并保留冻结回归 |
| B5 单一工具投影 | **未完全闭合** | 盲 CSV 的 assignment/profile/router 已相等；默认公共目录仍可准入声明了工具、但 Local 投影静默删除工具的 Operation |
| B6 路径身份 | **闭合** | Worker 可见目录为随机 `workspace_<uuid>`，Run 关联只在 backend 私有摘要绑定中 |
| B7 真实 Agent | **未闭合** | 有真实 stdio 进程，但所谓 live Agent 没有调用 MCP/领域工具/submit，也没有使用返回的编译 `agent_type` |
| B8 发布扫描 | **闭合** | 初次 seal 与已接受候选重读均执行路径、秘密、媒体/二进制和 UTF-8 检查，并受编译文件/字节上限约束 |

## 3. 阻断项

### B1：current 的真实控制入口仍是旧资格门，不是计划批准的最小显式 CAS

`RunCurrentGuard.freeze/unchanged` 已经把 `(kind, logical_name, exact ref)` 及生产收据继承锚冻结，并且
`RunService._complete` 在 attached scheduler 数据库的完成事务内重新检查锚点；这部分是有效返修。

但真正暴露给调度器的 `scientific_current_select` 仍有三项相反语义：

1. `ScientificCurrentSelectInput` 只有 `name`、`kind`，没有 `expected_ref`；
2. `mcp_root_instance_routes.py:243-277` 先强制目标必须是该语义名的最新 revision；
3. 同一路径调用 `_claim_admissible`，未资格化就拒绝 current。

因此计划 8.2 的“current 用预期旧 ref 显式 CAS、删除与资格的隐式捆绑”和 8.3 的“普通探索不创建
qualification/cohort”尚未进入真实 Root。`test_scientific_current_is_an_exact_compare_and_set_head` 直接调
`SchedulerBindingService`，绕开了生产 Root 输入合同；current 递归测试又只覆盖 `stale_rejected`，没有
证明生产命令能以精确旧 ref 推进 head。当前 `head_advance=advanced` 也没有任何可达声明或入口。

**影响：** 普通 Local Run 输出无法作为不带资格负担的最小 current；并发或陈旧调度器不能在 Root
命令边界提交预期旧 ref。违反当前计划 8.2/8.3、`AUTH-001`、`LIN-002`、`CQRS-002`。

**最小修正：** 不增加 CurrentPolicy/候选表。只把 `expected_ref`（首次设置显式为无 head）加入现有
Root 命令并直接调用现有 `select_scientific_object(..., expected_ref=...)`；删除 latest 与 qualification
门禁。需要资格的晋级留给后续可选 PromotionPolicy。增加经过 Root 的首次选择、精确 CAS、陈旧 CAS、
未资格普通 Artifact 和递归 stale 后代测试。

### B2：失败终态到 backend 隔离不是可恢复协议，真实进程崩溃矩阵未满足

候选摘要、`Run + digest` Artifact 幂等键、同事务完成收据和 completed 查询恢复均已存在，这是实质
改进。然而 `RunService.record_failure` 的顺序仍是：

```text
尽力 seal → 数据库 CAS 为 failed 并提交 → backend.discard/隔离 → 写 recovery_draft_json
```

若进程在 `runs.py:350` 提交 failed 后、`runs.py:353` 调用 `discard` 前崩溃，Run 已是 failed、工作区
仍可见且 `recovery_draft_json` 为空。重试 `record_failure` 在 `runs.py:318-320` 看到 failed 后立即返回，
不会补做隔离或草稿。若崩溃发生在 `LocalTrustedBackend.discard` 的 `os.replace` 之后、binding 删除或草稿
登记之前，binding 仍指向已不存在的原目录，随机 quarantine 路径又没有可重放关联，恢复同样丢失。

现有 `test_candidate_binding_crash_windows_and_response_replay` 使用同一 Python 进程内 monkeypatch，并在
同一个 Router 对象内重试；它没有杀死并重启 stdio MCP/backend。测试也没有覆盖上述失败 CAS 后窗口。
这不满足首轮已明确要求的真实进程 seal 后、Artifact 后终态前、completed 响应丢失以及失败隔离窗口。

**影响：** timeout/Agent 崩溃恰好落在该窗口时，旧工作区既未被可靠 fence，也不能创建显式恢复 Run；
`RES-002`、`IMM-002`、计划 5.3 的“先失败并隔离，再冻结 backend-private 草稿”尚未闭合。

**最小修正：** 不增加业务状态。让 backend-private Run→目录/隔离映射和 `discard` 可幂等重放；对已
failed 且草稿未完成的 Run，显式 reconcile 必须能够继续隔离和登记同一草稿。用独立进程在上述边界
退出并以新进程恢复，证明旧 submit/heartbeat 拒绝、目录已隔离、草稿摘要稳定、新 Run 只能绑定原
Operation 与精确输入。

### B3：Root 查询仍发布输出绑定，`status/list` 并非端到端纯读

`RunService.status/list` 本身已经不再推进 timeout，这项局部修复正确。但生产 Root 的
`mcp_root_run_routes.py:51-56` 在 `_run_status_value` 中执行：

```python
if value.output_ref is not None:
    self._bind("artifact", output_name, value.output_ref.artifact_id)
```

`run_status` 和 `run_list` 都经过该函数。于是 Worker 完成后，第一次查询才向
`scheduler_bindings.sqlite3` 插入 `name.output`；是否可供下游 Operation 解析取决于是否有人读过状态。
现有纯读测试只哈希 `runs.sqlite3`，且在 Run 尚未完成、`output_ref is None` 时调用查询，所以没有检测
这个跨库写入。

**影响：** 查询顺序决定科学输出何时进入语义目录；GET/状态观察仍承担发布命令。违反 `CQRS-001`、
`CQRS-002`、`AUTH-001`，也使 completed 收据不是完整的唯一终态事实。

**最小修正：** 不新增 collect 状态。Run 创建时冻结派生输出语义名，submit 完成命令在现有控制事务
中完成 Artifact 绑定；随后 `run_status/list/lifecycle_events` 只读。测试必须同时哈希 Run 和 scheduler
数据库，并覆盖 completed 后的首次及重复 status/list。

### B5：Local 工具投影对盲插件一致，但对默认公共目录仍会静默降级

盲 CSV Operation 的 assignment、生成 profile 和 Router 现在都消费
`operation_local_worker_tool_names`，逐项相等测试有效。但这个投影会静默删除所有既无 `handler` 也无
`contextual_handler` 的已声明工具；Root catalog/preflight 没有使用同一可执行性判定。

独立对 `CORE_PLUGIN + GENERAL_PLUGIN` 复算显示，10 个 public Agent Operation 的完整声明都包含
`worker_file_*`；五个证据类 Operation 还声明 `worker_extract_pdf_text`，而 Local 投影对它们全部只剩
三个生命周期动作。原生写可以有意替代 Hardened 文件运输，但 PDF 冻结没有等价 Local handler；目录
和 preflight 仍把这些 Operation 当作可调用。换言之，“实现对象恰好没有 handler”在运行时成了
OperationSpec 之外的隐式能力撤销条件。

**影响：** scheduler 可得到 admissible 的 public Operation，生成的 Agent 却没有其声明并可能依赖的
工具；`AUTH-003`、`TOP-002`、`ROLE-002` 尚未在默认目录上成立。盲插件正例不能外推到其他已安装
Operation。

**最小修正：** 不建 backend 工具注册表。由同一个编译投影明确解析“Local 原生等价能力”和“必须有
Local handler 的领域工具”；缺失后者时 catalog/preflight 对该精确 Operation 失败关闭。为 PDF 等确有
Local 消费者的工具提供无 Task/session 的窄 handler。增加所有已安装 Agent Operation 的
catalog→preflight→assignment→profile→Router 可执行工具一致性测试。

### B7：持久化探针没有证明编译角色真实调用 MCP 和领域工具

`test_real_stdio_worker_process_opens_calls_registered_tool_and_submits` 确实启动了真实
`python -m ...mcp_local_worker`，但调用者仍是测试代码，输出也由测试代码 `Path.write_bytes`；它不是
真实 Agent 证据。

`scripts/l2_live_agent_probe.py` 的证据更弱于说明文本声称的流程：

- `bridge()` 自己启动 stdio MCP，并由桥接进程调用 `worker_open_assignment` 和
  `worker_csv_summarize`（236—237 行）；
- 桥接进程把领域工具结果、绝对工作区路径和输出路径写入 `agent-exchange/instruction.json`
  （238—260 行）；
- Agent 只需原生写结果和一个 ready marker；
- marker 出现后，仍由桥接进程调用 `worker_submit_result`（268 行）；
- `final-evidence.json` 只记录“生成过的 agent_type 字符串”，没有记录实际执行角色或 Agent 工具事件。

证据文件已经披露实际使用通用 `worker`，不是 `operation_invoke` 返回的
`op_blind_csv_observe...`。因此真实子智能体没有经过正式生成 profile 打开 assignment、调用领域 MCP
并 submit；桥接文件反而绕开了该权限和工具边界。持久化 Run/Artifact 只能证明桥接进程完成了正式
提交，不能证明 Agent 完成。

**影响：** 用户明确要求的真实 `spawn_agent`、编译 `agent_type`、原生能力与领域工具联合验收仍缺失；
`ROLE-002`、`AUTH-003` 和 `MIG-002` 不能通过该探针证明。`SEC-002` 继续作为已披露 known issue，不是
本项失败的原因。

**最小修正：** 先在当前 Codex 会话启动前生成/安装 profile，必要时重启会话使自定义 agent type 可
发现；父调度必须使用 `operation_invoke` 返回的精确 `agent_type` 和 `fork_turns="none"`。子 Agent
自己调用 exact Worker MCP 的 open、注册领域工具和 submit，并用原生文件能力写输出；不得由 bridge
代调工具、转交工具结果或代 submit。最终仍只以 Root 的 sealed Artifact/收据为结果，并保留可核验的
实际角色、MCP 工具序列和配置摘要。

## 4. 已闭合边界与未发现的新权威

以下项本轮认可，不应在返修时推倒重做：

1. **B4：** `open_runtime(worker_backend="local")` 只实例化 `RunService`；Task/token 为 `None`，Local
   Root 不列出 `task_*`，默认部署禁用旧 Worker daemon。Codex Hardened 配置在 L5 接 Run 前明确失败，
   没有继续制造 Root=Run、proxy=Task 的可运行假象。旧 Task 实现仍只作冻结回归。
2. **B6：** 随机工作区名称和 backend-private 哈希 binding 已消除从路径直接读取 Run id 的问题。
3. **B8：** Local seal 的单一内容扫描同时用于初次候选和接受候选重读；测试覆盖机器路径、明显秘密、
   未声明二进制和正常 JSON。
4. 未发现按 `blind_csv`、TCAD、Schema 或角色名加入核心分支；`RunCompletionReceipt`、
   `CurrentAnchor`、`SealedWorkspace` 都是在保护既有承重不变量，不是新的科学语义权威。
5. 当前新增 Local/Run 生产文件约 2200 行，其中 `runs.py` 为 741 行。它偏大但仍围绕一个终态权威；
   此时为追求行数拆出 Repository/Manager 会增加对象和跳转，不应作为返修目标。

## 5. 非阻断建议

1. `runtime.py` 默认路径虽不实例化 Task/token，模块顶层仍导入 Hardened 的 `TaskService`、
   `TaskTokenService`，并经 `service.__init__` 载入较重旧实现。L6 可按已冻结删除门做延迟导入/独立包；
   不要在本轮为此建 BackendRegistry。
2. 同一 Operation digest 的全局单活动槽会串行化不同 ResearchInstance。第一版本意如此，待真实并发
   数据证明成为瓶颈再决定是否改为 `(instance, operation_digest)`，现在不扩并发协议。
3. Local 发布扫描是有界启发式，不应宣称能发现所有凭证；继续保留 `SEC-002 known_issue` 和仅可信
   本地、无生产凭证、无不可逆副作用的发布边界。

## 6. 最终判定

**FAIL。L2 不通过，不得进入 L3。**

本轮不是因为代码尚不够宏大而打回，而是四个最小主干事实仍未闭合：current 的生产 CAS、完成输出的
命令式绑定、失败隔离的可恢复性、以及编译角色真实调用工具。修复应只落在现有 Root 命令、Run 记录、
backend-private 映射和单一编译投影中；不得新增第二 current、第二注册表、第二生命周期、领域特判或
兼容转发。上述阻断全部由新的独立正反例和真实 Agent 证据闭合后，方可再次复审 L2。
