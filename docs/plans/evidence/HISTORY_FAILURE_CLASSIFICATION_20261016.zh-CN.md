# History/guidance 14 failures 的只读分类

## 结论

原始 14 个失败均不能直接当作当前生产路径回归：7 个调用明确退役的 `history.bind`，4 个依赖旧 history 公开布局，1 个伪造当前任务为 v2 的 fixture，1 个分页 fixture 已不超过实际页容量，1 个 guidance 仍固定旧上限和旧措辞。应迁移仍有效的边界断言，删除退役布局/兼容语义断言；不应恢复退役 API 来使它们变绿。

但仅删除这些失败会漏掉两项当前生产缺陷，本轮已通过受监督的无模型窄反例确认：

1. **同名成果缺少候选原件 → implementation ID 的公开绑定。** 两个构造场景的全部 8 个公开 history 页面完全相同，候选 P 的 implementation handle 也相同，正确选择 ID 却分别是 `W002-I002` 和 `W002-I001`。已证实公开输入无法唯一决定选择；未实际执行错误选择或外部提交。建议 **P1（待主审定级）**：影响科学原件选择正确性；如按仅已发生后果定级，可作为 P2 可用性缺陷。控制层按合法对象 ID 解析，因此猜错但有效的 ID 不会被“候选来源不符”拒绝，仍可能合法绑定另一个成果。
2. **A 的最新 null 推荐在 closeout/status 中被旧推荐替代。** A3 推荐 P，A5 明确 null；当前 lineage 正确显示 null，但 `controller.closeout(export_only=True)` 和 `cli.status(...).closeout.existing_A_recommendation` 均返回 P@3。建议 **P2**：公开事实自相矛盾；本轮未证明因此触发交付或绕过授权。

## 检查范围与限制

- 初始基线：`70afb76004b0532e5cd26f9bfd93529660785853`，当时有 B1/B2/B3 和 fragment fixture 未提交修复。
- 窄反例执行时：`3d2cc897608eac00689e3fe61c50351d0b59ddb8`。其他参与者已提交 B1/B3；`history.py`、`lineage.py`、`selection.py`、`checkpoint.py`、`guidance.py` 在这两个 HEAD 间无 diff。报告落盘时主审通知 B2 已提交，HEAD 为 `d2e29e25dafaa7a91738afc70c1d12eb1459781d`；未重复测试。本轮没有修改 repository 或 commit。
- 技能：`scid-cross-boundary-review` 和 `scid-change-scope-checks`。已读实际 AGENTS.md。
- 原始失败证据：`/tmp/scid-b2-release-gate5-20261016/batch-001/fixture-logs/release-source-checks.log`，`14 failed, 82 passed in 7.76s`。本轮没有重跑整个 batch，也不把这份旧结果当作新 HEAD 的测试结果。
- 本轮仅静态阅读当前 public projection、caller/consumer、原件解析和 checkpoint；运行了一个 `/tmp` 本地 fixture probe。无模型、外网、solver、真实提交、旧实例；没有裸跑 pytest。
- `git diff --check` 在窄反例后通过；这是共享工作区当时 diff 的机械检查，不是对他人修复的完整验收。

## 当前权威和可用读取入口

