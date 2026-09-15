# 安装教程

简体中文 | [English](INSTALL.md)

## 1. 支持环境

- 带 systemd 的 Linux 或 WSL2
- Python 3.10 及以上，并带有 `pip`、`setuptools>=68`、`packaging`、
  `pydantic>=2,<3` 和 `jsonschema>=4,<5`
- Codex CLI
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

安装器使用选定的 base Python 解释器，只把当前仓库的应用包安装到
`/opt/scidiscovery/site`。它不会创建 venv、联网下载依赖，也不会修改选定的
Python 环境。第三方依赖必须在部署前准备好。使用 Conda base 时执行：

```bash
conda install -n base -c conda-forge \
  'pydantic>=2,<3' 'jsonschema>=4,<5' 'setuptools>=68' packaging pip
```

正式安装会显示每个执行阶段，并且先完成本地包构建，再停止已有服务。激活过程是
事务化的：精确备份 release/configuration 目标和 SQLite 数据库；服务或 MCP 健康
检查失败时恢复安装前文件与服务状态。成功事务证据保留在
`/var/backups/scidiscovery/transactions/`。

通用事务化重装入口是：

```bash
SCID_WORKSPACE="$PWD/workspace/<project-name>" \
  deploy/reinstall.sh --dry-run
SCID_WORKSPACE="$PWD/workspace/<project-name>" \
  deploy/reinstall.sh reinstall
```

`reinstall.sh` 默认不安装领域插件；通过 `SCID_PLUGINS` 显式选择
`tcad_artifact,curve_score` 等插件，通过 `SCID_TCAD_COMMAND_CONFIG` 选择外部适配器。
`install` 和 `reinstall` 使用同一个事务化流程；无参数等价于 `install`。

图像曲线提取使用三个通用领域插件。部署前离线预装符合插件声明范围的
Pillow 和 Poppler `pdfimages`。坐标轴、刻度和科学身份由智能体查看原图后提供，
运行链不使用 OCR 或 Tesseract。安装器只记录实际的 Pillow 和 `pdfimages`
版本及可执行文件绝对路径。

```bash
export SCID_PYTHON=/absolute/path/to/service/python
"$SCID_PYTHON" -m pip install --no-index --find-links /srv/scid-offline/wheels 'Pillow>=10.0,<13.0'
export SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence
export SCID_PLATFORM=codex SCID_WORKER_BACKEND=local
export SCID_WORKSPACE=/srv/scid-project
export SCID_CODEX_LAUNCH_ROOT=/srv/scid-codex
export SCID_SERVICE_USER="$(id -un)" SCID_SERVICE_GROUP="$(id -gn)"
deploy/reinstall.sh --dry-run
# 安装与审查门通过后才执行：
deploy/reinstall.sh reinstall
```

workspace 与启动目录须已有且独立于 checkout。通用 wrapper 由服务用户运行。
安装器在创建安装事务前，以真实服务身份和 systemd 有效默认 PATH 执行 Python
import、版本调用及一次真实 PDF 嵌入图恢复；
操作者 shell 的 PATH 不充当服务依赖检查。

核验结果只写入暂存安装包的
`site/curve_figure_evidence/figure_dependencies.json`，切换前和安装后再用服务
Python 复验。激活时将安装前缀设为只读；运行时使用记录中的
`pdfimages` 绝对路径并复核版本。工具版本变化须重新生成安装记录。
未供应该记录的普通 wheel 可以编译，但不能通过 figure 安装预检。

当前可信 Local 后端采用软隔离，不是操作系统沙箱。生产包、运行资源、默认配置和
Worker 显式上下文不得携带案例几何、历史答案或可作为答案发现入口的路径。历史审计文档
可保留定位符，但运行端不得消费它们。宿主读取探针若显示可读，必须如实记录，只能声明这些文件
未向 Worker 提供或未观察到被使用；`SEC-002` 继续保持已知问题。获准切换前检查旧合同
queued/running Run，不承诺跨 digest 恢复。图像曲线 Operation 不绑定外部
`scientific-paper-evidence` 技能。

