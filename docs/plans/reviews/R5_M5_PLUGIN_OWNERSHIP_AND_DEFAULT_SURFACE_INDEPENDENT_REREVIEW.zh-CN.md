# R5-M5 插件所有权与默认产品面独立复审

日期：2026-09-01
审查者：未参与 R5-M5 实现或首轮审查的独立代码审查者
结论：**PASS（仅放行 M6）**

本结论只关闭首轮审查的 B1 并复核 R5-M5 阶段门。它不表示 R5-M 已完成，不把 M6、M7 或两位
最终独立审查者的完成门视为已满足，也不把 33 项约束整体升级为 `conformant`。

## 1. 范围、基线与方法

本次按 `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 第 10、13—16 节，先读首轮 FAIL 报告、
M5 实现证据第 10 节、当前计划/状态记录和 33 项约束，再独立追踪当前代码的真实路径。工作分支为
`baseline/8765-codex`，`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`。

工作树包含跨阶段的大量既有未提交修改，无法把 `git diff HEAD` 诚实地称为一份隔离的 M5 patch；
因此本报告复审当前候选及其可执行证据，不伪造提交边界。除本报告外没有修改生产代码、测试或既有
文档。写报告前 `git diff --check` 与 `git diff --cached --check` 均通过。

复审采用两条互相独立的证据链：一条从已编译 figure Operation 经 Root preflight、真实 Local Run
和通用 reviewer-output admission 复现 B1 正负例；另一条从封存 M2 源码双进程运行 M3 oracle，验证
有意改变仅限 figure 准入/父链，未用排除规则遮蔽 Transform 行为漂移。

## 2. 阻断发现

**没有发现仍未关闭的阻断项。首轮 B1 已闭合。**

### 2.1 bundle 合同已显式消费被审 intake 与 audit

`scidiscovery.curve-bundle.figure-evidence.v2` 的已声明输入现在明确包含：

- `scientific_intake`；
- `evidence_audit`；
- `figure_manifest`；
- `validation_report`；
- 一项或多项 `curve_tables`。

对应声明位于 `plugins/curve_score/curve_score/operation_transforms.py:489-505`。缺少 audit 已不可能以旧的
三端口请求通过端口绑定；真实 Root preflight 返回 `input_port_missing`，精确端口为
`evidence_audit`。

### 2.2 Root 复用通用 exact reviewer-output admission

返工没有在 Root 中增加 figure、curve、插件名或 operation id 分支。真实路径为：

1. `_prepare_operation_call` 完成同一编译 Operation 的端口绑定和 guard 后调用
   `_validate_operation_input_admission`（`mcp_root_operation_routes.py:848-967`）；
2. `_validate_producer_output_admission` 从 intake 生产者当前编译 `ReviewSpec` 读取 reviewer、输入端口和
   接受 verdict，并在本次全部输入中寻找精确 reviewer 输出（同文件 `:1061-1124`）；
3. `_operation_output_policy` 先校验生产者 operation digest 和精确输出端口，再投影其
   `subject_outputs`，没有第二份 reviewer allowlist（同文件 `:1171-1202`）；
4. `RunService.is_exact_reviewer_output` 只接受 `completed` Run、声明的 reviewer Operation、以 exact
   intake ref 绑定到 reviewer input port，且 handoff verdict 位于接受集合中的输出
   （`service/runs.py:562-589`）。

对 `src/scidiscovery/artifact_agent` 与 `src/scidiscovery/operations` 搜索 figure Operation id、
`figure_parentage` 和可选插件名为零命中。Run 仍只有 `queued/running/completed/failed` 四态
（`service/runs.py:879`）；未见新增 Root 工具、数据库事实、注册表或专用准入体系。

### 2.3 真实 Local audit Run 正例与四类 Root 负例

`tests/operations/test_m5_figure_review_closure.py:183-379` 通过 `RootMCPRouter` 创建真实 Local
Agent 类型的 figure audit Run，再由精确 `LocalWorkerMCPRouter` 打开 assignment、提交 Schema 和
context-validator 均接受的结果并完成 Run（同文件 `:125-146`）。独立执行该测试得到：

```text
1 passed in 1.03s
Maximum resident set size: 97,368 KiB
Swap: 0
```

同一真实 Root preflight 证据确认：

| 场景 | 结果 |
|---|---|
| 正确 completed figure audit、exact intake 与完整 sibling family | `admissible=True` |
| 缺少 `evidence_audit` | 拒绝，端口为 `evidence_audit` |
| 直接注册、没有可信 completed reviewer Run 的 audit | 拒绝，`input_independent_review_missing` |
| audit 属于旧 intake revision | 拒绝，`guard_rejected` |
| 绑定未被 report/audit 覆盖的另一 table family | 拒绝，`guard_rejected` |

这组负例不能靠伪造 audit 内容绕过：可信性来自完成 Run 记录及精确输入引用，而不是 Artifact 的
Schema、标签或聊天文本。

### 2.4 `figure_parentage` 精确绑定机械 sibling family

`figure_parentage`（`operation_transforms.py:183-200`）在单值端口和有界 table collection 上要求：

- validation report 的父链包含 exact manifest 和本次绑定的全部 tables；
- audit 的父链包含 exact intake、manifest、report 和本次绑定的全部 tables。

因此旧 intake、少表或混入未审 table 均不能通过。它只比较不可变 Artifact ref，不读取 audit
payload、check、科学解释或 verdict。`bundle_figure_evidence`（同文件 `:113-139`）也只消费
manifest/report/table 字节进行 Schema、身份、顺序和摘要的机械归一化；新增 intake/audit 不进入转换
函数，科学 verdict 仍只由 reviewer Run 产生并由通用 Root admission 解释。该边界满足
ROLE-001/DET-002：Transform 证明机械父链，不替代科学审查。

## 3. M3 oracle 复核

M3 oracle 未以全局排除、operation-id 特判或隐式跳过制造等价：

- 两个进程分别从封存 M2 源码与当前源码编译真实目录并执行 20 个保留 Transform；当前集合与 M2
  集合的唯一删除仍是 M4 已审查的两个 knowledge Transform（
  `test_m3_transform_equivalence.py:137-147`）；
- 递归排除仅限 `operation_digest`、`operation_invocation_fingerprint`、`request_fingerprint` 三个由
  所有权重编译派生的身份字段（同文件 `:22-38`）；
- figure 被单独取出后，只忽略其 `parent_refs` 做其余完整行为比较，再显式断言父链 Schema 类别由
  manifest/report/opaque 三类变为再加 intake/audit 的五类（同文件 `:159-187`）；
- 其余 19 个 Transform 仍整体比较输出 bytes、kind、media、Schema、父引用、语义 binding、Operation
  labels、幂等、冲突、修订和 guard；没有按 operation id 从行为清单删除它们；
- runner 对每个场景实际执行正 preflight、两次 invoke 幂等重放、同名异请求冲突、
  `create_revision` 和 guard 负例（`m3_transform_equivalence_runner.py:1248-1324`）。

独立执行结果：

```text
1 passed in 27.42s
Maximum resident set size: 103,800 KiB
Swap: 0
```

结论是：figure 转换内容、幂等、冲突、修订和 guard 仍被比较；唯一明确接受的变化是本次有意的准入
收紧及其输出父链从三类扩为五类。其余 19 项严格等价范围没有减少。

## 4. 首审其余 PASS 项防退化抽查

| 检查项 | 结论 | 独立证据摘要 |
|---|---|---|
| 公共组件与 Schema 唯一所有权 | PASS | builtin 单独公开七个文件工具；general_science 单独提供通用 codec/科研 Schema；六插件 `$id` 复算无重复；TCAD project schema 仍由 TCAD 单一提供，InGaAs 以公开 `ComponentRef` 复用。 |
| public 未消费导出与私有闭合 | PASS | `catalog.py:616-619` 只豁免 `public=True`；缺失、错误 kind、无依赖跨插件引用和未消费 private component 负例继续失败关闭。 |
| 显式最小工具授权 | PASS | `PermissionTemplate.tools` 直接从每个 Agent 的 `executor.tools` 同一有序引用生成（`catalog.py:448-459`）；公共注册不扩权，TCAD 作者有 delete、reviewer 无 delete。 |
| 可选 figure 默认不可见 | PASS | 默认目录不含三项 figure Operation；安装 `curve_figure_evidence` 后只由单一 `scidiscovery.plugins` 入口增加 extraction、audit 和 bundle 三项，Root/core 无插件名分支。 |
| TCAD 单 transport 与资源合同 | PASS | `TCADRuntimeConfig` 强制二选一；`build_runtime` 仅在选中分支惰性导入 socket 或 command adapter（`runtime_plugin.py:47-95`）；debug 复用同一 adapter；`ProjectExpectedOutput/ProjectResourceLimits` 分别是 execution-control 类型的同一对象（`project_packager.py:27-37,98-99`）。 |
| Local 默认面、显式 Hardened/portable | PASS | 普通 CLI/runtime/Codex 和默认目录不导入 hardened、portable、socket/command、SSH、daemon 或旧 runner；portable 只在相应管理命令分支导入，Hardened 只在显式 backend 分支导入；纯 MCP Hardened Run 仍可完成。 |
| 盲插件单入口 | PASS | 干净安装 blind CSV fixture 仅发布一个插件入口即可编译并调用其真实工具；core、Root、UI、调度器没有 `blind_csv` 分支。 |
| SEC-002 与 33 项状态 | PASS | 注册表仍为 33 个唯一 id：7 `conformant`、25 `pending_review`、1 `known_issue`；`SEC-002` 仍是 Local 原生工具隔离的 `known_issue`，没有被测试数量或提示词升级。 |
| 奥卡姆门 | PASS | B1 返工只增加两个既有类型输入并收紧一个既有 guard；没有新增 Registry、状态、Root 工具、数据库实体、兼容转发、插件私有调度器或第二部署事务。 |

## 5. 聚焦测试

所有命令均串行运行，设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
pytest -q -p no:cacheprovider ...
```

