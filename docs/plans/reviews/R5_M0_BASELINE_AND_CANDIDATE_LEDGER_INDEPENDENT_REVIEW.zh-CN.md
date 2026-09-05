# PASS — R5-M0 基线与候选账本独立设计/证据审查

日期：2026-09-01

结论：**PASS。仅放行 M1；不放行 M2—M7，也不表示 R5-M 已完成。**

本审查者未参与 R5-M 计划、M0 账本或当前实现的编写。审查绑定到分支
`baseline/8765-codex`、`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`，以及生产 Python
内容摘要 `fc97aa3277e0e9a5144049f95e806b1eb5ad95cd7156069ebcc68162cded6c41`。工作树包含大量既有修改和
未跟踪文件；本审查没有修改任何生产代码、计划、证据账本、测试或既有文档。

## 1. 放行范围

M0 已足以证明 M1 的目标是零生产消费者表面、无调用者在线清除接口和重复事件，而不是删除当前
能力或改写控制权威。M1 实现必须严格限制在计划的 M1-01—M1-05，并逐候选独立提交、独立复核。

本次通过不授权：集合输出行为替换、TransformAdapter 收敛、知识模型更改、实验模型合并、插件拆分、
transport/Hardened 可选化、实例/资格/用途/Effect 审批治理变更。这些分别属于 M2—M6，仍需各阶段
证据和独立审查。M7 以及 R5-M 总体完成当然也未放行。

## 2. Findings

### 阻断项

无。

### 改进项（按风险排序）

#### I-1：M1-05 必须先保住并验证离线完整性，再删除事件表

- 位置：`docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md:174-188`；
  `docs/plans/evidence/R5_M0_BASELINE_AND_CANDIDATE_LEDGER.zh-CN.md:219-229`；
  `src/scidiscovery/artifact_agent/audit.py:96-310`。
- 可达场景：当前 `verify_artifacts()` 在 `audit.py:123-129` 读取完整 snapshot，并在 `:214-238` 验证
  `artifact_events`，同时在同一函数内验证 CAS、Envelope、父链、幂等记录和孤儿内容。若先删除事件
  写入/表而未先收窄 verifier，离线审计会把正常新 Artifact 报为 event cardinality 错误；若整体删除
  `audit.py`，则 CAS、Envelope、父链、幂等和孤儿检测一并丢失。
- 当前证据缺口：当前测试树没有直接调用 `verify_artifacts()` 或 `scan_orphans()` 的测试；计划中的
  “人工损坏 CAS/Envelope/父链/幂等/孤儿仍可检测”是 M1 验收要求，不是已实现事实。
- M1 要求：先完成并通过新的损坏负例，再提交事件表/写入删除。推荐回滚边界为
  `M1-05a audit 收窄+负例` → `M1-05b artifact_events` → `M1-05c approval_events`。已有数据库中的旧表
  继续惰性存在，不增加在线迁移或删表状态机。

#### I-2：M1-02 的消费者账本漏记了一个测试 entry-point 夹具的无效导入

- 位置：`src/scidiscovery/artifact_agent/interfaces/mcp_worker_protocol.py:104-156`；
  `tests/fixtures/plugins/architecture_operation_plugin/architecture_operation_test_plugin/plugin.py:37-40,304`；
  M0 账本 `:185-194`。
- 可达场景：当前生产五插件没有注册 `worker_run_analysis` 或 `worker_fetch_web_evidence`，Local/Hardened
  也没有它们的 handler；但是 architecture fixture 从协议模块导入 `RUN_ANALYSIS_TOOL` 并赋给
  `ANALYSIS_TOOL`。该变量没有进入夹具的 `PluginDefinition.components` 或任何 Operation，因此不是运行
  能力消费者，但直接删除导出常量会先使测试插件 import 失败。
- M1 要求：删除该未使用测试导入/别名，并在 clean-wheel 与测试 entry-point 路径验证；不得为测试保留
  生产兼容别名。同步修正当前的 `docs/SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md:70`，历史审查
  原文不改写。

#### I-3：候选计数和分类呈现应更精确

- 位置：M0 账本 `:170-392`；计划完成门 `:113-124,139-143`。
- 事实：账本实际列出 19 个编号候选（M1 五项、M2 三项、M3 一项、M4 两项、M5 四项、M6 四项），
  不是 17 项。部分“消费者”段落把生产、动态 entry point、测试、当前文档和历史文档压成一句，没有
  逐类给出零值或路径。
- 影响：本次独立扫描没有发现因此产生的错误删除结论，所以不阻断 M1；但后续阶段应维持统一的
  19 项编号，并为实际实施的候选附机器可复核的分类清单，避免把“未列出”误读为“零消费者”。

## 3. 独立基线复算

