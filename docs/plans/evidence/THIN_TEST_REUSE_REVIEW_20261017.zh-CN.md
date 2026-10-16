# 新薄层测试复用与安装成本独立静态评审

日期：2026-10-17。范围：`dev`，HEAD `a1d37aa38e34af1a420fc41b81fe58a5f28f9e37`，以及评审时未提交的 P1 execution-config、完整 TCAD 传输容量补修与两个新测试文件。本文是建议，未删除或修改任何生产代码、既有测试、fixture 或运行器。

用户要求优先于技能中执行检查的建议。本次使用 `scid-cross-boundary-review` 与 `scid-change-scope-checks` 的边界/证据方法，仅运行文件枚举、文本搜索、带行号静态阅读和 Git 状态查询；没有 pytest、collect-only、构建、安装、环境创建、真实模型、SSH 或求解器运行，没有读取 `.trial` 或隐藏评分。

## 结论与先做什么

新薄层需要保护的是接受调用的不可变身份、本地执行事实、原调用恢复、候选/交付资格、预算和单写者；旧 Root/MCP/session 是仍有支持责任的另一组入口，不能作为薄层测试的前置架构。用户明确要求：**安装测试必须独立，不纳入全量功能测试；不得仅为换环境再次运行功能测试。功能检查及其传递 fixture 都应零安装。** P1 没改 `pyproject.toml` 的入口声明，不应把整套新 P1 用例在 installed 条件下再跑。源码证据不能声称证明已安装入口；只有实际打包/发现变化才需要另行安排一次最小包装冒烟。

推荐顺序：

1. 先接受本文的保留/改写/退役账，停止把整套安装 lane、全量 suite 或旧 Root 闭环列为每个薄层节点的退出条件。
2. 合并局部负控的重复启动与无效常量补丁；保留真正覆盖不同副作用边界的负控。此步骤不需要扩大测试架构。
3. 将已有进程/大输入检查明确列为按变更选择的检查，源码默认入口不递归拉起全部这些场景；移除对“source 就很轻”的假设。
4. 恢复任何测试执行前落实事故记录要求的内核资源域与持久证据；本文不指定无测量依据的内存额度，也不以安装重跑来找 OOM 原因。
5. P2/P3/P4 实际实现到达后，只为其新增职责选择或改写相应旧语义负控；P5 明确退役消费者后再删对应旧入口专属测试。

## 阅读范围与证据边界

静态枚举 `tests` 为 428 个文件（包含 fixture/JSON/README，**不是测试用例数**）。阅读重点包括所有 conftest、安装工具、运行器主体；`research_loop` 的执行注册、配置冻结、原调用恢复、控制器锁、通用交付，以及下表点名的测试主体/相关段落。搜索其余测试的安装依赖、参数化、并行与子进程调用，以定位风险；没有逐条读完 428 个文件，不能称“全审”。

本次没有完整核对发布脚本、安装器事务、所有 catalog 负控、全部 TCAD 分析/数值模型、全部 UI 与旧 SQLite 恢复故障点；未读完的项目列为暂无法判定。行号依据评审时工作树，后续编辑可能变化。

## 从生产职责确定覆盖，不从旧 suite 倒推

| 实际职责与生产位置 | 必须证明的用户故障 | 最小证据形状 |
| --- | --- | --- |
| `research_loop/controller.py:15` prepare；`:74` 模式所有权；`experiments.py:113` 注册；`:133` 公开设置；`:269` 宿主配置 | 选择错误执行器、用户设置覆盖宿主身份、prepare 提前建任务或触发外部动作 | 公共 prepare 成功一次、公共 CLI 拒绝一次，其余同一验证器的字段负控用直接调用；工厂若被提前调用即失败 |
| `experiments.py:164` 包实现身份、`:185` 原实现核对、`:336` 原配置、`:361` 原调用能力 | 配置文件/插件更换后 query、reconcile 或 run 改用新实现或重发 | 冻结后更换原件，断言拒绝且调用记录不变；query/reconcile/run 是不同副作用入口，不能全部只测其中一个 |
| `local_experiments.py:23`、`:94` 文件清单、`:122` lookup；`operations/execution.py:56` 显式 managed 契约 | 可变输入替换接受原件、字面参数变 shell、成功进程被坏 result 改判失败、unknown 被重发 | 一个真实本地小命令配冻结输入/字面 argv；坏结果只测语义状态；unknown 保持一个 call |
| `operations/execution.py:56` 原始终态/opaque/capability；`experiments.py:599` observation | 非本地后端被强加 POSIX 身份；未声明能力被猜测；私有 candidate 被误当科学候选 | opaque 假后端配明确能力；无 collect 的终态能 reconcile；不声明 candidate protocol 不推断候选 |
| `generic_delivery.py:17`/`:66`；`delivery.py:225` 冻结、`:435` 校验、`:696` invoke | 未审候选被提交、原件篡改、失败/未知被确认、重复提交 | 一个通用候选冻结→审查→确认场景，配篡改与重试幂等负控；领域 harness 的额外资格另列 |
| `controller.py:210` 单写锁、`:1039` 续接、`:1056` 显式执行恢复；`execution_recovery.py:51` | 重启重复启动、旧封存被改写、预算重置、两个控制器同时推进 | 原执行重接与 unknown 不重放；一个确需两个进程的锁竞争；显式恢复追加而不改旧封存 |
| `operations/runtime_plugins.py:12`/`:19` 归档归属、`:61` 工厂；迁移计划 P2–P4 | TCAD 授权绕过、受限来源洗白、归档丢插件原件 | 现有旧入口仍保留；仅抽取语义到新实例入口，不能把旧 Artifact/Run/session 搬入薄层。未实施前不声称薄层已有这些能力 |

这些职责已有大量可用检查。新增薄层测试的默认动作是选择、收窄和少量改写已有用例，不是另建一套运行器、通用 fixture 工厂或庞大新 suite。

