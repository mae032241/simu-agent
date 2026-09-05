# R5-H H4 Worker 原型边界实现独立审查

日期：2026-08-31  
审查对象：`docs/plans/R5_H4_WORKER_PROTOTYPE_BOUNDARY.zh-CN.md` 的实施候选  
审查基线：H3-D 最终封存发布快照  
审查性质：只读实现审查；除本报告外未修改生产代码或被审计划  
结论：**通过**

## 1. 结论与阻断项

**阻断项：无。**

H4 实现严格停留在“说清当前边界”：当前唯一接入的 Agent 派发链仍是
`task_prepare_dispatch → spawn_agent`；独立 Codex 进程代码仍是未接入 runtime 的实验基座；
`SEC-002` 仍为 `known_issue`。实施没有增加 dispatcher、模式开关、权限系统、运行状态、注册表、
Schema、配置字段或入口 validator，也没有修改 Task、凭据、代理、清理、工具或副作用行为。

因此 H4 达到了计划目标，同时没有把控制面入口校验再次做重。

## 2. 精确差异核验

以 H3-D 最终封存发布树为前态，H4 候选只改变以下表面：

- `agent_dispatch.py`：模块、`CodexTaskDispatcher` 和 `dispatch` 的说明文字；
- `codex_worker.py`：模块、异常类和 `prepare_codex_worker_launch` 的说明文字；
- 中英文当前架构各增加三行边界说明；
- 两份总计划同步 H3/H4 状态，新增 H4 计划及其方案独立审查；
- 机械更新 `MANIFEST.sha256`。

对两个 Python 模块分别移除 AST docstring 后与 H3 封存版本比较，语法树完全相同。没有测试文件、
部署文件、入口点、平台配置生成器、MCP 路由、服务或插件声明在 H4 中发生变化。新增 H4 计划及
方案审查属于被计划允许的“计划/清单”范围，不是新的运行时表面。

## 3. 当前派发路径与实验模块消费者

### 3.1 唯一接入链没有改变

- `mcp_root_task_routes.py` 的 `task_prepare_dispatch` 只对既有 Task 执行精确准备并返回编译得到的
  `agent_type`，不构造独立进程 dispatcher；
- `platforms/codex.py` 生成的父调度说明只要求 `spawn_agent`，关闭父历史继承，并明确子会话聊天
  不是科学结果；生成的 scheduler prompt 不包含 `codex_process`；
- 每个 Agent Operation 的配置仍只投影其精确 Worker MCP server 和工具集合，没有 dispatcher
  选择字段或运行模式分支。

所以文档中的“唯一接入”是当前事实；它不等于生产级工具隔离已经完成。

### 3.2 独立进程基座没有生产消费者

对 `src/`、`plugins/`、`deploy/`、`scripts/`、项目 entry point、runtime、Root/Worker MCP、平台
初始化和 service 公共导出进行扫描，生产源码中只有：

```text
agent_dispatch.py → codex_worker.py
```

除此之外没有导入、构造或调用 `CodexTaskDispatcher`、`prepare_codex_worker_launch` 或
`run_codex_worker`。当前消费者仅为专项测试和一份历史现场资格脚本。旧 `deliverables` 中还保留
曾经接线的安装副本，但它不在当前源码运行路径或发布清单中，不能作为当前生产消费者。

两个实验模块仍会作为普通包文件发布并可被显式导入，这是计划有意保留的下一版本研究基座；H4
没有为阻止显式导入再加禁用开关或启动扫描。

## 4. 提示约束与服务端授权没有退化

编译后的 Operation 提示仍同时列出：

- 唯一允许的 Worker MCP server 和精确 Worker 工具；
- 允许的任务本地原生读取/检查能力；
- 禁止的 Root 工具、其他 Worker server、原生写旁路、网络、委派、skill/app/plugin 和未声明工具；
- “可见不等于授权”，以及原生工具写能力可能无法被当前 runtime 技术隐藏的诚实限定。

