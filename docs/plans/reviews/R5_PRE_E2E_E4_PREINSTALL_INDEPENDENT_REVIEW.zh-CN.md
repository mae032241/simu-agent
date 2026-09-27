# R5 E4 安装前独立审查

日期：2026-09-05

结论：**PASS**  
阻断项：**0**  
是否允许用户执行证据文件给出的 M7 事务化重装命令：**允许**  
阶段含义：**仅放行真实重装；不代表 E4 已完成，也不放行 E5。**

## 1. 审查边界

本审查者未参与 E4 修改。审查范围严格限定为：

- `R5_PRE_E2E_E4_DEPLOYMENT_READINESS.zh-CN.md`；
- `deploy/apply_ingaas_fig4_profile.sh` 的插件组合变化；
- 对应部署测试和中英文安装说明；
- clean release、离线 installed-site 探针；
- 当前 systemd、安装目录和监听入口的只读事实。

没有修改生产或测试代码，没有执行 `sudo`，也没有扩展到 Hardened、UI 或部署框架重写。

## 2. 审查结论

### 2.1 插件组合正确且保持单一注册入口

Fig.4 profile 现在选择：

```text
tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4
```

该组合满足当前依赖方向：`curve_figure_evidence` 依赖 `curve_score`，`tcad_artifact` 依赖
`curve_score`，`ingaas_fig4` 依赖 `tcad_artifact`。它只通过已有 `SCID_PLUGINS` 入口传入通用安装器，
没有建立第二套注册表、第二套安装器或 Fig.4 专用控制服务。

隔离 installed-site 的实际入口点为：

```text
builtin, curve_figure_evidence, curve_score, general_science, ingaas_fig4, tcad_artifact
```

编译目录共 49 个 Operation。三个图 Agent、两个图 Transform 均存在且 scope/executor 正确，三个
Agent 没有本地 Worker 工具缺失；`tcad.study.execute` 仍是 public effect。

### 2.2 给用户的命令保持现有 M7 部署身份

证据文件给出的命令显式保持：

- 安装目录：`/opt/scidiscovery-m7`；
- 控制状态：`/var/lib/scidiscovery-m7`；
- 配置目录：`/etc/scidiscovery-m7`；
- 备份目录：`/var/backups/scidiscovery-m7`；
- 审批端口：`8765`；
- 外部 TCAD command adapter：`/etc/scidiscovery/command-adapter.json`。

profile 默认 workspace 与当前 systemd 使用的
`workspace/ingaas_inalas_photodetector` 完全相同。当前 shell 的 `python3` 也解析到现服务使用的
`/home/da/miniconda3/bin/python3`；worker backend 默认仍为已冻结的 `local`。通用
`reinstall.sh` 会把这些已解析值完整传给同一个 `install.sh`，复用既有事务、备份、失败回滚、状态
目录、Codex 配置和 TCAD runtime 配置逻辑。

因此该命令不会落入默认 `/opt/scidiscovery`、`/var/lib/scidiscovery` 或 `/etc/scidiscovery` 创建第二
套活动入口。机器上虽保留旧默认目录，但 systemd 只有一组活动且启用的
`scidiscovery-control.service` 与 `scidiscovery-approval-ui.service`，当前唯一 TCP 审批监听为
`127.0.0.1:8765`，唯一 Root socket 为 `/run/scidiscovery/control.sock`。

### 2.3 当前旧服务不能用于 E5

当前两项 systemd 服务均 active，但其 `PYTHONPATH` 是 `/opt/scidiscovery-m7/site` 的 2026-09-04
18:07 安装态。独立探针确认该安装态只有 44 个 Operation，插件入口缺少
`curve_figure_evidence`，五个新的图 Operation 全部不存在；只有 `tcad.study.execute` 仍可见。

因此服务健康不等于本阶段能力已部署。继续使用当前服务会把 E5 错跑在旧代码上，必须先执行获准的
事务化重装并完成安装后核验。

### 2.4 修改保持最小，没有不必要部署改造

E4 对运行源码的新增变化仅是 profile 增加一个已经实现并审查通过的论文图插件；相应测试与安装
说明同步这一事实。`install.sh`、`reinstall.sh`、systemd 模板、状态模型、回滚协议、Run/current、
执行 adapter 和 UI 均未因 E4 再次改造。

这符合奥卡姆原则以及 `AUTH-003`、`PLG-001/002`、`MIG-002`、`RES-002` 的当前约束边界：能力仍由
同一编译 Operation 目录授权，领域能力仍由插件提供，真实安装与回滚仍走唯一事务入口。

## 3. 独立验证证据

- 给出的完整 M7 环境变量组合执行 `apply_ingaas_fig4_profile.sh --dry-run`：通过；明确输出四插件、
  local backend、现有 workspace 与 command adapter，最后声明未修改包、状态、服务或平台配置。
- 重新生成的 clean release：目录内 `sha256sum -c MANIFEST.sha256` 全部通过，共 239 个清单条目，
  加清单本身为 240 个文件；不存在先前 wheel 构建残留。
- clean installed-site：五个发行包均从隔离安装目录加载，不从仓库 `src` 或当前 `/opt` 加载；49 项
  Operation 与五项图能力探针通过。
- profile、通用重装参数透传和插件选择的三个聚焦部署测试均通过。
- 当前 systemd/安装态只读探针确认旧服务为 44 项目录，故不能冒充 E4/E5 新入口。

## 4. 非阻断边界

- 已知 Hardened 测试失败不属于本次 Local E4 修改，本审查没有据此扩展后端工作。
- 审批 UI 可读性仍是既有已知问题，本次只审查端口与唯一运行入口，不宣称 UI 已验收。
- clean release 和 installed-site 只能证明安装前包与目录，不能证明 `/opt` 切换、systemd 重启、事务
  备份或运行服务已经成功。

## 5. 放行决定

允许用户执行 E4 证据中给出的 M7 事务化重装命令。执行后必须重新核对：服务 active、安装态 49 项
Operation、五项图能力、三个 Agent 工具投影、`tcad.study.execute` 及两个求解器 capability、唯一
8765/UI 与 Root socket、没有第二套活动服务。上述安装后核验完成并经阶段收口前，**不得把 E4 标记
为完成，也不得启动 E5。**
