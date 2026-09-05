# R5-L6 最终独立审查（第一轮）

日期：2026-09-01  
审查者：未参与本轮实现的独立审查者  
结论：**FAIL**  
放行范围：**不放行第二轮总审查，不宣布 L6 完成**

## 1. 总体判断

L6 已完成最重要的结构性减法：生产 Python 路径中未再发现旧 `TaskService`、Task token、中央
Worker daemon/proxy 或 Root Task route；Agent 调用由唯一 `operation_invoke` 创建 `Run`，Local 与
Hardened 复用同一 `RunService` 和同一编译目录，Hardened 只是 Local 工作区之上的可选文件传输与
每 Run 围栏。TCAD 领域调试合同位于插件，`OperationToolContext` 也没有 Task/session/token、
current、Approval 或 Artifact 登记写权。这些说明旧中央控制器不是被简单改名或包装起来。

但是，候选尚未达到 L6 的最终完成门。当前有三个可复现阻断：Hardened 没有部署级一致选择器；
旧中央 Worker 的 systemd 文件在升级安装后仍会遗留；当前规范性文档、33 项状态和规模证据与实际
实现不一致。前两项使最终安装矩阵并未真实闭合，第三项使用户会按已经删除的 Task 协议操作，并使
“满足 33 项约束”的结论无法复核。

## 2. 审查依据与方法

审查依据：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md`，尤其是第 6.3、10、12、13 节；
- `docs/plans/evidence/R5_L6_OLD_PATH_REMOVAL_AND_FINAL_MATRIX.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
- 当前工作树生产代码、部署脚本、插件声明和测试。

