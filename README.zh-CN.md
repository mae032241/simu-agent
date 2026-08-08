# SciDiscovery 科学发现 Agent

简体中文 | [English](README.md)

SciDiscovery 是面向 Codex 和 Claude Code 的科学发现编排服务。它将科学推理、
不可变证据、人工审批、确定性变换和外部仿真执行相互分离。仓库内的 TCAD 插件
可以管理经过独立审查的 Synopsys Sentaurus 工程，同时避免把 VM、SSH、许可证和
作业生命周期混入科学 Agent 的职责。

当前版本是工程原型。一次任务运行成功，只能支持实验与验证合同中明确声明的结论。

## 设计目标

长程科学任务不应由单个对话 Agent 同时记忆论文事实、产生假设、编写仿真代码、
管理作业并审查自己的结论。SciDiscovery 将这些职责拆开：

1. **信息解析**生成有来源、范围受限的科学基础资料。
2. **科学角色**分别负责假设、批判、证据审计、实验设计和结果诊断。
3. **领域作者与审查者**生成并独立审查可执行工程。
4. **确定性代码**负责 Schema 校验、补丁应用、工程 diff、打包和结果注册。
5. **控制面**负责上下文隔离、不可变记录、任务状态以及精确的人工审批。
6. **执行适配器**只执行已经授权的外部副作用。

主 Agent 只负责调度。科学内容来自具有明确边界的角色 Worker；身份和生命周期状态
始终由控制面管理。

## 工程组成

| 目录 | 职责 |
| --- | --- |
| `src/scidiscovery/` | 通用 Artifact、调度、审批、MCP、Worker 协议、Schema、平台生成器和执行桥 |
| `roles/` | 通用科学角色定义 |
| `plugins/tcad_artifact/` | TCAD 工程 Schema、作者/审查角色、确定性打包器、执行策略、SSH 通道和 VM Runner |
| `skills/sentaurus-tcad-code/` | 只涉及 SProcess/SDevice 代码的规范与静态校验 |
| `plugins/ingaas_fig4/` | 可选领域示例；通用控制面不依赖它 |
| `deploy/` | Linux/WSL systemd 安装和远端 Runner 部署 |
| `tests/` | 单元、故障注入、并发、平台、MCP 和闭环测试 |

`.codex`、`.claude`、`.mcp.json`、socket、数据库、审批记录、研究数据、Solver
输出和凭据都是运行时信息，不属于源码。

## 总体架构

```text
用户
  |  本地审批网页
  v
Codex / Claude 主调度 Agent
  |  Root MCP（只使用语义名称）
  v
SciDiscovery 控制面
  |-- 不可变 Artifact 与来源关系
  |-- ResearchInstance 绑定
  |-- 任务租约与受限 Worker 上下文
  |-- 审批与执行状态
  |
  +--> Worker MCP --> 科学角色 Agent --> 校验后的 JSON 结果
  |
  +--> 确定性变换 --> 审查包 / diff / 指标
  |
  +--> 执行桥 --> TCAD 适配器 --> 本地或远端仿真器
                                  |
                                  +--> 终态记录与输出文件
```

依赖关系只表示输入是否就绪，不构成固定流程图。主调度器应依据当前科学矛盾选择
最短且可辩护的角色拓扑。

详细说明见[架构文档](docs/ARCHITECTURE.zh-CN.md)。

## 快速安装

支持带 systemd 的 Linux 和 WSL2，要求 Python 3.10 及以上。

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip poppler-utils bubblewrap curl openssh-client

git clone <你的仓库地址> scidiscovery-agent
cd scidiscovery-agent

# 预检；全新 Python 环境也可以直接执行正式安装。
SCID_PYTHON="$(command -v python3)" deploy/install.sh --dry-run

# 默认生成 Codex 配置。
sudo SCID_PYTHON="$(command -v python3)" \
  SCID_SERVICE_USER="$USER" \
  SCID_PLATFORM=codex \
  deploy/install.sh install
```

安装器会创建三个 SciDiscovery 服务，并在
<http://127.0.0.1:8765> 启动仅监听本机的审批页面。未配置 TCAD command
adapter 时，只会安装 `/bin/true` 部署冒烟配置，不代表真实 Solver 可用。

Claude Code 使用 `SCID_PLATFORM=claude`；同时生成两个平台配置使用 `both`。
安装后需要完全重启所选客户端。

完整教程：

- [中文安装教程](docs/INSTALL.zh-CN.md)
- [Installation](docs/INSTALL.md)

## TCAD 边界

本工程不分发 Sentaurus、许可证、专有说明书或虚拟机。TCAD 插件接收已经审查的
`DeckProject`，生成受限作业包，并调用白名单工具配置。远端 VM 场景中，SSH 仅
执行短时的上传、提交、状态、取消和收集操作；VM Runner 负责后台进程和持久终态
标记。

机器相关路径应写入 `plugins/tcad_artifact/config/` 示例文件的本地副本，并安装到
`/etc/scidiscovery`。私钥、许可证、实际 IP 和服务密钥不得提交到 Git。

## 开发测试

```bash
python3 -m pip install -e '.[test]'
python3 -m pip install -e plugins/tcad_artifact
python3 -m pip install -e plugins/ingaas_fig4  # 可选示例
pytest -q
```

发布前必须运行 hermetic 测试。真实平台和真实 Solver 测试依赖外部配置，不能由
单元测试通过来替代。

## 生成干净 Git 仓库

发布脚本只复制源码边界，清理缓存和构建产物，扫描机器信息，生成 SHA-256 清单，
并可初始化新 Git 仓库：

```bash
python3 scripts/build_git_release.py \
  --output dist/scidiscovery-agent \
  --init-git
```

添加远端前应人工检查输出。脚本会排除研究数据库、仿真结果、论文 PDF、VM 数据、
生成的平台配置和凭据。

## 当前限制

- 审批网页和生产 TCAD 能力仍需在目标设备上做部署验证。
- 框架可以验证证据和实现合同，但不能令缺乏依据的物理模型自动变得正确。
- Claude Code 配置生成已实现并通过 hermetic 测试，但每个目标 Claude 版本仍需
  单独做冒烟验证。
- 当前源码未指定软件许可证；公开发布前必须由项目所有者选择并加入许可证。
