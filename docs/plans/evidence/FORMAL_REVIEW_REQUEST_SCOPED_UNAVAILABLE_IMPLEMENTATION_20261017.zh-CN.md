# 正式审查不可用：限制精确请求，不累计整场收口

日期：2026-10-17。实施基线：dev `21410f9`。本 worker 仅静态实施，未运行测试、项目导入、安装或模型；root 随后唯一串行完成下述定向回归，结果见末节。本报告替代 A2 历史方案中“同 failure key 累计到上限后整场 blocked/closeout”的当前行为决策，不改写旧验收报告。

## 根因与窄修

旧链 `request_route → semantic.effective_route → author_correction → controller._run` 将某精确对象缺身份的局部不可用，提升为独立补正次数，最终强制全场停止或进入交付收口。E 绕行不清该累计，因此合法科研虽然仍可做，也会被再次请求该对象触发整场限制。

新链保留第一次不可用的精确 host 原件及普通 A 科学反馈；不再为它创建 review 专属 author_correction，也不再依据其历史次数强制 closeout。原有非审查补正的 root、计数和上限保持，原全场预算、max_steps、交付收口和独立性资格检查保持。

普通 A 的 job 冻结 `formal_review_choices`，只保存该 step 之前已有的不可用原件 ref 与冻结 launcher 能力。重建 retained job 复用原 refs，不将后来失败倒灌历史 job；旧无此 marker 的已冻结 job 保留原形，历史补正验证 reader 保留，新的路由不使用其 review 失败累计。

选择检查复用既有 selected_inputs、exact producer/material 与 authors 原件解析，以及 request_route 共用的 failure key；不解析所有 candidate 作者，不新建失败/重试数据库。普通科学动作立即退出此检查。formal_review 缺唯一可解析对象，或其精确 contract/subject/authors/reason 与已有失败相同，则在封存前抛既有 OutputRepairRequired；不写新 seal、不封存新 unavailable、不自动派下一 A。改写理由、经 E 或普通科研绕行不删除失败事实。

同一输出可直接选择不同 exact singleton；若实际验证的身份证据/合同改变，failure key 改变也不会被旧键禁止。新对象仍可能首次核验为 unavailable，这只保留新事实和普通 A 反馈，不授资格。模型自报身份和 pass 文本均不获资格。

## 真实入口与 schema 边界

- `contracts.build_job` 冻结限制；`science_view` 给精确科学对象 ID、不可用原因、条件和紧凑省略数。ID 从原 producer seal 的确切 material 顺序和原 role/step 取得，不按 hash 猜同源。完整 refs 无 cap 留 host。
- `response_options` 对整体不支持的 launcher 直接剔除 formal_review action enum，其他动作照常。
- 细粒度 action + selection 联合限制由控制层 `formal_review.validate_choice` 执行，不声称它们全部 enum 化；未引入 anyOf/not 或首次 native strict schema 语法。
- `semantic.outcome` 是真实 seal_result/validate 路径，写科学 seal 前校验；`continuation.output_request` 复用同一 validator，使原 session 的有限输出补正承认相同错误。仍由既有 resume_policy/剩余预算决定能否启动补正，不新发预算或增加尝试。
- 无显式 output-repair 能力的 launcher 会保留 invalid 输出并报告 output_repair_required；这不等于科学完成，也不触发基于审查失败次数的全场 closeout。有效普通替代动作可以封存并继续。

## 精确文件清单

生产：

1. `src/scidiscovery/research_loop/formal_review.py`：共享请求键、冻结 refs、联合选择校验、紧凑任务限制和反馈。
2. `src/scidiscovery/research_loop/contracts.py`：job 绑定、schema enum 与任务投影。
3. `src/scidiscovery/research_loop/semantic.py`：真实封存前检查；不再新建 review 专属补正，保留已有其他补正。
4. `src/scidiscovery/research_loop/controller.py`：删除 review 次数强制 blocked/closeout 分支；旧 review 专属 correction 不再触全场上限。
5. `src/scidiscovery/research_loop/continuation.py`：输出补正原件判定复用同一检查（两行接线）。

测试：`tests/research_loop/test_formal_review.py`。证据：本文。

## 定向负控及建议 root 串行验证

既有“次数耗尽后整场关闭”两 process 预期改成：重复同 key 在原 A 输出修复边界停止且无新 seal/A；启用 delivery policy 时普通 extract→E→A→finish 完成 6 步后，沿原合法 scientific_finish 进入 adapter=None 的 exported_unsubmitted，失败 refs 跨 E 保留；断言 source_cutoff=6，不因 review 次数提前收口。原未知身份 case 改为第一次反馈后普通 finish，不再生成专属补正。

