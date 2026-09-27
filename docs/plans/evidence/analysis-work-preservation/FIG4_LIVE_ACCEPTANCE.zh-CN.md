# Fig.4 本轮现场验收记录

2026-09-12。状态：**本轮分析超时，后续 draft_from 被恢复链次数上限拒绝；科学闭环未完成。**
执行依据：[完整闭环及故障定位验收](FIG4_CLOSED_LOOP_ACCEPTANCE.zh-CN.md)。

## 安装、绑定与续接

- 用户安装重启后，13 个改动生产模块与工程候选完全一致，见[安装核对](fig4-acceptance-postinstall.json)。
- 真实服务名为 scidiscovery-control.service 和 scidiscovery-approval-ui.service；均 active/running，
  启动时间为北京时间 2026-09-12 16:13:00。带 m7 的安装目录不意味着 systemd 服务名也带 m7。
- 用户经管理 UI 绑定后，instance_current 确认原 M7-test0。启动续接前 queued/running 均为空。
- 在线 public 目录共 29 项；选定 tcad.result.analyze.v1，原始执行与回顾性分析端口的新说明已可见，
  native_view_image=true。该条目没有独立结果审查边；不把计划审查当成最终结论已独立审核。
- 通过 run_status.bound_inputs 恢复精确绑定，并由原执行计划父链确认原研究目标；
  直接绑定前轮四份正式计算文件，同时用 draft_from 交付允许读取的旧失败草稿。
  旧 Run 的 resume_available=false 与 draft_available=true 不矛盾，未绕过旧合同直接 resume。
- fig4_morphology_closure_1 的 preflight 一次通过；16:16:03 创建，16:16:31 打开，
  截止为 16:31:03。派发全新编译分析 Agent，不继承父聊天；不启动求解器。
  精确请求及初始状态见[调用记录](fig4-closure-1-start.json)。

## 新事件及补查

| 事件 | 定位及处理 | 当前证据边界 |
| --- | --- | --- |
| 重启后 unbound | 通过 instance_current 返回管理 UI，用户绑定后工具确认原实例。 | 正常会话准入，不是科学任务失败。未把聊天转换成审批或绑定。 |
| 运维服务名初查错误 | 调度者按目录名推测带 m7 的服务名，systemctl 显示未运行；实际 list-units 发现两个不带 m7 的服务均正常。 | 已纠正查询对象，没有发生真实服务宕机；不把错误探针结果当成生产故障。 |
| 工程源码搜索的路径猜测错误 | 部分预想模块路径不存在，rg/sed 返回缺文件；随后从 rg 实际符号结果定位。 | 只影响只读排查，不影响科学 Run，也不是 Worker 失败。 |
| 历史 runtime_failure 提示丢失 | 当前 RootRunRoutes.run_status 通过 _resolve 调用 bindings.resolve；缺名时 SchedulerNameNotFound 含 unknown run name。该异常是 RuntimeError 而非 DiagnosticError，mcp.rpc_error 将其压成通用 runtime_failure，未保留原消息。 | **源码确认诊断丢失路径**；历史事件当时是否恰为此异常仍缺原始回溯。只读查 12:24–13:00 control journal 有 6 条记录，无对应 Run 名或异常命中，不据此称异常从未发生。 |
| 历史管理链接 403 原因不可区分 | instance_management.verify_instance_management_capability 明确区分 invalid 与 expired；approval_ui.app 的 GET 异常处理将 InstanceManagementCapabilityError 与其他拒绝统一变为 FORBIDDEN，未转出具体原因。 | **源码确认 UI 诊断信息合并的位置**；旧请求未保留可核对的具体异常，不能反推历史一定过期，也不通过读取秘密来解密旧管理链接。 |

历史输入错绑、发布路径拒绝、comparison_keys 拒绝、原生 Python 错误、缺库后重算与两次超时，
继续由验收入口的既有账本及其原始报告追溯；后续状态与本轮新事件在此追加。
不读取运行中 Worker 草稿作科学结论，不将 native_execution=unobserved 当成无原生错误。

## 本轮失败与定位

fig4_morphology_closure_1 到 16:31:03 截止仍未提交；16:31:25 由 Root 按 CAS 记录 run_timeout，
随后中断 Agent。整个 Run 的输出拒绝数为 0，也没有 Worker MCP 工具错误记录。
这不是仿真目标被科学证据否定，更不构成闭环完成。

| 时间（北京时间） | 已证实事实 | 归因及边界 |
| --- | --- | --- |
| 16:16:03—16:22:20 | 创建后约 377 秒才出现第一次受观测原生调用。 | 这段是计算前墙钟间隔，不能全部算为模型推理或数值计算。 |
| 16:20:52—16:22:10 左右 | 第一次约 11 KB 补丁写入工作副本失败；检查发现副本模式为 0400，chmod u+w 后重发相同补丁。 | 16:19:34 的 cp 保留了只读输入模式；修改仅针对 scratch 工作副本。该原生 apply_patch 失败不在 Worker MCP 错误摘要内，先前只统计数值脚本异常时漏记，现补入。 |
| 16:22:20 | morphology_analysis.py 第 19 行读取 inputs/reference_material_002.csv 报 FileNotFoundError。 | 启动器的工作目录为 scratch，脚本仍采用另一基准的相对输入路径；后续同一工作单元于 16:22:50 重试，约 12.37 秒正常退出。 |
| 16:23:46 | 新单元受 150 秒上限运行；记录的耗时约 58.37 秒、退出 0。 | 这是单元进程完成证明，不是科学结论正确或整体完成证明。 |
| 16:25:02 | 批处理请求 300 秒、预留 100 秒；启动器按剩余预算截为约 260.44 秒。 | 动态预算机制生效；不能称这里发生了子进程超时。 |
| 16:27:56 | Agent 向批处理 PTY 发送 Ctrl+C，返回只显示 ^C。 | 七份原生 stderr 中，该批处理唯一缺少对应结束 JSON，stderr 为空；Agent 没有再轮询该会话取得最终退出回执。确认中断与观测缺口，不推测具体 finally 是否完成或编造退出码。 |
| 16:28:13 | 汇总调用正常退出。 | 阶段落盘已发生的覆盖由后续恢复清单证明；Root 未把失败草稿中的数值当科学证据。 |
| 16:29:01 | plot_morphology.py 第 4 行导入 matplotlib，报 ModuleNotFoundError。 | 已知环境问题再次出现在绘图实现；“先核实实际依赖”的任务要求没有有效落实。失败耗时约 0.02 秒，非绘图超时。 |
| 16:31:03 | 没有正式提交。 | 总任务未按时完成交付；计算预算留白不能保证 Agent 能在余量内写完报告并提交。没有证据把本次总超时归因于输出校验。 |

