# 实例 Agent 执行配置实施 R2 独立复审

2026-09-15。结论：**PASS（精确源码候选）**。R1 唯一 P2 已闭合；本次修订未发现新的阻断问题。最终四 wheel 重建及隔离安装核验仍待完成，此 PASS 不表示已经完成安装或生产验收。

## 精确范围

继续应用 [scid-cross-boundary-review 技能](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/.agents/skills/scid-cross-boundary-review/SKILL.md)，以 [R1 独立审查](INSTANCE_AGENT_EXECUTION_SETTINGS_IMPLEMENTATION_R1_REVIEW.zh-CN.md)为已审边界，对 [CANDIDATE_R2.json](../evidence/agent-execution-settings/CANDIDATE_R2.json)作增量独立复核。

独立计算确认：R2 全部 37 项文件散列均匹配；计划散列仍为 `d76e5ee486c1595fa7dc77c5776f3319b0650c9992f1914190b6ed69c9c731ec`。R1→R2 只有 `instance_archive.py` 和 `test_execution_settings_archive.py` 两项变化。将生产代码的这一行复原后，其完整文件散列与冻结 R1 一致，确认没有夹带其他生产修改。

## P2 闭合及反向影响检查

[instance_archive.py:566](../../../src/scidiscovery/artifact_agent/service/instance_archive.py#L566) 的 `_migrated()` 现在通过现有 `execution_settings_tombstone()` 比较旧墓碑。其效果仅为：对原来缺少的实例配置三列补固定 NULL/0。辅助函数使用原行覆盖默认值，档内已存在的配置值、修订号和更新时间不被替换；所有旧字段仍参与整行比较，活动行也没有被删减或重写。

空实例恢复提交前，活动 closed 墓碑与受限投影相同，故可回退到 archived；提交后，活动实例行已恢复原状态，与 closed 墓碑不同，故回退仍被拒绝并要求 resume。含业务记录的分支、结构检查、事务写入、归档身份及文件清理逻辑均未修改。没有扩大旧档兼容范围，也没有引入新的迁移或状态机制。

新增测试覆盖旧/新空档与提交前/后四种组合。测试通过正式 archive/restore/rollback/resume 服务路径，在 `after_restore_copy` 和 `after_database_commit` 故障点中断，再构造新的服务对象处理恢复；断言提交前可回退后再恢复、提交后拒绝回退而可续接，并核对全归档文件散列不变。该测试直接覆盖 R1 独立复现的故障条件，也检查了不得回退已提交数据库的相反条件。

## 验证证据及剩余步骤

已阅读而未重复执行：

- [p6-empty-archive-fix.json](../evidence/agent-execution-settings/p6-empty-archive-fix.json)及对应日志：9 passed，6.131 秒，峰值 118.72 MiB，覆盖归档回退和提交后续接的相关定向场景。
- [p6-empty-archive-boundaries.json](../evidence/agent-execution-settings/p6-empty-archive-boundaries.json)及对应日志：最终四边界组合 4 passed，3.016 秒，峰值 109.17 MiB。

两组均记录为串行、512 MiB 自有进程树限制，无超限终止。R1 的独立故障复现与新档对照已保存在证据目录 `scid-settings-review-*`，保留了修复前错误和对照成功的记录。本次仅运行只读散列核对，没有启动测试、平台 CLI、浏览器或科研任务，没有修改生产源码和既有报告。

R1 已审的配置/科学职责分离、预检和调用快照、提交、恢复预算、平台动态角色、UI 权限/CAS、安装首次创建及升级保留路径均未发生变化；R1 披露的既有测试失败和实际平台证据边界继续适用。

源码候选可进入按计划的最终四 wheel 构建与隔离安装核验。应确保包内容与本 R2 候选一致，再完成安装入口及必要合同核对；生产安装后的实际实例设置和正常科研任务新语言验收仍须独立完成。
