# R5-0 权威语料、基线与删除清单第二轮独立复审

日期：2026-08-29  
审查对象：首轮报告冻结的 F1—F4 返修候选  
审查性质：未参与实现的增量跨边界、复杂度、安装态和科学夹具复审  
最终结论：**打回（revise）**  
阶段放行：**不放行 R5-A1**

## 1. 结论摘要

F1、F2、F4 已按首轮精确要求闭合：双语事实已修正；五类消费者、职责后继与完整结构快照已经
机械冻结；三种 clean-wheel 目录的数量和摘要已成为专项硬门。F3 中的科学边界也有实质改进：
Fig.4 小任务明确把目标降格为用户冻结目标，禁止借 InAlAs、candidate、Fig.7 或网格相关性制造
论文事实或因果结论；精确 Operation、端口、skip、预算、来源、scorer 和 replay 字节均已冻结。

历史导出缺少 exact legacy experiment plan、capability 和当前 review Schema。拒绝伪造或重新
挂接这些父对象，并把必做机械链收缩为 `ingaas.fig4-baseline-recovery.v2`，是诚实、最小且可执行
的选择，不是本轮阻塞。独立把冻结的 project、curve、target、baseline PLX 和 replay PLX 送入
`CompiledTransformAdapter` 后，领域 Operation 正常产出 `metric_report`；恢复门仍失败，最大绝对
残差为 `1.0786323340881445` decade，与冻结历史指标一致。

仍有一个 F3 实现断点：冻结的 replay adapter 可以被测试代码直接调用，却没有对应的 compiled
Effect Operation 或 runtime factory contribution；它还缺少 `ExecutionAdapter` 协议声明的
`capabilities()`。当前唯一已编译的 TCAD Effect 是 `tcad.study.execute`，其输入和 preparation
profile 固定为 `tcad.reviewed-deck-package.v2`，不能合法消费本夹具的 replay request。R5-A2 又将
删除直接 `execution_request_create`。因此按当前冻结物，在 R5-G 时不存在一条从
`operation_invoke` 创建 replay Execution、经 UI 授权、start/sync/collect 并登记四个输出的真实
入口；直接导入夹具类的 6 项绿灯不能证明该生命周期。

这不是要求恢复缺失的通用 package/attestation/curve-score 链，也不要求真实 Sentaurus。最小修复
只需为同一冻结重放增加一个评估专用的标准插件闭包，并用真实 Effect 入口做一条有界生命周期
测试。修复前，R5-0 自己承诺的“已登记 replay adapter 跑通同一 Execution 生命周期”尚不可执行。

## 2. EvidenceAudit

### 2.1 来源声明

| 证据键 | 唯一来源 |
| --- | --- |
| S1 | `docs/ARCHITECTURE.md`、`docs/ARCHITECTURE.zh-CN.md` |
| S2 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 8.6、10、11 节 |
| S3 | `docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md` |
| S4 | `scripts/r5_baseline_metrics.py`、`tests/fixtures/r5_structure_baseline.json`、`tests/fixtures/r5_structure_inventory.json` |
| S5 | `tests/fixtures/r5_e2e_tcad/manifest.json`、`task.zh-CN.md`、`rubric.json`、`replay_request.json`、`replay_adapter.py` |
| S6 | manifest 声明的 19 个持久文件、InGaAs scorer 内嵌合同及 `plugins/ingaas_fig4` |
| S7 | `src/scidiscovery/artifact_agent/execution_bridge.py`、`src/scidiscovery/operations/invoke.py`、TCAD Effect Operation 与 runtime factory |
| S8 | `tests/operations/test_r5_frozen_baselines.py`、13 文件聚焦矩阵及本轮受限串行命令输出 |

### 2.2 紧凑核对表

| 核对问题 | 结果 | 证据 |
| --- | --- | --- |
| F1 双语只陈述 R4 已实现事实并标明 R5 债务 | 通过 | S1 |
| F2 五类精确消费者、替代权威和参数纵切面是否冻结 | 通过 | S3、S4 |
| F2 三重口径是否可复算并防搬移/压行 | 通过；后继表须随未来拆分追加，生产总量继续防整体搬移 | S2、S3、S4、S8 |
| F4 core/full/full+InGaAs 数量和摘要是否为 clean-wheel 硬门 | 通过 | S3、S4、S8 |
| Fig.4 文件是否同源、持久、hash/size 正确且来源边界诚实 | 内容通过；manifest 实为 19 项，实施记录误写 18 项 | S3、S5、S6、S8 |
| exact Operation、端口、skip、预算和 scorer 是否冻结 | 通过 | S5、S6、S8 |
| 不伪造 generic plan/capability/current-review 是否合理 | 通过；缺失父对象不能由验收夹具补造 | S2、S3、S5、S6 |
| exact InGaAs scorer 能否对冻结真实输入执行 | 通过；本轮真实编译调用复算失败门和残差 | S5、S6、S8 |
| replay adapter 是否能通过 R5-G 要求的统一 Effect/Execution 入口执行 | 不通过 | S2、S5、S7、S8 |
| 私有状态和脱敏交付边界是否分离 | 通过；实际 secret/release 负例仍是 R5-G/R5-F 未来门 | S2、S3、S5 |
| 测试与 7 GiB 串行约束是否可复核 | 通过；本轮复跑 6/127，未重复无必要全仓 | S3、S8 |
| 是否偏离 33 项约束、通用 AI 科学家目标或过度设计 | 主体未偏离；当前断点反而绕开了唯一 Operation 权威 | S1、S2、S5、S7 |

## 3. 唯一阻塞发现

### F3-R2（高）：replay adapter 有实现字节，但没有可到达的统一执行闭包

