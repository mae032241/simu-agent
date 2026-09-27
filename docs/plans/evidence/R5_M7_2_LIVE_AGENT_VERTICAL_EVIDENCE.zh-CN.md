# R5-M7.2 真实智能体纵向回归证据

日期：2026-09-02

状态：首轮第 5 项终审 FAIL 后按软隔离完成返工；全新独立终审 PASS，M7.2 已完成

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 本记录的范围

本文件是绑定当前候选、持久状态和真实运行事实的审计记录，不是新的运行入口。当前规范仍由架构
文档、33 项约束、一个启动期编译目录和当前代码共同拥有。

本轮验证根位于：

```text
deliverables/m7-live-generic-20260902-01/
```

验证只接受根控制面报告的 Run 状态、封存 Artifact、工具活动和精确审查关系。独立 Codex 进程的
退出码与聊天只作为运行信号，不作为科学结果。

## 2. 实时脚本迁移

L2、L3、L4 三个持久实时探针已从旧 Task 接口迁到当前最小 Run 主干：

- 删除已不存在的 `task_token_secret`；
- 删除 `RootToolFacade(tasks=None)`；
- 删除平台初始化的 `worker_socket`；
- TCAD 证据检查当前运行时不存在旧 `tasks` 权威；
- 通用 L3 探针最终检查作者域工具收据、作者与审查者完成态、精确审查 subject 和父链。

迁移没有恢复旧 Task 服务、Worker broker、第二状态机或第二 Operation 目录。

## 3. 历史失败路径

本轮没有覆盖或恢复失败 Run。持久账本依次保留了以下边界：

| Run | 状态 | 证明的边界 |
|---|---|---|
| `author` | failed | 启动期未加载动态角色；重启后由 Root 明确记为超时失败 |
| `author_recovery` | failed | 精确角色存在，但父会话没有其专属 Worker MCP |
| `author_exec` | failed | 独立进程复用只读 `CODEX_HOME`，会话未初始化 |
| `author_exec2` | failed | assignment 与领域工具可用，但输出工作区不在原生补丁可写根内 |
| `author_exec3` | failed | `--add-dir` 没有让原生补丁获得兄弟工作区写权限 |
| `author_exec4` | failed | 外层 Codex 沙箱内再启动 bubblewrap，合成挂载锁不可写 |
| `reviewer_exec` | failed | 审查 Operation 绑定了输入，却把原生代码能力声明为 `none` 且没有输入读取工具 |
| `author_exec6` | failed | 一次通用 CLI 重编译丢失验证插件路径，Worker 的精确 Operation 摘要不一致 |

这些失败均未产生被 Root 接受的候选。`author_exec5` 首次证明独立作者进程可完成受控提交，但其
产物属于修订前的插件编译代际；新审查合同对它的 preflight 返回
`input_producer_contract_changed`，因此没有跨代际复用。

`author_exec7` 与 `reviewer_exec3` 随后完成了精确科学闭环，但当时没有持久化 launcher provenance；
独立终审据此拒绝把终端输出升级为“两个独立 Codex 进程”的可复算证据。它们保留为 completed 历史
Run，当前资格结论改由带原子启动收据的全新 Run 承担。

## 4. 用户授权的独立 Codex 测试启动器

为避免每次安装角色或 Worker MCP 后重启交互父会话，本轮在测试层增加：

```text
scripts/run_compiled_codex_worker.py
```

它不是 Root 的第二调度器，只承载已由 Root 排队的一个编译 Operation：

1. 读取启动期生成的项目配置和精确角色配置；
2. 校验父投影与角色投影的 Worker 命令、参数、工具和环境完全一致；
3. 只启用目标 Worker MCP，显式禁用 Root 与其他 MCP；
4. 不把 Run 名、Artifact 名、控制身份、令牌、摘要或科学内容放入命令和提示；
5. 使用临时私有 `CODEX_HOME`，只复制登录凭据并在进程组退出后删除；
6. 默认仍使用 `workspace-write`；只有检测到当前已经运行在 Codex 外层 Linux 沙箱时，显式
   `--externally-sandboxed-debug` 才关闭嵌套 bubblewrap；
7. 为每个独立进程设置有界地址空间，并由启动器轮询整棵 Worker 后代进程树的聚合 RSS；本轮实跑
   两者均使用 4 GiB 上限，低于 8 GiB 约束；
