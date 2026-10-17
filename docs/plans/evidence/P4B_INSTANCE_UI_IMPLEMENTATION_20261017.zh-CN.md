# P4b 最小实例状态与控制 UI：实施冻结

状态：**冻结并交独立静态审查；没有动态验收。** 基线含 P3d1 `c03d0c3`，依据 [P4/P5 方案](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md)与[设计独审](P4_P5_THIN_DESIGN_REVIEW_20261017.zh-CN.md)。这是最小 live 实例状态与暂停/继续入口，不是 P4c 归档、科研原文/完整材料浏览或 P2/P3 执行闭环。

## 公共入口与共享原语

- 仍使用唯一 `scid-research serve-ui --root ... --approval-secret-file ... [--port ...]`、loopback server、实例 host lock、BrowserAccessService 和每次新 boot。原 flag 名保持兼容；本地 regular/0600/至少 32-byte secret 同时用于浏览安全，不意味着必须启用正式审查或执行授权。
- 无 `execution_authority_policy` 的普通 local 实例也能启动状态管理页。此时不调用 `authority.contract/bind_secret`，不生成 execution host key/endpoint 原件；只有审批路由不可用，普通科研与管理不阻断。已启用 authority 的实例继续复核原合同/key 身份，审批原件仍属于同一 owner。
- 操作者 stdout 同时返回管理链接和只读链接；二者交换成同实例 cookie 后跳转 `/`，地址不保留凭据。GET 验 read scope；POST 验 maintenance scope、当前 boot/实例、精确 Host/Origin、CSRF 与 nonce。只读页面不显示写表单；只读 cookie、旧 boot/过期/错实例 cookie 不能写。没有 JSON 选 gate 或浏览权限升为科学/执行许可的入口。
- 新 `instance_control.py` 从 CLI 搬出原 `status`、`pause`、`continue` 实现，CLI 与 UI 调同一函数。`continue_instance` 保持原 `_writer + _inactive_on_error`，取得锁后才确认 correction/移除 pause；第二调用不能清除 live owner 的标记。`request_pause` 在写前保留 CLI 的 current-protocol 前置检查。
- 默认 CLI `status(root)` 保持完整既有返回；UI 只额外使用同一函数的 `after/limit`，每页 20 个节点及固定 `/nodes/{step}`，没有任意路径读取路由。节点页只显示角色、原 runtime 状态、停止原因/exit code 等元数据，不显示原生私有聊天或日志，也不把 seal 存在冒充已验证成果。
- UI 摘要选取现有 ledger 时间/ceiling、原 usage 的 observed tokens 与未知节点数、pause/correction 状态及当前控制结果；不调用 reconcile/settle，不修改 ledger。token 剩余明确标为依据已观测 usage 的差额，未知不消失。UI 不调用 live-feedback adapter；原 status owner 的本地验证/历史折叠仍存在，分页仅限制展示和节点页扫描，不声称所有状态读取都是恒定 IO。
- 节点分页保留后续 continuation；所有原记录不改、不新增文件数/字节 cap。页面是紧凑状态视图：stop reason 300 字符、临时控制 note 512 字符均带省略数；不宣称本页已提供科研原文/完整原件历史浏览。既有完整研究原件仍在原实例，未来 P4c 的只读包浏览独立实现。

## 长时继续与即时暂停的边界

root 本轮明确了已审设计的交互收窄：**唯一 inflight 约束长时 continue/推进；pause 是原语义即时写标记，不另起推进 owner。** 否则一次长 continue 会使管理页无法暂停。该区分不产生队列或新预算。

