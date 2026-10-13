# 跨分支机会成本复议独立审查

状态：最终独立审查 PASS，无剩余阻断。没有真实模型或科学改善资格结论。

## 范围与结论

只读核对 `/tmp/scid-opportunity-source-final.json` 的七个生产模块、旧组合复议测试及新机会成本测试，九项实物 SHA 全匹配。审查者只新增此报告，未修改实现、运行测试/构建/模型或读取更多隐藏候选评分。

- 新显式 portfolio 策略默认 version2，选择协议12；已冻结 settings 缺 version 仍按协议11/v1。v1 schema、视图和 DEFAULT literal 保持，retained job 取自身冻结字段。
- v2 复用原 W+A 周期与 pending/deferred 延期计数。P/Q/R 轮换不能清掉 S 的延期；下一步选逾期机制可直接继续，即便另有逾期机制，否则 A continue_w 需科学取舍短文。说明后可以保留任一合法方向，控制层不排名、不判断理由充分性、不强制所有机制实验。
- audit/E/wait 不刷新窗口，返回 A 只消费原 W 一次；作者补正沿原 root/已消费身份，有限复议不多计 W，之后可再次到期。H 改名和省略不抹已承诺身份及延期。
- 新 schema/view 已明确仅 **A continue_w** 门控。A revise_h、H experiment 保持科学权限；本版不承诺防止所有 A→H→W 绕行。没有新账本、搜索器、科研硬时限或机制排名。
- 新 canonical 默认指导由 prepare 冻结为 OPPORTUNITY；旧 DEFAULT 不改，任意自定义指导不重写。H 科学排序与机会成本、W 短步判别/及时交负结果保留原约束、必要核验与数量要求。新四角色1843字节及域增补空间由测试检查，schema/view 对自定义指导仍明确门控。
- lineage 复用4096字节总上限、最多四项概览及完整只读索引。已完成计数与 pending 预计延期分栏，不能把尚未评估的 W 当完成。

## 证据与待补范围

逐条读取新测试：真实 controller 原 A 封存→作者 A 复议→仍选 R→下个窗口再次到期；实际 audit/E 返回与重启不重计；H 改名后延期保留；多逾期项可选、科学 waiver；实际 science-task 与 view 等值/原页损坏拒绝；旧11原件字节及未来任务保留；新 literal 与域增补、自定义指导冻结。

父代理报告旧组118项通过（43.76s）。已亲读新组首轮日志 `.trial/opportunity-new-20261013/batch-001/pytest.log`：30项通过、1个 fixture 失败，原因是要求4条 overview 全部装进总4096字节；实际合法裁为3条，其中包含逾期 S。修正版只改测试，保留 `0<len<=4`、`len+omitted=4`、逾期 S 可见、已完成/预计延期、完整四机制只读页及篡改拒绝断言。最终测试 SHA 为 `ca394d1959acfb8f2e3b8096614a308c486e72b0aa6e105f8096fd0866730289`，实物已核，生产源码未变。该裁剪是显式有导航的 excerpt 省略，不是删除机制。

已亲读精准复验 `.trial/opportunity-brief-fix-20261013/batch-001/pytest.log`：1项通过，0.87s。源码分批覆盖118项既有及12项新增，共130个不同用例；不将首轮部分通过说成一次全绿。

最终安装证据位于外层 `.trial/macro-role-installed-20261012/artifacts-opportunity-final-20261013/`：

- `opportunity-installed.log` 实际41项通过，21.76s；`opportunity-installed-result.json` 确认九个相关模块来自最终 venv 的 site-packages，SHA 与当前源一致，模型请求0。
- `result/result.json` 确认实际安装 CLI 的默认 H→A→W→A 及重启无重放；`result/module-bindings.json` 的22模块当前源 SHA 全匹配。最终 wheel SHA 为 `be3e0cc8581902416bf484c3bc68a8577d1120a3f64fe06d2f0888dbca40caea`。
- 实际新 CLI `cli-instance/settings.json` 冻结 `portfolio_policy={review_after_cycles:3,version:2}`，`jobs/001.json` 为协议12。最终九项冻结与当前实物全匹配。

以上 fake-native 工程验收不证明新排序、短步搜索、取舍说明的科研效果，也不授予未验证的原生续接能力。

上一场真实记录 [ROOTLESS_PORTFOLIO_LIVE_20261013.zh-CN.md](ROOTLESS_PORTFOLIO_LIVE_20261013.zh-CN.md) 与此前独立核查一致：三 W 分别覆盖 m1/m2/m4，m3 未执行，组合强制触发未观测；预算内确认 run2 不等于科学任务完成。该场终态后评分仅是外部诊断，未用于本轮控制规则或角色排序。
