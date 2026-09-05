# R5-L2 最小本地 Run 实现第三轮独立复审

日期：2026-09-01  
审查者：`r5s_s0_independent_review`（未参与实现）  
结论：**通过（PASS）**

## 1. 审查范围与结论边界

本轮基于当前工作树重新审查，不继承实现者结论，也不以测试数量代替跨边界语义核验。重点复核第二轮
报告的 B1、B2、B3、B5、B7，并回归 B4、B6、B8、33 项架构约束、奥卡姆边界及第二权威风险。

当前候选关键摘要为：

```text
计划                         e74c6032aa7eafc01915d2922957cc64efc2c040bb89a0db64f1abebad9d3a76
L2 证据                      ebc17d4b513b1ce88b3acc66921812a7a4909981e6b561c657545f39041fe2d8
RunService                   1d0e77e9e73081770f24c35a36aa82d0ca68f694ee92c71b25b2b43ca313e0c2
RunCurrentGuard              585431894d766e4a7c080dc9f33472d4e0cb8ac7213cb6f8be6350c1996751ae
LocalTrustedBackend          dfa87c78721a9e3de71e8ec7a6a82870a0515d77696774ecdc40c4c3ac7c71da
Run records                  686079c872e6cadb035c41357eabc269aadd218f1035709d315842d73ed33a47
Scheduler bindings           211b076500d603dad71db18f70e2f0a92456682314b57275128504f754baf65e
Local Worker MCP             051ac1317d944a0b9930e13a35218a6bd6a1f31867b96970637bbff434abddbc
Local PDF tool               3a7a3f6ba0940fc2663a9f4e5741917dec0dcd84b626b8bc43dd8a0a61bd7dd8
L2 invariant tests           1874df901efc7635c8139c56c6a6d1d8cba0c02f33e4d187243b87cb1f391ba8
direct probe harness         7697aeb16b37218be3f318437b354cf4e0841212510d0dfd64b9a1653cc7ac72
direct final evidence        8cec30907d9e94d4fade6cd6171b53ab5d3085e2924cd25ee52bc93b9c3e266d
```

