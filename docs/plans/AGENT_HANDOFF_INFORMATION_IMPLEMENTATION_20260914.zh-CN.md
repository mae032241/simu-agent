# Agent 信息交接修复实施记录

日期：2026-09-14。状态：R1 已实施；定向检查、隔离安装/stdio 验证和独立实现复审通过。用户安装重启后，15 个安装文件核对一致，已完成一次真实独立计划审查与历史成果选读验收；未启动新的求解器执行，不代表 Fig4 科学闭环或真实模型 token 节省率。

## 范围与检查点

执行依据：[通过的 R1 计划](AGENT_HANDOFF_INFORMATION_REPAIR_PLAN.zh-CN.md)。R0 计划复审要求补上新作者自动模板及共享 finalizer 组件身份，R1 复审通过后，按用户要求先提交 Git 检查点 `096a13f`，再执行 P0—P5。

该检查点包含此前四个已修改源码/测试文件及本轮计划/审查记录；用户工作中的两份未跟踪 Fig4 文档保持原样。此次实现以 `096a13f` 为基线，修改 15 个生产/角色源文件。未改科学模型、Run 存储格式、审批、VM runner 或 solver；未新建科学 Operation、摘要 Agent、检索系统或科学填表规则。

[候选文件摘要](evidence/agent-handoff-information/candidate-files.json)证明这 15 个源文件与隔离安装验证使用的 release 源码逐字一致。测试与工程记录的后续整理不改变该生产候选。

## P0—P5 交付

| 项目 | 实际行为与验收 |
| --- | --- |
| P0 基线 | 用隔离合法样本采集完整项目、长日志 gap、通用/TCAD 审查、简版及旧格式分析的真实回复。保存文件摘要和序列化大小，不读取生产状态目录。 |
| P1 作者说明 | 初始化对应关系和未测试 reset 路径进入源码注释，先写说明再生成当前证明；真实 author 封存→review 物化路径可读到原文，源码变化仍使旧证明不可用。未增加“缺注释拒绝”。 |
| P2 Root 读取 | `output_paths=[]` 不读 Artifact 正文；指针选读返回单独 `selected_output`，保留旧完整读取。超预算子树提供一层有界导航，不截断科学值；historical、signal、原绑定及错误分页保持。查询参数错误不会改变科学 Run。 |
| P3 合同按需 | Local open 返回当前 assignment 的工具合同路径/指针，不依赖 analysis start_here；设计、作者、审查、分析均覆盖。复杂 `$defs`、旧 assignment fallback 和 Hardened 保留；损坏 assignment 不回退到更新合同。 |
| P4 摘要单写 | ScientificReview、DeckReviewReport、ImplementationGap 草稿可以省略机械 handoff 字段。新作者默认模板没有 null 占位，只写正式 gap 即可完成。显式旧说明保留，完整项目和其他角色未获得新例外。无法从正式字段生成交接时，诊断指向正式来源，支持同一 Run 修正。通用及 TCAD 对应组件配置身份明确更新。 |
| P5 指导去重 | 三个分析角色移除重复完整指导；完整指导继续位于 analysis-start.json 和工作区 patch_contract，角色提示提供短导航。生成 profile、实际打开/提交及失败续接入口均能读到必要说明。 |

## 独立审查闭环

- [R0 计划复审](reviews/AGENT_HANDOFF_PLAN_R0_REVIEW_20260914.zh-CN.md)：要求小修。
- [R1 计划复审](reviews/AGENT_HANDOFF_PLAN_R1_REVIEW_20260914.zh-CN.md)：通过，随后保存检查点并实施。
- [首次实现审查](reviews/AGENT_HANDOFF_IMPLEMENTATION_REVIEW_20260914.zh-CN.md)：正常路径符合计划，但省略 handoff 的草稿可能先报机械字段缺失，掩盖正式 verdict/summary 错误；还识别到既有 TCAD verdict 集合判断遇到列表/对象会抛 TypeError。
- [实现复审](reviews/AGENT_HANDOFF_IMPLEMENTATION_REREVIEW_20260914.zh-CN.md)：上述缺口修正后通过。类型判断和机械投影错误使用现有 WorkspaceProtocolError，原正式字段保持，未重审输入或增加第二套完整草稿校验。

