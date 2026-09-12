# R5 端到端科学实验前最小闭合计划

当前入口说明（2026-09-08）：以下保留原 Figure 阶段的事实、计划和审查历史，其中“当前”“唯一活动入口”均受该阶段范围限制。本轮 author 失败修复及重新验收由 [TCAD author 失败最小修复与重新验收计划](TCAD_AUTHOR_FAILURE_MINIMAL_REPAIR_PLAN.zh-CN.md)接管；[原 Skill/execution_context 计划](SKILL_VISIBILITY_COMPATIBILITY_AND_EXECUTION_CONTEXT_REPAIR_PLAN.zh-CN.md)保留已部署修复、S5 及 S6 的状态更新。历史 Figure 阻断不能单独作为要求重跑已有科学上游的依据。

日期：2026-09-04

状态：**E5.3 源码实现及 GPT-6 独立复审已通过，已提交 `979a118`；2026-09-06
已部署到 M7 安装根并通过安装态目录校验，等待 Codex 完全重启、重新绑定及真实模型验证，
E6 未放行**。当前实例
已完成三组 Fig.4 请求／物化诊断中的前两组 Intake 与独立审查。第二组审查确认纵轴端点配对被请求
Agent 反向表达，且请求 Agent 可自行填写点数、可见比例和间隙阈值，形成“生产者定义自身验收标准”
的循环合同。第三组只用于验证明确提示能否绕过现有缺口，不构成架构修复或 E5 通过证据。
第二版虽然通过独立复审，但把审批页可读性、投影精细诊断
和已修部署透传的再次开发误列为开跑前工作；第三版将三者降为记录或普通安装验收，只保留会阻断
当前 Fig.4 科学闭环的修改。首轮发现的单输出 Intake 与 ReviewSpec 两项拓扑阻断仍按第二版修正。
本文是当前 M7
真实 Fig.4 闭环的唯一活动缺陷与实施入口；
它取代本文早先“只安装论文图插件即可恢复闭环”的不完整判断，但不改写已经封存的 Run、Artifact、
审批决定和历史审查。

## 1. 本轮只回答什么

本轮只回答：在重新开始一次真实、可审计的端到端科学实验之前，哪些缺陷必须先闭合。

目标纵向链为：

```text
冻结论文 PDF
→ 图像选择与数字化请求 Agent
→ 确定性图证据物化
→ 单输出图证据 Intake Agent
→ 独立图证据审查 Agent
→ 标准曲线证据包
→ 通用 Intake 展开/人工资格
→ 假设提出/批评
→ 实验设计/物化/独立审查
→ TCAD 工程编写/独立审查/打包
→ 人工执行授权
→ 真实求解器执行/结果收集/确定性证明
→ 曲线规范化/评分/诊断
```

成功不等于所有科学结论都通过。来源不足、曲线身份有歧义或实验不能区分机制时，封存的
`unresolved`、`inconclusive` 或“不确定”同样是合格终态；禁止为跑通流程伪造曲线、扩大主张或
强迫 Agent 给出肯定结论。

## 2. 当前事实基线

### 2.1 已经可用，不应重复重构

- 当前会话绑定实例为 `M7-test0`；控制面中已有 35 个实例内科学对象，V15 证据提取、修订和两次
  独立审计均已完成；最新证据资格决定为“要求修订”，理由是缺少曲线数字化结果。
- 当前安装目录共有 44 个 Operation；`tcad.study.execute` 可用，并公开 SProcess 与 SDevice
  R-2020.09 两个执行能力。因此本轮不修改 TCAD Effect、外部执行状态机、current 或 Run 生命周期。
- 现有确定性 Transform 已支持一端口多项和多端口输出，并为每项登记不可变 Artifact；无需给
  Agent Run 增加集合提交协议。
- `deploy/reinstall.sh` 的显式环境白名单透传源码修复已存在。本轮聚焦验证中，图插件、图算法、
  图审查、部署透传和参数资格相关 20 项测试通过；这只证明当前行为，不代表下述阻断已关闭。

### 2.2 当前实际阻断

