# R5-M3 确定性 Transform 双层删除返工独立复审

日期：2026-09-01

结论：**PASS**

阶段门：**首轮审查 B-1 已关闭，仅放行 M4。** 本报告不宣称 R5-M 完成，不改变 M0、M1、M2
既有独立审查结论，也不把 33 项约束整体升级为 `conformant`。

## 1. 独立性、范围与基线

本复审者未参与 R5-M3 实现或返工，且没有修改任何生产代码或测试代码。唯一写入是本报告。

仓库仍只有基线提交 `404aeb1`，M1—M3 与更早修改共同位于未提交/未跟踪工作树中；因此
`git diff HEAD` 不是 M2→M3 阶段补丁，本报告没有把它当作阶段差异。M2→M3 的可执行对照基线是：

- 首轮审查已冻结的 M2 生产源码摘要
  `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`；
- `archive/r5-m2-transform-oracle/m2-production-source.tar.gz` 中封存的源码；
- 当前 M3 工作树及其生产源码摘要
  `7669b06cd4ffdeb18085d4cc332fadcb2c5860bfebbbc0496d4504584d7b4d8f`。

复审完整阅读了 M3 计划第 8 节、首轮 FAIL、返工证据、当前架构、设计宪章和 33 项约束，并追踪：

```text
Root operation_preflight / operation_invoke
  -> RootOperationRoutes._invoke_compiled_transform
  -> execute_compiled_transform
  -> CompiledCatalog 唯一 executor component
  -> 编译输出端口校验
  -> Artifact 登记与 SchedulerBinding 语义修订
```

## 2. 首轮阻断关闭结果

### 2.1 精确 M2 oracle：通过

独立复算得到：

- 归档 SHA-256：
  `bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002`；
- 解压后的生产 Python：142 文件、49,018 行；
- 按“相对路径、零字节、原始文件字节、零字节”计算的摘要：
  `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`。

三项都与首轮审查预先记录的 M2 冻结值一致。测试先校验归档 SHA-256，解压后再校验文件数、行数和
生产源码摘要；改动归档字节或解压后的生产源码都会失败。

归档不进入产品：核心 wheel 只发现 `src/` 包，各领域 wheel 只发现自己的 Python 包；干净 Git 源发布
使用显式白名单，聚焦回归还直接断言输出中不存在 `archive/`。归档只由专项测试解压到 pytest 临时
目录，没有生产导入、entry point、运行时注册或部署消费者。

将 oracle 与当前生产树逐文件比较，只有 13 个生产文件不同；统计为新增 614 行、删除 1,235 行，净删
621 行，与 M3 证据一致。当前生产树仍为 142 文件、48,397 行。

### 2.2 两个独立进程真实加载两版生产模块：通过

`test_m3_transform_equivalence.py` 分别启动 M2、M3 两个子进程。M2 的 `PYTHONPATH` 把解压后的
`src` 和四个插件包放在当前仓库之前；当前仓库只用于加载共享测试 runner/fixture，不能优先提供生产
包。runner 的 `loaded_modules` 又验证以下六个关键模块均位于传入的 `--source-root`：

- `scidiscovery.operations.invoke`；
- 两个通用科学 Transform 组件模块；
- curve、TCAD 与 InGaAs 的生产 Transform/插件模块。

本复审另在 M2 进程完成 22 项执行后枚举 `sys.modules`：115 个 `scidiscovery`、`curve_score`、
`curve_figure_evidence`、`tcad_artifact`、`ingaas_fig4` 生产模块全部位于解压后的 M2 根目录，当前
`src/plugins` 混入数为 0。由此排除了只校验少数模块、其余实现回退到 M3 的跨版本污染。

两个进程都经真实 `RootMCPRouter.call_tool("operation_preflight", ...)` 与
`RootMCPRouter.call_tool("operation_invoke", ...)` 执行，而不是直接调用窄算法。runner 将 catalog 中
所有 `executor.kind == "transform"` 的 Operation 集合与冻结场景集合做精确集合相等检查，实际为
22 项；缺一项或多一项都会在执行前失败。

### 2.3 计划 8.3 的逐项行为清单：通过

去除只用于证明源码版本不同、且 M2 已先独立校验的 `source` 字段后，本复审复算两份规范清单均为：

