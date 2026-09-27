# R5-L L1 最小运行投影与盲插件证据

日期：2026-08-31  
状态：实现审查候选；不放行 L2

## 1. 本阶段回答的问题

L1 不实现新运行器。它只验证两个高风险前提：

1. 现有 `OperationSpec` 能否从唯一 `CompiledCatalog` 直接导出普通运行所需的最小事实，而不再建
   一份运行注册表；
2. 一个框架事先不知道名称和科学模型的 CSV 领域，能否只安装一个插件，同时得到作者、领域工具、
   文件合同和独立审查边。

## 2. 最小运行投影

`RuntimeOperationProjection` 是从一个 `CompiledOperation` 临时生成的不可变值，不持久化、不注册、
不排序，也不是新授权入口。`CompiledCatalog.runtime_projection(operation_id)` 每次先从唯一目录取得
原编译项，再投影：

- 操作身份、摘要、插件和执行组件；
- 原编译输入、输出、预算和 Agent 权限模板；
- 至多一条独立审查边；
- 可选 guard、资格 cohort、人工决定和 Effect 组件引用。

普通盲插件的可选策略投影全部为空。加固任务协议仍留在旧
`PermissionTemplate` 中防腐，L2 的本地 Run 不消费 token、session、assignment、lease 或
`finalizing`。

`CompiledCatalog.__slots__` 没有运行投影映射；本阶段没有第二目录、第二 preflight 或第二 invoke。
投影只使既有 8 文件 `operations` 包从 L0 的 2180 行变为 2215 行；编译器文件仍为 740 行，且没有
新增运行模块。

## 3. 盲 CSV 插件接入成本

插件位置：`tests/fixtures/plugins/blind_csv_operation_plugin/`。它是外部 wheel 测试夹具，不进入核心
产品包，也没有被加入默认全插件集合。

| 度量 | 结果 |
| --- | --- |
| 注册入口 | 1 个 `scidiscovery.plugins` entry point |
| Operation 数 | 2：作者、独立审查者 |
| `OperationSpec` 总字段 | 11；review/guards 为可选，limits 由声明助手一次构造 |
| 插件自有组件 | 13 |
| 每个 Operation 可达组件引用 | 14 |
| 每个 Operation 复用公共组件 | 6：3 个文件工具、2 个 codec、1 个 workspace |
| 注册与胶水 | `plugin.py`、`worker_tool.py`、`__init__.py`、`pyproject.toml` 合计 250 物理行、221 个非空非注释行 |
| 领域模型和算法 | `contracts.py` 111 行 |
| 领域工具 | `worker_tool.py` 33 行 |
| 首次接入文件 | 5 个插件文件；另有测试、测试路径和安装夹具接线 |
| 核心领域分支 | 0；`src/scidiscovery` 不含 `blind_csv` |
| UI/调度器/部署修改 | 0 |

插件复用 `general_science` 的 JSON/opaque codec 和 workspace，以及 `builtin` 的通用文件工具；没有
重复注册 codec、guard、资格、人工审批或 UI projector。它只注册自身 Schema、机械 validator、
上下文 validator、角色提示、两个角色和一个 CSV 工具，这些都是该能力不能从公共事实推导的内容。

## 4. 已验证行为

- 干净 wheel 环境只安装 core 与盲插件即可通过唯一 entry point 编译；
- 作者 Operation 的投影只包含声明的 CSV 输入、JSON 输出、领域工具和 reviewer edge；
- `worker_csv_summarize` 已经由真实 Root invoke、exact dispatch 和 `WorkerMCPRouter` 从精确绑定的
  CSV 读取字节，返回确定性结构和数值均值；
- 原始 CSV 在作者和 reviewer 中均物化为 `claim_evidence`，作者输出在 reviewer 中保持
  `prior_signal`；
- 真实 submit 的上下文 validator 拒绝把另一份 CSV 的结构冒充当前观察；
- reviewer 使用不同 Agent 组件，真实提交审查结果，并由 `is_exact_reviewer_output` 证明绑定作者的
  精确输出；
- 旧加固路径的生命周期碰撞、摘要传播、精确绑定、跨进程恢复、安装和路径负例继续通过。

L1 首轮独立审查曾以两项阻断打回，报告见
`../reviews/R5_L1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`：直接调用 handler 掩盖了插件自定义
activity 被核心白名单拒绝，以及原始 CSV 被错误标为 `prior_signal`。返修删除了没有独立事实的
自定义 activity，未扩核心白名单或新增活动注册表；并只纠正原始 CSV 的证据用途。

返修后自动化结果：L1 聚焦与 L0 防腐集合 `105 passed in 58.36s`；非 live Operation 全集
`300 passed in 111.01s`；`git diff --check` 通过。

## 5. 边界与下一门

L1 没有真实启动 Codex，也没有创建 `Run`、Local 后端或 current CAS。它使用冻结的旧加固 Task
路径完成真实工具、正式 Artifact 和 reviewer 绑定，只证明插件合同能穿过现有控制边；真实 Agent
使用原生读写与领域工具，以及轻量 Run 本身，仍是 L2 完成门，不能从本阶段测试外推。

只有独立审查确认投影不是第二权威、插件成本度量没有把注册胶水伪装成领域算法、且 L0 防腐门没有
退化，才允许进入 L2。
