# scid → Root 模型可见上下文优化计划

状态：**active proposal；未实施、未验证、未部署，待独立计划复审。** 日期：2026-09-24。本文只制定软件优化计划，不恢复 Fig.4，不启动科研 Run、求解器或外部执行，不新增人工 token 审批。当前目录、结果读取和合同规则仍由实际安装源码及既有规范决定；本文件不是通过记录或科学资格证明。

## 1. 目标、文档所有权与范围

目标是减少 Root 实际收到、反复携带的 scid 信息：默认状态足够短，候选目录只供发现，选定 Operation 后才读精确调用合同，科学结果只在明确请求且 Run 已完成时读取。优化不能损失合法调用所需约束、封存原文、已持久化且可读取的失败诊断、分页完整性、独立审查或执行审批。

| 当前所有者／重叠文档 | 本计划关系与处置 |
|---|---|
| `operations/spec.py`、`operations/catalog.py`、当前 MCP gateway/routes/views、`docs/ARCHITECTURE.zh-CN.md` | 当前实现及职责边界；本计划不成为第二合同注册表 |
| [Agent 上下文与工具开销修复计划 R3](TOKEN_CONTEXT_COST_REDUCTION_PLAN.zh-CN.md) | 保留其启动、Worker 和历史实测；本文聚焦新观察到的 Root 接收面，不重写历史收益 |
| [Root 上下文边界修复计划 R2](ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_20260921.zh-CN.md)及其实施记录 | 已有 poll/navigation/decision、invoke view 和 producer 输入投影是本轮基础。本文提出下一轮默认策略与 invoke 内容精简，**部分改变旧提案“默认 compat/full 不变”的未来取舍**；在实施通过前不宣称规范已替代，也不继承旧验收 |
| [Operation catalog 标签分级计划](OPERATION_CATALOG_TAG_TIERING_PLAN_20260923.zh-CN.md) | 保留 P2 语义标签、身份与召回问题；本轮首先复用已存在的 P1 结构导航，不要求完成语义标签或新增 search |
| `roles/scheduler.md`、`roles/scheduler/research.md`、`roles/scheduler/results.md` | 调度指引的源；`.codex/scidiscovery-guides/` 和生成配置为安装投影。将来同步改源与生成／安装验证，不能只改某个工作区副本 |
| `docs/plans/README.md` | 现有入口链接旧计划及实施记录，部分状态叙述早于当前安装字节；本次只有新增文件权限，未改索引。实施阶段须核对后添加状态链接，不能据安装哈希把旧原生 A/B 标为完成 |

范围包括 Root 三工具入口与其 `operation_catalog/run_status` 路由、调用合同投影、必要的调度指引、安装探针、可见输出计量。非目标包括 Worker 科学报告重写、科学 Schema 一律标准化、自动选 Operation、研究策略替代、Run 生命周期重建、权限放宽、数据库迁移、向量检索基础设施和全局平台缓存改造。不得把 scientific limitation 压成一个 verdict，也不得从 child chat 提炼“正式结论”。

## 2. 核实基线与根因

### 2.1 源码与安装态

2026-09-24 只读核对的仓库为 `123/scidiscovery-e5.2`，HEAD `01fc3abc4fb14b0292c52440721b0e2e7b4a2cf4`，工作树有大量既有修改及未跟踪证据，HEAD 不等于实际候选。不得 reset、checkout 清理或覆盖他人字节。

| 真实位置 | 已核实现状 | 下一轮差异 |
|---|---|---|
| `mcp_root.py:RunStatusInput`、`mcp_root_run_routes.py:run_status`、`mcp_response_views.py:root_response` | 默认 `response_profile="compat"`；存在显式 poll/navigation/decision。compat 组装 bindings、native/recovery/timing 等，summary 也可含 selected output、signal、诊断。Agent 新建／幂等的 `operation_invoke` 回执还经 `_invoke_local_run→self.run_status` 取得冻结派发字段 | 默认短状态；内容层级要同时在参数规范化、服务组装与模型可见投影落实，且不能破坏创建回执或丢失回执后的派发恢复 |
| `mcp_root.py:RunListInput`、`mcp_root_run_routes.py:run_list→_run_status_value`、`mcp_response_views.py:root_response` | `run_list(view="detail",state="running")` 逐项返回诊断／恢复／计时字段，未走 `run_status` 状态门；列表没有封存 payload，故这不是完成态全文旁路 | 活动态列表 detail 与按名读取共用短投影；混合状态列表逐项判定，终态显式详情保留 |
| `mcp_root.py:RootMCPRouter`、`mcp_root_run_routes.py:run_status` | router 校验后移除 `view`，facade 不收 `view` 且固定用 `view="summary"` 校验；仅在 router 加全文开关会使直接 facade 无法表达合法 detail 请求 | 冻结共享请求规范化／校验边界并传达显式读取意图，两入口接受／拒绝同一请求 |
| `mcp_root_run_routes.py:_sealed_output` | **已经**要求 state=completed 且存在封存 output_ref 才读取科学 payload；历史合同标 historical | 不把现状误称为任意 queued 科学 payload 泄露；补齐 detail/compat、错误文本及别名入口的状态门，避免活动 Run 详情携带草稿／科学内容 |
| `mcp_response_views.py:run_profile_projection` | poll 仍带较多时间、身份、诊断字段；非 completed 会组装 diagnostic_summary | 短状态只含下一次行动所需机械状态；失败正文显式读取；不靠摘要字符串长度截断来声称精确诊断 |
| `mcp_response_views.py:operation_catalog` summary | 每项已有 `operation_id/purpose/executor_kind/catalog_scope/runtime_binding`，**没有输入输出端口**；默认 20 项，保留 total/next_before | 默认项进一步收敛为 ID＋一句功能描述，保留顶层完整性与续页 |
| `mcp_gateway.py:CatalogInput`、`mcp_response_views.py:operation_navigation` | P1 `index/facets/matches` 已存在；结构维度为 consequence/executor_kind/input_schema，带快照／查询游标、分页、预算 | 复用并审计它，不重新实现。`decision_intents/action/subject` 仍不是已部署语义标签 |
| `mcp_gateway.py:DescribeInput/describe`、`mcp_response_views.py:operation_invoke_contract` | describe 默认 full；指南已显式要求 invoke。invoke 从同一编译项投影，但仍包含全部 inputs、outputs、admission、validation 等大字段 | 必须直接优化**显式 invoke**；只改默认 view 无法修复已观察成本 |
| `deploy/install.sh` | 探针断言现有 view/profile enum 并读首个 public invoke | 协议变化须同步这些断言；三工具可列出并不证明新状态门、约束完整或模型收益 |

