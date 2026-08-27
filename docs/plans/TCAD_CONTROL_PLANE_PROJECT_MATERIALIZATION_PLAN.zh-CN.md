# TCAD 项目确定性物化与审查边界重构计划

状态：P0-A～P0-D 已按 solver-neutral v2 纠偏并通过全仓回归；P0-E 等待安装后的真实纵向资格（2026-08-13）
优先级：P0，阻塞 Alpha 科学闭环继续执行
目标链路：`experiment_plan -> author 源码 -> 控制层物化/静态门 -> reviewer -> package -> execution`

> **2026-08-13 架构纠偏（当前权威方案）**
>
> 本文后半部保留了早期 P0 实验记录，其中“控制层解析 SProcess 命令、生成
> `.cmd` scaffold、从 `Zinc/InGaAs/pdbSet` 等语法推断 realization、要求 reviewer
> 逐项审查 realization requirements”的方案已经废止，不能作为当前实现、安装或验收
> 标准。该方案把物理状态名和 TCAD 语义硬编码进控制面，真实运行因此被强制绑定到
> built-in `Zinc` dopant callback，并在 `_AlloyCompound::DopantBulk` 初始化失败。
>
> 当前 v2 只接受 solver-neutral `deck/declarations.json`：author 写完整源码、production
> entrypoint、可选的 author-owned initialization entrypoint、每个 plan case 的唯一源码
> anchor，以及原始 solver 输出的名字/安全路径/MIME。控制层只校验安全路径、精确 case
> 集合、locator 唯一性、plan 值/单位、源码完整性、资源和收集边界；不生成或解析 TCAD
> 源码，也不生成 realization requirements。reviewer 阅读完整代码并做整体物理/数值/
> 实现审查，只输出 fidelity dimensions 和具体 findings，不填写逐项 requirement 表。

## 1. 决策摘要

当前 `tcad_deck_author` 不只是写 TCAD 代码，还要手工填写
`parameter_bindings`、`case_parameter_bindings`、`realization_manifest`、
`expected_outputs`、capability 三元组和大量 locator；随后控制层做字符串一致性检查，
`tcad_deck_reviewer` 又被要求逐项复核同一批字段。

这会造成三类直接损失：

1. author 的主要时间消耗在重复填表和修 schema，而不是写、调 TCAD 代码；
2. `worker_tcad_debug_run` 常在求解器启动前被机械字段错误拦截，诊断只能返回笼统的
   `$.deck` 路径；
3. reviewer 被迫重新计算控制层本可确定性证明的值、单位、覆盖率和 locator，职责越界，
   也增加了错误修订请求。

本计划作出以下架构决策：

- author 只维护受控目录中的 solver 源码，以及极少数不能由上游科学对象或源码唯一推导的
  科学实现决策；
- 控制层的 TCAD domain plugin 从 exact `experiment_plan`、exact
  `execution_capability`、author 声明和当前 deck 文件树生成规范 `DeckProject`；
- plan bindings、case 覆盖、单位投影、源码完整性、能力绑定和 revision diff 等机械字段
  由控制层生成；case locator 与 raw-output 路径由 author 声明，控制层只验证和登记；
- reviewer 只审查“科学假设是否被正确实现”和“代码是否存在显式物理、算法或 TCAD 逻辑 bug”，
  不再逐条重填或复核控制层已经证明的机械字段；
- 任何不能确定性解析的事项都形成有 reason code 的 materialization finding，绝不退化为让
  agent 猜值或手工复制 planned value。

不增加新的科研 Agent，不恢复 `DeckProjectPatch`，也不让 diagnostician、reviewer 或 author
承担控制层数据整理。

## 2. 当前问题的代码根因

### 2.1 author 输出模型混合了三种不同职责

当前 `DeckProjectDraft` 同时包含：

- solver 项目内容：`files`、`entrypoint`、`arguments`；
- 科学实现声明：`parameter_bindings`、`case_parameter_bindings`、
  `realization_manifest`；
- 控制/执行信息：`tool_profile`、`solver_kind`、`capability_sha256`、
  `resource_limits`、`expected_outputs`、`runtime_assertions`。

