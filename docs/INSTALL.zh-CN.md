# 安装教程

简体中文 | [English](INSTALL.md)

## 新项目默认：薄 CLI

`deploy/install.sh` 与 `deploy/reinstall.sh` 默认 `SCID_DEPLOY_MODE=thin`。
先提供 Python 3.10+ 及 `pyproject.toml` 声明的应用依赖；应用离线构建，
不安装第三方依赖、不建新环境。

```bash
SCID_PYTHON="$(command -v python3)" deploy/install.sh --dry-run
sudo SCID_PYTHON="$(command -v python3)" deploy/install.sh install
```

从全新 `/opt/scidiscovery-thin/site` 向 `/usr/local/bin` 发布 `scid-research`、
`scid-experiment`。可选 `SCID_INSTALL_ROOT` / `SCID_BIN_ROOT` 须为绝对 canonical
路径，bin 目录须已存在；无需 systemd、旧 workspace、Root 配置、SQL、密钥或实例，
也不自动创建它们。按 [CLI 合同](ROOTLESS_CLI.zh-CN.md)明确选择实例、原文、预算和
可选实例 UI；安装领域插件不配置或授权远端执行。

已有 site 或任一薄 wrapper 均拒绝覆盖，即使其它目标为空；不停止旧服务。
激活失败仅尝试回滚本次匹配的 wrapper，保留不可变代码 prefix；若失败处理中
发现外来 wrapper，整个命令事务保留并报告 rollback incomplete，不删除未知文件。
事务前 staging 失败可能
留下私有 `.site.new.*` 目录；它没有已发布命令或执行权。`status` 只核 wrapper
归属，不加载实例；`uninstall` 只删匹配本解释器/site 配置的 wrapper，保留代码、
实例与旧服务。这不是自动就地升级，也不证明旧写者已停止。

## 显式旧服务部署

**下文为旧 SQL/MCP/systemd 部署教程。** 原安装、重装、status/uninstall 的每次
命令都须显式传 `SCID_DEPLOY_MODE=legacy`（包括经 sudo 传递），例如：

```bash
export SCID_DEPLOY_MODE=legacy
sudo SCID_DEPLOY_MODE=legacy SCID_PYTHON="$(command -v python3)" \
  SCID_WORKSPACE=/absolute/existing-workspace deploy/install.sh install
```

保留旧数据和现有服务，不静默转换或删除。旧 UI 和多数 `scid` 管理命令会打开
runtime，不能冒称只读出口；离线 `active-bundle-verify` 仍可用，active bundle
export 只覆盖选定科学 Artifact，不是整个 SQL/控制状态迁移。独立旧档案读取/导出
及停写接缝属于下一迁移节点。

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
export SCID_DEPLOY_MODE=legacy
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
`.codex/config.toml` 顶层独立托管块中的 Root `developer_instructions`、受控角色
TOML，并将 `roles/common.md` 的共同规则写入项目 `AGENTS.md` 托管块。
交互 CLI 与后台 Root 使用同一项目配置；受控 Worker/helper 仍使用原有角色
developer 指令和冻结 assignment。

生成文件包含当前设备的绝对路径，因此每台机器都必须重新生成，不能提交到 Git。
workspace 的 `AGENTS.md` 只保留该论文或用户任务的专用约束，安装器会迁移并移除
旧版本重复写入其中的通用 scheduler 块。

重新生成会迁移可识别的旧 scheduler 块，并逐字保留托管块外的用户内容及空白。
项目或发现的上游配置已有用户 developer 值时，安装器在写入前报告适用范围冲突；
它不能推断这些规则属于 Root、Worker 还是共同约束。应明确解决所有权，安装器
不会复制、提升或静默覆盖用户规则。中途写入失败时逐项尽力恢复原文件字节和模式；
持续文件系统错误可能妨碍恢复，此时错误会列出恢复失败路径并保留原始安装失败。
信任实际项目配置并在重新生成后重载 Codex；已有线程历史仍保留旧指令，需要新
线程核查分离。未托管的 Agent、IDE 入口及任意 CLI/profile override 不属于受控角色承诺。

