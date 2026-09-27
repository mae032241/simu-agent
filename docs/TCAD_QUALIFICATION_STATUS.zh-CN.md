# TCAD 资格状态

[English](TCAD_QUALIFICATION_STATUS.md) | 简体中文

记录日期：2026-08-08。

## 已完成的工程资格

- 全量 hermetic 测试：`322 passed`。
- 单位换算、统一 claim 投影、reviewed-package v2 和 solver capability 漂移拒绝。
- case realization / execution DAG、控制面 snapshot materializer 和控制等价性比较。
- ArtifactRef 二进制输入的摘要、大小、媒体类型、目标路径和 byte-exact staging。
- PLX/PLT 合成文本 fixture 的列、行数和有限数值 gate；空、截断、非有限和描述符
  替换均失败关闭。
- site、launcher、systemd unit、配置、平台 skill 和 SQLite 状态的安装事务回滚测试。

这些结果证明 Schema、确定性变换、状态机和无许可证 fixture 的工程行为，不证明
Synopsys Sentaurus 或任何物理模型已经合格。

## 未完成的真实资格

当前机器没有可发现的 `sprocess` 或 `sdevice` executable，也没有提供许可证、经管理
员确认的 release capability 或 Git 外真实 PLX/PLT/TDR/log 资格 Bundle。因此：

- 真实 SProcess 审批—执行—收集—解析闭环：`unqualified / capability unavailable`；
- 真实 SDevice 及 TDR metadata provider：`unqualified / capability unavailable`；
- Fig.4 或其他科学结论：不得由本轮 mock/fixture 测试接受。

发布门禁必须在受控 runner 上绑定 exact `SolverCapability`，完成人工审批的真实
SProcess smoke，并保存输入/输出摘要、release 证据和 parser 结果。SDevice 只有在
许可证、真实 TDR fixture 和合格 metadata provider 同时具备时才可提升资格状态。
