# R5 E5：同一 Operation 创建／修订双模式计划

状态：完成。计划复审 PASS；P4 首轮一个动态调用面阻断已按最小范围修复，第二轮独立复审 PASS、
剩余阻断 0；clean release 与安装前 dry-run 已通过。等待真实重装后继续 E5。

## 1. 要解决的问题

`science.evidence.extract.figure.v2` 已能从一个完整、同源的图证据文件族产生
`ScientificIntake`，但审查不通过后只能尝试另一个通用修订 Operation。后者既不知道图证据
文件族，也不能证明修订仍绑定原始曲线表、图像和机械校验报告。为此再增加
`science.intake.revise.figure.v1` 虽能补齐当前拓扑，却会把同一个科学行为拆成创建／修订两项
公开能力，并诱发每个领域都复制一项 `revise.*`。

本轮将修订定义为同一行为闭包的再次调用：

```text
science.evidence.extract.figure.v2
  创建模式：完整图证据文件族 -> ScientificIntake
  修订模式：完整图证据文件族 + prior_draft + change_request
            -> 新版本 ScientificIntake

science.figure.evidence.audit.v1
  始终是独立 Operation，审查创建结果或任一修订结果
```

## 2. 最小设计

### 2.1 不增加新的核心实体

复用现有 `InputPortSpec`、`InputAdmissionSpec`、`ReviewSpec` 和直接完整对象修订机制：

- `prior_draft`：`min_items=0, max_items=1, usage=revision_base`；
- `change_request`：`min_items=0, max_items=1, usage=change_request`；
- 一个无审批的 `InputAdmissionSpec` 把二者声明为全有或全无的输入组；
- 二者都未绑定时是创建模式；二者都绑定时是修订模式；
- 输出 Schema、工具、完整图族、审查边和最大修订次数均属于同一个 OperationSpec；
- 修订仍是完整对象、写时复制、不可变新版本，不接受补丁作为科学结果。

这不是 Agent 实时决定模式。模式只由已经冻结的输入绑定决定。

### 2.2 通用运行时只认识“本次是否激活修订”

`direct_revision_ports()` 继续只负责识别 OperationSpec 是否具备直接修订能力。它在保持既有必需
`revision_base` 形状不变的同时，接受一种新的可选形状，但仅当：

1. 恰好一个 `revision_base` 和一个 `change_request`，二者均为 `0..1`；
2. 基线可物化，不是 `handoff_only`；
3. 两者由同一个无审批、成员恰好为这两个端口的 `InputAdmissionSpec` 绑定；
4. 输出、ReviewSpec、Schema、媒体类型、codec 和 schema resource 仍满足原有直接修订闭包；
5. ReviewSpec 强制声明正数修订上限和问题指纹；
6. executor 仍是 scientific Agent，主输出唯一且不是集合。

新增唯一的无状态总函数 `active_direct_revision_ports(compiled, actual_bound_port_names)`。它先调用静态
`direct_revision_ports()`，再只依据本次冻结绑定中是否存在 base 返回修订合同；不读取内容、不写
状态。运行期的 assignment、草稿预填、workspace 选择、提交差异校验、Root 修订次数／无进展／单
后继和 producer direct-base 路径统一使用它。未绑定时沿用普通创建路径。catalog 编译和后端能力
判断继续使用静态函数，现有只修订 Operation 的行为不变。

Worker 可见的 validation contract 对必需基线保持原描述；对可选基线明确声明“仅在 assignment
实际绑定 revision_base 时，完整修订必须不同于基线”。激活事实不持久化，Run 冻结 inputs 是恢复
时的唯一事实。

### 2.3 图证据插件只声明领域事实

图证据插件负责：

- 给原提取 Operation 增加两个可选修订端口和输入组；
- 在修订模式下证明基线和审查都绑定同一完整图证据文件族；
- 用非通过审查项的稳定问题指纹检测无进展；
- 在同一提示中明确创建与修订模式；
- 删除尚未发布的独立 `science.intake.revise.figure.v1` 声明。

核心不得出现图证据 Operation 名、Schema 名或插件分支。下游只依赖输出端口、完整父链和已编译
审查合同，不维护创建／修订生产者名单。

## 3. 实施步骤

### P0：计划独立审查

