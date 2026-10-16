# 测试清理独立评审（2026-10-16）

## 当前结论

**最终清理diff：PASS（限清理与测试合同修正）。** 初审发现的三处悬空导入已清理，最终再次核对无引用；删除范围、唯一覆盖及夹具/游标断言修正未发现剩余阻断。

**整链与发布：仍有阻断。** native CLI source批次保留3项真实seal_pending失败，发布allowlist闭包仍未修，不能声称全套测试、原生链路或发布源通过。

审查者未写这些实现；只读review，并在`/tmp`保存报告与patch。未运行pytest、模型或发布构建，避免与已排队的串行验收争锁。应用scid-cross-boundary-review、scid-find-simplifications、scid-change-scope-checks与decision-corpus维护规则。

## 受审对象与指纹

- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 分支：dev；基线与当前HEAD：`5251ee05c029774200d77a07bb9f69e403dc22bf`。
- 受审未提交tracked diff：26文件，49 insertions / 3056 deletions。
- `git diff --binary 5251ee0`：147062 bytes，SHA-256 `6e6e537cf516e26bb029e7a552fe905b0bb745ecfc976a92f0bad6164ee6df0d`。
- 完整patch保存：`/tmp/scid-test-cleanup-review-20261016.patch`。
- 未跟踪`docs/plans/evidence/*`为既存材料，不包含在该指纹中，未改写。

以上为初审快照，用于追踪已修发现。最终冻结行为diff另列：

- 精确命令：`git diff --binary 5251ee0 -- scripts tests/operations tests/research_loop tests/fixtures`。
- 上一冻结快照147307 bytes，SHA-256 `6e945049f2bd27a85a173b902cc908f89b7aa341a0bd2c387d034dbdbda54d06`，与实施者 `/tmp/scid-cleanup-final-1016.patch`逐字节一致。
- 追加获准的execution_log_cache单文件合同修订后，最终行为diff149646 bytes，SHA-256 `63996fa4b32da6847648c6e718ffbe9cde5feba031275f7163ee964df141a09f`。独立保存 `/tmp/scid-test-cleanup-reviewed-final-20261016.patch`。
- 实施者最终v2快照还包含`tests/README.md`文档：`git diff --binary 5251ee0 -- scripts tests` 为151265 bytes，SHA-256 `036eb467dd632780b72f2dc9197debcf948eae18b6fe383c42a3cd0b11d6f37b`，与 `/tmp/scid-cleanup-final-v2-1016.patch`逐字节一致。
- 最后单文件增量 `/tmp/scid-execution-log-cache-increment-1016.patch` SHA-256 `c5342975fa0bc0811a788334027cbd6168b5451dd9194c2ec5806328c31e02d2`，已复算。
- 文档另含README英中、docs/README及tests/README；读取时全tracked diff为30文件、65 insertions / 3066 deletions，SHA-256 `c216afbacca689903c8ba4bfca745ff8abb8a8562369ee1d0e2b52ae5320cc45`（153441 bytes）。主线程后续报告落档另属新增文档，不自动包含在此指纹。

## 发现

### 初审P1（最终已修）：删除 `_experiment_envelope` 留下三个收集期悬空导入

紧密定位：`tests/operations/test_agent_contract_alignment.py` 删除该定义；以下当前文件仍从它显式导入：

- `tests/operations/test_registration_diagnostics_repair.py:18-20`
- `tests/operations/test_experiment_intent_writer_contract.py:15-17`
- `tests/operations/test_validation_responsibility_pruning.py:12-14`

这些文件在pytest收集时导入模块，即使不用helper也会触发ImportError，导致源码/安装/进程全树收集和发布源收集失败。AST遍历所有当前测试的ImportFrom，发现仅此三处依赖已删除顶层符号。

进一步精确搜索显示三处都是残留导入，没有调用；因此推荐完整删除三处unused import，保留helper删除，且不修改真实test逻辑。恢复helper也可止损，但会保留已无调用死代码。

最终已删除这三处未调用import；精确符号rg为零。再次AST核对没有删除其任何test逻辑。`/tmp/scid-cleanup-collect-consumers-1016` 18 tests collected，returncode=0，监督清理完成；这证明收集问题已消除，不等于18项全部运行通过。此问题曾由清理引入，已在最终指纹前修正。

