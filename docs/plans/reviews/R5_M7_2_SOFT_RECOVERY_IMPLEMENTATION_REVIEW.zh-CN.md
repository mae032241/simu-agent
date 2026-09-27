# R5-M7.2 默认软隔离与恢复闭包实现独立审查

日期：2026-09-02  
审查范围：默认 Local Codex 能力投影、可选 Hardened 投影、Run 恢复总次数、恢复功能性金丝雀、真实
Codex 恢复测试脚本与相关聚焦回归  
审查方式：只读跨边界代码追踪、简化性审查、聚焦测试；未修改生产代码和测试，未启动真实 Codex  
结论：**PASS；阻断项 0。允许在全新持久证据根上进入一次真实 Codex 恢复纵向测试。**

本结论不等于 M7.2 第 5 项已经关闭。真实恢复 Run 仍必须同时满足草稿标记、Schema 常量、领域工具
重验、首次提交成功和恢复次数上限五项机器断言，随后再做独立终审。

## 1. 总体判断

本轮实现以最小改动关闭了上次终审的两个阻断项，没有增加文件读取 MCP、读取收据、恢复实体、恢复
状态机或后台守护进程：

1. 默认 Local 后端把任务内普通文件、代码和图像能力定义为后端基线；Operation 仍只注册领域工具，
   正式结果仍经唯一 `worker_submit_result` 进入封存、Schema、上下文和 Artifact 登记门；
2. 既有 `LimitsSpec.max_attempts` 被直接用作同一恢复根及全部后代的总 Run 数上限；预检与实际调度
   复用同一规则，实际写入在 SQLite 写事务内复核；
3. 测试夹具以互相独立的随机草稿标记和 Schema 必填常量，分别排除“只从原输入重做”和“靠提交
   拒绝反推格式”两种更简单解释；
4. 现有 Hardened 后端仍可显式编译和运行其支持的 Operation，且不会被默认 Local 路径导入为第二
   运行主干。

设计符合当前的奥卡姆剃刀边界：新增的是一个已有字段的消费者和两个测试金丝雀，不是新的治理
模型。默认 Local 的强文件/网络隔离仍只是软边界；这与架构已公开保留的 `SEC-002 known_issue`
一致，不能在后续报告中被扩大为平台级强沙箱。

## 2. Local 与 Hardened 能力边界

### 2.1 默认 Local

`src/scidiscovery/platforms/codex.py` 的 `_operation_toml()` 现在按后端统一生成能力：Local 的
`shell_tool`、`unified_exec` 和 `view_image` 均为真，`web_search` 为 `disabled`。对应的
`_local_native_tool_instruction()` 明确要求先打开唯一 Run assignment，以返回的工作区作为唯一文件
根；允许读取 assignment、Schema、显式输入和恢复草稿，并只在声明的输出/领域编辑路径写入。

这不是只为 CSV 恢复特设的分支。`initialize()` 遍历启动期唯一编译目录中的全部可运行 Agent
Operation，`validate_installation_profile()` 又以同一目录逐项复算每个生成角色的能力、唯一 Worker
MCP 和工具投影。`tests/artifact_agent/test_platform_configuration.py` 对所有 Local Agent profile
循环断言三项原生能力开启、网络搜索关闭、只有精确 Operation Worker MCP；
`tests/operations/test_l2_run_invariants.py` 还从实际盲 CSV Operation 的生成 profile 和 Worker router
交叉验证工具集合及 Local 原生写入提示。

服务端边界没有随软隔离一起放松。`LocalWorkerMCPRouter` 仍只注册三项生命周期工具和当前编译
Operation 的领域工具；`RunService.submit()` 仍执行封存、输出 Schema/上下文校验、候选摘要固定、
Artifact 登记和完成比较交换。聚焦测试继续验证宿主路径、秘密文本、未声明二进制和符号链接等内容
不能通过正式发布门。

网络结论需要精确表述：生成 profile 关闭 Codex `web_search`，Operation 默认网络声明仍为 `none`，
角色提示也禁止原生网络和未声明领域工具；但是 Local 被明确设计成提示约束的可信本地软隔离，原生
shell 本身不构成技术性网络沙箱。在标准启动器的 `workspace-write` 沙箱之外，尤其是外层调试沙箱
模式中，不能声称框架从操作系统层阻断了网络。这是已接受的 `SEC-002` 限制，不是本轮新增回归。