- `protocol.CURRENT=18`；`contracts.build_job` L569-570 固定当前协议、统一 lineage、selection protocol。L672-674 调用 `lineage.bind`，不是 `history.bind`。
- `science_view` 使用 `lineage`，不公开旧 `history` 默认包。`contracts._role_lineage` 从同一 frozen view 选择角色默认内容，并保留索引。
- `lineage.bind` L318-359 写每节点原始结论分片、节点分页、每节点实现对象分页、候选分页、机制和关系分页；`history.page_writer` L551-590 同时执行行数、单页字节、累计字节约束。
- `history.source_sequence` / `_source` / `validate_observation` 验证任务、原始科学输出、seal、观察快照及归档证据；派生 cache 不作权威。
- `history.resolve_implementation` L446-459 以 role+step+index 绑定精确 seal 的材料排序。保留 `history.resolve` 的历史 handle 供观察器内部校验，不等于恢复科学角色的旧 markup 选择接口。
- `selection.project` L173-198 明确 latest A / historical A 分离，最新 A null 清空 current recommendation；当前任务已有此公开语义。
- checkpoint 是尝试级原件留存；`checkpoint.brief` 明示不完整、上一 fragment 全文未挂载，`original_access` 仅指向原任务/sealed parents/lineage，不提供历史实验结果的通用全文补读口。因此它不能自动补齐下面的实验第 9 项缺口。
- 已存在的当前边界覆盖：`test_lineage_view.py` 的全角色 lineage/原始科学结论、节点 9/候选 17/实现 17 可达、页损坏硬拒绝、退役协议不可写、4096B 多字节包；`test_context_selection.py` 的原始限制和索引；`test_scientific_guidance.py` 的 2560B 和 frozen literal；`test_selection_binding.py` 的最新 A null。此处仅阅读现有测试，不声称本轮执行通过。

## 14 个失败逐组分类

| 原始失败 | 数量 | 实际原因 / 当前权威 | 应如何处理 |
|---|---:|---|---|
| `test_role_index_paging_and_complete_scientific_text_are_readable_now` | 1 | L20 调用 `history.bind`；当前 L596 明确拒绝退役 renderer。旧 `view.index/h_lineage/recent=3` 布局不再有效。 | 迁移“所有角色、翻页、全文原件可读”的边界到 `build_job → science_view.lineage.indexes.nodes`；退役布局断言可删。与当前 `test_lineage_view` 覆盖去重，不能只恢复旧 API。 |
| `test_deleted_projection_rebuilds_without_duplicate_attempts` | 1 | 同样先被 retired bind 拒绝；还要求重建时写 `host-history/nodes`。当前 `lineage.project` 显式 `records_from_sources(...,write_cache=False)`，此 cache 文件副作用不是权威承诺。 | 删除“必须重写旧 cache”要求；若保留恢复测试，应从 sealed originals 重建新任务/索引，并证明原件、attempt 和 seal 无重复/改写。 |
| `test_history_exact_implementation_handle_uses_original_seal` | 1 | retired bind 阻止后续 `history.resolve`。精确 seal/原件身份仍有效，公开选择已改 role-step-index 对象 ID。 | 迁移公开 ID 的合法/越界/role/step/seal 负例；内部 observer handle 校验可另保留独立测试。新确证同名缺陷需要额外的候选→ID绑定断言，不能靠本测试原有“原件严格解析”替代。 |
| `test_tampered_history_is_rejected[page/source/seal]` | 3 | 全部在 bind 初始化被拒绝，未执行篡改断言。`history.validate` 及 `_source` 仍是当前输入校验部分。 | 三种保护均有价值：改走 `build_job/lineage.bind` 后损坏 bound page / raw source / seal，再经当前 `_validate_inputs` 或真实 acceptance 拒绝。page 部分与现有 current tests 去重；source/seal 不应随着旧 API 一起删光。 |
| `test_page_and_total_bounds_are_explicit` | 1 | 修改 `MAX_HISTORY_BYTES=10` 后仍调用 retired bind，异常文字不匹配是预期结果。 | 用当前 lineage 或真实 page_writer caller 测单页/总容量失败，不把退役错误改成容量错误。 |
| `test_revised_h_reads_old_science_now_and_selects_only_old_code_for_successor` | 1 | 旧 `job.history.view.index` 不存在；当前应读 `view.indexes.nodes`。后半段旧 `#reuse-implementation` 也不再是 current role 选择语义。 | 改用当前公开 `implementation_selection` ID，保留“H 当下能读旧科学全文、选中后只传目标原件、没有祖先全量扩张”的边界；当前第17对象测试已覆盖部分。并加入同名来源反例。 |
| `test_handoff_v2_packets_are_byte_compatible_after_history_upgrade` | 1 | 把一个当前任务改 `handoff_protocol=2`，pop history，却残留 `lineage_projection_version=1`/selection marker。`science_view` 因伪造不一致 job 缺 history 报 KeyError；不是受支持的历史 archive 输入。 | 该“当前 write 自动接纳 v2并继续”的测试可删，替换为 archive 只读保留+current write 拒绝不变性测试。不要以此证明真实 v2档案不可读，也不要要求 current builder 去迁移它。 |
| `test_utf8_history_default_brief_is_at_most_4096_bytes` | 1 | `science_view(job)['history']` 已迁至 `['lineage']`；`declared_limitations` 等旧布局也失效。 | 保留 4096B、UTF-8 和 omission 显示的要求，改读 lineage，使用实际落盘编码大小。当前 thousand-node multibyte test 已覆盖通用包边界。 |
| `test_nodes_paginate_by_bytes_as_well_as_row_count` | 1 | 当前页面仅 **11770B**、6行，低于 64000B / 8行上限；目录长名被替换为 compact对象ID+basename，原fixture不能再迫使字节分页。 | 修 fixture 使当前公开行真正跨容量，或改在承载大 candidate 行的当前 caller 验证字节分页。不要要求六个合法小行强制分两页，也不能据此推断 page_writer 丢失字节限额。 |
| `test_optional_observer_unavailable_does_not_block_scientific_seal` | 1 | seal、unavailable snapshot 和 validate 均已执行到后半部；旧 `view.candidates` 被当路径，当前是 dict，故 Path / dict TypeError。 | 把最后断言改读 `science_view.lineage.candidates.coverage`（selection1为公开状态字符串）并保留“不把observer失败变成科学成功/阻断”的边界。不是生产 observer seal 故障。 |
| `test_candidate_pages_pack_valid_multibyte_rows_without_expanding_brief` | 1 | 已通过 ≥2 页、每页≤上限、20行完整断言，之后读不存在的 `inputs/history/candidates.json`。当前全行入口是 `indexes.candidates` 的分页链，概览是 frozen `view.candidates`。 | 迁移后续概览/推荐断言；保留已有效的页完整性和 brief 上限。不能因为旧 overview 文件缺失而丢掉测试前半段的当前有效边界。 |
| `test_a_guidance_is_bounded_conditional_and_scientific` | 1 | 默认 literal 合计2342B，旧固定2048B不成立；当前 `guidance.MAX_BYTES=2560` 且 policy显式检查。后续还匹配已改写的旧英文句子，单改数值仍会失败。 | 改按 `guidance.MAX_BYTES` 验证公开policy和frozen text，并把语义要求写成当前行为/契约断言。已存在 `test_scientific_guidance.py` 的2560B frozen literal覆盖。不要缩短当前合法建议只为旧字符串测试变绿。 |

