# Cov delivery current-protocol guard 独立修复审查

状态：**PASS，限定 full01 guard 修复及真实隔离交付机械接缝**。最终三文件 SHA 均 MATCH；父代理源码门禁29 PASS/2 opt-in skip，fresh installed 门禁31 PASS、无 skip。独审读取实际运行日志、driver、安装模块与 wheel 字节核对绑定；未运行 tests/build/Git/模型，只修改本审查文件，未修改生产或旧真实场、未恢复执行。旧场 [整体未通过](U4_COV_FINAL_RESULT_REVIEW_20261014.md) 仍为最终结果，不因本修复改写。

## 最终冻结与最小生产语义

`/tmp/scid-u4-delivery-full-01.json` 三文件实际 SHA 全部 MATCH：

| 文件 | SHA256 |
| --- | --- |
| src/scidiscovery/research_loop/cov_delivery.py | `82e20e0741001024ab284ba3477097f2e7d5d5331f6fca0c93305458a908706d` |
| tests/research_loop/test_delivery.py | `a617e73caf8b443a0a9b64cf64af7c8ed229931002bc6c14cfcc5adf01307fde` |
| tests/research_loop/test_cov_delivery_isolation.py | `4e21297df8422b4a9b15bee48ff7844e9fdcf4b45b3f93bcac659aaa0be909d2` |

生产仅将 `_current_guard` 中 `_exact` 返回的 Path 转为有界读取的 bytes：exact 路径/stat 校验后 read(256001)，实际读取超过256000继续拒绝，SHA/长度校验使用 bytes。保留原冻结 protocol proof、scope current14 校验及实际 leaf 隔离；不删除 guard、不恢复旧协议兼容、不加第二状态或账本。原件经只读 inputs mount 传入隔离 leaf。

`test_delivery` helper 仅为现 A schema 补 decision_request=None、portfolio_review=None，封存通过现合同，不放宽生产 validation。stderr 未留存的现场诊断限制仍保留，本修复不扩大为全交付观测重构。

## 新门禁真实路径静态核对

- 正例用 managed archived originals，经原 delivery.freeze_sources/invoke 与原 `_call`，实际 `--isolate → bwrap → /delivery.py --leaf` 完成 resolve→audit→promote→confirm。test hook 只检查每 phase 的自动追加 protocol proof、staged bytes/SHA/size/current scope，随后委托原 transport；没有 fake leaf 回复。
- 验证 promotion 精确选择原 artifact SHA、两个 target artifact 一致，确认阶段不修改 target/settings；不凭成功 stdout 接受错误原件。
- 四 phase byte 篡改负控直接执行同冻结 isolating argv、捕获真实 stderr。typed 原件拒绝且无 TypeError，目标目录字节不变；missing-proof resolve 也必须由实际 leaf 拒绝。协议13/bool 的负控在 host isolating entry 拒绝，不冒称已进入 leaf。
- 负控 transport hook 仅用于捕获实际 CLI 的拒绝证据和向原调用返回 unavailable，不替代隔离执行。正例的 cleanup/phase sequencing 与四 phase 仍由生产原 transport 管理。

## 资格边界

最终门禁已实际执行上述 isolate 用例及既有 cov_delivery_lineage/delivery 回归，安装轮无 skip。本修复只授无模型的 resolver/audit/promotion/confirmation 机械接缝，不授真实模型科学效果、不可见目标评分、旧真实场重新提交或在线恢复资格。

## 最终运行证据与冻结核对

- [source01 日志](../../../../../.trial/u4-delivery-source-01-20261014/batch-001/pytest.log)：29 PASS、2 skip，22.33s。两个 skip 是未设置公开 harness/task Python 的原 opt-in audit 用例，不把源码 skip 当作这些路径已通过。
- [installed01 日志](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-delivery-01-20261014/u4-delivery.log)：31 PASS，25.94s，无 skip；包含新实际四 phase isolate 正/负例及原 cov_delivery_lineage/delivery 用例。父 driver 显式启用 SCID_DELIVERY_PUBLIC_HARNESS 与 SCID_DELIVERY_TASK_PYTHON，补足源码 opt-in 两用例；没有读取隐藏测试或评分原件。
- [installed 结果](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-delivery-01-20261014/u4-delivery-result.json)：returncode=0、model_requests=0；cov_delivery、delivery、protocol 均指向安装 site-packages。独审读取三安装文件，全部 SHA 与记录一致；cov_delivery 实际 SHA=`82e20e0741001024ab284ba3477097f2e7d5d5331f6fca0c93305458a908706d`，等于 final production。
- driver 使用 fresh venv Python `-I`，移除 PYTHONPATH/PYTHONHOME，逐模块检查实际安装路径与源码 SHA，然后调用准确三个 frozen gate 文件；正例继续委托原 transport，负控继续执行真实 CLI，不替换隔离 leaf 回复。
- [freshwheel 基础结果](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-delivery-01-20261014/result/result.json)：passed=true、model_requests=0、实际安装 CLI H→A→W→A、route_context_preserved=true、no_replay=true。独审实际 wheel SHA=`cecab497b3d52645ed4bdf94d3c170d68f9077876ff29d31d13326e275866e35`，与结果原件相同。

无剩余本修复生产阻断。生产资格只针对现最小差量及以上隔离验证；原场 stderr 遗失的诊断限制、未观察到真实 fragment continue、未探索机制和未完成旧场交付均继续保留，不因本次无模型门禁得到整体 U4 PASS。
