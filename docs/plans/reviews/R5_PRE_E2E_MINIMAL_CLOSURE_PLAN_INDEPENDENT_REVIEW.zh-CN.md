# R5 端到端前最小闭合计划独立审查

日期：2026-09-04  
审查对象：`docs/plans/R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md` 当前工作区版本  
审查基线：工作区源码、插件、测试、部署脚本、33 项约束矩阵和计划索引；仓库提交基点为 `404aeb14c6eb`，但本结论针对未提交的当前工作树，不继承历史审查 verdict。  
结论：**FAIL**  
阻断项：**2**  

## 1. 总结

计划识别的九项现场缺陷均有当前实现证据，E0—E6 的范围总体克制：它没有要求给 Agent 增加集合提交、没有增加固定科研 DAG、没有重建重型控制面，也保留了 OperationSpec 单一能力入口、Agent 单主结果、Transform 多输出、文件交接、独立审查、最小上下文投影和 UI 人工决定等既定边界。

但计划当前描述的四个图证据 Operation 不能组合成其自己要求的“图证据→通用 Intake→资格”闭环，而且没有为完整图证据族给出一个能通过现有编译器的独立审查边。因此不能进入实施。两项都只需修改图插件内的 Operation 拓扑，不需要修改核心端口类型、Run 生命周期、调度器或资格体系。

## 2. 阻断项

### B1：图证据产物无法按 E5 的声明进入通用 Intake 提取

**事实。** E5 要求把 PDF、通过审查的 `CurveBundle` 和必要审计共同作为新通用 Intake 的冻结来源（计划第 245—246 行）。但通用 `science.evidence.extract.v1` 只有一个 `source_material` 输入，Schema 固定为 `opaque`（`src/scidiscovery/general_science_agent_operations.py:361-393`）；其独立审查者的 `source_material` 同样固定为 `opaque`（同文件第 318—359 行）。当前调用器对非通配端口要求 Artifact Schema 精确相等（`src/scidiscovery/operations/invoke.py:264-278`）。现有打包 Transform 输出的是 `scidiscovery.curve-bundle.v1` 和规范化审计，而图审查输出的是 `scidiscovery.evidence-audit.v1`（`plugins/curve_score/curve_score/operation_transforms.py:491-508`；`plugins/curve_score/curve_score/figure_science_operations.py:419-437`），均不能绑定到 `opaque` 端口。

把通用端口改为任意 Schema 不是最小修复：通配端口只允许 `handoff_only + evidence_inventory`（`src/scidiscovery/operations/spec.py:101-119`），无法向提取 Agent 暴露完整内容；让核心枚举曲线插件 Schema 又违反 PLG-001（`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml:144-149`）。

**影响。** 按当前 E1 完成四个 Operation 后，E5 第 5 步仍会在 preflight 因 Schema 不匹配而停止，通用资格 projector 也无法把曲线证据族识别为该 Intake 的精确 producer family/frozen sources。

**最小修正。** 在图插件内保留一个**单主输出**的图证据 Intake Agent（应使用新版本 operation id，避免旧 v1 语义漂移）：它精确消费 PDF、类型化请求、manifest、validation report、panels、overlays 和 tables，只输出 `ScientificIntake`。通用 `science.intake.split.v1` 和 `science.evidence.qualify.v1` 随后照常消费这个 Intake 及其精确审计。不要把 `CurveBundle` 反向塞进通用 `opaque` 来源端口；`CurveBundle` 是审计后供实验/评分使用的确定性派生物，不是为绕过端口类型而制造的输入容器。

### B2：计划没有形成可编译、可跟随的完整独立审查边

**事实。** 计划把物化 Transform 和图审查 Agent 分列为两个 Operation（计划第 76—87、157—163 行），并要求端到端中每个科学生产者都经精确 `review_edge`（第 271—273 行），但没有声明 ReviewSpec 应挂在哪个生产 Operation。现有编译器要求一个 review edge 的 `subject_outputs` 全部能汇入审查者的**同一个**输入端口，而且 Schema、媒体类型、codec、Schema resource 和基数必须兼容（`src/scidiscovery/operations/catalog.py:494-567`）。物化 Transform 的 manifest、图像、CSV 和报告是异构输出，不可能作为一组 subject outputs 直接汇入一个输入端口。

