# R5 端到端前最小闭合计划第二轮独立复审

日期：2026-09-04  
复审对象：`docs/plans/R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md` 第二版候选计划  
首轮审查：`R5_PRE_E2E_MINIMAL_CLOSURE_PLAN_INDEPENDENT_REVIEW.zh-CN.md`  
结论：**PASS**  
阻断项：**0**  

## 1. 复审结论

首轮 B1、B2 已在方案层面完整关闭。修订没有要求改变通用 evidence extract 的 `opaque` 输入规则，没有扩展 Agent collection、review graph、Run 生命周期、调度器或资格系统，也没有新增注册入口。该计划可以进入 E0/E1 实施；本 PASS 只批准实施计划，不代表尚未编码的五个图证据 Operation 已经通过实现验收。

## 2. 首轮 B1：已关闭

修订后的拓扑新增 `science.evidence.extract.figure.v2`：它精确消费冻结来源、类型化请求和完整物化输出族，只产生一个 `scidiscovery.scientific-intake.v1` 主结果（计划第 72—102、168—177 行）。E5 随后直接对这份已审查 Intake 执行现有 split/qualification，并明确禁止把 `CurveBundle` 或 `EvidenceAudit` 绑定到通用 `science.evidence.extract.v1` 的 `opaque source_material`（计划第 255—268 行）。因此首轮发现的 Schema 不可组合路径已经删除，而不是被兼容层掩盖。

这条新路径与现有核心能够组合：

- `science.intake.split.v1` 精确接受 `ScientificIntake + EvidenceAudit`，输出 problem frame 和 foundation（`src/scidiscovery/general_science_control_operations.py:129-168`）。
- `science.evidence.qualify.v1` 以单个 Intake 为 `extraction_primary`，允许 producer sibling 为零，并用 `frozen_sources` 通配端口接收完整生产来源引用（同文件第 209—280 行）。该通配端口是 `handoff_only + evidence_inventory`，符合现有 InputPortSpec 限制，不向 Agent 创建新的任意内容入口（`src/scidiscovery/operations/spec.py:101-119`）。
- Agent producer family 会把单一 Run 输出登记为唯一 member，并把所有声明为 claim evidence/evidence inventory/cached excerpt 的精确输入登记为 evidence sources，同时保存编译 reviewer 身份和 subject outputs（`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:483-555`）。
- 资格 projector 已要求完整 frozen source 集合、编译 review edge 以及覆盖主项和所有来源的 passing audit（`src/scidiscovery/general_science_components.py:325-387`）。新图审查 Agent 显式绑定 Intake 和完整物化族，能够满足这一既有合同。

`CurveBundle` 现在只作为通过审查后的确定性派生物进入后续实验和评分，不再被伪装为通用原始来源。**B1 关闭。**

## 3. 首轮 B2：已关闭

计划已明确将 `ReviewSpec` 挂在单输出 `science.evidence.extract.figure.v2` 上，只把 `scientific_intake` 映射到图审查 Agent 的同名端口；冻结来源、请求、manifest、报告、panels、overlays 和 tables 作为审查者其余显式输入精确绑定（计划第 83—94、171—176、260—264 行）。

该定义满足当前编译器：producer subject 和 reviewer target 均为一个 `ScientificIntake`，可以使用同一通用 JSON codec、Schema resource、媒体类型及 1:1 基数；异构 Transform 输出不再被错误合并进同一个 reviewer port。编译器要求和兼容性检查见 `src/scidiscovery/operations/catalog.py:527-567`。当前图插件的 `_input/_output` 已经通过对 `ScientificIntake` 使用通用 codec、Schema resource、validator 和 semantic contract 展示了可复用边界（`plugins/curve_score/curve_score/figure_science_operations.py:225-313`）。

审查者仍是独立 public Agent，完整附件只是同一次审查的其他绑定；打包 Transform guard 再要求精确 Intake、audit、request、source、manifest、report 和 tables 一致（计划第 90—98、173—176 行）。这既建立了唯一编译审查权威，也没有要求修改 review graph。**B2 关闭。**

