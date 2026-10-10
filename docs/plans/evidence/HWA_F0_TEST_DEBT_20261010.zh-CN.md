# HWA F0 测试债务索引（2026-10-10）

状态：**14 个已定位失败尚未关闭；另有 8 个历史失败有定向通过证据；“31 失败”明细缺失**。
此文只完成 B7 的有界盘点，不宣称 F0 整体通过，也不以“基线相同”放行。

## 1. 范围与证据效力

- 审计仓库：`123/scidiscovery-e5.2`，分支 `dev`，HEAD `4e66923bf79ab26ebf27d9f559932b98231b5102`。
- 当前工作区存在既有生产、测试、文档 dirty，包括采集/附件/工具证据/用量/连接及 helper；本次只新增本文，未修改或撤回其他人的内容。
- 读取主计划 F0–F4、AGENTS 和 `scid-change-scope-checks`、`karpathy-guidelines`；以外层指定 `.trial` 的结构化结果、确切日志片段和摘要为证据。未运行测试、真实模型、原生容量验证、安装烟测；未取得测试锁。
- 历史 tokenfix 证据的原始 base 是 `222be707c04394e418d667e7e480c0ffd4216084`，不是本次 HEAD。历史文件冻结入口为 `final-source.json`、`review-hashes.json`；它们不证明当前 dirty 候选已通过。
- 类别使用 F0 的“生产 / 合同测试过时 / 环境 / 未明”。已确认的普通测试实现错误另外标明；不把它虚构成合同变更或环境故障。推断和仍需复现的部分明确保留。
- 责任 F 节点是本次清账的处置归属。F0 登记；所属节点必须完成修复或有依据的测试更新并通过，F4 检查安装候选。历史通过不能自动继承到新候选。

本文中的证据路径均相对于**外层 workspace 根** `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`；源码路径相对于审计仓库。只记日志定位与安全异常摘要，不复制凭据、运行私密坐标或模型原文。

## 2. 精确集合与去重口径

| 集合 | 证据入口 | 计数及含义 |
| --- | --- | --- |
| T14 | `.trial/tokenfix_20261010/baseline-check-nodes.json`；`checks/final/batch-001/pytest.log:372–386` | 14 个唯一 node ID；末次六文件定向集合 `14 failed, 84 passed in 103.09s`，不是全套 pytest |
| T14 原 base replay | `.trial/tokenfix_20261010/checks/w-baseline/result.json`；`w-baseline-comparison.json` | 原 base 重放这 14 个节点仍失败；node 和异常行相同，只支持既有失败的重现 |
| C7 | `.trial/covopt_20261009/checks/view/batch-001/pytest.log:75–82` | 7 个唯一 node ID；`7 failed, 23 passed, 1 deselected` |
| C4 | `.trial/covopt_20261009/checks/view2/batch-001/pytest.log:56–60` | C7 中四个 workset 节点再次失败，**不新增四个债务**；另三个目标通过 |
| C1 | `.trial/covopt_20261009/checks/runner/batch-001/pytest.log:10–11` | 1 个唯一 node ID；`1 failed, 79 passed, 8 deselected` |
| U31 | 指定浅层证据未找到逐项失败列表或对应 31 个失败的终态结果 | 未知集合，不能与 T14 相加，也不能认定被 T14 覆盖 |

T14 与 C7/C1 的 node ID 无交集。当前能定位的历史联合集合为 **22 个唯一节点**，其中 T14 仍未关闭，C7/C1 的 8 个节点有历史定向通过证据。这个 22 不是“31 失败”的还原，也不是当前失败数。按根因归并为下述九组；同一异常的包装 `ToolInputError → WorkerToolError`、`ValidationError → RootToolError` 各算一次原因。

`checks/final/result.json` 显示正常退出、returncode 1、cleanup_complete=true、无内存停止触发；T14 是真实失败结果，无证据把它归为超时、资源停止或并发污染。

## 3. T14：每个失败的证据、类别、处置与阻断

表中 `TF` 指 `.trial/tokenfix_20261010/checks/final/batch-001/pytest.log`；各行 node ID 可与 `baseline-check-nodes.json` 逐项核对。

