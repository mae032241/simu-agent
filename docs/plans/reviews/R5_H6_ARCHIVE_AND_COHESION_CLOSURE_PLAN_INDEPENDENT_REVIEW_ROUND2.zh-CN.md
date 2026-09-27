# R5-H H6 归档与内聚收口方案第二轮独立复审

日期：2026-08-31
复审对象：`docs/plans/R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md` 当前第二轮候选
复审边界：只审查首轮 B1—B4 的方案闭环；不实施 H6，不放行 H6-B 或 H7

## 1. 结论

**通过。**

首轮四项阻断已经以最小方案修订关闭：错误的归档 `PYTHONPATH` 复跑承诺已删除；恢复方式改为
只在临时派生树按原路径还原并核对哈希，活动 pytest harness 同时明确脱钩 `r5_e2e`；发布文档改为
实施时重算数量和静态最小 allowlist；R5-H 主计划 H6/H7 已同步相同的生产净减口径；大文件审计
全集已覆盖当前全部至少 1,000 行的生产 Python 文件和额外点名的 curve `analysis.py`。源目标完整性、
外部 fixture 身份、用户数据保护、资源上限和逐阶段独立门也已成为明确验收条件。

本结论**只放行 H6-A**。H6-B 必须等待 H6-A 实施及其独立审查通过；H7 仍未放行。本轮通过不是
对尚未发生的归档移动、发布 allowlist 改造或 H6-C 最终审计的实现验收。

## 2. 复审对象与证据边界

本轮完整核对了：

- H6 第二轮候选和首轮独立方案审查；
- `R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 的 H6、H7、状态记录和消费者冻结；
- 当前 `scripts/build_git_release.py` 与 `tests/operations/conftest.py`；
- 七个 `scripts/r5_g_*.py`、四个 runner 和完整的 `test_r5_frozen_baselines.py`；
- 当前 `src/scidiscovery + plugins` 全部至少 1,000 行的 Python 文件、额外点名的 curve
  `analysis.py`、它们的生产/插件/测试消费者；
- fixture manifest、当前 release builder 测试和相关 catalog、Effect、Approval、Execution、
  InGaAs 回归入口。

复审读取时的候选 SHA-256 为
`39bb3a0394ca5c15603c2fe50fb57f70661ba7cc2747602f01e677d198972142`；首轮报告当前字节的 SHA-256
为 `5a056b624239f3aabde437a516441b8ea15f6cf1a3d5fba969c83f2938ff8c98`，与候选引用一致。
工作树已有大量未提交的 R1—R5 成果；本轮不把 Git 历史或首轮摘要当作当前候选证据，也没有修改
方案、生产代码、测试、fixture、workspace、deliverables 或用户状态。

## 3. 首轮阻断闭环

### B1：临时原路径恢复闭包已替代错误的 `PYTHONPATH` 承诺

**通过。** 候选第 2 节现在明确写明：

1. 不承诺把归档目录加入 `PYTHONPATH` 后直接运行；
2. 只在新建临时目录恢复冻结源码/源发布闭包，再把脚本、测试和冻结 conftest 放回原始
   `scripts/`、`tests/operations/` 相对路径；
3. 逐项哈希核对后才运行，结束后删除临时派生树；
4. 活动仓库不得新增 wrapper、alias、symlink、兼容入口、Operation 或 catalog 项；
5. 缺少私有 run state 时明确不可复跑，不得补造状态。

这与真实代码的路径语义一致：`r5_g_replay_live.py` 和 `r5_g_science_chain.py` 都用
`Path(__file__).resolve().parents[1]` 取得仓库根，冻结 baseline 测试用 `parents[2]`，pytest 又依赖
原 `tests/operations/conftest.py` 的 `installed_probe`。按原路径覆盖恢复会同时恢复这些父链和
conftest 发现规则；只改 `PYTHONPATH` 不会。冻结 conftest、源码/源发布闭包、外部 fixture manifest
身份和 H6-0 的精确路径哈希表共同构成取证恢复前提。H6-A 仍须实际做一次临时恢复，因而方案没有
把尚未运行的复跑写成既成事实。

活动 conftest 的脱钩范围完整。当前一次性安装成本只有三处：构建
`tests/fixtures/plugins/r5_e2e_tcad_plugin` wheel、解析该 wheel、建立名为 `r5_e2e` 的环境。当前
`tests/operations` 中只有将归档的 `test_r5_frozen_baselines.py` 后四项消费该环境；四个 runner
不通过 `installed_probe` 消费它。候选要求同时删除上述 wheel 源和环境，且保留前三项所需的
`core`、`full`、`ingaas`，不会误删当前 clean-wheel/参数链覆盖。

临时派生树不是第二产品入口：归档明确不进入 wheel、服务、Operation catalog 或源发布包，活动树
不留可调用别名，README 只能描述有外部前置闭包和私有状态时的一次性取证恢复。

### B2：发布 allowlist 与数量口径已闭合

**通过。** 候选不再把历史快照误写成 284 个文件目标，而是要求实施当刻机械重算顶层、reviews
和递归总数。第二轮报告落盘前本轮观测为顶层 37、reviews 125、递归 162；本报告自身又会使后两项
各增加 1，正说明固定文档数量不能成为实施验收真相。

发布投影现在有单一、可机械展开的静态集合：

- 既有 `DOCUMENTS` 保留中英文 `docs/ARCHITECTURE*`、安装、发布、协议和资格资料；
- 新增显式保留中文设计宪章和 `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 33 项当前约束；仓库当前
  不存在另一份英文设计宪章，因而没有遗漏同名双语文件；
