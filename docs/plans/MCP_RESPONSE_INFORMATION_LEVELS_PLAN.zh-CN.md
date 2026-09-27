# MCP 默认摘要与按需展开子计划 R1

日期：2026-09-16。状态：待独立审查，未实施。
属于 [总计划 R1](HYPOTHESIS_EXPERIMENT_FEEDBACK_PLAN.zh-CN.md) 的工作包 B。
用户要求：各个 MCP 接口不要默认全量展开；通常只给极短的计算结论，有问题时才展开。
本包与假设反馈分开验证，先处理已确认的信息浪费；不改变科学判据或执行授权。

## 1. 所有权与已确认现象

覆盖本仓库发布的 Root MCP、通用 Worker MCP、已安装领域插件 Worker 工具，以及 stdio/daemon/proxy 的实际结果投影。
不修改外部平台自带工具，不以 Root 直接调用 worker_* 来做测试；Worker 验证在隔离测试客户端进行。
MCP 标准工具定义不是科学结果：不能删除模型使用工具所需的参数合同。

已查到的默认展开位置：

- `mcp_root_execution_routes.py`：status 合并 observation，sync 再返回完整 progress；stdout/solver_log 可重复。
  本轮 status 实测序列化 JSON 5,382 字符，两个相同尾部各 2,028 字符。此数值不是 token 数。
- `mcp_root_run_routes.py`：省略 output_paths 时返回完整 sealed_output；还附 bindings、timing、native details。
- `mcp_root_operation_routes.py`：operation_catalog 展开所有操作完整声明；invoke 的 Agent 返回包含完整 Run 结构。
- `mcp_root_instance_routes.py`：scientific_inventory 返回所有最新成果，另嵌入完整 public_operations；缺少页边界。
- `mcp_local_worker.py`：新 assignment 已返回路径/指针，属于应保留的精简能力；旧 assignment fallback 仍可能回传整个工具合同目录。
- `mcp.py`：同一结果同时作为 content.text 和 structuredContent 返回。协议兼容表示不能被 Root 重复展开；不能未经兼容验证直接删除其中一个。

完整原件、日志、收据和科学报告仍按现有机制保存；短摘要只是读取投影，不成为第二事实来源。

## 2. B0：先给所有接口建立静态清单

从当前编译目录和 Root/Worker 工具声明生成一份测试/审查用清单，不新增运行时注册表。
逐个工具记录：所有者、返回类型、默认是否含正文/数组/日志、当前展开入口、授权范围、拟改或保留的理由。
目录先只输出名字/用途，再按候选读取完整声明；不为“审计全接口”把所有合同再灌进 Root。

分类必须穷尽：目录与列表、状态轮询、提交/变更回执、预检、完整合同读取、证据/文本读取、计算、诊断、文件写入及生命周期。
“已精简无需修改”也是有效结论；不能只搜 execution_* 后宣称覆盖所有 MCP。
主计划的预算仍生效；静态清单以代码/声明为主，不为测响应调用生产变更工具。

## 3. 默认与展开规则

### 3.1 共同原则

- 默认 summary：状态、下一步所需的精确语义名字、已观测耗时、关键错误或已有计算结果的少量核心数值、可用展开入口。
- detail：调用者明确请求的原始字段、分页列表、日志片段或正式结果。优先复用 output_paths、diagnostic_after、offset/max_bytes 等已有入口。
- 只有没有合适读取入口的接口才增加 `view: summary|detail`，默认 summary；不新增“每个工具一个摘要 Operation”。
- 不用 AI 生成这些摘要。控制层只投影已有状态及原文片段；科学原因由 Agent 的封存报告提供，计算工具摘要来自实际计算字段。
- 失败摘要保留具体 code、message、path、phase/affected_action、repairable（如已提供）及展开引用。
  多个错误显示一个具体首要错误、总数和后续读取入口；不能统一改写成“字段有误”或 checker_failure。
- 不静默截断 JSON。遗漏须有 omitted/count/next_cursor 或原文 pointer；未知、未采集、空和失败仍可区分。
- 默认正常状态目标不超过 2 KiB；有科学摘要、计算或错误的目标不超过 4 KiB。
  这些是测试与设计目标，不是运行时拒绝结果的硬门槛。不能为凑大小丢掉恢复、授权或纠错必需字段。
