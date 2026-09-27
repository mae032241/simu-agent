# R5-H H6 一次性验收归档与职责内聚收口计划

日期：2026-08-31  
状态：H6-C 首轮总审查打回项已最小返工，候选待独立复审；H7 尚未放行  
前置门：H5 第二轮独立实现复审通过  
目标：从默认开发、测试和发布表面移除一次性 R5-G/D4-H2 编排，同时只在有明确多职责证据时拆分生产文件

## 1. 核心判断

H6 不是新的架构重构阶段。当前运行时已经只有一个启动编译目录、一个数据库 current 权威和一条
正式 `spawn_agent` 派发路径。H6 已知的剩余负担主要在仓库外围：

1. 七个 `r5_g_*.py` 共3743行，只服务已停止的单次 Fig.4/R5-G/D4-H2 评估；
2. 四个 runner 测试及 `test_r5_frozen_baselines.py` 的后四项仍被默认回归收集；
3. 首轮审查开始时 `docs/plans` 顶层37个文件、`reviews` 124个文件，递归合计161个；发布脚本把
   整个目录都带入源发布包。审查报告生成后数量会继续增加，实施必须重新机械计数；
4. 当前最大生产文件虽仍较大，但 Root、Task、Worker 已按权威边界拆开；剩余大文件尚无第二权威、
   反向依赖或独立变化频率证据，继续拆分可能只增加导入和转接层。

因此本阶段以“归档一次性表面、缩小默认面、没有证据就不拆”为原则。不得为了满足行数指标删除
仍被当前路径使用的生产代码。

## 2. H6-A：封存 R5-G/D4-H2 一次性评估

建立仓库内、非临时目录 `archive/r5-g-evaluation/`，保存：

- 七个 `scripts/r5_g_*.py` 的原始相对结构；
- 四个 `test_r5_g_*_runner.py`；
- 当前 `test_r5_frozen_baselines.py` 的完整冻结副本；
- 当前 `tests/operations/conftest.py` 的精确冻结副本，作为历史安装态测试 harness；
- 一份中文 README，记录科学结论为 `blocked`、停止门、运行前提、原始路径、最小复跑命令、
  当前工作树外的私有运行状态不属于归档；
- 一个仅覆盖归档文件的 `MANIFEST.sha256`。

默认 `scripts/` 删除七个一次性入口，`tests/operations/` 删除四个 runner。活动
`tests/operations/conftest.py` 同时删除 `r5_e2e_tcad_plugin` wheel 源和 `r5_e2e` 环境，避免默认
session 继续构建无人消费的一次性 Fig.4 环境。原
`test_r5_frozen_baselines.py` 的前三项仍验证当前结构指标、干净 wheel 目录变化和 TCAD 参数链，迁入
一个当前测试文件；后四项固定 Fig.4 fixture、回放执行和一次性量表，只保留在归档副本，不再进入
默认回归。

`tests/fixtures/r5_e2e_tcad/`、对应测试插件、持久 workspace 证据和 deliverables 不移动、不删除。
它们是冻结输入/结果证据，不是产品入口；归档 README 只按当前相对路径引用。不得改写其科学内容
或哈希来适配新目录。

归档不进入 wheel、运行服务、Operation catalog 或源发布包。不得承诺通过 `PYTHONPATH` 直接复跑，
因为原脚本和测试按 `__file__` 推导仓库根并依赖原 pytest harness。唯一允许的取证复跑方式是：在
新建临时目录中恢复冻结源码/源发布闭包，把归档脚本、测试和 conftest 按原始相对路径放回，逐项
核对哈希后运行，结束后删除临时派生树。不得在活动仓库创建 wrapper、alias、symlink 或兼容入口；
缺少私有 run state 时明确不可复跑，不得补造状态。

H6-0 冻结“原路径 → SHA-256 → 归档路径”表。移动时逐文件拒绝符号链接和已存在目标，复制/移动后
先比较源目标字节与哈希，再删除源路径；不得使用无界 glob。归档 manifest 覆盖归档字节，外部
fixture 只记录其 manifest 身份，不复制、不接管用户资料。

