# TCAD Artifact 插件

简体中文 | [English](README.md)

`tcad_control` 是已准备 TCAD 作业的执行适配器，只提供 capability discovery、
submission lookup、submit、status、cancel、collect 六项操作。lookup 按冻结提交摘要权威查回，
submit 对同一描述符幂等；查询不可用时不得盲目重提。它只管理运行目录和后台进程状态；Artifact、Run、审批、执行
身份和结果注册均由 SciDiscovery 控制面负责。

输入为规范化 `TCADJobSpec`，其中包含本地归档描述、成员清单、部署方白名单工具
profile、可信执行用途、资源限制和预期输出。现有 reviewed/package 路径固定写入
`production`；缺少用途字段的 v1 作业会被拒绝。执行器不生成 Deck，也不判断物理模型。

reviewed-package transform 还必须接收精确 `experiment_plan`。在生成可执行 package 前，
它会验证每个 case-varying 科学比较控制量在每个 case 中都有源码绑定；冻结控制量也可使用一个
同值的全局绑定。缺失 realization coverage 必须在执行前失败，不能拖到运行后的 Control
Equivalence 才暴露。

Capability discovery 只产生 `tcad.solver-capability.v2`。私有固定参数、完整可执行
路径、环境和完整发行证据不会进入 snapshot。管理员可把固定参数逐项显式加入
`public_arguments`，并设置受限的 `public_release_label`；默认不公开任何参数，标签
由安全 profile 名派生。未公开值只以计数和摘要绑定，v1 snapshot 一律拒绝。

插件还提供统一的 TCAD Deck 作者/修订角色及独立代码审查者，以及完整工程比较、精确审查校验、
reviewed package、runtime attestation 和控制等价等确定性变换。
作者和审查者先通过 `worker_open_assignment` 获得 Run 内只读输入路径，再用 Codex 原生只读能力查看
完整源码；插件不注册第二个 TCAD 输入读取协议。作者的调试能力仍由精确 Operation 单独注册。

新的 direct-solver author 流程使用 solver-neutral declaration materializer：Worker 写完整
solver 工程、显式 case anchor 和原始 solver 输出路径，不填写 capability identity、资源策略、
case-binding 表、realization 行、runtime assertion 或 project diff。控制层只校验路径、精确
case 覆盖、不可变 plan 值/单位、源码哈希和收集上限；其中没有材料名、状态变量、方程、边界或
solver 命令语法，也不生成 `.cmd` scaffold。独立 reviewer 直接阅读完整源码，整体判断物理
忠实性、数值方案、case 隔离、原始输出与显式代码 bug，不逐项复述 requirement 表。Package
会按精确 declarations 重新物化，并要求同一源码的 bounded preflight 和独立审查通过。

直接 solver 工程只包含物理求解代码、输入、参数以及原始 TDR/PLX/PLT/log 输出声明。
曲线重采样、mask、派生指标、观测数据资格、阈值和科学结论必须在执行后由独立版本化
领域 transform/scorer 完成，不能写入 SProcess/SDevice deck。

跨设备执行通过受限 command contract 和已有 OpenSSH 授权连接调用无第三方依赖的
`remote_runner_py36.py`。Runner 不要求在仿真主机安装 Python 包或 systemd 服务。

本插件不分发或替代 Synopsys 软件和许可证。
