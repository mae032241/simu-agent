# 校验修订第三次独立审查

> 后继记录：本报告保留修复前事实；其后源码修复与验证见 [R3 修复完成记录](REVIEW_R3_FIX_COMPLETION.zh-CN.md)，[最终独立复审通过](INDEPENDENT_REVIEW_R3_FIX.zh-CN.md)。未完成生产 VM 复测。

2026-09-13。**结论：未通过。发现一项 P2 新增误阻断，另有一项非阻断 P3 诊断定位缺陷。**

## 范围和独立性

按用户要求新开不继承父会话历史的独立审查者。核对 `REVIEW_R2_FIX_BASELINE.json` 与 `REVIEW_R2_FIX_VERIFICATION.json` 的5个生产文件、4个测试文件及最终摘要；同时追查前轮 R1/R4 修复所依赖的8文件冻结边界。审查者只读，没有运行测试、修改文件或操作生产实例。主代理按其提出的最小场景统一执行隔离 MCP 对照，并回传实际结果供独立判断。

当前 git HEAD 的累计工作树修改没有被冒充为这5个文件的精确增量。测试证据不等于审查结论。日志接口另由主代理核查，见 [TCAD 日志专题](TCAD_LOG_VISIBILITY_AUDIT.zh-CN.md)，不归属于此独立审查者的结论。

## P2：同一计算记录的两种合法表示被当成冲突来源

位置：`src/scidiscovery/artifact_agent/service/analysis_artifacts.py:44` 与64行；TCAD 消费入口 `plugins/tcad_artifact/tcad_artifact/result_analysis.py:438`。

同一次注册曲线工具返回的记录，同时以 `calculation_records:score` 和返回的 `calculation_ref` 被同一 source_key 引用时，helper 按两个定位字符串生成不同身份，在原有计算收据校验之前拒绝。

既有 `CalculationRecord` 在 `schema/layered_diagnosis.py:114` 明确将 calculation_ref 定义为不参与计算身份的传输提示；`retain_calculation` 用同一个记录创建保存文件。这不是仅凭相同名称或内容猜测同源，而是一次受控工具返回的两种受支持表示。

实际对照：

| 同一工具结果的引用方式 | 当前源码 |
| --- | --- |
| 仅内联记录定位 | completed |
| 仅保存文件定位，仍保留内联记录 | completed |
| 两种定位共同使用同一 source_key | rejected，`$.payload.evidence[2].source_key` 来源冲突 |

同一个 both 探针在本轮精确改前快照为 completed，故可确定为本轮新增回归。它阻止合法同源多引用，不能通过要求 Worker 拆科学引用键来掩盖。

最小修正方向：复用已有受控计算收据身份统一这两种表示，继续区分不同记录、原始输出与计算结果。不能重新校验输入准入，也不应新增来源登记表或仅按 record_key/相同字节合并不同对象。

证据：当前 `check-1789263834573631843.log`；改前快照 `check-1789264035222055978.log`，工作目录 `/tmp/scid-review-r2-before-ylaef485`。探针为 `review_r3_diagnostic_probe.py`。通用分析共用该 helper，本次动态对照覆盖 TCAD，未把静态共用关系冒充通用分析的动态验收。

## P3：缺口分支把 handoff 错误定位到 gap

位置：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:620`—631。

同一异常包装覆盖 gap.json 和 handoff.json 解析，却统一添加 `$.deck.gap` 前缀。合法 gap 配合空 handoff.summary，实际诊断为 `$.deck.gap.summary`；只修 handoff 后即可 completed。

这会把 Worker 引向错误文件。它是前轮相邻诊断修复留下的问题，不是本轮5文件新增回归，也不否定原 R4 plan_locator 的准确定位修复。最小方向是按真正发生错误的文件添加诊断前缀，不增加内容约束。

证据：`check-1789263834573631843.log`，同一 `review_r3_diagnostic_probe.py` 的 gap/handoff 对照。独立审查者将其定为非阻断 P3。

## 已闭合的原问题

- 原 R2 错误自动映射、原始输出与计算记录混用、可选定位行改变绑定解释已修正；不应因新发现否认这些实际改善。
- 工作区准备失败经持久化、语义名称绑定、invoke/status/list 公开可见；同请求读取旧 failed，显式修订建立新 Run。
- R1 被审对象引用投影和 R4 精确计划字段诊断仍有效。
- 未见本轮增量放松输入准入、精确 execution/case、历史收据、独立 review 或 approval 边界。

## 证据限制

独立审查者核对了原4探针、96/60两组回归及生命周期39通过、3项基线失败。失败断言后的步骤不能算已验证。

首次改前对照从当前仓库绝对路径加载探针，触发混合插件 ImportError，记录为 `check-1789263960976817420.log`；复制同字节探针到精确快照内部后正常运行，both 为 completed。前者属于测试路径问题，不作为产品缺陷证据。

本轮没有修改生产源码、部署、安装包验证、全量测试或真实求解器执行。当前审查不能作为部署通过记录。最终摘要和本轮检查集合见 `REVIEW_R3_VERIFICATION.json`。
