# R5 E5 图证据修订拓扑独立审查

日期：2026-09-05  
审查范围：真实图证据审查返回非通过结论后，`ScientificIntake` 是否存在契约正确、最小且可审计的修订路径。  
限制：只审查，不修改生产代码或测试。

## 1. 结论

**当前实现：FAIL。阻断项 5 个。**

**方案方向：接受“在可选图插件新增一个 public 图 Intake 完整对象修订 Operation”；没有更小且契约正确的现有路径。**

但题述方案还需要两项已有机制的最小声明和一项插件内机械 guard 才能通过：

1. `prior_draft`、`change_request` 和完整 `FIGURE_FAMILY_INPUTS` 必须同时声明；
2. 新 Operation 必须声明与原图 Intake 完全相同的 figure audit review edge、同一
   `complete_transform_family`，并使用有界修订及无进展指纹；
3. 一个插件内、无状态的 guard 必须证明所绑定完整图族同时属于 `prior_draft` 和精确
   `change_request` 的父链；仅证明“当前绑定自身是一个完整族”还不够；
4. Worker 可见提示必须明确完整对象、写时复制和最小修订语义；
5. 下游 curve-bundle guard 必须删除初始提取 Operation id 白名单，否则新修订即使重新审查通过也
   无法被消费。

这些都可由现有 `OperationSpec`、`ReviewSpec`、guard、完整生产族合同和 direct-revision
准入实现；**不需要修改核心模型、Root 路由、数据库、调度器、注册入口或 Worker 生命周期。**

## 2. 当前没有可用的既有路径

当前可选图插件只注册请求、物化、图 Intake、图审查和曲线包五个行为，没有图 Intake 修订行为。
源码编译探针确认图 Operation 集合中不存在 revision Operation。

通用 `science.intake.revise.v1` 也不能作为替代：

- 它声明的 reviewer 是 `science.evidence.audit.intake.v1`，而图 Intake 冻结的 reviewer 是
  `science.figure.evidence.audit.v1`；Root 会比较精确 reviewer Operation、输入端口和接受 verdict，
  不允许不同审查合同互换；
- 它只有一个最多 6 项的 `opaque source_material` 端口，不能表达 PDF、类型化 request、manifest、
  report、panel、overlay 和两张变长 table 的端口身份及完整生产族；
- 真实负控已以 `fig4_e5_abi15_intake.output`、精确 figure audit 和 PDF 调用该 Operation，preflight
  返回 `input_revision_review_contract_mismatch`。因此仅放宽 `source_material` 数量既不能通过
  direct revision，也会丢失类型和族完整性，不是修复。

`direct_revision_ports()` 已提供正确的领域无关形状：科学 Agent、唯一必需 `revision_base`、单一
同 Schema/媒体/codec/resource 的完整输出，以及精确 review edge。Root 又要求 `change_request`
必须是冻结 reviewer 对精确 base 的非通过输出。现有能力足够，缺的是一个图插件声明，不是新的核心
修订系统。

## 3. 最小正确 Operation

建议 Operation id 使用稳定且明确的图插件名称，例如：

```text
science.intake.revise.figure.v1
```

它应为 `public`、`agent`、`scientific`，并声明：

```text
输入
  prior_draft       ScientificIntake，usage=revision_base，恰好 1 项
  change_request    EvidenceAudit，usage=change_request，恰好 1 项
  paper_source
  figure_request
  figure_manifest
  validation_report
  source_panels
  audit_overlays
  curve_tables

输出
  scientific_intake ScientificIntake，恰好 1 项
```

其中七组图输入直接复用 `FIGURE_FAMILY_INPUTS`；输出直接复用 `INTAKE_OUTPUT`；Agent、Schema、codec、
payload/context validator、语义合同、文件工具、PDF 工具和原生图像查看能力均复用现有图 Intake
能力。不得新增 patch、diff、receipt、字段白名单或“只允许改文案”的专用对象。真实 change request
可以只要求改文案，但修订 Agent 的职责仍是提交一个完整的新 Intake；独立审查决定其修改是否恰当。

review edge 必须保持：

```text
reviewer_operation  = science.figure.evidence.audit.v1
reviewer_input_port = scientific_intake
subject_outputs     = (scientific_intake,)
accepted_verdicts   = (pass,)
```

这使初始图 Intake 的冻结 review 合同与修订 Operation 声明一致，Root 才能接受精确 blocked/revise/
inconclusive 审查作为 `change_request`。修订输出是新 Artifact，不继承旧审查或资格；它仍必须重新经过
同一个 figure audit。

## 4. 阻断项

### 阻断 1：当前 catalog 没有图 Intake 修订 Operation