Local Worker 可以发现已安装 Skill 并按需读取参考资源，Operation 工具权限保持不变。
独立受管的 TCAD Skill 具备部署目录完整性校验和事务回滚；其字节不绑定 Operation
或 Run 身份，因此不承诺逐 Run 参考知识重放。安装后须在全新 compiled Agent 会话中
验证发现与 helper 使用，生成提示测试本身不能证明此行为。

曲线分析更新后，在全新会话核对编译目录：`science.result.diagnose.v1` 直接接收实验结果，曲线 bundle 与评分报告为可选输入；启用 TCAD 时另有 `tcad.result.analyze.v1`，其 Worker 提供 `worker_tcad_curve_score`，接收原始输出与参考材料。这两个入口是分析职责的替代入口，不是串行步骤。重新安装不会刷新已启动会话的 Worker 工具目录；须重启会话。旧记录保留，但变更合同后的资格应以当前预检为准。

## 2. 获取源码

```bash
git clone <仓库地址> scidiscovery-agent
cd scidiscovery-agent

deploy/init_workspace.sh ingaas-paper
export SCID_WORKSPACE="$PWD/workspace/ingaas-paper"
```

Git 仓库只保存框架源码。每个研究项目必须位于被 Git 忽略的
`workspace/<project-name>/` 下；论文、参数、研究账本、仿真工程、日志和结果均放入
该项目目录的对应子目录。

WSL 下不要从 `/mnt/c` 运行 systemd 服务。应把工程放在 WSL 文件系统，例如
`~/src/scidiscovery-agent`。

## 3. 选择 AI 平台

`SCID_PLATFORM` 目前只支持 `codex`。它在框架源码根目录生成
`.codex/config.toml`、角色 TOML，并在根目录 `AGENTS.md` 中写入受管理的通用
调度规范；其下的 workspace 自动继承。

生成文件包含当前设备的绝对路径，因此每台机器都必须重新生成，不能提交到 Git。
workspace 的 `AGENTS.md` 只保留该论文或用户任务的专用约束，安装器会迁移并移除
旧版本重复写入其中的通用 scheduler 块。

## 4. 本地部署冒烟测试

此模式只验证服务和 MCP 接口，不运行科学 Solver。内部 TCAD controller 只允许
`/bin/true`。

```bash
PYTHON="$(command -v python3)"

# 可选源码预检。选定 Python 必须已能导入工程依赖。
SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_PYTHON="$PYTHON" deploy/install.sh --dry-run

sudo SCID_PYTHON="$PYTHON" \
  SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  SCID_WORKER_BACKEND=local \
  deploy/install.sh install
```

安装后包含：

- `/opt/scidiscovery/site`：只读 Python 应用包；
- `/var/lib/scidiscovery`：控制面状态；
- `/var/lib/scidiscovery/tcad`：仅本地适配器模式使用的执行状态；
- `/etc/scidiscovery`：服务密钥和执行策略；
- `/run/scidiscovery/control.sock`：Root MCP；
- `scidiscovery-control.service`；
- `scidiscovery-approval-ui.service`；
- Codex 为受支持的 Agent Operation 生成按 Operation 隔离的本地 stdio MCP；不安装中央 Worker 服务；
- 仅本地适配器模式启用的 `tcad-control.service`。

审批网页只监听 <http://127.0.0.1:8765>。

安装后需要完全重启 Codex。可以从框架根目录直接启动：

```bash
codex -C "$PWD"
```

也可以进入默认的嵌套 workspace；它会继承框架根目录中的 MCP 和 Subagent：

```bash
codex -C "$SCID_WORKSPACE"
```

若实际从源码根和 workspace 之外的目录启动 Codex，请将该已有绝对目录设置为
`SCID_CODEX_LAUNCH_ROOT`。安装器会在同一事务中为它生成、备份和校验 `.codex`
与 `AGENTS.md`，避免启动目录继续加载旧 MCP 定义。若通过 `SCID_WORKSPACE` 使用源码树之外的 workspace，安装器会在该 workspace
生成等价的项目级运行时配置，因为它无法继承框架根目录；这不会复制研究数据或
控制面状态。

