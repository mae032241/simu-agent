# 校验纠错与跨轮续研最小计划独立复审 R2

日期：2026-09-08。结论：**PASS（计划可实施性与最小范围）**。R1 的唯一阻断已闭合，未发现本次增量引入新的具体阻断。可按冻结计划开始 P1—P3；本结论不预先认证实现、安装、资格恢复或真实研究验收。

## 1. 冻结对象与本轮范围

- 当前计划及 [R2 冻结副本](../evidence/research-correction-continuation/plan-review-r2-input.md) 的 SHA256 均为 `acc011a04ff2b6b0d7b7b2383f921c56faafe1e360cc53fdbe13f9bc1f01c93c`。
- 比较基线为 [R1 冻结副本](../evidence/research-correction-continuation/plan-review-r1-input.md)，SHA256 `4e4b0c1d6ee6342b48a8519527d26e22f383dedf8e69683b7b0ecaddaaa4126b`；复审依据为 [独立审查 R1](RESEARCH_CORRECTION_MINIMAL_PLAN_REVIEW_R1.zh-CN.md)。历史 REVISE 报告未被改写。
- 源码根 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`，HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`。再次按 [完整源码基线](../evidence/research-correction-continuation/source-baseline-2026-09-08.json) 核对 `src/`、`plugins/`、`roles/`、`skills/`、`deploy/` 的记录，摘要及已删除文件状态均无不一致。
- 仅审两个冻结计划之间的增量及其直接源码依据，未重新展开整套架构审查。沿用 R1 已读的适用 AGENTS、审查技能、架构、科学设计宪章及约束依据。本次只写本报告，没有修改计划或生产文件。

## 2. R1 的闭合证据

| R1 要求 | R2 计划中的实际落实 | 复审判断 |
| --- | --- | --- |
| 有真实可实现的父名称查询 | 第 3.4.1 节（253 行起）明确扩展已有 artifact_catalog，以 parent_refs 的顺序调用当前实例 find_name，返回 parent_artifact_names。源码落点为 `mcp_root_instance_routes.py:246`；复用能力位于 `scheduler_bindings.py:516`。 | 闭合；不需要新工具或存储。 |
| 旧版本与实例隔离 | 255—256 行区分空列表与未映射 null；仅按精确对象映射，不回退 latest，不跨实例补名字，不返回内部身份。 | 闭合；复用既有稳定语义名选择足够。 |
| 有界、纯读 | 257 行规定直接父项 4096 上限，超限显式失败且不截断；不新增分页/递归服务，不更新逻辑状态。 | 闭合；边界明确，可在现有查询函数实现。 |
| 首轮与 revise 冷启动不猜原件 | 239、258 行规定物化计划从直接父项找原目标，revise 沿唯一 ExperimentPortfolio 父项回到物化计划；不从 intent 的同型反馈猜原目标。 | 闭合；对应 `general_science_experiment_operations.py:223` 的单项物化上下文和 `:149` 的 prior_draft/change_request。无须额外来源别名。 |
| 找到名字后实际交付新 Worker | 261 行及 P3 要求经真实 Root 查询入口恢复原件，再绑定到新 design/review 的实际文件；输入替换改变指纹，仅检查内部父引用不算完成。 | 闭合；覆盖查询到使用之间的边界。 |
| 可证伪的入口验收 | 第 3.4.1 节、P3、L4 和第 6 节覆盖同文本异约束目标、至少一次 revise、退休版本、跨实例 null、空列表、上限、纯读及新 Worker 文件绑定。 | 闭合；列出的两个测试文件实际存在，真实无聊天验收仍保留在 L4。 |
| 明确最小生产范围 | 第 4.1 节成为 13 个已有生产文件，仅新增 `mcp_root_instance_routes.py`。 | 闭合；没有扩大科学 Operation、状态机或数值算法范围。 |

## 3. 范围与标准未退让

本次其他变化仅为 R1 报告索引、P0 已发生证据的状态说明，以及把既有理由字段精确到 `proposals[*].value_assessment.rationale` 和 `priority_rationale`。没有新增 rationale 字段、目标身份实体或进展包装对象。

R1 已核对的两个 curve 文件、三个 TCAD 文件、目标模型与物化、feedback/context_sources/引用规则、Agent inventory 例外、ABI 更新等方案均未被本次增量扩展或削弱。未覆盖总体目标及同 observable 目标的科学影响仍交由设计 Agent 判断并由独立审查复核；程序保留所选范围的机械一致性校验。没有通过删除负控、要求忽略关键依赖或把局部通过改称整体完成来获得 PASS。

P4 独立实现审查与候选验证、P5 安装及资格恢复、P6/L1—L5 真实结果要求继续保留。旧资格不能自动继承；必要资格无可接纳建立路径时仍须阻断发布。真实研究有据停止与“两轮实际推进完成”仍分开记录。

## 4. 实际检查与结论边界

本轮执行了冻结计划 SHA256 复核、两个版本的完整文本 diff、源码基线记录对照、相关测试文件存在性检查、计划及本报告链接/空白检查。上述最终检查通过。基线对照脚本首次未处理清单中的已删除文件记录而产生 KeyError，随后按原清单的缺省摘要语义修正只读脚本并完成核对；未改变源码或证据文件。

未运行 pytest、wheel、平台、科学 MCP 或 solver；未验证尚未实现的查询行为。本次没有新增可选建议或遗留计划阻断。**PASS 仅绑定上述 R2 冻结计划及未漂移的源码基线；实际实现仍须按该计划逐项验证并接受独立复核。**
