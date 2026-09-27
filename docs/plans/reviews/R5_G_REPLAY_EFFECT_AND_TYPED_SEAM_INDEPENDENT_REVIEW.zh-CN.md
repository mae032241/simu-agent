# R5-G 历史回放 Effect、类型边界与评分闭环独立审查

日期：2026-08-30  
审查者：未参与本环节实现与运行的独立审查者  
结论：**通过，允许进入多智能体链**

## 1. 审查边界

本轮只审查冻结历史回放的真实本地 UI 决定、Effect/Execution 生命周期、opaque→typed 机械边界、
InGaAs 确定性评分以及恢复不重执行。审查不评价尚未产生的多智能体或单智能体科学结果，也不把
历史回放解释为本轮新 solver 观测。除本报告外，审查者未修改生产代码、插件、测试、冻结清单或
私有运行状态。

审查采用跨边界、变更范围和简化三项规则。所有复测严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

## 2. EvidenceAudit

### 2.1 来源声明

- S1：`tests/fixtures/r5_e2e_tcad/manifest.json`，当前 SHA-256
  `f0336af639fcc32006f8dd0cdbf41f94d32d2d12378afa31d280338bfac2299f`，及其 19 份冻结文件；
- S2：`tests/fixtures/plugins/r5_e2e_tcad_plugin/` 的 pyproject、单一 `PLUGIN`、runtime closure；
- S3：`scripts/r5_g_replay_live.py` 与 `tests/operations/test_r5_frozen_baselines.py`；
- S4：`.scidiscovery/r5-e2e-private/replay-live-20260830-03/` 的 SQLite、CAS、exchange、运行摘要、
  UI 见证、失败见证、恢复报告、当前边界再验证收据和两份指标文件；
- S5：当前 compiled catalog、Root Operation/Approval/Execution 路由、ApprovalService、
  ExecutionBridge 与 ArtifactService；
- S6：`ingaas_fig4` Operation、严格结果 validator、冻结历史 scorer、metric/residual reference；
- S7：`docs/plans/reviews/R5_G_METRIC_PREFLIGHT_INDEPENDENT_REVIEW.zh-CN.md`，仅作为 049 清单与
  历史复算的先前独立来源，不把其 verdict 继承到本轮；
- S8：本轮独立源码探针、SQLite/CAS 探针、当前 Root 负例与串行 pytest 输出。

### 2.2 检查记录

| 检查键 | 结论 | 证据 |
| --- | --- | --- |
| `local_ui_decisions` | 通过；实例创建与执行授权均有 local UI session、一次性 nonce、封存决定和精确 subject 父链 | S4、S5 |
| `effect_execution_lifecycle` | 通过；compiled Effect 产生一个 execution，授权后提交并收集四项精确历史输出 | S1、S2、S4、S5 |
| `recovery_no_reexecution` | 通过；恢复前后 execution 均为同一个 collected 记录，当前再验证也保持计数 1 | S3、S4 |
| `single_plugin_authority` | 通过；两个评估 Operation 只由一个 `scidiscovery.plugins` entry point 和同一 `PLUGIN` 提供，核心无 id/Schema/角色分派 | S2、S5、S8 |
| `exact_request_admission` | 通过；Effect preparation 与 qualification 共用字节摘要、大小和严格 Schema validator；同字段异字节请求从真实 Root 失败且无输出绑定 | S1、S2、S3、S4、S8 |
| `typed_profile_integrity` | 通过；typed 输出与 opaque PLX 字节、SHA、大小完全相同，并精确绑定 frozen request 与 opaque output 两父 | S1、S2、S4 |
| `wrong_profile_fail_closed` | 通过；错误 PLX 摘要/大小从真实 Root executor 路径拒绝，未形成 typed 输出 | S2、S3、S8 |
| `scorer_typed_lineage` | 通过；评分第五父对象是 typed candidate，另四父与冻结端口一致；结果通过严格 Schema | S1、S4、S6 |
| `historical_metric_consistency` | 通过；当前指标 SHA 为 `7f3a5fe6…`，与独立历史复算公共数值最大差 `8.88e-16`，总门仍为 false | S4、S6、S7、S8 |
| `manifest_and_digest_binding` | 通过；当前 closure 四文件摘要、Effect/qualification/scorer 三摘要与 manifest、catalog、DB/再验证收据一致 | S1、S2、S4、S5、S8 |
| `replay_claim_scope` | 通过；UI、capability、目标、报告和 manifest 均声明历史复制边界，无新 solver 或机制归因 | S1、S2、S3、S4 |
| `occam_and_extension_boundary` | 通过；新增边界留在评估插件，无核心表、注册表、状态机、审批或执行旁路；恢复分支仅为一次性验收驱动 | S2、S3、S5、S8 |

