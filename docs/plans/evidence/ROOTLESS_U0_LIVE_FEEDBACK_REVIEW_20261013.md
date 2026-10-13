# U0 运行中只读反馈独立审查

状态：**U0 独立审查通过**。最终异常出口与 host 状态组合边界已闭合，源码 77 项、安装回归 89 项及真实安装 CLI 无模型验收通过。资格限定为通用观察合同和 cov 实现的运行中只读反馈；尚未授予 U0r 通用执行层、普通 local 或 TCAD 生命周期资格。没有科研模型、真实续接或 U4 效果结论。

## 范围与审查独立性

审查主计划第 7 节、基线 `0d10d1e` 的生产及测试 diff、新 `feedback.py` / `test_live_feedback.py`，并沿 observer transport、受管调用、原执行身份、host status、最终封存和父资产复用追踪。首轮复核的八文件 SHA 与 `/tmp/scid-u0-source-final.json` 完全一致。审查者只修改此报告，只读源码、测试和父级执行证据，没有修改实现、运行测试、构建或模型，没有读取隐藏评分。使用 `scid-cross-boundary-review`。

U0p 当前协议执行退役独立交付。本报告不将反馈组件 1 或 observer 合同 2 当作单当前科学协议已经切换，也不将 U0 当作 U1 准入、U2 检查点或 U3 科学意图与周期计数已经完成。

原独审者因平台 capacity 无法继续后，由未参与 U0 实现的 U1 设计者接手。接手者只读基线 `0d10d1e` 的完整八文件 diff、三文件最后修订及生产上下文，核对 `/tmp/scid-u0-source-revised.json` 八项 SHA 全部一致；只修改本审查记录，没有修改源码/测试，没有运行测试、构建、模型或 Git 写操作。

## 最后修订接手复核

原预算提示问题已修复：格式、UTF8、容量、深层 JSON 递归错误保留 unavailable；固定路径的 symlink、目录、读取错误均归一为不含私有路径的 ObserverIntegrityError。枚举类型与超大整数不再泄出 TypeError/OverflowError。

原 live 解析问题已修复：已发布 acceptance、scope、parent、process 类型与冻结身份校验进入统一完整性出口；半写 JSON/UTF8 保 unknown；巨大公开数值仅从反馈省略，不修改原 row 或已知终态。`feedback.live` 本身验证 native-intent 是 dict。最终 `_completed` 默认仍完整核验 source/model，run、parent 与最终 observer 不使用轻量预览模式，未发现资产资格弱化。

接手复核发现的一项入口已修复，另一项保留为明确限制：

1. `cli.status` 原来在配置 `node_budget_policy` 时先读 `intent.get('budget_slice')`，会绕过新 dict 校验。最终补修在读取后验证 intent/outcome 类型，以常量 ObserverIntegrityError 拒绝；负控已覆盖有/无节点预算、intent/outcome 与 list/null/scalar/string 的完整真实 CLI 组合。终态 outcome 的另一 `.get` 也有同样前置检查。接手者逐行复核最终补修，确认异常进入 CLI 既有有界出口，不泄露私有路径，不修改原件。
2. `history.read_adapter` 对冻结 adapter 的 `c.regular` 错误抛普通 ValueError；`feedback.live` 将其降成可选 unavailable，内容 SHA 变化仍硬拒。父级明确接受此区别：adapter缺失或非 regular 导致遥测不可用，不授予科学资格、执行成功或新权限；`c.regular` 拒绝 symlink/非 regular 原件，不跟随该文件路径；最终 `_capture` 仍硬拒。此行为不作为 U0 阻断，不能把 unavailable 宣称成成功、零进展或原件可复用。

独立实施者完成第1项与 native-intent 读取的 RecursionError 归一；接手者没有参与源码修改。深 JSON 的固定/动态深度夹具在当前 native parser 均不保证触发 Python RecursionError，修前最终门禁两次为76通过/1失败。最终夹具分开验证真实深JSON得到typed拒绝，以及对exact native-intent读取注入RecursionError得到精确parse诊断；生产校验没有放宽，测试不冒称实际解析器触发了该异常。