审查期间发现并打回了一项窄的崩溃原子性缺口：完成事务跨
`runs.sqlite3` 与 `scheduler-bindings.sqlite3`，而后者曾使用 WAL。[SQLite 官方 ATTACH 合同](https://www.sqlite.org/lang_attach.html)明确说明，WAL
下多个 attached 数据库只保证单库原子，不保证多库作为整体原子。候选随后没有新增状态或存储层，
而是在两个既有服务启动时统一请求并验证 `journal_mode=DELETE`，并增加“先把两个库预置为 WAL，
重开后归一为 DELETE”的正向测试。该问题在本报告冻结前已经闭合。

本报告只判定 L2 当前候选。它不把 L3—L6、TCAD 纵向闭环、动态自定义角色加载或生产级原生工具隔离
视为已经完成。

## 2. 独立测试

所有命令串行运行，虚拟内存上限为 7 GiB。

```text
PYTHONPATH=src:tests/fixtures/plugins/blind_csv_operation_plugin \
python -m pytest -q \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_l2_run_invariants.py \
  tests/artifact_agent/test_platform_configuration.py

21 passed in 5.23s
```

在两库日志修复后重新合并执行 L0/L2、平台、精确 dispatch、Hardened 防腐、runtime plugin gate 和部署
聚焦集合：

```text
86 passed in 19.83s
```

其中四个承重正例（Root current CAS、completed 输出发布与查询纯读、两个真实进程失败隔离窗口、全部
当前 L2 已安装工具及 Local PDF handler）单独复跑为：

```text
4 passed in 2.23s
```

`git diff --check` 通过。实现方另有 `314 passed` 的非 live Operation 全集证据；本审查没有用该数字
替代上述语义检查。

## 3. B1—B8 复核结果

| 项 | 第三轮判断 | 证据与结论 |
| --- | --- | --- |
| B1 生产 current CAS | **闭合** | Root DTO 强制显式提交可空的预期对象；`None` 表示期望空 head，不能与“未传预期值”混淆；Root 删除 latest/qualification 门后，把目标精确 ref 和预期精确 ref 交给唯一 current 权威 |
| B2 候选、收据与失败恢复 | **闭合** | accepted candidate、Artifact 幂等键和完成收据保持原主干；failed 后可继续同一 backend-private 隔离，active→quarantine 和 quarantine→recovery 两个进程退出窗口均可重放 |
| B3 completed 与查询纯读 | **闭合** | 输出绑定与 `completed` 在同一 attached 事务内提交；两个参与库均强制并验证 DELETE journal；Root `status/list` 不再写绑定，completed 前已可解析输出 |
| B4 Local/Hardened 边界 | **未退化** | 默认 Local 只创建 Run；Hardened 仍显式冻结，不伪装为已接入 Run 的可部署默认路径 |
| B5 单一工具投影 | **闭合** | assignment、Codex profile、Router 都从同一 `CompiledOperation` 投影；非原生等价工具没有 Local handler 时目录/preflight 失败关闭；PDF 使用窄 Local handler |
| B6 路径身份 | **未退化** | Worker 路径继续是随机 `workspace_<uuid>`；Run 到目录的关联只保存在 backend-private 哈希绑定中 |
| B7 真实 Agent | **按已批准原型边界闭合** | 新证据确有无父历史的独立通用 worker；它直接启动 exact stdio MCP，调用 open、CSV 工具、submit 并原生写结果；父/bridge 未代调。未冒充动态 `agent_type` 已热加载，也未宣称 SEC-002 已关闭 |
| B8 发布扫描 | **未退化** | 初次 seal 与 accepted candidate 重读仍经过同一有界发布扫描，拒绝机器路径、明显秘密、未声明二进制和非法文本 |

## 4. 承重语义核验

### 4.1 current 是独立、显式、精确的 CAS head

- `ScientificCurrentSelectInput.expected_artifact_name` 是必传的可空字段；独立模型探针验证省略字段被
  Pydantic 拒绝，而显式 `null` 被接受。首次设置因此不是无条件写。
- `scientific_current_select` 只核对目标 `kind`，再解析目标和预期对象的精确 Artifact ref；路径中不再
  检查 latest 或 `scientific_claim_admissible`。
- `SchedulerBindingService.select_scientific_object` 在 `BEGIN IMMEDIATE` 内读取现 head，并以显式
  `expected_ref` 比较后更新唯一记录。`None` 与内部“不要求 CAS”的 sentinel 不同。
- 未资格的 revision 可以按精确旧 ref 推进 current，陈旧预期值失败；这证明 current 不再隐式代表资格。
- `RunCurrentGuard` 冻结并递归传播的仍是精确 `(kind, logical_name, ArtifactRef)` 锚点；提交事务内重检
  没有被本轮简化绕开。

因此 B1 对 `AUTH-001`、`LIN-002`、`CQRS-002` 的直接问题已经关闭。当前没有引入
`CurrentProposal`、候选表或第二 qualification。

### 4.2 失败隔离能跨真实进程退出窗口重放

`record_failure` 先以 `(state,last_activity_at)` CAS 写 failed；如果进程在后续隔离前退出，再次调用同一
显式命令会进入 `_finish_failed_workspace`，而不是因已 failed 直接跳过恢复。`LocalTrustedBackend`
保留 Run→随机工作区的私有绑定，并采用可确定重访的 quarantine 路径：

1. 原工作区尚在时原子移动到 quarantine；
2. 原目录已不在而 quarantine 在时继续复制同一 accepted candidate；
3. quarantine 已清理但 recovery digest 已存在时重新验证并返回同一草稿；
4. recovery manifest 只在 failed Run 上幂等登记，不成为 Artifact、current 或 evidence。

真实子进程分别在“failed 已提交、调用 discard 前”和“工作区 `os.replace` 后、恢复登记前”以 71/72
退出；新调用恢复后旧工作区消失、草稿摘要稳定、旧 heartbeat 被拒绝，新 Run 只能绑定原 Operation
摘要与精确输入。该修复复用了 failed、候选摘要和 backend-private 目录，没有新增生命周期状态，符合
`RES-002`、`IMM-002` 与奥卡姆边界。

### 4.3 输出发布属于完成命令，查询端到端纯读

Run 创建时已经冻结输出语义名、revision 和请求指纹。提交路径在候选校验、摘要接受和 Artifact 幂等
登记后，由 `_complete` 打开一个写事务：事务内重新检查 current 锚点，通过现有
`SchedulerBindingService.bind_in_connection` 写精确 Artifact 绑定，再 CAS 写 completed、输出 ref、
信号和收据。状态路由只读取冻结的 `output_binding_name`，没有 `_bind` 或其他写操作。

审查中进一步发现：原候选的 scheduler 库为 WAL，不能仅因代码位于一个 `BEGIN/COMMIT` 就声称两个
文件在主机崩溃时整体原子。当前 `RunService` 和 `SchedulerBindingService` 均在初始化时请求
`journal_mode=DELETE` 并检查实际返回值，不满足就启动失败；测试先把两个库都置为 WAL，再证明重开后
均为 DELETE、完成后绑定已存在、随后 `status/list` 前后两个数据库摘要不变。由此 B3 的
`CQRS-001/CQRS-002/AUTH-001` 边界成立。

### 4.4 工具权限来自唯一编译投影

`operation_local_worker_tools` 从 `operation_worker_tools(compiled)` 派生。声明工具只有三种可接受结果：

- 已注册普通/上下文/Local 上下文 handler，进入 Router；
- 属于冻结的 Local 原生等价文件能力，不重复暴露 MCP 文件工具；
- 其余进入 `missing`，目录标为 unavailable，preflight 以
  `runtime_backend_capability_missing` 失败关闭。

assignment、生成 profile 的 `enabled_tools`、正式 stdio Router 都读取同一投影。Router 对缺失 runtime
service 在 open 前失败，不消耗 Run 启动槽。PDF handler 只消费 `OperationToolContext` 的输入媒体、
精确输入路径、工作区和剩余时间，调用有界 `pdftotext` 后把只读 excerpt 放在当前随机工作区；它没有
Task、token、session、Artifact 登记或 current 写接口。

这里没有按 PDF Schema、盲 CSV、TCAD 或角色名加入 Root 分支，也没有第二工具注册表。TCAD debug
service 的 Local 注入和真实 TCAD author/reviewer 仍属于计划 L4，不能用本轮 PDF/CSV 证据提前声称
TCAD 已闭环。

### 4.5 真实 Agent 证据的有效范围

仅接受 `deliverables/l2-direct-agent-probe-20260901/`。旧
`deliverables/l2-live-probe-20260901/` 明确标为桥接代调失败历史，不参与 verdict。

有效证据同时满足：

- 当前协作树存在 `/root/l2_direct_agent_probe` 独立子智能体，完成聊天严格为“已完成受控提交。”；
- 生成 profile 绑定精确 Operation digest、唯一 Worker server 和四个工具；
- 持久 Run activity 只有 `tool_succeeded:worker_csv_summarize`，随后 Run completed；
- 封存结果包含该工具所得的精确 source digest、两行、列名和均值 2.0，并有独立有界解释；
- completed 收据、候选摘要、输出绑定、Artifact 校验和一个精确父链均存在；
- 当前 probe harness 只有 prepare/status，没有启动 MCP、转交工具结果或代 submit 的 bridge 路径。

当前协作运行器确实拒绝热加载新生成的自定义 `agent_type`。按用户已经批准的第一版边界，本次使用
`fork_turns="none"` 的通用 worker 执行生成的精确 profile/MCP 合同。因此它证明“真实子智能体直接
使用原生文件能力和注册领域工具”，不证明“运行器已经动态加载自定义角色”。`SEC-002` 继续是明确
known issue；提示约束没有被写成技术沙箱结论。

## 5. 33 项约束与奥卡姆审查

本轮与 L2 直接相关的约束结论如下：

- `AUTH-001/AUTH-003/ROLE-002`：Artifact、Run 终态、current 和工具授权仍分别只有既有唯一权威；
  backend 与插件工具不登记科学事实。
- `IMM-001/IMM-002`：接受候选和 Artifact 继续按 `Run + digest` 幂等；旧 revision、父链和收据不修改。
- `LIN-002`：声明 `requires_current` 的输入仍冻结并递归检查精确锚点；Root current 更新是显式 CAS。
- `TOP-002`：Local 非原生工具缺少 handler 时 catalog/preflight 失败关闭，不会把不可调用行为报 ready。
- `CQRS-001/CQRS-002`：status/list 纯读；失败、timeout、完成、current 只由显式 CAS 命令推进。
- `PLG-001/PLG-002`：核心没有新增领域名分支；工具实现仍由单一插件入口进入 `CompiledCatalog`。
- `RES-002`：时间、输出、草稿和恢复均有界；失败重放不能换 Operation 或输入。
- `SEC-002`：只在可信本地、无生产凭证和无不可逆副作用的已披露边界内有条件满足；原生工具技术
  隔离仍未完成，状态维持 `known_issue`。

未发现针对盲 CSV 测试加入生产标签、隐藏状态、兼容转发或专用控制分支。新增加的对象均保护已存在
但不可由其他事实推导的边界：`RunCompletionReceipt` 固定完成事实，`CurrentAnchor` 固定递归 stale
依据，`SealedWorkspace/RecoveryDraft` 固定候选与失败草稿字节。两库 DELETE 修复只改变已有存储的
日志合同，没有制造新状态机。当前 `runs.py` 仍偏大，但围绕一个终态权威；此时为行数拆出 Repository/
Manager 会增加跳转和对象，不应作为 L2 阻断。

## 6. 非阻断建议与保留限制

1. **不要扩大 L2 主张。** TCAD runtime service、Deck 物化、8 MiB 工作区和真实 author/reviewer 属于
   L4；Hardened 接 Run 和生产原生工具隔离也仍未完成。
2. **保留动态角色限制。** 后续若协作运行器支持热加载，应再用 `operation_invoke` 返回的真实
   `agent_type` 复验；当前不得把通用 worker 证据改写成动态角色已加载。
3. **观察 DELETE journal 的真实并发代价。** 这是当前最小且正确的跨库原子方案；只有真实并发数据
   证明成为瓶颈时，再考虑把 Run 与目录共置一个控制库。不要现在新增 outbox 或双写恢复状态。
4. **Local/Hardened 双 handler 的优先级应在 L4 前明确测试。** 当前有 Local handler 的 PDF 路径正确；
   若未来同一工具同时声明通用 contextual handler 与 Local 专用 handler，应以一个编译规则明确选择，
   不要在 Router 再建分发表。
5. 旧无效 probe 可以保留为失败历史，但所有汇总继续只引用 direct probe，避免读者把桥接结果计入验收。

## 7. 最终判定

**PASS。R5-L2 当前实现满足本阶段完成门。**

第二轮五个阻断均已在现有 Root 命令、Run 事务、backend-private 映射和单一工具投影内闭合；审查中
新增发现的跨附加库 WAL 原子性问题也已用两库 DELETE + 启动时失败关闭的最小方案修复。未发现第二
current、第二工具注册表、第二生命周期、领域特判或为测试增加的生产状态。

本结论不授权把 L3—L6、TCAD 闭环、Hardened 生产接入、动态角色加载或 `SEC-002` 技术隔离标为完成。
