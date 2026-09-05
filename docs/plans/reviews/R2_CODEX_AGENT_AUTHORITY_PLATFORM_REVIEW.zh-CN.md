# R2 Codex 子智能体授权平台独立复审

日期：2026-08-27
审查者：R2 独立审查者（未参与本阶段实现）
审查范围：Codex CLI 0.150.1 的角色授权边界，以及
`deliverables/r2-operation-live-qualification/2026-08-27-run13/` 的真实子智能体验收证据。
最终结论：**打回**。R2 不得进入 R3。

## 1. 结论摘要

run13 证明了目标 `agent_type` 已经由真实 `spawn_agent` 启动，且编译得到的专属提示词已进入
子会话；但它同时证明了决定性的运行平台阻塞：Codex CLI 0.150.1 的自定义角色只能在父会话
配置上覆写提示、模型等少数字段和关闭少数能力，不能替换父会话的 `mcp_servers`、沙箱或
permissions。SciDiscovery 写入 operation 角色文件的 Worker MCP 和只读权限因此没有成为子会话
的实际授权。

在以下三项约束同时成立时，当前版本没有可行配置：

1. 必须用父调度会话内的 `spawn_agent` 派发；
2. 每个 OperationSpec 必须获得按任务收窄的 Worker MCP、文件、命令和网络权限；
3. 父调度者不得获得 Worker 权限。

父会话不持有 Worker MCP 时，子会话无法通过 role 增加它；父会话持有 Worker MCP 时，又直接
违反第三项，并使所有继承该父授权的子会话具有过宽能力。共享父权限不能作为修复，也不能用
提示词约束冒充执行边界。

因此，run13 不是“基本通过，仅缺一个测试”，而是暴露了当前 Codex 平台和冻结验收约束之间的
能力不相容。现有 R2 的 Task 权限摘要、Worker 服务端验权和编译配置仍是有用基础，但在真实
Agent 运行边界尚未生效，不能据此宣称 OperationSpec 已形成无旁路的行为闭包。

## 2. 审查方法与证据完整性

### 2.1 本地版本和源码来源

独立执行：

```text
git -C /tmp/openai-codex-01501 remote -v
git -C /tmp/openai-codex-01501 describe --tags --always --dirty
git -C /tmp/openai-codex-01501 rev-parse HEAD
codex --version
```

结果：

```text
origin https://github.com/openai/codex.git
rust-v0.150.1
90854393966b21e9ebfd21b122334eb09a20c93d
codex-cli 0.150.1
```

因此，所审源码的 tag、提交和实际验收所用 CLI 主版本一致。`codex --version` 同时报告无法在
只读环境创建 PATH alias，但仍成功返回版本；该警告与下面的子会话 bubblewrap 失败分别记录，
不把二者混为一个结论。

### 2.2 run13 证据哈希复核

独立执行 `sha256sum` 后，父、子 rollout、`codex-events.jsonl` 和 `codex-final.txt` 的摘要分别为：

```text
29524af8f70bafe2af7907ce6709aa5fcf8ae8ada5e42c29391428500d4a4e63
f1329e588925076b640d7cb3537716e92e56b1d1d14d2979b20ce1d1bdf4e4ce
341817221ab962453f2feaf9f9c431a9b7e0ea27c7855c08fa4add63b3a676ff
4502fff260925f719b55abbda8d7349885b9c12513a73f4f7e95613b92526d87
```

它们与 `qualification-report.json:14-25` 记录完全一致，说明本次审查读取的是报告所指的原始
会话证据，而非之后改写的摘要。

### 2.3 独立检查

独立运行：

```text
python -m pytest -q \
  tests/operations/test_baseline_worker_authority.py \
  tests/artifact_agent/test_platform_configuration.py
```

结果为 `7 passed in 17.31s`。它证明当前 Python 配置生成器能稳定生成预期 TOML，但不能证明
Codex 子角色实际采用其中的 MCP 或 permissions；run13 正好反证了后二者。

尝试运行上游 Rust 专项测试时，第一次因 rustup 不能在只读
`<用户主目录>/.rustup/tmp` 建临时文件失败；改用已安装的 Rust 1.96.0 直接调用 cargo 后，又因
cargo 不能在只读 `<用户主目录>/.cargo/git/db` 获取缺失的 git dependency 失败。因此本报告没有把上游
Rust 测试写成“独立运行通过”，而是逐行审阅其测试实现和断言。这个环境限制不改变源码中的
白名单实现和明确断言。