| 标识 | 优先级 | 现场事实 | 影响 |
|---|---:|---|---|
| `FIGURE-RUN-001` | P0 | `science.evidence.extract.figure.v1` 同时声明一个主结果和五组集合输出；Local Run v1 明确拒绝任何 Agent collection output，公共目录会移除该操作。 | 即使安装插件，调度器仍不能调用数字化能力。 |
| `FIGURE-CONTRACT-001` | P0 | `figure_request` 在 OperationSpec 中是 `opaque`，实际必填字段藏在 `FigureDigitizationRequest` 的 Pydantic 模型中；目录内也没有负责生成该请求的 public Operation。 | Agent 看不到真实输入契约；调度器只能越权手工制造请求。 |
| `FIGURE-SOURCE-001` | P0 | 当前实例只有冻结 PDF；数字化器只接受 PNG/JPEG/WebP。通用 PDF 工具只提取文本，没有声明谁从 PDF 恢复并绑定精确图像对象。 | 手工截图或工作区临时转换会绕过 Operation、来源身份和可重放性。 |
| `FIGURE-FIDELITY-001` | P0 | 迁移后的算法只按颜色逐列扫描，成功时把所有序列和所有点写成 `qualified/eligible`，任一序列不足则整包失败；它没有旧资格实现用于真实 Fig.4 的种子走廊、局部定义域、声明遮挡、共享覆盖和部分 `unresolved` 语义。 | 运行入口即使接通，也可能科学降级：把黑色轴/文字当曲线，丢弃可用红线，或把被遮挡区伪装成观测。 |
| `FIGURE-SHARED-002` | P0 | ABI 16 的 `shared_support` 只实现单一供体逐列连续、被覆盖曲线区间内完全缺失且两端均有直接像素的严格 `overdraw`。真实 Fig.4 中身份已分别绑定但颜色可交替显现的局部重合无法表达；同时 `covered_eligible=true` 会让同一像素在多张表中重复成为合格行，而归一化阶段不保留该共享身份。 | 两次真实共享请求均在校验阶段耗尽 600 秒，旧的全曲线请求只能把 831 行全部保持不合格；继续改提示词或使用四像素片段会制造形式闭环，不能形成科学上可用的双目标曲线。 |
| `FIGURE-AXIS-003` | P0 | `science.figure.request.prepare.v1` 让 Agent 直接填写 `pixel_min/pixel_max`，但 Worker 可见合同没有说明它们分别与 `value_min/value_max` 配对且允许像素坐标递减。真实第二版请求把纵轴像素端点按坐标排序，确定性物化因而把顶部高浓度和底部低浓度反向换算。 | JSON 结构与包完整性均可通过，但所有曲线浓度数值科学错误；后续曲线包、评分和 TCAD 对比必须停止。 |
| `FIGURE-TRACKING-004` | P0 | 请求 Agent 同时填写 `min_points`、`min_visible_fraction` 和 `max_gap_px`，物化器又用这些值判定同一请求是否合格。真实第二版自行将点数门槛抬到 520/700，造成两条曲线全部不合格。 | 生产者参与定义自身验收标准，既可误拒有效曲线，也可放宽阈值制造形式通过；算法参数与科学意图没有分层。 |
| `PREFLIGHT-PROJECTOR-001` | P1 | Approval 的 `operation_preflight` 只准备绑定，不运行实际 projector；`operation_invoke` 才读取完整 producer family 并失败。 | 同一精确调用可能预检通过、调用失败。 |
| `FIG4-PROFILE-001` | P1 | Fig.4 profile 当前未选择 `curve_figure_evidence`。旧计划把“加入插件名”误当成充分条件。 | 必须在 P0 图插件变成实际可运行后才可修改 profile；现在先加只会安装一个诊断态能力。 |
| `RUN-DIAG-002` | P1 | Root 在 Run 执行中只能看到状态和最后活动时间，不能看到去敏后的提交拒绝次数、`rule_id` 与字段路径。真实请求 Run 疑似经历多次可纠正拒绝，但完成后只保留最终封存结果。 | 不阻断科学正确性，但使调度器和开发者无法区分正常修订、合同错位与即将超时；不得通过读取 Worker 草稿或隐藏会话补洞。 |

以下不是本轮代码缺陷：旧代际 Artifact 被新合同拒绝、历史审批不继承、`SEC-002` 可信本地软隔离、
以及 `M7-test0` 中遗留的旧 queued/failed Run。它们必须在试验记录中如实区分，但不能借此扩张兼容层、
强沙箱或清库逻辑。

以下问题继续记录，但不作为本轮开跑阻断，也不在本计划实现：

- `PROJECTOR-DIAG-001`：已知 projector 错误仍可能统一报告为 `approval_projector_failed`；只要同一
  精确绑定在 preflight 与 invoke 结论一致，本轮不新增精细错误分类。
- `UI-READ-002`：通用证据资格页面信息层次差；用户已明确允许为先完成闭环而临时使用。页面必须
  保持精确对象、决定和后果，不得据此宣称可读性已验收；完整改版进入后续迭代。
- `DEPLOY-ENV-001`：显式环境透传源码修复已存在且聚焦测试通过。本轮只通过真实重装观察其结果，
  除非安装入口复现错误，否则不继续修改部署协议。

## 3. 目标架构：只重切图证据纵向边界

### 3.1 操作划分

论文图插件改为下面五个职责清晰的 Operation：

1. `science.figure.request.prepare.v1`：public Agent。
   - 输入：精确冻结的 PDF 或栅格来源；
   - 输出：唯一、类型化的 `FigureDigitizationRequest` JSON；
   - 工具：由同一插件注册的 PDF 图像枚举/只读预览工具，以及 Codex 原生只读图像能力；
   - 职责：选择精确页/图像对象、轴标定、曲线身份锚点、种子、遮挡和资格边界；不产生正式曲线点。
2. `science.figure.evidence.materialize.v1`：support Transform。
   - 输入：同一冻结来源和上述请求；
   - 输出：manifest 主项，以及 source panel、audit overlay、curve table、validation report 多项输出；
   - 职责：恢复精确 PDF 图像、跟踪可见像素、传播标定误差、生成确定性附件并逐项校验；不判断科学结论。
3. `science.evidence.extract.figure.v2`：public Agent。
   - 输入：冻结来源、类型化请求和物化出的完整输出族；
   - 输出：唯一 `ScientificIntake`；
   - 职责：用完整图证据族形成可供现有 Intake 展开和资格流程消费的科学摘要；不产生、修改或批准
     曲线点，也不把 `CurveBundle` 伪装成通用 `opaque` 来源。
   - 审查边：本 Operation 的 `ReviewSpec` 只把单一 `scientific_intake` 输出映射到审查 Agent 的
     同名端口；审查者的其他端口显式绑定同一冻结来源、请求和物化输出族。
4. `science.figure.evidence.audit.v1`：public Agent。
   - 输入：上述 `ScientificIntake`、冻结来源、类型化请求和物化出的完整输出族；
   - 输出：唯一 `EvidenceAudit`；
   - 职责：独立检查 Intake 与来源是否一致，以及图例/标注身份、轴标定、遮挡、未决项和叠图；
     不能修改 Intake、曲线或批准资格。
5. 现有图证据打包 Transform：support。
   - 输入：通过的精确图审计、被审 Intake、manifest、validation report 和曲线表；
   - 输出：标准 `CurveBundle` 与规范化审计；
   - 职责：机械规范化，继续复用现有曲线评分插件。

