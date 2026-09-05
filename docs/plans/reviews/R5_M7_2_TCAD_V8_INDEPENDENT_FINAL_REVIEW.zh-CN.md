# R5-M7.2 TCAD v8 独立终审

日期：2026-09-02  
审查者：未参与 v8 实现的独立审查者  
候选根：`deliverables/m7-live-tcad-receipt-v8-20260902-01/`  
结论：**PASS**

## 1. 精确结论

TCAD v8 候选真实关闭了 v7 的阻断：修订后的同一份最终源码先完成了合格
`preflight`，随后以 Sentaurus Device R-2020.09 的 `-i` 参数完成了独立
`initialization`；二者没有被后续源码修改失效。排队最终审查前的准入与最终状态复算都会要求
模式、配置、终态、退出码、诊断层和最终源码摘要同时匹配，因此普通预检、任意调试成功或旧源码
报告均不能冒充本次初始化证明。

四个 Run 的控制终态、封存 Artifact、精确父链、启动收据和最终审查对象相互一致。最终审查者读取的
`project` 字节与封存修订 Artifact 完全相同，其新 verdict 为 `pass`，且旧 `revise` 审查没有被
继承或改写。

本结论允许且只允许关闭：

- M7.2 第 2 项“TCAD 作者真实调用领域调试并受控提交”；
- M7.2 第 3 项“修订对象接受精确新审查，旧审查不继承”。

本结论不关闭 M7.2 第 4 项 Effect/UI/执行链、第 5 项失败或超时恢复，也不表示 M7.2、M7 或 R5-M
整体完成；更不证明真实 Sentaurus 完整求解、器件物理正确性或科学结论成立。

## 2. 阻断项

无。

## 3. v7 缺陷是否真实关闭

### 3.1 最终源码、预检和初始化具有同一绑定

从封存修订 Artifact 独立重算 `files` 源码树摘要，结果为：

```text
97e8ff7a4f8127189037b8baf15dba34d621986d9b236bce545f7e8b00df8a82
```

控制生成的两个报告分别声明：

```text
preflight      tcad.project-preflight.v1       97e8ff7a...  qualified=true
initialization tcad.project-initialization.v1  97e8ff7a...  qualified=true
```

两个实际提交的调试归档摘要均为：

```text
e977c96f53c898017fec4dc68aa82790ce2903dc84f2009026f69197ee940b88
```

逐成员复算还确认两份归档中的 `device.tdr`、`init.cmd` 和 `main.cmd` 字节完全一致。对应 Job 参数
分别为：

```text
preflight:      ["-P", "main.cmd"]
initialization: ["-i", "init.cmd"]
```

时间顺序为：最终 `project.json` 在 18:00:55 后不再修改，预检报告生成于 18:01:02，初始化报告生成于
18:01:05，Run 于 18:01:09 完成受控提交。修订 Run 的活动账本也在最终提交前记录了两次成功的
`worker_tcad_debug_run`。因此这不是先调试旧稿、再修改后提交的 v6/v7 型假阳性。

### 3.2 `-i` 语义已在领域适配器中修正

`debug_adapter.py` 将 R-2020.09 SDevice 的 `initialization` 映射为
`("-i", entrypoint)`，逆向模式识别也只把 SDevice `-i` 解释为 `initialization`；原先将其误称为
`smoke` 的映射已删除。该语义与冻结的 SDevice 合同一致：`-P` 是参数/预检模式，`-i` 是初始解
模式，二者都只是有界开发诊断，不构成完整科学执行。

### 3.3 准入门不会用较弱证据替代初始化

`l4_live_tcad_revision_probe.py` 的排队审查路径与最终状态路径均调用同一严格判定，要求：

- `profile` 精确等于 `tcad.project-initialization.v1`；
- `mode` 精确等于 `initialization`；
- `source_tree_sha256` 精确等于封存项目的合格预检源码摘要；
- 终态为 `succeeded`、退出码为 0、诊断层为 `complete`、`qualified` 为真。

聚焦负例已验证预检报告不能冒充初始化报告，旧源码摘要也不能复用。单独存在
`tool_succeeded:worker_tcad_debug_run` 不足以通过该门。

## 4. Run、Artifact 与独立审查链

持久 `runs.sqlite3` 中恰有四个目标 Run，均为 `completed`：

| 行为 | Operation | 封存结果 |
|---|---|---|
| 初始作者 | `tcad.deck.author.initial.v1` | 初始 `tcad_project` |
| 初始审查 | `tcad.deck.review.v1` | 新 `tcad_project_review`，verdict=`revise` |
| 修订作者 | `tcad.deck.author.revise.v1` | 新 `tcad_project` |
| 修订审查 | `tcad.deck.review.v1` | 新 `tcad_project_review`，verdict=`pass` |

修订 Artifact 的直接父项包含：初始项目、精确 `revise` 审查、真实 HDF5/TDR 网格、执行能力和实验
计划。新审查 Artifact 的第一个父项是修订 Artifact；最终 reviewer 工作区中的只读
`inputs/project.json` 与该封存修订 Artifact 逐字节相同。封存 review payload 也与最终 reviewer
提交 envelope 中的 payload 相同。