| 问题 | 独立结果 | 判定 |
|---|---:|---|
| `src/scidiscovery` Python | 101 文件，27,260 行 | 与账本一致 |
| `plugins` Python | 45 文件，22,763 行 | 与账本一致 |
| 生产 Python 合计 | 146 文件，50,023 行 | 与账本一致 |
| 生产树摘要 | `fc97aa3277e0e9a5144049f95e806b1eb5ad95cd7156069ebcc68162cded6c41` | 与账本一致 |
| 插件定义/组件/Operation | 5 / 220 / 46 | 与账本一致 |
| scope | public 26 / support 20 | 与账本一致；同一目录投影 |
| executor | Agent 22 / Transform 20 / Approval 3 / Effect 1 | 与账本一致 |
| 目录摘要 | `4c17c856ba4249d400d8d1455139b2e39588759e16ee1c31e5122b4e97dbb57e` | 与账本一致 |
| Local public Agent | 19/22 支持 | 三项仅因 `agent_collection_outputs` 拒绝 |
| Hardened public Agent | 0/22 支持 | 22 项 native shell；其中 9 项另需 view_image、3 项另有集合输出 |
| Root 公共工具 | 30 | Local/Hardened 相同 |
| 当前通用/后端表 | 21 | 含 Hardened 私有 `active_transport`；不含显式 TCAD socket 的 `submissions` |
| 约束注册表 | 33 个唯一 id | 结构测试通过，`SEC-002` 仍为 `known_issue` |

`pyproject.toml` 及三个生产插件包只发布 `scidiscovery.plugins` 这一组；
`src/scidiscovery/operations/catalog.py:719-739` 只从该组排序加载并一次编译。`public/support/internal/all`
由 `CompiledCatalog.scheduler_projection()` 和 scope 过滤得到，没有发现第二注册表。当前 shell 环境本身
没有已安装的该组 entry point；因此目录数字由五个精确当前 `PluginDefinition` 直接编译，并由
clean-wheel 测试独立覆盖安装态入口，而不是把源码 `PYTHONPATH` 冒充安装发现。

新建临时 Hardened 运行时后，实际枚举到：Artifact 4 表、scheduler bindings 8 表、Run 2 表、
Approval 5 表、Execution 1 表、Hardened dispatch 1 表，共 21 表。Root 30 工具来自
`src/scidiscovery/artifact_agent/interfaces/mcp_root.py:145-180` 的单一 `ROOT_TOOLS` 元组。

## 4. 候选逐项核验

### M1：本次放行

| 候选 | 独立消费者结论 | M1 边界 |
|---|---|---|
| M1-01 Schema/周期状态 | 四个 Schema 模块无生产、插件 entry point 或当前运行消费者；三个 readiness/status 类型仅模块自引用，`ScientificReadiness` 另被一个领域中性测试使用 | 可删；测试改用真实当前对象，不建替代 Schema |
| M1-02 web/analysis Worker 工具 | 只有协议 DTO、工具常量和 `web_fetch.py`；生产五插件不注册、两后端无 handler；存在 I-2 的测试夹具无效导入 | 可删，但同提交清理夹具和当前文档；外部来源的冻结要求本身不删除 |
| M1-03 runtime projection | `RuntimeOperationProjection` 仅定义/导出，`CompiledCatalog.runtime_projection()` 仅被 L1/L5 测试调用；Root 实际消费 `CompiledOperation` 与 `SchedulerOperationView` | 可删；测试直接断言 compiled Operation，不建新投影 |
| M1-04 在线清除 | 四个方法只有服务到存储的内部自调用；Root、CLI、部署、生产插件和测试均无调用 | 可删；不预建离线清理器，不保留别名/转发器 |
| M1-05 重复事件 | `approval_events` 只写不读；`artifact_events` 只有写入和离线 audit 读取；audit 仍保护独立完整性不变量 | 只删事件，保留/收窄 audit；遵守 I-1 顺序 |

因此 M1-01—04 是高置信删除，M1-05 是“删除重复事件、保留独立完整性检查”，不是 `audit.py` 整体
删除授权。M1 不得新增数据库表、Root 工具、Run 状态、Registry、兼容 adapter 或第二离线权威。

### M2—M6：真实性核验完成，但均未放行