| ID | 确切 node ID | 证据路径/行 | 根因组与类别 | 依据 | 责任、处置及发布阻断 |
| --- | --- | --- | --- | --- | --- |
| T01 | `tests/operations/test_native_experiment.py::test_comparison_source_rejects_unknown_and_oversized_originals[oversized]` | TF:4–40、372 | G1；合同测试过时 | `b"x" * 65537` 在 `_publish` 阶段被 bounded marker guard 拒绝，尚未进入测试预期的 comparison 65536 上限检查；异常发生在 `pytest.raises` 之外 | F2b：改成符合安全采集合同但超过 comparison 容量的输入并复验，保留 guard 负例；阻断“超大原件 comparison 准入已覆盖”的声明 |
| T02 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[research-objective-False]` | TF:43–64、373 | G2；合同测试过时 | Root `run_status(stage_reference=...)` 被 `SchedulerRunStatusInput` 的 extra_forbidden 拒绝 | F3：迁移到角色正确的读取入口，保留原执行出处与 attestation 断言；阻断该 native 正常交付用例的完整验证及 F4 通用交付验收 |
| T03 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[research-objective-True]` | TF:65–101、374 | G3；生产（任务日志误拒待精确触发复现） | missing module 是故意的负例；失败发生于发布 `execution.log`，guard 判 apparent private content，未进入交付断言；`_MACHINE_PATH` 同时拒绝任务绝对路径 | F2b：封存最小触发样本，核实授权任务路径与秘密的区分并修复；阻断含环境失败 traceback 的原件保留/交付。原 stderr 字节未在此日志展示，不宣称已证明具体匹配字节 |
| T04 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[source-text-False]` | TF:104–125、375 | G2；合同测试过时 | 同 T02；拒绝旧 Root stage_reference | F3：同 T02；阻断 source-text native 正常交付的完整验证 |
| T05 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[source-text-True]` | TF:126–162、376 | G3；生产（任务日志误拒待精确触发复现） | 同 T03；失败为发布 traceback 的采集安全拒绝，不能因为名称有 environment 就分类环境故障 | F2b：同 T03；阻断 source-text 环境失败日志原件保留/交付 |
| T06 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[scientific-intake-False]` | TF:165–186、377 | G2；合同测试过时 | 同 T02；拒绝旧 Root stage_reference | F3：同 T02；阻断 scientific-intake native 正常交付完整验证 |
| T07 | `tests/operations/test_native_experiment.py::test_no_provider_native_shell_delivery_and_environment_blocker[scientific-intake-True]` | TF:187–223、378 | G3；生产（任务日志误拒待精确触发复现） | 同 T03；发布执行 stderr 被 private guard 拒绝 | F2b：同 T03；阻断 scientific-intake 环境失败日志原件保留/交付 |
| T08 | `tests/operations/test_native_experiment.py::test_reused_native_execution_preserves_exact_files_and_consumer_aliases[False]` | TF:226–247、379 | G2；合同测试过时 | `test_native_experiment.py:404` 使用旧 Root stage_reference | F3 迁移读取合同，F2a 核对复用文件与 consumer alias 断言；阻断 native reuse 的完整验收 |
| T09 | `tests/operations/test_native_experiment.py::test_reused_native_execution_preserves_exact_files_and_consumer_aliases[True]` | TF:250–271、380 | G2；合同测试过时 | 同 T08 | F3/F2a；同 T08，保留 retain_log 变体覆盖 |
| T10 | `tests/operations/test_native_experiment.py::test_mixed_execution_checks_each_adopted_chain[None]` | TF:272–279、381 | G4；合同测试过时 | 夹具 `code` 仅具 scientific_attachment/tool_name，无 `output_port=attachments`、可信 sealed resolver；现行 `published_file` 要精确已发布原件，`ValidationSources(..., {})` 且未提供 resolver 不满足 | F2b：构造当前合同要求的可信原件链，禁止弱化生产来源校验；阻断 mixed native/remote 合法链正例的验证 |
| T11 | `tests/operations/test_native_experiment.py::test_unadopted_exploration_does_not_require_a_chain` | TF:280–287、382 | G4；合同测试过时 | 使用同一 `_chain_sources` 不完整正例；先在已采纳 native implementation 链失败，尚未验证未采纳 exploration 是否被正确忽略 | F2b：先修共享合法链夹具，再保留 exploration 负向范围断言；阻断“未采纳探索不要求完整链”的验证 |
| T12 | `tests/operations/test_experiment_continuation.py::test_bound_implementation_runs_collects_and_delivers_without_prepare[sprocess]` | TF:290–311、383 | G2；合同测试过时 | `test_experiment_continuation.py:119` 使用旧 Root stage_reference | F3 迁移读取，F2a 验证绑定实现续接；阻断该无 prepare 续接用例的完整验证，不代表真实 TCAD solver 已验收 |
| T13 | `tests/operations/test_experiment_continuation.py::test_bound_implementation_runs_collects_and_delivers_without_prepare[sdevice]` | TF:314–335、384 | G2；合同测试过时 | 同 T12 | F3/F2a；同 T12，保留 solver 变体 |
| T14 | `tests/operations/test_experiment_continuation.py::test_failed_producer_receipt_survives_recovery_and_a_third_task` | TF:336–370、385 | G5；未明 | 第三任务显式 subject=`objective`，控制层推导原始来源时 `input_origin_missing: subject`；已发生 recovered 任务成功提交，但第三任务未入队；缺乏完整来源图证明是夹具过时还是生产推导缺陷 | F2a：核对原目标/原始来源冻结图与第三任务准入；修生产或按合同更新夹具并通过；阻断“failed producer 证据跨恢复与第三任务保留”的验收，原因未明期间保持阻断 |

### 根因证据及关闭条件

| 根因组 | 节点数 | 可核查的源码依据 | 可执行关闭条件 |
| --- | --- | --- | --- |
| G1 bounded marker guard 先于 comparison | 1 | `test_native_experiment.py:175–184`；`artifact_capture.py:55–89` | 仍使合法发布的 observation 超过 65536，实际在 comparison 准入被拒；安全负例保持拒绝。不要把 65537 单字母长串的安全拒绝删除以绿灯 |
| G2 Root 读取合同已收紧 | 7 | `interfaces/mcp_root.py:266` 的 SchedulerRunStatusInput 无 stage_reference；同文件 parse 函数为 scheduler 固定 stage_reference=None | 更新测试读取所属 Worker/受控原件入口；保留 execution_origin、execution_attestation、精确 bytes/aliases 的语义断言；7 个节点通过。不得为旧测试给 Root 重开科学正文入口 |
| G3 执行 traceback 采集失败 | 3 | `test_native_experiment.py:244–252` 故意缺模块并发布 stderr；`artifact_capture.py:64` 合并 `_SECRET` 与 `_MACHINE_PATH`；`plugin_runtime/workspace.py:15` 对 /tmp 等机器路径匹配 | 证明触发内容确实是授权任务路径，原始 bytes/哈希可追溯且受控；派生视图路径正确；秘密、越界、符号链接负例通过。三个 True 分支随后可能显露 G2，不能只修首个异常就关闭 |
| G4 原件链夹具缺可信文件身份 | 2 | `general_science_experiment_task.py:298–320` 要求 attachments output_port、原件 resolver 与精确 identity；`test_native_experiment.py:418–438、461–476` 未提供 | 补齐夹具当前可信来源合同，正例通过；wrong_version/orphan/fake_receipt/ordinary_file 等现有负例仍拒绝。相同源文件不等于可信封存证明 |
| G5 原目标来源解析缺口 | 1 | TF:346–354 指向 `service/operation_origins.py:582、668`；测试第三 invocation 在 `test_experiment_continuation.py:289` | 封存 subject 原始来源及回执链，确定归因，第三任务合法入队且 exact original 回执保持；不能用同 schema 或最近任务替代缺失原始来源 |

G1/G2/G4 分类依据是**现行代码中的明确合同与夹具差异**，不只是 baseline 同样失败。G3 具体内容命中仍需 F2b 最小复现；G5 未确定生产/测试归因。这些分类都不构成修复通过证据。

## 4. covopt 浅层日志：8 个历史节点，按根因去重

`CV` = `.trial/covopt_20261009/checks/view/batch-001/pytest.log`，`CV2` = 同 checks 下 `view2/batch-001/pytest.log`，`CV3` = `view3/batch-001/pytest.log`，`CR`/`CR2` = `runner`/`runner2` 对应日志。

| ID | 确切 node ID | 失败证据及原因/类别 | 后续证据、责任与阻断 |
| --- | --- | --- | --- |
| C01 | `tests/operations/test_default_material_reading.py::test_complete_inventory_detail_is_preserved_at_the_advertised_pointer` | CV:3–11；G6 合同测试过时：run_id=`run_inventory_navigation` 不满足 `run_` 后 alnum 规则；当前测试改为 `run_inventorynavigation` | CV2 总结 4 failed/3 passed，result 的 7 目标中本节点无 FAILED；tokenfix final 六文件中该文件其余节点通过。历史关闭；F3 对当前候选保留导航完整性回归，未复验当前 dirty 候选前不继承通过 |
| C02 | `tests/operations/test_minimum_support.py::test_fixed_decision_worksets[initial_h]` | CV:12–24、CV2:3–15；G7 合同测试过时：启动核心与完整 instructions 的直接等同已变；第二次重建还存在 section 顺序差异 | CV3:2 `4 passed`；F3。历史关闭，当前候选仍须按冻结合同完整重建、按原 section 顺序复验 |
| C03 | `tests/operations/test_minimum_support.py::test_fixed_decision_worksets[h_revision]` | CV:25–37、CV2:16–28；G7，同 C02 | CV3:2；F3，同 C02 |
| C04 | `tests/operations/test_minimum_support.py::test_fixed_decision_worksets[w_portfolio]` | CV:38–50、CV2:29–41；G7，同 C02 | CV3:2；F3，同 C02 |
| C05 | `tests/operations/test_minimum_support.py::test_fixed_decision_worksets[a_results]` | CV:51–63、CV2:42–54；G7，同 C02 | CV3:2；F3，同 C02 |
| C06 | `tests/operations/test_minimum_support.py::test_each_exact_object_is_delivered_once[w_portfolio]` | CV:64–68；G8 未明（已定位测试实现错误）：测试引用未定义 workspace，NameError；不属于生产故障或环境故障 | CV2 目标包括这两个参数节点、摘要 3 passed 且无对应 FAILED，当前代码先获取 workspace；历史关闭。F3 保留 exact-object 去重语义，当前候选复验 |
| C07 | `tests/operations/test_minimum_support.py::test_each_exact_object_is_delivered_once[a_results]` | CV:69–73；G8，同 C06 | CV2；F3，同 C06 |
| C08 | `tests/operations/test_covshift_pilot_preparation.py::test_two_arms_have_same_image_view_empty_outputs_and_frozen_shared_limits` | CR:4–8；G9 未明（测试索引错误高度支持）：`launch['role_profiles'][name]` 的 name 已是 `submission`，抛 KeyError；当前用 arm_name；没有源码冻结差分可证明全部历史修改内容 | CR2:2 `1 passed`，result 目标即此确切节点且正常退出；历史关闭。F4 在当前安装候选重新验证两组画像/环境/共享限制，不能把 source 测试当真实模型/安装资格 |

C01/C06/C07 的历史通过依据可由 CV2 的**精确 targets + 全部 FAILED 集合 + 4 failed/3 passed**推出；不是仅依赖别人写“已修复”。C02–C05 的第二次失败是 C7 子集，同一个失败 node 在不同日志出现不重复计算。历史补丁与本次 HEAD 的完整绑定尚未核验，因此该“关闭”只指相应历史证据链，F3/F4 不能直接借用其发布结论。

G7 当前测试 `tests/operations/test_minimum_support.py:307–329` 已按 original_sections 顺序重建并核对 boundary；G8 当前代码在 `:465` 附近先从 `_context` 获取 workspace；G9 当前 `test_covshift_pilot_preparation.py:54` 使用 arm_name。这里的源码读取不是本次执行证据。

## 5. “31 失败”的证据缺口及责任

本次仅查看指定 tokenfix/covopt 根层结构化结果、covopt `checks/*/result.json` 与明确 `batch-001/pytest.log` 摘要，以及已有相关 review/manifest 中的测试引用；没有宽泛递归搜索或读取模型大日志。

这些入口中没有找到 `31 failed` 终态摘要及逐项 FAILED node ID。故不能给出“31 全部归因”、不能减去 T14 得出“剩余 17”，也不能把 C7+C4+C1 与 T14 简单累加来凑数字。数字 U31 暂不进入已确认 node 总数。

- **责任：F0** 补充原 31 失败的精确候选/commit 或 frozen file hashes、执行命令、终态 result、完整 FAILED 清单及首因定位；优先向原证据生产者获取确切入口，避免重跑无法定位的历史候选。
- **阻断范围：** 不能宣称“既有全部失败已清账”或 F0 B7 已关闭，不能宣称当前全套 green。若查明对应本轮修改入口，分配到具体 F 节点并在其验收前关闭；不以证据缺失自动放行发布。
- **后续出口：** 拿到 node 列表后先与本文 T14/C7/C1 去重，再按同一类别、责任、验收范围填写；若原始明细永久不可恢复，明确撤回“31 已分类/已通过”结论，对准备发布的冻结候选执行覆盖受影响边界的回归并保存新完整明细。旧数字仍标缺证据。

## 6. 最小复验建议（未执行）

执行者应先冻结准确候选、记录 dirty 归属并与父协调的串行测试资源安排一致；本次没有取得测试锁。以下命令在审计仓库根、项目已配置 Python/依赖环境中运行；保存 command/result/FAILED 清单，遇相关失败先归因。它们不调用真实模型。

T14 的最小整体重放可以直接使用已冻结的精确 14-node JSON，而不跑全部两个文件：

```bash
python - <<'PY'
import json
from pathlib import Path
import subprocess
import sys
nodes = json.loads(Path('../../.trial/tokenfix_20261010/baseline-check-nodes.json').read_text())
assert len(nodes) == len(set(nodes)) == 14
raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q', *nodes]))
PY
```

每组修复后的首次检查只选表中涉及的 exact node；例如 G3 先定位触发及秘密负例，随后验证其三个 True 变体，避免首个路径拒绝遮挡 G2。G4 修复还需保留现有损坏链负例，因此扩到该函数的全部参数是必要的：

```bash
python -m pytest -q tests/operations/test_native_experiment.py::test_mixed_execution_checks_each_adopted_chain tests/operations/test_native_experiment.py::test_unadopted_exploration_does_not_require_a_chain
```

C7/C1 8-node 复验只需下列四个函数（参数展开为 1+4+2+1）：

```bash
python -m pytest -q tests/operations/test_default_material_reading.py::test_complete_inventory_detail_is_preserved_at_the_advertised_pointer tests/operations/test_minimum_support.py::test_fixed_decision_worksets tests/operations/test_minimum_support.py::test_each_exact_object_is_delivered_once tests/operations/test_covshift_pilot_preparation.py::test_two_arms_have_same_image_view_empty_outputs_and_frozen_shared_limits
```

本文件不规定 F1a 新增 RPC 序列测试名：本次 22-node 证据不覆盖 resume/终态读取/释放，F1a 必须另冻结自己的确切回归节点及原生容量验证。F4 仍需安装后的无模型生产入口回归；源树 pytest 与历史模拟 fixture 不能证明平台原生名额回收、可信挂接、真实科学结论或当前 wheel 合同。根据修复后实际 diff 再选择所需全套 gate，不能把这 22 个节点视为完整发布测试矩阵。

## 7. 有界决策及证据完整性

- **允许开始 F1a：** 已定位的 T14/C7/C1 无 resume/终态重载/释放的失败；这些债务有责任节点和阻断范围，不能要求先消灭全部不相关失败才进入 F1a。F1a 自身仍须达到主计划出口。
- **不得放行相关节点：** F2b 的日志保留/可信原件链，F2a 的失败回执第三任务续接，F3 的角色读取合同及当前支撑集验证须按表关闭。F4 继承这些 gate；U31 缺口也阻断“失败清账完整/全套 green”声明。
- **无环境豁免：** 已定位集合没有一项已证明是环境/并发导致的测试失败；missing_environment=True 是负例输入，不是免责分类。
- **本次文档检查：** 仅核对报告 node 集合与上述日志/JSON一致、检查新增文档 diff 的空白错误；没有运行代码测试或模型。

关键静态证据 SHA-256（外层路径与上述缩写一致）：

| 文件 | SHA-256 |
| --- | --- |
| `.trial/tokenfix_20261010/baseline-check-nodes.json` | `80ac79fded60b67aa8a4e2994ab5660bc351fd960b0a0b265e01548ac850cbc4` |
| TF | `4c86d0748b6b3d524710ad5a2368495cb261362d5d76c805dfd5ddd71331180a` |
| CV | `c1649710295edf7ae72cb3970ffea4c9285ff47a23b4ea64e4b72bec17a5fd14` |
| CV2 | `f904664925e5da14fbc2af9d4aba5ba0b7249d6a0c9173512826bd929fcb3a38` |
| CV3 | `442faba38b59b242329fc87393ae99b9b9f84f900420f6df7ef37c7c6ee4657e` |
| CR | `d648f5dae5a804156e044c286adc1bc096a2a4d674c89c14ab8bf4db4e4de873` |
| CR2 | `4e8b6c5a89da44bf05d17100903172be04033067c113a6831bdfafbd42b7da52` |
