# R5-M7.2 Effect 探针运行前独立复审

日期：2026-09-02  
复审对象：B1/B2 返工后的 `scripts/m7_live_effect_probe.py`、
`tests/fixtures/plugins/m7_effect_operation_plugin/` 与
`tests/fixtures/m7_effect/manifest.json`  
结论：**PASS；阻断项 0，允许在限定条件下执行一次真实 loopback UI 验收。**

## 1. B1 复审：已关闭

旧探针的两项旁路均已删除：

- 不再向 `sys.path` 注入源码插件目录，不再导入若干 `PLUGIN` 后调用 `compile_catalog()`；
- 不再覆盖 `runtime.runs.operation_catalog`，也不再直接实例化领域 adapter。

当前探针要求 `scidiscovery` 从当前隔离解释器前缀加载，使用
`compile_installed_catalog()` 得到安装目录，再由 `open_runtime()` 启动。它显式比较 Runtime 所持目录
与安装目录的整体摘要；随后调用
`load_runtime_plugin_contributions(catalog, ..., mode="control")`，通过同一目录冻结的
`runtime_factory` 加载唯一的 `m7_effect_fixture:adapter`。Root、Run、preflight、invoke 和
ExecutionBridge 因而消费同一编译目录与同一启动贡献。

独立安装测试在仅含核心 wheel 与 M7 插件 wheel 的隔离环境中验证：

```text
compile_installed_catalog
→ open_runtime
→ 同一 catalog digest
→ runtime_plugin_ids == ("m7_effect_fixture",)
→ compiled Effect plan
→ load_runtime_plugin_contributions(mode="control")
→ 唯一 adapter binding

1 passed in 42.40s
```

因此，一个未安装入口、未注册运行工厂或错误 binding 的插件不能再通过该探针。B1 已关闭。

## 2. B2 复审：已关闭

新的冻结清单只描述本次最小 Effect 夹具，不再复用旧 Fig.4/TCAD 科学闭包。独立复算确认：

- 当前 Operation digest 为
  `8f685138cacdf07c3228b1b705a8e293b268b3370cfeab0dfb5547e0899400da`，与清单一致；
- 插件 `pyproject.toml`、`__init__.py`、`plugin.py` 三个源码摘要均与清单一致；
- 请求和唯一冻结输出的 SHA-256 与字节数均与清单一致；
- 运行 binding 为 `m7_effect_fixture:adapter`，与编译 Effect plan 和清单一致。

探针在创建 ResearchInstance、输入 Artifact、Execution 或 Approval 之前完成这些检查。清单缺字段、
目录中额外出现运行插件、Effect 不是 public/effect、版本/摘要/binding 漂移、插件源或输入输出字节
漂移都会抛错。`open_runtime()` 在此前建立空持久服务文件不等于创建上述控制对象，不影响失败关闭
结论。B2 已关闭。

## 3. 生命周期复核

- fresh root 首先要求 Execution 和 Approval 列表为空；同一不可变请求依次进入
  `operation_preflight` 与 `operation_invoke`。
- invoke 返回 `created` Execution 和 `pending` Approval 后，探针再次要求实例内恰有一个 Execution
  和一个 Approval，并从返回的精确 URL 提取访问能力读取该审批。
- 审批读取对象与 `ExecutionService.approval_subject_refs()` 的冻结 ExecutionRequest 和原请求顺序、
  身份一致。
- 脚本没有 HTTP POST、审批写接口或自动代审；人工决定只能从启动后的精确 loopback URL 产生。
- 决定前 `execution_start` 必须抛出 `ExecutionApprovalError`；只有 UI 授权后才显式执行 start、sync、
  outputs。
- adapter 的 prepare 只校验冻结请求，submit/status 是确定性测试状态，collect 只复算源文件摘要并复制
  一个冻结文件；没有 solver、网络或科学变换。
- 探针从控制面绑定的封存输出重新读取字节，复算 SHA-256、长度和媒体类型，并把 Operation、审批合同、
  catalog 与输出摘要写入最终证据。UI、Operation 和证据文案均明确不把它宣称为求解或科学证据。
- 异常、拒绝和超时均不会写 `final-evidence.json`，`finally` 始终停止 UI。

未发现 `execution_approval_request_create`、`instance_prepare`、旧 Task/Worker broker、第二 current、第二
目录或第二状态机回流。

## 4. 最小性判断

新测试插件只有一个标准 `scidiscovery.plugins` 入口、一个 public Effect、一个运行工厂、一个 adapter
和审批 projector；它复用现有 Operation、Approval、Execution、UI 和 runtime-plugin 机制。虽然单文件
包含完整的严格 Schema 与 adapter 合同，但每部分都有当前验收消费者，没有形成平行框架。按奥卡姆
剃刀，这比继续携带旧 TCAD/Fig.4 六插件闭包更小且更能隔离本项要证明的事实。

## 5. 非阻断项与实跑条件

1. `tests/fixtures/plugins/m7_effect_operation_plugin/` 当前出现本地 `__pycache__`；提交前应清理并确保不
   入库，但它不影响本次安装 wheel 或运行语义。
2. 探针在 preflight 前和 invoke 后检查对象数量，没有单独在 preflight 后再次查询；统一 preflight
   的只读性已有既有专项覆盖，本项不是本次实跑阻断。

允许执行一次，但必须满足：

- 在 `deliverables/` 下从当前已冻结源码新建干净 venv，只安装核心 wheel 与 M7 插件 wheel；清除
  `PYTHONPATH`，设置 `PYTHONNOUSERSITE=1`；
- venv 与探针的持久运行根使用不同子目录，传给探针的证据根必须全新且为空；
- 只打开探针打印的精确 loopback URL，由用户直接决定；脚本或调度器不得 POST/代审；
- 本次无需 Codex 或子智能体进程，不得并发启动其他 M7 实跑；
- 只在 final evidence 全部为真且之后独立复算持久数据库、审批对象和输出 Artifact 后，关闭 M7.2
  第4项；本次 PASS 不放行第5项或整个 M7。
