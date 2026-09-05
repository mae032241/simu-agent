# R5-H H6-C 职责审计与总收口第二轮独立复审

日期：2026-08-31  
审查对象：首轮四项阻断返工后的当前未提交工作树  
审查边界：只复核 B1—B4、H6 总收口不变量和必要回归；不实施 H7，不冻结 R5 发布

## 结论

**通过且只放行 H7。**

首轮报告
`R5_H6_C_RESPONSIBILITY_AND_TOTAL_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md` 的 B1—B4 均已按最小
边界闭合：活动执行索引唯一停在 H6-C 复审；四条约束 assessment/evidence 对齐当前阶段证据；补充
发现的三个零消费者方法已直接删除；失效根清单已删除，唯一发布清单只由既有构建器在清洁发布
目录生成。返工没有新增 Registry、状态、入口校验、兼容层、Operation、插件入口、数据库对象或
机械文件拆分。

本轮没有阻断项。H7 可以开始，但本通过结论不等于 H7、R5 发布冻结、真实 Agent、真实浏览器或
真实 TCAD solver 已通过。

## 首轮阻断逐项复核

### B1：活动执行索引——闭合

`docs/plans/README.md:13-16` 现明确声明 H6-A/H6-B 已通过、当前只返工并复审 H6-C、H7 未放行；
H6-B 门报告仍只授权 H6-C。总计划第 26 节、R5-H 状态表和 H6 顶部状态均停在“H6-C 首轮打回项
已返工，待独立复审”，没有另一活动文件把 H6 或 H7标成通过。

本地索引仍只有总计划、R5-H、H6 和当前有效 H6-B 门四个活动入口；历史报告没有成为第二状态
权威。该修改只是同步一句既有状态，没有新增状态 Schema 或动态推导。

### B2：四条规范 assessment/evidence——闭合

`SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 已更新到 2026-08-31，四条旧事实分别改为：

- `HIL-002 = conformant`：H5 第二轮证据覆盖科学资格与执行授权两个精确合同、不同投影和不共享
  决定；执行服务仍只接受 `execution_authorization`，没有把资格决定当成执行授权；
- `PLG-001 = conformant`：曲线 Schema、算法和工具位于 `curve_score` 插件，核心生产 Python 中没有
  `curve_score`、`tcad_artifact` 或 `ingaas_fig4` 名称分支；
- `PLG-002 = conformant`：`curve_score` wheel 只依赖 `scidiscovery`，TCAD 单向依赖 curve；本轮
  installed-wheel 矩阵独立复现 core/curve/table/TCAD 组合；
- `UI-001 = conformant`：compiled review sections 先显示科学层次，raw subject `<details>` 不带
  `open`，仍可展开或下载精确字节；证据诚实保留“真实浏览器视觉舒适度属于 H7 人工观察项”。

以上没有把 `HIL-001`、`UI-002`、真实 Agent 或尚待 H7 的约束提前改成通过；`SEC-002` 对
`spawn_agent` 原生工具隔离仍维持 `known_issue`。因此 assessment 没有以结构测试代替未发生的 H7
实证，也没有过度宣称浏览器舒适度。

### B3：六个死表面——闭合

对生产、插件、测试、部署、角色、当前文档和动态字符串逐名复核：

- `package_deck_project_json`；
- `curve_crossing_count`；
- `instance_related_approval_ids`；
- `clear_session`；
- `instance_invalidation_approval_ids`；
- `rotate_access`。

六个名字在活动代码、测试和注册面均无命中；仅 H6 实施记录及首轮审查保留“已删除”的说明性
引用。实现、`__all__` 或类方法均已不存在。保留的真实路径分别是 reviewed-deck 包装、
`curve_crossings`、实例历史/待处理审批查询和正常审批访问合同。

后三个方法只读取或更新既有 scheduler/approval 表，不定义数据库 Schema、持久对象、Operation、
插件 entry point 或科学 Schema；直接删除不需要迁移。前后三个删除承担相同的仓库外未文档化
Python API 风险，当前方案统一选择不增加假想兼容 alias，并记录可按单个定义恢复的回滚边界，口径
一致。独立 wheel/plugin 和完整 Operation 回归均通过，未出现针对调用点的例外补丁。

### B4：唯一发布清单边界——闭合

工作树根 `MANIFEST.sha256` 已删除。`build_git_release.py` 不把它列入 `ROOT_FILES`、
`SOURCE_TREES`、`DOCUMENTS` 或 `TOOLS`，而是在输出目录完成归一化和扫描后调用 `_write_manifest`
自产清单。当前发布说明只要求在“生成目录”运行摘要校验；部署、测试和运行入口没有读取源码根
清单。历史审查文档对旧根清单的引用明确属于各自当时代际，不是活动依赖。

第二轮新建发布目录只有一个 `MANIFEST.sha256`。静态 allowlist 展开、manifest 和实际非manifest
文件集合均为 250 项且完全相等；包内严格摘要校验 250/250 通过。删除根重复清单比同步维护两份
投影更符合奥卡姆剃刀。

## H6 架构与职责复核

### 精确规模

独立运行当前指标和机械 `wc -l` 得到：

- 生产 Python：150 文件、59,200 行；相对 H5 的 59,317 行净删 117 行；
- `src/scidiscovery/operations`：7 文件、2,064 行；
- R0 六项核心责任聚合：9,518 行；
- Task 五文件责任聚合：6,031 行。

当前仍是全部 12 个至少 1,000 行生产 Python 文件加点名的 989 行 curve analysis。仅
`scheduler_bindings.py` 从 1,887 降为 1,842 行、`approvals.py` 从 1,324 降为 1,291 行；没有文件
被机械拆分，也没有新增生产文件。

### OperationSpec、插件和轻控制面

- `operations/` 仍只有七个既有模块；`CompiledCatalog` 仍只有一个构造点；
- 插件仍只通过 `scidiscovery.plugins` entry-point group 注册；public/support/internal 仍是同一目录
  投影；
- 核心无领域插件名分支，TCAD/curve/table 能力仍由各插件声明；
- 六项删除没有改变 OperationSpec、operation id、端口、编译摘要、Root/Worker 路由、current、
  qualification、Approval/Execution 状态机或持久 Schema；
- 其余大文件继续按已有权威边界内聚。当前没有同时满足“独立责任、不同消费者、单向依赖、生产
  行数不增”四条件的强拆证据。

因此本返工是 78 行额外生产减法，没有以新胶水换取表面缩短，符合 33 项承重约束、轻控制面和
奥卡姆剃刀。

## 第二轮独立回归

没有继承首轮测试结论。所有 pytest 均在当前修订字节上串行运行，并在进程内设置
`ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1`：

1. TCAD、curve、InGaAs、installed catalog 四文件聚焦：`40 passed in 50.82s`；
2. `pytest -q tests/operations`：`292 passed in 98.50s`；
3. 33 项约束矩阵、部署脚本和平台配置：`38 passed in 5.16s`；
4. `archive/r5-g-evaluation/MANIFEST.sha256`：14/14 严格通过；
5. 清洁发布 `/tmp/scid-h6c-r2-review.R8TksB/release`：251 个文件、250 条 manifest；
6. 发布内 `sha256sum -c --strict MANIFEST.sha256`：250/250 通过；
7. 静态 allowlist = manifest = 实际非manifest文件集合，三者均为 250；
8. 发布计划投影精确为三份当前计划和 H6-B 第二轮通过报告；不含归档、workspace、
   deliverables、`123/`、私有状态或一次性入口；
9. `git diff --check` 通过；活动树不存在 `remote_runner_py36.pyc`。

发布继续携带当前设计宪章和 33 项 YAML，H7 未被加入通过门或发布冻结状态。

## 非阻断项

1. `UI-001` 的结构与语义证据足以关闭 H6 的旧“默认平铺 raw JSON”缺陷；真实浏览器视觉舒适度
   仍应在 H7 人工观察，但它是未来验收要求，不是当前 H6 失败。
2. 首轮记录的 TCAD runtime plugin 对 Task 私有实现的窄接缝仍存在。它没有第二 Task 权威且当前有
   真实工具消费者，不支持在 H6 预建通用 Service；H7 实际 TCAD 工具回归继续观察即可。
3. 六个已删名字可能被仓库外未文档化 Python 调用者直接导入。这是本轮明确接受的兼容取舍；若
   发现真实消费者，按单个定义回滚，不预留常驻 alias。

## 关键 SHA-256

- 首轮独立报告：`31050c9a7fbb0a929b8e191ba57946fb71421e9ac21099861f55d5585b599cc8`
- 当前活动索引：`9d1afe3249c51946be853080220b1440915973955f3408bd8b3043e9436ebf21`
- 当前 33 项约束：`49dae0bd9850e9e0092a6213de920b58c90516ce6536eb952ae5cb63c2f28296`
- H6 实施记录：`9437cb3c2356cb2a26c612af23598b0e510e6cca3cb84a83bf9f372a16b36d0f`
- R5-H 实施记录：`62655470a2e6bd3882b6d87c82aa9ed09c27cd7d06221e964f13b1fde333b50d`
- 总计划：`109a5d1be9983b9e87c5e8430ec6d15f4edba85a22142e3f3413500e9c68047e`
- `scheduler_bindings.py`：`6ed40e0d79625a4bf1c3e76fe3103e92a9f711d627e536d97ab849186c7d8481`
- `approvals.py`：`b3471f4d067c44fefda5271b77507c26f79a78240ee320dadf5d8789d51429be`
- TCAD `project_packager.py`：`b8d62c02d1e9041994d6285dc4c5fda44ce060f5abe3a741973498522da10203`
- curve `schema.py`：`a65cf1becf73080d9c62f81eda0c6077f82a22dbcf2bc8e5fadc78cbc1d94574`
- 发布构建器：`26c12f3e7128bf44023e27e2229e34603915439d6836ae56e14ef935fdca71c7`
- 归档 manifest：`312eaf0dfa45e330fb110ec02351315ae7e0ff283b92b9b9bc46090b0f61e74f`

## 放行边界

H6-C 和 H6 总收口通过，**只放行 H7**。H7 必须继续按既定分层门验证真实通用 Agent、真实 TCAD
Agent、原生/领域工具权限、安装组合、生命周期、UI 人工观察和有授权时的外部 solver；H7 独立审查
通过前不得宣称 R5 发布完成。
