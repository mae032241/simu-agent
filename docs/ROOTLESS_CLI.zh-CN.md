# 无 Root 的科研 CLI

`scid-research` 直接启动新的 H/W/A/证据原生线程；控制程序执行科学角色选择的路由。
不依赖 LoopX，不启动 Root 模型，不需要 MCP 管理页绑定。已提供实例 UI、可选来源/正式审查与执行授权接缝；TCAD 非空输入和长时人工等待恢复尚未接通，旧 daemon 不迁入。当前迁移节点仅通过静态独审，未验证真实远端执行。

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

可在 prepare 传入 `--role-profiles /absolute/path/role-profiles.json` 固定各角色的模型、推理力度和服务档位，例如：

```json
{"H":{"model":"gpt-6.1-sol"},"W":{"model":"gpt-6.1-sol"},"A":{"model":"gpt-5.6-sol"}}
```

省略的角色和字段继承 `--model`、`--reasoning-effort`、`--service-tier`；上例 E 继承全局默认。
显式配置文件须为 JSON 对象（`{}` 可用，`null` 和数组拒绝）；配置只接受 H/W/A/E 及 `model`、`reasoning_effort`、`service_tier` 非空字符串，模型名没有白名单。
准备时展开并冻结完整四角色配置；job、native intent 和实际 argv 使用同一 profile，原 session 的修复和 fragment 恢复也保持原值。
修改原配置文件不影响已准备实例；不传该选项时保留全局配置行为。未知角色、无效配置或原件绑定不一致在原生提交前拒绝，不自动换模型。
rootless cov launcher 的 operator 配置应声明相同全局值与 `role_profiles`（可为等价的稀疏配置）；它核对冻结实例，再生成匹配的 CODEX_HOME 配置，拒绝不一致的 model/effort/tier 参数。
这些记录证明请求参数一致，不代替服务端实际模型或计费观测。

## 插件选择与实例管理（迁移中的能力）

`prepare --execution-config /path/config.json` 显式选择已注册执行器，配置形状为 `{"executor":"plugin:binding","configuration":{...}}`。仅用于宿主配置的 `--experiment-mode local`；这里 local 表示配置归属，不表示只支持本机计算。不传时沿用默认本地执行器。公开配置不接受控制层 scope、预算、原件身份或凭据；能力和实现身份随实例冻结。

实例页面复用同一控制状态：

```sh
scid-research serve-ui --root /absolute/path/instance \
  --approval-secret-file /absolute/path/operator-owned.key
```

密钥由操作者提供，须为现有普通文件、权限0600且至少32字节。命令监听 loopback 并输出独立只读/管理链接，重启后旧浏览凭据失效。普通本地实例无需启用正式审查或执行审批，也能查看节点状态、请求暂停和继续。暂停只阻止下一节点；已接受工作继续完成。继续复用原实例写锁，服务只允许一个进行中的推进请求。页面当前展示状态元数据，不提供任意路径或完整私有会话读取。

准备实例时可选 `--source-restrictions` 冻结来源声明、`--enable-formal-review` 启用精确对象独立审查。正式审查不等于执行授权。另启 `--enable-execution-authority` 与 `--execution-resource-policy` 才接资源准入：资源策略显式声明 `{"version":1,"allowance":{"wall_time_seconds":N,"max_storage_bytes":N}}`（N为正整数），执行器必须支持冻结的授权合同；不支持不能静默绕过。人工决定在同一实例页面作出，浏览权限本身不授执行额度。

资源账复用原 control ledger，换候选/重试不重置消耗。`budget-amend --execution-wall-seconds N --execution-storage-bytes N --authorization-note ...` 仅修订有限资源上限，不代替精确调用的执行决定；不得和科学token/时间修订参数混用。未知调用不退款、不重发，已接受调用的查询/取消不因W结束而被当成新提交拒绝。

这些代码接缝不证明新TCAD链已可生产使用。完整范围及未验收项以[迁移计划](plans/THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)和对应独审报告为准；不从旧实例静默升级或复制预算。当前不运行安装矩阵、真实模型/solver或HTTP验收。

## 受管本地实验