## 3. H6-B：收窄活动决策与发布文档面

本地 `docs/plans` 保留完整决策历史，不批量移动或重写284个文件，避免制造断链和无意义改名。
活动入口 `docs/plans/README.md` 只把以下内容列为当前：

- `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`；
- `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md`；
- H6 当前实施记录和当前有效独立门报告。

其他文件放在明确的“历史决策语料”索引下，不再描述为并行活动计划。

本地索引含未发布历史链接，因此不进入精简发布包。`scripts/build_git_release.py` 不再递归复制整个
`docs/plans`，改为在既有静态 tuple 中显式复制：

- `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`；
- `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md`；
- `R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md`；
- H6 当时唯一有效的“通过”独立门报告，最终实施审查生成后以最终报告作为当前门证据。

H5 及更早计划/审查保留本地历史，不进入当前发布最小集合。现有 `DOCUMENTS` allowlist 还必须显式
补入 `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md` 和
`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`，因为当前中文架构直接声明二者为设计宪章和
33项约束。根 README、NOTICE、SECURITY、安装/发布/协议文档和插件 README 继续由既有 allowlist
保留。以上都是构建期文件清单，不是运行时文档注册表、版本判断或兼容入口。

## 4. H6-C：巨型文件重新评估，默认不拆

重新计算生产文件、职责聚合、导入方向和消费者。只有同时满足以下条件才允许拆分：

1. 文件包含两个可独立描述、独立测试并有不同消费者的职责；
2. 拆分不增加服务、facade、Registry、状态、数据库对象或兼容层；
3. 调用方向单向，权威数量不变；
4. 生产总行数不增加，测试能证明行为和摘要不变。

实施必须对当前所有至少1000行的生产 Python 文件，以及计划额外点名的文件，逐项记录职责、生产/
插件/测试消费者、共享不变量和不拆理由。行数只定义审计全集，不构成拆分理由。当前预判如下，
必须由实施审查复核：

- `task_worker_files.py`：受控 Worker 文件生命周期单一职责，不拆；
- `scheduler_bindings.py`：实例与语义绑定的单一数据库权威，不拆；
- `project_packager.py`、curve `schema.py`：消费者较多，是未来内部拆分候选；当前无死代码、第二
  权威或必须拆分的缺陷，不迁入核心；
- `tasks.py`、`task_outputs.py`：现有 TaskService 状态事务和输出 mixin 边界已明确，不拆；
- `debug_service.py`、TCAD `transform_adapter.py`、`parameter_operations.py`：当前均为有真实消费者的
  领域内聚闭包，不拆；
- `mcp_root_operation_routes.py`：统一 Operation 调用入口，按 executor 再拆会增加转接，暂不拆；
- `approvals.py`、审批 `app.py`：分别持有审批服务和 loopback UI 单一职责，本阶段不拆；
- curve `analysis.py` 低于1000行但由计划点名，仍记录消费者并保持领域所有权；
- H4 保留的独立 Worker 进程基座不在 H6 删除或接线。

若消费者和依赖审计没有推翻上述判断，H6-C 的正确结果就是“零生产拆分”。只有发现经消费者审计
证实的死生产表面才要求净删除；否则生产代码不得增加，运行代码零变化优于无理由删除。不得以
新增转接换取表面缩短；仓库默认测试/入口和发布体积必须实质减少。该措辞必须同步到主计划 H6/H7，
不能由本子计划单独解释状态权威。

## 5. 分阶段实施与审查门

### H6-0：方案与冻结清单

- 冻结七个脚本、五个测试文件、当前 operations conftest、fixture manifest 身份和历史文档实际
  数量/哈希；首轮审查观测的37+124=161只作为当时快照，实施当刻重新计数；
- 冻结当前默认 Operation 测试数317、部署/平台/33项约束38、生产150文件/59317行、
  `operations/` 7文件/2064行、R0核心9518行、Task6031行；
