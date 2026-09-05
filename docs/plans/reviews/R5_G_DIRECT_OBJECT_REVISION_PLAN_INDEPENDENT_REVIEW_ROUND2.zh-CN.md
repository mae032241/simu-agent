# R5-G 直接完整对象修订方案第二轮独立复审

审查对象：

- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md`；
- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/README.md`；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`；
- 对照 `docs/ARCHITECTURE.zh-CN.md`、当前 `OperationSpec`、Task、Root、通用科学插件、
  curve-score、TCAD、安装态测试和盲插件消费者。

审查方式：只读方案、源码消费者和跨边界合同；未修改生产代码、测试、计划或私有科学对象。本报告
是本轮唯一写入。由于候选仍是未实施方案，本轮没有用当前旧实现的 pytest 通过冒充 D1—D4 的实现
证据。

## 结论

**通过，仅放行 D0。D0 完成后仍须由未参与实现的独立审查者通过，才能进入 D1。**

首轮 F1—F5 已全部写回为可实施、失败关闭且顺序自洽的方案。新方案把修订恢复为原专业 Agent 的
普通完整对象生产：旧对象不可变，控制面只校验精确调用、完整 Schema、最小上下文、父链和新的独立
审查。迁移结束后会删除结构化补丁、Apply、Diff、Receipt、补丁专用 Task/Worker 合同和 Root 递归
修订族，没有新增修订实体、注册表、数据库表、状态机或领域白名单。相较旧强制链，这是有真实删除
对象和消费者证据的简化，不是把复杂度搬到另一套控制面。

本结论不表示 D1 的准入函数、D2 的消费者迁移、D3 的协议删除或 D4 的真实科学修订已经实现，也不
放行实验设计、R5-G 完成或发布冻结。

## 首轮问题复核

### F1：已关闭——迁移期免审和最终 catalog 硬门具有唯一结构边界

计划第 3.1—3.2 节现在从既有字段定义了直接完整修订的结构总函数：只有
`executor=agent`、`consequence=scientific`、恰好一个必需单值 `revision_base`、恰好一个与 base
Schema/媒体类型/编译 codec 相同的非集合主输出，并且该输出被 `ReviewSpec` 指定给独立 reviewer，
才是合法直接修订。调用期还必须验证旧对象显式允许 `revision_base`、新旧 review 合同一致，以及
可选 `change_request` 是旧合同指定 reviewer 对精确旧对象的完成输出。

该规则闭合了首轮指出的旁路：

- Transform、Effect、Approval、无 ReviewSpec Agent、不同 Schema/codec 或 reviewer 漂移均不满足
  结构；
- `blocked`、`revise`、`inconclusive`、`pass` 评审只能说明修改请求，不能把旧对象或新对象变成
  普通合格下游；
- 无 change request 只由端口基数决定，新对象仍必须重新审查；
- 迁移期只有满足完整结构的 Agent 在 preflight 获得旧 base 免审，旧 apply/receipt 虽暂时可编译，
  仍走普通资格门，不因 `revision_base` 得到例外；
- D3 删除最后一个旧声明后，才把同一结构规则提升为 catalog 编译硬门。

因此迁移期没有把 `revision_base` 变成通用免审用途，最终态也没有留下兼容 facade 或第二政策表。
D1 审查仍须核对 preflight 分类和 D3 catalog 硬门使用同一语义函数或有精确等价测试，不能形成两套
会漂移的修订判定；这是实施验收，不是当前方案阻断。

### F2：已关闭——先迁消费者、后删协议，D1 纵切面可闭合

阶段顺序已经改为：

1. D0 只撤销未通过的半修复并冻结旧失败；
2. D1 实现直接修订准入，同时迁 general intake/hypothesis、按 usage 的来源投影、直接 intake
   qualifier 和 TCAD project 的 `revision_base` 输出用途；
3. D2 再迁 curve-score experiment、盲插件、真实评估、生成资源和安装态消费者，并证明发布生产
   路径对旧协议零引用；
4. D3 才删除旧 Schema、spec 字段、Task/Worker 分支、apply/receipt Operation、Root 递归族和历史
   Transform 实现，并执行 clean-wheel 与 TCAD 两条完整工程修订重放；
5. D4 最后创建新的真实 hypothesis portfolio 和新的 critic。

这消除了首轮“先删 curve 依赖、后迁 curve”的不可编译顺序。D1 也不再只产出一个无法资格化的
direct intake，而是把新完整 audit 和新人工资格纳入同一阶段完成门；TCAD 也在通用准入改变时同步
开放精确 project revision 用途，不放宽普通打包和执行。

### F3：已关闭——完整父链与科学来源投影分离且不增加状态

计划第 4.5 节明确保留所有 Task/Artifact 直接父输入，同时只从现有 `TaskInput.usage` 的
`claim_evidence`、`evidence_inventory`、`cached_excerpt` 以及受控 web/PDF 登记投影
`ProducerOutputFamily.evidence_sources`。`revision_base`、`change_request` 和 `prior_signal` 留在
不可变父链中，但不能升级为支持事实陈述的来源。

该设计直接复用现有 Task 输入和既有 web/PDF 记录，不增加来源表、收据或注册表；正负例同时要求
删除真实来源会破坏 audit/qualification、删除旧 draft/review 会破坏父链，而旧 draft/review 不得
出现在 frozen source set。它既保留谱系，又避免把被打回的审查意见当科学证据。

### F4：已关闭——消费者矩阵覆盖当前真实发布面和历史边界

第 4.7 节现在逐类覆盖：

- spec/catalog/invoke/builtin 声明；
- structured revision 与 evidence receipt Schema/导出；
- Task、Worker 文件校验和模型可见 `roles/common.md`；
- Root producer family；
- general Agent/资源/组件/控制 Operation 和 intake projector；
- curve-score experiment 与复制的 apply/receipt；
- 历史通用 Transform；
- TCAD 完整 project revision；
- R5-G 脚本、冻结 manifest、生成调度提示、`MANIFEST.sha256`；
- installed entry path、四类 clean-wheel、盲插件和结构/专项测试；
- 中英文当前架构文档；
- 冻结 baseline 脚本、历史报告与旧持久 Artifact。

独立 `rg` 得到的当前生产、测试和夹具命中均能落入上述类别。最终零命中门只作用于发布生产路径
和当前生成资源，不要求为清洁统计篡改冻结历史。D3 候选闭合后才同步双语当前架构，D0—D2 不会
把设计草案提前写成实现事实。

### F5：已关闭——四份计划语料已同步且不改写历史结论

- R5 主计划第 6 节把 R5-B 的修订 Transform 递归明确标为已通过的历史实现事实，只局部拟被本
  计划替代，Agent/Transform family 完整性、指纹、去重和失败关闭仍保留；
- R5 主计划回退边界已承认本子阶段会修改 catalog、Task/Worker、Root family 和插件合同，并要求
  D0—D4 分阶段回退和复审；
- README 已同步 R5-B—R5-F 通过、R5-G 证据阶段通过、真实 critic 为 `blocked`、直接修订方案待审；
- OperationSpec 主计划顶部与末尾状态均同步至 R5-F 通过、R5-G 直接修订第二轮待审，不再残留
  “当前只允许 R5-C”的矛盾；
- 当前架构文档继续只描述已实现事实，方案明确在 D3 候选闭合后再双语更新并纳入独立审查。

历史 R5-B 和首批 structured revision 迁移记录继续保留为当时事实，不被本草案追溯改写；只有 D3
实现通过后，当前架构和发布资源才切换到直接完整对象修订。

## 跨边界与奥卡姆判断

方案保持以下承重边界：

- 单一 `scidiscovery.plugins` 入口和单一 `CompiledCatalog`；
- 一个 OperationSpec 闭合 Agent、端口、工具、资源、validator、review 和预算；
- Worker 只读精确旧对象、科学上下文和可选评审，输出完整对象但不写控制身份；
- Task、Artifact、CAS、审批和执行的既有状态权威不复制；
- 旧对象及旧 verdict 不可变，新版本不继承资格；
- 普通科学下游和外部执行仍要求新 reviewer 通过；
- TCAD 保留任务私有 deck 编辑与领域工具，这与跨 Artifact 结构化补丁协议明确分层；
- 差异仅在出现真实 UI 需求时由精确旧/新对象无状态投影，不预建新实体。

这符合当前 33 项约束族中不可变来源、最小上下文、独立审查、人工审批、外部副作用、插件单一
入口和失败关闭边界，也符合“灵活、低成本、可扩展的通用 AI 科学家”目标。未知插件只需声明一个
完整对象 Agent 和原 reviewer，不需核心识别 Operation 名、Schema、插件或角色。

## D0 放行边界

D0 只允许：

1. 保留真实 blocked critic、旧 portfolio 和既有独立审查证据；
2. 增加精确复现旧补丁链断裂的最小失败测试；
3. 撤销 `_REVISION_REQUEST_VERDICTS`、`_revision_admission_subject_refs` 及对应未通过的临时测试和
   文档结论；
4. 保留旧补丁协议，恢复到可比较的已知基线。

D0 不允许实现直接修订、删除旧协议、改写科学对象、启动新 hypothesis Agent 或进入实验设计。
D0 完成后必须先独立审查：确认半修复确实撤销、旧失败可复现、无科学证据或持久对象被改写，才可
考虑 D1。

## 非阻断实施注意

- `science.intake.revise.v1` 的固定 reviewer 合同会自然拒绝 reviewer 不同的 figure-extraction base；
  图证据缺陷仍应按已冻结边界重跑完整 figure extraction bundle 并重新审计，不应把单一 intake
  修订扩张成附件继承协议。
- D1 应用真实 unknown-plugin preflight/invoke 负例证明结构分类，而非只调用一个私有 helper；D3
  再用 clean-wheel 编译负例证明非法旧声明已经不能安装。
- 当前 `TaskOutputReviewSpec` 冻结的是 reviewer operation、subject port 与 accepted verdicts；本计划
  不应趁机扩张成新的 reviewer 身份实体。change request 只提供修改上下文，新输出的新审查才是
  下游资格事实。

## 实际检查

所有命令均在仓库根目录、7 GiB 虚拟内存上限、严格串行下执行：

```text
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1

git status --short --branch
git diff --check

rg -n --glob '!docs/**' --glob '!deliverables/**' --glob '!123/**' \
  'StructuredRevision|StructuredRevisionOperation|StructuredRevisionDiff|UnchangedEvidenceReceipt|structured_revision_apply|unchanged_evidence_receipt|revision_base_port|allowed_revision_paths|unchanged_set_receipt|science\.revision\.apply|science\.evidence\.receipt|revision_diff|revision_base|change_request' \
  src plugins roles scripts tests pyproject.toml MANIFEST.sha256

rg -n '直接完整对象|StructuredRevision|structured_revision|RevisionDiff|unchanged|R5-G|R5-B|状态：|当前阶段|修订' \
  docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md \
  docs/plans/README.md docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md

git diff --check -- docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md \
  docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md \
  docs/plans/README.md docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md
```

结果：文档空白检查通过；当前旧协议消费者均可由迁移矩阵归类；F5 的状态冲突已消除。未运行
pytest、clean-wheel、真实 Worker 或 TCAD：这些属于 D0—D4 的实现证据，其中 D0 只需精确旧失败
测试，D1—D3 才需要真实调用、安装态和全仓门，D4 才允许产生新的科学对象。