### 发布接缝：新增README链接需进入发布allowlist闭包

README英中新增`docs/ROOTLESS_CLI.zh-CN.md`链接正确指向源码树当前文档，但初始受审diff没有修改builder的DOCUMENTS，该文件不随当前生成release复制，生成源README因此有悬空链接。应在整体发布修复中补齐，不能靠删正确文档入口处理。

全局审计者正在处理的既有rootless脚本/JSON发布缺口与此属于同一个允许清单闭包：SOURCE_TREES复制全tests，但TOOLS/DOCUMENTS没有全部rootless依赖。当前测试对此仍有consumer，不能为发布绿色而删它们。本审查只静态定位，未重复执行全局复现。

### 整链阻断：seal_pending时序故障仍需独立解决

主线程报告：修复native CLI有效payload后暴露真实seal_pending时序bug，独立复现正在进行。此时不能声称七项CLI回归已全部恢复或整个运行链通过。该问题没有通过放宽测试、重试或删除断言规避；当前diff没有生产代码修改。

已读取 `/tmp/scid-native-cli-source-1016-d/result.json` 与batch日志：3 failed / 7 passed / 5 deselected，6.80s；失败点是finish前置与H→W→A完成要求。响应明确`Original native writer still owns this attempt; no delivery snapshot can be captured`。该批有终态资源记录、无资源止损、cleanup_complete=true。未据此独立宣称完整根因已修复；失败必须保留。

## 删除与唯一覆盖检查

1. **R5结构指标闭环**：r5_baseline/current_metrics及两个structure JSON无当前src/plugins/deploy/CI/tests可执行consumer，只有旧generator自循环与历史快照。删除不影响当前compiled catalog，也不删除测试节点。
2. **旧R3配置**：r3_runner_acceptance.json没有current consumer，旧schema不是当前run_tests配置；列出的真实执行/恢复/streaming测试均保留。
3. **11个原计划dead helper**：精确符号搜索确认无调用、无fixture装饰、无entry point。连带import删除未削弱其所在文件的任何test函数。第12个`_experiment_envelope`本身也无调用，三个遗漏import最终已清理。
4. **历史R5 case replay闭环**：只删除`test_historical_replay_fixture_uses_generic_curve_contracts`一个测试函数，及其唯一fixture plugin/历史清单。该测试只检验自定义fixture自己的映射及historical标签；manifest已明示非当前资格/不可运行。未发现当前wheel、runtime factory registry、部署或脚本动态消费者。
5. **当前package归属**：同文件`test_figure_implementations_belong_to_the_figure_package`函数AST完整保留。
6. **当前动态和安全边界**：catalog installed entry-point、m7 Effect installed factory、unified MCP真实proxy/daemon、submission recovery/retirement、exact approval identity、old backend archive只读、current protocol拒绝均未改动。历史case replay退出维护不等于这些安全边界退役。
7. **原始历史证据**：没有改写历史审计；被删tests fixture清单可从精确基线Git恢复。它们此前不是当前科学资格证明，不能把删除描述成关闭科学问题。

AST比较所有变更的测试Python文件：唯一移除的顶层test函数为上述历史R5函数；无新增test函数。除native CLI明确更新的4个函数及下面说明的2个日志测试外，其余存留test函数AST未变。删helper不会借此悄悄删掉现有断言。

## native CLI夹具与断言评审

- 基础payload显式给implementation_selection；W给stage_intent及blocked finding；A给decision_request/portfolio_review，使用pending而非伪造screened。H focus去掉当前schema不存在的repair_source。均对照当前protocol18的contracts/search/worker_delivery合同。
- 将W标为blocked、A为pending与本测试“无managed scientific observation、只有transport stand-in”的限制一致；没有捏造科学筛选完成。测试仍要求H→W→A三个节点和原usage。
- enum测试先提交完整合法A payload，再只更改next_action，错误必须指向next_action；比旧宽泛ValueError检查更能证明目标回归。
- 三个后继材料测试新增`status == finish`前置，避免前序失败后FileNotFound掩盖根因；原先tampered conclusion、material copy integrity与sealed_node_invalid断言保留。
- `test_next_role_receives_science_without_parent_bindings`的结论字段集合加stage_intent/mechanism_findings，对应W当前必填结果。parents集合加role/limitations/limitations_omitted_count，对应`contracts._parent_view`当前投影。仍拒sha256和递归父inputs；没有放宽到任意superset。
- 没有增加自动重试、修改预算或绕过schema。运行是否通过仍依赖真实seal_pending问题解决及精确结果。

