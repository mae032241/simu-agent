# R5-D2 Task 职责拆分独立审查

日期：2026-08-29  
审查性质：未参与实现的跨边界、简化性与变更范围审查  
结论：**通过**  
门禁决定：**只放行 D3，不提前放行 D4、R5-D 总审或 R5-E**

## 1. 审查范围

本轮只审查 `TaskService` 的职责拆分：生命周期本体、共享不可变合同、Worker 受控文件与封存、
证据输入以及 compiled output。审查没有修改生产代码、测试、计划或阶段状态；唯一写入是本报告。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行，覆盖源码入口、MRO/导入图、Root/Worker 消费者、TCAD runtime
窄访问、clean-wheel 测试及三重复杂度口径。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 权威计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；使用第 3 节、第 8.2 节和 R5-D 复杂度门。 |
| S2 | 当前架构 `docs/ARCHITECTURE.zh-CN.md`，SHA-256 `570d811adb87a7add86bc85057fba5214145f215bc58f95845c7ce20b8a0dfad`；最小重构权威 `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`，SHA-256 `77bb5c36ee71a683b0ffed5adec55968ba0be35d88af5ff0af5f2d7d951b0494`。 |
| S3 | 五个 Task 生产模块：`tasks.py`（`0772d1ea...`）、`task_shared.py`（`9a9f31cf...`）、`task_worker_files.py`（`9d217853...`）、`task_evidence.py`（`59319d43...`）、`task_outputs.py`（`c2f66fa3...`）。 |
| S4 | Root Task 路由、Worker Router、`plugins/tcad_artifact/tcad_artifact/runtime_plugin.py` 及其 `TCADTaskAttemptAccess` 生产消费者。 |
| S5 | 当前计量脚本 `scripts/r5_current_metrics.py`，SHA-256 `d0dac669f8b5f2ccf90bd9007f4d937b8356db8ee75eb7fcb5004a02b64b6266`；本轮输出 SHA-256 `f011f462b06185f7e474626973bc870796d2b44780dc157d55d5d4b204a8028e`。 |
| S6 | 冻结生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；冻结快照 SHA-256 `1b397e2dfea1bc579b2597caf5d3a37f5ef44e40d66b92f509b349b51b77983a`。 |
| S7 | D2 结构门 `tests/operations/test_r5_task_responsibility_split.py`，SHA-256 `2de1626ce6ffa3ee89bf8c540f8332a9363b7fc5a8c81cde5c240643ab92a04f`；精确派发、Worker 权限、Agent 合同、TCAD 恢复和通用科学 Agent 测试。 |
| S8 | 实施记录 `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`，SHA-256 `14831b5608c02cac770ad3bc38d85559755c76c7883fa2c5a14238666dab76d6`。 |
| S9 | 本轮独立命令记录：29 项聚焦测试、277 项全仓测试、五模块编译、未解析全局符号检查、生产导入/计量检查与 `git diff --check`。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `single_task_authority` | pass | S1—S4, S7, S9 | 只有 `TaskService` 构造 Artifact、Token、SQLite、Catalog 与 workspace root 依赖并建表；三个混入没有构造器、服务实例、连接副本、缓存、目录权威、注册表或状态机。 |
| `method_and_import_ownership` | pass | S3, S7, S9 | 生命周期本体 40、Worker 文件 30、证据 8、compiled output 24 个非构造方法，集合无重名；MRO 精确，模块导入图无环，五模块无未解析全局符号。 |
| `worker_file_boundary` | pass | S2—S4, S7, S9 | 文件读写、patch、JSON patch、集合、checkpoint、验证与 sealed finalize 均先校验精确 session/attempt；路径、符号链接、普通文件、单项与总字节上限继续失败关闭，原 CAS/事务和终态登记未复制。 |
| `evidence_boundary` | pass | S2—S4, S7, S9 | handoff-only 输入仍不可读；PDF cache/excerpt 绑定原 PDF、抽取 profile 与父链；Web 响应、文本和 snapshot 仍按任务尝试冻结，最终证据引用只接受精确本地输入或该尝试的 snapshot。 |
| `compiled_output_and_lineage` | pass | S2—S4, S7, S9 | 当前 operation id/version/digest、compiled output/validator/context/collection 合同和 revision scope 仍在同一终结路径复核；主输出、集合、SchedulerSignal 及父链继续由原 Artifact/Task 权威登记。 |
| `recovery_and_tcad_hook` | pass | S3, S4, S7, S9 | TCAD 插件仍只持有 `TCADTaskAttemptAccess`，其底层是同一 `TaskService`；`AgentTask`、`_WorkspaceSnapshotFile`、`_write_control_output_file` 等既有显式导入可达，未生成第二调试状态或兼容执行面。 |
| `real_entries_and_clean_wheel` | pass | S4, S7, S9 | Root Task 路由与 Worker Router 继续调用同一个对象；clean-wheel Agent/Worker authority、handoff 拒绝以及全仓安装态路径均通过。 |
| `domain_neutrality` | pass | S1—S4, S9 | 五个通用 Task 模块无 TCAD、设备参数、curve-score、InGaAs 或 Fig.4 分派/标识；领域调试实现仍在 TCAD 插件。 |
| `complexity_and_occam` | pass | S1, S3, S5, S6, S8, S9 | Task 职责真实聚合为 6218/6077（+141），R0 六职责 9776/13657，全生产 60440/62533，operations 包 2056/2060；16 个 R0 successor 全局唯一，没有以拆文件冒充减重。 |
| `constraints_and_goal` | pass | S1—S4, S7, S9 | 身份、谱系、最小 Worker 上下文、人工审批、唯一 Execution、单 compiled catalog、插件隔离和失败恢复未退化；没有新增领域流程、数据库表、顶层权威或科研实体。 |

