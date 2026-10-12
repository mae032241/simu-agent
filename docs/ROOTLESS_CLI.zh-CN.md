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
旧科学结论通过 `history` 给出的只读分页入口在当前节点按需读取，默认只投递不超过 4096 字节的历史简报。
旧实现保留在原拥有节点。角色需要给后继复用时，在科学结论明确链接
`[旧实现](history/nodes/002/artifacts/candidate.py#reuse-implementation)`，或标记当前已绑定的输入路径。
控制层核对原件后仅转交该文件；普通历史引用不转交文件，历史结论里旧附件链接也不自动挂载。
角色不计算身份、不复制旧材料，不继承祖先整包。旧实现虚拟入口并不表示当前节点已能读取代码。

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
`consumed_seconds / seconds_remaining` 和计时口径。`status` 只读，不追加计时事件；启动时钟倒退时拒绝推进和修订。
新计时事实绑定系统启动标识与 `CLOCK_BOOTTIME`，同次启动的开放区间按该单调时钟计量；
新 active 实例的 UTC 仅是展示时间，调速或回拨不停止计量，也不返还已按启动时钟消费的额度；账本按序号及同启动的单调时间排序。
跨系统重启或启动时钟倒退导致无法核对原区间时拒绝读取、推进和修订，须人工修复，不自动退款。
旧实例没有 `time_budget_basis` 标记时继续按首次运行起算的总经过时间执行原墙钟上限，暂停仍计时。
已有 BOOTTIME 账本的旧 elapsed 实例保留原 UTC 回拨与相对时钟检查，不把新 active 口径覆盖到旧实例。
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

## 可选的全角色节点预算（N6a）

新实例可在 `prepare` 添加 `--node-budget-policy /absolute/path/node-policy.json`。
JSON 必须恰有 `H/W/A/E` 四个对象，每个对象恰有正整数 `max_observed_tokens`
和正有限数 `max_seconds`。没有节点策略默认数值；操作者必须为每个角色明确冻结两项上限。
应保留参数所依据的已观察成本或试用假设；历史最大完成事件不是下一次请求的成本保证。
已有实例没有该字段时继续原行为，不可追加该策略或修改已冻结参数。

本节点启用前，总剩余观测 token 和推进秒数须能容纳有效节点上限。W 的 token/time 上限分别
取该策略与原 search policy 的较小值。真正 Popen 前再核对共享边界与原节点锚点；runner
启动已花费的推进时间计入这个节点，不再次预留同一段时间。运行中的节点达到时间或已观测
input+output 阈值即请求终止；cached input 已包含在 input 内，不重复累加。

`native-intent.json` 的 `budget_slice` 冻结角色、任务身份、同 boot 推进起点和有效上限；W
搜索统计复用这个起点。`status.nodes` 显示原锚点、终态 `budget_report` 和 `stop_reason`。
完成事件前 token 可能完全缺失，一次事件也可能大幅越限；时间检测的轮询与终止/清理开销
同样计费。节点阈值不是精确在途账单或严格零超额保证。无 completed usage、boot 失配、未知
提交或无法确认清理时保留失败/未知原件，不重放、不退款；硬停止输出不封存为科学成功。

`pause` 只阻止下一节点，已经接受的任务继续计时并按原上限执行。运行中或未知执行不允许
`budget-amend`；合法终态后的总额修订不修改既有节点策略、锚点或终态消费报告。
仅配置节点策略不启用交付预留。节点停止不代表已交 A、已交付或科学目标完成，
也不保证剩余额度足够完成后续节点。

## 启动边界

launcher 使用 argv，不拼接 shell。可复用经过验证的外部隔离启动器，但须适配上述目录和私有 schema。
直接 `codex` 是软隔离：关闭项目 AGENTS 自动加载、旧 scidiscovery MCP、native 子 Agent 和 fast。
其他配置仍可能继承本机环境；涉及隐藏基准资料应使用已经验证的隔离启动器。
本入口尚未完成统一功能插件、CLI 管理 UI/端口、旧入口退役。未知原生结果仍须人工核实，不能自动重放。

## 可选候选事实观察

`prepare --history-observer-config /绝对路径/observer.json` 可冻结一个可信宿主只读 adapter：

```json
{"adapter":"/绝对路径/scripts/observe_covshift_candidates.py","config":{"runs":"runs","evaluation_key":"cov-public-val-score-d78f5eb-v1"}}
```

默认不配置 adapter；历史仍维护 H/W/A/E 的原摘要、限制、H 范围与科学结论页。
通用控制层不识别 cov 字段、不读取隐藏评分。adapter 仅观察原件，不执行模型、反序列化模型或提交。
候选页独立显示当前候选（无事实为 null）、同口径最高已观察代理指标、A 推荐和实际提交观察。
A 可在新协议最终科学 JSON 可选填写 `candidate_recommendation`（已列候选 ID；未知可省略或 null）。
推荐不改变提交；公开 harness 的实际提交观察也不证明外部评测接收或隐藏得分。
代理记录提供原科学结论页以回查适用条件与盲区，不能当成目标最优或模型已留存证明。

