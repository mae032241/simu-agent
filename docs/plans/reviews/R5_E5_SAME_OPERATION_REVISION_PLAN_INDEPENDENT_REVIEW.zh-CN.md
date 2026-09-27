# R5 E5 同一 Operation 创建／修订计划独立审查

日期：2026-09-05  
审查对象：`docs/plans/R5_E5_SAME_OPERATION_REVISION_PLAN.zh-CN.md`  
审查方式：只读追踪 Operation 编译、preflight、Run 创建、assignment、提交校验、修订历史、独立审查及下游 bundle；未修改生产源码或测试。

## 1. 结论

**FAIL。阻断项 2 个。**

总体方向成立：对于图证据 Intake，创建和修订使用同一角色、同一完整图族、同一输出 Schema、同一
validator、同一工具以及同一独立审查边；差异只是是否额外绑定旧完整对象和精确审查请求。因此把它们
合并为一个 `science.evidence.extract.figure.v2` 行为闭包，比长期保留两个几乎重复的 public
Operation 更符合当前设计目标。

`InputPortSpec(0..1)` 加无审批 `InputAdmissionSpec` 已能声明 `prior_draft/change_request` 全有或
全无；实际模式由冻结输入决定，并非 Agent 自选，也不需要新增 `mode` 字段、状态或路由表。该方案在
原语层面可行。

但是计划尚未闭合“Operation 具有修订能力”和“本次调用实际是修订”之间的全生命周期区别，而且
没有把可选直接修订形状的失败关闭条件及通用负例冻结完整。若按当前 P1 逐文件各自判断，创建调用会
在至少三个现有路径被误当成修订，或形成多份模式判断。因此本计划不能直接进入实现。

按第 4 节做最小修订后可通过计划审查；不需要退回长期独立
`science.intake.revise.figure.v1`，也不需要增加核心实体。

## 2. 方案中正确且应保留的部分

### 2.1 同一行为闭包的边界合理

本例的创建与修订没有更换科学职责、输出类型、证据边界、工具、审查者或副作用。修订仍产生完整
`ScientificIntake`，不是 patch。把 `prior_draft/change_request` 作为条件上下文合入同一
Operation 没有把两个不同科学行为强行塞进一个巨型类。

该结论只适用于这种“除修订上下文外合同相同”的行为；不能推导出所有领域都必须合并 `revise.*`。
如果修订需要不同工具、reviewer、审批、输出或风险，它仍应是单独 Operation。计划第 128—132 行
明确不迁移其他领域，方向正确。

### 2.2 可选输入组是安全的声明方式

现有 `preflight_operation()` 会先按端口检查 `0..1` 基数，再以 `InputAdmissionSpec.member_ports`
检查任何成员出现时其他成员必须同时出现。因此：

- 两端口均空：创建；
- 二者均有且各一项：修订；
- 只绑定一项：`input_cohort_incomplete`；
- 重复绑定：端口基数拒绝。

只要编译器进一步要求该 cohort **恰好**由唯一 `revision_base` 和唯一 `change_request` 构成，且
`approval_kind/subjects/options/providers` 全为空，就不存在用审批 cohort 或第三端口暗中切换模式的
空间。模式事实仍只有冻结输入绑定一份。

### 2.3 direct revision 与独立审查语义可以保持

修订调用实际绑定 base 后，现有 Root 会验证：

- base 的冻结 producer ReviewSpec 与当前 Operation 的 figure audit edge 完全一致；
- `change_request` 是该 reviewer 对 exact base 的非通过输出；
- 新输出是同 Schema/媒体/codec/resource 的完整对象且字节发生变化；
- 新对象不继承旧 review，必须重新执行 exact figure audit。

图插件已有完整生产族合同、父链 guard 和排除审查自由文案的问题指纹，可以继续复用。没有必要创建
patch Schema、revision 状态机或核心图领域分支。

### 2.4 下游 producer id 白名单已采用正确方向

当前 `figure_parentage` 已不再要求
`intake_labels.operation_id == science.evidence.extract.figure.v2`，只保留类型化输出端口、完整图族父链、
精确 figure audit 父链和 pass verdict。该基线必须保留。Root 再按生产者冻结的编译 ReviewSpec
验证 exact reviewer output，因此无需创建／修订 producer 名单，也不会因合并 Operation 产生下游
旁路。

