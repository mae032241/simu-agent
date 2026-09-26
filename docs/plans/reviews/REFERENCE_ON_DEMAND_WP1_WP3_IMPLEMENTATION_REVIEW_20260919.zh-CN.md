# WP1 / WP3 独立实现审查

更新结论：**PASS（WP1/WP3本轮实现审查）**。下述初审WP1单点已修复，WP3失败用例已修正并到达preflight完成断言。初审意见和失败记录原样保留，关闭证据见末节。另按父审查要求窄查WP2编译/路由接入，未审服务实现，不对WP2整体放行。未运行测试、科研MCP、仿真或部署，未修改源码。

范围依照 `evidence/reference-on-demand-20260919/WP1.md`、`WP3.md` 的本轮增量，不把当前大量HEAD脏diff都认作本包。审查对应R4第6A/B/C。已核查TCAD finalizer/debug包装、控制写文件函数、candidate诊断记录、新增生命周期fixture、WP3设计/critic文本和scheduler research/results指引。

## 初审阻断（已关闭）：材料化失败后，诊断报告写失败仍掩盖原始错误

位置：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:710` 的 `except ProjectMaterializationError`。

当前先调用 `write_control_workspace_file` 写 `deck/reports/materialization.json`，然后才抛出携带 `error.details` 的WorkspaceProtocolError。若报告目标被替换为symlink、父目录不可用或实际写入失败，写函数先抛WorkspaceError，后面的原始材料化诊断不会到达Run。

可达路径为：缺源文件/错误locator引发ProjectMaterializationError，同时报告路径不可写；`runs.validate_candidate` 捕获的是写文件错误，记录其诊断，`plugin._debug_tool`返回同一诊断。Python异常链中可能仍有上下文，但Worker可见结构化诊断和正式错误记录丢失了原来的科学实现输入缺口。这违反R4“报告写失败不掩盖原错”的WP1要求。

**最小修复：** 在材料化异常分支窄范围捕获派生报告写入失败，保留原 `error.details`，另附准确的报告写失败诊断，再沿原一次错误登记路径返回拒绝。不吞掉文件安全错误、不继续成功封存、不允许symlink写入；成功材料化后的报告写失败仍应失败。无需修改通用不可变写入规则。

补一个真实debug入口负例：材料化缺locator，同时 `reports/materialization.json` 为symlink（或可靠注入写失败）；断言目标文件未改，响应同时保留原缺口和报告写失败，单次尝试只登记一次，修复路径后可继续。当前新增symlink测试只测试写函数拒绝，没有覆盖“原错误+写失败”组合。

## WP1其余核查

- `final_submission=False`使用明确inconclusive的开发transport handoff，不写回作者handoff；最终提交仍读取严格RoleHandoff并要求匹配当前project/declarations的preflight及必要initialization。没有用默认pass补科学结论。
- 派生报告替换复用目录句柄、O_NOFOLLOW、临时文件和os.replace；目标非普通文件拒绝，通用 `_write` 的不可变行为未变。正常A/B不同失败可以替换当前报告，原尝试诊断由Run留存。
- `runs.validate_candidate`记录一次并抛`recorded=True`，debug包装尊重该标记，消除该路径的空重复output_rejected；未发现本次修改吞掉最终封存错误。
- raw_outputs作者字段与控制生成字段在materialization帮助/角色说明中分开，测试保留对capture/max_bytes的严格拒绝；相关组件configuration_identity已升级。

证据记录报告 **6 passed / 94 deselected，119.41MiB峰值**。本审查阅读了新增fixture及真实调用路径，未自行重跑，未把该结果扩张为solver、安装或生产验证。

## WP3判断与验证限制

本轮新增设计者/critic文本区分数学可计算、分析工具、开发诊断与已注册executor；缺执行路线保留feasibility/implementation gap，不转移为作者必须创造执行器的义务，不把未知能力当物理反证。没有增加新的代码白名单、Schema必填科学字段或审批旁路。计划审查仍可指出必要输入缺失，但不要求未编写源码先给运行证据。

research指引从完整编译Operation及选定Effect能力记录取事实，明确不以目录首页证明能力不存在；results指引要求completed响应下读取正式结论、限制、矛盾、理由与signal，保留总体目标和原件绑定入口。复用已读payload、精确字段读取及禁止累积翻页后统一打印没有删掉科学内容，也没有宣称native shell受服务端硬预算。精简主要是公共指引，不能由此证明模型行为或token收益已经改善。

WP3证据记录为 **26 passed / 1 failed，128.07MiB峰值**。失败用例 `test_l6_runtime_capabilities.py::test_curve_error_agent_is_local_runnable_after_collection_is_moved_to_transform` 在默认catalog第一页中直接 `next` 查operation；当前分页默认20项，失败与所查测试代码的未分页假设一致。该用例后面的preflight断言未执行，不能写成能力回归全过。WP3本轮没有修改目录/分页生产逻辑，未将此失败归为新提示修改引入的功能回归。

**非阻断收尾：** 验证负责人应通过现有精确operation选择或正确分页修复该测试读取方式，再定向执行未覆盖断言；不要扩大默认catalog响应来迎合测试。保留当前失败记录，后续追加修复与重测结果。安装后的总体目标传递、原生行为和收益仍归WP4，当前不宣称通过。

## 本轮候选定位

以下摘要仅定位本次实际阅读的关键文件，不把它们相对HEAD的全部历史脏改归入本包：

| 文件 | SHA-256 |
|---|---|
| TCAD operation_workspace.py | `efc589040503e9d498d63ec33911d266ecc2d651e2a547fd30fa5180cfe0d65a` |
| TCAD plugin.py | `10f666aab4a9a7cdabfc16c17d02055094754afe2d5822b3b2d661f7fbda2049` |
| general_science_experiment_components.py | `25ae3337f222e98e3ac0bb9ff80ab117b89e21beb7eab8f26eb12c756a61a833` |
| general_science_resources.py | `7591caa27664fde7bd1ae9cf9bdbffbefd00aa014f15615d3f72dd32a7f64159` |
| roles/scheduler/research.md | `8e517e8c1c13a6d3228b6bde6d5f4846512e9e75295b1d5625ec37158371277d` |
| roles/scheduler/results.md | `a9d85eb2b2e1c727e92228a2d5ad59a5f837e7b71745e7714e1c2a5cb00b101d` |

关闭WP1单点阻断后可有界复审，不需要扩展到WP2或重启R4计划讨论。


## 修复复核与WP2接入边界补充

### WP1 / WP3关闭证据

WP1材料化失败分支现在先保存原error.details，以窄try捕获报告写入的WorkspaceError/OSError，附加materialization_report_write_failed，再抛含两类诊断的WorkspaceProtocolError。未跳过安全写入检查，未把报告失败改成成功，成功材料化后的写失败仍向上传播。`test_failed_report_write_preserves_original_materialization_error`可靠注入材料化与写入双故障，验证原details仍在首位并附写失败类型；它是finalizer定向回归，不冒称新增完整debug端到端测试。原有debug一次登记及symlink拒绝证据仍适用。父调度报告本次**1 passed，峰值约91MiB**；本审查静态核查测试内容，未自行运行。

WP3测试现在通过精确operation_id查询目录，从既有计算fixture生成真实包/PNG并按端口media_type登记；无材料端口显式断言min_items=0才省略。保留admissible/reason_code/port/executor_kind断言，额外验证normalized_request及preflight未创建Run。生产目录、准入和预算未为测试放宽。证据记录新增**1 passed，108.77MiB峰值**，原先其他26项已通过；应表述为分批定向验证通过，不重写成一次整批全绿。

本次复核摘要：operation_workspace.py `0316419ddadfee84addc8eee05748f9c76d23f6898b20f9bfa6ab72be4b57e29`；test_tcad_development_lifecycle.py `10ea993846f5933314e8259c423fb6c39f842f40bdae5dfacfd40dfad6ac35a1`；test_l6_runtime_capabilities.py `cd0129f0f9dd3754964511eaf002f7f0368d1ab040bf6a13162f55e86e9b3479`。当前无WP1/WP3剩余阻断，安装/原生收益与WP4仍未验证。

### WP2仅编译/路由接入静态检查

已查reference_tools、tooling、catalog、builtin_plugin、operation_declaration、operation_contract、run_outputs、run_assignment及OperationToolContext/Local router新增接入；未审reference_access服务实现，后者仍在施工，目录compile通过由父调度提供，不等于行为测试。

- `with_user_context`通过`with_reference_access`在声明构建时加入工具和控制manifest，最终工具权限出现在编译Operation及Worker工具列表，不是运行期根据角色名偷偷开放读取。非agent不由该helper添加读取能力。已有工具产物权限不单独授予reference callback；callback要求当前工具的reference_policy。
- policy是冻结dataclass，catalog资源digest纳入其序列化内容。builtin工具及共用tool_evidence_schema公开可供跨插件引用；public组件不等于无编译声明即可调用。
- 新增的1个文件和1MiB总输出预算对应单独控制manifest，主科学产物的max_item_bytes未提高；run_outputs仍按主端口max_item与总限额的较小值校验。没有统一输入端口扩容。已有manifest的Operation不重复加预算。
- direct_revision_ports只允许额外recovery_manifest_output collection，其余collection仍不能冒充完整对象修订；catalog要求工具声明集合与输出collection集合一致。没有增加任意附件口。
- reference_source_ports作为同一编译来源授权供Schema和context_validator筛选消费；assignment只增加短导航句，未自动展开引用正文。Hardened继承公共router的非文件工具路径，仍须在后续服务验收中验证其transport和文件入口。

未发现这部分当前接入构成新增隐藏权限或主产物不当扩容。**非阻断建议**：WorkerToolDefinition.reference_policy当前为Any，多policy冲突在运行时才拒绝；在编译时校验策略类型、正数边界及唯一性更能维持“编译完成即合同有效”。工具可见contract目前只有description/inputSchema，限额主要在服务policy；可在同一派生合同或服务返回投影声明额度/剩余额度，避免Worker只能通过超限错误发现预算。两项不授权新增状态表或独立预算权威。

WP2仍需其自身服务、来源封存/恢复、并发竞争和真实路由测试及独立实现审查，不能从本段接入检查推导整体PASS。