## 安装与资源链的静态发现

### fixture、环境与构建

- `tests/operations/conftest.py:15` session fixture → `create_environments`；`:24` 的 probe 传递依赖该 fixture。`tests/conftest.py:93` 根据 pytest 的 `fixturenames` 标记 installed，常规选择会看到传递 fixture；没有理由把所有源码测试都说成会安装。
- `scripts/installed_candidates.py:89` 在首次创建环境容器时就复制运行依赖缓存；`:94`–`:115` 有九个 wheel 源、九个环境选择，但 **wheel 是按实际访问懒构建，不是无条件一次构建九份**。`:118` 缓存构建出的 wheel。
- `:176`–`:184` 的 `LazyEnvironments.__missing__` 在切换环境时删除已有环境和 workdir，并清空 dict。`core→all_domains→core` 会再次创建和安装 core；session scope 只保证 wheel 缓存，不保证跨环境安装复用。
- `:143` 先为所选包取 wheel；`:149` 的 tcad_resolved 然后改成先装 core，再在 `:162`–`:171` 用依赖解析安装 tcad。这是依赖解析专属语义，不能把它说成和 `--no-deps` 安装完全重复；它也会预先构建 curve/tcad wheel。
- `:123`–`:130` core 暂存范围是 `src`、`roles`、`deploy/systemd` 加 pyproject/README；没有把仓库根 `.trial`、所有 evidence、整个 tests 复制进 core。其他插件在 `:132` 复制各自源目录并排除 build/dist/egg-info/字节码。现有证据不支持“整个仓库复制导致 OOM”的结论；插件各源目录实际体积未测。
- `tests/operations/conftest.py:33`–`:43` 每个 probe 都检查 scidiscovery 路径、venv 隔离、Pillow 路径。对不使用图片的 core/execution 配置语义重复导入 Pillow 没有额外证明价值；只在确实验证图片依赖的可选包装烟中保留。
- 根 `conftest.py:10` 只修改 TCAD 源码 import 路径；`tests/conftest.py:39` 全局 autouse 把 catalog 元数据模拟成四个插件并反复清 cache。它不执行 pip，但使不使用 catalog 的薄层检查也受旧 catalog fixture 包围；新薄层检查无需继续继承这项全局默认。

### 九种环境各自证明什么、哪些应合并

`installed_probe` 的静态消费者清单：`test_m7_effect_fixture.py:4`；`test_tcad_knowledge_closure.py:18`；`test_root_reading_installed.py:5`；`test_ledger_capture.py:262`；`test_codex_root_host_installed.py:4/:40`；`test_catalog_installed_entrypoint.py:126/:177/:208/:212/:224/:417/:437`；`test_analysis_tool_installed.py:8/:33`；`test_artifact_capture.py:686`；`test_tool_contract_reader_installed.py:4`；`test_minimum_support.py:697`（均在 `tests/operations/`）。本次搜索未发现其他通过该 fixture 或 `installed_environments` 触发安装的测试；这不等于已排除所有脚本自行安装。

| 环境（`installed_candidates.py:105`） | 已知消费者/独特失败模式 | 建议 |
| --- | --- | --- |
| core | `test_catalog_installed_entrypoint.py:126` 检查实际元数据、错误打入领域包；`test_root_reading_installed.py:5` 检查 scheduler 资源；`test_codex_root_host_installed.py:4/:40` 检查旧 host/daemon | 三者不是相同语义。薄层单次可选烟只取 core 的 console/execution entry point 和必需资源；旧 host/daemon 运行语义回到其源码/进程检查，旧资源包装随对应入口支持边界保留 |
| curve | `test_catalog_installed_entrypoint.py:177` curve 不依赖 figure 仍能评分/出图 | 可选插件分离性，薄层配置改动不需重证；评分结果本身放源码测试。独立依赖布局改变时才有安装价值 |
| architecture | 工具提供构建选择；本次搜索未发现 tests 中通过 installed_probe 访问该名 | 暂无法判定是否供 live host/probe 脚本使用，不得只因 pytest 无消费者删工具分支；不放薄层默认集合 |
| blind_csv | `test_catalog_installed_entrypoint.py:224` 完整旧 Root/Worker 提交读取链；`test_analysis_tool_installed.py:33` 两个 stdio 入口错误 | 一个验证第三方装入，一个验证协议诊断。协议业务矩阵无需另装；保留旧入口支持账，薄层无需 CSV/Root 链作为前置 |
| m7_effect | `test_m7_effect_fixture.py:4` 已安装 catalog 的工厂选择/adapter 绑定 | 可把工厂语义改为源码注册/直接加载，包装发现由唯一可选 smoke 承担；旧 Effect 入口仍支持时保留其契约覆盖 |
| all_domains | `test_analysis_tool_installed.py:8` 所有插件 digest 一致；catalog 安装测试 `:208` 图片依赖；TCAD知识闭合 `:18` 角色资源；tool reader `:4` 独立脚本 | digest/读取器内容/资源语义和图片二进制依赖不同。语义检查移回源码；如果实际修改这些插件包装，把需要的资源存在/真实加载合并进一次选定 cohort 烟，不每项再装。不纳入无领域插件的薄层默认烟 |
| broken | `test_catalog_installed_entrypoint.py:417` 组件导入失败稳定诊断 | 只需可发现的坏 entry point/坏组件，源码 metadata stand-in 能触达编译器；不需单独 wheel/venv。与缺包/重复注册不是同一错误，保留语义负控 |
| invalid_unicode | 同文件 `:437` 资源 Unicode 摘要错误 | 可改为源码资源/entry point 负控后删除专门安装环境。`test_catalog_negative_cases.py:306` 是 declaration digest，错误码不同，不能用它冒充已有完全等价覆盖 |
| tcad_resolved | 同文件 `:212` tcad 声明的 curve 依赖由安装器解析 | 仅插件依赖元数据/交付方案改变时有价值；全领域 `--no-deps` 环境不能替代它。普通运行逻辑不跑；不作为默认矩阵一员 |

