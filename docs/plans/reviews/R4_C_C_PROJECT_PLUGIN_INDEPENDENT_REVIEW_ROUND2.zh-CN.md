# R4-C-C 项目插件迁移第二轮独立复审

审查日期：2026-08-29  
审查范围：首轮四个阻塞项及第二轮首次复审两个剩余阻塞项返工后的 InGaAs 输出合同、项目语义
隔离、源码入口与构建卫生、测试发现机制和发布收口准备。  
审查性质：独立复审；未修改生产实现。

## 一、当前结论

**通过，允许 R4-C 收口并进入 R4-D；以本报告本次结论写入后的最后一次机械发布清单重建并通过
只读一致性核验为生效条件。**

首轮及第二轮首次复审发现的实现阻塞现已全部关闭：项目输出具有一个完整、严格、含最小科学
自洽的模型；项目/图号语义只存在于可选项目插件；源码与 clean wheel 的旧两组入口均为零；聚焦
与全仓回归不再向源码树写入构建缓存。测试内显式默认完整插件元数据仍只负责源码测试装配，没有
替代真实 wheel 发现。

实现、插件、安装和发布内容均已通过。独立审查者还从冻结工作树重新生成一份清洁发布目录，确认
当时根 `MANIFEST.sha256` 与生成清单字节一致，274 个被摘要文件的集合和逐项摘要完全一致。本报告
本身属于发布源；把本段从“待核验”改为正式通过会使该报告摘要发生最后一次变化。因此主进程只需
在本报告写入后机械重建清单，独立审查者再执行一次不修改报告的只读一致性核验，条件即告满足。

## 二、输出合同返工复核

### 2.1 一个模型同时生成 Schema 并执行运行验证

`plugins/ingaas_fig4/ingaas_fig4/plugin.py` 的 `_MetricReport` 与全部嵌套模型使用：

- `extra="forbid"`；
- 严格类型；
- `allow_inf_nan=False`；
- 精确版本、五个具名 SHA-256 输入摘要；
- raw reproduction、baseline recovery、两份 curve metrics、residual regions 的完整结构；
- 由冻结评分函数和 validator 共享的精确 `INTERPRETATION_BOUNDARY`。

`RESULT_SCHEMA` 直接由该模型生成，`RESULT_VALIDATOR` 也直接消费同一个模型，没有另建 Schema
注册表或第二套文字合同。Operation 仍只薄包装原冻结无状态评分函数。

### 2.2 科学语义和最小自洽已经失败关闭

全部定义上非负的 RMS 与最大绝对残差字段均使用非负有限浮点类型。模型只增加不依赖 scorer
project 可变阈值的数学恒等约束：

- raw reproduction RMS 不得大于其最大绝对残差；
- baseline recovery RMS 不得大于其最大绝对残差；
- residual region RMS 不得大于该区域峰值绝对残差；
- raw reproduction 的 pass 必须等于最大残差是否不超过 `1e-9`；
- baseline recovery 的 pass 必须等于六个 checks 的合取。

独立以真实成功报告为基准注入 15 类畸变，错误/空白解释、负 RMS/最大残差、RMS 大于最大/峰值、
raw pass 翻转、recovery pass 翻转和 checks 合取不一致均被统一输出 validator 拒绝。项目合同没有
复制 scorer project 中可变的六项阈值，避免形成第二科学权威。

新增回归同时覆盖错误/空白解释、四类负 RMS、两类 pass 翻转和 checks 合取不一致，能够直接防止
本轮缺陷回归。

## 三、通专分离与单入口复核

独立扫描以下共享生产范围已无 `ingaas`、`fig.4` 或 `fig4-baseline`：

- `src/scidiscovery`；
- `plugins/tcad_artifact/tcad_artifact`；
- `plugins/curve_score/curve_score`；
- `roles/scheduler.md`；
- 当前根 `AGENTS.md`。

首轮发现的通用核心 Fig.4 context profile 已删除且没有遗留消费者。项目语义只存在于默认不安装的
`ingaas_fig4` 项目插件、其测试及历史文档。

安装与目录边界保持不变：

- 项目包只有 `scidiscovery.plugins = ingaas_fig4.plugin:PLUGIN` 一个入口；
- 插件精确声明一个 `support` Operation；
- core 不加载领域包；默认 full 只有 TCAD/curve；显式 InGaAs 安装只新增该一项；
- 显式安装不改变既有 46 个 Operation 的任何摘要；
- 旧 `scidiscovery.transform_adapters`、`scidiscovery.operation_specs` 在源码与三种 clean wheel 中
  均为空，`load_transform_adapters()` 返回空元组。

因此旧 loader 只是 R5 待删代码，不再是发布或开发运行权威。

## 四、源码构建卫生返工复核

`deploy/install_ssh_tcad_runner.sh` 的本地 runner 语法校验现通过
`tempfile.TemporaryDirectory` 和 `py_compile.compile(..., cfile=<临时文件>, doraise=True)` 执行。
成功或异常离开上下文都会清理临时 pyc，不再把显式编译结果写到源文件旁。