```text
390,330 bytes
SHA-256 eb9236dd90914af27201884f37d2e46053eee5d630a0c1b4a436a24ac070d258
```

两份字节逐项相等。清单覆盖 22 项 Operation 的 38 个首次输出和 38 个 `create_revision` 输出，逐项
记录并比较：

- 有序 output label 与完整 Artifact 名；
- 原始内容的完整 Base64，即不做 JSON、PNG、CSV 或浮点归一化的输出字节；
- kind、Schema id、payload Schema version 与媒体类型；
- 按原顺序保存的完整父引用；
- Operation id、version、digest、调用指纹和输出端口身份；
- 集合成员的生成名称与 tuple 顺序；
- 同一请求的幂等返回；
- 同名、不同请求的拒绝类型；
- `create_revision` 的输出、绑定名、逻辑名、修订号和请求指纹。

本复审还验证每个首次/修订输出的父引用数量均等于该场景的完整输入数，没有因只比较部分父边而掩盖
输入漂移。22 项幂等重放均返回相同结果；22 项同名异请求均以 `SchedulerNameConflict` 拒绝。

语义修订的当前权威是 SchedulerBinding，不是 `ArtifactEnvelope.supersedes_ref`。全部 22 项主输出均由
base revision 1 进入同一 logical name 的 `.rev2`/revision 2，且请求指纹改变；派生兄弟以 `.rev2`
命名空间内的自身 binding 登记并共享新调用指纹。`supersedes_ref` 在 M2/M3 都为 `null`，清单明确
比较了这个既有事实，没有把空字段冒充替代链，也没有把 M4 才可能处理的语义变化夹入 M3。

### 2.4 全部 9 个 guard：通过

当前 22 项 Transform 中恰有 9 项、且每项恰有一个编译 guard。runner 对每项都先用完整谱系执行真实
preflight 正例，再只删除一条精确父边执行真实 preflight 负例：

| Operation | guard | 删除的精确父边 |
|---|---|---|
| `science.experiment.materialize.v1` | `experiment_lineage` | intent → critic |
| `science.parameter.uncertainty.v1` | `parameter_uncertainty_lineage` | coverage → requirements |
| `scidiscovery.curve-bundle.figure-evidence.v2` | `figure_parentage` | validation → curve table |
| `scidiscovery.curve-score.v1` | `score_parentage` | curve bundle → contract |
| `scidiscovery.objective-coverage.v1` | `objective_parentage` | curve contract → plan |
| `tcad.reviewed-deck-package.v2` | `package_parentage` | review → capability |
| `tcad.runtime-attestation.v1` | `runtime_parentage` | runtime manifest → package |
| `tcad.curve-bundle.sprocess-log.v1` | `curve_log_parentage` | attestation → solver log |
| `tcad.curve-bundle.sprocess-plx.v1` | `curve_plx_parentage` | attestation → PLX output |

9 个正例全部 `admissible=true`；9 个负例全部为 `admissible=false` 且
`reason_code="guard_rejected"`。实验物化的常用单输入 engineering 形状没有可删除父边，因此测试另用
同一生产 Operation 的完整五输入科学谱系探针；没有增加测试专用 Operation 或修改生产声明。

## 3. 测试语料和执行器质量

返工专项共 1,675 行（110 行 pytest 包装、1,565 行 runner）。该体量主要来自让 22 个领域 Transform
通过真实 Schema、资格和父链 preflight 所需的合法固定语料，而不是生产兼容层。审查结果如下：

- runner 复用了已有通用、曲线、参数和 TCAD 测试构造器，没有复制生产算法作为期望值 oracle；
- M2/M3 分别用各自的生产 codec、Schema、guard、executor、Root 和 Artifact 服务执行；
- 虽然共享测试 helper 来自当前仓库，但生产模块来源审计为 115/115 位于各自 source root，且输出
  的完整父引用 SHA 相等，证明两边实际消费的输入内容相同；
- 输出内容只做 Base64 包装，比较前仅删除已先校验的顶层 `source`，没有丢弃时间、路径、浮点、集合
  或错误字段的定向归一化；
- 场景集合与目录 Transform 集合、guard 场景集合与目录 guarded Operation 集合都要求精确相等；
- 修订输入使用新 Artifact identity 形成新完整请求，先证明默认冲突拒绝，再显式调用
  `on_conflict="create_revision"`；
