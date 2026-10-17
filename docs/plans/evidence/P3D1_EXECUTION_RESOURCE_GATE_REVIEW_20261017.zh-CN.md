# P3d1 资源账与可信执行 gate 实现独审

结论：**精确本节点静态 PASS，可提交；不是 P2/P3 退出或真实 TCAD 验收。** 对象为 HEAD `7b49fc1` 后作者冻结的 9 生产文件、2 测试文件和实施证据。仅静态文本/Git 审查；未运行 pytest/collect、项目 import、CLI、HTTP、业务进程、构建、安装、模型或远端计算。

## 精确提交范围

- `src/scidiscovery/operations/runtime_plugins.py`
- `src/scidiscovery/research_loop/{budget,cli,controller,contracts,execution_authority,experiments,instance_ui}.py`
- `plugins/tcad_artifact/tcad_artifact/managed_execution.py`
- 新 `tests/research_loop/test_execution_resources.py`，及既有 `tests/operations/test_runtime_plugin_configuration.py` 一个 case 的修改。
- 作者实施报告 `P3D1_EXECUTION_RESOURCE_GATE_IMPLEMENTATION_20261017.zh-CN.md` 与本独审报告。

**排除**并行 `project_packager.py`、`experiment_capability.py`、新增 `native_implementation.py` / `test_tcad_native_implementation.py` 及 P3d2-a/b 后续设计变化。d1 使用现有 v2 package API，不引用新 v3 类型/compiler；本 PASS 不覆盖这些工作树文件，不因它们已可读取而纳入 d1。

## 实际路径与权限

1. 显式 operator resource policy 冻结有限 wall/storage allowance；缺配置不发默认额度。`configure → freeze/load → _adapter` 验 exact job/native-intent/host projection，再注入非 JSON HostServices。启用策略时必须有冻结的中立 `host_execution_gate` 合同，旧忽略 services 的 factory 拒绝；无 TCAD 名称白名单。
2. 已 bound source/read-copy 必须精确匹配直接正式 review subject，且来源 clear；普通 A/package pass、同 hash 的另一文件不授资格。先本地验来源/review，才调用可信注册 provider 的 active capability/policy。非空输入缺 callbacks 在 gate 前拒绝，既不请求批准也不 reserve。
3. authority allocation 固定 call、原 scope/attempt/interface/subject/review/alias 与期限；pending 不冒充 accepted。相同重试不按当前 clock 重算 request。UI endpoint 签名及实际 host lock 证明可用才给无 token 请求 URL，管理 bootstrap token 不交 W；key locator 由原 serve-ui 操作者封存，gate 核原 key，无 JSON key 路径。
4. prepare/submit 都核实际原 native/runner 活跃、未 seal/结束、当前 attempt 与原科学授权；结束 W 的旧配置不能通过公开 run 偷开未来恢复入口。有效 exact policy/human 决定还须当前未撤销、未过期、policy 与 grant revision 相符。reserve 先于 backend prepare/upload；submit 再核原 accepted/prepared/reservation。
5. prepare-intent 已落而无 accepted 时不能盲重 prepare。reserve→失败的未知窗口保守占用，不伪造 accepted/fence 退款。query 不取新 solver grant；cancel/retire 沿原 permit 的有界维护，不要求 W 仍 live、human expiry 未过或科学余额为正。collect 有自己的首次窗口且不因重试续发。

## 唯一账本、修订与原科学预算

`budget.py` 仍用原 control-ledger、settings/seq/parent/clock 链和 writer。owner 稳定为实例+executor；package/call/attempt/修订不建新池。reserve 锁内扣历史 `{**reserved, **actual}`，幂等不多扣；actual 缺维度继续保留该 reserved。bind 保留同 reservation 的 exact accepted/prepared；只有 P2d 统一 verifier 认可的同 call/authority/prepared/accepted 永久未提交证明可 release。lookup None、取消请求、timeout、unknown 不退款。

资源 `budget-amend` 复用明确 operator CLI，修改两维 ceiling 保留历史占用/实际，不替代 exact-call 批准、不改科学 token/time ceiling；旧 grant ref 在 reserve/submit 不再有效。grant revision 指向 resource_grant 原件，科学授权 revision 只指 settings/明确 budget_amend；不断追加 clock seq 不成为授权修订。