计数：7 个 retired-bind 失败 + 4 个旧布局失败 + 1 个非法旧协议fixture + 1 个不再越界的分页fixture + 1 个 guidance过期断言 = **14**。

## 确证缺陷 1：公开候选无法绑定同名成果 ID

紧位置：`lineage.py` L320-323 和 `history.py` L439-459。

当前实现页仅包含 `id`、`label=Path(material.path).name`、truncation；排序使用 seal 完整 `path`，但排序依据/候选关联从公开页被擦除。candidate页保留候选的精确 historical implementation handle，却没有对应 `implementation_id`。这两个合法表示之间缺少公开、确定性的 join key。

反例构造（新建 `/tmp`，非真实科学结果）：

- 场景 A：W2 成果 `a/model.py` 和 `p/model.py`；P声明 implementation 为 `history/nodes/002/artifacts/p/model.py`。
- 场景 B：W2 成果 `p/model.py` 和 `z/model.py`；同一个 P声明同一 handle。
- 两者公开实现页均是 `W002-I001/model.py`、`W002-I002/model.py`；全部 8 个公开 history page JSON 逐项相等。H6 非 W2 direct child，旧成果没有被挂载。
- 用当前解析器读取真实 seal：P 在A是 `W002-I002`，在B是 `W002-I001`。因此无法从相同的公开信息选择在两者都正确的ID。