`src/scidiscovery/artifact_agent/service/tasks.py` 的 deck workspace 模板把上述字段全部放入
可编辑的 `deck/project.json`，再由 `_build_author_result_from_deck_workspace` 原样拼回完整
`DeckProjectDraft`。控制层目前只负责重建，不负责物化字段含义。

### 2.2 validator 只校验 agent 填写结果，没有生成事实

`plugins/tcad_artifact/tcad_artifact/project_packager.py` 当前检查：

- locator 是否出现且只出现一次；
- `realized_value` 字符串是否出现在 locator 中；
- case binding 是否覆盖 experiment plan 中的 comparison variables；
- realization requirement locator 是否存在；
- reviewer 是否逐项覆盖 manifest。

这些规则只能证明“一张人工表在字符串层面自洽”，不能证明控制量确实由可执行语句实现，
也不能避免 comment-only locator。当前真实 preflight 的
`case parameter binding value is not present in its exact locator` 就属于这一层失败；求解器尚未启动。

### 2.3 reviewer 被要求重复确定性工作

当前 reviewer prompt 要求：

- 逐条核对每个 `case_parameter_bindings` 的 experiment/case/variable/value/unit/locator；
- 为每个 `realization_manifest` key 输出一条 `requirement_reviews`；
- 用人工审查决定覆盖是否完整。

这不是独立代码审查，而是把 materializer/linter 的工作交给第二个 LLM 重做。

## 3. 目标职责边界

| 层 | 必须负责 | 明确不负责 |
| --- | --- | --- |
| Experiment designer | 科学比较设计、case、改变/冻结变量、单位、预期观测量、验证计划 | solver locator、文件路径、源码字符串 |
| Deck author | PDE/模型、IC/BC、几何、材料、数值算法、TCAD 源码和必要的科学实现决策 | 手填 capability、case 表、manifest、locator、diff、运行资格 |
| TCAD materializer | 从 immutable inputs、author 声明和源码生成规范项目；校验路径、case 集合、plan 值/单位和完整性 | 解析材料/状态/方程/边界/TCAD 命令，或判断物理实现 |
| TCAD linter | 安全路径、唯一 anchor、case 覆盖、值/单位投影、输出收集和源码完整性检查 | 推断 solver 语义、实现默认项或给出科学 verdict |
| Deck reviewer | 物理实现忠实性、代码逻辑、数值方案科学合理性、显式 bug | 重算 bindings、逐条抄写 manifest、运行 solver、扩张输出合同 |
| Packager | 重跑物化、校验 parentage/digest、冻结 reviewed package | 修复项目或接受 reviewer 未审查的候选 |
| Execution/Scorer | 执行与确定性后处理 | 修改 deck、补写实现声明 |

### 3.1 仍允许 author 声明的内容

“确定性字段移交控制层”不等于控制层猜测物理。以下内容仍属于 author，但表达形式必须最小化：

- 新增的、上游计划没有定义的数值离散选择及其科学理由；
- 每个 plan case 映射到哪个唯一稳定源码 symbol/block；
- TCAD 语法无法静态推导时，某个 raw solver-native output 的语义标签。

author 提供 case key、源码相对路径和唯一精确 locator，但不提供 planned value、unit、
evidence parent、摘要或逐变量重复记录。控制层只证明 locator 字节存在且唯一，不解释它
所指向语句的 TCAD 含义；完整代码与 plan 是否忠实对应由独立 reviewer 判断。comment 不得
冒充 case dispatch，reviewer 必须核对 locator 指向的实际控制流。

## 4. 新的项目合同

### 4.1 Author workspace

新的 author workspace 为：

```text
deck/
├── files/                         # author 可编辑：.cmd/.par/受支持 include
├── decisions.json                 # author 可编辑：仅不可推导的科学实现决策/稳定锚点
├── contract/
│   ├── experiment-controls.json   # 控制层只读生成：case/变量/值/单位/角色
│   ├── capability.json            # 控制层只读生成：精确公开 capability
│   └── required-outputs.json      # 控制层只读生成：仅 raw solver-native observables
├── reports/
│   └── materialization.json       # 控制层只读刷新：精确诊断和生成结果
├── handoff.json                   # author 的简短 scientific handoff
└── README.md
```