原来不可运行的“一个 Agent 同时写科学摘要和多组机械附件”操作退出目录；科学摘要仍由拆分后的
单输出 Agent 产生，机械附件全部归 Transform。核心 Run 继续只接收一个 Agent 主结果；集合能力继续
只存在于已支持它的确定性 Transform。不得新增数据库表、MCP 路由、Run 状态或集合恢复协议。

### 3.2 请求和来源契约

`FigureDigitizationRequest` 必须成为 OperationSpec 引用的版本化 JSON Schema，且同一模型/Schema
同时用于：

- 请求 Agent 的输出 Schema；
- 物化 Transform 的输入 Schema；
- Worker 可见提示和提交前校验；
- 确定性物化时的运行校验。

结构性约束全部放入 JSON Schema；只有“来源哈希与恢复图像一致”“身份锚点实际落在声明图像”等
跨输入规则由已有 validator/guard 实现并返回已声明 rule id。不得新增图规则注册表。

对 PDF，优先恢复其 embedded image，而不是任意页面截图。请求至少绑定 PDF 哈希、页码、图像对象、
恢复图像哈希与尺寸。Agent 的预览工具只写 Run 内只读临时文件；正式 Transform 必须独立重放相同
恢复步骤并登记来源图 Artifact，因此临时预览不成为科学证据或第二事实源。

### 3.3 科学能力下限

本轮不追求所有论文图类型，只保证当前 Fig.4 的连续线场景不低于已冻结历史资格边界：

- 支持每条线独立的可见横轴区间、种子/走廊、排除区和允许间隙；
- 支持对被另一条线遮挡的区间声明共享支持，但默认不可作为被遮挡曲线的定量观测；
- 支持同一图“部分序列可用、整体未决”，不能因黑线未决而丢掉红线；
- 每个 CSV 点保留源像素列、物理坐标、不确定性、直接/共享来源和定量资格标志；
- 只有请求明确声明且独立审查通过的直接可见点才能进入下游定量曲线；
- 结构损坏、来源哈希不符和跟踪器丢失可见实线应失败；真实遮挡或身份不确定应形成
  `unresolved`，而不是异常或伪 `qualified`。

历史记录给出的 Fig.4 预期边界是：InGaAs 红线可以形成高覆盖的直接可见证据；InAlAs 黑线因覆盖
区间保持未决。它是新实现的负控边界，不自动成为新实例的资格决定。不得从工作区旧 `targets/*.csv`
反向伪造本次数字化结果，也不得把数字化点称作论文作者提供的原始数据。

## 4. 实施阶段

### E0：冻结开跑合同和负控

修改范围：本文、当前约束矩阵、测试夹具说明；不修改运行时代码。

任务：

1. 保存当前目录事实：图提取在 `all` 中因 `agent_collection_outputs` 不可用，public 中不存在；
   TCAD Effect 及两个求解器能力可用。
2. 冻结本次论文 PDF 的引用、哈希和 Fig.4 科学范围；明确只处理论文实际存在的条件，禁止重新引入
   800°C/900°C 等来源中不存在的曲线。
3. 将历史 Fig.4 source image、请求/spec、manifest、CSV 和 overlays 定位为只读 oracle；若不能从
   历史 CAS 恢复精确请求，停止并先补齐来源，而不是根据旧 CSV 猜请求。
4. 冻结成功判据：真实 Agent 工具调用、确定性重放、独立审查、人工审批、真实求解器、结果证明、
   曲线评分和诊断全部有控制面记录；允许科学结论未决。

验收：负控必须证明“仅把插件加进 profile”仍不能调度旧提取操作。该负控是后续结构修改的基线。

### E1：重切图插件操作，不扩核心 Run

主要修改：

- `plugins/curve_score/curve_score/figure_digitization.py`
- `plugins/curve_score/curve_score/figure_science_operations.py`
- `plugins/curve_score/curve_score/operation_transforms.py`
- `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py`
- 对应插件测试

任务：

1. 注册类型化请求 Schema、请求 validator、请求 Agent prompt 和 PDF 图像只读检查工具。
2. 新增单输出请求 Agent；删除旧提取 Agent 的 collection outputs 和不再使用的数字化/集合提交工具。
3. 将 `build_digitized_figure_bundle` 接入确定性 Transform，多输出严格来自 OperationSpec 端口。
4. 调整图审计的输入和 parentage：审计精确请求及 Transform 输出族，不再依赖同一个 Agent 顺带生成的
   机械附件；新增的单输出 Intake Agent 显式消费这些附件并产生唯一 `ScientificIntake`。
5. 把 `ReviewSpec` 挂在 Intake Agent 上，只以 `scientific_intake` 作为 `subject_outputs`；图审查者的
   其他端口精确绑定同一来源、请求和完整物化族，避免让异构 Transform 输出汇入同一个 reviewer 端口。
6. 调整图证据打包 guard：只有精确独立审计覆盖同一 Intake、请求、来源、manifest、报告和曲线表时
   才能打包。
7. 保持一个 `scidiscovery.plugins` 注册入口；不向核心加入图名、Schema 名或插件名分支。

验收：

- public 目录包含请求 Agent、单输出 Intake Agent 和图审计 Agent；support 目录包含物化和打包
  Transform；
- 所有项在 Local 后端均为 available，`all` 中不再出现 `agent_collection_outputs`；
- Agent Operation 每个只有一个非集合主结果；Transform 的多输出逐项具有端口、父链、Schema 和摘要；
- 默认 core、普通 TCAD、curve-only 组合不加载可选论文图 Agent。

### E2：恢复 Fig.4 所需的科学保真度

任务：