### 2.2 可选 Hardened

同一 `_operation_toml()` 对 Hardened 继续关闭 shell、统一执行、图像和网络搜索，选择
`mcp_hardened_worker` 及其服务端文件工具；`HardenedWorkerBackend.supports_operation()` 仍会在运行
前拒绝需要原生能力的 Operation。`test_codex_hardened_profile_remains_explicitly_compilable`、
`test_l5_hardened_run_backend.py` 的同 Run 完成、并发所有者/租约恢复和独立 stdio 恢复用例均通过。
因此本次默认能力调整没有把 Hardened 偷换成 Local，也没有要求为了 M7 完成而扩建 Hardened。

## 3. `max_attempts` 的语义、唯一权威与并发

`src/scidiscovery/operation_declaration.py` 只把 `max_attempts` 暴露给现有 Agent Operation 构造器并写入
既有 `LimitsSpec`；盲 CSV 作者显式设为 2，语义是“根 Run 加全部恢复后代最多两个 Run”，即允许
一次恢复。

唯一恢复判断位于 `RunService._validate_resume()`：

- 先由 `_recovery_digest()` 检查源 Run 已失败且有草稿、Operation digest 相同、完整有序输入引用
  相同；
- 再由 `_recovery_root_id()` 沿 `resume_from_run_id` 找到根，并检测祖先环；
- 最后用递归 CTE 从根向全部后代计数，而不是只看当前深度或单一父子链；计数达到
  `max_attempts` 即拒绝。

Root `operation_preflight` 通过公开的 `validate_resume()` 调用同一内部规则；它只是纯读投影。真正
`RunService.schedule()` 不信任预检，在冻结实际输入之后，于 `BEGIN IMMEDIATE` 写事务内再次调用
`_validate_resume()`，通过后才插入 Run。SQLite 写锁使两个并发调用不能同时看到同一个旧计数后都
写入；后进入事务者会看到先前已经提交的兄弟 Run。Root 的进程内创建锁是附加串行化，不是正确性
唯一来源。

`test_status_is_pure_and_failure_recovery_is_explicit` 已覆盖：根失败后第一次恢复成功；恢复 Run 再失败；
重新打开 runtime 后，从根和子 Run 发起的第三次 preflight 与 invoke 均拒绝；Run 列表不变且没有
新绑定。虽然当前自动化没有单独用两个线程制造兄弟恢复竞争，但事务内重新计数和唯一写锁已给出
直接实现证据，顺序兄弟/子链及重启负例覆盖了同一最终状态。该缺口不阻止一次串行真实 Codex 纵向
测试；若以后更换非 SQLite 存储，必须补储存后端级竞争测试，不能沿用此推论。

## 4. 恢复金丝雀的可识别性

### 4.1 草稿读取/使用

`tests/fixtures/m7_recovery_crash_worker.py` 在故障进程内用 `secrets.token_hex()` 创建每次运行唯一的
`recovery-draft-only:*` 标记，只把明文写入未提交草稿的 handoff assumptions；外部故障收据只保存
该标记的 SHA-256。标记不能由 CSV 输入、领域汇总工具或初始 instruction 推出。

`RunService` 将候选转为只读 recovery draft，新 assignment 明确要求先读草稿、把它仅作为可编辑
起点且重新验证完整结果。`scripts/l3_live_review_probe.py` 从持久草稿清单复算文件摘要和只读状态，并
要求完成 Run 的封存 signal 保留同一明文标记。因此，一个只对相同 CSV 从头重做、没有读取任何草稿
副本的 Agent 无法满足该断言。草稿本身继续不是 Artifact、证据或父引用。

### 4.2 Schema 首读与首次提交

测试专用 `CsvObservation` 增加必填 Literal 常量；常量不出现在 Operation prompt、instruction、CSV
输入或故障草稿。恢复脚本从实际物化的 `schema/result.schema.json` 读取 const，要求封存 payload
包含相同值，并直接查询 `run_activity` 确认 `output_rejected == 0`。因此成功不能由“先提交错误结果，
再从拒绝诊断猜字段”解释，且能检验此前关闭文件能力导致 Schema 不可达的共性问题。