- 用户选择 full/detail 或具体原件读取后，允许有界的大返回；“按需展开”不等于再偷偷截掉其实际需要的合同与证据。

### 3.2 Root 接口逐类处理

| 接口族 | 默认内容 | 展开方式与保留边界 |
| --- | --- | --- |
| execution_status / execution_sync / execution_start / cancel / abandon | 执行状态、solver_state、日志观测时间、已观测耗时、收集状态、具体失败及结果名 | named query 增加 view，detail 读已保存 observation；sync 的刷新副作用保持，detail 读取不重新求解；summary 不含 log_tails |
| execution_collect | 已接受/忙/完成/失败、收集字节/文件计数及预算状态 | 详细文件进度在 status detail；不返回产品正文，不改总/单文件/空闲预算或重复请求语义 |
| execution_outputs | 已收集产品计数、首个有界元数据页 | limit/cursor 翻完精确 output_label/artifact_name；不读产品正文，不猜缺失名字；保留目前登记语义 |
| run_status | 生命周期、简短恢复/预算状态、最新具体错误、output metadata；完成时可给 payload.summary 的有界原文片段与原文 pointer | 省略参数不展开 sealed_output；保留 output_paths 选择，view=detail 时取得精确 bound_inputs、tool_timing、native details；view=detail 且不指定 output_paths 才读完整原结果 |
| run_list / execution_list / approval_list / instance_list / lifecycle_events | 精简行、有限页、下一页指针 | 列表不能逐行嵌套完整 status；逐条 detail 读取。已有分页机制优先复用，不再设计新的 cursor 体系 |
| operation_catalog | operation_id、purpose、executor_kind、目录身份及分页 | 增加按 operation_id 精确选择完整声明；不生成另一套目录。Root 必须先读选中项完整 inputs/outputs/review/approval/budget 后才能绑定 |
| scientific_inventory / scientific_current | 当前实例成果的有限元数据页与显式 current 选择；目录入口 | 不再嵌入所有操作的完整合同；可返回精简目录引用。分页可取全，保留历史/资格等事实而不推荐科学动作 |
| artifact_catalog | 单对象身份、schema/kind、parent 数量与读取入口 | detail 保留有序 typed parents、producer metadata；不能以摘要替代精确历史 objective 恢复 |
| instance_current / approval_status / ingest 与选择回执 | 保留必要短状态、语义名和必须交给用户的 URL | 不回显输入全文、审批材料或实例完整目标长文；审批精确 URL 与状态不得省略 |
| operation_preflight | 成败、具体诊断与成功 Agent 的完整 normalized_request | normalized_request 是后续 invoke 的必需机器合同，作为一次性精确请求例外保留，禁止截断/摘要重造；不附额外大报告；编排层只向 Root 展示所需状态并保留该原请求复用 |
| operation_invoke | executor_kind、Run/输出/Execution/Approval 名；Agent 的 agent_type、execution_profile、budget；需要的精确审批 URL | 不附整份 Run 或报告；具体状态与绑定由 named query 展开。失败不隐藏；返回仍足以正确派发并定位唯一结果 |
| execution_capabilities / capability_bind | 可选能力标识及有界说明、绑定回执 | 选中能力的完整约束按需读；不能把省略能力当作不可用，也不能修改安装能力 |
| diagnostic_read | 当前已有 section/offset/max_bytes 的明确诊断读取 | 属于显式展开，保留具体错误和分页，不再次只返一个“查看详情” |

`run_status` 组合优先级要写入工具合同：非空 output_paths 读取指定字段；[] 不读科学正文；
view=detail 只增加元数据，只有 detail 且 output_paths 未指定/为 null 时返回完整 sealed_output。
summary 模式的 completed 摘要保持 selected_output 的原 pointer 语义，标明片段，不能冒充完整封存结果。
Root 最终科学报告仍读所需正式结论、限制和 signal；默认摘要不能取代判断所需证据。

