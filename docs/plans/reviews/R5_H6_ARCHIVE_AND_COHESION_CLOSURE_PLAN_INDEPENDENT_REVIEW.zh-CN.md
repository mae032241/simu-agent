# R5-H H6 归档与内聚收口方案独立审查

日期：2026-08-31  
审查对象：`docs/plans/R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md` 当前工作树候选  
审查边界：仅审查 H6 方案，不实施 H6-A，不放行 H7

## 1. 结论

**打回。**

七个 `r5_g_*.py` 确实没有产品消费者，五个相关测试文件的“三项保留、后四项归档”总体分类也
正确；保留 fixture、workspace、deliverables 和用户状态而不自动移动或清理同样正确。方案不能
通过的原因不是这些方向错误，而是四个可达的实施缺口：归档后声明的 `PYTHONPATH` 复跑实际不可
成立；发布文档集合遗漏当前规范性来源且文件数量基线错误；子计划对“生产代码净减少”的解释与
状态权威原文冲突；大文件审计没有覆盖当前完整候选集合，也没有逐项冻结消费者依据。

以上问题修订前不得执行 H6-A；本审查不放行 H7。

## 2. 审查范围与证据边界

本轮交叉核对了：

- H6 候选、`R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 的 H6/H7、计划索引；
- `scripts/build_git_release.py` 的根文件、源码树、文档和工具复制集合；
- 七个 `scripts/r5_g_*.py`、四个 runner、`test_r5_frozen_baselines.py`、
  `tests/operations/conftest.py`；
- `tests/fixtures/r5_e2e_tcad/manifest.json` 与对应测试插件的真实消费者；
- 当前生产 Python 文件规模、被方案点名及遗漏的大文件、生产导入和测试消费者；
- 当前架构入口、设计宪章、33 项约束 YAML 及发布构建测试。

工作树在审查开始前已有大量未提交 R1—R5 修改。本报告以当前文件字节为候选，不把历史提交或
旧审查结论当成当前通过证据，也未修改方案、生产代码、测试或用户资料。

只读聚焦重放均在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、串行模式下执行：

- 五个相关测试文件：`28 passed in 46.60s`；
- 33 项约束结构、Task/Root/Worker 职责边界及 clean release 构建：
  `14 passed in 4.84s`。

未运行全量测试；方案审查不以当前绿测替代对移动后路径和发布闭包的检查。

## 3. 阻断项

### B1：归档后的 `PYTHONPATH` 复跑不是可执行闭包

**缺陷与可达场景**

`r5_g_science_chain.py:35-36` 和 `r5_g_replay_live.py:39-40` 都用
`Path(__file__).resolve().parents[1]` 计算 `REPOSITORY`，再从该根读取
`tests/fixtures/r5_e2e_tcad/manifest.json` 和测试插件。按方案移动到
`archive/r5-g-evaluation/scripts/` 后，即使把归档根加入 `PYTHONPATH`，`REPOSITORY` 也会变成
`archive/r5-g-evaluation`，而 fixture 明确不在该树内，因此脚本会在启动阶段读错路径。

`test_r5_frozen_baselines.py:9` 同样用 `parents[2]` 推导仓库根。归档后的测试不再位于当前
`tests/operations/` 父链下，还不会自动加载 `tests/operations/conftest.py`，因此既得到错误根，也
缺少 `installed_probe`。`scripts` namespace 仅靠 `PYTHONPATH` 可以导入，不代表数据根、pytest
harness 和安装态环境仍成立。

此外，当前 `tests/operations/conftest.py:50-144` 每次建立共享安装环境时都会构建
`r5_e2e_tcad_plugin` wheel 并创建 `r5_e2e` venv。若只删四个 runner 和冻结测试后四项而不修改
该 conftest，默认回归仍承担无人消费的一次性 Fig.4 环境成本，H6-A 并未真正移除该默认表面。

**影响**

归档 README 会给出不可工作的命令；为了让它工作，实施者很可能恢复原脚本、加兼容 import、
仓库内 symlink 或 wrapper，从而把归档变成第二产品入口。与此同时，默认测试仍构建一次性插件。

**最小修订**

1. 删除“把归档目录加入 `PYTHONPATH` 即可复跑”的承诺。归档只允许一种恢复方式：在新建临时目录
   中先恢复冻结的源发布/源码闭包，再把归档脚本和测试按原始 `scripts/`、`tests/operations/`
   相对路径放回临时树；逐项核对哈希后运行，结束后删除该临时派生树。不得在活动仓库恢复入口，
   不得增加 wrapper、import alias、symlink、Operation、catalog 项或兼容层。
2. 把当前 `tests/operations/conftest.py` 的精确冻结副本作为历史测试 harness 纳入归档 manifest；
   活动 conftest 删除 `r5_e2e_tcad_plugin` wheel 源和 `r5_e2e` environment。fixture/plugin 字节仍留
   原处作为冻结证据，不再被默认 session fixture 构建。
3. README 必须把复跑标为“有前置私有状态和冻结源码闭包时的取证恢复”，不是受支持产品能力、
   新科学运行或资格证据。缺少私有 run state 时应明确不可复跑，而不是补造状态。
4. H6-0 对七脚本、五测试和上述 conftest 建立“原路径 → SHA-256 → 归档路径”冻结表；H6-A 只对
   该精确路径表机械移动，先比较目标字节，再删除源路径。归档 manifest 记录新 README、冻结
   harness 和全部移动文件；fixture manifest 的摘要作为外部依赖引用，不复制或改写用户数据。

这仍是一次性离线恢复说明，不是第二入口。

### B2：发布 allowlist 尚未闭合当前架构真相，且文档数量基线错误

**缺陷与证据**

当前 `docs/plans` 顶层有 37 个文件，`docs/plans/reviews` 有 124 个文件，递归合计 161 个；方案所称
“160 个计划文件和 124 个历史审查报告”以及“不移动 284 个文件”把 reviews 重复计数。H6 文件
加入前的历史快照可以是 160 个总文件，但不能据此宣称当前有 284 个文件。

`build_git_release.py` 当前通过 `SOURCE_TREES` 递归复制 `docs/plans`；根目录的 README、NOTICE、
SECURITY、CONTRIBUTING，通过 `ROOT_FILES` 独立保留；架构、安装、发布、协议文档通过
`DOCUMENTS` 独立保留；插件 README 随各插件树保留。因此把 `docs/plans` 改成机械 allowlist 本身
不会删除法律、安全、安装或插件说明。

但当前 `docs/ARCHITECTURE.zh-CN.md:6-9` 直接把
`docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md` 和
`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 声明为设计宪章与 33 项当前行为约束；现有
发布脚本并未复制 `docs/architecture/`。H6 只写“当前架构仍存在”不能关闭这个已存在的发布断链。
若把本地 `docs/plans/README.md` 的完整历史索引也放入精简发布包，还会产生大量指向未发布历史
文件的链接。