安装配置 `.codex/config.toml` 指向 `/home/da/miniconda3/bin/python -m scidiscovery.artifact_agent.interfaces.mcp_proxy --socket /run/scidiscovery/control.sock`，`PYTHONPATH=/opt/scidiscovery-m7/site`；systemd control 使用同一 site 的 `mcp_daemon`，启动前校验 runtime identity。规划时四个文件源码与 M7 site 哈希逐项相同：

| 文件（interfaces/ 下） | SHA-256 |
|---|---|
| mcp_gateway.py | `8d4d9b2cb37d3b88391923f6a24c9cdc5a7e22dcddf76c5c8a71039514d60197` |
| mcp_root.py | `d4dcdda6f97970a8bac6b50d53095536dd0946042f022476fd15c5d3113f64c9` |
| mcp_response_views.py | `3f78345e5d3a5d660c17e3b084aa0cae8dddb3024f0d777b5de099daaa25373a` |
| mcp_root_operation_routes.py | `b2d4991b2178e6b0f985647270022718b0836e430ebb878b25b6a21e2f9271af` |

这只证明已读文件和配置入口，不证明 daemon 内存已重载、全部安装文件一致或新行为验收。本计划没有调用 live scid、绑定实例或对生产数据库写入。实施前必须重冻基线；`mcp_root_run_routes.py` 等其余文件还须纳入逐项安装验收。

### 2.2 实际模型可见日志

证据源为本机 root rollout `rollout-2026-09-23T10-09-55-01a0cc06-d71a-7a70-8d2c-de80c905996a.jsonl`，目录 `/home/da/.codex/sessions/2026/09/23/`；窗口 UTC 2026-09-23 23:29:39.802 至 2026-09-24 00:19:21.398。规划复算使用窗口前最近累计 token 记录及窗口末记录；流式忽略全文件两行非 JSON 并计数，后续冻结必须定位其是否影响窗口，不静默假设证据完整。未将 transcript、凭据、worker assignment 或科学正文复制进计划。

| 指标 | 复算值／证据范围 |
|---|---|
| 累计输入差分 | 23,711,153 token；它是多次模型请求输入之和，包含反复携带的历史 |
| 累计 cached input 差分 | 23,606,272 token |
| 累计 noncached input 差分 | **104,881 token**，等于前两项差；不是单请求上下文长度，也不是 scid 字段 token |
| 累计输出差分 | 28,349 token；须另分 reasoning／可见输出，不与输入重复相加解释上下文净增 |
| `scid_describe` 的 exec 打印 | 14 次、47,114 字符；排除 exec “Script completed…”包装 |
| `scid_call` 的 exec 打印 | 37 次、43,323 字符；其中 run_status 13 次、29,803 字符，**子集不可相加** |
| `scid_catalog` | 0 次；本窗口不能直接证明目录优化收益 |
| `wait_agent` | 65 次，51 次 timed_out、13 次 completed、1 次新输入中断；等待频率影响请求数，非等待工具正文单项即可解释 |

含 exec 通用包装时对应字符为 describe 47,772、call 45,062、run_status 30,414，说明模型可见边界必须一致。13 次 invoke 打印包装合计 45,671 字符；用 `ensure_ascii=False,separators=(",",":")` 重新序列化字段值，inputs 合计 23,994、outputs 合计 6,466 字符。先前审计的 45,356／24,124／6,609 使用另一字段归属口径，不作为逐字段精确等式；两种口径均显示输入、输出占主要合同体积。

前审计报告的压缩前净增长 66,563、旧尾部重复未命中 26,797、压缩后 11,521 合计 104,881；其分解方法与约 28,738 的 scid 差分归因在本计划中仅为待复核分析，不冒充工具字段 token。三次探索候选约 10,822 字符也只作为待回放假设。窗口内有一次 compaction，不能用末次减首次输入表示整段增长。

根因排序：①默认／兼容状态与显式合同传输过宽；②root 编排能把完整响应再打印进模型，服务层预算无法阻止多页合并或重复打印；③合同缓存、已读值复用和等待节奏影响多轮累积；④目录候选发现有可缩减空间，但该窗口没有目录调用，不能据此新增一个 search 产品。

## 3. 接口提案与状态矩阵

以下是待实施草案，新增字段名与错误码必须在实现前由独立审阅者冻结。所有投影来自同一不可变编译声明／封存对象，不写回源合同，不改变 digest、ABI、资格和准入语义。

### 3.1 run_status：省略参数就是短状态

