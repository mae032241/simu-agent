# R4-B 独立审查报告

状态：独立审查完成（通过）  
审查对象：R4-A 第四轮放行后的 R4-B 增量及当前共享工作树  
审查方法：跨边界闭环审查、最小复杂度审查、源码与安装态双重核验、聚焦与全量测试独立复跑

## 结论摘要

R4-B 已把六个 TCAD 确定性变换和一个外部执行 Effect 纳入 `tcad_artifact` 的同一
`PluginDefinition`/`CompiledCatalog`。六个机械变换属于同一目录的 `support` 投影，不污染默认
科研规划候选；author、独立 reviewer 和 `tcad.study.execute` 保持 `public`。旧 TCAD transform
entry point 已从发布声明删除；即使显式向 Root 注入旧适配器，同名已迁移 profile 也会被通用
入口拒绝，不能绕过 `operation_invoke`。

`tcad.study.execute` 只创建既有 `ExecutionRequest`，不直接启动外部副作用。执行仍需为精确
request/package 创建本地 UI 审批，并由原 `ExecutionService`/`ExecutionBridge` 完成授权校验、
prepare、submit、status、collect 和封存。真实本地 UI 授权测试已经走通 collect、输出绑定和编译
后的 runtime-attestation；无审批路径没有获得提交权。

运行时配置由两个通用 daemon 的可重复 `--plugin-config plugin_id=path` 入口装配。服务和执行器
键由加载器按组件所属插件限定，另一个插件声明同名局部键不能冒充 TCAD Effect 或调试工具。
加载器没有增加数据库表、生命周期或第二个注册系统，`CompiledCatalog` 中的 runtime factory 只是
同一编译闭包的启动期投影。

审查过程中发现的安装脚本语法、旧探针、载荷模式版本、显式旧适配器旁路、运行时清单模式、
失败清单可解析性、跨插件同名绑定、三视图污染、执行输出父链、可信 TaskService 注入边界和成功
路径证据不足均已逐项修复并有回归测试。本轮独立复跑聚焦 17 项和全仓 190 项全部通过；安装
dry-run、shell 语法、静态编译和差异检查通过。当前未发现 R4-B 阻塞缺陷。

## 一、范围和证据基线

当前工作树包含 R0—R4-B 的连续未提交重构，不能把整个 `git diff` 误称为只有 R4-B。此次重点
直接核验：

- `plugins/tcad_artifact/tcad_artifact/plugin.py`、`operation_transforms.py`、
  `runtime_plugin.py` 和插件 `pyproject.toml`；
- `src/scidiscovery/operations/spec.py`、`catalog.py`、`invoke.py`、`runtime_plugins.py`；
- Root 调用、执行桥、Task/Worker router、两个 daemon 和部署 systemd/install 入口；
- TCAD 插件、运行时配置、安装态、执行生命周期和父链测试；
- R4 实施记录及 R4-A 第四轮放行后保留的架构约束。

本报告只判断 R4-B 的架构与实现边界，不把 fake adapter 测试外推为真实 Sentaurus 求解器、许可证、
远端传输、物理模型正确性或科学结论已经合格。

## 二、六个 TCAD 变换已进入同一目录

### 2.1 单一声明、单一调用权威

`tcad_artifact.plugin:PLUGIN` 同时声明 author/reviewer、六个 transform、Effect、运行时工厂、
专业资源和窄 workspace/tool 组件。六个 transform 是：

- `tcad.deck-project-compare.v1`；
- `tcad.deck-review-validate.v1`；
- `tcad.reviewed-deck-package.v2`；
- `tcad.runtime-attestation.v1`；
- `tcad.realization-snapshot-materialize.v1`；
- `tcad.control-equivalence.v1`。

`operation_transforms.py` 没有复制原算法，而是把编译端口集合薄适配到既有无状态
`TCADProjectTransformAdapter`。Root 对 transform 的正式入口是
`operation_invoke → preflight_operation → CompiledTransformAdapter → Artifact 注册`。
`artifact_transform` 在发现当前目录已有同名 transform Operation 时通用地失败关闭；测试还显式
注入旧 TCAD adapter，证明不能借旧入口调用已迁移 profile。

插件发布配置只保留标准 `scidiscovery.plugins` 入口，不再发布 TCAD
`scidiscovery.transform_adapters`、role pack 或旧 operation-spec 入口。clean full 安装态只发现
curve-score 的旧 transform adapter；它属于 R4-C 的明确迁移范围，不是 TCAD 第二权威。

当前开发环境存在由旧 editable 安装遗留、且不受版本控制的
`plugins/tcad_artifact/tcad_artifact.egg-info/entry_points.txt`。它不是当前发布声明，clean wheel 测试
不会携带它；对六个同名已迁移 profile，Root 的目录检查仍会拒绝旁路。启动本地长期调试服务前
仍应重装 editable 元数据，避免把环境残留误认为当前插件能力。该清理不需要修改架构或新增门面。

### 2.2 声明与实现证据闭合