### 运行器与隐藏成本

- `tests/conftest.py:57` 拒绝 xdist，`:61` 串行锁，`:105` 重 lane 要求 guard。这只约束接入该机制的入口，不证明无并发子进程，更不证明内核内存隔离。
- `scripts/run_tests.py:166` 启 pytest 子进程，`:198` 采样进程树，`:210` RSS 止损；`:162` 只设置 `RLIMIT_CORE=0`，不是 memory/swap/pids 聚合限额。运行器自己在 `:1`–`:5` 如实声明不是硬隔离。
- `:315` 拒绝 installed `--per-file`，避免每文件重建 wheel，但不能解决同 session 环境切换重装。`:323`–`:331` per-file 是串行新进程，会重新导入/创建 session 级对象；不要把它再设为薄层每次必跑全目录。
- `:294` 与 `tests/README.md:15` 建议 `/tmp`，与事故后应持久化原始证据的要求不一致。需要调整后续实际执行安排；本文未修改文档或运行器。
- `test_composed_execution_results.py:65`–`:85` observer×private 产生 9+6 个完整封存/读取场景，全部通过 `case` 的 CLI 子进程。它保护的变量是真实的，但无证据需要每一种私有形状和每一种 observer 的全笛卡尔积；保留每个有效分支及一个组合负控即可，不能只保留全正例。
- 新 `test_execution_configuration.py:133` 对八个宿主字段分别跑 CLI prepare；`:230` 四种包变化×三个 CLI 动作，共十二个子进程，而且每种都先完成一次本地 dispatch。保留入口/副作用边界，字段全集在直接验证器测，包变化全集在身份校验测；只用代表变化贯穿三个 CLI 动作。
- `test_runtime.py:16` fixture 会启动控制器、native stand-in 与真实本地子进程（`:29`），不是纯单元 fixture；`test_controller.py:316` 锁竞争故意有两个进程，具有不可用单进程替代的故障意义。禁并行批次不应被误读为取消所有必要竞争负控；当前不运行它们。
- 新 `test_tcad_full_transport_records.py:26`、`:49`、`:91`、`:106`、`:128` 都启动本地进程/协议 stand-in，未见 process/stress marker，默认 source 会选择它们；P1 的 CLI 链同样如此。“无真实模型”不等于无进程或低成本。

## 文件/用例处理账

以下“直接复用”表示保留测试语义和现有代码，不代表现在执行、每次必跑或把其所有邻近用例一起搬迁。

### 直接复用

| 文件与用例位置 | 保护的具体失败 |
| --- | --- |
| `tests/research_loop/test_local_managed.py:35` `test_r1_snapshot_argv_facts_and_original_lookup` | 输入接受后变动仍执行快照；字面 argv；lookup/collect 不创建第二个 call |
| 同文件 `:61` `test_r2_bad_or_missing_result_preserves_process_success`，`:83` unknown cleanup | 缺失/非法科学结果不改写已知进程成功；unknown 不升级为成功或重发。这两者不是重复断言 |
| `test_registered_experiments.py:106` unknown、`:119` lost reply lookup、`:177` 无能力声明 | 不确定提交不能重发、恢复外部绑定、存在同名方法不授予能力；无需真实 solver |
| `test_delivery.py:153` 通用 descriptor、`:220` 篡改 | 通用交付不要求 cov 字段；接受原件/argv 被替换时硬失败。该文件后续完整提交场景有领域 fixture，应按下表改写 |
| `test_full_history_records.py:66` 流式归档、`:106` 默认无容量 cap/显式 quota 仍生效；`test_local_managed.py:383` 流式快照 | 防止完整原件被展示上限截断、避免 Path.read_bytes 全量读大原件；两条覆盖不同归档/快照实现，不能只因都用大文件就删其一 |
| `test_controller.py:316` 单写竞争；`test_runtime.py:73` 控制器断开重接、`:139` intent 未启动 unknown | 同实例双写；原执行重接；无启动证据不重放。前者 fixture 局部模拟其他依赖，只证明锁，不当作整体恢复资格 |
| `test_current_protocol.py:118` 旧原件 owner write 拒绝、`:143` 只读不重建、`:209` 工厂加载前 scope 拒绝 | 当前支持的历史原件只读保证；“拒绝旧协议”本身是当前协议职责，不能按年代删除 |

### 少量改写或合并

