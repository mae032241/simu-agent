# R3 B 六项整改：独立静态复审

## 结论与候选

**结论：REQUEST CHANGES。原 R3、R4、R5、R6 的具体缺陷静态关闭；R1、R2 已有实质修复，但仍各有一项 P1 可达缺陷。** 关闭表示所指出的代码断点已接通，不等于运行验证通过。

- 日期：2026-09-25。
- 前次报告：[2026-09-24 独立审查](FOUR_MODULE_R3_B_IMPLEMENTATION_REVIEW_20260924.zh-CN.md)。保留原报告，不覆盖其原候选结论。
- 本次作者候选：`/tmp/scid-r3-b-candidate-fixed.json`，52 文件；清单 SHA256：`69de1d8a03fe6266fb97ea331ff5fec6cc43759af1ae8f2bdc97c80caf35b367`。
- 审查者重算 52 文件 hash 全部匹配；其中 44 个 Python 文件通过 stdlib AST 解析。未执行项目导入、测试、pytest collection、catalog 编译、安装、构建或 solver。
- 严格串行，无派生 Agent，无实现修改。本次只审原六项和整改新增的直接调用路径。

## 未关闭项

### B-F1 / P1：尚未启动的策略授权无法按新配置重新授权，旧预留也无法转移

**位置：**`src/scidiscovery/artifact_agent/service/executions.py:457–459`；调用者 `src/scidiscovery/artifact_agent/execution_bridge.py:105–119`、`interfaces/mcp_root_execution_routes.py:205–212`。

原 R1 中“project 修改即获得新预算”的问题已修：控制层从科学主体 parent lineage 派生 owner，生产预留/终态结算落库，debug key 不再包含 operation_id。本地/远端 consumed_budget 经 status adapter 和 Bridge.sync 回到结算消费点。

但创建 execution 时已写入 policy authorization 和预留，submit 重新取得配置后，又调用 `authorize_policy`。该函数要求旧 record 与新 record 完全相等，任意 policy digest 变化都会报 `frozen policy authorization changed; create a new exact execution request`，即使新配置仍允许原请求。

**可达场景：**先以总额度 3600 秒创建请求，声明 1000 秒，尚未 submit；管理员将额度收紧为 1800 秒。submit 重新判定原请求仍在限额内，却被旧授权记录不等拒绝。按错误提示建立新的 execution 时，旧未启动请求仍预留 1000 秒，新请求再预留 1000 秒超过 1800，转成人工审批。当前没有“确认尚未提交后的授权修订/原预留迁移或释放”路径；结算只接受 terminal 状态。

**影响：**配置变动会卡住尚未启动、仍符合自主额度的任务，并可能因双重预留制造人工审批需求，不满足 R3 B 的提交前重新判断及配置内自主执行语义。

**最小修复：**将“不可变授权历史”与“尚未提交请求的当前有效授权”分开。提交前在同一精确 request、budget owner 下记录新的不可变判定，原预留保持一次计费；已准备/提交结果未知时先查询并保持原提交身份，不能盲目释放。新策略要求 human/deny 时显式转移状态。不得通过覆盖历史 record 或清空整池账本修复。

### B-F2 / P1：device_grid 仍未贯通 initial 与 runtime-failure 作者合同

**位置：**`plugins/tcad_artifact/tcad_artifact/plugin.py:502–527`；`local_debug_service.py:549–556`；`src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:569–573`。

原 R2 的正式 package 缺口已补：Operation 声明 `file_reference` device_grid；package 读取 exact binding descriptors，验证 grid 是 reviewed project 的直接父件，填入 resolved_inputs；后续 CAS → archive → adapter 路径使用文件流。64 MiB grid 端口上限也已从 revise 路径移除。

但 `DEVICE_GRID_INPUT` 仍只出现在 `REVISION_INPUTS`，`INITIAL_INPUTS` 和 `RUNTIME_INPUTS` 均无此端口。调试 `_candidate` 对项目每个 input_slot 均调用当前 Run 的 `context.input_ref` / `input_path`；这些方法只能取当前绑定，不能从 prior_project 的父链自动构造未声明输入。

