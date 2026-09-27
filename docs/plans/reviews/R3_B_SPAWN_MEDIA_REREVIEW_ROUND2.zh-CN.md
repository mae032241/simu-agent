# R3-B Spawn 与媒体能力独立复审（第三轮）

审查日期：2026-08-28  
审查基线：`baseline/8765-codex@404aeb1` 叠加已通过的 R0—R3-A 与当前 R3-B 工作树  
前次审查：`R3_B_SPAWN_MEDIA_REREVIEW.zh-CN.md`  
审查者：未参与本轮修复的独立审查者  
审查方式：只读检查当前源码、测试、文本 run8 的报告和全部父子 Codex JSONL；用新检测器重新解析旧 text run6、PDF run5 与 image run3；未修改实现、计划或前两份审查报告

## 一、结论

**R3-B 通过，可进入 R3-C。**

二次复审的唯一阻断已经关闭。资格检测现在从同一个 `CompiledOperation` 确定唯一 Worker MCP
服务，逐项核对子会话的 MCP `function_call` 命名空间、工具名和调用号，以及
`item_completed` 的服务名、工具名和调用号；两侧集合必须完全相同，且第一项 MCP 工具必须是
该精确服务的 `worker_claim_task`。错误服务即使返回 `failed` 也会立即使检查失败。

独立重放该判断得到：旧 text run6 为 `false`，当前 text run8、PDF run5、image run3 均为
`true`。因此这不是只对合成夹具成立的修复；它既抓住了前次真实误判，也接受当前三条实际合规
会话。text run8 的原始子会话只有一个 Worker namespace，第一项 MCP 调用就是精确 claim，随后
完整闭合物化、任务内原生读取、受控写入、校验、封存和 Root `completed`。

本结论只确认 R3-B 当前承诺的原型行为约束和真实闭环，不把 `inherited_prototype` 误述为网络、
原生写入或操作系统级硬隔离。真实 TCAD、凭据、外部副作用和不可逆动作仍不得依赖该原型提示
约束；这一既有边界不阻塞进入 R3-C。

## 二、独立检查结果

| 检查 | 独立结果 |
| --- | --- |
| exact Worker 检测专项 | `tests/operations/test_live_qualification_evidence.py`：`11 passed in 0.44s` |
| R3-B 相关专项 | 资格证据、通用科学插件、R3 Agent 合同、精确 Worker 派发、平台配置：`35 passed in 5.26s` |
| 完整 `pytest -q` | `132 passed in 41.16s` |
| `python -m compileall -q src tests/operations` | 通过 |
| `git diff --check` | 通过 |
| Operation 核心预算 | `spec.py / catalog.py / invoke.py = 319 / 449 / 428`，合计 `1196` |
| text run8 报告 | schema version 4，24 项检查全真，报告 verdict 为 `pass` |
| 旧 text run6 真实负例 | 用当前检测器重算为 `false` |
| PDF run5 / image run3 | 用当前检测器重算均为 `true`，既有通过结论未受破坏 |

## 三、唯一阻断项的闭合证据

### 3.1 唯一服务名仍由同一编译权威派生

`operation_worker_server_name(compiled)` 从 Operation 标识和编译摘要确定性生成唯一服务名
（`src/scidiscovery/operations/tooling.py:51-62`）。同一函数被 Agent profile 生成、父会话继承
配置和安装态验证共同使用（`src/scidiscovery/platforms/codex.py:215-295, 390-458`），没有新增
服务注册表或第二份 allowlist。

资格脚本也不是从报告字符串猜测服务名：它从运行时 catalog 重新取得当前
`CompiledOperation`，调用同一个 `operation_worker_server_name()`，再把结果和该 Operation 的
编译 Worker 工具集合交给检查器（`tests/operations/live_r3_science_agent_qualification.py:705-709,
750-754`）。

### 3.2 function call 与完成事件配对

`_child_uses_only_exact_worker_server()` 的实际逻辑（同文件 `313-365`）为：

1. 遇到任何 `mcp__*` function call，命名空间必须精确等于
   `mcp__<expected_server>`，工具必须属于 compiled allowlist，调用号必须存在；否则立即
   `false`。
2. 遇到任何 `McpToolCall` 完成事件，服务名、工具名和调用号必须满足同一精确合同；否则立即
   `false`。
3. 调用侧和完成侧按调用号保存的 `(server, tool)` 映射必须完全相同，因而缺失完成事件、孤立
   完成事件或工具错配都会失败。