| 文件/位置 | 具体收窄方式与留下的证据 |
| --- | --- |
| `test_registered_experiments.py:21` local/cov 参数 fixture | 薄层公共生命周期选 local 一次；cov 只留下真实差异（领域 receipt/parent 等）的 owning 检查。默认用明确 module 调用，去掉 `:36`–`:37` 对宿主任意 `scid-experiment` 的自动选择；console 脚本发现由可选安装烟负责 |
| `test_composed_execution_results.py:67/:81` | 去除 observer×private 全乘积；保留无声明 opaque、不合法显式声明、observer 缺失/失败各自的必要分支。复用 `:89` 无 collect reconcile 与 `:153` 身份篡改，不重造 async 测试框架 |
| 新 `test_execution_configuration.py:67` | 一个非本地执行器走 prepare→真实 native 自动接线完整链即可；第二个注册实现用 configure/freeze 定向证明同接口接入。`:93` 300000 schema 可合并到已有完整 contract 容量场景，P1 路由链不必同时测容量。`:104` 重跑幂等证据有价值，保留 |
| 同文件 `:122/:134/:146/:153/:161/:172/:191` | 提前工厂、宿主字段全集、缺失/重名、包 helper 变更、错误 binding/adapter 配置都是真实不同准入失败，不能整文件删除。字段全集直接调用 operator_configuration，留一个 CLI 拒绝与“实例未创建”；绑定错误留 native Popen 必不调用。删 `:181` `len(code)==3` 的实现结构断言，保留 helper 改变被拒绝；不要求包永远只有三个文件 |
| 同文件 `:215` | 单脚本相对 cwd 是实际故障，与远端 opaque 接线不同，保留；把仅验证 cwd 的部分沉到本地 configure/dispatch，是否仍保留完整 H/W/A CLI 链取决于 cwd 回归位置（当前 `experiments.py:292` 是宿主设置），无需为此安装 |
| 同文件 `:231` | 四种包路径集变化直接校验冻结身份；一个代表变化分别走 query/reconcile/run 负控，断言原件不变且不增加 call。接受前与接受后的冻结边界不同，不删 `:172` 来冒充已覆盖 |
| 新 `tests/operations/test_tcad_full_transport_records.py:26/:36` | 完整 stdout/stderr 超旧 8 MiB 与显式 quota/timeout 是不同保证，保留；选择恰好越过历史阈值的输入，不倍增数据作为“更强”。`:32/:33` 的完整重复 bytes 比较可改成长度、流式摘要与末尾 sentinel，避免断言另造大副本 |
| 同文件 `:49` | 9000 descriptors 长路径是让 JSON 超旧 8 MiB 的构造，不能无依据简单缩到几十个。将收集 descriptor 字节身份、完整诊断保留、日志内容哈希幂等的责任拆清；小日志足以测 preserve_log 重复/篡改，勿让大响应、日志副本、模型转储同时堆在一个用例。路径/篡改负控用小 descriptor 即可；`:78` read_bytes 的大副本不是保留完整日志的必要断言形式 |
| 同文件 `:91/:106/:128` | 三层分别覆盖 SSH header、standalone runner 输入、transport CLI 输入，均是本地 stand-in，不是“真实 SSH/solver 已通过”。只给发生历史截断的读取边界保留一个越阈值输入；其余协议和显式 quota 用小输入。每层独立入口的读取错误不能仅用底层 run_bounded 正例替代 |
| 同文件 `:158/:176/:185` | 一个完整 manifest 走 real attest（含末项篡改）足够；重复名/路径/escape 负控不需每次 4100 项，普通小列表即可证明校验仍在。`:185` terminal_error 分支先构造 9000 项、随后 outputs=[]，这部分构造可直接移至 undeclared_outputs 分支，保留 8192 错误全文断言。undeclared_outputs 分支的长 rationale 与 terminal error 是不同序列化边界，保留 |
| `test_full_history_records.py:15` | 当前 25 次 cov.run 同时证明容量、候选上下文、缓存重建、身份。将完整记录越历史容量部分改为封存的通用已接受记录；仅一条真实 local 接受/观测接入。不得把 cov domain fixture 变成通用完整历史的必要环境 |
| `test_delivery.py:191/:268`；`test_generic_inverse_tools.py`（本次未逐用例读完） | 现有交付主体含 cov fixture/harness；优先选其中已有的通用交付路径移除 cov 目标/评分字段，只留候选→审查→确认、篡改、未知不得重发。不要同时维护一套等价新 fixture 框架；未细读的 inverse 用例需先核对再确定替代项 |
| `test_ledger_capture.py:262` 与 `test_artifact_capture.py:686` 的 installed 语义主体 | projection、schema/roots 校验不需要 wheel。对应源码用例（ledger `:74/:180`，capture `:159/:594/:661`）已覆盖若干行为，但未逐项证明完全等价，不能现在整段删掉。把独特断言并入对应 source 检查，再去掉专用安装包装；资源存在性合入可选烟 |
| 安装负控 `test_catalog_installed_entrypoint.py:417/:437` | 改用源码临时 dist-info/真实坏组件或资源保留相同编译器错误码；无需单独安装环境。不能把 declaration_unicode 的不同错误码冒充资源错误 |

### 当前可删的最小项（不等于删整类职责）

静态搜索 `src` 发现 `experiments.MAX_INPUT_BYTES` 只在 `experiments.py:36` 定义，`local_experiments.MAX_SCAN_ENTRIES` 只在 `local_experiments.py:20` 定义，没有运行时读取。因此改小常量不能建立任何“超过旧上限”的负控。逐项处理：

| 用例/断言 | 建议与不丢失的保护 |
| --- | --- |
| `test_local_managed.py:169` | 删除此独立重复用例及无效 monkeypatch。它仍有有效“存在快照”断言，但普通输入快照由 `:35`、真实超旧容量并流式保留由 `:383` 覆盖；不是声称整段没有任何有效断言 |
| 同文件 `:354` | 删除无效常量补丁；其“若干空输入目录仍能成功”不是实际跨旧 1024 阈值的回归。可将一个空目录加进 `:35` 的输入树后移除独立重复 dispatch；不以任意增加目录数重建压力用例 |
| 同文件 `:363` | 去掉独立重复 dispatch：空 artifacts 子目录没有科学输出时 result missing 的有效断言合入 `:61` 的 missing 场景；保留 completed.json 已存在的断言。不能只删掉唯一的完成事实保护再宣称减重 |
| 同文件 `:374` | **不直接删除排除 prior artifacts 的职责。** 当前只建空目录并断言成功，不能证明 prior 文件没进快照。把旧输出放一个可识别小文件，并在 `:35` 场景断言 accepted.snapshot_files 无 artifacts/，再删该薄弱独立用例。生产排除逻辑在 `local_experiments.py:104`，这是有效职责 |
| 新 `test_execution_configuration.py:181` | 删除固定代码文件数量 ==3 的断言；同用例 `:182`–`:184` 的 helper 改变拒绝继续证明身份覆盖。数量只是测试包布局细节 |
| 新 `test_tcad_full_transport_records.py:186` terminal_error 情况 | 不生成随后立刻丢弃的 9000 outputs；只改构造位置，不删错误全文边界保护 |

