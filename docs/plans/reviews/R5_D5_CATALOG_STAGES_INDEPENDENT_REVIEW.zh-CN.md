# R5-D5 Catalog 阶段拆分独立审查

日期：2026-08-29  
审查性质：未参与实现的跨边界、简化性与变更范围审查  
结论：**通过，只放行 R5-D 总审**  
门禁决定：不提前放行 R5-E 或后续阶段

## 1. 审查范围

本轮审查启动期 Operation catalog 编译器的阶段拆分、唯一目录权威、组件闭包、Operation 合同、
review/provider 图、摘要构建、installed entry point 和复杂度计量。审查没有修改生产代码、测试、计划
或阶段状态；唯一写入是本报告。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行，覆盖源码阶段接口、稳定负例、四组目录摘要、运行时插件、干净安装和
全仓组合路径。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 权威计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；使用第 3 节、第 8.5 节及 R5-D 复杂度门。 |
| S2 | 当前架构 `docs/ARCHITECTURE.zh-CN.md`，SHA-256 `570d811adb87a7add86bc85057fba5214145f215bc58f95845c7ce20b8a0dfad`；最小重构权威 `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`，SHA-256 `77bb5c36ee71a683b0ffed5adec55968ba0be35d88af5ff0af5f2d7d951b0494`。 |
| S3 | 当前 `src/scidiscovery/operations/catalog.py`，SHA-256 `e3c99ce16d668b28add304acb218daf725a75850a4cc7f0f3c2ea4951ae7ef47`；相邻 `spec.py`、`invoke.py` 未由 D5 拆出目录状态。 |
| S4 | D5 结构门 `tests/operations/test_r5_catalog_stages.py`，SHA-256 `07991e8a...`；catalog compile/negative/installed-entry/runtime-plugin、Worker、通用插件与生命周期测试。 |
| S5 | core、architecture fixture、general science、TCAD、curve-score 与 InGaAs 插件的精确 `PluginDefinition`，以及 standard `scidiscovery.plugins` entry point。 |
| S6 | 当前计量脚本 `scripts/r5_current_metrics.py`，SHA-256 `453b6e51...`；本轮输出 SHA-256 `346ced58733dba65119e2cc717d29c563cbb97623fbbd8bde62dbd6746d0c590`。 |
| S7 | 冻结生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；冻结快照 `tests/fixtures/r5_structure_inventory.json`，SHA-256 `1b397e2dfea1bc579b2597caf5d3a37f5ef44e40d66b92f509b349b51b77983a`。 |
| S8 | 实施记录 `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`，SHA-256 `846a1d57...`。 |
| S9 | 本轮独立命令记录：71 项目录聚焦测试、288 项全仓测试、四组摘要复算、独立组件闭包正负例、AST 单构造/单缓存/无可变注册表检查、当前计量和 `git diff --check`。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `stage_coordination` | pass | S1—S4, S9 | `compile_catalog` 仅含三次阶段赋值和一次构建返回；声明规范化、Operation 合同、review/provider 图和构建是四个显式顶层过程，组件闭包由独立递归函数在需要精确 Operation/review reachable 集合时复用。 |
| `real_stage_boundaries` | pass | S3, S4, S9 | 每阶段只经显式参数/返回值传递；normalize 克隆声明，contract 返回 compiled parts/runtime factories/used，review 返回 provider 图，build 消费并封装。`_resolve_component` 可独立验证传递资源、跨插件 public、kind 和稳定错误，非空壳函数。 |
| `single_catalog_authority` | pass | S2—S4, S9 | 全生产只有 `_build_compiled_catalog` 一处调用 `CompiledCatalog(...)`；catalog 模块只有 `compile_installed_catalog` 一个 `lru_cache(maxsize=1)`，没有模块级 dict/list/set、在线 registry、第二 installed cache 或持久编译上下文。 |
| `component_closure` | pass | S3—S5, S9 | 闭包保留显式 dependency/public/kind 检查、workspace hook 唯一性、传递资源、逐 Operation reachable 和 unused component 失败关闭；独立正负例及全量 catalog 负例均通过。 |
| `operation_permission_contract` | pass | S2—S5, S9 | 端口、Schema 摘要、codec/validator/semantic contract、revision、cohort、limits、executor、Agent workspace/tool/resource/model/network 与 PermissionTemplate 的校验顺序和结果未退化。 |
| `review_provider_graph` | pass | S3—S5, S9 | reviewer 独立性、端口兼容、循环、Approval subject、provider public/dependency/kind/options 和 cohort 身份仍在构建摘要前闭合；跨插件 TCAD/curve 与通用资格 provider 可编译，负例保持稳定 reason code。 |
| `digest_and_runtime` | pass | S3—S5, S9 | Operation digest 仍覆盖 ABI、插件版本、精确 component specs/resource digests、PermissionTemplate、reviewer digest 与 provider identities；递归环失败关闭。runtime factory 仍从同一组件闭包产生并由 compiled catalog 只读暴露。 |
| `installed_entry_path` | pass | S3—S5, S9 | installed cache 只从排序后的 `scidiscovery.plugins` entry point 加载，重复、不可加载、名称不一致和错误组件保持稳定失败；core/full/InGaAs clean-wheel、Root/Worker daemon 和 Codex 消费同一 cached catalog。 |
| `frozen_catalog_summaries` | pass | S3—S5, S9 | 独立按排序 JSON `{operation_id:digest}` 复算：core 17/`5ac717e6623dc01c6349dc1c5ea1f78f240b6337f8e379657ebd6582a4c3e209`；architecture 20/`926e843f8cac6193f07b852e0bb801f262ef54bfede9e9bba2bc30e7d4f20c42`；full 51/`0cc88d23dd44f54fd429e523715e0bea8b063165c75b421f3b6696f983b7cf75`；full+InGaAs 52/`c80c94faa258f03cfcb3409d3223f5172ddc691b0526ec8a31804564d830f419`。 |
| `complexity_and_occam` | pass | S1, S3, S6—S9 | catalog 640/636（+4），仍是唯一 successor；operations 包 7 文件、2060/2060；全生产 60263/62533。逻辑未迁出包，D3/D4 测试只移除越权重复计量，D5 自有硬门仍在。没有新 service、context 对象、目录子包或状态机。 |
| `constraints_and_goal` | pass | S1—S5, S9 | 单一编译目录、启动期失败关闭、精确身份/权限/摘要、插件统一入口及领域中立 Root/Task/Worker 边界未退化；没有新增科学实体、领域分支或运行时规划权威。 |