`tests/fixtures/r5_e2e_tcad/replay_adapter.py:24-104` 实现了
`prepare/submit/status/cancel/collect`，会在复制四个输出前核对路径、大小和 SHA-256；这证明其
机械边界本身合理。可是：

1. `ExecutionAdapter` 在 `execution_bridge.py:27-44` 还要求 `capabilities()`，夹具类没有实现；
2. manifest 的 mandatory Operation 列表只包含 Agent、Transform 和 evidence approval，没有一个
   Effect Operation 指向 `r5_fixture:fig4_historical_replay`；
3. 当前 TCAD runtime factory 只贡献 `tcad` adapter，`tcad.study.execute` 只接受 reviewed package
   并返回 `tcad.reviewed-deck-package.v2` preparation profile；
4. 专项测试在 `test_r5_frozen_replay_adapter_returns_only_declared_bytes` 中直接 import 并调用该类，
   没有经过 `operation_invoke`、ExecutionRequest、精确 UI approval、ExecutionBridge start/sync 和
   结果登记。

所以“类的方法可以运行”并不等于“R5 删除旧 Root 创建面后仍可通过唯一行为权威运行”。若到 R5-G
才临时决定如何注册，会破坏本阶段冻结 exact Operation 和预算/来源合同的目的。

另有一项同属 F3 的机械事实错误：manifest 的 `files` 数组共有 19 项，专项测试也实际遍历 19 项，
但实施记录第 7 节写成“18 个持久科学输入”。这不影响字节完整性判断，但必须把记录改为 19，不能
让后续审查按错误分母验收。

### 精确最小修复

只修 F3，不重开 F1/F2/F4，也不补造历史父对象：

1. 在测试夹具范围增加一个仅供 R5-G 环境安装的标准 `scidiscovery.plugins` 插件定义；只包含一个
   replay Effect Operation、请求 Schema、固定审批 projector、effect component 和 runtime
   factory。不得加入生产 core/full 安装组合，不得新建 entry-point group、表或生命周期；
2. Effect 的唯一 payload 是当前已冻结 `replay_request.json`，executor/profile 必须解析为当前
   adapter id/profile；adapter 补齐一个明确标为 `historical_replay` 的有界 capability，不得冒充
   Sentaurus solver capability；
3. manifest 把该 exact Effect Operation id、输入端口、输出、UI 审批和 runtime binding 加入机械
   合同，并更新受影响摘要；InGaAs scorer 仍保持现有五输入，不增加 generic package、attestation
   或 curve report；
4. 增加一条严格串行测试：从 clean-wheel 的评估插件目录编译目录，经 `operation_invoke` 创建
   Execution，经现有审批/执行服务和该 adapter 完成 start/sync/collect，最后只登记四个已冻结摘要。
   测试不得直接把适配器调用当作这条入口证据；
5. 把实施记录的“18 个持久科学输入”改为 19，更新 R5-0 记录与专项测试计数，然后只复跑 R5 专项
   和 13 文件聚焦矩阵。若改动仍局限测试插件、
   夹具和文档，无需再次重复全仓；若触及生产 Effect/Execution 代码，则必须重跑全仓。

## 4. 已闭合且不应回退的内容

- 双语已正确写成“一个入口返回一个 PluginDefinition，同一发行包可发布多个定义”，并把 operation
  identity 限定到已迁移 Operation 创建的记录。
- 五类消费者快照区分生产、动态入口、测试、当前文档和历史文档；历史文档只允许单调保留，其他
  类别精确比较。设备参数 Schema/validator/Operation/legacy bridge、runtime/Codex/daemon/install、
  旧 Root 工具、producer family、readiness/profile/context 都有阶段和唯一后继。
- R0 职责聚合、operations 全包、全部生产 Python 和部署脚本分开统计；冻结生成器与完整 inventory
  摘要，不能靠只更新小型数字快照绕过。
- core/full/full+InGaAs 分别为 `32/49/50` 个 Operation，scope 为 `18+14`、`23+26`、`23+27`；
  三组完整 `id=digest` 摘要由无源码依赖的安装态 probe 比较。
- Fig.4 任务使用 19 个持久文件；目标是用户定义冻结目标而非独立论文证据，网格只作 prior signal，
  replay 不是新求解。量表、双路预算和私有/交付目录边界均已预冻结。
- 不运行不兼容的通用诊断 Operation 是正确的 fail-closed 行为。诊断内容由真实科学 Worker 封存
  对象和独立量表评价；不能为追求形式拓扑伪造 metric Schema。

## 5. 本轮实际验证

所有 Python/pytest 命令都使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

严格单进程串行，无并行 pytest：

| 检查 | 结果 |
| --- | --- |
| `git diff --check` | 通过 |
| `python scripts/r5_baseline_metrics.py` | 成功复算结构 inventory |
| `pytest -q tests/operations/test_r5_frozen_baselines.py` | `6 passed in 23.88s` |
| R4 13 文件聚焦矩阵 + R5 专项 | `127 passed in 49.40s` |
| 冻结真实五输入经 compiled InGaAs transform 调用 | 成功；`metric_report`，恢复门 false，最大残差 `1.0786323340881445` |
| 当前全仓 `251 passed` | 实现者已有记录；本轮按增量范围未重复，未发现触发全仓复跑的生产变更 |

本轮没有启动 daemon、浏览器、Codex 科学 Agent 或真实 solver；它们属于 R5-G，不应在 R5-0
冒充完成。这里要求的只是让已经冻结的 replay 闭包在未来真实入口上可到达。

## 6. 最终结论

**打回（revise）**。

F1、F2、F4 通过并保持冻结；F3 的来源、评分和不伪造边界通过，但 replay Execution 真实入口未
闭合。完成第 3 节的唯一最小修复并复审前，**不放行 R5-A1**。