本指令分离源码及定向验证已通过独立复审，包括持续写入拒绝和恢复拒绝负例。
候选 `1958a33` 已通过隔离 rebuilt wheel 加载、新安装、旧块迁移、幂等及配置校验，
以及真实交互/后台 Root 和 fresh text_disabled/image_live 的启动指令投递检查。
Token 观察止损前未验证后台 Root 与 image_live 自然终态；科学 assignment 流程、
本候选的恢复/轮换及正式部署仍未验证。

## 4. 本地部署冒烟测试

此模式只验证服务和 MCP 接口，不运行科学 Solver。内部 TCAD controller 只允许
`/bin/true`。

```bash
PYTHON="$(command -v python3)"

# 可选源码预检。选定 Python 必须已能导入工程依赖。
SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_PYTHON="$PYTHON" deploy/install.sh --dry-run

sudo SCID_DEPLOY_MODE=legacy SCID_PYTHON="$PYTHON" \
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
sudo SCID_DEPLOY_MODE=legacy SCID_PYTHON="$PYTHON" \
  SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
  deploy/install.sh install
```

外部适配器模式只校验适配器配置；执行策略由外部执行器返回。本机遗留的
`tcad-policy.json` 不参与此模式的校验，也不会被改写或调整权限。本地 socket
模式仍要求管理员提供符合当前 schema 的完整策略。安装成功不代表远端策略或
求解器已经通过真实执行验收。

TCAD 的 `agent_execution_policy` 现在区分两个可配置阈值：
`max_wall_time_seconds` 为单次阈值（示例 3600 秒），
`max_total_wall_time_seconds` 为同一研究实例的累计阈值（示例 21600 秒）。
执行仍须有精确控制绑定的研究目标；修改目标载体或 objective key 不会创建新额度池。
请求先预留声明上限，结束后按 runner 观测的真实耗时结算。安装事务只从随包示例配置
补充缺失的累计字段以及 `debug.budget_scope`，保留已有显式配置。诊断默认范围 `task`
累计控制层绑定的完整任务恢复家族；`scientific_subject` 可显式启用同一研究实例的共享历史额度。
该诊断策略不改变正式执行的实例额度池。诊断名称属于精确 Run，恢复同名作业需要唯一的控制授权来源 Run。
达到诊断额度时可由
管理员调整 `debug.total_wall_seconds` / `debug.max_runs`，不会清空历史用量；修改策略后
需要重建诊断 runtime 或重启其所属服务，以重新读取适配器缓存的策略。
使用随包 SSH 部署时，会同时升级 VM runner
代码和远端配置；两端须使用新策略合同。既有审批决定和科学 Run 重试次数不变。

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

资料归档功能本身沿用审批 UI 服务及原端口，不需要 VM 协议变更；TCAD 策略更新仍会同步 VM runner。
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

