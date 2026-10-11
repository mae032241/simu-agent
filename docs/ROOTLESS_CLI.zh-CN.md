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
N1a 已增加本地持久 runner：前台控制器退出后，已接受的原生节点继续运行并记录日志、用量和终态。
再次 `run` 按任务哈希、系统启动标识及进程启动身份核对同一 runner，并等待原完成通知，再封存和路由。
`status` 区分 `prepared / running / native_not_submitted / native_outcome_unsealed / seal_present_unverified / unknown`；
封存存在仍需 `run` 验证。原生成功但封存失败只重试封存；执行身份丢失、失败或缺量仍不自动重放。
实际模型提交前再查预算；已确证未提交时记录 `native_not_submitted` 和零用量。
控制层保留该节点及原意图，尚不支持对其再次发起首次模型提交；预算修订或重试不自动删除这些记录。
暂停只阻止新节点，恢复时也允许原已接受节点完成和封存。
本地完成通知限定为已启动 runner；科学角色的 `wait` 仍表示停止等待，不提供自动事件续接。

新建实例的 `--max-seconds` 是推进启用时长上限：控制推进与原生执行重叠只计一次。
暂停请求生效前已接受的工作和控制器断连后的原执行继续计时；无活动且进入暂停时停止消耗推进额度。
身份或终态无法核实时保守计时，后续核实从当前时刻停表，不回填旧终态时间返还消费。
`status.budget` 分别报告 `advance_seconds / paused_seconds / elapsed_seconds`，并显示有效上限、
`consumed_seconds / seconds_remaining` 和计时口径。`status` 只读，不追加计时事件；时钟倒退时拒绝推进和修订。
新计时事实绑定系统启动标识与 `CLOCK_BOOTTIME`，同次启动的开放区间按该单调时钟计量；
UTC 相对单调时钟回退超过采样容差（20 毫秒）时拒绝读取、推进和修订。跨系统重启无法核对原区间时同样拒绝，须人工修复，不自动退款。
旧实例没有 `time_budget_basis` 标记时继续按首次运行起算的总经过时间执行原墙钟上限，暂停仍计时。
旧计时账本之前的推进/暂停分布记为 `unclassified_seconds`，不推测历史。新实例未另设总经过时间截止。
`continue` 不增加上限，也不清零已消费时间或 token。

外部操作者可明确修订 token 或秒数上限；`max_steps`、科学目标、模型、启动器和已有节点保持冻结：

```sh
scid-research budget-amend --root /absolute/path/instance \
  --max-tokens 8000000 --max-seconds 2400 \
  --authorization-note '操作者明确批准本次上限修订及其原因'
```

修订须持有实例写锁，并确认没有活动或未知执行。仅变更声明上限，不重置消费、不清除原意图、不自动启动模型。
时间与修订共用 `control-ledger/` 追加账本，记录序号、前记录哈希、冻结 settings 哈希、前后上限、时间和授权说明。
授权说明是审计声明，不是身份认证。控制账本不加入科学输入或新增原生可写路径；
使用经验证的隔离启动器限制科学角色修改宿主控制记录。直接 `codex` 的软隔离不能证明人类身份或这种权限隔离。
原生用量只来自已收到的 `turn.completed`；运行中可能缺量或滞后，token 上限不是精确账单保证。
runner 收养主进程退出后的普通子进程，并按真实归属和启动身份清理；清理无法确认时停止封存。
runner 意外退出时，本地 watchdog 仅清理能精确核对的标准进程组成员；无法核对时保留 `cleanup_unknown`。
启动器应自行保证脱离进程组的后代清理；现有隔离启动器的原权限和配置协议保持原样。

## 启动边界

launcher 使用 argv，不拼接 shell。可复用经过验证的外部隔离启动器，但须适配上述目录和私有 schema。
直接 `codex` 是软隔离：关闭项目 AGENTS 自动加载、旧 scidiscovery MCP、native 子 Agent 和 fast。
其他配置仍可能继承本机环境；涉及隐藏基准资料应使用已经验证的隔离启动器。
本入口尚未完成统一功能插件、CLI 管理 UI/端口、旧入口退役。未知原生结果仍须人工核实，不能自动重放。
