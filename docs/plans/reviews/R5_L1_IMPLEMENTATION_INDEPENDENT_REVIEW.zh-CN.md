# R5-L L1 实现独立审查

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与 L1 实现）  
结论：**不通过；不得放行 L2**

## 1. 审查绑定与范围

本轮绑定当前工作树中的以下候选：

- 活动计划 `R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md`：
  `4a60cb3cecbf1058090f60c5257219e92854b0f6b1e1cd9dd1446088537dbe47`；
- L1 证据 `R5_L1_MINIMAL_PROJECTION_AND_BLIND_PLUGIN.zh-CN.md`：
  `b39a2b34dced700de44d43e715e3a32176fac78707a41204a70ac385d85b5180`；
- `operations/spec.py`：
  `23c83e50cb52c3943af4cd0e6ef0c7087712b2f96af5a31f5a7bd355c53695f1`；
- `operations/catalog.py`：
  `f4b8048078658f8ca34a55ca62d91c8c70d9a76ef9df8f256b1c5562dacef989`；
- L1 测试：
  `29a89fd7c96fd9e932a592c911d4e20217cb46c0aa45f57486c7def7584233ad`；
- 盲插件注册文件：
  `82a263723a6d83392e866fbb14d75ec28ed88f5d5be2e962c3c4ec0d669aaa4e`；
- 盲插件工具文件：
  `248645278f4d7cef1e0dc472c2413167a06d6a0dab831d7d26d5178764d341bc`。

相对 L0 的 209 项终点清单，生产范围只有四项发生变化：根 `pyproject.toml` 的 pytest fixture
路径，以及 `operations/__init__.py`、`operations/catalog.py`、`operations/spec.py`。盲 CSV 插件本体
位于测试外置 wheel，另有测试和安装 fixture 接线。本轮没有把相对历史 `HEAD` 的巨大重构差异误当
成 L1 差异。

## 2. 阻断项

### 2.1 盲插件领域工具在真实 Worker 路径不可调用

证据文件第 56 行声称 `worker_csv_summarize` 已可调用，但现有两个正例都直接取得
`WorkerToolDefinition.contextual_handler`，再传入测试自造的 `Task` 对象。它们绕过了
`WorkerMCPRouter`、精确任务绑定、Task capability 和真实 activity 服务。

独立审查使用当前生产入口执行：

```text
Root operation_invoke(blind.csv.observe.v1, 精确 CSV Artifact)
→ prepare_exact_dispatch
→ WorkerMCPRouter.worker_open_assignment
→ WorkerMCPRouter.worker_csv_summarize
```

真实调用稳定失败：

```text
blind_csv_plugin/worker_tool.py:20
  context.task.record_activity("blind_csv_summary_completed")
→ TaskService.record_activity
→ ValueError: unknown worker activity
→ WorkerToolError: registered worker tool failed
```

根因是 `src/scidiscovery/artifact_agent/service/tasks.py:812` 的 `record_activity` 仍使用核心硬编码活动
白名单，而插件发明了一个未在其中声明的领域活动。Router 本来已经在 contextual handler 成功后统一
写入 `operation_tool_succeeded:worker_csv_summarize`，因此这个插件私有 activity 没有独立事实，既
重复又触发第二份准入。

影响：

- 作者 Operation 的唯一领域工具实际不可用；
- 无法通过真实提交证明输出确实绑定精确 CSV；
- 作者不能产出正式 Artifact，因而独立 reviewer 边也不能沿真实控制路径闭合；
- 直接 handler 测试形成假阳性，clean-wheel 测试也只证明导入和直接函数调用，不证明安装态 Worker
  路由可用；
- 若按最直观方式把 `blind_csv_summary_completed` 加进核心白名单，会迫使每个新领域修改核心，直接
  违背 `AUTH-003`、`PLG-001` 和低成本插件目标。

最小修复边界：

1. 删除盲插件的自定义 `record_activity`；不得向核心白名单添加 `blind_csv` 名称，也不得新增活动
   注册表。通用 Router 已拥有足够的工具成功/失败审计事实。
2. 把测试改为至少一条真实 `operation_invoke → exact dispatch → WorkerMCPRouter` 路径，确认工具只
   在作者 Operation 可见、从 `source_table` 读取精确绑定字节、返回确定结构，并由第一次
   `worker_submit_result` 完成正式输出。
3. 同一路径增加错误 CSV 或篡改结构负例，确认输出 contextual validator 在真实 submit 上拒绝，而
   不是只直接调用 validator。
4. 用作者完成 Artifact 调用 reviewer Operation，绑定原 CSV 和精确作者输出，完成 reviewer 结果并
   验证 `is_exact_reviewer_output`；不要求 L1 启动真实 Codex，但必须闭合真实控制边。

在此之前，“作者工具可真实调用、输出绑定精确 CSV、独立 reviewer 边闭合”不成立。

