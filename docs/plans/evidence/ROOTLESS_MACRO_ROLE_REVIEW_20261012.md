# A 宏观决策与 W 自适应执行职责独立审查（2026-10-12）

结论：**PASS，无剩余阻断**。基线 `8fde8a6`；审查者仅只读复核并写本报告，未运行测试、构建、模型或提交。

## 范围与结论

复核 `guidance.py`、`controller.py`、`contracts.py`、`native.py`、专属回归与说明。新 prepare 冻结 `handoff_authority_version=1`，新任务冻结自己的 native 角色文字；旧 retained 无标记时不补字段，保留原任务投影和 native 提示。

普通直接 A→W/H 仅在原指令精确等于该 A 的 `route_reason` 时生成来源明确的决策背景。原路由、科学原文和 instruction 不改；宏观方向/证据缺口保留，方法配方不自动成为用户或 H 的新边界。用户原文、H 范围与判别预承诺仍有效。不同 host 指令、E 请求/返回、作者补正、N4 纠偏和 closeout 不经此替换。controller 路由、科学 schema、预算及原件规则未修改；不增加关键词门禁、状态机或模型表单。

新指引保留 H 请求 E/experiment/analyze、A 全局判断与机制回 H、W 机制内搜索并回 A 的职责。实际 raw launcher 的 developer instruction 与 stdin prompt 都读取同一任务冻结文字；新结束提示不再要求一个结果即结束或把 W 验证全交 A。全角色指引 1829 字节，保留 2048 字节上限。

## 发现关闭与证据

- 初审发现 decision_context 在 `correction_request` 写入之前计算，会与封存重算不一致；已移至请求绑定/校验之后，真实 N4 revise_h→H 请求封存回归通过。
- 精确来源 guard 避免不同 host 指令被误标成 A 方法建议。最初负控构造 step4 时 step3 尚未封存，日志为 90 passed / 1 fixture failed；改为独立参数的同一 A2→H3 后，确实覆盖该 guard，未放宽完整性断言。
- `.trial/macro-role-regression-20261012/batch-001/pytest.log`：215 passed / 141.08 秒；`.trial/macro-role-authority-fixed-20261012/batch-001/pytest.log`：6 passed / 1.76 秒。合计 221 个不同用例通过，不宣称单次全绿。
- 最终独立安装 `.trial/macro-role-installed-20261012/artifacts-final/result/result.json` 为 PASS，0 model requests。实际 CLI H→A→W→A 四节点封存；148 场景建议原文仍可读，W question 呈机制内决策问题，用户规则保留，重启不重放。已独立核对该目录 `module-bindings.json` 的 20 个源码 SHA 全部匹配；wheel SHA `352d5eab62c17ad245cde46d204787707067b83ccb6c7788f5f47138f245c545`。

## 未验证范围

无模型夹具证明上下文与恢复接缝，不证明真实作者遵循、搜索效率或目标质量改善。本轮未恢复真实场；新提示不是科学语义执行器。真实问题与验收口径见 [修订记录](ROOTLESS_MACRO_ROLE_FIX_20261012.zh-CN.md)。
