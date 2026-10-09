# 原生模型试验：复用已验证的启动路径

本文是测试执行者的启动指南。启动实现由
[run_covshift_pilot.py](../scripts/run_covshift_pilot.py) 的 `prepare`、
`outer_command`、`preflight` 和 `run` 拥有；资源监督复用
[run_tests.py](../scripts/run_tests.py)。新题目复用这些机制，更换公开材料和预算。

## 必须一起复用的配置

| 项目 | 做法 |
|---|---|
| 原生状态 | 每场使用试验目录内独立、可写的 `CODEX_HOME`，目录 `0700`。只复制所需 provider transport 和认证配置；认证文件 `0600`，provider 配置放在该私有目录内，含凭证时另外确认文件为 `0600`。个人会话、指令及 MCP 配置不复制。 |
| 原生命令 IPC | 使用 `outer_command` 的独立 namespace 和 `/tmp`。宿主的 `/tmp/codex-daemon-<uid>` 可能被当前沙箱屏蔽；只改变 `CODEX_HOME` 或 `TMPDIR` 不能替代 `/tmp` 隔离。共享 daemon 目录保持原样。 |
| 运行时挂载 | 同时提供精确 native 二进制及其 `codex-code-mode-host`、Python 运行时、公开任务材料、受控输出目录和所需控制通道。复用现有挂载清单生成逻辑。 |
| 角色配置 | 明确冻结 Root、Worker、helper 的模型和推理等级；helper 继承已冻结 Worker 配置。按实际运行记录核验。 |
| 配置加载 | 验证有效权限、MCP 和角色配置。宿主初始化成功不代表项目配置已加载，也不代表 Worker 的原生命令能执行。 |
| 用量与清理 | 复用串行锁、资源监督、逐线程用量和拥有进程的清理。记录缺失用量及异步超额；缓存输入是输入的子集。 |

## 最短启动顺序

1. 固定代码提交、公开材料、私有评分材料边界和整场预算，准备独立安装。
2. 沿实际试验启动路径做一次无模型检查：初始化、有效权限、原生命令读取公开文件和写入允许目录。已有隔离 canary 可同时验证私密材料边界。
3. 检查通过后才提交模型轮次。单独的 `initialize`/`thread/start` 成功不足以证明命令通路可用。
4. 使用当前宿主会话的管理链接绑定实例。用户明确授权测试执行者代办时，执行者可通过管理页完成；不据此改变框架内 Root 的授权边界。
5. 记录实际封存结果、helper 参与、关键原件核验和用量。模型聊天结束及进程返回零都不是科学验收通过。

新入口先对照上表检查差异，优先调用已有实现。轻量 `Host` 只是连接与生命周期组件，不能单独替代完整隔离启动器。

## 启动失败的处理

| 证据 | 首先核对 |
|---|---|
| `failed to initialize sqlite state runtime under .../.codex` | 是否误用了只读个人 `CODEX_HOME`。 |
| `app-server socket directory must be a user-owned directory with mode 0700` | 实际命令 namespace 中的 daemon 目录及 `/tmp` 挂载；不要仅检查自建临时目录。 |
| app-server 可用、Worker shell 不可用 | 新入口是否漏掉 `outer_command`、精确运行时挂载或有效权限配置。 |

保留失败证据，先修启动配置并验证无模型命令通路，再考虑新尝试。已提交模型的尝试保留独立标记；结果未知时核对原状态，不重放。重试计入已授权总预算，成本不因环境失败而清零。

## 经验来源与资格范围

宿主工作区的 `.trial/s26/`、`.trial/s27/` 保存了上述隔离入口的实际模型运行证据。
2026-10-09 的小型 H/W/A 薄入口仅复用 `Host`，先漏掉独立 `CODEX_HOME`，补上后又因未隔离 `/tmp` 而在 H 的首个原生命令前失败。该记录保存在宿主 `.trial/small_hwa_20261009/`。

这些历史记录说明启动机制的差异；本指南不把历史运行或启动预检当作新版本科研质量、整条 H/W/A 或读取优化的资格证明。
