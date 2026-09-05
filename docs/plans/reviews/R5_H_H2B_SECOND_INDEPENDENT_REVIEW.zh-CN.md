# R5-H H2b 第二轮独立审查报告

日期：2026-08-30  
审查对象：当前未提交工作树中的 H2b 第二轮候选  
审查基线：`404aeb1`（`baseline/8765-codex`）及当前工作树  
审查职责：全新独立审查，只审查，不参与实现

## 1. 结论

**打回。**

首轮阻断中的真实计划/曲线合同审查链和真实表格 Worker 链已经基本闭合；曲线 Schema、
Operation、Validator 和资格所需投影也已迁入曲线插件，干净 wheel 目录组合可以从统一
entry point 编译。但是第二轮候选仍未满足首轮第 5 节的全部复审门：确定性图像数字化与
support-overlay 实现被删除而不是迁入曲线插件；控制面仍按曲线科学错误文本生成领域修复
建议；clean-wheel 矩阵没有执行其声称的安装态领域 Worker 工具，表格纵向测试也未核验正式
工具收据和未授权调用拒绝。

任何一项均足以阻止 H2b 通过，因此本报告不放行 H3。

## 2. 阻断项

### 2.1 曲线图证据只迁入了合同与校验，确定性提取执行路径已经消失

影响：阻断；违反实施计划第 19.2 节以及 `DET-001`，未完整满足 `PLG-001`。

首轮报告要求把 `skill/scripts` 和工具实现迁入 `curve_score`，并由曲线 OperationSpec 注册的
Worker tool 执行。当前候选删除了根目录下的 `scientific-paper-evidence` skill、
`digitize_plot.py`、`render_curve_support.py` 和 `validate_evidence_bundle.py`，但
`plugins/curve_score` 下没有对应 skill 或 scripts。曲线插件注册的唯一图证据领域工具是
`worker_curve_figure_validate`；`science.evidence.extract.figure.v1` 另行获得的是通用
`worker_run_analysis`。其 prompt 让 Agent 自行暂存 manifest、CSV 和 overlay，再调用校验工具，
没有插件自有的版本化数字化器或 support renderer。

这不是单纯的文件布局变化。现有校验器核验 Schema、边界、校准换算、行关系、hash 和 provenance，
但不从源图像重新生成像素轨迹或 overlay。真实生命周期测试也先把预制的 manifest、CSV、source
panel 和 overlay 字节写进受控目录，再调用 validator；它没有证明源图像到曲线表和 overlay 的
生产路径。测试 fixture 甚至以普通字符串字节充当 `image/png`，仍可通过该机械校验，说明 validator
不能替代已删除的提取和渲染程序。

若正式曲线表改由 Agent 临时编写的 `worker_run_analysis` 代码产生，则同一机械关系不再由版本化、
可重放程序拥有，正是 `DET-001` 禁止的“未版本化脚本生成正式派生结果”。因此第 20.2 节所称
“曲线图证据纵切面归位”并未完整实现。

最小修复：把确定性、配置约束的 digitizer 和完整 observed-support renderer 作为
`curve_score` 自有实现迁入，并通过现有 OperationSpec 注册的窄 Worker tool 在受控输出目录运行；
继续复用通用文件生命周期，不新增脚本注册表或核心领域分支。增加一个真实 PNG 输入到 CSV、overlay、
validation report、validate、finalize 的端到端正例，以及像素不符和伪 PNG 负例。

### 2.2 Task 控制面仍解释曲线科学语义

影响：阻断；违反宪章第 3、4、7 节以及 `ROLE-001`、`PLG-001`。

`src/scidiscovery/artifact_agent/service/task_outputs.py:176` 至 `190` 的通用输出校验诊断仍检查
validator 错误文本中的 `thresholded validation-check binding` 和
`series roles are incompatible`，并生成“required numerical-qualification gate”及
“control derives compact-intent roles”等领域修复建议。该结果通过
`worker_validate_output_file` 返回给 Worker，是可达的生产行为，不是注释或测试词汇。

控制层可以原样报告插件 validator 的错误，也可以提供 JSON 语法、缺字段、额外字段和类型错误等
领域无关提示；它不能识别曲线 series role、数值资格 gate，或宣称控制面派生科研角色。该分支还让
不安装 `curve_score` 的基础 wheel 保留曲线科学知识，并可能因未知插件偶然使用相同错误短语而发出
错误指导。第 20.2、20.4 节的“通用层不含曲线规则/静态扫描无命中”因此不成立。

