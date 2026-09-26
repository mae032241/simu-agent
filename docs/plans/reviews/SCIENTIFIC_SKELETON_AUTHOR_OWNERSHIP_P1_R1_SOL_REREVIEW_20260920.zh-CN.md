# Scientific Skeleton / Author Ownership P1-R1 修复：独立 SOL 复审

结论：**PASS。P0：无；P1：无；P2：无。** `revision-p1-r1` 在原冻结候选上关闭了原独立审查的两项 P1：最终 TCAD reviewer 可沿受控公共引用读取真实 skeleton producer 的 exact `research_objective`；review 前 project plan 投影成为 intrinsic nonclaiming，并被现存 claim consumer 通用拒绝。综合 review、package、analysis 正链与 legacy exact review witness 保留。

本 PASS 只覆盖冻结工程合同与下述定向路径，不表示原生模型、真实 solver、生产审批或 token/任务数收益已经验收。

## 1. 复审绑定与范围

- 原计划：[SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_PLAN_20260920.zh-CN.md](../SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_PLAN_20260920.zh-CN.md)，SHA-256 `4ec9c6af0b921d8c5cc5235a52967c516ed6b278e37c6a8835b5e0010a61e10e`。
- 原冻结候选：[implementation.patch](../evidence/scientific-skeleton-author-20260920/implementation.patch) SHA-256 `d5c825ef2e5f8604824f2bee6319dfe154442351e37df73aa1a734a64d91753e`；[candidate-manifest.json](../evidence/scientific-skeleton-author-20260920/candidate-manifest.json) SHA-256 `123c859b805c9a8755ababc3ee882a90041383161bbc5b060b451f4ec6225390`。
- 原独立审查：[SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_IMPLEMENTATION_SOL_REVIEW_20260920.zh-CN.md](SCIENTIFIC_SKELETON_AUTHOR_OWNERSHIP_IMPLEMENTATION_SOL_REVIEW_20260920.zh-CN.md)，SHA-256 `d0db2e37ba3b14b9cacf9b1e256eac99009c00735063e78991e294b81b691631`。
- 本次修复冻结目录：[revision-p1-r1](../evidence/scientific-skeleton-author-20260920/revision-p1-r1/)；[fix.patch](../evidence/scientific-skeleton-author-20260920/revision-p1-r1/fix.patch) SHA-256 `99e0c0fc960f1ec8749c009d70df09b0cb623c0573d5cb232f37d73d3d6c8f9d`；[manifest.json](../evidence/scientific-skeleton-author-20260920/revision-p1-r1/manifest.json) SHA-256 `b7fb900b47b6e1d5f00578e9932db685f1c8839f914dd6f3d8c06b86681d0b34`；[FIX_REPORT.zh-CN.md](../evidence/scientific-skeleton-author-20260920/revision-p1-r1/FIX_REPORT.zh-CN.md) SHA-256 `363766b5c4bc2acea909fa6e3d8471c2d9b4e0084d27553e32fb72562e93525d`。
- 修复精确修改 4 个生产文件、2 个测试文件，共 104 行新增、13 行删除。manifest 中全部 after hash 和测试证据 hash 与当前文件匹配；`git apply --reverse --check fix.patch` 与 `git diff --check` 通过。
- 本轮只读审查“原冻结候选 + fix.patch”，没有把整个 dirty HEAD diff 当作修复，没有修改实现、部署、调用科研 MCP、模型或 solver，也没有启动子 Agent。

## 2. 原 P1-01 已关闭：exact objective 可读，standalone skeleton 不获最终资格

`src/scidiscovery/reference_tools.py:13-33` 为 skeleton schema 增加唯一的 `producer_input_alias='research_objective'` 规则；`src/scidiscovery/artifact_agent/service/reference_access.py:283-372` 只从该 artifact 的真实 producer sealed manifest 解析此 alias。原有完成状态、唯一 manifest 配对、binding-parent、instance、CAS 完整性、读取预算和 handle 检查仍包围该新边，没有从 skeleton 自由文本猜 objective，也没有把所有 producer inputs 展开。

真实 producer 的 `research_objective` 输入不是 `handoff_only`。最终 reviewer 已把 exact skeleton 作为可见根输入，因此 list/read 能在既有 reference capability 内工作；foundation、critic 或其他 producer 输入不会因本规则额外暴露。

`plugins/tcad_artifact/tcad_artifact/operation_transforms.py:140-175` 又在新项目最终 package 资格处要求 skeleton descriptor 具有真实 completed producer，并且其受控 `operation_id` 为 `science.experiment.skeleton.v1`。generic current producer contract、project/review/skeleton exact parentage 和 package 本地 lineage 检查仍共同生效。复制相同 bytes、parents 或 labels 的 standalone/imported artifact 没有真实 `producer_run_id`，不能取得 package 资格；gap 和负面 review 仍可读取这种对象，不被错误升级成可执行项目。

