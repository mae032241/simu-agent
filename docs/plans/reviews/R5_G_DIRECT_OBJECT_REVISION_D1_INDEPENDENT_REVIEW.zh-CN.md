# R5-G 直接完整对象修订 D1 独立实现审查

日期：2026-08-30  
审查范围：当前共享工作树中的 D1 精确候选  
审查者：未参与 D1 实现的独立审查者

## 结论

**打回。不得进入 D2。**

实现的核心数据流没有发现已证实的准入旁路：结构分类是领域中立的，Root 仍只有一个 producer-output admission 权威，完整 intake 修订、新审计、新 UI 资格和普通下游失败关闭能够闭合。但 D1 的两个明确完成门没有获得候选所声称的测试证据：未知插件非法形态/调用矩阵完全缺失；TCAD 只运行到修订 `operation_preflight`，没有真实创建并完成 TCAD revision Worker。后者也使实施记录中的“真实 TCAD 生命周期证明”超出了实际证据范围。

按计划的问题分类，这两项均属于**测试与冻结证据缺口**，不是允许通过局部放宽生产准入来修补的实现问题。最小修复只需补真实测试并同步实施记录；当前没有证据要求修改 Root、TaskService、OperationSpec 或新增实体。

## 阻断项

### F1（阻断）：缺少未知插件非法直接修订形态和真实调用负例

位置：

- `src/scidiscovery/operations/invoke.py:115`—`153`
- `tests/operations/test_general_science_plugin.py:348`—`372`
- `tests/operations/test_tcad_operation_plugin.py:552`—`559`
- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md:338`—`339`

当前测试中 `direct_revision_ports()` 只有五次调用：通用 intake 正例、通用 hypothesis 正例、旧 intake apply Transform 反例，以及两个 TCAD 正例。没有未知测试插件覆盖以下 D1 完成门：Transform、Effect、Approval、无 ReviewSpec Agent、多/缺 `revision_base`、集合/多主输出、不同 Schema、媒体、codec 或 schema resource、review subject 不匹配等非法形态；也没有把这些形态绑定到一个具有未通过审查的旧对象并经真实 Root preflight/invoke 证明其不能获得 `revision_base` 免审。

这不是仅靠阅读 `direct_revision_ports()` 即可取消的测试门。D1 的目的正是让未知领域只凭 OperationSpec 结构获得或失去准入；缺少未知插件真实负例时，未来对结构总函数、Root 调用顺序或旧 Transform 重叠的回归不能被现有领域正例捕获。

最小修复：

1. 增加一个仅测试态、非安装入口的未知插件/目录，声明一个合法完整对象修订形态作为对照；不要迁移 D2 的 blind producer fixture。
2. 从同一测试插件派生上述非法结构，断言 `direct_revision_ports()` 返回 `None`；迁移期允许它们编译时，还必须经真实 Root preflight 证明未通过旧对象仍以通用准入原因失败，而不是获得免审。
3. 至少覆盖旧输出未声明 `revision_base`、reviewer 合同漂移、审查另一对象、另一实例和普通下游仍失败关闭。现有通用测试已覆盖前两者中的部分，可复用而不要复制第二套准入夹具。
4. 不得为这些测试向 Root 增加 operation id、Schema、插件名、角色名或端口名分支；若测试暴露结构缺陷，应先按架构/合同问题重新审查，而不是增加例外。

### F2（阻断）：TCAD 修订只做 preflight，未证明 revision Worker、领域工具和完整工程输出

位置：

- `tests/operations/test_tcad_operation_plugin.py:1578`—`1896`
- `plugins/tcad_artifact/tcad_artifact/plugin.py:357`—`406`
- `plugins/tcad_artifact/tcad_artifact/plugin.py:427`—`437`
- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md:362`—`364`
- 同计划第 6 节正例第 6 项

