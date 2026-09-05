# R5-H H3-B 隐藏 Worker 协议删除独立实现审查

日期：2026-08-31  
审查基线：`404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前工作树  
权威计划：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
权威计划 SHA-256：`1c25cb8da2bc3799ac7c9ce8be07331cc49934c64b5adf406e5b5e451e52ab0b`  
审查范围：只审 H3-B；H3-A 已独立复审通过；不审查 H3-C/H3-D 实现，未放行 H3-D  
结论：**通过**

## 1. 最终判断与阻断项

**阻断项：无。**

当前候选完成了计划要求的纯减法：builtin 架构夹具和 TCAD author/reviewer 已迁移到既有
materialized task workspace 的 native read；12 个隐藏 Worker 工具及其模型、capability 映射、
dispatch、6 个旧服务方法和 7 个死活动值已从生产 Python 消失；当前 file lifecycle、proxy 续租和
TCAD 注册调试工具仍可达。没有新增入口校验、Registry、兼容层、控制状态或领域名核心分支。

H3-B **通过，只放行 H3-C**。H3-D 仍须等待 H3-C 实现及独立审查通过；本结论不替代 H3-D 的干净
wheel 组合、发布 manifest、重启和总审查。

## 2. builtin 与 TCAD 已真实改用 materialized native read

- `src/scidiscovery/builtin_plugin.py:39-55` 的架构夹具 prompt 要求先
  `worker_materialize_assignment`，再用 Codex native read-only 工具读取 `assignment.json` 和声明的
  task-relative 输入；组件表和 Agent 工具闭包（第423-485行）不再声明 `input_read_tool`；
- `plugins/tcad_artifact/tcad_artifact/plugin.py:336-355` 的 author/reviewer 生命周期只含既有
  materialize、file write/patch、file validate/finalize；author 额外获得注册的 debug 工具，reviewer
  不获得它。生产声明和两份 TCAD role prompt 均无 `worker_read_input`；
- `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md:24-47` 与
  `tcad_deck_reviewer.md:17-38` 明确把 native read 限制在 materialize 返回的 task workspace；
- `task_worker_files.py:744-789` 仍把非 handoff 输入写成 task-private、只读、不可变文件；第845-881行
  继续调用已存在的 Operation workspace materializer。TCAD materializer 在
  `operation_workspace.py:278-489` 展开 `deck/`、只读 review tree 和精确 read paths，没有新增读取工具；
- 完整 Operation 回归中的 `test_general_science_agent_operation_uses_exact_files_and_parent_chain`、
  installed handoff probe 和 `test_registered_tcad_author_debug_and_reviewer_lifecycle` 均通过，证明不是只改
  prompt 或目录断言。

结论：builtin 和 TCAD 的消费端、编译工具闭包、任务物化器及真实 Worker 调用已闭合到同一现有
native-read 路径，不存在“删导出但仍暗调旧服务”的残留。

## 3. `access_modes` 是机械总函数，没有过度设计

`src/scidiscovery/artifact_agent/service/tasks.py:833-857` 只有一个线性投影：

1. 初始为空；
2. exposure 不是 `handoff_only` 时固定为 `native_read`；
3. 同时满足规范化媒体类型为 `application/pdf` 且精确 Operation 授权
   `worker_extract_pdf_text` 时，按固定顺序追加 `extract_pdf_text`；
4. `handoff_only` 不进入上述分支，始终为空。

`schema/task.py:325-334` 的枚举只保留 `native_read` 和 `extract_pdf_text`；
`task_worker_files.py:764-789` 对 handoff-only 只写有界 handoff，不写 `relative_path`，其余输入才写
任务内路径。普通输入、获授权 PDF 和 handoff-only 的回归分别冻结为 `[native_read]`、
`[native_read, extract_pdf_text]` 和 `[]`/无路径。

该规则只消费已有 exposure、标准媒体类型和精确 Operation 工具闭包；没有媒体 Registry、插件名判断、
新入口校验、Schema 字段或派生控制状态。`controlled_read` 已从生产源码消失。

## 4. 旧协议删除完整，真实入口返回 unknown

### 4.1 逐项静态结果

对 `src/**/*.py` 和 `plugins/**/*.py` 使用标识符边界扫描，以下内容均为零命中：

- 12 个旧工具：`worker_get_assignment`、`worker_list_inputs`、`worker_read_input`、
  `worker_stage_input`、`worker_read_table`、`worker_profile_input`、
  `worker_begin_result_upload`、`worker_append_result_upload`、
  `worker_commit_result_upload`、`worker_validate_output`、`worker_write_result`、
  `worker_finalize`；
- 6 个旧协议模型：`ReadInput`、`TableInput`、`ProfileInput`、`ValidateOutputInput`、
  `FinalizeInput`、`ResultUploadChunk`；
- `_LEGACY_WORKER_TOOLS`、`READ_INPUT_TOOL`、`controlled_read`；
- 6 个旧服务方法定义：`begin_result_upload`、`append_result_upload`、
  `commit_result_upload`、`write_result_file`、inline `validate_output`、inline `finalize`；
- 7 个旧活动值：`assignment_read`、`inputs_listed`、`input_read`、`input_staged`、
  `table_read`、`input_profiled`、`output_written`。

`mcp_worker_protocol.py:108-143` 的工具和 capability 映射只含当前协议；保留的 `NamedInput` 和其子类
`PdfInput` 位于第29-35行。`mcp_worker.py:58-84` 只合并当前 builtin 工具和精确 Operation 注册工具；
`mcp_worker_dispatch.py:26-30` 对不存在的名称立即抛出 `unknown worker tool`，其余 dispatch 到第426行
只有当前 materialize、领域工具、file、validate、heartbeat、finalize 分支。

### 4.2 真实服务端负例

独立探针没有只调用 helper：它通过生产
`WorkerBrokerRouter.handle -> MCPRouter.handle -> WorkerMCPRouter.call_tool` JSON-RPC 路径，先确认
`tools/list` 与上述 12 名不相交，再逐名发出 `tools/call`。12/12 均返回精确错误：

```text
unknown worker tool: <被调用旧名>
```

现有 `test_r5_worker_router_split.py:92-116` 也逐项冻结相同 unknown 行为。历史计划、审查报告和测试中的
旧名称是预期的负例/历史证据，不是生产残留；没有以 tombstone Registry 或兼容转发器实现 unknown。

## 5. 当前 file lifecycle 与 proxy 续租语义保持

- 正式写入仍只有 `begin/append/commit_worker_file_write`（`task_worker_files.py:969-1209`）及当前
  patch/move/delete 方法；正式封存仍只有 `validate_output_file` 与 `finalize_file`
  （`task_outputs.py:370-445`）；
- `TaskService.read_input` 和 `stage_input` 仍位于领域 contextual handler/PDF 缓存需要的内部层，未被
  误删，也没有重新暴露为通用 Worker MCP；
- `mcp_worker_proxy.py:51-68` 保持：成功 claim 启动续租；file validation 失败时 stop 后 restart，使
  Worker 可修订；成功验证停止续租；只有 `worker_finalize_file` completed 停止。旧
  `worker_finalize` 不再是终态观察条件；
- `test_r5_worker_router_split.py:119-150` 对四个 proxy 状态迁移逐一检查；311项回归共同覆盖
  materialize、create/patch、validation rejection、validate file、finalize file、collection bundle、retry
  snapshot 和终态登记。proxy 聚焦用例单独证明失败验证后续租重启、随后成功验证和 file finalize 的
  观察语义，不把 mock 观察器夸称为一次真实后台 heartbeat 线程集成运行。

没有发现 file validation seal、finalization grace、不可变 Artifact 登记或 proxy lease 行为因删除旧
inline 路由而退化。

## 6. TCAD 注册调试工具真实可用

`plugins/tcad_artifact/tcad_artifact/plugin.py:182-204` 的 contextual handler 通过
`WorkerToolContext` 取得精确 runtime service；第254-264行把 `worker_tcad_debug_run` 注册为 author
Operation 工具，并绑定 `tcad.development_debug` capability/service。核心 dispatch
`mcp_worker_dispatch.py:104-158` 构造受限 `WorkerTaskAccess` 后调用注册 handler，不含 TCAD 名称分支。

`test_registered_tcad_author_debug_and_reviewer_lifecycle` 通过真实 Operation 编译、Root invoke、Task
claim/materialize、注册 handler、`TCADDebugService`、受控 fake adapter、poll、file validate/finalize
整条本地路径：author 的调试工具先返回 running、后返回 succeeded，重复 poll 不重复提交；reviewer
工具列表不含该工具且 review workspace 只读。这里验证的是“注册调试工具真实可调用”的 H3-B 边界；
没有把 fake adapter 夸称为真实 Sentaurus 求解器运行，后者不是本阶段门。

## 7. 33项约束、通用 AI 科学家目标与复杂度预算

- 33项约束结构门通过；语义上，本次删除直接收紧 `AUTH-003`、`ROLE-002`、`SEC-002`，并保持
  `PLG-001`、`RES-001/002`：工具权限仍来自一个 `CompiledCatalog` 和精确 Operation，Worker 输入仍是
  task-local 文件，领域工具仍由插件注册；
- native-read 规则不包含 TCAD、曲线、角色、Schema 或插件名。文本、JSON、PDF 和未来插件共享同一
  物化读取机制；PDF 冻结摘录仍是显式授权的附加能力。因此通用 AI 科学家目标没有被改成 TCAD
  专用流程或固定科研 DAG；
- 本阶段没有新增生产文件、数据库表/列、OperationSpec 字段、Registry、状态值、路由器、facade、
  适配器或入口校验。删除集中在旧模型、旧路由和零消费者服务，没有把复杂度搬到另一套抽象；
- H3-A 冻结指标为150个生产 Python 文件、59709行；当前为150个文件、59162行，**净删547行**。
  Worker 三文件从1172行降至810行，Task 责任聚合从6205行降至6031行；operations 包仍为7文件、
  2064行。测试增加的是逐名负例和当前协议正例，不是第二套测试基座；
- H3-C 未提前实施：`src/scidiscovery/builtin_plugin.py:599-601` 的 `PLUGIN = CORE_PLUGIN` 仍在，
  `scheduler_bindings.py:1757-1786` 的孤立 binding→`legacy.*` instance 合成块也仍在。

因此没有发现“针对测试打补丁”、新增旁路权威、复杂度转移或阶段越界。

## 8. 独立复核命令与结果

所有 pytest 命令均串行运行，并先设置 `ulimit -Sv 7340032`（7 GiB 虚拟内存上限）。

```text
pytest -q tests/operations
结果：311 passed in 108.98s；/usr/bin/time 峰值 RSS 133908 KiB