新增/收窄 source 路径：真实 thin seals 上同 key 拒封，continuation.output_request 识别同错误；null/清空/多选/不可解析对象拒绝；同一 frozen job 的不同对象可请求且形成不同 unavailable 原件；未来失败不改旧 job；失败原件篡改仍拒；整体不支持 launcher 的 enum 实际剔除且普通 finish 可封存。身份改变的 key 比较仅使用暂时的 unit stand-in，不写假 native identity，不声称验证真实身份恢复。已有其他补正 root/次数保持测试继续保留。

建议最小执行分两批（由 root 独占）：

- source：`tests/research_loop/test_formal_review.py` 的 `test_review_choice_rejects_known_failure_but_new_subject_can_use_same_output`、`test_unsupported_launcher_removes_review_action_without_blocking_science`、`test_unavailable_review_preserves_existing_nonreview_author_correction`。
- process：同文件 `test_unknown_identity_preserves_science_and_allows_ordinary_finish`、`test_reworded_unavailable_request_needs_original_output_repair_not_another_a`、`test_unavailable_review_does_not_force_delivery_closeout_across_extraction`；正常请求键提取也触及资格链，另验证原 `test_real_native_route_freezes_exact_review_and_uses_actual_home` 与 `test_native_author_session_cannot_review_itself_even_with_pass`。

所有上述测试本 worker 均未运行。process launcher 为实际本地子进程的合成协议/会话传输，不调用模型，不证明真实 Codex 平台身份或 native 权限隔离。首次/后续资格验证继续原控制合同；本修复没有实现 A1 强隔离，也没有开启新的执行资格。

## 独审定点修正

独审指出 delivery process 初稿曾错误断言合法 finish 不进入 closeout；按生产现有合同改为 scientific_finish/source_cutoff=6/exported_unsubmitted，保留跨 E 请求限制、无提前 review-limit 收口和预算断言。此为测试预期静态修正，尚无动态执行结果。root 计划 source 3 项、process 5 项（3 个变更路径 + 正常独立 pass 与 self-overlap 各 1）；由 root 唯一串行运行。

## root 串行定向回归实际结果

root 独占执行，共四批、12 次用例执行、8 个 unique 增量用例最终通过（source 3、process 5）。没有追加全套/安装/真实模型测试。本 worker 只静态修复并读取以下原始结果。

共同证据前缀：`.trial/review_reserve_followup_20261017/`；每批 `batch-001/pytest.log` 与同目录 `resource.json`。

| 批次目录 | pytest 实际结果/耗时 | 监督 elapsed | 观测进程树 RSS 峰值（bytes） | 清理 |
| --- | --- | --- | --- | --- |
| `review-source` | 2 passed、1 failed / 2.44s | 2.621s | 63,639,552 | complete=true |
| `review-source-retest` | 原失败单项 1 passed / 1.28s | 1.453s | 59,686,912 | complete=true |
| `review-process` | 2 passed、3 failed / 10.69s | 10.875s | 138,985,472 | complete=true |
| `review-process-retest` | 原失败三项 3 passed / 9.19s | 9.364s | 145,530,880 | complete=true |

监督累计 24.313s，最大已观测进程树 RSS 为 138.789 MiB。四批 memory_stop_triggers 与 received_signals 均为空，均正常 exited；这是该批定向执行的观测数据，不外推大负载或整套资源上限。

失败及最小修复：

1. source 首批最后篡改负控直接写入 0400 原件触发 PermissionError，尚未进入期望的校验拒绝；仅测试将该精确原件 chmod(0600) 后实际改变字节，仍要求原 validator 拒绝。生产权限不变。原失败单项复测通过。
2. process 首批中，正常独立 pass 与 self-overlap 两条实际链暴露生产 NameError：提取共享 `_request_value` 后，成功路由仍引用旧局部 `subject`。修为从同一 `value['subject']['producer_step']` 取得 exact parents；request、QUESTION 与 subject 仍绑定同一值，未削弱资格校验。
3. process 交付链夹具假定 exported_unsubmitted 回包含 completed_steps，实际合同无该字段。改验六个真实 seal 的角色 H/W/A/A/E/A，以及原 closeout 的 scientific_finish/source_cutoff=6、无第七 job 和无交付 action；没有新增生产字段。上述三项仅重跑原失败项，全部通过。

通过范围：精确请求已知失败的原输出修复、普通研究/合法 finish 不受审查累计封场、E 绕行保持限制、同一 frozen job 换 exact subject、整体不支持 launcher 的真实 enum 投影、不可用原件篡改拒绝、既有其他 author correction 保持，以及正常独立 pass/self-overlap 的真实本地 native 路由。合成 launcher 不调用模型，仍不证明真实 Codex 平台身份、任意 native 外读隔离、全部历史恢复或全功能套件通过。未修改 A1 后置强隔离范围。