第一次审查报告：
`reviews/R5_E5_SAME_OPERATION_REVISION_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，结论 FAIL、两个阻断。
本版已加入唯一 active 总函数、完整调用面、条件化 Worker 规则、严格编译门和盲插件测试，须复审
通过后实施。

### P1：通用双模式最小支持

修改：

- `src/scidiscovery/operation_contract.py`：保留静态能力识别器，增加严格受限的可选形状分支、唯一
  active 总函数，并让 Worker validation contract 对可选基线明确条件；
- `src/scidiscovery/artifact_agent/service/run_assignment.py`：草稿和 revision assignment 只使用 active
  结果；
- `src/scidiscovery/artifact_agent/service/run_outputs.py`：提交差异校验只使用 active 结果；
- `src/scidiscovery/artifact_agent/service/runs.py`：workspace 模式和预填只使用本次冻结输入派生的 active
  结果，不增加字段；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`：producer direct-base、修订次数、
  无进展和单后继只使用 active 结果。

同一 digest 的修订历史中，只有同时没有 base/request 的 Run 才是合法创建根并停止计数；二者各一
才计为一次修订，任何一有一无或重复仍返回 `revision_history_invalid`。既有必需基线 Operation 不
允许出现零／零根。

### P2：图证据 Operation 合并

修改 `plugins/curve_score/curve_score/figure_science_operations.py`：

- 把可选 `prior_draft`、`change_request` 合并进 `science.evidence.extract.figure.v2`；
- 增加全有或全无输入组；
- 将修订父链 guard 改为：创建模式直接放行，修订模式验证完整家族；
- 把 `max_revisions=2` 和问题指纹放到原提取 Operation 的 ReviewSpec；
- 删除 `science.intake.revise.figure.v1`；
- 不增加新 Agent、Schema、Validator、注册表或调度分支。

### P3：有界测试

低内存、串行测试至少证明：

1. 同一 Operation 在未绑定修订组时能创建；
2. 只绑定二者之一会在通用输入组校验处拒绝；
3. 二者都绑定时预填旧完整对象并产生不可变新版本；
4. 修订必须使用旧对象的精确非通过独立审查；
5. 修订必须复用旧对象和审查共同绑定的完整图证据文件族；
6. 相同问题指纹返回 `revision_no_progress`；
7. 超过两次返回 `revision_limit_reached`；
8. 任一修订结果必须获得新的独立审查，旧 verdict 不继承；
9. 下游 bundle 接受获得新通过审查的修订结果；
10. 既有必需基线的通用、实验和 TCAD 修订测试不回归；
11. 目录中不存在 `science.intake.revise.figure.v1`。

此外用一个不含 figure、curve 或 ScientificIntake 名称的最小盲插件证明通用编译／运行语义：

- 合法可选形状可编译，且同一 Operation 的创建 assignment 无 revision／无草稿，修订 assignment
  有 revision／有草稿；
- 缺 cohort、cohort 含第三端口、cohort 带审批、base/request 基数不匹配、缺 change request、输出
  身份错误、无 reviewer、无修订上限或无问题指纹均在编译期失败；
- 创建提交不执行 unchanged-base 规则，修订提交执行该规则；
- 创建输出是合法链根，半截历史失败关闭；
- 既有必需基线通用、实验和 TCAD 修订的 assignment、提交、恢复、单后继及上限测试不回归；
- preflight 与 invoke 对半组、错误审查、错族、无进展和超限等拒绝一致，失败前后不产生 Run 或
  Artifact。

测试命令必须使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、串行执行并限制虚拟内存；本轮不运行无关
全量测试。

### P4：实现独立审查

独立审查者检查：

- 是否真正只有一个图证据 Intake Operation；
- 核心是否仍完全领域无关；
- 创建路径与修订路径是否均失败关闭；
- 是否出现为了当前实例而写死的名称、兼容分支或第二注册表；
- 是否符合奥卡姆剃刀和既有架构约束。

只有 P4 结论为通过且阻断项为零，才构建部署包并重跑真实图证据链。由于原 OperationSpec 合同升级，
部署后旧 Intake 不冒充新合同输出；真实链从该 Operation 的新创建模式重新产生 Intake，再执行
独立审查和同 Operation 修订。

## 4. 明确不做

- 不把独立审查 Agent 合并进提取 Agent；
- 不在本轮迁移其他领域现有的独立 `revise.*` Operation；
- 不新增通用科学状态、资格、路由、注册表或修订状态机；
- 不放宽完整文件族、精确审查、不可变版本和最小上下文约束；
- 不为了复用当前线上中间产物保留一个长期平行修订 Operation。

## 5. 完成定义

源码、目录投影和测试中只有 `science.evidence.extract.figure.v2` 负责图证据 Intake 的创建与修订；
核心实现不含 `figure`、`curve`、`ScientificIntake` 等领域判断；独立实现审查通过；随后才允许部署
并继续真实端到端实验。
