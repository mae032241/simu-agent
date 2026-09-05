# R5-M3 确定性变换双层删除实现证据

日期：2026-09-01

状态：返工独立复审 PASS；M3 完成，仅放行 M4

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 删除的问题

M2 结束时，每个确定性 Operation 已有一个注册组件，但组件内部仍经由旧的 profile adapter：

```text
Compiled Operation 组件
  → 把端口集合改写为旧 inputs
  → adapter 按 profile 字符串再次分派
  → 领域算法生成旧 TransformOutput
  → 组件按 label 再拆成新端口集合
  → 通用调用器再次生成 TransformOutput
```

这里存在两个能力选择点、两次输入/输出包装和一套只为旧入口存在的父链协议。Operation 已经由唯一
启动目录选择后，第二次按 profile 选择没有独立不变量，只会让注册表统一停留在表面。

M3 将路径收敛为：

```text
Compiled Operation 组件
  → 已注册的窄领域函数返回 {端口: (字节, ...)}
  → execute_compiled_transform 按编译端口统一校验并生成登记输出
```

没有新增基类、adapter、注册表、状态或兼容入口。

## 2. 实现结果

### 2.1 唯一通用调用器

`operations/invoke.py` 删除 `CompiledTransformAdapter`，只保留
`execute_compiled_transform(bound, inputs)`。它只负责：

1. 校验调用对象确为已编译 Transform；
2. 校验精确来源名称并按已编译端口分组；
3. 调用目录解析出的唯一组件；
4. 按已编译输出端口校验基数、字节、validator、媒体类型和载荷版本。

Root 不识别领域名、Schema、TCAD、曲线或 profile。非资格输入和仅交接输入的处理直接来自同一
`InputPortSpec` 的 `usage`、`exposure` 与 Operation `consequence`；父链要求由编译 guard 执行。

### 2.2 领域算法不再二次分派

删除：

- `ScientificStateTransformAdapter`；
- `CurveScoreTransformAdapter`；
- `TCADProjectTransformAdapter`；
- `InGaAsFig4TransformAdapter`；
- `supports_transform_profile`；
- curve/TCAD Operation 组件中的 `_legacy()`；
- 无消费者的 TCAD solver-capability profile 分支；
- 领域模块对旧 `TransformOutput` 的构造与导入。

保留并直接注册的窄能力包括：科研目标投影、实验计划机械物化、知识更新、曲线证据归一化、曲线评分、
覆盖检查、TCAD 工程比较/审查鉴证/打包/运行鉴证/实现快照/对照等价，以及 InGaAs 冻结评分。领域算法
仍在各自插件，未迁入 Root。

### 2.3 父链和输出所有权

旧 adapter 中真正承重的父链规则已经是编译合同的一部分：

- TCAD 打包与运行鉴证使用 `package_parentage`、`runtime_parentage` guard；
- 曲线评分、图证据归一化和目标覆盖使用 `score_parentage`、`figure_parentage`、
  `objective_parentage` guard；
- 通用实验/知识更新继续使用原编译 guard。

因此删除的是重复协议，不是父链校验。Artifact 登记仍由 Root 的一个入口完成，所有输出仍使用完整
输入 Envelope 的精确父引用。

## 3. 等价证据

### 3.1 Operation 身份与媒体合同

新增 `test_m3_transform_adapter_removal.py` 冻结 M2 的四种目录组合：

| 组合 | Operation | 目录摘要 |
|---|---:|---|
| 默认 TCAD | 45 | `546421934d77110b144788872c0110f7c250ae94da19e1db8a199058f208a403` |
| 默认 TCAD + 可选图证据 | 47 | `39e20b502a963ec365fdb758c729c88ba10413371fb9746197013148fdd40bf1` |
| 默认完整产品 + InGaAs | 46 | `31a380bac3a2e231a44f9f51d867962f37957129de5aac6e5f9f7381dd439600` |
| 可选完整产品 + InGaAs | 48 | `6f6592e5ca396cc05eb17b27420becdf0cd6f8b40cfebc77493d1ef07fcc1213` |

四项与 M2 冻结值逐字一致。因为 Operation 摘要绑定输入、输出、媒体类型、载荷版本、validator、guard、
review、permission、limits 和组件实现引用，这证明这些编译身份没有因删除 adapter 漂移。

### 3.2 字节与集合顺序

本阶段没有修改领域计算表达式。旧包装中每个 `TransformOutput.content` 的表达式被原样移到对应端口：

| 范围 | 原内容表达式 | 当前端口 |
|---|---|---|
| 通用目标 | `objective.canonical_json()` | `research_objective` |
| 实验物化 | portfolio/report 的 `canonical_json()` | `experiment_plan` / `materialization_report` |
| 知识更新 | update/state 的规范 JSON | `knowledge_update` / `knowledge_state` |
| 曲线 | report、bundle、audit 的规范字节及原 PNG | 原已编译四个输出端口 |
| TCAD | diff/package/report/snapshot/audit 的原规范字节 | 原已编译六组端口 |
| InGaAs | `canonical_json(score_baseline_recovery(...))` | `metric_report` |