1. 从旧资格实现复用而不是重新猜测必要的线跟踪原语；只迁入 Fig.4 实际使用的连续线、种子走廊、
   局部定义域、遮挡/共享支持和 eligibility 逻辑，marker、拟合段、箱线图不在本轮扩展。
2. 让全图状态和逐序列/逐点资格分离。一个未决序列不得抹掉另一个合格序列；未决点不得被规范化为
   可比较曲线点。
3. 固定 PDF embedded-image 恢复命令及版本可见信息；同一输入和请求连续运行两次，所有正式输出逐
   字节一致。
4. 用真实 Fig.4 oracle 对照 source panel、identity/fidelity overlay、曲线点数/可见率、遮挡区和
   资格标志。任何差异必须有科学理由并经独立图审查，不以“新算法更简单”作为放行理由。
5. 增加负例：错误 PDF/图像哈希、轴超界、种子跳到同色坐标轴、连续实线未声明断裂、重叠身份、
   伪造 eligible、只给旧 CSV 不给源图。

验收：InGaAs 可用和 InAlAs 未决能够同时封存；确定性报告与每个附件摘要一致；审查者可从来源图和
叠图复核。为审计追溯，bundle 可以保留带明确状态的 observed points，但任何评分、插值或定量主张
不得使用 ineligible/unresolved 区间；必须增加一个跨未决内部空档的评分失败负例。

### E3：只闭合预检与审批调用等价

