# R3 A 图证据单作者实现：独立静态审查

## 结论与边界

**结论：需修复后复审。发现 1 项 P1、1 项 P2。** 此结论只针对下表精确候选的 A 实现；不评价此前清理，也不沿用 R2 的 PASS。

审查时间：2026-09-24。审查者与实现者独立，按 `scid-cross-boundary-review` 跟踪源码。候选基线为 HEAD `5871a64e3585e00f98f5357aadef959d343758c5` 加此前清理差异，再加 A；已阅读 `/tmp/scid-r3-start.patch` 区分已有清理。

未运行任何测试、pytest collection、项目动态导入、catalog 编译、安装、构建或 solver。只读源码、文本与 stdlib AST/哈希检查；本报告不授予运行、安装或部署资格。

## 发现

### A-R1 / P1：部分保存后更换输入别名恢复，会重复注册已收养成员，使选定族无法封存

**主要位置：**[figure_worker_tool.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py) 第 179–184、210–236 行，尤其第 223–226 行。

可达场景：原 Run 的 `worker_curve_figure_save` 已注册部分附件，但在写入 `selected_family/selection.json` 前中断。恢复任务绑定相同 `paper_source` Artifact、使用另一个合法 `source_name`；完成新 preview 后以这个名字再次 save。

实际链路：

1. [runs.py](../../../src/scidiscovery/artifact_agent/service/runs.py) 第 1598–1619 行的恢复校验以 Artifact refs 和 operation digest 为依据；输入别名不构成科学身份。`adopt_tool_evidence` 按原件身份匹配，并原样收养旧收据（[tool_evidence.py](../../../src/scidiscovery/artifact_agent/service/tool_evidence.py) 第 637–650、666–683 行）。
2. `_save` 的完整选定族复用分支只在 selection 已存在时生效。对于部分保存，它重新遍历所有文件，以新 `request.name` 填写 `derived_from`。
3. `accept_tool_evidence` 将 `derived_from` 别名加入 metadata，metadata 又参与幂等 key（同文件第 389–409 行）。因此同一个 data_item、同样字节和原件，在新别名下获得新的注册；旧收养成员仍留在当前 Run。
4. 新 selection 只列本次循环返回的成员。随后 [figure_family.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_family.py) 第 62–66 行要求 selection 精确覆盖全部 records，因额外旧成员拒绝。若附件接近数量上限，也可能更早在 evidence budget 处失败。再次 save 无法清除此状态；已有 selection 分支同样会触发完整性拒绝。

**影响：**一个原件和提取请求都未变化的合法恢复，变成不能完成的候选，违反声明的部分保存恢复/幂等语义。安全拒绝仍有效，但恢复路径断裂。

**建议：**部分保存重入时，先以精确原件、request digest、data_item、字节身份核对并复用已收养记录，只补缺件；不要因当前别名变化重写原收据，也不要放松完整族校验。后续获准运行时覆盖“保存中断、别名变化、收养、补齐、finalize、audit”的真实控制服务路径。现有 `_saved_family` 测试 helper 按 data_item 去重，与生产 key 不同，不能代表这个边界。

### A-R2 / P2：文字修订合同没有提供原选定族，迫使修订者重新提取且无法精确保留未被质疑的证据

**主要位置：**[figure_science_operations.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py) 第 167–180 行；[figure_family.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_family.py) 第 123–132 行。

可达场景：独立 audit 只要求收紧 Intake 的一句结论或补写局限；原校准、曲线和来源均无需修改。调用新作者的 `prior_draft`、`change_request` 修订入口。

合同只交付原 paper、prior Intake 和 audit，没有原 `figure_provenance`、原 request 或其附件。Intake 中的旧 `tool_evidence_*` 是旧 Run 的别名，不是原请求。通用 [reference_tools.py](../../../src/scidiscovery/reference_tools.py) 第 23–33 行也没有从 Intake 读取其图证据族的规则。完成校验又要求当前工具快照中存在一个显式保存的完整族，因此仅编辑 prior Intake 不能完成；作者必须重新描述/提取原图，才能生成新的族。

**影响：**提示要求保留未被质疑内容，但实际合同无法让新作者读取并复用原精确请求和文件。文字修订被迫变为再次数字化，可能产生额外数据变化，并恢复了本轮要消除的上下文重建工作。

**建议：**在同一新版作者合同内补齐精确 prior family 的受控读取/复用路径，绑定其 prior Intake 和指定 review；文字修订沿用证据身份，新 Intake 获得新身份并重新审查。需要重提取时显式形成新族。无需恢复旧双作者入口或兼容桥。

## 已追踪的边界与未发现的新阻断