最小修复：删除这两个按科学错误消息分支，保留领域无关的结构化错误提示；若曲线插件需要更具体的
修复说明，应由其版本化 semantic contract 或 validator 错误本身表达，不给核心新增 hint registry、
Schema router 或插件名分支。将整个 `src/scidiscovery` 纳入曲线科学语义负例，而不是只扫描四个
Schema 文件。

### 2.3 clean-wheel 与表格工具测试没有证明候选声称的安装态实调和精确收据

影响：阻断复审证据；首轮第 2.4 节和复审门第 2、4 项尚未全部闭合，涉及 `ROLE-002`、
`MIG-002`。

`tests/operations/conftest.py:121` 至 `181` 确实构建了 core、curve、table、full 和只指定 TCAD
并解析 curve 依赖的干净环境；`test_clean_domain_wheel_matrix_has_exact_plugin_ownership` 也确实从
唯一 entry point 编译了这些目录。但是其 installed probe 只枚举 entry point、调用
`compile_installed_catalog()` 并打印 Operation ID，没有 Root invoke、Task、Worker claim、
materialize、领域工具调用、受控写入、validate 或 finalize。现有其他 installed probe 只检查
生成配置中的 enabled tool，同样没有调用安装态领域工具。因此第 20.3 节“领域工具在安装态真实调用”
是超出测试事实的自我声明。

源码态表格测试已经走真实 Root → Task → `WorkerMCPRouter` → 受控文件 → validate → finalize →
独立 review，且获准工具实际成功；这是实质进展。但测试只断言 `worker_curve_analyze` 不出现在工具
列表，没有尝试调用并验证服务端拒绝；调用 `worker_table_summarize` 后也没有检查
`operation_tool_succeeded:worker_table_summarize` 的正式 activity receipt。旧的直接
`contextual_handler` 单元测试可以保留，但不能替代这些负例和收据证明。

最小修复：在 curve、table、TCAD-resolved/full 的干净安装环境中至少完成各自适用的真实
Root/Task/Worker 领域工具调用；对表格链补充未声明工具实际拒绝和精确 registered-tool receipt
断言。测试应继续从 wheel 外的干净工作目录运行，不增加 `PYTHONPATH`。

## 3. 首轮阻断复核

### 3.1 已实质闭合

- 从真实 `science.experiment.materialize.v1` 输出开始，计划 pass review 可以放行曲线合同提出；
  曲线合同的错对象、缺失和非 pass review 均在 Root preflight 失败关闭；精确 pass review 可以
  放行两种 TCAD 适配、评分、reference coverage 和两种 diagnosis。
- 曲线合同提出/审查、后续曲线 Operation、TCAD 适配和表格 Operation 都显式绑定所需 review
  端口；未发现插件复制 `is_exact_reviewer_output` 或另建 producer admission。
- 表格链的实现已经通过真实 Root、Task、WorkerMCP 和受控文件生命周期，不再依赖假 Task 才能
  成功；工具复用通用 `deterministic_analysis_completed` 活动。
- `figure_evidence` Schema、bundle validator、figure Agent Operation 和
  `worker_curve_figure_validate` 由 `curve_score` 注册；通用 Worker dispatch 已删除旧脚本名挂载。
- wheel 目录组合可以构建和编译；默认 pytest 配置已经包含表格插件路径，不再发生首轮的 collection
  import 失败。
- Python 和发行依赖均保持 `tcad_artifact -> curve_score`；`curve_score` 不依赖 TCAD。

### 3.2 仍未闭合

- 图证据提取/渲染的插件自有执行实现没有迁入，见 2.1。
- 通用核心仍含曲线领域诊断逻辑，见 2.2。
- clean-wheel 组合尚未执行安装态领域工具，表格收据和拒绝负例尚未验证，见 2.3。

## 4. 约束与复杂度判断

### 4.1 保持成立的最小权威

- 发行包只使用 `scidiscovery.plugins` 一个 entry-point group；旧 role pack、transform adapter 和
  operation-spec group 没有回退为发现入口。
- 生产代码只有 `src/scidiscovery/operations/catalog.py` 定义并构造 `CompiledCatalog`；
  `public/support/internal/all` 仍是同一目录的投影，没有第二注册表。
- Root 只有 `_validate_producer_output_admission` 一条 producer-output 准入路径；精确 review
  仍由 Task 权威的 `is_exact_reviewer_output` 校验。
- `ProducerOutputFamily` 新增的 `reviewer_operation` 与 `review_subject_outputs` 是资格 projector
  判断“哪个 reviewer 覆盖 producer primary”所需的最小投影；已删除的 `reviewer_input_port` 不参与
  该判断，未发现应继续删除的重复 review 字段。
- 未发现第二 current、第二任务状态机、固定科研 DAG、插件名 allowlist、第二 Schema router，或
  `curve_score -> tcad_artifact` 反向依赖。