当前非通过图审查没有可调度的下一 public 行为；通用修订又被精确 review 合同正确拒绝。继续绕到
通用 evidence extraction 或手工改 Artifact 都会破坏不可变性、角色边界和单一行动权威。

### 阻断 2：完整族尚未与被修订对象及审查请求绑定

`complete_transform_family` 只证明本次七组图输入来自同一次 materialize 调用及其精确
`paper_source/figure_request`，不会自动证明这个族就是 `prior_draft` 和 `change_request` 使用的族。
否则可以把族 A 的 Intake 和精确审查与族 B 的完整附件一起提交，两个局部合同分别成立，组合却错误。

最小修复是复用现有 `guards`，在图插件提供一个无状态机械 guard：

- 取得本次所有 `FIGURE_FAMILY_INPUTS` 的精确 refs；
- 要求它们全部存在于 `prior_draft.parent_refs`；
- 同时要求它们全部存在于 `change_request.parent_refs`；
- 不读取科学 payload，不识别 Fig.4，不查询数据库，不建立新状态。

每个 Agent 输出本来就把全部 Run 输入登记为父链，因此该 guard 使用的是已有不可变事实。完整族合同
负责“族自身正确”，guard 只负责“该族属于这次被审查对象”，职责不重复。

### 阻断 3：题述 review edge 未明确有界修订和无进展停止

设计宪章要求同一审查边修订次数有界，问题维度无进展时停止。新 Operation 应直接使用现有
`ReviewSpec.max_revisions` 与 `progress_fingerprint`，建议与已验证假设修订一致设 `max_revisions=2`。

只需在可选图插件增加一个确定性、无状态的 EvidenceAudit 问题指纹组件。指纹应基于非通过 check 的
稳定结构维度（至少 `check_key`、`status` 及其闭合引用），排序后摘要；必须排除 `subject`、`basis`
等自由文案，避免改写措辞冒充进展。它不是新事实源，也不选择下一 Operation。相同问题指纹返回
`revision_no_progress`，达到上限返回 `revision_limit_reached`，由现有 Root 路径完成。

不得复用 `critic_progress_fingerprint`：它解析的是 `CriticReview`，与 `EvidenceAudit` Schema 不同。
也不得用整个审查 JSON 摘要，因为文案变化会错误地被视为科学进展。

### 阻断 4：当前图 Intake 提示没有修订语义

现有 `INTAKE_PROMPT` 只描述首次从完整图族形成 Intake，没有要求先读 `prior_draft`、按精确
`change_request` 做写时复制和提交完整对象。若新 Operation 原样复用该提示，虽然结构准入成立，
Worker 仍可能重新提取或忽略审查意见。

最小改法是在现有图 Intake 提示增加条件段：仅当存在 `prior_draft/change_request` 时，先读旧对象，
只修改精确审查要求涉及的内容，保留未受挑战的来源、身份、不确定性和全局目标，提交完整新
`ScientificIntake`，且不继承旧 verdict/资格。无需新增第二提示组件或第二 validator。

## 5. 为什么不选择其他方案

### 修改通用 `science.intake.revise.v1`

不正确。要使它同时接受 generic audit 与 figure audit，必须引入多 reviewer/条件端口/动态族语义，
或让 Root 按领域判断；这比一个插件 Operation 更重，也把可选图能力反向耦合进通用插件。

### 把 prior/change 设为首次图 extraction 的可选端口

不正确。direct-revision 形状要求唯一 `revision_base` 是必需单项；把它设为可选会失去 direct revision
准入，设为必需又会破坏首次 extraction。为避免条件端口语言，两个窄 Operation 是更小方案。

### 将完整图族包装成单一 opaque bundle

不正确。它会新增聚合 Transform/Artifact 和另一套拆包校验，仍无法自然继承现有类型化端口与完整族
合同，属于以新实体隐藏问题。

### 让 scheduler 记住并手工校验附件

不正确。调度 Agent 可以选择和绑定，但完整性、父链和 direct review 准入必须由同一编译
Operation/preflight 机械证明；提示词或固定流程表不能成为第二权威。

## 6. 最小生产文件边界

实现本方案不应修改 `src/scidiscovery/operations/spec.py`、catalog、Root、Run、current、审批、UI、
Execution 或调度器。最小生产改动集中在：

1. `plugins/curve_score/curve_score/figure_science_operations.py`
   - 声明一个 public 图 Intake 修订 Operation；
   - 复用现有端口、输出、Agent、validator 和工具；
   - 增加条件式修订提示；
   - 增加一个父链 guard 和一个 EvidenceAudit 问题指纹组件；
   - 在 `ReviewSpec` 声明 `max_revisions` 和 `progress_fingerprint`。
