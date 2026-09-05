# R4-A 第四轮独立复审报告

状态：独立复审完成（通过）  
审查对象：当前共享工作树、第三轮唯一阻塞的返工、第 12/13 轮真实 Codex 持久证据  
审查方法：跨边界闭环审查、最小复杂度审查、原始会话与持久状态逐摘要核验、聚焦与全量测试独立复跑

## 结论摘要

第三轮指出的唯一阻塞已经闭合。编译后的 Operation Agent 在成功封存后只能以固定非科学信号
“已完成受控提交。”结束；父调度会话只以固定信号“子智能体已返回；受控状态待控制层查询。”
结束。父调度规则同时明确把 child completion chat 视为不可信传输信号，禁止复制路径、内部身份、
科学摘要、payload 或 verdict。真实科学结果仍只通过既有 Task 状态和封存 Artifact 取得，没有新增
消息总线、聊天收据、结果状态或平行权威。

第 13 轮真实证据与上述设计一致：author/reviewer 两个 child final 和两个 parent final 均逐字等于
各自固定信号；父会话只执行一次 `spawn_agent` 和一次等待；外层受控程序在 author 返回后查询
`task_status`，取得已完成 author Artifact，再以该 Artifact 创建独立 reviewer。持久数据库中两个
科学 Task 都是 `completed`，reviewer 输出的精确父链直接包含 author 输出。聊天没有再携带任务
工作区、session、Artifact 身份或科学判断。

第 12 轮也实际产生了四条正确固定信号，但当时的验收器把 Codex 写在 JSONL 前的两条固定运行时
提示误判为泄漏，因此报告诚实保留为失败；第 13 轮只为这两类已知前导输出增加兼容，结构化 wait
消息和 final 文件仍执行精确相等检查。合成负例证明附加路径或科学 verdict 会被拒绝。

前两轮的全部阻塞未见回归。独立复跑聚焦 37 项、`tests/operations` 145 项、全仓 178 项全部通过；
静态编译和 `git diff --check` 通过。第 13 轮仍明确不声称 Sentaurus 语法、输入槽解析、执行就绪
或科学主张合格，独立 reviewer 返回 `revise / unknown / false`，没有用架构夹具冒充求解器证明。

本轮没有发现 R4-A 阻塞缺陷。

## 一、审查范围与基线

审查的是未提交共享工作树相对 `baseline/8765-codex@404aeb14c6ebc4b08bac599db91eaee54c103f48`
的当前状态。工作树包含 R0—R4-A 的连续未提交重构以及持久验收资料；本报告没有把 `git diff`
误称为只含第四轮窄修复，也没有修改产品实现或主计划状态。

重点直接检查：

- `src/scidiscovery/platforms/codex.py` 的父调度协议、Operation Agent prompt 编译和固定完成信号；
- 当前 `AGENTS.md` 与第 13 轮实际生成的项目 `AGENTS.md`；
- `tests/operations/live_r4_tcad_agent_qualification.py` 的真实父子进程、状态查询、Artifact 读取和验收器；
- `tests/operations/test_live_qualification_evidence.py`、平台安装测试和 TCAD Operation 端到端测试；
- 第 12/13 轮 qualification report、四个 Codex 会话、两个父事件流、两个 parent final 和 daemon 日志；
- TCAD 单一插件声明、通用 workspace/tool 接口、Task/Worker/Codex 分派边界及安装态；
- 首轮七项和第二轮两项阻塞的现有回归证据。

## 二、第三轮唯一阻塞已经闭合

### 2.1 子智能体完成聊天已变成固定非科学信号

`src/scidiscovery/platforms/codex.py:78-85` 定义统一 Operation completion 规则：只有
`worker_finalize_file` 报告完成后，chat completion 才能严格返回“已完成受控提交。”，并明确禁止
科学摘要、结论、文件名、路径、task/session/artifact 身份、摘要值或 payload。

该规则不是 TCAD 私有 prompt 补丁。`_operation_toml` 在 `:397-400` 对每个编译 Agent Operation
统一追加原生能力边界和 completion 协议。它没有新增 Operation 状态或科学合同；科学结果仍由原有
Worker 文件生命周期 validate、seal、finalize 和 Artifact 注册完成。

平台安装测试确认每个 Operation Agent profile 都含该规则；第 13 轮实际 author/reviewer profile
也含相同文本。两份真实 child 会话的最终 assistant 消息均严格为：

```text
已完成受控提交。
```

没有路径、内部身份、项目摘要或审查 verdict。

### 2.2 父会话最终回复已变成固定传输信号

