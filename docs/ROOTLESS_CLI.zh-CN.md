# 无 Root 的科研 CLI

`scid-research` 直接启动新的 H/W/A/证据原生线程；控制程序执行科学角色选择的路由。
不依赖 LoopX，不启动 Root 模型，不需要 MCP 管理页绑定。旧 daemon、UI、TCAD 权限接口尚未迁移。

## 创建与运行

```sh
scid-research prepare \
  --root /absolute/path/new-instance \
  --objective /absolute/path/objective.md \
  --public-root /absolute/path/public-inputs \
  --native-launcher-json '["codex"]' \
  --max-tokens 8000000 --max-seconds 1800 --max-steps 3
scid-research run --root /absolute/path/new-instance
```

可重复传入 `--user-update /path/to/statement.md`，将用户补充和原始目标一起冻结。
本版尚不支持实例运行中追加补充。默认 `gpt-6.1-sol`、`high`、`default` 服务档位。
预算示例不保证完成一轮；三节点允许典型 H→W→A，但科学角色也可以选择证据提取或等待。
源码入口为 `PYTHONPATH=src python -m scidiscovery.research_loop.cli`。

## 文件与职责

```text
project/
  global/objective.md
  global/updates/001.md
  nodes/001/
    science-task.json             # 控制层生成的短导航
    inputs/global/               # 本节点绑定的全局文件，只读
    inputs/parents/<node>/
      conclusion.json            # 直接前驱的科学结论
      artifacts/                 # 直接前驱的成果
    work/                        # 本节点临时材料，不交接
    artifacts/                   # 必要交付成果
    experiments/<name>/
      work/                      # 子实验临时文件，不交接
      artifacts/                 # 子实验必要成果
      conclusion.md              # 可选的简短科学观察
    conclusion.json              # 控制层保存的最终科学回答
native-evidence/<node>/           # 私有原生轨迹、schema、哈希与封装
```

角色使用原生文件工具。模型只做科学工作、选择必要成果，最终直接回答简短科学 JSON。
`final_response` 给出字段名；无需读 schema、另存最终回答、制作索引、计算哈希或打包。
子实验不是额外 Agent，结论可以是 Markdown 或 JSON；无需逐次填写机械表单。

控制层自动采集节点 `artifacts/` 及子实验成果和可选结论，规范为直接前驱成果目录。
子实验模型不需要再复制到顶层。`work/`、输入和祖先材料不进入成果采集。
默认交接包括全局文件、直接前驱结论、关键成果直达入口和成果目录，启动材料不逐项展开文件。
角色在科学结论里自然使用 `[比较结果](artifacts/comparison.csv)` 这类相对 Markdown 链接；
控制层验证它指向本节点已采集的成果，并解析为后继节点的实际路径。无需另填附件清单。
普通文字路径不自动推断；外部链接与前驱材料引用保持科学原文，不冒充本节点新成果。
哈希、封装、路径校验、来源记录、输出 schema 和封存回执只由控制层维护。
历史中间材料保留在原节点；跨节点按需读取中间材料的独立接口尚未实现，当前隔离启动器不会自动暴露它们。

成果默认单文件上限 32MiB、单节点合计 64MiB；中间文件不占这份交付额度。
额度用于控制层采集和直接交接，并非实验存储总量。声明目录之外的文件不自动获得证据资格。
若模型正常退出且科学输出已经固定，而控制层封存失败，修复交付后 `run` 可只重试封存。
不修改原科学结论，不重复执行模型；结果未知、模型失败和用量缺失仍拒绝自动重放。

## 路由与暂停

H 选择 `experiment / analyze / extract / wait`；W 固定交 A；
A 选择 `continue_w / revise_h / extract / wait / finish`；E 返回请求它的 H 或 A。
`next_action` 是枚举，理由单独写 `route_reason`。`finish` 仍是科学结题建议，非控制层资格认证。

```sh
scid-research status --root /absolute/path/new-instance
scid-research pause --root /absolute/path/new-instance
scid-research continue --root /absolute/path/new-instance
```

同实例只有一个运行写者；status 不调用模型。pause 允许当前角色完成并封存，在下一节点前停止。
墙钟从首次运行计时，暂停目前仍计时；continue 不续额度。原生用量可能滞后，token 上限不是精确账单保证。

## 启动边界

launcher 使用 argv，不拼接 shell。可复用经过验证的外部隔离启动器，但须适配上述目录和私有 schema。
直接 `codex` 是软隔离：关闭项目 AGENTS 自动加载、旧 scidiscovery MCP、native 子 Agent 和 fast。
其他配置仍可能继承本机环境；涉及隐藏基准资料应使用已经验证的隔离启动器。
本入口尚未完成统一功能插件、CLI 管理 UI/端口、旧入口退役和原生未知会话恢复。