强制边界仍在服务端：Worker router 先拒绝目录外工具，再由当前 Task 的编译 authority 对精确
capability/tool name 做二次约束；安装态 TCAD author 可见其注册调试工具而 reviewer 不可见。
H4 没有把提示词变成新的权限权威，也没有削弱既有服务端门。

## 5. `SEC-002` 与声明范围

`SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 中 `SEC-002` 仍为 `known_issue`，证据仍明确说明：领域 Worker
MCP 有服务端门禁，但 `spawn_agent` 的原生工具隔离仍只是提示约束。设计宪章、中英文当前架构、H4
计划与总计划口径一致，没有把以下证据夸大为生产级隔离：

- 编译提示包含禁止项；
- 实验进程基座能生成收紧的配置；
- 实验模块专项测试通过；
- 当前只存在一条接入链。

H4 通过只代表边界陈述和接线事实闭合，不代表 `SEC-002` 已解决，也不授权生产凭据、真实外部 TCAD、
网络写入或不可逆副作用。

## 6. 复杂度与奥卡姆剃刀

未发现 H4 新增下列表面：

- 入口校验器、生产环境猜测器或 import 扫描器；
- dispatcher 选择开关、模式枚举或第二正式派发路径；
- 权限摘要、凭据分类、数据库状态或收据；
- 新注册表、OperationSpec 字段、MCP 工具、服务 facade 或测试框架；
- 针对 Codex 版本、角色、插件或 TCAD 的控制面特判。

本阶段用一次性差异/消费者扫描形成审查证据，没有把扫描固化进启动路径。这个实现符合“若非必要，
勿增实体”和用户特别强调的轻量控制面原则。

## 7. 独立检查

所有测试串行执行并设置 7 GiB 虚拟内存上限：

```text
Root 派发准备、平台生成、Worker authority、Operation 工具提示、
实验进程基座与 Worker 路由聚焦检查：16 passed in 38.85s
峰值 RSS：100,268 KiB

两个实验模块去除 docstring 后的 AST 与 H3 封存版本完全相同
git diff --check：通过
```

独立重建发布树结果：

```text
tracked source files：399
MANIFEST 条目：398
根清单与重建清单逐字节一致
全部 398 个条目 SHA-256 复算通过
候选 MANIFEST.sha256：
d41376b1f86188b2cd36a91fa16b70fd61309c9fea9a395b6bb71f73293e5eec
```

发布清单包含 H4 计划、方案独立审查、两份当前架构、两个实验模块及总计划的候选字节，未夹带新的
运行入口。实施审查报告生成后，主实现者需要机械重建一次最终清单把本报告和“已通过”状态纳入；
这不是运行时修复，也不得借机修改生产行为。

## 8. 非阻断项

1. `spawn_agent` 的原生工具、其他可见 MCP、sandbox 与 skill 隔离仍未形成平台强保证；这正是
   `SEC-002` 的已知问题，不能因 H4 通过而关闭。
2. 两个实验模块仍是可显式导入的发行包代码，并由历史现场脚本使用。当前没有生产消费者且文档已
   限定其地位；以后若要接入，必须另行完成唯一生产路径和真实隔离审查，不能增加并行模式开关。
3. R1—R5 仍是累计未提交工作树。本审查依靠 H3 封存发布快照恢复阶段差异；后续形成阶段提交会提高
   可审计性，但不是 H4 行为缺陷。
4. 本报告和最终“通过”状态尚未进入候选清单；按现有发布构建器机械封存即可，不需要新增 release
   状态机或入口校验。

## 9. 最终判断

H4 实施与计划一致：运行逻辑零变化；`task_prepare_dispatch → spawn_agent` 仍是唯一接入路径；
独立进程代码没有 runtime、MCP、平台、service、entry point 或部署消费者；提示与服务端授权没有
退化；`SEC-002` 未被虚假关闭；发布候选一致；没有过度设计或针对性补丁。

**结论：通过。允许主实现者仅做状态与发布清单的机械封存，然后进入 H5；无需架构或实现返工。**

本报告自身 SHA-256 由交付消息返回，不写入正文，避免自引用改变摘要。