**可达场景：**SDevice 详细计划作者初次需要外部 device_grid 时，invoke 合同无法绑定该 grid，项目声明 input_slot 后 preflight 调试失败。即使经 revise 路线得到可执行 SDevice 项目，solver 失败后进入正式 `tcad.deck.author.runtime-failure.v1`，原 grid 也不能作为该作者 Run 的输入；执行修复后的调试仍因未声明 Run input 而失败。修复并非要求所有 reviewer 都读取二进制，而是实际需要运行它的作者合同缺件。

**影响：**新增大文件通路只对 revise 分支闭合，尚不能声明现有 SDevice 作者/运行失败修复生产路径贯通。

**最小修复：**为实际消费 slot 的 initial/runtime-failure 作者声明同一 file_reference 输入，并在有 prior_project 时核对精确旧 grid 绑定/变更语义；让来源、调试、封存父链和 package 一致。可以共享作者输入组，避免多处分别维护；不能将文件读成 JSON/bytes 或以导入假 package 绕过作者和独立审查。

## 逐项关闭记录

| 原发现 | 静态复审结果 | 依据与限制 |
| --- | --- | --- |
| R1 稳定预算 | 部分关闭，B-F1 待修 | `scientific_budget_owner` 沿精确父链选主体；pool/reservation/settlement 在控制库；debug key 去掉 operation。真实配置变化下的授权记录更新仍断开。 |
| R2 大输入 | 部分关闭，B-F2 待修 | file_reference 与 exact metadata/parentage、CAS streaming 已接通 package/adapter；initial/runtime-failure 作者端口未接通。 |
| R3 debug 恢复 | 原缺陷关闭 | receipt 单独保留 submission、proof、文件 hash 和原文件；缓存命中改为恢复 receipt；控制 recovery chain 检查同实例；重建当前可信记录前后核对项目，finalizer 仍验证 Run/operation/project/declarations。未授权跨 Run 不采纳，未重跑 solver。 |
| R4 process_log | 原缺陷关闭 | materializer 使用独立 `.scid-capture/solver_stdout.log`；求解期间不再排除预期镜像路径；两端 `_publish_log_mirror` 分块写临时文件、校验后发布，冲突保留原件，不覆盖 solver 原日志。 |
| R5 preflight | 原缺陷关闭 | effect preflight/invoke 共用 `_effect_admission`，读取策略、能力及累计预算；预检返回判定，不写 execution/审批/预留。submit 仍重新判断，剩余问题在 B-F1。 |
| R6 debug 配置消费 | 原缺陷关闭 | 调用记录冻结 `collection_limits`，含实际模式 max_output_bytes；经隔离 debug_collection packet、debug adapter 到可信 proof/finalizer；不再用 smoke 总量限制所有模式，不再固定 8 MiB 读可信文件；AttemptFile 上限与总体交付边界已分离。 |

## 新 file_reference 与 receipt 的边界检查

- file_reference 在 compiled 输入合同中显式声明，只允许当前二进制媒体类型；字节不计入模型文本输入总量，metadata 仍绑定 exact ArtifactRef/size/media type。Run 调度/候选校验会流式 verify 原件。
- assignment 标明仅控制工具流式读取；通用 input reader、reference root 和 read_input 不把此类文件直接作为文本返回。受控 input_path 从精确 CAS 原件分块落盘，debug Source 接收 Path，package 不传巨大 bytes tuple。
- 新 transform 接收保留 binding_descriptors 的 ValidationSources；package 用直接父件核对避免仅凭 Agent 自填 grid 引用。但可达作者输入范围仍受 B-F2 限制。
- receipt 由控制服务写在工作区之外；恢复关系读取 sealed resume/draft 链并检查 instance，文件内容核对 hash。trusted record 只由工具上下文提供，不能以工作区自写报告恢复资格。
- 这些为静态路径检查，不构成实际文件容量、内存峰值、远端停止、运行成功或并发恢复正确性的证明。后续验证仍须遵守用户禁测要求，当前不运行。

## 补充候选身份

作者 52 文件清单未列入三份实际参与本次整改的文件；本审查读取了它们并记录下面身份。下次冻结候选应一并纳入，避免只凭 52 文件 hash 误认为冻结了完整整改。