现有 TCAD 测试真实完成了 initial author 和 reviewer，并在局部把 reviewer signal 投影为 `revise`；随后只调用 `operation_preflight` 并断言 admissible，再证明普通 reviewed-package 失败。它没有调用修订 Operation 的 `operation_invoke`，没有领取/物化修订 assignment，没有核对修订 Worker 仍获得注册的 `worker_tcad_debug_run` 与私有 deck workspace，也没有 validate/finalize 一个完整的新 `tcad.deck-project.v1`。

因此它足以证明“TCAD 没有 Root 特判且结构准入可达”，不足以支持实施记录中的“真实 TCAD 生命周期证明”，也没有闭合计划要求的“TCAD author revision 继续使用注册领域工具并输出完整工程”。这类跨 Worker/工作区/工具/父链的风险不能由静态目录断言或 preflight 替代。

最小修复：

1. 在既有 TCAD 生命周期测试中，对同一精确 prior project 和非通过 exact review 实际执行 `tcad.deck.author.revise.v1` 的 `operation_invoke`。
2. 走真实 Task/Worker claim、materialize、受控 deck 文件生命周期、validate 和 finalize；使用现有测试 runtime/fake debug adapter，不运行真实 Sentaurus。
3. 断言修订 assignment 仍只有 author 所需工具并包含 `worker_tcad_debug_run`，reviewer 不获得该工具；封存输出是完整 `tcad.deck-project.v1`，父链包含 prior project、exact review 和声明的科学/能力输入。
4. 断言旧 review 不能资格化新 project；新 project 未经全新 exact reviewer pass 仍不能进入 reviewed package。D3 才要求完整重放 runtime-failure 分支，本轮至少真实闭合 review-request revision。
5. 把实施记录改成与实测一致；不得把 preflight 描述为完整 Worker 生命周期。

## 已通过的语义和架构核验

### 1. 结构分类保持领域中立

`direct_revision_ports()` 只读取 executor kind、consequence、输入 usage/基数、输出基数/集合、ReviewSpec、Schema、媒体、codec 和 schema resource 的编译组件身份。函数中没有 operation id、Schema 字面名、插件名、角色名或端口名判断。旧 apply Transform 返回 `None`，D1 迁移期没有被错误授予免审。

### 2. Root 仍是单一 producer admission 权威

`mcp_root_operation_routes.py:1123` 的唯一输入准入顺序仍是 producer-output admission、compiled cohort 与 claim-admissibility；直接修订分支内嵌在同一个 `_validate_producer_output_admission()` 中，没有 readiness 或第二服务复制规则。

直接 base 在任何免审前仍必须：

1. 来自可恢复的冻结 Operation 输出合同；
2. 其旧输出明确允许本次 `revision_base` usage；
3. 新 Operation 满足完整结构总函数；
4. 旧输出的 reviewer operation、reviewer input port 和 accepted verdicts 与新输出完全一致；
5. 若绑定 change request，TaskService 的原 `is_exact_reviewer_output()` 必须证明 completed reviewer、精确 subject ref 和精确 reviewer input port。

传入 `accepted_verdicts=None` 只关闭 verdict 资格过滤，仍要求调度信号存在和精确 reviewer 关系。普通下游继续传冻结的 accepted verdicts；`revise`、`blocked` 或 `inconclusive` 没有被当作资格。

### 3. 新对象不继承旧资格，父链与 evidence source 已分离

通用 intake 实测链证明：完整新对象封存后，用旧 audit 进入 split 会失败；必须创建新的独立 audit。新资格 projector 只接受完整 producer family、新 audit 和完整 frozen source set；删掉真实来源会失败。新的 UI 决定绑定新 subjects 后，下游才可通过。

Agent producer family 保留全部 Task/Artifact 父输入，但 `evidence_sources` 只从 `claim_evidence`、`evidence_inventory`、`cached_excerpt` 和受控 web/PDF 来源投影。当前 D1 intake 修订中 prior draft 和 change request 仍在不可变父链，却不进入 frozen source set。没有新增来源表、收据或资格状态。