8. 子进程只负责 `worker_open_assignment`→领域/原生能力→`worker_submit_result`，完成判定仍属于
   Root。

该启动器不改变默认产品调度路径，不把提示词白名单宣称为生产级强隔离，也不增加 Run、租约、恢复
或 Artifact 状态。

## 5. 审查者输入能力缺口及修正

首次独立审查进程能打开 assignment 和写结果，却不能读取已绑定的 `source_table` 与
`csv_observation`。根因是插件自己的 `OperationSpec` 同时满足：

- `native_shell="none"`；
- 只注册生命周期与文件写能力；
- 审查任务又要求核对两个不可变输入。

这不是 Root 应补一个通用旁路。最小修正是在该审查 Operation 中明示本地原型需要
`native_shell="inherited_prototype"`。编译器据此投影任务内代码工具；没有增加中央注册表、领域
特判或新的读取协议。Hardened 后端仍不会因此获得原生 shell；将来若要求该审查者在 Hardened 执行，
应由插件声明专用只读 Worker 工具。

独立复审确认这项能力声明修正 PASS，并只放行全新 Root 服务、全新 Run 和独立 `codex exec` 复测。

## 6. 当前通过的真实闭环

根控制面在同一活动 ResearchInstance 下重新列出科学清单和 `public` 目录，并对每次调用执行同一
不可变请求的 preflight 与 invoke。

### 6.1 作者

当前作者 Run：

```text
author_exec8
agent_type = op_blind_csv_observe_v1_e5c14175e00d
state = completed
candidate_accepted = true
output = author_exec8.output
```

独立 Codex 进程真实调用了 `worker_open_assignment`、插件注册的 `worker_csv_summarize` 和
`worker_submit_result`。Root 活动账本存在 `tool_succeeded:worker_csv_summarize`，科学结果来自封存
Artifact，不来自进程聊天。

### 6.2 独立审查者

当前审查 Run：

```text
reviewer_exec4
agent_type = op_blind_csv_review_v1_995e51d375c6
state = completed
candidate_accepted = true
output = reviewer_exec4.output
```

这是另一个全新独立 Codex 进程。它从 `worker_open_assignment` 返回的唯一任务根读取
`assignment.json`、两个已声明输入和结果 Schema，计算被审对象的精确摘要，写入声明输出并通过
`worker_submit_result` 完成。Root 报告封存交接结论为 `pass`。

### 6.3 精确关系检查

`scripts/l3_live_review_probe.py status` 对持久状态完成最终检查：

```json
{
  "author_registered_tool_succeeded": true,
  "author_state": "completed",
  "distinct_launcher_invocations": true,
  "launcher_receipts_verified": true,
  "review_has_exact_subject_parent": true,
  "review_is_exact_and_passing": true,
  "review_state": "completed",
  "worker_transport": "independent_codex_exec"
}
```

机器可读投影保存在 `deliverables/m7-live-generic-20260902-01/final-evidence.json`。它证明审查结果绑定
当前作者产物并具有精确父关系，不只是 JSON 格式通过。

## 7. 自动化与独立审查

新增的启动器聚焦测试覆盖：

- 默认 `workspace-write`；
- 外层沙箱调试模式必须显式开启；
- 只启用精确 Worker MCP，Root 与兄弟 MCP 禁用；
- 命令不携带 Run/Artifact 元数据；
- 父配置与角色配置漂移时失败关闭。

启动器、收据原子发布、fresh L3 接线、审查合同和 Codex 平台配置组合回归：

```text
20 passed
```

加入 Run 生命周期不变量后的本次范围回归为 `31 passed`，差异格式检查通过。两份最终收据只包含
角色、投影摘要、调用时间、退出码、资源/沙箱模式、目标 Worker server 和 Worker 工具名；不包含
工具参数、结果、Run/Artifact 标识、工作区路径或科学内容。当前持久账本为 `5 completed / 8 failed`，
没有 queued 或 running Run。

最终独立实现复审已明确 PASS，报告见
[`R5_M7_2_GENERIC_CODEX_EXEC_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`](../reviews/R5_M7_2_GENERIC_CODEX_EXEC_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md)。
该结论只放行 M7.2 的 TCAD 作者→领域调试→独立 Deck 审查子链，不把通用子链的
自动化和运行事实扩大为 M7.2 或 R5-M 整体通过。

## 8. 仍然有效的边界与下一步