当前旧实现之所以能编译，是因为 review edge 只把旧提取 Agent 的单个 `scientific_intake` 输出映射到审查者的 `scientific_intake` 端口，而其余附件作为审查者的其他显式输入绑定（`plugins/curve_score/curve_score/figure_science_operations.py:395-425,438-464`）。删掉该 Intake 后，计划没有给出等价边。

**影响。** 即使审查 Operation 可以被手工选择，目录也没有声明“哪个精确生产结果必须由哪个独立 Operation 审查”的编译权威；这不满足计划自己的 E6 门，也不满足角色合同一致和独立审查边界。

**最小修正。** 与 B1 合并闭合：把 `ReviewSpec` 挂在新增的单输出图证据 Intake Agent 上，`subject_outputs=("scientific_intake",)`，映射到图审查 Agent 的 `scientific_intake` 输入；图审查 Agent 的其余必需端口精确绑定同一 PDF、请求和完整物化输出族。打包 Transform 的 guard 继续要求这份通过审查的精确 intake/audit/family。这样保留 Agent 单主结果与 Transform 多输出，且无需扩展 review graph 编译器。

## 3. 对现有缺陷账本的核验

计划列出的阻断不是臆测：

- 旧图提取 Agent 的五类集合输出位于 `plugins/curve_score/curve_score/figure_science_operations.py:327-365,438-464`；Local 后端明确拒绝任何 Agent collection output（`src/scidiscovery/artifact_agent/service/local_workspace.py:97-109`），Root 因而将它标成 unavailable（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:96-106`），对应回归见 `tests/operations/test_m2_optional_figure_plugin.py:44-54,87-100`。
- `figure_request` 在 OperationSpec 中仍是 `opaque`，真实字段只在 Pydantic 类型中（`plugins/curve_score/curve_score/figure_science_operations.py:445-451`；`plugins/curve_score/curve_score/figure_digitization.py:38-74`）。
- 当前提取器仅逐列按颜色匹配，遇同列断裂即失败，并把全部成功点标成 observed/eligible（`plugins/curve_score/curve_score/figure_digitization.py:123-169,172-207`）；manifest 又固定 matched、confidence 1.0、qualified（同文件第 268—337 行）。计划提出的 FIGURE-FIDELITY-001 因此真实。
- Schema 已能表达 PDF provenance、matched/unresolved、共享遮挡和图级 unresolved（`plugins/curve_score/curve_score/figure_evidence.py:46-67,97-103,132-166,257-268`），说明 E2 应修算法和请求契约，无需新建通用科学实体。
- Approval preflight 只做绑定和本地 Run 准备（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:168-179`），projector 直到 invoke 才执行（同文件第 181—220、326—378 行）；现有测试也明确表现为 preflight 通过、invoke 才报 `approval_projector_failed`（`tests/operations/test_m2_parameter_package.py:459-512,537-550`）。
- 通用资格页面把每个 JSON subject 作为根 `json_tree` 展示（`src/scidiscovery/general_science_components.py:297-322`），UI-READ-002 有源码依据。
- Fig.4 profile 当前确实遗漏可选图插件（`deploy/apply_ingaas_fig4_profile.sh:4-8`）；重装器已有显式环境透传列表（`deploy/reinstall.sh:62-86`），所以 E4 以独立审查和真实安装验证收口、而非继续重写部署，是合理范围。

因此，缺陷清单对当前已知现场问题基本完备；真正遗漏的是上述两项**目标拓扑自身的不可组合性**。

## 4. 最小性与 33 项约束

除 B1/B2 外，E0—E6 符合当前架构方向：

- OperationSpec 仍是能力、工具、输入输出、review 和 approval 的唯一编译入口；插件保持一个 `PluginDefinition` 注册入口（`plugins/curve_figure_evidence/curve_figure_evidence/plugin.py:35-50`）。
- Agent 只提交一个主结果，异构集合由确定性 Transform 产生；现有调用器已经按输出端口和基数校验每项（`src/scidiscovery/operations/invoke.py:241-263,296-329`），不需要 Agent 集合协议。
- E3 复用同一只读 projector 准备函数，不增加第二套 validator、审批状态或 UI Schema；这正面修复 TOP-002 和 UI-001/HIL-002 的已记录缺口（`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml:78-83,114-119,180-190`）。
- E4/E5 要求安装态目录、精确 agent type、关闭父历史继承、真实工具调用、sealed output 和人工 UI 决定，符合 AUTH-003、ROLE-001/002、HIL-001、PLG-001/002。SEC-002 继续如实为 trusted-local 软隔离 known issue，不应借本轮升级为强沙箱（约束文件第 156—167 行）。
- 计划明确说明长链是验收范围而非固定 DAG，运行时仍由调度 Agent 从 public 目录依据当前矛盾选择行为（计划第 264、269—274 行），没有引入阶段状态机。

