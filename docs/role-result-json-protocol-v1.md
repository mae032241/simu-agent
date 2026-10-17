# 科学角色输出协议入口

当前薄 CLI 使用冻结的 H/W/A/E 科学合同，由 `research_loop/contracts.py`、`semantic.py` 和 `protocol.py` 共同校验。
模型只填写科学输出和职责内的后继选择；控制层保存身份、封装、原件、预算与权限。
操作与边界见[CLI 指南](ROOTLESS_CLI.zh-CN.md)及[当前架构](ARCHITECTURE.zh-CN.md)。

共享插件的编译输出合同仍由其 OperationSpec 决定，不据薄角色协议改写旧 Artifact 字节。