- `inherited_prototype` 是外层沙箱加编译提示约束，不是逐 Operation 的生产级强隔离；
- 独立启动器是本轮用户授权的测试承载方式，不是 Root 默认调度路径或第二状态权威；
- 通用作者→审查者闭环通过不等于 M7.2 整体通过；
- TCAD v8 作者→领域调试→独立 Deck 审查以及修订后的精确新审查已通过独立终审；
- 下一步验证 Effect 精确 UI 决定与执行收集、失败/超时恢复；
- M7.3 安全负例、M7.4 物理报告、M7.5 全量回归与双独立终审仍未放行。

因此当前结论是：独立 Codex 进程已经解决“为测试反复重启交互父会话”的工程摩擦，并真实完成一条
通用 Operation 闭环；M7.2 继续进行，不宣称 M7 或 R5-M 完成。

## 9. TCAD 首次收据闭环失败与边界修正

`deliverables/m7-live-tcad-20260902-01/` 曾由四个相互独立的 Codex Run 完成初始作者、初始审查、
修订作者和修订审查，最终审查为 `pass`；但其 launcher receipt v1 会在兄弟 MCP 配置刷新后失去
历史可验证性，所以不能作为当前闭环证据。

receipt v2 已改为验证启动时冻结的安全投影。随后使用全新根
`deliverables/m7-live-tcad-receipt-v2-20260902-01/` 启动的首个 TCAD 作者却读取了框架仓库与历史
交付物，并尝试用文本占位伪造 `device.tdr`。父调度器立即中断该进程，Root 将该 Run 明确记为
`failed`；没有输出 Artifact，也没有推进 current。独立审查确认失败处置正确，但拒绝立即重试：
提示词禁止不是可审计的任务内文件边界。

## 10. 原生边界、内存事故与 receipt v4

为关闭该真实旁路，启动器增加了局部、可审计的 trusted-local 边界：

- SessionStart 激活原生 Hook；
- Pre/PostToolUse 只允许编译 profile 声明的 Bash、`apply_patch` 和 `view_image`，且路径必须落在
  `worker_open_assignment` 返回并绑定的精确工作区；
- 越界违规为 sticky，Worker MCP 代理会在转发 `worker_submit_result` 前失败关闭；
- 收据只记录守卫是否激活、是否绑定工作区、允许/拒绝计数与提交门结果，不记录命令、路径或科学内容。

一次用于探测真实 Hook 的嵌套 Codex/code-mode 调用已经出现宿主不稳定；随后错误地重试并可能与
审查进程叠加。原有 `RLIMIT_AS` 只约束单个进程，不能限制多个 Codex 后代的总占用，最终导致 WSL
失去响应并由用户强制重启。这是执行方式错误，不归因于科学任务。

重启后停止所有嵌套探针，并加入整棵 Worker 后代进程树的 4 GiB 聚合 RSS 熔断、根退出后代清理和
失败收据。cgroup v2 在当前会话中只读、用户 systemd 不可用，因此该轮询熔断被诚实标为本地可信
原型保护，不冒充生产级硬隔离。

官方 Codex 0.151 Hook 契约已直接固化为测试，不再通过真实模型探针猜测字段。启动器、Hook、提交
竞态、进程树、TCAD 本地工具和插件配置的低内存串行组合回归为 `27 passed`。独立审查先以五个
阻断项判定 FAIL；返工后复审 PASS，报告见
[`R5_M7_2_TRUSTED_LOCAL_GUARD_INDEPENDENT_REREVIEW.zh-CN.md`](../reviews/R5_M7_2_TRUSTED_LOCAL_GUARD_INDEPENDENT_REREVIEW.zh-CN.md)。

本次 PASS 只允许在全新根上严格串行启动一个 4 GiB 聚合预算的 TCAD Worker。它没有恢复失败 Run，
也没有证明 TCAD 作者或审查科学内容已经通过。

## 11. 启动器裁剪与 TCAD receipt v7 失败闭环

继续实跑前重新检查了上一节的 trusted-local 守卫。Hook、命令白名单、Worker MCP 代理和提交门实际
构成了第二套权限/运行协议，偏离了“启动器只解决测试进程承载与内存事故”的边界，因此已从当前
实现删除。历史失败和审查报告原样保留，但不再代表当前设计。

当前 `scripts/run_compiled_codex_worker.py` 只承担：

