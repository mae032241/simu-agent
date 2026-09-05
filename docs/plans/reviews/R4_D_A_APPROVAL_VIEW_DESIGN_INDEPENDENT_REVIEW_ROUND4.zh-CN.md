# R4-D-A 审批视图设计第四轮独立复审

状态：第四轮只读复审完成  
范围：第三轮唯一阻塞、typed intake revision family resolver，以及前三轮已通过的 catalog/provider、
Task family、legacy bridge、ReviewDocument、参数和 execution 边界  
方法：跨边界闭环审查、单一权威审查、插件生命周期审查、简化审计

## 结论

**通过，允许进入 R4-D-B。**

第三轮唯一阻塞已经闭合。family resolver 现在只允许两个精确分支：已完成 Agent extraction Task，
以及当前 compiled `science.revision.apply.intake.v1` 的 `revised_object`。修订分支不把“transform”本身
视为资格，而是要求同一次 invocation 的唯一 `revision_diff`、精确 base/patch、类型化 unchanged-
evidence receipt、可递归解析的 base family/frozen sources、针对 revised primary 的新独立 audit，
以及由 revised primary 精确 split 得到的一致 foundation。普通 transform、证据声明变化、未知
producer、混合 invocation、缺失 lineage、环和超过深度 8 均失败关闭。

该 resolver 只读取已有 Task/output、scheduler binding request fingerprint、Artifact labels/parents 和
compiled catalog，并在审批创建时形成一次性窄快照。它不持久化 family、不注册新 Artifact、不参与
调度或资格查询，因此不是第二注册表。资格权威仍然是 compiled approval provider、不可变
ApprovalRequest/HumanDecision 和消费 Operation 的 provider-aware admission。

前三轮已经通过的 provider digest/PluginDependency、逐候选 readiness、两个资格前 legacy bridge、
三个 approval Operation、固定 ReviewDocument、参数审批和 execution 双端身份门没有因本次修改而
退化。当前设计可以进入实现；本报告只批准设计，不替代 R4-D-B 的生产代码、真实 UI、clean wheel
和负例验收。

## 第三轮阻塞闭环复核

### 1. revised primary 与同调用 diff 的身份闭合

修订分支只接受：

- producer id 精确为 `science.revision.apply.intake.v1`；
- producer version/digest 与当前 compiled catalog 一致；
- primary 的 output port 精确为 `revised_object`；
- sibling 从同一 scheduler binding request fingerprint 恢复，且恰好一份；
- sibling producer labels、精确 parents 和 compiled output port 均指向同一次调用的
  `revision_diff`。

这与当前确定性 transform 的实际注册方式相容：同次调用输出共享 request fingerprint、operation
identity 和 parents，不同端口由冻结 output label/port 区分。缺 sibling、多个同端口、跨调用拼接或
合同漂移均无法落入合法分支。

### 2. exact base、patch、diff 与 receipt 闭合

resolver 要求 revised object 和 diff 的 exact parents 同时包含 base 与
`science.intake.revise.v1` 产生的 patch；patch 本身必须针对该 exact base。receipt 又必须由当前
compiled `science.evidence.receipt.intake.v1` 产生，并直接绑定 exact base、revised object、diff 和
base family 的全部 evidence refs。

receipt 不是先前审查结论，也不授予资格。它只证明 base/revised 的 evidence 声明相同，并把复用的
exact evidence refs 固定进受控 lineage。若 evidence 声明改变，typed revision 分支拒绝，调用者必须
重新进行完整 extraction 和完整 audit。这保留了“不静默继承资格”的核心约束。

### 3. base family、frozen sources 和递归边界闭合

base family 仍使用同一个二分 resolver：初始 base 回到已完成 Task 的精确 output/evidence-source
映射；若 base 是更早的一次 typed intake revision，则沿同样的受控 base/patch/diff/receipt 关系递归。
深度上限 8、visited-set 环检测、每层精确单值端口和 request fingerprint 检查把运行成本和恶意链限制
在固定范围内。

超过 8 层时要求重新提取或重新建立一个新的完整 evidence base，是明确的 fail-closed 取舍，不会
把过深历史静默当成当前资格，也不会新增压缩/继承状态。

### 4. 新独立 audit 与 revised foundation 闭合

