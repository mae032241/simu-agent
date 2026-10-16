# H1/H2 独立只读审查（2026-10-16）

**结论：PASS，未发现 H1/H2 合入阻断。** 该判定仅针对下面精确补丁与源码路径，不是发布、科学有效性、真实交付或运行环境资格。

## 精确范围

- Repository：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 分支：`dev`；审查基线与当前 HEAD：`4d7c6626f1d72a94a3ad9373c17e408d0820dd6d`，H1/H2 为未提交修改。
- 补丁：`/tmp/scid-h1h2-fix-20261016.patch`，SHA256 `8d01a213f9828cba90365effa244946f49acafbab00ef959dc091ca38e95561c`；补丁含未跟踪新增测试。
- 精确 diff：`src/scidiscovery/research_loop/lineage.py`（+12/-5）、`src/scidiscovery/research_loop/selection.py`（+12/-4）、`tests/research_loop/test_selection.py`（+3/-2）、`tests/research_loop/test_selection_binding.py`（+2/-2）、新增 `tests/research_loop/test_lineage_candidate_identity.py`（+81）。总计 +110/-13。
- 末次核对的 Git blob：lineage `9831a8b3252a090346c25dad3a3a52520ce21805`；selection `c3c7456cd265525cceac4dfb4713de22f7e0c703`；selection test `c5a95f28149efd33285f95a0e75751d0e7b79b91`；binding test `74c004c3c1aeee5d236da16dfb8ddb29502a80e3`；新 identity test `4d41fbee25b888550236b9527d91b51919966842`。均与补丁 index 对应。
- 同工作区 `controller.py`、`cli.py`、budget/controller tests 的 R 修复和已有大量未跟踪证据目录不计入本结论；仅阅读相关 consumer/授权边界。未修改 repository、commit 或 push。
- 已读实际内外层 AGENTS.md、原缺陷 `docs/plans/evidence/HISTORY_FAILURE_CLASSIFICATION_20261016.zh-CN.md`，并应用外层 `scid-cross-boundary-review`、`scid-change-scope-checks`。

## 语义与边界核对

1. **H1：精确候选到原件 ID。** `lineage.bind` L319–340 直接使用 `history.source_sequence → _source` 验证后的 sources/seals，按完整 `material.path` 排序，同时生成实现页 ID 和 `history.handle(material) → ID` join。`contracts.collect_materials` L471 固定材料所属节点，所以不同节点不会因相同 basename 合并。candidate page 的 `implementation_id` 与 `history.resolve_implementation` L446–459 的角色、节点、排序规则相同；实现路径不截断、不按 recency 或 basename 猜测。null 原件得到 null ID；非 null 缺失对应来源在 L338–339 硬拒绝。
2. **后继只收到精确选择。** `contracts.selected_inputs` L253–291 解析 listed ID 后，继续验证 frozen source receipt/seal、原节点材料成员身份、job/raw/source 哈希和字节大小；不能因新增显示 join 绕过原件约束。新反例分别使用 `a/model.py + p/model.py` 与 `p/model.py + z/model.py`，正确 ID 分别 I002/I001，实际后继读取均为 `P original`，其他同名成果没有被挂载。此处不是仅检查显示字符串。
3. **公开信息与模型边界。** 新增字段只有科学对象 ID；未加入 workspace/source 绝对路径、hash、receipt 或执行权限。模型输出 schema/选择语法未变。新增字段通过已有 candidate `page_writer` 落盘，仍受逐页与累计字节限制、分页和 frozen page hash 校验约束。
4. **H2：当前推荐有一份归约语义。** `selection.recommendations` L75–84 只考虑非 audit 的 A，按 step 排序；最新科学 A 的 null 清空 `a_recommended`，较早非 null 单列 `historical_a_recommendation`。`selection.project` 与 `lineage.candidate_view` 共用该函数。`history.refresh` L664–677 和 `controller._closeout_result` L570–572 都经 candidate_view，`cli.status` L52 经 closeout result，因此 cache/closeout/status 与当前 lineage 一致。显式 historical 字段不成为 current fallback。
5. **显示不授权交付。** `delivery.binding` L481–496 仍检查精确 A job、frozen job 内容、validate 后的原始 A choice，并解析冻结 delivery sources；`controller._run_closeout` L821–829 对普通直接交付仍要求 `authorization_step == source_cutoff`、角色 A、`next_action == deliver`。这些路径不读取新增 historical 推荐字段；没有发现旧推荐被转换成执行权限的路径。未发生真实外部提交。
6. **测试迁移合理。** selection test 将旧的“保留非 null”断言替换为 current=null/historical=P；binding test 使用实际 frozen `job.handoff_protocol` 和现有 `guidance.MAX_BYTES`，未放宽生产校验。

