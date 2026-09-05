# R5-G 最终工程收口独立审查

日期：2026-08-30  
审查对象：共享工作树中的 R5-G 最终工程候选、D3/D4-Q/D4-H/D4-H2 最终报告、真实持久 run 与清洁发布候选  
审查基线：`baseline/8765-codex`，`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`  
审查权限：只读审查与测试；本报告是唯一新增文件，未修改或回退生产代码、测试、计划、架构、状态或清单

## 一、最终结论

未发现工程实现阻断或重大缺陷。

**工程实现通过，科学验收未通过，R5-G 关闭但 R5 发布不放行。**

这个结论严格分为三个维度：

| 维度 | 结论 | 边界 |
| --- | --- | --- |
| 实现质量 | 通过 | 直接完整对象修订、ABI 8 代际与当前资格、独立 reviewer、停止门、发布集合和全仓回归均闭合；未恢复 patch/receipt/TCAD 特判 |
| 科学效果 | 未通过 | D4-H 与唯一一次 D4-H2 的新 critic 均为密封 `blocked`；Task 完成没有被冒充为科学通过 |
| 审批 UI 产品质量 | 未通过 | 回环 UI 的单一写入权威和精确主体绑定有效，但信息架构、可理解性和操作效率经两次真实现场观察仍未通过 |

R5-G 到此失败关闭于假设阶段。不得第三轮修订，不得进入实验设计、solver 或新外部执行，也不得以放宽 reviewer、资格、current、来源或审批门来改写本结论。

## 二、审查范围与证据纪律

完整阅读并交叉核验了：

