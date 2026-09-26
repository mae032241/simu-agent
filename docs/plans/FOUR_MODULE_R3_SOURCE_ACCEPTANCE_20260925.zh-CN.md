# R3 最小源码验收与修复记录

## 当前状态

2026-09-25：**用户已明确允许受限源码验证，调度器已传达授权。最小清单现已全部取得通过证据；中途失败、局部修复与续跑记录保留如下。**

承接 [实施记录](FOUR_MODULE_R3_IMPLEMENTATION_STATUS_20260925.zh-CN.md)中的 ABI 19 / job wire 4 候选。初始清单只准备验证；执行后发现的问题由原实施者局部修复，生产与测试修改身份分别记录，不追改既有审查结论。本清单不授权安装、构建、完整测试集、真实 Worker/solver、远端连接或部署。

## 唯一执行清单与边界

[配置](../../scripts/r3_source_acceptance.json)列出 20 个精确 pytest node selector，实际展开 29 个不同参数用例并取得通过证据，详见末节逐轮映射。按配置顺序逐个启动独立进程，任何失败立即停止，不自动重试或加额。

| 顺序 | 选取内容 | 能证明和不能证明的边界 |
| --- | --- | --- |
| catalog | `test_public_actions_are_a_direct_projection_of_the_compiled_catalog` | 真实生产 core/general/curve/TCAD 声明的源码 assembly 编译及 public projection。源码 autouse fixture 提供 entry point 元数据，不能证明 wheel 安装发现。 |
| A | compiled author、完整 save/bundle、6 类缺失/篡改/身份拒绝、部分 save 恢复、文字修订复用、精确 audit 父链 | 真实图像算法和领域工具使用 12×12 PNG；save 测试使用内存控制 receipt 替身。精确审查父链并不证明真实独立 Agent 身份/端到端审查交付。 |
| B | 等号/超额、禁用与配置摘要变化、缺失配置和 transport 上限拒绝、跨修订预算及紧缩、未启动重新授权、prepared reservation 保留、2GB metadata 与 grid 父链 | SQLite 临时库或内存库、配置模型与生产服务方法。2GB 仅元数据，无 2GB 分配；不证明进程重启恢复、未知远端提交查询、solver 或大文件传输。 |
| C | renderer 失败原 checkpoint 重绘；失败 Run 续作复用 checkpoint | 真实本地 Run/Artifact/CAS 与小规模计算、绘图；renderer 故障注入。续作仍非真实外部 Agent 中断恢复。 |
| D | skeleton 作者/独立 review/只读 preflight；`comparison-reviewed-producer-plan` 单一封包案例 | 真实控制层和临时文件/SQLite，准备 adapter 没有 submit 方法，debug adapter 仅返回合成结果；验证审查绑定与封包/执行身份幂等，不启动求解器。 |

## 静态 fixture 和 import 审核

- `tests/conftest.py` 唯一 autouse fixture 替换源码 entry points 并清 catalog cache，没有安装或 subprocess。
- `tests/operations/conftest.py` 的 `installed_environments`、`installed_probe` 会建 wheel/venv；它们不是 autouse，所选 node 及 fixture 链不请求它们。禁止改成目录选择或增加未经审核的 node。
- 直接 pytest fixture 为 `tmp_path`、`monkeypatch`、D 的 `experiment_case` 及有限参数；`experiment_case` 只构造科学夹具。`_feedback_root` 对既有基础审批做替身处理，因此不宣称覆盖全部真实资格。
- C 的 import 链中 `test_tcad_result_analysis.py` 和 `test_result_analysis_tool.py` 使用 `runpy.run_path` 读取两个兄弟测试模块。已检查这些模块顶层是定义、声明和配置读取，没有安装、构建或启动 solver；这仍会增加导入量和重复定义。
- D 的 `_ImmediateDebugAdapter.submit` 只是递增计数并返回合成状态；`PreparationOnlyAdapter` 提供 prepare 校验，补齐的 lookup 方法一旦被调用就抛错，没有任何 submit 能力。
- 静态检查不能穷尽第三方 import 副作用或证明资源上限足够；出现缺包、失败或超额应停下定位，禁止自动 pip/uv 安装或扩大内存。