```bash
export SCID_CODEX_LAUNCH_ROOT=/实际启动/codex/的绝对目录
```

不要在每次启动 Codex 时重复执行安装脚本。只有首次部署、切换安装配置或更新已
安装代码时才需要重新安装。

## 5. 远端 TCAD VM

### 5.1 配置 VM Runner

复制示例到不会提交 Git 的本地目录，不要把真实许可证或主机信息写回示例：

```bash
mkdir -p config/local
cp plugins/tcad_artifact/config/remote-runner.example.json \
  config/local/remote-runner.json
chmod 600 config/local/remote-runner.json
```

修改副本：

- 写入真实 `sprocess`/`sdevice` 路径；
- 写入 `STROOT`、`PATH` 和许可证环境变量；
- 为每个允许的 Solver 配置唯一 `profile_id`；
- 设置由 VM 普通用户拥有的 state/exchange 目录。

示例已显式包含一条 `sprocess` 与一条 `sdevice` profile。两条 profile 都必须保留
`solver_kind` 和非空 `release_evidence`，并分别指向管理员确认的真实可执行文件；不要
从可执行文件名或另一个 profile 的环境变量隐式推断这些信息。
仅复制并修改文件权限不算完成配置；安装器会拒绝与 tracked example 逐字节相同的
副本。

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

运行态 transport 已存在后，Runner 代码或私有 profile 配置发生变化时，应复用这份
transport 执行标准完整安装；这也是从旧版单 profile 配置迁移到当前双 profile 配置的
路径：

```bash
SCID_PYTHON="$(command -v python3)" \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install-from-transport --dry-run

SCID_PYTHON="$(command -v python3)" \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install-from-transport
```

`install-from-transport` 默认读取 `/etc/scidiscovery/tcad-transport.json`；可用
`SCID_TCAD_TRANSPORT_CONFIG` 指定另一个绝对路径。它复用 SSH executable、identity、
destination resolver、known-hosts 及精确远端路径，先在临时目录对候选 Runner 与配置
执行 `tcad_capabilities`，成功后才一起替换；提交后自检失败会恢复原文件。
所有会写入 VM 的安装模式都强制要求显式设置 `SCID_REMOTE_RUNNER_CONFIG`，并拒绝把
仓库中的 tracked example 当作私有配置部署。

仅当远端 `runner.json` 已经符合当前 schema、且明确只需更新代码时，才使用
`upgrade-code`。该模式不会上传或迁移配置，并会在旧 schema 上失败关闭：

```bash
SCID_PYTHON="$(command -v python3)" \
deploy/install_ssh_tcad_runner.sh upgrade-code --dry-run

SCID_PYTHON="$(command -v python3)" \
deploy/install_ssh_tcad_runner.sh upgrade-code
```

WSL 调用 Windows OpenSSH 时，常见 executable 是
`/mnt/c/Windows/System32/OpenSSH/ssh.exe`；identity 和 known-hosts 应使用该
可执行文件能够识别的路径格式。

使用外部适配器安装服务：

```bash
PYTHON="$(command -v python3)"
sudo SCID_PYTHON="$PYTHON" \
  SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
  deploy/install.sh install
```

外部适配器会替代本地 `tcad-control.service`。每次 SSH 操作都必须短时返回；后台
执行和持久 `running`、`status`、`done` 记录由 VM Runner 负责。
该模式忽略 `TCAD_STATE_ROOT`：安装器不创建本地 TCAD 状态目录、不修改其权限，也不备份其中的数据库。

## 6. 验证

```bash
deploy/install.sh status

systemctl is-active \
  scidiscovery-control.service \
  scidiscovery-approval-ui.service

curl -fsS http://127.0.0.1:8765/ >/dev/null
pytest -q
```

外部 TCAD 首先应使用部署冒烟 profile 验证 SSH 和 Runner。服务健康不代表
Sentaurus 许可证或任何科学模型已经通过。

### 实例工作台与归档