规范化优先区分“字段省略”和“显式给值”。`run_status({name})` 规范化为 poll、summary、values、`output_paths=[]`；所有状态默认短响应，不随 completed 自动升级。显式 `response_profile="poll"` 省略 paths 同样归一化；poll 加非空 paths 是精确参数错误，不能偷偷升级。新增正向开关 `include_full_output: bool = false`（严格 bool，拒绝 `1`、`"true"`）：只有请求**显式传入 `true`**，且 Run 已 completed、封存输出存在、`view="detail",response_profile="compat",output_mode="values"` 时，才可返回完整封存输出。省略开关、`false`、仅用 detail 或仅省略／置 `null` 的 `output_paths` 均不能触发全文；任意 values/decision/compat 路径数组中只要含根指针 `""`（含 `["/summary",""]`）就须精确拒绝并指向显式全文请求。非根路径仍可在预算内精确选择；开关只管整体 payload／封存输出的传输，不是科学访问权限。`include_full_output=true` 与任何 `output_paths` 数组（含 `[]`）、decision 或 index/navigation 互斥，报精确参数错误。

统一 gateway 和直接 Root facade 必须调用**同一个请求规范化／校验边界**，输入保留字段是否出现及显式 `view`，输出冻结的读取意图供服务组装和 `root_response` 使用。facade 应能接收 `view` 与严格 bool 开关；router 不得在传入 facade 前丢掉 view，facade 也不得固定 summary 校验合法的 detail＋compat＋values＋`true`。两入口都在读取 Run 内容前拒绝非法组合；服务层先取状态快照，再判定允许的内容范围，最后才读取 payload／诊断，避免先组装大详情再过滤。完成态／historical 仅在相同封存身份与状态门下读取，failed 和活动态即使传 `true` 也不能获得封存科学输出。

`run_list` 也属于活动态状态门：`RunListInput`、`RootRunRoutes.run_list→_run_status_value` 与 `root_response` 应逐项共用下述短投影；直接 facade 须接收列表 view，router 须传达它，不能只在最终响应过滤。`state="running"` 的 detail 和无 state 筛选的混合列表中，queued/running 项都不得带 reason 原文、diagnostic_summary、recovery 详情、tool_timing、草稿或其他长详情；保留小型冻结派发控制字段与必要机械状态。显式 terminal detail 仍可读取已持久化且可访问的诊断／恢复详情，不能因混合列表投影被一律裁掉。列表并不读取 completed 封存全文；本门针对活动态控制详情旁路。

“短”只禁止未封存的科学内容和冗长控制详情，不删除派发必需的冻结机械字段。Agent Run 创建／幂等的 `operation_invoke` 回执必须继续提供 `agent_type`、`execution_profile.profile` 中的 model／reasoning_effort、`deadline_at` 和精确 Run／Operation 身份；不能因内部改用默认短 `run_status` 而丢失。创建成功但回执丢失时，Root 仍须能按语义名从 queued/running Run 读取**同一冻结快照**的这些派发字段（短状态的小型控制白名单，或明确的机械恢复视图）；此路径不开放草稿、科学 payload 或活动态 detail。不得用当前模型默认值补缺，因为默认值可能已改变，错误档案会使 Worker 绑定失败。

全文开关还要求 `output_mode="values"`，不能与 index/navigation 或 decision 并用；错误组合在读取封存对象前拒绝。它控制的只是完成态封存输出全文，不代替失败诊断的显式读取。

| Run 状态 | 默认／poll | 显式 decision | 显式 navigation | 显式 detail（兼容入口亦同） |
|---|---|---|---|---|
| queued、running及其他未封存活动状态 | 短状态；Agent Run 可含上文冻结派发控制白名单；无科学字段、signal 正文、草稿、工具日志、bindings/timing 扩展；`run_list` 各项同门 | 短状态＋`content_unavailable`；不取 payload | 短状态＋不可用；不列草稿字段 | **仍只给短状态＋状态限制原因**；按名读取与 `run_list(view="detail")` 均不能绕过 |
| completed 且封存输出存在 | 短状态＋结果可读状态 | 明确的非根 paths 所选封存原文＋metadata／原始路径＋一次 signal；已知 Schema 一次读结论、限制、剩余矛盾，根指针须改用显式全文请求 | 明确请求的有界封存字段索引，不带值或 signal 正文 | detail 本身不带全文；仅显式 `include_full_output=true` 才返回完整封存输出（受现有传输上限约束），且不得同时提供 `output_paths` 数组 |
| completed 但输出不可读／不存在 | 短状态＋精确不可用状态 | 精确缺失／读取错误，不补造结论 | 同左 | 同左；不降级读草稿冒充成功 |
| failed、timed_out、cancelled 等非成功终态（按实际枚举映射） | 短状态＋失败标记／诊断可读状态 | 返回明确非科学终态及诊断入口，不给成功决策 | 不提供科学输出目录；给明确不可用原因 | 显式读取已持久化且该接口可访问的失败诊断与必要 recovery 数据；保留来源、分页及已知保存／投影限制，无封存科学结果 |

API 不必新增生命周期状态：超时若在当前模型中表示为 failed＋reason，就沿用该表达。`decision` 不强加跨 Schema 的固定科学字段；路径来自当前已读合同／既有结果 Schema，未知结构才 navigation。历史 completed 输出保留 historical 标记，读取不恢复 qualification。

超大叶值另有明确边界：当前 `_output_selection` 对超过 32 KiB 的单个字符串只标 `omitted`，`_output_index` 只枚举对象／数组的子项，**不能**靠它续读该字符串。因此本轮将现有隐式全文语义迁移为终态显式 `include_full_output=true` 的逃生口，不把它伪装成有界页，也不对活动 Run 开放；仅省略／置 `null` 的 `output_paths` 不再是读取全文的信号，`output_paths=[]` 也不能作为逃生口。全文大小仍受现有传输上限约束。若要对终态全文再施加不可例外的总预算，必须先独立设计绑定封存身份、偏移、UTF-8 边界、长度和重组校验的叶值分块协议，并通过真实入口测试；在此之前不得以“导航可继续”作为超大标量的完整性承诺。

