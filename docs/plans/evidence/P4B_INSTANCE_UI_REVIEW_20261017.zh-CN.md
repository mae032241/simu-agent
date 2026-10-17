# P4b 最小实例 UI 独立静态评审

结论：**本节点静态 PASS，可按精确范围提交**。基线 `c03d0c3`；不代表 HTTP、浏览器、模型推进或服务停止场景已动态验收。

## 范围

阅读 `research_loop/cli.py`、新 `instance_control.py`、`instance_ui.py`，以及 `execution_authority.implementation()` 中**仅追加 instance_control.py 的一行**；新 `tests/research_loop/test_instance_ui.py` 两条与既有 `test_execution_authority.py` 普通实例断言改动；实施报告。并行 d2a 对 authority 的 execution_inputs/HostServices 改动不在本结论内，不能整文件暂存混入。

未运行 pytest/收集、项目 import、CLI、HTTP、线程测试、原生进程、构建或安装。作者的 AST/空白检查仅为静态检查，不转换成动态通过声明。

## 真实路径与结论

- `instance_control.py:7` 保留 CLI 原 status 默认返回；分页增加 after/limit，继续读取原 jobs/runtime/usage/ledger。UI `instance_ui.py:114` 仅取每页 20 节点或一个精确节点，禁用 live-feedback adapter，页面仍保留续页位置。分页不证明全部状态计算恒定 IO：原 usage、correction 与账本折叠仍存在。
- `instance_control.py:71` 保留 current-protocol 检查，先写原 pause.request，再尝试非阻塞原 writer；忙时不取消已接受任务。`:85` 的 continue 先取原 writer，再处理 correction 和删除 pause，第二调用不能清掉活 owner 的暂停标记。
- `instance_ui.py:87` 长 continue 仅一个非 daemon 线程；`:234` 在浏览验证后启动，重复长请求明确拒绝且不排队。pause 不受长 continue 的 inflight 限制。UI 没有新调度账、任务库或执行授权入口；停止浏览服务没有 cancel/signal/join 科研 owner 的分支。任意 SIGKILL/平台停止不在此保证内。
- `instance_ui.py:38` 普通无 authority 实例可用状态/控制；只有启用 authority 才绑定原合同和 key。无能力时审批路由明确 unavailable，不以使用 UI 为由强加正式审查或执行资格。
- `instance_ui.py:148` 的 read bootstrap 与 management bootstrap 分离；GET 要 read，POST `:226` 要 maintenance、精确 Host/Origin、实例/boot cookie、action/browser/nonce 绑定 CSRF；接受后轮换 nonce。只读页面无写表单。原 P3c 决定/撤销仍调用唯一 authority owner。
- 已要求并确认 authority 自动绑定实际共享行为模块 instance_control.py，避免只冻结 UI 委托方而漏掉实际控制 helper。该修复是本节点单独一行，不依赖插件作者列资产。

## 最小测试能证伪什么（均未运行）

1. `test_ordinary_instance_status_pages_and_browser_bound_controls` 使用现有 prepare/seal 原件，固定断言真实创建的 H/A 两行与 next_after，能发现分页漏行、普通实例被错误强制要求 authority、只读 cookie 能写、Origin/CSRF/实例/boot/过期校验失效和任意节点路径可读。已修正最初仅把同函数分页与全量相比较的共同漏行盲点。
2. `test_single_continue_owner_still_allows_immediate_pause` 用真实 writer 与共享 continue，只有科学 `_run` 替换为有界 Event；能发现第二推进 owner、旧 nonce 重放、continue 期间不能暂停、外部 continue 提前清除 pause 等控制缺陷。该 stand-in 不产科学结论/accepted，不能证明科研推进、真实 native 恢复或完整服务停止行为。
3. 既有普通实例用例改为管理页可读、审批仍不可用，未丢掉原有 P3c 决定原件、Origin 和 boot 负控。

## 尚未覆盖与提交边界

页面只展示紧凑节点状态元数据；科研原文/完整材料浏览、归档和可写恢复未由本节点实现。300 字符停止原因和 512 字符临时控制 note 有省略数，原科学记录不被截断。真实 HTTP/浏览器、活 native 时停止服务、完整后台推进与 correction acknowledgment 尚未动态验证。宿主凭据与同 uid shell 保持原软信任边界。

建议先仅提交本报告列出的 P4b 文件与 authority 单行，再独立审 d2a。d2b 仍是待审设计，不因本节点 PASS 获得实现或执行许可。
