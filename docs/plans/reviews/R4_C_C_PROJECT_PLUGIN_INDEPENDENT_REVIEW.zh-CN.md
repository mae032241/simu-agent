# R4-C-C 项目插件迁移与 R4-C 收口独立审查

审查日期：2026-08-29  
审查对象：当前未提交工作树中的 `ingaas_fig4` 项目插件、安装选择、发布入口、清洁构建与 R4-C
收口状态。  
审查性质：独立跨边界审查；未修改生产实现。

## 一、结论

**打回。**

可选项目插件的主要方向正确：干净 wheel 中只有一个 `scidiscovery.plugins` 入口，编译目录只增加
一个 `support` Operation，默认 full 不安装项目插件，显式安装也不改变既有 46 个 Operation 的
摘要。冻结评分函数仍由项目包拥有，TCAD、curve-score 和通用调度合同没有新增 InGaAs 分支。

但是当前工作树尚未满足 R4-C 的完整收口门。存在四个阻塞项：完整输出合同没有失败关闭；通用
核心仍保留 Fig.4 专用策略；源码构建缓存会在本地开发运行时重新激活旧注册入口；根发布清单已经
过期。前三项属于实现/源码边界缺陷，第四项属于发布收口缺陷。修复并复审通过前，不允许将 R4-C
标记完成或进入 R4-D。

## 二、阻塞项

### 2.1 项目输出 validator 只校验局部字段，能接受畸形科学报告

位置：`plugins/ingaas_fig4/ingaas_fig4/plugin.py:71-118`、`:142-156`。

`_result_validator` 虽然校验顶层字段集合、版本、五个输入摘要、六个 gate 布尔值、五个 gate 标量
和非空解释边界，但没有校验以下已发布字段的结构、必需子字段、类型和有限性：

- `raw_baseline_reproduces_frozen_curve_bundle`；
- `baseline_metrics`；
- `candidate_metrics`；
- `baseline_recovery.crossing_errors_nm`；
- `residual_regions_above_0p02_decade`。

本次独立注入以真实成功输出为基准，分别把前三个对象改为 `null`、把残差区域改为字符串，四次均被
`_result_validator` 接受。`RESULT_SCHEMA` 同样只要求五个顶层字段，不能补上该缺口。这样一旦评分
函数回归、被错误包装或返回部分畸形对象，统一 Operation 输出门仍会登记一个结构不完整的
`metric_report`。实现记录中“核对……有限数值”的结论因此不成立。

最小修复应在项目插件内定义一个完整、严格、禁止额外字段且拒绝非有限数值的结果模型/validator，
覆盖评分函数实际返回的全部嵌套字段；不需要新增核心 Schema、注册表或控制面分支。至少增加上述
四类畸形输出负例，并增加 crossing、region 与 metric 内部数值/键集合负例。

### 2.2 通用核心仍含项目/图号专用上下文策略

位置：`src/scidiscovery/artifact_agent/core_context_policies.py:678` 起的
`scidiscovery.diagnosis.fig4-baseline-provenance.v1`。

源码扫描确认 `tcad_artifact`、`curve_score`、当前调度提示没有 InGaAs/Fig.4 分支，但通用核心仍
直接注册 Fig.4 专用输入名和大小策略。全仓生产代码扫描没有找到该 profile 的消费者；当前项目
能力已经由一个确定性 `support` Operation 表达。因此它既违反 R4-C-A 冻结的“核心、TCAD 和
curve-score 不得出现图号或 InGaAs 判断”，又是无生产消费者的旧纵向流程残留。

应删除这一精确核心策略及只为它存在的测试/说明期望，并用扫描回归证明 InGaAs/图号语义只存在于
可选项目插件。旧通用 loader 与旧 Root 表面留待 R5 删除，不等于仍需保留这个项目专用核心策略。

### 2.3 源码树受构建缓存污染，且污染会重新激活旧运行权威