为避免重复已通过命令，测试分成三组：

| 组 | 覆盖 | 结果 | 峰值 RSS |
|---|---|---:|---:|
| B1 专项 | 真实 Local audit Run；Root 正例及缺 audit、未受信、旧 revision、混合 family 负例 | `1 passed in 1.03s` | 97,368 KiB |
| M3 oracle | 封存 M2/当前双进程、20 Transform、9 guards | `1 passed in 27.42s` | 103,800 KiB |
| M5 防退化 | 所有权、目录负例、可选插件、盲插件、clean wheel、Local TCAD、Hardened、部署/平台与33项结构 | `29 passed in 52.87s` | 93,864 KiB |

三组共 31 项，全部通过，swap 均为 0；没有失败、超时或卡住。按复审要求没有重复实现者的
`234 passed` 全量回归，也没有运行真实远端 transport、真实 solver 或浏览器；这些不属于关闭本次
B1 和 M5 阶段门所需的最小证据，仍由后续 M6/M7、发布和现场资格门承担。

## 6. 33 项约束与阶段结论

本次直接复核的 AUTH-003、IMM-002、EVD-001/002、ROLE-001/002、DET-001/002、PLG-001/002、
SEC-001/002、RES-002 和 MIG-002 未见退化。尤其是 reviewer 身份、exact subject、接受 verdict、
父链和 revision 均来自已有编译合同和不可变 Run/Artifact 事实；Transform 不解释科学 verdict；默认
产品面没有因可选能力或 Hardened 扩张。

注册表状态保持 7 `conformant`、25 `pending_review`、1 `known_issue`。本次 PASS 不替代尚未完成的
语义审计，不关闭 `SEC-002`，也不宣称 33/33 已符合。

最终结论为 **PASS**：首轮 B1 已在真实 Root/Local 路径上闭合，R5-M5 阶段门通过，**仅放行 M6**。
R5-M 仍未完成；M6、M7 及两位最终独立审查者的完成门继续有效。