## 最终冻结前历史发现（均已闭合）

1. **固定预算提示的异常类型未闭合。** `feedback.budget_hint` 的读取只捕 JSONDecodeError。固定文件超过 4096 字节、被目录替换或非 UTF8，分别可抛普通 ValueError / UnicodeDecodeError；权限读取可抛 OSError。`cov_lineage.main` 的反馈出口只捕两个完整性异常，因而真实 `lineage-status` / `run` 会裸 traceback，无法交付有界工具结果。要求畸形格式、编码、容量保留 unavailable；固定原件路径及读取完整性错误以 ObserverIntegrityError 硬拒，不能降成零余额。
2. **新增 live 元数据解析有裸异常路径。** `_progress` 对合法 JSON 超大整数指标或耗时直接调用 `math.isfinite`，可抛 OverflowError；真实 CLI 的第一出口不捕它。接受记录的 parent 投影在解析防护之外，process 元数据使用 `.get` 而没有 dict 检查；合法 JSON 非预期结构可抛 KeyError / TypeError / AttributeError。`feedback.live` 对 native-intent 的 `.get` 也在可选 observer 防护之外，合法 JSON list/scalar 可穿透 host CLI 的异常集合。要求数值不可有限表达时省略该值；半写 JSON/UTF8 保未知；已发布结构或冻结身份损坏以有界 typed 完整性错误硬拒。

两类发现已通知父级并由独立实施者局部修复；最后冻结版已闭合。预算 enum/list/dict、预算超大整数、symlink typed 回包及已封存节点重扫也已修正。

## 已核对的跨边界语义

- 新 prepare 默认冻结 feedback component 1，job 保留其原 marker；无合格 observer 时明确 unavailable，counts 为 null。核心只读通用反馈，cov 解析留在适配器；没有新余额、实验台账或执行引擎。
- host status 只为未封存节点请求 live，复用冻结 observer 2 和接受的 execution keys；读取没有拿 instance writer、封存、回填或启动实验。已有封存节点保留原事实来源。
- scope 核对 step / role / job / execution / mechanism，call ID 必须等于原目录身份。只有精确 task、PID、boot、start_ticks、进程组/session 匹配才能显示 running；PID 不匹配或无完成回执保未知，不能当成功或重提许可。
- 由现有 call ID 重建一次计数，受管扫描上限沿用 128，公开最多 16 条调用并返回 counts / omitted / coverage / observed_at。轻量查询不读取大 source/model 内容，不加载 pickle；完成元数据仍校验同调用 accepted / stdout / row / terminal 原件及身份。
- `_completed` 默认继续完整校验所有资产，原 `run`、`_parent`、最终 observer 与封存消费方仍使用默认路径；轻量 `verify_assets=False` 仅用于预览。修改 source/model 允许预览元数据，但后续新调用或父复用仍硬拒，预览明确不建立资产完整性、审计或目标适用性资格。
- 固定 `work/budget-status.json` 只投影最近 host 观测、在途未知、剩余观测上界及 advisory 复核请求。它没有成为授权、余额权威、U1 guard 或科学周期来源，公开结果不转发 hint 原 instruction、秘密或 raw_log。
- 通知只在工具回包或显式查询发生，无已验证的 mid-turn 注入通道。未受管 shell 工作不冒充完整实验覆盖。查询没有修改推荐、实际提交、科学去向或预算。
- `history.read_adapter` 沿用既有同步信任边界、5 秒和 256KB 输入输出上限。部署入口为打包 `scid-research` 与安装后的 cov 脚本；脚本路径执行 import 根接线已核，最终安装验证已绑定最后修复后的 wheel。

## 已观察证据及适用范围

以下是父级执行、审查者实际读到的修复前门禁证据：

