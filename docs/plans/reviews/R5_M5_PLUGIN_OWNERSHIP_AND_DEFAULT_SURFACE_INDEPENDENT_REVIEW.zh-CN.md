# R5-M5 插件所有权与默认产品面独立审查

日期：2026-09-01  
审查者：未参与 R5-M5 实现的独立代码审查者  
结论：**FAIL（阻断 M6）**

本结论只针对 R5-M5 阶段门。即使返修后 M5 获得 PASS，也只会放行 M6，不表示 R5-M 已完成。

## 1. 审查范围与基线

本次按 `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 第 10、13—15 节，结合 M5 实现证据、
33 项约束注册表、当前代码、测试和工作树差异独立审查。工作分支为
`baseline/8765-codex`，`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`。

工作树包含跨阶段的大量既有未提交修改，无法把 `git diff HEAD` 诚实地称为一份隔离的 M5 patch；
因此本报告审查当前候选实现及其 M5 证据，不伪造精确提交边界。除本报告外没有修改生产代码、测试或
既有文档。`git diff --check` 与 `git diff --cached --check` 均通过。

## 2. 阻断发现

### B1：figure 插件没有强制闭合“提取—独立审查—bundle”链（高严重度）

实现证据明确声称可选插件提供“已审查图像证据到曲线 bundle 的确定性转换”
（`docs/plans/evidence/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_IMPLEMENTATION_EVIDENCE.zh-CN.md:52-62`），
但编译合同没有表达这个条件：

- extraction 的 `ReviewSpec` 只把 `scientific_intake` 声明为受审输出
  （`plugins/curve_score/curve_score/figure_science_operations.py:451-455`）；
- bundle transform 只接收 `figure_manifest`、`validation_report` 和 `curve_tables`，没有
  `scientific_intake` 或 `evidence_audit`
  （`plugins/curve_score/curve_score/operation_transforms.py:479-493`）；
- 该 transform 仍可把 `curve_bundle` 用作 `claim_evidence` 和 `prior_signal`
  （同文件 `:490`）；
- Root 只有在被消费的生产者端口属于 `ReviewSpec.subject_outputs` 时才要求精确 reviewer 结果
  （`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1190-1202`）。

因此，“三项 Operation 由一个可选入口安装”成立，但它们只是并列可见，并不是审查闭合的纵向链。
任何调用者都可在没有创建或接受独立审查 Artifact 的情况下，把机械校验通过的 figure 文件转成可供
科学主张消费的 canonical curve bundle。这不是 UI 或提示词问题，而是 Root 预检可直接接受的合同缺口。

真实 Root 预检复现如下；使用仓库 M3 fixture 创建合法 manifest/report/table，report 的父代包含
manifest 与 table，但根本不注册独立审查 Artifact：

```bash
bash -c 'ulimit -v 7340032; export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1;
PYTHONPATH="src:.:plugins/curve_score:plugins/curve_figure_evidence:plugins/tcad_artifact:plugins/ingaas_fig4" \
python <复现脚本>'
```

复现脚本调用 `tests.operations.m3_transform_equivalence_runner` 的 `_catalog`、`_scenarios`、
`_open_root`、`_register_data`、`_request`，选择
`scidiscovery.curve-bundle.figure-evidence.v2` 场景，注册其三个已声明输入后调用
`operation_preflight`。实测输出：

```text
{'declared_inputs': ['figure_manifest', 'validation_report', 'curve_tables'],
 'has_evidence_audit_input': False,
 'preflight': {'admissible': True, 'reason_code': None, 'port': None,
               'executor_kind': 'transform'}}
