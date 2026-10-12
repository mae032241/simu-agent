# T0：既有公开轨迹与全池诊断测量

日期 2026-10-12；源码 `dev 287b2e2`。只读源轨迹，未运行测试、模型、训练、原实例或评估器；只写本外层报告及 `measurement.json`。后者是机械明细，不投递科研角色。本文为 T0 输入，不是效果验收。

## 1. 计量口径与 W 成本

- 来源：外层 `.trial/rootless-n5-cov-20261011/instance/{jobs,project/nodes,native-evidence,native-homes}` 与 `.trial/rootless-hwa-live-20261011-02/instance/` 同结构。每个节点只读 `usage.json`、`science-task.json` 和已有 `sessions/**/*.jsonl`。
- 按 `token_usage_record.payload.response_id` 去重，累加原 response usage；两场全部节点均与 `native-evidence/NNN/usage.json` 三字段逐值相等。总 tokens=input+output；cached 是 input 子集，不再加。非缓存输入+输出是诊断量，不是账单金额。
- request input 为每条已记录响应的 `input_tokens`，不是平台内存驻留量，也不是独立科研步骤数。阶段秒数用 session 中 task_started/task_complete 的 UTC 时间戳；排除节点间隔，不能代替宿主 active ledger。未封存的 H017 仍在总消费分母中。
- 组件 bytes 用 JSON `ensure_ascii=False,indent=2` 加末尾换行测量；packet bytes 为真实文件大小，不换算 token。

| 场 / W节点 | 总tokens | 非缓存输入+输出 | 阶段秒 | task bytes | history/search bytes | 响应数 | request input 首→最大 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N5 W002 | 638,834 | 67,058 | 387.040 | 5,831 | 1,583 / 2,646 | 18 | 12,630→50,241 |
| N5 W004 | 1,129,054 | 91,486 | 521.363 | 9,033 | 3,104 / 3,104 | 24 | 12,630→68,475 |
| N5 W006 | 604,810 | 70,282 | 360.859 | 9,724 | 3,114 / 3,564 | 16 | 12,630→54,533 |
| N5 W008 | 1,076,042 | 95,306 | 635.466 | 10,904 | 3,235 / 3,650 | 23 | 12,748→70,219 |
| N5 W012 | 932,797 | 92,221 | 452.574 | 9,319 | 3,186 / 3,834 | 18 | 12,782→74,076 |
| N5 W015 | 1,125,317 | 95,173 | 666.370 | 9,606 | 3,371 / 3,815 | 24 | 12,782→68,666 |
| live02 W002 | 1,496,877 | 104,365 | 517.880 | 1,267 | 0 / 0 | 29 | 11,866→76,196 |
| live02 W005 | 1,516,468 | 104,500 | 547.325 | 1,284 | 0 / 0 | 30 | 11,866→76,666 |

N5 六 W 合计 **5,506,854 tokens / 511,526 非缓存输入+输出 / 3,023.672 阶段秒**，占全场 9,137,457 tokens 的 **60.27%**；其缓存输入为4,995,328。live02 两 W 合计 **3,013,345 / 208,865 / 1,065.205 秒**，占全场5,650,356 tokens的 **53.33%**，缓存输入2,804,480。N5 A合计2,500,716 tokens，live02 A合计1,363,499；交接与 A 成本也不能略去。

N5 W 的协议依次6/6/6/7/8/8；live02是协议1。N5经过多次授权恢复与额度修订，live02两轮、不同历史实现与停止预算；公开train/val/meta/harness相同只证明输入条件相同，不使两场成本成为受控对照。不能从平均每W较便宜推出框架效率提升。

交叉证据：仓库 `docs/plans/evidence/rootless-n0-20261011/baseline.json` 的 live02 W成本、响应数、request input最大值与本次重算相同；原N5终态在 `.trial/rootless-n5-cov-20261011/resume-protocol8/final-result.json`。

## 2. 读取与自适应：能观察到什么

- 每 W 新上下文都显式读取 task、全局目标、前驱结论/若干原件。例 N5 W004 session 的 custom_tool_call #2/#3/#4，W006 #2–#5；live02 W005 #6通过已存pickle反查旧实现。这证明跨阶段重复阅读确实发生，不能把每次必要来源读取直接判成无效成本。精确旧实现投递已由N2改善，不能再用协议1反查路径证明当前缺陷。
- 保留的 tool `input_text` 输出，N5每W为78,582–155,539 UTF-8 bytes，live02为124,837/141,433；含控制工具包装、截断提示，不是原命令全部输出或准确token数。生成源码、数值表、科学核查均会驻留本阶段对话。live02几乎无历史packet却有76k input峰值，因此历史不是上下文增长的唯一来源。
- 当前数据**没有**逐文件实际读取字节/CPU、必要与无效阅读的科学裁判、全上下文驻留、媒体/压缩成本或工具注册成本的可分解测量。`measurement.json.context_read_call_indices`只是宽松文本筛选导航，生成程序内字符串会误匹配，不能当严格重复次数统计。

