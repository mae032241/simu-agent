# Operation 校验职责裁剪记录

日期：2026-09-11。状态：本地源码修复及隔离安装验证完成，尚未部署或完成真实研究续跑。

用户直接授权“审查所有 Operation，把无意义的校验删掉”。本轮沿用唯一 Operation 编译目录，对已发生的重复填报、重复计算和科学职责越界做删除，没有新建流程、状态机、Operation 或规则注册表。不是对旧计划的追认；E7 的 7 次拒绝及最终超时仍是失败记录。

## 谁定义校验，审查覆盖什么

校验由开发者定义。`OperationSpec` 声明输入准入、输出 Schema、validator、context validator、guard、审查和审批组件；共享 Pydantic 模型与插件函数实现实际规则。编译器装配并投影这些声明，运行时执行。科学 Agent 并没有自行增加这些限制。单一来源可以消除副本不一致，却不能证明规则本身合理；这次删除的是职责错误的规则。

范围是本仓库 CORE、general_science、curve_score、tcad_artifact、curve_figure_evidence 的全部 **50 个生产 Operation：25 个 Agent、21 个 Transform、3 个 Approval、1 个 Effect**。83 个具名 validator／guard 组件的挂载及实现位置、逐 Operation 的处置见 [AUDIT.zh-CN.md](AUDIT.zh-CN.md)，机器可读版见 [DISPOSITIONS.json](DISPOSITIONS.json)。83 不是规则条数；共享模型、工具计算条件及审批／执行组件也按所有者检查。

