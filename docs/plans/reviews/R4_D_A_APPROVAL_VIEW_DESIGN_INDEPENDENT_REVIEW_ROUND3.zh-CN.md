# R4-D-A 审批视图设计第三轮独立复审

状态：第三轮只读复审完成  
范围：第二轮两项返工、`producer_output_family`、结构化 revision/transform producer、provider digest/
跨插件依赖、逐候选 readiness、两个 device-parameter legacy bridge 及第 7 节其余已冻结边界  
方法：跨边界闭环审查、单一权威审查、插件生命周期审查、简化审计

## 结论

**打回，不允许进入 R4-D-B。**

第二轮两个阻塞的大部分已经闭合：初次 Agent evidence extraction 可以由现有 Task/output 与
task-scoped evidence-source 映射即时得到精确 family，不需要新表或 Artifact；provider 的跨插件依赖、
摘要传播和逐候选 readiness 也已形成可实现的单一 catalog 路径；`task_schedule` 收紧为两个资格前
device-parameter bridge 与当前角色现实吻合。

仅剩一个实质阻塞：第 7.2 节把没有 Task/output 映射的 primary 统一失败关闭，但当前活动目录明确
支持 `science.intake.revise.v1 → science.revision.apply.intake.v1 → evidence receipt → independent
delta audit`。其中 final revised ScientificIntake 是确定性 transform 输出，不是 Task primary。按现稿，
这个 final primary 无法得到 `producer_output_family`，因而永远不能重新获得人工科学资格。对未知或
任意 transform 失败关闭是正确的；对已经编译、已有严格 revision lineage 的这一条公开路径 blanket
fail-closed 会造成当前设计自相矛盾。

该缺口可以复用现有 transform request fingerprint、编译输出端口、structured revision diff、unchanged
evidence receipt 和受控 lineage resolver 闭合，不需要增加第二输出注册表或通用 transform 资格。

## 第二轮两项返工复核

| 第二轮阻塞 | 第三轮状态 | 复核结论 |
| --- | --- | --- |
| evidence qualifier 缺唯一 primary/完整 output family | 初次 extraction 已闭合；revision 未闭合 | qualifier 已固定唯一 foundation/primary/audit 和三个有界集合；Task producer 可精确覆盖全部 sibling、source、validation。结构化 revised primary 没有 Task family，见阻塞 1。 |
| provider 依赖、readiness 与 legacy 合同来源不明 | 通过 | 跨插件 provider 必须 PluginDependency；消费摘要冻结完整 identity；readiness 按候选合同查询；对象库存不再授予全局资格；task_schedule 仅留两个资格前 bridge。 |

## 已通过的重点边界

### `producer_output_family` 仍是控制事实投影，不是第二注册表

当前 Agent output 的完整性已经由 Task finalization 和 `task_output_artifacts` 映射拥有；primary、每个
collection/item、任务输入、web snapshot/PDF excerpt 等 evidence-source 也已有精确不可变 ref。
审批创建时把这些现有事实读成有界 snapshot，再与本次 subjects 比较：

```text
既有 Task/output + task-scoped evidence mapping
→ 即时只读 family snapshot
→ projector 精确集合校验
→ ApprovalRequest 保存精确 subjects/document/provider identity
```

snapshot 不持久化、不产生新 identity、不参与调度、不接受写入，也不成为查询权威。资格事实仍由
ApprovalRequest/HumanDecision 与消费 Operation 的 provider-aware admission 共同决定。因此这里没有
第二注册表，也没有把 support 数据提升为科学对象。

内容摘要不一致、Task mapping 缺项、primary 不是该 compiled producer 的精确输出、插件合同漂移时
失败关闭是合理的。四个 figure 漏项反例足以覆盖最危险的“调用方和 audit 同时遗漏兄弟项”场景。

### provider digest、插件依赖和编译顺序可实现且无隐藏 allowlist

provider 不得含审批 cohort，所以 provider edge 不会回指消费端；provider digest 可以先按既有
operation/reviewer 依赖求出，再进入 consumer digest。跨插件 edge 同时要求 `PluginDependency`，TCAD
对 `general_science` 的依赖成为安装合同，而不是按全局 operation id 偶然命中。缺失、disable、版本
变化或合同 digest 变化都会使相关 consumer 启动编译失败，旧决定仍只读。

scheduler projection 只给模型 provider ids；Root 内部逐候选使用该候选 CompiledOperation 已冻结的
完整 identities 查询，与 preflight 共用同一 ApprovalService predicate。对象库存只显示已发生的审查，
不把它解释为对所有消费者有效的资格。因此 provider A 不会让只接受 B 的候选显示 ready，也不需要
Root provider allowlist。