- `ROOT_FILES` 继续保留根 README、NOTICE、SECURITY、CONTRIBUTING；插件 README 随显式插件树
  保留；
- 当前计划最小集合明确为总计划、R5-H 实施记录、H6 当前方案和当时唯一有效的 H6 通过门报告；
- 带大量未发布历史链接的本地 `docs/plans/README.md` 和历史 plans/reviews 全集不进入精简发布包。

候选还要求发布 manifest 的实际路径集合等于 allowlist 展开结果，并对架构双语、宪章、33 项 YAML、
安装/发布、插件、法律/安全、当前计划做正向断言，对归档、一次性脚本/runner、历史全集、workspace、
deliverables 和私有状态做负向断言。首轮指出的旧
`TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md` 必须存在断言也已明确要求更新。该设计只是构建期
tuple，不是文档 Registry、版本判断、运行入口或第二状态权威。

### B3：H6/H7 的生产净减口径已经一致

**通过。** R5-H 主计划 H6 完成门和 H7 最终审查现在都采用同一个条件：

- 经消费者审计发现死生产表面时才要求净删除；
- 没有死生产表面时生产代码不得增加；
- 无论哪种情况，D4-H2 特例不得增加，默认测试/仓库入口和发布体积必须净减少。

H6 候选采用相同措辞，并额外禁止用转接层抵消删除。因此不再存在“子计划把主计划的生产净减少
解释成零变化”的双重验收真相，也不会为了制造负行数删除有真实消费者的代码。

### B4：大文件审计全集和逐项预判完整

**通过。** 以当前 `src/scidiscovery + plugins` Python 文件机械重算，至少 1,000 行的对象正好是
下列 12 个；候选全部覆盖，并另含计划点名的 989 行 curve `analysis.py`：

| 对象 | 当前行数 | 第二轮判断 |
| --- | ---: | --- |
| `task_worker_files.py` | 2345 | 一个受控 Worker 文件/快照/校验/finalize 生命周期；不拆 |
| `scheduler_bindings.py` | 1892 | 共享一个 SQLite 实例、session、语义绑定/current 事务权威；未来候选，当前不拆 |
| TCAD `project_packager.py` | 1869 | 多模型和算法被插件/adapter/materializer 消费；未来可内部分层，当前无必拆缺陷 |
| `tasks.py` | 1841 | Task 状态事务、派发、claim、lease、活动和恢复主服务；现有 mixin 边界清楚 |
| curve `schema.py` | 1680 | 曲线合同与确定性求值被 curve/TCAD 多方消费；未来候选，当前无第二权威或死表面 |
| `approvals.py` | 1324 | 审批请求、精确 subject、决定和访问事务权威；不拆 |
| TCAD `debug_service.py` | 1279 | 有界开发调试的准备、提交、回收和恢复闭包；有真实领域消费者 |
| `mcp_root_operation_routes.py` | 1237 | 唯一 catalog/preflight/invoke 入口；按 executor 再拆会增加转接 |
| TCAD `parameter_operations.py` | 1207 | 参数 Agent/validator/transform/approval 的一次插件注册闭包；不迁入核心 |
| TCAD `transform_adapter.py` | 1152 | 多个已注册确定性 TCAD transform 的领域 adapter；有真实消费者 |
| `task_outputs.py` | 1027 | TaskService 的 compiled-output 校验、bundle 和 finalize mixin；不拆 |
| approval UI `app.py` | 1022 | 唯一 loopback UI 请求处理和维护入口；渲染已有外提，不增第二 UI 权威 |
| curve `analysis.py` | 989 | 曲线分析、分段和绘图由科学 Operation/Worker tool 消费；额外点名审计，不拆 |

