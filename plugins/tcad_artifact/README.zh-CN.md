# TCAD Artifact 插件

简体中文 | [English](README.md)

`tcad_control` 是已准备 TCAD 作业的执行适配器，只提供 submit、status、cancel、
collect 四项操作。它只管理运行目录和后台进程状态；Artifact、任务、审批、执行
身份和结果注册均由 SciDiscovery 控制面负责。

输入为规范化 `TCADJobSpec`，其中包含本地归档描述、成员清单、部署方白名单工具
profile、资源限制和预期输出。执行器不生成 Deck，也不判断物理模型。

插件还提供 TCAD Deck 作者、审查者和修订者角色，以及补丁应用、完整工程比较、
精确审查校验、reviewed package 和 runtime attestation 等确定性变换。

跨设备执行通过受限 command contract 和已有 OpenSSH 授权连接调用无第三方依赖的
`remote_runner_py36.py`。Runner 不要求在仿真主机安装 Python 包或 systemd 服务。

本插件不分发或替代 Synopsys 软件和许可证。