## 3. 阶段关系判断

### 3.1 四个协调调用承载五种编译职责

当前 `compile_catalog` 直接调用四个顶层过程：normalize、operation contract、review/provider graph 和
build。组件闭包不是一个预先遍历全部组件的第五个全局 pass；它是独立 `_resolve_component`，在
Operation contract 与 review projector 需要建立精确 reachable 集合时递归调用。

这仍满足五种职责分离，而且比强行建立“全局闭包阶段”更小：组件是否可达取决于具体 Operation、
Worker scope 和 review/provider 引用，提前全量解析会需要额外上下文或制造错误的全局可达集合。本轮
独立直接调用 `_resolve_component`，验证了传递 semantic resource、公开跨插件 workspace、私有跨插件
拒绝与 kind 不匹配；因此它是可测试边界，不是只为通过结构门改名的局部函数。

### 3.2 编译上下文只存在于一次调用

`plugin_map`、`components`、`compiled_parts`、`runtime_factories`、`used`、review provider map、digest
cache 和 recursion stack 都由一次 `compile_catalog` 调用创建并显式向后传递。输入
`PluginDefinition` 被严格克隆，独立重复 normalize 返回不同容器且不修改输入。最终只有
`CompiledCatalog` 内部以 `MappingProxyType` 固化 Operation 与 runtime factory。

唯一长期状态是明确允许的 installed `lru_cache(maxsize=1)`，它对应“启动时编译一次”；Root、runtime、
daemon 和 Codex 读取同一对象，不能在线追加 Operation。插件变化仍要求新进程/新编译代际，不存在
另一份热更新 registry。

### 3.3 错误次序与身份摘要

normalize 先校验并加载声明、再校验插件依赖；Operation 阶段按既有顺序闭合端口、Schema、组件、
cohort、limits、executor、Agent 权限；review 阶段随后闭合 reviewer/provider；build 最后拒绝 unused
组件并计算递归身份摘要。目录正负例、安装组件错误和无效 Unicode 资源仍返回原稳定 reason code。

四组目录的 Operation 数量和聚合摘要逐字复现，说明 component reachability、PermissionTemplate、
review/provider identity、runtime components 和最终 operation digest 没有因函数边界漂移。摘要一致
不能单独证明运行路径，因此本轮同时复跑了 Transform、Approval、Worker、runtime plugin、daemon 和
installed entry 的全仓组合测试。

## 4. 复杂度与奥卡姆判断

`catalog.py` 从冻结的 636 行变为 640 行，新增 4 行；整个 `operations/` 包仍精确为 2060 行硬门，
全生产相对 D4 也只增加同样 4 行至 60263。所有阶段仍在原文件，未通过移出统计目录获得虚假减重。
文件中原有紧凑写法仍存在，但本轮物理行数没有下降，新增边界也没有引入多语句压缩以换取指标。

阶段函数共享同一小组编译数据，未为每阶段建立 class、service、factory、repository 或持久 context。
继续拆成子包会增加循环依赖和中间对象，而不会减少 640 行合同本身；当前五种职责边界已足以定位
声明、闭包、合同、图和摘要错误，符合奥卡姆约束。

## 5. 独立运行记录

全部命令在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

```text
pytest -q \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_r3_catalog_authority.py \
  tests/operations/test_runtime_plugin_configuration.py
# 71 passed in 35.54s

pytest -q
# 288 passed in 89.42s

PYTHONPATH=src:plugins/curve_score:plugins/tcad_artifact:plugins/ingaas_fig4 \
  python <四组目录数量与完整聚合摘要复算>
# 17/5ac717e6...；20/926e843f...；51/0cc88d23...；52/c80c94fa...

PYTHONPATH=src:plugins/curve_score:plugins/tcad_artifact \
  python <独立组件闭包、跨插件 public/private 与 kind 负例>
# 通过

python <AST 单构造、单 installed cache、无模块级可变 registry 检查>
python scripts/r5_current_metrics.py
git diff --check
# 均通过；catalog 640，operations 2060，全生产 60263
```

未运行真实 Sentaurus、公网抓取或浏览器人工点击：D5 只重排启动期目录编译函数，没有修改 solver、
HTTP、UI 决定写入或科学内容；真实安装入口、Approval/Transform/Worker 和失败关闭路径已由上述组合
测试覆盖。这些外部未来观测不是当前 compiler 阶段拆分缺失的证据。

## 6. 最终结论

未发现阻断缺陷。D5 保持一个目录构造点、一个 installed cache 和一次调用内的显式编译数据；五种
编译职责具有真实且可独立验证的边界，错误顺序、组件闭包、权限、review/provider、摘要、runtime
factory 与 installed entry point 均未退化。四组目录摘要逐字一致，复杂度只增加 4 行且未迁出硬门。

**结论：通过，只放行 R5-D 总审。**
