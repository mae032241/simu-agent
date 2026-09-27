# R5-H H6-C 职责审计与总收口独立审查

日期：2026-08-31  
审查对象：当前未提交工作树的 H6-C 实现候选  
审查边界：独立核对职责、消费者、复杂度、归档、发布和状态证据；不实施修复，不放行 H7

## 结论

**打回（revise），H7 不放行。**

运行实现和发布生成路径的回归证据是绿色的：机械全集、三个已删名字、精确规模、292 项
Operation、38 项架构/部署、归档 manifest 和 251/250 清洁发布均可独立复现。但是当前候选仍有
四项总收口阻断：活动执行索引自相矛盾，发布中的规范性约束登记仍陈述已由 H2/H5 关闭的旧缺陷，
“只发现三个死表面”的审计遗漏三个同样零消费者的方法，根目录受跟踪 manifest 也不是当前有效
清单。这些不是哈希碰撞或运行失败补丁，而是当前状态、职责审计和完整性声明尚未唯一。

返工只应修正以下四项并重新独立复审；不得借机增加 Registry、状态文件、运行时校验、兼容别名、
facade 或大文件强拆。

## 阻断项

### B1：活动执行索引同时声明“正在 H6-B”和“H6-B 已通过”

`docs/plans/README.md:13-16` 的同一个“当前执行链”先写“当前只执行 H6-B”，下一项又写 H6-B
第二轮已通过且只放行 H6-C。总计划第 26 节、R5-H 状态表和 H6 实施记录均已停在“H6-C 候选待
独立总审查”，所以该索引是落后一代的活动状态陈述。它虽然不进入清洁发布包，却是本地明确标注
的当前入口，不能用下一行的相反陈述抵消。

最小修订：只把 H6 条目的阶段说明同步为“H6-A/H6-B 已通过，当前审查 H6-C，H7 未放行”；不新增
状态实体或动态推导。

### B2：发布中的 33 项规范登记含四条已过期的当前事实

`SCIENTIFIC_AGENT_CONSTRAINTS.yaml:114-119,144-155,180-185` 仍把 `HIL-002`、`PLG-001`、
`PLG-002`、`UI-001` 标为 `known_issue`，证据分别写“列入 H5 修复”“核心仍包含曲线 Schema/算法”
“curve_score 当前依赖 tcad_artifact”“当前 render 默认展开全部 raw subjects”。当前代码和已通过
阶段与这些陈述不一致：曲线 Schema/算法已在 curve 插件，`curve_score` wheel 只依赖
`scidiscovery`，审批渲染不再给 raw subject 添加 `open`，H5 第二轮也已通过。若 HIL/UI 仍有未完成
的真实浏览器或人工可读性风险，可以继续记为 `known_issue` 或 `pending_review`，但证据必须描述
当前剩余风险，不能继续把已经完成的 H2/H5 当未来工作。

该 YAML 由架构文档声明为 33 项当前规范基线，并被 H6 清洁发布显式携带，因此这是发布事实矛盾，
不是历史文档措辞。现有矩阵测试只验证 33 个键和状态枚举合法；其注释也明确语义符合性依赖独立
审查，所以 `38 passed` 不能证明这些 assessment 内容为真。`SEC-002` 对原生工具隔离的已知限制是
当前真实边界，不在本阻断范围内。

最小修订：逐条把上述四项 assessment/evidence 对齐当前实现和尚未验证的真实范围，并更新登记
日期；不要把所有 `pending_review` 无证据改成 `conformant`。

### B3：死表面审计不完整，保留项本身也是零消费者

H6 记录在 `R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md:251-258` 声明只发现三个高置信度
死表面，并明确保留 `instance_invalidation_approval_ids`。对生产、插件、测试、部署、角色和当前/
历史文档的逐字与 AST 导入复核发现以下方法均只有定义，没有仓库内调用、动态字符串注册、测试或
文档合同：

- `SchedulerBindingService.clear_session`（`scheduler_bindings.py:486-493`）；
- `SchedulerBindingService.instance_invalidation_approval_ids`
  （`scheduler_bindings.py:1149-1183`）；除 H6 记录说“保留”外无消费者；
- `ApprovalService.rotate_access`（`approvals.py:834-865`）。

特别是本轮删除的 `instance_related_approval_ids` 只是转调一个同样零消费者的底层方法，因而删除
别名并未闭合这条死查询。`instance_history_approval_ids` 和
`instance_pending_binding_approval_ids` 才有实例管理、UI 或 Root 的真实消费者。上述三个方法
是否保留可以有两种合格结论：删除；或给出当前受支持合同、真实消费者和目标入口回归。仅以“可能
存在仓库外未文档化 Python 调用者”保留不合格，因为三个已删除名字承担完全相同的外部 API 风险，
且本轮明确不为假想消费者保留兼容层。

