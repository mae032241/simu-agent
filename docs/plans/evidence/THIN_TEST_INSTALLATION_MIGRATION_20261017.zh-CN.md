# 安装检查独立化迁移记录

日期：2026-10-17。状态：实现已写入工作树，待独立静态审查；没有运行测试或安装验收。

依据 `THIN_TEST_REUSE_REVIEW_20261017.zh-CN.md` 的安装消费者账及用户硬要求：安装检查独立于全量功能测试；功能检查及传递 fixture 不安装；不得为更换环境重跑功能测试。本记录只描述本次分工负责的安装消费者、源码 fixture 与安装构建工具，不把未提交的 P1 或 TCAD 容量修改当成本次成果。

## 最终结构

- `tests/operations/conftest.py` 删除 `installed_environments` / `installed_probe`，只提供 `source_catalog(*plugins)`：选择 core 与所需插件的源路径和 `EntryPoint` metadata，清理真实 compiler cache。它没有 wheel、pip、venv、虚拟分发目录或另一套安装器。
- 原脚本中的功能断言直接展开成源码测试。需要干净 import 状态、stdio 协议或真实 daemon/UI 生命周期的少数检查继续使用源码进程，显式注入其所需 core/插件路径与源 metadata。
- 真正的安装 fixture 和检查只在 `tests/installation/`。`installed_environment` 是 session fixture，调用一次单环境 `create_environment`；`installed_probe` 只使用该环境，不接受环境名，不删除或切换环境。
- 安装 lane 显式选择；`--installation-cohort` 默认 `core`，只另允许显式 `tcad`，没有参数矩阵。选项注册、目录/lane 隔离及运行器由根分工负责。
- 单个安装检查只覆盖隔离导入、distribution/entry point、公共 console 的 `--help`、必要资源和依赖。没有科学任务、Root/Worker 闭环、runtime catalog digest 与源码相等断言或 solver。
- `scripts/installed_candidates.py` 抽出原构建原语供两个入口使用。新的 `create_environment(..., cohort=...)` 返回唯一环境；`tcad` 在同一环境用一次 pip 安装 core+TCAD wheel，并从 wheelhouse 解析 TCAD 声明的 curve 依赖。旧 `create_environments` 仅保留 live host probe 的兼容入口，pytest 不使用其环境池。

## 每个旧消费者的去向

下表路径均相对仓库根。源码迁移保留业务或负控，删除反复执行的 installed prefix / Pillow 位置断言；依赖导入位置检查在唯一安装冒烟执行。

