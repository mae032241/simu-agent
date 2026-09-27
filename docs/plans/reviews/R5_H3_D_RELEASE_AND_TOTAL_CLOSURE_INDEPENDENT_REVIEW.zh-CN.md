# R5-H H3-D 发布与 H3 总闭合独立审查

日期：2026-08-31  
审查基线：`404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前累计工作树  
权威计划：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
权威计划 SHA-256：`511634eeca880b934cd5526e65380886da8e97aa351a9631ca5661210f72cde5`  
审查范围：H3-A 至 H3-D 总闭合；不审 H4 之后的功能  
结论：**通过**

## 1. 最终判断与阻断项

**阻断项：无。**

H3 已经删除三类重复权威或隐藏兼容面，并在 H3-D 用干净发布树、安装后入口、当前格式重启、
Approval/Execution、Transform、TCAD 注册工具和负向入口完成收口。当前运行时只有数据库中的
ResearchInstance 与语义绑定解释 current；Worker 的普通输入只经 assignment 物化，输出只经当前
受控文件校验和封存协议；12 个旧内联 Worker 名称不在目录或路由中；builtin 历史别名和孤立
binding 自动合成实例均不存在。

本轮没有通过新增启动扫描、迁移器、全局入口 validator、OperationSpec 字段、数据库状态或第二注册表
换取通过。H3-D 没有修改生产 Python；H3-A 至 H3-C 的生产规模从 H2b 后的 60,177 行降至
59,128 行，净删 1,049 行和 1 个文件。现有较重的 Artifact/Task/Approval/Execution 承重边界仍在，
但 H3 没有继续加重控制面。

## 2. 唯一 current 权威已经闭合

- `src/scidiscovery/research_state.py` 已删除；基础运行依赖不含 PyYAML，PyYAML 只位于 test extra；
  `src`、`deploy`、基础 entry point、当前安装文档均不读取、迁移或删除
  `research/current.yaml`；
- `SchedulerBindingService.list_instances` 只读 `scheduler_instances`，`get_instance` 对不存在的实例
  直接报 unknown；`session_instance` 在
  `scheduler_bindings.py:467-484` inner join active `scheduler_instances`，因此孤立 session/binding
  不会成为 current；
- 初始化末尾在 `scheduler_bindings.py:1756` 结束，不再扫描孤立 binding，也不创建 closed
  `legacy.*` 实例。当前仍存在的表结构补列属于原有当前数据库 Schema 演进，没有新增 H3 专用扫描、
  旧命名空间识别或合成分支；
- 独立聚焦用例将孤立 binding 与 session 原始行保留在数据库中，重开后实例列表、session current、
  新 binding candidates 和 `get_instance` 均不能解释它；这证明结果不是靠破坏性清理或入口特判获得；
- 无 PyYAML 的隔离 venv 从真实 core wheel 编译唯一 installed catalog，并以同一 state root 读回
  closed ResearchInstance。H3-A 独立复审报告哈希复算为
  `e2dfb7d03fa11a6caf4c25685c851e66788b52625480554f919e8d0136d0983a`。

因此 YAML 不再是第二 current，也没有用新的“入口全局检查器”补回同一责任。

## 3. Worker 只保留一套文件协议和精确注册工具

`mcp_worker_protocol.py:108-124` 的当前通用表面由任务 claim、assignment 物化、有界 PDF/分析/网页
能力、受控文件编辑、checkpoint、校验、heartbeat 和 finalize 组成。基础插件实际授予普通 Agent 的
六个生命周期组件仍是 materialize、三项受控写入、validate file 和 finalize file；附加能力必须由
精确 Operation 编译授权。

关键边界如下：

1. `mcp_worker_dispatch.py:26-30` 对目录外名称直接返回 `unknown worker tool`；没有旧名转发；
2. `mcp_worker.py:62-74` 只从一个 `CompiledCatalog` 投影所选 Agent 类型的注册工具，调用时仍由
   `require_worker_capability` 按当前任务精确能力二次约束；
3. `tasks.py:823-857` 的输入投影只有一条机械规则：handoff-only 无路径、普通输入为
   `native_read`、精确 Operation 授权 PDF 工具时再增加 `extract_pdf_text`；规则不含角色、Schema、
   TCAD 或插件名；
4. `TaskService.read_input`/`stage_input` 只服务 PDF 缓存和已注册 contextual handler。Agent 看不到
   这两个方法，也没有 `worker_read_input` MCP；领域工具通过受限 `WorkerTaskAccess` 消费精确绑定
   输入，不形成第二套 Agent 输入协议；
5. proxy 只把 `worker_finalize_file` 视为当前完成信号，旧 `worker_finalize` 不会停止 lease。

本次独立运行逐名验证 12 个旧名称均未列出且实际调用统一 unknown。H3-B 先前还通过真实
`WorkerBrokerRouter` JSON-RPC 逐名负例和 TCAD author 调试完整生命周期；其报告哈希复算为
`c6726136b932e7fb62cd6ef9e3d5dc39c469dce8734efe0741816b65c4c3b074`。当前源码扫描未发现旧模型、
旧服务方法、旧活动值或兼容转发器。

## 4. 零消费者别名和历史实例合成没有换壳

- 基础发行 entry point 仍精确指向 `scidiscovery.builtin_plugin:CORE_PLUGIN`；模块只定义
  `CORE_PLUGIN`，不再定义或导出 `PLUGIN = CORE_PLUGIN`；
- 孤立 binding 合成块相对基线净删 30 行。旧 binding 可由底层精确历史查询保留，但不会进入实例
  current、session current 或 candidates；
- H3-C 没有新增删除器、迁移版本、启动扫描、旧格式 parser 或按 legacy 名称分支。当前格式
  Artifact、Task、Approval、Execution 四类 binding、completed task 和 closed instance 经重启仍可读；
- H3-C 独立报告哈希复算为
  `32db09cce58531a8715056e3f2a358af33a987c8fddcab5abcfe9ed103fcfbee`。

H3-C 删除的是伪造当前事实的启动期写入，而不是删除历史字节或扩大所有入口的校验逻辑。

## 5. 安装、生命周期和领域工具证据

候选实施记录的完整证据为：`tests/operations` 312 项通过；部署、平台与33项约束38项通过；干净
wheel 收口矩阵24项通过。本审查没有为形式完整重复三个全量集合，而是独立重建 wheel 并运行11个
会直接击中 H3 边界的聚焦用例：

- core_no_yaml 安装、curve、table、tcad_resolved 和 full 组合均从安装后的
  `scidiscovery.plugins` 单入口编译；组合的插件和 Operation 所有权精确；
- curve、table、TCAD 三类打包后的注册工具实现均可执行；TCAD author 可见调试工具而 reviewer
  不可见，工具没有落入通用核心分支；
- installed Agent Operation 完成 claim、materialize、注册工具、受控写入、validate 和 finalize，
  再关闭并重开同一 state root；Task completed 与 Artifact/Task/Approval/Execution 四类 binding
  保持；
- installed Effect 在 UI 精确决定前拒绝执行，真实 loopback UI 决定后只提交一次并幂等收集；
- installed Transform 两次相同调用幂等，全部输出带精确父链和 Operation 标签；
- 旧 Worker 名称、孤立 binding、未安装 Operation 和旧直接 Execution 入口均走目标入口失败关闭。

这些测试覆盖的是注册、控制边界和本地 no-effect 生命周期，不冒充真实 Sentaurus 求解器科学验收。

## 6. 文档和发布清单一致性

中英文架构、当前安装说明、Worker 文件协议和 TCAD 插件说明已经一致记录：数据库是唯一 current；
普通输入由 assignment 物化；PDF 是精确授权的附加能力；handoff-only 不暴露路径；12 个旧 Worker
名称 unknown；TCAD 不拥有第二输入协议。

根 `MANIFEST.sha256` 的当前 SHA-256 为
`ce44d0883810f07f7777e49a2d42518132b6da6e90060ecf208eb3f2cbecfcb2`。独立执行发布构建器后：

```text
root_vs_generated_manifest=0
generated_manifest_verify=0
tracked source files=396
```

根清单与新构建的规范化发布树清单逐字节一致，发布树内全部条目复算通过。根清单描述的是构建器先
执行 `_normalize_text` 后的干净发布树，因此不应把源码工作树直接 `sha256sum -c MANIFEST.sha256`
的结果误当作发布失败。

本独立报告位于发布构建器包含的 `docs/plans` 下，报告生成后自然需要由主实现者再机械生成一次最终
清单，并同步“已通过”状态。这是把本报告纳入发布快照的封存步骤，不是生产代码修复，也不得借机
增加运行时 release 状态或入口校验。

## 7. 奥卡姆剃刀、33项约束和目标一致性

H3-A 至 H3-C 的实现是可解释的净删除；H3-D 只同步文档、测试证据和机械清单。没有新增：

- 数据库表、列、状态或第二 current；
- Registry、OperationSpec 字段、Operation、路由器、facade 或兼容层；
- 按插件名、角色、Schema 或历史格式分支的入口校验；
- 固定科研 DAG、规划器、科学对象图或控制层排序；
- TCAD 专用的核心输入/输出协议。

33项约束结构门通过。本阶段直接收紧 `AUTH-001`、`AUTH-003`、`MIG-001`、`ROLE-002` 和
`SEC-002`，并保持 Artifact/Task/Approval/Execution、不可变父链、精确 UI 决定和副作用恢复等承重
边界。`AUTH-003` 仍按账本等待 H7 的完整合同验收；原生工具强隔离仍属于 `SEC-002`/H4。两者均没有
因 H3 测试通过而被提前改成完全符合。

架构目标没有偏移：行为仍以一个无状态 `OperationSpec` 声明，由插件窄组件实现并经
`scidiscovery.plugins` 一次注册编译；多角色 Agent 只见任务文件；领域能力可组合安装；控制面只保留
必要生命周期、资格和副作用门禁。本轮没有把“防止旧入口误用”升级成新的中央策略系统。

## 8. 独立检查结果

所有 pytest 均串行运行，并设置 7 GiB 虚拟内存上限。

```text
聚焦安装、current、旧工具、三生命周期和发布构建矩阵：
8 passed in 43.54s；/usr/bin/time 峰值 RSS 77,036 KiB