- 校验并启动精确编译角色；
- 只启用该角色对应的 Worker MCP，禁用兄弟 MCP；
- 串行运行一个独立 Codex 进程；
- 设置单进程地址空间上限，并监测整棵后代进程树的聚合 RSS；
- 以 4 GiB 为本轮上限，超限终止进程组并写最小启动/内存收据。

它不解释原生命令、不代理 Worker 调用、不决定提交是否成立，也不记录或声称实际工具调用。Run
完成、TCAD 调试成功和封存结果资格均由现有控制服务核验。裁剪后的启动器聚焦测试为 `9 passed`；
与 TCAD 本地工具及运行插件组合为 `18 passed`。独立架构复审确认该启动器不再是第二运行时，并
允许在严格串行、4 GiB 上限下执行全新 TCAD 链路。

v7 历史候选根为：

```text
deliverables/m7-live-tcad-receipt-v7-20260902-01/
```

四个独立 Codex 调用形成了以下不可变链路：

1. 初始作者真实使用原生读写和 `worker_tcad_debug_run`，提交带合格预检证明的项目；
2. 初始 Deck 审查者针对该精确项目返回 `revise`，指出入口只有文件段、缺少 Grid 闭合和求解结构；
3. 修订作者绑定一个真实 `device_grid` Artifact，声明输入槽、补全最小 SDevice 入口，重新调用
   `worker_tcad_debug_run` 并提交新的合格预检项目；
4. 最终 Deck 审查者只读取修订项目、能力和实验计划，返回 `pass`。

过程中保留而不覆盖的失败/不合格尝试包括：receipt v5 的过重原生守卫循环，以及 receipt v6 在
预检后继续修改声明导致最终源码没有对应合格证明。后者促成一条最小角色规则：任何源码、声明、
元数据或交接修改都会使之前调试结果失效，作者必须在提交前重新运行允许的调试模式。这是 Worker
行为约束，不是新增控制状态机。

`scripts/l4_live_tcad_revision_probe.py status` 最终输出：

```json
{
  "all_runs_completed": true,
  "distinct_launcher_invocations": true,
  "initial_review_is_exact_revision_request": true,
  "launcher_receipts_verified": true,
  "old_review_not_inherited": true,
  "revision_debug_tool_succeeded": true,
  "revision_has_exact_parents": true,
  "revision_preflight_qualified": true,
  "revision_review_has_exact_subject_parent": true,
  "revision_review_is_exact_and_passing": true,
  "revision_review_verdict": "pass",
  "worker_transport": "independent_codex_exec"
}
```

机器可读结果位于
`deliverables/m7-live-tcad-receipt-v7-20260902-01/final-evidence.json`，四份启动收据位于同一根的
`launch-receipts/`。随后独立终审判定该摘要是假阳性：修订增加了 `Physics`、`Solve` 和首次求解，
精确作者合同要求先对同一最终源码完成 `preflight`，再完成 `initialization`；v7 只有 `preflight`。
静态 reviewer 的 `pass` 不能补回缺失的运行层检查，因此 v7 不关闭 M7.2 第 2、3 项。

最小返工没有放宽控制门：SDevice R-2020.09 的 `initialization` 映射到手册支持的
`sdevice -i <commandfile>`；调试服务为 initialization 写入与最终源码摘要绑定的控制报告；M7 探针
必须验证该精确报告，且新增“preflight 不可冒充 initialization”和“旧源码报告不可复用”的负例。
v7 及其错误机器摘要保留为失败证据，正确结论由全新根、全新 Run/Artifact 和全新复审承担。

## 12. TCAD receipt v8 机器闭环候选

全新候选根为：

```text
deliverables/m7-live-tcad-receipt-v8-20260902-01/
```

本轮严格串行运行四个相互独立、每个聚合内存上限为 4 GiB 的 Codex 进程：

1. 初始作者产生带合格预检证明的最小 SDevice 项目；
2. 初始审查者针对该精确项目返回 `revise`，要求闭合原生网格输入并补全最小求解结构；
3. 修订作者绑定真实 `device_grid` Artifact，新增独立 `init.cmd`，并在同一份未再修改的最终源码上
   依次完成合格 `preflight` 与 `initialization`；
4. 最终审查者只读修订项目、执行能力与实验计划，逐项覆盖 realization manifest 后返回 `pass`。

`scripts/l4_live_tcad_revision_probe.py status` 对根控制状态、封存输出、工具活动、源码绑定报告、
精确父链和四份启动收据复算得到：