## 资源限制

[串行运行脚本](../../scripts/run_r3_source_acceptance.py)复用已有 `compiled_worker_process_guard` 的进程树读取与信号辅助函数；默认只读取 JSON/AST 并显示计划，必须显式 `--execute` 才会启动 pytest。

- `RLIMIT_AS` soft=hard=`1,073,741,824` 字节：**每进程虚拟地址空间硬限制**，不是 RSS 或进程树聚合硬配额。后代继承该限制，每个进程各有额度。
- `/proc` 采样的进程树 RSS 超过 `805,306,368` 字节则停止。此项是额外保险，0.1 秒采样存在漏采及超调，不宣称内存聚合硬上限或绝不 OOM。
- 每个 selector 120 秒，包括 pytest 导入、收集所选模块、执行和 teardown；到期先 TERM，2 秒后 KILL。结束时清理进程组及观测到的后代；主动脱离进程组且未被采样捕获的后代不是这个脚本的隔离保证。所选用例没有这样的启动路径。
- 数值库线程设为 1；禁 pytest 第三方插件自动加载，清理继承的 `PYTEST_ADDOPTS`/`PYTEST_PLUGINS`/`PYTHONPATH`，禁 cacheprovider；不使用 xdist。每个 selector 独立临时目录和日志。
- 准备时只静态确认 pytest/pydantic 元数据目录，未通过安装补依赖。随后受限验证使用 `/home/da/miniconda3/bin/python`，各轮结果记录实际 `sys.executable`。
- `/proc/self/cgroup` 是 `0::/`，可见 `/sys/fs/cgroup` 为只读 cgroup2 挂载，存在 memory controller，但根下 `memory.max` / `memory.current` 不可见。**有效容器内存额度未知**；不能把宿主 MemAvailable 当成分配依据，不能自动上调上述额度。

授权后由调度器安排唯一执行者运行，输出路径必须不存在，原日志不覆盖：

```bash
/home/da/miniconda3/bin/python scripts/run_r3_source_acceptance.py --execute --output /tmp/scid-r3-source-acceptance-20260925
```

配置的授权状态字段仅为记录，`--execute` 不是授权来源。用户未授权前不运行以上命令。实际结果为输出目录中的 `result.json` 和逐项日志；首次失败时后续 node 均未验收。通过这些源码案例后，runner 进程树终止/小额度超限、远端传输、安装发现、真实短 TCAD 闭环仍需分别安排，不能用本清单替代。


## 首轮执行结果

- [完整结果与命令](evidence/four-module-r3-20260925/source-acceptance-first-run/result.json)、[原始失败日志](evidence/four-module-r3-20260925/source-acceptance-first-run/17.log)、[归档哈希清单](evidence/four-module-r3-20260925/source-acceptance-first-run/manifest.json)。前 16 个 selector / 25 个参数案例通过，第 17 个失败，剩余 3 个 selector 未执行。
- 累计 16.300 秒，采样进程树 RSS 最高 125,317,120 字节；失败进程退出码 1，2.382 秒，未触发超时或采样内存停止。RLIMIT_AS 如上，未提高资源额度。
- 失败位置：`test_analysis_diagnostic_tool.py:189`，`test_render_failure_retries_exact_checkpoint_without_recomputing` 的 `failed["checkpoint"]` 为 `None`。
- [失败时保存的计算记录](evidence/four-module-r3-20260925/source-acceptance-first-run/failed-calculation-record.json)明确记录：`CurveErrorNumericalItem` 校验失败，`SchemaModel values must be JSON-compatible; got _ResidualAtom`。
- 静态定位：`diagnostic_tool.py` 在调用 `compute_curve_error` 后才保存 checkpoint；`analysis.py` 将普通 frozen dataclass `_ResidualAtom` 放入 `CurveErrorNumericalItem(SchemaModel).atoms`，通用 SchemaModel 的 `_deep_freeze` 拒绝这种非 JSON 值。指标已计算，所以保留 computed 记录并附带诊断；checkpoint 尚未产生，故模拟 renderer 异常还未执行。
- 最小修复方向：C 作者修正 checkpoint 中 atoms 的显式可序列化类型，并保证 JSON 往返后 renderer 输入一致。不能放宽通用 SchemaModel、删除身份验证或改断言掩盖失败。验收执行者未改生产或业务测试；修复后首先只重跑失败节点，随后继续原来尚未运行的 3 个节点，不重复已通过的 25 案例。


