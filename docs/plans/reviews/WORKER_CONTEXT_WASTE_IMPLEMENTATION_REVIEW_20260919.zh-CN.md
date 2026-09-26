# Worker 上下文浪费修复实现独立审查

日期：2026-09-19。结论：**本轮源码语义审查未发现阻断性缺陷；工程与真实行为验收仍有未完成边界，不能宣布五项全部关闭。**

## 范围与独立性

审查 [R1 计划](../WORKER_CONTEXT_WASTE_REPAIR_PLAN_20260919.zh-CN.md) 和 [R0 计划独立复审](WORKER_CONTEXT_WASTE_PLAN_R0_REVIEW_20260919.zh-CN.md)，以 `docs/plans/evidence/worker-context-waste-20260919/before/` 为本轮基线。已静态核验 `baseline.json` 中 8 个 before 文件的 SHA256 全部匹配，逐项比较当前文件与 before；没有把 `HEAD=943c4626f8490530e9318eb9fbb409d2670908b9` 之后的整个脏工作树算成本轮修改。另审新增 input reader、native trace 计量扩展及对应测试源码。

采用 `scid-cross-boundary-review` 与 `karpathy-guidelines`。本审查者未修改生产代码，未运行测试、模型、仿真、部署或访问科研实例，未派生其他 Agent；仅写本报告。其他工作者串行测试与安装包验证的结果不冒称为本审查者执行或已验证。

## 跨边界核对

| 路径 | 审查结论与依据 |
|---|---|
| S1：原件 → Workspace → helper → 外层显示 | `input_reader.py` 是独立 stdlib helper，`local_workspace.py` 沿用现有 reader 安装方式。解析后限定 Workspace 内路径，拒绝指向外部的 symlink；不新增权限或资格表。JSON 数字保留词形，文本模式保留原文；JSON 选值明确是重新序列化的值，片段明确标注。完整回复预算计入转义与元数据，连续读取要求版本，变更后拒绝沿用偏移。平台指引保留旧 Workspace 的定向标准库回退，并说明外层聚合预算。测试源码包含长数、多字节、转义键、分页、源变更、路径拒绝与复制安装入口。原生任意 shell 输出仍未被此 helper 强制限制。 |
| S2：launcher → 留存 → 模型摘要/raw 消费 | `local_process_observation.py` 保留原 128 KiB/stream 留存上限，新增单次 launch/saved 计数，避免将累计运行字节当成本次量。分析策略默认 summary，显式 raw 延续 argv 消费；`policy=inherit` 默认 raw 保留原生命令转发。执行 argv、stdin、资源策略、超时、进程组与返回码逻辑未被展示选择替换。摘要只读已规范化日志，按行给错误片段、原文路径与留存覆盖；不把关键词当成根因。`analysis_workspace.py` 的 cat 示例明确 raw。已检查生产调用点与 inherit 回归测试源码。 |
| S3：debug producer → author 提示 → role pack | `debug_summary` 将完整响应写入 `deck/reports/response-*.json`，短响应保留 details/log 路径；角色改为从 details 读取 `/progress/log_tails`、`/log_excerpt`，与 producer 一致。保留无进展不等于失败、不能为省略日志重跑 solver 的限制。新增测试调用实际 producer 和 role_pack，再用 reader 定位日志；其 running/failed/cancelled 合成回放不应表述为真实 timeout 或 VM 验收。角色变更须沿现有 digest 生效，不能覆盖旧冻结 assignment。 |
| S4：冻结 assignment → open 投影 → 复用指引 | `mcp_local_worker.py` 从本次 assignment 的 role 文本计算只读 SHA256，没有缓存数据库、复用准入或 author/reviewer 隔离改动。Codex/dispatch 明确 hash 不证明记忆；首次、失忆、压缩与变更须重读，每轮任务、目标/输入、预算、语言、输出/恢复与 schema/tool 变化独立处理。新增断言只证明本地 open 的 hash 与冻结文本一致，不证明两轮模型行为。 |
| S5：恢复原件 → service → summary/detail | 仅缩小 `mcp_response_views.run_summary` 的 coverage 投影；原 service、恢复 manifest 和 detail 原件不改。保留 saved/omitted 数量、complete/writers_stopped 等原状态，新增已列条数与机械原因类别，未知原因用 other，未推断“完整”。既有 detail 入口包含 `output_paths=[]`。路由测试比较 summary/detail 并验证原件不被修改，包含缺字段、unavailable、多字节长路径和未知原因。损坏 manifest 的实际读取仍归现有 service 分支；投影 fixture 不等于该分支的集成验收。 |

上述修改未发现新增科学必填字段、已读证明、审批绕过、Run/Artifact 身份变更或恢复预算改写。未见需要另建服务、角色或持久读取状态的理由。

## 尚未建立的验收证据

1. **真实行为不等于代码可用。** S1 一对真实独立 review、S4 一对同角色两轮接续未执行；必要信息是否充分、截断/重复是否下降、角色少重印是否同时消费新输入和语言，仍须真实链路证明。不能由 hash/reader 单测或旧 Root A/B 代替。
2. **计量工具的证明范围。** `native_trace_metrics` 去重逐 response usage，拒绝缺少 input usage 或错误模型/强度，保留负增量，导出元数据而非推理/正文，并明确不提供 Worker completion verdict。初审发现的显式压缩/裁剪事件缺失、缓存及输出 usage 缺失不使 valid_usage 变假的两项缺口，已按下述定向补审关闭。valid_usage 仍不能独自证明完整 A/B 合格；真实验收须另核对冻结输入、身份/attach、实际加载指纹及 sealed completion，缺失时保留待验收。
3. **部署与资源边界。** 当前源码尚未部署，本报告不证明控制服务/生成配置加载生效，旧 Workspace 也不自动升级。隔离安装验证由主工作者另行记录。native 内存硬限制未覆盖，不能借用 legacy CLI 的保护声称已覆盖；没有 native 精确 usage 时不得报告精确 Worker token 收益。
4. **定向测试边界。** 本审查阅读了测试定义，没有执行测试。S2 大日志、错误定位、raw/inherit，S3 保存详情及 S5 短/详投影具有直接对应的离线检查入口；最终通过与资源消耗必须引用主工作者实际结果。未实现或未实测的计划矩阵应逐项保留，不以本次“未发现阻断”替代。

本结论适用于本轮源码差异和上述检查路径；不是科研结论、运行资格、部署通过或真实 Worker 成本改善证明。


## 同日定向补审：计量缺口

仅复核 `probe_request_usage.py:native_trace_metrics` 与 `test_native_worker_usage.py` 两处补丁，未运行测试或扩展生产代码审查范围。结论：**两项初审计量缺口在源码层面已补齐，未发现新增阻断。**

- 新增 recognized `compacted` 及 `event_msg` 下压缩/裁剪 marker 的时间和类型记录，不导出 payload 正文；明确“未观察到 marker 不证明没有裁剪”。原先负输入增量仍原值保留，未改写为节省收益。测试源码增加 compacted 事件可见及其私密正文不导出的断言。
- 对 `cached_input_tokens`、`output_tokens` 逐项要求整数；缺失或类型无效加入 issues，使 valid_usage 为 false。测试新增缺少 cached usage 的拒绝断言；output 字段使用同一校验循环，已静态核对，但未声称具有独立执行的 output 缺失测试。

主工作者告知离线回放和隔离 wheel 安装已完成，生成配置测试也已更新；本次补审未检查这些结果文件，不将该告知提升为独立验证结论。真实 A/B、部署加载及 native 内存硬限制仍未验收，初审其余边界继续有效。
