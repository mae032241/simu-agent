# R0：W 在场时的早期隔离工程反馈

日期：2026-10-17。基线：`565a2e4`。状态：实现与定向用例已写入，独立静态代码审查PASS并提交2ca47a9；本轮仅静态检查，没有运行测试或安装验收。

## 故障与修改边界

已确认的结构缺口：受管实验完成只证明原任务环境中的执行事实。现有 shortlist smoke 虽与公开审计共用 `cov_delivery.isolate`，但到收口才执行，且只加载保存模型并预测，没有重新导入原源码、调用 `train()`。模型的序列化对象可能不再需要训练时 helper，因此 smoke 不能提前暴露这类依赖缺口。原 W 提示也没有说明隔离复跑可见的源码、依赖与公开输入范围。

R0 在原调用已确认终态后自动提供可选工程反馈，让 W 在同一任务/session 内修正实现。它不改已接受实验的完成状态、科学指标、候选身份、封存原件或 A 的选择，不执行 public audit、提交、promote 或隐藏评分。

设计先经独立审查通过后实施。两个实施前阻断已落实：replay 显式属于可写 scratch 且不挂真实 target/source_roots 的分支；R0 不依赖工作树尚未提交的 P1 public_capabilities、registered_implementation 或 operator_configuration。

## 通用接缝

- 继续使用既有 `AdapterCapability`。支持方声明 `isolated_replay`、检查范围、诊断上限及反馈余量，实现可选 `replay_check` 方法；没有新增必需 managed 方法，没有修改其他插件的 typing 或生命周期合同。通用 freeze 自动把 replay_check 框架原件加入执行实现身份，第三方支持方无需自行列出这个控制 helper。
- 通用 `replay_check.py` 在调用接受前绑定能力原文摘要、公开 policy、原调用 boot ID 与截止时刻到既有 `accepted.json` metadata。未声明能力返回中性的 `unsupported`；旧调用缺少绑定时只显示 `not_run`，不为历史补造声明或额度。
- 同步 `dispatch` 在 `record_observation` 确认原执行后触发一次；显式 `reconcile` 确认终态后采用同一接缝。`query` 只读，永不因此启动复跑。
- 工程 intent 先于检查进程/outcome 写入。intent 已存在但没有 outcome 时为 `unknown`，不自动重放。回执绑定原 accepted/completed 摘要；采用既有 call 文件目录、lease、proof 和写入原语，不建立新的候选索引、审计资格或科学状态机。
- 原执行与工程检查共享接受时确定的原调用截止；soft admission 还受已验证 host review 剩余时限约束。该次检查的绝对截止 `min(原调用/host 截止减反馈余量, 检查开始加诊断上限)` 绑定 intent 并传入 adapter，贯穿准备、分块校验、启动和执行循环。10 秒只是可选诊断的整体准备/执行上限；准入前保留 2 秒反馈余量，两者都不是新授权、节点硬停或科学完成门槛。缺失时限、boot 不符、预算不足时记 `not_run`。清理异常可能耗时，反馈余量不构成清理后还剩 2 秒的保证。
- 检查普通异常被隔离为工程 `unknown`，保留完整异常诊断，不改变成功实验的 CLI 退出码；进程中断与 `SystemExit` 等 `BaseException` 语义不被吞掉。

## Cov 实现与证据范围

只有已有独立公开 runner receipt profile 的 Cov adapter 声明该能力；任意 `backend_file` 实现不被推断为支持隔离复跑。普通 local、TCAD 或其他未声明 adapter 保持 `unsupported`。

接受调用前，Cov 使用已确认 runner 所在公开目录，冻结精确 runner/train.csv/val.csv/meta.json、当前纯 protocol、任务解释器原件及其来源；数据通过 HEAD 已有 `metadata.snapshot_files` / `Records.accept` 复制。runner 的证据必须与原独立 receipt producer 一致；额外环境映射不符合该公开布局时不猜测替代输入，检查返回 unsupported。源码仍使用原接受流程已有的 `source.py` 快照。 接受前新增的 public 文件 hash 与 `Records.accept` 快照复制属于原 native 任务的墙钟开销，由原宿主时限/计量覆盖，未被终态之后的 10 秒诊断上限包住；没有为它们另授时间。解释器二进制绑定原件，安装库在同审计 runtime 中只读可见，但库文件没有逐项冻结；不把这一点声称为完整软件环境身份。

