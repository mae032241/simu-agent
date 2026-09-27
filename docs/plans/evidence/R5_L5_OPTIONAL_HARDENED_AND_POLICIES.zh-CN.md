# R5-L5 可选加固后端与策略证据

日期：2026-09-01  
状态：两轮独立审查打回后第三轮复审候选

## 结论

L5 没有把旧 `TaskService` 包装成新后端。实际生产调用已经可以显式选择
`HardenedWorkerBackend`，但创建、校验、登记和完成的仍是与 Local 完全相同的 `RunService`：

```text
operation_invoke
→ RunService
→ HardenedWorkerBackend
→ Operation 绑定的 stdio MCP
→ 服务端文件工具
→ RunService 校验并登记 Artifact
```

加固后端只持有一个短租约传输表：`run_id → owner_id → lease_deadline_at`。它不能登记
Artifact、更新 current、创建 reviewer、解释科学结果或写 Run 终态。科学完成仍只有
`RunService.submit` 一个入口。

## 实际消费者

盲 CSV 插件未经核心特判，通过 Hardened 后端完成了以下真实链路：

1. Root 从同一编译目录创建 `blind.csv.observe.v1` Run；
2. Operation 绑定的 Worker 调用注册工具 `worker_csv_summarize`；
3. Worker 只通过服务端分块文件工具写 `output/result.json`；
4. `RunService` 完整校验输出并登记唯一 Artifact；
5. Codex 安装投影使用 `mcp_hardened_worker`，不再指向旧 `mcp_worker_proxy`；
6. 独立 Python stdio 进程打开 Run 后退出；短租约到期后第二个新进程接回同一 running Run，调用
   注册工具、写文件并完成。没有创建 Task 或走角色队列。

并发第二传输所有者在租约有效时失败关闭。租约过期并由第二进程接管后，第一进程的领域工具、文件
编辑、候选校验和提交统一在同一个 transport guard 上失败关闭。每个 Run 使用独立的操作系统文件
锁；SQLite 事务只覆盖短时 owner 核对/续租，不包住领域工具。两个独立 Run 可并行，同一 Run 的接管
必须等待在途调用结束。`output` 父目录被替换为工作区外符号链接后，服务端提交失败且外部目录保持
为空。

Hardened 通用文件编辑器提供精确上下文 `worker_file_apply_patch`，支持 Codex patch 和统一 diff，
拒绝模糊匹配、重复上下文和越界路径；一个显式 `native_tools=none` 的真实 Agent Operation 已完成
创建、补丁、字节核对和陈旧补丁拒绝。

Hardened v1 是纯 MCP 后端。任何声明原生 shell、代码或 `view_image` 的 Operation 都在同一目录中
标记为 unavailable，preflight/Run 创建失败关闭，Codex 安装不生成其 Agent/profile。当前 TCAD
Operation 需要原生代码工具，因此继续由 LocalTrustedBackend 承载；Hardened+TCAD 是显式不支持的
组合，直到存在真正任务根沙箱或 TCAD 改成纯 MCP 合同。该结论比用提示词要求可写 shell “只读”更
诚实，也没有在核心加入 TCAD 特判。

## 可选策略不污染普通 Run

- 普通盲 CSV Operation 的运行投影中，qualification cohort 为空，人工决定和 Effect 引用均为
  `None`；
- `runs` 表没有 qualification、cohort、approval、execution、session、token、attempt、lease 或
  finalizing 字段；
- 资格 cohort 仍只由显式声明 cohort 的 TCAD Operation 在 preflight 消费；
- Effect 仍只由显式 Effect Operation 创建 Execution，并经过精确人工审批；这些事实不进入普通
  Agent Run。

L5 的资格与 Effect 证据复用了已有真实消费者，没有另建 `PromotionPolicyService` 或
`EffectPolicyService`。策略就是编译 Operation 中的可选引用及其既有窄服务，不是新的中央状态机。

## 验证结果

- L5、Hardened TCAD 拒绝与平台聚焦回归：`19 passed in 4.27s`；
- Operation 非 live 全集：`332 passed in 123.97s`；
- Artifact Agent 全集：`40 passed in 5.98s`；
- 首轮审查三个阻断均新增或强化直接回归：接管后旧 owner 全能力拒绝、Hardened Root 不持有
  Task/token、精确文本补丁真实可用；第二轮新增的跨 Run 并发和原生工具旁路也有直接正反例；
- `git diff --check`：通过；
- 生产 Python：159 个文件、62,025 行。L6 必须通过删除旧 Task 传输收回 L5 的临时增加。

关键文件摘要：

- `hardened_workspace.py`：`78d9314ec664dd6406626480f0f16c159fe58ef858499c801c0b393c5eabf6bd`
- `hardened_files.py`：`e9c64ad7cfd23d854ea818145db182eef6f3306ac8abacd966558078886647e4`
- `mcp_hardened_worker.py`：`338f4070200fb1293b76df38d0c1dcf0e2b3bda7f9e09ee109c28f2937580357`
- `runs.py`：`82ca3241037e7dfbd983cf02710e43bb371e2b615daf07852e941a877591d0d3`
- `codex.py`：`c625724483e931b47c2c9d573865b4655f8aa8702cd062cf23db5479de1ddf63`
- `runtime.py`：`0dd1058e0abd7ee7a7c2d4336ffd86c1d8c3c15410b9ae443fc9e657f570be67`
- `test_l5_hardened_run_backend.py`：`876eb44a9bd5d331a37281fa2717464a4d25266ca7e122781ed0eaca5934bee1`
- `test_l4_local_tcad.py`：`fac62a9693d9ac43c1cdc1804d4a92359aa8967318e160220cfc1b839e896ab7`
- `operation_declaration.py`：`c24ec01f68729245a3bdf4ecb3162af9ff2ef3eba2dfc7ddcfb43b428882ba21`
- 盲 CSV 插件声明：`591859202f481da2b1e193ef5f47d1cf2dce64ea5141b1053fdae579d42a2264`

## 明确未冒充完成的事项

- `open_runtime(worker_backend="hardened")` 只实例化 Run 和 Hardened backend，不创建 Task/token；
- 尚未迁移的旧恢复测试显式使用生产部署拒绝的 `legacy_task` 兼容选择器。旧 Worker daemon 也暂时
  明示进入该选择器，不能被误认为 Hardened 生产路径；
- 旧 Worker daemon、proxy、Task 路由和 `legacy_task` 测试兼容选择器必须在 L6 删除。只要它们仍在生产包中，
  L 系列就不能宣称完成。

## 首轮独立审查与返修

首轮报告 `reviews/R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md` 结论为 FAIL，并提出三个阻断：

1. 旧 owner 在租约接管后仍可调用；
2. Hardened Root 仍读取旧 Task 科学事实；
3. TCAD 已声明的文本 patch 在运行时固定失败。

返修没有增加领域分支或第二目录：B1 收敛为所有调用共享的 ownership guard；B2 将旧 Task 隔离到
明确的临时测试入口；B3 在已有通用 Hardened 文件编辑器中补齐精确 patch。首轮 FAIL 报告保留为
历史证据。第二轮报告
`reviews/R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 同样为 FAIL：一个数据库级长事务
把无关 Run 串行化，且 shell-enabled Hardened profile 可绕过服务端边界。返修已分别收敛为每 Run
文件锁和“纯 MCP 才能投影到 Hardened”的统一能力规则；第三轮独立审查明确通过前仍不放行 L6。
