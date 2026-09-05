# R5-M7.2 Effect 探针运行前独立审查

日期：2026-09-02  
审查对象：`scripts/m7_live_effect_probe.py`  
结论：**FAIL；当前不允许以全新根执行真实人工验收。**

## 1. 阻断项

### B1：探针没有使用同一份启动期编译目录和注册后的运行插件

`run()` 先调用 `open_runtime()`；该入口在启动时自行执行
`compile_installed_catalog()`，并把结果同时保存为 Runtime 和 RunService 的目录权威。探针随后又调用
私有 `_catalog()` 手工拼装六个 `PluginDefinition`，覆盖
`runtime.runs.operation_catalog`，并把另一份手工目录交给 `RootToolFacade`。与此同时，Effect adapter
没有经编译目录中的 `runtime_factory` 和 `load_runtime_plugin_contributions()` 建立，而是直接
`FrozenFig4ReplayAdapter(...)` 后手工塞入 `ExecutionBridge`。

因此当前真实关系是：

```text
open_runtime 的 installed catalog
        ≠ 手工覆盖的 Run catalog
        = Root 手工 catalog

手工实例化 adapter
        ≠ compiled runtime_factory -> startup contribution
```

虽然后半段确实调用了 `operation_preflight` 和 `operation_invoke`，但目录发现、唯一目录权威和运行插件
注册这三段被测试脚本替换了。一个没有正确安装入口、配置合同或 runtime factory 的 Effect 仍可能让
该脚本通过。这违反 `AUTH-001`、`AUTH-003`、`PLG-001` 的承重边界，不能作为“插件注册后真实可用”
的 M7 验收证据。

最小修正：使用一个已经安装该评估插件的隔离解释器启动探针；探针只调用
`compile_installed_catalog()`/`open_runtime()` 得到同一目录，并通过
`load_runtime_plugin_contributions(..., mode="control")` 从该目录的 `runtime_factory` 加载 adapter。
不得写 `runtime.runs.operation_catalog`，不得导入并直接实例化 `FrozenFig4ReplayAdapter`。本次只需安装
Effect 所需的最小插件闭包，不要附带与该 Effect 无关的 TCAD runtime factory，也不要为测试新增
生产注册表、状态或运行器。

### B2：冻结清单中的当前 Effect 身份已经漂移，探针却未失败关闭

静态复算得到当前 `r5.fixture.fig4-replay.v1` 的编译摘要为
`0bfc79de2994bf86f66acf52b4fe2787886c8258f632ed4ddd8112cbf871a589`，而
`tests/fixtures/r5_e2e_tcad/manifest.json` 仍记录
`005f54a02ffcf0ef39556ada3a880917c822baac25ef24e394144202e20ef663`。同一清单记录的插件声明源码
摘要也与当前 `plugin.py` 不同。探针只从该清单读取输出文件摘要，没有核对清单声明的 Effect
版本/摘要和插件闭包；因此“输出字节仍相同”会掩盖行为闭包已经变化。

最小修正：先由当前冻结夹具的维护步骤有意更新清单中的插件源码摘要和 Effect 编译摘要，再让探针在
创建任何控制对象之前核对：目录中恰有该 public Effect，版本与摘要等于冻结清单，运行 binding
来自同一启动贡献。若任一不一致则停止。不要增加新的运行状态。

## 2. 已通过的设计检查

- 请求通过同一个 `operation_preflight`/`operation_invoke` 入口，且两次使用同一绑定；未恢复
  `execution_request_create`、`execution_approval_request_create`、旧 Task/Worker broker 或第二执行
  生命周期。
- `operation_invoke` 后只读取返回的 pending Approval 和精确 loopback URL；脚本没有 HTTP POST、
  `record_ui_decision` 或代审代码。人工拒绝和超时均失败关闭，`finally` 会停止 UI。
- 决定前显式尝试 `execution_start` 并要求 `ExecutionApprovalError`；授权后才依次显式调用
  `execution_start`、`execution_sync`、`execution_outputs`。
- `FrozenFig4ReplayAdapter` 的当前实现只校验请求、逐文件复算大小与 SHA-256、复制四个历史文件并收集；
  没有调用 Sentaurus。UI 文案、pending 提示和 Operation `not_for` 均明确它不是新求解。
- `_outputs_match()` 从控制面绑定的封存 Artifact 重新读取字节，并复算 SHA-256、长度和媒体类型；不是
  信任 adapter 自报摘要。
- 运行根要求全新或为空，持久状态不放入 `/tmp` 是调用方必须满足的运行条件；异常不会写
  `final-evidence.json`。

## 3. 非阻断改进

1. 在修复 B1 时顺手从控制面查询并断言：preflight 前后 Execution/Approval 数量均为零；invoke 后
   恰有一个 `created` Execution 和一个 `pending` Approval；审批 subjects 恰为冻结
   ExecutionRequest 与 replay request。这样最终布尔值不是只复述返回对象。
2. 最终证据增加实际 `operation_version`、`operation_digest`、`approval_contract_digest` 和四个输出的
   复算摘要，便于独立审查在不依赖进程内常量的情况下复算；这些是证据投影，不是新权威。
3. 给 `--timeout-seconds` 增加合理上限，且拒绝符号链接运行根；这是测试驱动的边界收紧，不需要生产
   状态机。

## 4. 运行前门结论

当前脚本的审批、显式启动、同步、收集和历史文件复算逻辑本身接近最小闭环；阻断集中在“它验证的
不是已安装、启动期编译并由 runtime factory 注册的那套 Effect”以及冻结身份漂移。修复 B1/B2并做
低内存聚焦复审后，才允许在 `deliverables/` 下使用一个全新持久根执行一次真实 loopback UI 决定。
无需扩大到 M7.2 第5项，也无需新增任何生产生命周期。