| 候选 | 独立事实 | 结论 |
|---|---|---|
| M2-01 参数提取 | 一个主 `scientific_intake` 加三个 collection 端口；参数 audit/coverage/qualification/TCAD author 链真实消费 | 行为替换，不是删除 |
| M2-02 曲线误差诊断 | 一个主 diagnosis 加 plot collection；分析/绘图和诊断验证有真实代码与测试 | Metric/绘图归 deterministic support，科学诊断仍归 Agent |
| M2-03 图证据提取 | 一个主 intake 加 manifest、source panels、overlays、curve tables、validation reports 五个 collection；curve 安装与专项测试真实消费，TCAD 默认 Deck 闭环不直接启动该 Agent | 只能单包+确定性展开或可选化，不能物理删除算法 |
| M3-01 adapter 双层 | TCAD 和 curve 的 `_legacy()`、general/curve 的 `ScientificStateTransformAdapter` 均有生产调用；InGaAs 类无调用但窄评分函数有新 Operation 消费；Root 真实使用 `CompiledTransformAdapter` | 必须逐插件折叠并做字节/父链/成员顺序等价，不得一起删除 |
| M4-01 知识桥 | `transforms.py:148,210-266` 的生产链补造空 parameters、`testable`、`unassessed` 和 rationale | 违反科学语义所有权，应后续消除，但不是 M1 |
| M4-02 intent/plan | `ExperimentDesignIntent` 由通用 Agent/物化器消费；`ExperimentPortfolio` 被 TCAD、curve、表格夹具、打包/物化广泛消费 | 账本“不修改/先做字段所有权审计”正确，不能草率合并 |
| M5-01 公共组件 | TCAD 重注册通用 Schema 与 patch/delete/move 工具；curve 某些路径已跨插件引用 general，另一些路径仍复制 Experiment Schema | 只可收敛所有权，Operation 仍显式授权每项工具 |
| M5-02 curve/figure | TCAD 包依赖完整 curve 包，生产代码真实只跨用曲线合同、bundle、validator、归一化等子集；图证据自身有真实产品链 | 先测净减量再拆；拆包不等于物理删行 |
| M5-03 transport/debug | runtime plugin 按配置选择 socket/command；SSH/Python 3.6 runner 有安装脚本；debug 有真实本地闭环 | 只能可选化/复用生命周期；保留 Effect unknown 查回与收集 |
| M5-04 Hardened/portable | `runtime.py` 顶层导入 Hardened，CLI 顶层导入 portable；Hardened 有纯 MCP Run/恢复/围栏测试，portable 有 CLI 子命令 | 惰性加载/可选安装，不是删除 |
| M6-01 instance/session | 提案、session binding request/candidate、Root/UI 均为生产消费者；current CAS 在 `scheduler_bindings.py:1048` 独立承重 | 只能行为替换；用户显式入口、session 绑定和 current 保留 |
| M6-02 资格合同 | `InputPortSpec` 四字段由编译器和 Root cohort admission 真实消费，通用实验/假设/TCAD 参数/Deck 都声明 | 可折叠为一个 Operation 级不可变值，不能新建资格注册表/表/状态 |
| M6-03 `allowed_input_usages` | 所有生产输出必须声明；编译器、Root producer admission、review/revision 防绕过真实使用 | 删除前必须冻结全边矩阵；review edge、direct revision、资格仍失败关闭 |
| M6-04 Effect 审批断点 | `operation_invoke` 只创建 Execution；独立 Root 工具随后重建审批请求；批准、start、sync 仍分离 | 后续可自动建“请求”，绝不能自动决定或 start |

账本对这些能力的分类总体可靠：没有把 Hardened、远程执行、图证据、Transform 算法、知识/实验科学
语义或 current/qualification/Effect 边界误归为 M1 死代码。

## 5. 对架构、奥卡姆原则和 33 项约束的判断

计划保留一个 `OperationSpec`、一个 `CompiledCatalog`、一个 preflight/invoke、一个 Run 生命周期和一个
Artifact/current 权威；删除候选要求零消费者证据，行为替换要求字节等价或独立新候选，可选化禁止复制
目录和部署事务。这符合奥卡姆剃刀：减少事实和胶水，而不是用新抽象包住旧抽象。

对本轮最敏感的约束检查如下：

- AUTH/PLG/TOP：当前仍为单 entry-point group、单目录与同源 preflight/invoke；M1 不得新增替代投影。
- IMM/LIN：Artifact envelope、CAS、父链、幂等、revision/current CAS 不在删除范围；I-1 是 M1 硬门。
- ROLE/DET：M2—M4 明确保持 Agent 科学判断与 deterministic 展开/Metric 分离；知识桥补造科学语义被正确列为后续高风险候选。
- HIL/CQRS/EFF：M1 不动精确 subject、nonce、HumanDecision、Execution；M6-D 只允许自动创建审批请求，不允许自动决定/start。
- SEC/RES：Hardened 只可可选化；Local 原生工具限制仍诚实保留为 `SEC-002 known_issue`；本次测试以 7 GiB 虚拟内存硬上限串行执行。
- MIG/UI：已有数据库废弃表惰性保留，不增加在线迁移；当前 UI/真实机器发布缺口没有被本次 PASS 伪装成关闭。