`src/scidiscovery/platforms/codex.py:52-63` 和 `AGENTS.md:170-181` 规定：child 返回后必须通过 Root
读取受控状态和封存输出；child chat 是不可信传输信号，不得直接用作科学结果。

真实验收的父 prompt 在
`tests/operations/live_r4_tcad_agent_qualification.py:333-339` 进一步冻结父 final。第 13 轮两个
parent final 都逐字为：

```text
子智能体已返回；受控状态待控制层查询。
```

父事件中没有再出现第三轮的 `state/workspaces/ses_*`、内部 session 身份、TCAD 文件摘要或
reviewer 科学结论。两个父会话各自只调用一次 spawn 和一次 wait；实际 spawn 参数均为精确编译
`agent_type`、`fork_context=false` 和固定消息“完成已经排队的工作分配。”，没有把任务元数据或
科学上下文写入 child 消息。

### 2.3 科学结果只沿受控状态和 Artifact 传播

真实链路在 parent completion 之后由外层受控程序执行：

1. `live_r4_tcad_agent_qualification.py:727-730` 查询 author `task_status` 并只在状态为
   `completed` 时取得语义输出名；
2. `:731-746` 以该精确已封存 author 输出创建 `tcad.deck.review.v1`；
3. `:788-805` 从 Task 的 `output_ref` 读取 CAS Artifact 并进行严格 `DeckProjectDraft` /
   `DeckReviewReport` 解析；
4. 第 13 轮持久数据库中 author 输出为
   `art_6a2fbbaea4db4143b3948759090b7c50`，reviewer 输出为
   `art_52ab27ddc02d41df91a4cf3b7ab5e3f2`；后者的父链位置 1 直接指向前者；三个相关 Task
   均为 `completed`；
5. author/reviewer 工作区在验收结束后为空，正式字节保存在内容寻址 Artifact 存储中；父 final
   没有暴露或依赖可变工作区。

所以当前只有一条科学结果权威链：

```text
Worker 受控文件 → validate/seal/finalize → Task output_ref → Artifact/CAS → Root 状态查询 → 下游 Operation
```

聊天只携带生命周期完成信号，不再形成第二条结果通路。

### 2.4 检查器不是只做关键词过滤

`_child_completion_signal_is_bounded` 在 `:394-420` 只接受一个 completed wait state，且其 message
必须与固定 child 信号精确相等；`_parent_final_signal_is_bounded` 在 `:423-428` 对去除文件末尾空白
后的整个 parent final 做精确相等判断。`test_live_qualification_evidence.py:285-323` 的反例加入
`state/workspaces/ses_internal/output/result.json` 或 `blocked` 结论后均失败。

第 12 轮 qualification report 摘要为
`f17eea42e06c8c6d16ba235f1931ea02ebaf719258200c3164205029a2b8bec1`。报告中仅两个 child
completion 检查为假；直接读取四份原始会话可见 child 和 parent final 实际都已固定。原因是父
JSONL 前存在 Codex 的 PATH alias warning 和 stdin 提示。当前检查器只跳过这两类运行时前导行，
其他非 JSON 行仍失败关闭。

第 13 轮 qualification report 摘要为
`241b3759f0fb51297f3ab790958f67f838c5036cfbf511c8540ee7c05c992994`，27 项检查全真。报告列出
的四个会话摘要 `8c53048d…`、`580a25b2…`、`f36ce03f…`、`68eb2eb4…`，父事件摘要
`6c6d179a…`、`91d6dc22…`，两个 parent final 摘要 `d5b47232…` 和两个空 daemon 日志摘要
`e3b0c442…` 均与独立实算一致。

第三轮阻塞判定：已闭合。

## 三、真实第 13 轮能力与主张边界

原始会话而非 qualification 汇总证明：

- author child 的 `thread_source=subagent`、角色为精确
  `op_tcad_deck_author_initial_v1_f5f264f9f4b8`；只调用对应 Worker MCP 服务和任务根内只读
  `exec_command`，实际调用注册的 `worker_tcad_debug_run`，最终 validate/finalize；
- reviewer child 的角色为精确 `op_tcad_deck_review_v1_339f4e3cab03`；只调用 reviewer Worker
  服务，没有 debug tool 或 debug 调用，只读检查独立物化的项目后 validate/finalize；
- 两个 child 的原生命令 workdir 都位于各自物化的 `state/workspaces/ses_*`，命令为 `sed`、
  `find`、`rg --files`、`nl` 等读取；没有原生重定向、仓库源码读取、兄弟任务读取或原生写入；