## 日志游标测试修订复审

`test_tcad_log_progress.py::test_actual_runner_tail_cursor_reads_appends_and_marks_replacement` 原在公开Root response期待text，违背当前`mcp_root.py:825`正文去除合同。最终改为：Root调用明确断言无text；通过真实`root.facade.execution_logs`读取同一缓存，保留first line、UTF-8追加delta、无gap、rotation的snapshot_replaced、overflow的source_truncated，以及读取时adapter.status_details不得被调用。没有换mock输出、删cursor或缩小输入。

当前`test_root_scheduler_ownership.py::test_raw_diagnostic_and_execution_log_bodies_stay_internal` 独立保留公开Root不泄漏sentinel、保留cursor/metadata、facade正文仍可读的覆盖。因此此修订纠正了测试与当前合同的入口错配，没有弱化唯一边界。

初始operations批次79 passed/1 failed的KeyError text正是旧断言；已读最终窄节点 `/tmp/scid-tail-cursor-source-1016/batch-001/pytest.log`：1 passed、1.42s；对应result.json监督正常退出、无资源止损、cleanup_complete=true。

最后批准的同类增量：`test_execution_log_cache.py::test_exact_execution_cache_collection_failure_cleanup_and_late_refresh` 将正文断言改到真实facade，公开Root保留metadata/cursor检查并加无text断言。坏散列CAS拒绝后cache仍可读、正确ingest释放、late refresh不复活正文、job-b隔离、durable字节和跨instance拒绝全部保留。其余三个test函数AST不变（Worker UTF-8分页/只读/frozen limit、cursor scope/redaction、增量drain）。独审此增量通过，没有弱化边界。

已读 `/tmp/scid-execution-log-cache-source-1016/batch-001/pytest.log`：4 passed、5.09s；result.json监督正常、无资源止损、cleanup_complete=true。到此收口，不再扩展清理范围。

## 文档评审

已读新增`docs/plans/TEST_CORPUS_RECONCILIATION_20261016.zh-CN.md`汇总及tests/README入口：明确静态函数数不同于参数化测试数、79/1初批未冒充重跑全绿、collect不等于执行、native source失败与发布阻断保留。汇总将最后cache单文件4通过补入后即可覆盖全部本批证据。

README英中对应段落语义一致：两组entry仍公开，MCP plugin不自动注册CLI execution adapter，资格/持久化证据边界不同。docs/README把MCP compiled合同与薄CLI冻结配置/协议区分，并纠正“所有历史材料都退出当前树”的绝对叙述。没有将历史PASS转成当前资格。发布链接闭包问题如前所述。

## 已做与未做验证

- `git diff --check 5251ee0`：通过。
- 完整diff阅读，生产current schema/parent projection/search/worker_delivery、动态插件注册与测试consumer搜索：完成。
- 当前测试ImportFrom与删除顶层定义的静态交叉核对：发现上述三处ImportError风险；无其他同类命中。
- 变更test函数AST对比：完成，结果见前。
- pytest/模型/真实solver/构建：本审查未运行；已读实施者的serial资源结果与日志：operations初批79 passed/1 failed（旧text入口，随后修正）；native process 5 passed/10 deselected（2.31s）；native source 3 failed/7 passed/5 deselected（6.80s）；消费者18 collect成功；tail单节点1 passed；execution_log_cache整文件4 passed。process/collect/tail/cache结果均监督正常终止、无资源止损、cleanup_complete=true。

最终冻结行为diff清理语义与合同修正PASS；指纹已独立核对，初审import缺陷已修。seal_pending与发布allowlist闭包是单独剩余gate，不能用清理PASS覆盖。未做全量、安装、浏览器或真实模型/solver验收，当前证据不支持这些范围的通过结论。
