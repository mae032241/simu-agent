# TCAD Artifact 插件

简体中文 | [English](README.md)

`tcad_control` 是已准备 TCAD 作业的执行适配器，只提供 capability discovery、
policy discovery、submission lookup、submit、status、cancel、inspection、collect 操作。lookup 按冻结提交摘要权威查回，
submit 对同一描述符幂等；查询不可用时不得盲目重提。它只管理运行目录和后台进程状态；Artifact、Run、审批、执行
身份和结果注册均由 SciDiscovery 控制面负责。

输入为规范化 `TCADJobSpec`，其中包含本地归档描述、成员清单、部署方白名单工具
profile、可信执行用途、资源限制和预期输出。现有 execution-package 路径固定写入
`production`；缺少用途字段的 v1 作业会被拒绝。执行器不生成 Deck，也不判断物理模型。

当前任务协议为 `TCADJobSpec.schema_version=4`：保留明确的 `collect_generated_outputs`，
资源限制包含墙钟、CPU、内存、输出字节，以及必填的任务总存储 `max_storage_bytes`，删除未执行的 `max_processes` 提示。
控制端与远端 runner 必须使用同一版本。现行配置严格校验，不再自动补齐旧 smoke policy；
项目与执行包完整序列化默认字段。打包使用 declared-source v2、完整 case anchors 与精确源码
物化。负责人提供科学设计与求解器源码；控制层解析 capability、文件绑定、资源策略和执行身份。
`ExecutionPackage` 使用 `tcad.execution-package.v2`；可选审查不表示执行包已获批准。

Capability discovery 只产生 `tcad.solver-capability.v2`。私有固定参数、完整可执行
路径、环境和完整发行证据不会进入 snapshot。管理员可把固定参数逐项显式加入
`public_arguments`，并设置受限的 `public_release_label`；默认不公开任何参数，标签
由安全 profile 名派生。未公开值只以计数和摘要绑定，v1 snapshot 一律拒绝。

## 完整实验任务

`science.experiment.v1` 是公开通用实验任务。同一负责人完成设计、求解器代码、局部调试、执行、
收集、有效性判断与交付。插件以 `ExperimentCapability` 提供领域工具及内部求解器 Effect，
不再注册单独作者/修订/审查调度链。SProcess 与 SDevice 共用该任务。负责人封存实际阶段结论，
供 UI 自动读取；普通阶段不要求独立审查或审批。仅适用合同明确要求时审查才是门槛，其余按需决定。
执行授权由下述配置策略控制。

负责人编写完整求解器项目、科学执行计划、case anchors 和原始输出声明；控制层解析精确能力、
源码/文件身份和资源配置。声明物化器不发明物理模型，也不生成 `.cmd` scaffold。局部修改保留在
同一任务内。原生助手可以读取任务文件、使用 Skill 和工具、完成获准局部工作；负责人等待并整合
结果。助手不成为审批者，也没有 Root 控制权。参与、权限和原生线程生命周期边界见
[核心架构](../../docs/ARCHITECTURE.zh-CN.md)。

求解器工程包含物理代码、输入、参数和原始 TDR/PLX/PLT/log 输出；派生曲线和指标由确定性
解析/评分工具负责，科学结论属于任务负责人。
跨设备执行通过受限 command contract 和已有 OpenSSH 授权调用无第三方依赖的
`remote_runner_py36.py`，不要求在仿真主机安装 Python 包或服务。
本插件不分发或替代 Synopsys 软件和许可证。

## 配置内自主执行

管理员须提供完整 `agent_execution_policy`、`runner`、`debug`，参考
`config/execution-policy.example.json` 与 `config/remote-runner.example.json`。缺失或非法配置拒绝；
部署不再生成 smoke policy。示例允许 **2,000,000,000 字节、3600 秒**，两项都可取等号，
全部可改配置，与 RAM 额度无关。关闭自主授权或超额时，`outside_limits` 选择人工审批或拒绝。

控制层保存独立的策略授权记录，绑定请求、执行 package、编译身份、预算和 policy digest，
不伪造 HumanDecision。提交时重新核对当前策略，启动后冻结 runner 约束。多 case 共用同一个
作业进程树的墙钟；持久项目预算归属和精确提交查询防止重命名、恢复取得新额度。
调试模式时限、次数、累计预留和诊断额度同样读取配置，提交前持久保存绑定不可变科学主题的
reservation，失败与未知提交也不退款。

总存储计入逻辑输入、中间文件、输出、日志；输入删除仍计费，stdout 保留镜像在终态观测中保守计费，所有 solver 文件均计入。
本地与远端采样目录总量，超限终止进程组，manifest 记录**观测高水位**、采样周期与超调，
不声称瞬时峰值或文件系统硬配额。科学输入物化、归档、SSH 传输及最终 CAS 登记均采用文件流；
小 JSON 与诊断视图保留独立限制。

传输配置与求解器授权和 RAM 独立。核心 `agent-settings.json` 中的 `execution_io` 配置
`max_export_bytes`（默认 2,000,000,000）、`read_page_bytes`（16,384）、
`collection_timeout_seconds`（600）、`file_timeout_seconds`（120）和
`idle_timeout_seconds`（30），单位分别为字节与秒。创建 Run 时合并公共值和实例显式字段，
恢复保留原快照；导出与收集还受 Run 剩余时限约束。扩大传输上限不授权更大的求解器任务。

当前实现和未验收事项只在 [R4 主计划](../../docs/plans/RESEARCH_TASK_REFACTOR_R4.zh-CN.md) 中记录；
历史求解器或助手传输探针不能代替完整科学链验收。

### 修订额度、文件绑定与诊断恢复

控制层沿精确父对象追溯research objective作为预算主体。实现修订各自保留身份，共享持久额度池；提交前原子预留完整请求，终态按 runner 观测的累计墙钟与存储高水位结算。观测缺失、提交结果未知均保留预留，不自动返还。策略收紧减少剩余额度，不清除历史消费。

SDevice grid 通过实验 `scientific_files` 声明，再按科学名称映射到实现输入 slot。文件引用
从精确 CAS 原件流式读取；控制包保留 slot 和父件身份。文件不作为内联文本进入模型，但仍受
runner 总存储约束。改变科学输入产生新实现，适用资格必须重新建立，不能按名字继承。

可信调试 receipt 与预算账本分开存放。恢复必须核对原始提交及文件哈希，只允许同一 Run 或控制层记录的 recovery 链；恢复相关模式后重新执行 candidate finalization。缓存 response 本身不构成可信记录。实际模式和输出选择的 collection limits 贯通子进程收集与封存。stdout 使用 `.scid-capture/solver_stdout.log`，solver 自身日志保留原件。

未提交请求保留不可变授权历史和一个当前策略指针。同请求/owner/额度重授权保持一次预留；human/deny 重判只在从未产生 prepared submission 时原子释放预留。prepared 或提交结果未知必须先精确查询，保留原预留。修复保留精确的先前科学输入，除非任务
有意修改；可选审查不能代替来源或执行身份检查。