- 独立方案审查通过前不移动文件、不改发布脚本。

### H6-A：一次性评估归档

- 按冻结路径表机械移动并生成归档 README/manifest；
- 迁留三个当前 baseline 测试；
- 活动 conftest 删除 `r5_e2e` wheel/venv；验证默认测试不再导入 `r5_g_*` 或构建一次性环境；
- 记录后四项产品不变量由当前 catalog、Effect/UI/Execution 和 InGaAs 测试替代覆盖的映射；
- 在临时派生树按原路径恢复一次并验证归档 manifest/恢复步骤；不得在活动树复活入口；
- 独立审查通过后才进入 H6-B。

### H6-B：活动语料与发布收窄

- 更新计划索引和发布 allowlist；
- 构建干净发布树，确认不含 `r5_g_*`、一次性 runner、历史计划全集或私有状态；
- 当前架构双语文档、设计宪章、33项 YAML、安装/发布、插件、法律/安全资料及当前 H6 决策文档存在；
- 发布 manifest 的实际路径集合等于 allowlist 展开结果；本地历史索引不进入发布包；
- 独立审查通过后才进入 H6-C。

### H6-C：职责审计与总收口

- 输出大文件职责/消费者结论；没有满足四条件的对象则不改生产代码；
- 串行运行默认 Operation、部署/平台/33项约束、clean release 和归档完整性；
- 新的独立实现审查通过后只放行 H7。

## 6. 验收

1. 默认 `scripts/` 和 `tests/operations/` 不含 R5-G/D4-H2 专用入口或 runner；
2. 归档 README、原始脚本/测试/conftest 和 `MANIFEST.sha256` 可核验；临时原路径恢复步骤通过，
   fixture 与用户数据未删除；