草案最短请求／响应：

```json
{"name":"run_status","arguments":{"name":"selected_run"}}
```

```json
{"name":"selected_run","state":"running","last_activity_at":"...","sealed_output_status":"unavailable","recovery_available":false}
```

结果读取继续复用现有显式请求：

```json
{"name":"run_status","arguments":{"name":"selected_run","response_profile":"decision","output_paths":["/formal_conclusion","/limitations","/remaining_contradiction"]}}
```

只有确需完成态封存输出全文时才显式请求：

```json
{"name":"run_status","arguments":{"name":"selected_run","view":"detail","response_profile":"compat","include_full_output":true}}
```

这些路径仅示例，不保证任何 Operation 都有它们。失败详细读取为 `view="detail",response_profile="compat",output_paths=[],diagnostic_after=0`；diagnostic_events 按已有事件游标 next_after 续读。新的短状态可把下一次读取提示集中到接口合同，避免每次重复长 detail 字典。这里的“精确”限定为**已持久化且由对应读取面可访问的字节**：现有失败 reason 入库前最多保留 4096 字符，`_stored_diagnostic` 每个事件最多投影前 16 个 details；`diagnostic_read` 只可分块读取确有 engineering reference 的原件，不能恢复未保存的 reason 尾部。默认只给机械原因码及可读标志；显式读取须保留当前可访问原文及其来源／限制，不把历史截断值标成完整原始错误。若要求其余已存 details 的继续读取，应另列读投影改造，不能冒称现有事件分页已经覆盖。

上面的失败诊断示例使用 `output_paths=[]` 是故意跳过科学 payload。完成态全文逃生请求必须显式加入 `include_full_output=true`；只省略 `output_paths` 或传 `null` 均不够，不能让旧的缺省值继续触发全文。

状态判断与结果读取必须绑定同一 Run 快照／封存输出身份；竞争完成不能导致返回 running 却附科学 payload。poll 默认不调用完整 recovery_status/native workspace 读取；只复用既有可判断的恢复布尔或小状态，不引入新的可漂移缓存。

### 3.2 catalog：候选发现维持一个入口

默认 `scid_catalog(kind="operations")` 每项仅 `operation_id` 和一句 `purpose`。描述必须区分相近候选，不以任意 120 字符切断否定、适用边界；首先核对现有 purpose 能否直接复用，需缩写则在原声明／同源导航摘要所有权内修订并审查身份影响，禁止维护独立 ID→文案注册表。

```json
{"scope":"public","view":"summary","operations":[{"operation_id":"selected.operation.v1","purpose":"一句准确的功能描述。"}],"total":31,"returned":20,"next_before":"opaque_cursor","complete":false}
```

数量是示例。保留分页与“本页／查询完成”的区别；优先复用现有 P1 的 snapshot/query 游标实现，禁止将旧 summary 原始 ID 游标直接当新游标接续。分页发生安装／可见集合变化时精确报 restart_query。默认项不含 inputs、outputs、input_schemas、review 合同或权限；顶层 scope、总数、完整性、游标不是候选项详情。动态不可用性继续由既有 public 可见性逻辑决定，不能把列出 ID 当作请求准入。

P1 结构导航继续显式开放 `index/facets/matches`；`consequence/executor_kind/input_schema` 是结构筛选，**不是科学意图标签**。matches 现有 input_schemas 属显式导航信息，不反向加进默认目录。标签值应从真实安装 V 集合生成并测试零匹配、非零但漏掉正确项、未标记插件和环境变化；读取一个非零过滤子集并不能证明完整召回。public/support/internal/all 维持既有边界：当前 P1 public 导航不覆盖 support 查询；已选 public 若需 support，仍沿精确合同和现有 `operation_catalog(scope="support")` 查询，不能称新标签已解决全部发现成本。

本轮**不新增 search 接口**。若后续 holdout 显示现有目录分页／结构筛选确实不能在合理成本找到候选，先评估 catalog 的显式查询参数；任何 search 都只能是同一 V 的派生导航，返回候选、覆盖范围和回退入口，不复制 callable contract、准入或行动权威。P2 语义标签继续按原标签计划单独验收，不作为本轮 run_status／invoke 优化前置条件；不新增 Worker 目录权限。

### 3.3 describe：显式 invoke 也要真正精简

建议保留 `view="invoke"/"full"` 两种主视图，新增可选的表示参数 `representation="compact"|"legacy"` 用于过渡；invoke 默认 compact，legacy 是显式短期逃生口，full 是明确的完整诊断读取。省略 view 时按已解析名字类别选择：Operation→invoke，interface→full；interface 显式 invoke 继续报不支持。不能统一把接口默认改为 invoke 导致接口 Schema 无法读取，也不能仅改默认而继续对显式 invoke 返回旧大体积。

compact invoke 保持当前单项 envelope 和常用键名，标记 `contract_view_version`、operation_digest 及精確 full 读取入口；具体空字段／默认值的压缩由同一协议版本确定，不能让客户端猜默认。为避免重复构建完整目录，优先从同一 compiled item 直接投影，保留现有 digest 一致性检查。