## 验证证据

### 已有证据，独立核对，未重跑

- `/tmp/scid-h1h2-before2-20261016/batch-001/pytest.log`：新 identity 两个反例 **2 failed in 1.32s**，失败分别为缺少 implementation_id、cache 仍为 P@3；不是被 fixture 错误挡住。先前无效 fixture 结果不计入修前确证。
- `/tmp/scid-h1h2-final-20261016/result.json`、`batch-001/pytest.log`、`batch-001/resource.json`：**56 passed in 68.41s**；监督 elapsed 68.747s，returncode 0，RSS 高水位 148,484,096B，cleanup_complete=true，无 memory_stop_triggers。
- 该 source batch 精确 targets：`test_lineage_candidate_identity.py`、`test_lineage_view.py`、`test_selection.py`、`test_selection_binding.py::test_new_job_freezes_selection_and_null_a_is_not_an_old_recommendation`、`test_audit_handoff.py`。覆盖新反例、分页/原文/brief、损坏页拒绝、audit defer、隔离 fake adapter 的冻结 handoff。fixture 自行 seal 本地科学输入，不是 live Worker/model 结论。

### 本独审亲自执行

- `git diff --check -- src/scidiscovery/research_loop/lineage.py src/scidiscovery/research_loop/selection.py tests/research_loop/test_selection.py tests/research_loop/test_selection_binding.py`：通过；新增文件无 whitespace 问题（已审读完整内容）。
- `python -B /tmp/scid-h1h2-review-supervise-20261016.py`：使用 repository `scripts.run_tests.serial_lock` 和 `run_one`，在 R 执行者释放锁后执行，未并行运行测试。probe 为 `/tmp/scid-h1h2-review-probe-20261016.py`，只使用新临时 fixture。
- probe 在真实 current prepare/build/seal fixture 上验证：lineage audit A 不覆盖前一个科学推荐；随后科学 A null 清空当前项且历史 P@3 单列。另在已验证 projection 边界注入“不存在的精确 implementation handle”，经真实 `contracts.build_job → lineage.bind` 得到 `Candidate implementation is outside verified sealed sources`，native intent 不存在。此负例是受控 fault injection，不声称真实受信 observer 会产出该非法值。
- `/tmp/scid-h1h2-review-probe-20261016/{pytest.log,result.json,resource.json}`：全部断言通过，returncode 0，elapsed 0.605s，RSS 高水位 46,780,416B，cleanup_complete=true，无 memory_stop_triggers。监督期间保持原资源限制，未调用模型、外网、真实 solver 或外部提交。
- 完成后复核补丁 SHA 和五个源码/测试 blob，H 范围未变化。

## 资格边界与保留限制

- 本地 source 路径回归与独立补充负例足以支持这两个定点修复；未运行完整 suite、architecture registry 校验、bench、wheel/clean-install、MCP/daemon、live Worker、browser 或 real solver lane，不将 56pass 与本报告提升为这些资格。H 改动未涉及打包或平台接口；本次不增加发布/部署授权。
- audit_handoff 使用隔离 fake adapter；不证明真实评分目标、隐藏数据或科学适用性。推荐与 proxy 指标仍是观察事实。
- 原分类报告提及的“同一实验第 9 项以后 metrics/outputs 的当前完整补读入口”风险未在本补丁修复或验证，继续保留，不能因 H1/H2 PASS 关闭该项。
- R 错误路径/预算复修及其新验证结果由另一独立范围负责，本报告不评价其是否完成。
