# 收口探索解释一致性修复（2026-10-14）

## 范围与根因

基线 `d5462f9`，仅修改 `search.py`、`semantic.py` 与专属回归。
真实场 `.trial/rootless-receipt-cov-20261014c/instance` 的 A012 已封存；
封存将 closeout 视为非探索决策，focus/allocation 为 null，历史重建却按普通 A
解释并继承 h001.m1/screen，导致 `Scientific intent differs from its sealed interpretation`。

## 修复

统一由 search.interpret 表达 closeout 的中性语义。重建仍校验协议、诊断、
状态和封存 focus/allocation，验证通过后保留既有探索状态，不应用收口决策。
其他 selection/decision/portfolio 未解决状态也不清除原探索状态。
未改协议、探索额度、模型指引、预算或旧场原件。

## 验收

所有测试由父代理串行执行；没有调用真实模型。

- 新 wheel 安装及实际 CLI / fake-native 进程门禁 PASS。
- 当前协议专属回归：修复版 **10 passed (3.23s)**；基线已安装包同测试
  **4 failed / 6 passed (3.00s)**。四个行为失败即本次修复覆盖的错误。
- 覆盖真实 build_job / seal / validate、closeout A → unavailable 审计回执 →
  后续 closeout A、三类 unresolved 不改探索状态、五类封存篡改拒绝、普通 A
  仍可改变探索方向。审计夹具无候选，未执行真实评分或提交。
- 新安装包只读重建原场 step12/13：状态全等；原场 **5,546 文件**前后 SHA256
  全等。原场没有恢复执行。
- 补跑旧六文件（closeout、candidate_audit、semantic_recovery、search、
  scientific_intent、audit_handoff）：基线和修复版均 **53 failed / 49 passed**，
  旧协议夹具等债务仍在，不能宣称该组通过。本次没有批量迁移这些测试。
- 未跑全量测试、浏览器、TCAD 或新真实模型场；本验收不证明最终模型交付成功。

证据位于外层 `.trial/macro-role-installed-20261012/`：
`artifacts-closeout-search-01-20261014`（构建/CLI/原场只读回放）、
`artifacts-closeout-search-finaltests-20261014`（新回归）、
`artifacts-closeout-search-finalbaseline-20261014`（旧版负控）、
`artifacts-closeout-search-baseline-20261014`（既有组基线对照）。

## 仍待独立处理

improve 仍被单次受管实验额度限制的吞吐问题，不属于本次收口一致性修复。