- 外层 `.trial/u0-source-20261013/result.json`：source lane passed、退出 0、cleanup_complete；对应日志 83 passed / 29.39s，覆盖七份相关测试。
- 外层 `.trial/u0-final-source-20261013/result.json`：source lane passed、退出 0、cleanup_complete；对应日志 44 passed / 12.78s，覆盖 live、cov、native CLI。
- 外层 `.trial/macro-role-installed-20261012/artifacts-u0-20261013/u0-installed.log`：56 passed / 18.38s；其 result 退出 0、model_requests 0、12 个导入模块位于 site-packages，相关模块 SHA 与所审冻结版相符。
- 同目录 `result/result.json` 与 `result/module-bindings.json`：fresh wheel `7a197e4c9fabeb288a8d5544e47d58637c958ea830b5021d593060a2f1c9aae2`，23 个 research-loop 模块绑定，默认 H→A→W→A、重启 no_replay、route_context_preserved 均通过，model_requests 0。夹具验证真实安装 CLI 和机械路由，不证明科研遵循或搜索效果。

上述早期 green 门禁没有覆盖后来发现，最终通过依据是下述补修后的源码复核与安装证据。

接手者另实际读取 `.trial/u0-revised-source-20261013/result.json` 与 `batch-001/pytest.log`：source lane passed、退出 0、cleanup_complete；live/cov/native CLI 三份测试合计 64 passed / 14.30s。此门禁仍在最后 host 状态补修之前。

## 最终冻结与通过依据

接手独审实际读取并核对以下父级执行证据，没有自行运行验收：

- 外层 `.trial/u0-close3-source-20261013/result.json`：source lane passed、退出0、cleanup_complete，无内存停止；`batch-001/pytest.log` 为 **77 passed / 15.02s**，覆盖 live、cov、native CLI。
- 外层 `.trial/macro-role-installed-20261012/artifacts-u0-close-20261013/u0-installed.log`：**89 passed / 20.72s**；`u0-installed-result.json` 退出0、model_requests=0，12个实际导入模块来自site-packages。
- 同目录 `result/result.json`：fresh wheel **`cacadde02e2fdb8786d6c54a89add0b2212165a2224b766c4cce70e155d82351`**，23个research-loop模块绑定；真实安装CLI无模型H→A→W→A、重启no_replay、route_context_preserved均通过，model_requests=0。夹具证明机械生命周期与真实安装接线，不证明科学遵循或搜索效果。

最终八文件审查绑定如下；六个生产模块均与该wheel的`result/module-bindings.json`一致。完整manifest同时保存在`/tmp/scid-u0-audited-close3.json`；后续变更需要新审查绑定。

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/feedback.py` | `5b299d22733eddbbce5f2fc60648d3707fbbef3dc596e213a15478b8f145018e` |
| `src/scidiscovery/research_loop/cov_lineage.py` | `c795fb2d06c9fab2dea4134d4dd49fda330ed94249bf3b5f9bcddbee1453f695` |
| `src/scidiscovery/research_loop/history.py` | `5d8b59fd81b27eeff56a20164e7ff5278cc2d8296639ff80f11584b43448daa8` |
| `src/scidiscovery/research_loop/controller.py` | `8e5cba30175a1941c3ff9bffabe873633348a72044ca36c27c7bf869aa40659b` |
| `src/scidiscovery/research_loop/contracts.py` | `7bc46760d54e334cad78f942e21c30dc75b16e22ee096a0055b4f885c0dbcddf` |
| `src/scidiscovery/research_loop/cli.py` | `c4291870e272dea8b72b6d39de2bc15f32d17d0a53e5951aa5c94e756bb89af9` |
| `tests/research_loop/test_live_feedback.py` | `1fbf09245ed0db8f88ca1c828e8b5e717c13dd965219a37f4b8883e3e77695d0` |
| `tests/research_loop/test_cov_lineage.py` | `088b1eacbc99b4f39d8fb1a021d09825dfe9601410668dfe5855ec1e385c9b21` |

在上述冻结范围、可选遥测与资产资格边界内，没有剩余阻断发现。后继 U0r 必须经同一注册入口证明cov和普通local两个实现；本次通过不替代该门禁。

## 保留限制

本轮无模型夹具不证明长期科学收益、任意 shell 隔离、真实平台续接、mid-turn 通知或 U4 配对结果；不启动 U4。最终资格消费方继续核原件。U0 完成与后继节点完成分开记录。
