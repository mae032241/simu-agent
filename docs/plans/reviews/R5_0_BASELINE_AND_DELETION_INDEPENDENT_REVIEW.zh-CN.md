# R5-0 权威语料、基线与删除清单独立审查

日期：2026-08-29  
审查对象：当前共享工作树的 R5-0 候选  
审查性质：未参与实现的跨边界、复杂度、防搬移、科学夹具和决策语料审查  
最终结论：**打回**

## 1. 结论摘要

R5-0 没有修改 R4 冻结的生产表面，结构数值、三种安装组合、13 个 Fig.4 文件摘要以及
`3/124/248` 项测试声明均可复核；私有运行根与脱敏交付根也没有被混成同一个目录。阶段方向没有
偏离 33 项约束或“灵活、低成本、可插件扩展的通用 AI 科学家”目标，也没有新增注册表、状态机
或科学语义实体。

但是，本阶段自己的完成门还没有成立：

1. 中英文当前架构有两处把 R4 的可选/多入口事实写成了绝对事实；
2. 删除清单没有按其承诺冻结测试、文档和全部符号消费者，第一复杂度口径也不能自动追踪职责
   搬移；
3. R5-G 只冻结了文件字节和宽泛的 Operation 家族，没有冻结可执行调用集合、输入映射、预算、
   skip 规则、replay adapter 身份及可独立复算 scorer 所需对象；
4. 编译目录摘要虽然本轮独立复算为真，但 R5 专项测试没有从 clean-wheel 对快照执行该比较，结构
   快照中的大部分字段同样没有被专项测试核对。

这些都可以只修改 R5-0 文档、脚本、快照和测试夹具完成，不需要提前进入 R5-A1，更不能用生产
代码改动绕过冻结门。本报告不放行 R5-A1。

## 2. 审查证据

| 证据键 | 唯一来源 |
| --- | --- |
| S1 | `docs/ARCHITECTURE.zh-CN.md`、`docs/ARCHITECTURE.md` |
| S2 | `pyproject.toml` 与 Artifact/Task/Approval/Execution 当前 Schema |
| S3 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 4 节 |
| S4 | `docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md` |
| S5 | `scripts/r5_baseline_metrics.py`、`tests/fixtures/r5_structure_baseline.json`、`tests/operations/test_r5_frozen_baselines.py` |
| S6 | `tests/fixtures/r5_e2e_tcad/manifest.json`、`rubric.json`、`task.zh-CN.md` 及其 13 个冻结文件 |
| S7 | `workspace/ingaas_inalas_photodetector/research/active_bundles/fig4_baseline_provenance_20260806.bundle` 与历史 scorer manifest |
| S8 | 根 `MANIFEST.sha256`、R5 三轮方案审查和本轮受限串行测试输出 |

### 2.1 紧凑核对表

| 问题 | 结果 | 证据 |
| --- | --- | --- |
| 双语是否语义对应 | 通过 | S1 |
| 双语是否只陈述当前真实事实 | 不通过 | S1、S2 |
| R5 生产行为是否保持 R4 候选 | 通过 | S8 |
| 删除清单是否覆盖生产/动态入口 | 基本通过 | S4、S5 |
| 删除清单是否覆盖每个测试/文档消费者 | 不通过 | S4、S5 |
| 三重结构数值是否真实 | 通过 | S5 |
| 三重口径是否防职责搬移且由测试冻结 | 不通过 | S3、S5 |
| core/full/full+InGaAs 数量和摘要是否真实 | 通过 | S5、S8 |
| 三组合摘要是否由 R5 专项 clean-wheel 门核对 | 不通过 | S5 |
| 13 个科学文件是否存在且 hash/size 正确 | 通过 | S6、S7 |
| Fig.4 任务是否已冻结成可执行 E2E 合同 | 不通过 | S3、S6、S7 |
| 私有状态与脱敏交付是否分离 | 通过；发布负例属于 R5-G/R5-F 后续门 | S3、S4、S6 |
| 3/124/248 测试声明是否可复核 | 通过 | S8 |
| 是否削弱承重边界或引入过度设计 | 未发现 | S1、S3、S4 |

