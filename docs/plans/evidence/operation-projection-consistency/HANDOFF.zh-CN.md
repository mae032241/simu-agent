# R1 安装与后续验收交接

日期：2026-09-11。源码与隔离安装验证已完成，生产仍是旧版。精确范围、保留失败和未验证项见[实施记录](EXECUTION_RECORD.zh-CN.md)。

## 安装命令

以下参数已通过本机[部署 dry-run](DEPLOY_DRY_RUN.log)。使用当前 `da` 用户执行；脚本自行调用已有 sudo 安装流程。用户和组按当前用户取默认值，TCAD command adapter 沿用现有配置。

```bash
SCID_WORKSPACE=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector \
SCID_CODEX_LAUNCH_ROOT=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent \
SCID_PYTHON=/home/da/miniconda3/bin/python \
SCID_INSTALL_ROOT=/opt/scidiscovery-m7 \
SCID_STATE_ROOT=/var/lib/scidiscovery-m7 \
SCID_CONFIG_ROOT=/etc/scidiscovery-m7 \
SCID_BACKUP_ROOT=/var/backups/scidiscovery-m7 \
SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence \
SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/deploy/reinstall.sh reinstall
```

本轮没有修改 VM runner，无需同步 VM。安装后重启 Codex 会话，使新生成的角色和 MCP 配置生效。上面是已预检的部署交接命令，本记录不表示它已实际执行。

## 安装后核验

先核对生产运行摘要、实际安装目录和生成配置来自同一候选；本轮隔离候选目录摘要为 `f6acab6e9e24838caeb090d7a72b94307256559b8e0589e04c68f23658d438d1`，完整身份见[候选记录](CANDIDATE_IDENTITY_RESULT.json)。若源码或插件组合随后变化，应重新核验，不把此摘要用于新的候选。

新会话先调用 `instance_current`，按其返回的管理页面绑定；沿用用户明确继续的原研究实例。不能以聊天确认代替 UI 决定，也不能用当前旧会话注册的角色测试新版合同。

## 尚需完成的 E6/E7

1. **E6：隔离工程实例的新 Agent 验收。** 测试装配绑定合法的已知数值夹具及所需记录，调度者从当时编译目录选择已有分析 Operation，preflight 后派发返回的精确角色，不继承父聊天。Agent 从绑定材料和 `tool_contracts` 自行构造请求；先验证一个明确超限边界，再在同一 Run 修正并计算、封存。独立 oracle 留在验收侧，不向 Agent 提供完整请求或答案。按 R1 计划核对实际调用、回执和 sealed output；手写工具请求测试不能替代。
2. **E7：当前研究续接。** 从编译目录和原实例封存记录恢复确切计划、匹配审查、执行结果、已完成恢复 manifest 和原始证据，创建新分析 Run。分析角色可自主选择评分或给出证据不足下的有限结论。未计算或只封存有限分析不能替代 E6；没有进入下一轮设计和匹配审查也不能称跨轮闭环完成。

真实 Agent 验收串行执行，不与构建、测试或求解器叠加。旧 Run 保留原合同、输入、预算和结果；摘要不一致时不原地恢复或重新签名。需要历史材料时只走既有声明端口与受控恢复入口。

如需回滚，使用安装器保存的前一代码包及其配套生成配置；不修改数据库历史、旧请求 JSON 或回执诊断。