该修复没有给 skeleton 增加 objective 复填字段，没有比较目标文本，也没有让控制层机械核对 mandatory targets。控制只保证 exact 原目标来源可读；objective、skeleton、具体计划和实现之间的科学一致性继续由最终 reviewer 判断。

我独立重放原始真实 producer→author→projection→reviewer 复现。修复前 `worker_reference_read(list)` 返回空列表；修复后返回：

```json
{"alias":"research_objective","locator":"/@producer_inputs/research_objective","media_type":"application/json","size_bytes":953}
```

同一复现的 sealed skeleton manifest 仍只记录真实输入 `critic_review`、`hypothesis_portfolio`、`research_objective`、`scientific_foundation`。进程守卫限制 768 MiB，峰值 122,084 KiB，退出 0、未超限。完整主链测试还用 `delivery=file` 比对 objective 原始 bytes，并验证 standalone skeleton 在 package preflight 以 `input_skeleton_objective_source_required` 拒绝。

## 3. 原 P1-02 已关闭：投影 intrinsic nonclaiming，局部受控用途与 legacy witness 均保留

`plugins/tcad_artifact/tcad_artifact/operation_transforms.py:443-455` 把 `tcad.execution-plan.project.v1` 的 consequence 改为既有 `explore` 语义。core 因而在注册投影时自动写入 `scientific_claim_admissible=false`；`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1240-1290` 对任何非 explore consumer 的 `claim_evidence` 通用拒绝该 intrinsic restriction，exact review 也不能把 explore 来源洗成普通 claim。没有新增 curve-score Operation allowlist 或新的状态机。

为解除“review 需要 plan、投影又需要 review”的循环，只有 `tcad.deck.review.v1.experiment_plan` 与 `tcad.reviewed-deck-package.v2.experiment_plan` 改成 `prior_signal`。这不会跳过 producer review admission：`prior_signal` 仍是 witness mode，带 review edge 的 legacy materialize/revise plan 仍要求 exact、passing `science.object.review.v1` 输出。新 skeleton 分支的 `_parameter_inputs` 与 `package_inputs` 继续核对 project 内 plan、projection exact project parent、producer identity、skeleton 和综合 review lineage。

explore/prior_signal 组合没有产生新的通用 claim 旁路：

- 投影作为 claim evidence 进入原复现的 `scidiscovery.curve-reference-coverage.v1` 时，在 transform 执行前即由通用 admission 拒绝。
- 投影可作为材料进入 exact TCAD reviewer；reviewer 必须绑定同一个 supported author project、project-derived plan 和原 skeleton，才能提交综合判断。
- package 同样以 project 的 exact passing version 3 review 为必要资格；legacy plan 的 producer review edge 仍由通用 witness admission 检查。
- 其他 deterministic transform 若从 nonclaiming prior signal 派生输出，core 的现有 `derived_from_nonqualifying` 传播仍会保留 false；agent 基于 prior signal 开展新的科学工作不等于把原投影本身改成合格 claim，其各自 producer/review 和本地合同仍适用。

我独立重放原 projection→legacy claim consumer 复现。修复前投影 label 缺省且 preflight `admissible=true`；修复后 label 为 `false`，preflight 返回：

```json
{"admissible":false,"reason_code":"input_scientific_claim_forbidden","port":"experiment_plan"}
```

该进程峰值 122,156 KiB，退出 0、未超限。

## 4. 独立验证与保留限制

除核对修复方冻结证据外，我串行运行了以下小集合，全部经 `scripts/compiled_worker_process_guard.py:run_process_group`，`aggregate_memory_limit_mib=768`、`sample_interval_seconds=0.1`：

| 独立复审检查 | 结果 | 峰值 |
|---|---:|---:|
| 原 P1-01 真实 skeleton producer/objective list 复现 | exit 0 | 122,084 KiB |
| 原 P1-02 author projection/curve-reference-coverage preflight 复现 | exit 0 | 122,156 KiB |
| `test_skeleton_author_projection_review_package_analysis` | 1 passed | 130,384 KiB |
| legacy exact pass、blocked/revise 与错 subject 小集合 | 3 passed | 134,544 KiB |

修复方证据还包括 37 个 reference-access 测试、3 个 review-admission 测试、gap、installed wheel/重启准入和完整新主链；其文件 hash 均与 manifest 一致。我没有重复运行 43 秒的隔离安装，因为本次独立源码/真实 gateway 复现已覆盖两个缺陷，installed 证据又验证了相同 consequence、port usage 与 reference policy 的打包投影。

已知旧 fixture 仍在 catalog 编译阶段命中 `agent_tool_evidence_contract_invalid: general_science/science.fixture.plan.v1`；修复方保存了同一失败，且它发生在本修复路径之前，不计为通过，也不改变本复审结论。

未运行 runtime-failure/retry 完整矩阵、全量 pytest、science-control bench、原生模型、真实 solver、Fig4 恢复、浏览器/生产审批或部署。PASS 证明冻结控制合同、来源流和定向新旧路径闭合；它不证明 reviewer 模型必然正确解释 objective 与 skeleton，也不证明任何任务数或 token 改善。
