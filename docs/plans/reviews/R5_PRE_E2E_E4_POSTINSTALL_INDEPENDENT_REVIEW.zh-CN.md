# R5 E4 真实安装后独立收口审查

日期：2026-09-05

结论：**PASS**  
阻断项：**0**  
E4 是否完成：**是**  
是否可直接进入 E5：**尚不可；当前会话必须先由用户在本地管理页绑定既有研究实例。**

## 1. 审查边界

本审查者未参与 E4 修改。本次只审查
`R5_PRE_E2E_E4_DEPLOYMENT_READINESS.zh-CN.md` 第 6 节及真实当前安装态，验证：

- systemd、8765 和 Root socket 是否只有一个活动入口；
- `/opt/scidiscovery-m7/site` 的真实插件入口与 Operation 目录；
- 五项图 Operation 的 scope、executor 和输出边界；
- `tcad.study.execute` 及两项真实执行 capability；
- 旧 `/opt/scidiscovery` 是否构成第二活动入口；
- `instance_current=unbound` 对 E4/E5 边界的影响。

没有修改生产代码，没有执行外部写入，没有扩展到 E5 Agent、审批页改造或 Hardened 后端。

## 2. 独立只读事实

### 2.1 活动服务与监听入口唯一

`scidiscovery-control.service` 与 `scidiscovery-approval-ui.service` 均为 `active`、`enabled`，本次启动
时间均为 `2026-09-05 06:41:58 CST`。两项服务均以用户 `da` 运行，且
`PYTHONPATH=/opt/scidiscovery-m7/site`。

控制服务的真实参数继续绑定：

- M7 工作区 `workspace/ingaas_inalas_photodetector`；
- `/var/lib/scidiscovery-m7`；
- `/etc/scidiscovery-m7/approval-receipt.key`；
- `/etc/scidiscovery-m7/tcad-plugin.json`；
- Local Worker；
- `/run/scidiscovery/control.sock`；
- `http://127.0.0.1:8765`。

审批首页返回 HTTP 200。系统只有一个 `127.0.0.1:8765` 监听和一个
`/run/scidiscovery/control.sock` 监听；systemd 只列出上述两项 SciDiscovery 活动服务，没有第二套
TCAD 或旧 SciDiscovery 活动服务。本次启动以来两项服务无 warning 级日志。

### 2.2 真实安装态目录正确

从 `/opt/scidiscovery-m7/site` 而非仓库源码加载的发行入口精确为：

```text
builtin, curve_figure_evidence, curve_score, general_science, ingaas_fig4, tcad_artifact
```

通过当前 Root Unix socket 读取的 `operation_catalog(scope=all)` 共 49 项，其中 public 28、support
21、internal 0。以下五项均存在且边界正确：

| Operation | 视图 | 执行器 | 输出边界 |
|---|---|---|---|
| `science.figure.request.prepare.v1` | public | agent | 单一类型化请求 |
| `science.figure.evidence.materialize.v1` | support | transform | 五个声明输出端口 |
| `science.evidence.extract.figure.v2` | public | agent | 单一 ScientificIntake |
| `science.figure.evidence.audit.v1` | public | agent | 单一 EvidenceAudit |
| `scidiscovery.curve-bundle.figure-evidence.v2` | support | transform | 两个声明输出端口 |

这证明新图能力来自同一安装态编译目录，没有建立第二注册表、第二调用入口或 Agent collection
协议。运行时摘要的 catalog digest 与证据第 6 节一致：
`f4bf465a8bc896c66bb9c5349d67e7174ad6e2a43066c2b80dea885f815039c8`。

### 2.3 TCAD 执行能力没有退化

Root 目录中的 `tcad.study.execute` 仍为 public effect，运行绑定为 `available`，required executor
仍为 `tcad_artifact:tcad`。通过真实 Root socket 调用
`execution_capabilities(operation_id="tcad.study.execute")` 返回且仅返回：

- `sentaurus-sdevice-r2020.09`，solver kind 为 `sdevice`；
- `sentaurus-sprocess-r2020.09`，solver kind 为 `sprocess`。

两项都明确带有 `Sentaurus R-2020.09` 发布标签。当前 TCAD plugin 配置继续使用 command transport，
并指向既有 `/etc/scidiscovery/command-adapter.json`。

### 2.4 旧安装目录不是第二活动入口

磁盘上的 `/opt/scidiscovery` 仍存在，但没有 systemd 服务、TCP 监听或 Unix socket 指向它。当前两项
服务的唯一 `PYTHONPATH` 都是 `/opt/scidiscovery-m7/site`。保留旧只读目录本身不构成运行权威，
也不需要为了 E4 删除历史目录。

## 3. `instance_current=unbound` 的阶段判断

当前 Root socket 的 `instance_current` 确实返回 `unbound`，并提供本地实例管理入口。这不否定 E4：
安装、服务、插件目录、Operation 编译和 effect capability 都已在未绑定状态下得到验证，且实例绑定
本来就是会话级控制事实，不应由安装器替用户创建或选择。

它是进入 E5 前的唯一用户动作阻断：用户必须在 Root 返回的本地管理页选择要继续的既有研究实例。
调度器不得回退到共享默认实例，也不得仅凭聊天内容代写绑定。绑定完成后才可发起真实 Agent Run。

## 4. 奥卡姆原则与33项约束判断

E4 只把已通过 E1—E3 的论文图插件加入既有 profile，并复用原事务安装、systemd、Root socket、
Operation 目录与 TCAD adapter。没有新增部署状态机、服务、监听、注册表或历史兼容路由，复杂度没有
超出本阶段需要。

真实结果符合相关约束：

- `AUTH-003`：能力继续由唯一编译 Operation 目录授权；
- `PLG-001/002`：图能力来自可选插件，核心没有 Fig.4 分支，插件通过统一入口组合；
- `MIG-002`：真实安装和服务切换已经发生，未以源码探针替代安装态事实；
- `EFF-001/002`：TCAD 仍通过既有独立 effect/adapter 边界暴露；
- `HIL-001`：8765 保持唯一 loopback 人工入口；
- `SEC-002`：仍诚实使用可信本地软隔离，没有把 Local backend 宣称为强沙箱。

## 5. 收口决定

E4 的安装前、事务化重装和安装后真实入口验证已经闭合，阻断项为零，故 E4 **PASS**。

本结论不代表 E5 已开始或通过。下一步只应把 Root 返回的本地实例管理 URL交给用户，由用户选择既有
实例；确认 `instance_current` 已绑定后，才可按计划逐个启动真实请求、Intake 与独立审查 Agent。