## C 局部修复后的第二轮

- C 作者将 `_ResidualAtom` 改为严格不可变 SchemaModel，并将四处构造改为关键字；原测试增加 strict JSON 往返等值断言，未降低原断言。[修复前后候选 SHA256](evidence/four-module-r3-20260925/source-acceptance-second-run/scid-r3-c-atoms-fix.json)与旧审查候选分别保留。
- 只重跑原第 17 节点。[结果与命令](evidence/four-module-r3-20260925/source-acceptance-second-run/result.json)、[原始日志](evidence/four-module-r3-20260925/source-acceptance-second-run/01.log)：新加的 `assert restored == numerics` 在第 187 行失败。退出码 1，2.970 秒，观测树 RSS 最高 126,668,800 字节，未触发限额。原第 18–20 节点仍未执行，首轮 25 案例未重跑。
- 原 dataclass 拒绝已经越过：[checkpoint 原件](evidence/four-module-r3-20260925/source-acceptance-second-run/saved-checkpoint.json)已保存，19,715 字节、65 atoms、412 个有限 float，无 NaN/Inf。strict JSON 解析成功，但恢复模型与原模型不等。
- 日志没有输出首个差异字段，原/恢复对象也没有分别落盘；静态阅读 Pydantic 等值实现和 SchemaModel 未发现自定义等值或 private 状态逻辑。因此目前不能确认是具体数值还是字段类型差异，不能猜测精度问题后直接放宽断言。作者需保留断言并补首个不同路径及值/type 诊断，再做最小节点验证。真实重绘/来源身份检查在此断言之后，尚未通过。
- 第二轮证据的 [哈希清单](evidence/four-module-r3-20260925/source-acceptance-second-run/manifest.json)独立归档，未覆盖首轮失败证据、旧 review 或集成候选。


## 第三轮：限定诊断复现

调度器授权仅给新增 roundtrip 等值断言增加递归首差异消息，再运行同一节点一次。该轮有诊断代码变化，保留原严格断言，不是原样重复失败，也未改生产实现。

- [原始日志](evidence/four-module-r3-20260925/source-acceptance-third-run/01.log)、[命令与结果](evidence/four-module-r3-20260925/source-acceptance-third-run/result.json)、[身份清单](evidence/four-module-r3-20260925/source-acceptance-third-run/manifest.json)。退出码 1，2.947 秒，采样 RSS 高水位 126,754,816 字节；原第 18–20 节点继续不执行。
- 诊断证实原/恢复模型的递归 `model_dump(mode="json")` 所有值及类型完全相等，根模型类型相同，private/extra 均为 None；因此这次不是浮点值漂移。
- 静态调用链解释：`DiagnosticRequest` 中 comparison 实际为 `DiagnosticComparison`、operator 为 `ResidualOperator` 子类，计算时直接保留原实例；checkpoint 字段却声明 `CurveComparison`，strict JSON 恢复得到基类 `CurveComparison` / `CurveOperatorSpec`。Pydantic 模型等值会比较嵌套 class，所以原/恢复规范 JSON 相同而模型等值不同。
- 来源/请求资格根据已绑定引用、摘要及原请求校验，renderer 消费相同字段值；实际恢复重绘尚在断言之后，不能提前宣称通过。作者应明确 checkpoint 的类型归一化合同，或将这次新增的过强 Python 对象等值检查换成规范 JSON/atoms 的真实往返要求；原重绘、请求篡改拒绝、产物身份和禁止重算检查必须保留。