4. MCP 调用序列非空，且首项必须为 `worker_claim_task`。

合成负例在 `tests/operations/test_live_qualification_evidence.py:332-355`：先向错误服务调用
`worker_claim_task` 并让其返回 `failed`，随后再向正确服务领取；检查仍必须为 `false`。正例则
覆盖同一精确服务上的 claim 与 finalize 配对（同文件 `307-329`）。

我另外直接把四份原始会话交给当前函数，而不是读取报告中的布尔值：

- text run6：20 个 MCP function call、14 个不同 namespace，首项为错误服务，结果 `false`；
- text run8：7 个 MCP function call、唯一 exact namespace，首项为 exact claim，结果 `true`；
- PDF run5：8 个 MCP function call、唯一 exact namespace，首项为 exact claim，结果 `true`；
- image run3：7 个 MCP function call、唯一 exact namespace，首项为 exact claim，结果 `true`。

这满足前次复审要求的“错误 namespace 即使失败也拒绝”，并证明检测范围没有只看最终成功服务。

检测器以正常 Codex 会话中调用号唯一为输入合同；它没有额外充当任意损坏 JSONL 的通用语法
验证器。四份实际会话中调用号均唯一、调用均先于对应完成事件，且报告固定了原始文件摘要，
因此这不影响本次实证结论。后续若要让 CI 在无人复核下接纳任意外部会话，可再增加重复调用号
和乱序事件负例；该加固不属于 R3-B 当前阻断。

## 四、text run8 原始证据复核

审查对象：

`.scidiscovery-state/r3-science-spawn-text-run8/qualification-report.json`

及报告列出的两个 retained session JSONL。

### 4.1 报告与文件完整性

- 报告为 schema version 4，24 个 checks 全部为 `true`，verdict 为 `pass`。
- `codex-events.jsonl` 的独立 SHA-256 为
  `bd6890d68e723ee618fe437e4580fc39bef5be2d51595b18c0fb060b460db5d6`，与报告一致。
- `codex-final.txt` 的独立 SHA-256 为
  `9bff165066c23b61713a8ee8b1b0d67750b448616cb2630fad2240f1fd5a0f80`，与报告一致。
- 父、子 session JSONL 的独立 SHA-256 分别为
  `62f96671ead067bed355e05dbe5ac30819de15e5e56868fb3a049e31fa4de0bc` 和
  `7beb0b434dab3842ff9ee0711fc33110ef47ced9aa638100048a021a6b4aee06`，均与报告一致。

### 4.2 spawn、角色与最小上下文

父会话只有一次 `spawn_agent` 和一次 wait；派发类型精确为
`op_science_evidence_extract_v1_a61600b59e20`，参数显式包含 `fork_turns="none"`，子消息仅为
“完成已经排队的工作分配。”。父会话没有 Root 或 Worker MCP 代写。

子会话的 `session_meta` 记录同一 agent role。其全部 7 个 MCP function call 依次为：

1. `worker_claim_task`；
2. `worker_materialize_assignment`；
3. `worker_file_write_begin`；
4. `worker_file_write_chunk`；
5. `worker_file_write_commit`；
6. `worker_validate_output_file`；
7. `worker_finalize_file`。

七项均来自唯一服务
`scid_worker_science_evidence_extract_v1_a61600b59e20`，每个调用号都有同服务、同工具的完成事件；
没有其他 Worker、Root、web、网络或委派调用。

### 4.3 任务路径、原生读取与文件生命周期

`worker_materialize_assignment` 完成事件返回唯一任务工作区。三个原生 `exec_command` 都把
`workdir` 精确设为该目录，只读取：

- `assignment.json`；
- `inputs/source_material.txt`；
- `schema/output.schema.json`。

三项命令均退出码 0；没有绝对任务外路径、`..`、项目根工作目录、框架导入或原生写入。结果
通过 Worker begin/chunk/commit 创建 `output/result.json`，校验返回 `valid=true`，封存返回
`state=completed`。

### 4.4 严格科学对象与最终状态

任务数据库只有一个任务，attempt 为 1，状态为 `completed`，事件序列为
`created → dispatched → claimed → completed`。任务 output ref 的摘要为
`c8515504c7629821d00fa3dbb3794ca70bcd0f938aaa0b7f131dbcac68d8d424`；对应 CAS 文件独立重算
一致，大小为 3176 字节。状态目录中的 7 个 Artifact payload 均通过摘要和大小复核。