- `docs/plans/reviews/R5_G_DIRECT_OBJECT_REVISION_D3_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4Q_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4Q_POSTRUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4H2_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/reviews/R5_G_D4H2_POSTRUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md`、`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 与 `docs/ARCHITECTURE.zh-CN.md`；
- direct-revision catalog/Root/Task/Worker/Approval 生产路径、D4 一次性脚本、对应测试及真实持久状态。

工作树包含 R1—R5 的累计未提交改动，不能把 `HEAD..工作树` 全部差异归因于 R5-G；本审查没有猜测远端 base。真实科学状态只以只读 SQLite `mode=ro&immutable=1`、Artifact registry、CAS payload、密封 scheduler signal 和阶段报告为证据；未采信 child chat、workspace draft、Codex final/events 或 daemon 日志中的科学内容。没有调度 Agent、运行 solver、访问网络、写审批或修改真实 state。

## 三、实现质量审查

### 3.1 直接完整对象修订消除了根因

`src/scidiscovery/operations/invoke.py` 的 `direct_revision_ports()` 是直接修订形状的领域无关总函数；`catalog.py` 对任何含 `revision_base` 的声明复用该函数并以 `direct_revision_contract_invalid` 失败关闭。它要求科学 Agent、单一必需 base、单一同 Schema/media/codec/resource 的完整输出及精确 ReviewSpec。Root 的生产者准入再次调用同一个函数，并只允许旧冻结 reviewer 对精确旧 subject 的输出作为 change request；`accepted_verdicts=None` 只证明审查关系，不授予通过资格。

新对象由新 Task 经受控文件生命周期封存，父链包含 instruction 与全部冻结输入；普通下游仍要求关于新 subject 的新独立 review。`revision_base` 和 `change_request` 保留在谱系中，但 evidence-source 投影只接受 `claim_evidence`、`evidence_inventory`、`cached_excerpt` 及受控 Web/PDF 证据，不把旧草稿或评审意见提升为事实来源。

对 `src/`、`plugins/`、`roles/`、部署和当前双语架构正文的定向扫描未发现以下旧协议残留：

- `StructuredRevision`、`UnchangedEvidenceReceipt`、`RevisionDiff`；
- `structured_revision`、`unchanged_evidence_receipt`、`revision_base_port`、`allowed_revision_paths`；
- `science.revision.apply.*`、`science.evidence.receipt.*`；
- `DeckFilePatch`、`ParameterBindingPatch`、`DeckProjectPatch` 及 TCAD 跨 Artifact patch/apply/profile。

仍存在的 `worker_file_apply_patch` 是 Task 私有工作副本编辑能力，不是跨 Artifact 修订协议；已注册的 TCAD 完整工程 compare/diff 也不生产 patch 或授予资格。当前生产数据库迁移仍只有 `0001_artifacts.sql`，没有新增修订表、状态机、注册表、兼容 facade 或领域 id 白名单。直接修订因此是普通专业 Agent 的完整对象生产，不是把旧补丁断裂移动到另一层。

### 3.2 D4-Q ABI 8 代际与当前资格诚实

当前已安装 D4 runtime 独立编译得到 ABI `8`、47 项 Operation（`public=25`、`support=22`、`internal=0`）。当前关键编译身份与持久报告一致：

- `science.evidence.qualify.v1` operation digest：`5d639ffaf9fd61f53ba1c9fb58bb59213a62dddc4a33166b75b3d41bb789ca16`；
- approval contract digest：`e77be3ab60b964ec16ecde3da6be0d4aa614913f7a91a52a113091697d628a0c`；
- `science.hypothesis.revise.v1` digest：`17ee7a2305dbb900ead87ca358b429f00de416255243af6f00e6f21ff52dda93`；
- `science.hypothesis.criticize.v1` digest：`fbb97082dd5c6c201e93b452066c7d3a751fa64c9aef06b65ec073c3048f1321`。

真实 run `.scidiscovery/r5-e2e-private/replay-live-20260830-03` 的内外 migration report 字节一致，SHA-256 均为 `257a2b9f613e7004786c49d587e7144d2b959ec29d2ff0e54f67abb1f1619939`。独立逐项复算 schema 2 的 12 个映射确认：旧 descriptor 规范 JSON 中只删除值为 `null` 的 `output.revision`；新 descriptor 以旧 descriptor 为唯一 parent 和 supersedes；源状态 12 个 Task ref 保持旧对象，新状态 task row 指向新 descriptor；旧科学 output/scheduler signal 的 task edge 未改写；报告冻结的四个控制数据库摘要仍与源状态一致。

D4-Q 没有给 ABI 6 旧 Agent 输出或旧人工决定换 digest。它在 ABI 8 中重新运行当前 extract 和独立 audit，重新 split，并由当前 qualification provider 创建新的九主体 ApprovalRequest。只读复核确认新决定为 `approve`、认证方式为 `local_ui_session`、`previous_decision_ref=null`；新旧 compiled identity 不同，报告明确 `old_decision_inherited=false`。因此“当前资格”是新的不可变代际记录，旧资格只作为历史事实。

### 3.3 D4-H2 后停止门真实生效

真实 ABI 8 状态当前恰有 18 个 Task：`completed=17`、历史 `failed=1`、非终态 `0`。D4-H 与 D4-H2 分别只新增一次 `science.hypothesis.revise.v1` 和一次 `science.hypothesis.criticize.v1`：

- 两个 revision Task 均输出完整 `scidiscovery.hypothesis-proposal.v1`；
- 两个 critic Task 均精确绑定各自的新 portfolio 与同一 approved foundation；
- output envelope 的 task edge、critic subject 和 scheduler signal 的 task edge 均回指各自精确 descriptor；
- 两个密封 critic verdict 均为 `blocked`。

首轮报告 SHA-256 为 `4d6e64e89db11ef23a16c214b9fdba44e6a72f7b376b42402e654b5c1d101444`；H2 followup 报告 SHA-256 为 `3cd745b2d996428496ec4b77be317e9c77e1e87d290ac57fc8fe667c1f888d8f`。两份报告均把 `revision_task_state=completed`、`critic_task_state=completed` 与 `critic_verdict=blocked` 分开记录；H2 还固定：

```text
review_contract_admissible=false
stage_admissible=false
experiment_design_released=false
further_revision_released=false
```

Task descriptor 中没有 `science.experiment.design.v1`；scheduler binding 中只有首轮 revision 与 H2 revision，没有 H3/第三轮；Execution 表只有 2026-08-29 创建的历史 frozen replay，状态为 `collected`，没有本轮 solver 或新外部执行。因此科学 `blocked` 没有被冒充为框架失败或科学通过，停止门已经在真实持久状态生效。

新增 `scripts/r5_g_hypothesis_revision_followup_stage.py` 只是一次性验收编排：它固定读取已封存 D4-H blocked checkpoint、ABI 8 qualification 与三项精确输入，只调用两个既有 Operation，并恒定关闭实验和进一步修订。D4-H2 名称没有进入 `src/` 或插件声明；没有新增核心修订补丁、Operation、Schema、validator 或资格权威。

## 四、架构约束与奥卡姆判断

仓库仍没有逐项编号的“33/33”自动验证器，本报告不伪称运行过这样的脚本。按计划冻结的行为约束族做跨边界复核，未见退化：

| 约束族 | 独立判断 |
| --- | --- |
| 单一权威与目录投影 | 只有 `scidiscovery.plugins` 一个 entry-point group和一个启动编译 `CompiledCatalog`；public/support/internal/all 是同源只读投影，不是平行注册表 |
| 不可变性、谱系与实例 | 旧对象不覆盖；修订、review、qualification 均形成新 Task/Artifact/Approval 与精确父链；ABI 代际显式 parent/supersedes |
| 最小上下文与文件通信 | Agent 权限、输入 exposure、工具、网络和资源由 CompiledOperation 投影；Worker 通过 Task 私有文件、validate/finalize 和密封 output 交付，聊天不是结果通道 |
| 科学与控制边界 | 专业 Worker 产生完整科学对象和 verdict 内容；控制层只拥有身份、Schema/资源校验、生命周期、资格、current 与副作用门；确定性 Transform 不承担 Agent 判断 |
| 独立评审与人工决定 | 新 subject 必须有新 reviewer；旧 review 只能作 change request；人工决定只由回环 UI 写入并绑定精确 subjects 与 compiled identity |
| 失败关闭与副作用 | 畸形修订、错误 reviewer/subject、旧 provider、缺少当前资格或非 `pass` review 都不能进入下游；Execution 生命周期未复制或绕过 |
| 插件与领域边界 | Root/Task/Scheduler/UI 未增加 D4-H2、TCAD 或 Schema 名分派；领域工具、validator、projector 和 adapter 仍由插件声明 |
| 恢复与原型诚实 | 一次性 ABI 转换有安全 staging、终态门和完整报告验证；Codex 工具不可见性仍明确是提示约束原型，没有夸大为进程级沙箱 |

奥卡姆门成立：`scripts/r5_current_metrics.py` 独立复算生产 Python 为 **141 个文件、59061 行**；相对 D2 的 60313 行净删 1252 行。直接完整对象修订复用既有 OperationSpec、Task、Artifact、Approval 与 reviewer，不引入万能 RevisionManager、多代际兼容 Schema、第二 readiness/qualification/current 权威或固定科学 DAG。

## 五、审批 UI 产品质量

真实状态证明审批安全写入和精确九主体绑定有效，但不能推出产品可用性通过。持久现场记录明确写明大量完整对象平铺、信息层级不足、关键科学结论/限制与来源身份缺少优先摘要；同日两次真实资格审批均得到“基本不可读/排版过差”的反馈。

因此必须保持：

- 审批生命周期、精确主体和单一写入权威：有效；
- 已封存决定：有效，不因 UI 缺陷被改写；
- 审批 UI 信息架构、可理解性和操作效率：**未通过**。

安全渲染单元测试、一次成功点击或科学链停止都不能把这一产品缺陷改写为通过。

## 六、独立测试、发布与清洁度证据

所有测试均严格串行并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
```

