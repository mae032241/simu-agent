# T4 单候选审计闭环最终独立审查（2026-10-12）

结论：**最终 PASS，源码与受测安装范围无剩余阻断**。公开动作指导/开发回放已独审并作为第一节点提交 `7be935b`；本报告审第二节点的候选audit闭环、audit延期投影、实际调用消费者及必要fixture修复。本人仅只读源码/证据并写本报告，0测试/模型/build/原件恢复/预算变更；未实施被审代码。

## 路径与权责

- 显式新prepare/CLI candidate_audit_policy={version:1}才启科学protocol9，A仅增加audit enum，复用候选ID选择，不增path/hash字段。无marker未来job仍8，retained仍自身协议/literal；native实际next_action_options也按job protocol。旧schema8不隐式改字节。
- A先正常科学seal，再保存节点附属intent/sources/binding/process/adapter-result/outcome。来源单candidatefilter复用已封存observer/raw/seal与model/source/harness archive，旧默认全池入口保持；没有第二账本、余额、候选chooser或current指针。
- audit_only显式复用delivery transport，只audit phase，不走promote/submit/confirm，不创建closeout_begin。真实隔离通道未挂target/hidden/control；audited仅adapter-scoped qualification，通用核心不制造leakage=false或目标效果。
- nextA冻结原outcome ref/digest，通过science_view/public_receipt→_outcome→intent/binding/source/result核验。模型只看ID/status/短note/scope，不承担控制链维护。普通无/未知候选、不具来源或审计不可用保科学，返回有界诊断；完整性失配仍硬拒。
- audit_request hostflag是延期判断，既不清旧推荐也不当当前/最终推荐；只有非audit A的null清current。N4延期不计eligible科学轮次、不消费ack；返回A的progress proof追回原真实W/H/E raw，而非把audit receipt/A新prose当新科学信用。
- 审计占原usedsteps一个名额，sources准备+调用时间归原active与动作deadline；global observedtokens/unknown/pause/reserve仍保护。unknown无outcome或cleanup未知不重发、不paused退款、不amend；已确认本地结束的失败/不可用可提供诊断。下一A仍独立准入，预算不足时原closeout/export，不承诺必有模型评审。
- closeout audit仍验证原begin seq/SHA、sourcecutoff、冻结delivery_sources；随后A沿同prefix/source继续，可进入原最终交付审计/submit/confirm。没有因临时audit把actual/confirmed提前写成功。

## 关闭的发现

1. 早审closeout路由已支持audit、intent校验却拒所有purpose：已允许且核精确closeout边界，真实A3audit→A4→原deliveryconfirmed补正例。
2. 已sealed/late audit只看userpause，未核N4publishedpause：freshaccept现在同writer区间核correction.gate，真实持久pause阻新audit；保已接受science，exactack后audit仍不消费permit，下一eligibleA才消费/再pause。
3. 节点附属receipt只status/SHA自报不够：现在canonicaloperation、actioncap、finiteanchor、原A候选/accepted==intent存在、binding/result op/candidate/artifact、process原SHA/shape、无effect只能unavailable、audited必有exactbinding/process。不同来源/单字段篡改拒绝。
4. 首audit未知amend负例期待ValueError，真实RuntimeError正确阻未知：仅改fixture预期，不软化生产。
5. 全子包暴露旧fake-native读取science-task.search：改为从当前lineage.indexes.mechanisms正规页读取ref，HWA completed3、315token/cache、三seal验证、restart/read-only全hash、unknown不重放与tamper原断言保留，未降低测试。

## 独立亲阅验证