- 插件单一注册入口声明新版 author、audit 和 bundle；新 author 的角色与工具包含 PDF 文本定位、原图恢复、preview、save 和视图能力。旧三个小步骤未作为生产 Operation 注册；内部 normalizer 的 v2 profile 常量不等于旧公开入口。
- preview 由 LocalWorker router 创建/结束受控尝试；ready save 要求相同 materialized request digest 的 completed preview。保存附件走 `accept_tool_evidence`，不是把工作区文件冒充封存证据。
- finalization 从控制服务读取快照和 CAS 字节。选定族检查 source、request、成员身份/字节/大小、manifest 和 deterministic report；最终 Intake 的 parent 包含该 control manifest。
- audit 准入同时检查选定族内容与 author/proof parentage；bundle 要求新 audit Operation、当前 Intake 及同一族的父链和 passing verdict。源码检查未发现旧 Intake audit 可直接替代新 Intake audit 的路径。
- 完整 save 已写 selection 后的同请求重入读取旧 CAS 记录，不重新注册；未发现与 A-R1 相同的问题。A-R1 特指 selection 尚未写完的部分保存。
- unresolved 请求只封存已知请求字段；可进入忠实性审查，不能产生定量 bundle。PDF 文本/原嵌入图恢复工具仍在新作者合同中可达；此处仅确认静态路由存在。

这些检查不是生产验证。真实 catalog 编译、Worker 调用和附件回收、PDF 依赖、独立身份运行约束、真实恢复以及资源消耗均未运行验证；不能写成这些场景已经通过。

## 精确候选

19 个文件哈希均与交接候选相符，候选中的 Python 文件 AST 可解析。交接清单 SHA-256：`59d24c1b6181362ca1b03511ceb7584990e4ec228ddbadf48addc7f65eeb9357`。

| 文件 | SHA-256 |
| --- | --- |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py` | `e31578ee3db8ca4fb6ec5991d79b63d634bb9221d37d804b16853dfd67b13418` |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_family.py` | `d76b129e507f3025d4078b8e5c7023c97dafc68c4031108966dad6f43f49fc10` |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py` | `6e13b8cdb79c337a1fdb5d64e0082a78759154208b0edad20f11bc2d37f97f46` |
| `plugins/curve_figure_evidence/curve_figure_evidence/operation_transforms.py` | `112df36f098d0dc0af6899f25bd8d7563273512ff34a00749aceb025416c2099` |
| `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py` | `e92377276ffb72b0282bd40eca33e60b4867a8762bf184aa4219237d2fbcea4e` |
| `plugins/curve_figure_evidence/README.md` | `ad20af26a92b0682aaa01268ef5ebf0b89da0ddc9854f00584514e8a52795ab7` |
| `plugins/curve_figure_evidence/README.zh-CN.md` | `60ad6fa10b1304e8f75092d3f1f5a38bfd42d9c040f316f7034331885ab4a9da` |
| `plugins/curve_score/README.md` | `63cc5df1352fcd06e3b1a0166386172a839a5a6a8e273772358ab844f0201d33` |
| `plugins/curve_score/README.zh-CN.md` | `b43252f87d2681e6f92b5333e5f70d9c2a00797cff7b6bd22aafce41c46ba079` |
| `src/scidiscovery/artifact_agent/operation_tool_context.py` | `fd30b8abfa9b065eb1c79eb6b48375106fc2d25761b7fb2f3d1d40fd88234ff3` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` | `dde03ad1b78c0deea9de265ebf97204910a0ab6b210f001e8656c579874b8eb2` |
| `src/scidiscovery/artifact_agent/service/tool_evidence.py` | `d70a970ca86f759978b24d5214c78af9b2bc171cb9504dccdd7d6f69b41b8e5a` |
| `tests/operations/test_catalog_installed_entrypoint.py` | `f692a6db33a377d593fa1428fea66fe1d1295847c111359d8b5f626e93aee16f` |
| `tests/operations/test_figure_semantic_compilation.py` | `ec5130a0de4b8dbf498ca8dac05623033bed8dfcf0b5a7633bc8060944971184` |
| `tests/operations/test_h2b_domain_boundaries.py` | `39af0695c99cb65586ff3a7c656076bd1807ca67f2efa0ccf20ed11e2590f4b8` |
| `tests/operations/test_m2_optional_figure_plugin.py` | `4f2c3c5ce61c9f9da3729dd75b3c17a55e735fc8cb094d7c593aa196ed5e2031` |
| `tests/operations/test_m6c_producer_topology_removal.py` | `cb8579bd2f5eda6bd5158252630f68f4ecac16b83411df7f69fab76f47f163ce` |
| `tests/operations/test_minimal_figure_extraction.py` | `0b8ff0c77e5accea87a17fc0ea45e12f669cb696ce7c2ca649507f804358994f` |
| `scripts/run_root_invoke_ab.py` | `ad7cd714fa2d7e30f73ab40650aaa483c818eae3c5b314dd0803157967789084` |
