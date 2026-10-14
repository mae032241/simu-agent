# U4 当前协议真实场：科研链通过局部边界，交付失败

日期：2026-10-14。候选 `96639a0`，gpt-6.1-sol high/default，安装包隔离启动。独立验收见 [复核](U4_COV_FINAL_RESULT_REVIEW_20261014.md)。

## 结论

**整场 U4 未通过。**H→W→A 已真实运行，注册实验和 W 封存不再触发上场的旧状态/scope缺陷。但控制层预留收口时 `closeout_unresolved / delivery_resolver_unavailable`，最终 A 未启动，没有框架确认交付。

流程：H001 → W002 → A003 → 审计复核 A004 → W005 → A006 → W007 → 收口解析失败。7 个科研节点均封存，26 次正式实验均有 accepted/completed 回执，无缺失。三个 W 均主动返回 review；**new_context 分片续接未观测**，不能将此前无模型通过代替本场验证。

## 成本与结果

- 新场 4,590,117 token，其中缓存输入 4,086,144；未缓存输入＋输出 503,973。H 270,432，W 3,734,656，A 585,029。
- driver 单调计时 2919.831 秒（48.66 分钟）；控制启用时长 2917.624 秒。墙钟显示受时钟变化影响，不用文件 mtime 推算节点耗时。
- 原授权总额 600 万 token／3600 秒，旧失败场保留其 215,639 token／310.602 秒。合计已观测 4,805,756 token；本场没有增额或 token 超额。
- 公开验证最高 **run26：0.9320**。实验侧最后提交 **run17：0.9119**，任务自己的 honesty audit 0.9382、leakage_flag=false；这不等于框架 adapter qualification 或目标效果。
- 最后 A006 推荐仍为 **run2**：它仅评估到 run13，对 run12 的均值优势和置信区间、公开审计分作保守比较。之后 W007 的 run14–26 未经新的 A 评估，旧推荐不能冒称最终选择。
- 未执行隐藏评分、原生对照或重复场；不得据公开分证明目标条件下更优。

## 覆盖与遗留

| H 机制 | 正式实验数 | 本场状态 |
| --- | ---: | --- |
| 自适应 OMP | 5 | A 已评估 |
| 凸稀疏恢复 | 8 | A 已评估 |
| 算子不确定性修正 | 13 | W 已封存，最终 A 未进行 |
| 批量自校准 | 0 | 未探索 |

- H 按列举顺序注册机制，仅解释首先筛选 OMP，没有逐项科学优先依据。当前单 focus W 的内部精修不能等同跨机制广度优先。
- A003 一次读取 W 报告与证据约 89,654 字节；上下文视图的相关性筛选仍需改进。工具日志文件大小不能直接当成模型输入 token。
- 在役用量不完整时保留 unknown/inflight 状态，软目标并非实时准确的 token 硬上限。
- 科研机制关系依作者声明；全部正式 run 自动采集不意味着任意 shell 诊断完整纳入台账。

## 交付失败定位

[独立诊断](U4_COV_AUDIT_UNKNOWN_REVIEW_20261014.md)：protocol 输入由控制自动追加，并非用户漏配置。`cov_delivery._current_guard` 在隔离 leaf 分支将 `_exact()` 返回的 Path 当成 bytes 校验 SHA/长度，存在确定类型缺陷。外层未保存 stderr，本场精确 traceback 未留存；实际 audit 和 closeout 均留下 resolver_unavailable，结合代码构成强路径定位。后续修复须用真实隔离 leaf 验证解析、审计、提升提交和确认，不再仅验证宿主直调。

现场外层 `.trial/rootless-u4-cov-20261014/`：`acceptance-summary.json`、`final-result.json`、`controller-result.json`、实例各节点原件。结束时 frozen_inputs_unchanged=true；旧场不迁移、不重放原 native 或外部动作，后续修复不热替换本场安装包。没有自动开启新真实场。
