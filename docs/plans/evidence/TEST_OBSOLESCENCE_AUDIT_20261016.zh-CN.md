# 测试过时与失配独立审计（2026-10-16）

只读审计；审计者未改仓库、未运行模型、pytest、全量验证或发布构建。报告只写入 `/tmp`。使用 scid-find-simplifications、scid-decision-corpus-maintenance、scid-change-scope-checks。后续实施者与文档维护者正在并行修改；以下定位以开始审计时的 HEAD 为准。

## 范围、权威与限制

- 仓库 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`，`dev`，起始 HEAD `5251ee0`。起始只有既存未跟踪 `docs/plans/evidence/*`；未触碰它们。
- 阅读了 AGENTS.md、当前架构、设计宪章、约束登记、发布说明、tests/README、CI、pyproject、资源串行入口及相关生产/测试注册路径。
- `pyproject.toml` 同时公开 MCP 服务 CLI `scid` 与薄科研 CLI `scid-research`、`scid-experiment`。MCP、UI、TCAD、原生 H/W/A/E 均有当前消费者；不得依据文件名 R0/R3/R5、旧日期或失败就退役。
- 当前研究循环协议为 `research_loop.protocol.CURRENT = 18`；旧协议只允许受界限归档只读，不运行旧科学 schema、不重放执行。相关拒绝测试是当前安全边界。
- 遍历测试 AST，移除函数名及首 docstring 后比较完整 AST，未发现逐字重复的顶层 test 函数。这不证明不存在语义重复，但不能据此随意合并不同失败点。
- 下文为可执行清单和验收建议，不声称测试通过。失配复现引用既有 ROOTLESS_P2_FIX_REVIEW_20261016.zh-CN.md，未重复运行。

## 当前测试入口与动态边界

| 入口 | 当前职责 | 审计判断 |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Python 3.10/3.12；依次 source、installed、process；资源入口串行 | 保留。尚未声称当前整个矩阵已过。 |
| `scripts/run_tests.py` / tests/conftest.py | 每用户 serial_lock；lane 选择、资源监督、传递 inherited lock；明确重型层 | 保留，不能用裸 pytest 绕过。source 不运行其他层。 |
| `tests/operations/conftest.py` installed fixtures | 暂存 wheel、隔离环境与已安装 distribution 元数据 | 保留；source 测试的 monkeypatch 不能代替安装注册。 |
| `tests/operations/test_catalog_installed_entrypoint.py` | 核心单插件组、可选插件wheel、broken/unicode插件导入、安装后完成链 | 保留；是删除历史 fixture 后的真实当前插件边界证明。 |
| `tests/operations/test_m7_effect_fixture.py` | installed m7 Effect 编译工厂与动态配置 | 保留。其 fixture plugin 是当前安装测试消费者，不能一并删。 |
| `tests/operations/test_unified_mcp.py` | 原生thread绑定、真实proxy/daemon scope、迁移只读与工具集 | 保留，尤其 process lane。 |
| `tests/research_loop/test_registered_experiments.py` | execution entry-point/lifecycle、不可知提交不重发、原件字节绑定 | 保留；与 MCP execution 是不同入口，不能互相视为重复。 |
| `tests/operations/test_submission_protocol_recovery.py` / receipt_recovery / retirement | 不确定提交、版本拒绝、保留预算、永久retirement proof | 保留。旧版案例是当前混合版本拒绝边界。 |
| `tests/research_loop/test_current_protocol.py` | 当前整数protocol；旧job不能伪装；所有owner写入先拒绝；归档纯读、原件损坏 | 保留。只读兼容不是旧执行兼容。 |
| `tests/operations/test_retired_backend_history.py` | hardened历史只读与旧queued任务不可在Local执行 | 保留。删除后会丢唯一archive兼容回归。 |

## 可独立实施批次 A：修复七项有价值的 CLI 回归

文件：`tests/research_loop/test_native_cli.py`。生产权威：`contracts.result_schema/science_payload`、`protocol.CURRENT`、`controller`、`cli` 与 `scid-research` 声明入口。

当前 launcher 夹具缺少 protocol 18 的 W `mechanism_findings`/`stage_intent`、A `decision_request`/`portfolio_review` 等必填字段；H/A 搜索字段也应按当前 schema核对。`job['final_response']` 在当前contracts是属性名的list，`'implementation_selection' in ...` 本身不是 dict 层判断错误；不能只修这一行。`test_role_route...` 的独立 A payload 也必须先满足其他当前必填字段。

| 测试函数 | 决定 | 原因与需保留的回归 |
| --- | --- | --- |
| `test_real_native_process_completes_without_root_or_loopx` | 更新夹具、保留 | 真实本地替身H→W→A、封存/用量/幂等再次run；失配导致非法字段停止。 |
| `test_cli_entrypoint_status_is_read_only` | 更新夹具、保留 | 实际模块CLI的run/status与文件不变；不能由直接Python service测试代替。 |
| `test_pause_and_continue_between_nodes` | 更新夹具、保留 | pause不建job、continue恢复完成；当前公开命令。 |
| `test_role_route_is_exact_enum_not_prose` | 更新独立A payload、保留 | 先构造完整有效A，再只改变next_action，使红例只因非法enum失败。 |
| `test_tampered_direct_result_never_reaches_next_role` | 更新夹具、保留 | 003不存在是前序失败派生；真正需要验证篡改父conclusion被拒。 |
| `test_actual_material_copy_cannot_change_while_parent_stays_valid` | 更新夹具、保留 | 验证实际读取copy原件完整性，父封印有效不能掩盖copy篡改。 |
| `test_next_role_receives_science_without_parent_bindings` | 更新夹具/精确当前字段断言、保留 | 验证最小上下文、无父私有绑定、无递归inputs；不是废测试。 |

替代覆盖：这些节点自己就是应恢复的覆盖；不能以相邻mock单测替代后删它们。风险：过度通用schema filler会令测试只镜像实现，应显式给有意义的最小角色结果并保留目标断言。

必要验收：串行 `run_tests.py --lane source ... test_native_cli.py`；文件中的 process_e2e 节点独立以 `--lane process` 验证。必须报告lane的deselected，不能source通过就声称整个文件通过。修复不需要真实模型。

## 可独立实施批次 B：删除无消费者的旧结构指标闭环

| 文件/符号 | 当前生产权威、删除依据 | 替代覆盖 | 风险/验收 |
| --- | --- | --- | --- |
| `scripts/r5_baseline_metrics.py` 全部 | 固定404aeb14的R5结构快照，扫描大量退役路径；没有src/plugin/deploy/CI/test执行consumer。唯一当前Pythonconsumer是下一项。 | 当前编译catalog、架构文档与具体边界测试；这些旧行数不是运行资格。 | 放弃在当前scripts目录重算旧R5指标；git保留原版。静态rg确认无当前消费者、diff check。 |
| `scripts/r5_current_metrics.py` 全部 | 只被自身main调用，依赖前项；successor清单含当前不存在文件，不能作为当前架构检查。 | 同上。 | 不新建替代行数工具；历史报告不改写。 |
| `tests/fixtures/r5_structure_baseline.json` | 无可执行消费者；只指向旧inventory/generator。 | 无需测试替代，这是无消费者数据。 | 原始捕获身份由Git保留。 |
| `tests/fixtures/r5_structure_inventory.json` | 只有上述baseline JSON指向它；内容枚举Task时代路径/生产消费者。 | 同上。 | 删除前后测试节点数不变。 |

此批共1388行只是规模记录，不是删除目标。历史evidence快照及manifest内原始路径/散列不应为迁就删除而重写。

## 可独立实施批次 C：删除不被调用的测试 helper

全部精确符号搜索覆盖src、plugins、tests、scripts、deploy、CI，结果仅定义；无pytest fixture装饰器、无entry point或反射注册。删除这些helper不会减少test节点。连带只删除确定无剩余消费者的imports，不能按整文件删除。

| 文件 | 符号（起始定位） | 保留的当前测试/权威 | 风险与验收 |
| --- | --- | --- | --- |
| `tests/operations/test_runtime_plugin_configuration.py` | `_CapabilityAdapter`(76)、`_CollectingTCADAdapter`(108)、`_authorize_through_local_ui`(269) | `test_abandoned_execution_manifest_remains_attestable`及被其他文件导入的`_execution_package`；生产runtime_plugin_bindings/ExecutionBridge | 保留实际abandoned attestation与其他消费者；source定向此文件+test_tcad_control_output_capture+test_tcad_generated_capture。 |
| `tests/operations/test_hypothesis_review_routing.py` | `_critic_bytes`(101)、`_revision_foundation_bytes`(105)、`_revision_portfolio_bytes`(154) | `test_critic_routes_current_uncertainty_to_experiment_design`；`_critic`被其他测试导入，保留 | source本文件+test_user_context_contract+test_validation_responsibility_pruning；勿删_critic。 |
| `tests/operations/test_agent_contract_alignment.py` | `_validate_experiment_submission`(626) | 真实当前Agent schema/admission/submission测试及被其他测试导入的fixture | source本文件；别误删submit生命周期使用的common helper。 |
| `tests/operations/test_m2_curve_analysis_boundary.py` | `_register_inputs`(970) | curve编译/部分coverage/legacy numerical replay；`_inputs`/`_bundle`/`_compiler_*`等大量被其他文件/runpy消费 | source本文件；注意runpy消费者，不整文件搬迁。 |
| `tests/operations/test_tcad_log_progress.py` | `finish_job`(24) | 当前TCAD progress sync、非阻塞/有界/private output测试 | source本文件；进度生产入口仍在。 |
| `tests/operations/tcad_policy_fixtures.py` | `PreparationOnlyAdapter`(17) | `policy_fields`/`policy_snapshot`大量用于真实执行授权与恢复测试，保留 | source test_tcad_execution_policy等最小消费者。 |
| `tests/operations/science_fixtures.py` | `_review`(6) | `_engineering_intent`被test_general_transform_operations导入，保留 | source test_general_transform_operations。 |

通用验收：删除前后相关文件收集到的test node集合相同；定向source通过；`git diff --check`。不需重跑installed/process来证明未被调用helper的删除。

## 可独立实施批次 D：删除真正退役的测试函数与历史 case plugin

当前唯一测试消费者：`tests/operations/test_e54_plugin_removal.py::test_historical_replay_fixture_uses_generic_curve_contracts`。它用手工syspath载入R5 fixture plugin，验证fixture自带的`project_science_sources`恒等映射、schema名称及历史manifest标签；没有调用当前生产case功能，也不执行其历史adapter。

建议：

1. 删除该函数及其专用imports，保留同文件 `test_figure_implementations_belong_to_the_figure_package`（当前figure组件归属边界）。
2. 删除 `tests/fixtures/plugins/r5_e2e_tcad_plugin/`：pyproject、__init__、327行plugin、428行runtime。这是无生产消费者的evaluation-only replay实现；没有安装fixture环境、根pyproject、CI或deploy声明它。不要将它与当前m7/architecture/blind_csv插件混淆。
3. 从tests移出 `tests/fixtures/r5_e2e_tcad/{manifest.json,evidence_contract.json,replay_request.json,rubric.json,task.zh-CN.md}`。manifest明确状态 `historical_only_not_current_qualification`，原因为E5.4 scorer退役，并声明不是runnable current qualification manifest。历史manifest、任务、rubric与精确hash不改写；可完整归档到明确的docs/archive目录并加外部说明，或按仓库既有策略保留Git历史。不要把历史科学结论搬成当前资格。

生产权威：当前curve_score/figure plugins及compiled catalog，不包含r5.fixture操作。替代覆盖：`test_catalog_installed_entrypoint.py`（动态安装、插件dep、真实完成链）、`test_m7_effect_fixture.py`（当前Effect factory）、`test_submission_protocol_recovery.py`、`test_r4_execution_approval_identity.py`（执行权限/不确定提交）仍保留。它们不声称重现旧Fig.4科学资格；此批明确放弃维护旧case replay工具。

必要验收：精确当前引用rg为零；保留的figure归属测试通过；测试收集只少所删节点，installed fixture注册集合不变；发布源不能再包含退役case plugin。无需真实模型/solver。

风险：历史路径将只通过归档说明/Git解析；若后续发现未登记的外部R5 replay使用者，这是有意退出的历史工具而非受支持安装接口，恢复边界为本批文件。不得为了保留它而虚构当前生产consumer。

## 可独立实施批次 E：旧R3测试配置

删除 `scripts/r3_runner_acceptance.json`。全当前树无引用、无consumer；含旧`stage/checks/candidate_files`及`address_space_bytes`，不是当前run_tests的完整配置。`tests/README.md`已经明确“历史R3精确节点脚本和配置已经被此入口替代”。

保留JSON所列真实测试：runner limits/reaping、log preservation、unknown submission lookup、restart budget、SSH streaming、CAS streaming；它们仍保护当前生产行为。替代配置权威为`scripts/test_resources.json`及CI counterpart。验收只需无当前引用、diff check；不需pytest。

## 不应按旧名称删除的具体材料

- `tests/research_loop/legacy_selection_view.py`：`test_control_selection.py::test_legacy_sealed_author_retains_original_screen_and_public_view_bytes`消费它；生产shortlist.public_table仍明确支持public_view_version 1/2。它固定旧格式输出以防新字段污染原始sealed bytes，保留为兼容oracle，不能改成调用当前函数给expected。
- `tests/fixtures/operation_digests_964713f.json`：test_evidence_upgrade_lifecycle与test_instance_read_model消费，防止旧operation被自动升级当前资格；保留。
- `curve_calculation_pre_support.json`、`curve_support_v1.json`：当前replay_calculation支持历史算法；固定向量避免expected由当前实现自生成，保留。
- `tests/artifact_agent/fixtures/r2_h_result_schema.json`：当前output_schema_reader用其复现retained envelope scope/闭包优化，测试完整schema重建与独立materialized工具；保留。
- `figure_digitizer_v1_family.json`：当前historical figure行为回归仍消费；不能因v1名称删。
- `l2_failure_crash_probe.py`、`m7_recovery_crash_worker.py`、workbench_progress.mjs：分别有crash window、真实probe或UI消费；保留。
- `_source_checkout_plugin_metadata`默认monkeypatch与installed entry-point测试看似重复，实则源码fixture和真实metadata边界不同；保留二者。

## 文档入口失配与处置

当前入口搜索（README英中、docs/README、RELEASE英中、ARCHITECTURE英中、当前architecture目录、tests/README）结果：

- `tests/README.md` 精确测试示例为仍存在的 `test_r3_catalog_authority.py`，不退役。
- RELEASE英中提 `test_native_worker_usage.py` 是已经删除的历史说明，不是运行命令；可以缩短历史流水，但不能把它改成当前测试仍存在。
- 约束登记 evidence 对Local/Hardened平台组合、旧Worker合同的“已通过”描述绑定旧候选；当前架构明确hardened执行已退役。应明确历史范围/指向当前owner，不能用旧PASS证明现在可执行hardened，也不应修改原历史审计。
- tests/README已有资源层与R3配置退役说明；新增本轮清理范围时只列当前入口，保留lane限制与没有整套通过的事实。
- 当前rootless协议由 `docs/ROOTLESS_CLI.zh-CN.md`与研究循环代码拥有。README/docs入口此前偏MCP，主线程正在修订。审计期间已观察到他人的修改，未覆盖。
- skill建议的 `scripts/validate_architecture_constraints.py` 与 `scripts/run_science_control_bench.py` 当前树不存在；不可机械运行不存在的旧命令。需要维护者对该instruction源另行修正，不能把缺失脚本当成已经通过的gate。

## 当前测试与发布脚本的接缝（独立发现，未重复执行）

`build_git_release.py` 的 SOURCE_TREES复制整个tests，但TOOLS只选部分scripts。当前rootless测试的真实consumer包括：

- test_public_selection_replay：收集时载入 `scripts/acceptance/rootless_public_selection_replay.py`，并读 `docs/plans/fixtures/rootless-selection-actions-v1.json`。
- test_rootless_fragments / rootless_fragment_namespace / rootless_resume_namespace：调用rootless_cov_launcher。
- test_prelive_production_chain：调用prelive_gate，后者再载入rootless_cov_launcher。
- test_role_budget_share：载入behavior_card。

这些测试保护当前允许动作、hidden字段非干扰、namespace权限与真实注册链，应更新发布 allowlist，不能为令release绿而删测试。当前TOOLS没有这些路径，DOCUMENTS也没有rootless public selection fixture。source checkout通过不能证明发布源完整。

`test_git_release_builder_emits_clean_manifested_source` 已经对source/installed/process收集，但runtime代表点仍偏旧MCP/插件，没有执行上述rootless依赖链。建议把无模型rootless的代表点纳入release已生成源验证，并把文档/JSON数据闭包一并验证；构建命令由主线程正在复现，本审计未重复执行。

验收应在生成release目录内执行有资源监督的collect，并运行一个source public-selection/behavior-card节点及一个有界无模型process fragment节点；不能仅对allowlist literal做镜像断言。保持部署、安装、动态plugin、execution recovery/security的现有独立证据。

## 审计结论

有充分证据的删除集中在无消费者结构指标、死helper、历史R5 case replay闭环与旧R3配置。真正过时test函数确定一项；没有证据支持大批删除仍注册的MCP/UI/TCAD/rootless生产回归。七项已知失败是需要修复的schema夹具债务。删除数量不能替代唯一有效覆盖检查；当前发布依赖缺口应补齐并用生成源验收。

审计证据仅静态阅读与rg/AST分析；尚无本轮测试通过或发布修复通过结论。必要命令须由实施者在源码冻结窗口使用serial_lock/run_tests，报告精确HEAD/diff、lane、失败与deselected。