**最小修订**

1. 把 H6-0 基线改成当前递归总数及顶层/reviews 分解，并在实施当刻重算，不保留 284 的错误目标。
2. 在发布脚本的现有静态 tuple 中显式加入设计宪章和 33 项 YAML；这只是机械文件 allowlist，
   不是文档注册表。
3. 当前发布的最小计划/审查集合应明确为：
   - `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`（状态与总目标权威）；
   - `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md`（当前 H 阶段实施记录）；
   - `R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md`（当前 H6 方案）；
   - H6-B 当时已通过的唯一当前独立门报告；H6 最终实施审查生成后，以最终报告作为当前门证据。

   H5 已完成计划和逐轮报告属于历史 audit，不是当前发布最小集合。若产品决定仍要发布 H5，则
   必须把 H5 文件实际引用的完整审查闭包一起列出，不能只写含混的“H5 最终报告”。
4. 本地 `docs/plans/README.md` 可以继续作为完整历史入口；若其历史链接指向不发布文件，就不要把
   该索引复制进精简发布包。发布包由 `ARCHITECTURE*` 直接链接上述当前权威，不生成第二版索引。
5. 更新现有 release builder 测试：正向冻结架构双语文档、设计宪章、33 项 YAML、安装/发布、
   插件 README、NOTICE/SECURITY 及上述当前计划；负向冻结 `archive/`、`r5_g_*`、runner、历史
   plans/reviews、workspace、deliverables 和私有状态均不存在。现有对
   `TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md` 必须存在的旧断言应按新集合更新。

### B3：零生产代码变化的奥卡姆判断合理，但不能由子计划重解释状态权威

H6 候选提出“已证实没有死生产消费者时，运行代码零变化优于无理由删除”，这个工程判断合理，
也符合不得按行数强拆的奥卡姆目标。当前七脚本属于仓库辅助脚本，不在 `src/ + plugins/` 的
59,317 行生产口径内，归档它们不会让该生产口径下降。

然而主计划 H6 完成门仍写“全仓生产代码和默认发布体积有可解释的净下降”，H7 最终门仍写
“生产代码净减少”。H6 子计划把它解释成零变化，会留下两个同时声称当前的验收真相。独立审查
不能靠解释覆盖状态权威。

