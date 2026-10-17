# P2c TCAD managed wrapper 设计独立评审

结论：**最终设计 PASS，可实施**。[设计稿](P2C_MANAGED_EXECUTION_DESIGN_20261017.zh-CN.md)及书面补充已核对；root 已批准 experiments 两处窄消费点扩展。本结论不代表代码、真实后端或生产执行通过。仅文本/Git 及现有调用链阅读，未运行测试、收集、项目导入、CLI、构建、安装、模型或远端操作。

## 最终边界

- 新 wrapper 复用两底层 adapter、P2b 原件回调及唯一 Records，不造本地 command/entry/snapshot 字段。`result_protocol=None`，领域候选/评分/交付仍 unsupported。
- managed factory 构造无远端调用，固定缺可信 gate；配置无 allow/test/gate 路径开关。P3 未完成时在底层 prepare/upload 之前明确 production blocked；注册不等于启用。prepare gate 前只能本地核 descriptor/profile/package，不能调用会读取远端 capability 的底层验证函数。
- 单一可信宿主 gate 负责来源/正式资格/请求/目标/policy/累计预算原件，prepare 前 reserve，submit 再核原回执，不二次发额度。target 来自冻结宿主配置，不信 W payload。collect/cancel 只核原调用权限；CollectionContext 由当前原授权 remaining 裁剪，不能把操作 timeout 当 job wall 或恢复时新授整场额度。
- P2b metadata/open 仍是独立的精确冻结原件依赖，不把来源发现塞进 gate。真实接线缺失时含 resolved_inputs 为 unsupported，不造 Artifact 服务或按相同 hash/近似路径猜来源。
- 一次接受 lease 与持久 submit intent 区别明确：只有刚持有原 accepted lease 的 fresh owner 能首次提交，在 backend 副作用前以独占写保存意图。重启/已有意图只 lookup 原 prepared；None 是 unknown，不是未提交，不重发或退款。原 descriptor/name 始终对应同 call，lookup/query/cancel 均核原 external ID。
- query/status 不 collect。result/collect_original 只在原权限/remaining 内有界收集，核 manifest、日志、outputs 身份并封存原回执后才发布共同 completed。cancelled 的原 native_state 保留，只作工程 known_failed。已保留的终态后续只核原件，不反复查询/收集。

## 发现并收口的共通接缝

现有 `experiments.record_observation` 在 query 看到 native terminal 后会调用 result 并读取 completed。收集无权限/剩余资源或失败时，wrapper 不能返回中性 unknown 却让控制读不存在 completed，亦不能造终态原件。

root 批准仅增加两处共通处理：

1. result **显式 unknown 且尚无 completed 原件**时 observation 返回 None。已有 canonical completed 却与 result 矛盾仍按身份错误处理，不能宽泛吞异常。
2. 新 call 准入扫描全部 known terminal 都先要求 verified observation；缺证据保留原 call unknown，不放新调用。不会只对 cancelled 验证，而把缺原件的 succeeded/failed 误放行。

已在 waiting 的 W 保留原 raw/checkpoint/reservation，继续既有 terminal_unverified 路径，不自动重跑；终态初见而证据缺失可按现有控制边界封存 unknown 执行事实，不能抹掉普通科学结果。此处仅扩适配协议消费，不新建状态机或恢复预算。

## 实现独审与未验收

代码需验证 gate 前零 backend 副作用、wrong lookup/prepared/gate 拒绝、一次提交/丢回执不重放、unknown 不造 completed/不放后继，以及 opaque 原件完整保留。测试可注入可信小假 backend/gate，禁止公开旁路和安装/Root 环境；fake backend 不能证明真实 TCAD 身份、权限、SSH、solver、累计资源或跨 boot 合格。

准入、终态、恢复仍归 Records/现有管理路径；源码实现与最小负控完成后另做代码独审。P3b–d、可信 gate 与真实冻结来源接线未合格前，真实 prepare/upload/submit 继续 blocked。
