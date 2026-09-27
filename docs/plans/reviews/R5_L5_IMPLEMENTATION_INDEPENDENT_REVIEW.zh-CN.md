# R5-L5 实现独立审查报告

日期：2026-09-01  
审查者：独立实现审查者（未参与 L5 实现）  
结论：**FAIL**  
放行范围：**不放行 L6，不放行正式发布**

## 1. 审查口径

本轮完整阅读并交叉核对：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` 中的总体目标、6.3、L5、L6、自动停止条件与当前状态；
- `docs/plans/evidence/R5_L5_OPTIONAL_HARDENED_AND_POLICIES.zh-CN.md`；
- L5 相关生产代码、Codex 投影、TCAD Operation 声明与聚焦测试。

审查不把“已有测试通过”直接等同于能力闭合，而是分别检查唯一科学权威、传输所有权、服务端文件、可选策略、插件边界及证据表述是否与真实实现一致。按要求未重跑已记录的 327/76 项大集合，只在 7 GiB 虚拟内存限制下串行运行最小聚焦测试和独立负例。

## 2. 总体判断

L5 的主要方向是正确的：Local 与 Hardened 确实消费同一 `RunService`；`HardenedWorkerBackend` 本身没有登记 Artifact、推进 current、解释科学结果或创建 reviewer；普通 `runs` 表也没有 qualification、approval、execution、session、token、attempt、lease、finalizing 字段。盲 CSV 链路确实通过独立 Python stdio 进程、注册领域工具和服务端文件完成了同一 Run，并未冒充真实 Sentaurus。

但当前候选不能通过 L5 完成门，原因不是 L6 尚未删掉旧文件，而是仍有三项当前生产行为与 L5 明示合同相冲突：

1. 短租约接管没有失效旧所有者；旧进程在新进程接管后仍能完成 Run；
2. 显式 Hardened Root 仍实际消费旧 `TaskService` 的 scheduler signal 与 reviewer 判定，因此旧科学权威并非“仅为历史测试实例化”；
3. Hardened Codex 投影会向 TCAD Operation 宣告 `worker_file_apply_patch`，但该后端对该工具固定报错；这是模型可见的虚假能力，并直接冲突于 TCAD 作者合同。

前两项分别违反“精确 Operation/传输归属”和“唯一 Run 科学权威”；第三项使显式 Hardened + TCAD 组合在编译时通过、运行时必然缺工具。均不能降为 L6 的普通删码事项。

## 3. 阻断项

### B1：租约接管没有 fencing，旧进程可在失去所有权后完成 Run

严重性：阻断。

`HardenedWorkerBackend.claim_transport` 只替换 `active_transport.owner_id`；`renew_transport` 才校验 owner。`HardenedWorkerMCPRouter.call_tool` 仅在 `worker_heartbeat` 前续租，领域工具、服务端文件工具和 `worker_submit_result` 均不校验当前 owner。因而“租约到期后新进程接回”并不会使旧进程失效。

独立复现步骤：

1. 创建一个 `blind.csv.observe.v1` Run；
2. 第一个 Hardened router 打开 Run；
3. 将其租约期限置为过去；
4. 第二个 Hardened router 成功接管同一 Run；
5. 再使用第一个 router 调用 `worker_csv_summarize`、服务端文件写入与 `worker_submit_result`。

实际输出：

```text
second_owns= True
first_domain_tool= 2
first_submit_after_takeover= completed
second_owner_still_recorded= True
```

即数据库声称第二个进程是 owner，但第一个进程完成了科学 Run，且第二个 owner 记录仍残留。这说明当前短租约是可观察状态，不是有效的精确所有权协议；已有并发测试只覆盖“有效租约时第二 owner 被拒绝”和“过期后第二 owner 能打开”，没有覆盖接管后旧 owner 必须失败的关键负例。

返修完成条件：接管后，旧 transport 的领域工具、文件修改、候选验证和提交全部失败关闭；新增真实双 router 负例，不得只验证 `heartbeat`。实现应使用通用 transport ownership/fencing 原语，不能针对盲 CSV 或单个工具加条件。

### B2：旧 TaskService 仍是 Hardened 生产 Root 的科学判断权威

严重性：阻断。

证据文档声称旧 Task/token “唯一用途是历史测试，生产 Root 和生成的 Codex profile 都不消费它们”，实际代码不成立：

- `open_runtime(worker_backend="hardened")` 创建真实 `TaskTokenService` 和 `TaskService`；
- `build_root_router` 将 `runtime.tasks` 传给生产 `RootToolFacade`；
- `_scheduler_signal_for_output` 在 Run 未命中时回退到 `TaskService.scheduler_signal_for_output`；
- `_is_exact_reviewer_output` 将 `TaskService.is_exact_reviewer_output` 与 Run 判定作逻辑或；
- Operation 输入准入、非资格传播、独立 reviewer 和修订请求检查会调用这些 helper；`scientific_inventory`、`lifecycle_events` 与实例关闭也读取旧 Task 状态。

虽然 Hardened Root 的工具列表隐藏了 `task_*`，但隐藏入口不等于移除权威。旧 Task 产物仍可影响新 Operation 的 scheduler signal、独立审查准入和科学库存；这正是计划 6.3 与自动停止条件明确禁止的情形。

返修完成条件：显式 Hardened 的生产 `RootToolFacade` 不持有、不回退读取旧 `TaskService` 科学事实。若历史恢复测试仍需旧服务，应放到明确的 legacy test/runtime 入口，不能注入 Hardened 生产 Root。旧代码实体本身可按 L6 删除，但其当前生产消费者必须在 L5 先断开。

### B3：Hardened 向 TCAD 宣告一个固定不可用的文件工具

严重性：阻断。

Hardened Codex 配置使用完整的 `operation_worker_tool_names(compiled)`。TCAD 作者和 reviewer Operation 显式声明 `file_apply_patch_tool`，作者提示也要求使用 `worker_file_apply_patch` 编辑已有 Deck；但 `HardenedWorkerMCPRouter` 将该工具列入文件工具集合后，在分派中固定返回“text patch is not enabled by this hardened backend version”。

独立编译检查确认四个 TCAD Deck Agent Operation 均向 Hardened profile 暴露 `worker_file_apply_patch`：

- `tcad.deck.author.initial.v1`；
- `tcad.deck.author.revise.v1`；
- `tcad.deck.author.runtime-failure.v1`；
- `tcad.deck.review.v1`。

这不是“未声明、所以不虚构”的能力，而是已经编译并展示给 Agent、调用必失败的能力。尤其修订与运行失败修复场景依赖文本修改，不能把盲 CSV 只用分块创建的通过结果推广为 Hardened 对已安装 Agent Operation 的完整支持。

返修完成条件：要么以共享、通用且有边界的实现提供已声明文本 patch，并覆盖 TCAD/普通文本负例；要么在编译/部署前失败关闭不受该 Hardened backend 支持的 Operation，且不得生成声称工具可用的 Codex profile。不能在运行时等 Agent 调用后才报固定错误，也不能用 TCAD 特判。

## 4. 已通过的边界

以下项目在本轮范围内未发现阻断：

- `operation_invoke → RunService → HardenedWorkerBackend → Operation-bound MCP → RunService.submit` 是同一 Run 主干，没有第二个 preflight/invoke 或第二目录；
- `HardenedWorkerBackend` 只保存 backend-private 的 `run_id/owner_id/lease_deadline_at`，没有直接科学写权；
- `OperationToolContext` 不暴露 Task/session/token、Artifact 注册、Run 终态、current CAS 或 reviewer 创建接口；
- 服务端分块创建、JSON patch、移动、删除均通过编译 Operation 工作区规则准入；此前通用目录句柄/`O_NOFOLLOW` 原语仍覆盖 output 父目录符号链接负例；
- 核心 Hardened、Run 和 Operation 模块没有 TCAD/Deck/Sentaurus 名称分支；TCAD 工作区与调试逻辑留在插件；
- 普通盲 CSV 的 runtime projection 中 cohort 为空，人工决定和 Effect 引用为 `None`；普通 Run schema 未被策略私有状态污染；
- cohort/人工审批/Effect 仍由声明这些合同的 Operation 选择性消费，没有新增中央 `PromotionPolicyService` 或 `EffectPolicyService`；
- 默认 `worker_backend="local"` 不创建旧 Task/token；Hardened 为显式部署选择，并未被包装成默认后端；
- L5 三个新增模块合计 616 行。`hardened_workspace.py`（102 行）和 `hardened_files.py`（248 行）职责集中；`mcp_hardened_worker.py`（266 行）虽与 Local router 有一定编排重复，但目前仍是后端适配层，不单凭行数构成复杂度阻断。返修 B1/B3 时应避免再增加一套 dispatcher 或能力投影。

## 5. 独立验证

所有命令串行执行，先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

- `pytest -q tests/operations/test_l5_hardened_run_backend.py`：`6 passed in 2.87s`；
- Effect、TCAD cohort 与 L3 可选策略聚焦回归：`4 passed in 40.80s`；
- 独立 stale-owner 双 router 复现：失败关闭预期未满足，旧 owner 实际完成 Run；
- `git diff --check`：通过；
- 三个 L5 新模块共 616 行；证据文档列出的六个 SHA-256 与当前工作树一致。

已有 6 项 L5 测试全部通过说明当前证据不是伪造，但测试集遗漏了决定租约是否真实有效的反向并发场景。因此这些绿测不能覆盖 B1。

## 6. 奥卡姆剃刀与 33 项约束判断

设计主体比旧 Task 中央控制器明显更小：一个 Run 权威、两个工作区后端、一个编译目录和可选策略投影是合理结构。未发现为 cohort 或 Effect 新建第二状态机，也未发现 TCAD 核心特判。

但当前候选仍同时保留“Run reviewer/signal 权威”和“Task reviewer/signal 回退权威”，形成了第二权威；短租约又没有形成真实 fencing，属于协议表面存在而安全语义未闭合。继续在这些路径上添加单工具判断会造成新的针对性补丁。返修应收敛到两个通用动作：断开旧科学权威的生产注入；建立一个所有 Hardened 调用共享的 owner/fencing 边界。文本 patch 则必须做到“声明即真实可用，或部署前明确不兼容”。

因此本候选尚不满足单一事实来源、最小授权、精确归属、能力声明真实和失败关闭等基本约束。

## 7. L6 边界

本轮结论为 FAIL，故不得开始 L6。

即使返修后 L5 通过，L6 仍必须完成而不能在 L5 冒充完成：

- 删除旧 Task/token/session/assignment/lease/finalizing 生产路径与临时双路由；
- 默认 wheel/deploy 不启动或导入旧 Worker daemon/proxy；
- 验证默认 Local、显式 Hardened、无 Hardened 插件、TCAD、review、approval、Effect 与回滚矩阵；
- 最终证明默认零旧消费者、唯一 Run 权威，并完成双重独立总审查。

只有 B1—B3 全部以领域无关方式闭合、补入对应负例并通过第二轮独立复审后，才可只放行 L6。
