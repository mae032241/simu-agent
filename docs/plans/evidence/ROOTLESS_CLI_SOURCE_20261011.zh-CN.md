# CLI 薄 HWA 源码节点验收

基线：dev `ff95dfc`。范围：新的 `scid-research` 安装入口及 `research_loop` 包。

## 变更

控制程序直接启动 H/W/A/E 原生进程，按照封存科学选择路由；没有 Root 模型、LoopX 依赖或
MCP Agent 调度。模型只写科学 payload；绑定与原件快照由程序处理。下一角色不接收父控制
envelope 或祖先附件。单实例跨进程写锁；暂停阻止下一节点；未知原生启动不重放。

## 独立审查

独立审查者检查 CLI→原生→封存→后继路由。发现并修复：

1. 父 envelope 携带祖先引用进入模型输入：改传科学 raw payload。
2. 只核对父原件而未核对模型实际读取的副本：增加实际副本哈希校验。
3. 冻结配置在控制/启动之间被重复读取：统一同份字节校验及解析，并在启动边界复核。
4. CLI 返回遗漏科学主结果入口：返回精确 `scientific_output_path`。
5. status 未校验原件却写 sealed：改为 `seal_present_unverified`。

最终源码语义审查 PASS，无剩余阻断项。该结论不包含真实模型、外部 wrapper 或旧系统迁移资格。

## 检查

- `python -m pytest -q tests/research_loop`：31 passed，1.62 秒。
- 测试包含实际 CLI 与假原生子进程 H→W→A、H→A 首次无 W、H/A 请求证据及返回、
  完成节点恢复不重放、未封存结果停止、预算/配置篡改、跨进程占用、原件/副本篡改。
- wheel 本地无依赖构建成功，隔离 venv 安装后通过实际 `scid-research prepare/run` 完成三角色闭环。
  模型请求 0；native launcher 为确定性假进程。安装证据保存在仓库外
  `.trial/rootless-cli-20261011/installed-smoke.json`。
- 最终 wheel SHA256：`a6b0626caff089365594188d408bcd33f72980dabb90fb427709780289b583bd`。
- `git diff --check` 通过。

未跑旧系统全量测试：旧调度/MCP源码未纳入本节点，新增包由独立入口加载；定向检查与安装入口
覆盖本次实际改动。未调用真实模型、未部署、未迁移 UI/TCAD/旧实例。

## 保留的边界

这是替换主链的第一个可执行节点，不是旧 Root 代码全部删除。功能 MCP、实例 UI 与旧管理 API
仍需按迁移计划接入/退役。直接 Codex 为软隔离，严密的秘密材料与外部副作用隔离由经过验收的
launcher/功能插件提供。原生计量可能滞后；墙钟包含暂停；未知原生线程不自动恢复。
`finish` 是 A 的结题建议，不是目标级科学验收通过。
