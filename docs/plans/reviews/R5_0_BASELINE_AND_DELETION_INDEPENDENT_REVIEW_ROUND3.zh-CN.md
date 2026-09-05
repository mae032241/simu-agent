# R5-0 权威语料、基线与删除清单第三轮独立复审

日期：2026-08-29  
审查对象：第二轮报告唯一 F3-R2 阻塞及 19 项记录修正  
审查性质：未参与实现的增量插件、审批、执行与安装态复审  
最终结论：**通过（pass）**  
阶段放行：**只放行 R5-A1，不放行 R5-A2**

## 1. 结论

第二轮唯一阻塞已经闭合。新增内容是评估环境专用的标准
`scidiscovery.plugins` 闭包 `r5_e2e_fixture`，不是生产 core 的特判：它声明一个公开 Effect
Operation `r5.fixture.fig4-replay.v1`、一个运行时工厂、一个 `historical_replay` capability 和一个
固定审批 projector。运行时工厂只在 control 模式贡献 `r5_e2e_fixture:replay` adapter；adapter
实现完整 `ExecutionAdapter` 协议，并把自身明确限定为历史字节重放而非 solver。

本轮从 clean wheel 独立复跑确认，闭环真实经过：

```text
scidiscovery.plugins 安装发现
→ compile_installed_catalog
→ runtime factory contribution
→ operation_invoke
→ ExecutionRequest
→ 本地 ApprovalUI HTTP 决定
→ ExecutionBridge start/sync/collect
→ 四个内容寻址 Artifact
```

四个结果的大小和 SHA-256 均与预冻结 manifest 一致。测试没有直接 import adapter 来代替统一入口，
也没有恢复 `execution_request_create` 作为第二行为权威。评估插件只进入独立 `r5_e2e` 安装组合，
没有进入 core、full 或 full+InGaAs；三种生产目录的冻结数量和摘要仍保持原值。

manifest 已冻结 Effect 的 operation id、version、digest、输入/输出端口、审批权威、runtime binding、
preparation profile，以及插件四个文件的 SHA-256。实施记录中的持久文件数量已从错误的 18 修正为
实际 19，专项测试逐项核验全部 19 个文件。

没有发现需要继续打回 F3-R2 的证据。第二轮已经通过的 F1、F2、F4 按任务要求未重新展开。

## 2. EvidenceAudit

### 2.1 来源声明

| 证据键 | 唯一来源 |
| --- | --- |
| S1 | `docs/plans/reviews/R5_0_BASELINE_AND_DELETION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` |
| S2 | `tests/fixtures/plugins/r5_e2e_tcad_plugin/pyproject.toml`、`plugin.py`、`runtime.py`、`__init__.py` |
| S3 | `tests/fixtures/r5_e2e_tcad/manifest.json`、`replay_request.json` 及 manifest 声明的 19 个持久文件 |
| S4 | `tests/operations/conftest.py`、`tests/operations/test_r5_frozen_baselines.py` |
| S5 | `docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md` |
| S6 | 本轮 7 GiB 严格串行命令输出 |

### 2.2 紧凑核对表

| 核对问题 | 结果 | 证据 |
| --- | --- | --- |
| 是否只使用唯一标准插件入口 | 通过；唯一 group 为 `scidiscovery.plugins` | S2、S4 |
| Effect Operation 是否在 clean wheel 编译目录可见 | 通过；id/version/digest/ports 与 manifest 一致 | S2、S3、S4、S6 |
| runtime factory 是否贡献 exact adapter binding | 通过；control 贡献 `replay`，Worker 不获得副作用 adapter | S2、S3、S4 |
| adapter 是否实现完整协议并诚实声明能力 | 通过；含 `capabilities/prepare/submit/status/cancel/collect`，kind 为 `historical_replay` | S2、S4 |
| 是否真实经过统一 Effect 创建入口 | 通过；由 `operation_invoke` 创建带 compiled identity 的 ExecutionRequest | S2、S4、S6 |
| 是否真实经过本地审批边界 | 通过；固定 projector 校验 identity，决定经 ApprovalUI HTTP POST 写入 | S2、S4、S6 |
| 是否真实完成 Execution 生命周期和 Artifact 登记 | 通过；start/sync 后 collected，四输出字节摘要匹配 | S3、S4、S6 |
| 是否污染 core/full/full+InGaAs | 通过；评估 wheel 仅安装于独立 `r5_e2e` 环境，三组快照门保持通过 | S3、S4、S6 |
| 插件闭包和请求身份是否预冻结 | 通过；四个插件文件、请求、adapter、Operation 合同均有精确摘要 | S2、S3、S4 |
| 19 项记录是否修正并可机械复核 | 通过；manifest 实际 19 项，实施记录与测试均写为 19 | S3、S4、S5、S6 |
| 是否增加第二注册表、状态机或伪造科学父对象 | 未发现；只组合既有 Plugin/Approval/Execution 权威 | S1、S2、S3、S4 |
| 是否偏离轻量、低成本、可插件扩展目标 | 未发现；实现局限于一个评估插件闭包，无生产 core 分支 | S2、S4 |