验收范围与未完成的生产现场项见[发布说明](RELEASE.zh-CN.md#current-status)。

## 7. 主要配置变量

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `SCID_WORKSPACE` | `<源码根>/workspace/default` | 已创建的独立项目工作区；不能是源码根 |
| `SCID_CODEX_LAUNCH_ROOT` | 未设置 | 可选的 Codex 实际启动目录；与源码根和 workspace 不同时生成同代项目配置 |
| `SCID_PYTHON` | `PATH` 中第一个 `python3` | base 解释器 |
| `SCID_SERVICE_USER` | `SUDO_USER` 或当前用户 | 服务账户 |
| `SCID_SERVICE_GROUP` | 服务用户主组 | socket 和文件组 |
| `SCID_PLATFORM` | `codex` | Codex 平台选择器；其他值会被拒绝 |
| `SCID_WORKER_BACKEND` | `local` | 仅支持 `local`，保留声明的原生权限；退役的 `hardened` 在部署变更前拒绝 |
| `SCID_PLUGINS` | 空 | 逗号分隔的本地插件目录名；例如 `tcad_artifact,curve_score,curve_figure_evidence` |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | 应用安装目录 |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | 控制面状态 |
| `TCAD_STATE_ROOT` | `${SCID_STATE_ROOT}/tcad` | 本地适配器执行状态；外部 command 模式忽略此项 |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | 密钥和策略 |
| `SCID_APPROVAL_PORT` | `8765` | 本机审批端口 |
| `SCID_TCAD_COMMAND_CONFIG` | 未设置 | 外部 command adapter 配置 |

升级已使用独立状态目录的本地适配器时，显式设置 `TCAD_STATE_ROOT` 沿用原目录；安装器不自动迁移数据。

`hardened` 已退役。升级旧部署前，先在旧版结束或归档在途任务并保留状态，
再显式设置 `SCID_WORKER_BACKEND=local`，通过安装器重新生成 Codex profile。安装器、CLI、运行时
和平台生成器会拒绝旧值并给出迁移说明，不自动降级或扩大原生权限。历史 Run、Artifact 和归档
仍可读取，旧 Run 不能在 Local 上启动。回滚需核对旧配置和在途任务身份。此次删除不实现 OS
强隔离，也不关闭 `SEC-002`；Local 原生写者无法证明已停止时仍拒绝归档，终态本身不充分。

Runner 安装脚本还支持 `SCID_SSH_*`、`SCID_VMRUN_*` 和 `SCID_REMOTE_*` 变量。

## 8. 升级与卸载

重复执行 `install` 即可升级。应用包和生成的平台配置会被原子替换，旧配置备份到
`/var/backups/scidiscovery`。

```bash
sudo SCID_DEPLOY_MODE=legacy deploy/install.sh uninstall
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

分析内受控补收集需要控制端、Worker 和 VM helper 匹配更新。使用随包 SSH 适配器时，主重装事务按选定的 command 配置同步 runner 代码和配置；策略 schema 更新不能只跑代码升级命令。保留原结果目录和显式管理员设置，重新加载 Codex 后再创建新分析 Run。独立维护的外部适配器需自行部署匹配版本。不要为了重新收集而重提原执行。

## Agent 执行配置

`run_list` 和 `scientific_inventory` 的整页 JSON 大小由公共
`agent-settings.json` 中的 `mcp_read` 控制：`summary_max_bytes` 默认 4096，
`detail_max_bytes` 默认 32768。`limit` 是条数上限；字节预算可能让本页更短，
须使用返回的 `next_before` 续读。摘要不含逐任务派发说明或模型配置，科学对象的
资格标记仍保留。单条对象超过预算时，返回 `entry_omitted` 标记、精确名称和
`read_request` 读取入口；`next_before` 可越过该标记，后续对象不会被挡住。
省略标记不代表科学结论，须用 `run_status` 或 `artifact_catalog` 按名读取原内容，
不能把未返回对象当作不存在。这是公共控制面设置，实例覆盖不适用。预算包含追加的 attention 通知，装不下的通知保持待交付。回滚到不认识 `mcp_read` 的旧版前，须从配置中移除该节。

安装器首次创建 `${SCID_CONFIG_ROOT}/agent-settings.json`（默认 `/etc/scidiscovery/agent-settings.json`），默认使用简体中文新报告、`gpt-6-sol`、`medium`。已有文件若与上一版安装器生成的默认内容完全相同，会在安装事务中升级为新默认值；自定义文件保持不变。控制服务与审批/管理页面通过相同的 `SCID_AGENT_SETTINGS_FILE` 读取它；修改公共文件后重启两个服务生效。缺文件沿用兼容默认；文件存在但内容错误时显示具体字段错误，不静默回退。
初始模型值来自随包提供的 `scidiscovery/default_agent_settings.json`；Agent Operation 声明不再固定模型。

同一文件中的 `experiment_provider` 是部署级设置，选择完整实验任务的远端贡献。
默认 `"auto"` 在零候选时支持原生本地实验，单候选时自动采用，多候选时拒绝启动。
`"none"` 显式禁用远端实验工具；`"tcad_artifact:experiment_capability"` 选择该已安装 provider。
允许安装多个 provider，但这类任务一次只启用一个。此选择不禁用独立 Effect 接口，
也不免除已安装 runtime 插件的现有配置要求。控制、独立 Worker、健康检查和生成的
Codex 配置读取相同的 `SCID_AGENT_SETTINGS_FILE`。改变选择后运行 `scid init codex`
重新生成配置并重启宿主；旧 Run 不能以不同编译身份重新启动。已有远端执行的恢复与收集
仍使用原 executor，不支持热切换或自动迁移。Worker 每一步可选择原生本地计算或实际
可用的远端工具。本地源码、日志和结果沿用文件发布与阶段封存；不可变文件身份保留
Worker 来源，不构成执行证明。

当前 M7 配置与上一版生成的默认文件完全一致，重装时会自动把其中的 `defaults.model` 升级为 `gpt-6-sol`。其他安装若自定义文件仍使用旧模型，需要单独修改并重启控制服务与审批 UI 服务。实例级模型覆盖仍优先；已创建 Run 的执行 profile 保持冻结值。

```json
{
  "schema_version": 1,
  "defaults": {"narrative_language": "zh-CN", "model": "gpt-6-sol", "reasoning_effort": "medium"},
  "operations": {}
}
```

实例管理列表提供独立的“Agent 设置”和“资料整理与归档”入口。点击“Agent 设置”可取得编辑权限并覆盖语言、模型、推理强度和恢复链总 Run 数，也可按已安装 Operation ID 覆盖后三项。留空继承，清除全部覆盖恢复公共默认。只读访问不能保存；归档实例只读；保存仅影响新预检，不启动 Agent、仿真或审批，也不改变会话绑定。历史英文报告不翻译，历史 Run 未记录的配置不回填。

首次升级本功能需要正常安装、重新生成角色并重新加载 Codex，移除旧角色文件固定的模型；之后实例修改配置无需新 role 或重启。Worker 按每个 Run 的冻结配置工作，调度方须将预检返回的 `normalized_request` 原样用于 invoke，并使用返回的 `execution_profile.profile.model` / `reasoning_effort` 分发。旧独立 CLI 启动脚本支持 `--model` 与 `--reasoning-effort`，新动态角色要求这两项来自已排队 Run。配置是请求事实，不冒充实际模型遥测。VM runner 不变，本次无需同步 VM。回滚应使用安装事务中匹配的代码、角色、数据库和配置备份。

## 实验材料与读取预算

### 封存后的 UI 自动导读

阶段结论及最终 Run 结果封存后，控制层将展示整理请求写入既有 UI 缓存；审批 UI
服务串行处理。模型使用 `helpers.profiles.lightweight`（包默认 `gpt-6-luna` / `low`），
不占用 Worker 的原生 helper 次数，也不要求 Worker 或 Root 阅读、确认或审批。
原始结论、数值、图件、执行状态均保留；导读单独标注，可失败或缺失。
相同来源版本与配置只入队一次，重启后不自动重试已发起但状态不明的模型调用。

`agent-settings.json` 的 `presentation` 配置在 dev 默认关闭；开启后会额外调用模型生成导读。
启用前应为其预留独立资源和 token 预算。原始封存内容、阶段进展和审批展示不依赖它。支持：

```json
{"presentation":{"enabled":true,"command":["/absolute/path/to/codex"],
  "timeout_seconds":60,"interval_seconds":5,"max_source_bytes":1048576,
  "max_input_bytes":16384,"max_output_bytes":32768,"memory_limit_bytes":2147483648}}
```

使用 [Codex 非交互结构化输出](https://developers.openai.com/codex/noninteractive/)，每次为
独立临时会话，只传有界科学文本，不加载用户工具配置、项目说明或父会话，不提供
科学执行工具。`deploy/reinstall.sh` 在 sudo 前定位 Codex，以绝对路径
`SCID_CODEX_EXECUTABLE` 传给服务；可显式设置该变量覆盖自动发现。启动器同时解析
npm 入口旁的 Node，不要求 systemd 继承 nvm PATH。非默认 `codex` 的
`presentation.command` 自定义命令优先。

展示助手默认使用 `${SCID_WORKSPACE}/.scidiscovery-ui/display-codex` 作为持久 Codex 目录，
也可通过 `presentation.codex_home` 指定独立绝对路径。安装器以 `0700` 权限创建隐藏
父目录，并为审批 UI 服务开放该目录的写入权限；框架 Git 忽略规则已排除该目录。
首次仅从服务用户的 Codex
目录复制文件式认证缓存，并以私有权限保存；后续认证刷新保留在专用目录，不覆盖回
交互用户目录。不复制研究会话或用户配置；原 home 的旧式管理策略文件保持链接，
系统管理策略仍生效。若只使用系统 keyring，需单独为专用目录登录。
这采用官方支持的 [Codex 认证缓存复用](https://developers.openai.com/codex/auth/)；
该目录包含认证信息，须保持私有。

SQLite 索引也保存在专用目录。此前每次新建临时 SQLite 目录、却沿用研究会话目录，
会触发历史会话索引，造成额外内存消耗和启动超时。`memory_limit_bytes` 是每进程的
虚拟地址空间上限，不是实际 RSS；仍可配置，例如 `13000000000` 表示 13 GB。
部署修复后，旧失败条目也可通过显式“重新整理”使用修好的默认运行目录。
没有可用启动器或认证时回退原文，
不会影响封存和审批。无需更改 VM runner。

缓存位于 `ui/workbench.sqlite3` 的 `display_summaries` 表，按实例及精确 ArtifactRef
隔离；保存成功调用的 input/cached-input/output token、输入字节及耗时。
失败调用的实际 token 可能不可得，不能按零计费；完整错误进入受实例限制的工程诊断。
历史材料不会因打开页面而触发模型调用。全局禁用后重启服务可停止后台整理。
具有实例管理权限的页面提供“生成导读”（尚未生成）和“重新整理”（已完成或失败）；
按钮位于可折叠的“自动导读”区域外，折叠后仍可使用。阶段子节点按自己的确切封存
材料和版本读取、刷新和整理导读，不复用父实验报告。重新整理沿用该条目的整理配置，
不修改科学结果，不要求 Worker 核对。排队或运行期间按钮禁用，重复提交旧表单不会
多启动一次整理。归档、维护期间及全局禁用时不可操作。

“实验进展”也可折叠，自动刷新保留手动展开状态。审批页的“作废此审批请求”只对
未决策请求开放，仍需页面身份与提交校验；作废记录人工决定和回执，不授权执行，
不能覆盖已有批准或拒绝。

### 科学材料预算

完整实验的 `scientific_materials` 支持原始 PDF、图片、CSV、JSON、归档和网格文件；
`scientific_files` 也接受这些类型，显式采用按需文件交付。它们共用材料存储预算，
不再把 1 MB 当作论文或文件的准入上限。小文本可以直接读取，较大或二进制材料
只保留精确引用，通过 `worker_materialize_input(source_name=...)` 分块取到工作区。
实验 Worker 允许原生图像查看；启动材料不会携带原始文件内容或要求填写哈希等机械字段。

在 `${SCID_CONFIG_ROOT}/agent-settings.json` 中配置以下顶层字段（单位为字节）：

```json
{
  "input_materials": {
    "max_item_bytes": 2000000000,
    "max_total_bytes": 2000000000,
    "inline_max_bytes": 1048576,
    "inline_total_bytes": 8388608,
    "transfer_chunk_bytes": 1048576
  }
}
```

将该字段合并进现有配置，保留模型等其他设置；不要整文件覆盖。前两项限制绑定文件的
单项与合计大小，中间两项限制自动内存交付，最后一项控制流式复制块大小。
实例设置中已有的同名覆盖会继承并覆盖公共值；当前表单不提供这些字段的编辑控件。
`scid_describe` 返回实际生效的预算，新 Run 冻结预算和交付方式。超限诊断指出具体材料；
不得通过丢弃必要原始证据规避失败。该预算不替代 TCAD 执行授权与运行资源策略。
升级需要重新生成角色并重载 Codex；不要在旧合同任务运行期间切换服务版本。

## 后台研究候选：启用、验收与回滚

B6 当前为发布候选，资格以 源码仓库 `docs/plans/AUTONOMOUS_RESEARCH_RELEASE_PLAN.zh-CN.md` 的 B6 验收记录 为准。安装、重启或选择实例不会创建目标；只有用户明确启动已冻结原文才运行后台 Root。`progression.enabled` 默认允许显式启动，并非安装即开工；管理员可在公共 agent-settings.json 中设置 `"progression":{"enabled":false}` 禁止新启动。修改公共设置后重启 control 与 UI。普通任务不增加审批或资格门。

真实旅程入口（普通登录终端，使用已登录的 Codex）：先将 `SCID_PREVIOUS_CANDIDATE` 设为已静止的旧验收候选，`SCID_INSTALLED_CANDIDATE` 设为已验证的新版本安装候选。目标路径必须未使用；迁移保留原实例和证据，但不继承会话选择或调度权限。

```bash
python scripts/probe_root_host_live.py prepare-upgrade \
  --candidate /tmp/scid-b6-upgrade \
  --from-candidate "$SCID_PREVIOUS_CANDIDATE" \
  --installed-candidate "$SCID_INSTALLED_CANDIDATE"
python scripts/accept_progression.py --candidate /tmp/scid-b6-upgrade
```

准备过程复用新安装，不重新构建；验收入口拒绝未准备或无既有实例的空状态。入口共享资源守卫及串行锁。打开打印的管理页选择原验收实例，之后自动继续，无需再运行协议命令。原生 Root 冻结合成研究原文并启动后台目标，后台 Root 自主选择完整任务。问题含已知样本关系与不能识别机制的情形；最多三个任务、八轮、1200 秒，token 与资源策略沿用配置，不调用 TCAD。原生输出、封存回读审计、错误和缺测分别留在候选的 `journey-*/summary.json`、`progression.json`、`fixture-logs` 和 `resource.json`。机器摘要不自动授予 B6 通过；科学依赖、附件与原生生命周期仍须依据实际证据核对。若启动在任何模型提交之前失败，修复环境后可给同一命令增加 `--retry-startup`；已经可能提交过模型请求时拒绝重放。

此验收使用可独立运行的生产 daemon/UI 模块，继承当前用户的 PATH、HOME、CODEX_HOME 和现有认证，不复制认证文件。正式单用户运行也可直接用安装解释器启动同一模块：

```bash
# 以下变量取自该安装，不能把两个 daemon 指向同一 state/socket。
export SCID_AGENT_SETTINGS_FILE="$SCID_CONFIG_ROOT/agent-settings.json"
"$SCID_PYTHON" -m scidiscovery.artifact_agent.interfaces.mcp_daemon \
  --project-root "$SCID_WORKSPACE" --state-root "$SCID_STATE_ROOT" \
  --socket "$SCID_CONTROL_SOCKET" --approval-secret-file "$SCID_APPROVAL_SECRET" \
  --approval-base-url http://127.0.0.1:8765 --worker-backend local \
  --local-workspace-root "$SCID_WORKSPACE/.scidiscovery-runs" \
  --runtime-summary "$SCID_STATE_ROOT/runtime-summary.json"
```

UI 使用安装器已有 `scidiscovery-approval-ui` 服务，且必须指向相同 state、设置、签名密钥及端口。独立 daemon 的解释器须能导入安装包（wheel venv 自带；site 安装遵循原安装的 PYTHONPATH）。需要关闭交互终端后保持服务时，将上面的 daemon 命令交给当前用户的进程管理器，例如 `systemd-run --user --unit=scid-user-control --setenv=PATH="$PATH" --setenv=CODEX_HOME="${CODEX_HOME:-$HOME/.codex}" --setenv=SCID_AGENT_SETTINGS_FILE="$SCID_AGENT_SETTINGS_FILE" --setenv=PYTHONPATH="${PYTHONPATH:-}" --property=MemoryMax=1500M --working-directory="$SCID_WORKSPACE" <上述解释器及参数>`；使用 `systemctl --user status/stop/restart scid-user-control` 管理。先停止系统级 control，确认没有其他有效写者，再启用户服务；保留相同 state/socket，禁止同时启动两个入口。用户服务是否跨注销存活取决于主机 user manager 配置，不能由本项目保证。

系统级安装默认 `SCID_SERVICE_USER=SUDO_USER` 或当前用户，未必是专用账号；但其 systemd PATH 不继承登录 shell，单元有 `PrivateTmp=true`、`ProtectHome=read-only`，且不显式继承自定义 CODEX_HOME。即使账号相同，也不能据普通终端验收宣称这个单元的原生 Codex daemon、认证刷新与 helper 写入已通过。当前原生资格应在所选运行方式下验证，不应复制密钥或随意放宽系统单元权限。真实模型/助手、浏览器操作、跨终端持续运行及费用优劣，未测量者保持缺测。

升级前保存版本与 wheel 清单、agent-settings、生成配置、签名密钥、state 数据库和 WAL、封存对象、工作区结果及归档目录。通过管理页暂停/停止推进，核清已接受 Worker 与外部作业，并停止所有写者后备份；活跃数据库用 SQLite backup 或既有维护/归档机制，不能只复制主文件。`prepare-upgrade` 复制旧候选时拒绝未完成任务、活跃或身份未核清的宿主；复制后的推进保持暂停，旧会话/派发权清除，预算、封存结果和历史通知保留。管理页重新选择实例，显式恢复之前不会运行。

回滚顺序：管理页停止新派发 → 核对在途/未知提交 → 停 control 与相关宿主 → 备份当前完整状态 → 切换兼容代码/配置 → 保持推进停用并先只读核对。不要用 `git revert`、旧数据库覆盖或恢复旧快照抹掉已经接受的外部提交。A 版本不认识新增推进表；不能假定它会安全拒绝新数据。新控制服务拒绝高于自身的 scheduler `user_version`；归档外层仍为 v1，内含新控制表，不能凭外层版本判断旧代码兼容。无同格式恢复证据时禁止降级读取/写入活动库，保留新版代码停用推进作为只读/人工恢复入口。任何未知提交必须先查回原作业，不能重新发起。
## 历史未知提交的管理员恢复

升级时先更新并验证远端 runner，再启用新控制面；标准安装事务按此顺序执行。
部署探测必须通过能力、策略及 `tcad_submission_protocol` 三项只读检查。
仅替换 runner 文件不能停止已加载旧代码的 RPC/提交进程。

历史请求没有撤销支持标记时，普通取消不会自动释放预算。管理员应先停止本地旧提交者，
确认远端旧 RPC/提交进程及待处理提交已退出，并升级 runner。不要把“查询不到任务”作为此确认。
以控制服务账户，在已安装的 Python 环境中执行（替换精确执行 ID；安装路径按实际配置）：

```bash
PYTHONPATH="${SCID_INSTALL_ROOT:-/opt/scidiscovery}/site" "${SCID_PYTHON:-python3}" \
  -m scidiscovery.artifact_agent.interfaces.submission_recovery \
  --state-root "${SCID_STATE_ROOT:-/var/lib/scidiscovery}" \
  --execution-id EXACT_EXECUTION_ID \
  --confirm-old-submitters-stopped \
  --reason '管理员已确认旧提交进程全部退出，远端已升级；记录对应运维凭据'
```

命令拒绝仍持有本地提交锁的请求，并持久记录管理员 UID、理由、时间与精确提交摘要。
它不修改执行终态、不删除证据、不释放预算。恢复服务后，对原执行调用普通取消/放弃：
远端查到任务时接续该任务；只有原子撤销成功后才能释放预留。远端不可达时仍保留原状态和额度。
此命令不注册为 MCP 或 Worker 工具；同 UID 的技术隔离仍受已披露的 SEC-002 限制。

终态查询短暂失败不会立即按上限扣账。管理员可在 `agent-settings.json` 的 `lifecycle` 中设置
`terminal_observation_failure_limit`（默认 3，正整数）；连续失败达到阈值才估算，成功查询重置计数。
