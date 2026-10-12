# A 选择前审计：最小闭环

新实例通过 `prepare --enable-candidate-audit` 显式冻结 `candidate_audit_policy={"version":1}`；需要已配置的隔离 delivery adapter。没有此字段的实例后续新节点仍使用协议 8；已准备任务使用自身协议及冻结文本，不修改原件。协议 9 仅给 A 增加 `next_action="audit"`，对象沿用 `candidate_recommendation`，不增加科学机械表单。

A 的科学输出先正常封存。控制层只对一个已选择候选准备原件，复用 `delivery.freeze_sources(..., candidate_id=...)` 及隔离 transport；调用只有 audit 阶段，没有 promote、submit 或 confirm。截止沿原 `submit_seconds`，准备与调用耗时都计原 active-time；一次接受占一个原执行名额，准入保留既有交付预留。后续 A 仍须独立通过准入；预算不足可能直接进入 closeout 或只导出，审计不保证必有下一次模型评审。用量仍是 `turn.completed` 的观测口径，不保证账单零超额。

`native-evidence/NNN/candidate-audit/` 保存节点附属 intent、sources、binding、process、adapter-result 和 outcome；没有新的余额、候选表或 mutable current 指针。A job/raw/seal 和候选 model/source/harness 原件绑定通过原校验核对。已接受但缺终态、清理未知不重发并阻止继续派发及预算修订；已证实清理的失败、超时或不可用给下一 A 有界诊断。

下一 A 冻结原 outcome 的路径及 digest，但科学输入只展示候选 ID、状态、短 note 及 scope。`audited` 表示该 adapter 所声明检查通过；通用核心不据此猜 `leakage_flag=false`、目标代表性、总体模型合格或外部提交成功。缺候选/null 请求保科学并返回 unavailable；缺来源不按分数或文件名补造资格。

审计请求是延期判断，不算最终推荐，也不消费纠偏的科学轮次或 ack。审计 receipt 不是新的科学 raw 贡献证据；下一 A 仍针对原 W/H/E 工作判断，可 null、保留或修改推荐。正常交付仍走原 closeout 权威与审计/提交/确认链。

## 退出条件

- 实际隔离 adapter 审计后回 A；真实目标、hidden、控制目录不可访问；不会 promote。
- 原件失配硬拒；unknown 不重放；pause、总额度及预留继续有效。
- 旧 8 schema/job 字节保留；默认全池 source resolver 与单候选过滤均回归。
- 开发门禁、安装 CLI 及独立审查结果由父代理归档；本稿不宣称真实模型或科学选择效果已经验证。

开发与安装验收见 [T4 审计验收](ROOTLESS_T4_CANDIDATE_AUDIT_ACCEPTANCE_20261012.zh-CN.md)；科学效果仍待独立真实场验证。
