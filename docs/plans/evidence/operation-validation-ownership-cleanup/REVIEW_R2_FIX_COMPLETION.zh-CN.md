# 第二次独立复审后的修复记录

> 后续状态：第三次独立审查发现同一计算记录双表示的新增误阻断，尚未通过；另有 handoff 字段误定位。详见 [独立审查报告](INDEPENDENT_REVIEW_R3.zh-CN.md)。下文保留本轮修复及原有测试记录，不作为新审查通过证明。

2026-09-13。按用户“根据复审，再修一次”的授权，修正 [第二次独立复审](INDEPENDENT_REVIEW_R2.zh-CN.md) 的两类确定遗漏。**本轮增量为5个生产文件和4个所属测试文件，复审的4个故障探针均通过；尚未部署，也未进行新的独立复审。**

## 来源解释与自动补全

在现有 `analysis_artifacts.py` 中增加一个无副作用的来源解释函数。通用分析、TCAD 分析和 TCAD 机械补全共用它，不再分别认定哪些字段代表来源。它只使用已经绑定的元数据与当前输出引用，不重新执行输入准入，不读取新增文件，不判断科学结论。

统一处理直接绑定的 source_key、显式 input_alias、允许输入的 locator 前缀和已有 calculation_records 定位。自动补全使用全部绑定描述，不再只看具有 output_name 的 solver 输出子集；仍然只为已有 solver 产品生成对应的机械字段。先收集完整主张，有冲突时不生成映射，也不补写冲突项的 case/output 信息。

确定的命名解释是：**已绑定输入别名保持原身份；局部来源名可以通过可选映射或定位指向输入。** 这沿用此前有 evidence 行时的身份解释，将其统一应用于没有该行的情况。合同说明同步表达此规则；不是要求输出重新登记输入，也不是通过删除可选行绕开身份冲突。普通局部来源名、同源重复定位、没有 evidence 行的可选映射仍被接受。

计算记录的定位参与同一来源解释；记录是否存在、计算收据是否真实仍由原有 owner 检查。移除通用分析中被共享逻辑覆盖的单独“计算引用与原始来源并存”检查，没有建立第二套记录规则。

已验证的行为：

- source_key 已绑定到 A、locator 指向 B：拒绝时草稿没有错误自动映射；只修 locator 即可继续。
- 同一局部键指向 solver 输出与 reference_material：不因后者缺少 output_name 而漏掉冲突；修正定位可继续。
- 同一局部键分别指向原始输出与有效计算记录：明确指出冲突；修正引用名即可提交，原计算收据不改写、不重算。
- 同一显式来源映射有无可选定位行，接受结果一致；正常局部来源名可仅提供映射，无需补 evidence 表。
- 同源多定位、后续定位补充来源、历史条件映射、当前工具文件和跨轮保存的计算记录仍可使用。
- source_key 类型错误仍得到具体字段的可修正拒绝，不变成 finalizer 工程故障。

涉及生产文件：`analysis_artifacts.py`、`analysis_bindings.py`、`result_analysis.py`、`science_operations.py`。

## 工作区准备失败的公开可见性

`RunService.schedule()` 在 Run 已写入、准备步骤失败且失败记录已成功持久化后，返回该 Run 的身份。Root 因而沿现有成功返回路径绑定请求的语义名称，再投影它实际的 **failed** 状态和具体原因。

没有将失败伪装为 queued 或 completed，没有新增异常类别、Root API、数据库结构或状态机。Run 尚未建立时的准入/预算/名称错误，以及失败记录本身不能保存的异常，仍沿原路径处理。

真实 JSON-RPC/MCP 隔离测试覆盖准备工作区之前和之后的故障：

- invoke、run_status、run_list 均能读到同一失败记录及 admission_defect 原因，没有科学封存输出或输出拒绝计数。
- 同一不可变请求再次 invoke 返回原 failed 状态，不重新准备或隐式重试。
- 改变请求内容但复用名称仍被拒绝；显式 create_revision 在故障修复后可创建新 queued Run，旧失败记录保持不变。

这部分仅修改 `runs.py` 的已有失败返回路径。没有补写历史孤立记录的名称或迁移生产数据库。

## 验证证据

按本轮修改前快照计算增量，见 `REVIEW_R2_FIX_BASELINE.json`；最终文件摘要、目录和命令见 `REVIEW_R2_FIX_VERIFICATION.json`。工作区已有的其他修改均保留。

| 验证 | 结果 | 日志 |
| --- | --- | --- |
| 原独立复审4个故障探针 | 4 passed | `check-1789262671646484033.log` |
| TCAD 分析、引用职责、工程分类及历史续接 | 96 passed，1 stress deselected | `check-1789262902549771938.log` |
| 生命周期、受控修订与架构矩阵 | 39 passed，3个基线失败 | `check-1789262981545606077.log` |
| 修改前快照复现上述3个失败 | 同样3处断言失败 | `check-1789263070893389275.log` |
| 保存记录消费、通用曲线分析、字段诊断与职责边界 | 60 passed | `check-1789263107545142270.log` |
| 实际五插件目录编译 | 50个 Operation，25个 public Agent，编号集合不变 | `check-1789263187841439957.log` |

分组存在重叠，不合计为互不重复用例数。`git diff --check` 通过。开发中新增 MCP 测试曾错误地直接读取 invoke 外层的 state；按实际 `result` 包装修正测试后，两条准备故障测试通过，见 `check-1789262853808795171.log`。未为满足断言改变返回协议。

### 明确保留的三个基线失败

均位于 `test_l2_run_invariants.py`，在修改前320个 Python 文件的精确快照中复现相同断言及相同实际结果：

1. `test_candidate_binding_crash_windows_and_response_replay`：仍匹配旧异常文本，实际为 `Worker call failed`。
2. `test_status_is_pure_and_failure_recovery_is_explicit`：要求返回字典完全相等，未包含已存在的 diagnostics 字段。
3. `test_real_process_failure_isolation_windows_replay_after_restart`：仍匹配旧状态异常文本，实际为 `Worker call failed`。

这些失败不能算通过；断言后的剩余步骤也不能算已验证。本轮不修改这些无关断言，不用它们的失败推断此次修复引入了回归。

所有检查串行运行，地址空间及进程树 RSS 限制为512 MiB；峰值约181.4 MiB，无资源超限终止。没有全量或压力测试。当前版本中不存在技能所列的两个独立架构/科学基准脚本，因此使用本版本的架构矩阵、实际目录编译和上述运行路径测试，没有借用旧快照脚本冒充当前验收。

本轮没有安装包构建、生产部署、真实平台调度或求解器验收。无需新增配置或数据迁移；安装后真实研究仍应单独验证。