### 4. 通用修订复用原专业 Agent

`science.intake.revise.v1` 与初次 intake 共用 `evidence_agent`、`evidence_prompt`、`INTAKE_OUTPUT`、完整 ScientificIntake Schema/validator/semantic contract 和工具；hypothesis 修订同样复用 `ideator_agent`、`ideator_prompt`、`HYPOTHESIS_OUTPUT` 和批准的 foundation。两者的 Task 输出 `revision` 均为 `None`，Worker 写入完整对象而非 StructuredRevision。

通用补丁 Agent 专属提示/validator 已删除；旧 apply/receipt Transform、Task revision 投影和 Root applied-revision 识别仅作为 D1/D2 回退重叠保留，未获得直接修订免审。

### 5. TCAD 没有核心领域分支

TCAD author Operation 共用同一 `_author_operation()` 生产完整 project，initial、review-request revision 和 runtime-failure revision 都声明同一 ReviewSpec。project 输出由 TCAD 插件声明 `revision_base` usage，review 输出由插件声明 `change_request`/`prior_signal` usage。Root 和 `operations.invoke` 没有 TCAD/curve/InGaAs 分派。F2 只否定生命周期证据完整性，不否定当前静态合同。

### 6. 没有新增 Task 状态或第二查询权威

TaskService 继续使用原 `is_exact_reviewer_output()`；仅把 `accepted_verdicts` 改为可选，以便同一精确关系查询在 change-request 语义下不授予资格。全仓调用点只有直接修订关系检查传 `None`，普通下游传冻结 verdict 集合。TaskService 自身方法数仍为 40，没有新表、状态机、注册表、缓存或 reviewer 查询副本。

## 复杂度与 D1/D2 边界

独立复算与候选记录一致：

- 生产 Python：143 文件、60303 行；
- `operations` 包：7 文件、2097 行，低于 D1 临时上限 2100；
- 通用科学声明：959 行；确定性组件：1036 行；合计 1995，较 D0 的 2065 减少 70 行；
- Root 聚合：3146 行；TaskService 聚合：6221 行。

ABI 7、通用/TCAD Operation digest、安装态摘要、R5 fixture 的资格端口和机械指标属于 D1 合同的直接派生变化。curve experiment、blind producer fixture、`scripts/r5_g_science_chain.py` 和旧协议删除仍未迁移；当前脚本仍带旧 diff/receipt 端口，符合计划把实际评估脚本迁移留到 D2 的阶段边界，不能在 D1 运行它并宣称闭环。

40 行 operations 临时重叠有明确撤销期，当前 2097 没有越界；D3 必须撤销余量并证明净删除。除 F1/F2 的测试缺口外，未发现为 D1 新增 RevisionManager、policy、会话、数据库表、第二目录或兼容 facade。

## 独立复测

每条测试命令均严格串行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

1. D1 聚焦矩阵（通用完整修订、TCAD 合同/preflight、Root/Task/Catalog 责任、安装态入口）：`35 passed in 40.42s`。
2. `pytest -q tests/operations`：`269 passed in 89.55s`。
3. `pytest -q`：`306 passed in 98.67s`。
4. 受影响生产文件 `python -m py_compile`：通过。
5. `git diff --check`：通过。
6. `scripts/r5_current_metrics.py`：与上述指标一致；冻结生成器未修改。

绿色回归不能替代 F1/F2 明确缺失的跨边界负例和 TCAD revision Worker 正例，因此不据此放行 D2。

## 复审放行边界

只允许修复 F1、F2 及同步 D1 实施记录，然后重新独立审查 D1。修复不得迁移 curve experiment、blind producer 生产者族或实际 R5-G 脚本，不得删除旧 apply/receipt，不得新增 Root 领域判断、Task 查询、持久状态或注册表。两项都由真实测试闭合后，复审才可考虑只放行 D2。
