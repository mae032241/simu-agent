# T4 单候选审计闭环独立审查（2026-10-12）

结论：**PASS，源码与受测安装范围没有剩余阻断**。公开动作指导/开发回放已独审并提交 `7be935b`；本报告审后续audit闭环。本人未实施被审代码、未运行测试/模型/build、未改失败T5或预算；仅独立读取源码和父级原证据。

## 已核边界

- 新实例显式candidate_audit_policy才启protocol9；无marker未来job仍8，retained取自身协议/literal。9只加A audit enum，不添机械path/hash字段；native菜单按job协议。亲比实际A8 schema与A9移除新增audit enum后原序列化，字节一致。
- A先科学seal，控制层单candidatefilter绑定原job/raw/seal/model/source/harness。节点附属不可变facts复用原预算/transport，无第二账本或chooser；audit只scratch单phase，不promote/提前confirmed。回下一A只给ID/status/note/scope，完整receipt沿science_view/_validate_inputs逐源核验。
- audit_request延期不清上一推荐、不算N4科学轮次、不消耗ack。下一A的proof仍指原W/H/E raw，不把宿主审计当新科学信用。audit占一个usedstep；active/time/token/reserve/pause/unknown原guard保留，下一A另过准入，不续额或承诺必能评审。
- closeout audit核同begin/sourcecutoff/delivery_sources，再回A和原交付链。unavailable保科学，完整性错误硬拒；unknown无outcome/cleanup不明不重发或amend。

## 发现已关闭

closeout audit被purpose校验误拒、freshaudit遗漏published N4 pause、receipt/intent自报校验不足均已修复。现在canonicaloperation/cap/finiteanchor、accepted/candidate、binding/result对象、process原SHA与audited资格交叉核；真实closeout与N4 pause/ack回归通过。

首fixture异常类型预期错误及旧native fixture读取已移除search槽只改测试：使用正式lineage机制页，HWA/seal/cache/restart/read-only/unknown/tamper强断言未降。

## 独立亲阅证据

详细结果与失败保留见 [父级验收记录](ROOTLESS_T4_CANDIDATE_AUDIT_ACCEPTANCE_20261012.zh-CN.md)、[设计](ROOTLESS_CANDIDATE_AUDIT_DESIGN_20261012.zh-CN.md)。

- 全子包首轮495pass/5fixturefail/2skip；native文件复验10pass/4.48s；最终真实边界13pass/22.74s。合并distinct **501pass/2skip**，不宣一次全绿；两skip为原publicharness optin。
- 最终真实N4 publishedpause拒lateaudit、exactack后audit不耗permit、下一eligibleA才消费/再pause；closeout A3audit→A4收到同source/prefix→原delivery_confirmed且restart不增调用。mock仅科学transport，audit/gate/封存真实。
- 外层 `.trial/t4-choice-audit-installed-20261012/artifacts/result/result.json`：fresh installedCLI H1W2A3auditA4wait、四seal/一次audit/usedsteps5；实际bwrap确定性harness验证target/hidden/control不挂载、无提交/no closeout_begin、重run不重审，0model。
- 亲核对应 `module-bindings.json` **20模块 source/wheel/sitepackages逐字一致**。wheel SHA `5f392e22a5442b1752229a953c13846ff004c500e92ed920e5d92eb7556a7bc3`；result SHA `dfb695d68d605ad91e2bd617dd1517c46be7b9c38df4b042999996fd00e6ee07`。最终两boundary只改test，生产仍同受测wheel。

## 限定

adapter-scoped audited不等target效果或提交；通用核心不制造leakage=false。fake native/bwrap与92公开开发回放不证明实际Codex行为、隐藏分提升或科学选择质量。本节点无新HWA/cov/隐藏评分，后续真实运行须单独授权与新冻结实例。
