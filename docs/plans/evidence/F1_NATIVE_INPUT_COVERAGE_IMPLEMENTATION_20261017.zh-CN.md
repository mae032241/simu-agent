# F1 精确 native 输入覆盖实施账

状态：独立静态审查 PASS，4个独立目标经增量修复全部通过；限本文件声明的精确 native/compiler 子范围。2026-10-17。

范围沿[已审设计](F1_MANAGED_INPUT_PROVENANCE_DESIGN_20261017.zh-CN.md)，**只接 native/compiler 子范围，完整 F1 仍未关闭**。实施时 root 收窄两点：仅共同已验证 known_success/known_failed 可发布 complete；首次控制封存验 HMAC，后续只核已封存 projection 的 exact 原件关系，不再生成 coverage 或索取私有 key。not_submitted/unknown 保持 incomplete，不影响 F2 的 blocked 科学封存，不伪造 completed。

## 精确7文件

- `history.py`：`managed_input_coverage` 首次复用 validate_managed 后检查签名/已有边；`validate_input_coverage` 只核原 projection 与 accepted/authority/compiler 原件，不重建覆盖或补边。
- `execution_authority.py`：首次 `accepted_input_subject` 在原 host key/locator 下核授权和决定 HMAC；`validate_accepted_input_subject` 对已有封存 binding 只重验 exact identity。共用私有纯关系验证，不走 `_validate_binding`、`request/decision`、`require_review`、当前来源/clock/余额准入；无 RPC、grant 或新权限。缺 host 来源绑定不可 complete，原件矛盾拒绝。
- `execution_inputs.py`：`execution_input_coverage` 只证明 exact selected subject 及原 compiler slots/author_input 已被现有 source-provenance producer edges 覆盖；复用 verify_compilation/resolve_native_original，不新贡献图、解析器、schema 或祖先复制。
- `qualification.py`：新 seal 的原 provenance 可选绑定覆盖；只读验证原 marker，旧无 marker 保原格式与 unknown，不回填或重签。complete 只取消附加 unsupported unknown，最终限制仍由既有输入图三态递归计算。
- `formal_review.py`：只改 authors 消费段，将贡献覆盖与来源限制分开；原 selected/compiled 作者遍历、reviewer自身身份，以及刚修的 review 选择/路由完全沿用。opaque/local/外部 observer 未闭合仍 incomplete/unknown。
- `test_native_execution_inputs.py`：原 fixture 加必要小终态回执和按 prepared identity 的 lookup；同一成功链延长至 W10（max_steps 从8到12）完成原非空输入执行后新成果→精确独立资格→后继 run。另一个无执行源限制 unknown 用例不伪造 gate 应拒绝的成功调用。
- 本实施账。

## 负控与保护

同一主链先验 queued/unknown coverage 不完整，再用真实共同 observation 验 known terminal；缺 selected 边、同 hash 错 producer 不补边；缺 authority 不授覆盖。原 projection 的 request ref 改动明确拒绝；unknown/not_submitted row 即使给完整 projection 也拒绝。旧无 marker 按旧表达 unknown。原作者集合包含 compiler source contributors；新 reviewer 独立，不把 subject 作者当 reviewer。

另一个合法未执行 subject 用例证明作者已知且限制 unknown 时仍可 formal review，而实际 run 在 gate/RPC 前拒绝。原 wrong-instance/wrong-producer/unbound alias/author读竞态/篡改 package 负控保留；未复制矩阵或增加安装/模型环境。

新源结果封存时验证原签名，原 provenance 绑定 accepted snapshot、request/authorization/decision/allocation、compiler refs。测试定义在后继 run 后移除原 operator key，重读 live output qualification/authors/history 并断原 provenance/seal 字节不变；只读路径没有公开 skip 验签入口，也不能生成新的 complete。

## IO、边界与未验收

没有 call 的节点保持原成本。每次首次封存只扫描本节点已归档 rows；共同 validate_managed 的完整日志/原件核验仍有成本，局部 compiler memo 不跨请求持久化。只读每个 call 重核其小 accepted/授权/准备/脚本原件及 compiler proof，重复 compiler 在一次调用中去重；既有科学 history/source/作者 DAG 完整递归与 code/hash IO 仍在，不声称零 IO 或硬实时。

“不新增 host key 依赖”仅指**后续 live 原件重核**。alias/material.source/prepared/script/native-intent 位于既有归档 roots，但绝对原 root、外部 implementation code/capability_source 原件仍是既有资格读取依赖。归档只 inspect blobs；不承诺脱原路径、清理上述原件后的资格读取或可迁移/离线 qualification，不为此另复制材料。

