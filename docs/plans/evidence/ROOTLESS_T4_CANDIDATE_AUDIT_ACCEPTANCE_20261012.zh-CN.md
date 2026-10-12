# T4 选择前审计验收（2026-10-12）

范围：dev / f4f51f9 起的 T4 补齐；公开选择规则节点已提交 `7be935b`。本节点只增加 A 请求单候选审计、控制层绑定并执行、下一 A 读回执的路径。没有新付费模型、cov 场次、隐藏评分或历史耗时门禁。

## 行为与边界

- 新实例显式 `prepare --enable-candidate-audit`，需要冻结的隔离 delivery adapter；旧实例、已准备的 job 和科学原件不升级。协议 9 增加 A 的 audit 动作，复用候选选择字段，无机械引用填表。
- 请求先封存科学结论，控制层保存节点附属执行事实并核对候选原件。只运行隔离 audit，不 promote；回执只说明适配器检查的范围，不证明目标效果。
- 审计请求不替换/清空上一推荐，不算科学进展或无进展周期，不消耗纠偏确认。下一 A 才作科学决定；原最终交付审计、提交、确认仍保留。
- 用户暂停、科学暂停、原总预算、收口预留和未知执行阻断均有效。审计独占一个执行名额；后续 A 另过准入，不能保证不足预算仍能启动模型。已接受无终态或清理未知不重放，不自动续额。
- 收口 A 也可请求审计，但仍绑定同一冻结前缀/来源；审计后可正常进入既有交付。无来源或不可用保持科学结论并报告缺口；完整性失配硬拒。

## 父代理执行证据

所有测试/构建在共享串行锁内执行；独立作者和审查者未运行模型或测试。

| 门禁 | 结果 | 证据（外层 .trial） |
|---|---|---|
| 首审计/交付/schema/closeout 定向 | 46 通过、1 失败、2 跳过；失败为 fixture 期待 ValueError，生产正确抛 RuntimeError 阻止未知执行续额 | t4-candidate-audit-source-20261012 |
| 选择规则/选择投影 | 44 通过 / 0.14s | t4-public-actions-tests-20261012 |
| 研究循环整个子包 | 495 通过、5 失败、2 跳过 / 179.52s | t4-audit-regression-20261012 |
| 旧 native CLI fixture 修复复验 | 10 通过 / 4.48s | t4-native-fixture-fixed-20261012 |
| 最终审计边界 | 13 通过 / 22.74s | t4-audit-boundaries-final-20261012 |
| 新 wheel + 独立 venv + 安装 CLI | PASS；实际隔离进程，四节点封存、一次审计、五个总名额 | t4-choice-audit-installed-20261012/artifacts |

子包的五个失败均由同一旧 fixture 访问已移除的 `science-task.search` 导致，A 子进程 KeyError；原日志留在 `t4-native-fixture-diagnosis-20261012/instance/native-evidence/003/native.stderr`。只改 fixture 通过当前 `lineage.indexes.mechanisms` 读取正式分页；未降低完整性、未知重放、恢复、状态只读或封存断言。生产行为未为测试退让。

按最终测试集合去重为 **501 项通过、2 项跳过**；这是子包门禁加受影响文件复验的合并证据，**不是一次全绿运行**。跳过项为需额外原始公开 harness 配置的两个已有 opt-in 测试；不是实际 Codex 或真实 cov 验收。

安装验证执行 H1→W2→A3 audit→A4 wait；核对新包所有 research_loop 模块的 source/wheel/site-packages 字节相等。实际 bwrap 中运行确定性公开 harness，断言目标目录、控制目录和隐藏材料不可访问。审计后正式提交未变、无 closeout_begin，重复 run 不再执行审计；status 只读。测试使用假原生进程，不调用模型。

安装 wheel SHA256：`5f392e22a5442b1752229a953c13846ff004c500e92ed920e5d92eb7556a7bc3`。

真实收口回归另验证 A3 audit→A4 finish→原 submit/confirm，审计完成、A4 决策前目标仍为空；重复恢复不增加调用。真实纠偏回归验证持久化暂停阻断 late audit，明确 ack 后 audit 不耗科学名额，下一科学 A 才消费该确认。

独立审查发现的 closeout 身份校验与科学暂停遗漏已在本轮修复并补真实回归。最终独立审查 PASS；报告随本节点提交。本文件不把开发回放或假原生进程等同科学效果。

## 未验证与下一步

- 92 个公开候选回放为规则/信息缺口检查：0 新选择、0 reward、0 模型请求；不证明选择质量提高。
- 没有新真实 HWA 场；没有证明模型会合理使用 audit 或选出更高隐藏分候选。T5 科学效果仍未完成。
- 未跑旧 MCP/TCAD 全仓库矩阵；本变更在新的 research_loop、开发脚本及其文档，旧插件入口未改。适配器资格仅限实际验证过的隔离通道。
- 后续真实运行须使用新授权与新冻结实例；不修改此前失败 T5 原件，也不重用其预算。