- author 的 debug 使用精确 `run_name=direct-sdevice-preflight`、`mode=preflight`，控制层记录工具
  receipt；reviewer 没有继承该能力；
- 架构夹具返回的证明为 `diagnostic_layer=runtime`、`qualified=false`。第 13 轮 reviewer 返回
  `verdict=revise`、`syntax_fidelity=unknown`、`execution_ready=false`；
- qualification scope 继续把 Sentaurus 语法、输入槽解析、执行就绪标为 `not_claimed`，并把
  `scientific_claim_admissible` 标为 `false`。

因此第 13 轮证明的是“真实 Codex author → 注册领域工具 → 封存 Artifact → 独立 reviewer”的
架构集成，不是 Sentaurus parser、solver 或科学结论资格。检查器没有为取得通过而放宽科学主张。

## 四、前两轮全部阻塞的回归判断

| 既有阻塞 | 第四轮判断 | 核验结果 |
| --- | --- | --- |
| 正式实验计划审查不可达 | 无回归 | materialize→精确 object review→TCAD author 正负测试仍通过；缺失、错误或未接受审查失败关闭。 |
| legacy TCAD role 双权威 | 无回归 | TCAD 包不发布 `agent_role_packs`；四个 TCAD 行为只来自标准 catalog Operation，legacy 调度拒绝迁移角色。 |
| 参数 cohort 不闭合 | 无回归 | 正式 `science.parameter.uncertainty.v1` 仍在同一 catalog；coverage→uncertainty→精确整组审批→author 测试通过，部分/未批 cohort 被拒绝。 |
| 专业静态资源与 Worker 指令冲突 | 无回归 | author/reviewer/SDevice 合同并入插件 prompt resource 并进入 operation digest；child 不加载宿主 skill。 |
| 1200 秒 author 无续租 | 无回归 | 三个 author 均注册 heartbeat；租约只能续至冻结绝对预算。 |
| debug 失败快照绕过 Operation snapshotter | 无回归 | 新 attempt 能从 operation-aware provisional snapshot 恢复无效候选；debug 不走通用无界快照。 |
| finalizer 顺序不确定 | 无回归 | 目录和文件双排序，跨创建顺序输出字节和摘要一致。 |
| `parameter_uncertainty` 私有伪造/无正式 producer | 无回归 | 仍由 `general_science` 的确定性 support Operation 产生，有严格 Schema、父链、调度 cohort 投影和正式调用测试。 |
| 无作用 debug 夹具冒充 solver 合格 | 无回归 | 第 13 轮仍为 `qualified=false`/`not_claimed`；生产 bridge 的缺失槽和错误媒体类型负例仍通过。 |

## 五、R4-A 架构目标与 33 项约束族

### 5.1 单一插件入口与 OperationSpec 行为闭包

源代码编译探针结果：

```text
core: public=15, support=14, TCAD operation=0
full: public=19, support=14, TCAD operation=4
```

四个 TCAD public Operation 都由 `tcad_artifact.plugin:PLUGIN` 的唯一标准
`scidiscovery.plugins` 入口注册。保留的 `scidiscovery.transform_adapters` 是 R4-B 尚未迁移的既有
确定性/执行桥，不注册 author/reviewer，也没有形成第二 Agent 行为目录。

`OperationSpec` 仍只声明端口、executor、输出、审查边、guard 和预算。TCAD workspace 引用
`workspace_materializer`、`workspace_file_policy`、`workspace_finalizer`、`workspace_snapshotter`
四个窄组件；review workspace 只引用 materializer。`operations/workspace.py` 只有 138 行，接口
只向插件提供任务私有根、已物化输入和本任务 provisional roots，没有 TaskService、ArtifactService、
数据库、仓库根或兄弟任务句柄。启动编译仍拒绝未知钩子和同类重复钩子。

### 5.2 最小权限与领域分派

- TaskService、Worker router 和 Codex 平台没有按 TCAD role、context profile、输出 Schema 或
  `tcad_artifact` 动态 import 决定工作区、文件、finalizer、snapshot 或工具；
- debug 只在三个 author Operation 的编译工具集中；reviewer 和 core-only catalog 均无该工具；
- Worker router 在实际调用 contextual tool 前仍核对精确 task/attempt/operation capability 和工具名；
- reviewer 工作区只读，不能取得 author 文件策略、snapshot、finalizer 或 debug；
- 第 13 轮真实 Agent 行为与这些声明一致。