本 agent 仅文本/AST，不运行 pytest/collect、项目 import、安装/build、模型、solver、SSH、HTTP、CLI业务或 Git。root 最小串行目标：

1. `tests/research_loop/test_native_execution_inputs.py::test_native_observation_new_subject_review_and_next_run_use_covered_inputs`。
2. `tests/research_loop/test_native_execution_inputs.py::test_known_native_authors_with_unknown_restrictions_can_review_but_not_execute`。
3. 原 `tests/research_loop/test_native_execution_inputs.py::test_unbound_alias_and_author_read_race_reject_before_gate`。
4. 原 `tests/research_loop/test_native_execution_inputs.py::test_same_hash_wrong_origin_and_changed_package_cannot_reuse_compiler_proof`。

六份 Python（五生产、一既有测试）仅 stdlib AST 解析与尾随空白静态检查通过，不 import 项目。以上4目标之外的旧目标是否复验由 root 精确选择。fixture 的 native session 身份、可信后端和 cleanup 仍是合成边界；测试通过也不证明真实平台独立性、TCAD solver 外读闭合、Local/opaque 剩余 F1 或恶意 Worker 隔离。

## 追加：首批实际失败及原件 reader 修复

root 唯一串行首批运行上述4目标，日志 `.trial/review_reserve_followup_20261017/f1-source/batch-001/pytest.log` 记录2通过、2失败（2.92秒）。两个旧负控通过；两个新增目标在首次 W2 科学封存前同因失败，尚未验收新增闭环。

根因是本次 `seal_outputs` 错把 history 的 `{path, sha256}` receipt 传给要求 `{path, sha256, size_bytes}` 的 qualification `_read`；新增测试读取 observation 也有同错。修复不伪造 size、不改 receipt 或 fixture：将 history.validate_observation 原有的配置/精确路径/hash/raw-source-binding 读取段提为同 owner `read_observation`，原完整验证继续在 validate_observation，两个错误调用改用该 owner reader。首次 coverage 仍经 validate_managed，不新增重复全日志验证。限定三份变动 Python AST/空白静态检查通过；本 agent 未执行测试。修复冻结待独审及 root 复测。

root 第二批仅重跑两新增目标，`f1-source-retest/batch-001/pytest.log` 记录1通过、1失败（11.63秒）：成功链已过 W6 terminal/seal、A7 request、review8 独立 passed，但 W10 返回 unresolved。静态已确认为测试对象选择错误：W6 的新 managed log/manifest 与 revised 包一起进入按材料路径排序的公开清单，硬编码 `W006-I001` 实际选择日志，随后用 revised 包执行正确遭到 exact-subject 门禁拒绝；该批没有保留响应 note，不能将 review8 的 passed 记成 revised 包资格通过。

只修此 target：用原 `history.implementation_options/resolve_implementation` 在 A7 的冻结清单解析 exact revised material 对应对象 ID，A9 复核同一 ID 与 exact material；正式 request 与独立 qualification 均断 subject material 等于 revised 原件。保留 W10 `queued` 严格断言，并携完整非密钥响应作诊断。不重述排序编号公式，不改生产门禁或 backend 状态，不接受 unresolved。此修复仅静态 AST 通过，待独审和 root 单项验收。

## Root 最终增量验收

仅 root 串行使用 `scripts/run_tests.py --config .trial/p_migration_validation_20261017/resources.json --lane source`，各批精确目标见对应 result.json；没有全文件/全库、安装、真实模型或 solver 测试。

| 输出目录（`.trial/review_reserve_followup_20261017/`） | 结果 | 监督器耗时 | 峰值进程树RSS |
| --- | --- | --- | --- |
| f1-source | 2通过、2失败 | 3.272秒 | 82550784 B |
| f1-source-retest | 1通过、1失败 | 11.874秒 | 84332544 B |
| f1-chain-retest | 1通过 | 15.14秒 | 84176896 B |

合计4个独立目标、7次执行；先通过的目标不重复跑，不能称最终HEAD全套重跑。三批 cleanup_complete=true、memory_stop_triggers=[]，峰值约80.43MiB，监督器合计30.286秒。采样止损不是cgroup硬限制。首批原件reader生产错误和第二批错选日志的fixture错误均保留日志，不抹成环境失败。最终单链已通过精确包审查及后继run，删除私有key后的只读重核不修改旧seal/provenance。存在既有 utcnow 弃用警告，未因此扩大修改范围。

[独立审查](F1_NATIVE_INPUT_COVERAGE_REVIEW_20261017.zh-CN.md)与本增量结果共同限定本节点；Local/opaque/observer、真实平台独立性、任意外读、可迁移归档资格仍未证明。
