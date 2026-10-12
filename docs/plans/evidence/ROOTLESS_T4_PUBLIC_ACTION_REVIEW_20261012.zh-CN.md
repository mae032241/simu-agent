# T4 公开动作指导与开发回放独立审查（2026-10-12）

结论：**此拆分节点 PASS，无剩余范围内阻断**。只审短A guidance、development replay脚本/专属测试、九公开夹具及文档；protocol9审计生产闭环另行审查，本报告不批准尚未收口的审计执行接缝。本人0测试/模型/源代码修改。

- A指导总1888UTF8B≤2048，通用而条件化：是否支持目标、仅proxy或未知由A解释，不用关键词或阈值制造支持；弱proxy不强制换/淘汰，unbound/missing audit为unknown。若audit可用，candidate_recommendation明确为本次请求目标，不当最终选择；否则保资格缺口。旧jobliteral仍自身冻结，不改结果schema或实际提交权限。
- allowed_actions只是开发期约束/信息缺口建议，没有chooser/执行/author结论；targetrank固定unknown，automatic swap/eliminate false，unknown submit不许unchecked resubmit、科学继续仍须真实执行guards。不能把audited资格当target效果。
- 实际导出只从已冻结公开ledger及public-condition五字段，instance分组防run-ID碰撞，历史audit记录仅recorded_unbound，不授exact资格。显式隐藏输入被拒，混合manifest中的hidden/official_reward不进入whitelist投影；变更它们不影响输出。未重建历史decision-time prefix，synthetic probes不是旧A选择或新choice。
- 脚本SHA先校验才读pool；只metadata，不加载pickle/科学全文，不读取评分输出、不使用隐藏数值调规则，原件symlink/ledgerSHA/4MiB bound与metric finite检查保留。
- 亲阅 `.trial/t4-public-actions-tests-20261012/batch-001/pytest.log`：**44 passed in0.14s**（public_selection_replay与selection），result passed/returncode0/cleanup_completetrue。没有模型由本人执行。
- 亲阅 `.trial/t4-public-action-replay-20261012/pool-replay/report.json`及公开inputs/replay：**92候选=N5 50+live02 42**，0models/0choices/0rewards；所有精确publicaudit状态unknown，target_best null，input无显式hidden_score/test_score/official_reward。报告明确final snapshot开发回放，不是独立科学收益或历史A模拟。
- source-freeze SHA `67c6a0506a30dccf6b4bf0fed0263674a2d07f0e83701fd5e0b3a2c59db6cc47`五项与现源逐项匹配。首节点可独立提交；安装后的guidance绑定随审计闭环finalwheel核，未宣实际Codex会按指导执行。

## 精确五文件SHA256

- `src/scidiscovery/research_loop/guidance.py`: `829881a1dd7b627c85e06b988323e86da5f474d78ecbe71c5d4ea4d31d08dff0`
- `scripts/acceptance/rootless_public_selection_replay.py`: `bf36e7100772586340903075c66754064e829c725fb46e511652578a4365435d`
- `tests/research_loop/test_public_selection_replay.py`: `ba967d5fcaf30e6dc8c2a78a2faa615efb74c793ac78edd22f01cc61f629d66f`
- `docs/plans/fixtures/rootless-selection-actions-v1.json`: `ae76062e8ff41c72b0fcb54fe9845f04014fc50da198f2430b10fbf728850f8e`
- `docs/plans/ROOTLESS_T4_PUBLIC_ACTION_REPLAY.zh-CN.md`: `4d415b59dd64116ade48d43439fd69bc67014718658f3ce9cb936d59031845c0`