标准单项 `codex` launcher 新建实例默认冻结 `--experiment-mode local`，W 启动前由控制层准备本地执行配置。
自定义 launcher 省略此参数时按兼容规则冻结 `external`，其执行配置由 launcher 提供；任务简报会说明普通 shell 命令没有自动记录。
自定义本地 launcher 可显式传 `--experiment-mode local`；已有 cov launcher 使用 `external`，不会被默认 local 配置覆盖。
模式在 settings/job 中冻结，恢复沿用原选择；已有实例缺少此字段时保持原配置路径。
原生 shell 和权限照常可用，临时分析无需逐项受管。

W 可在 `experiments/<name>/` 编写脚本及输入，通过已有执行 CLI 正式运行：

```sh
scid-experiment --config work/experiment-config.json run \
  --experiment-dir experiments/check-one --script experiments/check-one/run.py -- --seed 7
```

控制层只快照明确选择的目录，排除该目录原有的 `artifacts/`，在接受执行前验证文件原件并原子保留。
完整输入快照不设框架固定文件数、单件或累计字节上限；仍拒绝符号链接和路径逃逸，不扫描整个工作区寻找依赖。
复制的脚本以快照根为工作目录运行，命令参数按 argv 原样传入；脚本将输出写到 `artifacts/`。
原目录不接收这些运行输出。控制记录命令、参数、退出码、耗时和日志，保留输入及输出快照。
命令默认最多65秒且不超过实例原秒数上限，完整执行日志不按紧凑视图容量截断；任务和共享预算仍适用。
未在所选目录中的导入、环境及外部文件没有被快照，不据此承诺完整环境复现。
脚本应使用相对路径读取受管输入；argv 不推断文件含义或改写绝对路径，原生访问本身不构成读取快照的证明。
仅 `--script` 的原单文件入口仍可用；需要输入、成果自动快照时使用 `--experiment-dir`。

科学代码可生成可选的 `artifacts/result.json`：

```json
{"version":1,"metrics":[{"name":"loss","value":0.2,"unit":null,"evaluation_key":"public-v1","direction":"min"}],"outputs":[{"path":"artifacts/comparison.csv","label":"比较数据"}]}
```

`metrics` 要求不同的名称和有限数值；`unit`、`evaluation_key`、`direction` 可省略或为 null。
`outputs` 声明本次已保留的 `artifacts/` 相对路径及科学标签；完整指标和成果清单不设框架固定项数上限。科学代码只写结果，不填哈希、原件ID或审计结论。
控制保留原 JSON 和成果，自动采集指标，在后继角色的 `lineage.indexes.experiments` 提供分页入口，并按现有成果机制交接文件。
结果可另声明可选的候选元数据，例如 `"candidate":{"label":"method-a","metric":"loss","artifact":"artifacts/comparison.csv"}`。
`metric` 必须精确指向具备非空 `evaluation_key` 和 `min/max` 方向的已声明指标，`artifact` 必须指向已声明并保留的成果；控制层由原 scope 和 call 生成稳定候选身份，纳入已有候选比较、A 选择及交付流程。
多个指标而未声明候选时只记录测量，不猜选指标；只有冻结接口明确声明本地结果协议时才解析该候选字段，其他 adapter 的私有结果保持原件。
指标名不赋予目标含义，同口径比较不代替 A 的科学判断；无合格候选时 A 的推荐仍可为 null。

执行状态与结果状态分别显示：退出码0只表示命令成功；结果文件缺失为 `missing`，JSON或指标无效为 `invalid`，采集失败为 `unavailable`。
原件、cleanup或外部结果未知时保留 `unknown`，不得重发以代替查明原调用。
完整执行、结果、观察和封存记录不受紧凑视图的字节或累计项数上限约束；公开摘要和分页视图仍有界，明确标记省略并保留原件入口。视图超限不会使封存失败或丢失候选、调用与成果的权威关联。
使用 `lineage-status` 查看已有调用，或用其原 call ID 执行 `query`、`lookup`、`collect`；失败和缺失不会变成科学合格。
无外部交付 adapter 时可使用 `scid-research closeout --root /path/to/instance --export-only` 保留成果及限制，状态为 `exported_unsubmitted`。
本地成果封存及交接不产生 cov 审计资格或外部提交确认。
显式配置通用目录交付 adapter 后，A 的 `deliver` 可授权控制层解析精确输入和成果、封装并确认目标目录；该确认只证明本地目录交付。
默认本地工具的两候选、A 选择、目录交付及独立重放已有[通用逆问题真实模型报告](plans/evidence/GENERIC_INVERSE_LIVE_RESULT_20261016.zh-CN.md)；该场为本地同步任务，不代表 TCAD 或异步执行验收。

