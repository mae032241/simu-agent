# Fig.4 本轮交接、恢复、上下文与可视化整改实施独立 SOL 验收

日期：2026-09-21

验收对象：`123/scidiscovery-e5.2` 共享 dirty 工作树中冻结的 18 文件相对基线补丁。

本地代码验收：**PASS（仅限冻结的 18 文件候选）**。

部署态验收：**未完成，不得称端到端通过或已交付部署。**

P1：**无。**

P2：**2 项，均不推翻 18 文件本地 PASS；其中一项使共享工作树不能宣称 full-installed 回归全绿。**

## 1. 权威输入、责任边界与冻结核对

本次按 `scid-cross-boundary-review` 审查身份、准入、Root/Worker、恢复、安装入口和模型可见合同，并按
`scid-change-scope-checks` 选择最小定向检查。未修改生产源码或测试，未部署、重启、提交 git，未运行
TCAD、模型 A/B、科研实例动作或审批。

- 权威 R1 计划：
  `docs/plans/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_REMEDIATION_PLAN_20260921.zh-CN.md`；实算
  SHA256 为 `37bbbb240fd64f61b3d4f6d24a6de81a79d3390d430b42709f69f840d51861d3`，与委托一致。
- R1 独立计划复审：
  `docs/plans/reviews/FIG4_ROUND_HANDOFF_CONTEXT_AND_VISUALIZATION_PLAN_R1_SOL_REREVIEW_20260921.zh-CN.md`；
  其结论为计划 PASS，不替代本次实现验收。
- 基线 HEAD 与当前 `git rev-parse HEAD` 均为
  `943c4626f8490530e9318eb9fbb409d2670908b9`；分支为 `refactor/m7-pre-e5.2`。工作树有大量其他 dirty
  修改，本报告没有把全仓 diff 归给本轮。
- 精确责任补丁
  `docs/plans/evidence/fig4-round-remediation-20260921/RELATIVE_BASELINE_DIFF.patch` 实算 SHA256 为
  `a6aa082cd788675b4648d7ffbbced84d419d101bd2e1368bc180bc0016b0c7b2`，与委托一致。
- `BASELINE_FINAL_SHA256.txt` 所列 18 个最终 SHA256 逐项与当前文件字节一致；
  `git apply --reverse --check RELATIVE_BASELINE_DIFF.patch` 通过，证明该补丁能从当前冻结终态干净回到
  逐文件基线。补丁为 12 个生产/角色/指南文件和 6 个测试文件，共 `208` 行新增、`32` 行删除。
- 对这 18 个路径执行 `git diff --check` 通过。

因此后续发现只按该相对补丁归责；邻近共享修改只用于判断组合影响。

## 2. 本地代码验收结论

### 2.1 身份、历史兼容与准入：PASS

`src/scidiscovery/operations/input_validation.py:157-211` 没有删除或放宽既有四项配对条件。修改仅把
`direct_parent`、`prior_producer`、`same_producer`、`recovery_output_port` 分别写入精确诊断；manifest
内容仍以完整 `ArtifactRef` 映射，冲突 alias、非直接父件和重复输入身份仍拒绝。它没有把旧历史可读性
转成 current/qualification，也没有把 output-time 消费重新定义成新的 input admission。

`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:603-725` 对同 Run recovery manifest
的识别仍是 fail-closed：先由 `RunService.completed_for_output` 找到精确完成 Run，再要求目标 ref 出现在
该 Run 的 `evidence_output_refs`；随后核对 envelope 的 operation id/version/digest、精确输出端口、当前
安装合同的 collection 形态和 artifact kind/schema/media。family identity 使用真正的
`status.output_ref` 作为 primary，而不是把 manifest 伪装成主输出。历史合同不可用分支也只恢复既有
冻结 producer identity，不产生 current 资格。

独立定向检查中，真实 Run 先封存 calculation 与 recovery manifest，下一 Run 再同时绑定
`prior_analysis`、同 Run manifest 和精确 calculation；preflight、Worker 打开和提交均通过，且 monkeypatch
确认没有重新计算历史 score。这验证了修复经过真实 preflight/Run/Worker 路径，而不只是直接调用
validator 夹具。

