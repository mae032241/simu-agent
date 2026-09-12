# 曲线评分移入结果分析：实施记录

状态：源码修复、独立源码审查及隔离安装包验证通过。未部署到运行服务，未完成真实求解器／下一轮研究现场验收。

## 固定基线

- 被审 R3 计划 SHA256：33d0072b660aa3dd34048f8230cf1be61dd69211981089125267ae657e893ea0。实施期间保留原文。
- HEAD：2edac5d317a74056869a567bd0daa7f556ecbc85；当前工作树已有修改。
- [P0 工作树清单](p0-baseline.json)：857 件路径，包含删除项；源码快照保存于该记录指定的本地临时归档。本次增量按此基线核对，不把既有工作混入成果。
- [已安装目录](p0-installed-catalog.json)：当前 49 项 Operation，仅为安装前快照。

## P0

三个原有入口用例已运行，参数展开后 5 passed：
`test_local_tcad_author_debug_and_independent_review_share_one_operation_path`、
`test_curve_contract_operation_keeps_v1_and_exposes_only_compiler_write_path`、
`test_curve_analysis_transform_and_single_file_agent_complete_real_run`。
命令使用 `/home/da/miniconda3/bin/python -m pytest -q`，耗时 8.97 秒。
该结果证明现有 fixture 路径，不代表无评分新路径、安装版 Worker 或真实求解器通过。

独立执行者分别负责核心只读描述符、通用分析及评分、TCAD 领域分析；均先复现本切片的入口缺口，再修改。共享接口由父任务协调。

三个切片的反例证据已归档：[通用分析](p0-generic-analysis.json)、[TCAD 原始结果入口](p0-tcad/results.json)、[元数据接线](p0-metadata.log)。TCAD author／review／package／执行预检 fixture 在不绑定曲线合同的情况下通过，因此保留该生产路径原样；执行预检使用适配器能力 fixture，未启动外部求解器。

## 崩溃前的实施进展

核心描述符接线及相关生命周期回归：63 passed，11.10 秒，命令覆盖 `test_analysis_input_descriptors.py`、`test_l2_local_run.py`、`test_l2_run_invariants.py`、`test_incremental_revision_runtime.py`。这证明候选预检与提交共用精确输入元数据，含同内容不同对象、隐藏输入过滤及工程故障分类。

调度源规则及生成 AGENTS 投影已移除评分必经步骤，中英文架构／安装说明同步。此时通用分析与 TCAD 分析仍在实现，整体验证尚未完成；后续结果见下文。

兼容回归首轮发现两个旧测试仍调用已改为可选评分的新通用入口，要求旧的完整合同约束。它们现明确测试保留的旧曲线诊断校验函数；旧约束未删除，新入口行为由新增入口测试覆盖。

## 恢复后完成的源码修复

- 共享分析 Schema 由 curve_score 单点注册并公开引用，移除 TCAD 重复注册；更新新分析入口对应的输入 inventory 回归。
- TCAD 对未知加权／来源选项显式报告 unsupported；畸形比较、无效记录名及 CSV 解析异常按工具边界处理。
- 计算请求说明公开现有比较 schema 与原始来源映射格式。只按匹配原计划的指标、阈值、方向及单位计算检查覆盖；改变方法不能冒充原计划通过，目标成功不能引用失败比较作为成功计算。
- 原始文本先检查行数及行分隔符，再进入会分配逐行对象的旧解析器；累计点数仍有上限。回归使用约 264 KiB 的反例验证解析器不会被调用，不运行大文件压力测试。
- 工具读取前开始半剩余预算计时，解析与比较检查共同截止时间。共用候选／提交路径向只读 ValidationSources 传递临时重放期限，不新增持久字段或状态。超时的 computed 重放可修正拒绝，移除对该计算的依赖后仍可作受限分析。
- 时间控制采用协作式检查与有界单步工作，不声明硬实时抢占。原始读取、既有解析调用和 Pydantic 验证仍是有界不可任意中断步骤。

## 验收结果

全部测试串行执行，子命令继承 3 GiB 虚拟内存上限；源码用例超时 120 秒，安装用例超时 180 秒。没有并行测试或构建。

| 验证 | 结果 | 记录 |
| --- | --- | --- |
| 工具、TCAD、只读描述符、旧曲线链路及 Run／修订回归 | 127 passed，1 stress deselected；20.25 秒；最大 RSS 110136 KiB | [源码验证](source-validation.log) |
| 原计划标准仍能通过的正向控制 | 1 passed | [正向检查](positive-check.log) |
| 新工具与此前两项失败所属的插件／inventory 回归 | 95 passed，1 stress deselected | [兼容验证](compatibility-validation.log) |
| 隔离 wheel 目录／Worker 配置、无 TCAD 通用分析、无评分提交、原始 PLX／CSV 工具到正式提交及身份拒绝 | 5 passed；40.88 秒；最大 RSS 91216 KiB | [安装验证](installed-validation.log) |
| 独立实现审查 | PASS，仅限所列源码与证据 | [独立实现审查 R1](../../reviews/CURVE_SCORING_AS_ANALYSIS_TOOL_IMPLEMENTATION_REVIEW_R1.zh-CN.md) |

各测试组存在重叠，不把通过数相加当作独立用例总数。安装验证是临时隔离环境，未修改 /opt 或重启服务。

遵照用户的资源约束及已批准的测试裁剪，本轮不重新运行全量与大文件压力用例；不宣称全量全绿。两项已知的 schema 归属和 inventory 快照失败已在所属回归中消除。其他未执行路径不由本结论覆盖。

原计划文档保持 SHA256 33d0072b660aa3dd34048f8230cf1be61dd69211981089125267ae657e893ea0；先前 /tmp 工作树归档随崩溃丢失，P0 文件摘要清单仍保留。后续源码复核以独立审查列出的确切文件摘要及本次验证记录为准，不将其他既有工作树修改合并为本修复成果。

## 后续现场验收

源码任务已完成；计划 P5 的服务部署、新会话目录核验，以及第 6 节真实新执行结果进入分析并接续下一轮仍待实施。不能把 fixture 结果作为科学结果，也不能继承已退役的输入资格。
