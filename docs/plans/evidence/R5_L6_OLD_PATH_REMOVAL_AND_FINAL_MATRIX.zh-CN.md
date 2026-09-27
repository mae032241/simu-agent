# R5-L6 旧中央路径删除与最终矩阵证据

日期：2026-09-01  
状态：双重独立总审查通过，L6 完成

## 1. 本阶段实际完成的减法

默认运行权威已经从旧 Task 控制器切换为唯一 `RunService`：

- Root 只暴露 `operation_preflight`、`operation_invoke` 和 Run 查询/失败记录，不再装配 Task 路由；
- Agent Operation 只创建 `Run`，没有 Task 包装、兼容转发或双写；
- 删除 Task Schema、TaskService 及其拆分模块、Task token、中央 Worker daemon/proxy、Root Task route；
- 删除旧中央 Worker systemd 单元；安装器只启动 control 与 approval UI，TCAD control 仍按 adapter 配置可选；
- 删除旧实例/孤立状态在线删除管理器，避免为了历史清理继续维持生产控制协议；
- `SchedulerSignal`、输出清单和领域工具上下文已从 Task 私有类型迁为 Run/Operation 中性类型；
- TCAD debug 领域合同归 TCAD 插件，核心没有 TCAD、曲线、角色或 Schema 名称分支；
- `LocalTrustedBackend` 与显式 `HardenedWorkerBackend` 消费同一个编译目录和同一个 RunService。

生产扫描对以下旧权威符号为零命中：`TaskService`、`TaskToken`、`legacy_task`、
`WorkerTaskAccess`、`task_ref`、`task_private`、`mcp_worker_daemon`、
`mcp_worker_proxy`、`worker_socket`。部署脚本中 `scidiscovery-worker.service`
只存在于旧服务停用、事务回滚和卸载清单，不是当前服务。

## 2. 仍然保留且没有被误删的边界

- Artifact/CAS 的不可变字节、父链和实例语义名；
- ResearchInstance 与显式 current CAS；current 不代表科学正确或资格；
- 作者与独立 reviewer 的 Operation review edge；修订不继承旧审查；
- 人工决定只在 Operation 声明时创建，并且只能由 loopback UI 写入；
- Effect 仍由精确人工授权与领域 adapter 执行；
- Hardened 的 lease 只围栏同一 Run 的服务端文件传输，不写科学状态；
- Agent 之间仍只交换显式输入文件和封存输出，聊天只作不可信完成信号。

## 3. 最终安装与运行矩阵

| 验收项 | 自动化证据 | 结果 |
| --- | --- | --- |
| 干净源码发布与 wheel 插件所有权 | `test_git_release_builder_emits_clean_manifested_source`、`test_clean_domain_wheel_matrix_has_exact_plugin_ownership` | 通过 |
| 默认 Local Run | L2 Run、崩溃窗口、current 与 Codex profile 测试 | 通过 |
| 纯 MCP Hardened | L5 精确 Run、文件修改、接管、同 Run fencing、跨 Run 并行测试 | 通过 |
| Worker 工具投影一致 | Local/Hardened 的 assignment、Codex profile、实际 router 三方恒等；缺创建工具时 preflight 拒绝 | 通过 |
| 部署后端一致选择 | 同一 `SCID_WORKER_BACKEND` 驱动 daemon、systemd、Codex profile 与安装验证；人为跨后端 profile 在 Worker open 失败关闭 | 通过 |
| 无 Hardened 的普通插件组合 | 安装入口矩阵和 Local profile 测试 | 通过 |
| TCAD Local | L4 作者、领域调试、独立审查和 8 MiB/符号链接边界测试 | 通过 |
| Hardened + TCAD | 在创建 Run 前因原生工具要求统一失败关闭 | 通过 |
| review / optional approval | L3 精确修订审查与普通探索无审批状态测试 | 通过 |
| Effect | 基线 Effect 与执行审批身份测试 | 通过 |
| 部署回滚 | 安装事务、TCAD surface 回滚、服务清单测试 | 通过 |
| 默认无中央 Worker 服务 | 模板不存在；旧 unit 升级时事务删除，失败回滚恢复文件与原服务状态 | 通过 |
| Agent 集合输出边界 | Local/Hardened 能力原因、目录、preflight 和 Codex profile 一致失败关闭 | 通过 |
| 通用/领域边界 | 非 TCAD kind、推荐行动与 reviewed-equivalence 回归；通用生产源码无 Deck/TCAD 语义 | 通过 |
| 当前角色协议 | 只分发 scheduler；旧 common/Task/collection/finalizing 合同删除；Run 提交、current、review 职责与代码一致 | 通过 |

完整命令在 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2` 下串行执行：

```text
pytest -q
200 passed in 64.56s

bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh
通过

git diff --check
通过
```

## 4. 规模观测

- L5 结束时通用包 `src/scidiscovery`：159 个文件、62,025 行；
- L6 候选通用包 `src/scidiscovery`：101 个文件、27,260 行；
- 当前领域插件：45 个文件、22,763 行；
- 当前全部生产 Python（`src/scidiscovery + plugins`）：146 个文件、50,023 行；
- 其中通用 control/artifact 包：76 个文件、21,377 行；
- Operation 编译包：8 个文件、2,139 行；

行数不是正确性证明；它只证明 L6 没有用新包装器长期包住旧中央控制器。

## 5. 明确保留的原型限制

1. `LocalTrustedBackend` 依赖可信本地用户和编译提示约束；Codex 原生工具不可见性仍不是技术沙箱，
   `SEC-002` 不因本阶段完成而关闭。
2. Run v1 只接受一个 `result.json` 主输出。声明 Agent 集合输出的 Operation 会在同一目录中显示为
   后端不可用并由 preflight 失败关闭；不会假装已经支持。确定性 Transform 的多输出不受影响。
3. Hardened v1 只支持没有原生 shell、代码或 `view_image` 要求的 Operation；TCAD 第一版只走 Local。
4. 审批 UI 的信息层级和排版仍是已记录产品缺陷；安全合同通过不等于可用性已经完善。
5. 本阶段证明框架和 TCAD 最小纵向路径没有结构性回归，不宣称科学结论准确率或三领域优越性。

## 6. 双重独立确认

两个未参与本轮实现的独立审查者已经分别确认：

- 旧 Task 权威确实退出，而非改名或隐藏；
- Run/current/review/approval/Effect 的职责没有断裂；
- Local 与 Hardened 没有形成第二目录、第二 preflight 或第二科学状态；
- 已知限制被诚实失败关闭，没有用针对性补丁掩盖；
- 33 项矩阵是否与本候选一致，且没有把 25 项 `pending_review` 和 1 项 `known_issue`
  误写成全部满足；OperationSpec 中心和奥卡姆剃刀目标是否达到。

第一位最终审查在两次返修后明确 PASS，见
`../reviews/R5_L6_FINAL_INDEPENDENT_REVIEW_ROUND1_REREVIEW2.zh-CN.md`。第二位最终审查在运行时与
活动计划两轮返修后明确 PASS，独立聚焦回归为 `18 passed in 39.17s`，见
`../reviews/R5_L6_SECOND_INDEPENDENT_FINAL_REVIEW_REREVIEW2.zh-CN.md`。两份结论共同放行 L6 和
R5-L0—L6 整个系列。

33 项当前状态为 7 项 `conformant`、25 项 `pending_review`、1 项 `known_issue`。L6 只同步了现行
Run v1 语义和当前证据，不宣称 33 项全部通过；`SEC-002` 明确保留。
