# R5-M7.2 Effect/UI/执行独立终审

日期：2026-09-02  
审查对象：M7.2 第 4 项的最小已安装 Effect、loopback 审批、恢复与执行收集  
持久证据根：`deliverables/m7-live-effect-20260902-01/`  
结论：**PASS；阻断项 0。M7.2 第 4 项可以关闭，但不放行第 5 项、M7.2 整体或 R5-M。**

本审查只读取持久状态和源码，没有启动审批 UI、没有作出或重放审批决定，也没有再次启动 Effect。
审批访问能力、CSRF、随机数和本地 secret 均未写入本报告。

## 1. 结论摘要

当前证据足以证明一条严格限定的调试闭环：

```text
标准插件入口
→ 启动期编译唯一 public Effect
→ runtime_factory 注册唯一 adapter
→ operation_preflight
→ operation_invoke 创建唯一 Execution/Approval
→ 决定前 execution_start 被拒绝
→ 恢复同一 pending 对象
→ loopback UI 刷新访问能力并提交决定
→ 显式 execution_start
→ execution_sync
→ execution_outputs
→ 封存输出与冻结 manifest 逐字节一致
```

没有发现手工替换目录、直接实例化测试 adapter、第二执行注册表、第二审批状态机、恢复时重新 invoke，
或由控制面制造科学结论的路径。这个 fixture 只复制一个冻结文件，不能被解释为真实 TCAD 求解、
科学证据或远程执行证明。

## 2. 安装态插件与唯一注册路径

独立复算持久 venv 得到：

- `scidiscovery` 从该 venv 的 `site-packages` 导入，不是仓库 `src/`；
- `scidiscovery.plugins` 入口只有核心 `builtin`、`general_science` 和独立安装的
  `m7_effect_fixture`；
- 运行插件集合精确为 `("m7_effect_fixture",)`；
- 目录摘要为
  `94366f3f8a098dc682be1262c6cfdb01d9d5bcf2dd2a0f94656834a5a2b7da80`；
- `m7.fixture.frozen-copy.v1` 是 `public`、`effect`，操作摘要为
  `8f685138cacdf07c3228b1b705a8e293b268b3370cfeab0dfb5547e0899400da`；
- wheel 中的入口明确指向 `m7_effect_operation_plugin:PLUGIN`；wheel 内 `plugin.py` 摘要与冻结
  manifest 及当前源文件三者一致。

`plugin.py` 只声明一个 `PluginDefinition`、一个 public `OperationSpec`、一个
`RuntimePluginFactory`、一个 adapter 和一个审批 projector。`build_runtime()` 在 control 模式下
提供局部名 `adapter`，编译目录将其解析成 `m7_effect_fixture:adapter`。实跑脚本只调用
`compile_installed_catalog()`、`open_runtime()` 和 `load_runtime_plugin_contributions()`，并要求启动
目录与运行目录摘要相同；脚本没有导入 `FrozenCopyAdapter` 或插件私有实现。

因此 B1 所担心的“测试代码手装目录或直接构造 adapter”没有回流，统一入口和启动期编译确实被真实
安装态路径消费。

## 3. preflight、invoke 与唯一对象

初次运行在创建对象前验证了冻结 manifest、插件源码、请求和期望输出摘要；随后在空实例中执行
同一个不可变请求的 `operation_preflight` 和 `operation_invoke`。源码要求：

- preflight 必须返回 `admissible=true`；
- invoke 必须返回 `created` Execution 和 `pending` Approval；
- invoke 后全实例必须恰有一个 Execution 和一个 Approval；
- Approval 的 subject 顺序必须与 ExecutionService 给出的 ExecutionRequest、原请求精确引用一致；
- 决定前真实调用 `execution_start`，只有捕获 `ExecutionApprovalError` 才能继续。

持久库独立复算与上述条件一致：一个 ResearchInstance、一个 Execution binding、一个 Approval
binding；Execution 总数为 1、ApprovalRequest 总数为 1，且没有第二 revision。ApprovalRequest 的
编译身份同时绑定操作编号、版本、操作摘要和审批合同摘要，subject 精确为 ExecutionRequest 与冻结
请求。最终 Execution 状态为 `collected`。

## 4. 同一对象恢复

第一次 UI 进程结束时，唯一 Execution 仍为 `created`，唯一 Approval 仍为 `pending`。`resume()`：

- 只调用 `select_instance()`，不调用 `create_instance()`；
- 不调用 `_register_request()` 或 `operation_invoke()`；
- 重新复算安装目录、manifest 和 runtime contribution；
- 要求全实例仍恰有一个 `created` Execution 和一个 `pending` Approval；
- 从不可变 ApprovalRequest 再次核对该 Execution 的两个精确 subjects；
- 再次以真实 `execution_start` 负例确认未决定时不能启动。

持久记录中对象创建时间早于恢复后的决定时间约 91 分钟，原 Execution/Approval 编号和 revision 均
保持不变；只有同一 Approval 的访问能力经过显式刷新。数据库最终仍只有一条 ApprovalRequest、
一条 ApprovalDecision、一条 decision attempt 和一条 used nonce。由此可以排除“恢复时同名重建”或
“第二次 invoke 后碰巧得到相同结果”。

## 5. 调试代审与 loopback UI 边界

用户在本次对话中明确授权：只为跑通当前 debug 流程，父调度者可以代为审批。该授权没有被扩大成
默认产品权限，也没有绕过 UI。

操作者运输收据记录的实际 HTTP 顺序为：

1. `GET /`，Host 为同端口 `localhost`，返回 200；
2. `POST /review/<同一审批>/refresh-access`，携带同源 Origin 和首页会话 CSRF，返回 303；
3. `GET /review/<同一审批>?token=<已遮蔽>`，返回 200；
4. `POST /review/<同一审批>/decision`，携带同源 Origin、该页面的 token/CSRF/nonce、显式 confirm
   和 `authorize_execution`，返回 303。