当前源码范围内仍存在多组 `build/`、`*.egg-info`、`__pycache__` 和 `*.pyc`，包括：

- `plugins/curve_score/build` 与 `scidiscovery_curve_score.egg-info`；
- `plugins/ingaas_fig4/build` 与 `scidiscovery_ingaas_fig4.egg-info`；
- `plugins/tcad_artifact/build` 与 `tcad_artifact.egg-info`；
- `plugins/scholarly_evidence` 下的同类缓存；
- `src/scidiscovery.egg-info`、`src/scidiscovery/**/__pycache__` 及测试夹具缓存。

这不只是目录卫生问题。按当前源码 `PYTHONPATH` 独立读取 `importlib.metadata.entry_points()` 时，旧
egg-info 实际暴露三个 `scidiscovery.transform_adapters` 和两个
`scidiscovery.operation_specs`；`load_transform_adapters()` 实际加载
`CurveScoreTransformAdapter`、`InGaAsFig4TransformAdapter` 和
`TCADProjectTransformAdapter`。这会让本地调试路径重新出现第二套运行权威，与干净 wheel 的行为
不一致，也直接违背“源码无构建缓存污染”。

应删除所有精确构建产物和字节码缓存，然后在不向仓库源码写入缓存的模式下重跑聚焦/全仓验证。
清理后应同时断言活动源码环境与三种干净安装环境的旧两组 entry point 均为零。测试夹具先复制到
临时目录再构建的修复方向正确，但必须清除此前已经遗留的产物，不能只证明本次没有新增污染。

### 2.4 根发布清单与当前发布源不一致

使用 `scripts/build_git_release.py` 从当前工作树生成清洁发布目录后，生成清单包含 272 个被摘要
文件；当前根 `MANIFEST.sha256` 只有 265 项。根清单缺少 7 个当前发布文件，包括：

- R4-C-A/B 四份审查报告；
- `plugins/curve_score/curve_score/operation_transforms.py`；
- `plugins/curve_score/curve_score/plugin.py`；
- `plugins/ingaas_fig4/ingaas_fig4/plugin.py`。

另外已有 9 个文件的摘要不一致，包括安装脚本、R4 计划、curve-score 说明/配置、InGaAs 配置、
TCAD Operation 包装和调度提示。新生成的临时发布目录内部清单自校验通过且没有缓存，说明构建器
正常，问题是根清单尚未最终重建。

应在本报告及前三项返工完成后最后一次重建根清单，再用独立发布目录逐项比较文件集合与摘要。

## 三、已经通过的边界

### 3.1 单一注册、三种安装与摘要稳定性

- `plugins/ingaas_fig4/pyproject.toml:12-13` 只有
  `scidiscovery.plugins = ingaas_fig4.plugin:PLUGIN`；活动发布配置没有
  `scidiscovery.transform_adapters` 或 `scidiscovery.operation_specs`。
- 编译目录计数为：core 29（public 15/support 14）、默认 full 46（public 20/support 26）、显式
  InGaAs 47（public 20/support 27）。项目插件精确增加
  `ingaas.fig4-baseline-recovery.v2` 一项 support Operation。
- 干净安装测试证明 core 不安装三个领域包；默认 full 只有 TCAD/curve；显式安装只增加 InGaAs
  一项，且原 46 项摘要逐项不变。
- 插件选择器拒绝只选择 `ingaas_fig4` 而不选择其 `tcad_artifact` 依赖。

因此“默认不加载、显式安装一次注册编译、既有目录摘要不漂移”本身已经成立。

### 3.2 五输入、算法所有权与解释边界

Operation 精确声明 `scorer_project`、`curve_bundle`、`target_metrics`、
`historical_baseline`、`candidate_profile` 五个单项输入，并由原冻结评分函数完成：

