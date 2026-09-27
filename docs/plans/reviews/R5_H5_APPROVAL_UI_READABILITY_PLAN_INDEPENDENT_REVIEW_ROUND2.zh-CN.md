# R5-H5 审批 UI 可读性方案第二轮独立复审

日期：2026-08-31  
审查对象：`docs/plans/R5_H5_APPROVAL_UI_READABILITY.zh-CN.md` 第二轮候选  
首轮报告：`R5_H5_APPROVAL_UI_READABILITY_PLAN_INDEPENDENT_REVIEW.zh-CN.md`  
审查性质：只读复审；未修改生产代码或被审查计划

## 结论

**通过。允许进入 H5 实施。**

第二轮候选准确闭合了首轮 B1—B3，且没有扩大实现范围。当前方案仍然只是：

1. 固定 renderer 删除 raw subject 的默认展开；
2. 窄屏用既有 CSS 改变决定栏的计算后视觉顺序；
3. 两个 TCAD projector 用已有 `ReviewDocumentItem + JSON Pointer` 重排摘要；
4. 保留完整 raw、受控下载、历史回退和原有审批决定生命周期。

没有新增摘要 Schema、item kind、数据库状态、前端框架、插件 HTML、第二 renderer、注册表或控制面
入口校验。

## 首轮阻断项复核

### B1：数量、标签和字节预算——已闭合

修订计划为 claim、非确认 coverage、来源和 resolved input 分别设置 TCAD projector 内部的 64 项
展示阈值。集合超过阈值时，不截断、不拒绝审批，而是用一个现有 `json_tree` item 指向完整集合
子树。标签只使用固定短标签、序号或既有 ASCII Identifier key，不复制最长可达 2048 字符的来源
标题。

参数资格 projector 的最坏逐项情形发生在各集合恰好 64 项时。按计划列出的字段上界计算：

- coverage 状态和三个计数：4 项；
- foundation objective/summary：2 项；
- 64 个 claim 的 key、unit、epistemic status、selected value：最多 256 项；
- missing inputs/open questions：2 项；
- 64 个非确认 coverage 子树：64 项；
- 64 个来源的 title/class：128 项；
- 四个必需 audit check 状态：4 项。

合计最多 **460 项**，低于 `ReviewDocument` 的 512 项硬上限。若实现把 claim 的短元数据合并进
label，实际 item 数只会更少。每个 item 只冻结短标签、subject 序号和短数组索引 Pointer，不复制
被指向的科学值；即使按 256 字节 key 标签做保守估算，也显著低于 512 KiB 文档上限。计划又要求
用最大合法集合实际覆盖 512 项和 512 KiB 两个边界，足以防止实现偏差。

execution projector 的固定标量和审查字段数量很小；64 个 resolved input 即使分别显示其五类既有
字段，也仍显著低于 512 项。第 65 项起退化为一个 `/resolved_inputs` 子树 Pointer，因此模型允许的
4096 项输入不会变成审批准入失败。

64 是 TCAD 展示形态选择，不是核心字段、Operation 合同、审批上限或新的准入规则；这不构成通用
摘要协议。

### B2：冻结研究目标——已闭合

“研究目标与参数”现在明确同时展示 foundation `/objective` 和 `/summary`，验收第 4 项也要求
objective 具有冻结指针。页面不再依赖实例上下文中的目标替代本次决定实际绑定的科学目标。

### B3：旧请求与新 projector 的身份语义——已闭合

验收已正确拆开两种情况：

- 对同一冻结请求，仅 renderer/CSS 改变时，请求引用、subject set、nonce、CSRF 和决定语义不变；
- 新 projector 创建请求时，保持 exact subjects、subject-set hash、选项和当前 compiled approval
  identity 的绑定，允许新 `ReviewDocument`、请求引用和 nonce 变化，并明确禁止继承旧决定。

这与不可变 ApprovalRequest 和一次性人工决定语义一致，不再诱导实现复用旧 nonce 或旧决定。

## 其他边界复核

- 计划包含 TCAD 参数 pass/exception 两个 projector，也包含 TCAD execution projector；没有遗漏
  外部执行授权页面。
- 无 `ReviewDocument` 的历史页面必须继续逐项展开和下载全部 subjects；raw 默认折叠不会删除或
  替换历史对象。
- 窄屏验收已改为 CSS 计算后的视觉顺序，同时保留唯一 DOM 表单和原有语义顺序，没有自相矛盾地
  要求移动 DOM。
- 完整 subject、subject-set hash、compiled identity、nonce/CSRF、决定绑定和下载字节继续由现有
  Approval 服务持有；projector 只冻结安全展示指针。
- 核心固定 renderer 仍不按插件名、Operation、Schema 或领域字段分支；TCAD 字段理解只存在于 TCAD
  插件 projector。
- 现有服务已经验证 subject 序号、JSON 媒体类型、JSON 解析和 Pointer 实际存在。计划没有叠加第二
  轮入口校验，这是正确的轻量化选择。
- 超过 64 项时显示一个完整集合子树会降低极端对象的摘要精细度，但仍比重复展开全部 subject 根树
  更小，并且保持完整性。当前阶段不应为这一极端情形增加表格组件、分页状态或摘要 DSL。

## 实施审查要求

本轮通过只放行既定最小实现。实现审查仍应确认：

1. 64 项阈值只在两个 TCAD projector 内，不进入核心 schema、catalog 或 admission；
2. 最大合法集合测试真实构造 `ReviewDocument`，而不是只断言手算 item 数；
3. 历史回退、完整下载、固定转义、一次决定和重复提交测试继续通过；
4. 使用已封存的真实 D4 资格 subjects 和真实结构的 execution request/package 做页面可读性检查，
   小型 fixture 不能单独替代现场验收；
5. 若实现需要新增 item kind、通用摘要器、前端状态或核心领域分支，应立即停止并重新审查。

在这些既有完成门下，第二轮方案符合奥卡姆原则，也没有把可读性修复重新做成重型控制面。