独立执行结果：

1. `python -m pytest -q -p no:cacheprovider`：**323 passed in 99.86s**，退出码 `0`，最大 RSS `128580 KiB`；
2. `git diff --check`：通过；
3. `python scripts/r5_current_metrics.py`：`production_python={files: 141, lines: 59061}`；
4. 生产旧 patch/receipt/TCAD 补丁标识扫描：零命中；
5. 测试结束后 `src/`、`plugins/` 中无 `build/` 或 `*.egg-info`；清洁候选中同样无这些目录；
6. 清洁候选 `/tmp/scid-r5g-closure.hAWsVO/scidiscovery-agent`：**374 个文件、373 条 manifest 记录**；候选根执行 `sha256sum --check --strict --quiet MANIFEST.sha256` 通过；
7. 审查开始时根 `MANIFEST.sha256` 与候选清单逐字节一致。随后主计划修正了非自引用收尾表述，本报告又成为新的发布见证，因此当前根工作树按约定处于待最终机械重建状态。

第 7 项不是实现故障。`MANIFEST.sha256` 不能包含自身，本报告也不能预先冻结其自身间接依赖的摘要。本报告落盘后，父会话必须使用唯一发布生成器做一次机械重建，并再次确认最终候选的文件数、记录数和包内 strict SHA；最终生成的根清单才是发布集合权威。这一动作不得改变本报告对科学未通过、UI 未通过和 R5 发布不放行的判断。

## 七、关闭边界

R5-G 已经完成了工程实现、真实直接修订与停止门验证；其科学效果没有通过，审批 UI 产品质量也没有通过。关闭 R5-G 表示停止本轮链路并保存失败证据，不表示 R5 发布资格成立。

最终结论保持唯一且不可扩张：

**工程实现通过，科学验收未通过，R5-G 关闭但 R5 发布不放行。**
