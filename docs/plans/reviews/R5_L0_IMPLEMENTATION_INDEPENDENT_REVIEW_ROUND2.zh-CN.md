# R5-L0 实现候选第二轮独立复审

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与 L0 实现和返修）  
结论：**通过；只放行 L1，不放行 L2—L6，也不放行 S3—S6/H7**

## 1. 本轮绑定范围

本轮以当前工作树而不是历史审查结论为准，绑定以下候选：

- `R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md`：
  `1c901f130a2e25b367d2e503d59cde41b644bd74c068b7afdd68b4ebd280210c`；
- `R5_L0_S2_CLASSIFICATION_AND_HARDENED_FREEZE.zh-CN.md`：
  `66d0d5685b72a22cb15959aa04262e49fed707db2dba1c29567946f6c0ba3a51`；
- `R5_L0_SOURCE_ENDPOINT.sha256`：
  `5811ae85499247ef56977b2e1e3f62a2f64bb9a9aab24875a345e341f975d986`；
- `test_l0_lifecycle_contract.py`：
  `d4b6a5271e0dc0ccfbae7f28cf93d10d19992a4db577fd2ab346b4833138a8b9`；
- `test_worker_exact_dispatch.py`：
  `d3a151708b1c82d13132351e7e35c0a967ff52e9e34bedca9716a2efbd0db13f`；
- S2 起点仍为 208 项，清单摘要
  `96740af4dcce821dc376adfb41e9f8bd5cf026a566c7bc8e2b4caf3d67347e53`。

本结论不声称 `LocalTrustedBackend`、`RunService`、盲插件或新 TCAD 闭环已经实现；L0 的职责只是
冻结迁移边界并为后续减重建立不可退化见证。

## 2. 首轮阻断闭合情况

### 2.1 终点清单和四类账本已可复算

独立复算结果如下：

- `sha256sum -c --quiet docs/plans/evidence/R5_L0_SOURCE_ENDPOINT.sha256` 通过；
- 按该清单声明的生产范围重新枚举，实际文件和清单均为 209 项，双方集合差为零；
- 与 `R5_S2_START_SOURCE_SNAPSHOT.sha256` 比较：28 个共同路径内容变化、0 个路径消失、唯一新增
  `src/scidiscovery/operations/lifecycle.py`；
- 证据文件第 1.1 节列出的 29 个变化/新增路径与上述集合一一对应；首轮误写的
  `TaskTokenService.issue_dispatch_capability` 和 `WorkerProxyLeaseKeeper` 已分别纠正为真实符号
  `TaskTokenService.issue` 和 `_AutomaticLeaseKeeper.observe`；
- `prepare_exact_dispatch`、`claim_exact`、exact capability/session 恢复被归为 Hardened 私有能力；
  `prepare_dispatch`、`claim_next` 和无 capability 的 role-queue fallback 被唯一归为“从默认路径撤回”。

role queue 的两个现有测试仍证明迁移期旧路径没有被 L0 意外破坏，但冻结文件已经明确把它们标为
迁移见证并要求 L6 删除，未再把普通角色队列误写为 Hardened 目标能力。因此首轮关于互斥分类和
长期兼容入口的阻断已关闭。

### 2.2 三个提交崩溃窗口已有真实进程证据

`test_worker_exact_dispatch.py` 新测试不是在同一 pytest 进程里重新构造 Router。它通过
`subprocess.Popen` 启动独立 Python 进程，进程内实际建立 `UnixSocketDaemon` 和
`WorkerBrokerRouter`，客户端通过 Unix Socket JSON-RPC 调用，然后让该进程以不同退出码退出并启动
新进程读取同一持久状态。三个窗口的边界可由生产调用顺序和断言共同确认：

1. **seal 后**：测试只在 `TaskService.submit_result` 已调用 `validate_output_file`、冻结候选并把任务
   置为 `finalizing` 后，替换的 `finalize_file` 才退出；重启后只允许恢复同一 sealed 候选。
2. **Artifact 后、Task CAS 前**：测试包装真实 `ArtifactRegistry.register`，先完成带
   `task:{task_id}:output:1` 幂等键的登记，再退出而不返回给 `_finalize_validated_output`；测试同时
   断言登记记录存在，重启后幂等复用并完成原任务。