删除 author 可编辑的机械 `project.json`。若为兼容 Worker 文件工具保留该文件，它只能是控制层
生成的只读 projection，不能作为 author 输入。

### 4.2 Source project 与 canonical project 分离

引入两个清晰对象：

1. `tcad.deck-source-project.v1`
   - 由受控文件树和 `decisions.json` 表示；
   - 不包含 case binding、realization manifest、capability digest 的人工副本；
   - 仅存在于 task-private workspace，不作为下游科学 Artifact。
2. `tcad.deck-project.v2`
   - 由控制层 materializer 生成；
   - 包含完整 source files、capability、case/global bindings、realization manifest、raw outputs、
     source locator、resource limits 和 materialization summary；
   - 是 reviewer、diff、package、debug 和 execution 的唯一规范输入。

历史 `tcad.deck-project.v1` 保持只读可验证，不原地迁移；新任务只生成 v2。

### 4.3 受控 case 参数

控制层从 `ExperimentPortfolio.comparison_contract` 生成只读 case table。对可直接表达的标量/枚举
控制，优先生成 profile-specific solver include，例如：

```text
deck/generated/scid_case_controls.tcl
```

solver deck 通过稳定 key 读取该 include 中的值，避免 author 再复制 5、21 或更多 case 值。
include 机制必须先分别通过 SProcess 与 SDevice capability qualification；在未资格化的 profile 中，
materializer 使用严格的源码 symbol anchor 解析，不静默猜测。

每个 canonical `CaseParameterBinding` 由控制层生成：

- experiment/case/variable/scientific_path/unit 来自 exact plan；
- realized value 来自生成的 case table 或已解析的可执行 assignment；
- relative path、line span、command kind、source digest 来自 parser；
- requirement keys 来自 plan requirement projection；
- comment-only、重复或不可达 anchor 直接 fail closed。

### 4.4 Realization manifest

manifest 不再由 author 逐行填写。控制层按以下优先级生成：

1. experiment plan 中的 case controls、raw observables 和明确实现要求；
2. 上游物理设计/假设中已结构化的 PDE、IC、BC、材料、几何要求；
3. author 在 `decisions.json` 中声明的、确实无法从上游唯一推导的新增实现决策。

materializer 将这些 requirement key 解析到实际 executable statement/block。它自动填充 category、
source path、locator、verification mode 和 output name。若某项没有实现，报告
`missing_requirement_realization`，不生成 `implementation_status=unsupported` 的 deck 职责行。
属于 scorer/diagnosis 的 observed gate、mask、metric、threshold 或 verdict 根本不进入 deck manifest。

### 4.5 Raw output 与 runtime contract

控制层根据 exact experiment plan 和 profile parser 只接受 solver-native TDR/PLX/PLT/log：

- author 只在 solver 代码中真实声明输出；
- materializer 从命令解析文件名和生成位置；
- execution bridge 负责文件 freshness、non-empty、日志收集；
- deck 的 `runtime_assertions` 固定为空；
- CSV、JSON、重采样、mask、score、readback 自检和科学阈值在 deck 层一律报
  `postprocessing_scope_violation`。

## 5. Materializer 与 linter

### 5.1 Plugin 接口

在 `plugins/tcad_artifact` 内新增纯确定性接口，不把 TCAD 语法放进 Root control：

```text
TCADProjectMaterializer.materialize(
    source_tree,
    experiment_plan,
    execution_capability,
    scientific_inputs,
) -> MaterializedDeckProject
```

首批 profile adapter：

- `SProcessProjectIntrospector`
- `SDeviceProjectIntrospector`

两者共享路径安全、case coverage、单位、parentage 和报告 schema，但保留独立语法解析与 raw output
发现逻辑。未知语法返回 `unsupported_syntax`，不得退化为正则猜测后 pass。

### 5.2 确定性检查项

P0 必须覆盖：