修订资格不继承 base verdict。`science.evidence.qualify.v1` 必须绑定针对 revised primary 的新独立
evidence audit，并要求其实际输入、父链和 producer handoff verdict 为 `pass`。最终 foundation 还
必须由 revised ScientificIntake 经当前 compiled `science.intake.split.v1` 精确产生，split 调用绑定
该 revised primary 和新 audit；foundation 内容必须与 revised primary 内声明完全一致。

因此人类看到并批准的是 revised primary、reused exact evidence、diff/receipt、新 audit 和 revised
foundation 的同一不可变 cohort，而不是旧 foundation 或旧 verdict。

### 5. 普通 transform 资格旁路已关闭

合法 transform producer 被精确写死为一个 typed Operation 和一个 output port，但该限制位于通用
catalog/lineage resolver 的合同判断中，不是按领域 Schema 自动授予资格。以下对象均失败关闭：

- 其他 support/internal/public transform 的 JSON 输出；
- 伪造 `operation_id` 但 digest、port、parents 或 request fingerprint 不同的 Artifact；
- hypothesis/experiment revision apply 输出；
- intake revision 中 evidence 声明已变化但试图复用 base receipt/family 的对象；
- 缺 diff、receipt、base family、新 audit 或 revised split foundation 的对象。

这没有把 transform 变成新的科学资格生产者；唯一资格动作仍是公开
`science.evidence.qualify.v1` 及其人工决定。

## 是否新增第二注册表

没有。当前事实归属保持为：

| 事实 | 唯一权威 |
| --- | --- |
| Agent output family | 既有 Task finalization/output mapping |
| Transform 同调用 siblings | 既有 scheduler binding request fingerprint + Artifact producer labels/parents + compiled output ports |
| Evidence 未变化 | typed unchanged-evidence receipt 及其精确父链 |
| 可接受审批 provider | 消费 Operation 的 compiled input contract |
| 人工决定 | ApprovalRequest/HumanDecision |
| UI 展示 | 请求内冻结 ReviewDocument + exact subjects |

`producer_output_family` 只是这些事实的有界、即时、只读组合视图；它没有持久身份、写入口或独立
查询语义。实现中不得把它升级为 family 表、资格 receipt 或第二 catalog。

## 前三轮边界回归复核

| 边界 | 第四轮结论 |
| --- | --- |
| provider digest/依赖 | 仍通过；provider 无审批 cohort，跨插件必须 PluginDependency，consumer digest 冻结 provider identity。 |
| readiness/preflight | 仍通过；按候选 Operation 的冻结 providers 查询，不存在对象级全局 qualified。 |
| legacy bridge | 仍通过；`task_schedule` 只保留两个资格前 device-parameter 精确组合。 |
| 三个 approval Operation | 仍通过；revision 是 evidence qualifier 的受控输入分支，没有新增第四审批 Operation。 |
| 参数审批 | 仍通过；不复用 typed intake revision 分支绕过参数 pass/exception 的 coverage/audit 合同。 |
| ReviewDocument/UI | 仍通过；diff、receipt 只是新增 exact subjects，仍使用固定五类型和有界安全 renderer。 |
| execution | 仍通过；科学资格 family 与 external execution authorization 继续分离。 |
| 三视图 | 仍通过；approval 为 public，support lineage 不进入普通规划，internal 不获得资格。 |

## R4-D-B 实现完成门

第 7.5 节的验收集合足以进入实现，至少必须真实证明：

1. 初始 extraction 和完整 typed intake revision 两条正路径均能创建精确审批请求；
2. 缺 diff、receipt 未覆盖 exact base evidence、普通 transform 伪装、递归环/超限分别失败；
3. revised foundation 必须来自 revised primary + 新 audit 的 exact split；
4. figure collection item、validation、frozen source、primary 任一漏项均失败；
5. provider A/B、跨插件依赖、disable/upgrade、历史无身份决定的 readiness/preflight 一致失败；
6. 旧 execution fallback 决定不可 authorize/start，插件卸载后历史审批仍可只读审计；
7. core-only/default-full clean wheel、三视图、全仓测试、源码零缓存和发布清单通过。

若实现为了方便新增持久 family 表、接受任意 transform、按 Schema 在 Root 分支资格、让旧 verdict 随
receipt 继承，或让 readiness 使用全局 provider allowlist，均视为偏离本次通过的设计，应在 R4-D-B
独立实现审查中打回。