```

现有 M3 等价场景也只绑定这三个输入
（`tests/operations/m3_transform_equivalence_runner.py:661,715-725`），所以它会把当前旁路固化为成功路径；
绿色等价测试不能证明独立审查闭合。

这直接违反本次指定验收的“提取—独立审查—bundle 闭合”，并削弱 EVD-001/EVD-002 的精确来源与
独立性边界，以及 ROLE-002 的全生命周期同合同要求，故不能以其他聚焦测试通过抵消。

### 最小修复

1. 让 bundle Operation 精确消费 `scientific_intake` 与其对应的已接受 `evidence_audit`，或采用同等小的
   编译合同表达同一关系；优先复用 Root 已有的 exact reviewer-output 校验，不增加第二目录、状态机或
   operation-id allowlist。
2. 扩展 parentage guard，要求 audit 精确覆盖本次 manifest、validation report、全部 curve tables 及
   被审 intake，拒绝旧 revision、错误 reviewer、混合 sibling family 和少/多表拼接。
3. 增加经 Root `operation_preflight`/`operation_invoke` 的一条正例和至少无 audit、错 audit、旧 revision、
   混合 family 四类负例。M3 oracle 应显式接受这次有意的 admission/parentage 行为变化，不能通过新增
   行为字段排除或按 operation id 打补丁来制造等价。

## 3. 其余逐项核验

| 检查项 | 结论 | 独立证据摘要 |
|---|---|---|
| public 未消费导出豁免 | PASS | `catalog.py:616-619` 只豁免 `public=True`；现有负例之外，另构造“未消费 public validator 依赖未消费 private resource”，编译仍以 `component_unused` 拒绝 private resource，豁免不能遮蔽私有死组件。 |
| 工具唯一注册、Operation 最小授权 | PASS | 通用文件工具只有 builtin 的 7 个实现注册；对 6 插件组合逐 Agent 比对，`permission_template.tools` 与其显式 `executor.tools` 的完全限定集合相等，没有公共注册即自动授权。 |
| Schema/codec/project schema 所有权 | PASS | JSON/opaque codec、通用科研 Schema 由 general 单一提供；TCAD `project_schema` 单一公开提供，InGaAs 通过跨插件 `ComponentRef` 复用；未发现重复实现注册。 |
| 可选 figure 插件 | **FAIL** | 未安装时目录无三项能力，安装后恰有单入口和三项 Operation；但独立审查不在 bundle admission/parentage 中，故纵向闭环不成立，详见 B1。 |
| TCAD transport/debug/resource 合同 | PASS | runtime 只按所选 transport 惰性导入 command 或 socket；debug bridge 复用同一 adapter 的 prepare/submit/status/cancel/collect 路径；工程输出/资源类型复用 execution-control 合同。 |
| 默认面与 Hardened | PASS | 普通启动未加载 hardened、portable、远程/可选 TCAD 模块；显式 Hardened 纯 MCP Operation 实测可用；注册表 `SEC-002` 仍为 `known_issue`（`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml:162-167`），没有被测试数量升级。 |
| 盲插件 | PASS | 干净安装 fixture 仅用一个 `scidiscovery.plugins` 入口即可编译并真实调用 CSV 工具；core/Root/UI/调度器无 `blind_csv` 针对性分支。 |
| M3 等价测试 | PASS（但不覆盖 B1） | 20 个保留 transform 严查输出 bytes/media/schema/parents、幂等、冲突/revision 和 9 个 guards；只递归排除 `operation_digest`、`operation_invocation_fingerprint`、`request_fingerprint`，并单独比较 catalog transform 集合/差异，排除项仅是所有权重编译派生身份。 |
| 隐式扩权、重复注册、默认污染、过度设计 | 除 B1 外 PASS | 未发现第二注册表、转发表、插件私有调度路径或默认可选模块污染；B1 应在既有声明与 guard 中最小修复，不能新增治理层。 |

公共组件拆出、单编译事务、按需加载和盲插件均符合奥卡姆剃刀及通用 AI 科学家插件目标；然而 B1
恰好表明“同入口共置”尚未等价于“科学证据生命周期闭合”。因此整体不能给 PASS。

## 4. 聚焦测试

在 WSL 资源限制下串行执行最小可信集合：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
pytest -q -p no:cacheprovider \
  tests/operations/test_m5_plugin_ownership_and_default_surface.py \
  tests/operations/test_catalog_negative_cases.py::test_unused_missing_and_wrong_kind_components_are_closed \
  tests/operations/test_catalog_negative_cases.py::test_agent_authority_cannot_gain_undeclared_or_unbounded_capabilities \
  tests/operations/test_catalog_negative_cases.py::test_cross_plugin_components_require_dependency_and_public_export \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_domain_wheel_matrix_has_exact_plugin_ownership \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_domain_tools_execute_the_packaged_implementations \
  tests/operations/test_l4_local_tcad.py::test_local_tcad_author_debug_and_independent_review_share_one_operation_path \
  tests/operations/test_l5_hardened_run_backend.py::test_hardened_transport_completes_the_same_run_without_task_science \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/operations/test_r5_general_plugin_split.py \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_previews_core_only_and_explicit_tcad_paths \
  tests/artifact_agent/test_deploy_scripts.py::test_curve_figure_capability_is_plugin_owned_not_a_platform_skill \
  tests/artifact_agent/test_platform_configuration.py::test_codex_hardened_profile_remains_explicitly_compilable
```

结果：`30 passed in 82.94s`；`/usr/bin/time -v` 报告峰值 RSS `103816 KB`、swap `0`、退出码 `0`，
没有超时或卡住。按审查要求没有重复实现者声称的 233 项全量套件。聚焦测试全绿与 B1 的真实 Root
负例可同时成立，因为当前测试没有断言 bundle 必须携带审查结果。

## 5. 33 项约束与阶段结论

注册表仍为 33 个唯一编号：7 项 `conformant`、25 项 `pending_review`、1 项 `known_issue`；本轮没有
把任何 pending 或 `SEC-002` 自动升级。M5 其余改动未见 AUTH、PLG、SEC、MIG、RES 等边界退化，
但 B1 未满足 EVD/ROLE 的本阶段语义门，因此不能声称 33 项矩阵整体无退化。

最终结论为 **FAIL**：M5 不放行 M6，R5-M 更未完成。返修应只闭合 figure 审查消费关系并增加真实
Root 正负例；不得借机增加注册表、兼容层、隐式权限或针对 operation id 的补丁。