1. capability/profile/solver kind/entrypoint/arguments 精确绑定；
2. 安全路径、UTF-8、文件大小、入口文件和 include 闭包；
3. 每个 plan case 的存在性和唯一性；
4. 每个 intended/permitted/frozen control 的完整覆盖；
5. actual value、canonical unit 与 plan expectation 的精确比较；
6. anchor 唯一性、可执行语句类型、可达性和源码 digest；
7. comment-only locator、dead declaration、重复 assignment；
8. case 外未声明差异，以及 case 内缺少的冻结控制；
9. raw output 的名称、后缀、生成语句和 plan observable 覆盖；
10. scorer/diagnosis 职责泄漏；
11. profile policy 要求显式声明的数值控制与禁止依赖的 simulator default；
12. revision 后 capability、计划控制和非授权科学字段的冻结一致性。

其中第 11 项必须由版本化 profile policy 驱动。控制层能证明“显式/缺失”，但不能替 reviewer
判断某一显式数值方案是否科学合理。

### 5.3 可操作诊断

不再只返回 `$.deck` 和一个长字符串。每条 finding 至少包含：

```text
reason_code
severity
experiment_key
case_key
variable_key / requirement_key
source_path
line_start / line_end
command_excerpt（有界、去敏）
expected
observed
suggested_fix_scope
```

P0 reason code：

- `missing_control_binding`
- `duplicate_control_anchor`
- `comment_only_anchor`
- `unreachable_assignment`
- `value_mismatch`
- `unit_mismatch`
- `missing_requirement_realization`
- `downstream_only_requirement_in_deck`
- `implicit_solver_default`
- `dead_declaration`
- `raw_output_not_declared`
- `raw_output_not_produced`
- `unsupported_syntax`
- `source_changed_after_materialization`

`worker_tcad_debug_run` 在 preparation 失败时原样返回首条 finding 和有界 finding summary；author
能够直接定位到文件/行/变量，不再猜测是 schema、parser 还是 solver 问题。

## 6. 新的 author/debug/reviewer 流程

```text
Control materializes read-only contracts
                |
Author edits solver files + minimal decisions
                |
Control materializer -> canonical project v2 + lint report
                |
        deterministic gate pass?
          | no                 | yes
          v                    v
actionable finding       bounded preflight/smoke
                               |
                    canonical project + report
                               |
                    independent deck reviewer
                               |
                 reviewed package re-materialization
```

### 6.1 Author

- 首次和修订继续合并为同一角色；
- revision 直接编辑 exact prior 文件树；
- 不编辑 bindings、manifest、capability、output contract 或 diff；
- debug 前只需运行一次控制层 materialization；
- 机械门失败时根据精确 finding 修源码，不需要重构 JSON；
- handoff 只报告科学/实现状态和仍未解决的非确定性问题。

### 6.2 Reviewer

移除 `DeckReviewReport.requirement_reviews` 的全量逐项列表，改为：

- `physical_fidelity`
- `implementation_fidelity`
- `numerical_protocol_fidelity`
- `findings[]`
- `unresolved_assumptions[]`
- `execution_ready`

reviewer 读取完整 solver code、experiment plan、科学输入和控制层 lint 摘要。它可以引用稳定
`requirement_key` 或 source locator 指出问题，但不重新声明已经通过的行。控制层强制：

- reviewer 输入必须绑定 exact canonical project 与 exact passing materialization report；
- report 中引用的 key/path 必须存在；
- blocker/major finding 与 pass 相冲突；
- reviewer 不能修改 deck、运行 TCAD 或添加 scorer/runtime 合同。

reviewer 的 `syntax_fidelity` 改由 preflight attestation 提供，不再要求 LLM 自称完成语法验证。
若没有 preflight，reviewer 只能对静态代码给 verdict，`execution_ready` 保持 false。

### 6.3 Package

package transform 不信任 author/reviewer 期间保存的旧机械字段。它必须：

1. 对 exact project source tree 重跑 materializer；
2. 比对 canonical project digest 和 materialization report digest；
3. 校验 exact experiment plan 与 capability parentage；
4. 要求独立 reviewer pass；
5. 要求 preflight attestation 满足当前 profile policy；
6. 任一源码或 plan 变化即拒绝旧 review/package。

