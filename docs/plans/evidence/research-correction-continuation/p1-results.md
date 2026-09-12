# P1 工程交接（2026-09-08）

**当前状态：R3 包装增量已实现，P1 工程正负检查通过（94 passed）；等待独立实现复核。以下原交接和失败记录保留，最新结果见文末 R3 补充。**

冻结计划：`acc011a04ff2b6b0d7b7b2383f921c56faafe1e360cc53fdbe13f9bc1f01c93c`。只追加三份分配的生产文件和两份测试文件；没有 commit、solver、真实科学 MCP、wheel 或全套测试。相对接手时脏基线的增量见 `p1-implementation.patch`，精确文件摘要见 `p1-files.json`。

P1 修改已实现：review project 使用 prior_signal；任何 verdict 保持原件解析、参数 set/coverage、批准 key、report subject/capability/handoff 校验；case/value/unit 实现和 uncertainty readiness 仅对 pass 严格，author 完整检查不放宽。没有新增 helper、框架或状态。包装与 Effect 实现未改。

## 实际检查

- 基线命令：`python -m pytest -q tests/operations/test_l4_local_tcad.py::test_negative_deck_review_can_report_implementation_defects tests/operations/test_l4_local_tcad.py::test_deck_review_cannot_pass_the_same_implementation_defects tests/operations/test_l4_local_tcad.py::test_local_tcad_author_debug_and_independent_review_share_one_operation_path --tb=short`。退出 1，10 个预期失败、5 个对照通过，2.56s；见 `p1-baseline-pytest.txt`。负面 case/value/unit/uncertainty 各 revise/blocked 失败；blocked author 项目在 Root review preflight 的 project 端口被 input_scientific_claim_forbidden 拒绝。
- 修复后同 Run 的假 pass、execution_ready=true、handoff/subject 错配均拒绝，随后结构合法的 missing-case blocked 报告 completed/sealed，原 workspace 输入保持只读且字节不变。实际 blocked author 输出可经 Root preflight/invoke、Local review、submit 完成 revise/blocked 报告；同精确项目/负面审查的 package 被 input_independent_review_missing 拒绝，Effect 的原 schema 门仍拒绝项目冒充 reviewed package。
- 最后一次聚焦文件命令：`python -m pytest -q tests/operations/test_l4_local_tcad.py tests/operations/test_m6c_producer_topology_removal.py --tb=short`。退出 0，93 passed，13.14s；见 `p1-final-pytest.txt`。此时额外 package 探针已移到证据，之后按父任务要求恢复了两 case 的 package 正式回归，所以该结果不能宣称最终含该回归的文件全绿。
- 额外包装正控：`python -m pytest -q 'tests/operations/test_l4_local_tcad.py::test_materialized_sprocess_author_review_package_preserves_case_anchors[True]' --tb=short`。退出 1，完整两 case/deck-scoped bias binding 经真实 author/review 完成，但 package invoke 报 deterministic rematerialization 不一致；见 `p1-scientific-package-pytest.txt`。
- 原三文件隔离复核：复制 TCAD 插件到 `/tmp/p1-package-original`，覆盖接手时原 plugin.py/project_packager.py/reviewer role，预先导入并断言两个模块来自该副本、打印 SHA256，再调用 `pytest.main(['-q', 'tests/operations/test_l4_local_tcad.py::test_materialized_sprocess_author_review_package_preserves_case_anchors', '--tb=short'])`。退出 1，两 probe 均失败。只读异常钩子打印重物化差异，不改执行；见 `p1-package-baseline-differences-pytest.txt`。
- 最终 `git diff --check --` 限定五个文件：退出 0，见 `p1-diff-check-final.txt`。未启动更多 pytest，测试执行权已释放。

## 尚未满足的包装退出条件

1. 工程单 case 没有 comparison binding 时，`transform_adapter.py:157–165` 只从 case_parameter_bindings 重建 anchors，`project_materializer.py:331–343` 因而报缺 source anchor。这是额外探索发现的基线缺陷；原 author 测试已恢复原范围，完整单/多case探针保留在 `p1-package-counterexamples.patch`。
2. 完整科学 case binding 路径也失败：`transform_adapter.py:167–193` 重物化仅传 preflight，`initialization_attestation` 从完整的 qualified 证明变为 None；`:196–201` 正确拒绝不相等项目。隔离原三文件得到同一差异，证明 P1 没有引入它。该路径可能影响 Fig4 当前 declared-source.v2 项目，不能靠删初始化证明或弱化 equality 过关。

