# R4-C-B Curve Score 单入口迁移独立审查

审查日期：2026-08-29  
审查范围：R4-C-A 第二轮放行后的 `curve_score` 单入口迁移、真实执行输出身份链、安装态入口与
当前活动调度合同。  
审查性质：只读跨边界、简化性与变更范围审查；未修改生产实现。

## 一、结论

**打回**

六个确定性能力的生产实现、单一插件入口、真实执行输出父链和四类 PLX 身份反例已经基本闭合，
源码态、清洁安装态及全仓回归也全部通过。但是，当前活动调度提示和插件双语说明仍公开旧的动态
输入名，与启动期编译目录的集合端口不一致；照此调度会在 `operation_preflight` 直接失败。另有
若干 R4-C-A 已冻结为完成门的身份与输出验证反例尚未成为可重复测试。因而本轮不能声明端到端合同
已经收口，也不允许进入 R4-C-C。

## 二、阻塞项

### 2.1 模型可见调度合同仍指向已删除的动态端口

位置：

- `roles/scheduler.md:153`—`159`；
- 由该源生成的当前 `AGENTS.md:149`—`159`；
- `plugins/curve_score/README.zh-CN.md:7`—`35` 与对应英文说明。

当前编译事实是：

- `scidiscovery.curve-bundle.sprocess-plx.v1` 消费
  `runtime_manifest`、`runtime_attestation`、`experiment_plan`、`solver_outputs`；
- `scidiscovery.curve-score.v1` 消费
  `curve_bundle`、`runtime_attestation`、`experiment_plan`、`reference_bundles`；
- 图表桥和覆盖检查同样只公开 `curve_tables`、`reference_bundles` 等有界集合端口。

但活动调度提示仍要求用 `solver_output__<series_key>` 和 `reference_curve__<name>`，还漏掉 PLX
操作必需的 `runtime_manifest`。这些名称只存在于 `operation_transforms.py` 内部调用旧算法的薄适配
层，不是目录端口。Root 会把按提示形成的调用判为未知端口或缺少端口，无法进入身份 guard。

插件说明还把三个不再登记目录的单项 normalizer、bare consistency 和不可再调用的 figure v1
与六个保留 Operation 并列为可用 Profiles，并继续描述 `curve_table__*` 等内部别名。这会把已经
收敛的单一编译权威重新暴露成第二套文字注册表，违背 R4-C-A 的明确裁剪结论。

影响：真实 scheduler 即使正确选择了目录中的 Operation，也可能依据更具体但过时的提示构造一个
必然失败的调用；新领域接入者也会把插件内部适配协议误认为公共注册协议。这直接偏离“轻控制面、
单一入口、OperationSpec 为唯一行为权威”的目标。

返工要求：

1. 更新 `roles/scheduler.md`，只说明从 `operation_catalog(scope="support")` 读取并绑定上述精确端口；
   不再公开任何内部动态别名；
2. 重新生成或同步 `AGENTS.md`，保证运行时父调度者看到相同合同；
3. 更新插件中英文说明，只列六个可调用 support Operation；三个内部函数明确标成非目录实现细节，
   figure v1 只说明历史 Artifact 可读而无新调用入口；
4. 增加一个模型可见合同回归，至少断言 scheduler 源中没有旧动态输入名，并与目录端口投影一致，
   防止以后再次漂移。

### 2.2 冻结的集合身份与输出验证完成门尚未有完整回归证据

位置：`tests/operations/test_curve_score_operation_plugin.py:1038`—`1130`。

已有论文图反例只有一张曲线表，因而不能证明“两张不同摘要表交换顺序”会失败；它覆盖的是父链和
摘要变化，不是集合错序。当前输出 validator 破坏测试也只篡改 figure bundle。评分输出和两个
coverage 输出没有各自的畸形旧算法返回值反例。引用曲线集合的内容身份实现虽按摘要排序并拒绝重复
内容，但测试只有单个引用 bundle，没有证明输入排列不改变结果、重复摘要会失败关闭。

这不是要求新增框架机制。生产代码中的对应逻辑已经保持在插件薄包装内，缺少的是冻结边界要求的
最小可重复证据：

1. 构造至少两个 figure series/table，正确 manifest 顺序成功，交换两个不同摘要表失败；
2. 对 `curve-score`、`curve-reference-coverage`、`objective-coverage` 的主输出分别注入不能通过声明
   Schema 的 bytes，证明编译输出 validator 而非旧适配器自觉性是最后门；
3. 用两个不同内容的 reference bundle 证明调用顺序不改变确定结果，并证明重复内容摘要被拒绝；
4. 保留当前缺项、额外端口和父链反例，不以新的宽松兼容分支绕过预检。

影响：实现从人工阅读看大体正确，但尚不足以满足 R4-C-A 第二轮报告明确要求独审查看的“论文图
集合身份、reference bundle 身份、输出 validator”完成门。此处应补测试，不应增加新 Schema、
注册表或控制状态。

## 三、已经通过的实现边界

### 3.1 单入口和六项最小表面成立