上述是明确可删/可合并项，没有证据支持现在按整个 operations、artifact_agent 或 installed 文件批量删除。

### 旧入口退役才删；迁移只取语义

- `tests/operations/test_codex_root_host_installed.py:4/:40`、`test_analysis_tool_installed.py:33`、`test_catalog_installed_entrypoint.py:224`：RootHost、daemon、MCP local_worker/proxy、旧 Root/Worker 闭环。源码仍提供 `scid`（`pyproject.toml:27`），README `tests/README.md:65` 明确这些入口仍支持；不能用薄层本地 fixture 替代真实远端能力后就删除它们。运行语义可去掉安装包装，但入口本身的支持账未关闭。
- `test_r4_execution_approval_identity.py:238/:619/:672/:688/:704`：确切对象审批、revision 不继承、契约漂移/插件移除/错误身份阻断。fixture 自 `:10` 导入 ExecutionBridge/RootMCPRouter/open_runtime，不能原样迁移。P3 需要对应新实例语义负控；旧调用者退役前旧测试保留。
- `test_frozen_input_execution.py:75/:160/:182`：受限源继承、错误 derived ref、同名复制不能冒充来源。应复用这些反例思想；旧 ArtifactRef/transaction/Root admission fixture 不当成新薄层架构。
- `test_instance_archive.py:206/:223/:252/:408/:462/:515`：旧 SQLite/审批 nonce/精确执行诊断/插件文件/断点恢复。P4 只把原件、插件归属、篡改、提交前后断点语义接入新实例存储；其 session/client 归档许可测试（`:66/:86`）随旧入口消费者退役再删。旧归档逻辑仍承担支持责任，不能只因薄层也有 history archive 删除。
- `test_root_reading_installed.py:5`、`test_tool_contract_reader_installed.py:4`、`test_minimum_support.py:697`：scheduler 资源、旧工作区独立读取器；不属于薄层 prepare 的必要覆盖，包装语义可收敛，但是否删文件要跟对应生成/发布消费者的退役决定绑定。

### 暂无法判定

`architecture` 安装环境的脚本级外部消费者；完整 `test_minimum_support.py`；安装事务/真实依赖解析跨交付方式；全部历史协议形状组合；全部 archive 故障点是否两两等价；领域专属科学/物理验证。本文未取得足够语义证据，不提出整文件删除。另已核对 `test_unified_mcp.py:555`–`:565`：名为 installed_probe 的局部变量只是在 `:558` 把 src 链接到临时 site 后调用安装器的 probe_mcp shell 函数，**没有通过上述安装 fixture，也没有在这段构建/安装**；它证明源码条件下真实 proxy/daemon 的探针协议，不能把变量名算作 wheel 安装证据。该文件其他大量行为未逐项复核。

## 独立维度：这个测试能证伪哪个真实生产行为

确定性输入配已知答案是回归测试的正常形式；需要剔除的是答案由 fixture 自己制造、关键生产决策被替换后，只检查自己制造的结果。是否启动 subprocess、是否安装 wheel、是否使用“real”命名，都不能单独证明有效。以下维度与上面的复用分类并列，保留建议只限于表内可证伪的行为，不扩大解释为科学资格或整体闭环。