独立检查测试确认六项不是只“能编译”：

- compare 和 review-validation 经过编译 Operation 的预检与真实适配调用；
- reviewed-package 成功解析严格 project/review/capability/plan，输出端口明确冻结
  `payload_schema_version=2`；
- realization 和 control-equivalence 经过同一 `CompiledTransformAdapter` 执行既有算法并检查
  输出 schema/集合；
- runtime-attestation 既有跨执行输出拒绝负例，也有真实 ExecutionBridge 收集后经
  `operation_invoke` 生成 attestation 的成功路径。

`OutputPortSpec.payload_schema_version` 现在是显式、至少为 1 的编译字段，Operation ABI 为 5；
通用适配器逐端口传播，不再把 v2 包伪注册为 v1。

### 2.3 父链和集合没有断裂

package guard 要求独立 review 的父链含精确 project、capability 和 experiment plan；可选 reference
与 objective coverage 也核对相应父项。runtime guard 按端口分组，要求 manifest 来自所审查包的
执行父链，且每个原始 runtime output 与 manifest 具有完全相同的执行父链；另一执行产生的同字节
输出不能混入。

runtime manifest 作为 `opaque/application-json` 由 TCAD callable 严格解析，而不是由通用核心假装
理解 TCAD schema。启动前失败的正式 manifest 允许 `started_at=null`，仍能生成明确失败的
attestation；这没有把失败输出提升为合格科学证据。

## 三、Effect、审批与能力发现

### 3.1 Effect 不拥有外部执行生命周期

`tcad.study.execute` 的编译 Effect 只冻结三项：所属插件限定后的 executor、本次 preparation
profile 和唯一 payload port。`operation_preflight` 先让 TCAD adapter 严格解析
`tcad.reviewed-deck-package.v2`；`operation_invoke` 随后只调用既有
`execution_request_create`。此时状态仍为 created，没有调用 adapter submit。

审批请求从 ExecutionRequest 上的 operation id/version/digest 反查当前编译审批合同，冻结精确
request/package 两个 subject；合同变化、操作卸载、主体歧义或 projector 失败都会拒绝。只有本地
UI 形成的 `execution_authorization` 决定被既有服务核对后，`execution_start` 才能提交。测试通过
真实 loopback UI POST，而不是直接在测试中伪造服务端授权。

旧 `execution_request_create` Root 表面仍为历史过渡入口，R4-B 没有复制或改造它；R5 已明确负责
删除旧入口。TCAD 正式调度路径只经 `tcad.study.execute`，本阶段为了删除一个通用旧表面而扩张
Effect/审批改造反而会越界。

### 3.2 capability 与 Effect 绑定

`execution_capabilities` 和 `execution_capability_bind` 接受的是编译 Effect 的 `operation_id`，不能
再用裸 executor 名做调度合同。Effect 返回的局部 `tcad` 在通用调用层限定为
`tcad_artifact:tcad`。另一个插件即使返回同名局部执行器，也只能得到自己的限定键，不能满足 TCAD
Effect。

通用 ExecutionBridge 只核对 capability 文档的有界机械合同；socket/command TCAD adapter 负责
严格解析 `tcad.solver-capability.v2` 并冻结公开快照。因此领域 Schema 没有重新硬编码进核心。

## 四、启动期配置和权限边界

### 4.1 单一启动配置投影

两个 daemon 只新增可重复的 `--plugin-config`，没有 TCAD 专用 CLI 参数或 import。加载器拒绝
重复插件编号、未知/无编译运行时工厂的插件、符号链接、非普通文件和超过 1 MiB 的配置；插件自身
用严格 Pydantic 模型决定 socket 或 command transport。安装脚本以 root/服务组、`0640` 写入同一
`tcad-plugin.json`，并把它同时传给控制和 Worker 服务。

runtime contribution 只含内存中的限定执行器、限定工具服务和可恢复服务 reconciler。它没有新表、
第二 registry、持久插件状态或平行执行生命周期；Operation 仍只由 CompiledCatalog 决定。

### 4.2 可信安装插件不等于任务内 Agent 权限

`runtime_factory` 是已安装并受信的控制侧 Python 扩展，不是 Worker 能力，也不是针对恶意插件的
OS 沙箱。普通工厂默认拿不到 `TaskService`；只有编译组件显式声明
`requires_worker_task_service=True` 时，Worker daemon 才在启动期注入。TCAD 是当前唯一声明者，
用于复用既有任务令牌、租约、调试快照和恢复生命周期。

这一受信扩展边界没有传播到任务内 Agent：RuntimePluginContext 不进入 Worker router；router 只
持有按插件限定的 `TCADDebugService` 映射；具体工具还要经过精确 task/attempt/operation
capability 和所声明 `required_services`。reviewer 没有 debug tool，普通 Agent、transform、Effect
和 workspace hook 都拿不到 TaskService。跨插件同名服务负例证明不能越权满足 TCAD author。

