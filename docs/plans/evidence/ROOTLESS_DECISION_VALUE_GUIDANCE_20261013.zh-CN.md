# 下一步科学决策合同与同线程输出修复（2026-10-13）

状态：实现及父级分批定向源码门禁已通过；fresh wheel / installed CLI H-A-W-A 与重放验证通过。安装包 64 场景门禁与独立审查均通过；未执行科研模型，未读取独立隐藏评分。

## 科学职责与可执行边界

A 声明下一步可能改变的候选选择、机制取舍或合规判断，具体问题及改判条件。无法改变决定的重复验证应停止；必要检查、原用户数量要求和预承诺仍保留。当前机制不能解决的目标条件缺口回 H 提出可证伪解法，没有合法解法时保留不确定性。H 提出竞争解法机制，W 在用户/H 约束内观察驱动搜索，先便宜筛选再关键验证；E 原职责不变。指引仍领域通用，四角色总字节数受原 2048 界约束，保留至少 200 字节追加余量。

CLI `prepare --decision-contract` 显式冻结 `decision_contract_version=1`，仅此类新任务使用科学协议10。A 增加 required nullable `decision_request={decision,question,change_criterion}`，decision 为 candidate/mechanism/compliance；continue_w、revise_h、extract 必须声明非空科学问题和改判条件。audit、finish、wait 可 null。A 不填哈希、路径或原件表单；没有 search/focus 时机制为 unknown/None，不凭文字制造机制。

控制只机械检查缺项与精确重复：trim 后相同请求、相同已绑定机制/候选上下文，且此前合格请求已得到实际直接依赖 W/H/E 的封存响应，而当前没有新的已绑定科学原件 proof。raw 原件相同的复制或别名不增加 evidence；新的负结果或反例可增加 proof。作者补正 A 自身、未执行请求不算依赖完成。这里不识别换措辞后的语义等价，不裁判改判条件的科学价值，也不按低 proxy、目标 unknown 或候选数自动拒绝。

科学 null/blank 或精确重复保留原 science seal，走既有 MAX2 author clarification 回 A，预算、步数和重启记录不退款；不派依赖研究。decision unresolved 不增加 N4 科学 eligible 周期。审计仍独立且 adapter-scoped，不等于目标证据或交付确认。旧 settings 无显式标记、已有 protocol1..9 job/schema/view 保留，不会升级未来节点。

## 机械输出异常分离

JSON、类型/字段、空 final content 或已知终态缺 final output属于 typed `OutputRepairRequired`；它们不转成新科学 A 节点。仅冻结 resume policy 的 `output_repair:true` 可自动沿原 session、原 node、原 workspace 有限续接；原 attempts/cap、累计计量、全局余额、delivery reserve 和最多两次限制复用。控制器新执行和重启终态收集均调用同一 seal-or-repair helper。成功格式先封存，不重复实验或提交。

原件/schema/task 哈希变化、symlink/I/O、未知 native execution、缺必要计量、清理无法证明均保持硬边界，不归类为可修 final 格式。没有输出必须是精确 known rc0/无 stop/known usage、已确认清理且 pending/raw 真正缺席；纯 export 不启动修复模型。无授权或额度/次数不足准确停止，不能称未知工作已成功。科学 decision null/blank 的合法 JSON 继续走上一节作者科学纠偏。

## 最小实现与验证范围

`decision.py` 纯原件重放，`semantic/correction` 复用控制 outcome 和有限作者路径；`contracts/controller/cli` 接显式协议、模型可见合同和收集入口，`search` 仅新增协议/独立诊断 guard。无新账本、Root 科学判断、强制每次 H、比例预算或树执行器。

作者只静态 AST 检查；父代理统一测试/构建/安装/提交。专属 `test_decision_contract.py` 覆盖缺项三动作、精确重复/新负结果、审计及结束豁免、未完成/换 prose 限制、真实控制器两次补正与重启、N4 排除、递归 strict schema/旧协议。`test_decision_value_guidance.py` 验角色指引冻结和字节界；同线程机械修复由独立协作作者的 `test_worker_resume.py` 验证。无模型回归不等于科学行为效果或实际原生权限资格验证。

既有回归按新 typed 分类精准更新两处：`test_result_schema.py` 仍拒缺失 recommendation，改为断言 `OutputRepairRequired.code=invalid_fields`；`test_controller.py` 仅 invalid_science 分支期待 output_repair_required，额外要求 reason=invalid_fields、没有 continuation，原无模型重派/无 seal 不变量保留。failed/stopped/unknown 仍拒原恢复路径。它们不将错误输出改判为成功。

## 分批验证与保留的失败记录

父级源码门禁累计覆盖 262 个不同场景，并非一次整套运行：resume49、decision10、schema12、semantic26、controller46、correction40、authority6、scientificguide12、decisionguide5、closeout13、budget24、softadmission7、softnode12。新/旧合同、有限科学补正、原会话输出修复、原件完整性与预算/收口接线都纳入对应定向文件。作者未执行任何门禁。

初始失败记录保留在外层 `.trial/decision-repair-control-20261013`、`.trial/decision-repair-existing-gates-20261013` 及父级后续分批目录：repair fixture 未先写控制器同口径 host-started，以及初始预算不足 fixture 已精准修正；早期 standalone guidance 缺 200 字节余量和审计动作措辞已压缩恢复，未放宽 2048 界。旧 schema/controller 的两个分类断言按 typed 错误更新，拒绝错误输出、无未授权 continuation 和无重派不变量保留。before-seal 原错误输出身份漂移回归通过集中 terminal repair-chain 校验关闭，而不是忽略原错误。

父级已构建 fresh wheel，实际 installed CLI 完成 H-A-W-A 及重复运行无重派验证；安装包 64 场景回归 64 passed / 29.55s；CLI --decision-contract 的实际 prepare 冻结 protocol10，fresh wheel 的 22 模块源码/包/安装字节一致，H-A-W-A 与重启无重放通过。wheel SHA256 为 `726dd4b301698ceb7a860effb4a4c53444d2bb961b963f9ea8c4c34629164d94`。独立 reviewer n1 最终审查 PASS，见 [独立审查记录](ROOTLESS_DECISION_VALUE_REVIEW_20261013.md)。不得将这些无科研模型回归宣称为真实原生权限资格或科学效果验证。