| 文件 | SHA256 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/debug_collection.py` | `441c45fb012f7810bdc7e667ec071901fb8bc75749da9a07a613c1298c52a572` |
| `plugins/tcad_artifact/tcad_artifact/debug_contract.py` | `d9b4823c7e5b4d09f24a1da901324b5a48af736a0ed3c67ec8327b237f1c57e4` |
| `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` | `eea24d7d1d3454640ad66dad512c1e1e8aeeb3251fcb0bff1e61fff300cd07db` |

下一轮只需对 B-F1、B-F2 及其直接受影响边界复审；不重新打开已静态关闭的条目，除非修复改变它们的实现。

## 第二次补充复审：fixed2 候选最终处置

**本节为最新处置：B-F1、B-F2 静态关闭；原六项及补充两项目前无未关闭的静态阻断。STATIC REVIEW PASS，仅表示本报告范围内的代码缺陷已修复，不表示测试、安装或运行资格通过。** 上文 REQUEST CHANGES 保留为前一候选的历史结论。

- 精确候选：`/tmp/scid-r3-b-candidate-fixed2.json`，55 文件；SHA256 `40930d47b06ea931686a473b1d445942cf238f8b57d7f508c4f9f671b2d8e9f4`。
- 审查者重新核验 55 文件 hash 全部匹配，47 个 Python 文件通过 stdlib AST 解析。上轮漏列的 debug_collection/debug_contract/operation_workspace 已纳入本次清单。
- 相比上轮已冻结候选，仅 7 个既有文件 hash 变化（授权服务、Bridge、Root execution routes、TCAD plugin、双语 README 和策略测试）；本轮只复查 B-F1/B-F2 的整改路径，未重新扩大其他条目审查。

### B-F1 关闭依据

`ExecutionService.authorize_policy` 不再要求新旧策略 record 完全相同，改为保留不可变授权历史并更新 `execution_current_policy` 指针；`_record_policy_decision` 仍禁止更改 request/payload/compiled identity、budget owner 和请求预算。`_reserve_budget` 在事务内排除本 execution 自身的旧预留后重新判断，不增加第二份预留。

因此，上轮“3600 秒策略下预留 1000 秒、提交前收紧为 1800 秒”的路径可以在同一 execution 内重新授权。Root execution_submit 统一进入 Bridge；已经 prepared 的请求先 lookup 原 submission，接受结果未知时不另起身份。需要 human/deny 的重新判定调用 defer_policy，仅 never-prepared 请求释放未消费预留；prepared 请求保留原身份及预留。准备完成落库时再次核对有效 policy digest，已启动请求禁止重新授权。

静态结论：原 B-F1 的合法配置变化卡死和建议另起 execution 所造成的重复预留路径已关闭。真实事务竞争、准备期间配置变化、远端 lookup 超时仍须后续运行验证。

### B-F2 关闭依据

`DEVICE_GRID_INPUT` 已进入共用 `INITIAL_INPUTS`，initial/revise/runtime-failure 三作者通过同一声明获得 file_reference 绑定；revise 不再单独重复声明。review 输入明确排除该二进制端口，保持引用/审查职责。

`_parameter_inputs` 对 prior_project 的 device_grid slot 核对精确父件 ArtifactRef 和媒体类型；runtime-failure 的专用 validator 也调用该共用检查。原 grid 的修复任务因而可以绑定同一文件，换 grid 必须走新的 initial 作者设计和独立审查。此前已复核的受控 input_path、调试 Path、project 父链及正式 package resolved_inputs 消费路径可以继续衔接。

静态结论：原 B-F2 的缺失作者端口已关闭。未执行真实 SDevice、外部网格文件调试或大文件传输，不能据此报告 solver 支持已经通过运行验收。

### 当前验证边界

本轮仍未执行测试、pytest collection、动态项目导入、catalog 编译、安装、构建或 solver；未修改实现。结论只绑定上述 fixed2 候选及本报告明确范围。部署、运行资格、2GB 文件内存峰值、进程停止、SSH 与故障恢复验收仍待用户解除相应执行限制后另行安排。
