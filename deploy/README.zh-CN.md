# 部署入口

简体中文 | [English](README.md)

- `install.sh`：安装、验证、查看或移除 Linux/WSL 服务。
- `install_ssh_tcad_runner.sh`：通过已有 SSH 连接验证或安装无第三方依赖 Runner。
- `systemd/*.service.in`：服务模板；不要直接修改 `/etc/systemd/system` 下的生成文件。

安装器会根据自身位置推导仓库根目录。机器相关信息通过 `SCID_*` 环境变量和 JSON
示例的私有副本提供。完整步骤见[中文安装教程](../docs/INSTALL.zh-CN.md)。

部署命令不会安装 Sentaurus、许可证、虚拟机或 SSH key。