**最小修订**：在执行 H6-A 前，对 `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 的 H6/H7 两处
做同一项窄修订：只有发现经消费者审计证实的死生产表面才要求净删除；否则生产代码不得增加，
默认测试/仓库入口/发布体积必须净减少。H6 候选保留相同措辞。不得为了制造净负数删除活代码，
也不得新增转接层抵消删除。该权威同步是修正文档冲突，不是扩大 H6 实施范围。

### B4：大文件审计范围不完整，现有“不拆”标签缺少逐项消费者依据

当前最大生产文件不仅是候选列出的若干文件。以当前 `src/scidiscovery + plugins` Python 字节重算，
至少 1,000 行的对象还包括候选未讨论的 `tasks.py`（1,841）、`debug_service.py`（1,279）、
TCAD `transform_adapter.py`（1,152）和 `task_outputs.py`（1,027）。候选把“单一数据库权威”或
“领域内聚”直接当成不拆结论，也没有列出不同生产消费者，尚不足以满足其自己定义的四条件。

本轮消费者核对得到以下结论：

| 对象 | 当前消费者与职责证据 | 本轮判断 |
| --- | --- | --- |
| `task_worker_files.py`（2,345） | 由 `tasks.py` 组合为唯一 TaskService；patch、上传、快照、校验、finalize 都在同一 Worker 文件生命周期，纯 helper 无外部生产消费者 | 不因行数拆；没有死表面 |
| `scheduler_bindings.py`（1,892） | runtime、Root instance routes、UI、instance/orphan admin、portable bundle 分别消费实例、session、语义绑定和清理；共享同一 SQLite 事务权威 | 是最强的后续内聚候选之一，但当前没有必须拆的缺陷 |
| `project_packager.py`（1,869） | TCAD plugin、execution/command/debug adapter、workspace、materializer、transform 和 InGaAs plugin 消费不同模型/算法 | 消费者确实不同；可未来内部分层，但无死代码或第二权威证据 |
| `tasks.py`（1,841） | TaskService 持有状态事务和任务生命周期；三个无状态 mixin 由现有结构测试约束 | 方案遗漏；当前不拆 |
| curve `schema.py`（1,680） | curve objective/plotter/worker/transform/analysis/science operations 及 TCAD curve 适配消费；同时含合同与求值算法 | 可审计的未来拆分候选，当前无必须拆证据 |
| `approvals.py`（1,324） | runtime、execution、UI、Root 和管理服务共同依赖同一审批事务、精确 subject 与决定验证 | 不拆事务权威 |
| `debug_service.py`（1,279） | TCAD runtime plugin、debug adapter 和 plugin tool 共用受限开发调试生命周期 | 方案遗漏；当前不删不拆 |
| `mcp_root_operation_routes.py`（1,237） | 只由 Root facade 组合，内部按 executor 实现统一 catalog/preflight/invoke | 可未来提取内部 executor helper；当前不新增 facade |
| `parameter_operations.py`（1,207） | TCAD plugin 一次登记 Agent、validator、transform、projector 和 Operation 闭包 | 领域闭包有真实消费者；当前不拆 |
| TCAD `transform_adapter.py`（1,152） | 由 `operation_transforms.py` 注册的多个确定性 TCAD 变换消费 | 方案遗漏；当前不拆 |
| `task_outputs.py`（1,027） | 只作为 TaskService 的 compiled-output mixin 使用 | 方案遗漏；当前不拆 |
| approval UI `app.py`（1,022） | CLI 创建唯一 loopback UI；处理审批和已存在的维护页面，渲染已部分外提 | 不因行数拆；保持单一 UI 权威 |
| curve `analysis.py`（989） | curve science Operation 与 Worker tool 消费分析和绘图 | 低于上述边界但被方案点名；当前不拆 |

因此本轮没有发现一个“现在必须拆”或“现在必须删”的生产对象。最小修订不是实施拆分，而是在
H6-C 中按一个明确的审计集合（例如当前全部至少 1,000 行对象，再加计划点名对象）逐项记录职责、
生产/插件/测试消费者、共享不变量和拒绝拆分的理由；阈值只定义审计全集，不能成为拆分理由。

## 4. 其余对抗性判断

### 4.1 七脚本和四 runner 的产品消费者结论

七脚本合计 3,743 行，内部互相 import，并固定 `r5_e2e` manifest、实例名、ABI8 state generation、
run-root 报告摘要和 D4-H2 停止门。仓库检索未发现 console entry point、服务启动、OperationSpec、
catalog、部署或发布工具消费者；生产树也没有 import。直接消费者只有四个 runner、冻结测试、
R5-G/H 历史文档及脚本彼此。因此它们是一次性评估编排，不是当前运行产品能力。

移动不会破坏受支持产品路径；会破坏当前就地历史复跑路径，必须先按 B1 建立只在临时树恢复的
取证方式。已触发 `blocked` 停止门的私有状态不得因“保留能力”而变成继续科学链的理由。

### 4.2 `test_r5_frozen_baselines.py` 的三/四划分

前三项应保留在默认回归：

1. 当前结构生成器、R0 聚合和领域 token 约束；
2. core/full/InGaAs clean-wheel 的 catalog 数量、scope 和摘要变化；
3. clean-wheel 参数链进入 TCAD author/review。

后四项均绑定 `r5-e2e-fig4-baseline-recovery-v1` 的 manifest、专用 plugin、历史 replay、量表和工作区
字节，适合归档。第五、六项虽然顺带覆盖当前 catalog 端口和 Effect/UI/Execution 生命周期，但
这些产品不变量已有 `test_catalog_installed_entrypoint.py`、`test_baseline_effect_lifecycle.py`、
`test_r4_execution_approval_identity.py`、`test_runtime_plugin_configuration.py`、
`test_ingaas_operation_plugin.py` 等当前测试直接覆盖。H6-A 应把这张替代覆盖映射写进实施记录并运行
这些测试，不能用“后四项都是 Fig.4”一句话代替。四个 runner 中的 ABI8 migration、旧 report
identity、prompt 和停止门断言随其一次性脚本一起归档是正确的。

### 4.3 fixture、workspace、deliverables 与历史文档

- `tests/fixtures/r5_e2e_tcad/` 和其 plugin 由 manifest 固定哈希，是历史输入/adapter 闭包；不移动
  可避免改写路径和科学字节。正确处置是从默认 conftest 脱钩，而非删除或改 hash。
- workspace、deliverables、`123/`、运行状态和用户数据不得由 H6 自动移动或清理；计划对此边界
  正确。归档 manifest 只记录引用的外部 manifest 摘要，不能递归接管用户资料。
- 不物理移动 161 个计划语料、只收窄本地“当前”索引和发布投影，足以把历史移出活动阅读路径，
  也避免大规模链接灾难；必须先修正 B2 的数量和发布索引边界。

### 4.4 阶段门、资源和机械完整性

H6-0 → H6-A → H6-B → H6-C 的独立审查顺序是合理的，且没有新增运行状态。为闭合实施，修订后还
必须把以下机械门写成明确验收，而不是留给实现者推断：

- 所有 H6 pytest 命令先设 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2` 并串行运行；主计划只给
  H7 “不超过 8 GiB”不足以约束 H6 移动和 release 验证；
