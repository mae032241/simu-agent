# R5-H H4 Worker 原型边界方案独立审查

日期：2026-08-31  
审查对象：`docs/plans/R5_H4_WORKER_PROTOTYPE_BOUNDARY.zh-CN.md`  
审查性质：方案审查；未修改生产代码或被审方案  
结论：**通过**

## 1. 总体判断

H4 方案是解决当前问题所需的最小方案。它没有尝试在本阶段补造进程级权限系统，而是完成三件必要
且足够的事：确认当前唯一接入的 Agent 派发链，标明两个独立进程模块尚未接入，禁止把提示约束或
实验模块测试误写成生产隔离证明。

方案明确禁止增加第二 dispatcher、模式开关、权限状态、凭据分类器、全局工具注册表、入口校验和
第二套 Task 生命周期；验收扫描也只作为一次性证据，不进入启动路径。该范围符合奥卡姆剃刀原则，
没有把 H4 重新做成控制平台。

## 2. 消费者事实核验

### 2.1 当前接入链确为 `spawn_agent`

- `mcp_root_task_routes.py:127-136` 的 `task_prepare_dispatch` 只准备既有 Task 并返回编译得到的
  `agent_type`，没有构造或调用独立 Codex 进程；
- `platforms/codex.py:45-66` 生成的调度说明要求父会话使用 `spawn_agent`，关闭父历史继承，并把
  子会话聊天仅视作不可信完成信号；
- 同一平台生成器为每个编译 Operation 生成精确 Worker MCP 工具投影，但没有 dispatcher 配置字段
  或 `codex_process` 分支；
- 聚焦测试 `test_root_prepares_spawn_agent_dispatch_without_starting_a_codex_process` 和
  `test_scheduler_profile_registers_spawn_agent_and_inherited_worker_mcp` 通过。

因此，方案第 1 节关于当前接入链的判断与源码一致。这里的“正式”应理解为“当前唯一接入”，不
代表已经具备生产级进程隔离。

### 2.2 两个独立进程模块没有正式消费者

对 `src/`、`plugins/`、`deploy/`、`scripts/` 和项目入口进行消费者扫描后确认：

- `artifact_agent/service/agent_dispatch.py` 直接导入 `platforms/codex_worker.py`；
- 除上述内部依赖外，生产 runtime、Root/Worker MCP、平台 `initialize_platform`、服务公共导出、
  console script 和部署脚本均没有导入或构造 `CodexTaskDispatcher`；
- `codex_worker.py` 没有项目脚本或 entry point；
- 当前消费者是专项测试和已明确属于历史/现场证据的脚本，其中 `live_r3_exact_agent_qualification.py`
  不是产品入口。

两个模块会随基础 wheel 作为普通包文件发布、可被显式导入，但“包内可导入”不等于运行路径已接
线。方案选择保留代码、只修正模块与公开对象说明，足以消除当前表述冲突，不需要再加禁用开关。

## 3. 权限、凭据和副作用边界

### 3.1 已有服务端边界没有被削弱

`mcp_worker_dispatch.py:25-85` 先按实际工具表拒绝未知工具，再按当前 Task/Worker 和编译 capability
调用 `require_worker_capability`。Operation 专属 Worker 工具因此仍有服务端硬门，H4 复用现有负例
即可，无需新增入口校验。

独立进程实验基座自身已有精确 dispatch capability、私有 Codex home、凭据文件权限、秘密清理和
调试开关，但它们没有接入当前链路。方案正确地要求不修改这些行为，也不把其专项测试外推为当前
生产资格。

### 3.2 当前未闭合边界被如实保留

`spawn_agent` 子会话的父会话原生工具、Root MCP、其他 Worker MCP、sandbox 和 skill 可见性不是
服务端完整隔离。编译提示可以声明禁止使用，不能在技术上隐藏这些能力。设计宪章
`SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md:36-41` 已据此限定：该路径只用于开发调试，不得携带
生产凭据或执行不可逆动作；`SEC-002` 也仍是 `known_issue`。

方案第 3 节明确排除真实外部 TCAD、网络写入、生产凭据和不可逆副作用测试，因此没有漏掉这些
边界，而是有意不在 H4 越权解决。H4 通过后也不得把 `SEC-002` 改成 `conformant`，不得宣称
`spawn_agent` 已成为生产安全路径。真正的进程隔离只能在后续把独立进程基座验证并替换为唯一
生产派发路径时另行审查。

## 4. 复杂度与验收充分性

方案没有要求新增：

- dispatcher 选择开关或运行模式枚举；
- 新数据库表、状态、收据或权限摘要；
- 第二注册表、第二 Worker 协议或第二任务生命周期；
- 凭据分类器、生产环境猜测器或启动期 import validator；
- 为 H4 特制的完整科学闭环和外部副作用测试。

计划中的现有测试加一次性生产消费者扫描足以验证“当前接线事实”和“既有服务端门不退化”。本次
审查实际运行 12 项聚焦测试，覆盖 Root 准备派发、平台 `spawn_agent` 配置、精确派发服务端合同和
Operation 网络权限，结果为 `12 passed in 3.27s`。

## 5. 阻断项与非阻断项

### 阻断项

无。

### 实施时必须保持的非阻断边界

1. H4 状态通过只表示“当前边界已说清且只有一条接入链”，不能把 `SEC-002` 的已知问题改写为
   已解决；
2. 消费者扫描应继续区分生产、测试、历史现场脚本和旧 `deliverables` 安装副本，不应把字符串
   零命中做成新的启动校验；
3. 中文当前文档宜使用“未启用的实验基座”而非新的模式术语；这只是表述收敛，不得引入配置字段；
4. 若实现 diff 出现生产分支、Root 接线、凭据处理变化、入口 validator、权限状态或新测试框架，
   应立即停止并打回 H4，而不是扩大方案。

## 6. 放行结论

**通过。** 可以按被审方案实施 H4。独立实现审查应核对实际 diff 只包含实验模块说明、当前中英文
架构、计划状态和机械发布清单，并复核既有聚焦测试；满足后方可进入 H5。