## 3. 阻断项

### 阻断 1：缺少唯一的“本次激活修订”总函数，P1 调用面不完整

当前 `direct_revision_ports(compiled)` 是**静态合同识别器**。只要 OperationSpec 声明
`revision_base`，它就返回 direct-revision 形状；它不知道本次绑定是否包含 base。对必需基线修订
这两件事等价，对计划新增的双模式 Operation 则不再等价。

现有调用面证明不能仅修改计划列出的几个条件：

- `run_assignment.revision_draft_json()` 和 `_revision_assignment()` 在静态识别成功后直接 `next()`
  查找 base；创建模式会抛错；
- `run_outputs.validate_run_output()` 在静态识别成功后要求 `input_bytes` 中存在 base；创建结果会被
  当成缺失修订基线而拒绝；
- Root 的 `_validate_revision_successor_slot()` 与 `_validate_revision_policy()` 同样直接查找 base；
- `RunService.create()` 以静态形状选择 revision workspace 和预填草稿；虽然数据库单后继判断已按
  实际 base 条件执行，workspace 路径仍会把创建当成修订；
- `operation_output_validation_contract()` 只要发现 revision_base 就向 Worker 声明
  `runtime.revision: complete revision must differ from base`。计划没有列出该函数，创建 Worker 会看到
  与实际提交规则不一致的无条件修订规则；
- Hardened 后端和 catalog 使用静态能力判断是合理的，它们不能被误改为某次调用判断。

若每个运行文件各写一次“是否存在 prior_draft”，会产生多份隐藏模式事实，并迟早使 assignment、
submit、Root 和恢复再次断裂。

最小修复不是新增状态，而是在 `operation_contract.py` 增加一个纯函数，例如：

```text
active_direct_revision_ports(compiled, actual_bound_port_names)
```

它先调用 `direct_revision_ports()` 取得静态合同，再仅在实际端口集合含 base 时返回该合同；否则返回
空。由于 all-or-none cohort 已保证 change request 同时存在，运行期无需第二模式字段。必须：

1. catalog 编译和 backend capability 继续调用静态 `direct_revision_ports()`；
2. assignment、草稿预填、workspace 模式、提交差异校验、Root 修订次数、无进展、单后继及 producer
   direct-base 路径统一调用 active 函数；
3. 不把 active 标志写入数据库；Run 的冻结 inputs 是恢复后的唯一事实；
4. Worker assignment 的 `revision` 在创建时为 `null`，修订时才是 copy-on-write 合同；
5. `operation_output_validation_contract()` 对可选 base 的 `runtime.revision` 使用明确条件表述：仅当
   assignment 实际绑定 revision_base 时生效。创建 Worker 不能看到无条件修订要求。

计划第 80 行把 `runs.py` 写成“必要时”，不够明确；它是必改调用面。计划也必须明确
`operation_output_validation_contract()`，否则违反 Worker 可见规则与真实 validator 单一来源。

修订历史遍历还必须严格区分合法创建根与损坏历史：对同 digest 的 producer Run，`base/request`
均不存在才表示双模式 Operation 的创建根并停止计数；二者各一项才计为修订；任何一有一无或重复仍
返回 `revision_history_invalid`。既有必需基线 Operation 不允许出现零／零根，其原行为必须保持。

### 阻断 2：可选形状的编译门与通用负例不足

计划第 42—47 行给出了方向，但完成条件尚未冻结全部失败关闭要求。可选 direct-revision 形状应只在
以下条件同时满足时被识别：

1. 恰好一个 `usage=revision_base` 端口和一个 `usage=change_request` 端口；
2. 二者均为 `min_items=0,max_items=1`，base 可物化而非 `handoff_only`；
3. 唯一 `InputAdmissionSpec` 无审批，且 `member_ports` 集合恰好是这两个端口；
4. 单一完整输出与 base 的 Schema、媒体、codec、schema resource 相同；
5. 存在精确独立 reviewer、review subject 正好是该输出；
6. 对可选双模式形状强制 `max_revisions>0` 且声明 `progress_fingerprint`，以落实设计宪章的有界修订；
7. executor 仍是 scientific Agent，输出不是 collection。

