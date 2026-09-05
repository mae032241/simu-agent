# R5-H H3 重复状态与隐藏兼容面删除计划

日期：2026-08-30  
状态：H3-A/H3-B/H3-C/H3-D 均通过独立审查；H3 完成  
前置门：H2b 第五轮独立审查已通过  
目标：只做减法，不增加兼容层、控制状态或入口校验

## 1. 要解决的问题

当前主路径已经统一为：数据库中的 ResearchInstance/语义绑定、启动时编译的单一 OperationCatalog、
`worker_materialize_assignment` 和受控文件封存生命周期。但源码仍保留三组会让读者和插件误判权威的
旧表面：

1. 468 行 `research_state.py` 和安装器对 `research/current.yaml` 的条件校验，形成数据库之外的第二套
   current 叙事；
2. 12 个 `_LEGACY_WORKER_TOOLS`、对应路由和三组旧服务方法，允许插件继续选择内联读写/提交协议；
3. `builtin_plugin.PLUGIN` 别名和启动时把孤立 binding 合成为 `legacy.*` instance 的历史迁移。

H3 不设计新的状态模型，只删除已经没有生产必要性的旧权威和旁路，使失败直接表现为“未知工具”或
“旧状态不受支持”。

## 2. 现状消费者冻结

| 表面 | 当前生产消费者 | 当前测试/部署消费者 | 处理 |
| --- | --- | --- | --- |
| `research_state.py` | 无运行时 import | `deploy/install.sh` 在文件存在时调用 | 删除模块和安装条件分支；不创建离线兼容器 |
| PyYAML 运行依赖 | 仅 `research_state.py` | 33项约束 YAML 测试 | 从运行依赖、安装探针和 runtime identity 删除；只放入 test extra |
| `worker_read_input` | builtin 架构夹具和 TCAD author/reviewer 显式注册 | `test_r5_worker_router_split.py`、`test_catalog_compile.py`、`test_baseline_worker_authority.py` 仍冻结导出/目录/拒绝行为 | 两个 Operation 改用已存在的 materialized native read；三个测试改为当前协议正例和旧名 unknown 负例；删除组件和路由 |
| 其余11个 legacy Worker 工具 | 无 OperationSpec 注册 | 无精确工具名调用 | 直接删除协议声明和路由 |
| inline upload/write/validate/finalize 六个服务方法 | `begin/append/commit_result_upload`、`write_result_file`、inline `validate_output`、inline `finalize` 只被 legacy Worker 路由调用 | 无直接调用 | 连同路由删除；保留 file write/validate/finalize |
| 旧 Worker 活动名 | `assignment_read`、`inputs_listed`、`input_read`、`input_staged`、`table_read`、`input_profiled`、`output_written` 只由待删路由写入 | 无当前协议消费者 | 从允许集合删除；保留 `output_validated` 等当前活动 |
| `TaskService.read_input` | 注册领域工具的 `WorkerTaskAccess` 使用 | 多个真实领域工具测试 | 保留，不把服务内部读取误删为 Worker 公开工具 |
| `TaskService.stage_input` | PDF 提取缓存路径使用 | PDF 测试 | 保留；只删除公开 legacy `worker_stage_input` |
| `builtin_plugin.PLUGIN` | 无 | 无 | 删除别名；entry point 继续指向 `CORE_PLUGIN` |
| 孤立 binding→`legacy.*` instance | 只在数据库初始化执行 | 无精确测试 | 删除自动合成；不删除其他当前 Schema 初始化/迁移 |

历史计划、审查报告和用户工作区只作为历史证据保留，不批量改写或删除。已存在的
`research/current.yaml` 也不由安装器删除；新版本只是不再读取它。

## 3. 不可退化边界

- 一个 `scidiscovery.plugins` 入口组和一个 `CompiledCatalog`；
- Artifact、Task、Approval、Execution、ResearchInstance 与 scheduler binding 的当前持久化语义不变；
- handoff-only 输入仍不产生文件路径，普通输入只在当前 task workspace 中只读物化；
- Worker 仍只能调用所选 Operation 编译授权的当前工具；未知/已删除工具必须在服务端拒绝；
- primary 和 collection 只经 `worker_file_*`、`worker_validate_output_file`、
  `worker_finalize_file` 封存；
