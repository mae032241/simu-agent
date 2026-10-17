# P1 执行配置入口独立生产静态审查

日期：2026-10-17。最终定点复审结论：**PASS（限原 P1 基线与本文两文件兼容修复的静态语义），初审唯一 P2 阻断已关闭。** 本审查没有修改生产或测试代码，没有执行测试、导入、安装或构建。R0 仍先行；本结论不批准其并行修改，也不代表运行或安装验收通过。

## 精确基线与独立性

审查基线 HEAD 为 `565a2e422498addb33cfc71436fef99b5b6663ea`，对象为抓取时尚未提交的 P1 差异：`src/scidiscovery/research_loop/{cli,contracts,controller,experiments,local_experiments,native}.py`，以及 `tests/research_loop/{test_execution_configuration,execution_fixtures,composed_execution_fixture}.py`。抓取时保存了九文件全文、SHA-256 和 tracked diff；快照整体 SHA-256 为 `a74a09a9f846d365b2952f0f6513d2a61e297533955333a94ae0fac50a6545af`。私有基线已移存仓库本地持久目录，不纳入提交。下文行号均指这份快照；后续 R0 对 experiments/native 的编辑没有混入本审查。

审查者没有编写上述 P1 生产差异，但先前负责其新测试的成本精简。因此这里独立审查生产路径，测试仅作为覆盖证据核对；不将自己的测试精简自评为独立通过。该精简已有另行独审。

## 已关闭：旧 current-protocol 实例的 status 被新配置投影打断

**位置：基线 `src/scidiscovery/research_loop/cli.py:33–37`，最紧位置为第 35 行。** 新代码仅以 `experiment-config.json` 存在为条件，随后无条件取 `['execution_interface']`，再取其 executor/capabilities/result_protocol。

仓库已有 `tests/research_loop/test_local_managed.py:184` 的 `test_legacy_current_job_without_mode_keeps_science_view_and_observer_shape`，明确建模并保留以下旧契约：handoff_protocol 仍为 current；settings/job 没有 experiment_mode；host `experiment-config.json` 是 `{'legacy_configuration': True}`。它仍须保留科学视图/observer 形状且可继续只读校验。该场景没有命中 cli.status 开头的旧协议 archive 分支；新增第 35 行对该配置必然抛出 `KeyError('execution_interface')`。基线 cli.main 第 192 行只捕获 OSError/ValueError/RuntimeError，所以状态查询连既有 JSON 错误响应也无法返回。此前 status 不解析这份旧配置，新增投影导致兼容性回归。

影响是旧实例只读状态入口中断，不涉及已证明的错误执行或科学结论变更。这是由已有兼容契约和字典访问直接推出的可达静态缺陷，**尚未动态复现**。

收口要求：只为声明并具备当前 managed 配置形状的节点展示相应字段；旧或 unsupported 配置保持中性、显式的不可用状态，不补写或迁移旧原件。定点保护须使同一旧契约经过真实 status 入口，并保留原件不变断言。无需为此重跑整套 P1 或安装功能测试。

### 定点复审与关闭依据

修复只将基线 `cli.py:34` 的条件改为 `config_path.exists() and 'experiment_mode' in job`。上述旧契约的 job 不包含 experiment_mode，因此不会读取旧配置内容或生成 execution 投影；该分支没有新写入。修复后的 CLI 全文件 SHA-256 为 `562ac7e729ed38fe042712c704e3142b27f9dd47d94ee796a5524c07235a799f`，与初审基线的文本比较只有这一项条件差异。

既有 legacy 用例在同一 fixture 中新增直接调用 `status(root)` 并检查 W 节点不含 execution 字段，随后继续执行原科学视图、observer、校验及四个关键原件字节不变断言；没有新建环境或重型 fixture。修复后测试全文件 SHA-256 为 `d9f46aeb6f9a3c450669d6dc74381bb7831a660c487b16bae1ad697981dbab83`。两文件通过 AST 和静态空白检查，未导入、收集或运行测试；后续快照整体 SHA-256 为 `7e015ea2e9d1750973c34691191c295ec28e348bca249b4ec72078b9f1ba3337`，同样仅本地持久保存。

据上述分支和既有兼容契约，初审缺陷在静态语义上关闭；没有发现这项定点修复新增的阻断。该结论针对无 experiment_mode 的已知旧配置，不声称任意损坏的、已声明当前 managed 模式的配置都能被解释为有效原件。没有重新评审同期 experiments/native 的 R0 修改。

## 已追踪的生产边界