3. **completed 响应丢失**：真实 Broker 已完成请求处理且持久任务为 `completed` 后，包装器在 Socket
   写回响应前退出；重启后 open/submit 都只返回同一完成投影。

同一矩阵还证明：

- seal 场景把 exact/session 绝对期限设为 3 秒并在重启前等待超过该期限，仍只能在既有
  finalization hard deadline 内继续；
- hard deadline 被置为过去后，重启 open 失败并把任务收敛为 `timed_out`；
- 错误 proxy、worker、authority、task、attempt 和 session 持久绑定均失败关闭；
- 重启前后 attempt 与 absolute deadline 不变，session 表始终只有一行；另一个专门测试还确认
  lease、last activity 均未被重启 open 续期；
- `finalizing` 恢复时 heartbeat 被拒绝，只能 submit。

崩溃注入完全位于测试文件的子进程脚本中。对 `src/`、三个产品插件和 `deploy/` 搜索没有发现
`SCID_TEST`、三个 crash mode 或 pytest 分支；生产实现没有为了通过这些测试增加隐藏状态或特判。
因此，测试既是真实跨进程/跨 Socket 恢复，又没有把测试开关带入产品协议。首轮恢复证据阻断已关闭。

### 2.3 生命周期单一投影已有直接合同测试

`test_l0_lifecycle_contract.py` 直接覆盖首轮要求的五类边界：

- 外部 fixture 尝试把 `worker_open_assignment` 注册为插件工具时，目录编译以
  `agent_lifecycle_tool_collision` 失败关闭；
- 将编译器所消费的协议版本从 `1` 改为 `2` 后，`PermissionTemplate.lifecycle` 随之变化，Agent
  Operation digest 也发生变化；协议不是摘要之外的旁路字段；
- 同一编译 Operation 的 lifecycle 名称/capability 被投影到 Task authority，Codex TOML 的
  `enabled_tools` 精确等于 Task worker tools，Worker Router 至少且只通过编译 Operation 增加领域
  工具；安装探针从 `AGENT_LIFECYCLE_PROTOCOL.tools` 读取固有工具，而不是维护固定数量的第二表；
- 架构 fixture 通过自己的 `ComponentSpec` 注册生产 `RUN_ANALYSIS_TOOL`，编译后 authority 得到
  `analysis.python`，真实调用 `worker_run_analysis` 在隔离分析进程中成功返回；这不是直接调用 fixture
  handler 冒充外部工具；
- 无效完整结果第一次 submit 返回 `rejected` 且仍可编辑；JSON patch 修正后下一次 submit 直接返回
  `completed`，Task 同步成为 `completed`，不存在公开 validate/finalize 二段协议。

生产代码只有一个 `AGENT_LIFECYCLE_PROTOCOL` 声明；`AGENT_LIFECYCLE_BY_NAME` 是由该值对象即时生成
的只读索引，`LIFECYCLE_WORKER_TOOLS` 是从同一协议生成的 MCP 投影，不是第二注册权威。插件工具仍
来自精确 `OperationSpec.executor.tools`。首轮生命周期合同阻断已关闭。

## 3. 没有新增双路径或伪装后端

本轮对生产树搜索未发现 `LocalTrustedBackend`、`HardenedWorkerBackend`、`RunService`、
`SealedWorkspace` 或 `WorkspaceBackend` 的提前包装实现。当前仍是待拆的旧 Task 路径，证据文件也
如实把其职责分为共享纯合同、未来 Local 可复用纯能力、Hardened 私有能力和待撤回能力，没有将
`TaskService` 改名或包一层后宣称迁移完成。

同时确认：

- 没有第二个 Operation 目录、preflight、invoke、current 或科学准入入口；
- 三个固有生命周期动作消除了插件重复声明，没有把 PDF、analysis、web、通用编辑或 TCAD debug
  并入巨型 submit；
- 服务端文件协议和 exact/session 恢复仍被冻结为 Hardened 候选，L0 没有为追求行数草率删除；
- `worker_submit_result` 返回的 `valid` 被明确标为 L0 过渡诊断，未形成第四个动作，计划要求 L2
  随旧 Task 外部合同一起删除；
- Local 原生工具隔离缺口继续按 `SEC-002 known_issue` 披露，没有以提示词禁令冒充安全边界。