给 TCAD 插件再造一个复制 TaskService 状态和恢复逻辑的“窄服务”会形成第二生命周期。当前实现
对可信边界的描述是诚实的，也保持了任务内最小权限；若未来要支持不受信第三方 Python 插件，应
单独设计进程/系统级隔离，不能把当前类型门面宣传为安全沙箱。

## 五、三视图、核心去领域化与阶段边界

独立编译当前 full catalog 得到：

```text
public=20, support=20, internal=0
```

TCAD 的 author 三项、reviewer 和 `tcad.study.execute` 为 public；六个机械 transform 全部为
support。即使所有输入 Schema 都存在，默认 readiness 也不会把这些机械步骤当成可选科研行为；
调度器可在已选择 public 行动之后按精确名称调用 support 操作。三种视图是同一目录的投影，不是
三套注册表。

TaskService、Worker router、Codex 平台和两个 daemon 没有按 TCAD role、context、Schema、参数或
领域 import 分派这些新行为。R4-B 没有新增 TCAD readiness 拓扑、数据库状态或领域 Scheduler
指令。

本阶段也没有提前实现 R4-C/D：curve-score 旧 adapter 仍在，TCAD 审批 projector 只是
`external Effect` 当前可执行所需的最小编译组件，没有迁移通用 UI renderer 或重写审批系统。

## 六、33 项架构约束与复杂度判断

仓库没有逐项编号的“33/33”自动检查器，本报告不伪称运行了这样的脚本。按已冻结约束族复核，
本轮未见以下能力退化：单一编译权威、不可变 Artifact、精确父链、独立 review、显式人工外部副
作用审批、默认拒绝、任务私有 Worker、内容寻址、幂等创建、既有执行生命周期、错误终态证明和
确定性输出封存。

通用核心当前行数为：

```text
spec.py=350
catalog.py=486
invoke.py=450
runtime_plugins.py=162
```

领域端 `plugin.py + operation_transforms.py + runtime_plugin.py` 为 1249 行，其中多数是既有严格
Schema 端口、TCAD Agent 合同和六项薄适配声明。`runtime_plugins.py` 只负责启动期读取、限定和
合并已编译工厂，没有演化成生命周期控制器。新增 162 行通用代码对应真实的控制/Worker 双进程
装配、失败关闭和跨插件同名隔离，当前没有更小且仍能闭合这些边界的重复实体可删除。

需要继续守住复杂度门：R4-C 只迁移最后的 curve-score/示例插件旧入口，R5 必须兑现旧 Root 表面
和领域遗留注册的删除，不能继续为每个领域增加 runtime hook 类型或并行权限状态。

## 七、独立验证结果

| 检查 | 独立结果 |
| --- | --- |
| `tests/operations/test_tcad_operation_plugin.py` 与 `test_runtime_plugin_configuration.py` | `17 passed in 4.77s` |
| 全仓 `pytest -q` | `190 passed in 75.45s` |
| `bash -n deploy/install.sh` | 通过 |
| `python -m compileall -q src plugins/tcad_artifact plugins/curve_score` | 通过 |
| `git diff --check` | 通过 |
| 独立 `deploy/install.sh --dry-run`（独立临时 workspace） | 通过；未修改包、状态、服务或平台配置 |
| clean core-only/full/architecture/broken-plugin 安装态 | 包含在全仓测试并通过 |

dry-run 中 `systemd-analyze` 对宿主 `netplan-ovs-cleanup` 权限和旧版 systemd 不识别
`RestartMode` 给出环境警告，但目标 unit 校验和 deployment preview 均通过；这不是本仓库服务
模板失败。

## 八、非阻塞债务

1. 当前同进程 Python 插件是可信安装代码，不具备恶意插件强隔离；后续若开放第三方插件，应在
   独立阶段引入进程或系统级边界，而不是在 OperationSpec 中继续堆权限字段。
2. 本地旧 editable egg-info 需要在启动开发 daemon 前重装；clean wheel 和发布入口已经正确，且
   六个迁移 profile 当前不能借残留适配器绕过目录。
3. `TCADRuntimeManifest.started_at` 为了诚实表示“提交前失败”允许 `null`；成功终态是否强制非空可
   在领域模型中追加条件校验，但当前失败/成功链均有明确终态和时间，不阻塞 R4-B。
4. 通用 `RuntimePluginContribution` 没有在构造时提前检查 reconciler 的 `reconcile` 方法；错误的
   可信插件会在启动/后台调用时失败而不会越权。可在后续做一个小型启动期协议校验，无需新增
   reconciler registry。
5. 插件 distribution 版本/描述仍沿用基线 `0.1.0` 和“execution-only”措辞，而内部
   `PluginDefinition` 已为 `0.2.0` 且能力扩大。它不影响编译摘要和运行权限，但发布前应统一版本与
   包描述。
6. 报告写入后发布 `MANIFEST.sha256` 必然需要重建并包含本报告；这是发布收尾顺序，不是增加第二
   清单。重建后应只读复核清单和 clean 安装态，如不一致则不得进入下一阶段。

## 最终结论

通过，允许进入 R4-C