## 3. 按严重性排序的发现

### F1（高）：当前架构文档仍有两处不符合 R4 实现事实

位置：

- `docs/ARCHITECTURE.zh-CN.md:21` / `docs/ARCHITECTURE.md:26`；
- `docs/ARCHITECTURE.zh-CN.md:91` / `docs/ARCHITECTURE.md:113`。

第一处称“一个安装包发布一个 `PluginDefinition`”，但根 `pyproject.toml:26-28` 在同一个发行包中
发布 `builtin` 和 `general_science` 两个 `scidiscovery.plugins` 入口。当前成立的事实是“只有一个
entry-point group；每个入口返回一个 PluginDefinition；同一发行包当前可以发布多个插件定义”。

第二处称 Task、Artifact、Approval、Execution 记录都带 operation id/version/digest。实际
`AgentTask.operation_authority`、`ApprovalRequest.compiled_identity` 和
`ExecutionRequest.compiled_identity` 均为可选，普通 Artifact 也只有已迁移 Operation 产物才写入
相应标签；两个 legacy bridge 和旧创建面仍然存在。该句必须限定为“由已迁移 Operation 创建的
记录/产物”。

影响：R5-0 的首要职责是建立当前真相。若保留绝对表述，A2 删除入口和 R5-B 生产者族审查会拿
目标状态误判当前状态。

最小修复：只同步修改上述中英文两句，不改变 PluginDefinition ABI、打包结构或生产 Schema。

### F2（高）：删除清单和第一复杂度口径没有达到自身承诺的可机械冻结程度

位置：

- `R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md:14-18,50-117`；
- `scripts/r5_baseline_metrics.py:14-27,80-109,111-153`；
- `tests/operations/test_r5_frozen_baselines.py:13-36`。

基线脚本的旧符号扫描只覆盖 production Python、`deploy/`、`roles/` 和 pyproject，明确没有扫描
`tests/` 与 `docs/`。清单中的“baseline/role/platform tests”“旧直接审批测试”等是类别描述，
不是每个符号的精确消费者。例如 `load_roles` 还被四个测试文件消费，`task_schedule`、
`artifact_transform`、两个直接创建工具分别被多组历史/当前测试和文档消费，但快照只保存总数，
没有保存分类后的文件集合或位置。设备参数纵切面、readiness/context 和 Root 生产者族也只列到
模块级，无法作为 A1/A2 的逐项删除见证。

同时，第一口径只对 `R0_CORE_PATHS` 六个固定路径求和。若职责迁到另一个核心文件，它不会自动
进入该聚合；全仓生产总量能暴露“没有真删除”，但不能兑现清单第 26 行“原职责迁到新文件仍计入”
的硬门。专项测试又只比较 baseline commit、baseline 总数、六个路径和部署脚本是否排除，没有
比较 R5-0 当前行数、operations 包、生产总量、旧符号位置、领域命中或职责清单。

最小修复：

1. 将旧符号扫描结果按 `production/dynamic-entry/test/current-doc/historical-doc` 分类，冻结每个删除
   符号的精确文件集合；历史文档只需标为保留，不要求删除；
2. 给第一口径增加一个版本化的“职责后继路径”元组，R5 拆出新文件时必须显式加入同一聚合；
   保留 operations 全包与全仓生产总量两个防搬移口径，不增加新度量服务；
3. 将上述字段写入结构快照，并增加一个完整快照比较/差异报告门；删除文件按零行、后继文件按
   声明聚合；
4. 在清单中把设备参数、旧 loader、Root 工具、producer family、readiness/context 的精确符号与
   替代消费者逐项列出。可由脚本生成位置，文档只解释处置，避免手工复制多份权威。