## 3. Codex 0.150.1 是否禁止角色覆盖授权

结论：**是，而且不是偶然遗漏，是明确的安全模型。**

- `/tmp/openai-codex-01501/codex-rs/core/src/agent/role.rs:1-4` 明确声明角色可以定制子会话或
  降低能力，但不能替换父会话 authority。
- `role.rs:36-48` 的 `AgentRoleOverrides` 白名单只有提示、模型、推理设置、人格、服务层级、
  feature 和 skill；没有 `mcp_servers`、`sandbox_mode`、approval policy 或 permissions。
- `role.rs:69-128` 虽然解析完整角色 TOML，但只把白名单字段复制进 `AgentRoleOverrides`，再用
  该投影建立下一配置。因此角色文件能被 TOML 解析，不等于其所有字段会生效。
- `role.rs:91-117` 只允许关闭指定 feature 和 skill 设置；不能利用该入口增加角色专属 MCP，
  也不能建立 operation 级路径或网络权限。
- `role.rs:178-237` 先 clone 父配置，再只应用上述白名单字段，授权对象本身保持父值。

上游测试把这一边界写成了显式不变量：

- `role_tests.rs:354-390` 让角色尝试声明自己的 workspace root，最后断言
  `config.permissions == parent_permissions`。
- `role_tests.rs:394-456` 构造一个试图设置 `approval_policy=never`、
  `sandbox_mode=danger-full-access` 和 `[mcp_servers.attacker]` 的 hostile role，最后断言
  permissions 和 `mcp_servers` 均与父配置相同。
- `role_tests.rs:461-480` 进一步断言角色投影层根本不含 `sandbox_mode`、`mcp_servers` 等键。

这里应准确区分两个概念：Codex 防止“不受信任角色自行扩权”是合理的；R2 所缺的是由可信
平台在派发时把一个预注册、不可由模型篡改的 task authority **委派给子会话且不授予父会话**
的能力。0.150.1 的 `spawn_agent`/role 投影没有这个受控委派通道。

## 4. run13 是否真实启动目标角色并缺失 Worker MCP

结论：**是。**

### 4.1 角色注册和声明本身正确生成

- `project/.codex/config.toml:37-39` 把
  `op_builtin_test_agent_71b0d5d53db8` 注册到其生成角色文件。
- 同文件 `:49-56` 表明父调度会话的 `scidiscovery` MCP 指向 Root
  `mcp_proxy`，暴露的是 scheduler 工具，不是 Worker broker。
- operation 角色文件 `project/.codex/agents/op_builtin_test_agent_71b0d5d53db8.toml:2-7`
  声明专属名称、模型、permissions 和提示；`:16-23` 声明指向 Worker socket 的
  `mcp_worker_proxy` 及九个精确 Worker 工具；`:25-26` 声明只读权限。
- 生成实现与该产物一致：`src/scidiscovery/platforms/codex.py:225-255` 从 compiled operation
  投影模型、提示、原生工具开关、精确 Worker 工具和权限；`:325-358` 生成 Worker MCP；而
  `:288-310` 生成父调度会话的 Root MCP。

这证明 SciDiscovery 生成了想要的文本合同，但上节源码证明 Codex role 应用器会丢弃其中的
MCP 和 permissions 字段。

### 4.2 子会话确实使用了指定 agent role

子 rollout
`codex-session-evidence/2026/08/27/rollout-2026-08-27T22-45-08-01a043ae-8f35-7032-92fa-9e86c2c364f5.jsonl:1`
记录：

```text
thread_source=subagent
depth=1
agent_role=op_builtin_test_agent_71b0d5d53db8
cli_version=0.150.1
```

同文件 `:3` 包含 operation 专属 developer instruction。故“角色没有被启动”不是失败原因；
失败发生在角色授权不能替换父授权。

### 4.3 Worker MCP 没有进入子会话

- 子 rollout `:13-14` 第一次精确搜索 Worker 工具时，只返回无关的 app namespace；`:41-42`
  对精确字符串 `worker_file_write_begin` 的搜索返回 `tools=[]`。