终态后的 stage 不再重拷整份数据：只把原 accepted call 的 `source.py` 与 inputs 快照硬链接为只读 leaf 输入，核对 regular/size/inode，绝不链接当前 harness 或旧工作区。leaf 对实际挂载字节做摘要核对；public/runtime/protocol 的 hash 每 1 MiB 块检查同一绝对截止。准备到期返回 not_run，不再启动 leaf；`_call` 使用剩余时间且循环取该绝对截止，不能在准备之后重新发满额 seconds。隔离复用原 `cov_delivery.isolate` 与 `delivery._call` 的 namespace、无网络、进程身份和 owned-group 清理。replay 只挂只读输入、任务 runtime 和可写 scratch，不挂真实提交目标、原工作区、解析 source_roots 或用户 home，不调用 exp_cli 的 submit/audit。无法建立该隔离时不能改在普通 host 环境执行。

leaf 使用 CSV 原顺序前最多 32 个 train 行和 8 个 val 行，`read_csv(nrows=...)` 不为检查扫描其余记录。回执记录实际读取行数、选择方法和未扫描的总数限制。随后执行精确源码 import、一次 `train(sample_train, sample_val)` 和公开 runner 约定下的样本预测；检查预测接口、形状与有限值。没有重新运行完整训练或完整科学审计，也没有创建或安装环境。

| 工程状态 | 含义与 W 可以采取的动作 |
| --- | --- |
| `sample_replay_ok` | 仅该实际小样本路径完成；未执行分支、完整数据训练、公开审计和隐藏表现仍未验证。 |
| `dependency_error` | 该声明样本路径出现可识别的 `ModuleNotFoundError` 或 `FileNotFoundError`；诊断指出缺失对象。W 可在原 session 修改源实现，以新调用验证；原调用不重跑。不能推导全数据可复跑结论。 |
| `inconclusive` | 一般训练异常、固定 shape/最小样本/类别数量要求、预测不适配，或有界检查未获得结果。未完成的检查可能是超时或进程失败，未凭返回空值冒称已确定超时。不会拒绝候选或改科学分数。 |
| `unsupported` / `not_run` | 无声明、公开输入映射不足、旧调用无绑定，或原剩余预算/反馈余量不足；均非通过。 |
| `unknown` | 已接受但无确认 outcome、能力/回执不可验证或 cleanup 未确认；不自动重放。 |

原调用目录保存持久的工程 stage，包括完整 replay stdout/stderr、leaf JSON 与部分记录。确认清理后，原始诊断文件设只读；只有原截止内完成 hash 的诊断才保存完整 proof，到期时保留原文件并明确记为未 hash，不补造 sealed 原件。清理未知时保留 stage，不把仍可能写入的日志称为封存诊断。既有 `_call` 的 tail 是额外预览，完整日志没有随临时目录删除。完整异常在工程 sidecar/持久 leaf JSON，检查结果在 outcome；Cov leaf 向控制进程的回包也只带 1024 字节诊断预览，完整诊断仍保留，避免期外读取大响应；截止已过时不再启动 `_call` 的 JSON 解析。W 的 public view 只含状态、范围、实际样本、清理状态和最多 1024 字节诊断，显式给出省略字节数，不灌入原始路径与日志。

所有 W 的原生提示都收到简短指导，覆盖 external Cov launcher 与 registered 路径；提示不要求 W 手工打包、计算 hash 或填写机械表格。声明范围之外的 sibling scratch helper/home 不可见，科学判断仍交 A。

## 定向回归用例（已写，未运行）