在当前软隔离模型下，静态常量也存在于测试插件的已安装 Python 源码中，框架没有技术手段阻止恶意
Agent 越出任务目录搜索源码。因此后续只能作如下准确主张：遵循编译提示和声明上下文的 Agent 已从
模型可见任务合同取得该值；不能把金丝雀扩大为操作系统级来源证明。随机草稿标记不受这个静态常量
限制，两者组合足以在当前可信本地验收口径下排除普通的“同输入重做”。这仍是 `SEC-002` 的已知
限制，不需要为本轮增加读取收据或动态 Schema 实体。

### 4.3 领域重验与总次数

恢复 Run 必须在持久 `run_activity` 中出现 `worker_csv_summarize` 成功，证明新 Agent 没有把失败草稿
直接晋级为结果；最终 Artifact 又必须只有原始 CSV 的精确输入父引用。完成后，脚本从失败根再执行
超限 preflight 与 invoke，要求两者拒绝、Run 列表不变且无绑定。这些断言与草稿标记、Schema 常量
互相独立，没有单个伪成功路径可以同时替代全部事实。

## 5. 奥卡姆剃刀与 33 项约束

本轮没有新增数据库表、Run 状态、Root 工具、Worker 生命周期工具、Operation 类型、恢复服务或插件
注册入口。恢复边界仍由 `RunService` 和现有 `runs.resume_from_run_id` 单独拥有；测试能力只存在于
盲 CSV fixture。符合：

- 单一编译目录和单一 Operation 调用入口；
- Agent 只拥有科学内容，控制层只做精确绑定、封存、校验和生命周期；
- 文件式显式输入/封存输出，草稿不是 Agent 间聊天；
- 原始 Artifact、审查、人工审批和 Effect 硬边界不因 Local 软隔离放松；
- `RES-002` 的恢复次数现在由已有声明字段得到控制，且重启后仍生效。

仍有两项非阻断设计债务：

1. `NativeToolPolicy.shell` 仍保留旧的“每 Operation 最低后端要求”含义，而不再表示 Local 的普通文件/
   代码权限真值；默认 Local 会为声明 `none` 的 Operation 也打开任务内能力。当前唯一生成路径和文档
   已明确这一点，不造成双重授权，但字段名容易误导。应在后续常规简化中重命名、降为后端兼容要求
   或删除，不能为 M7 再增一层权限状态。
2. 上次终审记录的只读 quarantine 候选残留尚未处理。它不进入 Artifact、父链或新 Run 授权，也不
   影响本轮两个阻断项；继续按低优先级存储清理债务记录，不应在 M7.2 以补丁方式扩展恢复状态机。

## 6. 独立检查结果

独立执行：

```text
PYTHONPATH=src python -m pytest -q -p no:cacheprovider \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_l5_hardened_run_backend.py \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/operations/test_independent_codex_worker_launcher.py
```

结果：`62 passed in 58.55s`。

另外完成：

- 对本轮生产文件、测试脚本和架构文件执行 Python 编译检查：通过；
- 对本轮相关已跟踪差异执行 `git diff --check`：通过；
- 静态追踪实际入口 `operation_invoke -> RunService.schedule -> LocalTrustedBackend.prepare ->
  LocalWorkerMCPRouter -> RunService.submit -> Artifact/current`：没有发现旁路；
- 静态追踪生成 profile、父配置中继承 Worker MCP、Local/Hardened router 工具投影：同一编译目录和
  精确 Operation digest 保持一致。

这 62 项聚焦测试足以进入真实 Codex 测试，因为它们覆盖本轮改动两侧的实际生产入口、重启、
Hardened 非退化、安装 profile 和正式发布门；但不能替代真实模型是否按提示读取草稿/Schema 的最终
观察，也不能替代 M7.5 全仓回归。

## 7. 放行边界

本轮独立结论为：

- 默认 Local 软隔离实现：**PASS**；
- Hardened 非退化：**PASS**；
- 恢复根全后代总次数及重启拒绝：**PASS**；
- 功能性草稿/Schema/领域工具测试设计：**PASS，可进入实跑**；
- 新控制实体或针对性恢复补丁：**未发现**；
- M7.2 第 5 项：**尚未关闭，等待真实 Codex 机器证据和独立终审**；
- M7、R5-M：**尚未关闭**。

