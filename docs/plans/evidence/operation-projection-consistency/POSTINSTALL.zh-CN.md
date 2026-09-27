# R1 生产安装后核验

状态：生产部署核验通过，当前 Codex 会话的分析角色注册仍为旧代。E6/E7 未执行，计划尚未关闭。

本记录承接用户重新安装后的只读检查，不改写[安装前实施记录](EXECUTION_RECORD.zh-CN.md)及原计划。精确结果与时间见[核验数据](POSTINSTALL_SESSION.json)。

- 运行中的服务目录摘要与已验证候选相同：`f6acab6e9e24838caeb090d7a72b94307256559b8e0589e04c68f23658d438d1`。
- 15 个本轮生产文件全部匹配最终候选，按既有发布器的文本规范化比较。
- 磁盘上的通用分析和 TCAD 分析 profile 已生成，摘要匹配，包含 `tool_contracts` 读取指引。
- 实际 Root `operation_catalog` 返回新版输入元数据；`instance_current` 确认原 `M7-test0` 实例仍处于绑定状态。
- 当前会话可见的分析 Worker 工具及可派发角色仍是旧代，不含两个新版分析角色。未创建一个无法派发的新 Run，也未用旧角色替代。

下一步是重启 Codex 客户端/会话，重新加载项目角色和 MCP 配置，再复核实际可派发角色，串行执行[交接说明](HANDOFF.zh-CN.md)中的 E6 和 E7。无需再次安装或同步 VM runner。新会话是否需要绑定，以届时 `instance_current` 的实际结果为准。

OpenAI Docs 说明项目自定义角色位于 `.codex/agents/`，由 Codex 作为子会话配置加载；MCP 配置修改在桌面端/IDE 提供重启入口。[自定义角色文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[MCP 配置文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。当前会话仍持有旧注册这一判断来自上述本机对照；官方页面没有保证已有会话能热更新全部角色。

本轮只读核验及记录更新没有运行测试、构建、求解器或 Agent，也没有修改生产状态。
