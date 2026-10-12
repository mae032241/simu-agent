# 审计回执跨科学节点传递独立审查（2026-10-12）

状态：**独立审查 PASS，无剩余阻断**。审查者仅只读检查并写本报告，未运行测试、构建、模型或提交，未修改运行场。

## 问题与修复边界

真实场中 run-2 的 A003 审计仍绑定 W002 同一归档模型，但回执只交给紧邻 A004；跨 H/W 后候选投影又显示 unknown。A007 保守处理正确，A009 后续再次请求该审计，表明机械事实缺失会重复付成本。

新 job 的 `audit_projection_version=1` 从已验证来源任务的冻结 ref 和本次紧邻 ref 收集回执，并校验原 outcome、binding、process 和适用对象。模型原件的匹配/不同/未知单列；公开 `adapter_audits` 不从科学正文继承资格，不从 nonleaking note 制造 leakage=false，也不授权目标判断或交付。小公开页只含候选、adapter 结果、对象匹配及范围；不投递私有哈希链或模型附件。

brief 仍最多 4096 字节，有省略计数和只读分页入口。新投影不吸取未冻结后到事实；历史验证从任务既有 sources/refs 重建并检查页 SHA，损坏拒绝。旧 retained 无标记保持原投影，科学 schema、执行预算及审计执行接口未改。

初审发现 closeout 历史 ref 错误要求 audit 节点也在当前 extra_steps：prefix2→A3 audit→A4→A5 时 sources 合法为 `[1,2,4]`。已改为由已封存 A4 的冻结 ref 锚定原回执，不扩大祖先继承；当前紧邻 ref 仍必须属于 exact prefix。新增 A5 构建/验证及回执损坏负例覆盖该边界。

## 证据

- 第二冻结 `/tmp/scid-audit-handoff-freeze-20261012/manifest-02.json`，SHA `6e7495b63b6065dfdd577a4b5cd468e8c60ff163816d5434ea982513606c3397`，四源码及测试文件五项 SHA 已逐项核对。
- 首组 `.trial/audit-handoff-fix-20261012/batch-001/pytest.log` 为 83 passed / 7 failed；七失败共同来自新 fixture 的 runs namespace 别名与真实 fake stdout 不符，未进入审计成功后的投影断言。修正为明确同源别名，未放宽原件门槛；不将首组表述为最终通过。
- `.trial/audit-handoff-fixed-20261012/batch-001/pytest.log`：新九场景 9 passed / 50.80 秒，已亲读；覆盖跨 H/W、adjacent 首 A、对象不同/未知、note 不生成泄漏事实、旧协议9 retained 字节、原 outcome/公开页损坏拒绝以及 closeout `[1,2,4]` 来源边界。首组 83 个既有通过与九场景不是同一次最终全量结果。
- 最终安装 CLI `.trial/macro-role-installed-20261012/artifacts-audit-handoff/result/result.json` 为 PASS，0 model requests，H/A/W/A 四节点封存且重启不重放；它是宏观角色路由回归，不冒称测到了跨节点审计。已逐项核其 `module-bindings.json` 的 20 个源码 SHA 与当前一致，wheel SHA `22186e39b80b78254e9b855da97009b171dcf44cfe270505a1f2acb5787442bf`。
- 同安装包隔离导入下的专属九场景：`artifacts-audit-handoff/audit-installed.log` 为 9 passed / 50.39 秒，已亲读；`audit-installed-result.json` 明确绑定该 venv 的 site-packages/candidate_audit.py，returncode=0、model_requests=0。

本轮投影修复不证明科学目标收益或模型必读回执；当前真实场与其冻结安装包保持不变。