阈值只定义审计全集，不是拆分理由。当前消费者扫描没有发现必须现在拆分的反向依赖、第二权威、
独立发布边界或零消费者生产对象；也没有一个对象满足候选规定的全部四项拆分条件。因此当前正确
预判是“零生产拆分”。`scheduler_bindings.py`、`project_packager.py`、curve `schema.py` 和 Root
operation routes 可保留为未来内部内聚候选，但未来可能性不能成为 H6 增加 facade、服务或胶水的
理由。H4 保留的独立 Worker 进程基座也明确不在 H6 删除或接线。

## 4. 文件安全、外部证据和阶段门

**通过。** 候选的机械边界足以约束 H6 实施：

- H6-0 先冻结七脚本、五测试、operations conftest 的“原路径 → SHA-256 → 归档路径”精确表；
- 每个源拒绝 symlink，每个目标拒绝既有冲突；不使用无界 glob；复制/移动后先比较源目标字节和
  SHA-256，再删除源；
- 归档 manifest 只拥有归档内字节；外部 fixture 只记录其 manifest 身份，不复制、不改写哈希，
  不接管 workspace、deliverables、`123/`、run-root 或用户状态；
- 所有 H6 pytest 均在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2` 下串行运行；7 GiB 限制与
  一次性真实 Agent 脚本自身的地址空间检查一致；
- H6-0 方案门、H6-A 归档门、H6-B 发布门、H6-C 总收口门彼此独立；前一阶段独立审查未通过时
  不得进入后一阶段。

这些要求不需要 ArchiveService、迁移表、文档注册表、入口校验、兼容层或运行时开关。

## 5. 三项保留、四项归档及替代覆盖

**通过。** `test_r5_frozen_baselines.py` 的划分仍可实施：

1. 结构生成器/R0 聚合/领域 token 约束保留在默认回归；
2. core/full/InGaAs clean-wheel catalog 数量、scope 和摘要变化保留；
3. clean-wheel TCAD 参数链进入 author/review 保留；
4. Fig.4 fixture 字节身份移入归档，由归档 manifest 与外部 fixture manifest 身份继续证明；
5. `r5_e2e` 专用 catalog 端口测试移入归档，当前 catalog/安装入口由
   `test_catalog_installed_entrypoint.py`、`test_runtime_plugin_configuration.py` 和领域插件测试覆盖；
6. Fig.4 专用历史 replay 生命周期移入归档，产品的 Effect、UI、Execution 精确授权和 InGaAs
   变换分别由 baseline Effect、审批 UI、execution approval identity 和 InGaAs 当前测试覆盖；
7. 一次性比较 rubric 留作冻结科学审计证据，不作为当前产品回归；通用产品边界由上述当前测试
   直接验证。

候选没有把这张映射冒充已经完成的实施证据，而是要求 H6-A 在实施记录中冻结精确替代测试名并
实际运行。四个 runner 中的 ABI8 migration、旧报告 identity、prompt 和停止门断言随一次性脚本
归档，不被泛化为产品工作流。

## 6. 复杂度与架构总判定

修订后的 H6 仍是有界减法：机械封存七脚本/五测试/harness，默认 conftest 删除一个 wheel 和一个
环境，随后只收窄一个静态发布清单和本地活动索引，最后做消费者审计。方案不修改 OperationSpec、
目录编译、Task/Artifact/Approval/Execution 生命周期、数据库 Schema、正式派发或科学算法。

没有新增归档服务、注册表、兼容层、入口校验、路由、状态或第二产品入口；没有用强拆内聚文件来
制造表面行数下降。若 H6-C 没发现死生产表面，生产代码零变化就是符合主计划的结果，默认入口、
回归和发布面仍必须实质净减。

## 7. 本轮验证

所有 pytest 均为 7 GiB 地址空间上限、`MALLOC_ARENA_MAX=2`、串行：

- 七脚本对应四个 runner 加完整冻结 baseline 文件：`28 passed in 45.70s`；
- 33 项约束结构、Task/Root/Worker 职责边界和 clean release 聚焦：`14 passed in 4.93s`；
- 当前生产 Python 机械统计：150 个文件、59,317 行；至少 1,000 行对象 12 个，另审计 989 行
  curve `analysis.py`；
- 首轮报告 SHA-256 复核与候选引用相同；H6/H7 净减措辞、错误 `PYTHONPATH` 负承诺、资源限制、
  symlink/冲突/glob 和用户数据边界均作了静态复核。

未运行全量默认回归，也未执行归档移动或临时恢复；这些属于 H6-A 实施验收，不能由方案绿测代替。

## 8. 放行边界

H6-A 可以开始，但实施必须逐项兑现精确路径表、哈希后删除、活动 conftest 脱钩、前三项测试迁留、
后四项替代覆盖表和一次临时原路径恢复。H6-A 独立实现审查通过之前，不得进入 H6-B；H6-B/H6-C
各自的发布投影和总收口门也不得提前继承本报告结论。H7 仍未放行。
