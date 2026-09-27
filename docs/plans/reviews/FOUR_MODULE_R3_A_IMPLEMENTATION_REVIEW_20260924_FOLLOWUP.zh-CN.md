# R3 A 实现独立复审（第一次修复）

## 结论

**需修复后复审：原 A-R1/P1 和 A-R2/P2 的代码路径已静态闭合；新增发现 A-R3/P1，当前可选 figure 插件的 catalog 编译会遇到语义合同身份不匹配。** 未执行 catalog 编译；该结论由声明和编译器的确定性检查直接推出。

审查日期：2026-09-24。本次仅复核原发现、其恢复/修订路径和新增 `direct_revision_ports` 边界，未重做全仓审查。

[原审查](FOUR_MODULE_R3_A_IMPLEMENTATION_REVIEW_20260924.zh-CN.md)保持原文，SHA-256 为 `5b86b9c92b4e6994959b852932f73f760b758b9110634c6aad0e2b36c46da042`。本轮候选清单 `/tmp/scid-r3-a-candidate-fixed.json` 的 SHA-256 为 `e73d96cfde7a39fdddc17965eb46e320478d7d945a8ac1377608a768f478861d`，20 文件身份均匹配，16 个 Python 文件 AST 可解析。精确文件身份列于文末。

## 原发现的处置

### A-R1：静态确认修复

[figure_worker_tool.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py) 第 225–250 行先检查全部已收养部分成员的 data_item、原件、request digest、algorithm、media、size、digest 和原始字节，再复用原记录，仅注册缺件。恢复使用新 source_name 时，不再将旧成员重新交给包含别名的幂等 key 生成路径；selection 包含原记录与新增记录的完整集合。重复成员、额外文件或字节变化仍拒绝。

这是代码路径闭合结论，未运行真实恢复/控制服务测试。

### A-R2：静态确认修复

[figure_science_operations.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py) 第 174–196 行提供 prior provenance/family 输入和 revision validator；[figure_family.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_family.py) 第 159–177 行要求它们属于 exact prior Intake，且指定的非通过 audit 覆盖 prior、原件与全部族成员。

`worker_curve_figure_reuse` 校验完整族并调用受控收养，不调用数字化算法；[tool_evidence.py](../../../src/scidiscovery/artifact_agent/service/tool_evidence.py) 第 449–506 行检查 manifest 属于当前实例内已完成的同 Operation 生产者，成员和原件均显式绑定、字节/类型/额度一致、别名无冲突，再原样收养收据。新的 Intake 与控制 manifest 仍使用新 Run 身份；audit/bundle 的精确父链要求不变，旧 audit 不能作为新 Intake 的通过审查。

`_reuse` 拒绝与已保存的其他族混合；revision guard 加完整族 validator 拒绝其他 prior 的 proof、错 review、缺件和多件。这是合同和路径静态结论，未运行 author→reuse→finalize→新 audit。

## 新发现

### A-R3 / P1：作者主输出的 validator 注册资源与其 semantic contract 不一致，导致插件不能编译

**主要位置：**[figure_science_operations.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py) 第 154–159 行，尤其第 157–158 行。

`scientific_intake` 输出声明：

- payload validator = `general_science:intake_validator`；
- semantic contract = `curve_figure_evidence:figure_semantic_contract`。

然而 [general_science_components.py](../../../src/scidiscovery/general_science_components.py) 第 432–454 行只为该 validator 声明 `general_science:intake_semantic_contract` 资源。插件本地 `figure_intake_context` 声明了 figure 合同，不能替另一独立 validator 补足其 resources。

真实编译边界 [catalog.py](../../../src/scidiscovery/operations/catalog.py) 第 497–501 行对每个主输出的 payload/context validator 分别检查：输出 semantic contract 的精确 qualified key 必须出现在该 validator 的资源列表。上述两个 key 不相等，必然触发 `validator_semantic_contract_mismatch`。这发生在可选插件 catalog 构造期间，三个新 Operation 都无法通过该安装态对外服务；无需进入 save 或 revision 才触发。

**修复建议：**在 figure 插件内注册引用 figure semantic contract 的 Intake payload validator，复用既有 ScientificIntake 验证实现；同时保持 rule_id 和 context validator 资源一致。不要删除或放宽全局编译器检查。静态复核应比较 validator 的精确 resources，而不只确认 Python target 存在。解除禁测后再做真实可选插件编译/入口验证。

该缺陷也存在于上轮候选，本轮在核对 direct revision 的真实编译入口时发现；上轮审查没有覆盖到这个精确 resource-key 对应关系。

## 通用 direct_revision 变化

[operation_contract.py](../../../src/scidiscovery/operation_contract.py) 第 317–385 行只将受控 `tool_evidence` 集合加入允许的附属输出；仍要求单一主输出、唯一 revision_base、匹配 schema/media/codec/resource、正确的两端口修订 cohort、独立 reviewer、修订次数与 progress fingerprint。

本次检查未发现这一放开本身赋予 Worker 任意集合写入权：catalog 第 483–487 行要求集合与已注册工具声明完全对应；`tool_evidence_ports` 再限制允许名称；RunService 第 175–176 行拒绝未获该能力的集合；`run_outputs.py` 第 88–100 行仍只接受主 result 和控制快照，不接收 Worker 自写附件族。具体 prior/family 权限仍由上述 A 的准入与收养检查约束。

## 验证限制

所有操作串行。未执行测试、pytest collection、动态项目导入、catalog 编译、安装、构建、solver 或部署。没有修改作者代码，原审查文件未改；本报告不等于运行通过或运行资格。