## 3. 结构与运行边界判断

### 3.1 一个对象、一个状态权威

当前不是四个相互协调的 Task 服务，而是一个 `TaskService` 对象加三个无状态方法集合。SQLite
连接构造、全部表定义、Artifact/Token/Catalog 引用、workspace root 和任务生命周期状态仍只在
主类中。混入通过同一个 `self` 调用 `_connect()`、ArtifactService 和 TokenService；这会参与原
事务，但不会复制连接所有权或建立第二份状态。

导入方向为：

```text
tasks -> evidence, worker_files, outputs, shared
evidence -> shared
worker_files -> shared
outputs -> worker_files, shared
```

没有子模块反向导入 `tasks`，也没有运行时服务定位器。`outputs -> worker_files` 只复用普通文件读取、
bundle 路径检查和原子控制写入等同一文件协议辅助；跨混入的 `self` 调用全部落在唯一
`TaskService` MRO 中，并由方法集合无重名门防止隐式覆盖，因此不是第二执行路径。

### 3.2 权限、证据与终结链

Worker Router 仍从 compiled Operation 得到允许工具，再把精确 session token 交给同一个
TaskService。Worker 文件方法没有绕过 active claim；验证成功后冻结精确 bytes，进入短暂
`finalizing`，最终化再次验证 sealed manifest 与当前 compiled contract，才登记主输出、集合与
SchedulerSignal。验证拒绝、尝试到期、finalization grace 到期、retry 和恢复仍使用原任务行与
assignment instance，没有新状态镜像。

证据混入保留了与文件协议不同的变化原因：只读输入 exposure、PDF 全文 cache/有界 excerpt、Web
snapshot 和来源清单。compiled output 混入只负责 Operation 合同、role envelope、context/collection
validator、revision scope、Artifact 封存和最终谱系。主类保留少量跨生命周期的只读输出合同、审查
绑定和 SchedulerSignal 查询；它们读取原完成态，不形成新的输出存储或资格权威。为追求“纯度”再
迁移这些窄查询会增加互调，而不会删除状态，因此本轮不要求继续拆分。

### 3.3 旧导出与插件边界

生产消费者的显式导入均实际成功：service 包继续导出 Task 错误和 `TaskService`；Root、Worker、
instance/orphan 管理与 dispatcher 不需改调用面；TCAD runtime 仍能从原 Task 模块显式取得其现有
窄类型和控制写入辅助。该转发只保留 Python 符号身份，没有新对象、条件分派或持久状态，不能调用
出另一条 Task 生命周期，因而不构成禁止的兼容 facade。

## 4. 复杂度与奥卡姆判断

五文件总量由拆分前 6077 行变为 6218 行，净增 141 行，约为原职责的 2.3%。新增成本主要是独立
模块导入、共享不可变合同和三个类边界；运行时对象数、表、状态转换和注册入口均未增加。换来的
边界对应真实独立变化：文件安全协议、证据取得、compiled output 合同和任务生命周期。

`task_worker_files.py` 仍有 2433 行，但其纯 patch/file 辅助、受控 workspace、snapshot、sealed
finalize 与分析输出共同保护同一个“Worker 只能通过任务文件协议改变候选 bytes”的不变量。继续
按行数拆成 repository/service/factory 会扩大跨文件协议面，不符合当前计划的奥卡姆约束。因此
+141 行可接受，不能把 `tasks.py` 单文件降到 1876 行单独宣称为减重；权威口径应继续使用 6218、
9776 和 60440。

## 5. 独立运行记录

全部命令在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

```text
pytest -q \
  tests/operations/test_r5_task_responsibility_split.py \
  tests/operations/test_worker_exact_dispatch.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_worker_authority.py \
  tests/operations/test_r3_agent_contract.py \
  tests/operations/test_r5_tcad_debug_ownership.py \
  tests/operations/test_general_science_plugin.py
# 29 passed in 36.70s

pytest -q
# 277 passed in 93.14s

PYTHONPATH=src python -m py_compile <五个 Task 模块>
# 通过

python <symtable 未解析全局符号检查>
# 五模块均通过

PYTHONPATH=src:plugins/tcad_artifact python <旧显式导出与 TCAD runtime 导入检查>
# 通过

PYTHONPATH=scripts python <R0 successor 唯一性与当前计量重算>
# 16 个 successor 全局唯一；9776 / 13657

git diff --check
# 通过
```

未运行真实 Sentaurus、浏览器点击或公网抓取，因为 D2 没有修改 solver adapter、人工决定写入或网络
获取算法；这些未来观测不是当前 Task 机械拆分的失败条件。

## 6. 最终结论

未发现阻断缺陷。D2 保留了唯一 Task/数据库/事务/生命周期权威，三个混入具有真实且可验证的变化
原因，文件、证据、compiled output、谱系、恢复、TCAD 窄访问和 clean-wheel 路径均未退化；+141
行没有形成复杂度反噬。

**结论：通过。只放行 D3。**