## 第四轮：C 通过，D fixture 合同失败

- C 作者在 checkpoint 构造时用声明基类 `CurveComparison.model_validate_json(..., strict=True)` 归一化比较及嵌套 operator；外层 bounded request 和完整 JSON 身份不变。原严格模型等值和诊断断言保留。[候选身份](evidence/four-module-r3-20260925/source-acceptance-fourth-run/scid-r3-c-comparison-fix.json)。
- 原第 17、18 节点均通过：严格往返、同 Run 重绘、请求/来源拒绝及失败 Run 续作复用已经执行，累计 **27 个不同参数案例通过**。前三轮失败证据保留。
- 原第 19 节点在 `test_tcad_scientific_skeleton.py:130` 失败，尚未到只读 preflight：`PreparationOnlyAdapter` 缺少 `lookup_submission`，`ExecutionBridge.__init__` 按注册合同拒绝，报 `execution adapter tcad_artifact:tcad has no authoritative submission lookup`。该 fixture 尚未同步 B 的 adapter 能力合同。应补充只准备 fixture 的显式防执行 lookup 方法，不放宽生产注册守卫或启动 solver。
- [结果与命令](evidence/four-module-r3-20260925/source-acceptance-fourth-run/result.json)、[D 原始失败日志](evidence/four-module-r3-20260925/source-acceptance-fourth-run/03.log)、[哈希清单](evidence/four-module-r3-20260925/source-acceptance-fourth-run/manifest.json)。本轮 3 节点 9.137 秒，D 失败 3.291 秒、退出码 1；第 20 节点未执行。未因失败自动重跑或加额。


## 第五轮：skeleton 通过，详细计划 fixture 缺执行服务

- D 作者仅给 `PreparationOnlyAdapter` 增加明确抛错的 lookup 方法；没有 submit 能力。原第 19 skeleton 节点通过，含只读 preflight 及审查绑定，累计 **28 个不同案例通过**。
- 原第 20 节点到正式封包/创建执行身份时失败：`self.executions` 为 None（`mcp_root_execution_routes.py:236`）。`test_l4_local_tcad._system` 的 `open_runtime` 未传 `approval_receipt_secret`；`runtime.py` 因没有 ApprovalService 也未构造 ExecutionService。这是已有 author-only fixture 扩展为 effect 验收后未初始化所需控制服务。第 19 所用 `_root` 传入测试 secret，因此不受影响。
- [第五轮结果](evidence/four-module-r3-20260925/source-acceptance-fifth-run/result.json)、[原第 20 失败日志](evidence/four-module-r3-20260925/source-acceptance-fifth-run/02.log)、[哈希清单](evidence/four-module-r3-20260925/source-acceptance-fifth-run/manifest.json)。原第 20 退出码 1，4.335 秒，观测 RSS 143,142,912 字节；未触发资源限额。
- 最小修复是为这一 effect fixture 显式初始化测试控制服务；不修改生产许可、删除审查/幂等断言或调用 solver。原第 20 为唯一尚未通过节点，前 28 案例不重复运行。


## 最终收口：29 个不同案例取得通过证据

第六轮只运行原第 20 节点，通过。D 作者给旧 fixture 增加可选测试 secret，仅这一 effect 案例显式开启并断言 Approval/ExecutionServices 创建；生产许可和审查/幂等断言未修改。

