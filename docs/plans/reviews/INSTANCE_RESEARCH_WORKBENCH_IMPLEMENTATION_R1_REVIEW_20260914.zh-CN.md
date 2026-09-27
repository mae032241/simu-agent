# 实例研究工作台实现 R1 独立工程审查

日期：2026-09-14。当前总体结论：**REVISE，尚未进入 P6 交付验收**。

审查基线：`da220ce31c8cc9f9a60542a018b279e2f331f4c0`；对象为当前未提交工作树。
依据为已通过的[实施计划 R3](../INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md)。本记录只审工程边界，
未读取真实科研 state、审定科学结论、执行测试/build/服务或修改生产源码。作者与主代理仍在修订归档主体，
以下“已闭合”只适用于明确列出的维护边界，不是全部工作台或归档能力通过。

## 首轮发现与修复复审

| 项目 | 首轮因果与影响 | 本次状态 |
| --- | --- | --- |
| P1：open 的旧 Run 写入归属 | `worker_open_assignment` 跳过实例门后，参数校验错误或 hardened 旧 transport 过期错误可能向正在归档的旧 Run 写诊断、workspace report 和 timing | **入口已闭合**：open 参数在记录和 transport 前验证；仅本次已选 Run 可获得 open 诊断/timing；hardened 重开旧 assignment 先核对其精确实例 |
| P2：无实例依赖的只读调用 | 静态绑定实例被关闭后，统一 active 检查误挡 `operation_catalog`、`instance_list` | **已闭合**：两个目录/列表读取保留全局读取保护，不要求缓存实例 active；旧实例写入继续拒绝 |
| 收集 scope 回归 | 诊断标签 `scope` 被误当实例准入凭据，破坏既有内部/无归属调用 | **已闭合**：真实 binding 决定实例门；有 owner 时诊断归属该实例，无 owner 时仅持可继承 global writer lease |
| P1：恢复完成与清门的崩溃窗口 | 原实现先持久标记 restored 且禁止 resume，再清 marker；两步之间硬退出会留下不可继续的维护门 | **归档调用链待最终复审**；本次仅确认新 `handoff` 原子替换 primitive 及其精确旧/新 job 恢复配合 |
| P1：活动 event_id 复用 | 删除最新 `run_activity.rowid` 后，另一实例正常追加活动会复用原编号，导致归档实例恢复冲突 | **统一编号 primitive 已闭合，归档接入待复审**：高水位与活动写入同事务；全部七处 INSERT 已统一。当前施工版本的 Records 筛选仍须单独处理无 `run_id` 的计数表 |
| P1：复制期间新增共享 recovery 引用 | recovery 的共享判定仅来自预览；晚来的其他实例同 digest 引用可能遭清理删除 | **待复审**：必须在临界区保护整个 recovery/staging 树，含目录删除，不能仅复核 CAS |

## 本次已核对的边界

- Local/hardened Worker 的外层维护保护覆盖正常工具、错误记录、最终 timing 和 transport 释放。
  新 open 未选中 Run 时不继承旧 Run 的科学或工程记录归属；维护拒绝不写成 Run 科学失败。
- Collection 的独立共享描述符传入 guard 子进程，并覆盖监督线程最终日志、进程退出和占用释放。
  无归属的历史执行不获得推断出的实例身份，也不失去全局写入保护。
- `InstanceMaintenance.handoff` 要求同一实例排他锁及精确旧 job，通过临时文件 fsync、原子 replace、
  目录 fsync 替换 marker；替换前后均保留维护门。恢复索引记录 previous_job_id，resume 核对新/旧 job。
- `RunService._append_activity` 在调用者原事务内分配和插入；失败回滚同时回退计数与事件。
  初始化及追加取既有高水位和现存最大 rowid，兼容历史显式编号，不重编号原事件或改变分页游标。
  已检查 `runs.py` 三处及 `tool_evidence.py` 四处写入全部使用同一分配器。
- 其他迁移表没有同类普通行删除后的序号复用：审批为 nonce/text 主键，旧 artifact_events 为 text 主键，
  UI events 为 AUTOINCREMENT，run_tool_evidence 为 `(run_id, ordinal)`，其余为文本或复合身份。

新增 `run_activity_sequence` 是共享存储元数据；归档不能将它当目标实例独占记录迁走或用旧快照覆盖。
它属于此次必要的数据库结构增补，交付文档需明确，不能再笼统声称五库 Schema 完全不变。

## 证据与仍未覆盖的验收

已读取主代理提供的 [p5-writer-second.log](../evidence/instance-workbench/p5-writer-second.log) 及对应
[资源记录](../evidence/instance-workbench/p5-writer-second.json)：86 passed、1 deselected，退出码 0，
峰值进程树 RSS 332.59 MiB，预算 512 MiB。本审查未自行重跑测试。此证据覆盖列出的定向测试集合，
不证明完整归档事务、跨进程硬崩溃恢复或最终安装路径已经验收。

归档主体仍需复审共享 recovery/CAS、完成标记与门清理、五库恢复和计数表接入。
旧 Records 实现的限制是单库全部记录 16 MiB、全 runtime 32 MiB，且枚举全状态最多 50,000 文件，
并非只限制目标实例；其他实例增长也能阻断小实例归档。作者正在修订规模实现，最终范围须按交付源码重核。
当前 local backend 的历史 Run 仍不能证明 native writer 已停止，属于明确未验收边界，不能计为 Fig4 归档通过。

修复完成后仍须按 R3 完成归档—浏览—恢复—接续、普通科研回归和独立最终复审，方可改变本记录的总体结论。