### 2.2 manifest 有界投影与依赖补齐合同：PASS，部署态仍待真实 Root 验收

`src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py:288-341,441-496` 只在
`view="parents"` 且对象是 `scidiscovery.tool-evidence-manifest.v1` 时增加投影。它只遍历 manifest 自身的
直接 `parent_refs` 当前页，用完整 ref 连接 sealed binding/record；不递归祖先，不按 schema、时间或名称
猜用途，不返回 artifact ref。原 `parent_count`、`next_offset` 仍表示分页，投影另给 invalid/unmapped/
page record 计数；无当前 `artifact_name` 的父件仍显式为 `null`，没有伪造可访问名。

`.codex/scidiscovery-guides/inputs.md:19-29` 与安装来源 `roles/scheduler/inputs.md:19-29` 明确要求科学
Agent 先选择本任务需要的角色，Root 只按封存记录和精确名称构造 immutable request；缺名、不完整页、
多候选或非 complete 投影均停止，不全绑、不递归、不让控制层从自由文本推断科学用途。局部实现没有
新增依赖 schema、机械来源台账、Fig.4 分支或第二状态机。

本地 fixture 已证明 manifest record 能投影到当前语义名，下一 Run 能显式绑定脚本/数字/图件并复用；
但没有真实 Root Agent 从“只给 prior result 名称”开始完成首次 invoke。因此这里只验收模型可见合同和
机械能力，不能把依赖交接端到端闭合写成部署事实。

### 2.3 `artifact_name` 与 `source_name` 权限：PASS

`src/scidiscovery/artifact_agent/service/run_assignment.py:60-77` 把冻结的 `artifact_name` 与固定
`artifact_name_usage="navigation_only"` 投影到 assignment；
`plugins/curve_score/curve_score/analysis_workspace.py:37-46,181-195` 仅把这两个字段带到
`analysis-start.json` 索引。工具解析、evidence、正式报告和输入字节仍使用既有 `source_name` 与绑定
descriptor。

独立负例把 `artifact_name` 直接传给 `worker_analysis_publish_files.source_aliases`，得到
`DiagnosticError`；换成同一输入的 `source_name` 后发布和提交通过。没有发现第二 alias、未绑定读取或
权限扩张。

### 2.4 通用曲线图与发布路径：PASS（提示词/本地合同），真实页面链未验

`plugins/curve_score/curve_score/analysis_files.py:76-119` 修改共享 guidance：数据和绘图实现足够且科学
判断涉及 reference/candidate 时默认发布 overlay PNG；只有残差分布影响判断时才增加 residual。尺度和
残差定义仍由科学 Agent 决定；单位、图例、实际比较域和正式报告 alias 引用被明确要求。绘图失败保留
数字和精确错误，可 plot-only 重试或交付受限结论。

修改没有新增图表 schema、角色、提交 gate、路径/hash 登记，也没有改
`worker_analysis_publish_files`、PNG evidence 封存或 UI。安装态/角色提示词定向检查通过。真实同一曲线
Run 的 PNG 生成、发布、报告引用、manifest 封存与所属节点预览/原图/下载/来源链仍未执行，故 UI
零修改是合理的条件分支，不是页面端到端已通过。

### 2.5 TDR 恢复与事实分离：PASS（静态与本地夹具），真实 TDR accept 未验

本轮 TCAD 生产修改仅在
`plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md:82-91` 要求按选定 solver release 的实际完整
文件名声明，包括 solver 生成后缀，并禁止从 `struct` 文本猜最终路径；没有硬编码 `_fps`。

邻近既有 `output_recovery.py` 路径仍只检查原 terminal execution、读取/复核字节并以显式 rationale
封存，不编辑、重命名或启动 solver。独立 fixture 验证 recovered bytes 可在同 Run score/seal、失败 Run
证据可供新 Run 绑定、terminal state/solver exit/collection 97/科学结论保持分离。源码与测试均没有把
原 failed execution 改成成功，也没有把“文件存在”算作科学完成。真实 Fig.4 TDR 的唯一对应和
`worker_tcad_accept_output` 尚未在部署态执行，不能据本地夹具声称真实恢复完成。