## 文件与职责

H 提出竞争机制和最小判别依据，决定是否请求 E。W 在用户约束与 H 范围内拥有实验设计和搜索责任，根据结果新建、改进、修复或回退候选。A 判断全局贡献、关键证据缺口和下一方向；它可要求关键反例，但不默认指定完整算法、参数或扰动矩阵。机制改变交回 H。

新实例将 A→W/H 的路由原话标为带来源的决策背景；具体执行方法是建议，用户原文和 H 的真实约束仍有效。控制层不判定科学语义，不删改原始路由；旧已冻结任务保持原投影。证据提取、控制补正和收口指令保留各自含义。新任务把原生角色指引冻结，启动与恢复使用同一份文字。

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

新实例的成果采集默认不设单文件或单节点累计存储大小限制（冻结值为 null）。操作者可显式传入正整数 `--max-output-item-bytes`、`--max-output-total-bytes` 限制采集和直接交接；已有实例冻结的整数配额仍生效，不自动扩大。
显式配额与模型紧凑视图限制分别执行，也不改变 token、时间或执行次数预算。声明目录之外的文件不自动获得证据资格。
若模型正常退出且科学输出已经固定，而控制层封存失败，修复交付后 `run` 可只重试封存。
不修改原科学结论，不重复执行模型；结果未知、模型失败和用量缺失仍拒绝自动重放。

## 路由与暂停

H 选择 `experiment / analyze / extract / wait`；W 固定交 A；
A 选择 `continue_w / revise_h / extract / deliver / wait / finish`，冻结启用候选审计能力时还可选 `audit`；E 返回请求它的 H 或 A。禁用时 `audit_capability.available=false`，audit 请求返回明确不可用回执且不执行外部调用；已接受原件仍按原身份计步并检查未知状态。
`next_action` 是枚举，理由单独写 `route_reason`。`deliver` 明确授权适配器交付所选候选；`finish` 结束科学探索，收口时表示不授权交付。两者都不宣称全局目标已完成。`extract` 仅向 E 请求科学证据提取；精确原件定位、复制、封装、提交由控制层和交付适配器完成。

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
科学角色的 `wait` 仍表示停止等待。W 已接受且同一 external execution 明确 running 时，控制在科学封存前保留原 checkpoint 并进入 `waiting`；默认 `run` 自动监控原 call，终态后 reconcile 并在合格的原会话中续接 W 消费原件，再封存。等待不调用模型、不增加 native dispatch 或 `advance_seconds`，但真实执行的 `waiting_seconds` 仍消耗原授权总运行时限；旧 elapsed 口径继续按总经过时间计量。暂停阻止唤醒的新 native turn，允许核对原终态；控制进程同 boot 重启后从原 waiting 恢复，未知提交不重放。续接仍受原预算/有限次数与冻结 launcher/session 能力约束；能力不足保留 checkpoint 并报告 unavailable。

旧 W 已 sealed unknown 的事实保持不变。`scid-research execution-recover --root /absolute/path/instance --step N` 可对同 call 追加已验证终态；后继新 job 冻结其恢复事实前缀与材料，已准备 job 仍只读原输入。该动作不把旧科学结论改为 screened，也不重计机会、grant 或原 slice。

新建实例的 `--max-seconds` 是推进启用时长上限：控制推进与原生执行重叠只计一次。
暂停请求生效前已接受的工作和控制器断连后的原执行继续计时；无活动且进入暂停时停止消耗推进额度。
身份或终态无法核实时保守计时，后续核实从当前时刻停表，不回填旧终态时间返还消费。
`status.budget` 分别报告 `advance_seconds / waiting_seconds / paused_seconds / elapsed_seconds`，并显示有效上限、
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