```json
{
  "all_runs_completed": true,
  "distinct_launcher_invocations": true,
  "initial_review_is_exact_revision_request": true,
  "launcher_receipts_verified": true,
  "old_review_not_inherited": true,
  "revision_debug_tool_succeeded": true,
  "revision_has_exact_parents": true,
  "revision_initialization_qualified": true,
  "revision_preflight_qualified": true,
  "revision_review_has_exact_subject_parent": true,
  "revision_review_is_exact_and_passing": true,
  "revision_review_verdict": "pass",
  "worker_transport": "independent_codex_exec"
}
```

机器可读投影位于该根的 `final-evidence.json`，四份启动收据位于 `launch-receipts/`。针对 v7 假阳性
所增加的精确负例与 TCAD/运行插件组合回归为 `22 passed`；Python 语法、差异格式检查通过，实跑后
系统仍有约 14 GiB 可用内存。

未参与实现的独立终审者从持久 Run、封存 Artifact、实际 Job 参数、调试归档、源码摘要、父链和启动
收据重新复算，结论为 PASS、阻断项 0。报告见
[`R5_M7_2_TCAD_V8_INDEPENDENT_FINAL_REVIEW.zh-CN.md`](../reviews/R5_M7_2_TCAD_V8_INDEPENDENT_FINAL_REVIEW.zh-CN.md)。
据此只关闭 M7.2 第 2、3 项。保留的非阻断限制是：底层 transport 为确定性测试夹具而非真实
Sentaurus；初始化证明当前依赖保留的 Run 工作区；修订 handoff 的后续动作文字已滞后。第 4、5 项、
M7.2、M7 和 R5-M 均未完成。

## 13. Effect、环回审批与执行收集候选

本项没有借用 TCAD 或旧 R5 的大型组合夹具。测试层增加一个只复制单个冻结文本文件的最小已安装
插件 `m7_effect_fixture`，其公开 Effect 为 `m7.fixture.frozen-copy.v1`。插件通过同一个安装入口进入
启动期目录；执行适配器只能由该目录声明的 `runtime_factory` 装载。探针不覆盖运行时目录，也不直接
实例化适配器。

冻结身份与结果为：

```text
catalog digest   = 94366f3f8a098dc682be1262c6cfdb01d9d5bcf2dd2a0f94656834a5a2b7da80
operation digest = 8f685138cacdf07c3228b1b705a8e293b268b3370cfeab0dfb5547e0899400da
output sha256    = 702f1be3326ee07765cc21c46c881eef9fd0a2c0095f70107d503c847a85708b
```

持久运行根为 `deliverables/m7-live-effect-20260902-01/`。首次启动产生唯一 Execution 和唯一 pending
Approval，并证明决定前 `execution_start` 被拒绝。随机端口进程退出后，审批本身仍 pending，但一小时
访问凭证已过期。恢复没有重新 invoke 或创建对象，而是选择同一 ResearchInstance，从冻结
`ApprovalRequest` 复核精确 subjects，并在自有 `localhost:8766` 环回服务上展示同一审批首页。

用户随后明确授权仅在当前 M7 调试阶段由父调度者代审。代审仍完整经过真实 UI 协议：审批首页
GET 200、同一审批的访问刷新 POST 303、精确 review GET 200、携带页面 Origin/CSRF/nonce/confirm 的
决定 POST 303；没有直接调用 ApprovalService 写接口或修改数据库。无秘密运输收据位于该根的
`approval-ui-transport-receipt.json`。这项调试授权不改变产品的人类决定策略。

UI 决定密封后，探针才显式调用 start、sync 和 outputs。最终 Execution 为 `collected`，唯一输出字节、
大小、媒体类型和摘要与冻结 manifest 完全相同。`final-evidence.json` 的全部门条件为真，包括：

- 安装态目录与运行态目录摘要相同；
- 唯一 invoke 建立执行与审批；
- 审批 subjects 精确；
- 审批前启动被阻止；
- 恢复的是同一 pending Approval；
- UI 决定后才显式启动、同步和收集；
- 输出与冻结 manifest 一致。