### 2.2 原始 CSV 被错误标为 `prior_signal`，与模型可见证据规则冲突

`blind_csv_plugin/plugin.py:71-82` 的 `_input` 把所有输入硬编码为 `usage="prior_signal"`。这同时作用
于作者和 reviewer 的原始 `source_table`。然而：

- `roles/common.md:34-39` 明确告诉 Worker：只有 `claim_evidence` 可以支持任务主张，
  `prior_signal` 不得替代 claim evidence；
- 作者提示又要求根据 exact source table 给出 `interpretation`，其 deterministic structure、均值和
  科学解释都直接来自该 CSV；
- reviewer 也被要求对照原 CSV 审查观察，却收到同样的非证据用途标记。

因此模型面对的是互相冲突的合同：Operation 要求它用 CSV 做科学观察，共同角色合同却要求它不得把
该输入当证据。现有测试只在 Python 中直接传 bytes，未物化和检查 Agent 实际看到的 usage，因而没有
发现冲突。

影响：盲插件即使修复工具调用，也不能作为“通用科学 Agent 可低成本吸收新领域”的有效证明；Agent
要么违反证据边界，要么无法完成 Schema 要求的解释。这影响 `EVD-001`、`ROLE-001`、`AUTH-003` 和
最小上下文中的认识论授权。

最小修复边界：

1. `_input` 接受显式 usage；作者和 reviewer 的原始 `source_table` 使用 `claim_evidence`；作者输出在
   reviewer 中仍可作为 `prior_signal`/精确 review subject，不要把所有端口机械改为 claim evidence。
2. 在真实物化 assignment 中断言两类端口的用途正确，并通过真实 submit 验证来源绑定。
3. 不要为盲插件新增资格、cohort、approval 或 Evidence 实体；修复只是纠正现有输入端口的科学角色。

## 3. 已确认正确的部分

### 3.1 `RuntimeOperationProjection` 没有形成第二目录或第二授权

当前实现满足以下事实：

- `CompiledCatalog.runtime_projection(operation_id)` 每次先调用唯一 `operation(operation_id)`，再对该
  `CompiledOperation` 临时投影；
- `CompiledCatalog.__slots__` 没有 runtime projection 映射，投影不缓存、不持久化、不注册、不排序；
- `inputs`、`outputs` 和 `permission_template` 直接引用原 compiled 对象中的不可变值，Operation digest
  仍是唯一完整合同身份；
- reviewer edge 从同一个 `ReviewSpec` 去除 approval 后派生，人工合同另行派生；guard 和 cohort 只是
  同一 spec 的确定性摘要；Effect 引用来自同一 executor；
- 对当前 core/general/curve/TCAD 共 45 个 Operation 独立遍历，12 条 review、4 个人工合同、15 组
  guard、12 组 cohort 和 1 个 Effect 的投影均与原 `CompiledOperation` 逐项一致；
- 相对 L0，8 个 `operations` 源文件总量为 2215 行，新增投影没有引入运行模块、数据库表、MCP 入口、
  preflight 或 invoke。

所以该值对象目前是无状态的派生视图，不是第二事实权威。L2 只能从当前 catalog 现算它并以
`operation_digest` 绑定 Run；不得允许调用者提交或持久化一份 projection 来替代目录。

### 3.2 可选边界的分离方向基本正确

- reviewer edge 与人工 approval 已分离，既有 reviewer+approval 组合不会把人工决定混进审查边；
- ordinary blind Operation 的 guard、cohort、human decision 和 Effect 均为空；
- guard 使用完整限定组件名，不按插件或领域名分支；
- projection 没有新建 qualification、Decision 或 Effect 状态。

当前 `policy_qualification_cohorts` 只是 cohort 名称摘要，并不是计划中的完整 `PromotionPolicy`；
`policy_effect_component` 对 Effect 又与 `executor_component` 重合。因为二者尚无生产消费者且每次从
唯一合同现算，本轮不把这两个冗余视为第二授权。但 L2 不得据此自行实现准入，L5 也不能把 cohort
名称摘要冒充完整资格策略；若没有真实消费者，应直接删除而不是再增加策略实体。

### 3.3 外置插件和 clean wheel 边界真实

- wheel 只有一个 `scidiscovery.plugins` entry point；core、UI、调度器、roles、deploy 和产品插件中
  没有 `blind_csv` 名称分支；
- fixture wheel 从仓库测试目录单独复制、构建和安装；probe 移除 `PYTHONPATH`，将工作目录置于仓库
  外，并断言 core 和 blind plugin 都来自 venv prefix；
- 插件定义 13 个自有组件、两个 Operation；每个 Operation 可达 14 个编译组件，分别复用 builtin/
  general_science 的 6 个公共组件；作者与 reviewer 使用不同 agent 组件，目录编译会拒绝不独立或
  Schema 不兼容的 review edge；