观察调用上限仍为 5 秒；完整输入、输出、候选/上下文清单及内部传输不再设置框架固定字节或累计项数上限。超时或格式问题保留明确不可用事实，不冒充完整观察。
配置、封存绑定和归档原件篡改仍拒绝恢复。完整公开台账及提交模型的原观察字节由宿主按内容去重封存，使用流式哈希和复制，不设原单件 32MiB、总对象 128MiB 上限；既有 `digest_only` 或 `unavailable` 记录不因新规则被追认成可回读原件。
历史默认投递紧凑简报（最多 4096 字节），按需读取的历史分页每页最多 64000 字节；可选 overview 超限时明确省略，完整观察和索引仍保留。归档私有原件不因此全部挂给科学角色；读取仍按冻结来源与权限解析。
最后一个节点也更新 `host-history/overview.json` 投影；投影删失可由封存科学原件和观察快照重建，观察快照不是可删除缓存。


## 可选的预算内收口（N6b）

新实例可在 `prepare` 同时冻结 `--node-budget-policy` 和 `--delivery-policy`。
交付策略包含 `closeout_a` 的 token/秒上限、`inflight_tokens`、`cleanup_seconds`、
`submit_seconds`、`confirm_seconds` 和 `adapter`；各值由操作者明确配置，没有生产默认预算。
预留来自原总额度，不是追加额度。默认 soft 模式预留一次收口 A 目标、在途缓冲、清理及提交/确认；有预留之外的正额度即可准入探索，不要求剩余额度容纳完整下一节点目标。进入收口前为下一次 A 保留声明的 token/时间目标与机械交付底线；接受后的 soft A 仍按共享剩余预算运行。额外 A 逐次准入，可选审计另保留一个后续 A 的完整目标。
显式 hard 及未记录模式的旧实例仍预留最多三个收口 A（含两次补正），并要求下一节点硬上限与预留同时可用。到达准入边界时转入收口；A 选择候选，适配器落实提交。soft 提示不能保证在途节点及时返回，总预算硬停止仍有效。

适配器是独立的领域接口。核心冻结其代码、启动器、输入原件及读取范围，不解释领域台账。
收口先冻结完整候选目录，`science-task.json` 给出目录文件；16 项紧凑摘要有省略计数，完整目录保留全部精确候选 ID 和来源节点，不按紧凑摘要容量截断。控制层仅对实际选择或控制 shortlist 中的候选解析并冻结原件。可用性与审计资格分别展示；精确原件的审计结果、工件匹配和适用范围沿历史传递，不额外制造未知泄漏待办。A 选择不等于审计通过。原生 `exp submit` 保留公共命令，但只使用 run 声明的路径，不解析历史跨节点原件；受管 wrapper 的 submit/help 会提示历史交付使用 A `deliver`，不会阻断或改写命令。
普通 A 的 `deliver` 复用其已封存选择进入控制交付，不经过 E。未配置选择策略时保持 H/W/A 三节点；显式 `selection_policy` 先执行冻结筛选，再由精确 closeout A 按默认与 override 合同比较，不能绕开策略。交付策略要求的公开审计必须完整通过才能更新实际提交；失败、跳过或未知不能冒充审计通过。未提供可选 audit/smoke 能力保持中性，不绕过已冻结的必需审计策略。收口 A 用 `deliver` 授权适配器交付，用 `audit` 请求资格，用 `finish` 拒绝交付，用 `wait` 暂停。`extract / continue_w / revise_h` 的原话保留并触发最多两次作者补正，不会静默转换成交付授权，不会据此重新开放收口探索；协议 18 只为已绑定工程故障允许一次精确 W repair。正常审计往返及提交前完整审计明确拒绝后的改选只消耗原总预算，不消耗错误补正次数。完整审计拒绝的同一候选工件不能再次提交；工程故障、未运行和未分类回执不冒充科学拒绝。未知操作绝不改选或重放。
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

`delivery_confirmed` 仅表示 A 选定的确切工件已在声明目标确认交付；通用目录 adapter 只确认本地目录，不表示外部服务接收。`goal_completion` 仍为 `not_asserted`。
`exported_unsubmitted`、`closeout_unresolved`、`delivery_failed`、`delivery_unknown` 分别保留未提交、
未决、失败和未知，不等同科研任务完成。配置交付但预算不足返回 `closeout_budget_unavailable`，保留 model 收口边界，不伪装成操作者 export_only。暂时来源准备失败返回 `closeout_preparation_unavailable`，保留失败原件，重复 `run/closeout` 可在原预算内重试准备并复用已封存 A；它不固化为操作者 `export_only`。清理未知继续阻止任何新执行。`status` 由相同原件重建状态和最新收口 A 推荐；此前实际提交观察与当前确认结果仍分开。真实科学效果须另行验收。