| 旧消费者 | 新位置及保留的断言 |
| --- | --- |
| `test_m7_effect_fixture.py::test_installed_m7_effect_uses_its_compiled_runtime_factory` | 同文件 `test_source_m7_effect_uses_its_compiled_runtime_factory`：真实 `open_runtime` 获取的 catalog 选择 fixture runtime，Effect plan 绑定原 adapter，配置加载产生对应 adapter。删除相同 compiler 的 digest 重比。 |
| `test_tcad_knowledge_closure.py::test_installed_tcad_resources_and_experiment_capability` | 同文件 `test_source_tcad_resources_and_experiment_capability`：只选择 curve+TCAD；保留禁止 host skill lookup、原角色内容与 capability 语义。TCAD 角色打包存在性在显式 tcad 安装检查。 |
| `test_root_reading_installed.py` | 删除整个重复文件；既有 `tests/artifact_agent/test_scheduler_guides.py::test_guide_installation_is_dry_run_safe_and_idempotent` 已逐项比较生成 guide 内容，还覆盖 dry-run、幂等和用户文件冲突。必要资源从已安装包加载另在唯一安装检查。 |
| `test_ledger_capture.py::test_installed_configuration_contract_and_derived_projection` | 同文件 `test_source_configuration_contract_and_derived_projection`：保留配置/公开 schema、脱敏 derived projection、源突变拒绝及失败读取不退还 consumed bytes。 |
| `test_codex_root_host_installed.py::test_installed_root_host_can_wait_resume_and_close` | 删除重复文件中的该用例；既有 `test_codex_root_host.py::test_two_turns_wait_without_model_and_reduce_usage` 覆盖等待/进程存活/close，`test_resume_has_exact_identity_and_no_automatic_turn` 覆盖精确 resume 与禁止自动 turn。 |
| `test_codex_root_host_installed.py::test_installed_progression_daemon_starts_without_native_model` | 与额外隐藏安装消费者合并至 `test_progression_acceptance.py::test_source_dormant_daemon_ui_and_restart`：真实 source daemon initialize、UI 静态资源、无 progression logs、重启同状态后仍 dormant；未调用 native host。 |
| `test_catalog_installed_entrypoint.py` core 发现检查 | 重命名为 `test_catalog_source_entrypoint.py`；源码保留 core catalog cache 与无领域 operation。真实 entry point 名值、core 不含领域 distribution/旧专属模块改在唯一 core 安装检查。 |
| 同文件 curve 独立评分检查 | `test_curve_scores_without_importing_figure` 使用仅 core/curve 源路径的新进程和会立即失败的 figure import finder，保留四类输出、失败 verdict 和 PNG；curve-only 的真实分发分离性本轮未验收。 |
| 同文件 figure tool 检查 | `test_source_figure_tool_preserves_image_and_worker_contracts` 直接检查 worker 工具 schema、decision fields、真实小图读取、只读输出及 activity。核心 Pillow 二进制依赖导入位置合入安装检查；figure wheel 本轮未验收。 |
| 同文件 TCAD dependency resolution 检查 | 真实解析仅在显式 `tcad` 安装 cohort，同一环境的一次 pip 安装 core+TCAD，并用 wheelhouse 解析 curve；源码 TCAD catalog/capability 在 knowledge closure。没有以 all_domains `--no-deps` 冒充依赖解析。 |
| 同文件 blind CSV Root/Worker 完整链 | `test_source_third_party_plugin_completes_a_local_run`：源码注册一个第三方插件，保留 profile 权限、精确 Worker attach/assignment、seal、Root 状态裁剪及下游独立 reader 读回原 payload/limitations。 |
| 同文件 broken / invalid Unicode | `test_source_broken_plugin_retains_its_diagnostic` / `test_source_invalid_unicode_plugin_retains_its_diagnostic` 通过真实可加载 fixture 源码 metadata 触发 compiler，分别保留 `component_implementation_error`/`broken_transform` 和 `component_resource_digest_invalid`/`invalid_resource`，没有把 declaration digest 错误充作替代。 |
| `test_analysis_tool_installed.py` digest 相等检查 | 重命名后的 `test_analysis_tool_source.py` 删除同轮 source/package compiler 相等检查；它没有独特功能负控，不用其声称安装功能保证。 |
| 同文件两个 stdio 协议入口 | `test_source_stdio_errors_share_protocol_diagnostics`：source core+blind 子进程，保留两种非法协议输入、秘密不回显以及 proxy runtime failure/local Worker tools 诊断；标为 process。 |
| `test_artifact_capture.py::test_installed_capture_roots_and_stage_authoring_schema_preserve_sealed_contract` | 同文件 `test_source_capture_roots_and_stage_authoring_schema_preserve_sealed_contract`：保留 draft 导航与 sealed 标识区别、单位负控、第三方 capture roots 和 startup 输出路径。 |
| `test_tool_contract_reader_installed.py` | 重命名为 `test_tool_contract_reader_source.py`：仅 curve+TCAD source metadata，保留复制 reader 使用 `python -I`，完整 tool contract/schema、handoff 和验证字段裁剪。 |
| `test_minimum_support.py::test_installed_m1_open_and_copied_input_and_reference_readers` | 同文件 `test_source_m1_open_and_copied_input_and_reference_readers`：仅 core source metadata；保留原文/分节导航、重复打开 assignment 不变、读取越界拒绝且无泄漏、未 attach 冒名拒绝及三角色契约。 |
| 额外 `test_progression_acceptance.py` 的 `prepare(root)` 隐藏安装 | 删除 `prepare`、外部 retained candidate 和 wheel interpreter 前置。daemon/UI 行为改源码进程；`test_source_archive_restore_retains_checkpoint_without_waking_runtime` 直接使用未修改的 production `InstanceArchive`，保留无 progression/有 progression 两种形状、恢复无 session/host owner、paused 与 budget/usage/report 原值。无安装环境依赖。原 callable-only RunService 形状断言不再单独启动解释器；业务调用由既有源测试承担。 |