已安装插件、Effect 生命周期和运行时绑定聚焦回归为 `4 passed in 40.28s`，语法和差异格式检查通过。
恢复路径的事前独立审查为 PASS、阻断 0，见
[`R5_M7_2_EFFECT_RESUME_INDEPENDENT_REVIEW.zh-CN.md`](../reviews/R5_M7_2_EFFECT_RESUME_INDEPENDENT_REVIEW.zh-CN.md)。
实际执行结果的独立终审为 PASS、阻断 0，报告见
[`R5_M7_2_EFFECT_INDEPENDENT_FINAL_REVIEW.zh-CN.md`](../reviews/R5_M7_2_EFFECT_INDEPENDENT_FINAL_REVIEW.zh-CN.md)。
据此关闭第 4 项。该结论不证明人工浏览器可用性、真实远程副作用或失败恢复；第 5 项及 M7.2 仍未
完成。

## 14. 一次失败 Run 的持久恢复候选

全新持久根为：

```text
deliverables/m7-live-run-recovery-20260902-01/
```

在实跑前，独立审查发现恢复请求的 preflight 只检查“失败且有草稿”，而 Operation 摘要和精确输入
要到 invoke/schedule 才检查。该跨层断裂没有用补丁理由绕过：`RunService` 现在用唯一纯规则同时
校验 failed+draft、Operation digest、有序输入引用和 draft digest；Root preflight 调用同一权威，
schedule 在 `BEGIN IMMEDIATE` 内冻结实际输入后再次调用。错输入负例证明 preflight 拒绝、Run 列表
不变且没有目标 binding。共享校验独立复审为 PASS，报告见
[`R5_M7_2_RECOVERY_PREFLIGHT_INDEPENDENT_REVIEW.zh-CN.md`](../reviews/R5_M7_2_RECOVERY_PREFLIGHT_INDEPENDENT_REVIEW.zh-CN.md)。

随后按事前独立审查通过的最小方案严格串行执行：

1. 一个独立确定性进程通过真实 stdio Worker MCP 打开排队 Run；
2. 调用该 Operation 注册的 `worker_csv_summarize`，写一个 Schema 合法草稿，但不 submit，以退出码
   73 结束；
3. Root 读取 running 状态和精确 `last_activity_at`，用比较交换把原 Run 记为 failed；
4. 失败草稿被隔离为只读 recovery draft，未登记 Artifact、无 output/signal/completion receipt；
5. 错输入恢复在 preflight 阶段拒绝且零 Run 写入；
6. 相同 Operation、指令和完整输入以 `resume_from` 创建不同标识的新 Run；
7. 只启动一个聚合内存上限 4 GiB 的独立 Codex；它重新调用注册分析工具，并最终通过
   `worker_submit_result` 完成；
8. 新进程重开运行时后，从数据库、恢复清单、实际只读草稿、启动收据和封存 Artifact 复算关系。

`final-evidence.json` 的机器断言全部为真：原 Run 保持 failed，新 Run 精确指向原 Run；操作版本、
摘要、指令和 `inputs_json` 一致；实际 recovery draft 的路径、大小和 SHA-256 与 source manifest
一致并在文件/字节上限内；新 Run 真实调用注册工具；最终 Artifact 通过 CAS 验证且父引用精确；重启
后没有 queued/running Run。启动器峰值进程树 RSS 为 278828 KiB，未触发 4 GiB 限制。

本次实跑同时保留一个不能掩盖的观察：恢复 Codex 尝试对 Worker MCP 执行资源列表时得到
`unknown JSON-RPC method`，其后经历 6 次输出格式拒绝才完成。运行事实证明恢复草稿被精确挂载、只读
且明确标为 `scientific_evidence=false`，但没有证明 Agent 实际读到了草稿内容。无秘密观察记录位于
`live-worker-observation.json`。终审必须判断这是否阻断“恢复可用性”的主张。

Run 恢复、独立启动器和审查策略组合回归为 `23 passed in 4.97s`，语法和差异格式检查通过。当前
只声称“一次恢复 Run 的时间、文件、字节和进程内存有界”；`LimitsSpec.max_attempts` 尚未由
`RunService` 消费，因此不声称任意恢复链的总次数有界。

独立终审结论为 **FAIL，阻断项 2**，见
[`R5_M7_2_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md`](../reviews/R5_M7_2_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md)：

1. 真实 Codex 没有可审计的恢复草稿读取事实；当前正例只证明相同输入重新执行成功；
2. `max_attempts` 没有被运行服务消费，恢复链不存在硬上限，不满足 `RES-002`。