## 7. 分阶段实施计划

### P0-A：冻结合同与回归样本（0.5 天）

- [x] 将当前 5-case author、preflight validation failure 和 reviewer revise 固化为匿名 fixture；
- [x] 记录当前 author/project/reviewer schema 和 transform parentage；
- [x] 新增 reason-code schema 与 `MaterializationFinding`；
- [x] 明确 P0 SProcess 支持语法子集和 raw output 子集；
- [x] 禁止在本阶段继续派发真实长时 author/reviewer 任务。

验收：现有问题可以由测试稳定复现，且不会依赖某个 Agent 的自然语言输出。

### P0-B：控制层 materializer 核心（1.5 天）

- [x] 新增 source-project、control-materialized canonical project 与 materialization-report schema；
- [x] 从 capability 自动生成 tool profile、solver kind、digest、固定参数边界；
- [x] 从 experiment plan 自动生成 case/control contract；
- [x] 实现安全 source tree 和稳定 executable locator；
- [x] 实现 P0 SProcess scalar/direct case dispatch/raw LogFile 解析；
- [x] 自动生成 global/case bindings 和 realization manifest；
- [x] 自动排除 scorer/diagnosis-only requirements；
- [x] 生成 canonical JSON 与内容 digest。

验收：5-case fixture 不需要人工 bindings/manifest 即生成完整项目；comment-only locator 不能通过。

### P0-C：Worker lifecycle 与 debug 集成（1 天）

- [x] author workspace 改为源码 + 只读 contract + control-owned project projection；
- [x] `worker_validate_output_file` 在 seal 前运行 materializer；
- [x] `worker_tcad_debug_run` 使用同一 canonical materialized candidate；
- [x] preparation failure 返回精确 finding，不再只有 `$.deck`；
- [x] checkpoint/retry 保存源码、handoff 和 materialization report；
- [x] materialization 后源码变化触发重新物化，旧 preflight/source digest 不可复用。

验收：一次字段错误在 debug 前 5 秒内定位到具体 case/variable/source line；修正源码后无需编辑 JSON。

### P0-D：Reviewer 与 package 边界收缩（1 天）

- [x] 发布向后兼容的精简 `DeckReviewReport` 合同；
- [x] 删除 reviewer prompt 中 bindings/manifest 全量复核要求；
- [x] reviewer context 加入 exact materialization report 和 source-bound preflight attestation；
- [x] package transform 强制重跑 materializer并校验 digest/parentage；
- [x] 删除新流程对 `DeckProjectPatch` 和全量 `requirement_reviews` 的依赖；
- [x] 更新 readiness：只有 materialization pass + preflight pass + exact review pass 才可 package。

验收：reviewer 输出不再包含 N 条机械 pass 行；旧 project/review 不能绕过 v2 门。

实现兼容说明：为避免在 Alpha 资格前同时迁移全部历史 Artifact/context schema ID，
canonical project 暂沿用 `tcad.deck-project.v1` 外层标识，但新对象必须包含 passing
`materialization_report`，package v2 会拒绝缺少该报告的历史人工项目。换言之，安全边界
已经按 v2 语义切换，破坏性的外层 schema ID 改名不再作为 P0-E 前置条件。

### P0-E：真实 Alpha 纵向资格（0.5–1 天）

- [x] 首次重新安装并重启控制面/worker；
- [x] 用当前 5-case plan 新建一次 author 任务；
- [x] 记录首次真实失败：task contract 未公开
  `SCIDISCOVERY_CASE_BINDING` 的唯一 key/unit grammar，author 写出完整源码但在
  preflight 前被 25 条 materialization error 拒绝；该任务已 CAS fail-close，未注册输出；
- [x] 新增只读 `deck/contract/materialization-spec.json`，投影 profile、精确 unit
  suffix、bare scalar 规则、当前计划所需 directive keys、每个 case 的 reviewed
  tokens 与 raw-output 边界；