计划索引也把本文标为当前唯一活动闭合计划且尚待独立审查（`docs/plans/README.md:19-22`），状态一致。

## 5. Fig.4 科学保真度门

门的方向足以防止把遮挡或身份不明数据冒充为已资格证据：计划要求逐序列/逐点 eligibility、共享覆盖默认不可用于被遮挡曲线、部分序列可用且全图仍可 unresolved、来源哈希和 overlay 复核，并包含伪造 eligible、同色坐标轴、身份重叠及缺源图等负例（计划第 110—124、172—188 行）。历史冻结判据也明确记录了 InAlAs 589 行、可见率 0.727160、最大空档 55 px 且 unresolved，以及 InGaAs 806 行、可见率 0.995062、最大空档 2 px（`docs/SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md:81-117`）。

这里有一项应在 E2 测试说明中澄清但不单列阻断：当前 v2 normalizer 为审计可追溯性会保留 observed points，同时通过 `availability`、`valid_intervals` 和 `exclusions` 限制定量使用（`plugins/curve_score/curve_score/figure_evidence_normalizer.py:172-267`）；评分路径会失败关闭不可用序列及跨空档域（`plugins/curve_score/curve_score/schema.py:1100-1151`）。因此“bundle 只接收允许的点”不应被实现成删除审计所需的 observed points，验收应表述为“任何评分或插值均不得使用 ineligible/unresolved 区间”，并增加一个跨未决内部空档的评分负例。

## 6. 部署、真实 Agent 和开跑门

E4—E6 已覆盖本轮必要的发布与真实入口证据：干净 wheel、真实安装脚本、服务/UI/Codex 配置、profile 组合、三目录视图、TCAD capability、真实 Agent 工具投影与调用、sealed output、父链、负控和人工浏览器决定。没有发现需要在开跑前新增服务、注册表、后台 Worker 或通用工具协议的理由。

建议在 E4 验收记录中显式保存 `pdfimages/pdftoppm` 的实际路径和版本、embedded-image 产物摘要，以及重装后 Worker 所见工具名；这些属于既有验收证据的具体化，不是新阻断。

## 7. 非阻断延期项

以下不得借本轮扩大范围：

1. trusted-local 的原生跨目录技术隔离（SEC-002）；继续标记 known issue。
2. 通用 Agent collection 输出和集合恢复协议；本轮由 Transform 多输出解决。
3. marker、拟合段、箱线图及任意论文图通用化；E2 只恢复 Fig.4 连续线所需能力。
4. 审批 UI 的全站视觉重做；本轮只修通用证据资格 projector 的首屏信息层级。
5. 哈希碰撞、旧代际兼容、历史 Run 清理、第二 current、高可靠远程恢复与真实远端失联演练。
6. 三领域通用性或相对单 Agent 的统计优势；这次门只授权真实 Fig.4 纵向闭环。

## 8. 复核证据

在当前工作树串行执行：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m2_parameter_package.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：**54 passed**，无并行测试。该结果确认现有行为和账本事实，不会消除 B1/B2，因为两项是待实施拓扑的合同缺口。

## 9. 放行条件

只有在计划文本完成以下两处最小修订并重新独立审查后，才可 PASS：

1. 明确增加或重构一个图插件内的单输出 `ScientificIntake` 生产 Operation，使完整图证据族能进入现有 split/qualification，而不修改通用 `opaque` 输入规则；
2. 明确把可编译的 `ReviewSpec` 挂在该单输出生产者上，并让审查者其余端口精确绑定同一物化族，打包 guard 再验证同一通过审查的 family。

当前结论只阻止 E1 开始，不否定缺陷账本、E0 冻结材料或已经完成的历史闭环。
