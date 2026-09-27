# R5-L L1 实现第二轮独立复审

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与 L1 实现或返修）  
结论：**通过；只放行 L2，不授权 L3—L6**

## 1. 本轮绑定范围

本轮重新审查当前文件，不继承首轮“不通过”结论。候选摘要为：

- 活动计划 `R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md`：
  `2672948e07d1819776c080e1673f16f0f5e89e66c1b0ec19e600e6de2dc18004`；
- L1 证据 `R5_L1_MINIMAL_PROJECTION_AND_BLIND_PLUGIN.zh-CN.md`：
  `db16434d37c1d73df1feb6fd03e914f93381b0bc7ce9ed8d7429b0f9ecf5f172`；
- 首轮报告 `R5_L1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`：
  `f4b25a08b46b74703a2ef296a08da3c53078f61b39ee201f7c490995ed2e30fc`；
- L1 聚焦测试：
  `d0c3754765c4f73b8ce40fc98e84a974dd0211fcda177e559a3b0b87877869e9`；
- blind CSV 注册文件：
  `1bb215397bb8916051a5726f3d6eaae168ec88f18a90008b23d5d9de18b7270f`；
- blind CSV 工具文件：
  `385aa96a17ce94aa08bbcdffceb631d7670bd6696519e3953fbbe44e5a60e2be`。

相对 L0 的 209 项生产终点，仍只有根 `pyproject.toml` 的测试路径以及
`operations/__init__.py`、`operations/catalog.py`、`operations/spec.py` 四项变化。返修没有修改
Task/Worker 服务、部署、UI、调度器或产品插件。

## 2. 首轮阻断闭合情况

### 2.1 自定义领域 activity 已删除，未向核心迁移复杂度

当前 `blind_csv_plugin/worker_tool.py::summarize` 只做两件事：按科学别名 `source_table` 读取精确输入，
调用领域确定性函数 `summarize_csv`。它不再调用 `context.task.record_activity`。

独立核验结果：

- 生产树和盲插件中均不存在 `blind_csv_summary_completed`；
- `src/scidiscovery` 中不存在 `blind_csv` 或 `blind.csv` 名称分支；
- `TaskService.record_activity` 当前摘要为
  `25da6d1cbbc66c6616bccb197ea8e57794b06bf0e44aa2f20eb6726334890956`，与 L0 终点清单完全相同；
- 没有新增 activity 表、插件 activity 注册接口、兼容转发或测试专用生产分支；
- Router 仍以通用事实 `operation_tool_succeeded:worker_csv_summarize` 记录工具成功，不要求核心认识
  CSV 领域。

因此，首轮真实 Worker 调用失败已经通过删除无独立事实的重复 activity 闭合，而不是通过扩充控制层
白名单打补丁。这符合奥卡姆原则和 `AUTH-003/PLG-001`。

### 2.2 CSV 的科学用途已按端口分开

`blind_csv_plugin/plugin.py::_input` 现在允许调用点显式指定 usage：

- 作者的 `source_table`：`claim_evidence`；
- reviewer 的 `source_table`：复用同一 TABLE，仍为 `claim_evidence`；
- reviewer 的 `csv_observation`：默认且显式物化为 `prior_signal`。

这与共同角色合同一致：原始数据可以支持本次观察和审查，作者产出的待审对象只是精确 review
subject，不能凭自身成为 claim evidence。返修没有增加资格、cohort、approval 或 Evidence 状态。

真实 materialized assignment 已直接断言上述三个端口用途，首轮认识论冲突已关闭。

## 3. 真实作者路径和篡改负例

新增聚焦测试实际执行完整旧加固控制路径，而非直接调用 handler：

```text
Root operation_invoke(blind.csv.observe.v1, 精确 CSV Artifact)
→ prepare_exact_dispatch
→ WorkerMCPRouter.worker_open_assignment
→ worker_csv_summarize
→ 服务端文件创建
→ 第一次 worker_submit_result
→ 正式 Artifact 与 completed Task
```

独立运行确认：

- assignment 只含绑定的 `source_table`，usage 为 `claim_evidence`；
- `worker_csv_summarize` 通过真实 `WorkerTaskAccess.read_input` 读取该绑定字节；
- Worker 只留下通用 registered-tool success 收据；
- 作者第一次 submit 即返回 `completed/valid=true`，Root `task_status` 也为 completed；
- 输出 Artifact 的结构、源 SHA、行列和均值由 contextual validator 对照精确 CSV 重新计算。

同一测试另外创建第二个真实作者任务，把另一份 CSV 的结构写入本任务输出。`worker_submit_result`
返回 `rejected/valid=false`，证明拒绝发生在真实提交与实际 task inputs 上，不是直接调用 validator 的
假阳性。

## 4. reviewer 独立性和精确绑定

作者完成后，测试通过 Root 正式调用 `blind.csv.review.v1`，同时绑定原始 CSV 和作者的正式输出
Artifact。独立核验确认：

- reviewer Operation 使用不同 Agent 组件和不同编译 Agent 身份；
- reviewer assignment 中原 CSV 为 `claim_evidence`、作者输出为 `prior_signal`；
- reviewer 的 Worker 工具列表不含 `worker_csv_summarize`，实际调用得到 `unknown worker tool`；
- reviewer contextual validator 同时验证作者观察结构仍对应原 CSV，并验证 `subject_sha256` 对应作者
  Artifact 的精确 canonical bytes；
- reviewer 第一次 submit 完成；
- `TaskService.is_exact_reviewer_output` 对 reviewer operation、reviewer input port、accepted verdict 和
  作者精确 Artifact ref 的组合返回真。