主要修改：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`
- 对应 Approval 与 producer-family 测试

任务：

1. 从现有调用路径提取一个无状态、只读的 approval projection 准备函数；preflight 和 invoke 调用
   同一函数。invoke 仍在事务边界内复核，不复制规则。
2. 保留现有失败关闭和错误外观；本轮不新增 reason code、端口诊断、UI item、展示 Schema、前端
   框架、数据库字段或领域 HTML。

验收：

- 错加 split 后的 `problem_frame`、漏/加 sibling、替换 frozen source 均在 preflight 阶段以精确
  拒绝结论失败关闭，且零 Approval 写入；
- 正确零 sibling 的普通 Intake 以及多 sibling 的图证据族，preflight 与 invoke 结论相同；
- 不改变审批对象、选项、决定写入和后果合同；UI 可读性继续标记为已知问题。

### E4：部署组合与真实入口验证

任务：

1. 只有 E1—E3 通过后，才把 Fig.4 profile 改为
   `tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4`。
2. 通过 release builder 构建干净 wheel，从真实安装脚本重装；验证服务、UI、Codex 配置、唯一插件
   目录和已有事务回滚仍有效。不得直接从源码 `PYTHONPATH` 代替安装态证据，也不得为本轮重写回滚
   或部署协议。
3. 重启 Codex 后重新绑定用户选择的实例，核对 public/support/all 三视图、图像工具实际可用和 TCAD
   execution capability。若已有环境透传错误没有复现，不改部署协议。

验收：profile dry-run 在停服务前发现缺包/依赖错误；真实安装后图链全部 available，TCAD 两个求解器
仍可用，旧服务没有恢复为第二入口。

### E5：真实 Agent 与工具纵向探针

必须串行执行，每次只启动一个 Agent；Codex 进程树内存熔断保持 4 GiB，整轮 WSL 常驻增量不得超过
8 GiB。pytest 禁止并发和第三方插件自动加载。

顺序：

1. 真实请求 Agent 由 `operation_invoke` 返回的精确 `agent_type` 启动，关闭父历史继承；它实际调用
   已注册 PDF 图像检查工具和原生只读图像能力，提交一个 Schema 合法的请求。
2. 通过 Root 调用确定性物化 Transform，确认多输出被逐项登记，不经 Agent collection 提交。
3. 启动单输出 Intake Agent，精确消费 PDF、请求和完整物化族，提交唯一 `ScientificIntake`；以错误
   请求、少一个附件和替换来源验证其 preflight 失败关闭。
4. 沿该 Intake Agent 的编译 `review_edge` 启动全新独立图审查 Agent，检查 Intake 和完整输出族；
   子 Agent 聊天不得作为结果，只有 completed Run 的
   sealed output 可用。
5. 调用打包 Transform；用错误审计、少一张表和替换来源作三个真实入口负控。
6. 对通过审查的图 `ScientificIntake` 执行现有通用 split/qualification，并把通过审计的 CurveBundle
   作为后续实验与评分的类型化证据；不得把 CurveBundle 或 EvidenceAudit 绑定到通用
   `science.evidence.extract.v1` 的 `opaque` `source_material` 端口。旧 V15 决定不得改写或继承。

验收证据必须同时包含：安装态 Operation 摘要、实际 Worker 工具投影、工具调用成功、输出 Schema、
Run 终态、Artifact 父链、负控拒绝以及精确绑定的人工 UI 决定。页面可读性不在本轮验收，但必须
继续明确标记 `UI-READ-002`，不能把临时点击写成视觉验收通过。仅直接调用 Python 函数或用测试桩
模拟 Agent 不算通过。

#### E5.1：Fig.4 重合共享阻塞的首次修复（历史实现，科学语义未通过真实回归）

本项是 E5 现场新增的 P0 阻塞，只修改图证据插件，不扩核心控制面、Run、资格或调度器：

1. 保留现有严格 `overdraw`，新增一个与之判别的 `coincident_overlap` 声明；它允许同一重合区间内
   每列的直接可见颜色来源在已独立绑定身份的成员曲线之间变化，不允许插值或平均像素。
2. 每个成员必须有独立匹配的图例／标注身份、在重合区两侧有直接锚点、在区间内贡献直接像素；
   每列至少存在一个成员的直接像素，同时可见的成员点必须处于声明的距离上限内。
3. 每列选择一个真实直接像素作为唯一证据单位；其他成员只登记同组、同坐标、可追溯来源的共享
   遮挡行。复制行始终不具独立定量资格，验证器拒绝同一共享证据单位出现多条 eligible 行。
4. 归一化和评分继续只消费直接 eligible 行，并以回归测试证明不会跨共享复制段制造连续拟合域；
   本轮不增加相关性加权器、共享证据状态机或新的资格实体。
5. 合成测试必须覆盖颜色交替重合成功，以及缺联合逐列支撑、缺成员锚点、成员距离超限、篡改复制
   行为 eligible 的失败关闭。完成后重新运行真实 Fig.4 请求、物化与独立审查。
6. 这是 ABI 16 内的向前兼容小版本扩展：保留请求 v2、清单 v1、验证报告 v1 和既有 `overdraw`
   语义；旧生产者输出继续由新运行时读取。`coincident_overlap` 只是可选联合分支，验证器版本递增但
   同一报告模型继续读取历史版本；不得为此创建 ABI 17 或平行注册入口。

实现进度（2026-09-05）：代码与合成对抗回归已经完成；独立实现复审结论为“通过，阻断项 0”，见
`reviews/R5_E5_1_SHARED_OVERLAP_ABI16_INDEPENDENT_REVIEW.zh-CN.md`。该结论只放行重装和真实 Fig.4
重跑，`FIGURE-SHARED-002` 与 E5.1 在真实物化及独立科学审查完成前仍保持未关闭。
干净发行包已生成于 `deliverables/r5-e5-shared-overlap-abi16-clean-release/`，其 240 个受控文件均通过
`MANIFEST.sha256` 校验；包内可独立执行的部署测试为 `36 passed`。

真实回归随后证明第 3、4 项的资格语义错误：已验证 `coincident_overlap` 中的共享引用被当作不可
定量，启发式局部 `possible_overdraw` 又传播为 InAlAs 整条曲线 `unresolved`。同时真实 Audit
连续两次因 Worker 不可见的来源排除规则拒绝，并把 Intake 忠实性与来源充分性混为一个 verdict。
因此上述独立审查只作为“实现符合当时错误合同”的历史见证保留，不能关闭 E5.1 或放行 E6。当前
返工权威为
[`R5_E5_2_FIGURE_QUANTITATIVE_AND_VALIDATION_CONTRACT_REPAIR_PLAN.zh-CN.md`](R5_E5_2_FIGURE_QUANTITATIVE_AND_VALIDATION_CONTRACT_REPAIR_PLAN.zh-CN.md)；
它必须先经独立方案审查，再按阶段修复和真实重跑。

只有上述真实 Fig.4 回归形成两条科学上有意义的非空直接合格子域，E5 才能继续。不得使用已经封存
的四像素片段请求作为端到端通过证据。

### E5.3：科学图证意图与确定性测量解耦（源码实现，尚未部署验收）

本项由 2026-09-05 安装态真实回归新增，取代继续让请求 Agent 猜测数字化参数的做法。它是当前
E6 的 P0 前置条件，但不是重写通用调度器或控制面的理由。

现场证据：

- `fig4_e52_scientific_intake_revision_2` 封存为 `inconclusive`：1009 行直接像素观测全部不可定量；
  两条曲线同时违反请求自行设置的点数、可见比例和最大未声明间隙门槛。
- `fig4_e52_evidence_audit_revision_2` 封存为 `blocked`：顶部高浓度像素被换算到约 `10^15`，底部
  接近检测限的像素被换算到约 `10^19`。审查明确判定纵轴方向反转，包完整性不能弥补科学标定错误。
- 源码中的确定性换算按 `(pixel_min,value_min)` 与 `(pixel_max,value_max)` 成对插值，且既有测试
  允许纵轴 `pixel_min > pixel_max`。因此当前缺陷属于 Worker 可见输出合同和职责划分，不是调度器
  选择错误，也不应通过在换算器中盲目排序像素端点修复。

2026-09-05 的进一步职责收敛及本次实现取代上版“让请求 Agent 手填成对像素刻度”的方案。
本节是本次实现的活动状态权威；E5.2 的历史审查、历史 Run 和资格决定保持原文，不继承为本次通过。

1. `science.figure.request.prepare.v1` 的唯一公共输出改为 `FigureExtractionIntent.v1`：来源摘要、
   目标图、面板、可见系列标签；选择不明确时只给有界未决理由。公共 Schema 拒绝像素坐标、种子、
   `pixel_range`、`declared_gap_ranges`、点数、覆盖率、间隙阈值和 CSV。旧的数值请求不再是该 Agent
   的可提交结果；当前合同摘要使旧生产者输出退出当前消费路径。
2. `ingaas_fig4` 在原 `PluginDefinition` 和同一入口组注册
   `ingaas.fig4.figure-request.compile.v1` support Transform。它读取纯语义意图与冻结 PDF，使用领域
   包内 `figure_geometry.json` 生成内部 `FigureDigitizationRequest.v2`。资源参与 Operation 摘要，
   不产生第二注册表；领域插件现在显式依赖 `curve_figure_evidence`。通用核心、Run、current、审批、
   执行器及三种目录视图均未修改。
3. 当前确定性几何仅支持本文绑定的 Fig.4 两条实测线，不宣称通用 OCR 或任意论文自动识图。
   来源 SHA-256 为 `750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`，
   PDF 第 6 页、对象 241，恢复图像摘要为
   `88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a`。不同来源、恢复图像或
   不支持的标签必须拒绝；新图必须有其自身可审计的领域测量能力，不能退回让 Agent 填几何。
4. 领域资源保存 `(像素, 刻度值)` 成对测量。代码只按刻度值排列整对锚点，因此内部纵轴为
   `(685, 10^15)` 与 `(36, 10^20)`，允许像素方向递减。数值、点表、共享来源、覆盖统计和叠图全部
   由代码生成，Agent 不参与阈值选择。内部 v2 是唯一机械消费格式，不是第二条公共 Agent 路径。
5. 删除 tracker finding 到全系列 `series_unresolved` 的传播。坏种子、点数/覆盖统计及局部间隙只进入
   `tracking_diagnostics` 和覆盖条；直接观测保留，间隙切分连续区间。无足够连续点时不伪造区间，
   单个真实点仍可保存。来源和轴错误失败关闭，身份整体不确定的系列继续不可定量。
6. 对独立身份已经绑定的重合声明，逐列选择真实源像素；共享区中的空列保持缺失，不因端点缺失或
   任一成员某列未显色而否定其他真实点。共享组和供体身份保存在 CSV，并进入规范化审计的
   `shared_pixel_provenance`；共享引用不是独立重复测量。普通遮挡复制仍保留其局部不可定量标志。
   机械验证器版本为 6，继续检查真实源像素、共同坐标、身份和附件摘要。
7. 领域资源记录图示 SIMS 检测限**约** `3×10^15 cm^-3` 及灰色虚线来源说明。物化器按每行校准后
   `y_value` 局部标记低于该值的点；不改变其他点。每个系列使用独立源图叠层、身份色、共享金色
   标记及灰色缺失/红色局部限制覆盖条，供科学审查直接对照原图。

首轮本地验证（本次工作树，未提交、未安装；后续局部歧义修正见下）：

- 先复现局部坏 seed/间隙与点数门槛清零、共享成员连坐、共享空列整包失败、单点规范化失败和
  规范化共享来源丢失，再修复。最终八个文件的串行聚焦集 **62 项通过、0 跳过**（18.15 秒）；
  冻结图测试使用显式来源路径。安装资源/真实 entry-point 烟测 **1 项通过**（40.44 秒），
  领域 JSON 确实进入 wheel。
- 真实 PDF 的新纯语义 Agent 提交→领域 support 编译→图物化路径通过本地 Root/Worker 集成测试，
  核对了来源→意图→内部请求→所有物化附件的精确父链。该测试使用受控提交夹具，不冒充真实模型
  首轮识图 Run。
- 实际读取冻结 PDF、生成并查看 source panel 与最终 audit overlay：黑线 565 个直接点，其中 70 个
  低于约定检测限，局部可用 495 个；红线 805 个直接点，4 个同色标注重叠点保持局部不可用，
  可用 801 个。连续可用区间分别为 35 和 4；机械包有效。最终包指纹为
  `bcd989e9b5f6088fc30b1fb3fdb4765381b71ce21bb8a40d54f664f269d4b6d8`。
- 本次领域资源未新增真实图共享区间；共享能力由有真实像素的合成正负控验证。原图局部曲线识别、
  同色标注、近检测限噪声及共享声明仍需新合同下独立科学审查。上述统计不是科学资格批准。
- 聚焦 pytest 均使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`、无 xdist，
  每个进程限制 8 GiB；安装测试和本地重放不能替代真实部署及模型 Run。`git diff --check` 通过。