3. 当前三项通用/TCAD baseline 测试继续在默认回归中通过；
4. 默认测试收集数按归档项可解释下降，生产功能测试无减少；
5. 源发布包不含归档、历史计划全集和带断链的本地索引，只含显式当前决策、架构宪章和33项约束；
6. 生产文件数、Operation 数、catalog 构造点、数据库对象、状态、路由和注册表不增加；
7. 无证据时不拆巨型文件；若发生拆分，必须生产行数不增且另行独立审查；
8. `archive/`、`deliverables/`、`123/`、workspace、运行状态和用户数据均不被自动清理；
9. H6 所有 pytest 命令均先设 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2` 并串行；完整默认回归、
   38项架构/部署组合、规范化发布 manifest 和 `git diff --check` 通过；
10. 独立审查确认 H6 是仓库表面减法，没有把归档变成第二产品入口。

## 7. 明确不做

- 不修改 OperationSpec、编译器、调度器、Task/Approval/Execution 生命周期；
- 不新增 ArchiveService、文档 Registry、迁移状态、兼容导入或运行时开关；
- 不把一次性 runner 泛化成产品工作流；
- 不删除 fixture、workspace、deliverables、用户状态或历史审查证据；
- 不为降低单文件行数强拆内聚领域模块；
- 不在 H6 重跑科学 Agent 或 TCAD solver；真实 Agent/工具/结构回归属于 H7。

首轮独立方案审查见
`reviews/R5_H6_ARCHIVE_AND_COHESION_CLOSURE_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，主代理核验报告
SHA-256 为 `5a056b624239f3aabde437a516441b8ea15f6cf1a3d5fba969c83f2938ff8c98`，结论“打回”。第二轮复审见
`reviews/R5_H6_ARCHIVE_AND_COHESION_CLOSURE_PLAN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，报告 SHA-256
为 `9a2e990004539e311b9d3aed92f96962524d9e000451aa1ec202a76d25963867`，结论“通过，仅放行 H6-A”。
H6-A 实现及独立审查通过前仍不得进入 H6-B。

## 8. H6-A 实施记录

H6-A 已按第二轮通过方案完成候选实现：

1. 七个 `r5_g_*.py`、四个 runner、完整冻结 baseline 测试和冻结 operations conftest 已保存到
   `archive/r5-g-evaluation/`；十三份原文件的字节哈希与 H6-0 冻结值一致；
2. 归档 README 明确记录科学结果为 `blocked`、停止门、外部 fixture/workspace/private-state 边界、
   原路径、哈希和取证恢复前提；归档 `MANIFEST.sha256` 校验全部通过；
3. 默认测试只保留 `test_r5_current_baselines.py` 的前三项当前结构/clean-wheel/TCAD 参数链验证；
   活动 conftest 只删除 R5 专用 wheel、wheel 解析和 `r5_e2e` 环境共三处，不修改其余安装矩阵；
4. 默认 Operation 测试从317项降为292项，精确减少21项一次性 runner 和4项固定 Fig.4 验收；
   当前产品能力的36项聚焦替代覆盖通过；
5. 临时源发布派生树首次运行得到25项通过、3项因缺少 Git 基线对象和 manifest 指向的持久 workspace
   证据而失败；补入这两个已声明的只读取证前提后，归档五文件 `28 passed in 44.84s`。没有修改
   归档测试或产品代码来掩盖前提；临时树随后按精确路径删除；
6. 默认 Operation 全量 `292 passed in 100.26s`；部署、平台和33项约束组合
   `38 passed in 5.66s`；`git diff --check` 通过；
7. 生产指标保持150文件/59,317行，Operation 包保持7文件/2,064行，R0核心9,518行、Task职责
   6,031行。H6-A 没有新增或修改生产运行逻辑、状态、注册表、路由或控制面校验。

H6-A 独立实现审查见
`reviews/R5_H6_A_ARCHIVE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`，报告 SHA-256 为
`0382ac1505cea714d66ce1f0f5e9c42105b950d10b51cf3f4b435411a94b321a`，结论“通过，仅放行
H6-B”。H6-B 独立实现审查通过前不得进入 H6-C。

## 9. H6-B 实施记录

H6-B 已完成候选实现，改动仅限活动决策索引、现有源发布静态清单及其测试：

1. 本地 `docs/plans` 的37个顶层文件、127份 reviews 和递归164份完整历史文件均原位保留；
   `docs/plans/README.md` 只把总计划、R5-H、H6和H6-A当前通过门列为执行链，其余按历史语料
   分类，不再冒充并行待办；索引四个链接均可解析；
2. `build_git_release.py` 从既有 `SOURCE_TREES` 删除递归 `docs/plans`，并直接在既有
   `DOCUMENTS` tuple 中增加三份当前计划、一份H6-A通过报告、设计宪章和33项约束；没有新增
   文档 Registry、动态发现、状态、服务或版本分支；
3. 干净源发布只含上述四份 `docs/plans` 文件，明确不含本地历史索引、旧整改计划、归档、
   workspace、deliverables、`123/`、`.scidiscovery`、R5-G脚本或runner；现有双语架构、安装、
   发布、插件、法律/安全文档继续保留；
4. H6-A 前的同一构建器试运行记录为408个受跟踪源文件；H6-B候选为251个，其中 manifest
   覆盖的250个实际文件与发布树非manifest普通文件集合完全相等，净减少157个发布文件；
5. 发布构建测试通过；部署、平台和33项约束组合 `38 passed in 5.28s`；
   `git diff --check` 通过；
6. 本阶段不修改生产Python、OperationSpec、catalog、控制面、插件注册、Agent派发、测试收集或
   归档字节。当前H6-A通过报告作为发布中的最近有效门；H6最终审查形成后才替换为最终门证据。

H6-B 首轮独立实现审查见
`reviews/R5_H6_B_RELEASE_DOCUMENT_PROJECTION_INDEPENDENT_REVIEW.zh-CN.md`，报告 SHA-256 为
`2cdb19858895a4f382ba74ef907dd662c90695cc5242abc86ba0741a6a4bbfb1`，结论“打回”。唯一阻断是
总计划第26节仍停在只放行H5，与当前发布的R5-H/H6状态冲突；发布投影、manifest和测试均已通过。
返工只同步既有总计划顶部状态、第26节R5行及其进度叙述，不增加状态文件、Registry、动态校验或
构建期推导。第二轮复审见
`reviews/R5_H6_B_RELEASE_DOCUMENT_PROJECTION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，报告 SHA-256
为 `9b59e88f799eec2c93767924194c6a8df35265071dadab41f3ff4cf0cadb4bfc`，结论“通过，仅放行
H6-C”。H6-C 独立总审查通过前不得进入 H7。