观察调用上限 5 秒、输入/输出各 256000 字节，每次至多 128 个新候选；超时、格式或容量问题封存不可用事实，保留科学结论。
配置、封存绑定和归档原件篡改仍拒绝恢复。公开小台账和提交模型原观察字节由宿主按内容去重封存（单件 32MiB、总对象 128MiB）；
容量不足明确为 `digest_only` 或 `unavailable`，不能声称原件可回读。它们不挂给科学角色。
最后一个节点也更新 `host-history/overview.json` 投影；投影删失可由封存科学原件和观察快照重建，观察快照不是可删除缓存。


## 可选的预算内收口（N6b）

新实例可在 `prepare` 同时冻结 `--node-budget-policy` 和 `--delivery-policy`。
交付策略包含 `closeout_a` 的 token/秒上限、`inflight_tokens`、`cleanup_seconds`、
`submit_seconds`、`confirm_seconds` 和 `adapter`；各值由操作者明确配置，没有生产默认预算。
预留来自原总额度：最多三个收口 A（含两次补正）、一次提交、一次确认。预留不是追加额度。
探索下一节点不能同时容纳自身上限与预留时，控制层转入收口；A 选择候选，适配器落实提交。

适配器是独立的领域接口。核心冻结其代码、启动器、输入原件及读取范围，不解释领域台账。
普通候选在 A 前由控制层冻结为 `audit_pending`；A 选择不等于审计通过。
公开审计必须完整通过才能更新实际提交；失败、跳过或未知不能冒充确认成功。
未知提交仅在本地进程已结束、原额度仍足够时查询同一操作，不重复提交。
`adapter: null` 时 `submit_seconds` 和 `confirm_seconds` 必须为零，仅作本地导出，不启动新的交付 A。

```bash
scid-research closeout --root /绝对路径/实例
scid-research closeout --root /绝对路径/实例 --export-only
```

已知硬停止留下未封存节点时，收口绑定停止前最后一个连续封存前缀；失败原件保留。
`--export-only` 不调用模型或外部适配器；它可记录本地收口事实，不是文件系统零写入命令。
原暂停、未知执行、缺失用量和完整性检查继续生效。额度不足只能导出现有状态；
新预算仍须通过原 `budget-amend` 明确授权，修订预算不会重新开放探索。
旧实例没有冻结交付策略时，只支持本地导出，不能原地追加适配器或修改原设置。

`delivery_confirmed` 仅表示 A 选定的确切工件已确认提交；`goal_completion` 仍为 `not_asserted`。
`exported_unsubmitted`、`closeout_unresolved`、`delivery_failed`、`delivery_unknown` 分别保留未提交、
未决、失败和未知，不等同科研任务完成。真实科学效果须另行验收。

### 恢复能力的区别

控制器退出后可以重接仍活着的原 Worker；Worker 成功结束但未封存时，可以补封存原结果。
本节的硬停收口转交 A，并不是续跑已停止的 Worker。原线程续接见下节 N6c，源码与零模型安装已验收；
实际 Codex 同线程恢复仍未验证。任意本地 shell 仍是软隔离；
框架管理的外部执行应按原执行身份恢复，不重发不确定提交。

## 可选的 Worker 原线程续接（N6c）

新 `prepare` 可同时传 `--node-budget-policy /绝对路径/node.json` 和
`--worker-resume-policy /绝对路径/resume.json`，后者无默认值，格式为：

```json
{"max_attempts":2,"protocol":"codex_exec_resume","usage_scope":"turn"}
```

`max_attempts` 只能为 1 或 2，表示初次执行之外最多新增的已接受续接次数。
必须使用支持 resume 的冻结 launcher；策略声明和文件身份校验不等于实际 native 资格。
旧未启用实例或 fresh-only wrapper 不支持，不原地改 settings，也不绕 wrapper 直接启动模型。

```bash
scid-research worker-resume --root /绝对路径/实例 --step 2
```

命令继续同一科学节点、真实 thread、home 和 workspace，追加 attempt 原件，保留 checkpoint；
原 job、初次 intent/outcome/usage/raw 不覆盖。已接受续接先收集原工作，重复命令不重派；
成功但未封存的输出优先补原 seal。首版仅接受非零数字 returncode、无 stop_reason、有效
completed meter 且清理可确认的已知本地故障；缺 session/thread/meter、执行或清理 unknown、
身份失配、原 pause/closeout 均不放行，不将预算硬停止当可无额续接。

所有 attempt 成本累计，原 node/W cap 不重置、不退款；续接使用当前有效共享授权，并占一个
原执行名额、保留交付预留。合法总额修订不自动扩节点 cap；命令没有续额参数。
受管理执行按原 ID 恢复，不重发不确定提交；普通 shell 仍由角色判断 checkpoint，不承诺任意脚本幂等。

源码、独立审查与最终 fake/installed 零模型门禁已通过；实际 Codex 同线程有效性、增量用量
与权限尚未验证。范围见[原线程续接设计](plans/evidence/ROOTLESS_WORKER_RESUME_DESIGN_20261012.zh-CN.md)，
测试快照与失败保留见[验收记录](plans/evidence/ROOTLESS_N6C_WORKER_RESUME_20261012.zh-CN.md)。
