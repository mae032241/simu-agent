# R0：8765 行为基线独立审查报告

审查日期：2026-08-27

审查基线：`baseline/8765-codex@404aeb14c6ebc4b08bac599db91eaee54c103f48`

审查对象：当前 R0 测试、测试夹具、基线报告、计划状态说明和发布清单的未提交 diff

本报告只记录独立审查结论。阶段状态仍以
`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 26 节为唯一权威。

## 1. 首轮结论与修复闭合

首轮审查结论为“有条件通过”，在修复完成前不得进入 R1。四项缺口现已闭合：

1. `test_baseline_effect_lifecycle.py` 现在验证 execution review 的 subject 精确等于
   ExecutionRequest 与 payload；在 UI 决定前，`execution_start` 经 Root 调用面抛出
   `ExecutionApprovalError`，adapter 提交数保持为零，execution 状态仍为 `created`；真实回环
   UI 决定后才允许一次提交、同步和输出登记。
2. `test_baseline_role_contracts.py` 从 full clean-wheel 安装态加载八个角色，对完整 prompt、完整
   Worker JSON Schema、解析后的全部 context policies 和 runtime profile 计算规范 SHA-256，
   并对 latency、timeout 和最大输出字节做精确比较。
3. `test_baseline_worker_authority.py` 建立两个同时活动的任务，确认当前共享 workspace 根允许同一
   Worker 进程直接读取兄弟任务的 `assignment.json`，同时验证任务完成后其 workspace 被删除。
   报告明确将该结果标记为待替换的过宽权限，而不是目标合同。
4. `test_baseline_structure_metrics.py` 固定六个通用 Python 文件、大小写敏感正则和逐匹配源码行
   计数规则，可复现 114 个结构命中、6 个核心领域 import 和七个关键文件的行数。安装态插件
   测试同时精确断言三个自产 distribution 及三个直接运行依赖的版本。

## 2. R0.1—R0.11 审查结果

| 项目 | 结论 | 主要证据 |
| --- | --- | --- |
| R0.1 | 通过 | 基线 commit、Python、自产 wheel/直接依赖版本和 systemd 生产启动模块均已记录 |
| R0.2 | 通过 | 发布构建器先生成排除 ignored `build/lib` 的清洁交付树，再构建并分别安装 core/full wheel |
| R0.3 | 通过 | 八角色语义合同与资源 profile 在 full 安装态按完整规范摘要冻结 |
| R0.4 | 通过 | 安装态完成 schedule → dispatch → claim → materialize → validate → finalize → status，未虚构 `task_reconcile` |
| R0.5 | 通过 | 确定性 transform 的重复调用幂等，主输出和拆分输出均绑定同一精确父 Ref |
| R0.6 | 通过 | 精确 execution subject、未授权拒绝、UI 授权、单次提交、同步与输出登记均有正负证据 |
| R0.7 | 通过 | 回环 UI 显示精确原始 subject；读取不写状态；重复提交保持同一决定 Ref |
| R0.8 | 通过 | TCAD author 私有文件交付、无真实 solver 的 fake debug、冻结 author 输出到独立 reviewer 任务交接及 reviewer debug 拒绝均通过 |
| R0.9 | 通过 | 分散 entry points、断裂 operation-spec 元数据、核心领域 import、结构命中和关键行数均有可执行口径 |
| R0.10 | 通过 | 当前源码不存在 `OperationIntent`、`QualificationReceipt` 或 `ActiveHead` 实现，计划未将其误列为保留实现或本轮建设目标 |
| R0.11 | 通过 | `allow_additional`、共享根、角色级工具、默认网络、`handoff_only` 和兄弟目录可读现状均由安装态或可执行测试固定，并明确标为迁移债务 |

## 3. 安装入口与构建卫生

所有执行框架代码的 R0 probe 都从 `scripts/build_git_release.py` 生成的清洁交付源码构建 wheel，
再安装到独立 core/full 虚拟环境。子进程工作目录位于仓库外，移除了 `PYTHONPATH` 和
`SCIDISCOVERY_ROLE_DIR`，并断言 `scidiscovery` 实际导入路径位于虚拟环境前缀。

因此，core-only 的领域包缺失和 full 的插件发现结果来自安装包，而不是 pytest 的源码
`pythonpath` 或源码角色扫描。clean full wheel 发现两个 TCAD 角色；ignored
`plugins/tcad_artifact/build/lib` 中的陈旧 `tcad_deck_reviser` 没有进入 wheel。两个
`scidiscovery.operation_specs` entry-point 元数据仍存在，但其目标模块在 clean wheel 中缺失；
测试将此固定为发布缺陷负例，没有用陈旧 build 产物掩盖它。

## 4. 架构与迁移边界

R0 没有修改生产源码、插件实现、部署脚本或打包元数据，也没有连接真实 TCAD、远程服务或
生产状态目录。现有测试继续覆盖不可变 Artifact、精确 transform 父链、Worker 文件 finalize、
精确人工决定、幂等 execution sync 和外部提交单次性；未发现对 33 项基本约束中的权威、
不可变性、谱系、人工审批、CQRS、副作用、隔离、资源或迁移边界的退化。

旧 role loader、三个 entry-point group、静态 topology、共享 workspace 和角色级权限只作为
8765 的可测事实与待删除债务。计划明确要求 R1—R5 将它们收敛或删除；角色摘要冻结的是当前
prompt/Schema/context/profile 的语义输入，未来可改由 compiled catalog 投影同一语义摘要，
不要求保留旧 loader 或 entry-point 形式。测试也没有把固定 TCAD 顺序或旧注册形式定义为目标
不变量。

目标计划继续满足轻量 `OperationSpec`、单一插件入口、Agent 负责科学判断、控制面只负责精确
输入、校验、谱系、人工决定和副作用门禁的方向。R0 未提前实现 R1，也未新增 registry、状态机、
readiness、qualification 或 current 权威。

## 5. 独立实测

在上述精确工作树上执行：

```text
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/operations
11 passed in 15.16s

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
41 passed in 19.82s

git diff --check HEAD
通过

sha256sum -c --quiet MANIFEST.sha256
通过

git diff --exit-code HEAD -- src plugins roles deploy pyproject.toml scripts
通过；目标生产路径相对基线无 diff
```

R0 有意未运行真实 solver、真实外部 adapter、生产 daemon 或 live Codex Worker；这些不是 R0
行为基线的完成条件，后续 R6/R7 仍须按计划完成真实入口、恢复、最小授权穿透和经 UI 授权的
TCAD 回归。

## 6. 最终结论

**通过**

首轮四项阻断证据已全部闭合，R0.1—R0.11 有可信、可复现且范围适当的证据。R0 足以放行
R1；本结论不预判 R1 实现正确性，也不把 8765 的旧注册、固定拓扑或过宽权限提升为目标合同。