这不要求拆分 `scheduler_bindings.py` 或 `approvals.py`。相反，先闭合死表面比为了行数拆文件更符合
奥卡姆剃刀。

### B4：根目录受跟踪 `MANIFEST.sha256` 不是当前有效清单

根 `MANIFEST.sha256` 当前有 399 条，独立执行 `sha256sum -c` 得到 123 条摘要不匹配，并仍列出
完整历史 `docs/plans` 投影；它的 SHA-256 为
`e60638ee19e7b90f9802a4e1479583a4b2c994946d16f69fbc644402f15b3a8a`。清洁发布构建器不复制该
文件，而是在输出目录重新生成正确的 250 条 manifest；发布文档也只要求在“生成目录”核验，因此
清洁发布本身没有被根清单污染。但仓库仍受跟踪一个名称相同、部分更新、实际校验失败且没有声明
权威范围的文件，不能作为 H6“总收口”的当前完整性表面保留。

最小修订二选一：删除这个非权威根清单，只保留构建产物 manifest；或明确其范围并使其在当前候选
上可机械通过。不要再维护两份不同投影的手工摘要清单。

## 已通过的职责与复杂度核对

### 机械全集和消费者

`find src plugins -name '*.py'` 与 `wc -l` 得到精确 150 文件、59,278 行；全集确为 12 个至少
1,000 行生产 Python 文件，加计划点名的 989 行 `curve_score/analysis.py`。AST 解析相对/绝对导入
和逐字字符串复核得到的直接生产消费者数如下，与 H6 表一致：

| 对象 | 行数 | 直接生产消费者 | 审查判断 |
| --- | ---: | ---: | --- |
| `task_worker_files.py` | 2,345 | 2 | Worker 文件、快照、验证生命周期内聚，不强拆 |
| `scheduler_bindings.py` | 1,887 | 7 | 单一绑定/current SQLite 权威，不强拆；但须处理 B3 |
| TCAD `project_packager.py` | 1,848 | 12 | 工程合同与确定性打包共享执行合同，不强拆 |
| `tasks.py` | 1,841 | 10 | Task 事务主类，evidence/output/file 已外提，不强拆 |
| curve `schema.py` | 1,667 | 11 | 曲线合同与确定性评价属同一插件，不迁回核心 |
| `approvals.py` | 1,324 | 7 | 单一审批事务权威，不强拆；但须处理 B3 |
| TCAD `debug_service.py` | 1,279 | 3 | 单 attempt 调试服务有真实工具消费者，不强拆 |
| `mcp_root_operation_routes.py` | 1,237 | 1 | Root 唯一 Operation 组合入口，不按 executor 加 facade |
| TCAD `parameter_operations.py` | 1,207 | 1 | 插件内领域纵切面由统一插件入口消费，不强拆 |
| TCAD `transform_adapter.py` | 1,152 | 1 | 同一无状态变换协议，不按 profile 增注册胶水 |
| `task_outputs.py` | 1,027 | 1 | Task 输出验证/finalize 边界内聚，不强拆 |
| approval UI `app.py` | 1,022 | 1 | loopback/Origin/维护锁为同一 UI 权威，不强拆 |
| curve `analysis.py` | 989 | 2 | 报告和图共享同一确定性采样，不强拆 |

除 B3 的未闭合死方法外，没有证据要求为了文件长度拆分上述对象。零文件拆分符合四条件、33 项承重
不变量和奥卡姆剃刀；行数本身不是职责证据。

### 三个已删除名字

`package_deck_project_json`、`curve_crossing_count`、
`instance_related_approval_ids` 在生产、插件、测试、部署、角色、文档和字符串注册面的唯一当前命中
都是 H6 实施记录；实现和 `__all__`/类表面均已不存在。保留路径分别是
`package_reviewed_deck_json`、`curve_crossings` 和更具体的实例审批查询。聚焦 wheel/plugin 与完整
Operation 回归均通过，Operation id、插件 entry point、当前 Schema、数据库表和持久对象没有因这
三个名字变化。仓库外直接导入未文档化 Python 名字仍是明确兼容风险；H6 的“不增加常驻 alias”
取舍合理。

### 精确指标与单调复杂度门

独立运行 `scripts/r5_current_metrics.py` 得到：

- 生产 Python：150 文件、59,278 行；相对 H5 的 59,317 行净删 39 行；
- `src/scidiscovery/operations`：7 文件、2,064 行；
- R0 六项核心责任聚合：9,518 行；
- Task 五文件责任聚合：6,031 行。

`test_r5_catalog_stages.py:180-183` 从精确等式改为 H5 文件数/总行数上限是合理的：合法删除不会
失败，新增复杂度仍不能使生产文件或总行数超过 H5 上限，也没有把当前 59,278 冻成新的特例。
本修改没有掩盖本轮运行失败。