审查报告保留各自当时的结论。独立审查者只读源码，未与父侧并行运行测试。

## 验证与资源

所有检查串行，BLAS/OMP 单线程；进程树内存上限 512 MiB，普通批次外部限时 150 秒。四个发布包的构建及单环境安装批次独立限时 300 秒，实际 14.35 秒；没有调用全量 suite 或真实 TCAD。各批日志、退出码、耗时和 RSS 位于 [检查记录](evidence/agent-handoff-information/checks.jsonl)。

| 验收边界 | 完成证据 |
| --- | --- |
| 作者→审查、当前证明 | P1 定向 11 项通过；P3 再覆盖作者/审查的新 open。 |
| Root 读取与查询错误 | 10 项通过：完整/省略/选读、字段导航、missing/null/转义/数组、预算、historical、未完成 Run、错误分页。省略路径以禁止 artifacts.read 的负证据验证。 |
| 合同与恢复 | 21 项通过：Local/Hardened 冻结合同、新旧 workspace、两种通用角色的精确反馈、作者/审查、损坏 assignment 和恢复导航。 |
| 正式摘要与兼容 | 草稿省略、旧显式说明、非适用类型、gap/完整项目区别、组件身份已通过；最终正式来源错误定位及同 Run 修正批次 11 项通过。 |
| 三类分析与后续设计 | 正常及恢复入口、三个生成 profile、简版报告到下一设计绑定已通过；P5 报告/设计批次 7 项通过，恢复检查单独通过。 |
| 编译合同与规范 | Local/Hardened 工具合同与实际 MCP Schema、所有 public Agent 输出合同、Root 参数、现有架构约束登记结构等 6 项通过。技能所提旧 `validate_architecture_constraints.py` 在当前仓库不存在，使用现有登记结构检查，并由独立审查判断语义。 |
| 实际发布入口 | 单个隔离 venv 安装 core、TCAD、curve、figure 四个实际 wheel，确认模块来自该 venv；安装目录编译摘要与使用相同安装组件的调用一致。真实 stdio proxy→Unix socket daemon 完成工具 Schema、完整/省略/导航/选读调用；正式审查/gap及三个分析入口完成提交。 |

表中按边界列举，复测不累计为独立覆盖数。所有检查观测到的最大进程树 RSS 为 **298,532,864 字节（约 285 MiB）**，无内存终止或检查超时。现有 runner fixture 的 `datetime.utcnow()` 弃用告警与本次修改无关，未据此改 runner。

## 实施期间的错误与定位

| 发生项 | 原因及处理 |
| --- | --- |
| 基线脚本两次启动失败 | 一次导入错误类名 LocalWorkerToolRouter；一次把 call_tool 挂到不拥有该方法的 RootToolFacade。修正临时采集脚本为 LocalWorkerMCPRouter/RootMCPRouter 后成功；未改产品接口。 |
| P4 新测试五项预检拒绝 | 新测试请求漏传既有必需 instruction，准确返回 instruction_required。补足测试任务指令后五项通过；没有放宽准入。 |
| P5 新测试七项生成失败 | 测试调用已有 profile 生成器时漏传 local_workspace_root。提供隔离路径后七项通过；未改生成器要求。 |
| 独立审查指出正式错误被机械字段掩盖 | 源码静态发现后，增加从默认无 handoff 草稿提交错误正式值、按精确字段纠正并在同 Run 完成的实际回归。修复机械投影反馈及 TCAD 类型判断，未通过人工补 handoff 绕过。 |

前述临时脚本/测试构造错误与产品缺口分开记录。原日志和检查命令已保留在同一 evidence 目录；脚本是此次隔离验证的快照，复现应复制到临时目录并在目标源码检出中运行，不在 evidence 目录生成工作状态。

## 阅读量测量

这些是 UTF-8 字节，不能换算成实际 input/output/cached token。

| 同类入口 | 修改前 | 修改后 |
| --- | ---: | ---: |
| TCAD author open，基线样本 | 2,614 | 882 |
| TCAD review open，基线样本 | 1,370 | 881 |
| 通用 review open，首个基线样本 | 1,220 | 729 |
| TCAD analysis open，既有紧凑入口 | 1,040 | 1,040 |
| TCAD analysis 生成 developer prompt | 20,042 | 18,377 |
| 通用 analysis 生成 developer prompt | 16,594 | 14,929 |
| 固定曲线误差 analysis 生成 developer prompt | 10,936 | 9,271 |