聚焦 Effect UI 授权、Transform 幂等、TCAD Operation 工具范围：
3 passed in 39.02s；/usr/bin/time 峰值 RSS 78,760 KiB

独立重新构建发布树并复算 MANIFEST.sha256：
通过；根清单与生成清单逐字节一致

python scripts/r5_current_metrics.py：
production_python={files:150, lines:59128}
worker_lines=810；task_lines=6031；operations_package={files:7, lines:2064}
generic_core_domain_tokens=0

git diff --check HEAD：通过
```

## 9. 非阻断债务与可信度边界

1. 当前 R1 至 R5 仍在同一个累计未提交工作树，Git 不能直接生成各 H3 子阶段 patch。三份已核验阶段
   报告、精确符号扫描、净删除指标和当前真实入口测试共同降低了该风险；后续交付仍宜形成阶段提交。
2. `MANIFEST.sha256` 属于规范化发布树，README 可以在 H6 做一句更明确的验证说明，避免维护者在
   未规范化源码树直接复算后误判；不需要为此增加新脚本或校验入口。
3. 发布构建器当前仍携带全部历史 `docs/plans` 和审查报告，活动阅读面偏大；这已经明确属于 H6 的
   文档归档工作，不应倒灌为 H3 的新发布状态机。
4. Codex 原生工具隔离仍是已知 H4 边界；H3 没有扩大权限，也没有把提示约束宣称为平台沙箱。
5. 本审查没有运行真实外部 Sentaurus。H3 的目标是协议、插件和发布闭合，真实 solver 仍须按后续
   精确授权和资格边界执行。

## 10. 结论

H3-A 至 H3-D 已完成预定减法：数据库 ResearchInstance 是唯一 current 权威；Worker 只有当前受控文件
生命周期与 Operation 精确注册工具；旧 Worker 协议、builtin 别名和孤立 binding 自动实例合成均无
在线兼容入口；干净安装、重启、Approval/Execution、Transform、TCAD 工具和发布清单均有真实入口
证据。没有用过度入口校验或新控制实体替代删除项。

**结论：通过。允许主实现者机械纳入本报告、更新最终状态与清单后结束 H3；不要求架构返工。**

本报告自身最终 SHA-256 由交付消息给出；不写入正文以避免自引用改变摘要。