- [第六轮结果](evidence/four-module-r3-20260925/source-acceptance-sixth-run/result.json)：1 passed，进程 4.717 秒，观测树 RSS 高水位 135,188,480 字节。
- **20 个精确 selector、29 个不同参数案例全部已有通过结果。** catalog/A/B 的 25 案例在第一轮通过；C 两例在第四轮通过；D skeleton 在第五轮通过；D reviewed-producer-plan 在第六轮通过。保留五次失败执行，不覆盖原审查或原候选。
- [最终验收候选与逐项证据映射](evidence/four-module-r3-20260925/source-acceptance-final-candidate.json)记录原 92 文件候选 SHA、最终文件身份、4 个修复文件的前后 SHA、脚本/配置/guard 身份及各通过节点对应候选差异。**这是跨局部修复候选的增量验证，未在最终工作树重跑全部 29 案例。**
- 六轮执行累计 44.194 秒，观测进程树 RSS 最高 143,142,912 字节；均沿用 1GiB 每进程地址空间硬限制、120 秒 timeout、线程 1 和串行锁，没有加额、安装、构建或 solver。RSS 数字是采样高水位，不是真实峰值或聚合硬配额。
- 未验收边界仍是安装发现、真实独立 Agent 交付、local/remote runner 限额终止、2GB 实体文件传输、真实重启/未知提交恢复、短 TCAD/SDevice 闭环及部署。源码通过不能替代这些后续边界。


## 下一阶段已完成：小额度 runner 运行边界

在原源码清单通过后，调度器授权继续真实子进程/文件边界验证。新增一个小测试模块 `tests/operations/test_r3_runner_boundaries.py`，复用现有日志、控制恢复和 remote 协议用例；[独立配置](../../scripts/r3_runner_acceptance.json)共 6 个 selector，**15 个案例首次执行全部通过**，未修改生产代码。

| 实际执行 | 结果与范围 |
| --- | --- |
| local worker / remote runner 各 4 例 | 使用秒级标准库假 solver、16KiB 存储额度：同任务两个顺序 case 共用 wall deadline；两个各未超限的文件总和超限；stdout 日志计入总存储；正常主进程退出仍清理子进程。断言 TERM-resistant 子进程不再存活，允许已死亡 zombie 等待容器 init 回收。 |
| local / remote 日志各 1 例 | 真实 `/bin/sh` 假 solver 的 stdout/stderr 和独立 solver.log 保存，执行失败不丢诊断。 |
| unknown-submit 两例 | 真实控制 SQLite 重开后，假 adapter 返回已有 submission，失响应/本地登记失败不导致第二次提交；这是控制恢复合同，不是远端 solver 恢复实测。 |
| 预算跨进程一例 | 两个独立 Python 进程重开同一 ExecutionService SQLite，预留额度不重置，终态使用量结算与重复结算不重复退款；终态记录由 fixture 播种，未伪称完整执行链。 |
| remote 协议流式下载一例 | 本地子进程运行真实 remote helper 传输 2.2MB；仅替换 SSH 启动位置，无网络/真实 SSH 主机。 |
| CAS 流式注册/读取一例 | 实际 2MiB 二进制写入并按小块核对 digest；对二进制 `Path.read_bytes` / CAS 全量 read 设失败守卫。 |

[命令与结果](evidence/four-module-r3-20260925/runner-acceptance-first-run/result.json)、[候选/日志/runner job 与输出 manifest 哈希](evidence/four-module-r3-20260925/runner-acceptance-first-run/manifest.json)已独立归档。6 节点累计 9.552 秒，观测进程树 RSS 最高 120,041,472 字节；资源保护与前述相同。原 92 文件验收候选逐项 SHA 未变化。至此前后两份有限清单共 **44 个不同案例通过**，不代表完整测试集。

剩余边界现在收窄为：隔离 wheel/插件安装发现、真实短 TCAD/SDevice 科学运行、真实 SSH 现场、2GB 实体传输/1h 长任务、真实外部 Agent 交付及目标部署。用户已授权受限安装、构建和短 TCAD，并要求在当前 cwd 新建专用临时验证目录、完成后删除；由调度器串行启动下一阶段，先归档必要日志，不修改既有服务。本 runner 阶段没有预先启动这些后续动作。