M0 因此足以放行一个小而可回滚的 M1，同时没有为通用科研 Agent 或 TCAD 目标引入固定科研 DAG、
核心领域分支、第二权威或虚假物理减量。

## 6. 独立执行的命令与结果

以下命令均串行执行；pytest 前设置 `ulimit -v 7340032`（7 GiB）和 `MALLOC_ARENA_MAX=2`，未使用
pytest 并行插件。

1. `git status --short; git branch --show-current; git rev-parse HEAD`：确认既有 dirty worktree、分支
   `baseline/8765-codex`、HEAD `404aeb1…`。
2. 账本给出的 `find ... | sort -z | xargs -0 sha256sum | sha256sum`：得到生产摘要 `fc97aa…`。
3. 分别对 `src/scidiscovery`、`plugins` 执行排序 `find` + `wc -l`：得到 101/27,260、45/22,763；
   合计 146/50,023。
4. `python scripts/r5_current_metrics.py`：生产规模、Operation 包规模和现行/历史消费者分类可复算。
5. 直接导入五个当前 `PluginDefinition` 并调用 `compile_catalog()`：得到 220 组件、46 Operation、
   scope 26/20、executor 22/20/3/1、摘要 `4c17…`；Local 19/22、Hardened 0/22。
6. 以同一目录临时 `open_runtime(..., worker_backend="hardened")` 并查询各 SQLite
   `sqlite_master`：得到上述 21 表，临时目录退出后删除。
7. 读取 `ROOT_TOOLS` 并核对 Router：Local/Hardened 均为 30 项。
8. 对 M1—M6 符号在 `src`、`plugins`、`deploy`、生产 pyproject、roles、当前 docs、tests 分域执行
   `rg -n`：确认本报告的消费者分类；历史 `docs/plans` 与备份目录不冒充生产消费者。
9. 解析 `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 id：33 个且唯一；随后运行结构测试。
10. `python -m pytest -q` 的聚焦集合：
    `test_architecture_constraint_matrix.py`、`test_l1_minimal_runtime_projection.py`、
    `test_l6_runtime_capabilities.py`、`test_platform_configuration.py`、
    `test_l5_hardened_run_backend.py`、`test_catalog_installed_entrypoint.py`、
    `test_baseline_effect_lifecycle.py`、`test_r4_execution_approval_identity.py`、
    `test_l4_local_tcad.py`、`test_general_transform_operations.py`、
    `test_ingaas_operation_plugin.py`、`test_h2b_domain_boundaries.py`：**64 passed in 52.47s**。
11. `bash -n deploy/install.sh deploy/reinstall.sh deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh`：通过。
12. `git diff --check`：通过。

六份主要输入文件的审查时 SHA-256：

```text
ef82b0df8f056da7d03488bc2d9867f200008882e3a1e7ab5892dd3006a62db1  R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md
2339fe319602acb34aa5685060a6a960cfdf71ee19fca5a00336e5d291187686  R5_M0_BASELINE_AND_CANDIDATE_LEDGER.zh-CN.md
cd0e8e9f0e0907defed8783c89b44bc5626e56187cc55f4161cc842220eda328  CURRENT_PRODUCTION_CODE_REDUNDANCY_ASSESSMENT.zh-CN.md
7d73bd6a1a642e77294c23145648b4e15a5dfe236fa4ee908d8c2aebe9a53f16  ARCHITECTURE.zh-CN.md
bf85c3c43dd8944f81407f87d327212bc74a3b94d6ddd011889713c129707fe7  SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

## 7. 未验证风险

- 没有重复运行账本记录的全量 `200 passed in 79.98s`；本审查独立运行的是与 M0/M1 边界直接相关的
  64 项串行集合。原 200 项结果仅作为已供应的 M0 记录，不作为本审查自行观测。
- 没有运行真实浏览器 UI、真实远程 SSH/VM、真实 Sentaurus solver 或长任务失联恢复；这些不是 M0
  放行 M1 的必要条件，后续 M5—M7 仍必须验证。
- 没有验证论文图数字化科学精度、参数来源科学正确性或三领域统计优势；本次只审结构、消费者、运行
  可达性与边界，没有把工程测试提升为科学资格。
- 无法排除仓库外第三方包对内部 Python 导出（尤其 Worker 协议常量）的非承诺依赖；M1 的 clean-wheel
  和外部插件兼容取舍必须明确记录，不能增加永久兼容别名。
- 当前 `SEC-002` 仍是已知问题；本次 PASS 不把提示约束解释成平台级文件/原生工具沙箱。

## 8. 最终判定

**PASS：M0 足以放行 M1。** M1 实现必须落实 I-1/I-2，逐候选证明净减少并接受独立实现审查。
**M2—M7 全部保持未放行。**
