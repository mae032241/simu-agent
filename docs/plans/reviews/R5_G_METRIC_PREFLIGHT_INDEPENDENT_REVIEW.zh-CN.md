# R5-G 冻结确定性指标复算独立审查

日期：2026-08-30  
审查者：未参与本环节实现与运行的独立审查者  
结论：**通过（仅放行历史 replay Effect/UI 环节）**

## 1. 审查边界

本轮只审查当前冻结字节下的 Fig.4 历史输出确定性指标复算，以及运行前删除 TCAD
author/reviewer 两个不适用输入绑定的最小拓扑修订。审查不评价后续多 Agent、单 Agent、真实
Sentaurus 执行或科学效果，也不把本次历史 PLX 重放解释为新的 solver 观测。除本报告外，审查者
未修改生产代码、测试、冻结清单或阶段状态。

所有复测严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

## 2. EvidenceAudit

### 2.1 来源声明

- S1：`tests/fixtures/r5_e2e_tcad/manifest.json`，SHA-256
  `049ca4cf5e520442191cf8f652da6ca27ac13401919214269da23ff1a13d37f2`；
- S2：S1 声明的 19 份冻结文件、4 份评估专用 replay 插件文件及嵌入
  `SCORER_CONTRACT.v2.json`；
- S3：`.scidiscovery/r5-e2e-private/metric-preflight-20260830-03/` 的摘要、公开指标、SQLite、
  CAS 和权限元数据；
- S4：`.scidiscovery/r5-e2e-private/metric-preflight-20260830-01/failure.json` 及该轮 SQLite；
- S5：当前 `ingaas_fig4` Operation/transform/结果 Schema、TCAD Operation 声明与编译目录；
- S6：冻结历史 scorer、`historical_metric_reference`、`historical_residual_reference`；
- S7：`docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md` 当前运行前修订记录；
- S8：`tests/operations/test_tcad_operation_plugin.py`、
  `tests/operations/test_r5_frozen_baselines.py` 及本轮独立命令输出。

### 2.2 检查记录

| 检查键 | 结论 | 证据 |
| --- | --- | --- |
| `frozen_source_integrity` | 通过；19 份冻结文件和 4 份 replay 插件文件的 SHA/大小均匹配 | S1、S2 |
| `catalog_identity` | 通过；当前编译 Operation id/version/digest 为 `ingaas.fig4-baseline-recovery.v2`/`1`/`50ca636a…`，五入一出合同匹配 manifest | S1、S3、S5、S8 |
| `database_parentage` | 通过；03 仅登记五个输入和一个指标输出，输出具有有序五父链、精确 invocation fingerprint 与 Operation 标签 | S1、S3 |
| `output_integrity_schema` | 通过；输出为 2052 字节、SHA `7f3a5fe6…`，当前严格结果 validator 接受，当前 scorer 独立再算得到逐字节相同输出 | S2、S3、S5 |
| `numeric_reproduction` | 通过；冻结历史 scorer 再算的 metrics/residual CSV 摘要分别精确等于历史两份参考；当前公开共同数值最大绝对差为 `8.88e-16` | S2、S3、S6 |
| `gate_consistency` | 通过；六项阈值布尔值、总 `pass=false`、残差区间及输入摘要均由冻结合同和原始 PLX 复算支持 | S2、S3、S5、S6 |
| `replay_claim_boundary` | 通过；03 无 Task、Approval 或 Execution，输出只声明确定性定位/复现且拒绝因果归因和物理模型接受 | S1、S3、S5 |
| `failed_harness_truthfulness` | 通过；01 只登记五个输入，无输出、父链、Task、Approval 或 Execution；失败原因与 compiled `text/csv` 端口一致 | S4、S5 |
| `topology_amendment` | 通过；只删除两条不满足完整参数 cohort 的重复可选绑定，experiment plan 与独立 plan review 保留，生产 OperationSpec 和参数资格未放宽 | S1、S5、S7、S8 |
| `private_evidence_boundary` | 通过；01/03 运行根均为 `0700` 且 `.scidiscovery/` 被 Git 忽略 | S3、S4 |

## 3. 核心核验

### 3.1 当前目录、输入与谱系一致

当前源码编译的目标 Operation 摘要为
`50ca636a68d9a048f551d74535ba2c53dec6e4050157cd57181b3def6ec25ab9`。其输入顺序为
`scorer_project`、`curve_bundle`、`target_metrics`、`historical_baseline`、
`candidate_profile`，每个端口基数均为 1；媒体类型分别与 manifest 和数据库登记一致。唯一输出
是 `metric_report`。

