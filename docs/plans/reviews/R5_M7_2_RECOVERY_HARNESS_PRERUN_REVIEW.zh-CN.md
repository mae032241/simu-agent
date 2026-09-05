# R5-M7.2 恢复实跑工具事前独立审查

日期：2026-09-02  
审查范围：`tests/fixtures/m7_recovery_crash_worker.py` 与
`scripts/l3_live_review_probe.py` 的恢复实跑路径  
审查方式：只读调用链、状态权威和证据充分性审查；未创建持久根，未启动 Codex  
首轮结论：**打回；阻断项 2。**  
最终复审结论：**通过；两项阻断均已关闭。允许创建一个全新持久根，并串行启动一次 4 GiB
恢复 Codex。**

## 1. 已正确闭合的边界

### 1.1 故障注入走真实 stdio Worker MCP

故障注入进程实际启动 `scidiscovery.artifact_agent.interfaces.mcp_local_worker`，以 JSON-RPC 顺序调用
`worker_open_assignment` 和已注册的 `worker_csv_summarize`。草稿写入 Worker 返回的 Run 私有输出目录；
代码中没有 `worker_submit_result` 调用，内部 MCP 进程关闭后，外层故障注入进程以固定非零码 `73`
退出。

Root 不相信故障进程的自述：脚本又从 Run 活动账本确认 `worker_csv_summarize` 成功，确认 Run 仍为
`running`，随后把刚读取的 `last_activity_at` 连同 `expected_state=running` 交给
`run_record_failure`。因此失败状态通过现有比较交换入口建立，而不是由夹具修改数据库。

### 1.2 失败草稿没有被提升为科学结果

失败后检查覆盖：

- Run 为 `failed` 且具有恢复草稿；
- `accepted_candidate_digest`、output ref、scheduler signal 和 completion receipt 均不存在；
- 草稿 payload 摘要在失败时没有对应 Artifact；
- 原活动工作区由既有后端隔离。

故障注入脚本中的科学文字只是故意留下的未提交草稿，控制面不读取它作结论，也没有将它登记为
Artifact、current 或 scheduler signal。外层 JSON 仅为故障测试收据，不是科学结果。

### 1.3 错误输入和正确恢复请求边界正确

错误输入在调用 `operation_preflight` 前单独建立为测试 Artifact；随后快照 Run 列表。拒绝后要求 Run
列表完全不变，且不存在目标 Run binding。因此这里的“零状态”准确含义是拒绝本身不产生 Run 状态，
不是禁止测试预先建立错误输入。

正确请求使用同一个字典依次执行 preflight 和 invoke，并保持：

- 同一 Operation；
- 同一指令常量；
- 同一 `source_csv` 输入；
- `resume_from` 精确指向失败源；
- 新语义名 `author_recovered`。

重启后的 status 路径又从唯一 Run 数据库比较两个 Run 的 Operation id/version/digest、instruction 和
完整 `inputs_json`，并验证 `resume_from_run_id` 及不同 Run ID，没有把普通新 Run 冒充恢复。

### 1.4 状态与启动器没有建立第二权威

恢复 Codex 仍由现有 `run_compiled_codex_worker.py` 承载；4 GiB 内存、精确 agent type、唯一 Worker
MCP、运行时间包络和 completed Run 的关系由既有 launcher receipt verifier 检查。启动器和故障收据
都不迁移 Run 状态、不登记 Artifact，也不解释科学内容。重启后的 Root/Run/Artifact 数据库仍是唯一
终态权威。

调试 dispatch 文件包含运行所必需的本地路径和生成 profile，但这些字段不进入子 Agent 的科学消息或
最终科学 Artifact；最终汇总也没有把路径、内部 ID 或聊天内容当作科学结论。

## 2. 阻断项

### B1：没有证明恢复 Codex 重新调用确定性工具验证完整结果

`status_recovery()` 验证了恢复 launcher receipt，但该 receipt 只证明编译 profile 中投影了
`worker_csv_summarize`，不证明恢复 Codex 实际调用了它。当前最终门没有查询恢复 Run 的
`successful_tools(recovered_id)`。

