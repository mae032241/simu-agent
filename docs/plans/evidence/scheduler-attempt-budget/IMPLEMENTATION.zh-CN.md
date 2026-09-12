# 调度侧尝试预算：实施与交接

2026-09-12。源码、隔离工程验收及生产安装已完成；真实 Fig.4 有界形貌分析已封存。
当前结果与限制见 [现场记录](LIVE_FIG4.zh-CN.md)；下面保留实施时的步骤与安装前交接，文末记录实际收尾。
本轮依据用户直接授权，未开展独立 Agent 审查；完成了本地语义与跨边界检查。

## 实施

- 现有 Root preflight/invoke 增加可选正整数 `max_attempts`，是恢复链累计 Run 数（含首次）的调度预算；各 Agent Operation 通用。
- 显式值成为新请求的不可变组成部分，写入现有 recovery_policy；后继省略时沿绑定的恢复来源继承。无显式值的旧链保留旧默认规则；不修改旧 Run 或科学审查次数。
- 默认预算进入目录投影，实际已用数/上限进入 Run recovery.attempt_budget。预检与创建共用逻辑，事务内再计数；同一请求重放不消耗额外次数。越额说明具体次数与 $.max_attempts，不再混为草稿不可用。
- 多轮工具恢复证明保留分立来源作用域；不同 Run 的同名 attempt_001 不混并。增加可选 ancestors，旧证明仍能读取。无本轮工具调用时透传已有证明，不堆积空层。
- 未改变单次时间/内存、工具次数/字节、精确来源验证、执行审批；未新增 Operation、科学必填项、数据库迁移或 VM runner 修改。

修改相对本轮开始时的脏工作树快照，见 baseline.json、changed-files.json、implementation.patch。
生产源码 5 个文件，另有 2 个测试文件、scheduler 角色与决策索引；证据目录保存本轮新增计划和记录。

## 验证

最终两组定向检查：99 项通过，1 项已知旧断言失败。没有重复累加先前通过数。
失败是 test_l2_run_invariants.py::test_status_is_pure_and_failure_recovery_is_explicit 的第 536 行：
整字典断言没有容纳原已有 diagnostics 字段，输入身份错配仍被正确拒绝；修改前复现见
../analysis-work-preservation/check-1789198069018444631.log，本轮没有改写该测试或隐藏失败。

重点覆盖：resume/draft 两条链的显式扩额、预算继承、旧 Run 不变、越额诊断、同名重放与变更冲突、
过期预检后的事务拒绝、跨实例/损坏草稿仍拒绝、严格整数与非 Agent 不适用、MCP Schema、
第三轮接手（有/无新增计算）、冲突 attempt_key 的来源隔离、伪造结果拒绝、历史完成证明无需重算。
现有收据上限、失败诊断、历史引用、声明投影测试也通过。

三个 wheel 串行构建，隔离环境编译 45 个 Operation；安装版 Root MCP 接受预算覆盖，实际 Worker
stdio 进程完成三轮恢复与最终提交。原生数值计算 1 次，恢复后只补图；两个不同来源的评分收据都正式提交。
这只是工程夹具，不是 Fig.4 的科研结论。五个生产文件与安装包字节一致，见 installed-smoke.json。

所有测试和构建串行，512 MiB 地址空间及进程树 RSS 监控、150 秒墙钟限额，BLAS/OMP 单线程；
最高观测进程树 RSS 约 286 MiB，无 OOM 或预算终止。初版测试发现的入口漏传及诊断构造错误已修复；
一次安装探针变量名错误也已修复，原始失败日志全部保留在 checks.jsonl。未执行全量测试。

git diff --check 通过。按原安装目录、状态、workspace 和现有命令适配器执行部署 dry-run 通过；
系统单元验证有既存 netplan 权限及 snapd 键告警，未修改相关服务。preview 未改生产安装和数据。
技能提及的旧 architecture validator/bench 脚本不在本版本，未以其他快照脚本替代验收。

## 下一步

按 DEPLOYMENT.zh-CN.md 安装并重启会话，核对实际服务接口与编译角色，再继续 M7-test0 的 Fig.4。
现场仍为 fig4_morphology_closure_1 failed、无 sealed_output；77 个文件已保全、原目录保留，pending 为真。
当前安装版尚不支持新预算，未通过改名、修改旧 Run 或创建平行控制服务绕开限制。

安装后从该失败 Run 的受控草稿建立新 Run，显式 max_attempts=3，表示在已用两次基础上增补一次。
沿用确切原执行计划/审查、参考证据和 current_progress；读取受控可用状态后再按实际目录返回角色调度。
设计与分析目标仍为掺杂深度、形状及前尾平台；只补必要工作，得到明确、有证据支撑的有限结论，
并按编译目录所声明的独立审查关系处理。若出现新的工程失败，应定位并记录，不可把失败当科学结论。

续接内容与准备成本已列为后续第一优先级，见 CONTINUATION_PRIORITY_1.zh-CN.md。

## 2026-09-12 现场收尾

用户安装并重启后，五个生产模块核对匹配，原实例已绑定。fig4_morphology_closure_2 以显式累计预算 3 完成真实续接，
两次输出修正后在截止前约 18 秒完成，60/60 单元和有限科学结论已封存。总体机制与带不确定度的拟合判定仍 inconclusive。
具体科学边界、旧执行 failed/97 及日志/拒绝问题见 [现场记录](LIVE_FIG4.zh-CN.md)。上文未安装状态是实施阶段记录，已由本补充推进。
