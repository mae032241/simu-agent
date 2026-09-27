# R5-M7.2 通用独立 Codex Exec 闭环独立审查

- 日期：2026-09-02
- 审查者：未参与本轮实现、运行提交或科学内容编写的独立代码/架构审查者
- 文档角色：绑定精确候选、运行状态与证据集的当前审计账本；不是新的架构规范或运行入口
- 结论：**PASS**
- 阻断项：**0**
- 阶段门：**只放行 M7.2 的下一条 TCAD 作者→领域调试→独立 Deck 审查子链；不宣称 M7.2、M7 或 R5-M 完成。**

## 1. 结论先行

当前通用候选 `author_exec8` 与 `reviewer_exec4` 通过最终独立审查。两条 Run 均由不同的短寿命
`codex exec` invocation 打开精确 assignment 并经各自唯一 Worker MCP 提交；Root SQLite Run、工具
活动、密封 Artifact、精确 review subject/parent 关系和两份原子 launcher receipt 相互闭合。

本结论不依赖子进程聊天，也不把 launcher、stdio audit proxy 或 receipt 提升为第二套 Run/Artifact
状态权威。当前通用闭环只关闭 M7.2 的一个子项；TCAD、修订、Effect 与恢复纵向回归仍待后续精确
证据。

当前规范范围仍由
[R5-M 主计划](../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md)拥有；运行事实与实现侧说明见
[M7.2 实时证据](../evidence/R5_M7_2_LIVE_AGENT_VERTICAL_EVIDENCE.zh-CN.md)。本报告只拥有下述
精确候选的独立审查结论，不取代两者。

## 2. 精确候选与启动收据

验证根为：

```text
deliverables/m7-live-generic-20260902-01/
```

两条当前 Run 和启动投影如下：

| 项目 | 作者 | 独立审查者 |
|---|---|---|
| Run 语义名 | `author_exec8` | `reviewer_exec4` |
| Run ID | `run_064a52220daa487cb0e572f96fbf8171` | `run_ab61bea119f74b4abf1f72bbaadff5d7` |
| Operation | `blind.csv.observe.v1` | `blind.csv.review.v1` |
| Operation digest | `e5c14175e00d72196761c527740b3c0abc03c77388ec89943969bd15be3c4417` | `995e51d375c6197d3946383c0186570cea6ddecf9ca0cc9d7a54e85617cc2c88` |
| `agent_type` | `op_blind_csv_observe_v1_e5c14175e00d` | `op_blind_csv_review_v1_995e51d375c6` |
| launcher invocation | `4998007de73f4df388bf0e57e7f22ce8` | `5f5fa013493c4a6da5ce231fa5f06fbc` |
| command projection SHA-256 | `b48470863394f723b365624238a77e0bea032a5328cd737655d7692e44166512` | `e92b69fc6b4598803b18e7fdf92b49fd308b9dc2a8961a4fd8c5ccdb3f90d893` |
| profile SHA-256 | `d7b258ac2bfb73312294b3ef16f8747cf9a036c0e96829f8a05991d195a536ac` | `efcb116813c43dac3666018e81292fce60f8914d5b5ae7d1b299991982886b7e` |
| 内存/模式 | `4096 MiB` / externally sandboxed debug | `4096 MiB` / externally sandboxed debug |
| 终态 | `completed` | `completed` |

本审查没有信任 `final-evidence.json` 中的布尔值本身，而是使用 receipt 的 `invocation_id` 重建精确
`.events` 路径和完整 `build_command` 投影，再独立计算 canonical digest。两个 command digest、两个
profile 文件摘要、目标 server、4096 MiB 和沙箱模式均与 receipt 逐项相等。重建命令同时确认：

- `--ephemeral` 与 `--ignore-user-config` 生效；
- `agents.enabled=false`、apps 关闭；
- Root MCP 与全部兄弟 Worker MCP 均禁用，只有目标 Worker server 启用；
- 作者只观察到 `worker_open_assignment`、`worker_csv_summarize`、`worker_submit_result`；
- reviewer 只观察到 `worker_open_assignment`、`worker_submit_result`；
- 两组调用均为各自 Operation 编译允许工具的子集，并含本轮必需调用。