因此，一个 Codex 可以直接复制已经完整、且符合 Schema 的 recovery draft，再调用 submit；输出
context validator 仍可能通过，当前 `final-evidence.json` 会给出全真结论。这不满足 assignment 中
“恢复草稿只作起点，重新验证完整结果”的要求，也弱于此前通用作者闭环已经采用的工具活动证据。

最小修复：要求恢复 Run 的活动账本含 `worker_csv_summarize`，把该事实作为独立布尔项写入最终证据，
并纳入全真门。无需新增工具、状态或收据。

### B2：重启后没有复算实际恢复文件和最终 Artifact 字节

当前 status 仅确认：

- recovery assignment 标记 `scientific_evidence=false`；
- `recovery-draft/result.json` 存在且不可写；
- source manifest 声称的文件数和字节数没有超限。

它没有重新读取实际恢复文件，复算 size/SHA-256 并与 source recovery manifest 的
`relative_path`、`size_bytes`、`sha256` 对照。`draft_bounded` 也使用清单声明值而非实际文件值。
因此最终证据尚不能证明恢复 Run 收到的正是先前封存的有界草稿。

同时，恢复输出只经 `get_by_id()` 读取 envelope 并检查父链，没有调用 `ArtifactService.verify()` 复核
CAS 字节。

最小修复：

1. 对实际 `recovery-draft/result.json` 读取字节并计算长度与 SHA-256；
2. 精确匹配 manifest 的单一 `relative_path/result.json`、`size_bytes` 和 `sha256`；
3. 用实际字节数执行上限判断；
4. 对 recovered output 调用 `runtime.artifacts.verify(output.ref)` 后再判断父链。

这些都是证据汇总层的只读检查，不增加生产实体或运行协议。

## 3. 首轮判定

主链的运行与权威边界是正确的：没有人工修改数据库、没有恢复旧会话、没有新插件、没有第二 Run
状态机，也没有由脚本伪造 completed 状态。两个阻断均是现有持久事实没有被最终门充分交叉验证，修复
范围应只落在 `status_recovery()` 的只读证据计算。

在 B1、B2 修复并通过聚焦 smoke 后，需再次独立复审；复审通过前不得创建持久证据根或启动恢复
Codex。本首轮报告不放行 M7.2、M7 或 R5-M。

## 4. 返修复审

返修只修改了 `status_recovery()` 的只读证据门，没有改变 Run 生命周期、Operation、Worker MCP、
数据库 Schema 或启动器。

### 4.1 B1 已关闭

最终证据新增 `new_run_revalidated_with_registered_tool`，其值直接来自恢复 Run 的持久
`run_activity`：只有 `successful_tools(recovered_id)` 含 `worker_csv_summarize` 才能为真。该字段
已进入统一全真门。launcher receipt 继续只证明启动身份和能力投影，没有被扩大解释为工具调用成功。

### 4.2 B2 已关闭

重启后的 status 现在读取实际 `recovery-draft/result.json` 字节，并同时要求：

- source manifest 只有一个文件且相对名为 `result.json`；
- 实际字节长度等于 manifest 的 `size_bytes`；
- 实际 SHA-256 等于 manifest 的 `sha256`；
- 文件只读并带 `scientific_evidence=false`；
- 上限判断使用实际字节长度，而非只相信 manifest 声明。

恢复输出也改为先调用 `runtime.artifacts.verify(recovered_status.output_ref)`，在复核 CAS 字节后才检查
精确输入父链。

### 4.3 最终事前门

独立静态解析结果为 `AST_OK`，范围差异格式检查通过。当前工具将：

1. 经真实 stdio Worker MCP 制造一个未提交、可恢复的失败草稿；
2. 只由 Root 比较交换记录失败；
3. 证明错输入预检不写 Run 状态；
4. 以相同 Operation、指令和完整输入建立显式新 Run；
5. 只启动一次 4 GiB、精确 agent type 的 Codex；
6. 从重新打开的运行时交叉验证 Run、活动账本、恢复文件、Artifact CAS、父链和无活动 Run。

没有发现路径、ID、退出收据或测试摘要被冒充为科学结果，也没有第二运行时权威。最终结论为
**PASS，阻断项 0**。该 PASS 只放行本次最小持久恢复实跑；在实跑产生完整机器证据并通过事后独立
审查前，M7.2、M7 和 R5-M 仍未完成。