## 3. 关键独立核验

### 3.1 UI 决定和 Effect 确实发生

私有数据库有两个 ApprovalRequest：研究实例创建与历史执行授权。两次决定的
`authentication_method` 均为 `local_ui_session`，同一受控 UI session 分别选择
`create_instance` 和 `authorize_execution`；决定 nonce 各消费一次。执行审批的 review document
明确展示 executor、preparation profile 和冻结请求，subject 父链为 compiled execution request 与
SHA `7a836232…` 的 replay request。验收脚本自身没有代写 UI 决定的 HTTP 路径，只输出本地 URL 并
轮询封存状态。

Execution 数据库只有一个记录：executor 为 `r5_e2e_fixture:replay`，external run id 为冻结 replay
id，终态为 `collected`。四个 execution output 的 SHA、大小和媒体类型分别匹配 manifest 的 PLX、
TDR、log 与 runtime manifest；每个输出都绑定同一个 execution request 和 replay request，结果
Artifact 再绑定四输出。全部 23 个当前 Artifact envelope 的 20 份唯一 CAS payload 均通过字节大小
和 SHA 复核。

数据库能证明的是“经本地 UI 会话认证并封存的用户决定”；它不能也无需从文件系统证明操作者的
生物身份。这个边界与框架所称人工决定一致，且没有聊天文本转批准或调试阶段代审。

### 3.2 恢复只继续确定性 support 工作

首次回放已在 `23:29:15Z` 收集四项输出；后续 typed/metric Artifact 分别在 `23:40:50Z` 和当前
边界再验证的 `23:48:41Z` 产生。恢复代码先要求原 execution 已 collected 且原 UI 决定已授权，
随后只查询 outputs 并调用两个 support Transform；它不装配 ExecutionBridge，也不调用 start/sync。
数据库始终只有原 execution 一行，当前收据独立记录 before/after 均为 1。因此恢复没有再次复制
或重新执行 Effect。

`post_collect_failure.json` 对最初 harness 误以为 outputs 投影含 SHA 的具体原因只有运行方见证，
没有保留原 traceback。本轮不以该具体调试原因证明通过；材料事实由数据库独立证明：输出已经
collected，科学解释尚未产生，恢复没有新 execution。

### 3.3 类型提升首轮阻断及修复

首轮候选的 `qualify_replay_profile()` 只解析 `ReplayRequest` 的 Literal 字段。独立反例证明，字段
相同但压缩编码或增加前导空格、因而 SHA 不同的请求也会被接受。这不满足任务要求的“exact
request”，并会让 typed Artifact 父链落到未冻结的请求摘要，因此首轮不能放行。

当前修复新增一个共享、无状态的 `validate_replay_request(raw)`：先要求 267 字节和 SHA
`7a836232…`，再做严格 Schema 验证；Effect preparation 与 qualification 共同调用，没有平行策略。
独立源码探针现确认 frozen 请求通过，而同字段 compact 请求 SHA `e6b9035d…` 被拒。

更重要的是，当前同一 collected 数据库上的真实 Root 再验证已经运行该修复：

- 正例 typed 输出两父依次为 frozen request `7a836232…` 与 opaque PLX `62dbca930…`；
- typed 输出仍为 91063 字节、SHA `62dbca930…`，Schema 提升为
  `ingaas.fig4-zinc-profile-plx.v1`；
- compact 请求作为独立输入登记后，`operation_invoke` 返回 `executor_component_failed`，且
  `alternate_request_boundary_qualification` 没有 Artifact binding；
- Execution 行数前后均为 1。

因此阻断已在当前源码、安装态测试和真实 Root/DB 三层关闭。

### 3.4 当前 manifest、运行时代际和来源诚实性

真实 Effect 在 pre-qualification manifest SHA `049ca4cf…` 下执行；该代际及当时四文件 closure 已
由上一关独立冻结核验。本轮 post-collection 类型边界加入后，当前 manifest 为 `f0336af6…`，当前
runtime implementation 为 `1959486f…`。当前边界再验证收据同时声明先前恢复报告 SHA 和这两个
当前摘要，没有把新 closure 倒填成 Effect 执行时的来源。

当前编译摘要为：

```text
r5.fixture.fig4-replay.v1                    9fe27da331e2…
r5.fixture.fig4-replay-profile.qualify.v1    38cec0d16023…
ingaas.fig4-baseline-recovery.v2             50ca636a68d9…
```

