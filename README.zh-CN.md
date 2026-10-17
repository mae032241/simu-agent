# SciDiscovery 科学发现 Agent

简体中文 | [English](README.md)

SciDiscovery 是面向 Codex 的科研框架。它围绕明确目标与冻结输入运行原生 H/W/A/E
线程，提供有限共享预算、科学结果封存及原调用恢复。科学 Worker 负责模型选择与结论；
确定性控制负责身份、输入绑定、资格校验、预算和执行权限。

当前是工程原型。命令或求解器运行成功，只支持其精确输入、实验和验证合同实际建立的结论。

## 可以做什么

| 入口 | 用途 |
| --- | --- |
| `scid-research` | 准备实例，运行、查看、暂停和继续研究，收束并导出结果。 |
| `scid-research serve-ui` | 显式启动一个实例的页面，提供实例控制和封存结果分页。 |
| `scid-research archive-*` / `checkpoint-*` | 导出和核验原件、恢复指定材料，或执行限定的同宿主冷迁移。 |
| `scid-experiment` | 使用受管本地实验或声明的领域执行接口。 |

可选 TCAD adapter 通过有界传输提供 detached solver 执行；曲线插件提供确定性评分和论文图
证据能力。安装插件只注册其声明能力，不提供 solver、许可证或科学资格。插件声明也可按
[Plugin API](docs/PLUGIN_RUNTIME_API.md)作为库使用。

## 安装与开始使用

提供 Python 3.10+ 和 [pyproject.toml](pyproject.toml) 声明的运行、构建依赖，离线安装应用：

```sh
SCID_PYTHON=/absolute/python deploy/install.sh --dry-run
sudo SCID_PYTHON=/absolute/python deploy/install.sh install
scid-research --help
```

安装发布 `scid-research`、`scid-experiment`，要求使用新安装前缀。通过 `SCID_PLUGINS`
明确选择可选插件；依赖、路径设置与卸载见[安装指南](docs/INSTALL.zh-CN.md)。

开始研究时，为新实例提供目标文件、公开输入、明确的原生 launcher，以及有限的 token、
时间和步数上限，再运行和查看该精确实例。[CLI 指南](docs/ROOTLESS_CLI.zh-CN.md)
包含命令、策略示例、结果读取与恢复规则。执行另需冻结配置及授权；科研预算、独立审查和
用户陈述均不授予执行权限。

## 文档与开发

[文档入口](docs/README.md) · [当前架构](docs/ARCHITECTURE.zh-CN.md) ·
[发布范围](docs/RELEASE.zh-CN.md) · [安全边界](SECURITY.md) · [贡献指南](CONTRIBUTING.md)

现行控制器位于 `src/scidiscovery/research_loop/`，领域算法、合同与 adapter 位于 `plugins/`。
按[测试分组](tests/README.md)串行、受监督运行精确目标；功能测试不构建或安装包。
`scripts/build_git_release.py` 从显式选择的源码、当前参考文档、工具和功能 fixture
生成源码包及逐文件 SHA256 manifest。

开发计划、审计、交接与试验输出作为本地工作资料保存，不进入长期源码跟踪或源码发布。
当前用法和行为由代码及当前参考文档定义。

## 支持边界

当前信任 Worker 与宿主同权限进程，控制层属于软边界。浏览器、真实原生线程续接、TCAD
solver 和实际掉电恢复需要精确候选及环境的证据；源码测试不能建立这些资格。
跨宿主完整灾备不在支持范围。冻结实例保留原实现身份；未知外部提交须先按原调用身份核对。

受支持的应用入口为上述两个命令。旧 `scid`、Root/MCP 应用、平台角色生成及 legacy systemd
应用安装不可用。分发源码包前，按[分发声明](NOTICE.md)核对软件许可和随附参考资料限制。
