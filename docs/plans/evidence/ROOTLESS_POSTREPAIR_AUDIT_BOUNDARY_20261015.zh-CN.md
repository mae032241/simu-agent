# 修复后候选审计边界与旧准入现场恢复

基线 `c5790ba83951684b9bc5d9d6bf7927ba2f56fbb9`。全新独审发现 P1：收口工程修复后，新 A 的合法 `audit` 仍拿扩展来源与 begin 初始来源比较。真实 CLI 抛出 `Candidate audit closeout boundary changed`，留下 intent/sources/binding，无 outcome；status/run 随后重复异常。原先验收只覆盖新 A 直接 deliver，未覆盖这一合法分支。此前集成 PASS 不关闭此缺陷。

## 精确修复

- audit 与 contracts/controller 同样使用 `engineering.sources(root, job.step)`，严格保持原 cutoff、begin 哈希、job/raw/seal 及截至该 job 的 sealed repair W；不把未来节点或任意来源纳入边界。
- 请求边界在 transition/intent 写入前纯校验；解析后的 source/binding 在各自落盘前纯校验。实际调用仍复核落盘原件。execute 也拒绝与磁盘原 job 不同的调用参数。
- 新增控制私有 `dispatch.json`，在调用适配器前持久化，绑定 operation、intent、sources、binding 四项身份。有 dispatch 而无 outcome 始终 unknown，不能因缺 process 记录重放。
- 已受此精确旧缺陷影响的 intent，仅在合法来源确含 sealed repair W、旧 guard 必然在 staging/Popen 前拒绝、全部原件通过当前严格校验，且没有 dispatch/process/leaf/recovery 证据时，由 run 命令结算为 accepted `unavailable`，原因明确 `candidate_audit_legacy_preflight_not_dispatched`。这是控制层未执行结论，不是审计结果或科学拒绝。
- 原 intent、job、seal、原已用步数及时间不改，不执行旧 operation。后续由新 A 明确选择；旧 unavailable 不授予资格。新 A 请求 audit/deliver 仍经过原预算和控制真实审计。状态查询只读，旧现场可显示 unknown，不能在 status/facts 中写恢复回执。
- 控制不可用回执已写而 outcome 未写的中断，只能按同一精确结果幂等补齐；任意执行证据均保留 unknown。

## 定向验证

全部使用仓库共享 serial_lock 与默认资源监督，无模型、预算提升、真实场更改或 push。原始日志保留于 `/tmp/protocol18-postrepair-*`，结构化原件见 [验证记录](ROOTLESS_POSTREPAIR_AUDIT_BOUNDARY_20261015.json)。

| 运行 | 结果与结论 |
| --- | --- |
| postrepair-fix | 1 passed, 7 failed；57.381s。正常真实 CLI 正例通过；建旧现场的 direct-controller 测试 helper 未给 native 子进程源码路径，没到被测逻辑。改用真实 CLI 和预设 pause barrier 建场，不改变核心断言。 |
| fix-recheck | 19 passed, 2 failed；183.82s。正常 repair→A audit→A deliver→confirmed/restart、验证失败不接受 intent、四种执行证据保持 unknown、原 candidate audit 13 例均通过。两旧现场例需要第 13 步但原 fixture 只有 12 步，原 reserve 正确拒绝；未提高限额。 |
| legacy-budget | 2 passed；73.12s。保留原 12 步：新 A 坚持额外单独 audit 时明确预算停止；部分回执恢复后新 A 明确 deliver 时控制实际 audit/promote 并确认。验证旧原件不变、旧 operation 无新 leaf、不可用不成为资格、status 只读及重复 run 不重复计步。 |
| 新 wheel 隔离安装 | 成功；2.591s。新 venv 不继承系统 site-packages；wheel SHA256 `7732118b797be109cf6d38c0221ac26d7b95d909c6da32e3aef6be60d346428d`。 |
| 安装版 python -I 联合正例 | 84.671s，exit 0、清理完成。新 repair→audit→deliver 和旧 partial-result→新 A 明确 deliver 两场均确认；实际 W/A argv 与 intent 的角色配置一致，W live/terminal matched。 |
| 安装身份 | 239 文件无差异，sys.path 无 repo/src。源码清单 SHA256 `58c78496a1ce45a1e195b1a4d29dd91a10e72062976c76fdd6db64240cfbbea8`。 |

所有失败尝试保留。资源均在原阈值内完成并清理；没有隐藏或放宽 reserve、科学资格及 unknown 判定。当前只补此 P1，不宣称修复任意既有未知操作，不重跑全库或真实模型场。独立复审及成文证据核对 PASS：确认本次 P1 已关闭，未发现新增阻断缺陷；范围仅为此精确修复与确定性安装链，不包含全库、真实模型或任意 unknown 恢复。