- 领域 contextual handler 仍可通过受限 `WorkerTaskAccess.read_input` 读取精确绑定字节；该能力不是
  Agent 可直接调用的 MCP；
- 不修改外部 TCAD Effect、审批语义或调度 Agent 的科学判断。

## 4. 明确不做

- 不新增 `CurrentState`、迁移状态、兼容模式、版本协商、旧工具转发器或 tombstone Registry；
- 不把12个旧工具改名后继续保留；
- 不删除 `worker_run_analysis`、PDF 提取、网页证据或 Operation 注册领域工具等当前能力；
- 不因为看见其他文件中的 `legacy` 字样，就扩大到曲线源格式、TCAD runner wire contract 或业务枚举；
- 不删除用户的 YAML、SQLite、CAS、历史终态或 deliverables；
- 不为“可能有人还在用”保留在线兼容。若出现真实必要历史输入，另做发布包外、一次性、只读工具，
  不能重新接入运行时。

## 5. 分阶段实现

### H3-A：删除 YAML current 权威

1. 删除 `src/scidiscovery/research_state.py`；
2. 删除 `deploy/install.sh` 对 `research/current.yaml` 的探测和调用；
3. 从基础运行依赖、安装 Python 版本探针和 `runtime_identity.TRACKED_DISTRIBUTIONS` 删除 PyYAML；
4. 把 PyYAML 只加入 `[project.optional-dependencies].test`，保留 33 项约束测试读取
   `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
5. 增加静态负例：生产/部署/基础 entry point 不再引用 `research_state`、`current.yaml` 或 PyYAML；
6. 在没有 system site packages、确认 `find_spec("yaml") is None` 的干净 base-wheel 环境中验证：无需
   PyYAML 即可编译目录、打开/重开当前格式数据库并读取终态。

H3-A 独立审查通过前，不删除 Worker 兼容面。

### H3-B：删除隐藏 Worker 协议

1. builtin 架构夹具删除 `input_read_tool`，prompt 改为只读取
   `worker_materialize_assignment` 返回的 `assignment.json` 和声明的普通输入文件；
2. TCAD author/reviewer 删除同一 `input_read_tool` 组件和工具引用，继续使用已有 workspace
   materializer 与 native read；不新增 TCAD 读取工具；
3. assignment 的 `access_modes` 是一个机械总函数：非 handoff-only 一律含 `native_read`；只有媒体
   类型为 `application/pdf` 且精确 Operation 授权 `worker_extract_pdf_text` 时再追加
   `extract_pdf_text`；handoff-only 始终为空且无 `relative_path`，即使 Operation 拥有 PDF 工具。
   删除 `controlled_read` 枚举，不增加媒体注册表或入口检查；
4. 删除 `_LEGACY_WORKER_TOOLS`、`ReadInput`、`TableInput`、`ProfileInput`、
   `ValidateOutputInput`、`FinalizeInput`、`ResultUploadChunk`、旧 capability 映射、`READ_INPUT_TOOL`
   导出，以及 Worker router 对 legacy 集合的装载；明确保留当前 `NamedInput` 和其子类 `PdfInput`；
5. 删除 dispatch 中12个旧分支及只为旧表格/profile 分支存在的 helper/import。proxy 保留
   `worker_claim_task` 启动续租和 `worker_validate_output_file` 成功停止/失败重启续租；终态观察只从
   `{worker_finalize, worker_finalize_file}` 删除旧 `worker_finalize`，继续以
   `worker_finalize_file` 为唯一完成工具；
6. 删除只被旧路由消费的 `begin/append/commit_result_upload`、`write_result_file`、inline
   `validate_output` 和 inline `finalize`；删除只由旧路由写入的 `assignment_read`、`inputs_listed`、
   `input_read`、`input_staged`、`table_read`、`input_profiled`、`output_written` 活动允许值。保留
   `read_input`、`stage_input`、`output_validated` 及全部当前 file lifecycle 方法/活动；
7. 结构负例逐一实调12个旧名，全部返回 unknown tool；静态负例确认上述六个服务方法、七个活动名和
   旧协议模型均消失；正例覆盖 materialize→native read→
   file create/patch→validate file→finalize file，以及 TCAD 注册调试工具真实调用。
8. 增加 proxy 聚焦回归：claim 后续租启动、file validation 失败后可修订并继续续租、成功验证停止
   续租、`worker_finalize_file` 完成；不为旧 `worker_finalize` 保留观察分支。

H3-B 不新增工具注册字段、服务 facade 或适配器。独立审查通过前不进入 H3-C。

### H3-C：删除零消费者别名和历史合成

1. 删除 `builtin_plugin.PLUGIN = CORE_PLUGIN`；基础 entry point 和所有生产 import 继续使用
   `CORE_PLUGIN`；
2. 删除 scheduler bindings 初始化时扫描孤立 binding 并合成 closed `legacy.*` instance 的块；
3. 不删除当前表创建、当前字段补齐或当前请求指纹校验；不借 H3 清理其他业务兼容枚举；
4. 用当前格式数据库完成：创建 instance、绑定 Artifact/Task/Approval/Execution、形成一个 completed
   终态、关闭并重开 runtime、读取同一终态；
5. 构造含孤立旧 binding 的数据库后打开 runtime，确认 `list_instances` 和 session-binding candidates
   不出现伪实例，`session_instance` 不返回孤立 id，`get_instance` 对该 id 报 unknown。原始旧行可
   保持只读、不可达；不承诺底层任意 `resolve(old_id)` 都拒绝，也不增加启动扫描、全局入口校验或
   迁移器。

H3-C 独立审查通过后才进行 H3-D 总收口。

### H3-D：安装、重启、文档和总审查

1. 跑 base/curve/table/TCAD/full 干净 wheel 组合，确认单一 entry point 和 Operation 工具集合；
2. 跑 Worker 进程、Root/Task、资格、审批、Execution、重启恢复和部署/平台回归；
3. 更新中英文架构、安装、Worker 协议和插件 README，只描述当前文件协议；历史审查报告不改写；
4. 更新规模哨兵和发布 manifest；记录生产净删除，不把测试迁移计为控制面减重；
5. 全量 `tests/operations`、部署/平台、`git diff --check`、旧名静态负扫描全部通过；
6. 新的独立审查者确认唯一 current、唯一 Worker 文件协议、无转发器和无设计目标偏移后，H3 才通过。

## 6. 验收矩阵

| 场景 | 必须成立 |
| --- | --- |
| 普通 Agent 输入 | materialize 后有任务内只读相对路径，`access_modes=[native_read]` |
| handoff-only 输入 | 只有有界调度信号，无路径，`access_modes=[]` |
| PDF Agent | 原始 PDF 可 native read；仅注册 PDF 工具时可产生冻结文本摘录 |
| TCAD author/reviewer | 无 `worker_read_input`，仍能读取 materialized/workspace 文件并调用注册调试工具 |
| 旧12工具 | `list_tools` 不出现且直接调用均 unknown tool |
| 正式输出 | 只有 file create/patch + validate file + finalize file 可完成 |
| current | 数据库/instance binding 是唯一运行时权威；安装器不读取 YAML |
| 旧 YAML | 文件不删除、不读取、不影响安装结果 |
| 当前终态重启 | 重开后 completed/closed/current binding 保持可读 |
| 旧孤立 binding | 不自动合成 `legacy.*` instance；生产 current 列表/session/get 入口均不可达，不新增全局校验 |

## 7. 复杂度预算与停止条件

- 生产 Python 与 shell 必须净删除；若某子阶段生产行数净增加，必须打回重新设计；
- 不允许新增生产文件、数据库表/列、OperationSpec 字段、Registry、状态值或路由器；
- 测试可增加精确负例和当前协议正例，但不得保留两套测试基座；
- 任一真实领域工具依赖 legacy MCP 时，先迁移到现有 materialized workspace 或 contextual
  `WorkerTaskAccess`，不得恢复全局 legacy 集合；
- 若删除导致当前格式终态不可读取，修复当前持久化实现；不得以恢复旧 YAML current 或自动合成
  legacy instance 解决。

## 8. 状态门

当前只批准把本文件交给独立方案审查。方案审查未通过则只修改本计划，不执行 H3-A；方案通过后按
H3-A→H3-B→H3-C→H3-D 顺序执行，每个子阶段分别独立审查，未通过不得进入下一阶段。

首轮独立方案审查见
`reviews/R5_H3_LEGACY_SURFACE_DELETION_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，主代理对报告最终字节
计算的 SHA-256 为 `a60f638b13a650c2f9509e775bbcbaed40ee970ccec7de28dd33bc91d81737db`，结论“打回”。
本修订只补齐六个旧服务方法、七个死活动名、精确协议模型、proxy 当前续租、三类 access mode 和
生产 current 不可达验收；没有扩大实现范围。第二轮方案审查通过前仍不执行 H3-A。