通用调用器按 `OperationSpec.outputs` 顺序取端口，集合成员直接保留窄函数产生的 tuple 顺序；它不依赖
Python mapping 插入顺序。现有回归覆盖：

- 通用多输出 Transform 的输出名称、父引用、幂等重放和非资格传播；
- 曲线分析包与 PNG 集合的名称、顺序、摘要和篡改负例；
- InGaAs 固定输入的真实评分、Schema validator 和冻结输入篡改负例；
- 编译 Transform 的载荷版本、严格输入绑定和组件异常边界；
- TCAD 本地作者—调试—独立审查共享同一 Operation 路径。

首轮独立审查确认，上述目录摘要、机械映射和当前回归不能替代可执行的修改前对照。返工已按其四项
关闭条件补齐：

1. 从会话变更事件逆序恢复精确 M2 生产源码，封存于
   `../../../archive/r5-m2-transform-oracle/m2-production-source.tar.gz`。归档 SHA-256 为
   `bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002`；解压后严格复算为 142 个
   Python 文件、49,018 行、源码摘要
   `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`。
2. `m3_transform_equivalence_runner.py` 在独立进程中加载指定源码树，并验证核心、通用科学、曲线、
   TCAD、InGaAs 的实际生产模块均来自该树。M2 与 M3 使用同一冻结语料，各自经真实 Root
   `operation_preflight` 和 `operation_invoke` 执行目录中的全部 22 个生产 Transform。
3. 机器清单逐项包含有序输出 label/Artifact 名、完整 Base64 内容、kind/schema/payload version/
   media type、有序完整父引用、Operation id/version/digest/调用指纹、同请求重放、同名冲突拒绝、
   `create_revision` 输出，以及每个输出的 SchedulerBinding 名称、逻辑名、修订号和请求指纹。Artifact
   的 `supersedes_ref` 也被比较；确定性 Transform 的语义修订权威位于 SchedulerBinding，故该字段在
   两版均为 `null`，不能冒充替代链。去除仅证明源码版本不同的 `source` 字段后，两份规范清单均为
   390,330 字节，SHA-256 均为
   `eb9236dd90914af27201884f37d2e46053eee5d630a0c1b4a436a24ac070d258`，逐字段相等。
4. 目录中全部 9 个父链 guard 均执行一个真实 preflight 正例和一个删去精确父边的负例；每个负例均
   以 `reason_code="guard_rejected"` 失败。实验物化 guard 的单输入合法模式无法制造缺边，故另用完整
   五输入科学谱系探针验证，未改变生产 Operation。

自动门位于 `tests/operations/test_m3_transform_equivalence.py`；归档只由测试解压至临时隔离目录，不
进入安装或运行时。由此计划 8.3 的可执行证据缺口已在实现侧关闭，但阶段仍须新的独立审查明确 PASS。

## 4. 复杂度变化

| 指标 | M2-03 | M3 候选 | 变化 |
|---|---:|---:|---:|
| 生产 Python 文件 | 142 | 142 | 0 |
| 生产 Python 行数 | 49,018 | 48,397 | -621 |
| `operations` 核心包 | 8 文件 / 2,103 行 | 8 文件 / 2,080 行 | -23 行 |
| Root 公共工具 | 30 | 30 | 0 |
| 完整产品 Operation | 46 | 46 | 0 |
| Agent / Transform / Approval / Effect | 20 / 22 / 3 / 1 | 20 / 22 / 3 / 1 | 0 |
| 插件组件 | 216 | 216 | 0 |
| Run 状态 | 4 | 4 | 0 |

当前生产树摘要：

```text
7669b06cd4ffdeb18085d4cc332fadcb2c5860bfebbbc0496d4504584d7b4d8f
```

没有新增数据库表、Root 工具、Operation、组件、运行状态、服务、目录投影或领域专用控制分支。

## 5. 回归结果

串行执行并设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`：

```text
pytest -q tests/operations/test_m3_transform_adapter_removal.py \
  tests/operations/test_invoke_preflight.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_ingaas_operation_plugin.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_m2_curve_analysis_boundary.py
28 passed in 9.22s

pytest -q tests/operations/test_m3_transform_equivalence.py
1 passed in 29.99s

pytest -q
226 passed in 126.33s

git diff --check
通过，无输出
```

全量首轮唯一失败是旧测试要求 Transform 责任文件总行数必须精确等于 1,105；合理删除后变为 1,087。
该测试已改为“统计自洽且不超过冻结上界”，没有为通过测试修改生产行为。

## 6. 当前阶段判断

M3 满足“一个编译目录、一个 Transform 调用入口、领域算法归插件、控制层不做领域选择”的结构目标，
同时是净删除而非换壳重构。首轮独立审查提出的 8.3 双实现证据缺口已完成返工，并由
`../reviews/R5_M3_TRANSFORM_ADAPTER_REMOVAL_INDEPENDENT_REREVIEW.zh-CN.md` 独立复审 PASS。M3 完成，
仅放行 M4；不宣称 R5-M 完成。