旧审查只绑定初始项目且 verdict 为 `revise`。最终新审查由另一个新 Run 产生，绑定修订项目且
verdict 为 `pass`，不存在修改旧 verdict、把旧审查当作新项目通过证明，或跨 revision 继承资格的
路径。

最终审查的科学范围与工程目标相符：它只判断最小 SDevice 工程是否具有已声明的原生网格输入、直接
入口、初始化入口、最小求解顺序和原始输出，不把开发调试结果解释为物理结论。项目计划明确
`study_kind=engineering` 且声明不作物理结论。

## 5. 启动器和复杂度审查

四份启动收据具有四个不同 invocation id，时间窗口覆盖对应 Run，退出码均为 0，声明的单进程地址
空间上限和整棵进程树聚合上限均为 4096 MiB；记录峰值约为 285—376 MiB，未触发内存熔断。角色、
精确 Worker MCP、工具集合和生成 profile 的摘要均可从当前冻结配置复算。

当前启动器只承担本次独立 Codex 测试的承载职责：读取精确生成 profile、只启用目标 Worker MCP、
启动一个临时 Codex 进程、施加内存上限、清理后代并写最小启动收据。它不解释 TCAD 调试结果、不
代理 Worker 工具、不判定 Run 完成、不决定 Artifact 接受，也没有 Hook、原生命令白名单、提交门或
独立生命周期。因此它没有重新成为第二运行时或第二权限协议。

v7 的生产修正留在 TCAD 插件拥有的调试适配器、现有本地调试服务与 M7 验收探针内：

- 未修改 Root 路由；
- 未增加插件名或 Schema 名中央分支；
- 未增加数据库表、注册表、current、Run 状态或恢复协议；
- 初始化报告复用现有 Run 工作区与领域调试工具；
- `OperationSpec`、Run、Artifact 和独立审查的既有权威没有改变。

从奥卡姆剃刀角度，本次修复解决的是一个确切的模式语义和证据绑定缺口，没有为一次验收引入新的
通用实体。实现符合 `PLG-001`、`ROLE-001/002`、`IMM-002` 和单一控制权威的方向，也没有掩盖
`SEC-002` 仍为已知问题的事实。

## 6. 独立复算与测试

为避免修改正式候选，先将候选复制到 `/tmp`，再对临时副本运行最终状态复算。输出的 12 项布尔
证据全部为真，verdict 为 `pass`，临时输出与正式 `final-evidence.json` 的 SHA-256 相同：

```text
c2bddc3f59a1da3ec764337f24e98e8afed3fb72f4897ef3e8ec7bee19040399
```

聚焦回归命令：

```text
python -m pytest -q \
  tests/operations/test_l4_live_tcad_revision_evidence.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_independent_codex_worker_launcher.py
```

结果：

```text
22 passed in 3.65s
```

以下检查也通过：

```text
python -m py_compile \
  plugins/tcad_artifact/tcad_artifact/debug_adapter.py \
  plugins/tcad_artifact/tcad_artifact/local_debug_service.py \
  scripts/l4_live_tcad_revision_probe.py \
  scripts/run_compiled_codex_worker.py \
  scripts/compiled_worker_process_guard.py

git diff --check
```

没有启动新的真实 Codex、真实 Sentaurus 或全量测试；这些都不是本次窄终审的必要证据。

## 7. 非阻断限制

### N1：本轮是确定性传输夹具，不是实际求解器资格

领域调试链真实经过注册的 `worker_tcad_debug_run`、TCAD 打包和执行适配边界，并生成了正确的
`-P`/`-i` Job；但底层 transport 是 M7 的确定性夹具，不是许可证环境中的真实 Sentaurus 进程。
这足以证明 M7.2 第 2、3 项要求的 Agent/领域工具/受控提交/独立审查链，不足以证明真实求解器语法、
初始化、收敛或物理正确性。后续报告不得扩大表述。

### N2：初始化证明依赖保留的 Run 工作区

预检摘要进入了封存项目 Artifact；初始化报告目前是控制生成、只读并与 Run 绑定的持久工作区文件，
没有另建 Artifact 或新控制实体。当前候选根完整保留该工作区、Job、归档和执行结果，足以复算本次
门禁。若未来允许清理完成 Run 的工作区，应先明确保留这类验收证明的最小策略；本项不要求在 M7.2
内增加新的持久化系统。

### N3：修订 handoff 的后续动作文字已滞后

封存修订结果的 `handoff.next_actions` 仍写着运行预检/初始化并提交审查，而这些动作随后已经完成。
控制面没有依赖这段文字推进状态，实际排队由精确报告和 Run 状态决定，因此不影响本轮资格；后续可
把此类 handoff 写成条件式“合格后进入独立审查”，避免在调试后因改写 handoff 又使证明失效。

## 8. 最终放行边界

**PASS。阻断项 0。**

允许父任务将 M7.2 第 2、3 项标记为完成，并继续第 4 项。不得据此标记 M7.2、M7 或 R5-M 完成，
也不得把本报告当作真实 Sentaurus 求解或科学结论的资格证明。