- 整个子 rollout 没有任何 `worker_claim_task`、`worker_fixture_inspect` 或其他
  `mcp__scidiscovery` Worker function call；仅有这些名字出现在提示、搜索字符串和最终错误说明。
- `qualification-report.json:54-60` 显示任务最终仍为 `dispatched`，输出为 null，领域工具收据为空，
  总 verdict 为 fail。

因此不能把“专属 agent role 已启动”表述成“OperationSpec 的真实工具闭包已生效”。

## 5. 原生 shell 和负例是否通过

结论：**没有。shell 在执行被测命令之前发生基础设施失败，因而正例和负例均未得到验证。**

- 子 rollout `:71` 确实发出最小只读命令 `cat native_probe.txt`。
- `:72` 在零秒内以 code 101 返回，错误为：

  ```text
  failed to open synthetic bubblewrap mount registry lock
  /tmp/codex-bwrap-synthetic-mount-targets-1000/lock:
  Read-only file system (os error 30)
  ```

- 早先的原生命令在 `:49-51` 以同一原因失败。失败发生在 linux sandbox 初始化阶段，不是
  `cat` 的文件权限判定，也没有执行实际写入或 HTTPS 请求。

验收器这里还有一个需要修正的判据：
`tests/operations/live_operation_agent_qualification.py:345` 只以禁止文件不存在计算
`write_probe_absent`，`:352` 直接把它记作 `native_write_was_blocked`。所以
`qualification-report.json:5` 的 true 只能证明文件最终不存在，不能证明 Agent 发起写入后被
执行层拒绝。Agent 的最终消息也明确说没有完成写入和网络探测（子 rollout `:76-79`）。

后续验收必须分别观察：

1. 允许的只读命令确实成功并读到精确内容；
2. Agent 确实发起越界写入，执行层以可归因的权限错误拒绝；
3. Agent 确实发起网络请求，network none 或域名/次数策略以可归因的权限错误拒绝；
4. 这些失败不是 shell、broker 或 sandbox 根本无法启动。

应给 sandbox helper 一个隔离、可写的内部运行时/锁目录，或使用修复该初始化问题的平台版本；
不得通过给 Agent 开放共享项目写权限或共享父权限来规避。具体目录机制应以 Codex 平台支持的
配置为准，不能在 SciDiscovery 中猜测未公开环境变量。

## 6. 三项硬约束下的可实现性证明

令 `P` 为父调度会话实际拥有的 authority，`C` 为 `spawn_agent` 子会话 authority，`W_t` 为任务
`t` 所需的精确 Worker authority。Codex 0.150.1 的实现给出：角色不能替换 `P` 的
MCP、sandbox 和 permissions；在这些维度上 `C=P`，只能在少数 feature/skill 维度降权。

- 为满足“调度者不能获得 Worker 权限”，必须有 `W_t` 不属于 `P`。
- 为满足“OperationSpec 按任务最小授权”，执行子会话必须获得 `W_t`。
- 但内部 `spawn_agent` 无法使 `C` 在上述授权维度不同于 `P`，所以 `W_t` 也不属于 `C`。

若把 `W_t` 加入 `P`，第二项表面可运行，但第一项被破坏，而且不同 operation/任务的子会话都
继承该权限并集；这也破坏“未声明工具不可见”“精确任务路径”“普通 Worker 不得 spawn”以及
兄弟任务隔离。服务端的 task token 验权虽可降低部分后果，却不能消除调度者可见/可调用 Worker
入口、原生文件/网络权限和跨任务权限并集，因此不是等价实现。

结论是在当前 0.150.1 下，三项硬约束没有同时可满足的配置解。继续调整
`.codex/agents/*.toml` 不会改变这个结论。

## 7. 三种处理方案的裁决

### 7.1 升级或等待具备受控子会话委派的平台能力

这是在“必须 `spawn_agent`”不可修改时唯一合规方向，但不能假定任一更新版本已经支持。升级后
必须先做源码/配置契约审查和真实 qualification，至少证明：

