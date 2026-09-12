# 历史判定与分析准入 R2 实施记录

2026-09-10。状态：P1/P2 源码、P3 定向验收、P4 本地目录/安装包一致性完成；正式安装与真实实例分析尚未进行，线上缺陷未宣称关闭。

依据：../../HISTORICAL_SIGNAL_ADMISSION_MINIMAL_REPAIR_PLAN.zh-CN.md，冻结 SHA256 76449194210618435a7e63aceab7e6016c9e36111701e647b0e5388442b58c86；计划复审见 ../input-validation-boundary/HISTORICAL_SIGNAL_PLAN_R2_REVIEW.zh-CN.md。

## 精确增量

三个生产文件与实施前完整快照在 baseline.json、*.before.txt 中，精确差异见 implementation.patch。此前工作树已有大量改动；此处不以累计 git diff 冒充本轮增量。

1. Root 将输入历史事实与审批所需当前判定分别读取，沿用现有 completed Run 和资格接口。
2. TCAD 与通用分析的 plan/review 使用既有历史材料用途，避免再次要求当前实施资格；保留类型/预算，创建前核对精确审查来源、父链、目标和通过判定。
3. 全局 current、作者/修订/物化的审查门禁、批准 provider 与执行审批、输出验收、恢复和数据库均未改。VM runner 无需同步。

增量静态复核见 IMPLEMENTATION_REVIEW.zh-CN.md；该复核由实施者完成，不冒充独立实现审查。

## 验收证据

原始命令、退出码、耗时、总树预算与峰值保存在 checks.json；完整 stdout/stderr 位于相邻 input-validation-boundary 目录的同名日志。组合有重叠，不累加成独立测试总数。

| 范围 | 结果 | 日志 |
| --- | --- | --- |
| 修复前实际物化计划、正式审查、收集入库，再升级 reviewer 的复现 | 正确复现 guard_rejected，未伪称通过 | check-1789039100145001137.log |
| 分析交接、评分工具、TCAD 输入/输出职责 | 67 passed，1 stress deselected | check-1789039368989563892.log |
| 升级交接、历史兼容、证据/参数资格对照、结构/来源负例 | 33 passed | check-1789039500214127619.log |
| 新构建 wheel；两条 installed Root/Worker 升级交接；安装合同一致性 | 3 passed | check-1789039549103328261.log |
| 通用角色合同 | 111 passed 后遇另一文件的旧测试夹具问题；不将整个命令计为通过 | check-1789039641653543913.log |
| 修正夹具后的共享审查、审批、draft、通用工具、升级交接与错误生产者负例 | 62 passed | check-1789039726597159992.log |
| 最终动态目录 | 默认 45 项、可选 figure 50 项编译成功 | check-1789039775781473470.log |
| 实际安装环境 Root/Worker 同源投影 | 14 项输入规则一致，draft_from 保留 | check-1789039837886271675.log |

最后三文件生产代码从首次修复后未再改变，实际安装验证对应最终生产源码。升级测试同时验证历史 pass 可读、当前 exact reviewer 资格不通过、新分析正式 completed、author 仍拒绝旧实施资格。另有真实错误 review producer、无完成记录的伪审查、非通过审查、错误计划及同字节跨执行日志负例。结构/target/verdict 的最小输入 checker 测试与 Root 交接测试分开，不把直接函数测试声称为真实 Worker 运行。

测试夹具修订原因保留：新增 author 负例补 instruction 后观测到最早的 producer_contract_changed（审查摘要传播到了 materialized plan）；通用分析报告使用其要求的输入别名而非 TCAD 自定义证据键；非通过审查负例移除同一背景对象的重复绑定；旧多计划审查夹具关闭不适用的单计划输入 checker，控制层精确多对象审查验证保留。没有为测试失败放松生产约束。

## 兼容与资源

catalog-before.json 与 catalog-source.json 是本轮精确前后目录。digest-impact.json 表明只有两个分析 Operation 变化，其余 48 项不变；没有全局 ABI 变更。旧 review 能作为历史分析事实，不会因此满足当前资格。旧活动 Run 不由新合同验收；当前 failed 分析保留原状，不伪造可恢复草稿。

测试单进程串行，由 Root 执行，没有并行测试或求解器。预算 min(512 MiB, MemAvailable/4)，峰值 157315072 字节（约 150.0 MiB），无超限终止。没有跑全量或压力测试。

git diff --check、限定 Python 的 AST/空字节检查通过，源码及测试哈希见 source-check.json。仓库不包含技能提到的两项额外脚本，未虚构执行；本次未改变其对应全局架构声明。

## 下一步与完成标准

按现有匹配 core/插件集合安装并重启 Codex；无需改 VM runner 或重跑求解器。重新绑定 M7-test0 后，继续以原 plan_3、review_6、reviewed_package_2、execution_1 的精确产物和目标进行 preflight，通过才创建新分析、派发控制返回的角色。

不以重审原计划、删除诊断证据、替换历史输入或修改旧 Run 绕过准入。只有新 Run completed 且封存分析可读，才能关闭线上缺陷。该步骤依赖正式安装，未包含在本次本地通过结论中。