控制严格绑定当前所选ID对应原件，没有在这次反例中错误解析任何ID；问题是科学角色拿不到选择目标对应ID所需的信息。probe 未实际提交错误ID，也未调用交付，因此报告不声称发生了错绑/错交付。

建议修复方向：公开候选的精确 `implementation_id`，或在实现页保留无私有绑定的完整相对科学身份，并在实验成果项携带相同ID；受 frozen seal 校验。不能用basename、最近节点、候选顺序猜测。

## 确证缺陷 2：最新 A null 在 closeout/status 中变成旧推荐

紧位置：`lineage.candidate_view` L174-177（只在非null时覆盖 selected）；`history.refresh` L669-677（统一lineage仍写这个旧投影）；`controller._closeout_result` L554-556/L638（生产结果consumer）；`cli.status` L52（公开只读consumer）。

相对正确权威：`selection.project` L173-198 使用最新有效A，最新null使 `a_recommended=None`，另以 `historical_a_recommendation`携带过去推荐。`contracts.build_job → lineage.brief(selection_protocol=1)` 已采用正确投影。

probe 结果：A3=P；A5=null；H6 current lineage=null；cache=P@3；`closeout(export_only=True)` status=`exported_unsubmitted`且 `existing_A_recommendation=P@3`；再读 `cli.status` 仍P@3。不是单纯未使用的旧cache：公开 closeout/status直接消费旧投影。

影响限于本次已验证的推荐事实呈现；未证明 delivery admission 直接消费这个字段、null继承授权或发生外部副作用。建议将 closeout和cache的current recommendation事实与selection权威对齐，需要历史值时使用显式历史字段。

## >8 实验指标/成果：静态风险，未升格为本轮实证缺陷

- `local_experiments.read_result` L255-256 合法接受≤32项 metrics、≤128项 declared outputs；`history.managed_calls` 保留完整 execution.result 和归档 outputs。
- `lineage.bind` L368-374 仅写 `metrics[:8]`、`outputs[:8]` 和 omitted_count，外层 experiments page 的 `next_page` 只推进 call 行，不能读同一call的后续指标/成果。
- 直接子节点有完整结果文件交接，因此不是所有读者都失去后续信息；较早历史节点的全文结果未自动挂载，实验索引也未指明完整结果页/原件的补读入口。可经未来implementation selection交接文件，但存在上面的同名映射问题，且不等于当前可直接补读。
- 前一 `/tmp/scid-project-audit-history-probe-20261016.py` 在 execution registration阶段失败，没有成功实验或probe-result；**不能引用为已验证**。本轮根据主审要求不扩大probe，保留为明确未验证风险。现有 `test_local_managed` 的happy path只有1个指标，不能证明第9项可读。

## 本轮执行证据

命令：`python -B /tmp/scid-history-public-supervise-20261016.py`。

监督器明确使用 repository `scripts.run_tests.serial_lock()`，并在持锁期间 `run_one`执行 `/tmp/scid-history-public-probe-20261016.py`；使用现有 `test_resources.json` limits。它以当前 controller/contract/lineage/selection/history/status真实函数创建并seal假科学fixture，观察器只打印本地JSON；不启动原生模型launcher。

- `/tmp/scid-history-public-probe-20261016/result.json`：两项缺陷的精简结果。
- `/tmp/scid-history-public-resource-20261016/pytest.log`：probe输出（虽沿用日志名，未运行pytest）。
- `/tmp/scid-history-public-resource-20261016/resource.json`：returncode=0，elapsed=1.411s，observed tree RSS高水位=38,526,976B，cleanup_complete=true，memory_stop_triggers=[]。
- 脚本与两个新构造场景均保留；没有重试未确定外部动作。

后续最小测试建议：把两项反例迁入各自当前public boundary regression；不需要为本分类重跑全部历史旧布局测试。完整suite、wheel、live Worker/browser/solver均未在本轮验证。