`tests/research_loop/test_early_replay.py` 复用现有 execution metadata/公开 receipt profile；fixture 的真实原 runner 调用一个常量预测器的 train 并保存模型，不制造工程成功 JSON。测试调用生产 dispatch、真实 namespace 和 leaf。

1. train-only helper 在原 runner import 上下文可用，保存模型无此依赖；早检真实调用 train 时报告 dependency_error。W 修改为独立实现后同任务的新调用得到样本成功，旧 completed 字节与科学指标不变。
2. 原 64 行训练有效，而样本行数不满足算法要求；CLI 仍返回原实验 known_success/零退出码，工程结果 inconclusive。
3. 原执行完成后修改当前源码与公开 val；检查仍使用接受前冻结字节。随后模拟已有 intent 丢 outcome，再次接入不重放或改原文件。
4. optional check 抛 RuntimeError 仍保留原成功 CLI；原接受截止耗尽时跳过检查，不重新给 10 秒；普通 local 执行成功且能力中性 unsupported。
5. 在真实 stage 的首次 accepted snapshot 硬链接之后模拟原时限耗尽；仍保留原实验 known_success，工程反馈 not_run，且不允许 `_call` 再启动一个获新时限的 leaf。

没有增加安装环境、业务闭环矩阵、真实模型或 solver 用例。实际回归执行要等根任务确认硬资源域后另行授权；本记录不能称这些用例已通过。

## 共享文件拆分与最小前置

R0 代码/测试共 8 个文件（定向用例现为 5 条，均未运行）：

- `src/scidiscovery/research_loop/replay_check.py`（新增）
- `src/scidiscovery/research_loop/experiments.py`
- `src/scidiscovery/research_loop/native.py`
- `src/scidiscovery/research_loop/cov_experiments.py`
- `src/scidiscovery/research_loop/cov_delivery.py`
- `src/scidiscovery/research_loop/cov_lineage.py`
- `src/scidiscovery/research_loop/delivery.py`
- `tests/research_loop/test_early_replay.py`（新增）

本记录另为新增文档。

`experiments.py` 与 `native.py` 动代码前已有 P1 未提交修改，已事先保存基线。R0 专属 patch 只取该基线之后的增量；experiments 为接受声明、完成触发、reconcile 触发和简短投影，native 为独立的全 W 提示。P1 的注册配置、发现合同、输入 schema、CLI prepare 与能力读取等增量不在 R0 patch 内；TCAD 容量生产改动也未触及。

已将 R0 专属 patch 实际应用到 `565a2e4` 的临时最小文件树，8 个文件及内嵌 replay/runner 脚本通过内存语法检查；对 index 的 `git apply --check --cached` 也通过。R0-only patch 没有 P1 的上述字段或方法。因此本次 R0 的最小前置是 HEAD 既有 AdapterCapability、accepted 输入快照、execution observation、budget review 与隔离调用原语，不要求先提交 P1。私有基线、临时树和补丁只供编排/审查，不随本记录提交。

## 静态检查与未执行事项

已做：源文件/内嵌脚本内存 `compile(..., 'exec')`；对 clean HEAD+R0 的同类语法检查；R0 patch 可应用性；`git diff --check`；新旧能力和调用链的文本/AST 静态阅读。语法检查不执行 import、fixture、候选或 launcher。

未做且当前禁止：pytest、collect-only、构建、pip、venv、模型、SSH 或 solver。没有自行提交。运行时行为、资源开销和真实安装结果均未获本轮执行证明。

独立预算审查修正：移除完成后重复全量 original 验证和 stage 数据复制；将原调用/host 剩余与 10 秒上限合成唯一绝对截止，传入 intent、adapter、runtime/protocol/input 分块 hash 及 `_call` 启动/循环。保留 2 秒只作为准入余量，不承诺阻塞 IO 或清理后仍剩余 2 秒。Python 同步文件/stat/读取单次系统调用不能被该软检查强行中断，截止在块间和阶段边界检查；仍需外层已配置资源域，不能把本次静态补修宣称为硬资源隔离。