- [x] 更新 `$sentaurus-tcad-code` Skill：先读机器合同、180 秒内落首份最小候选、
  手册只按具体 solver syntax/diagnostic 定点检索、合同缺失时禁止猜格式；
- [x] unit/value mismatch 返回完整期望 token 与 bare-scalar 修复范围；
- [x] Skill quick validation、80 项集成回归、安装 dry-run 与 artifact-agent 全量
  `553 passed` 通过；
- [x] 第二次真实 author 验证确认 spec 可读且内容正确，但 180 秒内无写入；CAS
  审计定位为子 agent 在 JavaScript template literal 中承载 Tcl `${caseKey}`，随后又
  调用了 isolate 不存在的 `TextEncoder`，两次均在 Worker tool 前失败；任务已
  fail-close，未运行 preflight；
- [x] 控制层从计划自动生成 `deck/files/study.cmd` mechanical scaffold，包含 exact
  procedure 参数、binding directive 与五个 direct case calls；author 只替换显式
  `SCIDISCOVERY_AUTHOR_IMPLEMENTATION_REQUIRED`，不再重写机械 Tcl；
- [x] `worker_file_write_begin.expected_bytes` 改为可选；省略时服务端累计 UTF-8
  字节、执行总量上限并在 commit 原子校验，大文件仍可分块；
- [x] Skill/role 明确普通 quoted strings/line arrays，禁止 JavaScript template
  literal 承载 Tcl `${...}`，禁止在编排 isolate 使用 `TextEncoder`；
- [x] 第二轮 Skill quick validation、78 项聚焦集成测试、安装 dry-run 和全量
  artifact-agent `554 passed` 通过；
- [x] 第三次真实 author 验证成功使用 control-generated scaffold 并完成原子 patch；
  第一次确定性验证将错误收敛到 `geometry_initial_far_boundary`，证明格式/写入路径
  已闭合；
- [x] 记录并修复 introspector 的错误否决：原实现把初始零浓度和 far=0 Dirichlet
  绑定硬编码为旧 `select`/`BackStop_InGaAs` 名称，无法识别合法的
  `init concentration=0 field=Zinc` 与同一边界对象的 `Fixed_InGaAs 1` + 零方程；
- [x] 新 geometry resolver 名称无关但语义配对，继续拒绝注释、非零初值、缺 fixed
  gate 和跨边界对象拼接；同时修复字符串 `"0".rstrip("0")` 生成空 regex、可能将
  非零误判为零的隐藏缺陷；
- [x] geometry/materializer/debug/package 聚焦 `73 passed`，全量 artifact-agent
  `559 passed`；
- [ ] 重新安装并重启上述合同修复；
- [ ] 用当前 5-case plan 重试一次全新 author 任务；
- [ ] 控制层生成 bindings、manifest 和 raw output contract；
- [ ] 完成一次 bounded preflight；
- [ ] 完成一次独立 code/physics review；
- [ ] package 并进入 execution；
- [ ] 继续 control-equivalence、curve-score、diagnosis，直至产生一次合法闭环。

验收：author/reviewer 不再因机械字段填写失败；Alpha 闭环至少成功跑通一次。

### P1：SDevice 与复杂语法扩展

- [ ] SDevice electrode/physics/solve/output introspector；
- [ ] multi-file include graph 与参数文件；
- [ ] 受支持的表达式常量折叠和单位换算；
- [ ] 更精确的 dead branch/dataflow 检查；
- [ ] profile-specific simulator default policy；
- [ ] 非 Codex worker 的等价 workspace 支持。

P1 不阻塞 SProcess Alpha 闭环。

## 8. 代码改动地图