其中第 6 项不能只靠图插件自觉设置。若通用编译门允许另一个插件声明同样可选形状却把
`max_revisions=0`，就会重新引入无限审查循环；既有必需基线修订可保持旧规则，不在本轮扩修。

P3 目前只有图领域正例和“既有测试不回归”，不能证明新增的**通用核心语义**没有依赖图名称。至少
应在现有 `test_incremental_revision_runtime.py` 使用一个最小盲插件双模式 Operation 验证：

- 合法可选形状能编译，创建与修订走同一 Operation；
- 缺 cohort、cohort 含第三端口、带审批、base/request 基数不匹配、缺 change request、错误输出
  身份、无 reviewer、无修订上限或无问题指纹均在编译期失败；
- 创建 assignment 无 revision、无预填草稿，提交不执行 unchanged-base 规则；
- 修订 assignment 有 revision 和草稿，相同输出被 `runtime.revision` 拒绝；
- 同一 Operation 的创建输出是合法修订链根；半截历史仍失败关闭；
- 现有必需基线的通用、实验和 TCAD 修订 assignment、提交、恢复、单后继与上限行为不变。

否则实现可能只对 `science.evidence.extract.figure.v2` 可用，不能证明核心变更是领域无关原语。

## 4. 对原计划的最小修订建议

只修改计划，不扩大目标：

### 4.1 重写 P1 的责任边界

P1 应明确为：

1. `direct_revision_ports()` 仍只判断编译静态能力，新增严格的可选形状分支，必需形状原样保留；
2. 增加一个无状态 active helper，从静态合同和实际绑定端口导出本次是否修订；
3. catalog/Hardened 使用静态函数；所有 Run/Root/assignment/submit 调用使用 active helper；
4. 修改文件明确包括：
   - `src/scidiscovery/operation_contract.py`；
   - `src/scidiscovery/artifact_agent/service/run_assignment.py`；
   - `src/scidiscovery/artifact_agent/service/run_outputs.py`；
   - `src/scidiscovery/artifact_agent/service/runs.py`；
   - `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`；
5. validation contract 对 optional base 使用 Worker 可见的条件规则；
6. active 事实不持久化，不增加 Run 字段、状态或兼容分支。

这是五个既有调用面的一次语义替换，不是五套判断。若实现需要数据库迁移、第二 helper 链或按
Operation id 分支，应停止并退回独立 Operation 方案。

### 4.2 收紧 P2

图插件只做：

- 向原 extraction 增加两个 `0..1` 输入和无审批 all-or-none cohort；
- 把现有父链 guard 变为“组空则创建通过、组全则验证 prior/audit 与同一完整族”；
- 复用现有问题指纹、Agent、prompt、Schema、validator、工具、完整族和 audit edge；
- 将 `max_revisions=2` 放入同一 ReviewSpec；
- 删除未发布的独立图修订 Operation；
- 保留当前下游无 producer-id 白名单实现，不再修改其它 curve Transform。

不得添加 `mode` 字段、模式枚举、第二 prompt、第二 validator、图名称核心判断或兼容路由。

### 4.3 补齐 P3

在原 11 项图测试之外，加入阻断 2 所列的盲插件编译／运行负例，并显式检查：

- Worker 可见 validation contract 在创建与修订时没有自相矛盾；
- preflight 与 invoke 对半组、错误 review、错族、无进展和上限返回一致，失败前后无 Run/Artifact；
- downstream bundle 接受“同 Operation 修订 + 新 exact pass audit”，拒绝旧 audit 和非通过 audit；
- 默认 catalog 不安装可选图插件时，不获得双模式图能力；
- 生产核心源码不包含 `figure`、`curve`、图 Operation id 或 ScientificIntake 特判。

保持低内存串行测试，不需要无关全量回归。

## 5. 是否存在补丁化、隐藏模式或过度设计

按当前文本直接实施：**存在隐藏模式分散风险**，因为静态 `direct_revision_ports()` 与实际激活修订
未由一个总函数区分；这正是阻断 1。