所有列表应有固定页上限和清晰结束标记；在不改变已有序的前提下采用已有稳定语义键/游标规则。
不在本补丁改变 current、Result 发布或查询已有副作用；这些既有语义只做回归，不夹带控制状态整改。

### 3.3 Worker 与领域工具

| 工具类别 | 必须保持/修改的行为 |
| --- | --- |
| worker_open_assignment | 新 workspace 的路径/精确工具合同指针保持；不再次回传整份 assignment。旧 workspace fallback 也提供可访问、同合同的受控引用或按工具精确展开，不能换成新版本合同 |
| worker_submit_result、文件写入/patch/move 等 | 短状态、实际失败字段或收据；不回显整个提交 JSON、文件正文、旧新 diff 或完整 Schema |
| 曲线评分与详细诊断 | 默认返回计算状态、实际计算的核心汇总、异常计数和 calculation_ref/证据文件定位；残差数组、梯度变化点列表、逐案例表、图等保存在既有 tool evidence 中按需读。不给科学总 verdict，不剥夺分析 Agent 的细节/看图权限 |
| TCAD debug/preflight/初始化及执行文件检查/接收 | 返回退出码、超时/故障、具体首要错误、必要证据引用及有限候选页；日志和原执行目录不全展开。接收文件的精确身份、同执行约束保持 |
| PDF/来源文本读取 | 明确属于取证正文读取，可按页/片段返回。若默认 max_chars=131072 导致一次读取过大，降低默认到有界片段并提供精确继续位置；调用者显式请求时保持现有最大能力，不以摘要替代证据 |
| 分析文件发布、证据抽取及其他插件工具 | 收据/manifest 与结果引用默认短返回；若某工具实际已精简则不改。所有大返回必须说明原件位置和可授权读取方式 |

不能为了小响应先把原计算结果压缩再封存：完整计算先按现有机制保存，摘要只影响工具交付视图。
若某结果没有受控完整保存/读取入口，必须在其所属工具实现内补齐这一最小路径后才精简；
不能返回不可访问的服务器绝对路径或要求 Root 绕过 Worker 权限。复用现有 tool evidence、工作区文件与 scoped diagnostic，不新增通用结果缓存服务。
工具的默认返回行为变化应更新所属 ComponentSpec configuration_identity；共享 guidance 若变化，也更新实际 materializer 身份。

### 3.4 传输与内部消费者

- `mcp.py` 的双表示先保留协议兼容；两者都承载同一个精简业务返回。支持 structuredContent 的编排只消费一份；纯 text 客户端仍可用。
- 不对 JSON-RPC 做盲目统一截断，不改工具错误为成功状态，不删除 tools/list 的完整参数 Schema。
- 如果双表示仍被平台重复注入模型上下文，记录实际平台证据再单独决定协议层改法；本轮不凭推测删除 fallback。
- 在 routes/facade 的同一结果投影入口实现 summary/detail，复用共享的少量投影函数；不做新消息总线或 LLM 摘要层。
- 枚举 UI、直接 Python facade、测试与生成客户端等实际调用者。原来依赖完整字段的内部调用显式取 detail 或底层原服务，
  不让 MCP 默认精简改变审批页、轨迹页、归档和恢复的内部数据。
- 只修改读参数模型或纯输出格式；不要向 OperationCallInput 的不可变科学请求混入展示参数，normalized_request 与 invoke 幂等指纹保持原规则。
- 更新目录、工具说明、scheduler 源及生成配置；编译器产生所有投影。已部署客户端需重启刷新合同，不静默恢复同 digest 下不同 Worker 工具行为。

## 4. 文件与实施顺序