03 的 Artifact 数据库有 6 个 envelope、5 条 parent link 和 6 条幂等记录。输出父链位置 0—4
与上述编译端口顺序及五个冻结 SHA 一一一致；输出标签同时绑定 Operation id/version/digest、输出
端口和 invocation fingerprint。Scheduler 只有同一实例的五个输入绑定和一个输出绑定。Task、
worker session、Approval、Execution 表均无记录，因此没有隐藏 Agent、批准或外部执行路径。

### 3.2 输出 Schema 与原始曲线复算闭合

审查者从 manifest 五个精确文件直接调用当前无状态 scorer，再由当前严格 Pydantic validator
验证，所得 canonical bytes 与 03 的公开输出逐字节相同：

```text
SHA-256 = 7f3a5fe6f1c7614e5ce82d9fd429947b68bfc4132148737dc4bb189c1e4b53aa
size     = 2052
```

另以冻结的历史 scorer 从原始 baseline/replay PLX、曲线表、目标指标和运行伴随文件独立复算，
新生成的 `metrics.json` 与 `residuals.csv` 摘要分别精确为：

```text
9849b697c83351fc079df5fb0ba468f50a3fd777270d88f75f6debead4e56a0a
fbf39c5d94f0b6b4b8b640bfaf1a078c0f7f5552ebb310c0b5d94f4ab7a7ec92
```

它们就是 manifest 冻结的历史 metric/residual reference。当前 Operation 发布的是该完整历史报告
的有界公共子集，并用 `candidate_metrics` 替代历史字段名 `replay_metrics`。共同非数值字段无差异，
29 个共同数值叶的最大绝对差仅 `8.88e-16`，属于同一 binary64 计算的末位表示差异，不跨越任何
阈值，也不改变六项检查或总 verdict。

复算支持的材料结论只有：baseline 原始 PLX 在 `1e-9 decade` 门内复现冻结 baseline 曲线；本次
replay 相对 baseline 的 recovery 总门失败，其中只有 target-front-RMS 子门通过。报告没有将失败
归因于网格、solver 或物理机制，也没有接受模型。

### 3.3 01 失败没有被冒充科学观察

01 的数据库只有五个冻结输入 Artifact 和五个实例绑定；不存在指标 Artifact、parent link、Task、
Approval 或 Execution。其失败文件把问题限定为 harness 把 CSV 误登记成 `application/json`，而
当前编译端口要求 `text/csv`。03 使用新状态目录和精确媒体类型重新运行，没有覆盖或改写 01。

### 3.4 最小拓扑修订合理

当前 TCAD author/reviewer 的 `scientific_foundation` 属于 `approved_parameters` cohort，和参数需求、
参数集、来源目录、coverage、audit、uncertainty 共同构成全有或全无的参数纵切面，并只接受两个
参数资格 Operation。冻结通用科学链产生的 foundation 由另一资格合同批准，不能合法占用该端口；
仅绑定它既不是完整参数组，也不能通过 exact admission。

当前修订没有放宽 cohort 或修改生产声明，只从评估 manifest 的两个 TCAD Agent 步骤删除这两个
不适用的可选绑定。TCAD author/reviewer 仍接收同一精确 experiment plan、独立 plan review 和
运行能力，reviewer 还接收 author project；foundation 仍进入假设、批判、审计、目标和实验生成
链。该修订因此减少无效权限和重复上下文，没有绕过科学前序或参数资格，也没有新增实体、状态或
注册权威。

## 4. 独立命令结果

```text
当前五插件 compile_catalog + exact scorer + strict result validator
=> Operation digest 50ca636a…；重算输出 SHA 7f3a5fe6…；与 03 bytes 相等

冻结 19 文件与 replay plugin closure 4 文件 SHA/size 复算
=> 全部匹配

冻结历史 scorer 对原始输入复算
=> metrics/residuals 与历史参考逐字节同摘要；公共共同数值最大差 8.88e-16

pytest -q tests/operations/test_tcad_operation_plugin.py \
  tests/operations/test_r5_frozen_baselines.py
=> 19 passed in 37.97s

git diff --check -- tests/fixtures/r5_e2e_tcad/manifest.json \
  docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md
=> 通过
```

## 5. 门禁结论

**结论：通过（仅放行历史 replay Effect/UI 环节）。**

当前 03 运行的目录身份、五输入摘要、有序父链、Operation 摘要、结果 Schema、公开输出字节、历史
原始曲线复算和失败边界均闭合。运行前删除两条不适用的 generic foundation 绑定是保持 TCAD 参数
cohort 失败关闭的最小修订，没有放宽生产门禁或切断通用科学链。

本结论只允许进入下一项历史 replay Effect/UI 生命周期验证；**不放行多 Agent 或单 Agent 科学
运行，不表示 R5-G 完成，也不提供科学效果结论。** 后续 Effect/UI 的真实批准、执行与四输出证据
是未来环节的要求，不是本轮已完成事实。
