# 安装教程

简体中文 | [English](INSTALL.md)

## 1. 支持环境

- 带 systemd 的 Linux 或 WSL2
- Python 3.10 及以上，并带有 `pip`
- Codex CLI、Claude Code，或两者同时使用
- `poppler-utils`：受限 PDF 文本提取
- `bubblewrap`：Worker 隔离分析
- `curl`：服务健康检查
- OpenSSH Client：远端 TCAD 执行

Sentaurus、许可证和虚拟机均为外部前置条件，本仓库不提供。

Debian、Ubuntu 或 WSL：

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip poppler-utils bubblewrap curl openssh-client
```

安装器使用选定的 base Python 解释器，但会把应用包及其依赖安装到
`/opt/scidiscovery/site`。它不会创建 venv，也不会修改 Conda base 中已有的包。

## 2. 获取源码

```bash
git clone <仓库地址> scidiscovery-agent
cd scidiscovery-agent
```

WSL 下不要从 `/mnt/c` 运行 systemd 服务。应把工程放在 WSL 文件系统，例如
`~/src/scidiscovery-agent`。

## 3. 选择 AI 平台

`SCID_PLATFORM` 支持：

- `codex`（默认）：生成 `.codex/config.toml`、角色 TOML，并在 `AGENTS.md`
  中写入受管理的调度规范；
- `claude`：生成 `.mcp.json`、`.claude/agents/*.md`，并在 `CLAUDE.md`
  中写入受管理规范；
- `both`：同时生成两个平台配置。

生成文件包含当前设备的绝对路径，因此每台机器都必须重新生成，不能提交到 Git。

## 4. 本地部署冒烟测试

此模式只验证服务和 MCP 接口，不运行科学 Solver。内部 TCAD controller 只允许
`/bin/true`。

```bash
PYTHON="$(command -v python3)"

# 可选源码预检。选定 Python 必须已能导入工程依赖。
SCID_PYTHON="$PYTHON" deploy/install.sh --dry-run

sudo SCID_PYTHON="$PYTHON" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  deploy/install.sh install
```

安装后包含：

- `/opt/scidiscovery/site`：只读 Python 应用包；
- `/var/lib/scidiscovery`：控制面状态；
- `/var/lib/scidiscovery-tcad`：本地执行状态；
- `/etc/scidiscovery`：服务密钥和执行策略；
- `/run/scidiscovery/control.sock`：Root MCP；
- `/run/scidiscovery-worker/worker.sock`：Worker MCP；
- `scidiscovery-control.service`；
- `scidiscovery-worker.service`；
- `scidiscovery-approval-ui.service`；
- 仅本地适配器模式启用的 `tcad-control.service`。

审批网页只监听 <http://127.0.0.1:8765>。

安装后需要完全重启 Codex 或 Claude Code。

## 5. 远端 TCAD VM

### 5.1 配置 VM Runner

复制示例到不会提交 Git 的本地目录，不要把真实许可证或主机信息写回示例：

```bash
mkdir -p config/local
cp plugins/tcad_artifact/config/remote-runner.example.json \
  config/local/remote-runner.json
```

修改副本：

- 写入真实 `sprocess`/`sdevice` 路径；
- 写入 `STROOT`、`PATH` 和许可证环境变量；
- 为每个允许的 Solver 配置唯一 `profile_id`；
- 设置由 VM 普通用户拥有的 state/exchange 目录。

通过现有免密 SSH 安装无第三方依赖的 Runner：

```bash
SCID_SSH_DESTINATION='tcad@vm主机或IP' \
SCID_SSH_IDENTITY="$HOME/.ssh/id_ed25519" \
SCID_REMOTE_RUNNER_ROOT='/home/tcad/scidiscovery-tcad' \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install
```

此脚本不会创建 SSH key，也不会在 VM 安装 systemd 服务，只会在 VM 普通用户目录
部署兼容 Python 3.6 的 Runner。

如需通过 VMware Tools 处理 DHCP 地址变化，可不设置固定
`SCID_SSH_DESTINATION`，改为设置：

```bash
export SCID_SSH_DESTINATION_FALLBACK='tcad@192.0.2.10'
export SCID_VMRUN_EXE='/path/to/vmrun'
export SCID_VMX_PATH='/path/to/guest.vmx'
```

### 5.2 配置 WSL/Linux 传输

```bash
sudo install -d -o root -g "$(id -gn)" -m 0750 /etc/scidiscovery

sudo install -o root -g "$(id -gn)" -m 0640 \
  plugins/tcad_artifact/config/ssh-transport.example.json \
  /etc/scidiscovery/tcad-transport.json

sudo install -o root -g "$(id -gn)" -m 0640 \
  plugins/tcad_artifact/config/command-adapter.example.json \
  /etc/scidiscovery/command-adapter.json
```

修改 `/etc/scidiscovery/tcad-transport.json`：

- SSH executable 和可选 identity；
- 固定 destination 或 VMware resolver；
- known-hosts 与稳定的 host-key alias；
- 远端 runner、config 和 exchange 路径。

WSL 调用 Windows OpenSSH 时，常见 executable 是
`/mnt/c/Windows/System32/OpenSSH/ssh.exe`；identity 和 known-hosts 应使用该
可执行文件能够识别的路径格式。

使用外部适配器安装服务：

```bash
PYTHON="$(command -v python3)"
sudo SCID_PYTHON="$PYTHON" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
  deploy/install.sh install
```

外部适配器会替代本地 `tcad-control.service`。每次 SSH 操作都必须短时返回；后台
执行和持久 `running`、`status`、`done` 记录由 VM Runner 负责。

## 6. 验证

```bash
deploy/install.sh status

systemctl is-active \
  scidiscovery-control.service \
  scidiscovery-worker.service \
  scidiscovery-approval-ui.service

curl -fsS http://127.0.0.1:8765/ >/dev/null
pytest -q
```

外部 TCAD 首先应使用部署冒烟 profile 验证 SSH 和 Runner。服务健康不代表
Sentaurus 许可证或任何科学模型已经通过。

## 7. 主要配置变量

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `SCID_WORKSPACE` | 由安装脚本位置推导仓库根目录 | 源码/工程根目录 |
| `SCID_PYTHON` | `PATH` 中第一个 `python3` | base 解释器 |
| `SCID_SERVICE_USER` | `SUDO_USER` 或当前用户 | 服务账户 |
| `SCID_SERVICE_GROUP` | 服务用户主组 | socket 和文件组 |
| `SCID_PLATFORM` | `codex` | `codex`、`claude` 或 `both` |
| `SCID_ENABLE_INGAAS_FIG4` | `0` | 设置为 `1` 时安装可选领域示例 |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | 应用安装目录 |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | 控制面状态 |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | 密钥和策略 |
| `SCID_APPROVAL_PORT` | `8765` | 本机审批端口 |
| `SCID_TCAD_COMMAND_CONFIG` | 未设置 | 外部 command adapter 配置 |

Runner 安装脚本还支持 `SCID_SSH_*`、`SCID_VMRUN_*` 和 `SCID_REMOTE_*` 变量。

## 8. 升级与卸载

重复执行 `install` 即可升级。应用包和生成的平台配置会被原子替换，旧配置备份到
`/var/backups/scidiscovery`。

```bash
sudo deploy/install.sh uninstall
```

卸载只移除服务，保留状态、配置和备份。只有在完成归档决策后才应手动删除它们。

## 9. 常见问题

- **无法安装 `pydantic`/`pydantic-core`**：确认 Python 3.10+、Linux 架构受支持，
  并确保 pip 能访问 wheel 或本地 wheelhouse。
- **MCP socket 不存在**：查看
  `journalctl -u scidiscovery-control.service -n 100`。
- **Worker 超时**：重试前先读取 `task_status` 的 phase 时间；不能覆盖仍活动的尝试。
- **审批返回 403**：必须在同一主机打开精确 URL，并确认当前进程已绑定正确实例。
- **VM IP 变化**：只更新私有 transport 配置或使用 resolver，不要把新地址写进源码。
- **TCAD 作业似乎卡住**：使用短状态调用，不得用长连接 SSH 等待 Solver。