已追原消费者：snapshot 只按 clock 积分 advance/waiting/paused，只按 budget_amend 改科学 max_tokens/max_seconds；transition 查最后 clock；closeout_state 仅折叠原 closeout/action 事件。node/continuation/exploration/repair 沿原 snapshot/native usage 与保留 floor，不把 resource event 当 phase。旧无资源事件的 ledger 不增加默认 grant。

## 异步四种期限

- **新 dispatch/RPC**：原 native live、node/search/shared 剩余，allocation 冻结 dispatch deadline；不等于 solver wall。
- **请求 expiry**：原分配的有限 UTC expiry，重复不刷新；不能过期后借原 W config 新 submit。
- **solver/job**：精确 package/request 的资源量、显式执行 grant、原全场适用剩余及 closeout floor；job deadline 独立冻结，不裁成 W 推理 slice。
- **collection/维护**：collect 首次窗口取原 job/shared 截止与 runner collection policy 较小者，重试复用；不要求原 native 活跃。跨 boot 不伪造旧 clock 可验证性；release 暂不可写时保留原 fence 与占用，不抹原件。

首次派发授权与长时间等待后的显式恢复仍不同：后者未实现，不能利用本修订自动重开旧 native。

## 独审发现并已收口

旧 W 结束后仍可公开 dispatch；明确不支持的非空输入先 reserve；旧 factory 忽略 HostServices；W 推理 slice 被误套 solver/collect；资源 metadata 重读；同 observation 重复资源投影；可选 projection 普通异常破坏成功读取。最终分别用原 owner 检查、前置本地拒绝、冻结能力合同、四期限分离、同次 origins 索引、原 resource_settle.observation 幂等、可选边界 catch Exception 修复。BaseException 不吞；失败不记 actual=0，全文诊断留原 call，公开预览有真实省略数。

## 负载与 OOM 证据边界

新增 resource events 会增加原 ledger 的扫描/内存 metadata；当前每次读取临时建 origins 并复用同次 fold，没有第二持久 cache，也不从 snapshot 扫完整执行原件。新 dispatch 还增加原 native usage metadata 和 exact 来源/review/实现 proof 校验；不能宣称零开销或固定内存。

**已接受的实际 I/O 限制**：首次 TCAD resource_consumption 仍经 `_completed/_collection/_inventory`，对 canonical observation 刚验证的完整 native outputs 再哈希一轮并解析 manifest。已 settled 的同 exact observation 不重复该新增投影；原 canonical 完整性验证保持。此额外读取为流式，完整 JSON 仍需内存；不声称硬实时/恒定内存，未来可沿 verified descriptor 复用减少。root 明确本节点如实保留此限制，不继续扩大实现。

这些是静态可证新增工作量，不能据此归因此前 OOM，也没有性能实测。没有要求或执行大回归、重复安装、环境重建、真实模型/solver。新增竞争用例仅未来单用例内两个小 ledger 写者，非并行 suite/安装；当前也未运行。

## 必要负控的实际证明范围

- 原 ledger 交错 advance/waiting/paused 与 resource grant/reserve；两个小竞争者、exact reserve 幂等、同 owner CLI ceiling amendment 保消费、旧 grant 拒绝及 lookup-none 不 release。若新资源事件改科学余额/phase、race 超支或换修订清消费，会失败。opaque request/decision 仅测试账本数学，不冒充真实批准。
- 真实 configure 拒旧 factory 无 gate 合同：若 services 被静默忽略而策略失效，会失败。
- 脚本化 native/formal-review 原件经实际 controller/seal，再以旧 hard-W config 调公开 dispatch；provider/prepare 是失败陷阱。若结束 owner 可继续调用新派发，会失败；合成身份不证明真实平台独立性。
- 既有 wrapper case 保留 self-contained 默认 blocked，并用 gate 失败陷阱证伪非空缺 resolver 进入 authority；不以伪 backend 成功 JSON 当资格。

以上均仅编写未执行。没有新增活 owner 正向 pending、job 大于 W slice、collection、partial settlement、retirement release 或 optional projection 异常的动态通过证据；这些生产路径本轮只做定点静态复核。实际 HTTP、native、TCAD、跨 boot、文件锁并发及传输可抢占性未验收。

限定已跟踪 d1 diff whitespace 检查通过，新测试已逐条静态阅读；作者报告 11 Python 文件标准库 AST/no-index whitespace 通过。非空 native 输入闭环、迟批显式恢复和 P4 后续仍未完成，不能把本中间节点 PASS 写成全迁移完成。