父任务要求的两case成功断言已保留为正式 `test_materialized_sprocess_author_review_package_preserves_case_anchors`（仅移除 False/True 参数化，保留 True 路径和完整断言；此最终签名未另跑）。它目前是已知失败；P1 不标完成，等待 transform_adapter.py 最小增量计划与独立复审。失败日志和基线证据均保留。

前期 fixture 修正和诊断探针也保留：`p1-fixture-*-pytest.txt` 是 fixture Schema 修正过程；`p1-focused-pytest.txt` 的两失败是测试误传 Transform instruction，随后已修正并通过 `p1-local-review-pytest.txt` 与 93 项检查；`p1-boundary-pytest.txt` 的两失败是测试误写输出端口 revised_project，修正为现有 project 后进入最终通过结果。`p1-package-original-pytest.txt` 仅靠 pythonpath 覆盖被仓库 conftest 抢先插入路径，不能作为隔离基线；有效复核是带显式模块路径/SHA 的 verified/differences 日志。


## R3 包装增量完成补充

冻结计划 `plan-review-r3-input.md` SHA256 `9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8` 与 R3 PASS 已核对。新增授权的唯一生产文件为 `plugins/tcad_artifact/tcad_artifact/transform_adapter.py`，原摘要 `9050ff406bb833019dd887c231e8e063abde55174f56f15bacc176eb8aebeb8c`。

修复仅在 declared-source.v2 重建后增加九行：从原被审项目保留 initialization_attestation，组织重建 JSON，再调用 `DeckProjectDraft.model_validate_json(..., strict=True)`；其后原完整对象比较、受限日志迁移、preflight、case controls、review 与 Effect 门不变。None 原样保留，没有生成证明或改变 qualified，没有修改 materializer 或工程单case anchor 算法。

复用正式 `test_materialized_sprocess_author_review_package_preserves_case_anchors`：真实 Root author/review 完成，Root package preflight/invoke 成功注册唯一输出；读取该注册原件，证明完整两case binding、review 原文和初始化证明 canonical bytes 均保留。另在同一测试中验证初始化 source/project digest 替换仍被严格模型拒绝，重建 arguments 修改触发 project digest 拒绝，重建 materialization_report 字段修改仍被完整比较拒绝，缺省初始化证明保持 None。这些模型/重建负控使用相同真实已封存输入的确定性 adapter 入口；没有声称它们各自是新的真实科学 Run。

- 修改前命令：`python -m pytest -q tests/operations/test_l4_local_tcad.py::test_materialized_sprocess_author_review_package_preserves_case_anchors --tb=short`，退出 1，1 failed / 1.45s，原 deterministic rematerialization 失败复现；`p1-package-fix-before-pytest.txt`。
- 修复后同命令：退出 0，1 passed / 1.31s；`p1-package-fix-focused-pytest.txt`。
- 最终一次文件检查：`python -m pytest -q tests/operations/test_l4_local_tcad.py tests/operations/test_m6c_producer_topology_removal.py --tb=short`，退出 0，94 passed / 13.22s；`p1-package-fix-final-pytest.txt`。原负面报告、假pass、包装/Effect拒绝和author严格检查均包含。
- `git diff --check -- plugins/tcad_artifact/tcad_artifact/transform_adapter.py tests/operations/test_l4_local_tcad.py tests/operations/test_m6c_producer_topology_removal.py`：退出 0；`p1-package-fix-diff-check.txt`。

本次增量与精确摘要分别为 `p1-package-fix.patch`、`p1-package-fix-files.json`；旧 `p1-files.json`/`p1-implementation.patch` 保留为 R2 阶段快照。本次没有 commit、wheel、全套pytest、solver或真实科学MCP。测试执行权已释放。P1 工程验收退出条件现已满足，正式步骤登记仍等待独立实现复核；不代表整体候选、部署或 Fig.4 科学执行认证。工程单case缺anchor仍是未修复的范围外已知缺陷，旧失败证据保留。
