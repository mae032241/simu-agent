# TCAD 资格状态

[English](TCAD_QUALIFICATION_STATUS.md) | 简体中文

本页拥有当前 TCAD 资格边界。[架构](ARCHITECTURE.zh-CN.md)拥有控制职责；
[传输合同](tcad_transport_contract.md)拥有领域执行和收集行为。

## 已实现的工程范围

薄科研链能够冻结所选 TCAD 受管执行接口，保留精确准备输入和收集原件，
请求精确对象的独立审查，绑定执行权限并累计有限资源消耗。
可选原生实现编译提供非空输入链。自包含 V2 package 与 observer 声明来源
可在冻结的声明范围内提供经核验的输入绑定和作者关系。来源缺失或明确不完整
仍保留不确定性，不能据此证明任意 native 或 solver 文件外读已经封闭。

定向源码、合成进程和 loopback HTTP 检查覆盖所选绑定、审查、预算、原调用恢复
及收集路径，不证明所有组合、已安装 solver 行为、物理模型或科学主张已经合格。
删除旧 Run/SQL 宿主及 wheel/source 打包检查不增加 solver 资格。

## 真实资格仍未建立

当前资格记录尚不能证明真实 Sentaurus SProcess 或 SDevice 的执行—收集—解析闭环、
合格 TDR metadata provider 或 Fig.4 科学主张。这是证据边界，不是对当前机器的
可执行文件、许可证或远端 runner 的实时探测。mock 输出、合成 PLX/PLT fixture、
历史 solver 结果和工程测试通过数量均不能建立这些资格。

提升资格必须提供绑定精确候选与受控 runner 的证据：

- 提供可用 solver 许可证，冻结 solver capability、release 证据、获准的 executable/arguments、环境和
  精确输入 package；执行前拒绝 capability 漂移。
- 完成经授权的真实 SProcess smoke，贯穿执行、收集与解析。保留输入/输出摘要、
  原始日志、release 和 parser 证据、失败、限制及所选合同要求的独立审查。
- 单独验证 SDevice，具备可用许可证、真实 TDR 证据和合格 metadata provider；
  SProcess 成功不能授予该资格。
- 物理模型或图中主张须基于精确科学证据及适用条件判断；执行成功和 parser
  接受本身不能证明科学正确。

执行权限来自冻结策略或精确人工决定。科学审查、solver 资格与执行授权相互独立。
其他尚未取得资格的部署和恢复路径见[发布范围](RELEASE.zh-CN.md)。
