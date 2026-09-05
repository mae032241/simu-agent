# R5-F 发布、扩展性与总回归独立审查

日期：2026-08-30  
审查者：未参与 R5-F 实现的独立审查者  
结论：**通过（仅放行 R5-G）**

## 1. 审查边界

本轮审查对象是当前共享工作树的 R5-F 精确候选。审查只判断发布态架构集成、扩展性、权限、
生命周期、安装态和复杂度门，不评价尚未开始的 R5-G 科学效果，也不把真实 Sentaurus、许可证、
输入槽求解或本轮科学结论资格提前算作 R5-F 要求。除本报告外，审查者未修改生产代码、测试、
计划或阶段状态。

所有测试和只读探针均严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

## 2. EvidenceAudit

### 2.1 来源声明

- S1：`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 3、10、12—16 节；
- S2：`docs/plans/R5_F_RELEASE_AND_EXTENSIBILITY_VERIFICATION.zh-CN.md`；
- S3：`docs/plans/reviews/R5_E_RUNTIME_PLUGIN_GATE_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；
- S4：当前 `src/scidiscovery/operations/`、Root/Task/Worker、runtime plugin bindings、daemon、
  ExecutionBridge、审批 UI 及四个生产插件源码；
- S5：当前 `tests/operations/`、`tests/artifact_agent/`、clean-wheel fixture 与发布构建器；
- S6：`.scidiscovery/r5-f-private/tcad-run-20260830-06/qualification-report.json`、其声明的四份
  Codex session、父事件/诊断/最终消息、运行时摘要、只读 SQLite/CAS 状态；
- S7：`.scidiscovery/r5-f-private/tcad-run-20260830-01` 至 `-05` 留存的失败报告、事件和日志；
- S8：`scripts/r5_baseline_metrics.py`、`scripts/r5_current_metrics.py`、冻结结构 fixture 及本轮
  独立命令输出；
- S9：`docs/ARCHITECTURE.md`、`docs/ARCHITECTURE.zh-CN.md` 与 `docs/plans/README.md`。

### 2.2 检查记录

| 检查键 | 结论 | 证据 |
| --- | --- | --- |
| `f1_static_integrity` | 通过；diff、207 个生产/测试 Python 文件 AST、6 个部署 shell 均有效 | S5、S8 |
| `f2_single_discovery_authority` | 通过；生产元数据只有 `scidiscovery.plugins`，目录构造和安装缓存各一处，旧三组入口有真实不可达负例 | S4、S5 |
| `f3_clean_wheel_matrix` | 通过；core、full、full+InGaAs、broken/未知插件均从生成的 clean release/wheel 独立运行 | S5 |
| `f4_four_executor_entries` | 通过；Agent、Transform、Effect、Approval 均从 `operation_invoke` 进入既有生命周期 | S4、S5 |
| `f5_parameter_two_workers` | 通过；真实 PDF 受控读取、提取 Worker、独立审计 Worker、coverage、UI、uncertainty、TCAD author/reviewer 链均由 full wheel 执行 | S5 |
| `f6_blind_producer_extensibility` | 通过；未知 Schema/端口插件无需改核心，任意端口族、主附件错配、指纹漂移、跨实例和修订负例失败关闭 | S4、S5 |
| `f7_tcad_least_authority` | 通过；author 获得一个注册调试工具和受控 deck 写面，reviewer 无该工具且只读任务根 | S5、S6 |
| `f8_runtime_double_daemon` | 通过；缺失/额外/损坏/符号链接配置和递归运行时身份漂移在实际 control/Worker daemon 入口早失败 | S3、S4、S5 |
| `f9_fixed_ui_boundary` | 通过；固定文档节点、XSS 转义、未知 Schema 原始附件回退和精确一次决定未恢复领域 renderer | S4、S5 |
| `f10_regression_and_metrics` | 通过；独立全仓 299 项通过，三重复杂度数值与实现记录一致 | S5、S8 |
| `f11_real_codex_lifecycle` | 通过；实际父会话无代写，两个独立子 Agent 无父上下文，原生只读、精确 Worker MCP、受控写/校验/finalize 和 Root completed 均有原始会话与数据库证明 | S6 |
| `failure_history_truthfulness` | 通过材料失败项；启动配置、聊天边界、任务根读取三类失败有原始失败见证，成功轮使用新状态、任务、Agent 和摘要；最早通用 runner 的源码路径失败缺独立日志，仅作非材料调试叙述 | S2、S5、S7 |
| `constraints_and_occam` | 通过；未增加表、持久状态机、注册表、入口组或第二生命周期，删旧权威后的聚合净减满足门槛 | S1、S4、S8 |
| `core_domain_token_boundary` | 通过；四处命中仅是领域无关曲线科学数据模型对同包 `curve_score` Schema 的静态类型导入，不参与 Operation/插件/角色/端口分派 | S4、S8 |
| `stderr_chat_boundary` | 通过；JSON 事件和诊断分流，事件解析拒绝任意非 JSON，wait 消息与父最终消息均要求唯一固定文本，诊断不进入科学结果或调度输入 | S5、S6 |
| `claim_scope_honesty` | 通过；报告只声明架构集成，不声明语法、输入槽、执行就绪或科学可采纳性 | S2、S6 |