## 候选身份

| 文件 | SHA-256 |
| --- | --- |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py` | `da644fd072847390ce55155f003b417c17ff446e9182880f2fdc891247fe795f` |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_family.py` | `27f467379d6e8f7eec530fc8f63cf76068d5c6d86d732e0e3c6714f58a5ce7cd` |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py` | `582dc73ae4a192ef43fb8ee05ba60e0ae55524d7f9fc756fdf7b60819aecfba7` |
| `plugins/curve_figure_evidence/curve_figure_evidence/operation_transforms.py` | `112df36f098d0dc0af6899f25bd8d7563273512ff34a00749aceb025416c2099` |
| `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py` | `e92377276ffb72b0282bd40eca33e60b4867a8762bf184aa4219237d2fbcea4e` |
| `plugins/curve_figure_evidence/README.md` | `8c3fd79611352447fac04e2d635ea6373c78c444058c21ebc1771963c627f27c` |
| `plugins/curve_figure_evidence/README.zh-CN.md` | `c08d0cea8554b3de963d90fd2d2976bd5c44074fec30d3d864b4552de88cd4d2` |
| `plugins/curve_score/README.md` | `63cc5df1352fcd06e3b1a0166386172a839a5a6a8e273772358ab844f0201d33` |
| `plugins/curve_score/README.zh-CN.md` | `b43252f87d2681e6f92b5333e5f70d9c2a00797cff7b6bd22aafce41c46ba079` |
| `src/scidiscovery/artifact_agent/operation_tool_context.py` | `8d98648e58d704b96dbdede36d339bde6dbaf98a86fdb71ff66ca7fd4e88537a` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` | `c1d534eda9eda0ec7414be54e059317db993a86080326254d0dd498fb5e2b734` |
| `src/scidiscovery/artifact_agent/service/tool_evidence.py` | `af049499fbbd7c329481cc38c1f86c47e6b903a67da4a91a04f25656cbfc8c6f` |
| `tests/operations/test_catalog_installed_entrypoint.py` | `f692a6db33a377d593fa1428fea66fe1d1295847c111359d8b5f626e93aee16f` |
| `tests/operations/test_figure_semantic_compilation.py` | `8cd1d961ebcef0e22900ef1ac4b83eee1392970bf0cb68a8522d84f1ae64a783` |
| `tests/operations/test_h2b_domain_boundaries.py` | `39af0695c99cb65586ff3a7c656076bd1807ca67f2efa0ccf20ed11e2590f4b8` |
| `tests/operations/test_m2_optional_figure_plugin.py` | `fdf8dffb69d024b86cbc0eb23a44d7de5925fa37c268dbb05e68fd6ae832c34d` |
| `tests/operations/test_m6c_producer_topology_removal.py` | `9550dc54bbd585acbcdf1caec331a936fb727297123f34d409100617d08bbfee` |
| `tests/operations/test_minimal_figure_extraction.py` | `e5180984efc317e5914564c9b86b5369bd15dff2e4be9e30543aa988bea7f0aa` |
| `scripts/run_root_invoke_ab.py` | `ad7cd714fa2d7e30f73ab40650aaa483c818eae3c5b314dd0803157967789084` |
| `src/scidiscovery/operation_contract.py` | `8638c8b560e5942a689523a3a5e1bd22bec696312969833913836eec4b17b46e` |

## 第二次修复的最小复核（2026-09-24）

**本节为最新处置：A-R3 静态关闭。结合上轮已关闭的 A-R1、A-R2，已报告的三项问题均完成静态修复复核；本次最小范围内未发现新问题。运行仍未验证。** 前文保留第一次修复候选的审查事实，不将其结论套用于新候选。

本轮精确候选 `/tmp/scid-r3-a-candidate-fixed2.json` SHA-256：`4ee3eb9c102f95be75669940da5b0215a4fff64611c543377224c117b3a28f37`。20 个文件身份匹配；相比前轮仅以下两文件变化，其余 18 文件哈希沿用前表：

| 文件 | 新 SHA-256 |
| --- | --- |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py` | `54a37d60d202509a71e2cf4ff6252dae189bfb3dacf2d03c2493fb0ebb4398f6` |
| `tests/operations/test_m2_optional_figure_plugin.py` | `e1ec67c28278a9302d79f82146d7051d58b6873916c945638b973f3beacd1266` |

复核依据：

- `figure_science_operations.py:126` 新增插件本地 `figure_intake_validator`，复用原 `Components.intake_validator` 实现，明确声明本地 `figure_semantic_contract` 资源。
- 第 158–160 行主输出改为本地 validator。payload 和 context validator 的 resources 现在都包含 `curve_figure_evidence:figure_semantic_contract`，与输出合同的精确 qualified key 相同；沿 `catalog.py:497–501` 的原检查条件不再出现 A-R3 的错配。
- 共通 Intake 验证实现和全局编译器拒绝规则未更改。原 `intake.internal_closure` 与 `curve.figure.evidence_binding` 规则仍与该合同对应。
- 独立用 stdlib AST 检查这两个资源引用关系、实现 target 和两份变更文件语法，核对全部候选哈希；同时阅读作者静态检查清单（SHA-256 `e5f41896e94a6692ed372462bc57f0664b2c331355e4da922d4b1d931702cd1f`）。没有以作者自述替代源码检查。

未运行测试、collection、动态导入、catalog 编译、安装或构建。这里只关闭已经定位的注册错配，不声称真实 catalog 已成功编译，不授予运行或部署资格。
