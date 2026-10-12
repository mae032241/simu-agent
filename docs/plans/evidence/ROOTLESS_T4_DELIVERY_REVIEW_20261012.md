# T4 后 delivery 原件接缝独立审查（2026-10-12）

结论：**PASS，范围内无剩余源码或受测安装阻断**。基线 `dfd7176`；只审其上 delivery/cov_delivery/test_cov_delivery_lineage、T5 外部脚本映射修复。本人未实现本次代码，未运行测试/模型/实验，未改原科学实例；独立读取了源码、父级门禁、原安装产物与真实公开验收输出。

## 原件、资格与恢复边界

- core先走 history._source：job/raw/seal/observer/archive绑定均保留原完整性核验。候选仅获得该封存 observer 的 exact execution context与archived proof切片，按SHA去重、字节/时间额度复用；通用 core不懂cov文件名、不扫描当前call或最近目录，不另建ledger/budget/资格。
- resolver 仅获得 /inputs/execution/SHA blob，返回 proof_label只能取该candidate已授权的archive；不能读取whole host-history、私有根或sitepackages来补链。source/model复制后仍重核SHA/size，原件篡改在原消费边界拒绝。
- cov leaf需唯一 known_success、同candidate/run、唯一source.py/model.pkl/row.json；context.model与proof一致，冻结同调用row对比sealed ledger的run/ok/model/script/val事实。选择P不因W后来覆盖train.py/model_runN/currentcall而审Q。模型/代码来自同call，关系声明不授公开audit资格。
- v2缺/多/unknown/unretained返回来源unavailable，不按null/旧语义fallback；archive失配不被 SourceUnavailable 路径吞成合格。v1无contexts仍旧current-source snapshot，明确不能保证历史代码版本；旧settings/job/source-envelope不改写。
- 来源只标audit_pending。原公共harness隔离audit完整且无leakage后才promote，持久intent+confirm仍沿N6b同operation恢复规则；本补丁未新增提交重试或科学裁判。
- T5实际alias修复为launcher的绝对instance/runs；误配/别prefix无法取另一候选。scid_python启动adapter，task_python执行audit，叶不依赖scid包。

## 独立亲阅证据

1. `.trial/t4-delivery-source-20261012-01/batch-001/pytest.log`：**33 passed, 2 skipped in 11.73s**，三个 owningfiles。skip是原publicharness显式optin，未当通过；源码门禁returncode0、cleanup_complete=true。专属8例包含覆写当前script/model/call后仍Parchive、alias错配、archive hash硬拒、v2四种未解不可fallback、v1限制兼容。
2. `.trial/t5-candidate-installed-20261012/artifacts/result/result.json`：freshwheel/installedCLI PASS、0model_requests；resultSHA `b88d8794ab73f648aa76a909a7b65a22cf8c15fef38b305af0c4a623017f3d98`。本人按字节核**19模块 source/wheel/installed一致**，wheelSHA `224c76eef9cd84615c16473d23bf3db65edc181b0970ee26a1c00387dd65fc29`。
3. `.trial/t5-delivery-gate-20261012/result-02/result.json`：**2原公共exp、0LLM、真实bwrap+taskpython publicaudit/promote/confirm PASS**，结果SHA `0feece9b842de18df3be5ebbd7fa47c2818e6c0ad406974a4d5891748580068d`。
4. 本人读取实际closeout A004的delivery_sources：科学选择run-1；source archivedSHA `efc1d3166b8db32a9a74d868bbb572261371978d7bee6f72f1b564e770100ca6`，确含原train而当前同名script为明确raise RuntimeError，二者字节不同。selected model archiveSHA `9230285f317b00557d6d956d66413ef934a4f0737a1daa0d542cb4b229480b8c` 与最终submission/model.pkl逐字节相同。原submitted receipt run_id1/leakage=false，controller交付confirmed且goal_completion=not_asserted；没有把交付成功当科研目标达成。
5. publicgate result-01因驱动漏all-rolepolicy在prepare拒，0模型/0run；修driver后result-02，不改生产；失败证据保留，不记成功。
6. 父追加 exact-delivery-proof.json SHA `ccafb548a91bc6888fdecbbbacb02385772dc7a9e4d356dffeeab9a49fd298da` 已亲阅，来源action000005，与本人前述独立source/model逐字核验一致。
7. T5prepare07497a09…486f的recognized models_called/model_requests计数强int零与alias修改已经独审。run_case保持5ac8b493…011a one-shot/无retry-amend-ack-resume。完整脚本静态报告 `/tmp/scid-t5-script-review-20261012.md`，实际T5尚未准备/启动。

## 限制

- fake模型transport与constant-zero公开训练用于工程资格，未调用科研模型、不读隐藏评分，不证明实际Codex权限/科学选择收益/最终目标质量。
- trusted frozen adapter与已封存SHA仍是边界；不追求恶意整组原件+封存同时重写的另套认证系统。
- v1 historical source能力仍受限；新v2 unavailable诚实保留，不能伪audit通过。
- T5启动仍需reviewedcommittedHEAD、最终wheel/install/namespace证据与脚本资格精确冻结；本报告不授新的模型预算或nativecontinuation资格。

## 精确冻结

- `src/scidiscovery/research_loop/delivery.py`: `2a347b42b632e3c66ac298bbcf962800513495e0841e62ec8fa24e7c9d1e4f66`
- `src/scidiscovery/research_loop/cov_delivery.py`: `14191a59dba8cf675191f60e55bda9e106ff09de9aca5a7f98e1359f2ebc2be2`
- `tests/research_loop/test_cov_delivery_lineage.py`: `104dca22d28ecd5fd53a6afd8d824e7f108473442fe6b5c2f27bd7a2bdc77e67`
- `source-freeze.json`: `feff360cdb20ea3e605c29d0b0309d6af9b3bbf161489a11b17fe5db6d71c247`
- `docs/plans/evidence/ROOTLESS_T4_DELIVERY_INTEGRATION_20261012.zh-CN.md`: `59f5dc4283380027ab1dfa14428ae592c09694ea6ed26c77434cf888b406cc72`（最新父级结果段已核，原待执行句只是尚待状态同步）