## 3. 关键独立核验

### 3.1 单一权威与真实入口

生产发行元数据只声明 `scidiscovery.plugins`。`compile_installed_catalog()` 是唯一安装发现入口；
`catalog.py` 只有一处 `CompiledCatalog(...)` 构造和一个 `lru_cache(maxsize=1)` 安装缓存。
`public/support/internal/all` 由该对象投影，没有第二目录。

Root 的统一准备路径继续共同服务 preflight/invoke；Agent 进入 Task，Transform 直接产生不可变
Artifact，Approval 进入唯一 ApprovalService，Effect 进入唯一 Execution/ExecutionBridge。
插件 runtime factory 只贡献本地 adapter、tool service 和 reconciler，没有变成 capability、人工
批准或在线协调服务。未知 producer 插件和 InGaAs 增量插件的 clean-wheel 测试证明插件扩展不需
修改 Root、Task、Scheduler、UI 或安装器。

### 3.2 真实双 Agent 证据

第 6 轮资格报告 SHA-256 为：

```text
0e23b55fb021c6531162d944764200b4d890e2fd9d2c8617f272cecf8217592e
```

报告声明的四份 session 和全部日志摘要均与当前私有字节一致。原始 session 进一步证明：

- author/reviewer 父会话均只调用一次 `spawn_agent` 和一次 `wait_agent`；
- 两次 `spawn_agent` 都使用精确编译 `agent_type`、`fork_context=false` 和唯一固定消息；
- 两个子 session 的 `thread_source=subagent`、角色和唯一用户任务消息匹配，未继承父验收提示；
- author 的 21 次、reviewer 的 9 次原生命令全部在各自物化任务根内、全部退出码为零，未原生写文件；
- author 只调用自身 Worker server，真实调用 `worker_tcad_debug_run(mode=preflight)`，随后受控
  写入/修补、validate、finalize；reviewer 只调用自身 server，没有调试工具；
- Task 数据库中两者均为 `completed/finalized`，输出 Artifact 摘要指向 CAS；父会话无 Worker 调用，
  Approval/Execution 表为空，因此该预检没有被冒充为人工资格或外部执行。

资格脚本的 27 项布尔检查本身没有单列 `fork_context=false`。这不造成当前证据缺口，因为留存的
两份父 session 已直接记录该参数，两份子 session 也直接证明上下文没有继承；以后若修改资格脚本，
宜把已有 `_spawn_has_no_parent_context` 判据接入 R4 报告，避免未来只能靠人工复核原始 session。

### 3.3 失败轮次与聊天旁路