| 现有证据 | 可成立的结论 | 不能成立的结论 |
| --- | --- | --- |
| N5各W先写CONFIGS/RECIPES，再用同一脚本批量screen；W012 `artifacts/train_multitask.py`四fractions×两arms，W015 `artifacts/train_covariance.py`四settings×两stages；对应 `scientific_report.md`明称冻结网格 | 固定批次占显著可见部分；保留必要预承诺/对照，但H不必枚举整轮配方 | 50次run都无适应，或全部无效 |
| live02 W002 session tool #17（ordinal132）在已有粗筛之后写四个新lambda，#18执行；`artifacts/report.md:74–79`、`work/protocol.md`记载先粗筛再声明0.25/0.30/0.40/0.45 | 原生W已经能根据观测追加有限候选细化；不应先造helper系统才能自适应 | 已有候选父子关系被控制层完整绑定，或已验收通用树搜索 |
| live02 W005 `artifacts/scientific_report.md:92–97`明确主结果后追加联合幅度/残差诊断；tool #18/20保留fallback并正式提交run42 | 观察驱动追加诊断和保留旧候选可发生 | 诊断直接改变新候选配方；按隐藏分数选择 |
| N5 W004 tool #11/#14在失败日志后提高iteration cap并处理zero rows；W012 report:38记录报告顺序KeyError修复 | 工程修复是结果驱动动作，须保留成本 | 修复就等于新机制或科学搜索收益 |
| N5 A013→H014→W015、A016→H017的公开route与限制；终态H017未seal | A能要求新科学方向，预算可能先耗尽 | 每一个廉价实验都需要一次A，或候选级回退分叉已验收 |

**T3规模建议：首版原生W有界步骤，复用已有预算与谱系入口；允许数个廉价实验组成一步。先减少两套默认摘要与重复来源重建，再测必要工作集/单位有效步骤成本。没有因果测量支持新增辅助者。**

平台资格：当前旧role launcher `role-native-launcher.py:143`冻结 `multi_agent=false`；这里的native-bin helper只是可执行文件别名，不是科学辅助Agent。现有证据未证明新上下文科学辅助者启动成本、可观察释放/名额回收。**T3首版不用辅助者**，不为检查能力启动科研试验；未来需单独资格。

## 3. 92池：选择损失与资格限度（仅评估者诊断）

精确来源：`.trial/n5-live02-pool-eval-20261011/{manifest.json,final-summary.json,candidates.csv,REPORT.md}`；仓库 `docs/plans/evidence/ROOTLESS_N5_LIVE02_POOL_EVALUATION_20261012.md` 与独审记录。92/92已有模型均完成离线预测评分，无新增模型/训练/submit；输入公开数据一致，原实例before/after hashes不变。

| 场/槽 | reward | 对记录审计池最优损失 | 对全池条件性最优损失 |
| --- | ---: | ---: | ---: |
| N5实际run17 | 0.2172 | 0 | 0.5076 |
| N5历史非null A013推荐run34 | 0.1879 | 0.0293 | 0.5369 |
| N5公开验证最高run32 | 0.1520 | 0.0652 | 0.5728 |
| live02实际/A006文字保留run42 | 0.4205 | 0.0855 | 0.0855 |
| live02公开验证最高run15 | 0.0068 | 0.4992 | 0.4992 |

N5条件性池最高run19为0.7248，但无audit；记录审计池最高是实际run17。N5最新A016推荐为null，文字保留run17，不能把A013历史推荐冒称当前决定。live02无结构推荐字段，仅有A006明确文字保留。故**N5未收口是明确工程失败；不能据此声称实际旧提交必然造成正式得分损失**，盲替run34反而会降低此池记录审计口径得分。

N5为50/50，其中20记录完成audit、30缺audit；live02为42/42且42有记录audit。除实际submitted-model/receipt确切SHA外，历史audit没有将其另行拟合audit模型与当前candidate pickle加密绑定；此处“记录审计池”是历史证据口径，不重新授资格。缺audit永不变leakage=false。池内最高只作事后上界，不作为实际科学选择器。

公开val/隐藏recovery平均并列秩Spearman：N5 0.608717(n=50)、live02 0.290925(n=42)；公开val/条件reward分别0.600707/0.285019。相互依赖候选不是独立场次。数据支持评估盲区与选择规则还需处理，不能唯一归因搜索、框架或角色；不能按这些隐藏答案调公开规则/阈值，更不能反馈运行角色。