两份 receipt 均为 `0600`、单链接的完整 JSON，目录中没有残留 `.events` 或 `.tmp` 文件。receipt 字段
仅含角色、command/profile 摘要、唯一 invocation、起止时间、退出码、内存/沙箱模式、目标 server
和 Worker 工具名/时间；全文扫描不存在 Run/Artifact 标识、工具参数、工具结果、工作区路径、科学
payload、summary、verdict 或 subject。

## 3. Run、工具活动与密封 Artifact 交叉证据

### 3.1 作者链

作者 receipt 的时间包络为 `03:08:36.750856Z`—`03:10:09.195957Z`；SQLite 中该 Run 从
`03:08:51.571829Z` 进入 running，并在 `03:10:04.415991Z` 完成，严格落在该 invocation 内。

receipt 中 `worker_csv_summarize` 请求时间为 `03:09:08.715316Z`；Run 活动账本在
`03:09:08.722179Z` 记录 `tool_succeeded:worker_csv_summarize`。随后七次 submit 请求对应六条
`output_rejected` 活动和最后一次 completed 提交；拒绝没有从证据中删除或改写。

作者输出为：

```text
author_exec8.output
artifact_id = art_dd990b88a2e34764b805f4e2b2175367
sha256      = 63b94bab3756dc8f4644f1ebb61a3f5408cf073afe9c169bf3adb64f3ca82281
```

独立对 CAS 原始字节执行 SHA-256，结果与 Run output ref、Artifact envelope 及 completion receipt 完全
一致。作者 Artifact 的 creator 是精确作者 `agent_type`，唯一父引用为绑定的 source Artifact。

### 3.2 独立审查链

reviewer receipt 的时间包络为 `03:10:36.024042Z`—`03:11:43.151886Z`；SQLite 中该 Run 从
`03:10:53.632498Z` 进入 running，并在 `03:11:36.040288Z` 完成，同样严格落在该 invocation 内。

reviewer 的不可变输入同时绑定原始 `source_table` 和 `author_exec8.output`，其中后者的
`producer_run_id` 精确为作者 Run ID。密封 review 输出为：

```text
reviewer_exec4.output
artifact_id = art_2648656b09a6481ea3394476a38352c3
sha256      = b8d9d74cb267cca3ba7f5164d1d19c29e4281cc84a2472b375f8f053d387898a
```

CAS 原始字节摘要与 Run、envelope 和 completion receipt 相等。密封 payload 的
`subject_sha256` 精确等于作者输出 SHA-256，`verdict` 为 `pass`；Artifact append-only parent links
按位置同时包含 exact source 和 exact author subject。运行时 `is_exact_reviewer_output` 对相同
Operation、输入端口、subject ref 和允许 verdict 返回真。因此这是对当前作者修订的精确通过审查，
不是旧审查继承、仅 Schema 通过或名称近似。

### 3.3 状态完整性

当前 Run 数据库共有 `5 completed / 8 failed`，没有 `queued` 或 `running`。八条失败 Run 全部继续
保留原始失败原因且没有 output ref；`author_exec7`/`reviewer_exec3` 也作为缺少 launcher provenance
的历史 completed 组合保留，没有被改写成当前证据。当前实例 binding 精确指向
`author_exec8.output` 和 `reviewer_exec4.output`。

## 4. 首轮 FAIL、返工与最终 PASS 历史

历史结论未被绿化或删除：

1. `author_exec7`/`reviewer_exec3` 首次证明科学 Artifact 与精确 review 关系能够闭合，但 L3 状态曾
   硬编码 `bridge_used=false`，且没有持久证据证明两个结果来自不同独立 `codex exec`。首轮独立
   审查因此为 **FAIL**。
2. 首版 receipt 返工仍有四项放行阻断：fresh control 未接入 receipt 名；command digest 只检查
   形状而不比预期投影；dispatch 未携带当前外层沙箱 debug 模式；最终 receipt 直接写目标路径而非
   原子发布。该预审继续为 **FAIL**。
3. 返工把 receipt 名、4096 MiB 和模式同源冻结到 control/dispatch；status 由 invocation 重建完整
   命令并精确比较；receipt 改为同目录 `0600` 临时文件、flush/fsync、hard-link no-replace 发布和
   目录 fsync。聚焦测试补齐原子不覆盖与 fresh dispatch 接线，放行前复审为 **PASS**。