| 类别 | invoke 初读必须保留 | 允许按需披露 |
|---|---|---|
| 身份与用途 | ID、版本、digest、scope、后果及影响选用的 applies_when/not_for；禁止从截断句子猜适用性 | 重复 purpose 文案、纯背景论证可去重；不把规范规则埋进 full |
| 每个输入端口，包括 optional | name/schema、基数、current 要求、required_non_null_fields、usage/exposure、media types、大小限制；总体目标与相关进展 optional 端口也必须可见；理解输入语义所必需的 description | 重复描述或非约束例子可移至 full；有科学绑定语义的原文不能被机械截断 |
| 跨端口与资格 | input_admission、all-or-none cohort、approval subject/provider/options、complete_transform_family、input_validation 的可执行规则含义 | 实现组件位置／内部调试元数据；不能以“失败后再纠错”取代可发现的调用条件 |
| review／revision | review_edge、独立审查、人审要求、revision base/change request/progress 端口及修订限制 | Worker 输出撰写提示、内部执行模板 |
| 输出 | output name/schema/基数、解释结果与绑定下一步所必需语义、review subject 输出、实际返回身份映射 | 完整输出 JSON Schema、不影响调用和结果解释的长说明、生成端验证细节 |
| 执行与请求限制 | 当前可用性、Root 可设置的 timeout/attempt/max input 等边界和合法 request 语法入口 | native shell/network/tool/file 等 Worker 执行诊断详情，仅 full 显式读取 |

第一轮只实施能逐字段证明安全的去重与非 Root 执行详情剥离。现有 invoke 已去掉部分执行字段，不能再次计作收益。可共享的相同默认约束可以在单次合同的 `defaults` 中声明一次，但必须有明确继承／覆盖规则及“展开后与旧合同等价”检查；不能凭键缺失推断 require_current=false、基数=1 或无限字节。若这会令旧客户端复杂度超过收益，保留冗余、只做低风险裁剪，达不到目标如实记录。

服务端渐进披露的边界：invoke 是**合法调用完整面**，full 是完整诊断面。必要合法约束不能因为字符预算而移入可选页面。超大且不可约简的合法调用面明确报告实际尺寸与预算未达，不返回“已完整”但缺约束的合同。如确需合同分节，必须先返回可机械验证的未读必需节清单和同 digest 精确读取请求，并在所有必需节读完前标记 incomplete；该额外往返方案仅在第一轮压缩失败、有测量支持后另审，不成为本轮新增状态机。禁止客户端对字符串直接截断 invoke 以达标。

不添加业务层“合同已阅读”审批或持久化门。准入仍由 operation_invoke 一次验证；operation_preflight 保持可选。optional 端口不能因 min_items=0 隐形，input_validation 的自然语言不能被当装饰删除，output 的名字／Schema 不能靠 Operation ID 猜。

## 4. 默认迁移与兼容

本轮改变默认，不能声称旧客户端字节兼容。采用同一发布中的清晰迁移，避免无限期保留默认大响应：

1. P0 枚举调用方：统一 gateway、`scid_call` logical interface、直接 Root facade、CLI、安装脚本、生成 scheduler 指引与测试；特别列出 `_invoke_local_run` 新建／幂等回执和丢失回执后的派发恢复，以及 `run_list(view="detail")`／混合状态列表的消费者。记录哪些依赖 compat 默认、`view="detail"` 加省略／`null` paths 的隐式全文、活动态列表详情、full 默认、summary 附带执行字段、旧游标、旧 invoke 空字段。既有第三方调用方按公开兼容约定列出未知项。
2. 先在共享规范化边界、gateway Schema 和直接 facade 同时提供并验证 `include_full_output=true` 的显式终态全文请求；迁移所有受控调用方，再原子切换安装。切换后省略该字段不得返回全文；旧 `output_paths=[""]` 或含根指针的混合数组须迁移为正向开关。短状态成为省略参数的唯一行为；`view="detail"` 省略 profile 可规范化为显式 compat detail，**但它也不隐式打开封存输出**，所有活动状态及 `run_list` 活动态项受同一短状态门。Agent 创建回执与按名恢复须保留同一冻结派发控制字段；旧的只给 output_paths 的非根字段请求返回明确迁移错误，提示显式 decision；不得自动读内容让默认语义含混。
3. 显式 `representation="legacy"` 只保留旧 invoke 表示；`view="full"` 保留完整 Operation 合同。run_status 的 compat 仅为**显式终态控制详情／诊断**过渡，不能以它单独读取封存输出，也不能绕过 queued/running 门。旧客户端原来通过缺省 paths 取得全文的请求须迁移为正向开关；不能用永久隐式兼容分支规避用户的显式请求要求。对旧客户端原来的活动 Run detail、活动态 `run_list` detail 缩减记为有意行为变化，冻结派发字段不在缩减之列；终态显式诊断详情仍可达。
4. Operation 与 interface 的省略 view 在 gateway 名字解析后分别决定；接口 inputSchema 仍完整。分页 cursor 不跨协议代际续用，精确错误要求重启同一查询；客户端不静默退回旧大页。新的完整性标记不得与旧 total/next_before 含义矛盾。
5. 发布说明列明响应表示版本和显式旧表示支持期限；期限由已识别消费者迁移完成决定，不能本计划臆定所有消费者已更新。若存在阻断客户端，延后默认切换，不部署一半。用户已明确的短状态目标不通过“永久 legacy 默认”规避。

本次只改读投影，预期 Operation digest、ABI、存量 Run/Artifact 与封存审批不变；必须测等价，不能仅声称。任何为了导航摘要或默认表而修改声明身份的方案须单列影响，并重新独立审查，不纳入无迁移投影发布。

## 5. 模型可见预算与责任边界

服务端能约束单次 scid 原始响应、状态允许面、分页、合同同源性；不能清除 Root 已有上下文，也不能阻止 `functions.exec` 把多份响应拼起来或用其他工具读取原件。`store()` 保留完整对象后再 `text(full)` 仍是全量暴露。仅改服务 JSON 大小不能宣称 Root 上下文已受控。