按第 4 节修订后：

- 没有针对 Fig.4 的核心分支；可选形状只读端口 usage、基数、cohort、review 和输出合同；
- 没有第二注册表、状态机、current、审批或 revision Artifact 类型；
- 模式是冻结输入的纯派生值，assignment 对 Worker 显式可见，不是提示词暗号；
- 必需基线修订继续使用原静态形状，不承担新条件语义；
- 图插件只声明同族父链和审查问题指纹，符合插件所有权；
- 下游依赖类型、父链和编译 review，而非 producer 名单。

这属于一个小而通用的 Operation 组合能力，不是为当前 Fig.4 写死的补丁。其复杂度上限必须冻结为
“一个可选二端口 cohort + 一个 active helper + 现有五个调用面的机械替换”。不要继续扩展为任意
模式系统、多 cohort 条件语言或自动合并所有 revise Operation。

## 6. 通过门

计划当前保持 **FAIL**。只有原计划按第 4 节补齐、再次独立审查确认两个阻断关闭，才可进入 P1。

修订后的计划若仍满足以下条件即可 PASS：

- 创建／修订由同一编译 Operation 和冻结输入唯一决定；
- optional 与 required direct revision 的静态/动态语义都有盲插件正负证据；
- assignment、validation contract、submit、Root policy、Run 恢复使用同一 active 判断；
- 旧必需基线修订无回归；
- 图插件和下游无 producer id 名单，核心无领域字面量；
- 无新增状态、注册表、兼容层、模式语言或无关改造。

---

## 7. 第二轮独立复审

复审日期：2026-09-05  
复审对象：第一次审查后修订的同一计划文件。  
复审结论：**PASS，阻断项 0 个，可以进入 P1 实施。**

本结论只批准计划边界，不表示生产实现已经完成或 E5 已通过。P1—P3 实施后仍须按 P4 进行独立代码
和真实入口审查。

### 7.1 首轮阻断关闭情况

| 首轮阻断 | 修订结果 | 判断 |
|---|---|---|
| 静态 direct-revision 能力与本次 active 修订混用 | 第 40—61、87—103 行增加唯一 `active_direct_revision_ports(compiled, actual_bound_port_names)`，明确 catalog/backend 使用静态函数，assignment、草稿、workspace、提交、Root policy 和 producer direct-base 使用 active 函数；active 不持久化 | 已关闭 |
| 可选形状编译门和通用负例不足 | 第 42—49 行冻结唯一 base/request、`0..1`、可物化 base、恰好二成员无审批 cohort、完整输出身份、独立 reviewer、正数上限和问题指纹；第 132—145 行增加无领域名称盲插件正负矩阵及既有必需修订回归 | 已关闭 |

### 7.2 全生命周期复核

修订计划已经正确区分两种事实：

```text
direct_revision_ports
  = 该编译 Operation 是否具有完整对象修订能力

active_direct_revision_ports
  = 该次冻结调用是否实际绑定 revision_base/change_request
```

这是本方案能否成立的承重边界。catalog 编译和 backend capability 必须理解 Operation 的全部可能
能力，所以继续使用静态函数；Run、Worker assignment、草稿、提交、修订次数、单后继和恢复处理的是
某次精确调用，所以统一使用 active 函数。计划没有新增 `mode` 字段、数据库列或第二状态权威。

创建调用的可见和运行语义现在闭合：

- optional cohort 两端均空；
- assignment 中 `revision=null`，不预填草稿；
- validation contract 明确 `runtime.revision` 仅在绑定 base 时生效；
- submit 不执行 unchanged-base 检查；
- Root 不执行修订次数、问题指纹或单后继门；
- 同 digest 创建 Run 在后续修订链中被识别为零 base/零 request 的合法根，不计为一次修订。

修订调用的语义也闭合：

- all-or-none cohort 保证 base/request 同时出现；
- assignment 显式给出 copy-on-write 修订合同并预填旧完整对象；
- Root 验证 exact 非通过 reviewer output、同一完整图族、修订上限、问题进展和单后继；
- submit 要求完整新对象且不能与 base 相同；
- 新 Artifact 保留全部冻结输入父链，旧审查不继承；
- 新结果必须再次经过同一 figure audit。

