# Soft 目标准入修复独立审查（2026-10-12）

状态：独立审查 PASS，无剩余阻断。审查者仅只读检查并写本报告，未运行测试、模型、构建或提交。

## 源码结论

范围为 `budget.py`、`controller.py`、`candidate_audit.py` 及必要回归。soft 探索只保护一次 A 目标、inflight、清理和提交/确认；新节点与已知失败续接不再要求完整节点目标能够放入剩余额度。真正 Popen 前仍共用 `node_admission`，未知用量、冻结身份、累计消费、总额硬停止及名额检查保留。

收口 A 保留机械执行 floor 与正的科学余量；已准备但尚未接受的 A 不重复占用一个新名额。soft 收口 audit 保护本次审计时限、机械 floor、下一 A 和外部动作名额；普通探索 audit 仍保护一次完整收口预留。hard 及缺少 mode 的旧实例保留原全目标准入和三次 A 预留。

`budget-status.json` 的 purpose 分支与准入相同：普通工作扣最小收口预留，收口工作扣机械 floor，标明 `reserve_scope` 和扣除预留后的可用时间/观测 token 上界。提示仍是有界建议，不是权限或新预算。未新增账本、协议、科学表单或隐含恢复。

## 验证证据

- 首轮 `test_soft_admission.py`：4 passed。定向组 `.trial/soft-admission-focused-20261012/batch-001/pytest.log`：132 passed、1 failed，已亲读日志及源码。唯一失败是旧 accept 夹具仍要求整 A 目标：剩 40 秒、实际机械 floor 33 秒，soft 准入正确后，假 launcher 因缺少 science-output 才报错。负控移至剩 32 秒，保留原 typed 拒绝/无 intent/原 job 不变断言；最终 `test_closeout.py` 整文件 13 passed / 8.70 秒，日志 `.trial/soft-admission-floor-final-20261012/batch-001/pytest.log` 已核。合计 133 个不同用例通过，不宣称单次全绿。新增真实续接、prepared A 精确名额和 500 秒隔离收口审计均通过。
- 独立安装 CLI：外层 `.trial/soft-admission-installed-20261012/artifacts/result/result.json` 为 PASS，0 model requests。1906 秒总额度、900 秒 W 目标下 H/W/A/audit/返回 A 四节点封存，审计一次，used_steps=5；无提前收口、无提交变化、重启不重复审计。
- 安装 wheel SHA：`b59ea4aa156de322da31155ee2f1a1b49947f5c2e94363a3df699405e6790ad5`。已独立核对 `module-bindings.json` 的 20 个当前源码 SHA 全部一致。

最终三生产文件 SHA 分别为：budget `3303fad6d0052dfd517df19fd16108887bc9ab54e763b11576400817761d3f57`；controller `34b9e0209c4527fe3993b6be9157dea287e1395a14e1dedde94ee85e16a10b54`；candidate_audit `560d81745c981021cfdd3404fdef598343e3573da706076f23aa75ed2ae629d1`。最终夹具修正未改变生产源码，安装证据仍对应该源码。

## 边界

无模型夹具和安装验证不证明真实科学收益、模型必读提示或收口一定完成。soft 在途工作可以侵占建议预留；全局硬预算和未知执行仍按原规则处理。本轮未恢复或修改真实场。真实问题与后续验收口径见 [修复记录](ROOTLESS_SOFT_ADMISSION_FIX_20261012.zh-CN.md)。
