# P3c / P3d1 执行授权设计独审

结论：**P3c 与 P3d1 安全中间节点设计 PASS；不是 P2/P3 整体退出或真实 TCAD 启用批准。** 对象为 `P3CD_EXECUTION_AUTHORITY_DESIGN_20261017.zh-CN.md` 当前含第 9 节的版本，基线含 `00cb132`、`4f0a455`、`3ac974d`。仅静态阅读设计与真实 dispatch、adapter、Records、control-ledger、旧资源数学及退役协议消费点；未运行测试、项目 import、CLI、HTTP、构建、安装、模型或远端执行。

## 真实入口与最小责任

- `experiments.py:691` 的现有路径随机分配 call，`adapter.prepare` 先于 `Records.accept`。设计第 5 节在同 Records namespace 的 authority 原件固定 exact scope/native-attempt/subject/payload/target 所属 call，pending 不伪造 accepted，也不混入 calls 扫描。不是只增加一个无法实际重试的 gate helper。
- 第 4–5 节的同一 serve-ui host 才写人工决定；BrowserAccess、精确 Host/Origin、CSRF、nonce/expiry 与决定签名保护同一实例，chat、普通 A、package pass 或 JSON authorized 字段不能替代授权。UI 不建立第二调度器，点击批准不自动 submit 或重放 unknown。
- 同 attempt 在原期限内精确重试；改变输入/目标/规则/资源授权修订不能继承决定。原 W seal 后本中间节点不后台启动旧工作，原科学结果保留。缺 host 不伪造 review_url。
- 来源与审查从 P3a/P3b 精确 subject/member、producer seal、显式 review ref 读取；直接绑定，不搜索最近 pass、相同 hash 或祖先资格。nonempty inputs 暂缺诚实映射继续 blocked；不借旧 ArtifactRef 形状伪造旧服务事实。
- 第 6 节仅扩 `budget.py` 原 ledger、链和锁；稳定 owner 不随 package/attempt/revision 重置。先 reserve 再 prepare/upload，远端 RPC 不占 ledger 锁；actual 只覆盖已证维度，unknown 维度仍占 reserved。普通 authorize 不增 grant。P2d 唯一 validator 才可 release，lookup None、取消请求、timeout 均不可退款。
- 第 7 节非 JSON HostServices 为唯一可信注入，freeze/load 声明保持一致，动态不可用由 gate 拒绝；不让 capability 随当前 UI/余额改变。旧无声明配置不回填权限。

## 独审提出并已补入的条件

1. 新 authority/security/resource helper 属行为身份：core 自动冻结适用的真实代码 proof，request 绑定实现集，load/consume/submit 复核；不能只冻结对象形状或要求插件手写框架 assets。UI 决定也绑定实际安全实现。此要求沿用 `experiments.py:251` 起现有 code proof 机制，不建新注册框架。
2. reserve 已落而尚无 accepted 的 prepare 失败窗口，若 P2d 仅能验证 accepted，明确 `pre_accept_release_unsupported` 并继续占用。不能虚构 accepted/retirement 退款。安全 pre-accept 释放另审；保守占用的运维限制须显示。

## 必需后续集成，尚未批准具体实现

第 9 节正确将两项列为 P2/P3 最终退出前必完：非空 scientific slot 的 exact sealed original→P2b 回调映射；人工等待封存后显式恢复原 pending call。当前只认可其责任、精确身份、无自动重放、无新授时/余额和复用 append-only recovery 的边界。native ref 版本/旧 ArtifactRef 语义、pending-not-prepared 的持久证明、原 owner 与恢复时限及具体 CLI/函数尚须分别独审，不能以本报告代替。

## 最少证伪与限制

实施负控应通过真实 dispatch/host consumer 证伪：pending 前任何 backend prepare/upload/reserve；同原请求换 call；普通 pass/错 subject/同 hash 异来源继承权限；JSON 注入 services；错实例/Origin/nonce 或过期决定；同 owner 换 package 重置余额；unknown 或缺 actual 维度释放额度；collect 重授期限。可信 provider/合成 HTTP 身份 fixture 只证明控制消费，不能证明真实浏览器、独立 native 身份或 TCAD 权限/执行。

本次没有审查未来 P3d2 的完整合同，没有动态验证 HMAC/HTTP、并发账本、跨 boot、真实包/模型/solver。P3d1 实施完成必须仍标“安全中间态，P2/P3 退出条件未满足”。