pytest -q tests/artifact_agent/test_deploy_scripts.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/operations/test_architecture_constraint_matrix.py
结果：38 passed in 5.60s；峰值 RSS 89676 KiB

PYTHONPATH=src python <独立静态清单与 WorkerBrokerRouter JSON-RPC 逐名探针>
结果：static_negative=pass counts=12_tools,6_models,6_methods,7_activities
      broker_jsonrpc_negative=pass unknown_tools=12

python -m compileall -q src plugins
结果：通过

python scripts/r5_current_metrics.py
结果：production_python={files:150, lines:59162}
      worker_lines=810；task_lines=6031；operations_package={files:7, lines:2064}

git diff --check HEAD
结果：通过
```

补充 JSON-RPC 探针首次因源码布局未设置 `PYTHONPATH=src` 而在导入前以
`ModuleNotFoundError: scidiscovery` 退出；修正测试环境后用 fail-fast 重跑并得到上述通过结果。这是审查
命令环境错误，不是候选行为失败，也没有被记作一次通过。

## 9. 非阻断债务与剩余风险

1. 根 `MANIFEST.sha256` 的发布代际更新按计划冻结在 H3-D；当前源码、完整 Operation 回归和安装测试
   已通过，但本报告不宣称根 manifest 已完成最终发布收口。
2. 整个 R5 当前工作树仍混合在同一个未提交差异中，Git 不能直接给出独立的 H3-A→H3-B patch。
   本审查用已封存 H3-A 报告的59709/1172/6205指标、当前逐符号生产扫描、当前指标和真实入口测试交叉
   核验出547行净删除。后续交付宜保留阶段提交或不可变文件清单，降低独立审查的差异重建成本。
3. 当前 Codex native read-only 仍有已知的提示约束而非平台级文件沙箱；本阶段没有扩大该能力，且
   task-local 路径、服务端 Worker 工具授权和封存写路径均保持。该既有 H4 风险不阻断 H3-B。
4. 本地 TCAD 聚焦回归使用受控 fake adapter 验证注册/服务/轮询/封存链，没有运行外部 Sentaurus；
   solver 与部署组合仍由后续既定资格/发布门负责。

## 10. 结论

H3-B 达到了“删除隐藏 Worker 协议、只做减法”的全部验收边界：现有 native materialization 成为唯一
普通读取路径，12 个旧名在真实 Worker JSON-RPC 服务端均 unknown，当前 file/proxy/TCAD 路径保持，
生产规模净减且 H3-C 未提前实施。**结论：通过，只放行 H3-C。**

本报告最终字节的 SHA-256 由交付消息给出；哈希不写入自身以避免自引用改变摘要。