- scorer project 的严格 `DeckProjectDraft` 解码与规范合同读取；
- curve CSV/target metrics 的冻结摘要和可重复指标检查；
- 两份 PLX 必需字段、有限性、正值、单调深度与覆盖检查；
- 全部五项输入摘要写入结果；
- baseline recovery 六项 gate 及项目专用解释边界。

`OperationDescription.not_for` 与结果的 `interpretation_boundary` 都明确禁止把确定性复现门升级为
机制归因或物理模型接受结论。项目算法留在 `ingaas_fig4`，没有迁入 TCAD 或 curve-score。除了
阻塞项 2.2 的旧核心策略外，通专分离方向正确。

### 3.3 旧 loader 的发布安装态边界

core、full、显式 InGaAs 三个干净 wheel 中，旧 transform-adapter 与 operation-spec entry point
均为空，`load_transform_adapters()` 返回空元组。旧 loader/Root 表面在干净发布态不是注册权威，
可以按计划留到 R5 删除。阻塞项 2.3 说明的源码缓存路径必须另行清理，不能用干净 wheel 结果掩盖。

## 四、独立验证证据

| 检查 | 结果 |
| --- | --- |
| InGaAs Operation、三种 clean wheel、部署/发布相关专项 | `34 passed in 28.44s` |
| 全仓回归 | `204 passed in 57.50s` |
| `git diff --check` | 通过 |
| `bash -n`：install/reinstall/InGaAs wrapper | 通过 |
| `python -m compileall`：核心、三个领域包、插件选择器 | 通过，但也再次证明必须隔离/清除字节码缓存 |
| 显式 `tcad_artifact,curve_score,ingaas_fig4` 部署 `--dry-run` | 通过；无部署状态变更 |
| 清洁发布构建与清单自校验 | 通过，272 个被摘要文件，无发布缓存 |
| 当前根清单对清洁发布清单 | 失败：缺 7 项，9 项摘要不同 |
| 源码 entry point 探针 | 失败：旧 transform 3 项、operation-spec 2 项被缓存重新暴露 |
| 完整输出畸变注入 | 失败：4 类畸形报告均被 validator 接受 |
| InGaAs/图号生产源码扫描 | 失败：通用核心仍有 1 个 Fig.4 专用 context profile |

未运行真实 Sentaurus、许可证或远端执行；R4-C-C 迁移的是冻结确定性项目 scorer 和插件发布边界，
不是求解器能力变更，因此该项不是本轮放行前提。

## 五、复杂度与架构判断

项目插件本身没有引入新注册表、状态机、领域路由器、角色或通用 Schema，新增扩展面是一个
`PluginDefinition`、一个 `support` Operation 和插件内薄包装，符合轻控制面、单一注册编译和
通专分离目标。保留冻结评分函数有现实生产消费者，属于有证据的最小项目扩展，不是过度设计。

反而应删除的是两类无效重量：无消费者的核心 Fig.4 context profile，以及只为旧入口/构建过程
残留的缓存元数据。`InGaAsFig4TransformAdapter` 类目前没有生产消费者、未由包顶层导出、也不再是
entry point；它可以随 R5 旧 loader 清理一并删除。该类本轮不构成独立阻塞，因为当前 Operation
只复用同模块的无状态评分函数，但不应重新成为兼容入口。

## 六、返工完成门

再次独立复审前至少满足：

1. 完整结果模型/validator 拒绝所有嵌套结构、键集合、类型和非有限数值畸变；
2. 通用生产源码扫描不再出现 InGaAs/Fig.4 项目逻辑；
3. 源码构建缓存清空，源码及三种 clean wheel 的旧两组 entry point 都为零；
4. 聚焦测试与全仓回归通过，运行过程不重新污染源码；
5. 最后重建根 `MANIFEST.sha256`，与独立清洁发布目录逐项一致。

## 最终结论

**打回。修复上述四个阻塞项并经独立复审明确通过前，不允许 R4-C 收口或进入 R4-D。**