用当前 `ScientificIntake.model_validate_json(..., strict=True)` 解析最终 CAS payload 成功；
`problem_frame.objective` 与 `scientific_foundation.objective` 完全相同，唯一 evidence source key 为
`source_material`，唯一事实为“在架构夹具条件下，样品温度为 300 K”，并显式限制不得外推。

## 五、PDF run5 与 image run3 回归影响

本轮生产行为没有改变媒体合同、Operation profile、catalog、Worker 文件生命周期或科学 Schema；
新增内容集中在资格解析和其负例。按照前次复审冻结的口径，不为仪式重复拉起昂贵真实 Agent，
而是用当前检测器重新解析两份既有原始 child JSONL。

- PDF run5 仍只有 exact Worker 服务，第一项为 exact claim，所有 call/completion 配对，当前函数
  返回 `true`。前次已确认原生 `pdftotext`、注册 `worker_extract_pdf_text`、任务内 excerpt、严格
 对象、validate/finalize 与 Root completed 全部闭合。
- image run3 仍只有 exact Worker 服务，第一项为 exact claim，所有 call/completion 配对，当前
  函数返回 `true`。前次已确认同调用号 `view_image → ImageView`、任务内图像路径、严格对象、
  validate/finalize 与 Root completed 全部闭合。

因此新门没有把合法 PDF/图像路径误拒绝，也没有破坏“媒体阅读优先复用 Codex 原生能力、领域
工具只承担受控冻结或输出生命周期”的既有结论。

## 六、33 项约束族与复杂度判断

仓库没有逐项编号的 33/33 自动验证器；本次继续按已冻结的行为约束族审查，不伪称存在该脚本。

| 约束族 | 判断 | 依据 |
| --- | --- | --- |
| 单一插件注册、启动期编译、catalog 唯一权威 | 通过 | 服务名和工具集合仍从同一 compiled operation 投影，无新注册表 |
| OperationSpec 行为闭包 | 通过 | Agent 类型、prompt 中的精确服务、原生能力和 Worker 工具均由 compiled operation 派生 |
| 科学内容归 Worker | 通过 | text run8 科学对象由真实 child 生成，父会话零代写 |
| 最小上下文、文件交接 | 通过 | `fork_turns="none"`，只读物化任务根与声明输入/Schema |
| Worker 最小授权行为 | 通过于 R3 原型口径 | 唯一 exact Worker 服务、首项 exact claim；旧错误探测现被拒绝 |
| Root、网络、未声明工具 | 通过于观察口径 | run8 无 Root/web/其他 Worker；不外推为硬隔离 |
| CAS、校验、封存、终态 | 通过 | 摘要、严格对象、validate/finalize、数据库 completed 一致 |
| 控制面不增加科学判断 | 通过 | 本轮只增强证据资格解析，不增加科学排序或内容生成 |
| 无新实体、状态机、第二权威 | 通过 | 修复没有增加 Operation、存储实体或调度状态 |
| 真实证据不误判 | 通过 | 旧 run6 为真实负例，run8 为当前配置正例，PDF/image 合法路径仍通过 |
| 快速闭环与复杂度预算 | 通过 | 完整 132 项通过；核心总计 1196 行，未发生复杂度转移 |
| 人工决定与外部副作用 | 未退化 | 本轮没有审批替代、真实执行或外部副作用 |

## 七、阻断项与非阻断边界

阻断项：**无。**

非阻断边界：

1. `inherited_prototype` 仍是模型可见行为约束，不是操作系统级硬隔离；不得把 R3-B 通过解释为
   已经授权真实副作用。
2. 当前资格检测针对正常 Codex retained session；重复调用号或刻意乱序的损坏 JSONL 尚无专门
   负例。当前四份证据调用号唯一、顺序正常、摘要固定，不影响本轮事实判断。
3. PDF run5 与 image run3 的旧报告没有 schema version 4 的第 24 个布尔字段，但本轮已直接把
   它们的原始 child 事件交给当前 exact-server 检查器，均通过，因此不要求无意义重跑。

## 八、最终裁定

**R3-B 通过，可进入 R3-C。**

二次复审的唯一阻断已由真实失败反例、合成负例、当前文本正例和两条媒体回归共同闭合；没有
发现需要在进入 R3-C 前修复的新阻断。