- 已删除旧 `curve_score.normalizer`/`plx_normalizer` 模块，未发现兼容 import 转发器。现有
  `operation_transforms` 对内部确定性 adapter 的调用没有建立另一套发现或准入权威。

### 4.2 不成立的约束

- `PLG-001`：核心仍按曲线语义分支，且曲线图机械提取实现未由插件拥有。
- `DET-001`：正式曲线图派生值只能依赖 Agent 临时代码或手工暂存，缺少迁移后的版本化
  digitizer/renderer。
- `ROLE-001`：控制面向科学 Worker 解释 series role 与 numerical-qualification gate。
- `MIG-002`：wheel 构建与目录编译成立，但声明的安装态领域工具生产路径没有被执行证明。

其余 33 项约束不能因本轮聚焦测试绿色而整体判为 conformant；本报告只判断 H2b 涉及的边界。上述
任一失败维度都使第二轮组合不能通过。

## 5. 非阻断债务

- `test_blind_table_plugin_registers_and_executes_its_domain_tool` 仍直接调用 contextual handler，但
  同文件已经另有真实 Root/Task/Worker 纵向测试；该单元测试本身不是绕过生产路径的唯一证据，故不
  单独阻断。完成 2.3 后可按重复价值决定保留或精简。
- clean-wheel fixture 中 `full` 表示 core+curve+TCAD，表格插件另有独立环境；当前计划也分别记录
  这两种组合，故命名不构成缺陷。
- 未发现首轮指出的 `project_objective_readiness` 及其两个投影类型残留，也未发现
  `*.egg-info`、`build` 或 `__pycache__` 成为候选源文件。

## 6. 独立命令证据

在 8 GiB 以下地址空间限制、串行执行条件下运行：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1 pytest -q \
  tests/operations/test_curve_score_operation_plugin.py::test_real_plan_and_curve_contract_reviews_gate_downstream_preflight \
  tests/operations/test_h2b_domain_boundaries.py::test_table_plugin_runs_through_real_root_task_worker_and_review_chain \
  tests/operations/test_r4_approval_operation.py::test_real_figure_family_qualification_and_four_omission_boundaries \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_domain_wheel_matrix_has_exact_plugin_ownership
```

结果：`4 passed in 42.68s`。这证明四条测试本身可运行，同时也通过源码审查确认 wheel matrix 只编译
目录，图证据测试只校验预制 bundle。

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1 pytest -q \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_r5_blind_producer_family.py::test_unknown_plugin_family_and_revision_are_resolved_without_core_changes \
  tests/operations/test_r5_blind_producer_family.py::test_unknown_plugin_fails_closed_when_one_identity_has_two_primary_members \
  tests/artifact_agent/test_deploy_scripts.py::test_curve_figure_capability_is_plugin_owned_not_a_platform_skill \
  tests/artifact_agent/test_deploy_scripts.py::test_git_release_builder_emits_clean_manifested_source \
  tests/artifact_agent/test_platform_configuration.py::test_codex_installation_profile_probe_uses_the_compiled_catalog
git diff --check
```

结果：`9 passed in 5.01s`，`git diff --check` 通过。

独立目录/工具投影探针结果：

```text
catalog_count 47
figure_owner curve_score
figure_tools worker_materialize_assignment,...,worker_run_analysis,worker_curve_figure_validate
curve_dependencies builtin,general_science
tcad_dependencies builtin,general_science,curve_score
curve_skill_scripts_absent
```

控制面静态扫描的非零命中：

```text
src/scidiscovery/artifact_agent/service/task_outputs.py:186:
    if "thresholded validation-check binding" in normalized:
src/scidiscovery/artifact_agent/service/task_outputs.py:188:
    if "series roles are incompatible" in normalized:
src/scidiscovery/artifact_agent/service/task_outputs.py:189:
    return "use one declaration per series; control derives compact-intent roles"
```

## 7. 下次复审门

下次复审必须同时：

1. 恢复并迁入插件自有、版本化的图像 digitizer 与完整 support renderer，经已注册 Worker tool
   完成真实 PNG 到封存证据 bundle 的纵向正反例；
2. 删除核心 Task 输出校验中的曲线/资格语义分支，并以全 `src/scidiscovery` 负例防止回归；
3. 在干净 wheel 环境执行真实领域 Worker 工具路径，补齐表格未授权调用拒绝和精确工具收据断言；
4. 重新通过真实计划/曲线审查链、表格链、producer family、单一 catalog/admission、依赖方向和
   `git diff --check`。

只有新的独立审查明确“通过”才可进入 H3；即使 H2b 通过，也不等于 R5 完成。