2026-09-05 独立复审 H1/M1 定向修正（已实现，等待独立复审；原 FAIL 报告不改写）：

- H1：tracker 将实际候选 tie 标记保留到对应直接点，物化器仅将这些列标记为
  `ambiguous_path`、不可定量，并在叠图覆盖条显示局部限制；规范化自然切分区间。共享点保留供体
  和本系列已有点的歧义标记，不扩散到其他列，不恢复 tracker finding 全曲线连坐。
- M1：同一 `FigureExtractionIntent` Pydantic 模型的 Schema 元数据声明标签 `uniqueItems`，
  并以 `oneOf` 表达标签与未决理由恰有一方非空；模型验证仍作为防御。未新增规则表、公共机械
  字段或通用核心修改。
- 新增 8 项反例/正例先得到 **5 失败、3 通过**，修正后 **8 项通过**。正式 Root materialize
  验证同色平行线居中 seed 的 9 个观测均不授予定量资格、局部分叉仅排除相应 3 列且保留两段
  明确区间、近邻但选择唯一时保留全部点；真实 Worker Schema 和正式 submit 同时验证三个结构
  负例及两个正例。旧冻结图测试同步记录新排除列，不修改生产几何来迁就旧点数。
- 最终四文件串行聚焦回归 **53 项通过、0 跳过**（17.66 秒），包含真实 PDF；使用上述环境变量、
  无 xdist、`ulimit -v 8388608` 的 8 GiB 进程地址空间上限，未单独采集峰值 RSS。
- 原冻结 PDF 再次经领域编译、物化及规范化并查看真实 audit overlay：黑/红直接点仍为
  **565 / 805**，局部 tie 列分别为 **459、538 / 633**；结合原有检测限和标注限制，局部可用点为
  **493 / 800**，可用连续区间 **36 / 5**，两条系列均为 available。生成物位于本机
  `/tmp/e53-h1-m1-review-uueojofp/`，包指纹
  `493ce0247373c7a18ef36ded3d43e10c82a2007fac560fc4e1fdf85fc32dbff6`。
  分系列叠层与缺失/局部限制覆盖条仍可对照源图；本次查看不替代独立科学资格审查。
- `git diff --check` 通过；实现已提交为 `979a118`。2026-09-06 的 M7 事务化重装后，两项服务均从
  `/opt/scidiscovery-m7/site` 运行，领域 compiler 与 geometry 的安装摘要与源码一致，审批页返回 200；
  安装态 catalog 已显示公共 `figure_intent` 和 support 编译操作。通用自动识图缺口、真实模型首次语义选择及独立科学
  审查仍未完成，E6 继续关闭。