2. `plugins/curve_score/curve_score/operation_transforms.py`
   - 仅从 `figure_parentage` 删除对初始图 Intake producer id 的判断；保留类型化输入、输出端口、
     完整图族父链、精确 figure audit 父链和 pass verdict 校验。
3. `plugins/curve_figure_evidence/README.md` 与 `README.zh-CN.md`
   - 把公开能力清单更新为六个 Operation，不新增设计文档体系。

`curve_figure_evidence.plugin:PLUGIN` 已从上述模块汇集 `COMPONENT_SPECS/OPERATIONS`，无需新增注册入口、
plugin-private registry 或手写启动接线。若本阶段执行发布版本递增，只同步现有插件包版本，不改变
核心 Operation ABI。

## 7. 最小测试边界

聚焦修改现有测试，不新建通用修订框架：

1. `tests/operations/test_m2_optional_figure_plugin.py`
   - 可选插件增加且独占第六个 public Operation；插件未安装时该 Operation 消失；
   - catalog 投影包含 exact review edge、完整族、两项修订界限；
   - direct-revision 形状被现有总函数识别，工具和输出合同与初始图 Intake 一致。
2. `tests/operations/test_m5_plugin_ownership_and_default_surface.py`
   - 更新可选图插件完整切片集合，证明默认通用/TCAD catalog 未获得该能力。
3. `tests/operations/test_m5_figure_review_closure.py`
   - 初始图 Intake + 精确非通过 figure audit + 完整原族的 preflight/invoke/Worker submit 成功；
   - 当前通用 `science.intake.revise.v1` 继续以
     `input_revision_review_contract_mismatch` 拒绝同一请求；
   - 缺 sibling、混合 materialize invocation、替换 source/request、族与 prior/audit 不同、错误
     reviewer、审查对象不是 exact prior、以及 passing audit 作为 change request 均在 preflight 失败；
   - 对一个负例调用 invoke，证明同一拒绝且 Run/Artifact 数量不变；
   - 修订输出与旧对象同时保留，`supersedes_ref`/父链正确，旧 audit 不能审查新对象；
   - 新 figure audit 对精确修订重新执行后才能进入下游；
   - 精确重新审查通过的修订 Intake 能进入 curve-bundle，旧 audit、错 subject、错族和未通过的新
     audit 均不能进入；
   - 同问题结构只改文案触发 `revision_no_progress`，有限的新问题进展最多允许两次，随后触发
     `revision_limit_reached`。

完成源码聚焦测试后，还必须用安装态真实入口做一条纵向验证：catalog 可见新 public Operation、实际
Worker assignment 只包含声明文件和相同工具、真实修订 Agent 能读取 prior/change/完整族并提交、
新独立 figure audit 审查精确 revision。该验证属于 E5 继续执行，不要求新增测试后端。

## 8. 约束判断

- `AUTH-003`、`ROLE-002`：所有输入、工具、review、guard、修订界限和输出由同一编译 Operation
  授权；无 Root 私有名单。
- `IMM-001/002`：提交完整新对象，保留旧对象；精确请求变化创建 revision，旧 review 不继承。
- `TOP-001/002`：scheduler 只从 public catalog 选择；同一 preflight 对图族、父链和 change request
  失败关闭，invoke 无旁路。
- `ROLE-001`：Agent 修订科学内容，guard 只比较 refs，独立审查给 verdict；控制面不改文案。
- `DET-001/002`：完整族、父链和问题指纹是确定性机械关系，不选择科研结论。
- `PLG-001/002`：新能力只存在于可选图插件；核心和通用插件不出现图分支。
- `RES-001/002`：端口、字节、尝试和修订次数有界；不引入集合 Agent 输出。
- 奥卡姆原则：新增一个真实缺失的行为声明和两个窄无状态组件，复用所有既有核心机制；没有新实体、
  状态机、注册表、兼容层或固定流程。

## 9. 通过门

当前拓扑保持 **FAIL**，不得把 blocked figure audit 绕过为通用修订或重新 extraction。

完成第 3—7 节的最小实现、聚焦测试、安装态真实修订与独立复审后，如阻断项归零，可将本拓扑判为
**PASS** 并继续 E5。无需等待 UI 重写，也不得借本问题扩修 generic intake revision、核心资格或调度器。

## 10. 补充审查：curve-bundle 的 producer id 白名单

### 10.1 新发现的真实阻断

`plugins/curve_score/curve_score/operation_transforms.py::figure_parentage` 当前要求：