历史遍历规则也足够严格：只有 optional 双模式 Operation 的零／零 Run 可作为创建根；一／一才是
修订；半组或重复仍是损坏历史。既有必需基线 Operation 不获得零／零例外，因此没有因新能力放宽
通用、实验或 TCAD 修订。

### 7.3 OperationSpec 单一事实源

双模式完全由以下既有声明组合形成：

- 两个 optional `InputPortSpec` 的 usage 与基数；
- 一个无审批、恰好二成员的 `InputAdmissionSpec`；
- 单一输出及其 Schema/codec/resource；
- 同一个 `ReviewSpec`、修订上限和问题指纹；
- 图插件声明的完整生产族和无状态父链 guard。

active helper 只解释该声明与冻结输入，不增加新配置。Worker assignment、validation contract 和提交
规则都由同一 compiled Operation 导出。计划没有用 instruction 文案、Agent 自报字段、Operation id
名单或 scheduler 阶段表决定模式，故不存在隐藏模式或第二事实源。

### 7.4 插件边界与下游旁路

领域内容仍只位于 `figure_science_operations.py`：图族父链、EvidenceAudit 问题指纹和创建／修订提示。
通用文件只处理 usage、基数、cohort、实际端口集合及 compiled review，不出现 `figure`、`curve`、
`ScientificIntake` 或具体 Operation 名。

当前下游 `figure_parentage` 已删除初始 producer id 白名单。bundle 继续要求类型化 Intake、完整图族
父链、exact Intake+图族 audit 父链和 pass verdict；Root 依据 Intake producer 冻结的 ReviewSpec
再次要求 exact reviewer output。计划 P3 又要求修订新 audit 正例和旧／非通过 audit 负例，因此合并
Operation 不会打开未审查旁路。

### 7.5 奥卡姆判断

计划把复杂度限制为：

```text
一个严格 optional 二端口 cohort
+ 一个纯 active helper
+ 既有运行调用面改用该 helper
+ 一个图 Operation 删除重复声明
```

它没有建立模式语言、多 cohort 条件系统、通用 revision 实体、兼容路由或新状态机。对于创建和修订
科学职责完全相同的本例，这比长期维护两个重复 public Operation 更简单。计划又明确不自动迁移
其他 `revise.*`，避免把单一真实需求扩张为全框架改造。

### 7.6 实施期必须保持的精确边界

以下是复审通过的边界，不是新增阻断：

1. active helper 的输入必须是实际**端口名**集合；不能用 instruction、文件是否存在或 payload 内容
   推断模式。
2. optional 分支必须新增在 static direct contract 中，必需 `1..1` 分支保持原行为；不得为通过旧
   测试写 Operation id 兼容条件路。
3. `runs.py` 是明确必改调用面；不能保留静态函数选择 workspace 再在下层补异常。
4. Worker validation rule 必须写成条件规则；创建 assignment 不得声称自己是 revision。
5. 创建链根的零／零例外只适用于编译认定的 optional 双模式合同；必需基线和半截历史仍失败关闭。
6. 图父链 guard 在组空时只表示创建模式；完整图族合同仍独立执行，不能因 guard 放行而跳过。
7. 测试必须包含盲插件，不得只用图 Operation 证明通用核心；负例 invoke 前后必须零 Run/Artifact
   写入。
8. 不修改数据库、Run 状态集合、scheduler、current、审批、Execution 或其它领域 Operation。

### 7.7 最终判定

修订计划已经关闭首轮两个阻断，并在最小范围内满足：

- 同一 Operation 创建／修订的显式行为闭包；
- optional all-or-none 输入安全；
- direct revision 的精确审查、不可变新对象和有界无进展停止；
- 必需基线修订不回归；
- OperationSpec 单一事实源、插件解耦与下游无 producer 名单；
- 奥卡姆剃刀和现有架构约束。

**第二轮结论：PASS；剩余阻断项：0。可以按 P1 → P2 → P3 实施，完成后必须执行 P4 独立实现审查。**