### 2.6 Root compact/error 保真：PASS（合同），真实 Agent 行为待 A/B

`.codex/scidiscovery-guides/results.md:8-18` 与 `roles/scheduler/results.md:8-18` 只增加先处理 MCP transport
`isError`、保留 code/path/message 的顺序；既有 `poll`、`navigation`、`decision` profile、游标、
missing/null/omitted 和原访问路径实现均未改动。安装态 Root guide 与 compact report 检查通过。没有新增
摘要协议，也没有以截断错误换 token。真实 Root 是否避免重复合同/正文/父链读取只能由部署后的 matched
A/B 判断。

## 3. P1/P2 发现

### P1

无。未发现会绕过 preflight/current/qualification/独立审查/审批、接错历史身份、授予
`artifact_name` 工具权限、递归全父链、强制图表门或把未验恢复写成成功的缺陷。

### P2-1：共享工作树 full-installed 测试仍为红，原因是旧 required-port 断言未随 skeleton 分支更新

位置：`tests/operations/test_analysis_tool_installed.py:78-116`，尤其 `114-116`；组合生产事实位于
`plugins/tcad_artifact/tcad_artifact/result_analysis.py:93-121,356-377,585-601`。

独立运行
`test_installed_analysis_catalog_and_worker_projection[full]` 稳定得到 `1 failed in 41.77s`。失败发生在
安装 wheel 内的 TCAD required-port 精确集合断言：测试仍要求
`experiment_review` 永远 `min_items=1`。共享工作树另一 skeleton 分支已把它改为 optional，并增加同样
optional 的 `execution_review`、`scientific_skeleton`；生产 `analysis_parentage` 和
`validate_analysis_inputs` 根据 package branch 要求 legacy review 或 skeleton execution review 二选一，
缺项、混绑和替代均拒绝。因此这不是本轮 18 文件造成的准入放宽，也没有证据表明安装 runtime 主路径
失守。

影响：本轮 18 文件本地候选不因此失败；但当前共享工作树不能宣称 full-installed 测试全绿，发布所有
dirty 修改前仍需由 skeleton 分支所有者处理。最小建议是在其精确范围内把集合断言改成“不分支必填端口
+ 三个 branch port 均 optional”，并分别以 legacy 与 skeleton 正例、缺/混 branch 负例验证实际
preflight；不要简单删除断言或把所有 review 都视作可选。该测试不在本轮冻结 18 文件中，本验收未改。

### P2-2：实施者的 88 项/RSS 自报缺少原始批次证据，精确数字不可独立复核

位置：`docs/plans/evidence/fig4-round-remediation-20260921/`。冻结时该目录只有
`IMPLEMENTATION_REPORT.zh-CN.md`、`RELATIVE_BASELINE_DIFF.patch`、`BASELINE_FINAL_SHA256.txt`，没有
实施报告所述各 pytest 批次的命令、stdout、退出码和 guard JSON/log。

影响：报告中的“88 项通过、最高 166128 KiB”不能由另一验收者从交付目录重新核算。本报告没有把它
当作独立证据，也没有为补数字无意义重跑 88 项；而是按风险选择 42 个检查，并把自己的 guard JSON
留存。最小建议是后续实施批次保留每次 guard record 与测试输出，或把实施报告明确标成未留原始日志的
自报；不得仅复制汇总数字冒充原始证据。此项是可追溯性缺口，不改变本次源码语义结论。

## 4. 独立检查、RSS 与证据