4. 最终另建 `author_exec8`/`reviewer_exec4`，没有恢复或覆盖旧 Run。两份新 receipt、SQLite 活动和
   密封 Artifact 形成上述可复算证据，本次最终审查为 **PASS**。

## 5. 没有第二状态权威或聊天摄入

`scripts/run_compiled_codex_worker.py` 只启动一个已经由 Root 排队的编译 Operation。stdio proxy 在
转发目标 Worker MCP 流时只旁录 `tools/call` 的 Worker 工具名和时间，不解释参数/响应，不选择 Run，
不写科学结果，也不执行 Run 状态迁移。receipt 只在子进程结束后发布，L3 status 只把它作为执行来源
证据；Run 生命周期、候选接受和 Artifact 注册仍唯一属于现有 SQLite 服务。

`scripts/l3_live_review_probe.py` 的 Root 路径只调用 `operation_invoke` 和 `run_status`，没有调用任何
`worker_*`。`launcher_receipts_verified=true`、`distinct_launcher_invocations=true` 和
`worker_transport=independent_codex_exec` 虽以常量写入最终投影，但只位于 receipt 全量验证及
invocation 不等检查之后；任一检查失败都会在写 `final-evidence.json` 前终止。精确 review 和 parent
布尔值来自运行时/Artifact 关系计算，不是固定 fixture verdict。

launcher 给独立模型的消息只要求完成已排队 assignment，不含 Run/Artifact 元数据或科学内容；子进程
chat 既不进入 receipt，也不被 L3 status 解析、转发或注册。科学结论只来自 Root completed 后读取的
密封 Artifact。

## 6. 31 项范围回归

本审查以 6 GiB 虚拟地址空间外层约束、`MALLOC_ARENA_MAX=2`、禁用 Python 字节码和 pytest cache，
串行复跑以下范围：

```text
tests/operations/test_independent_codex_worker_launcher.py       6
tests/operations/test_l3_review_and_human_policy.py              3
tests/operations/test_catalog_installed_entrypoint.py           10
tests/operations/test_architecture_constraint_matrix.py          1
tests/operations/test_l2_run_invariants.py                       11
                                                               ----
                                                                 31
```

结果为：

```text
31 passed in 49.88s
```

该回归覆盖 launcher 默认/外层沙箱模式、精确 Worker/禁用 Root、配置漂移、receipt 原子发布、fresh
control/dispatch、reviewer 原生读取能力、Codex profile/已安装入口、33 项约束投影和 Run 生命周期
不变量。测试计数只证明该候选的工程防退化，不替代上述真实 Run、密封 Artifact 和精确 review 证据，
也不构成 TCAD 或 M7.2 整体资格。

## 7. 保留边界

- receipt 是同一主机、同一 OS 用户边界内的本地审计证据，不是签名、远程证明或针对恶意 same-UID
  写者的密码学证明；原子 no-replace 关闭的是意外覆盖和部分发布窗口。
- proxy 证明工具请求经该 invocation 发出，不单独证明服务端成功；成功性由 Run activity、completed
  receipt、CAS 字节和 Artifact 关系交叉证明。
- reviewer 的 `inherited_prototype` 和 `--externally-sandboxed-debug` 依赖当前外层 Codex 沙箱及编译
  提示边界，不是 Hardened Worker 或生产级逐 Operation 强隔离。
- 4096 MiB 是本轮 launcher 设置并由 receipt/投影核对的进程地址空间限制；它不是进程组级 cgroup
  资源证明。
- launcher 是本轮用户明确授权的测试承载方式，没有接入 Root 默认调度器，也不得据此修改生产默认
  派发合同。

## 8. 最终放行判断

当前候选已经真实证明一条轻量
`OperationSpec → queued Run → 独立 Codex Worker → 文件交接 → Artifact → 独立 exact review`
通用闭环，且没有增加中央注册表、第二 Run 状态机、聊天结果通道或生产默认调度旁路。因此本审查结论
为 **PASS，阻断 0**。

本 PASS **只放行 M7.2 的下一条 TCAD 作者→领域调试→独立 Deck 审查子链**。它不宣称 M7.2 完成；
修订不继承旧审查、Effect 精确 UI 决定/执行收集、失败/超时恢复仍需后续纵向证据。M7.3 安全负例、
M7.4 物理报告、M7.5 全量回归和两位最终独立审查亦未放行。因此不得宣称 M7 或 R5-M 完成。