## 10. H6-C 职责审计与总收口记录

审计机械覆盖当前全部12个至少1,000行的生产Python文件，并额外覆盖计划点名的989行曲线分析
文件。消费者同时按直接生产导入、插件注册/重导出、测试和历史文档分类；行数不是拆分理由。

| 文件（候选行数） | 当前责任与直接生产消费者 | 结论 |
| --- | --- | --- |
| `task_worker_files.py`（2,345） | Task受控工作区、文件写入/补丁、快照和验证状态；`tasks.py`与`task_outputs.py`直接消费 | 单一Worker文件生命周期；现有输出mixin共享其私有不变量，不再拆 |
| `scheduler_bindings.py`（1,842） | 实例、session、语义绑定/current、删除和变更观察的同一SQLite事务权威；7个直接生产消费者，runtime还经service重导出消费 | 删除三个零消费者方法；其余拆分会把同一current/绑定事务分成多个服务，不拆 |
| TCAD `project_packager.py`（1,848） | TCAD工程合同、确定性打包、review/runtime attestation；TCAD与InGaAs共12个直接生产消费者 | 删除一个零消费者JSON包装器；Schema和算法是未来内部候选，但当前共享同一执行合同，不拆 |
| `tasks.py`（1,841） | Task调度、claim/lease、活动、失败/重试、恢复和数据库权威；10个直接生产消费者 | 已把evidence、output、Worker文件拆成mixin；主文件保留单一Task事务，不再拆 |
| curve `schema.py`（1,667） | 曲线合同、交叉点和确定性一致性评价；curve与TCAD共11个直接生产消费者 | 删除一个零消费者兼容计数器；Schema/评价是未来内部候选，但当前无第二权威或必拆缺陷 |
| `approvals.py`（1,291） | 请求、精确subjects、访问、manifest、决定和审批SQLite事务；7个直接生产消费者 | 删除零消费者访问轮换入口；UI渲染已外提，保留单一审批权威，不拆 |
| TCAD `debug_service.py`（1,279） | 绑定单次Task attempt的有界开发调试、提交、收集和恢复；插件内3个直接生产消费者 | 有真实TCAD作者工具消费者且不冒充正式Execution；H7验证实际工具，不拆 |
| `mcp_root_operation_routes.py`（1,237） | 唯一catalog/preflight/invoke入口，组合Agent/Transform/Approval/Effect与共同准入 | 仅由Root facade组合；按executor拆会增加转接并分散同一调用权威，不拆 |
| TCAD `parameter_operations.py`（1,207） | 参数Agent、validator、Transform、审批projector和Operation声明的一个领域纵切面；由TCAD插件一次导入 | 领域内聚且未泄漏核心；按Operation拆只会增加组件胶水，不拆 |
| TCAD `transform_adapter.py`（1,152） | 七类执行外确定性TCAD变换；由注册adapter单点消费 | 无状态、同一变换协议；按profile拆会增加注册与转接，不拆 |
| `task_outputs.py`（1,027） | 编译输出校验、bundle、finalize和登记；由TaskService组合 | 单一输出提交边界，与Worker文件层方向明确，不拆 |
| approval UI `app.py`（1,022） | loopback HTTP、审批POST和受控维护页面；经包重导出供CLI启动 | render已外提；同一回环/Origin/维护锁边界，无第二UI权威，不拆 |
| curve `analysis.py`（989） | 有界残差定位、分析报告和确定性绘图；由curve科学Operation与Worker tool两个生产模块消费 | 报告与图共享同一确定性采样结果；无死入口或跨领域泄漏，不拆 |