核心 Worker daemon 仍有 TCAD debug 服务装配和旧 CLI 参数。这是实施计划明确留给 R4-B 的过渡
边界，并未按 role/context/schema 赋权；实际工具可见性和调用资格仍来自唯一 compiled operation。
本轮没有提前迁移 capability、外部 effect、TCAD transform 或 R4-D UI renderer。

### 5.3 没有新增平行状态或权威

本轮通信修复只增加两段平台提示和资格检查，没有新增：

- 数据库表；
- Task、Approval、Qualification、Execution 或 current 状态机；
- message bus、chat receipt 或结果封装实体；
- 第二 catalog、第二 plugin entry-point group 或 role 权限表；
- TCAD readiness 拓扑或核心领域候选分支。

仓库仍没有逐项编号的“33/33”自动验证脚本，本报告不伪称运行了该脚本。按计划冻结的行为约束族
复核，唯一权威、不可变 Artifact、精确父链、独立审查、同 cohort 人工决定、默认拒绝、Worker
隔离、确定性 finalizer、compare-and-set 生命周期和失败恢复均未见退化。

## 六、独立测试结果

| 检查 | 结果 |
| --- | --- |
| 固定信号、TCAD 插件、平台生成和通用科学回归聚焦 | `37 passed in 4.34s` |
| 全部 operation 测试 | `145 passed in 46.65s` |
| 全仓测试 | `178 passed in 65.90s` |
| `python -m compileall -q src plugins/tcad_artifact/tcad_artifact tests/operations` | 通过 |
| `git diff --check` | 通过 |
| source-independent wheel/core-only/full/破损插件安装态 | 包含在全仓与 operation 测试中并通过 |
| 第 12/13 轮报告及其列出的所有会话、父事件、final、日志摘要 | 独立实算匹配 |

没有运行真实 Sentaurus solver、浏览器审批或外部副作用。这些不属于第 13 轮诚实声明的资格范围，
不能由本报告外推为已通过。

## 七、非阻塞债务与简化建议

### 1. 通用核心复杂度必须在 R5 兑现下降

当前 `spec.py/catalog.py/invoke.py` 为 `348/462/430`，合计 1240 行；另有通用
`workspace.py=138`。cohort、最大尝试次数和窄 workspace 协议目前都对应已复现的真实断裂，未
形成第二系统，不应为了 R4-A 行数机械删除。但 R5 的旧注册/拓扑删除门必须执行；不得在 R4-B
继续为每个领域增加通用钩子种类。

### 2. 生成器与当前根调度文本有一处措辞漂移

当前根 `AGENTS.md` 写“OperationSpec 编译的静态专业资源”，而
`src/scidiscovery/platforms/codex.py:68` 仍写“属于 OperationSpec 的 skills”；第 13 轮生成项目也
使用后者。child 的高优先级编译提示明确禁止 skills，TCAD 专业合同实际已静态并入 digest，因此
没有形成运行时权限旁路。但应在后续窄文档修订中统一为“静态编译资源”，避免再次引发首轮的
skill 语义歧义；不需要新增 skill registry。

### 3. 第 12 轮前导 warning 白名单可以再收紧

当前验收器按固定 warning 前缀跳过 Codex 自身输出，足以避免第 12 轮假阴性，结构化 child message
仍做精确相等检查。为了提高证据工具抗伪装性，可将允许的 warning 改成完整正则或单独捕获 stderr。
这只影响验收证据强度，不影响第 13 轮已直接核验的原始固定消息和生产结果权威。

### 4. 插件隔离仍是可信代码/原型权限边界

workspace hook 的参数最小化和真实 Agent 的任务根遵守已经证明，但同进程已安装 Python 插件并非
针对恶意插件的 OS 强沙箱；Codex 原生工具仍是 `inherited_prototype` 提示约束。该限制在 R2 已
冻结且本轮未扩大。真实凭据、不可逆外部执行和不受信第三方插件不得据此放行。

### 5. 第 13 轮父会话专门验收传输，Root 查询由外层 harness 承担

为了防止父会话代做，真实父 prompt 禁止 Root/Worker 调用；因此本轮直接证明的是“父子聊天不
承载结果”，而受控查询由同一真实 harness 的 Root facade 执行。生产调度规则已经要求父调度器
自行查询 `task_status`。未来若修改 Codex 父调度实现，应补一个同时执行 spawn/wait 和 Root 状态
查询的生产式父会话测试；当前 author→reviewer 下游绑定没有从 chat 取值。

上述项目均不需要新增实体、状态机或注册表，不阻塞 R4-A 放行。

## 八、阻塞问题

无。

## 最终判定

通过，允许进入 R4-B