第 1 轮 control daemon 日志精确记录未安装 runtime 配置被拒；第 2 轮父事件保留了子 Agent 对
新建序列的误判；第 3、4 轮报告只因混入 JSON 流的诊断而失败；第 5 轮只因 reviewer 的父目录
搜索而失败。第 6 轮没有覆盖旧目录，而是使用新的操作摘要、Task 和 Codex session 重跑。

当前 runner 把 stdout JSON 事件与 stderr 诊断分别封存。完成信号判据对 JSON 流中的任意非 JSON
文本失败关闭，并只接受固定 child wait 消息和固定 parent final；stderr 既不被解析为结果，也不
进入 Root/Task 科学对象。因此这次分流修复的是证据通道，不是放宽聊天内容白名单。

### 3.4 复杂度与通用核心边界

独立复算：

- R0 六职责后继聚合：`9818 / 13657`，净减约 `28.11%`；
- `src/scidiscovery/operations/`：7 个 Python 文件、`2053 / 2060` 行；
- `src/ + plugins/`：144 个生产 Python 文件、`60723 / 62533` 行；
- `deploy/install.sh`：1026 行，按计划单列；
- 冻结基线生成器 SHA-256：
  `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`。

职责 successor 口径防止搬文件伪造减重；全生产口径防止把核心代码搬到插件后误报删除；Operation
包继续受独立上限约束。当前没有为了 R5-F 新增科学实体、服务定位器、所有权数据库或插件状态机。
四处 generic core 领域词均位于通用实验、实验意图、科学目标和曲线诊断数据模型的静态导入；
核心没有据此选择 Operation、插件、角色或端口。

## 4. 独立命令结果

```text
pytest --collect-only -q
=> 299 tests collected

pytest -q
=> 299 passed in 93.01s

git diff --check
全部 src/plugins/tests Python ast.parse
bash -n deploy/*.sh
=> 均通过

python scripts/r5_current_metrics.py
=> 9818/13657；operations 7/2053；production 144/60723；deploy 1026；
   generic core domain-token count 4
```

全仓回归包含 clean release 构建、wheel 构建、core/full/full+InGaAs/unknown/broken 隔离安装和真实
daemon/CLI 探针，不是只在源码 `PYTHONPATH` 上运行。实现记录中的 167 项聚焦结果未附单独命令，
但其所有材料问题均被本轮当前字节的 299 项全仓回归及上述源码审查覆盖，不影响门禁判断。

## 5. 非阻断发布边界

根 `MANIFEST.sha256` 仍是历史 R4 清单，不能用来证明当前 R5 工作树；当前计划第 11.4、15 节明确
要求 R5-G 科学效果审查通过后才冻结下一代根清单。R5-F 的 clean release 构建器已在隔离目录生成
并自校验当前候选清单，因此这里不提前改写根清单，也不把未来发布冻结冒充当前完成事实。

双语 `docs/ARCHITECTURE*` 明确自称 R5-0 冻结的 R4 快照，其债务段落不是当前 R5-F 代码事实。
它们在最终发布冻结前仍需更新为已审查后的当前架构，但按同一停止规则，这属于 R5-G 后的发布
语料收口，不是本轮实现缺陷。

最早一次通用历史 runner 的目录只留有密钥和运行时配置，没有 stdout、stderr 或 Codex session，
因此无法独立复现实施记录所称的“命令环境缺少源码路径”这一具体原因。它发生在选定当前 TCAD
真实验收链之前，不参与 F1—F11 的通过证据；当前 clean-wheel 负例已独立证明被删除的内部
Operation 返回 `operation_unknown`。本报告不把该缺失调试日志当作当前架构失败，也不从它推导
任何通过结论。

## 6. 门禁结论

**结论：通过（仅放行 R5-G）。**

F1—F11 的当前事实均有源码、安装态测试或原始运行证据支持；没有发现第二注册表、第二状态权威、
领域核心分派、权限扩大、聊天结果旁路或复杂度反噬。该结论只允许开始 R5-G 冻结小任务的科学
效果回归与独立科学审查；不表示 R5 已完成，不批准下一代发布清单，也不声明真实 Sentaurus、
三领域通用性或科学效果已通过。
