# 无 Root 的科研 CLI

`scid-research` 直接启动新的 H/W/A/证据原生线程，控制程序执行科学角色选择的路由。
它不调用 LoopX，不启动 Root 模型，不需要先通过 MCP 管理页创建或绑定实例。
本入口使用独立的新实例目录；尚未迁移旧 daemon 实例、UI 或 TCAD 审批/资格接口。

## 创建与运行

安装当前包后：

```sh
scid-research prepare \
  --root /absolute/path/new-instance \
  --objective /absolute/path/objective.md \
  --public-root /absolute/path/public-inputs \
  --native-launcher-json '["codex"]' \
  --max-tokens 2000000 --max-seconds 1200 --max-steps 8

scid-research run --root /absolute/path/new-instance
```

源码树可将 `scid-research` 替换为 `PYTHONPATH=src python -m scidiscovery.research_loop.cli`。
示例预算仅示范参数，并不保证在此额度内完成科研循环。默认角色模型是 `gpt-6.1-sol`，
思考等级 `high`，服务档位 `default`；prepare 支持显式指定。没有隐藏的 Root 预算。

原生 launcher 使用 argv 数组，不经过 shell 拼接。也可指定经过验收的外部 launcher，
例如 `["python", "/absolute/launcher.py", "--config", "/absolute/config.json"]`。
控制器沿用薄原型的 `exec --json --output-last-message ...` 和 `THIN_HWA_*` 环境接口。
外部 launcher 拥有自己的权限、MCP 功能服务与数据隔离策略；新增 E 角色须由该 launcher 明确支持。

直接 `codex` 使用本地软隔离，关闭项目 AGENTS 自动加载和旧 `scidiscovery` MCP 调度服务。
其他原生配置仍可能来自本机配置。机密数据、隐藏评分资料或生产副作用不得仅依赖这个默认方式隔离；
原有基准的已验证 wrapper 可以复用，但需为新的 schema 文件和 E 角色重新验收。

## 状态与暂停

```sh
scid-research status --root /absolute/path/new-instance
scid-research pause --root /absolute/path/new-instance
scid-research continue --root /absolute/path/new-instance
```

一个实例只允许一个运行控制进程；再次 run/continue 明确报占用，不另开模型。
status 只读、不消耗模型。`seal_present_unverified` 只表示存在封存记录；run 恢复时验证原件。
pause 在当前角色完成后阻止下一节点。continue 清除这道暂停并从已封存节点恢复。
实例的墙钟预算从第一次运行开始，暂停期间目前仍计时；继续不会续额度。

原生启动留有意图但没有完整终态/封存时，不自动重跑。它可能已经执行实验或产生外部效果；
当前版本报告 `native_outcome_unsealed`，没有宣称具备原生会话自动恢复。
计量未观测到也不能当作零成本。token 上限依赖原生事件，可能滞后，不是精确计费承诺。

## 科学交接

- H 选择 `experiment / analyze / extract / wait`。
- W 完成后固定交 A。
- A 选择 `continue_w / revise_h / extract / wait / finish`。
- E 是按问题启动的证据角色，返回请求它的 H 或 A。
- `next_action` 是单个枚举；理由单独写 `route_reason`，不把解释拼进动作字符串。

每个角色读 `science-task.json` 和短的输出 schema；模型只写科学 payload。
控制程序保留原生输出、构建封装、登记直接来源及本节点 artifacts，模型不用发布附件或填写绑定。
下一角色收到父科学 payload，不收到父 envelope 或递归展开的祖先材料。

`finish` 表示 A 提出了结题建议，响应保留 `goal_completion: not_asserted`。
这不替代科学评分、独立资格或执行授权。功能插件/UI 的统一接入和旧 Root 退役状态见
[迁移计划](plans/ROOTLESS_THIN_HANDOFF_PLAN.zh-CN.md)。