manifest、执行审批 compiled identity、typed/metric Artifact 标签及当前 catalog 对应一致。当前
manifest 的 19 项持久文件和四项 plugin closure 摘要全部复算通过。报告明确分开 Effect 的 049
代际与当前 support 再验证的 f033 代际，因此没有声称一次 execution 使用了事后修改的代码。

### 3.5 评分使用 typed 对象且不扩大结论

当前边界 metric 的有序五父为 scorer project、curve bundle、target metrics、baseline PLX 和
**typed candidate**，最后一项不是 opaque execution output。metric bytes 与首次指标逐字节相同，
SHA 为 `7f3a5fe6…`，当前严格 validator 接受。

相对冻结历史 metric reference，公共共同字段无非数值差异，最大数值绝对差为 `8.88e-16`，不跨越
任何阈值。六个 recovery 子检查中仅 target-front-RMS 通过，总 `baseline_recovery.pass=false`。
这只复现和定位历史差异，不支持网格、solver 或物理机制归因，也不接受物理模型。

## 4. 插件边界与复杂度判断

评估能力只通过：

```text
scidiscovery.plugins
  -> r5_e2e_tcad_plugin:PLUGIN
     -> public historical replay Effect
     -> support exact typed-profile Transform
```

产品 `src/`、四个生产插件和部署脚本均无这两个 Operation id、冻结 hash 或调度分支。public/support
是同一 compiled catalog 投影；runtime factory 只贡献现有 ExecutionBridge 的 adapter。类型提升不
创建服务、表、缓存、目录、审批或第二执行生命周期，评分仍由 InGaAs 插件拥有。

验收 runner 当前 929 行，插件声明/runtime 合计 632 行，绝对体量不小；但它们全部位于评估专用
fixture/script，复杂度来自真实 UI、daemon、恢复见证与正负例，而没有进入产品控制面。此时把恢复
逻辑或 exact-hash 规则抽进通用核心反而会造成领域泄漏。合理边界是 R5-G 完成后把 runner 当作
冻结验收资产，不把其一次性 `reverify-current-boundary` 分支发展成通用恢复框架。

## 5. 独立命令结果

```text
pytest -q tests/operations/test_r5_frozen_baselines.py \
  tests/operations/test_ingaas_operation_plugin.py
=> 首轮当前候选 12 passed in 42.70s

精确请求阻断修复后：
pytest -q tests/operations/test_r5_frozen_baselines.py
=> 7 passed in 35.79s

当前源码 exact/compact request 独立负例
=> frozen SHA 7a836232… 通过；同字段 compact SHA e6b9035d… 拒绝

当前 compiled catalog 探针
=> Effect 9fe27da3…；qualification 38cec0d1…；scorer 50ca636a…

当前 manifest/19 文件/4 closure 文件摘要复算
=> 全部匹配，无遗漏

当前私有 SQLite/CAS 探针
=> executions=1 collected；typed 两父；metric 五父；23 envelopes/20 unique payloads 全部完整；
   compact request 有输入 binding、无 qualification 输出 binding

当前 metric strict validator + 历史 reference 比较
=> SHA 7f3a5fe6…；最大数值绝对差 8.88e-16；无非数值差；总门 false

git diff --check -- tests/fixtures/plugins/r5_e2e_tcad_plugin \
  tests/fixtures/r5_e2e_tcad/manifest.json \
  tests/operations/test_r5_frozen_baselines.py scripts/r5_g_replay_live.py
=> 通过
```

没有重复全仓回归：当前变更只涉及评估插件、冻结 manifest、拥有者测试与验收脚本，真实 UI/daemon/
Execution/Root 已由当前私有运行和 clean-wheel 专项覆盖；生产核心字节未因本关修改。

## 6. 门禁结论

**结论：通过，允许进入多智能体链。**

首轮唯一阻断——同语义但异字节请求可被提升——已由 Effect/qualification 共用的 exact-byte
validator、clean-wheel 负例和同一 collected DB 的真实 Root 再验证闭合。审批、Effect、四输出、
类型提升、评分与恢复边界均有精确身份和父链；没有第二插件权威、核心硬编码、执行重放、Schema
冒充或科学结论扩大。

本结论只放行 R5-G 冻结多智能体科学链；**不判定多智能体科学内容通过，不放行单 Agent 比较，也
不表示 R5-G 或 R5 已完成。** 后续 Agent 输出、独立科学审查、量表评分和预算实测仍是未来证据。
