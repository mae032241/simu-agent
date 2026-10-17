# P4c2 可写恢复边界独立静态审查

结论：**认可本轮阻断结论与收窄边界；完整可写归档恢复仍 BLOCKED，未授予实现或动态资格。** 基线 `71394a3`，对象仅[冻结短设计](P4C2_WRITABLE_RESTORE_BOUNDARY_DESIGN_20261017.zh-CN.md)，不是 restore 实现审查。

## 静态依据

- `protocol.py:30` 的 `require_current` 只校验 settings/CURRENT；`contracts.py:71` 校验可复制的 settings 字节，`controller.py:232` 取得所给 root 内文件锁。它们不能区分原 owner 与复制出的另一把锁；同 path/goal_id/hash、目标为空、旧 PID 不可见均不能授予恢复权。
- `instance_archive.py:327` 明确 `restorable=False`。包没有 owner 交接或导出后账本高水位证明，且排除 native-homes/私有密钥定位原件，部分外部依赖只登记。完整 hash 验证不能证明不存在更晚消费、撤销或外部提交。
- 设计第 15–26 行复用包内只读 inspect 与原 live 合同；不把归档变成 control 输入，不给旧 seal 补 positive pending-set，也不承诺跨 boot 一律能读/继续。原调用 unknown/lookup None 继续不重发，当前预算、session、权限条件仍适用。
- 设计第 39–58 行列前台与后台实际写者的共同 owner 接缝，未假称只在 restore CLI 检查一次即可安全；同时不实施新 owner/key/ledger、material repair、live 目标或第二调度库。

未来 fencing 的语义须是阻止旧 owner 再产生重复的新副作用；已经存在的外部作业仍按原身份维护、核验和收集，不能把永久 fencing 理解为必须销毁成果或撤销全部管理员维护路径。此次边界认可不要求另建这一协议。

## 检查及未完成项

仅静态阅读本文、相关已提交归档/协议/控制入口、旧消费者，以及限定 Git diff/空白检查。没有项目 import、pytest/collect、业务 CLI、模型/服务器、构建/安装或远端执行。没有修改生产代码。

P4c1 只读导出/包内查看和原目录现有恢复入口保持原合同；**P4c2 单 owner 交接、所有写者共同准入、当前消费状态不回滚及失败半成品不可推进仍未实现**。不能据本文把 P4 全部恢复能力标成完成。允许提交本节点边界记录，后续消费者退役独立评审。