- `/control/continue` 通过全部浏览/表单检查后，唯一非 daemon 后台线程调用共享 continue；HTTP 不等待模型/推进完成。第二个进行中的 continue 明确拒绝，不排队。控制结果只是内存中的本次 UI 回执，权威科研/等待/预算状态始终从原实例读取；重启 UI 不重放它。
- `/control/pause` 即时调用共享 pause，先写原 `pause.request`，尝试原非阻塞 writer；已有 owner 忙时让已接受工作继续 finish/seal。它在长 continue 期间仍可使用；重复独立暂停保持同一语义。表单 nonce 接受后旋转，旧 POST 不能再次启动操作。
- correction trigger 由权威状态自动放入隐藏字段，操作者只写继续的理由；共享原 `correction.acknowledge` 再核 exact 当前 trigger，不让模型/人手填 hash/机械 ID，也不扩大原 correction 或预算授权。
- UI server 正常停止/KeyboardInterrupt 只关闭浏览服务及临时 endpoint，不 cancel、signal 或 daemon-exit 已接受继续线程。线程持有原控制 owner 并按原生命周期运行；异常/unknown 不被 UI 自动重试。这里没有声称任意 SIGKILL、机器关机或平台撤销不会中止进程。
- 共用 `instance_control.py` 的实际代码身份自动追加到 `authority.implementation()`，不依赖插件手列 assets；consume 时沿原代码 proof 校验。该单行与并行 d2a 的 `execution_inputs.py`/HostServices 改动隔离。

## 最小负控（仅编写，未运行）

新增 `tests/research_loop/test_instance_ui.py` 两条：

1. 使用普通无 authority 的真实 prepare/seal fixture，CLI 与共享分页保持相同节点语义，固定 node 入口可达、越界路径拒绝；审批不可用；read cookie 无写表单/写权限；错 Origin/CSRF、错实例/过期/旧 boot cookie 拒绝且无 pause 原件。
2. 真实共享 continue/writer 在后台线程中持锁，科学 `_run` 用有界 Event stand-in 防止启动业务；验证唯一长 owner、第二 continue 拒绝、忙时即时 pause、旧 nonce 拒绝、重复新 pause 幂等、外部 continue 不清除活 owner 的 pause。释放 fixture 后线程正常完成，原 pause 保留。此例没有 seal 伪造科学成功或生成 accepted。

既有 `test_execution_authority.py` 普通实例一条断言改为“管理页可用、审批路由 unavailable”，与新产品边界一致；其余 P3c Origin/boot/决定原件负控保留。未增加测试矩阵，没有运行这些用例。

## 精确冻结文件与共享 hunk

生产：

1. 改 `src/scidiscovery/research_loop/cli.py`
2. 改 `src/scidiscovery/research_loop/instance_ui.py`
3. 新 `src/scidiscovery/research_loop/instance_control.py`
4. `src/scidiscovery/research_loop/execution_authority.py` **仅一行**：`paths += [directory / 'instance_control.py']`

测试：新 `tests/research_loop/test_instance_ui.py`；改 `tests/research_loop/test_execution_authority.py`。文档：本实施记录；独审报告由 reviewer 持有。

共享 authority 的可独立应用 HEAD 的最小 patch 存在私有 `.trial/p4b-authority-helper.patch`，仅供 root 隔离暂存；已 `git apply --check --cached` 静态检查，未修改 index。不能整文件暂存并行 d2a 的 authority hunks，`.trial` 本身不提交。本轮未写 TCAD packager/compiler/adapter、experiments、contracts、budget 或新执行恢复路径。

## 静态检查及未验收范围

对 6 个自有/共享 Python 文件执行标准库 `ast.parse`，并做自有 tracked/new 文件 whitespace 检查；没有导入项目或运行 CLI、HTTP/浏览器、pytest/collect、安装/build、业务子进程、模型/solver。最小 authority patch 的 cached check 只验证可应用，不是 stage/commit。

真实浏览器/HTTP、服务停止时仍有 live native owner、后台线程完整推进/恢复、并发控制与真实 correction acknowledgment 尚未动态验收；Event stand-in 仅证明控制/writer 接缝，不证明平台/科研执行。P3d2-a 原件映射、P3d2-b 长等待恢复、P4c 只读归档与另审的可写恢复均未由本节点完成。宿主密钥/同 uid shell 仍是原软信任边界，不是 OS 隔离。