```text
intake_labels.operation_id == science.evidence.extract.figure.v2
```

因此新增 `science.intake.revise.figure.v1` 后，即使它提交完整新 Intake、绑定原完整图族并获得精确
`science.figure.evidence.audit.v1` 的新 pass 审查，`scidiscovery.curve-bundle.figure-evidence.v2`
仍会以 `guard_rejected` 拒绝。这是第五个阻断项，也是典型的注册目录与插件私有 producer 白名单
断裂。

### 10.2 唯一建议：选择 B

**选择 B：删除 Intake producer Operation id 特判，不枚举初始与修订两个 id。**

保留以下现有检查：

- `scientific_intake` 的类型化端口准入及 `operation_output_port == scientific_intake`；
- request 属于精确 paper source；
- manifest、report、panel、overlay 和全部 table 属于同一 materialize invocation，并具有精确
  source/request 父链；
- Intake 父链包含该完整图族；
- `evidence_audit` 的输出端口、精确 Intake+完整族父链和 `handoff_verdict == pass`。

同时，Root producer-output admission 会根据 Intake Artifact 冻结的 `operation_id/version/digest/output
port` 回读其已编译 OperationSpec；若该输出声明 review edge，Root 要求本次输入中存在该冻结
reviewer 对 exact Intake subject 的接受 verdict。新修订 Operation 声明与初始提取相同的 figure
audit edge，因此该通用门正好覆盖两者，不需要 guard 再复制 producer 名单。

这不会形成旁路：

- 任意 JSON 仍会被 `scientific_intake` Schema、媒体和编译 producer 合同拒绝；
- 未知、退役或 digest 漂移的 producer 仍由 Root 失败关闭；
- 缺少精确审查、复用旧审查、错误 subject、非 pass verdict 或错误图族仍分别被 Root 与
  `figure_parentage` 拒绝；
- 一个未来同样产生类型化 Intake、包含精确图族父链并经过同一 figure audit 的已注册 Operation，
  可以合法组合，而无需再次修改下游 guard。这是契约组合，不是放宽为任意 producer。

### 10.3 为什么拒绝 A 和其他替代

**拒绝 A：枚举两个 producer id。** 它能让本次 revision 暂时通过，但每新增一个合法图 Intake
producer 都必须再修改下游代码。该判断与 producer 冻结 ReviewSpec 重复，使插件私有函数成为
第二份拓扑注册表，违反 `AUTH-003`、`TOP-001` 和 OperationSpec 单一行动权威；也是本轮明确禁止的
针对性补丁。

不建议让 guard 自行访问 catalog、解析 OperationSpec 或新增“允许 producer”字段。Root 已拥有并
执行 producer 合同；把同一检查复制到 guard 会增加第二权威。也不应顺带删除 request/materialize
id 检查或重写整个 parentage guard：本次真实断裂只涉及 Intake producer 的可替换行为，其他条件
没有被新 revision 拓扑否定。

### 10.4 必须增加的测试

在 `tests/operations/test_m5_figure_review_closure.py` 的真实 Root 路径至少证明：

1. 初始 `science.evidence.extract.figure.v2` Intake + 精确 pass figure audit 仍能 bundle；
2. 新 `science.intake.revise.figure.v1` Intake + 对该 revision 的新精确 pass figure audit 也能 bundle；
3. revision + 初始旧 audit 被拒绝；
4. revision + 新但 blocked/inconclusive audit 被拒绝；
5. revision + 另一图族或 audit subject/父链不一致被拒绝；
6. 一个未知/退役/digest 漂移的 producer 不能借删除 id 检查通过 Root；
7. 负例 preflight 与 invoke 返回同一拒绝且不新增 Run/Artifact。

实现断言应同时确认 `figure_parentage` 不再包含两个 producer id 的集合或新的 allowlist。改动只删除
该一个初始 producer id 条件并补测试；不得借机泛化或重写其它曲线 parentage 规则。

### 10.5 补充约束判断

- `AUTH-003`：接受 B 后，合法 producer 由其编译 OperationSpec 与 Root admission 决定，不由
  `figure_parentage` 的名字列表决定。
- `PLG-001/002`：修改留在可选图插件实际提供的组件模块中；核心不增加图或 revision 分支。
- `ROLE-001/002`：guard 只验证机械父链，figure audit 仍拥有科学 verdict，修订 Agent 仍拥有内容。
- `TOP-002`：新 revision 在 catalog、preflight、精确审查和 downstream bundle 间可组合；负例仍在
  同一 preflight 失败关闭。
- 奥卡姆原则：删除一个冗余条件，复用既有强门；不增加 producer 枚举、字段、状态或注册表。