因此 reviewer 不是同一作者工具权限的复用，也不是只在 `ReviewSpec` 中存在的纸面边；L1 所要求的
真实控制边已闭合。L1 仍未启动真实 Codex，模型独立运行属于 L2/L3 的后续门，当前报告不外推。

## 5. clean wheel、插件成本和唯一投影

### 5.1 clean wheel

安装测试继续从仓库外工作目录运行，清除 `PYTHONPATH`，并断言 core 与 blind CSV 包均来自 venv
prefix。唯一 `scidiscovery.plugins` entry point 能发现两个 Operation，编译目录能生成相同 Operation
digest 和 runtime projection，安装态领域 handler 能读取绑定接口并计算预期均值。

这证明 wheel/entry point/依赖发现成立。真实 Worker 路径由源码态精确 Task 测试证明；真实 Codex
进程仍是 L2 完成门。

### 5.2 接入成本

独立按证据声明的四个注册与胶水文件复算：

| 文件 | 物理行 |
| --- | ---: |
| `plugin.py` | 195 |
| `worker_tool.py` | 33 |
| `__init__.py` | 5 |
| `pyproject.toml` | 17 |
| 合计 | **250** |

四文件非空非注释行合计 **221**。`contracts.py` 为 111 行领域数据模型、CSV 算法和两个与输入字节
绑定的 validator，未将注册表或框架 glue 移藏其中。插件仍只注册 13 个自有组件、两个 Operation，
每个 Operation 可达 14 个组件并复用 6 个公共组件；核心、UI、部署和调度器零领域分支。

250 行刚好达到而没有超过计划门槛，度量口径现已覆盖工具 adapter、包导出和 wheel entry point，
首轮只报 `plugin.py` 的不完整口径已纠正。

### 5.3 唯一 catalog 投影

`RuntimeOperationProjection` 实现未在返修中变化：仍由
`CompiledCatalog.runtime_projection → operation → runtime_operation_projection` 当次派生，无缓存、
持久映射、第二注册或调用入口。对 core/general/curve/TCAD 的 45 个产品 Operation 重新核验：12 条
review、4 个人工合同、15 组 guard、12 组 cohort 和 1 个 Effect 投影均逐项等于唯一
`CompiledOperation` 中的来源合同。

投影仍只是无状态视图，不得在 L2 变成由调用者提交的权限对象，也不得用 cohort 名称摘要代替完整
资格策略。

## 6. L0 防腐、复杂度和 33 项约束

本轮聚焦执行：

1. `pytest -q tests/operations/test_l1_minimal_runtime_projection.py`：
   `6 passed in 39.52s`；覆盖 clean wheel、作者真实 Worker、篡改 submit、reviewer 和成本边界。
2. `pytest -q tests/operations/test_l0_lifecycle_contract.py
   tests/operations/test_worker_exact_dispatch.py`：`21 passed in 10.80s`；三个生命周期、摘要、精确绑定、
   三个真实进程崩溃窗口和 hard deadline 未退化。
3. 45 个产品 Operation 的五类投影一致性检查：通过。
4. L0 209 项清单差异复查：仍只有 L1 既定四项，TaskService 与核心 activity 边界未变化。
5. `git diff --check`：通过。

候选记录的聚焦集合 `105 passed` 和非 live Operation 全集 `300 passed` 本轮没有机械重复；本轮已
运行会对返修语义直接失败的最小集合，首轮阻断也由真实路径而不是测试数量关闭。

约束判断：

- `AUTH-003/ROLE-002`：工具、输入和 reviewer 身份仍由同一编译 Operation 授权；
- `EVD-001/ROLE-001`：原 CSV 是显式 claim evidence，控制层只重算机械结构，不生成 interpretation
  或 reviewer verdict；
- `PLG-001/002`：插件一次入口，核心零 CSV 分支，缺失插件不影响核心；
- `SEC-002/RES-002`：精确 Worker 不见未注册领域工具，L0 session/absolute deadline/恢复防腐不变；
- `IMM-001/002`：作者和 reviewer 输出均为正式不可变 Artifact，审查绑定精确 subject ref；
- `TOP-001/002`：review edge 是声明式数据依赖，没有新增固定阶段调度器；
- `DET-001/002`：CSV 结构/均值由确定性工具生成，科学 interpretation 和 verdict 仍属于两个不同
  Worker 角色。

本轮未发现为通过个别测试增加的生产状态、领域特判、兼容层或第二注册表。返修是删除一项重复行为
并纠正一个端口用途，复杂度方向正确。

## 7. 非阻断项与 L2 边界

1. 当前成本测试仍只自动断言 `plugin.py` 的有效行数，尚未把四文件 250/221 聚合写成自动门；本轮已
   独立复算，证据真实。建议 L2 前将同一聚合算法放入测试，防止以后通过移动文件绕过门槛。
2. `OPERATION_AGENT_PREAMBLE` 仍使用旧的“claim/materialize”和复数
   “validation/finalization tools”措辞。L1 未启动 Codex，不影响本轮程序合同；L2 真实 Agent 前必须
   改成一次 open 和一次 submit，避免模型寻找已撤回工具。
3. clean-wheel 正例仍直接调用安装态 handler，而不是在安装态启动完整 Worker daemon；源码态真实
   Worker 与 L0 安装/daemon 防腐的组合足以支持 L1。L2 必须用安装态或正式生成 profile 的真实 Agent
   补齐最终平台证据。

## 8. 最终结论

**L1 第二轮独立复审通过。首轮两项阻断均已在最小边界内闭合，且未引入新的核心注册表、领域分支、
生产状态或过度设计。只放行 L2。**

本结论不授权 L3—L6，也不宣称 LocalTrustedBackend、最小 Run、真实 Codex Agent、current CAS 或
TCAD 新闭环已经完成。L2 必须按活动计划实现并再次接受独立审查。
