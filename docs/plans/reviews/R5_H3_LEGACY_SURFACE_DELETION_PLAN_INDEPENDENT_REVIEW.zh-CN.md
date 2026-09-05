# R5-H H3 旧表面删除方案独立审查

日期：2026-08-30  
审查对象：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md` 及其引用的当前实现与总计划  
审查性质：只读、跨边界、复杂度削减方案审查  
结论：**打回**

## 1. 总体判断

H3 的目标和分段顺序是正确的：删除 YAML current、12 个隐藏 Worker 工具、零消费者别名和孤立
binding 自动合成，能够直接恢复“一个 current 权威”和“一个 Worker 文件协议”。方案没有提出新的
Registry、状态机、OperationSpec 字段、兼容转发器或领域核心分支；PyYAML 降为测试依赖、普通输入
改为任务内原生只读、handoff-only 不物化，以及保留领域 contextual tool 的内部读取能力，也都符合
当前设计宪章和 33 项行为约束。

本轮打回不是要求扩大控制面，而是因为 H3-B 的删除清单仍会留下真实的旧服务/活动表面，并且一处
心跳表述可能误删当前文件协议所需的行为；消费者清单和旧孤立 binding 的验收也还不够精确。按下述
最小修订完善计划后即可重新审查，不需要改变 H3 的总体架构。

## 2. 阻断项

### B1：旧输出协议的服务删除清单漏掉 `write_result_file` 和对应死活动名

计划第 88—89 行只明确删除 `begin/append/commit_result_upload`、inline `validate_output` 和 inline
`finalize`，没有列出只被 `worker_write_result` 使用的 `TaskService.write_result_file`。

当前真实调用链是：

- `worker_write_result` 分支位于
  `src/scidiscovery/artifact_agent/interfaces/mcp_worker_dispatch.py:526-557`；
- 其唯一服务消费者是
  `src/scidiscovery/artifact_agent/service/task_outputs.py:427-462` 的 `write_result_file`；
- `begin/append/commit_result_upload` 位于
  `src/scidiscovery/artifact_agent/service/task_worker_files.py:1513-1593`，同样只有旧路由消费；
- inline `finalize` 和 `validate_output` 分别位于
  `task_outputs.py:805-830`、`:1008-1023`。

若按现计划逐字实施，路由会被删除，但 `write_result_file` 会成为残留的第二套“把内联对象写成
result.json”的服务表面，不满足“唯一 Worker 文件协议”和生产净删除目标。

此外，删除旧路由后，`TaskService.record_activity` 中的 `assignment_read`、`inputs_listed`、
`input_read`、`input_staged`、`table_read`、`input_profiled`、`output_written` 将没有当前生产消费者；
它们仍可由注册领域工具通过 `WorkerTaskAccess.record_activity` 写入，形成看似存在的旧协议审计事件。
当前文件协议仍真实使用 `output_validated`，不得连带删除。

最小修订：

1. 在 H3-B 第 6 步明确同时删除 `write_result_file`；
2. 在消费者表中逐一列出六个待删旧服务方法；
3. 删除上述七个已无消费者的旧活动名，但保留当前文件验证、文件编辑、PDF、分析、网页证据和领域
   工具所需的活动名；
4. 增加静态负例，确认这些旧服务方法和旧活动名不再存在，不为它们增加别名或转发器。

### B2：proxy 心跳步骤措辞会误伤当前文件封存协议

计划第 86—87 行写“proxy 心跳观察只认识 `worker_finalize_file`”。当前
`mcp_worker_proxy.py:58-68` 除了在完成时识别旧/新 finalize，还承担当前协议所需的两项行为：

- `worker_claim_task` 成功后启动自动续租；
- `worker_validate_output_file` 成功时停止续租，失败时重启续租。

H3 只应把终态条件从 `{worker_finalize, worker_finalize_file}` 收窄为
`worker_finalize_file`，不能删除 claim 和 file-validation 的观察分支。按现文字实现可能让
`worker_validate_output_file` 后的 lease/finalization 边界发生回归。

最小修订：把该步骤改为“保留 claim 与 `worker_validate_output_file` 的当前续租行为；终态观察只删除
`worker_finalize`，继续以 `worker_finalize_file` 为唯一完成工具”，并增加一个成功验证、失败后修订、
最终封存的聚焦心跳回归。

### B3：协议模型与真实测试消费者的冻结不够精确

计划第 84—85 行笼统要求删除“旧输入请求模型”。但
`mcp_worker_protocol.py:34-40` 的 `NamedInput` 仍是当前 `PdfInput` 的基类，不能和
`ReadInput`、`TableInput`、`ProfileInput`、`ValidateOutputInput`、`FinalizeInput`、
`ResultUploadChunk` 一起删除。这里若不冻结精确符号，实施很容易误伤当前
`worker_extract_pdf_text`。

同时，第 28 行把 `worker_read_input` 的测试消费者只写成 handoff-only 边界测试，实际还包括：

- `tests/operations/test_r5_worker_router_split.py:26-43` 对 `READ_INPUT_TOOL` 导出的结构断言；
- `tests/operations/test_catalog_compile.py:56` 对 `architecture_fixture:input_read_tool` 的目录断言；
- `tests/operations/test_baseline_worker_authority.py:168-196` 对编译授权与 handoff-only 拒绝的真实调用。

这些测试不是保留旧协议的理由，但必须在迁移清单中明确改写为当前协议正例/旧名 unknown 负例，不能
以“全量测试之后自然失败”代替消费者冻结。

最小修订：精确列出待删模型，明确保留 `NamedInput`/`PdfInput`；在消费者表加入上述三个测试，并说明
删除旧断言后由同一测试文件继续覆盖 `native_read`、handoff-only 无路径及旧名服务端拒绝。

## 3. 必须澄清但不要求增加控制面的验收项

### 3.1 `access_modes` 的机械投影规则

计划的方向正确，但第 81—83 行应冻结一个无歧义的现有事实投影：

- 非 handoff-only 输入在 materialize 后声明 `native_read`；
- 只有媒体类型为 `application/pdf` 且该精确编译 Operation 授权
  `worker_extract_pdf_text` 时，再追加 `extract_pdf_text`；
- handoff-only 始终 `access_modes=[]`、无 `relative_path`，即使 Operation 拥有 PDF 工具；
- 不增加新的 capability、入口校验或媒体类型注册表。

当前 `TaskService.assignment` 在
`src/scidiscovery/artifact_agent/service/tasks.py:839-859` 仍按 `worker_read_input` 生成
`controlled_read`；任务文件物化在 `task_worker_files.py:745-956` 已经拥有普通输入路径和
handoff-only 无路径的真实来源。这里只需改投影，不需建立新权威。

### 3.2 旧孤立 binding 的“拒绝”必须限定在生产 current 入口

计划第 103、129 行只要求“不自动合成、不污染列表”，同时写“错误应明确”。当前初始化自动合成块
确实位于 `scheduler_bindings.py:1757-1786`；但底层 `resolve/list` 会按调用者提供的 instance 字符串
直接查询（`:907-1028`）。因此，不能写一个只检查 `legacy.*` 名称不存在的弱测试，也不应为此新增
全局扫描、启动失败或每次调用重复入口校验。

最小且不过度的验收应限定为真实生产 current 路径：用旧格式孤立 binding 打开 runtime 后，
`list_instances` 和 session-binding candidates 不出现伪实例，`session_instance` 不返回孤立 id，
`get_instance` 对该 id 明确 unknown；原始旧 binding 行可以保持不可达、只读，不删除也不迁移。
这足以证明它不能成为 current，又不增加控制面实体或校验层。若计划想承诺底层任意 `resolve(old_id)`
也拒绝，则必须另行说明现有 API 取舍；本轮不建议扩大到该承诺。

## 4. 已核查并认可的设计判断

### 4.1 `research_state` 与 PyYAML

- `src/scidiscovery/research_state.py` 是唯一生产 `yaml` import；运行服务没有 import 它；
- 当前唯一运行入口是 `deploy/install.sh:145-149` 在 `research/current.yaml` 存在时执行 validate；
- PyYAML 还出现在 `pyproject.toml:13`、`runtime_identity.py:15`、安装探针
  `deploy/install.sh:179-180`；
- 当前测试消费者是
  `tests/operations/test_architecture_constraint_matrix.py:3-12`，安装/发现测试还冻结了旧版本断言。

因此，把 `PyYAML>=6,<7` 从基础依赖移到 test extra 是合理的，不会破坏当前运行包。H3-A 必须用一个
没有 system-site-packages、确实未安装 PyYAML 的 base-wheel 环境验证编译目录、打开/重开当前数据库
和终态读取；仅在现有开发环境运行测试不能证明运行依赖已删除。安装中英文文档的依赖命令在 H3-D
同步修改即可。

### 4.2 Agent 公开读取与 contextual 读取的边界

删除 `worker_read_input` 但保留 `WorkerTaskAccess.read_input` 是正确分层：

- `WorkerTaskAccess` 只交给所选已注册 contextual handler；
- `TaskEvidenceMixin.read_input` 在 `task_evidence.py:47-60` 仍验证当前 session、active attempt、精确
  task input 和 handoff-only 拒绝；
- table、curve figure 和 curve analysis 的领域工具是当前真实消费者；
- `stage_input` 在 `task_evidence.py:62-89` 仍被 PDF 冻结提取路径 `:164-166` 使用，必须保留。

该内部能力不是 Agent 可直接调用的 MCP，不构成第二套 Agent 文件协议。

### 4.3 TCAD 与 builtin 迁移

`READ_INPUT_TOOL` 的真实 Operation 注册者只有：

- builtin 架构测试夹具：`builtin_plugin.py:428-431,483-486`；
- TCAD author/reviewer：`plugins/tcad_artifact/tcad_artifact/plugin.py:344-356,511`。

TCAD author/reviewer 的现有 prompt 已明确要求 materialize 后用任务内 native read；TCAD workspace
materializer 已消费物化输入路径。因此删除该组件不需要新增 TCAD 读取工具。builtin prompt 只需把
第 42 行的 `worker_read_input` 改为读取 assignment 声明的任务内相对路径。

### 4.4 `builtin_plugin.PLUGIN` 与孤立合成

- `builtin_plugin.py:605-607` 的 `PLUGIN = CORE_PLUGIN` 没有生产或当前测试消费者；
- 基础 entry point 已是 `pyproject.toml:27` 的 `CORE_PLUGIN`；
- 删除别名是安全的纯减法；
- 删除 scheduler 初始化的孤立 binding 自动合成也符合本轮明确不兼容历史文件的取舍，但必须采用
  3.2 的精确不可达验收，不建立迁移器。

## 5. 分段、复杂度和 33 项约束判断

H3-A→H3-B→H3-C→H3-D 的顺序可实施：先移除第二 current，再移除 Worker 旁路，最后删除零消费者
别名/历史合成，安装与总回归收口。逐门独立审查虽然成本较高，但这是用户明确要求，且能阻止一个
阶段的删除错误扩散到下一阶段。

“每子阶段生产 Python 与 shell 不得净增加”是合理硬门。修订后的 H3 不需要新增生产文件、数据库
表列、状态值、OperationSpec 字段、Registry、路由器或领域分支；测试和文档新增不应计作控制面
增重。保留 Artifact/Task/Approval/Execution/current/qualification、file validate/finalize、PDF、
领域 contextual tool、TCAD Effect 与人工审批，可以维持 33 项约束中的唯一权威、不可变谱系、最小
上下文、服务端工具门禁、人工边界、CQRS、外部副作用和恢复语义。

未发现需要为低概率哈希冲突、历史 YAML、旧插件消费者或旧孤立 binding 增加在线兼容与新校验。

## 6. 复审通过的最小条件

只需修订计划文件，不得提前实施 H3-A。复审通过条件为：

1. 补齐 `write_result_file`、死活动名和三个真实测试消费者；
2. 精确列出待删协议模型并保留 `NamedInput`/`PdfInput`；
3. 把 proxy 步骤限定为只删除旧 finalize 终态识别，保留当前 claim/validate 续租行为；
4. 冻结 PDF/普通/handoff-only 三类 `access_modes` 总函数；
5. 把旧孤立 binding 验收限定为生产 current 路径不可达，不新增全局启动校验、迁移器或状态；
6. 继续保持生产净删除、每段独立审查和不兼容历史文件的明确取舍。

完成这些最小修订后，H3 的方案可再次提交独立审查；本报告当前不放行 H3-A。