## 未声称获得的证据

本轮不运行任何检查，不能声称源码功能或 core/tcad 包装已通过。保留的 live 工具也不代表完成 live 资格。

旧 architecture、blind_csv、m7_effect、broken、invalid_unicode、all_domains 和 curve-only 真实 wheel 组合均未验收；它们未进入 pytest 新安装矩阵。其中 bad component 与 Unicode 的 compiler 负控已由源 fixture 保留，不能扩大为其真实 wheel 交付证明。figure 二进制/资源打包也未获真实安装证明。需要这些发布边界时，应明确选择对应后续包装任务，不能重跑业务闭环取得包装证据。

## 完整修改清单

修改：

- `scripts/installed_candidates.py`
- `tests/operations/conftest.py`
- `tests/operations/test_artifact_capture.py`
- `tests/operations/test_ledger_capture.py`
- `tests/operations/test_m7_effect_fixture.py`
- `tests/operations/test_minimum_support.py`
- `tests/operations/test_progression_acceptance.py`
- `tests/operations/test_tcad_knowledge_closure.py`

重命名并改写：

- `tests/operations/test_catalog_installed_entrypoint.py` → `tests/operations/test_catalog_source_entrypoint.py`
- `tests/operations/test_analysis_tool_installed.py` → `tests/operations/test_analysis_tool_source.py`
- `tests/operations/test_tool_contract_reader_installed.py` → `tests/operations/test_tool_contract_reader_source.py`

删除：

- `tests/operations/test_root_reading_installed.py`
- `tests/operations/test_codex_root_host_installed.py`

新增：

- `tests/installation/conftest.py`
- `tests/installation/test_packaging.py`
- 本记录。

未修改根 `tests/conftest.py`、`scripts/run_tests.py`、`tests/README.md`、research_loop 测试或 TCAD 容量测试；这些由其他分工负责。没有回退已有工作树改动，没有提交 Git。

## 静态检查与执行限制

已做：13 个负责范围 Python 文件的 `compile(source, filename, 'exec')` 内存语法检查；4 段独立内嵌脚本同样语法检查；`git diff --check`；全 tests 中安装 fixture/标记文本搜索；对重命名旧路径在 scripts、当前 docs 的引用搜索，没有发现当前执行入口需要更新，历史 evidence 引用保留原样。`test_unified_mcp.py` 剩余局部变量 `installed_probe` 是 source installer shell probe 的返回值，没有使用安装 fixture。

未做且本轮禁止：pytest、collect-only、构建、pip、创建 venv、真实模型、SSH 和 solver。仅编译语法不执行 import、fixture 或模块。所有运行语义、资源预算与真实打包结果等待后续授权验证。

独立静态审查修正：安装 entry point 检查改用保留重复项的名字列表比较；core console 每项要求恰好一条，TCAD console 要求完整唯一名单。没有用 set 吞掉重复注册，也没有扩大运行语义。修正后重复内存语法及 diff 空白检查；仍未执行测试。

最终兼容性修正：`test_catalog_source_entrypoint.py::test_source_third_party_plugin_completes_a_local_run` 对 Python 3.10 添加 `tomli as tomllib` fallback，复用 pyproject 已声明的条件依赖。只修改该测试文件与本记录；内存语法和 diff 空白检查通过，未运行测试。实现再次冻结。

最终安装精简：新 `create_environment(cohort="tcad")` 向内部 creator 传 `resolve_once=True`，只调用一次 pip 安装 core+TCAD 原 wheel，curve 由 `--find-links` 依赖解析选取；仍只有一个 venv。旧 live `tcad_resolved` 默认行为保留。只做静态语法及 diff 检查，没有执行构建或安装。
