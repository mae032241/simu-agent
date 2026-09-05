# R5-M3 确定性 Transform 双层删除独立审查

日期：2026-09-01

结论：**FAIL**

阶段门：**M4 不放行。** 本报告不否定 M0、M1、M2 已有独立审查结论，也不宣称 R5-M 完成。

## 1. 审查范围与基线限制

本审查者未参与 R5-M3 实现。审查对象是当前 `baseline/8765-codex` 工作树中的 M3 候选、
`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 第 8 节及
`R5_M3_TRANSFORM_ADAPTER_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`。

Git 只有基线提交 `404aeb1`；M1、M2、M3 与大量更早修改共同位于未提交/未跟踪工作树中。因此
`git diff HEAD` 不是 M2→M3 的精确差异，本报告没有把它冒充阶段补丁。M2-03 证据冻结的生产源码
摘要是 `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`（142 文件、
49,018 行），但仓库、Git 对象库和现存临时安装环境均没有与该摘要对应的可执行源码快照；现存较早
命名临时运行只足以核对一个通用 intake split 样例，不能代表全部生产 Transform。

本轮实际追踪了：

- `operation_invoke` → `_invoke_compiled_transform` → `execute_compiled_transform` → 插件组件 →
  Artifact 登记；
- 当前完整产品的 22 个 Transform 及其通用、curve、TCAD、参数、InGaAs 组件；
- 编译 digest 的构造、输出端口顺序、父引用、producer family、幂等 fingerprint 与
  `create_revision` 路径；
- 插件 entry point、旧 adapter/profile 符号、Root 领域词、33 项约束登记和安装入口。

## 2. 阻断发现

### B-1：计划要求的 M2→M3 全量行为等价没有可执行证据

计划 8.3 明确要求“对每项生产 Transform 固定输入，比较修改前后”，比较面包括输出字节和媒体类型、
父引用、Operation 身份与摘要、集合成员名称和顺序，以及幂等/冲突修订结果（计划第 251—261 行）。
当前证据没有执行这项比较：

1. `test_m3_transform_adapter_removal.py:35-73` 只检查旧类/函数名消失及唯一调用器函数名；
   `:76-109` 只冻结四种 catalog 的 Operation 数量和摘要。它没有装载 M2 实现，也没有比较任一
   M2/M3 输出 tuple、Artifact envelope 或第二次调用/修订结果。
2. catalog digest 不能代替行为等价。`operations/catalog.py:645-669` 将 `OperationSpec`、
   `ComponentSpec`、资源摘要、permission 和 review 身份纳入 digest；callable 实现仅在
   `:675-679` 放入运行时 `implementations`，函数源码/字节码不进入 digest。本审查做了内存内负控：
   保持 `ingaas_fig4:score` 的 ComponentSpec 和实现引用字符串不变，把实际 callable 换成返回
   `b"{}"` 的函数后，完整 catalog digest 仍为
   `31a380bac3a2e231a44f9f51d867962f37957129de5aac6e5f9f7381dd439600`，该 Operation digest 也
   保持 `45879beef1cb841603c76422a8d0c8b16834b08e9ca73f13fa10e4b31741654d`，但运行输出已经改变。
   因而目录摘要只证明声明和实现定位符未漂移，不能证明实现行为未漂移。
3. 实现证据第 97—118 行承认没有“修改前”可执行状态，改用“目录摘要＋逐表达式机械映射＋当前
   回归”。这最多支持当前实现自洽，不能满足前后对照。其机械映射表本身还有一个可复核错误：第
   102 行把实验物化第二输出写成 `validation_report`，实际
   `general_science_experiment_operations.py:308-312` 和
   `general_science_experiment_components.py:154-157` 均为 `materialization_report`。因此该表也
   不能作为精确成员名称 oracle。
4. 当前回归分别验证当前路径的若干性质，但没有覆盖“全部 22 个生产 Transform × 8.3 五类观察量”的
   双实现矩阵。尤其没有 M2 侧输出，就无法排除窄函数搬移时发生的字节、集合顺序或标签/修订漂移。

影响：这是高风险删除候选的完成门本身，而非文档改进项。一个 callable 可以在全部现有目录摘要测试
保持绿色时改变科学字节；随后相同 Operation 身份会把变化后的结果登记为看似同一确定性关系。这使
DET-001 的“可重放”证据和 M3 的精确等价声明不可审计。33 项登记仍诚实保持 DET-001
`pending_review`，不能用本轮 `225 passed` 将其升级或绕过。

#### 可执行关闭条件

必须在不恢复任何生产兼容层的前提下完成以下工作：

1. 在独立 worktree/测试夹具中恢复精确 M2 源码或 wheel，并用既有 metrics 算法验证其生产源码摘要
   精确等于 `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`；恢复后的
   M2 状态应提交或封存为只读测试 oracle。仅有相同行数或 catalog digest 不足。
2. 用同一组冻结输入分别经 M2 和 M3 的真实 Root `operation_invoke` 路径执行全部 22 个生产
   Transform；生成机器可比较的 manifest，逐项比较：有序输出 label/Artifact 名、完整内容字节、
   kind/schema/payload version/media type、有序父引用、Operation id/version/digest、集合顺序、同请求
   重放结果，以及变化请求在 `reject` 和 `create_revision` 下的结果。
3. 为每个保留下来的父链 guard 至少运行一个正例和一个从真实 preflight 进入的负例；负例必须因对应
   guard 拒绝，而不是由无关 Schema 或夹具错误提前失败。
4. 把双实现比较加入 M3 专项回归并由新的未参与实现者复审。若无法恢复精确 M2 源码，则只能提供在
   M3 修改前生成、覆盖同一 22 项和上述全部观察量、且绑定该 M2 源码摘要的完整 golden corpus；当前
   零散临时 Artifact 不满足此条件。

在以上条件关闭前，M3 不得标记完成，M4 不得开始。

## 3. 当前实现的非阻断审查结果

除 B-1 的证据门外，本轮没有发现当前生产路径中的第二 Transform 权威或明显语义回退：

- 当前完整产品精确有 22 个 Transform；所有调用均进入
  `operations/invoke.py:273-295` 的一个 `execute_compiled_transform`。该函数从已编译端口分组输入，
  只调用 catalog 已解析的唯一组件；Root 没有按 TCAD、curve、Schema、插件名或角色选择算法。
- 生产树不存在 `CompiledTransformAdapter`、`ScientificStateTransformAdapter`、
  `CurveScoreTransformAdapter`、`TCADProjectTransformAdapter`、`InGaAsFig4TransformAdapter`、
  `supports_transform_profile` 或组件 `_legacy()`；各发行包也只注册统一
  `scidiscovery.plugins` entry point。保留的 `operation_transforms.py` 函数是已编译端口到插件窄算法
  的局部绑定，没有 profile 选择器、第二注册表、基类或兼容 fallback。
- `invoke.py:328-361` 按 `OperationSpec.outputs` 顺序生成输出，集合 tuple 顺序不依赖 mapping 插入
  顺序；`:362-370` 执行单项上限与声明 validator。Root
  `mcp_root_operation_routes.py:757-845` 由 Operation id/version/digest 和有序精确父引用生成请求
  fingerprint，在同一登记入口保留媒体类型、输出端口、父引用、幂等返回和显式 revision 语义。
- TCAD `package_parentage`/`runtime_parentage`，curve `score_parentage`/`figure_parentage`/
  `objective_parentage` 及通用实验 guard 仍由编译 Operation 引用。没有发现把这些规则搬到 Root、删除
  后失去保护，或增加领域专用准入分支。
- 当前 metrics 与实现证据一致：142 个生产 Python 文件、48,397 行；`operations` 为 8 文件/
  2,080 行；完整产品 46 个 Operation，其中 22 个 Transform；Root 公共工具仍为 30。没有新增
  数据库表、Run 状态、Registry、preflight/invoke 或服务。M3 为净减 621 行，没有用新框架替换旧
  adapter。结构行数测试从精确相等改为冻结上界，允许经证据支持的删除，未发现为本候选放宽生产语义。
- 33 项登记仍为 33 个唯一编号，状态为 7 `conformant`、25 `pending_review`、1 `known_issue`；
  `SEC-002` 未被回归数量掩盖。当前实现方向符合通用、低成本科研 Agent 的目标，但等价证据缺口阻止
  本阶段放行。

## 4. 独立测试记录

所有 pytest 均为串行执行，并设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`。

1. M3、通用 Transform、invoke、InGaAs、TCAD 与曲线聚焦集合：

   ```text
   28 passed in 9.78s
   MAXRSS_KB=110420
   ```

2. 33 项结构、installed entry point、领域中性核心：

   ```text
   12 passed in 45.81s
   MAXRSS_KB=74336
   ```

3. 全量：

   ```text
   225 passed in 74.92s
   MAXRSS_KB=138300
   ```

4. `git diff --check`：通过，无输出。

绿色结果证明当前候选在本机回归集内自洽，并不提供已丢失的 M2 对照侧。未运行真实外部 solver、浏览器
或实时模型 Agent；它们不是本次 adapter 删除的 8.3 等价缺口替代物。

## 5. 最终判定

**FAIL。** 删除结构符合 M3 的奥卡姆方向，当前回归也全部通过，但计划规定的逐生产 Transform 前后
等价门没有被执行，且 catalog digest 已被负控证明不能代表 callable 行为。B-1 关闭并经新独立复审
PASS 前，**M4 不放行**。