第二轮方案审查见
`reviews/R5_H3_LEGACY_SURFACE_DELETION_PLAN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，主代理对报告最终
字节计算的 SHA-256 为 `421f888982c90b483b818bde5c0378b3a4af49907216dbf178596ca02ace698a`，
结论“通过”，只放行 H3-A。

## 9. H3-A 候选实施记录

- 已删除 468 行 `src/scidiscovery/research_state.py` 和安装器对 `research/current.yaml` 的条件读取；
  用户已有 YAML 不删除、不迁移，运行时不再把它解释为 current；
- PyYAML 已从基础运行依赖、安装前版本探针和 runtime identity 移除，只保留在 test extra 供33项
  约束 YAML 测试使用；中英文安装依赖说明已同步；
- 安装测试新增 `core_no_yaml` 环境：venv 不继承 system site packages，只复制当前 Pydantic/Pillow
  运行依赖，确认 `find_spec("yaml") is None`。该环境完成基础目录编译、runtime 打开、instance 关闭、
  同状态根重开和 closed 终态读取；
- `tests/operations` 309项全部通过，用时108.51秒；部署、平台与约束矩阵38项通过；独立安装文件
  6项通过；`git diff --check` 通过；
- 生产 Python 从151个文件/60177行下降为150个文件/59709行；Task 与 Operation 包规模不变。没有
  新生产文件、Schema、入口、状态、注册表或兼容器；
- 静态扫描确认 `src`、`deploy`、基础 entry point、当前安装文档均无 `research_state`、
  `research/current.yaml` 或运行时 PyYAML 引用；仅 `pyproject.toml` 的 test extra 保留 PyYAML。

H3-A 首轮实现审查因两处当前文档事实未同步而打回；最小修复后，独立复审见
`reviews/R5_H3_A_YAML_CURRENT_REMOVAL_INDEPENDENT_REREVIEW.zh-CN.md`，主代理核验报告 SHA-256 为
`e2dfb7d03fa11a6caf4c25685c851e66788b52625480554f919e8d0136d0983a`，结论“通过”，只放行 H3-B。
旧 Worker 工具与路由在 H3-A 候选中保持原状，现按既定边界进入 H3-B。

## 10. H3-B 候选实施记录

- builtin 架构夹具与 TCAD author/reviewer 已删除 `input_read_tool` 组件和工具引用，继续使用既有
  `worker_materialize_assignment` 物化的任务内只读文件；未新增读取工具、适配器或入口判断；
- assignment 投影现在是单一机械规则：普通输入为 `native_read`；精确 Operation 同时授权 PDF 工具
  的 PDF 输入再追加 `extract_pdf_text`；handoff-only 始终无路径且 `access_modes=[]`。已删除
  `controlled_read` 枚举；
- 已删除12个 legacy Worker 工具、六个旧输入模型、旧 capability 映射、全部对应 dispatch 分支、
  表格/profile helper、六个无消费者服务方法和七个旧活动名；proxy 只观察当前 file validate/finalize
  生命周期；
- 结构负例逐一实调12个旧工具名，均返回 `unknown worker tool`；普通、PDF、handoff-only 三类输入
  投影、file lifecycle 失败后续租恢复、成功校验与 finalize、TCAD 注册调试工具真实调用均有聚焦正例；
- `tests/operations` 311项全部通过，用时107.63秒；部署、平台与33项约束38项通过；TCAD author
  注册调试工具聚焦用例通过；`compileall`、生产旧名静态负扫描和 `git diff --check` 通过；
- 生产 Python 从 H3-A 的150个文件/59709行下降为150个文件/59162行，净删547行；Worker 路由三文件
  从1172行下降为810行，Task 责任聚合从6205行下降为6031行。没有新增生产文件、数据库表/列、
  OperationSpec 字段、Registry、状态、路由器或入口校验。

H3-B 独立审查见
`reviews/R5_H3_B_HIDDEN_WORKER_PROTOCOL_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告
SHA-256 为 `c6726136b932e7fb62cd6ef9e3d5dc39c469dce8734efe0741816b65c4c3b074`，结论“通过”，
只放行 H3-C。现按既定边界进入 H3-C，H3-D 仍未放行。

