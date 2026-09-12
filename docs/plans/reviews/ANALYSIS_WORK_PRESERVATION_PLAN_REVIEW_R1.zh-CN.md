# 分析工作保全与跨轮交付计划 R1：独立工程审查

日期：2026-09-12。结论：**REVISE**。

R1 已准确吸收原生命令证据，直接处理绘图前未落盘、缺库后整批重算及重试超过剩余预算，
并把恢复入口缺失降为未证实。主方向可实施，无需改写科研流程。批准实施前需补齐下面三项：
停写与删除的顺序、恢复文件与现有发布校验的兼容、无证据的统一 180 秒计算硬限制。
不要求新增科研角色、状态机、全平台执行器或全量测试。

## 1. 审查范围与输入

本审查是独立工程计划审查，不是科研 Operation。未修改目标计划、生产源码或其他工作者文件。
使用 `scid-cross-boundary-review`、`scid-find-simplifications` 与 `karpathy-guidelines`；
核对当前工作树源码，不把历史审计的 PASS 或风险描述当成当前实现事实。

仓库：`123/scidiscovery-e5.2`。基线 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。
工作树含大量先前修改，故本结论针对读取时的工作树；HEAD 不能单独标识此次代码输入。
目标计划为 285 行。以下均为完整文件 SHA256：

| 输入 | SHA256 |
| --- | --- |
| `docs/plans/ANALYSIS_WORK_PRESERVATION_AND_DELIVERY_PLAN.zh-CN.md` | `88e3d3130bd63d3f2cf8dd029d6876f703cb557c3336e52b9f572338fa9a58ba` |
| `docs/plans/evidence/operation-validation-reaudit/ANALYSIS_TIMEOUT_ROOT_CAUSE.zh-CN.md` | `2478a072a138096536c2b299bbb847839cf1db472050c84808b776a9c7d12ea0` |
| `docs/plans/evidence/operation-validation-reaudit/ANALYSIS_TIMEOUT_TIMELINE.json` | `072a9828321e44d79dcefe0013955a1de5e7aaaa7fabb9ed41d124ca06ee0f57` |
| `docs/plans/evidence/operation-validation-reaudit/RESPONSIBILITY_PLACEMENT_POSTINSTALL.zh-CN.md` | `7dc169e5b0b88880158ce58e0c2754d21669e89f444ab4961ecc0d60efee1029` |

另读取架构中文文档、科学设计宪章与约束登记，以及下述接口两侧和相关恢复测试。
没有读取生产科学草稿或原平台完整会话；历史事件依据上述限定证据，源码结论依据当前文件。

## 2. 阻断项

### B1 · P1：只复现停止顺序，尚不足以保证活跃写入不会被清理

- **计划位置**：第 86–96 行，尤其第 88–90 行；第 118 行；第 259–262 行。
- **源码位置**：`src/scidiscovery/artifact_agent/service/runs.py:588` 的失败 CAS，
  `runs.py:644` 的 snapshotter 调用及 `runs.py:657` 的 discard；
  `src/scidiscovery/artifact_agent/service/local_workspace.py:353` 的目录移动与 `:394` 的递归删除；
  `src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py:55` 的同步失败调用。
- **实际边界**：现有失败命令先把 Run 置为 failed，随即快照并删除隔离目录。
  Local backend 的这条路径没有停止原生 Python 子进程。失败 CAS 能挡住 Worker MCP 后续写入，
  不能让已启动的原生命令退出。P2 只承诺启动脚本自身超时时清理进程组，不能覆盖提前中断、
  外层启动脚本被终止或仍使用直接原生命令的路径。
- **可达失败情景**：程序已有一个完整单元，仍在计算下个单元；Root 记录失败时快照枚举结束，
  程序随后原子写入另一个完整单元，接着 discard 删除原目录。每个被读取文件在读取时都稳定，
  因而“读取期间变化检查”也可能全部通过，但新写入仍不在恢复包内。状态可显示保全成功。
  此情景不需要恶意 Worker，也不依赖先前未证实的恢复字段问题。
- **最小修正**：在计划中选定本轮 Local 分析的顺序保证：失败 fencing 后，未确认原生写入停止时，
  保留原工作目录或 quarantine，不以当前快照允许删除；停止确认后再执行既有快照和清理。
  无法取得停止确认时明确保留 pending，不承诺完整保全。可以复用现有失败/pending 路径，
  不需要新增 Run 状态或全平台进程注册表。具体停止手段可在实现时选择，但这个保留条件必须先写清楚。
- **所需验收**：秒级活跃写入夹具通过真实失败入口，在枚举完成后写出下一单元；证明该字节最终可恢复，
  或原目录确实保留且没有误报完整保全。另覆盖停止启动脚本时子进程仍存在的路径；不能只测子进程自然退出后失败。

### B2 · P1：把原生日志和所有普通 scratch 文件送入现有 seal，会使正常故障反而无法恢复

