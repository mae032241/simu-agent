# 校验职责清理修复：第二次独立复审

> 后续实施：两类确定遗漏已按本报告修正，原4个故障探针通过，见 [修复记录](REVIEW_R2_FIX_COMPLETION.zh-CN.md)。本报告保留审查当时的结论；后续实施尚未经新的独立复审。

2026-09-13。结论：**未通过。上一轮 R2 的来源解析与自动补全仍不一致，R3 的工作区准备失败仍缺少 Root 可观测性。** R1 的被审对象引用和 R4 的缺口字段诊断，在本次检查范围内已修正。

## 范围与独立性

用户要求再次独立评审。新审查者不继承父会话历史，按 `REVIEW_FIX_BASELINE.json` 的精确快照和 `REVIEW_FIX_VERIFICATION.json` 的八个生产文件检查增量，沿编译注册、finalizer、输出校验、持久化和 Root 查询链路复查。审查者只读，不运行测试；主代理集中、串行执行隔离 MCP 探针，再将实际结果交给审查者判断。

本轮没有修改生产源码、部署服务、操作生产科研记录或执行求解器。没有全量测试。旧的绿色定向测试不能证明未覆盖路径正确。生产文件摘要复核见 `REVIEW_R2_VERIFICATION.json`。

## P2：来源解释与自动补全没有使用一致规则（原 R2 未闭合）

位置：`plugins/tcad_artifact/tcad_artifact/analysis_bindings.py:130`、`src/scidiscovery/artifact_agent/service/analysis_artifacts.py:43`、`plugins/tcad_artifact/tcad_artifact/result_analysis.py:438`。

### 已复现：控制生成的错误映射导致修正后仍被拒绝

不提交 `source_references`，仅提交 `source_key=solver_outputs_001`、`locator=solver_outputs_002:row1`。finalizer 只按 locator 收集候选，先将 `solver_outputs_001 → solver_outputs_002 / output B` 写回草稿。校验随后拒绝这次冲突。

读取当前草稿，只将原始 locator 修正为 `solver_outputs_001:row1` 后再次提交，仍被拒绝：控制生成的错误来源表继续声称 B。Agent 必须额外清理控制层生成的信息。上一轮“双 locator 冲突”测试没有覆盖 source_key 本身就是已绑定别名的情况。

这不是要求放行原始冲突，而是控制层不能先猜错，再要求 Agent 维护该猜测。证据：`check-1789261771922163338.log`，探针 `review_r2_mapping_probes.py::test_direct_alias_conflict_does_not_leave_a_guessed_control_mapping`。

### 已复现：有效计算记录分支没有参与同一来源解释

通过真实注册曲线工具取得有效的小型计算记录后，同一个 `raw_evidence` 键分别引用原始 solver 输出和 `calculation_records:score`，提交仍为 `completed`，封存来源表仅映射原始输出 A。

共享 helper 跳过计算记录行，TCAD 调用方确认记录存在，却没有统一解释该键同时指向的两个对象。这不代表计算记录伪造或计算错误；它证明上一轮“一键一来源”的实现没有覆盖全部表示分支。

证据：同一日志，探针 `review_r2_mapping_probes.py::test_inline_calculation_and_raw_input_do_not_silently_share_one_source_key`。

### 已复现：增删可选定位行会改变绑定解释

保持 `source_references=[{source_key: solver_outputs_002, input_alias: solver_outputs_001}]` 和结论引用不变。有 `locator=row1` 的 evidence 行时，提交被判定来源冲突；仅删除该可选行后，提交成功。

局部 locator 没有新增其他来源主张。该对照说明是否执行别名冲突解释依赖可选表示是否存在。它本身不能决定哪种别名解释应被接受，不能据此直接增加拒绝条件。

证据：`check-1789261921264150213.log`，探针 `review_r2_mapping_probes.py::test_optional_citation_does_not_change_the_meaning_of_a_bound_alias`。独立审查者收到实际结果后确认归入同一个 R2 根因，不另立规则。

### 最小修正方向

来源解析和自动补全应共用完整且一致的解释，覆盖直接绑定别名、允许的 locator 来源、显式映射和计算记录身份。仅在来源明确时生成机械字段；有无可选定位行不能改变同一来源主张的解释。保留同源多定位、可选来源表及现有计算收据验证，不要求 Agent 再登记或清理控制层猜测。上述方向不是新增统一注册表或一组额外校验的授权。

## P2：准备失败记录已经保存，但 Root 无法读取（原 R3 外层路径未闭合）

位置：`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:294`、`src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py:14`；对应上一轮修改 `src/scidiscovery/artifact_agent/service/runs.py:353`。

隔离 MCP 故障注入让工作区准备抛出带 `admission_defect` 分类及明确原因的 `RunCheckerError`。数据库中存在失败 Run，具体原因也正确保存。但 `schedule()` 抛错后，Root 在建立语义 Run 绑定之前返回通用 `local_run_creation_failed`。

实际公开接口结果：invoke 不含具体原因，`run_list` 返回空列表，同名 `run_status` 返回通用 `runtime_failure`。只有利用内部 Run ID 才能读到详细失败记录。调度者无法按公开接口定位这次失败。

这是既有外层缺口在上一轮扩展到“创建工作区”时没有闭合；数据库持久化修复本身成立。上一轮测试读取内部 Run 状态，因此没有覆盖真实调度方的读取路径。

证据：`check-1789261662784365762.log`，探针 `review_r2_visibility_probes.py::test_pre_dispatch_failure_is_visible_through_root`。

最小修正方向：让已经建立的失败 Run 经现有语义名称和状态投影可见，保持不可变请求和身份绑定，不新增状态机，也不暴露内部 ID 或原始异常链。

## 已有效的修复与边界

- R1：被审对象经 `context_sources` 进入动态来源枚举，投影 v2 进入编译摘要，未发现科学资格放松。枚举仍是结构上界：参数提取的 checklist 出现在枚举中，但角色声明和上下文校验仍禁止把它作为科学证据。此处不能宣称 enum 完全等于科学证据资格，也不应为消除差异直接放行 checklist。
- R4：缺口定位错误经既有诊断转换保留具体原因和 `$.deck.gap.affected_work[index].plan_locator`，原发现的可纠正字段路径已修复。
- 未发现八个生产文件增量削弱精确 execution、输出身份、case、计算 receipt、独立 review 或 approval 检查。此结论限于受审增量与实际追查链路，不等于所有 Operation 已逐一动态验收。

## 复现资源与证据

三个测试进程组串行运行，均由现有 `check.py` 限制地址空间和进程树内存至 512 MiB。最高观测进程树 RSS 为 125,820,928 字节，约 120.0 MiB，无资源超限终止。四个探针均以期望行为断言失败，日志是缺陷复现证据，不是通过记录。

| 日志 | 内容 | 进程组耗时 | 峰值 RSS |
| --- | --- | ---: | ---: |
| `check-1789261662784365762.log` | 准备失败的 Root 可见性 | 2.65 秒 | 113.0 MiB |
| `check-1789261771922163338.log` | 控制映射纠错、计算记录来源 | 3.53 秒 | 120.0 MiB |
| `check-1789261921264150213.log` | 可选定位行对照 | 3.52 秒 | 115.9 MiB |

探针原始命令和资源记录保留在 `checks.jsonl`。临时探针按原字节保存为本目录中的两个 `review_r2_*_probes.py`，未加入默认测试收集。当前结论不覆盖生产环境部署验收。