## 独立测试证据

所有 pytest 均串行运行，并在命令进程内设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`：

1. TCAD、curve、InGaAs 和 installed catalog 四文件聚焦：`40 passed in 50.30s`；
2. `pytest -q tests/operations`：`292 passed in 96.45s`；
3. 架构矩阵、部署脚本、平台配置：`38 passed in 5.22s`；
4. `archive/r5-g-evaluation/MANIFEST.sha256`：14/14 通过；活动脚本/测试树不存在 R5-G runner，
   活动 conftest 不再含 `r5_e2e`；
5. 新建 `/tmp/scid-h6c-review.x5vBUd/release` 清洁构建：251 个文件，其中 manifest 250 条；静态
   allowlist 展开、manifest 和实际非manifest文件集合均为 250 且集合完全相等；
6. 发布 `docs/plans` 精确只有三份当前计划和 H6-B 第二轮通过报告，不含归档、workspace、
   deliverables、`123/`、私有状态或一次性入口；发布内 `sha256sum -c` 250/250 通过；
7. `git diff --check` 通过；测试后不存在活动 `remote_runner_py36.pyc`。

H6-A/H6-B 报告字节与实施记录一致：

- H6-A：`0382ac1505cea714d66ce1f0f5e9c42105b950d10b51cf3f4b435411a94b321a`；
- H6-B 首轮打回：`2cdb19858895a4f382ba74ef907dd662c90695cc5242abc86ba0741a6a4bbfb1`；
- H6-B 第二轮通过：`9b59e88f799eec2c93767924194c6a8df35265071dadab41f3ff4cf0cadb4bfc`。

归档字节、H6-A/B 门和发布四文件投影没有退化；总计划与 R5-H 均仍将 H7 标为未开始。B1 是活动
索引同步遗漏，不能据此否定 H6-A/B 已完成的机械结果，但必须在 H6 总审查前闭合。

## 非阻断改进

TCAD `runtime_plugin.py` 目前通过 `TaskService` 的若干私有方法以及 `_WorkspaceSnapshotFile`、
`_write_control_output_file` 构造窄的 `TCADTaskAttemptAccess`。这没有建立第二 Task 权威，当前也有真实
调试工具消费者，因此不构成 H6 强拆理由；但它是插件对核心私有实现的耦合。H7 真实 TCAD 工具回归
应把该接缝列为观察项，后续只有在出现第二个领域消费者或独立变化证据时，才考虑把现有窄能力提升
为公共协议；本轮不要预先增加通用 Service。

## 关键审查对象 SHA-256

- H6 实施记录：`77e562b4963ce128e72d8cf4b88796baf9bb28d8fc10de597336aa0433c0a467`
- R5-H 实施记录：`d0a384c52af5d2ee6f713aad061befa5a352d1812038e4e48431bbfa1d580f35`
- 总计划：`7b40efa09e3cb27b466ccfb2285985d5b76726ab5b685623ebc2741f3de078f3`
- 活动计划索引：`dd505be1fe32ff2537e99811f3ec85cd3953ae0995d109ca7996062cd9543f7d`
- 33 项约束：`9549b03a1c106e4e7dc1c49b23a21fec648eaf9769ac4c5498b98eae69ac1c48`
- `scheduler_bindings.py`：`1f17cee30cc7f358234e7675cb719c90b6305cac86d9b2b8f02c13145aa69d07`
- `approvals.py`：`d65cef89fa9e230a1f24e583f3e56e2451b3607b2941deedcbdb61460cc5e885`
- TCAD `project_packager.py`：`b8d62c02d1e9041994d6285dc4c5fda44ce060f5abe3a741973498522da10203`
- curve `schema.py`：`a65cf1becf73080d9c62f81eda0c6077f82a22dbcf2bc8e5fadc78cbc1d94574`
- 复杂度门测试：`77ae7e6c03775a4dcaca798ee2a96131d1b66133613281149a7e4bb25c7acc3d`
- 归档 manifest：`312eaf0dfa45e330fb110ec02351315ae7e0ff283b92b9b9bc46090b0f61e74f`
- 发布构建器：`26c12f3e7128bf44023e27e2229e34603915439d6836ae56e14ef935fdca71c7`
- 根目录失效 manifest：`e60638ee19e7b90f9802a4e1479583a4b2c994946d16f69fbc644402f15b3a8a`

## 放行边界

本报告不放行 H7。只允许修复 B1—B4，并针对修订后的精确工作树重新进行 H6-C/总收口独立复审。
四项闭合且回归不退化后，新的审查者才可决定是否只放行 H7；不得继承本轮运行绿灯作为修订候选
的通过结论。