| 层 | 应实施的约束 | 不能声称的保证 |
|---|---|---|
| 服务／gateway | `run_status` 与 `run_list` 共用活动态短投影；按名读取两入口共用规范化／校验，先状态门后内容读取；有界常规页、终态显式大读逃生口、同源 compact 合同；对象／数组的精确遗漏和续页不冒充超大叶值续读 | 任意 Root 编排永不重复、模型总上下文上限、外部平台缓存命中率 |
| 编排的可见输出 | 先存原始对象；structuredContent 优先，text fallback 只解析一次；只打印选择值、计数、完整性与精确错误／路径；按 digest＋view＋字段集合复用已读值 | 自由形式 exec／shell 的全部输出可由 scid 服务拦截 |
| 调度器行为 | 已选 Operation 才 describe，按版本失效；相同 sealed payload 不重复读子字段；等待完成通知，无理由不轮询；短期无变化不打印相同状态 | 科学结论完整性可由一般摘要代替；固定字段可以覆盖所有 Schema |
| 测量／运行时 | 记录真正传入 Root 的工具 output blocks、每次请求 token、cache、compaction 分段及 episode 累积；超预算产生机械记录并停止无关重复读取 | 已经存在一个可强制拦截全部 functions.exec 输出的宿主能力 |

最小实施复用现有编排工具与存储，不新增第二 scid 工具集。给调度器一条明确的可见输出策略：单次打印不合并多个大页；已知路径直接读；未知路径一页导航；目标决定已具足便停止展开。以 Operation digest、sealed artifact identity、profile/path/page 作为复用键，安装／合同变化或上下文丢失后才重读；不额外缓存动态 currentness／权限结论。

若实际产品宿主无法拦截任意 exec 输出，必须报告“服务单响应有界、受控编排路径已测，任意 Root 累积仍不能硬保证”。强制全局预算需要宿主层输出投影/会话窗口能力，属于待核实集成面；不在 SciDiscovery 内用第二预算审批、科学权限门或伪造压缩摘要代替。累计可见预算触及时先减少重复打印、保留精确未读引用并在支持的平台使用既有 compaction；不隐去还影响决策的必要证据，不向用户请求 token 人工批准。

## 6. 分阶段最小实施与独立复审

| 阶段／优先级 | 最小变更面 | 退出条件 |
|---|---|---|
| P0 基线冻结 | 只读记录 dirty 文件 before hash／可恢复快照、源码与 M7 安装入口、窗口 identity、调用方清单；含列表 detail 和直接 facade，建立仅含必要结构的 replay fixtures 与测量脚本 | 原始响应和实际打印清楚分层；字段保留清单、共享规范化契约、迁移策略、验收数据集经独立计划复审；无科研 Run |
| P1 最高优先：短状态与终态显式读 | `mcp_root.py` 的 `RunStatusInput`／`RunListInput` 和 router、`mcp_root_run_routes.py` 的按名／列表组装、`mcp_response_views.py`；共享规范化／校验，传入 facade 的显式 view／开关，逐项活动态投影；同步 logical schema／`_invoke_local_run` 创建回执及派发恢复调用方 | gateway 与直接 facade 正反例同判；默认所有状态短，queued/running 的 status 与 list detail 均无长详情且冻结派发字段同源可恢复；混合列表终态显式诊断仍可读；完成态仅正向 `include_full_output=true` 可取全文，显式大读不回退；已持久化且可访问的失败诊断可达 |
| P2 高优先：显式 invoke 精简 | `mcp_gateway.py`、`mcp_response_views.py`，必要的同源 projection；不动准入验证器／科学 Schema | 逐字段展开等价、optional 与跨端口约束全保留；actual invoke 打印变小；默认操作／接口视图迁移可用 |
| P3 小包：目录与编排 | 复用 P1 catalog；默认条目去除非发现字段、补齐完整性；scheduler 源指南及生成路径，复用与可见打印纪律 | 候选 V 不丢失，support 有明确现有路径；受控 replay 无新增重复打印／漏读，实际增长另在 P4 测；不新增 search／语义标签 |
| P4 发布与模型验收 | `deploy/install.sh`、真实 wheel/loader/proxy/daemon 探针、精确生成配置、定向测试、状态文档 | 安装态正负例、独立跨边界实现审查通过；按 §7.2 分别判定工程完成与原生收益，不把 stretch 未达当安全失败 |

P1、P2 可分别冻结增量，避免把目录标签研究拖成依赖。每阶段只按当前 dirty 字节作 patch，记录实际新增文件与变更文件；不覆盖用户已有修改，不将宽泛仓库 diff 当本轮改动。独立节点至少三处：R0 计划（约束保留与默认迁移）、R1 实现（接口两侧和所有旁路）、R2 安装／真实模型证据（成本、失败样本、角色及资格边界）。独立复审不得由作者自评替代；本计划未执行任何一个节点。

## 7. 验收样本、指标与通过条件

### 7.1 正反例与真实入口