| 拟保留或改写的测试 | 哪个生产缺陷出现时应失败 | 自证循环/证据限制与处置 |
| --- | --- | --- |
| 新 P1 `test_execution_configuration.py:67` 自动接线 | `native.run_native` 仍硬选 local；prepare 没冻结 operator 配置；W 不能拿到注册能力/完整 schema；真正 experiments CLI 无法执行/查询同一 opaque call；重跑增加 call | `NATIVE` 的 H/A 固定给 experiment/finish，不能检验角色是否会正确作科学决定；W 则在 `:26`–`:40` 调用实际 capabilities/describe/run/query，关键执行链没有由 fixture 直接写 completed.json。保留这部分机械接线证据；`:24`–`:25` 提示词字符串只证明文字存在，不能证明 unsupported 永不被当成功，退出条件应依赖状态负控而非该字符串 |
| 同文件 `:122` prepare 禁工厂 | prepare 试图提前 build adapter 或伪造任务，forbidden_factory 会立即失败 | 属于有意义的“禁止副作用”哨兵；没有实际启动模型不减损该保证，不能拿它证明正常 adapter 配置可用 |
| 同文件 `:134/:146/:153/:161/:191` 准入负控 | 宿主字段通过、外部所有权冲突被接受、重名注册任取一个、错误 binding/config 触发 native Popen | 字段集合来自生产 `HOST_CONFIGURATION_FIELDS`，若生产误删一个禁止字段，参数列表也随之消失，测试会共同漏掉！改写时固定公共禁止字段契约中的代表身份/权限项，断言行为；其余扩展列表可来自契约，但不能只遍历实现常量就声称完整防注入。Popen 哨兵需保留；错误发生后无实例/无 calls 是真实副作用负控 |
| 同文件 `:172/:231` 包 helper 身份 | 只 hash factory 而漏 helper，或新文件/删除/链接后仍接受旧任务；query/reconcile/run 绕过冻结校验 | helper 改变发生在真实文件，不由 mock 直接抛预期异常；真正 CLI 路径会加载修改后的包。删文件数断言；检查调用数/原件未变，避免仅检查某错误字符串就允许另一次提交 |
| 同文件 `:215` 默认 local cwd | 宿主没有把当前 workspace cwd 注入 local config，相对原件读取失败或 cwd proof 不同 | 固定 H/A JSON 不影响 cwd 缺陷辨别力；但完整 H/W/A 仪式不是 cwd 的核心证据，按前述方案收窄 |
| `test_local_managed.py:35/:61/:83/:383` | 接受后改输入仍从可变目录读；字面 argv 经 shell；缺 result 抹掉成功；unknown 被升级/重发；快照改为大文件 read_bytes | `:35` patch `_execute` 只在调用真正原方法前改源，关键执行没替换；`:83` 模拟 cleanup unknown 只证明该报告的消费/不重放，不证明操作系统 cleanup 本身可靠；后者由进程 owning 测试证明 |
| `test_registered_experiments.py:106/:119/:177` | lookup 丢回应后重复 submit；丢 submission.json 后不能恢复同一绑定；未声明 query 仍获权 | 使用确定性 fake backend 是外部响应控制，保留实际 Records/调度路径及调用计数；不能据其成功宣称 TCAD 协议已接入 |
| `test_composed_execution_results.py:67/:81/:89/:153` | 仅有私有 candidate 字段就被纳入候选；collect=false 阻断有效终态；重复 reconcile 再读后端/提交；篡改身份仍封存 | fixture 的 Remote.complete 在 `composed_execution_fixture.py:37` 自己写终态，**不证明真实后端能独立完成或跨进程存活**；它能证明控制层消费终态与冻结不变量。需要异步独立进程资格时使用/改写 owning 进程场景，不把这条 fixture 完成当作 P2 整体验收 |
| 新 TCAD `test_tcad_full_transport_records.py:26/:36` | run_bounded 对完整 stdout/stderr 仍截到旧上限、显式 stdout quota/timeout 失效 | 小程序只生产字节，生产读取/超时逻辑是真实的，已知字节答案可证伪截断；不支持任何 solver 结论。stderr 显式 quota 的 excerpt 是约定语义，不应为了统一全文错误删除 |
| 同文件 `:49` command collect、`:91` SSH RPC、`:106` runner、`:128` transport CLI | 大描述符响应/请求在某读取边界截断；stderr 未归档；runner 请求过旧界限失败；显式 transfer/manifest quota 被取消 | command stand-in 自己输出 descriptor，证明消费者而非生产端收集完整性。SSH executable 是本地脚本，`_client` 再 exec 实际 runner，不能检验 SSH连接、远端 Python 3.6、许可证。保留不同读取边界的证据但收窄每层大数据；“有 subprocess”不是增加重复大 payload 的理由 |
| 同文件 `:158/:176/:185` attestation | 忽略最后一项、丢检查、遗漏 hash mismatch、允许重复/escape、失败理由序列化被截断 | 不是只断言 fixture 的 9000 数量；`:168`–`:170` 末项改 bytes 必须把 verdict 翻为 fail，这是明确负控。保留翻转；重复名/路径负控小输入足够。不能由 attestation pass 推出科学有效性 |
| `test_delivery.py:153/:191/:220/:268` 与完整原件检查 | 通用 descriptor 硬依赖 cov 字段；未审/泄漏被提交；已冻原件被换还通过；partial 被确认或重复提交；history 变成整文件读入 | delivery fixture 可能自造领域评分/确认标记，只证明确定性门禁消费；必须保留真实 `delivery.invoke`、目标字节和无新提交记录断言，不以 fixture 提供一个 confirmed JSON 就收口。未来通用改写不得 mock 掉 invoke/候选资格决定 |
| `test_controller.py:316` 与 `test_runtime.py:73/:139` | 锁不互斥；断开控制器后第二次启动 native；intent 无运行证据却自动重发 | controller scene 模拟 contracts/native，只适合锁和局部路由；runtime 则有实际独立本地进程及启动计数，能推翻重复启动。不要用 scene 的已知 result 替代 runtime 恢复证据，也不要求所有局部路由都启动进程 |
| `test_current_protocol.py:118/:143/:209` | 旧原件写入口继续 mutation、只读重建 cache、旧 scope 仍加载 factory | 文件树/原件不变与禁止副作用哨兵是真实的保护；它不证明旧科学 schema 在当前运行仍可写，旧对象本就只读 |
| `test_full_history_records.py:15` 当前 cov 25-call 场景 | complete observation 丢第17/25候选或 contexts、缓存删除后 lineage 身份不同、旧 proof 篡改不被发现 | 当前 fixture 预先生成成功结果，不能证明 cov 学到有效模型；它能证伪历史关联/容量/原件校验。改写为通用已接受记录后，仍须保留一条真实接入，避免全由测试手写 observations 再读回自己 |
| 旧安装 `test_analysis_tool_installed.py:8` 源码/安装 catalog 相等 | wheel 漏资源、装错版本或 entry point 导致两个 catalog 不同 | 两边用同一个 compile_catalog；编译器共同产生错误 scientific contract 时仍绿。它证明包装一致性，不能成为业务正确性/薄层资格；不能为它展开所有业务环境 |
| 旧安装 `test_catalog_installed_entrypoint.py:126/:177/:208/:212` | core 多带领域包、curve 暗依赖 figure、图片依赖装漏、TCAD依赖声明不解析 | 是各自明确的打包反例，已知 catalog/PNG 答案合理；只有包装变更才安排选定检查。不能从 core catalog pass 推出 local execution native 接线可用 |
| 旧安装 `:224` Root/Worker 链与 `test_m7_effect_fixture.py:4` | 已安装第三方插件实际不能被旧控制链调用/工厂绑定错误 | 前者真实走旧控制链但答案由 fixture 提供，支持的是旧入口的机械链；后者只加载工厂/绑定，不发生外部执行。二者都不能给新薄层执行授权/TCAD生产资格背书 |
| 旧安装 `test_codex_root_host_installed.py:4/:40` | wheel 漏模块、app-server stand-in 不能初始化/恢复身份、daemon不能起 socket、close未清理 peer | peer 按脚本返回已知 JSON，检查的是 transport 生命周期；不证明模型 wait/resume 决策正确，也不证明真实平台运行。可回到来源进程检查，名称或 installed 标签不提高证据层级 |
| 旧来源/授权/归档代表（上节点名） | 错 exact subject 能获授权、revision 继承决定、来源限制消失、篡改或断点恢复丢原件 | 价值来自禁止条件和原件/事务不变量。迁移时如只手写一个 approved/archived JSON 后断言状态，会丢掉这些证伪能力；须经实际新层授权/归档入口后再断言，而非继承旧 fixture 结构 |