- spawn 从可信、预注册 profile 获得 child-only MCP，模型不能通过任意 role name 自行扩权；
- 子会话只获得本任务 Worker proxy 和精确工具，父会话仍只有 Root MCP；
- 子会话 sandbox roots、命令模式和网络策略可以按任务收窄，且服务端/沙箱再次验权；
- 普通 Worker 的 delegation 关闭；兄弟路径、未声明领域工具和网络都有真实负例；
- broker 重启后只恢复同一任务、同一 authority digest，不漂移到父权限或工具并集。

在这些门通过前，R2 保持打回，不得仅因为版本号变化放行。

### 7.2 每任务独立 Codex 进程执行适配器

这是当前平台下最小、且不背离最小授权理念的工程替代，但它**不满足当前冻结的“必须由内部
`spawn_agent` 派发”验收文字**。若用户明确同意修改这一条架构决定，它可以成为推荐实现；未经
该决定不得静默替换并宣称 R2 通过。

可接受边界如下：

- 仍由现有 Operation invoke 创建现有 Task/attempt；不新增 OperationRun、第二任务状态机或
  另一套恢复权威。
- Agent runtime adapter 为每个 dispatched task 启动一个全新的 Codex 进程和独立配置根；该
  顶层进程只配置本任务 Worker MCP，不配置 Root MCP，也不继承调度会话配置。
- Worker proxy 绑定精确 task/attempt/authority digest；进程没有选择其他任务或其他 worker id
  的能力。
- task-scoped sandbox 只暴露允许的只读输入和受控工作路径；网络、命令、图片及领域工具来自同一
  compiled authority；普通 Worker 禁止 collaboration/spawn。
- 进程 stdout、退出码或模型最后一段话都不是科学结果；唯一完成路径仍是
  claim → 工具 → 受控文件 → validate/finalize → reconcile。
- 进程崩溃、重启和 broker 恢复继续复用现有 Task CAS 与 attempt 截止时间；进程对象只是暂态
  transport，不得成为新的生命周期实体。
- 真实验收仍须包含允许的原生/领域工具正例、路径/网络/未声明工具负例、以及恢复不漂移。

这一路径不是“外部科学 Effect”；它只是 Agent executor 的运行隔离适配器，不能借机绕过真实
Effect 的 ExecutionRequest 和 UI 审批。

### 7.3 给父调度会话共享 Worker 权限

**明确拒绝。** 这会把 Root 控制权限与 Worker 内容/文件能力合并到同一个主体，并把所有
operation 的工具、路径和网络能力提升成父会话/兄弟子会话的并集。无论再加提示词、agent role
名称或服务端部分拒绝，都不符合按任务最小授权，也不能满足用户要求的“未声明工具不可见”。
不得用此方案制造 qualification 假通过。

## 8. 阻塞项与允许的下一步

### 阻塞项 B1：真实子会话 authority 未由 OperationSpec 闭合

生成角色文件中的 Worker MCP、permissions 和网络声明在 Codex 0.150.1 子角色中不生效；真实
任务没有 claim、工具收据、输出、finalize 或 reconcile。R2 核心验收未完成。

### 阻塞项 B2：原生工具资格证据无效

只读正例和写入/网络负例都被 bubblewrap 初始化失败遮蔽；当前
`native_write_was_blocked=true` 的判据还会把“根本未尝试”误报成“执行层拒绝”。必须修正验收
判据并在可启动的隔离 sandbox 中重跑。

### 当前允许的下一步

只能在 R2 内选择并完成以下一条：

1. 采用经源码和真实测试证明支持 child-only authority 的 Codex 平台版本，继续用
   `spawn_agent`；或
2. 由用户明确修改“必须内部 `spawn_agent`”的架构决定，然后实现上述每任务独立 Codex 进程
   适配器。

无论选择哪条，都必须重跑完整真实链路并再次独立复审。不得共享父权限，不得把服务层单测、
TOML 文本或不可启动的 shell 当成 Agent 边界证据。

## 9. 最终结论

**打回。**

Codex 0.150.1 官方源码和 run13 原始子会话证据相互印证：专属 `agent_role` 已启动，但其
Worker MCP、sandbox 和 permissions 不能替换父会话 authority；同时 shell 在 bubblewrap 初始化
阶段失败。现有方案无法同时满足“必须 `spawn_agent`”“OperationSpec 按任务最小授权”“调度者
不得获得 Worker 权限”。R2 只能修复或作出明确的平台适配架构变更，不允许进入 R3。