- Run：queued/running＋默认、detail、compat、decision、navigation、`output_paths=[""]`、diagnostic_after 全矩阵；在合成草稿／error 中植入可识别科学文本，断言活动态响应没有其正文。`run_list(view="detail",state="running")` 和无 state 筛选的混合列表经统一 gateway 与直接 facade 均须逐项限制活动态诊断、恢复、计时等长字段；混合列表中的 failed／其他终态显式详情仍保留其原有可访问诊断，不把列表误测成完成态封存全文入口。另测 Agent 新建和幂等回执均保留冻结 `agent_type/execution_profile.profile/deadline_at`，以及“创建成功但回执丢失→默认模型改变→按名恢复原档案→正确派发”，不准以当前默认值代替。分别覆盖已封存 completed、failed 的超时表达、未知／兼容取消态、缺封存输出、旧合同 historical、跨实例名字、状态完成竞争、null／missing／empty。用多字节超过 32 KiB 的单个叶值证明常规选择为 omitted、索引无续读，却能经显式终态全文路径取得现有传输上限内的相同原文；超出传输上限不虚称可达。
- 参数正反例：同一 completed Run 的显式 `view="detail",response_profile="compat",output_mode="values"` 分别用 `include_full_output` 省略／`false`／`true`，并交叉省略 `output_paths`、传 `null`、传 `[]`；通过统一 gateway 和直接 facade 都执行。只有显式 `true` 且 paths 省略／`null` 才返回与旧全文相同的封存字节；省略开关／`false` 不得返回 payload，`true` 配 `[]`、非空 paths、decision、index/navigation 或错误 view/profile 须在读内容前精确拒绝。两入口都拒绝非 bool 的 `1`、`"true"`，都接受合法的 detail＋compat＋values＋`true`，不因 facade 固定 summary 而误拒。`response_profile="decision"` 与 compat values 的 `output_paths=[""]`、`["/summary",""]` 均须拒绝；任何数组元素为根指针都不能绕过开关。非根字段选择仍可按预算精确读取。queued/running、failed 即使显式传 `true` 也不得返回封存科学输出；historical completed 在同一状态／封存身份门下可读且保持 historical 标记。
- 诊断：测试已持久化 reason 的 4096 字符界、历史可能已截断且不可恢复的尾部、事件投影最多 16 个 details、事件分页与确有 engineering reference 时的 `diagnostic_read`。单个超大已存诊断事件须经显式终态读取保持当前可达性；没有 reference 时不能伪造原件续页，也不能把未保存的错误尾部判为接口回归。
- Contract：至少选用 hypothesis proposal、带 progress 的 revision、独立 reviewer、Transform complete family、human approval、Effect 以及第三方 optional 多端口样本；正例由旧合同可合法构造的请求在新合同同样可构造，反例覆盖 currentness、基数、缺总体目标、漏相关 optional 语义、all-or-none、错误 provider／reviewer、超 max bytes、revision budget。精确拒绝原因与原 preflight/invoke 一致；不运行真实科研来证明准入。
- 逐字段性质：从 compact 展开得到与旧 invoke 调用相关投影等价的结构；单一声明发生受控改变时 compact/full、Schema 和校验同时反映，不可依赖维护者同步两份规则。必须加入一项新／未知字段负例：不能默认把新增约束丢掉仍报 complete，编译／投影需显式处理或保守保留。
- Catalog：默认项严格 ID＋purpose、无端口；多页穷举新旧 V 相等；非零过滤漏项仍能从 index 回退；support 未被 public P1 虚假覆盖；未知维度、游标换过滤／换安装快照、多字节说明、极长 ID、末页、插件缺失／禁用、reviewer／effect adapter 不可用均保留精确行为。与接口目录、Worker 任务工具目录分开测试。
- 编排：同时存在 structuredContent 与 text 仅打印一次；store 后 full text 泄漏的负控制必须能被计量发现；禁止把多页合并打印通过单页验收。重复 describe、重复 status、读取 whole 后再次读子字段列入成本，不只检查服务端。
- 安装：先用隔离状态根与已冻结合成 fixtures 验证 wheel→entry point→open_runtime→daemon/socket→stdio proxy→三工具返回；再按已授权发布流程验证 M7 实际配置、runtime identity、生成指南和服务重载。至少让 running＋`run_status(view="detail")`、running＋`run_list(view="detail")`／混合列表活动态项、根指针混合数组、非法开关类型及缺必要准入字段的负例走真实安装入口；合法终态全文请求亦须走同入口。检查模块 `__file__` 与文件 hash，防止源码 PYTHONPATH 假装 installed。仅 tools/list PASS、哈希相同或手工构造 runtime 不能代替此链。

本次规划不运行上述测试。实施只运行变更范围所需的既有定向测试（如 `test_mcp_response_views.py`、`test_unified_mcp.py`、相关 run/output 测试及 installed entrypoint），以 [scid-change-scope-checks](../../../../.agents/skills/scid-change-scope-checks/SKILL.md) 的实际可用位置为准；不为文档计划启动重测试。部署探针不能用生产 Fig.4 Run 作可变夹具。

### 7.2 度量与分层验收（P0 冻结口径，安全硬门优先）

每个样本记录四层：①服务响应的规范 JSON 字符／UTF-8 字节；②MCP 包装及 text/structuredContent；③真正发给模型的 exec/tool output blocks（包含通用包装、打印投影和错误）；④模型请求使用记录。各层分别报告，不用 chars/4 推导精确 token。

模型侧同时报：每次 input/cached/noncached/output/reasoning；累计差分；未压缩分段首／尾／峰值输入和净增；compaction 数及重读量；调用／重试／等待数。统计单次短状态与整段决策 episode，不能以缓存命中改善替代上下文缩短。无法逐字段 token 化的工具贡献只标近似关联；raw MCP 不在 trace 时不能从 exec 打印反推它的完整尺寸。

验收分三层：**A 安全／等价硬门、B 无损工程改善、C 原生多轮收益**。A 包括 §7.1 全部关键正负例、字段语义／准入等价、冻结派发档案的创建与恢复、现有终态大值逃生口、已持久化且可访问诊断的精确可达性及兼容迁移；任何百分比不能抵销 A 的失败。B 以相同输入与输出边界证明实际缩减、不新增必要读取或漏读；合理的无损增量可独立通过工程验收。C 再测整段模型收益，不能从 B 外推。