### F3（高）：R5-G 夹具是文件库存，还不是可执行且有界的科学回归合同

位置：

- `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 4.2 节；
- `tests/fixtures/r5_e2e_tcad/manifest.json:7-13,14-100`；
- `tests/fixtures/r5_e2e_tcad/rubric.json:55-65`；
- `R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md:131-143`。

13 个文件确实存在，大小和 SHA-256 正确；历史 scorer manifest 也把 baseline、replay、curve、
metrics、residuals 和 diff 绑定到同一 2026-08-05 链。当前问题不是字节伪造，而是上位门要求冻结
的执行语义没有进入 manifest：

- `required_operation_families` 是自然语言家族，不是精确 operation id、端口绑定和最短允许拓扑；
- 没有冻结哪种矛盾允许跳过 ideation、哪些 Operation 不得跳过；
- “大致相同预算”没有模型档位、工具集合、token/墙钟上限或偏差规则；
- replay 只有模式名，没有 adapter id/version、实现或配置摘要；
- scorer execution manifest 引用了 scorer 实现与合同摘要，但 13 项清单没有冻结相应实现/合同，
  也没有冻结历史 replay project/review/experiment plan/runtime attestation，因而不能仅凭当前清单
  独立重建“package → attestation → curve score”的精确机械链；
- frozen curve bundle 被当作 Fig.4 target，但没有冻结其论文/图版 locator 或已有独立 evidence
  audit。若它只是用户定义目标，任务和量表必须如此标注；若要主张它来自论文 Fig.4，则必须提供
  可审计来源。

范围声明也没有机械门：`frozen_target_metrics.json` 同时含 InGaAs/InAlAs、baseline/candidate，且
pilot id 含 `fig4-to-fig7`；`deck.diff` 明确包含 mesh 变化。这些文件可以作为同一历史链的控制证据，
并不自动说明选题错误，但当前测试只核对 hash，不能证明 Agent 只看到 InGaAs Fig.4、480 °C 的
有界问题，也不能阻止把 mesh 相关性写成论文条件或物理因果。

最小修复：

1. 在 manifest 中冻结精确 operation id、输入文件到端口的映射、必需/可跳过规则，以及多角色链
   与单 Agent 对照的同一模型档位、工具集合和可量化预算容差；
2. 冻结 replay adapter 的 id/version/实现摘要，并补齐可独立重建历史机械链所需的最小对象；最小
   选择是引用并校验现有 ActiveResearchBundle 的 exact replay project/review/audit payload，加上
   scorer 实现/合同，不能重新复制一套科研控制状态；
3. 为 target curve 增加精确来源 locator/evidence audit，或明确降格为用户定义目标且禁止论文来源
   主张；
4. 增加语义范围断言：本任务评分对象为 InGaAs Fig.4、480 °C；InAlAs/candidate/Fig.7 字段不进入
   Agent claim evidence；mesh diff 只能作为实现差异 prior signal，不能成为论文事实或既定因果；
5. 测试除 hash 外校验上述合同字段与必要文件。真实 Sentaurus 仍保持可选，不扩大 R5。

### F4（中）：目录摘要是真值，但不是当前 R5 专项门产生的真值

位置：

- `R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md:37-48,145-169`；
- `tests/fixtures/r5_structure_baseline.json` 的 `catalogs`；
- `tests/operations/test_r5_frozen_baselines.py:13-36`。

本轮从刚构建的 clean-wheel 环境独立计算得到：

```text
core         32  public=18  support=14  internal=0  a8257982…f5a11
full         49  public=23  support=26  internal=0  f1dec7d2…fc4a1
full+InGaAs  50  public=23  support=27  internal=0  3312dc08…dd1ba
```

因此快照数值可信。但是基线脚本不导入产品包，也不输出 catalog；R5 专项测试完全不读取快照的
`catalogs` 字段。当前 124 项矩阵验证了 clean-wheel 安装和部分数量，却没有把三种完整摘要与 R5
快照绑定。后续 A1 合法改变 core/full 摘要时，缺少一个统一差异见证来区分“所有权迁移”与行为
丢失。

最小修复：复用现有 `installed_probe`，增加一个测试/小型捕获函数，从 core/full/InGaAs 三个
clean-wheel 计算同一排序摘要并与 R5-0 快照比较。A1 后保留 R5-0 旧值，同时生成当前值和解释过的
差异；不要新增 catalog、数据库或运行时探针。

## 4. 已通过且应保留的部分

- 根 `MANIFEST.sha256` 中 `src/`、`plugins/`、`deploy/`、`roles/` 的全部条目当前校验通过，支持
  “R5-0 未修改生产行为”；R5-0 不应为了本报告提前重写根发布清单。
- 双语文档章节和债务项语义对应，工具可见性明确标成提示约束原型，没有冒充平台级沙箱。
- 参数纵切面被正确分类为 A1 先迁移，旧发现/Root 工具被正确分类为 A2 后删除；没有误删
  `RecommendedTaskMode/NextTaskMode`、ApprovalService、ExecutionService、Artifact/CAS、Worker
  文件生命周期或人工 UI。
- 三重结构实测为：R0 聚合 11297/13657 行、operations 7 文件/2060 行、生产 Python 126 文件/
  62533 行、`deploy/install.sh` 1026 行；均与快照一致。
- 私有新运行目录 `.scidiscovery/r5-e2e-private/` 被 Git 忽略，且不在 `/tmp`；
  `deliverables/r5-e2e/` 仅作未来脱敏交付。release/secret scan 是 R5-G/R5-F 的未来验收，不应被
  误报成 R5-0 当前失败。
- R5-0 没有引入新的持久对象、生命周期、注册表、排名器或固定科学 DAG，整体符合奥卡姆剃刀。

## 5. 本轮实际验证

所有 Python/pytest 命令均使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

且严格串行、无并行 pytest。

| 检查 | 本轮结果 |
| --- | --- |
| `python scripts/r5_baseline_metrics.py` 与快照人工全字段核对 | 数值一致；发现专项测试覆盖缺口 |
| `pytest -q tests/operations/test_r5_frozen_baselines.py` | `3 passed in 0.46s` |
| R4 13 文件聚焦矩阵 + R5 专项 | `124 passed in 46.95s` |
| `pytest -q` | `248 passed in 100.30s` |
| clean-wheel 三目录数量/摘要独立复算 | 与快照完全一致 |
| 13 个 Fig.4 文件 size/SHA-256 | 全部一致 |
| R4 生产表面按根清单核对 | 全部一致 |
| `git diff --check` | 通过 |

本轮没有启动 daemon、浏览器、Codex 科学 Agent 或 solver；这些不是 R5-0 的实现目标。真实 Agent
效果属于已冻结后才执行的 R5-G，不应由本报告预先声称通过。

## 6. 冻结的最小返修清单

再次送审前只需完成以下四组 R5-0 修改：

1. 修正双语架构的“每包一个插件定义”和“所有记录都有 operation identity”两处绝对表述；
2. 将删除消费者按生产/动态入口/测试/当前文档/历史文档精确冻结，加入职责后继路径，并让结构
   差异门覆盖快照全部关键字段；
3. 将 Fig.4 manifest 从文件库存补成精确 Operation、端口、skip、预算、replay/scorer 身份和来源
   边界合同，补齐最小可重建对象与语义范围负例；
4. 复用 clean-wheel probe，把三组合数量和摘要绑定到 R5-0 快照。

不得借返修修改生产代码、增加新领域、强制真实 solver、重跑整篇论文流程、新建状态机或提前执行
R5-A1。返修后应由独立审查者只复核上述四项，并重新运行 R5 专项、124 项聚焦和全仓串行回归。

## 7. 最终结论

**打回**

R5-0 尚未通过；不放行 R5-A1，更不放行 R5-A2。