| 步骤 | 预期修改位置 | 完成条件 |
| --- | --- | --- |
| B0 全接口清单 | docs/plans/evidence/mcp-response-levels 下的静态清单 | 每个本框架安装接口有分类、改/不改及理由，无遗漏 |
| B1 高频 Root 返回 | `interfaces/mcp_root.py` 与 execution/run/operation/instance/approval routes | 默认短响应、按需完整展开、列表不递归带详情；精确请求和派发参数保持 |
| B2 领域工具与 Worker | B0 确認的大返回所有者：`mcp_local_worker.py`、`mcp_worker_protocol.py`、`curve_score` 与 `tcad_artifact` 相应工具 | 全量证据有可读保存位置，默认只回计算摘要和实际错误；已有精简工具不改 |
| B3 消费者/说明 | `roles/scheduler.md`、受影响的精确 UI/客户端调用点、生成投影 | 旧内部完整读取显式化；Root 不依赖聊天记忆猜参数或结果；无新增审批/执行副作用 |
| B4 隔离验收与审查 | 现有返回、分页、工具合同、历史恢复及安装测试的定向节点 | 下列矩阵通过，独立报告和用户可读前后体积对照 |

本包允许修改接口投影、既有工具的展示/留存和必要消费者；不改求解算法、科学评分定义、执行状态机或访问权限。
B0 发现需要新的存储服务、全局版本机制或权限模型时，记录具体阻断并先修订计划，不现场架构扩张。

## 5. 验收：信息少，但下一步仍做得对

1. 全接口覆盖：清单逐个对应实际发布工具，按类别说明哪些已短、哪些已修；测试通过不能代替该覆盖表。
2. execution status/sync 正常默认无 log_tails；同一执行 stdout/solver_log 相同不重复展开；detail 可读原日志与观测时间。
3. run_status 省略参数不展开 sealed_output/完整 bindings；output_paths 和 detail 能恢复同一原字节字段、null alias、signal 与 recovery。
4. 目录先摘要后按 ID 展开：完整选中合同与原编译声明等价；分页取全且不重复，inventory 不嵌完整 public catalog。
5. invoke 短回执仍能按精确 agent_type/profile 派发；预检 normalized_request 原样 invoke，审批 URL 和人工决定边界保持。
6. 故障负控：超时、求解器失败、提交拒绝、字段错、校验器异常和采集失败均保留真实类别/具体字段；按引用能读完整上下文，不能重新算才能拿日志。
7. 工具证据：评分/诊断的完整记录、关键指标、曲线数组、图和原件在精简前后相同；默认摘要不重写科学数值、不伪造科学结论。
8. 老 workspace/老 Run：能读冻结合同和原输出，精简不使恢复材料丢失；绑定/归档/审批页面仍正常获得所需完整材料。
9. transport：stdio 与 daemon/proxy，以及只读 text 和 structuredContent 客户端，均能解析一次正确响应；无兼容性错误、具体诊断丢失。
10. 一条无聊天历史的实际工作链：目录选择→preflight/invoke→打开→工具计算/保存→提交→Root摘要/指定字段读取。
    既不依赖全量默认展开，也不靠额外填表补回被删信息；允许与工作包 A 的 E2/E3/E7 共用安装环境和纵向链。
11. 精确比较同一对象的默认 JSON 字节与展开次数：已确认的大型默认返回应明显降低；execution 本轮样本目标至少减少 60%。
    同时记录取得同等决策信息的一整段调用总量，避免一次变小却十次往返。无实际 token 遥测时只报告字节/字符，不冒称 token 数。
12. 源码声明、安装包、模型可见参数、返回字段和文档一致；新默认不能只在 Root 的 JavaScript 输出过滤中实现。

沿用总计划串行、2 GiB 子进程树及 180 秒单批预算。不跑全量测试，不并发浏览器/安装/pytest。
默认大小不是新的提交守卫；超目标先定位冗余，必要的错误和合同允许明确例外并在清单解释。

## 6. 与工作包 A 的组合风险

- 摘要隐藏绑定后，A 的历史恢复必须主动读取 exact bound_inputs/parents；不得拿短 summary 代替原证据。
- 目录精简后，A 的新增输入必须能在选中 Operation 的完整声明中被看见。
- 工具详情保存后，A 的原件必须能通过原 evidence 端口显式补绑；只转交 calculation_ref 字符串不等于证据已经传递。
- B 不能给 A 增加 mandatory gates、改 foundation 资格或利用摘要自动判断假设真伪。
- 独立复审绑定本子计划和总计划的两个 SHA-256，分别给两个工作包及组合路径结论。