## 4. 复杂度与架构边界

修订仍是最小闭合：

1. Agent 均只有一个非集合主结果；异构附件只由已支持多输出的确定性 Transform 产生。计划明确禁止新增 Agent collection、数据库表、MCP 路由和恢复协议（计划第 100—102、179—185 行）。
2. 图像 Schema、算法、工具、prompt、guard 和 Operation 留在可选图插件内；唯一注册入口仍应是该插件的一个 `PluginDefinition`。当前入口位于 `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py:35-50`，计划明确不向核心加入图名、Schema 名或插件名分支（计划第 177 行）。
3. 核心新增预算仅为 preflight/invoke 共用的私有 approval projection helper；禁止公共 MCP、数据库状态和领域分支，并设定触及 Run、Scheduler、current、Execution 或三处以上核心模块即停止（计划第 314—324 行）。
4. E5 的串行步骤是安装态验收脚本，不是运行时固定科研 DAG。完整实验仍由调度 Agent根据当前矛盾从唯一 public 目录选择 Operation（计划第 286、291—300 行），符合 TOP-001。
5. 文件交接、最小上下文、真实 Worker 工具投影、关闭父历史继承、sealed output 和 UI 人工决定均保留；SEC-002 继续诚实标记 trusted-local 软隔离 known issue，没有借机扩张强沙箱（计划第 250—272、302—312 行；`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml:156-167`）。

未发现第二注册表、第二 current、第二任务生命周期、第二校验器或通用控制面扩张。

## 5. 科学与发布门复核

首轮提出的非阻断澄清也已吸收：E2 允许 CurveBundle 为审计保留带状态的 observed points，但禁止评分、插值或定量主张跨 ineligible/unresolved 区间，并要求内部空档评分失败负例（计划第 187—204 行）。这与当前 normalizer 的 `availability/valid_intervals/exclusions` 和评分失败关闭规则一致（`plugins/curve_score/curve_score/figure_evidence_normalizer.py:172-267`；`plugins/curve_score/curve_score/schema.py:1100-1151`）。

E4 也已要求保存 `pdfimages/pdftoppm` 路径、版本、恢复图像摘要和安装后 Worker 工具名，再以干净 wheel、真实重装、服务/UI/Codex 配置、三目录视图和 TCAD capability 作为发布证据（计划第 233—248 行）。E5 要求真实 Agent 调用、完整父链、错误请求/缺附件/换来源负例、独立审查和可读人工审批页；E6 再由未参与实现者作开跑审查（计划第 250—287 行）。没有发现本轮开跑门的新增遗漏。

## 6. 实施时必须兑现的验收点

以下是计划已有要求的实现核对项，不是新阻断：

- 新 v2 producer 与 reviewer 的 `ScientificIntake` 端口必须复用完全相同的 codec 和 Schema resource，使目录编译真实通过；
- v2 Intake 的 `context_sources` 必须覆盖它实际允许引用的完整物化输入端口，不能保留旧版仅含 `paper_source/figure_request` 的隐藏限制；
- qualification 的 `frozen_sources` 必须等于 v2 Run 记录的 evidence source refs，审计 Run 的 parents 必须覆盖 Intake 主项与这些来源；
- Fig.4 单次来源数必须保持在现有资格端口的 32 项上限内；如果实现意外产生更多附件，应先收敛附件，而不是扩核心上限；
- 旧 `science.evidence.extract.figure.v1` 必须退出可调度目录，不能与 v2 并存为第二生产路径。

这些内容均可在 E1/E5 的目录编译、preflight、真实 Run、错误绑定和资格 projector 测试中证明。

## 7. 复核证据

当前工作树串行执行：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m2_parameter_package.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：**54 passed in 9.66s**。约束矩阵实际包含 **33** 项。现有测试只确认当前事实基线；新拓扑仍须按 E1—E5 增加并通过相应实现测试。

最终判定：**PASS，阻断项 0；允许开始 E0/E1，不提前授权 E2 或完整端到端开跑。**