2026-09-06 安装态首个语义请求后的 panel 合同修正（源码已实现，未部署）：

- 现场 Root 封存结果的来源摘要、`figure='Fig. 4'` 和两条系列标签正确，但
  `panel='single panel (no panel label)'` 在 support preflight 后触发编译失败。根因为公共合同未
  说明无标签面板的结构表达，而领域资源只接受私有固定字符串 `whole figure`；这不是测量或
  调度生命周期错误。真实模型首次语义选择已发生，但完整图证链仍未通过。
- 同一 v1 公共模型将必填 `panel` 扩展为字符串或 `null`：整图或无可见面板标签用 `null`，
  否则复制准确的可见面板标签。Schema 描述与 Worker 提示复用同一合同文本。原有字符串
  Artifact 仍可解析，机械字段仍不属于公共输出。
- 本领域 compiler 对当前整图资源接受 `null`，仅保留既有精确 canonical `whole figure`
  的兼容性；不新增同义词表、不忽略任意面板文本、不变更数值几何或通用核心。已封存描述句
  **不受理编译，也不改写或重新解释为 null**；保留原结果和失败证据，待部署后由公共请求
  Operation 基于同一来源创建新的语义意图修订，再以其精确绑定执行 support。
- 测试先复现 **9 失败、9 通过**；修复后三文件聚焦回归 **23 项通过、0 跳过**（14.85 秒），
  覆盖实际 Worker Schema/submit、真实 PDF 的 null 与旧 canonical 正式 Root 编译→物化父链、
  错误面板及现场描述句拒绝、机械字段拒绝。串行、无 xdist，使用
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2` 与 8 GiB 地址空间上限；未测峰值 RSS。
  33 项约束登记结构测试 **1 项通过**（0.05 秒），`git diff --check` 通过。
  本地测试不替代部署后重跑与独立图审查，E6 继续关闭。

`RUN-DIAG-002` 的去敏运行摘要不在本次改动内，继续作为 P1 后续项；不读取 Worker 草稿或隐藏上下文。

最小验收：同一冻结 Fig.4 来源由真实请求 Agent 首次输出科学意图；确定性编译后的纵轴必须满足
底部像素对应 `10^15`、顶部像素对应 `10^20`；请求 Agent 输出中不存在算法点数门槛；两条曲线的
实际点数与覆盖质量由物化报告给出；独立图审查通过轴方向、身份、遮挡、共享支持和定量边界。不得
使用提示词硬编码 Fig.4 像素值作为正式通过证据，第三版诊断 Run 只保留为复现材料。

### E6：端到端开跑门

进入完整科学实验前，由未参与实现的审查者复核：

1. E0—E5 每阶段的正例、目标入口负例和真实安装证据；
2. 33 项中至少 AUTH-003、ROLE-001/002、DET-001/002、TOP-002、EVD-001、HIL-001、
   PLG-001/002、RES-002 和 SEC-002 的诚实状态；HIL-002、UI-001/002 保持当前未完成状态，不作为
   本轮通过项；
3. 通用核心没有 Fig.4/TCAD 分支，调度器没有固定阶段表，插件仍只有一个注册入口；
4. 未增加 Agent collection 协议、第二 current、第二校验器、第二注册表、第二任务生命周期或历史
   兼容路由；
5. 实际 Fig.4 科学边界没有被“流程成功”覆盖。

只有 E5.3 实现与真实回归结论为 PASS 且阻断项为零，才开始假设、实验、TCAD 与评分的完整端到端实验。若 E2 无法从冻结
来源复现实图边界，应停在图证据能力修复，不得绕过并使用旧 targets 曲线。

## 5. 端到端实验本身的验收

开跑后仍需满足：

- 调度器每次只依据当前矛盾和唯一 public 目录选择下一行为，不执行本文作为固定 DAG；
- 每个可被下游科学消费的 Agent 结果由精确 review edge 的独立 Agent 审查；图请求只是后续完整图
  审查覆盖的中间方法配置，不为它增加第六个审查 Agent；
- 数值判据、提取算法和误差传播归实验设计/确定性工具，不塞回假设文本；
- 修订有界且问题指纹无进展时停止；允许不确定；
- TCAD 外部执行必须经过精确 UI 授权，历史 replay 不冒充新求解；
- 求解输出经过收集、runtime attestation、曲线规范化和确定性评分后，诊断 Agent 才能解释；
- 最终记录结论准确性、严重证据错误、修订次数、工具失败、token、墙钟时间和峰值内存；一次运行不
  宣称统计优越性或跨领域通用性。

## 6. 明确延期

以下内容不阻断当前可信本地 Fig.4 实验，并明确延期：

- 通用 Agent collection output、远程集合恢复或新的 OutputBundle 生命周期；
- Hardened 后端功能补齐、多租户强隔离和 `SEC-002` 关闭；
- 全局 current/qualification 重构、历史 V14/V15 对象迁移或清理旧 Run；
- 通用候选规划器、科学图、固定 Fig.4 调度器或第二行动类型体系；
- marker、拟合段、箱线图和任意论文图自动理解；
- 全站 UI 重写、前端框架和自定义插件模板；
- projector 精细 reason/port 诊断及审批页科学信息层次改造；
- 小概率摘要碰撞、非阻断安装状态提示和与本次真实入口无关的代码清理。

## 7. 复杂度预算与停止条件

- 核心允许的新增仅限：preflight/invoke 共用的 approval projection 私有 helper 和必要测试；不得新增
  公共 MCP、数据库状态或领域分支。
- 图像复杂度必须留在可选插件/曲线算法包；复杂算法可以因为真实科学对象而存在，但不能转化为控制
  状态或通用 Schema。
- 删除旧不可运行图 Agent 的集合工具与声明后再计新增；不得同时保留两条数字化生产路径。
- 若实现开始要求修改 Run 生命周期、Scheduler、current、Execution 或三处以上核心模块，立即停止
  并重新审视操作划分。
- 若真实 Agent 不能稳定生成请求，优先改进可见 Schema、提示和图像检查工具；不得降低运行校验或让
  调度器代写科学字段。

## 8. 当前恢复点

当前闭环停在 `fig4_e52_evidence_audit_revision_2` 的已封存 `blocked` 结论；第三版请求 Run 只作为
现有合同的诊断，不推进 E6。完成 E5.3 后，应在同一用户明确选择的 ResearchInstance 中创建新的
科学图证意图、确定性执行请求、图证据、审计、CurveBundle 和 Intake revision；
不得原地修改 V15 对象或继承旧审批。实例内旧 queued/failed Run 只作为历史记录，不自动恢复、调度
或删除。

## 9. 审查记录

- 首轮独立审查：`reviews/R5_PRE_E2E_MINIMAL_CLOSURE_PLAN_INDEPENDENT_REVIEW.zh-CN.md`，结论
  `FAIL`、阻断 2。两项均源于初版四操作拓扑删除了单输出 `ScientificIntake` 生产者：类型化图产物
  无法绑定通用 `opaque` 来源端口，异构 Transform 输出也无法直接形成现有编译器支持的 review edge。
- 本版修正只在图插件拓扑中增加单输出 Intake Agent，并把 ReviewSpec 挂在其单一输出上；未修改
  核心端口、Run、调度器、资格体系或 Agent 集合输出边界。
- 第二轮独立复审：`reviews/R5_PRE_E2E_MINIMAL_CLOSURE_PLAN_INDEPENDENT_REREVIEW.zh-CN.md`，结论
  `PASS`、阻断 0。该结论对应范围较宽的第二版。
- 第三版进一步删除非阻断工作：不改 UI、不增加 projector 精细诊断、不再次开发部署透传；只在
  真实安装中验证已有修复。最小范围独立审查见
  `reviews/R5_PRE_E2E_MINIMAL_SCOPE_INDEPENDENT_REVIEW.zh-CN.md`，结论 `PASS`、阻断 0，只放行
  E0/E1。审查同时明确不得新增第六个请求审查 Agent，E4 不得重写部署/回滚协议。

## 10. 实施进度

- E0：完成。精确来源、Fig.4 PDF 对象、480°C/8 分钟科学范围、历史负控和旧集合操作不可调度负控见
  `evidence/R5_PRE_E2E_E0_FIG4_BASELINE.zh-CN.md`。
- E1：完成并经独立审查通过（阻断项 0）。可选论文图插件已经重切为五操作拓扑，精确 PDF
  来源链、单输出 Agent、机械附件 Transform 和最终父链均已闭合；证据见
  `evidence/R5_PRE_E2E_E1_FIGURE_TOPOLOGY_IMPLEMENTATION.zh-CN.md`，独立结论见
  `reviews/R5_PRE_E2E_E1_INDEPENDENT_REVIEW.zh-CN.md`。
- E2：完成。首轮独立科学审查为 `FAIL`、阻断项 2；结论见
  `reviews/R5_PRE_E2E_E2_INDEPENDENT_SCIENTIFIC_REVIEW.zh-CN.md`。现已只修正红线可见掉点和同色
  SEM 标注资格：805 个 observed、801 个 eligible、最大空档 2 像素；91 项聚焦测试通过，等待独立
  复审为 `PASS`、阻断项 0，只放行 E3；结论见
  `reviews/R5_PRE_E2E_E2_INDEPENDENT_REREVIEW.zh-CN.md`。实施证据见
  `evidence/R5_PRE_E2E_E2_FIG4_SCIENTIFIC_FIDELITY.zh-CN.md`。
- E3：完成并经独立跨边界审查通过（阻断项 0）。preflight/invoke 共用唯一只读审批投影准备函数，
  invoke 仍在写入前复核；证据见
  `evidence/R5_PRE_E2E_E3_APPROVAL_PROJECTION_EQUIVALENCE.zh-CN.md`，审查见
  `reviews/R5_PRE_E2E_E3_INDEPENDENT_REVIEW.zh-CN.md`。
- E4：安装前工作完成并经独立审查通过（阻断项 0），真实事务化重装及安装态核验已通过；证据见
  `evidence/R5_PRE_E2E_E4_DEPLOYMENT_READINESS.zh-CN.md`，审查见
  `reviews/R5_PRE_E2E_E4_PREINSTALL_INDEPENDENT_REVIEW.zh-CN.md` 与
  `reviews/R5_PRE_E2E_E4_POSTINSTALL_INDEPENDENT_REVIEW.zh-CN.md`。当前真实 Root 目录已有 49 项
  Operation、五项图链和两个 TCAD capability，安装后独立收口 `PASS`。E4 已完成；等待用户通过
  唯一管理页重新绑定既有实例后启动 E5。
- E5：执行中。ABI 15 已证明完整生产族正例成立，缺表、混族和旧代际对象均在 Run 创建前拒绝；真实
  Intake 的独立审查因一项曲线状态措辞错误返回 `blocked`。该失败暴露的不是新科学任务，而是同一
  Operation 缺少创建／修订双模式。新方案不增加 `revise.figure`，只以可选全有或全无修订输入组和
  冻结绑定派生的 active 总函数复用原 Agent、Schema、工具、完整图族及审查边。计划独立复审通过，
  P4 第二轮独立实现复审已通过，剩余阻断 0；clean release 和真实配置 `--dry-run` 均通过。当前
  生产服务尚未安装该新 Operation digest，必须重装后从新创建模式重跑 Intake，不复用旧 digest
  的 Intake 冒充新合同结果。