## 11. H3-C 候选实施记录

- 已删除 `builtin_plugin.PLUGIN = CORE_PLUGIN` 及其历史 editable 环境说明；基础发布 entry point 和
  全部生产消费者继续显式使用 `CORE_PLUGIN`，干净 core wheel 证明模块不再暴露旧别名；
- 已删除初始化时扫描孤立 `scheduler_bindings` 并合成 closed `legacy.*` instance 的整块逻辑；没有
  新增启动扫描、迁移器、旧行删除、版本判断或入口校验；
- 精确旧库负例保留一条孤立 binding 与孤立 session 原始行，重开后实例列表、`session_instance`、
  session-binding candidates 和 `get_instance` 均不能把它解释成 current instance；原始 binding 行
  仍在数据库中，证明不是通过破坏性清理获得通过；
- 当前格式正例真实完成 Artifact、Task、Approval、Execution 四类绑定及一个 completed Agent task，
  关闭实例并重开同一 state root 后，closed 实例、completed 终态和四类绑定均保持可读；
- `tests/operations` 312项全部通过，用时108.11秒；部署、平台与33项约束38项通过；两个 installed
  wheel 正例和孤立旧 binding 负例聚焦通过；生产旧合成文案/别名静态扫描与 `git diff --check` 通过；
- 生产 Python 从 H3-B 的150个文件/59162行下降为150个文件/59128行，净删34行。没有新增生产文件、
  数据库表/列、OperationSpec 字段、Registry、状态、路由器、facade、兼容器或入口校验。

