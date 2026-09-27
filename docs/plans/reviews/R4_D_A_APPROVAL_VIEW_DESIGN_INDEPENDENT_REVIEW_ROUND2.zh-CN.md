# R4-D-A 审批视图设计第二轮独立复审

状态：第二轮只读复审完成  
范围：`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 第 7 节首轮五项返工、当前 Operation digest/
插件依赖、证据输出族、legacy bridge、readiness、ApprovalService、固定 UI 与 execution authorize 路径  
方法：跨边界闭环审查、单一权威审查、插件生命周期审查、简化审计

## 结论

**打回，不允许进入 R4-D-B。**

首轮五项阻塞的主体修复已经正确写回：provider identity 被定义为消费端准入事实；参数两个
Operation 均补了唯一 extraction primary 并纠正了 metadata-only 来源关系；projector 被诚实限定
为受信进程内窄 API；固定文档已有类型、顺序、数量、字节和 XSS 边界；execution 也要求 create 与
authorize/start 双端复核同一 compiled identity。这些设计没有引入第二审批注册表，也没有形成
provider digest 递归或资格环。

但是仍有两个实质缺口。第一，通用 `science.evidence.qualify.v1` 仍没有显式要求恰好一个
`extraction_primary`，也没有可用信息证明调用方提交了该 producer 的全部附件；这与已冻结的完整
科学审批束矛盾，尤其会允许遗漏 figure collection 中的兄弟输出。第二，
`accepted_approval_operations` 只解决了 Operation 消费者；readiness 和临时 legacy task 没有消费
Operation 摘要，因而没有合法来源取得允许的 provider 集合，且 TCAD 对 general-science provider 的
跨插件依赖尚未要求显式声明。按现稿实现，只能回到 Root allowlist、接受任意已安装 provider，或让
readiness 与 preflight 不一致。

这两项都能通过补充现有 catalog 与只读快照完成，不需要新增科学实体、资格状态机或第二注册表。

## 首轮五项返工复核

| 首轮阻塞 | 第二轮状态 | 复核结论 |
| --- | --- | --- |
| provider identity 未进入准入 | 部分闭合 | Operation cohort 已有 provider-aware 合同和摘要绑定；legacy/readiness 的 provider 来源仍未闭合，见阻塞 2。 |
| 参数束漏 primary、来源规则错误 | 通过 | pass/exception 都明确消费恰好一个 extraction primary；observation 必须落入 catalog，catalog 额外项仅作 metadata-only，不能贡献数值、coverage 或独立来源计数；audit 只声明实际输入。 |
| projector 被误写成沙箱 | 通过 | 已明确它是受信进程内插件组件，窄快照只限制正式 API；复用现有 `projector` component kind，没有新增组件注册类型。 |
| ReviewDocument 协议不完整 | 通过 | 五种固定 item 覆盖 JSON 和非 JSON；非 JSON 只能 metadata/download；顺序、256 subjects、64 节、512 项、512 KiB、escape、CSP、`nosniff` 和历史不重跑插件均已冻结。 |
| execution 只在创建端校验身份 | 通过 | 创建和 authorize/start 两端均比较当前 Effect、ApprovalRequest、两个精确 subjects 与 ExecutionRequest 标签；旧 fallback 决定不可启动。 |

## 已通过的关键边界

### approval executor 是最小且必要的执行类型

最终人工资格跨越多个 producer 的不可变结果，无法诚实附着在某一个 Agent/transform 输出上。
无输出、无 Worker、无 execution state 的 approval executor 只复用既有输入、guard、limits、
ReviewSpec、ApprovalService 和 compiled catalog；它比第二审批注册表或占位 Artifact 更小。
executor component 按已有 `projector` kind 解析并与合同 projector 精确同一，也避免了组件双权威。

### provider digest 不产生递归或资格环

消费 Operation 摘要依赖 provider 的 id/version/operation digest/contract digest；provider 被禁止再
依赖审批 cohort，因此 provider edge 深度为一，不会回指消费端。approval Operation 没有科学输出，
也不能成为 independent Agent reviewer，所以不会经 reviewer digest 形成间接环。实现时只需把
provider edge 纳入现有 catalog digest 的有向无环解析，并为任何违反“provider 无审批 cohort”的
声明启动失败；不需要单独的 digest registry。

### 三个审批 Operation 的数量仍然合适

一个通用证据资格加参数 pass/exception 两个价值分支是最小集合。参数 pass 与 exception 的选项和
coverage 前提不同，拆开可保持静态合同；不应再合并成运行时 option selector，也不需要第四个参数
审批 Operation。剩余问题是通用证据 Operation 的端口完整性，而不是 Operation 数量不足。

### 固定文档可以落地且没有新的插件权限

`json_value/json_tree/status` 只能解析冻结 JSON pointer，`subject_metadata/download` 只指向 subject；
PDF、图像、CSV 和 TCAD 包不需要插件 renderer。subject 顺序由合同端口和调用绑定顺序唯一决定，
插件不能注入 URL、HTML、脚本或 disposition。核心统一 escape，并保存 ReviewDocument 而不是保存
渲染 HTML，插件卸载后仍能安全审计。该协议与当前 256-subject ReviewManifest、固定下载路由和 CSP
兼容。

## 阻塞 1：通用证据资格仍不能证明完整科学审批束

第 7.3 节把 `science.evidence.qualify.v1` 定义为“最终科学基础、一个或多个待审科学对象、独立 audit
和 supporting evidence”。这里的“一个或多个待审科学对象”不能替代“恰好一个 final extraction
primary”：调用方可以只绑定 foundation 或另一对象，仍满足文字合同。参数两个 Operation 已经补了
明确 primary，通用证据 Operation 也必须采用同一不可省略语义。

更重要的是，projector 当前快照只含本次已绑定 subjects 的端口/位置、Schema、媒体、父引用、标签、
handoff 和字节。它能证明“这些附件属于 primary、audit 审过这些附件”，却不能证明“producer 没有
另一个未被调用方绑定的兄弟附件”。当前 figure extraction 最多产生 primary、manifest、16 个 source
panels、32 个 overlays、128 个 curve tables 和 validation report；Worker 的完整 bundle 在 TaskService
中有精确 output-family 映射，但这个完整映射不在第 7.2 节的 projector snapshot 中。调用方同时漏掉
某个 curve table 和 audit 输入时，仅比较已提交父链无法发现遗漏。

这会违反现有“final extraction primary + task_outputs 全部附件 + frozen sources + deterministic
validation + final audit”的资格定义，并使人类看到的 cohort 不是 producer 的完整结果。

### 最小修复

1. 把 `science.evidence.qualify.v1` 的输入明确冻结为：恰好一个 `scientific_foundation`、恰好一个
   `extraction_primary`、恰好一个 `evidence_audit`，以及有界的 supporting evidence；不得让
   `extraction_primary` 混在通配集合中。
2. 核心在调用 projector 前，从既有 immutable task/output 映射形成一个只读、内容绑定的
   `producer_output_family` 快照：primary ref、每个 output port/collection/item 的精确 ref 和冻结顺序。
   它只是现有控制事实的窄投影，不注册 Artifact、不暴露 TaskService/数据库/可写句柄，也不是第二
   registry。若 primary 没有可验证的 compiled producer/output-family，资格请求失败关闭。
3. evidence projector 要求本次 subjects 精确覆盖该 family 的全部科学附件，并覆盖 foundation 声明的
   全部冻结来源与适用的 deterministic validation；audit 必须绑定它实际审查的 primary、附件、来源
   和 validation。不得靠父引用的普通祖先扩张或凭 Schema 猜测兄弟输出。
4. 增加真实 figure bundle 负例：分别遗漏一个 collection item、validation report、frozen source 和
   extraction primary；即使余下对象的父链和 audit 都自洽，也必须拒绝创建审批。

## 阻塞 2：跨插件 provider 依赖与非 Operation 调用者没有唯一合同来源

第 7.2 节规定 `accepted_approval_operations` 只能引用同一 catalog 的 public approval Operation，
并把 provider digest 冻结进消费 Operation；但没有要求跨插件引用必须由 `PluginDependency` 声明。
TCAD 参数消费者将接受 general-science 插件中的 pass/exception provider，而当前 TCAD 插件只声明
对 builtin 的依赖。若只按全局 operation id 查找，插件会获得一个未声明的安装/升级依赖；卸载或版本
变化时，错误只能表现为偶然的 catalog 失败，而不是插件合同明确失败。

此外，`accepted_approval_operations` 位于 `InputPortSpec`。Operation preflight 可以据此调用
provider-aware 查询，但当前 global readiness 和 `task_schedule` legacy bridge 没有消费 Operation
摘要。第 7.2 节只说它们“调用同一处查询”，没有说明它们向查询传入哪一个已编译 provider 集合：

- 若 Root 写死 `science.evidence.qualify.v1` 或参数两个 provider，就重新形成 allowlist；
- 若接受任意当前已安装的 public approval provider，恶意或错误插件可以用较弱 projector 取得资格；
- 若 readiness 先把对象全局标为 qualified，再为不接受该 provider 的 Operation 广告可用行动，
  advisory 与 authoritative preflight 会发生断裂。

当前仅应保留的两个 device-parameter legacy bridge 是资格产生前的 extraction/audit 路径，本身不应
成为已批准 foundation 的通用下游消费者。其余 legacy role 若仍可由 `task_schedule` 消费科学资格，
就无法在不增加第二合同面的情况下安全接入新 provider 模型。

### 最小修复

1. 编译器解析跨插件 `accepted_approval_operations` 时，要求消费插件显式声明 provider 插件依赖，
   与现有 cross-plugin reviewer/component 规则一致；TCAD 插件声明对 general-science 的依赖。缺失、
   版本不符、provider 非 public/approval、provider 自含审批 cohort 都在启动时失败。
2. scheduler catalog 的端口摘要公开声明的 provider operation ids；readiness 在枚举每一个候选
   Operation 时，使用该候选已冻结的 provider identities 调用同一查询。对象级状态只能报告
   “存在由某 provider 作出的已决定审查”，不能把它当成对所有消费者都成立的全局资格。
3. `task_schedule` 在代码上只允许现存两个精确 device-parameter pre-qualification bridge 及其固定
   context/output profile；二者不授予下游资格，也不需要 accepted-provider allowlist。任何仍需消费
   已批准科学对象的 legacy role 必须先迁成有 `InputPortSpec` 的 Operation，不能从 prose 或 Root
   常量获得 provider 集合。
4. 增加 clean-install/disable/upgrade 负例，以及“对象由 provider A 批准，但候选 Operation 只接受
   provider B”的 readiness/preflight 一致性测试；两个 legacy bridge 以外的 `task_schedule` 调用必须
   失败关闭。

## 第二轮复审后的最小返工门

在第 7 节补齐以下两项后再进行第三轮只读复审：

1. 通用 evidence qualifier 的唯一 extraction primary 和完整 producer output-family 快照/精确覆盖；
2. provider 跨插件依赖，以及 readiness 与 legacy bridge 从哪里取得消费端 provider 合同。

无需改动已经闭合的参数 pass/exception 分拆、ReviewDocument 五类型、projector 信任模型或 execution
双端身份门，也不应新增 Approval Registry、QualificationReceipt、领域 UI、兼容 provider allowlist
或新的资格状态机。