基线/修改后 open 的实际序列化记录分别见 [前](evidence/agent-handoff-information/baseline-sizes.json)、[后](evidence/agent-handoff-information/after-sizes.json)。旧生成 profile 数字来自前期只读源码审查的静态测量；修改后来自隔离安装组件生成的 profile，见 [记录](evidence/agent-handoff-information/after-prompts.json)。原完整回复仍保留，因此不承诺小对象每次选读都更便宜，也不将减少的默认合同回复等同于任务全程减少同样字节：实际使用工具时仍需读其完整合同。

隔离 stdio 的同一读取任务是“获得 gap 的 summary 和 affected_work”：完整回复 **76,474** 字节；正文省略 **1,932**、根导航 **2,536**、字段选读 **2,302**，三次合计 **6,770** 字节，已包括新增往返的回复开销。原大日志仍在不可变成果中，显式完整读取可获得。详细结果见 [安装入口输出](evidence/agent-handoff-information/installed-probe.stdout)。

该隔离数据证明目标路径的重复传输减少；没有测量真实模型 token、缓存命中、推理时间或 Fig4 科学效益。后续真实验收见下节，无需为本轮工程验收重算 TCAD。

## 安装后真实验收

用户安装、重启并重新绑定原实例后，15 个生产/角色安装文件与已审查候选全部一致。仅从 Root 公共接口取得状态和封存成果；未读取 Worker 私有目录或生产数据库。[现场工程证据](evidence/agent-handoff-information/live-effect-test-20260914.json)保存文件核对、UTF-8 回复大小、字段一致性和受控错误历史，不复制科学 checkpoint。

同一个历史 author 缺口结果 `fig4_regularized_author_1`：完整回复 127,133 字节；仅状态 4,950、根导航 5,581、五个必要结论字段 7,026，三个紧凑回复合计 17,557 字节。选读的 result_kind、summary、affected_work、missing_inputs、suggested_resolution 与完整原件逐项相同；状态、绑定、诊断、恢复、signal、历史资格及工具计时也一致。本次为了核对额外读取一次完整原件；上述是两种读取方式的成本比较，不是本会话实际 token 净节省。

全新 Agent 不继承父会话，绑定原材料完成 `fig4_dimensionless_plan_review_2`：从打开到封存 221.217 秒，总创建到封存 241.924 秒，一次提交完成。正式审查已封存，verdict=pass；handoff.summary 为固定的正式摘要引用，未重复科学结论。受控诊断摘要及完整错误分页为空，无提交拒绝或已记录工具错误。native coverage 为 unobserved，不能据此声称所有 native 操作都无错误。

前一次成功的同类计划审查 `fig4_alignment_gap_plan_review_2` 打开到封存 178.266 秒，本次多 42.951 秒；任务内容不同，且没有模型读取/推理分项计时，不能认定总耗时缩短。同一份当前计划的旧审查 `fig4_dimensionless_plan_review_1` 在 97.423 秒被用户暂停，未封存，不能充当完成耗时基线。

这次现场只覆盖真实审查交接、摘要不重复和 Root 选读。未重新执行 author、solver、分析恢复或作者源码注释到审查的现场路径；这些仍只有前述定向/隔离验证。Root 初次展示全目录过大而发生输出截断，后续从保留的完整响应只展开所选 Operation；这属于调度侧展示开销，不是预检或提交失败，未为此修改代码。科学内容以受控封存审查为准，不从工程验收推出 Fig4 对齐或机制结论。

## 部署与保留范围

本次代码已经安装重启，新的 compiled Agent 和按需读取接口已在实际任务中使用；本轮未改 VM runner，无需因这些修改同步 VM。完整记录、历史可读性、独立审查和执行审批保留。现场测试结束于新计划审查已封存，尚未创建下一次 author 或求解器执行。

通用首读视图、差异辅助、其他 status 字段精简及平台实际 token 计量仍按 R1 的范围说明保留，本次不宣称已解决全部信息交接成本。
