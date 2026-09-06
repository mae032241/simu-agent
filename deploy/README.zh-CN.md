# 部署入口

简体中文 | [English](README.md)

- `install.sh`：安装、验证、查看或移除 Linux/WSL 服务。
- `reinstall.sh`：通用、事务化的长期重装入口。
- `install_ssh_tcad_runner.sh`：通过已有 SSH 连接安装 Runner；也可复用运行态 transport
  完整更新 Runner 与私有配置，或在当前 schema 上仅升级代码。
- `init_workspace.sh`：以 `0750` 权限初始化与源码分离的研究 workspace。
- `install_transaction.py`：为 site、unit、配置、skill、launcher 和 SQLite 状态生成
  精确事务快照，并在安装失败时回滚。
- `systemd/*.service.in`：服务模板；不要直接修改 `/etc/systemd/system` 下的生成文件。

安装器先离线构建并验证 release site，随后才停止服务和事务化激活；健康检查失败会
恢复安装前文件、数据库和服务状态。安装器会根据自身位置推导仓库根目录。机器相关信息通过 `SCID_*` 环境变量和 JSON
示例的私有副本提供。完整步骤见[中文安装教程](../docs/INSTALL.zh-CN.md)。

自动图提取须显式选择 `tcad_artifact,curve_score,curve_figure_evidence`，按该教程离线
供应工具／模型合同。dry-run 和安装均在事务前以服务身份核验，不安装论文专用
wrapper 或人工几何技能。

部署命令不会安装 Sentaurus、许可证、虚拟机或 SSH key。