审计最终发现六个高置信度死表面，并已直接删除实现与导出：

1. `package_deck_project_json`：无生产、插件、测试、文档或字符串注册消费者；保留的
   `package_reviewed_deck_json` 才是正式执行包装入口；
2. `curve_crossing_count`：源码明确标为compatibility helper，仓库内零消费者；正式证据接口
   `curve_crossings` 保留；
3. `SchedulerBindingService.instance_related_approval_ids`：零消费者旧别名；
4. `SchedulerBindingService.clear_session`：只有定义，没有清除 session 的当前合同或调用者；
5. `SchedulerBindingService.instance_invalidation_approval_ids`：被删别名只转调该方法，两者都无真实消费者；
6. `ApprovalService.rotate_access`：当前 UI、Root、测试和文档均无轮换入口合同或调用者。

这里有意放弃六个未文档化Python兼容表面，不增加alias、wrapper或迁移层。生产Python从
150文件/59,317行降到150文件/59,200行，净删117行；Operation包仍为7文件/2,064行，R0核心仍为
9,518行，Task职责仍为6,031行。其余13个审计对象均有真实生产消费者，没有对象满足“独立责任、
不同消费者、单向依赖、生产总行数不增”四项即时拆分条件，因此H6-C正确结果是零文件拆分。
删除风险只限仓库外代码直接导入这六个未文档化Python名字；wheel入口、Operation id、Schema字节、
数据库和持久对象均不变化。若在发布前发现真实外部消费者，回滚边界只是恢复相应定义与`__all__`
项，不需要数据迁移；不得用常驻alias预防一个尚未出现的消费者。

删除后TCAD/curve/plugin/clean-wheel聚焦 `43 passed in 53.63s`。第一次完整Operation回归为
`291 passed, 1 failed`；唯一失败是旧测试把生产总行数精确锁死为59,317，合法减法也会失败。该
断言已改成文件数和总行数不得超过H5上限，没有冻结新的精确数字；随后完整Operation回归
`292 passed in 110.77s`。这修正的是复杂度验收语义，不是为生产失败增加例外。

38项架构/部署组合首次执行因本轮诊断 `compileall` 留下一个可再生 `remote_runner_py36.pyc` 得到
37通过、1失败；部署测试正确拒绝源码树编译缓存。只删除该精确生成文件后，组合测试
`38 passed in 5.16s`。归档manifest的14个自有文件全部校验通过；干净发布含251个文件、250条
manifest记录，静态allowlist、manifest与实际非manifest文件集合相等，只投影三份当前计划和
H6-B第二轮通过报告，不含归档、workspace、用户资料或一次性入口；`git diff --check`通过。

H6-C首轮独立总审查报告为
`reviews/R5_H6_C_RESPONSIBILITY_AND_TOTAL_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`，SHA-256
`31050c9a7fbb0a929b8e191ba57946fb71421e9ac21099861f55d5585b599cc8`，结论“打回”。返工严格限于四项：
同步活动索引；将四条过时约束评估更新为当前事实；删除补充发现的三个零消费者方法；
删除与构建产物清单重复且已失效的根 `MANIFEST.sha256`，只保留构建器在清洁发布目录中
机械生成的唯一发布清单。返工没有新增 Registry、状态、入口校验、兼容别名或文件拆分。
返工后串行复测为：插件/干净安装聚焦 `40 passed in 48.79s`，完整 Operation
`292 passed in 97.11s`，约束/部署/平台 `38 passed in 5.37s`；归档清单 14/14 通过。
新建清洁发布仍为251个文件、250条清单，发布内 `sha256sum -c` 全通过，计划投影精确保持三份
当前计划与 H6-B 第二轮通过报告。
当前候选待独立复审，明确通过前不进入H7。