H3-C 独立审查见
`reviews/R5_H3_C_LEGACY_SYNTHESIS_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告 SHA-256 为
`32db09cce58531a8715056e3f2a358af33a987c8fddcab5abcfe9ed103fcfbee`，结论“通过”，只放行 H3-D。
现进入安装、重启、文档、manifest 与总回归收口，H3 尚未整体通过。

## 12. H3-D 候选实施记录

- 在干净 wheel 环境中复核 core、无 PyYAML core、curve、table、TCAD、full 等安装组合及真实
  Operation 生命周期，24 项全部通过；覆盖单一插件入口、目录编译、Agent/Transform/Effect、TCAD
  注册调试工具、审批、Execution 与关闭重开；
- 最终 `tests/operations` 312 项全部通过，用时111.43秒；部署、平台与33项约束38项全部通过，
  用时6.01秒；`git diff --check` 和生产旧名静态负扫描通过；
- 中英文架构、安装和 TCAD 插件说明以及当前 Worker 文件协议已同步：普通输入只读物化，PDF 可按
  Operation 授权提取，handoff-only 不暴露路径，12个旧内联工具均为未知工具；
- 生产 Python 保持150个文件/59128行；Worker 三文件810行，Task 实现6031行。H3-D 没有新增生产
  代码、状态、注册表、OperationSpec 字段、入口校验或兼容层；
- 发布清单由当前源码机械生成并校验，不在控制面增加发布状态或运行时判断。

本候选只完成收口证据，不自行宣称 H3 通过。新的独立审查者必须同时确认唯一 current、唯一 Worker
文件协议、安装与重启可用、发布清单一致，以及没有因收口重新引入过度入口校验，才可放行 H3。

H3-D 与 H3 总闭合独立审查见
`reviews/R5_H3_D_RELEASE_AND_TOTAL_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告 SHA-256 为
`fa147f1c78a92030224be8a4a348b649bbcea08c1816da20cc50b78a85fa5ccf`，结论“通过”，阻断项为零。
审查确认 H3 没有新增入口校验、状态、注册表、OperationSpec 字段或兼容层；H3 至此完成，只放行 H4。
