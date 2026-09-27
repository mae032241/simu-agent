# R5-H H0 第二轮独立审查

日期：2026-08-30  
性质：只读独立复审  
结论：**通过，只放行 H1**

## 1. 审查范围

本轮只复审 H0 规范、消费者和验收证据返修，不审查 H1 或后续阶段实现：

- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第26节；
- `docs/plans/README.md`；
- `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
- `docs/ARCHITECTURE.md` 与 `docs/ARCHITECTURE.zh-CN.md` 的当前状态入口；
- `docs/INSTALL.md` 与 `docs/INSTALL.zh-CN.md` 的默认插件说明；
- `tests/operations/test_architecture_constraint_matrix.py`；
- 上述文档声称的消费者、插件入口、目录组合和测试证据。

本轮未修改实现，也未把累计工作树中的其他 R1～R5 变更纳入 H0 候选。

## 2. 上一轮阻断及关闭证据

### 2.1 双语当前架构状态矛盾

上一轮英文架构顶部称 D4-H2 已结束，但第7节仍称 D4 尚未执行真实修订和新 critic。

返修后，英文第7节已与中文架构、主计划第26节和真实停止门一致：D4-H 与唯一一次有界
D4-H2 均已完成，两个精确新 critic 都返回 `blocked`；工程停止门通过但科学结果未通过，
因此 R5-G 停止于假设阶段，不授权第三轮修订或实验设计。

结论：关闭。

### 2.2 33项约束只有编号完整、语义不完整

上一轮约束矩阵将多项稳定承重行为压缩得过窄，结构测试也只能证明编号和字符串存在，不能证明
33项语义完整或当前实现符合。

返修后：

- 33个稳定编号保持完整且唯一；
- 每项均有 `requirement`、`prohibited`、`assessment` 和 `evidence`；
- `AUTH-003` 明确覆盖 readiness、preflight、invoke、assignment、validation、finalize、receipt、
  reconcile、端口用途、上下文资源、资格、预算、工具和副作用，并禁止 Root、Task、profile、
  Schema 名、插件实现表和隐藏工具路由成为第二授权源；
- `PLG-002` 恢复独立安装、禁用、组合、升级失败统一回滚和正确依赖方向；
- 已发现缺陷保留为 `known_issue`，未验证项保持 `pending_review`，没有继承历史候选的
  `conformant` 结论；
- 结构测试改名并明确注释：它只验证注册表结构，语义符合性仍需独立审查。

该矩阵仍是行为验收矩阵，不是33个运行实体、收据或状态。

结论：关闭。

### 2.3 当前真实安装组合与 H2 目标矩阵混淆

上一轮“核心”同时被用于仅 builtin 的概念组合和实际基础 wheel，无法对应真实安装入口。

返修后已明确区分：

- 仅 builtin：只作编译诊断，当前因未消费组件而失败，不是可安装产品组合；
- 当前基础 wheel：同一个 `scidiscovery` wheel 发布 builtin 与 general_science，共11个 Operation；
- 当前基础 wheel加 tcad_artifact：28个 Operation；
- 目标基础 wheel加 curve_score：当前因 curve 插件错误依赖 tcad_artifact 而不能安装，是 H2
  待修目标；
- 当前完整安装：基础 wheel加 tcad_artifact、curve_score，共43个 Operation；
- InGaAs 项目插件是完整安装上的可选项目插件，不属于通用默认组合。

当前事实和 H2 目标不再混写，完整安装不能掩盖 general-only 或 curve-only 的依赖泄漏。

结论：关闭。

### 2.4 旧 Worker 工具消费者误分类

上一轮将旧读取工具误记为两个生产声明。返修后已按真实消费者分类：

- 一个生产声明：TCAD 插件显式注册 `worker_read_input`；
- 一个测试声明：`ARCHITECTURE_TEST_PLUGIN` 夹具注册旧读取工具；
- 其他消费者为 baseline/兼容测试和部分现场脚本；
- H3 的处置是先迁移一个生产声明和一个测试夹具，再删除隐藏路由，并以旧工具直接调用返回
  “未知工具”作为负例。

模块级兼容别名也已准确记为 `builtin_plugin.PLUGIN`，不再写成不存在的
`CORE_PLUGIN.PLUGIN`。

结论：关闭。

## 3. 其他证据问题关闭情况

- R5-G/D4-H2 消费者已精确列出：`test_r5_g_science_chain_runner.py`、
  `test_r5_g_hypothesis_stage_runner.py`、两个 revision runner、
  `test_r5_frozen_baselines.py` 和历史评估文档；不再使用含混的“六组 runner 测试”。
- H0 已列出精确文件范围，并明确不修改 `src/`、`plugins/`、`deploy/` 或数据库文件，不改变
  运行行为。
- 安装文档所述“默认不安装领域插件”与部署脚本的空 `SCID_PLUGINS` 默认值一致。

## 4. 独立重放

精确测试命令：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
pytest -q \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_deploy_scripts.py \
  tests/operations/test_catalog_installed_entrypoint.py
```

结果：

```text
39 passed in 34.77s
```

另行执行：

```bash
git diff --check
```

结果：通过，无输出。

## 5. 架构目标判断

H0 返修维持以下目标：

- 一个 `scidiscovery.plugins` 注册入口和一个启动时 `CompiledCatalog`；
- `public`、`support`、`internal`、`all` 只是同一目录的投影；
- Agent 和专业 Worker 拥有科研判断；
- 控制面只拥有身份、不可变记录、生命周期、资格、人工决定和副作用门禁；
- 通用科研、曲线和 TCAD 所有权能够在后续阶段按插件边界收口；
- 不新增科学图、固定阶段 DAG、第二注册表、第二 current、数据库状态机或历史在线兼容层。

因此，H0 符合 OperationSpec 单一目录、Agent 科学所有权、轻量控制面、插件化和奥卡姆目标。

## 6. 最终结论

**通过。允许进入 H1。**

本结论只证明 H0 的规范、消费者调查、安装矩阵和验收证据完成返修；它不预判 H1 的设计或实现
正确，也不放行 H2 及后续阶段。H1 完成后仍须按同一规则进行独立实现审查。