原生定位依据：[各调用结束记录及具体异常](fig4-closure-1-native-diagnosis.json)、
[缺失结束记录及进程观察](fig4-closure-1-native-coverage.json)、
[原生命令及 PTY 控制事件](fig4-closure-1-native-transport.json)。
仅提取技术元数据、异常帧和执行控制；没有读取/引用失败草稿的科学结果，也没有采用 Agent 聊天作为证据。
具有结束记录的进程最高记录 RSS 为 18,544 KiB；缺少结束记录的批处理峰值未知，不能声称整轮峰值就是此数。
事后未发现 cwd 位于保留工作区的进程，但这不证明全部写入者已停止，未据此删除原目录。

## 保全成功但续接被拒绝

控制层已验证副本，delivery_preserved=true：77 个文件、359,844 字节，其中 output 2 个、scratch 75 个；
12 个日志经过规范化。16 项未纳入副本的是 14 份原始 .raw 流及 lock/stop 文件；原目录保留，
原始 stderr 可用于上述工程定位。完整保存状态仍为 false，recovery_pending=true。
这些事实证明有交付副本，不证明全部科学工作已完成。

随后 Root 为“读取保全结果、局部修复、优先完成正式提交”的有限续接作 preflight，
得到 draft_source_unavailable，**没有调用 invoke 或另起同样的计算**。
精确状态、后续请求和拒绝见[失败与预检记录](fig4-closure-1-failure.json)。

阻断由如下已有实现共同造成：

1. TCAD 分析 Operation 声明 timeout=900、max_attempts=2。来源已追到 2026-09-10 的[恢复 P0 合同](../analysis-evidence-recovery/P0_CONTRACT.zh-CN.md)：当时为支持“本轮加一次显式受控接手”从默认 1 次改为 2 次；它是一次失败交接实现的工程取值，不是用户要求的科研停止条件。本轮保全修复前基线仍有该值。
2. _check_recovery_attempts 统计 resume_from 与 draft_from 的整条链，包含原始 Run；
   本轮 draft_from=fig4_morphology_analysis_3，所以旧失败 Run 与本轮已占满 2 个名额。
   源码使用原根 Run 冻结策略与新 Operation 上限的较小值，不能靠更名或只改新合同绕过。
3. recovery_status 先验证副本，再作含次数检查的 draft 准入，因此出现
   delivery_preserved=true 但 draft_available=false；这不是文件验证失败。
4. Root 预检入口把具体异常统一包成 draft_source_unavailable，丢掉 recovery attempt limit reached。
   当前 public 目录没有展示 max_attempts，调度也未在接续前从可见投影获知剩余额度。

次数限制在预检阶段按现有代码执行，未发生“成果提交重新检查输入”；问题在于该策略限制了
阶段工作交付，且没有清楚投影限制和拒绝原因。Root 选择旧失败草稿作为起点也消耗了唯一一次续接额度，
本轮调度没有提前识别这个后果，应计入调度责任。

当前停止的是这条已被拒绝的恢复链，不是宣称研究完成。未修改生产预算、重新绑定旧草稿、
读取失败科学结果冒充封存证据或重复启动原计算。图表补齐、正式结论和故障诊断验收均仍有未决项。

## 首次计算前约 6 分 17 秒的细分

补查[准备阶段技术事件](fig4-closure-1-preparation.json)，只统计调用时间、输出体积和文件操作，
没有读取或复述隐藏推理。约 29 秒用于创建后的派发及打开；打开后至 16:19:34，
Agent 读取任务、合同、新旧计划、恢复材料、既有脚本/结果并查看参考图，包含调用间处理时间。
该阶段工具文本输出约 243 KB，包含重复和封装信息，发生 3 次文本截断，不能当成唯一证据量。
16:19:34 复制既有脚本，16:20:52 首次尝试写入约 11 KB 补丁；随后因工作副本只读而失败，
检查/改权限及重发相同补丁至约 16:22:10，16:22:20 才启动计算。

单次工具执行多数为 0.1–0.2 秒，打开任务约 1.1 秒，故没有证据指向慢磁盘或长时间工具排队。
主要是上下文处理、实现准备及一次可避免的文件权限返工；调用间间隔不能进一步无依据地拆成
模型推理、生成或平台等待。现有脚本确实被复制复用，不能说全部从零编写；
但它未直接形成可执行的剩余工作单元，仍需大量修改且未先排除基本文件操作问题。