在 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2`、串行执行条件下完成的独立聚焦检查包括：

```text
L2/L3/L4/L5、Effect、执行审批、平台与部署聚焦集：49 passed
干净源码发布与领域 wheel 所有权：2 passed
当前候选的 Hardened、平台和部署再聚焦：23 passed, 26 deselected
python -m compileall -q src plugins：通过
bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh：通过
git diff --check：通过
```

遵循任务要求，没有重跑证据中已经记录的完整 189 项集合。上述通过项只能证明被覆盖路径没有行为
回归，不能覆盖下列缺失的部署迁移和配置组合。

## 3. 已确认闭合的部分

### 3.1 旧科学权威已从 Python 生产路径退出

对 `src/`、`plugins/` 和 `pyproject.toml` 扫描，下列旧权威符号均为零命中：

```text
TaskService、TaskToken、legacy_task、WorkerTaskAccess、task_ref、task_private、
mcp_worker_daemon、mcp_worker_proxy、worker_socket
```

保留的 `mcp_proxy.py` 是交互调度器到 Root control socket 的轻量代理，不是旧 Worker proxy；
保留的 scheduler session key 只把一个交互调度会话绑定到 ResearchInstance，不参与 Worker 授权、
科学输出或 Run 终态。Run 本地 `assignment.json` 是显式文件输入，不是旧 assignment 状态机。

### 3.2 唯一目录、调用入口和科学终态成立

- 插件只有 `scidiscovery.plugins` 一个入口和一个启动编译目录；`public/support/internal/all` 只是投影；
- Root 只有一个 `operation_preflight` 和一个 `operation_invoke`；
- Agent Operation 只创建 `Run`，Artifact 登记、Run 终态、current CAS 和 reviewer 精确父链仍由
  `RunService`/Root 控制面完成；
- Approval、Effect 与 qualification/cohort 只由声明相应策略的 Operation 启用，普通 Run 未重新
  引入 token/session/qualification 字段；
- 未发现 backend、领域工具或插件直接登记科学 Artifact、解释 Run 终态或更新 current 的第二权威。

### 3.3 Local/Hardened 是两个后端，不是两套框架

`HardenedWorkerBackend` 继承 `LocalTrustedBackend` 的工作区实现，只增加后端私有的服务端文件编辑和
每 Run transport lease；`HardenedWorkerMCPRouter` 复用 `LocalWorkerMCPRouter` 和同一
`RunService`。聚焦测试覆盖了不同 Run 并行、同 Run 在途调用与接管互斥、旧 owner 失效、服务端
patch、路径逃逸以及纯 MCP 提交。未发现第二目录、第二 preflight 或第二科学状态。

### 3.4 TCAD、最小上下文和 v1 边界基本诚实

- TCAD 作者—调试—独立 reviewer 仍走 Operation/Run/Local Worker 主干；测试中的调试适配器被明确
  标为夹具，没有冒充真实 Sentaurus 或科学准确率；
- TCAD workspace hook、debug contract、领域工具和运行时工厂属于 `tcad_artifact` 插件；核心没有
  按 TCAD 插件名进行调度或准入的分支；
- `OperationToolContext` 只有声明服务、Run 私有工具状态、工作区、精确输入读、候选校验/快照和有界
  活动记录，不提供 Task/session/token/current/Approval/Artifact 写接口；
- Agent 集合输出暂不支持是可接受的 v1 范围，本身不是阻断。当前 Local 与 Hardened 都会对包含
  collection 输出的 Agent Operation 返回不支持，Root preflight 也失败关闭；确定性 Transform 的
  多输出没有受此限制。

因此，第 6 项所述的“集合输出不可用”可以保留为原型边界；问题不在于尚未实现该能力，而在于必须
继续如实投影并增加直接等价测试。

## 4. 阻断项

### B1：Hardened 没有部署级一致选择器，所谓“部署显式选择”不能成立

计划明确要求“后端由部署配置选择”以及“Hardened 只在部署显式选择时加载”。实际代码只有 Python
组装函数具有该参数：

- `open_runtime(worker_backend=...)` 和 `build_root_router(worker_backend=...)` 可以选择后端；
- `platforms.codex.initialize(worker_backend=...)` 可以生成 Local 或 Hardened 子 Agent/MCP profile。

但真实部署入口没有把这个选择贯穿：

- `artifact_agent.interfaces.mcp_daemon` 没有 `--worker-backend` 参数，并且调用
  `build_root_router(...)` 时不传该值，因此 control daemon 永远采用默认 Local；
- `scid init codex` 没有 `--worker-backend` 参数；
- `deploy/install.sh` 没有后端配置项，systemd control 单元也没有向 daemon 传递后端选择。

这不是单纯缺少命令行便利功能。如果调用 Python API 强制生成 Hardened Codex profile，而部署的
Root daemon 仍为 Local，Root 会在 `local-runs` 中创建工作区，Hardened Worker 则从同一 Run 数据库
尝试打开 `hardened-runs` 工作区，真实进程链路无法完成。同样，如果全部使用安装脚本，则根本没有
选择 Hardened 的部署入口。现有测试分别手工组装 Hardened runtime 和生成 Hardened profile，没有
覆盖同一个已安装 control daemon 与子 Worker 的一致选择，因此不能证明最终矩阵中的“纯 MCP
Hardened”是可部署组合。

修复要求：用一个部署配置值同时驱动安装预览、systemd control daemon、Codex profile 生成和安装
后验证；非法值失败关闭。至少增加 Local 默认、Hardened 显式选择、Root/profile 不一致拒绝和纯
MCP Hardened 已安装链路测试。不得再增加第二目录或第二 preflight。

### B2：升级安装只停用旧中央 Worker，没有事务性删除其 systemd 文件

`begin_install_transaction` 会备份 `/etc/systemd/system/scidiscovery-worker.service`，说明升级迁移已
识别该旧对象；`retire_old_deployment` 也会 `disable --now` 它。但是该函数的 `rm -f` 清单没有删除
该文件，新的 `install_units` 又只安装 control、approval UI 和可选 TCAD 单元。结果是从旧版升级后：

```text
/etc/systemd/system/scidiscovery-worker.service
```

仍然存在，只是处于 inactive/disabled。`cleanup_legacy_services.sh` 也只检查 retired unit 不活动，
不会删除它。由于新 site 已删除旧 Worker 模块，人工或误配置再次启动这个遗留单元还会指向不存在
的生产入口。

现有 `test_default_deployment_has_no_central_worker_service` 只检查源码模板不存在、cleanup 把名称列入
retired；安装器测试只检查名称出现在停用函数，均没有模拟“旧单元存在 → 新版升级 → 文件消失 →
失败回滚恢复旧文件”。因此证据文件中“删除旧中央 Worker systemd 单元”和“默认无中央 Worker
服务”的升级结论不成立。

修复要求：在已开始安装事务之后事务性删除该精确旧 unit，成功安装后保持删除，失败回滚时恢复
原文件及原 active/enabled 状态；增加真实临时根或安装事务级的迁移正反例，不能只做字符串断言。

### B3：当前规范、33 项状态和规模证据与候选实现不一致

这是最终架构交付物的实质问题，不是措辞瑕疵：

1. `docs/ARCHITECTURE.zh-CN.md` 仍把当前状态写成 R5-G/R5-H，并把旧计划列为当前重构权威；英文版
   同样未成为 L6 当前真相。
2. `SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md` 仍写“控制面拥有 Artifact、Task……”和旧 Task
   语义，未改为当前唯一 Run 权威。
3. `docs/role-result-json-protocol-v1.md` 仍要求 `task-workspace`、worker session、
   `worker_materialize_assignment`、`worker_file_*`、`worker_run_analysis`、
   `worker_validate_output_file` 和 `worker_finalize_file`，并宣称 Agent collection 可用。当前 Local
   主干实际是原生工作区加 `worker_open_assignment/worker_heartbeat/worker_submit_result`，Agent
   collection 明确不可用。该文件会直接误导 Worker/插件作者使用已经删除的协议。
4. `docs/tcad_transport_contract.md` 仍把 debug 描述为 Task/attempt/session/capability lease、
   provisional CAS、token-independent reconciler 和 Task/orphan cleanup。当前实现是 Run 私有
   Operation 工具状态与有界 Local debug 服务，没有这些实体。
5. 33 项 YAML 中当前有 25 项 `pending_review`、7 项 `conformant`、1 项 `known_issue`，大量 evidence
   仍指向未来 H7；计划第 10 节又明确规定 Local 的 `SEC-002` 不得被条件化豁免、不能声称 33 项全部
   conformant。L6 证据结尾却直接声称“当前结果满足 33 项约束”，二者自相矛盾。
6. L6 证据中的“生产 Python：101 个文件、27,244 行”实际只统计 `src/scidiscovery`。当前
   `src + plugins` 的 Python 是 146 个文件、50,007 行；TCAD 与曲线插件是本次生产交付的一部分，
   不能在“生产代码规模”中静默省略。27,244 行可以继续作为通用包口径，但必须明确口径并同时列出
   插件和总量，不能据此证明整个生产实现已降到 27,244 行。

修复要求：将中英文当前架构、设计宪章、角色文件协议、TCAD debug 合同、33 项状态和 L6 证据同步
到实际 Run v1；对每项约束给出当前证据或诚实保持 `known_issue/pending_review`，不得把已知的
`SEC-002` 写成关闭；修正规模统计口径。历史报告可以保留，但必须明确归档，不能继续作为当前操作
协议。

## 5. 非阻断问题与后续建议

以下问题不单独阻断本轮，但应在返修或后续小步简化中处理：

1. 对 collection Agent，目录目前用 `required=["native_tools_disabled"]` 表示不可用，
   `RunService` 的第一条错误也写成 native tools，即使真正缺失的是 collection 输出生命周期。
   失败关闭是正确的，但原因不准确。建议从同一 backend capability 判定返回结构化原因，并增加
   catalog/preflight/Codex profile 等价测试；不需要为了修正提示而实现 collection。
2. `RootOperationRoutes` 仍有若干 `runs is None` 兼容式分支，但生产构造中 `runs` 已为必需；
   `ArtifactService.purge_registrations` 等接口也暂未发现生产消费者。它们没有形成第二权威，可在最终
   修复后作为小型死表面删除，不应再建立抽象层。
3. `mcp_root_operation_routes.py`、`SchedulerBindingService`、`ApprovalService` 和 `RunService` 仍较大，
   但本轮没有发现按领域名的重复路由或第二生命周期。后续拆分应只按已有职责边界进行，不能以行数
   为目标新增 facade/registry。
4. Local 的 Codex 原生工具隔离仍只是提示约束，按计划保持 `SEC-002 known_issue` 是可以接受的开发
   原型范围；不得把它用于携带生产凭证或不可逆副作用。

## 6. 放行决定

**FAIL。** B1、B2、B3 全部关闭前，不放行第二轮独立总审查，也不宣布 L6 或整个 L 系列完成。

返修后第二次送审应至少提供：

- 一个贯穿 control daemon 与 Codex Worker profile 的部署后端选择测试；
- 一个旧 `scidiscovery-worker.service` 存在时的升级删除与失败回滚测试；
- 更新后的当前架构/协议/TCAD/33 项证据及可复算的全生产规模口径；
- 原有 Local、纯 MCP Hardened、TCAD Local、Hardened+TCAD 拒绝、review、approval、Effect 和 clean
  wheel 聚焦回归。

修复应保持当前已经成立的一个 Operation 目录、一个 preflight/invoke、一个 Run 科学权威和两个
后端的薄边界，不得为解决部署配置与文档问题重新引入 Task、兼容转发或第二注册表。