- archive、runner 和专项测试都没有生产消费者，也没有加入安装或发布入口。

没有发现会让 M2/M3 共同调用当前实现、漏掉生产 Transform、绕过 Root、提前死于 Schema、重排输出、
忽略父链或只比较 catalog digest 的夹具缺陷；也没有发现为专项测试增加生产标签、放行分支或兼容代码。

## 4. 生产结构、奥卡姆性与 33 项约束

生产删除方向保持成立：

- 生产树不存在 `CompiledTransformAdapter`、`ScientificStateTransformAdapter`、
  `CurveScoreTransformAdapter`、`TCADProjectTransformAdapter`、`InGaAsFig4TransformAdapter` 或
  `supports_transform_profile`；curve/TCAD Operation 组件不存在 `_legacy()` 桥；
- 仅有一个 `execute_compiled_transform` 定义，并只有 Root 的编译 Transform 路径调用它；
- 22 个 Transform 的 executor 全部来自其已编译插件组件；Root 只按编译端口分组、调用、校验和登记，
  没有按 TCAD、curve、InGaAs、Schema、角色或插件名选择算法；
- Root 中保留的 `profile` 字段只是等于 Operation id 的历史 Artifact 标签/返回字段，不是能力分发点；
- 当前完整产品仍为 46 个 Operation（20 Agent、22 Transform、3 Approval、1 Effect）、216 个插件组件，
  Root 公共工具 30 个，`operations` 包 8 文件/2,080 行；
- M3 没有新增生产文件、Registry、数据库表、Run 状态、服务、preflight、invoke、目录投影、插件入口或
  领域核心分支；四种 M2 目录数量与摘要保持不变；
- 当前差异是净删 621 行生产代码，没有用新基类、第二框架或新 adapter 换壳。

33 项约束注册表仍为 33 个唯一 id，状态为 7 `conformant`、25 `pending_review`、1 `known_issue`。
与 M3 直接相关的 DET-001 仍诚实保持 `pending_review`；DET-002、PLG-001、PLG-002 的当前结论没有被
本轮测试数量夸大；`SEC-002` 仍为 `known_issue`。本次通过只说明 adapter 删除与 M2 行为等价及其结构
边界成立，不证明全部科学、安全、部署或真实 solver 条件已经符合。

## 5. 独立执行记录

所有 pytest 均串行运行，设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`，并禁用仓库 pytest cache
与 Python bytecode 写入。

1. 最终版 M2/M3 双进程等价门：

   ```text
   1 passed in 28.50s
   MAXRSS_KB=105604
   ```

2. M3 结构、invoke/preflight、通用/曲线/InGaAs/TCAD Transform、33 项结构、领域中性核心和干净源发布
   隔离聚焦集合：

   ```text
   32 passed in 10.95s
   MAXRSS_KB=113552
   ```

3. 独立手工执行 M2/M3 runner：22 Transform、9 guard、390,330 字节行为清单及 `eb9236…` 摘要均
   复现，逐字节相等；M2 生产模块来源审计为 115/115 位于 oracle 根目录。

4. `git diff --check`：通过，无输出。

实现者报告的最终串行全量为 `226 passed in 126.33s`，并报告 `py_compile` 通过。本复审没有重复全量：
返工相对首轮已审生产候选只增加 oracle、测试和证据文档，专项与相关跨边界聚焦集合已直接覆盖阻断；
没有运行真实 solver、实时模型 Agent 或浏览器，它们不是本次 8.3 确定性等价门的替代证据，也未被本
报告宣称验证。

## 6. 最终判定

**PASS。** 首轮 B-1 的四项关闭条件均已满足：精确 M2 源码可执行且防篡改、M2/M3 分别从独立生产
源码树经真实 Root 执行全部 22 项 Transform、计划 8.3 的字节/合同/父链/身份/顺序/幂等/冲突/修订
观察量逐项相等、全部 9 个 guard 有真实 preflight 正负例且负例精确因 `guard_rejected` 失败。

当前生产结构仍是一个编译目录、一个 Transform 调用入口和插件内窄函数，净复杂度下降且未削弱已编译
门禁。**因此 M3 完成，只放行 M4；R5-M 仍未完成。**