所有 pytest 批次均串行、无 xdist，通过
`scripts.compiled_worker_process_guard.run_process_group` 启动，固定
`aggregate_memory_limit_mib=768`、`sample_interval_seconds=0.1`；环境固定
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`。守卫按 `/proc`
进程树 `VmRSS` 汇总 resident set；本报告没有以 VA 代替 RSS。守卫 SHA256 为
`59c449aee185a45cbd52cf732f374d1cd30119a48994a306ce48ad6a611793a4`。

| 检查 | 结果 | 时长 | 峰值树 RSS | guard 证据 |
|---|---:|---:|---:|---|
| 四维 prior 配对、manifest 直接父投影、assignment/analysis-start 导航字段、artifact_name 负例、scheduler guides | 33 passed | 6.50 s | 136020 KiB | `independent-acceptance/core-contracts-guard.json` |
| 真实 prior calculation/manifest 下一 Run 复用；TDR recovered bytes、failed Run handoff、solver/collection 事实分离 | 7 passed | 9.12 s | 130940 KiB | `independent-acceptance/recovery-paths-guard.json` |
| 安装态 Root reading guide 与 TCAD compact/prompt 投影 | 2 passed | 43.05 s | 193424 KiB | `independent-acceptance/installed-root-prompt-guard.json` |
| full-installed curve/TCAD projection 的已知共享断言 | 1 failed | 42.14 s | 138560 KiB | `independent-acceptance/installed-full-projection-guard.json` |

三批正向共 **42 passed**；一项已归因的 full-installed 旧断言失败。最高独立观测树 RSS 为
**193424 KiB**，四批均 `memory_limit_exceeded=false`。四份 guard JSON 的 SHA256 分别为：

- `core-contracts-guard.json`：`08b8eac9b767c9681f2edb32f9b2b786188234b2e80a4e2e7825c565c4459856`
- `recovery-paths-guard.json`：`f39d531cade5cab5955e4ca4fa0d34c6053d8496b9a24e91da7090db43fd5471`
- `installed-root-prompt-guard.json`：`3f678735cd1f69a47dee1c82198f4c1a033823724ce00b4bc974b22e3c535b4f`
- `installed-full-projection-guard.json`：`a4d3aef0a34aebb6ee8e6325818ab871640656fc8278a5d265d6bba74097340f`

未运行全量 pytest、ruff、浏览器、模型、TCAD 或科研实例动作。没有扩大资源预算，也没有并行测试。

## 5. 部署后待验收与真实剩余风险

以下各项均为**未验**，不能由本地 PASS 代替：

1. 在原真实 prior analysis 与其直接 recovery manifest 上重新执行同一 preflight，记录四个身份事实、
   producer family、最终准入和失败时的原诊断。当前只证明源码与本地真实 Run fixture 闭合。
2. 真实 Fig.4 TDR 先 inspect 再 accept，证明唯一实际文件名/字节/声明映射且 solver 启动次数为零；原
   execution failed、solver exit、collection 和科学 verdict 不改写。本报告没有执行该动作。
3. 同一条真实曲线 Run 使用封存 reference/candidate 数据生成当次 overlay PNG，必要时 residual；正式
   报告引用返回 alias，完成后从所属节点核对预览、原图、下载字节和 Run/manifest 来源链。没有真实
   证据前不应改 UI，也不能称图件端到端通过。
4. Root 与 Worker 分开的 matched A/B：每组至少 A1/B1/A2/B2 交替，冻结代码、安装、合同、任务、输入、
   模型、预算和停止边界；记录响应、token/cache/compaction、调用/拒绝和功能等价。当前 token 收益仍
   **未证实**，不得把历史压缩、可见字符或累计 cached input 冒充收益。
5. 部署后核对实际安装字节和 guide/role/prompt 投影，再执行上述路径。当前 full-installed 旧断言需按
   P2-1 由其所有者闭合，或在发布说明中明确为尚未全绿；不能把“范围外”当作全树绿的理由。

剩余主要风险不是已发现的本地身份绕过，而是模型是否会按新 guide 在首个 immutable request 前完成
有界依赖选择、真实图件是否被节点 lineage/display budget 完整展示、以及实际 TDR 对应是否唯一。这些
都需要部署态事实；静态审查不能预先判定成功。

## 6. 最终判定

**冻结 18 文件本地代码验收 PASS。** 实现保持精确身份和准入权威，补齐了同 Run manifest producer
识别、直接父项机械投影与导航语义，同时保留 `source_name` 权限、非强制绘图、TDR 无重算恢复和 compact
错误保真。没有 P1。

**共享工作树整体仍有 P2 测试债务，部署态验收未完成。** 因此本结论不表示 full-installed 全树绿、
真实 prior 已修复、真实 TDR 已接纳、真实 PNG 页面链已通过、matched A/B 已完成、token 收益成立或
Fig.4 科学结论改变。
