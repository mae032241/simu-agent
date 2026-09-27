# R5-B：领域无关审批生产者族实施记录

状态：第二轮独立审查已通过，R5-B 完成并放行 R5-C。

## 目标

删除审批调用对固定端口、固定 Operation、固定 Schema 和固定领域角色的认识。审批投影器只接收
由同一启动期编译目录、任务完成合同、变换父链和实例绑定证明的完整生产者族；是否需要某个族
仍由插件自己的审批合同和投影器决定。

## 最小实现

本阶段没有增加数据库表、注册表、审批服务或状态机，只增加两项通用数据：

1. 每个 compiled Transform 产物由调用器统一写入
   `operation_invocation_fingerprint` 标签；插件不能提供或覆盖；
2. `ProducerOutputFamily` 增加无状态的 `family_identity`，仅用于一次审批投影中的一致性检查和
   去重，不持久化。

生产者族解析对每个审批输入执行同一算法：

- Agent 产物由完成任务、当前 OperationAuthority、主输出合同及全部集合输出合同还原；
- Transform 产物由当前编译 Operation、调用指纹、顺序父引用、当前实例 binding 和完整输出端口
  还原；每个输出的端口、数量、类型、Schema、媒体类型、大小和规范输出标签必须一致；
- 只有当 Transform 同时声明唯一 `usage=revision_base` 和唯一 `usage=change_request` 时才尝试
  修订关系；patch 必须是当前编译 Agent Operation 的主输出，其 `revision_base_port`、任务输入和
  base Schema 必须精确指向同一 base；
- 同一不可变成员集合只交付一次，同一族身份产生不同成员时失败关闭；递归深度和环路仍有界；
- Root 不按审批端口、Operation id、插件、角色或 Schema 选择解析分支。

领域投影器不再假设上下文全局只有一个族，而是按自己声明的主对象引用选择唯一匹配族。该变化
只属于插件展示规则，没有形成核心 provider 表。

## 盲插件证明

新增 clean-wheel 测试插件 `blind_producer_fixture`。核心源代码不认识它的 Operation id、端口名和
Schema。它声明：

- 一个产生主对象和两个附件的 Transform；
- 一个产生有界 patch 的 Agent；
- 一个应用 patch 并产生修订对象和差异的 Transform；
- 一个要求完整对象族的 Approval。

真实入口测试覆盖初始族和修订族成功，以及附件遗漏、指纹缺失、指纹漂移、摘要漂移、跨实例
对象、同族多 subject 去重、同父链不同指纹隔离和同一身份两套成员失败关闭。独立安装态测试从
唯一 `scidiscovery.plugins` 入口发现插件，并通过真实 `operation_invoke` 创建审批。

## 第一轮独立审查与修订

第一轮独立审查真实复现了一个阻塞反例：当主对象和附件共享 Schema 时，附件能够被 Agent patch
和修订 Transform 合法消费；旧解析递归得到附件所属完整族后，没有证明被修订 base 就是族主
对象，因而可能把附件错误提升成新的族主对象并创建待审批请求。

修复保持为一个通用守卫：递归得到 `base_family` 后必须满足
`base_envelope.ref == base_family.primary_ref`，否则不构造修订族。没有增加附件修订协议、字段、
实体或注册表。盲插件现固定让主对象和附件共享 `blind.object.v1`，新增真实
produce→附件 patch Agent Worker 文件闭环→revision Transform→Approval 负例；结果必须是审批
投影失败且不存在 Approval binding。原主对象修订正例继续通过。

第一轮报告保存在
`reviews/R5_B_GENERIC_PRODUCER_FAMILY_INDEPENDENT_REVIEW.zh-CN.md`，其“打回”结论保留，不能由
本文件覆盖；只有第二轮独立报告可以放行。

## 修订候选证据

- R5-B 及既有审批/修订聚焦测试：41 项通过；
- 盲插件源码态正负例：8 项通过；
- 盲插件 clean-wheel：1 项通过；
- 全仓严格串行：262 项通过，92.73 秒；
- `git diff --check` 与相关 Python 编译检查通过；
- R5 冻结结构门通过，`src/scidiscovery/operations/` 保持 7 文件、2060 行；
- generic Root 的生产者族解析区不再出现旧固定提取端口、intake 修订 Operation 或设备参数角色。

第二轮报告
`reviews/R5_B_GENERIC_PRODUCER_FAMILY_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 已独立重放第一轮
反例、合法主对象修订和 clean-wheel 入口，并明确给出“通过，放行 R5-C”。R5-B 至此完成；该
结论不预先批准 R5-C。