当前写协议为 **18**。协议 17 及更早的真实场和证据保持归档只读，不能用新代码续接、重解释或原地迁移；新场必须重新 `prepare`。此变更不增加预算，不对冻结旧场执行任何恢复。

适配器只冻结声明的脚本 `source.py`、模型和静态输入。受管 call 的封存脚本可来自旧 W scratch；审计台账局部改写为 `/inputs/source.py` 与 `/inputs/artifact`，旧 W workspace 不挂载到审计命名空间。脚本的任意本地兄弟模块或未声明依赖不会递归捕获；缺依赖属于工程故障，不能据此声明审计已完成或所有脚本都可交付。

### 审计工程故障与科学拒绝（协议 18）

进程退出 0、`leakage_flag=false` 都不足以证明审计通过。适配器核对精确候选、有限审计数值、完整执行回执及审计模型字节：`audited` 表示通过，`rejected` 才表示完整审计明确不合格；脚本、依赖、训练、进程或资源故障为 `engineering_error`，缺回执、无法可靠归因或原件身份不一致为 `unclassified`。后二者均不授予科学资格，也不自动要求换候选。

控制层先允许一次 scratch 审计工程恢复：重新从封存原件准备输入，写入独立不可变 intent/outcome，使用原共享余额与原单次上限并计步。它只重做未写真实交付目标的审计，不能重放 promote、confirm 或未知提交。任一 accepted intent 缺 outcome、进程清理未知或用量未知都会阻止新执行。重复 `run` 不重放已接受恢复。

确认是实现或未声明依赖问题时，可在原额度内建立一个精确 W repair，绑定故障回执、原候选、原 W 和封存输入。相同原候选 lineage 最多一个此类 W，不提高总额度或原次数上限。注册工具只允许对绑定 parent 运行一次新候选；不接受无 parent、新计划、换 parent 或重复调用。W 报告实现修复或需要科学改动，A 重新判断并授权新候选，旧授权不覆盖新字节。已封存结论不可覆写；只有未封存且符合既有恢复条件的任务可用 `worker-resume` 在原 session 续接。工件无法定位时不能重建并冒充历史原件。

选择策略在修复后保留旧筛选原件，并按 repair W step 冻结新一代比较。原故障实现仍展示但不当作可执行默认；A 仍须遵守同一默认/override 规则。状态从当前代相同 intent/outcome 投影，工程故障和未分类早停不会显示成等待执行。

这套自动恢复针对控制适配器和注册工具的语义回执，不解析任意 shell 输出，也不把原生 `exp submit` 退出成功当作资格。冻结运行时/公共 harness 无法恢复的工程问题会明确停机；不会热改安装或递归捕获任意依赖。预算、输入容量不足或修复次数耗尽分别保留明确状态，不能静默增额或改派无限任务。

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
身份失配、原 pause 均不放行；收口继续阻止普通探索任务续接，但允许对该收口 A 的已知故障使用同一 `worker-resume --step` 和原 session。原模型、launcher、权限、attempt 上限、累计用量及交付底线均保留，不将预算硬停止当可无额续接。

所有 attempt 成本累计，原 node/W cap 不重置、不退款；续接使用当前有效共享授权，并占一个
原执行名额、保留交付预留。合法总额修订不自动扩节点 cap；命令没有续额参数。
受管理执行按原 ID 恢复，不重发不确定提交；普通 shell 仍由角色判断 checkpoint，不承诺任意脚本幂等。

本节的恢复边界由上述冻结策略、原件身份、累计用量和拒绝条件共同限定。源码审查与
fake/installed 零模型门禁仅验证本地输运及拒绝路径；实际 Codex 同线程有效性、增量用量
与权限尚未验证。零模型检查不能授予实际 native 恢复资格，也不证明任意科学工作能够
安全续接。具体运行仍须保留原 attempt 记录、失败及未决限制，按该运行的实际证据判断。