| 模块 | 计划改动 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/project_packager.py` | 新 v2 schema；移除 author 输入的机械字段；review/package 新门 |
| `plugins/tcad_artifact/tcad_artifact/project_materializer.py` | materializer 核心、报告与 digest |
| `plugins/tcad_artifact/tcad_artifact/sprocess_introspector.py` | P0 SProcess 解析器 |
| `plugins/tcad_artifact/tcad_artifact/sdevice_introspector.py` | P1 SDevice 解析器 |
| `src/scidiscovery/artifact_agent/service/tasks.py` | workspace 合同、validate/finalize 物化、retry 恢复 |
| `plugins/tcad_artifact/tcad_artifact/debug_adapter.py` | debug 前物化及精确诊断 |
| `plugins/tcad_artifact/tcad_artifact/transform_adapter.py` | diff/package 重物化与 parentage |
| `roles/tcad_deck_author.md` | 只写源码和最小科学决策 |
| `roles/tcad_deck_reviewer.md` | 只审物理忠实性与显式代码 bug |
| `skills/sentaurus-tcad-code/` | 解释 source contract、profile 语法和诊断，不承担控制表生成 |
| `tests/artifact_agent/` | materializer、linter、workspace、debug、review、package、E2E |

## 9. 测试矩阵

### 9.1 正向

- 单 case engineering project；
- 多 case、单 intended change；
- 多 case、多 frozen controls；
- 同值 frozen control 自动生成 global binding；
- SProcess 直接 `.cmd` + native log；
- revision 只改一行源码并自动更新 locator/diff；
- 科学计数法、整数、浮点、布尔、枚举值；
- include 文件中的控制变量。

### 9.2 反向/对抗

- comment 中含 planned value，但 executable statement 不含；
- 同一 anchor 出现两次；
- plan 与源码单位不同；
- JSON 序列化把科学计数法变成错误整数表示；
- case 缺失、额外 case、冻结变量只覆盖部分 case；
- author 手写 planned value 但执行路径未读取；
- raw output 只在注释声明；
- deck 内出现 CSV scorer、threshold、observed gate 或 verdict；
- materialization 后修改源码再复用旧 report；
- reviewer 尝试 pass 未 preflight 或 materialization failed 的项目；
- package 使用不同 experiment plan/capability。

### 9.3 性能与可用性

- 8 MiB source tree 的静态物化目标小于 5 秒；
- 典型 5-case project 的机械诊断不超过 64 KiB；
- preparation failure 必须返回首条具体 finding；
- author 不再编辑超过 10 个非源码字段；
- reviewer 不再输出与 manifest 行数线性增长的 pass 列表；
- preflight solver 时间与 control materialization 时间分别计量。

## 10. 发布与迁移

1. 新旧 schema 并存一个迁移窗口；历史 v1 Artifact 只读可审计；
2. 新 author 任务只生成 v2，scheduler 不再创建 v1；
3. v1 reviewed package 不自动升级，必须用 exact source/plan/capability 重物化；
4. 安装 smoke 同时检查 materializer profile、SProcess/SDevice parser 注册和 Worker 工具面；
5. 更新中英文架构、安装、角色协议、TCAD plugin 和 Skill 文档；
6. 完整测试、真实 SProcess 纵向资格通过后再更新 `MANIFEST.sha256`。

## 11. 完成判据

本计划只有同时满足以下条件才算完成：

1. author 不再手填 capability、bindings、manifest、locator、diff 和 runtime assertions；
2. 控制层能从 exact plan/capability/source 生成完整可追溯 v2 项目；
3. comment-only、值不一致、缺 case、postprocessing leakage 在 debug 前被精确拒绝；
4. reviewer 只审科学实现与代码逻辑，不重复控制层机械证明；
5. package 对 exact source 重物化，旧 report 不能在源码变化后复用；
6. SProcess 5-case 真实任务不再因机械字段阻塞；
7. 至少一次完成 author -> materialize -> preflight -> reviewer -> package -> execution ->
   scorer -> diagnosis 的 Alpha 科学闭环；
8. 全量测试通过，计划中所有 P0 项有对应自动化证据。

## 12. 明确不做

- 不新增“manifest agent”“binding agent”或“schema fixer agent”；
- 不让 reviewer 修文件或运行 TCAD；
- 不让控制层根据自然语言猜测 PDE/IC/BC；
- 不恢复大 JSON 全文替换或 `DeckProjectPatch` 主流程；
- 不把 score、mask、threshold、observed evidence 或科学 verdict 塞回 deck；
- 不为完成 P1 通用化而继续推迟 Alpha SProcess 纵向资格。
