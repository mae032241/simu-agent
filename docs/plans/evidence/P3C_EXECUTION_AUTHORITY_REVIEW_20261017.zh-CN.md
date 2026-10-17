# P3c 执行授权原件与同一 UI host 独审

结论：**本节点静态 PASS；仅 authority-only 中间层，不启用 TCAD，不代表 P2/P3 退出。** 精确范围为作者冻结的 9 个生产文件、`tests/research_loop/test_execution_authority.py` 和实施证据；基线包含 P4c1 原语抽取 `b01e636`。并行 P2d、后续 P3d ledger/factory/gate 不在本结论内。

## 真实路径及权威边界

- `controller.prepare` / CLI 的显式 opt-in 冻结 authority 合同，缺 formal-review opt-in 拒绝；普通实例继续 build/seal/validate，不新增审批必经阶段。
- `contracts.build_job/_validate_inputs` 接入 `bind_job/validate_job`：只沿直接父 job/直接 formal-review return 取显式 passed ref，再要求 exact subject material 仍属本 job 的冻结输入。`formal_review.require_review` 复核当前合同、seal 与独立身份，不从最近 pass、同 hash 文件或普通 A 文本授资格。
- `create_request` 只作可信 P3d 宿主 seam，核 W job/native-intent、subject/member/source、直接 review ref、来源 clear、target 原件、grant revision 原件及有限资源/expiry；没有 public JSON/CLI request writer，也没有 reserve/backend provider。本阶段 UI 可消费已存在请求，不声称已完成生产请求派发链。
- 实际 `serve-ui` / HTTP handler 到 InstanceUI GET/POST、管理链接换 maintenance cookie、精确 Host/Origin、nonce/CSRF、registered option、HMAC decision/revoke 的代码路径已接通。管理链接重定向去凭据，服务不记 capability URL 日志；错误/重启前 cookie、异实例授权不能替代当前浏览授权。决定不调用 prepare/submit/cancel/native，不增加额度。
- 同 nonce 同完整决定复用原 ref，异内容拒绝；过期新决定拒绝；状态区分 revoked/expired/decided/pending，验证原 HMAC 与绑定。已决定请求仍有撤销表单；撤销不自动取消或退款。浏览 boot 失效与历史决定有效性分开。

## 实现身份与旧调用方

最终 `execution_authority.implementation()` 自动包含实际 `execution.py` native-attempt 枚举代码，以及 authority/UI/contracts/qualification/security/browser/provenance 行为。正式审查合同另绑定 review_rules/native/continuation。独审早期快照缺 execution.py 的疑问已在最终文件核实收口，不要求插件手填框架 assets。

旧 approval option 函数直接重导出；旧 `execution_decision_authorizes` 显式保留历史 approve，thin 不接受普通 approve/pass。旧 ApprovalService 将原 canonical bytes 交同 SHA256-HMAC，无新前缀；其构造器既有 secret>=32 校验保持。旧 runtime secret loader 只适配原异常类型，新 owner 仍 regular/non-symlink/权限检查并补打开时 inode 检查。新 UI 不导入旧 ApprovalUI/SQL/Root owner。

## 测试是否能证伪真实行为

五条仅编写、未运行：

- 选项与 HMAC wire：若 generic scientific_review/pass 被授执行资格，或旧签名字节被加前缀/换算法，会失败；正常确定性向量有兼容价值。
- 真实小文件 secret 负控：若 loader 跟随 symlink 或接受公开权限，会失败。
- 普通 H/A build/seal：若 authority 被变成默认门控或 pass 文本产生权限，会失败；finish 为合成 native 终态，不证明平台执行。
- 真 InstanceUI 路由方法：错 Host/Origin、旧 boot cookie、换 key 若被接受会失败；未启动真实 HTTP/浏览器。
- 一条 process_e2e 使用已有脚本化 Codex 协议 fixture，经真实 native/seal/review 路由，再调用真实 UI POST。可证伪 review ref 传递、CSRF、决定幂等/冲突与 HMAC 篡改保护；合成身份不证明真实独立性，opaque fixture grant 不证明 ledger、provider 或 TCAD 授权。“无 accepted/submission”仅核本阶段未产出执行事实，不能当真实 backend 零副作用验收。

## 静态证据及未完事项

独立阅读上述路径和旧适配，限定 `git diff --check` 通过；作者报告十文件标准库 AST 通过。本审未运行 pytest/collect、业务 import、HTTP、CLI、进程、安装、构建、模型或远端计算。

P3d 仍须唯一累计 owner、有限 grant、reserve-before-prepare、submit 再验、partial actual/unknown 占用及 P2d 唯一 release。维护 query/cancel/退役与新 submit 的科学额度/expiry 分界尚属后续 gate 实施审查，不能从本报告推出维护已可用。非空输入 exact 映射、长时人工等待后的显式原 call 恢复仍是 P2/P3 必完且须另审的集成；不以永久 blocked 标迁移完成。
