# P3d2-a 实施冻结：native 科学输入到原 reviewed package

状态：**代码与定向负控已冻结，待实现独审；未动态验收/未提交。** 依据[设计](P3D2A_NATIVE_INPUT_CHAIN_DESIGN_20261017.zh-CN.md)及[设计独审](P3D2A_NATIVE_INPUT_CHAIN_DESIGN_REVIEW_20261017.zh-CN.md)，接在已审 P3d1 `c03d0c3` 后；不包含 P3d2-b 或其他并行工作。

## 实际公共路径

现有 `research_loop.experiments --config ... describe --key implementation_authoring` 返回可选 author 合同；`compile --implementation <file> --scientific-files <slot-alias-json> --output artifacts/<new>.json` 进入原注册 factory 和可信 `NativeInputHost`。Worker 只选择当前任务公开的 exact 输入 alias，不写 hash/storage/ArtifactRef。compiler 纯本地生成 v3 package，host 保存 author/capability 原字节、完整 slot originals、实际 compiler/helper/interface/contract 与 output proof；编译没有 policy RPC、prepare、upload、reserve 或执行资格。

原 W seal 的可选 `compiled_implementations` 绑定该输出 material 与 compiler proof。现有正式 A review 仍以该**同一 sealed package**为 subject，作者排除额外读取所有 slot producer，以及 author 文档确为已绑定读副本时的原 producer；不接受模型自报作者。来源沿既有 all-frozen-input provenance 保守继承，没有 compiler 洗白路径。

后继 W 的 existing `run --payload` 消费同一原件或 d1 明确绑定的只读副本。v3 wrapper 在 gate 前核 exact reviewed compiler/output/slot 清单，可信 callbacks 从唯一原 producer seal 成员取得原 source；随后继续原 d1 source/review/policy/authorization/reservation gate，再进入两个既有底层 adapter/P2b materializer。缺原件、缺 callback 或手写 v3 无 compiler proof，均不先创建授权 request/reserve。review 后不重编译。

## 精确文件名单

| 文件组 | 变动 |
| --- | --- |
| 新 `research_loop/execution_inputs.py` | 唯一 native-ref loader、可信 compile 原件保存、seal/review/run 共同验证、精确 payload callbacks；没有任务/预算/授权库。 |
| `operations/runtime_plugins.py`、`research_loop/execution_authority.py` | `ExecutionHostServices.implementation_inputs` 默认 None；原 host context 检验后注入。authority contract 冻结新增实际 helper；gate/ledger算法未改。 |
| `research_loop/{experiments,contracts,formal_review}.py` | 可选 compile CLI/冻结能力；原 seal capture/validate；声明的 compiler 输入贡献进入原独审作者排除。普通 HWA 最终 JSON 不扩机械字段。 |
| 插件 `project_packager.py`、新 `native_implementation.py`、`experiment_capability.py` | 独立 typed native v3，不造 ArtifactRef；旧 author→control project 纯逻辑只保留一份；v2 字段/默认/入口保留；shared slot/identity/materialize 校验。 |
| 插件 `managed_execution.py`、`execution_adapter.py`、`command_adapter.py` | 可选 `implementation_compilation.capability_snapshot_path` 仅 operator 配置；与旧 strict transport 配置剥离，snapshot proof 纳 interface assets/target。显式 v3 profile沿同一物理 packager；旧远端 TCADJobSpec/job.json/tar/submit/retire协议不变。 |
| 新 `tests/operations/test_tcad_native_implementation.py`、新 `tests/research_loop/test_native_execution_inputs.py` | 两个纯合同负控、三个公共链/原件拒绝负控，均未运行。 |
| `tests/operations/test_runtime_plugin_configuration.py`、`tests/research_loop/test_execution_configuration.py` | 必要旧 DI fixture 同步可信 host-interface边界，保留所有 collection/retire 独特断言；独立列举新增 host 字段拒绝，补占位 interface 不可 prepare。 |

上述为 **12 个生产 Python 文件、4 个测试 Python 文件**；另有设计/实施证据。不触及并行 P4b 的 `cli.py/controller.py/instance_ui.py` 或其 owner；P4b 的 `instance_control.py` asset 行已随其独立提交，不归本次批准。

## 实际 factory 断链的必要收口

追真实路径发现：原 `_adapter` 从 JSON body 剥掉 `execution_interface`，但 managed wrapper `_bound` 必须核它与 accepted 相等，直接构造 fixture此前遮住了该断点。经 root 批准及独审定点确认，`RuntimePluginContext` 仅加默认 None 的非 JSON `frozen_execution_interface`，core 从已验证 selected 传入，factory恢复原投影；operator JSON 明确拒绝此字段，factory也拒绝 body 中该字段。freeze 的 executor 占位只可构造/describe，prepare/acceptance/_bound 必须完整 version/code 投影。

旧 `_managed_tcad_case` 因新检查需合成 version/code，其注释明确只是可信 DI，不冒称真实 freeze。默认 factory 负控也传可信 context，并保留 default-blocked、missing-resolver、collection deadline、retirement 等原保护。新的公共链用 `e.main→e.load/_adapter→build_managed_runtime→Records/_bound`，不再仅靠直接 wrapper 构造。

## 静态验证及限度

全部 16 个 Python 文件只作 AST/空白与 diff 检查，无项目/测试 import。固定旧 v2 fixture +旧 envelope 得到预期 2,902 字节、SHA-256 `3a91a6302f39e63626a9ed1982d4f4a432803d5b51785a129b47b8874ad074c3`；测试的期望字节由固定旧文档/标准库编码产生，不由新 serializer 两端自证。另用 AST 比较旧 v2 package/input 字段声明未改；这不是运行通过证明。

公共链负控只在后续获准运行时检查：可选 CLI compile 无后端调用→实际 node seal→实际 formal qualification 函数→后继 CLI existing run→P2b 原 bytes/同 call queued/不重发，并确证 slot 原 producer 被列为作者。可信 fixture注入的 backend、调度 eligibility 与合成 native session 文件不证明真实平台独立性；source/ref、seal、正式 review规则、gate、ledger与公共 factory为生产函数。另覆盖 unbound alias、author read→identity间换同slot正文、同hash错producer/instance、改包不能复用原proof；审查指出的author读竞态已加本次raw len/SHA及后置identity核验。

没有 pytest/collect、项目导入、CLI/进程、安装/build、模型、SSH或 solver执行。旧 v2其它可选 result/debug服务仍只支持其原合同，不借此宣称全面 v3 功能。native MIME只是冻结的科学 slot 类型声明，非字节鉴定。真实生产接线、平台身份、跨boot及远端solver资格仍受主计划未验收限制，静态PASS/fixture不授生产资格。
