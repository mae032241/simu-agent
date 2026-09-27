# R4-C-B Curve Score 单入口迁移第二轮独立复审

审查日期：2026-08-29  
审查范围：首轮报告两个阻塞项返工后的活动调度合同、插件说明与新增边界回归。  
审查性质：只读复审；未修改生产实现。

## 一、结论

**通过，允许进入 R4-C-C**

首轮两个阻塞项均已按最小范围关闭。返工只同步了模型可见合同并补足既有插件 guard/validator 的
可重复证据，没有新增 Schema、注册表、状态、角色、路由器或控制面分支。R4-C-B 现在满足单一
编译权威、六项最小 support 表面、集合身份失败关闭和真实执行输出父链的完成门。

## 二、首轮阻塞项关闭情况

### 2.1 活动调度合同已与编译端口一致

`roles/scheduler.md` 及当前生成的 `AGENTS.md` 已明确要求：

- PLX bundle 绑定 `runtime_manifest`、`runtime_attestation`、`experiment_plan` 和有序
  `solver_outputs`；
- 通用评分绑定 `curve_bundle`、`runtime_attestation`、`experiment_plan` 和可选
  `reference_bundles`；
- 论文图与覆盖操作通过 `curve_tables`、`reference_bundles` 集合端口调用；
- 精确端口必须从 `operation_catalog(scope="support")` 读取，内部适配别名不是调度合同。

活动提示中已不存在 `solver_output__<series_key>`、`reference_curve__<name>` 或
`curve_table__<panel_key>__<series_key>` 等内部动态别名。专项测试直接比较六项编译 Operation 的
输入端口清单，并检查 scheduler 源和生成提示所需集合名及旧别名消失，因此不再依赖人工同步。

`plugins/curve_score/README.md` 与 `README.zh-CN.md` 也只列六个可调用 `support` Operation，端口与
目录一致。单项日志/PLX 归一化及 bare consistency 被明确标为内部函数；figure v1 只保留历史
Artifact 语义，当前目录不能创建 v1 产物。说明文件不再构成第二套行为注册表。

### 2.2 集合身份和输出 validator 证据已经补齐

新增论文图双 series fixture 产生两个内容摘要不同的 CSV：按 manifest 顺序调用成功并得到
`reference, candidate`，交换集合成员后在 executor 摘要映射处失败。validation report 的父链同时
包含精确 manifest 和两张表，因此该反例证明的是集合错序，不是用缺父项代替错序。

引用集合测试使用两个不同内容、不同 series 身份的 `CurveBundle`：交换调用顺序后 coverage 输出
字节完全一致，证明插件按内容摘要建立稳定内部顺序；把同一内容通过另一 Artifact 再次输入则因
重复摘要失败关闭。科学身份仍来自严格 bundle 内容，没有恢复调用方动态别名。

评分、reference coverage 和 objective coverage 三项分别将旧算法的主输出替换为畸形 JSON
对象。旧算法调用本身已返回，随后由各自编译输出端口的严格模型 validator 拒绝；测试还区分该
ValueError 与 executor 包装错误，证明失败发生在统一输出门。figure 输出 validator 的注入已改用
真实 dataclass 替换，亦确实到达输出校验而不是提前因错误测试写法失败。

## 三、生产实现边界复核

### 3.1 单一入口和最小目录未退化

独立编译仍得到 46 项：`public=20/support=26/internal=0`。`curve_score` 精确贡献以下六项且全部为
support：

1. `scidiscovery.curve-bundle.sprocess-plx.v1`；
2. `scidiscovery.curve-score.v1`；
3. `scidiscovery.curve-score.sprocess-log.v1`；
4. `scidiscovery.curve-bundle.figure-evidence.v2`；
5. `scidiscovery.curve-reference-coverage.v1`；
6. `scidiscovery.objective-coverage.v1`。

插件发布配置仍只有 `scidiscovery.plugins = curve_score.plugin:PLUGIN`。旧适配器只是六个 wrapper
内部复用的无状态算法门面；没有旧 transform 或 operation-spec entry point，也没有 figure v1、
单项 normalizer 或 consistency 目录项。

### 3.2 真实 PLX 执行身份链保持通过

首轮已经独立核验并在本轮专项继续通过的路径为：真实本地执行审批、`ExecutionBridge` 收集、
`execution_outputs` 登记、TCAD runtime attestation、Root `operation_invoke`、PLX bundle。成功调用
使用的是执行桥返回的 Artifact。成员交换、另一执行的同 Schema/同长度 PLX、另一执行 manifest、
attestation 缺少一个输出四类污染继续全部失败关闭。

此次返工没有修改 production `operation_transforms.py`、Root、ExecutionBridge、Artifact、目录编译
或执行生命周期，因而没有为了修测试引入新的旁路或权威。

## 四、独立验证结果

| 检查 | 第二轮结果 |
| --- | --- |
| `test_curve_score_operation_plugin.py`、clean installed catalog、baseline plugin discovery | `18 passed in 27.60s` |
| scheduler 源与生成提示旧动态别名扫描 | 三个旧别名均不存在；所需集合端口均存在 |
| 独立目录编译 | 46 项；`public=20/support=26/internal=0`；curve-score 精确六项 support |
| `git diff --check` | 通过 |
| `bash -n deploy/install.sh` | 通过 |
| `python -m compileall -q plugins/curve_score tests/operations/test_curve_score_operation_plugin.py` | 通过 |

首轮同一生产实现已经独立全仓通过 `195 passed`，并通过 clean core/full wheel、部署 dry-run 和真实
Root 执行身份链。本轮改动范围是提示、双语说明和新增测试，故以能直接失败于两个原阻塞的 18 项
专项作为最小可信复审；主进程仍应在发布清单最终重建后再运行一次全仓收口。

安装态测试的 `pip wheel` 会在三个未跟踪测试夹具源目录生成被忽略的 `build/egg-info`，第二次直接
构建前需把这些精确缓存隔离，否则 setuptools 会递归扫描。它是现有测试夹具卫生债务，不进入发布
wheel，也没有影响本次从清洁夹具开始的安装态结果；后续可让 fixture 先复制到临时目录再构建，
无需增加产品控制层。

## 五、架构目标判断

返工没有把文档漂移问题解决成新的配置实体，也没有为集合测试增加通用动态端口或领域路由。调用
者只看编译 OperationSpec 端口，插件内部才负责把内容身份映射到旧算法；控制面继续只做不可变
Artifact、精确父链、预检和输出验证。该实现保持了轻控制面、通专分离、单一注册编译入口以及
最小上下文授权的原定方向。

## 最终结论

**通过，允许进入 R4-C-C。**