- 源/目标逐文件 SHA-256 相等后才删除原路径，拒绝 glob 外文件、symlink 和已存在的冲突目标；
- 归档 manifest 只覆盖归档字节，外部 fixture 只记录其 manifest 身份；
- release manifest 的实际路径集合必须等于 allowlist 展开结果，并核对正/负集合；
- `archive/`、workspace、deliverables、`123/` 和任意 run-root 不得成为 `--force` 或清理目标。

这些是有界文件操作和测试门，不需要 ArchiveService、迁移状态或文档注册表。

## 5. 架构与复杂度总判定

修订后的 H6 仍符合 33 项约束、OperationSpec 中心、一个插件入口一次启动编译、一个 catalog、一个
current 和轻控制面目标。归档及静态发布 allowlist 不应进入运行时；不得新增入口校验、状态、表、
注册表、路由、兼容层或第二派发路径。

方案方向足够小：精确归档一次性脚本/测试，脱钩一次性 pytest 环境，收窄一个发布 allowlist 和
一个本地索引，最后只做消费者审计。最小返修就是关闭 B1—B4 及其机械验收，不需要新框架，也不
需要为满足行数目标拆分任何当前生产文件。

## 6. 文档所有权图

| 文档 | 角色 | H6 处置 |
| --- | --- | --- |
| `docs/ARCHITECTURE*.md`、设计宪章、33 项 YAML | 当前规范性架构 | 本地与发布均保留 |
| `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` | 唯一总状态/目标权威 | 发布保留；B3 窄同步 |
| `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` | 当前 H 阶段实施记录 | 发布保留；B3 窄同步 |
| H6 候选 | 当前 active proposal | 返修复审通过后发布保留 |
| H6 当前独立门报告 | 当前 audit ledger | 只保留实际有效的通过门；本次打回报告留本地历史 |
| H5 及更早计划/审查 | 历史实施与 audit | 本地保留，移出当前发布最小集合 |
| `docs/plans/README.md` | 本地活动/历史入口 | 收窄“当前”分类；有未发布历史链接时不进入精简发布 |
| clean release + `MANIFEST.sha256` | 机械生成投影 | 由现有 builder 生成，不成为架构权威 |

返修完成后应重新进行独立方案审查；只有新的审查结论为“通过”时，才可放行 H6-A。
