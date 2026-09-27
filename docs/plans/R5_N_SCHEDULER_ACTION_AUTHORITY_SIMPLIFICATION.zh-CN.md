# R5-N 调度行动权威简化

## 状态

已实施；独立跨边界终审通过，阻断项为0。

## 决策

具体调用哪个 Operation 由交互式调度 Agent 决定。科学 Worker 只输出封存的科学对象、结构化结论
和非约束性建议；控制面只验证精确输入、来源、独立审查、修订边界、权限、人工审批与副作用条件。

废弃 `next_action_kind`、`accepts_actions` 和诊断结果中的 `recommended_task_mode`，删除全部 Root
匹配、准入和路由逻辑。三个字段暂时保留为可解析的兼容元数据，不具有控制权威；动作词缺失、错误
或自造均不能使科学结果提交或下一步 Operation 失败。

Operation ABI 保持13，不因删除错误路由权威而使全部旧 Run 集体退休。字段仍按旧形状进入
Operation 身份；只有输入用途、提示或科学合同确实改变的 Operation 才产生新摘要。这里不增加
版本映射、双读或迁移状态机。

## 保留的边界

- `CriticReview.disposition` 等字段仍是科学结果的一部分，负责表达问题性质，不包含 Operation id；
- `run_status` 只在单个 Run 完成后返回其已校验、已封存的科学载荷；`run_list` 不批量加载载荷。
  因而调度 Agent 能依据科学内容判断，又不能读取运行中草稿或绕过封存边界。读取前还必须匹配
  当前编译 Operation 的版本和摘要；旧合同只返回 `contract_retired`，不返回旧载荷或旧
  `scheduler_signal`。当前 Run 的结构化对象位于 `sealed_output`，有界交接位于同一响应的
  `scheduler_signal`；
- `handoff.next_actions` 仍可记录给调度 Agent 和人的建议，但不是命令或准入凭据；
- 废弃字段仍可随旧输出解析和保存，但调度提示、准入代码和后续行为选择必须忽略它们；建议、假设
  和缺失输入只保留数组数量上限，不为非权威文本增加逐项内容门禁；
- `change_request` 表示直接修订所依据的精确独立审查；`review_signal` 表示一个非通过审查作为其他
  科学行为的精确来源。二者只接受 `revise/blocked/inconclusive`，拒绝 `pass`，且只影响来源与审查
  证明，不选择后继 Operation；每一个此类输入都必须被同次调用中的精确被审查对象消费，不允许
  游离信号或只凭 schema 冒充审查；`change_request` 还必须与唯一 `revision_base` 成对声明；
- 调度 Agent 只能从启动期唯一编译目录选择 public Operation，并必须使用统一 preflight；
- 同一公开目录在生产者条目上投影最小 `review_edge`，包含审查 Operation、审查输入端口、被审查
  输出端口和可接受 verdict；旧 `requires_independent_review` 布尔值只作兼容摘要，不形成第二目录。
  public 生产者的 reviewer 必须同为 public 且当前运行后端可用，否则生产者也不进入 public 视图、
  preflight 也失败关闭；
- Root 可以显式调用 public Operation 及被选 public 行为所需的 support Transform，但 `internal`
  Operation 在 preflight/invoke 入口由控制面拒绝，不能只依赖调度提示；
- 修订次数、无进展检测、current、人工审批和外部副作用门不变。

## 文档所有权

| 角色 | 文件 | 处置 |
|---|---|---|
| 当前规范 | `docs/ARCHITECTURE*.md`、设计宪章、`AGENTS.md`、`roles/scheduler.md` | 同步调度权威 |
| 当前协议 | `docs/role-result-json-protocol-v1.md` | 保留废弃字段形状，删除机器路由语义 |
| 历史决策 | `HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_REVISION.zh-CN.md` 及其审查 | 保留原证据，标明已被本决策部分取代 |
| 增量修订计划 | `R5_N_INCREMENTAL_REVISION_RUNTIME_PLAN.zh-CN.md` | 只改已失效的路由依赖说明 |

## 验收

1. `next_action_kind`、`accepts_actions`、`recommended_task_mode` 仍可解析，但生产控制路径不存在基于
   它们的匹配、准入或路由；
2. ABI 保持13；与本次科学合同无关的部署版 Operation 摘要保持不变；
3. 假设批判的结构化处置与 handoff verdict 仍一致，调度器可以自主选择实验、证据或假设操作；
4. 调度器能从完成 Run 的 `run_status.sealed_output` 读取结构化科学结果，运行中状态和批量列表不
   暴露载荷，旧 Operation 合同的完成结果只报告 `contract_retired`，同时不暴露旧 handoff；
5. 非通过的精确独立审查仍能通过 `change_request/review_signal` 证明修订或替代行为的来源，`pass`
   审查不能冒充变更请求；
6. 实验方案、TCAD Deck 等单一修订场景不再要求 Worker 命名后继操作；
7. 公开目录的 `review_edge` 足以让调度 Agent 从同一目录选择并绑定审查者，无需角色表或硬编码；
8. public 审查边不悬空：非 public 或当前不可用 reviewer 会在编译/公开目录/preflight 失败关闭；
9. 每个 `change_request/review_signal` 都绑定同次调用中的精确被审查对象；游离信号、通过审查和
   无 `revision_base` 的 `change_request` 均被拒绝；Root 也不能调用 internal Operation；
10. 废弃 action hint 和普通建议文本无论缺失或内容欠佳都不阻断科学结果提交；
11. 完整目录、修订、review edge、33 项约束和分批全量回归通过；既存生产文件数门单独如实报告；
12. 独立审查确认没有第二路由表、固定阶段图或针对 Fig.4 的特例。

## 受限内存测试纪律

当前 WSL 上限为 16GB，本轮验证不得再把安装态矩阵、全量测试和独立 Codex 审查并发叠加：

- 不使用并行 pytest；普通测试按相关文件分批，每批使用独立进程，退出后确认内存释放；
- `installed_environments` 会构建多组 wheel/虚拟环境，所有依赖它的安装态测试合并为一个独立批次且
  只执行一次，不在每个定向批次中重复触发；
- 测试期间暂停独立审查进程；测试完成并确认无遗留子进程后再启动审查；
- 每批使用 6GB 进程地址空间上限并记录最大常驻内存；开始前若可用内存不足 8GB则不启动；
- 不再直接执行整个 `tests/operations` 或整个仓库。最终结论由分批集合覆盖同一文件清单，逐批记录
  结果；既存生产文件数门仍单独如实报告。

审批页面现场决定仍只用于调试通路，不构成可读性验收；`UI-READ-002` 继续保持 P1 未闭合。

## 实施与终审结果

- 三个废弃字段只保留为可解析兼容数据；生产控制路径不存在基于其值的匹配、准入或路由；
- 一个真实本地 Run 携带自造值 `not a registered operation` 仍正常封存并进入独立审查；
- 默认 TCAD 目录43个 Operation 中33个摘要与当前部署完全一致，其余10个对应真实提示、输入用途或
  科学合同变化；
- 分批定向回归为64、30、34项通过，追加兼容纵向11项通过；测试峰值均约100MB；
- catalog 为762行、operations 包为2149行，继续满足既有765/2150上限；既存生产文件数门
  `184 > 159` 单独保留为历史裁剪问题，不归因于本轮，也未通过提高上限掩盖；
- [独立终审](reviews/R5_N_SCHEDULER_ACTION_AUTHORITY_INDEPENDENT_FINAL_REVIEW.zh-CN.md)
  结论为 PASS，无阻断，可收口。