参数区提供精简预览，以及按原件分页的完整参数入口；设计取值、文献依据和实现绑定分别说明，
不推断缺失的出处或不确定性。每页最多 8 条，超过 4 MiB 的原件保留下载入口。
安装 `curve_figure_evidence` 插件后，证据节点可展示已保存的论文局部图、CSV 数值重绘与
叠点审计图，并下载原 CSV。仅按同次调用与原清单精确关联；缺图、缺输出端口或清单不完整时
显示局部缺口，不重新提取或判定旧资料资格。历史正文翻译暂未实现，无需配置翻译服务。

本版沿用审批 UI 服务及原端口，不新增服务、环境变量或 VM runner 协议；此次更新无需同步 VM。
使用原部署配置执行重新安装并重启服务。已绑定会话可通过 `instance_current` 返回的管理 URL
取得实例浏览/维护入口；URL 过期后重新获取。审批链接仍仅授权原请求，不能代替实例维护凭据。

安装器仅为审批 UI 增加 `<SCID_WORKSPACE>/.scidiscovery-archive/instances` 的写权限，安全创建
该固定目录并拒绝符号链接；不开放整个工作区。管理页支持精确预览后归档、只读浏览、恢复及
清理本实例的 UI 缓存，本版没有永久删除入口。恢复后需重新选择实例，不自动重启任务或延长审批。
共享原件和无法确认归属的历史文件保留并列明；远端 VM 原文件不迁移。首版限制目标实例的
控制记录快照为 32 MiB、单个控制载荷读取为 16 MiB、文件清单为 50,000 项；超过目标维护上限
会在预览报告不支持，保留原资料。无法完整读取的外部引用按共享缺口保守保留，不推定无引用。

如果无法确认本地原生进程已经停止，归档预览显示 busy/unknown 并保留资料。当前
LocalTrusted 历史 Run 不能单凭终态证明无写入者，这个限制不影响工作台读取或原科学流程。
归档/恢复中断应在管理页继续或回退，不能删除维护日志强行解锁。回滚旧代码前须使用新版完成
恢复，或将已归档实例保留为旧版无法续跑的离线资料。安装、卸载不删除归档。

验收范围与未完成的生产现场项见[实施记录](plans/evidence/instance-workbench/IMPLEMENTATION.zh-CN.md)。

## 7. 主要配置变量

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `SCID_WORKSPACE` | `<源码根>/workspace/default` | 已创建的独立项目工作区；不能是源码根 |
| `SCID_CODEX_LAUNCH_ROOT` | 未设置 | 可选的 Codex 实际启动目录；与源码根和 workspace 不同时生成同代项目配置 |
| `SCID_PYTHON` | `PATH` 中第一个 `python3` | base 解释器 |
| `SCID_SERVICE_USER` | `SUDO_USER` 或当前用户 | 服务账户 |
| `SCID_SERVICE_GROUP` | 服务用户主组 | socket 和文件组 |
| `SCID_PLATFORM` | `codex` | Codex 平台选择器；其他值会被拒绝 |
| `SCID_WORKER_BACKEND` | `local` | `local` 为可信本地原生工具路径；`hardened` 为纯 MCP 文件后端，值同时驱动 daemon、systemd、Codex profile 和安装验证 |
| `SCID_PLUGINS` | 空 | 逗号分隔的本地插件目录名；例如 `tcad_artifact,curve_score,curve_figure_evidence` |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | 应用安装目录 |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | 控制面状态 |
| `TCAD_STATE_ROOT` | `${SCID_STATE_ROOT}/tcad` | 本地适配器执行状态；外部 command 模式忽略此项 |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | 密钥和策略 |
| `SCID_APPROVAL_PORT` | `8765` | 本机审批端口 |
| `SCID_TCAD_COMMAND_CONFIG` | 未设置 | 外部 command adapter 配置 |

升级已使用独立状态目录的本地适配器时，显式设置 `TCAD_STATE_ROOT` 沿用原目录；安装器不自动迁移数据。

`hardened` 当前拒绝要求 shell、代码或 `view_image` 的 Operation，因此 TCAD Deck 作者第一版必须使用
`local`；这不会降低 Effect 的独立审批和 adapter 边界。

Runner 安装脚本还支持 `SCID_SSH_*`、`SCID_VMRUN_*` 和 `SCID_REMOTE_*` 变量。