| 边界 | 基线静态证据与结论 |
| --- | --- |
| 注册身份与包路径集 | `experiments.py:145–194` 枚举 factory 所在顶层常规 Python 包的全部 .py 路径，拒绝 package-root 路径替换和包内符号链接；operator 校验重算身份，accepted 使用的验证器先比较完整路径集再逐文件核对 proof。新增/删除/修改 helper 不能仅靠 factory 文件未变而通过；非包模块走自身源文件。限定为可检查的常规 Python 包，namespace、多根、extension、第三方依赖和动态资源没有被声称纳入该身份。 |
| 操作者与宿主字段 | `controller.py:74–89` 在创建实例前调用 operator_configuration；`experiments.py:129–142` 拒绝 scope、record_dir、native_attempt、admission、breadth、engineering_repair、execution_interface、registered_implementation。`configure:287–301` 必须匹配原选择，再由 host 注入真实字段，local 默认 cwd 也在 host 处补入。未见操作者配置覆盖宿主身份的可达分支。 |
| prepare 与真实任务绑定 | prepare 只冻结公开配置及注册实现身份，没有调用 adapter factory.build 或伪造 scope；job 在 `contracts.py:639` 绑定选择摘要，`_validate_inputs:776` 核对原 settings。`native.py:140–156` 先检查原 native intent 的 task_sha256 和 profile，再校验注册选择、调用 configure；configure 自己还核对当前协议、job、settings 摘要和 intent。未见 prepare 提前完整 configure 的路径。注册发现仍会导入可信插件模块；这不是“禁止执行任意模块顶层代码”的保证。 |
| 原调用恢复与换实现阻断 | `load:320–333` 重新 freeze 并比对原 config；query/reconcile/lookup/collect/cancel 经 `original_adapter:361` 校验当前与原调用能力和原配置。CLI 在动作前 load，dispatch 在接受新 call 前 load；包路径集或 proof 改变会拒绝，未见退回新实现并重发旧调用的分支。已有原终态的纯封存校验与 live backend 操作是不同路径，前者不要求重读新后端。 |
| 可选能力与结果协议 | 既有 `lifecycle_capabilities` 对缺声明返回全 False；`record_observation:639` 仅在声明 collect 时收集，CLI 请求未声明操作返回 unavailable。新增 public_capabilities 允许空集合；native 提示使用已绑定原件或报告 unsupported。result_protocol 仍须显式声明，未见根据私有 candidate 字段推断科学候选或把缺能力变成通过的代码。 |
| 默认 local | 无显式配置时 standard codex 仍选 local，自定义 launcher 仍选 external；显式 external 与 execution_config 冲突。默认 local 的 run_argv/有限 max_seconds 冻结在 prepare，cwd 在真实 W workspace 注入；无新 execution_config 的既有 local 实例在 native 中仍走原默认分支。nonlocal 的 cleanup 明确 not_applicable，没有套用 POSIX 进程身份。status 的旧契约兼容缺陷已按上文定点关闭。 |
| 可发现的完整输入合同 | 新 capabilities 以 compact metadata、omitted_count 和 next_start 给出有界视图，describe 输出完整合同/metadata并核对原 hash。角色科学交接正文没有直接加入 operator 配置，status 也仅投影执行器/能力/结果协议；未见将完整配置或凭据材料注入 science-task 的新增代码。可信插件如何处理公开摘要和外部凭据不在本次验证范围。 |

## 测试证据与未验证处

九个快照文件及新测试嵌入的 NATIVE 字符串均通过 AST 解析，没有 import 其中任何模块。新 P1 文件有 13 个测试函数、26 个静态参数行；这不是 pytest collection 或运行结果。

静态读取确认其保留一个非本地 CLI→native→experiments 机械接线场景、第二实现的较小 freeze/dispatch/query、固定字面八字段负控和一个 CLI 拒绝、四类包变化直接验证、一个包变化贯穿 query/reconcile/run 且不增加 calls、提前 factory/Popen 禁止哨兵、默认 cwd 及独立大 schema describe。初审时没有 legacy-current 配置经过 status 的保护；本次在原 legacy 用例内补入了该调用及无投影断言，详见关闭依据。

本次未执行 pytest、collect-only、真实 CLI/进程、wheel 构建/安装、模型、SSH 或 solver；没有新的终态、性能/RSS 或内核隔离证据。此前 /tmp 丢失后的历史运行报告不作为本次可复查原始结果。真实已安装入口、真实外部 backend、模块升级/加载时序及完整恢复组合仍未动态验证。唯一已知阻断经定点静态复审关闭；本报告不表示完整 suite 或 P1 科学/外部执行资格通过。