运输收据明确声明没有调用内部审批写接口。它是事后操作者收据，不单独构成密码学证明；但其四步
状态与持久控制事实交叉吻合：

- `decision_attempts` 恰有一条记录，绑定唯一 UI session；
- `used_nonces` 恰有一条记录；
- `approval_decisions` 恰有一条 `authorize_execution`；
- HumanDecision 的认证方式为 `local_ui_session`，理由明确限定为 M7 调试代审和冻结文件复制；
- 决定 Artifact 的 parents 精确包含原 ApprovalRequest、ExecutionRequest 和冻结请求；
- ApprovalUI 生产路径仍要求合法 loopback Host、同端口 Origin、表单类型/大小、token、CSRF、nonce
  与 confirm，代码没有为探针增加 bypass。

因此，本次结论是“经真实 loopback UI 协议完成的、用户明确授权的调试代审”，不是“聊天文字自动
成为审批”，也不是“真实人在浏览器中完成了可用性验收”。

## 6. 决定后执行和冻结输出

探针只有在只读 `approval_status` 观察到允许选项后，才依次调用：

```text
execution_start → execution_sync → execution_outputs
```

持久 Execution 使用编译后的 `m7_effect_fixture:adapter`，终态为 `collected`，外部测试运行终态为
`succeeded`。执行结果 Artifact 精确引用一个输出 Artifact；该输出、execution exchange 文件和冻结
fixture 的 SHA-256 均为：

```text
702f1be3326ee07765cc21c46c881eef9fd0a2c0095f70107d503c847a85708b
```

三者 `cmp` 逐字节相同，长度均为 61 字节，媒体类型为 `text/plain; charset=utf-8`。输出父链回指
精确 ExecutionRequest 和原请求。没有 solver 进程、网络调用或科学结果声明。

## 7. 轻量性与架构目标

本项实现没有向生产控制面增加实体、状态或公共工具。测试插件通过标准入口一次注册；OperationSpec
声明输入、Effect、审批和限额；运行工厂提供领域执行代码；通用 Root 只负责准入、不可变绑定、审批
和四态执行。控制面没有解释 fixture 内容，也没有把复制结果升级为 Evidence/current。

按奥卡姆剃刀，这个最小 fixture 比为本项携带 TCAD/Fig.4 全插件闭包更合适。它隔离验证了“领域插件
可注册 Effect 并走通通用审批/执行主干”这一事实，同时没有建立并行框架。复杂的远程可靠性、实际
求解器和失败恢复仍留给各自后续验收，不被这个小测试冒领。

## 8. 复算与测试

独立终审执行：

```text
env -u PYTHONPATH PYTHONNOUSERSITE=1 <持久venv>/bin/python <安装态目录复算>
结果：PASS；入口、运行插件集合、目录摘要、操作摘要、scope 和 executor 均与 manifest 一致

python -m pytest -q \
  tests/operations/test_m7_effect_fixture.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_runtime_plugin_configuration.py
结果：4 passed in 43.16s

git diff --check -- <本项脚本、fixture、测试范围>
结果：PASS
```

这四个聚焦测试覆盖：已安装插件经启动目录和 runtime_factory 装载；Effect invoke 自动创建精确审批；
UI POST 后才可 start；start/sync/outputs 幂等主路径；运行插件配置和失败态 manifest。再加上本次持久
真实恢复/刷新/决定/收集，足以关闭第 4 项。没有执行整个仓库测试，因为本项没有修改共享生产代码，
且完整产品回归属于 M7.5，不能用全量测试替代这里的真实安装态纵向证据。

## 9. 阻断项

无。

## 10. 非阻断项

1. **本次不是人工浏览器可用性证明。** 用户曾遇到随机端口页面不可访问，最终决定是用户显式授权
   的调试代审。它证明 Host/Origin/CSRF/nonce 路径和执行授权语义，但不证明页面排版、浏览器转发或
   人工理解体验；UI 可用性应单列后续验收。
2. **运输收据是事后、非密码学证明。** 当前以 HTTP 状态摘要和数据库唯一行交叉核验已经足够支持
   调试闭环；若未来把自动代审作为正式测试设施，应由测试客户端在请求时原子写入无秘密收据，避免
   依赖事后说明。
3. **运输收据字段措辞过宽。** `secrets_or_tokens_persisted=false` 应理解为“该运输收据自身不含
   secret/token”；持久 Approval 服务按设计保存访问能力，证据根也保存权限为 0600 的
   `approval.secret`。后续可把字段改成不歧义的 `transport_receipt_contains_secrets_or_tokens=false`。
4. **完成后仍保留 `pending.json`。** 文件已不含 token 且不是控制权威，但其文案仍描述等待刷新，
   容易误导人工读者。后续探针应在最终证据原子发布后将其改名为历史运输记录或写入明确终态。
5. **测试插件源目录含本地构建产物。** `build/` 和 `*.egg-info/` 不影响已冻结 wheel 或本次语义，
   但提交前应清理或确保被忽略，避免把生成物混入源码。
6. **Effect 是确定性复制 fixture。** 它证明通用 adapter 注册、精确审批和执行收集，不证明远程
   副作用、真实 TCAD solver 或崩溃恢复；这些仍属于 M7.2 第 5 项及后续阶段。

## 11. 放行边界

本终审只关闭 M7.2 第 4 项：最小安装态 Effect 的统一注册、精确审批、同对象恢复、决定后显式执行和
冻结输出收集已经成立。

M7.2 第 5 项失败/超时恢复仍未执行，因此 **M7.2、M7 和 R5-M 均不得宣称完成**。