这是一项真实但很窄的减重准备：新增一个无状态协议值对象，用它删除插件侧重复生命周期注册；其余
复杂恢复实现只被冻结而未扩散到默认目标。符合奥卡姆原则。

## 4. 对 33 项约束和通用插件目标的判断

L0 没有把 33 项约束全部改写为“已实证”，但其变更没有降低这些不可退化边界：

- `AUTH-003`、`ROLE-002`：生命周期、工具投影和摘要来自同一 CompiledOperation；Task、Codex、
  Router 与安装探针没有获得独立能力声明权；
- `AUTH-001`、`IMM-001`、`CQRS-002`：Worker 仍不能登记正式 Artifact 或解释终态；封存、幂等登记和
  Task CAS 仍由控制服务完成，恢复不产生第二终态；
- `AUTH-002`、`SEC-002`：capability/session 由 transport 绑定而非模型参数承载，错误绑定失败关闭；
  原生工具隔离仍是公开的已知问题；
- `RES-002`：恢复只沿用原 attempt/session/absolute deadline，hard deadline 之后失败关闭；
- `PLG-001`、`PLG-002`：核心没有 TCAD、曲线、Schema、角色或插件名分支；外部 fixture 只通过统一
  Component/Operation 入口获得 analysis 能力；
- `TOP-001`、`TOP-002`：L0 没有新增固定阶段或 role queue 作为目标调度语义，普通 role queue 已进入
  明确删除账本；
- `MIG-002`：部署探针仍验证编译目录，Hardened 的进程恢复事实已先冻结，后续拆分不得靠源码假设。

其余科学认识论、人工审批、外部执行、current 和资格约束不在 L0 的改动面内，本轮没有发现受其
影响的退化。L1 仍必须按计划用盲插件验证“低成本注册”而不是从本轮协议单测推断通用性已经成立。

## 5. 独立复算与测试

本轮在串行、低内存条件下执行：

1. 终点 209 项逐文件 SHA 校验：通过；
2. 重新枚举生产范围并与清单比较：209 对 209，集合差为零；
3. 起点/终点差异：28 changed、0 missing、1 new；
4. 生命周期和 exact dispatch 两个核心文件：`21 passed in 10.77s`；
5. 生命周期、exact dispatch、Worker Router 拆分、运行插件门、精确 Operation 工具、Worker
   authority、Codex 平台和部署聚焦集合：`74 passed in 62.45s`；
6. `git diff --check`：通过。

候选文件记录的完整非 live operation 集为 `294 passed`。本轮没有重复运行该完整集合，因为首轮已
运行当时全集，第二轮新增风险均由上述 74 项聚焦集合直接覆盖；测试数量不作为通过依据。

## 6. 非阻断改进项

1. 证据文件写“聚焦跨协议 75 passed”，但没有记录精确命令；本轮按第 4.4 节能直接复原的命令收集
   到 74 项且全部通过。建议后续进度记录附精确 node-id/命令，避免把测试计数当成不可复算证据。
   这不影响本轮语义边界，因为所有点名的生命周期、恢复、Router、插件、平台和部署检查都已运行。
2. 第 1.1 节插件路径使用了 `curve_score/...`、`tcad_artifact/...` 的缩写，而终点 SHA 清单使用完整
   仓库相对路径。建议下一次机械更新表格时统一为完整路径；当前缩写无歧义且 29 项集合已由 SHA
   清单精确绑定，不构成放行阻断。
3. 可在 role-queue 两个测试名称或测试标记中直接加入 `migration_witness`，使 L6 删除检查无需依赖
   计划正文解释。当前证据第 4、5 节已明确其唯一撤回终点，因此不是双重权威。

## 7. 最终判定和允许的下一步

**R5-L0 第二轮独立实现复审通过。首轮三项阻断均已由可复算账本和直接执行证据关闭，未发现新的
架构阻断。**

只允许开始 **L1：最小合同投影和盲插件**。L1 必须继续运行本轮冻结的生命周期和 Hardened 防腐
测试，并由未参与实现的审查者明确通过后才能进入 L2。当前结论不授权提前实现 Local Run、TCAD
新闭环、Hardened 接回、旧 Task 删除或 S3—S6/H7。