实现时应把 provider edge 加入 operation digest 的显式递归保护，即使当前“provider 无审批 cohort”
已令合法图天然无环；这是编译器防御，不是新的运行状态。

### 两个 legacy bridge 与当前代码角色吻合

现存 bridge 正是：

- `evidence_extractor` + `scidiscovery.evidence-intake.device-parameters.v1` +
  `device-parameter-evidence`；
- `device_parameter_evidence_auditor` +
  `scidiscovery.evidence-audit.device-parameters.v1` + 无 output profile。

它们处于参数资格产生前：前者产生 primary/requirements/parameters/catalog，后者产生独立 audit；它们
不应消费 provider-aware 已批准资格。把 `task_schedule` 代码入口限制为这两个精确组合，比继续让
角色 prose 约束其他 legacy role 更安全，也没有新增 bridge registry。所有真正下游消费者走
InputPortSpec/Operation 即可。

### 参数、ReviewDocument 与 execution 边界维持通过

参数 pass/exception 的完整 subject 顺序、metadata-only source 关系和真实 audit lineage无新矛盾；
ReviewDocument 的固定五类型、二进制 metadata/download、稳定顺序、256 subjects、64/512/512 KiB
上限与 escape/CSP 可以直接落在现有 ApprovalRequest/UI；execution 创建和 authorize/start 双端身份
比较也没有被本轮 family/provider 返工削弱。

## 阻塞 1：结构化修订后的 final extraction primary 没有可达的资格路径

第 7.2 节的 family 只从 Task/output 映射构造，并规定找不到该映射时失败关闭。对初次
`science.evidence.extract.v1`、figure extraction 和 device-parameter legacy extraction 都成立，因为
它们的 primary 和 sibling 是同一次 Task finalization 的输出。

但当前公开且仍由 scheduler 指导的 intake 修订路径不同：

```text
base ScientificIntake
→ science.intake.revise.v1            # Agent 只产生 StructuredRevision
→ science.revision.apply.intake.v1    # support transform 产生 revised_object + revision_diff
→ science.evidence.receipt.intake.v1  # 证明 evidence 集未变
→ independent delta audit
→ final human qualification
```

`science.revision.apply.intake.v1` 的两个 transform 输出通过同一个 invocation request fingerprint、相同
精确 parents、operation id/version/digest 和不同 output port 被注册；它们有可验证 producer，但没有
`task_output_artifacts` 行。修订后 final foundation 位于 revised ScientificIntake 中，不能继续审批旧
base primary。若 qualifier 一律拒绝 transform primary，则“要求修订”这个 UI 选项会导向一个永远不能
重新批准的对象，结构化 revision Operation 和 unchanged-evidence receipt 也成为死路径。

这不是历史兼容性问题，而是当前 public Operation 与当前 scheduler 合同。

### 最小修复

二选一，优先采用第一项：

1. 把 family resolver 明确限定为两个受控分支，而不是开放所有 transform：
   - **Agent extraction 分支**：维持现有 Task/output + evidence-source 精确 family；
   - **typed intake revision 分支**：只接受当前 compiled
     `science.revision.apply.intake.v1` 的 `revised_object`，从既有 scheduler binding 的同一
     request fingerprint、Artifact labels/parents 和 compiled output ports 即时恢复恰好一份
     `revision_diff`；再沿已有受控 revision lineage 验证 exact base、patch、diff、
     `unchanged_evidence_receipt`、base family/frozen sources 和新的 independent delta audit。只有 receipt
     明确证明 evidence 未变时才复用 base family；changed evidence 必须走新的完整 extraction/audit。
   该分支仍是对现有绑定/Artifact/Operation 的即时投影，不建立 invocation-output registry，也不让
   任意 transform 获得资格。
2. 若本阶段明确不支持 revised evidence qualification，则必须同时从 public catalog、scheduler 指导
   和测试中退休 `science.intake.revise.v1`、`science.revision.apply.intake.v1` 与对应 evidence receipt，
   并规定 evidence 修改只能重新运行完整 extraction。不能保留公开修订路径却让其 final object 必然
   fail-closed。

第一种方案应增加一正三负：完整 typed revision + receipt + 新 audit 可创建资格；缺 diff、receipt
不覆盖 exact base evidence、普通 transform 伪装 revised primary 均拒绝。无需支持 hypothesis 或
experiment transform 的人工 evidence qualification，它们有各自的科学审查路径。

## 第三轮复审后的最小返工门

只需在第 7.2/7.3/7.5 节说明 typed intake revision 的 family 恢复和完成门，或明确退休这条公开路径。
第二轮已闭合的 Task family、provider dependency/readiness、legacy bridge、参数、UI 和 execution 设计
不应再次扩大。

返工后进行第四轮只读复审；在此以前不能进入 R4-D-B。
