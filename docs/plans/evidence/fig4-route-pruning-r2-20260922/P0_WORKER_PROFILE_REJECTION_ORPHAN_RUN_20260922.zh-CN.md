# P0：Worker profile 拒绝后遗留 queued Run 并阻塞同 Operation

- 发现日期：2026-09-22
- 严重度：**P0**
- 状态：**已复现、未修复**
- 当前所有者：控制层 Run/Worker attachment 生命周期
- 现场 Run：`fig4_hypothesis_redesign_20260922_1`

## 现场事实

1. `science.hypothesis.propose.v1` 创建成功，Run 冻结 profile 为 `model=gpt-6-Astra`、`reasoning_effort=high`。
2. 平台 Worker 通过 `worker_identity` 返回 `model=gpt-6-astra`、`reasoning_effort=high`。
3. `worker_attach` 接受真实 thread ID，并返回 `state=attached`。
4. Worker 在打开 assignment 前被统一 MCP 拒绝：`DiagnosticError: Worker platform model/effort do not match the bound Run profile`；诊断为 `tool_rejected`、`phase=tool_execution`、`repairable=false`。
5. Worker 未打开 assignment、未读取科学输入、未生成草稿、未提交科学结果。
6. 拒绝后 `run_status` 仍报告 `queued`，无 failure reason 或 diagnostic event。
7. 相同科学输入、仅规范化模型名的新请求被拒绝：`local_run_creation_failed` → `RunSlotBusy: this compiled Operation already has an unopened or running Run` → `UNIQUE constraint failed: runs.operation_digest`。
8. 当前公开接口没有 Run cancel/detach。原 deadline `2026-09-22T12:58:02Z` 已过，之后再次调用 `run_status(response_profile="poll", output_paths=[])` 仍返回 `queued`、无 reason/diagnostic；status 查询不会回收该 Run，而错误 Worker 又在进入 `Runs.open` 前被 gateway 拒绝，因此它可永久占槽。

## 根因边界

这是两个相连的控制缺陷，不是科学失败：

- Run 创建/配置层没有将模型标识规范化为平台身份使用的 canonical form，导致仅大小写不同也形成不可运行的冻结 profile。
- 已 attach Worker 遭遇不可修复 profile admission 拒绝时，没有原子地终结 Run、解除 attachment 并释放活动 `operation_digest` 槽。

唯一槽本身仍是必要并发不变量；P0 不是要求删除 slot gate，而是要求失败生命周期正确释放它。历史正常并发触发的 `RunSlotBusy` 记录不被本缺陷改写。

## 必须保持的不变量

- 不删除或改写失败 Run；保留冻结 request、profile、thread attachment、诊断和时间。
- 不把 Worker admission/平台失败当作科学结论。
- 不允许同一 compiled Operation 同时存在两个真实活动 Run。
- 不允许通过直接改数据库、复用 Root 凭据或忽略模型/effort 身份来恢复。

## 修复验收条件

1. 模型 ID 在实例设置、invoke 冻结、platform metadata 与 Worker identity 比较前使用同一 canonicalization；显示名不参与身份相等性。
2. attach 后的不可修复 profile mismatch 必须在一个控制事务中：记录精确诊断、将 Run 转为 `failed`、解除活动 attachment 并释放 operation slot。
3. repairable 的 attach 前拒绝可以保留 queued；不可修复的 attach 后拒绝不得等待完整科学 deadline。
4. 终态后同 Operation 的新不可变请求立即可创建；旧 Run 仍可审计，且不能作为 `resume_from`/`draft_from` 科学来源，除非真实保存工作存在并通过既有门。
5. 增加真实统一 MCP/metadata 回归：大小写 alias、真实 mismatch、attach 后拒绝、并发 slot、不产生双 Run、精确错误与 deadline 竞争。
6. 显式受权的 Run cancel/detach 只可作为补充恢复面，不能代替上述自动终态语义。

## 当前处置与限制

本轮已形成一个**未部署且不完整**的本地候选：`ExecutionProfile` 和 gateway/线程复用使用 canonical model ID；已 attach 的新不可修复 mismatch 会记录失败并释放槽；model/effort 正负例和槽释放测试通过。候选尚未处理部署前已存在、已过 deadline 且绑定死线程的 queued Run；还需在控制服务启动/显式生命周期协调点完成过期活动 Run reconciliation，不能让 `run_status` 查询偷偷变成写操作。

当前安装 `/opt/scidiscovery-m7/site` 不含该候选，服务仍运行旧版本。没有直接访问或修改控制数据库，不宣称 P0 已修复。

Token：Root、科学 Worker 与相关平台拒绝路径的精确 token 均不可观测，未估算；Worker 未打开 assignment，不能把平台调用开销冒充科学 Worker token。