- core、UI 和部署未为 CSV 添加 Schema、renderer、scheduler 指令或 adapter。

这些证据证明“一次入口”和 clean-wheel 发现成立，但不消除第 2.1 节真实 Worker 路径失败。

## 4. 接入成本与奥卡姆判断

证据中的“注册文件 198 行”没有覆盖全部注册胶水。更诚实的统计是：

| 文件 | 物理行 | 非空非注释行 | 判定 |
| --- | ---: | ---: | --- |
| `plugin.py` | 198 | 178 | Operation/组件/提示和注册 |
| `worker_tool.py` | 33 | 21 | 领域工具 adapter 与工具注册，不应全部冒充算法 |
| `__init__.py` | 5 | 3 | 包导出胶水 |
| `pyproject.toml` | 17 | 14 | wheel 与 entry point 胶水 |
| 合计 | 253 | 216 | 不含 `contracts.py` 的领域模型和算法 |

按能排除空行、注释的有效行口径，注册与胶水为 216 行，仍低于 250 行；按物理行则为 253 行，仅高
3 行。该差异不说明架构失败，但证据不应只报 198 行。第一次接入也不是只有 5 个文件：除 5 个插件
文件外，还修改/新增了测试文件、pytest 路径和安装 fixture 接线，实际测试型接入涉及 8 个领域相关
路径；这些额外路径是验证设施，不是产品注册表。

总体上插件没有重复 codec、workspace、文件工具、guard、资格、人工审批或 UI projector，接入规模
符合轻量目标。真正不符合奥卡姆的是插件额外写入一个已有通用工具审计可以推导的领域 activity；
应删除该事实，而不是扩建核心注册机制。

## 5. L0 防腐与回归证据

本轮在串行、低内存条件下执行：

1. `pytest -q tests/operations/test_l1_minimal_runtime_projection.py`：
   `5 passed in 35.59s`；这同时说明现有测试会在真实 Worker 失败时产生假阳性。
2. `pytest -q tests/operations/test_l0_lifecycle_contract.py
   tests/operations/test_worker_exact_dispatch.py`：`21 passed in 10.83s`；生命周期单一投影、精确绑定和
   三个真实 daemon 恢复窗口未退化。
3. 对 45 个产品 Operation 的五类可选投影逐项检查：通过。
4. `git diff --check`：通过。
5. 独立真实 Root/Task/Worker 调用：在 `worker_csv_summarize` 失败，详见阻断 2.1。

候选记录的 `104 passed` 和非 live Operation `299 passed` 本轮没有重复运行；阻断已由更接近生产的
短路径稳定复现，继续重复大集合不会改变结论。没有运行真实 Codex、浏览器或 TCAD solver；它们不是
L1 完成门，真实 Codex 属于 L2。

## 6. 33 项约束和总体目标判断

在投影本身上，`AUTH-001/003`、`ROLE-002`、`PLG-001/002`、`TOP-001/002` 和 `MIG-002` 的方向未
退化：目录仍唯一，投影无状态，插件没有领域分支，L0 恢复证据仍通过。

但是当前盲插件实际运行失败，意味着插件扩展只能在绕过控制面的直接函数测试中成立；若通过增加核心
activity 白名单修复，就会重新形成分散注册表。CSV usage 冲突又使模型不能在遵守共同证据规则的
同时完成科学观察。因此 L1 尚未证明“轻量、低成本、可扩展通用科学 Agent”，也不能作为 L2 最小
Run 的可靠输入。

## 7. 非阻断改进项

1. `OPERATION_AGENT_PREAMBLE` 仍写“claim、materialize”以及复数的 validation/finalization tools，
   而 L0 对外已收敛为 open/heartbeat/submit。L1 不启动真实 Codex，因此不单列阻断；进入 L2 前必须
   将模型可见文案改为一次 open 和一次 submit，避免 Agent 寻找已删除工具。
2. L1 证据应把“工具 handler 可直接调用”“真实 Worker Router 可调用”“真实 Codex Agent 可使用”
   分成三个层级。当前只证明第一层，第三层属于 L2，不能继续用“可调用”笼统表述。
3. 下一轮把接入成本固定为非空非注释行，并同时列物理行与首次接入总路径数；不要通过移动文件改变
   口径。

## 8. 最终结论与允许的下一步

**L1 不通过，不放行 L2，更不授权 L3—L6。**

只允许在上述最小边界内返修盲插件和测试：删除冗余领域 activity、纠正 CSV input usage，并通过真实
Root/Task/Worker 作者提交和 reviewer 绑定测试。不得借此修改核心 activity 白名单、增加新注册表、
提前实现 RunService/LocalTrustedBackend、扩建 qualification/Policy 类型或改写 L0 Hardened 恢复。
返修后需重新独立复审。