- **计划位置**：第 74–80、86–96 行；第 112–124 行；第 239–244 行。
- **源码位置**：`src/scidiscovery/artifact_agent/service/local_workspace.py:289` 在自定义 snapshot
  路径仍调用 `_validate_publication_content`；`:685`–`:689` 在恢复验证中再次按扩展名识别并校验；
  `:710`–`:736` 拒绝主机绝对路径、未声明二进制与非 UTF-8 文本。
  `src/scidiscovery/artifact_agent/service/runs.py:673`–`:678` 把快照失败留为恢复 pending。
- **实际边界**：快照 hook 没有绕过发布检查。R1 承诺保存 stdout/stderr 和 scratch 普通文件，
  但没有说明这些真实文件如何满足现有 seal 与 verify 两侧的格式及内容约束。
  在 hook 中仅指定 media_type 也不足以保证恢复可读，因为 verify 会重新推断类型。
- **可达失败情景**：P2 记录的 Python traceback 含 `/home/.../scratch/analysis.py`，或一个导入生成了
  `scratch/__pycache__/...pyc`。二者均为普通文件，也很小；按 R1 整体收集会使整个恢复包失败，
  连已经完整写好的 CSV/JSON 都无法通过现有 draft_from 交付。原目录可能得以保留，
  但“真实新 Agent 仅凭 assignment/草稿接续”的完成条件仍达不到。
- **最小修正**：先定义本轮可恢复文件的窄范围和诊断策略，例如可恢复脚本/CSV/JSON/PNG，
  启动脚本生成的日志在写入时将任务绝对路径替换为相对路径，标明日志规范化；
  自动字节码缓存可禁写或明确排除。未能安全封存的原文件保留在原目录并报告覆盖不足，
  不能伪称完整，也不能因为一个缓存文件丢掉全部可用结果。
  若要求原始日志逐字节跨 Agent 恢复，则需明确另行设计私有恢复的兼容边界；
  不应在实现时顺手放宽正式发布的路径、秘密或二进制检查。
- **所需验收**：实际 Python 异常产生 traceback，加一个正常的字节码缓存/不支持文件；
  经 seal、verify、discard、draft_from、新 assignment 全链验证完整数值单元可交付，
  覆盖不足与保留原目录如实报告。不得仅用不含真实路径的手写短日志做正例。

### B3 · P2：统一 180 秒硬上限会引入与已证实根因无关的失败条件

- **计划位置**：第 109–122 行，尤其第 116 行；第 135、201–206、245 行。
- **源码位置**：`plugins/tcad_artifact/tcad_artifact/result_analysis.py:549` 已声明 900 秒 Run 上限；
  `src/scidiscovery/artifact_agent/service/runs.py:171` 从该合同生成截止时间；
  `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:258` 已交付剩余秒数。
- **证据边界**：时间线证明的是 400/420/560 秒的独立命令上限没有随 Run 剩余时间收缩，
  不是证明所有科学上不可分的计算单元都能在 180 秒内完成。约 58 秒中央计算和 301/354 秒整批计算
  都不能推出这个普遍阈值。用户没有指定统一的 180 秒硬上限或 120 秒提交余量。
- **可达失败情景**：一个仍符合绑定方法的完整计算单元需 220 秒，Run 尚余 600 秒，
  即使预留 120 秒也足够交付，但观测脚本会在 180 秒杀掉它。
  Worker 被迫继续拆分不可分单元，或绕开观测脚本恢复直接原生命令，反而削弱新方案。
  这里是设计反例，不声称已证实历史拟合有这样的不可分单元。
- **最小修正**：去掉统一 180 秒硬限制，利用已经存在的“本次计算超时”参数，
  将实际执行上限截到本 Run 剩余预算减提交余量；由 Worker 根据实测耗时选择工作单元和请求上限。
  180 秒可以是首次小批试运行的建议值；120 秒可作为说明依据的初始提交余量，
  无需新增 Schema 字段、配置系统或把建议阈值变成科学可实施性的条件。
- **所需验收**：缩短夹具同时证明“请求超时超过剩余预算时被截断”和
  “请求超过建议的小批时间但仍在剩余预算内时可以完成”。不能只验证较大任务一律被拒绝。

## 3. 审查边界与保留结论

R1 的阶段原子落盘、计算/绘图独立入口、绑定方法变化后局部重算，以及安装后全新 Agent 仅凭
assignment/恢复文件接续的验收可以保留。原生结果不要求虚构 comparison_keys，遥测不成为提交条件，
输入身份诊断仍在原 guard 分支，均未重引入输入/输出职责混淆。没有额外非阻断修改要求。

本次仅运行只读文件检索、源码阅读、git 状态/HEAD 与 SHA256 计算。
**未运行** pytest（包括定向和全量）、恢复故障注入、真实 Agent、安装/构建、求解器或拟合计算；
未调用控制面或 worker 工具。所列失败情景是基于当前代码路径的审查结论，不冒充已执行的复现。
R1 尚未实施；本报告不是源码修复或现场验收通过记录。