独立重跑聚焦 44 项和全仓 207 项后，立即扫描 `src`、`plugins`、`tests/fixtures`：

- 无 `build/`；
- 无 `*.egg-info`；
- 无 `__pycache__`；
- 无 `*.pyc` 或 `*.pyo`。

源码 entry-point 探针在测试后仍返回旧两组入口为空，证明此次修复不只是测试前手工清理。

## 五、测试内显式默认完整插件元数据审查

`tests/conftest.py` 只在 pytest 进程内 monkeypatch
`scidiscovery.operations.catalog.entry_points`，为没有安装元数据的源码 checkout 显式提供默认 full
的四个标准 `scidiscovery.plugins` 条目：builtin、general science、TCAD、curve-score。它不包含
可选 InGaAs，也不引入旧 transform 或 operation-spec 入口。

该做法可以接受：

- 它只属于测试代码，不进入 wheel 或生产运行时；
- 每个测试前后清空 compiled catalog 缓存；
- `installed_probe` 通过独立虚拟环境子进程执行，父 pytest monkeypatch 不传播；
- clean core/full/InGaAs、错误插件及 Operation 摘要均在子进程中读取真实 wheel entry point；
- 真实安装测试继续存在且本轮独立通过。

因此该 fixture 是源码测试装配，不是第二个产品注册表，也没有掩盖打包元数据缺陷。未来不能用它
取代 clean-wheel 测试；本轮没有必要为形式纯度增加额外测试装配系统。

## 六、独立验证结果

| 检查 | 结果 |
| --- | --- |
| 15 类独立输出畸变注入 | 全部由统一 validator 拒绝 |
| InGaAs、三种 clean wheel、目录入口、部署/发布聚焦回归 | `44 passed in 34.47s` |
| 全仓回归 | `207 passed in 59.13s` |
| 聚焦与全仓后的源码缓存扫描 | 零命中 |
| 活动源码旧 transform/operation-spec 探针 | 两组均为零，loader 返回空元组 |
| 共享生产代码项目语义扫描 | 零命中 |
| 显式 `tcad_artifact,curve_score,ingaas_fig4` 部署 dry-run | 通过，无部署状态变更 |
| install/reinstall/InGaAs/SSH runner shell 语法 | 通过 |
| `git diff --check` | 通过 |
| 独立清洁发布树与更新结论前的根清单 | 274 项文件集合及逐项摘要完全一致 |
| 独立发布树重新构建三组 wheel | core=29、full=46、InGaAs=47；旧两组入口为零 |
| 显式项目 wheel 对既有目录摘要 | 既有 46 项逐项不变，只新增一个 InGaAs support Operation |

测试使用 `PYTHONDONTWRITEBYTECODE=1` 和禁用 pytest cache；SSH runner 的显式 py_compile 另由临时
cfile 保证不写源码。未运行真实 Sentaurus、许可证或远端 solver；本阶段改变的是冻结确定性项目
scorer 的输出门与插件/发布边界，不是 solver 实现，故该项不是 R4-C-C 完成前提。

## 七、复杂度与架构判断

返工只增加项目插件内部严格结果模型、共享解释常量、少量数学自洽 validator，并删除无消费者的
核心项目策略及构建污染。没有新增控制状态、注册表、路由器、角色、通用 Schema 或领域核心分支。
它保持了轻控制面、单一插件入口、通专分离与最小扩展面。

项目包中旧 `InGaAsFig4TransformAdapter` 类仍无发布入口和生产消费者；当前 Operation 只复用同模块
评分函数。它可以随 R5 旧 loader 代码统一删除，不构成本阶段第二权威，也不值得为本轮另开兼容
抽象。

## 八、最终发布清单核验

独立审查者使用新的临时目录 `/tmp/scid-r4cc-independent.qGvCf7/release` 从冻结后的工作树重新生成
发布树，构建器报告 275 个发布源文件；清单自身不摘要，故清单包含 274 项。核验结果：

- 根清单与独立生成清单字节完全一致；
- 274 个路径集合完全一致，每一项 SHA-256 与清洁发布字节一致；
- 发布树没有 `build`、`*.egg-info`、`__pycache__`、`*.pyc` 或 `*.pyo`；
- 所有发布 `pyproject.toml` 都没有旧 transform-adapter 或 operation-spec 入口；
- 从该发布树重新构建并安装的 core/full/InGaAs wheel 目录分别为 29/46/47，旧入口均为空，显式
  项目安装只新增一个 InGaAs support Operation，既有摘要不变。

唯一剩余动作是处理清单的正常非自引用性质：`MANIFEST.sha256` 不摘要自身，却必须摘要本报告。
本次正式结论写入后，主进程应只重建根清单，不再修改其他发布文件；然后独立审查者只读比较根
清单与新生成清洁发布清单。该最后一次比较不需要、也不得再次修改本报告。

## 当前阶段结论

**通过，允许 R4-C 收口并进入 R4-D；该结论在本报告写入后的根清单完成最后一次机械重建且只读
一致性核验通过时生效。在此条件满足前不得进入 R4-D。**
