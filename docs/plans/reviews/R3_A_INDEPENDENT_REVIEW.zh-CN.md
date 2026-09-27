# R3-A 独立架构与实现复审

> **历史审计状态说明：派发结论已失效。** 本报告记录当时对 R3-A 候选的审查，不改写其
> 原始判断；但其中“独立 Codex 进程作为当前版本默认派发路径”的放行，已被当前规范权威
> `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 26 节及 R3 派发纠正决定
> 明确撤销。R2 已冻结的首版默认路径仍是 `task_prepare_dispatch → spawn_agent`，独立进程仅作
> 下一版本加固基座。本文其余合同审查内容仅具有绑定当时实现候选的历史参考价值，不能单独
> 证明当前 R3-A 已通过。

日期：2026-08-28  
审查对象：`baseline/8765-codex@404aeb1` 之上的当前共享工作树；由于 R0—R3 尚未形成独立
提交，本报告按当前工作树和可复核的本地运行证据判断，不把未跟踪文件误写成某个提交的差异。  
复审结论：**通过，允许进入 R3-B。**

本结论表示 R3-A 已形成一个可执行、失败关闭、默认由精确独立 Codex 进程承载的通用 Agent
Operation 最小基座；它不表示六个真实科学角色已经迁移，也不表示框架总复杂度已经下降。后两项
分别是 R3-B 和 R3-D 的完成责任。

## 一、R3-A 完成门复核

### 1. 单一编译权威与失败关闭

- 插件仍从唯一入口 `scidiscovery.plugins` 装载，编译结果为唯一 `CompiledCatalog`；没有新增角色、
  工具、上下文或输出子注册表。
- Agent Operation 的 prompt、输入端口、主输出、集合项、集合级规则、上下文规则、修订规则、
  Worker 工具、网络权限和预算均由同一个 `CompiledOperation` 投影。运行期按 authority digest
  复核，不能按 role/profile 回退。
- 编译期会实际构造完整 `TaskOutputSpec` 投影；不能被当前 Task 模型表示的声明以稳定
  `agent_task_projection_invalid` 拒绝，而不是推迟到任务创建或 Worker 提交时抛出普通模型异常
  （`operations/catalog.py:417-425`）。
- Agent 输出端口必须声明 `semantic_contract`；该合同由与运行期 validator 相同的已安装组件资源
  投影为 Worker 可见的 `x-scidiscovery-semantic-constraints`，缺失则以
  `agent_semantic_contract_missing` 失败（`operations/catalog.py:195-203,257-258`；
  `operations/invoke.py:238-251`）。

判断：符合“一次注册、一次编译、唯一派生”的 R3-A 完成门。

### 2. 首审六类阻塞已闭合

| 首审阻塞 | 当前证据 | 结论 |
| --- | --- | --- |
| 修订 scope 只投影不执行 | Operation 主输出在 codec/port validator 后解析 `StructuredRevision`，逐项调用 `operation_is_within_scope`；越界路径失败。编译器还要求修订基端口恰好 `min_items=max_items=1` 且 `usage=revision_base`（`tasks.py:1578-1620`；`catalog.py:209-224`） | 闭合 |
| Operation 仍进入旧科学特判 | figure evidence、handoff binding、device parameter 特判仅在 `task.operation_authority is None` 时运行；Operation 路径只执行 compiled codec、项、集合和上下文组件（`tasks.py:3689-3704`） | 闭合 |
| 启动期不验证 Task 输出可表示性 | catalog 编译 Agent Operation 时构造完整 Task 输出投影，并把投影异常转换成稳定编译错误（`catalog.py:417-425`） | 闭合 |
| Worker 看不到跨字段语义 | 每个 Agent 输出端口必须有 semantic contract；Schema 扩展与运行期 validator 解析自同一 compiled component（`invoke.py:238-251`） | 闭合 |
| 精确独立 Codex 不是默认 | `task_prepare_dispatch` 遇到 `operation_authority` 必须调用 `CodexTaskDispatcher`，缺 dispatcher 直接失败；不会返回 `spawn_agent` fallback（`mcp_root.py:1996-2013`） | 闭合 |
| 工具、附件 codec、虚假资源字段不闭合 | Worker router 按精确 `operation_agent_type` 只解析该 Operation 的工具；集合 codec 实际执行且要求 canonical bytes；未实现的 native tool、额外 Agent resource、自定义 workspace 和旧 `memory_mb` 承诺均被删除或编译期拒绝 | 闭合 |

复审没有再发现同类重复权威。旧 role/profile 路径仍服务尚未迁移的 8765 角色，但 Operation 任务
不能进入它；这属于迁移期双实现共存，不是新路径的 fallback。

### 3. 精确 Codex Worker、工具与网络边界

- 父调度器配置不再注册 Operation Agent 或 Operation Worker MCP；父进程只保留调度工具。Operation
  任务由 Root 启动精确、独立的 Codex 子进程（`platforms/codex.py`；
  `artifact_agent/service/agent_dispatch.py:30-127`）。
- 子进程配置的 `enabled_tools` 只包含任务生命周期工具和该 compiled operation 登记的 Worker
  工具。R3 首版明确不授予 Codex 原生 shell 和 `view_image`；`NativeToolPolicy.issue()` 只接受
  `shell="none"`、`view_image=False`，否则以 `native_tool_policy_unsupported` 编译失败
  （`operations/spec.py:98-105`）。这比“提示词要求不用”更强，且没有夸大当前能力。
- 所有读写、网络和领域能力因此必须作为显式 Worker 工具注册。router 用精确
  `operation_agent_type` 过滤工具，不把另一个 Operation 的工具暴露给当前 Worker
  （`mcp_worker.py:308-323`）。
- 注册工具 handler 的公开 ABI 只接收已校验 request；不再把 `TaskService`、token、worker id 或
  session 上下文交给插件代码（`mcp_worker.py:390-410`）。插件仍是受信任安装代码边界，但它不再
  因方便接口获得完整控制面对象。
- 网络工具必须同时声明 restricted network policy；TaskService 对精确工具、方法、HTTPS 域名和
  请求预算授权并原子扣减，初始请求及每次重定向均在发出 I/O 前检查。无网络工具或声明不一致在
  编译期失败关闭。
- `ExecutorRef.resources` 及 prompt 的传递资源如果超出唯一 prompt，会以
  `agent_resources_unsupported` 编译失败；没有“写进 authority 但运行期未物化”的资源。
- `WorkspaceContract` 当前只接受真实存在的默认 `inputs/output/scratch` 三目录；自定义目录在编译期
  拒绝。此收缩符合最小原型原则，未来只有在真实 materializer 和隔离协议同时实现后才能扩展。

判断：精确独立 Worker 已是 Operation 默认路径，不再是可选实验。进入 R3-B 后，真实科学角色
必须沿用这一路径；不得重新启用父权限继承或仅靠提示词限制工具。

### 4. 真实进程与秘密清理证据

最新持久证据位于 `deliverables/debug-evidence/r3-exact-agent-run12/`。其
`qualification-report.json` 的九项检查全部为真：

- Root 使用精确独立进程，任务完成；
- 已注册领域工具真实调用成功；
- 原生 shell、网络/apps、未声明 analysis 工具均不可用；
- 兄弟任务秘密未泄漏；
- attempt 秘密已撤销；
- 完成结果与受控文件校验内容精确一致。

报告记录的事件摘要
`a48c622030eb4a6e1c18898dccbf5be491189f95118ce602acb2185ba251e7e5` 与实际
`codex-events.jsonl` 一致。事件中可见真实 `worker_fixture_inspect` 以及受控写入、校验和 finalize，
未出现 shell command、`worker_run_analysis` 或 web search 调用。Codex 对旧 web-search 配置键产生的
弃用提示是诊断噪声；顶层 `web_search="disabled"` 且没有搜索事件，不构成能力暴露。

运行时秘密放在 daemon 管理的临时
`codex-workers/<task>/attempt-N` 目录；复制的 `auth.json` 权限为 0600，dispatcher 和 worker 的
异常、超时及正常退出路径都会清理。daemon 启动清理只接受经验证的 task/attempt 叶目录并拒绝
不安全路径或符号链接。run12 持久证据中不存在 `auth.json`、`task.secret`、`approval.secret` 或
`dispatch.capability`。

部署入口已将 `--codex-worker-runtime-root`、`--codex-auth-file`、`--codex-executable` 从安装模板接到
daemon；可执行文件要求绝对路径，认证文件要求 0600。因此该路径不只是测试夹具，也已接入当前
部署入口。

run12 只证明 R3-A 当前实际承诺的进程、工具和文件生命周期边界；它不证明 TCAD 科学质量或六个
科学角色的语义正确性。这些不应被伪装成 R3-A 已完成的能力。

## 二、33 项架构约束不退化判断

仓库没有把“33 项”实现成一个逐项编号的可执行检查器，因此本报告不伪称运行了“33/33”脚本。
按现行计划中的约束族逐一映射，其结果如下：

| 约束族 | 复审判断 | 证据 |
| --- | --- | --- |
| Artifact 不可变、内容寻址、来源和父链 | 不退化 | Operation 输出仍走现有受控文件、Artifact 注册与父链；没有旁路写入科学结果 |
| Task/attempt/deadline/finalize 唯一权威 | 不退化 | 没有新增 OperationRun、第二任务表或第二完成状态；dispatcher 只驱动并观察现有 Task 生命周期 |
| current、qualification、审批、Execution 唯一权威 | 不退化 | R3-A 未复制这些状态；人工决定和真实副作用继续使用原有 UI/Execution 门 |
| 科学内容归 Worker，控制面不增加科学判断 | 不退化 | compiled validator 只执行插件声明的结构、闭包和上下文准入；没有加入候选排序、科研阶段 DAG、科学图或结论生成 |
| 单一插件入口和单一 compiled catalog | 通过 | prompt、输入、输出、修订、工具、网络、预算从同一 authority 派生；启动期关闭不可表示声明 |
| 最小上下文和最小工具授权 | 通过其当前承诺 | 输入按精确端口绑定；工具按精确 Operation 过滤；默认无网络、无原生 shell、无额外静态资源、无自定义 workspace |
| Worker 可见合同与运行时校验同源 | 通过 | semantic contract 强制存在并投影；运行期从同一 compiled component 执行 validator |
| 领域规则不泄漏核心 | Operation 新路径通过 | 旧 figure/device parameter 特判只服务 legacy；新路径必须由插件显式组件声明 |
| 故障恢复、CAS、幂等和 authority 不漂移 | 不退化 | 精确 dispatcher 复用现有 attempt；authority digest 参与恢复检查；秘密撤销、启动清理和失败路径有负例 |
| 人工判断与外部副作用边界 | 不退化 | 本轮没有把聊天、测试成功或 Agent 输出转换为审批；真实执行仍需原有专门授权 |

据此，33 项约束所覆盖的全部约束族均未见退化。特别是本次重构没有新增科学实体、流程状态机、
资格权威或控制面科学判断，仍符合“控制面只做最小准入与治理”的目标。

## 三、复杂度与迁移顺序

三个冻结核心文件为：

```text
operations/spec.py      315
operations/catalog.py   444
operations/invoke.py    428
合计                   1187
```

分别满足 315 / 450 / 430，总计不超过 1195 的当前预算。代码没有通过巨型 OperationSpec 类吸收所有
行为；spec 仍是声明，实际能力由注册 codec、validator、projector、tool handler 和现有 Task/Worker
生命周期实现。

但是，**当前不能声称框架总复杂度已经真实下降**：新 Operation 路径与尚未迁移的 legacy
roles/profiles 同时存在，TaskService 也暂时保留 legacy 科学特判。此时的复杂度是受控的迁移期
增量，而不是最终简化成果。

计划中的合理责任边界现已统一为：

```text
R3-A：新 Operation 路径可执行、失败关闭、没有 role/profile fallback
R3-B：迁移六个真实角色及变体，roles/*.md 退化为纯 prompt 资源
R3-D：确认无消费者后删除 legacy role/profile 装配和旧科学特判
```

因此 roles/runtime 的物理删除不是 R3-A 阻塞项；在 R3-B 迁移前删除反而会破坏现有角色。但
R3-B 和 R3-D 必须以“替代一处、删除一处”为门，不能无限保留双轨并把 1187 行核心预算冒充整个
系统已经变轻。

## 四、独立测试与边界覆盖

本轮在最终共享工作树独立执行：

```text
git diff --check
通过

python -m compileall -q src tests/operations
通过

pytest -q tests/operations
79 passed in 31.74s

pytest -q
110 passed in 37.96s
```

除合同正例外，测试已包含下列真实边界负例：

- 修订越界、错误 revision base usage 和非单项基对象；
- Agent 缺语义合同、Task 输出不可表示；
- 未实现原生工具、额外静态资源和自定义 workspace；
- 另一个 Operation 的工具不可见；
- 网络初始 URL 和重定向在 I/O 前被拒绝，请求预算原子消耗；
- 精确 dispatcher 启动失败、超时和秘密清理；
- daemon 不安全清理路径；
- 父调度配置不注册 Operation Agent/MCP；
- output/collection codec、项/集合/context validator 和受控 finalize。

因此本轮不再属于“只测合同自洽”。但真实科学边界仍未覆盖：architecture fixture Agent 不能替代
evidence extractor、critic、experiment designer、TCAD author/reviewer、diagnostician 的真实语义
合同和任务效果。这正是 R3-B 的验收对象，而不是继续阻塞 R3-A 的理由。

## 五、进入 R3-B 后的非阻塞硬门

1. 每迁移一个真实角色，必须证明其 prompt、全部输入、输出变体、修订、工具和网络从 compiled
   operation 唯一派生；不得恢复 role/profile fallback。
2. 对每个角色至少运行一条真实正例和一条最小授权负例；TCAD 编码角色必须真实调用已注册领域
   工具，不能用架构 fixture 代替。
3. 发现首版确需原生 shell、图像或额外静态资源时，应先实现可执行、可审计的 materializer/权限
   协议再放开编译器；不得把权限藏回 prompt。
4. R3-D 删除 legacy role/profile 和旧科学特判前，不得宣称总体简化完成。
5. `deliverables/debug-evidence` 是本地审查证据，不是发布资产；提交前应按发布范围处理，但不得
   删除当前用于复核的 run12 证据或把其中秘密带入版本库。

以上是下一阶段的验收门，不是当前阻塞项，也不要求增加新科学实体、注册表或状态机。

## 六、最终结论

**通过，允许进入 R3-B。**

首审六类阻塞以及复审中追加发现的 handler 过权、虚假资源、自定义 workspace、修订基端口和原生
工具承诺问题均已用最小修改闭合。Operation 新路径现在具备单一注册、启动期失败关闭、运行期
同源派生、默认精确独立 Worker 和现有 Task/Artifact 生命周期复用；33 项约束族未见退化。剩余
双轨复杂度必须通过 R3-B 迁移和 R3-D 删除兑现，但不再阻止进入 R3-B。