## 3. 关键实现证据

### 3.1 最小插件闭包

`plugin.py:26-132` 只声明一个 PluginDefinition 和一个 Operation。Operation 的唯一输入是严格冻结的
`replay_request`，唯一输出是核心 `ExecutionRequest`，外部副作用必须经过精确审批。没有新的
数据库对象、注册表、调度拓扑或科学 Schema 家族。

`runtime.py:58-62` 用 Literal 约束 request 中的 fixture、active bundle 和 source project 身份；
`runtime.py:105-130` 返回明确的历史重放 capability；`runtime.py:208-227` 把 runtime binding、
preparation profile 和 payload port 组成一个标准 EffectExecutorPlan；`runtime.py:230-280` 的固定
projector 同时校验 executor、profile 和完整 compiled identity。

### 3.2 真安装与真生命周期

`tests/operations/conftest.py:54-120` 先把评估插件构建成 wheel，再只把它安装进独立 `r5_e2e`
环境。probe 删除 `PYTHONPATH` 并断言核心包来自虚拟环境，因而不是源码目录导入假阳性。

`test_r5_replay_effect_uses_compiled_ui_execution_lifecycle` 通过安装态目录加载 runtime contribution，
调用 Root 的 `operation_invoke`，创建精确执行审批，通过 loopback ApprovalUI 的 HTTP 表单作出决定，
再调用 execution start/sync/outputs。最终从 CAS 读取每个登记 Artifact，并与四个冻结 SHA-256 比较。
这正面覆盖了第二轮指出的真实入口缺口。

### 3.3 范围与科学边界

该 capability 的公开内容明确写明不执行 solver；Operation 的 `not_for` 明确禁止把重放当作新科学
证据。manifest 仍保留“不伪造 legacy plan/capability/current-review、不把领域 metric 冒充通用
curve report”的边界。修复没有回退到缺失的 generic package/attestation/curve-score 链。

## 4. 本轮验证

所有 Python/pytest 命令均使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

严格单进程串行，无并行 pytest：

| 检查 | 本轮结果 |
| --- | --- |
| `git diff --check` | 通过 |
| `python scripts/r5_baseline_metrics.py` | 成功复算 |
| `pytest -q tests/operations/test_r5_frozen_baselines.py` | `6 passed in 28.54s` |
| R4 13 文件聚焦矩阵 + R5 专项 | `127 passed in 53.87s` |

本轮没有重复全仓 251 项。返修局限于测试评估插件、夹具、测试装配和实施记录；专项测试已经通过
clean-wheel、真实 UI/Execution 生命周期和生产目录隔离覆盖精确缺口，没有触发修改共享生产合同后
必须重跑全仓的条件。真实 R5-G 科学 Agent、daemon 和 solver 仍是后续执行要求，不是 R5-0 当前
观察，也不应被本报告提前宣称完成。

## 5. 最终结论

**通过（pass）**。

第二轮唯一 F3-R2 阻塞及 19 项记录错误均已修复；R5-0 完成门成立。**允许进入 R5-A1**。本结论
不放行 R5-A2，也不代表 R5-G 科学效果回归已经执行。
