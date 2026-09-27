# 读取流程回退修订：实施记录

日期：2026-09-19。状态：**源码、定向测试、真实失败路径回放和隔离安装完成。已部署并完成原生 D 两轮验收；独立复审未执行，首次读取误用仍保留。见[验收记录](READING_FLOW_NATIVE_D_ACCEPTANCE_20260919.zh-CN.md)。**

对应[修订计划](READING_FLOW_REPAIR_PLAN_20260919.zh-CN.md)。本轮保留 [C 组 token 回退结论](MECHANICAL_READING_NATIVE_C_ACCEPTANCE_20260919.zh-CN.md)，不改写历史审查结果、不恢复 Agent 比较哈希的做法。

## 已修订

1. **输入续读。** 首次明确材料/文件、字段和预算，裸 next/repeat/restart 自动沿用当前选择；选择和位置在既有锁与原子更新中提交。切换材料明确指定，读失败不切换；无选择时要求重新指定。版本 1 工作区收到完整选择续读的兼容提示，旧游标 helper 继续定向原文回退，冻结文件不热改。
2. **受控接续指引。** worker_connections 从现有绑定表只读查询前序 Run；gateway 验证当前 profile 后内部传递定位。Local open 比较实际角色、Schema、工具合同，返回 reading_guidance。前序原件不可读则回退读取，不阻断任务，不假定同 compiled digest 就代表动态 Schema 相同。新任务、总体目标/输入索引、语言、预算及恢复要求始终保留。没有新增表或改变 attach 准入。
3. **Schema 自动补读。** 新 CLI 首次输出总览和必需闭包，随后按同一原件只补缺少的定义；多个 field 合并，共享定义不重复。内部缓存放 .read-input，不作为恢复证据、不跨 Run。--full 总能恢复原文，原件变化/缓存损坏自动刷新；不可保存时返回完整所需视图。已有 read_schema Python API 和显式 definitions-only 模式保留，CLI 不回传内部哈希。
4. **提示与文档。** 更新安装角色、dispatch 和双语架构。声明缓存不证明记忆或交付，不禁止必要重读。基础角色指引（text-disabled 配置）6,127 → 5,827 字节；接续时会多一条短阅读指引，其实际 token 成本必须计入 D。

生产修改限两个 reader、worker_connections 只读查询、gateway/Local open、codex 角色与 dispatch。local_workspace、科学 Schema、提交门禁、审批、执行权限未改。源码实施阶段没有运行 TCAD 或生产部署；用户后续部署及原生测试见验收记录。

## 验证

所有测试串行，沿用 768 MiB 进程树采样 guard，不跑全量测试。

| 检查 | 结果 | 采样峰值 / 时间 |
|---|---|---|
| 首轮 reader 旧回归 | 19 通过、1 条旧 CLI 哈希断言失败，随后修正 | 76.19 MiB / 1.43 s |
| reader、Schema、统一 MCP | 32 项通过 | 279.48 MiB / 7.90 s |
| 设置、生成角色、指南、接续/实际恢复 | 38 项通过 | 132.95 MiB / 11.10 s |
| 最终 reader、MCP 接续、架构矩阵 | 19 项通过，含与前组重叠项 | 114.61 MiB / 3.06 s |
| C 真实失败调用回放 | 通过 | 60.01 MiB / 0.58 s |
| core wheel 隔离安装 | 通过，7 个安装文件一致，独立输入/Schema helper 生效 | 96.75 MiB / 2.46 s |

初轮断言仍要求 CLI 提供 sha256，现改为检查不输出哈希、Schema 更新后确实读取新约束；没有放宽科学 validator。现有 datetime.utcnow 警告不属于本轮。各日志、当前 C 源码快照、指纹与脚本见[证据目录](evidence/reading-flow-repair-20260919/)。

关键负例覆盖：裸续读保留模式/字段/预算；缺选择、缓存损坏、失败切换、源变更、末页 repeat；Schema 并发字段去重、未知字段、缓存不可用和 full 恢复；首次无复用提示、同线程接续、gateway 重建、动态 Schema/工具合同变化、前序原件缺失和模型不匹配；输入/Schema 缓存不进入恢复扫描。不同 Run 不继承本地阅读缓存。

## 同正文回放

[回放结果](evidence/reading-flow-repair-20260919/replay_c_failures.json)使用 C1 的实际 assignment 与 Schema；不导出科学正文、不猜测片段。

- C1 角色读取原顺序：7 次调用，4 次错误；新入口：2 次读取，0 错误，精确拼回相同角色正文，repeat 能重发末段。回复 10,054 → 5,454 字节。
- C 的总览 + evidence/findings/hypothesis_reviews 序列：32,663 → 10,795 字节；总览从 4 份降至 1 份，所有原定义闭包逐值一致。full 恢复完整 Schema 成功。

这是有界路径修复证据，**不是原生 Worker token 验收**，不证明模型必然采用最优读法或停止重复阅读。回放不复刻模型写作随机性；下一次测试需同时比较 C 与此前更好的 B，不能只挑较差基线。

## 源码实施时的验收清单（部署与 D 已完成，见后续验收记录）

- 本轮独立实施复审尚未执行；可使用逐文件 before 快照审查，不能把整个已有 dirty tree 当成本轮。
- 用户重新安装并重启后核对 helper、角色和 gateway；无需同步 VM runner。
- 原协议 D 两轮 sol/medium、600 秒，组间新 Agent、组内复用。核对精确输入与科学合同，报告首轮/接续/整体窗口峰值、净增长、阅读错误、提交拒绝、截断和完整交付。原生硬内存限制仍未覆盖。
- 不以离线字节收益或静态审查宣布 token 目标已完成；若仍回退，保留失败，不重复试跑挑样本。
