# P3c 执行请求与可信决定原件：实施冻结

状态：**实现冻结，已获[独立代码静态审查 PASS](P3C_EXECUTION_AUTHORITY_REVIEW_20261017.zh-CN.md)；没有动态验收。** 依据 [P3c/d 设计](P3CD_EXECUTION_AUTHORITY_DESIGN_20261017.zh-CN.md)及其[设计独审](P3CD_EXECUTION_AUTHORITY_DESIGN_REVIEW_20261017.zh-CN.md)。本节点仅实现 authority-only 中间层，P3d 预算/gate 与 P2d 原调用恢复分别持有责任；P2c 工厂继续默认 blocked。

## 精确入口及原件链

- `scid-research prepare --enable-formal-review --enable-execution-authority ...` 显式冻结本实例 authority 合同。普通未声明实例不增加资格要求；单独启用 authority 而无 formal review 合同拒绝 prepare。原件绑定实际 authority/UI/security/contracts/source/review/native-attempt 验证代码，consume 时检查当前实现相同，不靠插件手工列 framework helper。
- `contracts.build_job/_validate_inputs` 只沿直接父 job 及直接 `formal_review_return` 传播仍精确匹配当前 bound material 的显式 passed review ref。没有“最近 pass”查询、祖先清单复制或模型 ID/hash 字段。完整 ref 在 host job；科学视图仅路径预览及遗漏数。
- `execution_authority.create_request` 是可信宿主的后续 P3d 接缝，**没有 public JSON/CLI request writer**。它核 exact W job/native intent、payload source/producer/member、当前正式 review、全部绑定来源 clear、target 配置原件及资源授权修订 ref，再冻结 instance/call/policy/resources/expiry/nonce 原件。当前没有 P3d provider/资源 owner，不能因此视为已获执行许可。
- `scid-research serve-ui --root ... --approval-secret-file ...` 是唯一明确实例的 loopback UI host；P4b 后续扩展同一个 server/session。宿主显式读取 regular/non-symlink/0600/至少 32-byte key，仅保留原 key digest，拒绝换 key。此实施过程没有创建真实凭据，也没有复制 native home/缓存/凭据。
- 真实 HTTP GET/POST handler 只通往管理链接换 cookie、请求原件查看、decision/revoke。Host/Origin、当前 boot 的实例 maintenance cookie、CSRF、request nonce、expiry、注册执行 option 和重复决定语义通过后，封存 HMAC 原件。HTTP 不调用 native/prepare/submit/cancel/budget。重复相同决定返回旧 ref；改变内容拒绝；决定/撤销篡改被验证原语拒绝。当前 UI 没有资源增加表单，exception option 也不隐含增加额度。
- `record_policy_decision` 仅供后续可信 provider 消费 exact policy request；没有模型/API 入口接收 policy JSON 并直接授权。`status` 始终显示 `blocked_pending_resource_gate`。人工决定只记录事实，不自动恢复或执行旧 W。

## 复用与所有权

中立 `execution_security.py` 复用执行专用选项和 pure HMAC/secret 验证。旧 schema re-export 相同 option 函数，旧 `execution_decision_authorizes` 保留历史 approve 拼写兼容；thin 不接受 approve/pass 作为执行选项。旧 ApprovalService 把**原先相同的 canonical bytes**交共享 HMAC 原语；旧 runtime 的 secret loader 仅适配原异常类型。没有把旧 SQL、ArtifactService、Root 或 ApprovalUI 导入新链。

本次 **9 个生产文件 + 1 个测试文件**：

1. 新 `src/scidiscovery/execution_security.py`
2. 新 `src/scidiscovery/research_loop/execution_authority.py`
3. 新 `src/scidiscovery/research_loop/instance_ui.py`
4. 改 `src/scidiscovery/research_loop/controller.py`
5. 改 `src/scidiscovery/research_loop/contracts.py`
6. 改 `src/scidiscovery/research_loop/cli.py`
7. 改 `src/scidiscovery/artifact_agent/schema/approval.py`
8. 改 `src/scidiscovery/artifact_agent/service/approvals.py`
9. 改 `src/scidiscovery/artifact_agent/runtime.py`
10. 新 `tests/research_loop/test_execution_authority.py`

文档另有本记录与本节点设计文档；独审报告由 reviewer 持有。没有修改并行 P2d 的 experiments/history/execution_recovery/lineage、TCAD wrapper/adapters，没有修改 budget/factory/HostServices 或 P4 状态/控制/归档。

## 最小负控账（只编写，未运行）

| 用例 | 真实目标与证明边界 |
| --- | --- |
| 选项/HMAC wire bytes | scientific_review/pass/非 legacy approve 不授执行选项；旧原 bytes 继续使用同 SHA256-HMAC。只证明 pure wire 语义。 |
| secret 文件 | symlink/公开权限拒绝，不读取任意模型给的 key JSON。 |
| 普通科学 | 未 opt-in 的普通 H/A seal/validate 不依赖 authority；pass/approved 文本不产生资格或 UI host。 |
| 实例 UI 边界 | 直接调用真实 UI 路由方法，不启动 HTTP；错 Host/Origin、旧 boot cookie、换 key 拒绝。 |
| 精确 review→UI receipt | 复用已有 native/seal/formal-review 路由的合成平台身份 fixture，再直接调用真实 UI POST；错 CSRF、相同决定幂等、改内容和篡改 HMAC 拒绝，明确断言无 accepted/submission。opaque grant 原件只是 P3c 绑定 fixture，不声称已有 ledger/TCAD admission。 |

没有删除旧测试或把旧端到端 suite 搬来重跑。最后一条 fixture 不证明真实 Codex 独立性、policy RPC、预算 reservation、真实 HTTP/浏览器或 TCAD 执行通过。

## 静态检查与未完成退出条件

对上述 10 个 Python 文件仅执行 `ast.parse`（标准库 AST，不导入项目），语法检查完成；`git diff --check` 完成。工作树同时有 P2d 修改，未将其计入本节点自有 diff。没有运行 pytest/collect、项目 import、HTTP、模型、业务子进程、build/install、SSH/solver。

P3d1 必须接唯一 budget ledger、稳定累计 owner、reserve-before-prepare、submit 再核验、实际/unknown 资源结算与 P2d 唯一永久未提交 fence 消费。reserve 已发生但无 accepted 的窗口若不能证明安全释放，保留占用，不能假造 terminal/accepted 退款。

非空输入的控制生成 exact sealed material→slot/ref→P2b callbacks 映射，以及人工等待后显式原 call 恢复，均仍是 [设计第 9 节](P3CD_EXECUTION_AUTHORITY_DESIGN_20261017.zh-CN.md#9-p2p3-最终退出前的必需闭环)要求的后续必需节点；具体 ref/恢复合同尚须窄设计独审，不能永久 unsupported 后标 P2/P3 完成。

边界仍是可信操作者 prepare/UI 的软隔离：不抵御同 uid 任意 shell 取得宿主密钥或改写宿主原件，不把 HMAC/字节 proof 说成科学语义认证或 OS 隔离。