特别应删除的“结果已知但不解决问题”是字段数量、提示词出现、内部调用次数等无法连接用户故障的断言；有明确副作用约束的调用次数（例如 submit 必须至多一次、Popen 必须零次）则直接连接重复计算/越权故障，应保留。表内尚未逐条对照所有实现分支的旧测试仍受本报告未覆盖范围限制。

## 新薄层最小检查方案（复用现有节点，不新建框架）

这是一张按变更选择表，不是新的全量必跑清单。每行只有相关职责改变时才触发；多行证明同一缺陷时取能覆盖真实入口的最小组合。

| 何时选择 | 最小保留检查 | 实际用户损害 |
| --- | --- | --- |
| 配置选择/宿主接线改变 | P1 一个非本地 CLI 自动接线正例；一个 CLI 非法配置无实例负例；其余字段/缺失/重复直接验证器 | 选错后端、用户配置劫持身份、非法配置先发任务 |
| 已接受执行身份/恢复改变 | 已接受记录后一个实现变化贯穿 query/reconcile/run；直接校验路径集变化；一个 lost reply lookup | 插件升级重发旧任务或静默用新实现 |
| 本地输入/执行/结果改变 | local snapshot+字面 argv；一个缺失/坏 result；unknown 不升级/重发 | 执行错原件、shell 注入、失败事实被覆盖 |
| opaque/异步接缝改变 | 无 collect 的终态 reconcile；一例 private local-like 字段不能推断候选；一例错误身份 | TCAD 被伪装成本地候选，异步终态遗漏/重提交 |
| 封存/预算/恢复改变 | 重启重接原执行；unknown 无启动不重放；仅锁实现改变时加一个两进程竞争 | 重复付费执行、预算重置、双写 |
| 通用候选交付改变 | 已有通用小候选冻结→审查→确认；篡改拒绝；unknown/partial 不确认或重发 | 提交错候选、未经审查发布、重试重复交付 |
| 完整原件容量/存储改变 | 对发生截断的读取边界一个越历史阈值原件；流式摘要/完整末项；一个小的显式 quota 负控 | 完整科学证据被展示上限截断；不要在所有层重复大 payload |
| TCAD transport/attest 改变 | 对受改读取边界的本地协议 stand-in；完整 manifest attestation 含末项篡改；小数据路径/唯一性负控 | 截断原始输出、吞掉失败理由、采集错原件；不证明真实 SSH/solver 可用 |
| P3/P4 实现时 | 从上列旧来源/授权/归档测试抽取确切对象、不继承决定、插件原件、篡改、断点语义，走新入口 | 授权越权、来源限制丢失、归档恢复丢证据。当前仅列缺口，不提前造整套测试 |

### 功能组与安装组的具体拆分（用户硬要求，尚未实施）

1. 复用现有 lane 选择机制，把安装检查与其私有 fixture 移到一个独立 `tests/installation/` 目录；构建/venv/pip 只允许从该目录的 conftest 触达。`tests/operations/conftest.py` 不再导入 `scripts.installed_candidates` 或提供安装 fixture。无需另建运行器或 fixture 体系。
2. 根 conftest 在收集导入前按现有显式 `--test-lane installed` 排除/允许该目录；默认功能全量，以及 source/process/stress 等所有功能选择都排除安装目录，不能只在执行阶段 deselect。显式安装组也不回收任何 source/process 功能用例。功能 fixture 不得传递请求 installed_probe/installed_environments；不以环境变量偷偷把同一功能测试转换成 installed 模式。
3. 对 `test_execution_configuration.py:55/:69/:75` 的 `SCID_EXECUTION_INSTALLED` 分支、`test_composed_execution_results.py:44` 的 `SCID_COMPOSED_INSTALLED` 分支，建议在精简时去掉“同一套功能换解释器重跑”入口。新 P1 整组 installed 复跑不接受；配置准入、native 接线、恢复、身份篡改均只在功能组验证。
4. 独立安装组只保留包文件/资源是否存在、真实 public console 是否可装载启动、entry point 是否发现/唯一/可加载、必要依赖声明或解析。不能在其中再封存科学结果、运行业务评分、走 Root/Worker 全链或重复配置/恢复矩阵。某依赖需要一次最小 import 才能发现漏装时，只做那个 import；不以“顺便再跑评分”扩张。
5. 现有 LazyEnvironments 九环境池不作为新默认安装 fixture 继承；独立包装烟只创建一次所选交付环境，不在测试之间切换删除重建。环境分离需求先由静态元数据/源码负控验证；确实互斥且未实际装过的包装组合标为未验证。

下表是当前安装用例迁回功能组/去重的具体账；“保留包装”只指留下的小检查，绝不要求再建立同名完整测试副本。