- 首四文件 `.trial/t4-candidate-audit-source-20261012`：46pass/1fixturefail/2skip；失败上述异常类型预期，不当绿灯。
- 全research_loop `.trial/t4-audit-regression-20261012`：495passed/5fixturefailed/2skipped，179.52s；五项都是旧科学view槽KeyError，原stderr与全失败日志保留。
- `.trial/t4-native-fixture-fixed-20261012`：10passed，4.48s；`.trial/t4-audit-boundaries-final-20261012`：13passed，22.74s。后者包含实际原sealedscience/真实N4project+publish+ack、原prefix closeout与实际隔离audit/最终交付；mock只科学native transport，不mock审计/gate/科学封存。后续两boundary仅test变化，production与已测wheel完全一致。
- 当前不同用例合并 **501passed/2skipped**，不是一次全绿；两skip为已有原publicharness显式optin，本轮fake-harness实际bwrap不冒充新真实cov资格。没有扩大旧MCP/TCAD全平台矩阵。
- freshwheel实际CLI `.trial/t4-choice-audit-installed-20261012/artifacts/result/result.json` PASS/0model_requests；H1W2A3auditA4wait四封存、一次audit、usedsteps5；nextA绑定scope/原候选，noactualsubmission变更、no closeout_begin、重run不重审，status只读。
- 本人逐字读取 **20模块 source/wheel/sitepackages精确一致**；wheelSHA `5f392e22a5442b1752229a953c13846ff004c500e92ed920e5d92eb7556a7bc3`，installedresultSHA `dfb695d68d605ad91e2bd617dd1517c46be7b9c38df4b042999996fd00e6ee07`。
- 本人比较原实际A8schema文件与实际A9schema：移除唯一新增audit enum后按原indent2/UTF8/newline序列化，**字节一致**。默认无marker8与retained旧job回归也通过；没有科学9隐式升级旧实例。
- 父验收记录 ROOTLESS_T4_CANDIDATE_AUDIT_ACCEPTANCE_20261012.zh-CN.md 与设计 ROOTLESS_CANDIDATE_AUDIT_DESIGN_20261012.zh-CN.md 已读，distinct计数/skip/隔离fake范围与当前证据相符。

## 限制

不证明实际Codex会合理使用audit或提高隐藏评分、科学选择质量；未新跑HWA/cov/隐藏评分，未修改此前失败T5。adapter检查通过不等target支持/审计全部域资格/外部提交。指导与92公开池回放没有新选择/reward，不是历史A决策模拟或独立科学收益验证。后续真实运行需单独授权和新冻结实例。

## 精确最终源码及必要回归 SHA256

- `src/scidiscovery/research_loop/candidate_audit.py`: `1f857068438c5f20b8617e10de086eff7dd5160a671c687f88d5a615a07bc49b`
- `src/scidiscovery/research_loop/budget.py`: `7b4d44bd2690142d9c6a4f6defed7f4fd280a0484cc9fff70a64d10ab3d24631`
- `src/scidiscovery/research_loop/contracts.py`: `46db608aa6e925bb41934c789d549a7237eccc03443aebe287ccb0b27a293c26`
- `src/scidiscovery/research_loop/controller.py`: `4f792186511585ca6a0fbb9e0722b460eabc35fad93129dd4692003e28173878`
- `src/scidiscovery/research_loop/correction.py`: `0734fcbfe6d1dfd4133a1dbb653bd23a73d7e8adff2be3df7cf6d5c9f7ebc665`
- `src/scidiscovery/research_loop/delivery.py`: `f5593c88f5bfb62c75a38ba88d6b07dfaa6a965f61b30d5d46e6c047bedfbc57`
- `src/scidiscovery/research_loop/history.py`: `cf54aa6af8417d332fc2d6ee04da83fbef56bb9ddb9eedf0fd544f1ff12ae859`
- `src/scidiscovery/research_loop/native.py`: `71a41e94f804eeb472790bba2d6e4d7c1b72ad8d26f19c71fd53b40c8e4e1c5a`
- `src/scidiscovery/research_loop/search.py`: `1f566286295fcc23bf5b2e2e5de158e2d995a013fa3fdbd7adb1fa6c58499a1b`
- `src/scidiscovery/research_loop/selection.py`: `9298ca8948d514b730f17832383ca3f436f5b7b9ce590dd778da4fe9a2c639b3`
- `src/scidiscovery/research_loop/semantic.py`: `6c726c670999fa2e5531b648efe89894728ffc990eba50bf0de03f4585a4c5ca`
- `src/scidiscovery/research_loop/cli.py`: `ced93d00d7fdcff63fafdc50b882817e40397974a957526a1d4c3eac89be6464`
- `tests/research_loop/test_candidate_audit.py`: `20277cfb79b41c86ac47714466a823f956ef4c8e97382f4e184eaf956ef6a4da`
- `tests/research_loop/test_native_cli.py`: `19dace1b7349f619a46dce4fdbfc146d5ab97787958587f740fef9bb93e2c984`
- `tests/research_loop/test_selection.py`: `bacc25d4aeec8e27bc8543f01ea9c2376b1421cedee14df869b2850d9706f4fb`