基线为当时已存在大量未提交改动的工作树，HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`。不是把整棵 dirty tree 当作本轮改动。[BASELINE.json](BASELINE.json) 保存修改前源码／测试哈希；[SOURCE_DELTA.patch](SOURCE_DELTA.patch) 和 [CANDIDATE.json](CANDIDATE.json) 保存本轮精确增量及最终文件身份。架构双语文件另有修改前副本；索引基线是在本轮新增索引条目前保存的，包含之前已记录的 E7 历史。

## 已删除的规则

| 问题 | 修改后行为 | 仍保留的事实检查 |
| --- | --- | --- |
| 报告重复填写评分请求中的案例映射，连解释文字和引用顺序也逐字比较 | 映射在科学判断发生处给出一次；报告直接引用计算记录 | 已声明案例不能覆盖，错误来源、执行身份和实际请求篡改仍拒绝 |
| 原始证据已有绑定别名，还强制填写另一份来源结构 | 原始证据可直接引用别名；补充科学对应关系时才填写 source_references | 提供的引用必须存在且指向实际绑定对象 |
| 提交分析时重新解析原文件、重新评分，耗尽预算后要求删除计算 | 提交核验控制层工具收据及记录完整性，不重算 | 当前计算不能无收据伪造；历史结果必须来自精确封存记录和配对来源 |
| 固定六门、研究标签、覆盖率或阈值组合决定总体科学 verdict；critic 不知道解法也必须编造解决动作 | 分析者、设计者和独立审查者判断科学结论、局限及处置；可诚实报告没有已知解法 | 输出引用须真实；工具记录的实际数值、失败状态和诊断不能篡改 |
| 科学实验必须至少两案例、具有完整对照／预测模板；工程任务只能单案例；曲线比较用途强制 required | Agent 选择本轮实验形状及必要比较，允许单案例科学实验、多案例工程实验和全部可选比较 | 一旦声明比较，其变量、单位、案例及引用仍须自洽；物化程序继续生成机械字段 |
| author／review 提交时重查输入参数 ready；缺口列表必须抄进 handoff；无完整项目的审查只能把各维度填 unknown | 提交只核对交付对象；缺口载荷填写一次即可封存、审查和交接；审查者可指出具体失败 | 缺口不能 execution_ready；真实项目仍要满足实现、初始化、独立审查及授权条件 |

增量涉及 **14 个生产文件，增加 101 行、删除 447 行，净减少 346 行**。修改了共享科学模型、既有分析／作者检查函数、相应合同说明和作者角色说明；没有改核心 Run 生命周期、审批 UI、执行 adapter、数据库或部署脚本。

## 明确保留的校验

保留格式、大小、有限数、唯一引用、源哈希和确切父链；保留独立审查、current／qualification、预算、权限和外部执行授权。它们保护可以机械确定的事实。

科学 verdict 与其 handoff 的一致性仍保留，因为资格和后继读取依赖封存交接；不能把载荷里的拒绝变成 PASS。来源审计的失败／未知不能通过另一份交接变成已核准证据，缺少真实实现的项目不能取得执行就绪。它们与从一张固定科学检查表推导研究结论不同。

既有曲线合同编译器仍核对自己生成的机械合同是否兑现精确计划；它不要求 Agent 手填，也不运行评分。专用“解释既有确定性曲线包”操作仍要求其声明的完整包；通用／TCAD 分析是可选评分的另一条入口，不受这一专用包前置条件约束。

现有报告结构和历史兼容类型保留；本次没有重做所有科学表单，也没有删除未挂载的旧 Schema。科学内容的正确性仍需独立审查，结构校验通过不代表科学结论已经得到证明。

## 验证及限制

所有测试／构建串行，单次执行进程地址空间限额 512 MiB、整棵测试进程树 448 MiB 提前终止线。日志采样所见最高内存 **242.2 MiB**，未触发内存终止。没有全量测试、真实求解器、生产 Run 或部署操作。

| 记录 | 结果 | 证明内容 |
| --- | --- | --- |
| [FINAL_ANALYSIS](FINAL_ANALYSIS.log) | 134 通过，1 项压力测试未选 | 通用／TCAD 正式 Worker 计算与提交，不重复映射，不在提交时重算；数值、来源、请求、尝试记录篡改仍拒绝；当前计算与历史复用边界 |
| [ROLE_BOUNDARIES](ROLE_BOUNDARIES.log) | 167 通过，4 失败 | 科学角色、作者／审查、假设与参数交接；其中 1 项本轮测试夹具目标键写错，已修正并在 FINAL_ANALYSIS 通过，其余 3 项基线失败见下表 |
| [FINAL_BOUNDARIES](FINAL_BOUNDARIES.log) | 153 通过，5 失败 | 恢复、同字节跨执行防替换、历史资格、编译目录／权限负例、参数和图证；2 项旧结论门禁断言已按本轮行为修正并通过 FINAL_RECOVERY，其余 3 项为基线失败 |
| [FINAL_RECOVERY](FINAL_RECOVERY.log) | 4 通过 | 失败／取消执行仍可封存局部发现，原始 solver 状态未被改写 |
| [FINAL_GAP_HANDOFF](FINAL_GAP_HANDOFF.log) | 5 通过 | 非空缺口列表不必抄进 handoff，缺口可审查具体失败并进入新修订 Run；提交不读取输入 ready 状态 |
| [FINAL_INSTALLED_R3](FINAL_INSTALLED_R3.log) | 4 通过 | 最终源码生成的隔离 wheels：全插件目录与源码身份一致、TCAD 原始结果正式提交且不重算、无 TCAD 的通用计算与失败结果有限分析 |

各行有交叉覆盖，不能相加称为互不重复的测试总数。最初安装探针 [FINAL_INSTALLED](FINAL_INSTALLED.log) 失败，因为测试守护脚本把源码 PYTHONPATH 传入 pip，临时虚拟环境误判包已存在。取消该继承后 R2 通过；最终合同说明补正后重新构建并通过 R3。该问题没有通过修改生产安装逻辑绕过。

仍有 **6 项修改前也失败的测试**，本轮没有删除、跳过或改写它们来制造全绿：

| 用例 | 修改前、修改后共同失败点 | 基线证据 |
| --- | --- | --- |
| `test_review_validates_bound_original_context_and_actual_source_aliases[execution_context]` | 断言旧 ValidationError，当前抛出输入契约 OperationInvocationError | [BASELINE_FAILURES](BASELINE_FAILURES.log) |
| `test_root_preflight_rejects_replacing_the_prior_intake_source` | 原始来源正例在 preflight 已被拒绝，未走到替换来源负例；基线缺少迁移文件的首次尝试不作证明，补齐原文件后单独复现 | [BASELINE_COHORT_FAILURE](BASELINE_COHORT_FAILURE.log) |
| `test_role_prompts_use_only_packaged_role_resources` | 断言 prompt 等于原始角色文本，没有计入已存在的公共研究上下文 | [BASELINE_FAILURES](BASELINE_FAILURES.log) |
| `test_real_parameter_run_reaches_expansion_audit_and_qualification[no-checklist/checklist]`（2 项） | 升级审计合同后的旧审计正确被拒绝，但测试期待的异常类别与实际工程异常不同 | [BASELINE_PARAMETER_FAILURES](BASELINE_PARAMETER_FAILURES.log) |
| `test_parameter_run_rejects_package_with_invented_source_alias` | 虚构来源确被拒绝，但测试仍断言旧诊断字典／旧错误文本 | [BASELINE_PARAMETER_FAILURES](BASELINE_PARAMETER_FAILURES.log) |

`git diff --check` 通过。Skill 所建议的 `scripts/validate_architecture_constraints.py` 和 `scripts/run_science_control_bench.py` 在当前源码目录不存在，本轮没有声称运行它们或获得该类验收。上述真实入口测试不替代现场 Agent／研究闭环验收。

## 安装与接续边界

编译目录仍是同一组 50 个 Operation；共享模型、合同与审查依赖使其中 26 个摘要发生变化。安装后需使用新生成的 Worker 配置并重启会话，不能把旧 Run／审查视为新合同下的资格。没有数据迁移；历史记录保持可读，复用计算仍绑定原分析和精确来源。

本轮没有部署。下一项现场验收是在安装后恢复原研究记录，用新的受控分析 Run 验证：案例映射无需重复填写，计算记录不被提交重放，有限或完整分析能够封存。原失败 Run 不重开，也不继承为成功；端到端科学闭环目前仍未完成。