复核反馈提供过一次离线机械原型参照：invoke 按其序列化口径由 45,356 降至 39,709 字符，约 12.5%。该结果未保存独立证据文件，**本计划未复现，须在 P0 重放后才能作为基线证据**，也不能与 §2 的 45,671 打印口径直接相减。它足以提示原定 30% 硬门缺少依据；本轮将其降为 stretch，并禁止为追比例删除必要约束或增加必读分节往返。

| 目标面 | B 层实际判据与目标（百分比均非安全硬门） |
|---|---|
| 默认短状态 | 短状态语义及活动态门属于 A；工程尺寸目标为常规响应 ≤1 KiB UTF-8／≤800 字符，Root 可见 output 含包装 ≤1.5 KiB，典型同模型 ≤400 token。超限逐项解释并测量，不裁掉必需身份凑值 |
| run_status 显式结果 | 科学选择值及当前已持久化、可访问的错误字节保持不变，同路径 replay 实际减少非必要包装即可记 B 改善；相对窗口 29,803 字符下降 35% 为待 P0 分解验证的 stretch，不是已证明可达的门槛。必要正文占比须单报 |
| 显式 invoke | 同 13 次样本、同一 envelope、全部必需读取合计确实缩小且通过 A，即可通过 P2 工程验收；现实目标约 10%，以待复现的约 12.5% 原型为参照，30% 为 stretch。未达 10% 如实报告并评估维护成本，不因此删除约束；只改默认 full 而显式 invoke 无改善，不能称 P2 完成 |
| catalog | 两字段、V 等价及分页完整性属于 A；同 V 遍历的总字节不高于现状为 B 判据，降低 15% 仅为探索目标。新增必要完整性元数据若使它增长，应报告取舍，不伪称目录省 token；该窗口 0 次调用无目录收益证据 |
| scid 工具整组 | 同路径计入新增读取后的总可见字符须实际下降才称整组工程改善；相对 90,437 下降 25% 为 stretch，不能反向分摊成每个字段的削减配额；run_status 不重复相加 |

其中 90,437 为日志原打印正文之和，不含 exec 通用包装，候选须用同口径并另报全包装值。仅 B 通过可以报告安全的无损工程缩减，不宣称 C 已通过；某个 stretch 未达不要求回滚一个满足 A/B 的简洁实现。

C 层独立测成对 episode 的可见正文 token、compaction 分段上下文净增长、累计 noncached input、峰值和长尾，计入所有额外请求／失败。原先的 25%／20%／15% 分别保留为探索性收益目标，**不是有证据支持的发布硬门**。推广收益判据须在 P0 用独立基线重复测量确定噪声和关键案例的可接受波动，预先冻结算法／容差再看候选：主要指标为可见正文 token 与分段上下文净增长均出现可重复下降，noncached 无超出预设波动的恶化，关键案例无新增错误调用或科学误读。没有可信改善、样本不足或新增往返抵销缩减时，C 仍未通过，保留工程／pilot 结论；不能看候选后放宽容差。安全的短状态行为与显式无损压缩可按 A/B 独立交付，不用尚未证明的收益数值拖住它们；以 token 收益为理由推广默认表示则须通过 C。

最小原生对照先冻结 8 个 episode，涵盖活动等待、成功决策、失败诊断、proposal/revision、review、Transform、Effect 导航和第三方 optional 端口；每个基线／候选至少两次配对，交错顺序，模型／effort、初始上下文、封存输入、工具代际和可见包装一致，冷／热缓存分别记录。目录标签若另做科学召回收益，沿用原标签计划更充分的 holdout 门槛，不借本轮 8 个样本降低它。开发样本与独立留出反例分开，不看完留出结果再改文案复用。资源不足或 token 数据不可观测只报 pilot，不能称默认推广验收通过。

## 8. 停止、回滚与未关闭问题

下列任一情况阻断相关默认发布：活动 Run 的按名读取或 `run_list` detail／混合列表仍泄露长诊断、恢复、计时或草稿详情；终态显式诊断因此不可读；gateway 与直接 facade 对同一全文请求接受／拒绝不一致，或合法显式 `true` 被固定 summary 误拒；非 bool 开关、非法组合、含根指针的混合数组可绕过门；创建回执或丢失回执后的活动 Run 无法提供原冻结派发档案；现有终态大标量因新预算变得不可读；已持久化且原本可访问的诊断变得不可达；调用约束丢失／未知字段静默删除；审批或历史资格改变；新旧 V 有非预期差异；安装探针未走候选；默认迁移使已知必要客户端无法完成任务。平均节省不能抵销这些安全／正确性负例。真实多轮收益未证明或关键案例出现超出预设波动的成本增长，阻断的是该 token 优化的收益验收／推广，需诊断或撤回相关表示变化；未达 stretch 本身不构成回滚理由，也不自动否定已通过 A/B 的独立增量。

回滚单位是本轮按 dirty 基线保存的投影／指南／安装增量，不是 git HEAD，也不是科研数据库。若紧凑 invoke 有问题，先恢复已知完整的显式合同表示，保留短状态和活动态内容门；若必须整体回退到旧默认，应明确标记本轮未发布／撤回，不对用户宣称目标已达。回滚不删除 Run、Artifact、封存审批、日志或恢复材料，不以旧读取恢复资格。协议游标和合同表示版本在回滚后精确失效；旧客户端迁移说明同步撤回／更新。

待 P0／复审关闭的问题：具体 invoke 必需语义的最小集合及收益；第三方客户端对缺省字段的依赖；宿主是否提供可强制预算的模型可见输出边界；原生日志 token 归属与 compaction 分段算法；当前 daemon 实际加载代际及所有修改文件的安装一致性。它们是待测事项，不是已实现能力，也不应扩展成 search 平台、人工 token 审批或恢复 Fig.4 的理由。