`plugins/curve_score/pyproject.toml` 只发布一个 `scidiscovery.plugins` 入口，指向
`curve_score.plugin:PLUGIN`；当前发布声明不再含 `scidiscovery.transform_adapters` 或
`scidiscovery.operation_specs`。独立编译所得目录为：

```text
public=20
support=26
internal=0
all=46
```

其中 `curve_score` 精确贡献六个 `support` Operation，没有单项 log/PLX normalizer、bare
consistency 或 figure v1 目录项。旧 `CurveScoreTransformAdapter` 只由六个薄 wrapper 在插件内部
复用算法，没有成为安装入口或第二次运行选择权威。核心没有新增领域路由器、集合 Schema 注册表、
数据库实体或持久化插件状态。

### 3.2 多 PLX 的真实执行身份链成立

`test_real_execution_outputs_reach_plx_operation_and_identity_failures_close` 真实走过：

```text
tcad.study.execute
→ 本地 UI 执行授权
→ ExecutionBridge collect
→ execution_outputs
→ tcad.runtime-attestation.v1
→ Root operation_invoke
→ scidiscovery.curve-bundle.sprocess-plx.v1
```

成功路径使用了 ExecutionBridge 登记的两个 PLX 与 runtime manifest，不是手工
`Mapping[str, bytes]`。以下四类污染均通过 Root 正式入口失败关闭：

1. 交换两个不同摘要 PLX：manifest 顺序与逐项摘要核对失败；
2. 混入另一执行中相同 Schema、相同字节长度的 PLX：execution 父链 guard 失败；
3. 换入另一执行的 manifest：manifest/PLX 父链不一致；
4. passing attestation 没有直接包含全部输出：attestation 父链 guard 失败。

实现同时核对成功终态、退出码、逻辑名、`solver_native` 分类、媒体类型、大小和 SHA-256。科学
series 来自实验计划，原始字节身份来自 runtime manifest，职责没有混入核心或文件名猜测。

### 3.3 评分、图表和覆盖算法是薄复用

六项均至少有一个成功执行路径。薄 wrapper 只完成集合到旧无状态算法入参的确定映射，再由统一
`CompiledTransformAdapter` 按端口输出并执行 validator。reference bundle 由严格 `CurveBundle`
内容给出 series 身份，内部临时名仅按内容摘要稳定排序；图表由 manifest panel/series 顺序、
validation report 摘要及 CSV 自描述列共同绑定。确定性代码没有解释科学机制，support 视图也没有
污染公共规划候选。

### 3.4 安装态和旧旁路

清洁 core-only/full wheel 测试证明：

- core-only 只发现 `builtin` 与 `general_science`；
- full 只再发现标准 `tcad_artifact`、`curve_score` 插件入口；
- legacy transform adapter 与断裂 operation-spec 入口均为空；
- full 目录包含精确六个 curve Operation，figure v1 不存在。

本地源码树仍有被 `.gitignore` 排除的旧 editable `egg-info`，会在直接把插件目录放入
`PYTHONPATH` 时显示旧 entry point；它不进入 clean wheel，也不是版本控制内容。启动长期本地服务前
仍需重装 editable 包，但不应为此增加兼容 loader。测试夹具第一次安装复跑还发现三个被忽略的
生成 `build/egg-info` 目录导致 setuptools 递归；主进程已把精确目录移动到可恢复的 `/tmp` 隔离区，
清理后安装态和全仓测试均正常。该环境事件不是生产实现缺陷，但本报告保留其原始记录。

## 四、独立验证结果

| 检查 | 结果 |
| --- | --- |
| `test_curve_score_operation_plugin.py`、安装目录、基线插件发现、部署脚本聚焦集 | 首次 `32 passed, 9 errors`，错误均为测试夹具生成目录递归；隔离后 `41 passed in 31.21s` |
| 全仓 `pytest -q` | `195 passed in 51.32s` |
| `bash -n deploy/install.sh` | 通过 |
| `python -m compileall -q src plugins/curve_score plugins/tcad_artifact` | 通过 |
| `git diff --check` | 通过 |
| `deploy/install.sh --dry-run`，独立临时 workspace | 通过；明确报告没有修改包、状态、服务或平台配置 |
| 独立目录编译 | 46 项；`public=20/support=26/internal=0`；curve-score 精确六项且全为 support |

dry-run 期间宿主 systemd 对无关 netplan 权限和旧版 systemd 键给出环境警告，但目标部署预览通过，
不构成本轮缺陷。未运行真实 Sentaurus、许可证和远端求解器；R4-C-B 验证的是执行 Artifact 身份与
确定性曲线处理，不外推为物理仿真合格。

## 五、复杂度与架构目标判断

本轮生产实现没有把集合身份问题推回通用核心，而是在唯一领域插件的 manifest/content 映射和
guard 中关闭；也没有把六个 helper 提升成 public 科研动作。这个方向符合“OperationSpec 行为
闭包、轻控制面、通专分离、最小上下文授权”。阻塞项的正确修法是同步活动合同并补足边界测试，
不是再增加角色、状态机、注册表、动态端口类型或新的抽象实体。

## 最终结论

**打回。修复上述两个阻塞项并由独立审查者复核通过前，不允许进入 R4-C-C。**