## 8. 升级与卸载

重复执行 `install` 即可升级。应用包和生成的平台配置会被原子替换，旧配置备份到
`/var/backups/scidiscovery`。

```bash
sudo deploy/install.sh uninstall
```

卸载只移除服务，保留状态、配置和备份。只有在完成归档决策后才应手动删除它们。

从旧版 `artifact-agent-vnext` 或早期 `tcad-control` 迁移后，先审计旧服务目录和
用户级重复包：

```bash
deploy/cleanup_legacy_services.sh --dry-run
```

若审计确认当前服务正常，且当前配置没有引用旧目录，再删除旧版本并仅保留最近三份
SciDiscovery 安装备份：

```bash
sudo deploy/cleanup_legacy_services.sh clean
```

清理脚本不会删除 `/opt/scidiscovery`、`/etc/scidiscovery`、
`/var/lib/scidiscovery` 或 `/var/lib/scidiscovery-tcad`。

## 9. 常见问题

- **base Python 缺少依赖**：按照错误提示在选定的 Conda 或系统 Python 环境中
  安装依赖，再重新运行。部署过程本身不会联网解析第三方依赖。
- **MCP socket 不存在**：查看
  `journalctl -u scidiscovery-control.service -n 100`。
- **Agent Run 超时**：先读取 `run_status`；失败后创建新 Run，不覆盖旧结果或 current。
- **审批返回 403**：必须在同一主机打开精确 URL，并确认当前进程已绑定正确实例。
- **VM IP 变化**：只更新私有 transport 配置或使用 resolver，不要把新地址写进源码。
- **TCAD 作业似乎卡住**：使用短状态调用，不得用长连接 SSH 等待 Solver。

分析内受控补收集需要控制端、Worker 和 VM helper 匹配更新。本地重装后，执行 `SCID_PYTHON=/absolute/path/to/python deploy/install_ssh_tcad_runner.sh upgrade-code`，沿用现有传输配置只更新 helper 代码。保留原结果目录和远端配置；重启 Codex 会话后再创建新分析 Run。旧 helper 不支持检查时返回不可用，普通离线分析仍可进行。不要为了重新收集而重提原执行。

## Agent 执行配置

安装器首次创建 `${SCID_CONFIG_ROOT}/agent-settings.json`（默认 `/etc/scidiscovery/agent-settings.json`），默认使用简体中文新报告、`gpt-5.6-sol`、`medium`。升级保留已有文件，并把该文件纳入安装事务备份。控制服务与审批/管理页面通过相同的 `SCID_AGENT_SETTINGS_FILE` 读取它；修改公共文件后重启两个服务生效。缺文件沿用兼容默认；文件存在但内容错误时显示具体字段错误，不静默回退。

```json
{
  "schema_version": 1,
  "defaults": {"narrative_language": "zh-CN", "model": "gpt-5.6-sol", "reasoning_effort": "medium"},
  "operations": {}
}
```

实例管理列表提供独立的“Agent 设置”和“资料整理与归档”入口。点击“Agent 设置”可取得编辑权限并覆盖语言、模型、推理强度和恢复链总 Run 数，也可按已安装 Operation ID 覆盖后三项。留空继承，清除全部覆盖恢复公共默认。只读访问不能保存；归档实例只读；保存仅影响新预检，不启动 Agent、仿真或审批，也不改变会话绑定。历史英文报告不翻译，历史 Run 未记录的配置不回填。

首次升级本功能需要正常安装、重新生成角色并重新加载 Codex，移除旧角色文件固定的模型；之后实例修改配置无需新 role 或重启。Worker 按每个 Run 的冻结配置工作，调度方须将预检返回的 `normalized_request` 原样用于 invoke，并使用返回的 `execution_profile.profile.model` / `reasoning_effort` 分发。旧独立 CLI 启动脚本支持 `--model` 与 `--reasoning-effort`，新动态角色要求这两项来自已排队 Run。配置是请求事实，不冒充实际模型遥测。VM runner 不变，本次无需同步 VM。回滚应使用安装事务中匹配的代码、角色、数据库和配置备份。