| 当前用例 | 迁回功能组或并入已有检查 | 独立安装组最多留下什么 |
| --- | --- | --- |
| `test_catalog_installed_entrypoint.py:126` core catalog | cache 对象相同、operation 集合语义回源码；第三方/领域模块是否排除属于包布局可留 | 实际 core entry point 集合、必需公共模块存在、领域包未误带 |
| 同文件 `:177` curve score | scoring 状态/PNG 输出/算法行为回 owning source 测试，不能安装后重跑 | curve 依赖声明、独立 import 无 figure 依赖；仅相关包装改动时选 |
| 同文件 `:208` figure image tool | 完整 `_INSTALLED_CURVE_TOOL_PROBE` 的图像工具调用/响应和 scientific schema 行为回功能；先合并已有覆盖 | 必需图片依赖和包资源可 import/访问；不重跑图像业务 |
| 同文件 `:212` tcad dependency | catalog 中 experiment/diagnose 归属回源码 | 必要 TCAD→curve 依赖声明/一次解析（如果本轮交付元数据改变） |
| 同文件 `:224` third-party local run | 旧 Root/Worker/提交/读取全链放旧入口功能/进程组并去重，随旧入口支持账保留 | 如果第三方打包接口改变，在单次 smoke 确认那个 entry point 可加载；不再完整运行 |
| 同文件 `:417/:437` broken/unicode | 稳定诊断是功能负控，改用源码 metadata/resource 后去掉安装包装 | 不留两个坏插件安装环境 |
| `test_analysis_tool_installed.py:8` | 所有科学 operation digest/agent_type 语义留功能；源/包同编译器比较不是业务资格 | 只对必需资源和真实入口作加载/存在检查，避免全 catalog 双算作为包装常规门禁 |
| 同文件 `:33` stdio errors | 两个错误协议入口迁进程组；复用真实 MCP/proxy 负控，不因换 wheel 再跑 | 公共 console/module 入口可装载，止于该边界 |
| `test_codex_root_host_installed.py:4/:40` | fake app-server 生命周期、daemon socket 初始化迁进程组/合并旧入口已有检查 | 必需公共模块/console 能装载；不是再次启动业务 daemon |
| `test_m7_effect_fixture.py:4` | factory→adapter binding/load 语义迁源码注册功能检查 | 确实变更第三方插件交付时才确认 entry point 发现，不在包装烟再 open_runtime |
| `test_root_reading_installed.py:5` | initialize_platform 写 guides 和内容比较迁功能，合并 scheduler/deploy 检查 | 仍支持的 scheduler data-files 存在/可访问 |
| `test_tcad_knowledge_closure.py:18` | instructions/prompt 拼接与能力语义迁源码 | TCAD 声明角色资源在 wheel 可访问；与同 cohort 资源检查合并 |
| `test_ledger_capture.py:262` | projection/settings/schema 迁 source，先并入 `:74/:180` 等适用检查，保留独特负控 | 无专门 installed 重跑；模块缺漏由公共入口 smoke 曝露 |
| `test_artifact_capture.py:686` | schema/roots/LocalTrustedBackend 迁 source，先并入 `:159/:594/:661` 等适用检查 | 不为这组创建 core 环境 |
| `test_tool_contract_reader_installed.py:4` | 生成 reader 后用 `-I` 独立读取是功能/进程性质，源码条件同样可验证无需 wheel | 若 reader 模板确有单独 packaged 文件，资源存在性可并入唯一 smoke；不重走读取业务 |
| `test_minimum_support.py:697` | M1 open/copy/input/reference readers 是旧功能链，迁回其功能组；未逐断言读完，先保留行为，去安装依赖前核对去重 | 仅实际依赖的 package-data 可访问；不把整条 minimum-support 链保留安装组 |

`test_catalog_installed_entrypoint.py:18` 已直接造 dist-info 调实际 installer 声明校验，**没有安装**；可继续放功能/安装器语义检查，不因文件名含 installed 就要求搬进 wheel 环境。独立安装组不纳入功能全量，是用户本次明确约束，优先于技能中的旧安装门禁建议。

### 默认零安装与唯一可选安装烟

默认验证没有 pip、wheel、venv fixture；source metadata stand-in 只能证明发现逻辑与语义，必须写明没有证明 wheel。普通配置/恢复/结果逻辑修改止于上述定向语义证据。

确实修改 `pyproject.toml`、console entry point、package-data、插件依赖/加载交付方式时：先静态核对声明与文件，再在已具备事故要求的硬资源域和持久日志条件下，安排**一个干净环境、一个选定 cohort、构建一次、安装一次、顺序执行一个冒烟程序**。这不是当前授权执行，当前不运行。

以核心薄层为对象的该程序只需确认：从 checkout 外清除 PYTHONPATH 后加载安装包；实际 `scid-research`/`scid-experiment` console 可装载并显示公共帮助；真实 execution entry point 唯一且可加载默认 local 的注册声明；声明的必需资源/依赖可访问。止于安装发现边界，不执行本地实验、不创建业务实例、不在已安装环境重新证明 query/reconcile、H/W/A 或配置负控。

如果改动对象是 TCAD 的依赖解析或领域资源，选择一次包含该插件的明确交付 cohort；确认其真实依赖/资源发现即可，不同时再安装 core、curve、blind_csv、broken 等矩阵。无法用一次 smoke 同时证明互斥的 core-only/curve-only 缺包场景时，未测的可选组合明确留作未验证；不为“全覆盖”静默重建环境。单次 smoke 不等于证明 `deploy/install.sh` 事务、Git 源码发布或未声明的 Python sdist 路径。

## OOM：能证实与不能证实

事故事实以 `TEST_RESOURCE_INCIDENT_20261017.zh-CN.md:7`–`:11` 为准：用户报告 OOM；重启后的可用内存不是事前峰值；先前 `/tmp` 原始日志丢失，未取得 kernel OOM 条目、确切命令、峰值、受害进程或落盘终态。最近处于 P1 安装门禁阶段，但不能据此证明两个批次并行，也不能认定容量补修批次已运行。

静态代码能证实：安装环境切换重建；多个测试会启动多个本地子进程；有完整 payload 与断言副本；监督器是采样且没有内核聚合硬约束。这些说明成本和保护缺口，**不是某一项造成此次 OOM 的因果证据**。当前禁止安装/并行/大规模回归应继续生效，不能以“已串行”“日志有界”宣称不会 OOM，也不能恢复旧科学原件容量限制来遮蔽测试运行问题。

本次没有执行证据，不能给出通过率、内存峰值、耗时收益、精简后的实际资源安全性或最终生产资格。实施精简后仍需在约束到位时以最小相关检查取得新证据，不重跑原安装批次来复现事故。