另记录非阻断问题：失败工作区的只读候选在 quarantine 中残留副本。本轮审查结束后按用户要求暂停，
未开始修复、未进入 M7.3；第 5 项和 M7.2 均未关闭。

后续计划决策（不改写上述实跑与终审事实）：当前可信本地原型改用默认软隔离，不再以新增 MCP
读取协议或逐次读取收据关闭该阻断。下一次候选将允许 Local Agent 直接读取 assignment、Schema、
输入和 recovery draft，并用草稿独有测试标记证明实际续作；恢复链仍须消费现有 `max_attempts`
形成简单硬上限。具体完成门由
[`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`](../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md)
第 1.1 和 12.2 节拥有。本证据记录继续保持 FAIL 状态，直到新实现、新实跑和新独立审查完成。

## 15. 默认软隔离恢复候选

上一节的失败候选与终审结论保持不变。本轮在全新持久根重新验证修正后的最小恢复闭包：

```text
deliverables/m7-live-run-recovery-soft-20260902-01/
```

实现只做两项产品改动：Local 后端把任务工作区内的原生文件、代码和图像能力作为所有 Agent 的默认
基线；既有 `LimitsSpec.max_attempts` 由 `RunService` 在同一恢复根的整棵后代树上计数。没有新增文件
读取 MCP、读取收据、恢复实体、恢复状态机或后台进程。可选 Hardened 后端保持原能力投影。

事前实现独立审查为 PASS，阻断项 0，见
[`R5_M7_2_SOFT_RECOVERY_IMPLEMENTATION_REVIEW.zh-CN.md`](../reviews/R5_M7_2_SOFT_RECOVERY_IMPLEMENTATION_REVIEW.zh-CN.md)；
父进程与审查者各自完成一轮 `62 passed` 聚焦回归。

真实测试严格串行：故障进程先打开原 Run、调用 `worker_csv_summarize`，把每次随机生成且只存在于
草稿的 `recovery-draft-only:*` 标记写入 handoff，然后不提交并以 73 退出。Root 用状态和
`last_activity_at` 比较交换记录失败；恢复 Run 保持完全相同的 Operation、指令和输入。随后只启动
一个聚合内存上限 4 GiB 的真实 Codex。

该 Codex 从 assignment 得知恢复目录，先读取输出 Schema，再定位并读取
`recovery-draft/result.json`；它重新调用注册的 CSV 工具，在首次 `worker_submit_result` 前同时：

- 保留草稿独有随机标记；
- 写入只存在于测试 Schema、而不在提示、输入或草稿中的必填常量；
- 保留领域工具重算得到的输入摘要。

它曾把恢复目录本身作为文本文件执行一次 `sed`，收到普通的“目录不可读为文件”命令错误，随后用
`rg --files` 找到实际草稿。这不是输出提交或 Schema 拒绝；持久 `run_activity` 中
`output_rejected=0`，因此最终格式不是从控制面拒绝诊断反推而来。

重启 Runtime 后，`status-recovery` 的全部机器断言为真，包括：原 Run 仍为 failed、恢复 Run 为
completed 且身份不同、恢复草稿不是 Artifact、草稿标记进入封存 signal、Schema 常量进入封存
payload、领域工具在新 Run 中成功、输出父链精确、无活跃 Run。完成一次恢复后，从失败根再次
preflight 和 invoke 均因总次数上限被拒绝，Run 列表与 binding 不变。

启动收据显示唯一 Codex 进程正常退出，峰值进程树 RSS 为 291576 KiB，未触发 4096 MiB 上限。机器
断言保存在该根的 `final-evidence.json`，启动投影保存在
`launch-receipts/recovery_launcher_receipt.json`。当前只形成新的机器候选；M7.2 第 5 项仍须独立终审
明确 PASS 后才能关闭。

独立终审已从持久数据库、草稿和封存字节、Artifact 父链、活动账本、生成 profile 与启动收据重新
复算，结论为 **PASS，阻断项 0**。旧阻断 B1（未证明使用草稿）和 B2（恢复链无总次数上限）均已
关闭；报告见
[`R5_M7_2_SOFT_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md`](../reviews/R5_M7_2_SOFT_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md)。
据此关闭 M7.2 第 5 项及 M7.2 整体，并放行 M7.3。`SEC-002` 继续保持已知问题，quarantine 副本和
`NativeToolPolicy.shell` 命名只作为非阻断债务记录。
