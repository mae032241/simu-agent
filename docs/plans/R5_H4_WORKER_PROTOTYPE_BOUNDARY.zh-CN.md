# R5-H H4 Worker 原型与生产隔离边界计划

日期：2026-08-31  
状态：方案与实现独立审查均通过；H4 完成  
前置门：H3 独立总审查通过  
目标：只澄清现有边界，不新增 dispatcher、权限系统、运行状态或入口校验

## 1. 当前事实

当前唯一正式的 Codex Agent 派发路径是平台配置生成的
`task_prepare_dispatch → spawn_agent(fork_turns="none")`。它把启动时编译的 Operation prompt、专属
Worker MCP 配置和任务文件合同交给子 Agent。服务端会拒绝未声明的 Worker/领域工具，输出只能经
受控文件校验和封存；但子 Agent 对父会话原生工具、MCP、sandbox 与 skill 的可见性仍受 Codex
0.150.1 原型限制，提示中的“禁止使用”不是平台强隔离。

`artifact_agent/service/agent_dispatch.py` 与 `platforms/codex_worker.py` 是未接入正式路径的下一版本
实验基座。生产 runtime、Root/Worker MCP、平台初始化、服务导出和部署脚本均不导入它们；只有前者
导入后者，专项测试直接调用二者。它们不能与 `spawn_agent` 同时被描述成正式 dispatcher。

## 2. 最小改动

1. 只修改两个实验模块的模块/类/公开函数说明，明确“未接入正式 runtime、仅供后续隔离研究”；
   不改变命令、凭据、capability、proxy、任务状态或清理逻辑；
2. 中英文当前架构各增加一句：正式路径是 `spawn_agent`，两个独立进程模块是 dormant experimental
   base；不得把其单元测试当成当前生产隔离证明；
3. 复用已有测试证明：
   - 平台生成的 scheduler prompt 只要求 `spawn_agent`，不出现 `codex_process`；
   - 每个 Operation prompt 同时列明允许和禁止工具，并诚实说明可见不等于授权；
   - 服务端仍按精确 Operation 拒绝未授权 Worker/领域工具；
   - 两个实验模块本身的聚焦测试继续通过，但只证明基座代码未腐烂；
4. 用生产 import/entry-point 扫描确认 runtime、Root/Worker MCP、平台初始化、service 公共导出和部署
   不引用 `CodexTaskDispatcher`/`codex_worker`。该扫描是验收证据，不做成新的启动 validator；
5. 同步总计划状态和发布清单，交给新的独立实现审查者；未通过不进入 H5。

## 3. 明确不做

- 不把独立 `codex exec` 接入 Root，不增加 dispatcher 选择开关或模式枚举；
- 不删除实验基座，也不复制一套正式 Task/Worker 生命周期；
- 不增加凭据分类器、生产路径猜测、全局工具注册表或新的权限摘要；
- 不宣称提示词能隐藏 Codex 原生工具，不把单元测试升级为生产安全资格；
- 不真实连接外部 TCAD、网络写入、生产凭据或不可逆副作用；
- 不因 H4 重跑完整科学闭环或重构两个实验模块内部实现。

## 4. 验收与停止条件

- 正式配置、当前文档和代码说明都只承认 `spawn_agent` 为当前正式路径；
- 未授权 Worker/领域工具仍由现有服务端门拒绝，提示约束不被描述为强隔离；
- 两个实验模块没有生产消费者，也没有新增入口、状态、注册表、Schema 或生产行为；
- 聚焦平台、工具权限、Worker authority 和实验基座测试通过，`git diff --check` 通过；
- 独立审查明确确认没有把 H4 做成新的权限控制平台，才将 H4 标为通过并放行 H5。

若实现需要新增生产分支、配置字段或入口 validator，立即停止并重新审视；H4 的目标只是说清现有
边界，不是提前实现下一版本的进程隔离。

## 5. 实施候选记录

- `agent_dispatch.py` 与 `codex_worker.py` 只修改模块、类和公开函数说明，明确它们未接入当前 runtime；
  命令、凭据、capability、proxy、任务状态、清理和工具行为均未改变；
- 中英文当前架构均明确：唯一接入路径为 `spawn_agent`，两个独立进程模块是未启用的实验基座，
  其专项测试不是当前生产隔离证明；
- 生产消费者扫描只有 `agent_dispatch.py → codex_worker.py` 这一条实验模块内部依赖；runtime、
  Root/Worker MCP、平台初始化、service 公共导出、entry point 和部署脚本均无消费者；
- 平台配置、Root 派发准备、Worker authority、Operation 工具提示和实验基座共15项聚焦测试通过，
  用时41.47秒；`git diff --check` 通过；
- 没有新增生产分支、入口、状态、注册表、Schema、配置字段、权限摘要或测试框架；`SEC-002` 继续
  保持已知问题，不把 H4 候选描述为生产级原生工具隔离。

方案独立审查见
`reviews/R5_H4_WORKER_PROTOTYPE_BOUNDARY_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告 SHA-256
为 `15f05a3f32165c16d919dc2fdc393877bd0f4e7fce57c155dc1b90b88106ca13`，结论“通过”。本候选仍须
新的独立实现审查明确通过后，才能把 H4 标为完成并进入 H5。

H4 独立实现审查见
`reviews/R5_H4_WORKER_PROTOTYPE_BOUNDARY_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告
SHA-256 为 `a17e83d6550809127e65ffb57417bdeebba70683aa3b8efadf7ad2615081ce5d`，结论“通过”，阻断项为零。
审查确认运行逻辑零变化、正式派发仍只有 `spawn_agent`、实验模块无生产消费者、`SEC-002` 未被虚假
关闭，且没有新增入口校验、模式开关、权限系统、状态或注册表。H4 至此完成，只放行 H5。
