# P2d 原调用永久未提交证明设计独审

结论：**设计 PASS，可按独立节点实施；不批准真实后端执行或资源退款。** 对象为 `P2D_ORIGINAL_SUBMISSION_RETIREMENT_DESIGN_20261017.zh-CN.md` 当前 context-manager 修订，基线 P2c `4f0a455`、P5 `3ac974d`。仅静态核对设计、原 submit/退役协议、history、recovery 与 search 消费点；没有运行测试、项目 import、CLI、进程、构建、安装或远端计算。

## 独立事实比伪终态更薄

`submission-retirement.json` 只证明原 exact prepared 永久未提交，公开为受统一 validator 保护的 `not_submitted` disposition；不添加 native terminal 状态、不造 external、manifest、completed、execution-observation 或科学失败。现有 `verify_observation` 仍只负责实际执行事实。

准入、progress、history、lineage、append-only recovery 与 P3d 共用一个 `verify_retirement`，不用各自从状态字符串推 absence。原 sealed unknown 只追加绑定旧 seal/row hash 的恢复证据；accepted 机会计数不退，原科学 seal、候选与指标不改。`execution_recovery.py` 当前只认已执行终态的限制需要在此 owner 窄扩展；不是另建恢复账。

## 权威、身份与竞态

- 冻结的可选 capability 和方法同时存在才支持；不扩大必需 managed methods，不用探测后端升级旧 call 的权限。
- receipt 验 accepted/scope/native attempt/mechanism/interface、prepared、原 intent 或被保护的无 intent、authority/target、完整请求/响应/永久协议的 exact bytes。已有任何 external/submission/已执行事实则不能判从未提交。
- `remote_runner_py36.py:440` 起 submit 与 `:499` 起 retire 复用 submission 锁；retire 核查原 digest，写 tombstone 并同步目录后才确认。`ssh_transport.py:403` 起将冻结 transport descriptor 映射到原 remote descriptor，响应重新绑定 local prepared digest；实施必须保留并校验这条原映射，不能只采信自报布尔值。静态协议存在不证明真实远端掉电/混合版本安全。
- found 返回原 external 后只按原权限 cancel，实际终态仍沿 query/manifest/observation；lookup None、忙、丢响应、timeout 均保 unknown/reservation，不重 submit、不退款。

独审要求并已补入的原子边界：`retire_original(call)` 为可选 context manager，wrapper 持原 call 的 Records lease，core 在 `with` 内核验和发布共同 receipt、对照重复原件，退出才释放。submit 取同 call lease，且在写 intent 前拒绝已存在的永久证明。这样不会在 wrapper 释放与 core 发布之间出现迟到 intent 破坏“无 intent”快照。backend RPC 不占 node accepted 短锁；本地 lease 本身不证明从未提交。

## 后续实施的最少证伪

检查 optional 缺失及 capability/code 变更拒绝；错 call/prepared/target/authority/原响应字节；已有 external 与 absence 矛盾；同 call submit/retire 发布窗口；回执丢失仍 unknown；重复消费不再 RPC；真实准入与旧 sealed recovery 解除该 call 的 unknown，旧 seal/计数不变。可信 fake backend 的锁/fence 模型只证明控制消费，不证明远端原子性。

P3d 仍是唯一 release owner，只消费同一 validator 的原 ref 并复核 reservation。P2d 不写余额，证据不授后继执行权限；缺原权限/目标/实现/协议时 unsupported。pre-accept 没有 accepted 的 reserve 失败窗口不在此设计中伪造证明，P3d 保守占用或另审安全释放。

未覆盖未来 P3 长时间 pending 的授权恢复、真实后端并发/掉电、跨 boot、权限隔离、安装发现与 solver。本节点实现与静态独审完成仍不能标 P2/P3 全体退出。