## 4. 给T0作者的逐函数复用/替换建议

源码位置均为仓库 `src/scidiscovery/research_loop/`、HEAD287b2e2；这里是设计输入，尚未删除代码。机械facts只有一份权威，多个投影/校验不自动等于重复账本。

| 精确接缝 | 处理建议/必须保留的事实 |
| --- | --- |
| `execution.records/reference/record/raw/identity`；`contracts.validate/seal_result` | 复用唯一本次成功execution原件解析与root seal；统一谱系不能重新读取初次failed raw，也不能复写旧job/schema/receipt |
| `history._source:257`、`direct_sources:272`、`resolve_implementation:305` | 复用原seal/raw与singlehop输入身份；派生/复用/证据关系由此解析，unknown不靠最新H/同文件猜归属 |
| `history._capture:123`、`capture:227`、`validate_observation:556`、`_validate_proof:582` | 保留不可重建的封存observer事实与原件快照。cov adapter仍外置；不能用mutable results.jsonl重采覆盖旧facts |
| `history.rebuild:321`中的view/detail/h_scope组装；`history.candidate_overview:388` | 替换为统一谱系重建和一种候选投影；保留分页原科学fields与evalkey/direction分组。candidate_h_scope/parent_candidate/action目前null，不得把observation_h_scope/implementation_owner当candidate origin |
| `history.bind:448`的recent/declared_limitations/h_lineage与`search.bind:254`的commitments/recent_w/focus | T2统一角色投影，删重复默认summary/limitations、两处recent W与索引拼装；保留必要失败边界与原页入口。现各自≤4096，不等于合并总默认包≤4096；共同包需一次byte预算 |
| `search._apply/assess_payload/project:184/198/214`、`launch_reason:359` | 保留H/A增量机制处置、screen/repair资格与准入；统一机制身份及原件入口，不能再平行存一份新mutable机制表。历史列表与search事实可共享原件遍历，不混科学优劣判断 |
| `search.project:245`候选new count/coverage、`search.bind:294`recent_w.meter；`history.candidate_overview:394`候选聚合 | new-count/coverage与meter直接引用同observer/nativefacts；删除重复候选/成本推导；W派发数、candidate数、A纠偏周期继续分别计数 |
| `semantic.outcome/validate_job/accepted/effective_route` | 保留部分应用、bounded unresolved、最多2作者补正与硬完整性边界；统一source/mechanism解析，不再复制谱系状态 |
| `correction._proofs:42/project:150/publish:275/gate:337/acknowledge:344` | 复用统一原件与原A计数；trigger/ack事实保持sticky与exact cutoff；不可用candidate数替代科学判断周期或因换名/分叉清零 |
| `budget.snapshot/node_report/used_steps/delivery_reserve/closeout_state`、`native.usage` | 唯一消费/额度/名额事实不变；谱系仅引用成本，不存第二份余额。obs token有迟滞，不设未经验证典型常数 |
| `delivery.freeze_sources/validate_sources/binding/invoke` | N6交付事实与确切资格保留；统一候选导航不能把observer ok/metric、代码handle升级成模型+audit资格。推荐/实际观测/确认操作保持区分 |
| `host-history/nodes`与`history.refresh` | 继续仅可重建cache。新统一投影若取代旧重复overview，可删除新协议旧cache拼装；旧1..8解释/恢复仍保留兼容分支，不原地迁移 |

**最小可落地选择：T1一份可重建事实关系投影，T2一份有界角色工作集，T3原生W按观测选下一步，T4单独冻结公开适用/未知规则；不新建搜索executor、candidate资格账本、辅助者状态机或收口余额。**


## 5. public cov 一次实际 run 的接口事实

只读原件：`.trial/loopx_thin_hwa_20261010/public-task/public/environment/harness/{exp_cli.py,runner.py}`。`exp_cli.main:358–359`的run仅接`--script`；`cmd_run:87`调用`[sys.executable,RUNNER,script]`，没有外部request ID或预定run ID。`runner.main:117–122`按台账非空行数+1分配ID，无锁；先写`model_runN.pkl`(159)，最后append `results.jsonl`并打印(178–180)。台账含run_id/script/started_at/metric/ok及score/model_path，不含request ID、script SHA或科学parent_plan。

`_read_results/cmd_results:100/114`与`cmd_status:323`是现有只读查询；没有run的resume/recover/request-key lookup。`--run-id`仅属`submit:266/362`。模型写后append前崩溃可能留下孤儿；同名script、猜下一个N或现存model文件不足以证明一次实际run归属。薄适配器只能在自己受管理的一次调用上下文绑定冻结科学计划/源码与完成row，明确外部普通shell覆盖范围；未知调用不盲重提。不能把不存在的MCP Operation作为T0实施接缝。
