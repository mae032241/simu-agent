# R5-M7.2 Effect 审批恢复独立审查

日期：2026-09-02  
审查对象：`scripts/m7_live_effect_probe.py` 的同一 pending Effect 恢复路径，以及
`deliverables/m7-live-effect-20260902-01/` 的只读控制状态  
结论：**PASS；阻断项 0。**

本审查没有启动 UI、执行或审批，没有读取审批访问令牌、CSRF、nonce 或其内容，也没有修改持久根。

## 1. 同一控制对象恢复

当前持久根只读复算结果为：

- 一个名为 `m7_live_effect` 的活动 ResearchInstance；
- 同一实例下恰有三个语义绑定：一个 `replay_request` Artifact、一个 `m7_frozen_copy` Execution、一个
  `m7_frozen_copy.approval` Approval；
- 恰有一个 Execution，adapter 为 `m7_effect_fixture:adapter`，状态为 `created`，decision、外部运行标识
  和结果均为空；
- 恰有一个 Approval，状态为 `pending`，decision 为空；审批决定、决定尝试和已用 nonce 表均为零；
- ApprovalRequest 的冻结 subjects 与该 Execution 的 ExecutionRequest、payload 两个精确引用及顺序
  一致；
- 不存在 `final-evidence.json`。

`resume()` 只通过 `select_instance()` 读取已存在的活动实例，不调用 `create_instance()`、
`_register_request()` 或 `operation_invoke()`。它先复算安装目录、冻结 manifest 和运行插件 binding，
再要求实例内恰有一个 `created` Execution 和一个 `pending` Approval；随后按既有语义名解析原对象，
从不可变 ApprovalRequest 校验原 subjects。没有创建 revision、第二审批或第二 Execution。因此恢复的
是同一控制对象，不是以相同名字重建一套对象。

## 2. 人工决定和显式执行边界

恢复路径在展示页面前再次调用 `execution_start`，并要求它因 Approval 尚未决定而抛出
`ExecutionApprovalError`。之后只轮询只读 `approval_status`；代码中没有 HTTP POST、
`record_ui_decision`、审批写工具或自动代审。

当旧访问能力已过期但 ApprovalRequest 本身仍是 pending 时，脚本不调用 `refresh_access()`。它只显示
同一个 ApprovalUI 的首页。首页中的“刷新访问链接”是用户主动提交到 loopback UI 的操作：UI 校验
精确 Host、Origin、当前 UI 会话 CSRF 和原 approval id 后，只更新该 pending 请求的访问能力，不创建
新的 ApprovalRequest，也不记录授权决定。用户随后仍须在精确 review 页面再次显式选择并确认。

只有 `_wait_for_decision()` 从控制面读到允许的 UI 决定后，`_collect_effect()` 才依次显式调用
`execution_start`、`execution_sync` 和 `execution_outputs`。拒绝、审批请求过期或等待超时均不会启动
adapter。人类决定的唯一性没有因恢复或刷新访问能力而减弱。

## 3. loopback、Host 与 Origin 安全

- UI 始终实际绑定字面地址 `127.0.0.1`；`--ui-port` 只选择该 loopback socket 的端口。
- 对用户显示的 authority 固定为 `http://localhost:<实际端口>`，没有切换到通配地址或非 loopback
  接口。
- 主动可用性检查先要求 scheme 为 `http`、hostname 为 `localhost`、端口与实际监听端口一致，再连接
  `127.0.0.1` 并发送 `Host: localhost:<端口>`；它只执行 GET，不发送决定。
- ApprovalUI 原有 Host 校验接受的仍只是同端口 loopback authority；POST 决定和访问刷新继续要求
  同端口合法 loopback Origin。探针没有修改或绕过这些生产校验。

审查者收到的临时副本实测事实为：当前恢复分支打印 `http://localhost:8766/`，主动 GET 返回 200，
一秒后只因等待人工决定超时，未产生执行。该试验与上述静态路径一致，但本审查未把临时副本状态
混入正式持久根证据。

## 4. 证据字段真实性

- `resumed_same_pending_approval=true` 由同一持久根、唯一实例绑定、唯一 pending Approval、唯一 created
  Execution 和精确 subjects 共同支持；它不表示新建了请求。
- `start_before_decision_blocked=true` 由恢复路径中的真实负例调用支持。
- `preflight_admissible=true` 在恢复时针对当前已安装目录和原输入绑定重新计算。
- `approval_decided_in_loopback_ui=true` 只会在本次恢复先观察到 pending、随后轮询到 UI 决定后写入；
  脚本没有另一条决定写路径。
- `invoke_created_execution_and_approval=true` 描述本持久根已存在且经唯一绑定、状态和 subjects 复核的
  原始 invoke 事实；resume 本身没有再次 invoke。
- 执行开始、收集和输出摘要字段只有 start/sync/outputs 全部完成并重新读取封存 Artifact 后才会写入
  `final-evidence.json`。

未发现通过伪造布尔值绕过控制状态的路径。

## 5. 简化与架构判断

恢复实现复用既有 Artifact、Approval、Execution、安装目录、runtime factory 和 UI。新增内容只有：

- 一个显式 `resume` 命令分支；
- 一个只读 localhost GET 可用性检查；
- 一个原子更新的用户提示文件；
- 对已存在对象数量、状态和 subjects 的失败关闭检查。

它没有恢复旧 Task/Worker broker、审批创建工具、第二 catalog、第二 current、第二执行状态机或后台自动
刷新/自动执行。`pending.json` 只是给用户传递本次可访问页面的探针文件；最终判断仍来自控制数据库，
它没有成为 Approval 或 Execution 的第二事实权威。实现针对实际发生的“进程退出导致 UI 消失、访问
能力随后到期”恢复问题，规模与风险相称。

## 6. 非阻断项

1. `resume()` 与初始 `run()` 重复少量运行时装配代码。当前只有两个调用点，立即抽象反而会隐藏关键
   恢复差异；暂不重构更符合奥卡姆剃刀。
2. UI 在 `start()` 后、进入 `try/finally` 前仍有少量纯本地对象装配；若这几行发生异常，UI 线程可能
   需要进程退出清理。该风险不改变审批或执行事实，也不阻断本次受控恢复。

## 7. 最终判断

当前恢复路径可以继续用于原持久根：它恢复的是同一 pending Approval 和 created Execution，过期的
只是访问能力。用户必须在 `http://localhost:<固定端口>/` 首页主动刷新原请求的访问链接，再在精确
review 页面作出决定；决定前不得调用后续执行，决定后才允许显式 start、sync 和 outputs。

本次 PASS 只覆盖 M7.2 第4项中这一次 pending 审批恢复，不自动证明 M7.2 第5项恢复矩阵或整个 M7
完成。
