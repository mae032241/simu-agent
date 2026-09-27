# R5 E4：部署组合与安装前证据

日期：2026-09-05

状态：**PASS；真实事务化重装、安装态核验与独立收口均完成**

## 1. 唯一源码修改

Fig.4 profile 的默认插件组合由：

```text
tcad_artifact,curve_score,ingaas_fig4
```

改为：

```text
tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4
```

仅同步已有 profile 测试和中英文安装说明。没有修改 `install.sh`、`reinstall.sh`、事务回滚、systemd
模板、状态目录、Run、current、执行适配器或 Codex 生成逻辑。

## 2. 停服务前验证

源码 profile 与 clean release profile 的真实 `--dry-run` 均通过，输出明确选择四个插件，并完成：

- 插件依赖解析；
- 源码导入；
- Pydantic、Pillow、jsonschema、setuptools 基础依赖检查；
- systemd 模板渲染与部署预览；
- 不修改包、状态、服务或平台配置。

clean release 位于 `deliverables/r5-pre-e2e-e4-clean-release/`，由仓库 release builder 生成，包含
240 个源文件及 `MANIFEST.sha256`；对应归档为
`deliverables/r5-pre-e2e-e4-clean-release.tar.gz`。

## 3. 离线 wheel 与安装态目录

从 clean release 离线、无依赖下载构建并安装五个发行包到：

```text
deliverables/r5-pre-e2e-e4-installed-site/
```

结果：

```text
Successfully installed:
  scidiscovery-0.1.0
  tcad-artifact-0.1.0
  scidiscovery-curve-score-0.2.0
  scidiscovery-curve-figure-evidence-0.1.0
  scidiscovery-ingaas-fig4-0.2.0
peak RSS: 51148 KiB
```

从项目 workspace 启动、移除外部 `PYTHONPATH` 并仅指向该安装目录的探针确认：

- 唯一 `scidiscovery.plugins` 入口集合为
  `builtin,curve_figure_evidence,curve_score,general_science,ingaas_fig4,tcad_artifact`；
- 编译目录共有 49 个 Operation；
- 请求 Agent、物化 Transform、Intake Agent、审查 Agent、打包 Transform 五项分别位于预期的
  public/support 视图和 agent/transform executor；
- 三个图 Agent 均无本地 Worker 工具缺失；
- `tcad.study.execute` 仍为 effect，TCAD runtime factory 仍唯一归属 `tcad_artifact`。

## 4. 安装前真实服务不是新版本

当前 systemd 服务仍运行 2026-09-04 18:07 安装到 `/opt/scidiscovery-m7/site` 的旧安装态：44 个
Operation，插件入口缺少 `curve_figure_evidence`，五个图 Operation 均不存在。控制与审批 UI 服务
虽为 active，但不能作为本次 E4/E5 的运行入口。

本 Codex 会话受 `no-new-privileges` 沙箱约束，`sudo` 无法取得 root，因此不能自行写 `/opt`、
`/etc` 或切换 systemd。真实切换必须由宿主普通用户执行以下已经 dry-run 验证的事务化入口：

```bash
SCID_INSTALL_ROOT=/opt/scidiscovery-m7 \
SCID_STATE_ROOT=/var/lib/scidiscovery-m7 \
SCID_CONFIG_ROOT=/etc/scidiscovery-m7 \
SCID_BACKUP_ROOT=/var/backups/scidiscovery-m7 \
SCID_APPROVAL_PORT=8765 \
SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
deploy/apply_ingaas_fig4_profile.sh reinstall
```

该命令复用现有 workspace、M7 状态、审批端口和 TCAD command adapter，并由现有安装器在停服务前
离线构建、验证，失败时事务回滚。不得用默认 `/opt/scidiscovery` 创建第二套入口。

## 5. 已知非阻断

`test_clean_installed_pure_mcp_plugin_completes_a_hardened_run` 因当前可选 Hardened 后端把该测试
Operation 判为 runtime unavailable 而失败；E4 使用已冻结的 Local Worker profile，且本阶段没有
修改 Hardened 代码。该问题不扩入本轮。

安装前独立审查见 `reviews/R5_PRE_E2E_E4_PREINSTALL_INDEPENDENT_REVIEW.zh-CN.md`，结论 `PASS`、
阻断项 0，只允许执行上述 M7 事务化重装。未经真实重装后的服务、目录、工具及 TCAD capability
核验，不宣称 E4 完成。

## 6. 真实重装后的安装态证据

用户已于 2026-09-05 通过上述唯一事务化入口完成重装。Root 从真实 systemd、Unix socket 和
`/opt/scidiscovery-m7/site` 核对得到：

- `scidiscovery-control.service` 与 `scidiscovery-approval-ui.service` 均为 `active`，本次启动时间均为
  `2026-09-05 06:41:58 CST`；
- 控制服务继续使用 M7 工作区、`/var/lib/scidiscovery-m7`、`/run/scidiscovery/control.sock`、
  `/etc/scidiscovery-m7`、Local Worker 及 `http://127.0.0.1:8765`，没有切换到默认部署根；
- 审批主页真实 HTTP 状态为 `200`，8765 只有一个监听者；安装后两项服务均无 warning 级日志；
- 唯一活动 SciDiscovery 服务仍只有上述控制服务和审批 UI。磁盘上虽保留旧
  `/opt/scidiscovery/site`，但没有对应活动服务或监听入口；
- 安装态插件入口精确为
  `builtin,curve_figure_evidence,curve_score,general_science,ingaas_fig4,tcad_artifact`；
- Root socket 的编译目录为 `public=28`、`support=21`、`internal=0`、`all=49`；五个论文图操作均位于
  预期视图，三项 Agent 均为单主输出，两项 Transform 分别承担五项物化输出和两项打包输出；
- `tcad.study.execute` 为 `effect`，控制进程运行绑定状态为 `available`，且仍真实公开
  `sentaurus-sprocess-r2020.09` 与 `sentaurus-sdevice-r2020.09` 两项 capability；
- 运行时摘要的编译目录摘要为
  `f4bf465a8bc896c66bb9c5349d67e7174ad6e2a43066c2b80dea885f815039c8`。

安装重启后 Root MCP 已能读取新目录，证明当前 Codex 工具配置不是旧的 44 项投影。当前会话的
`instance_current` 返回 `unbound`；按照唯一实例绑定规则，必须由用户在本地管理页重新选择原实例，
不得由调度器创建默认实例。完成绑定后，才能从真实 Agent Run 核验图像工具投影并进入 E5。

安装后独立收口见
`reviews/R5_PRE_E2E_E4_POSTINSTALL_INDEPENDENT_REVIEW.zh-CN.md`，结论 `PASS`、阻断项 0；E4 完成。
`instance_current=unbound` 不否定安装阶段，只是启动 E5 前必须完成的用户会话绑定。
