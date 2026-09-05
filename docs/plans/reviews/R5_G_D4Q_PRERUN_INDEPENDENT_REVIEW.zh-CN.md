# R5-G D4-Q 运行前第二轮独立审查

## 一、结论

**结论：通过（只放行 D4-Q，不放行 D4-H）。**

首轮报告的 F1—F3 已在一次性运行边界内按最小范围闭合。当前方案不会把 ABI 6 的旧批准换成
ABI 8 digest，也不会用确定性别名洗白旧 Agent 输出；它保留旧证据族和旧决定不变，在 ABI 8
代际中从相同六项冻结来源重新执行当前 evidence extract、独立 audit、split 和本地 UI qualify。
只有当前 audit 给出 `pass` 且用户在本地回环审批界面选择 `approve`，D4-Q 才能形成新的资格报告。

本结论只允许：

1. 对真实持久 run 创建一次 `state-d4-abi8/` 前向代际；
2. 在该代际中运行 `scripts/r5_g_requalify_evidence_abi8.py`；
3. 把新审批网址交给用户并只读取界面封存决定；
4. D4-Q 结束后进行独立科学与谱系复审。

**本报告不授权启动 `science.hypothesis.revise.v1`、新 hypothesis critic、实验设计、外部求解、
R5 发布冻结或任何 D4-H 工作。**

## 二、审查范围与方法

审查基线是本地 `baseline/8765-codex` 的未提交工作树；没有猜测远端基线，也没有评价无关脏文件。
本轮完整阅读并交叉核验：

- 首轮报告 `R5_G_D4_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md` 的 D4 返工记录；
- `scripts/r5_g_migrate_state_to_abi8.py`；
- `scripts/r5_g_requalify_evidence_abi8.py`；
- `scripts/r5_g_hypothesis_revision_stage.py`；
- `scripts/r5_g_science_chain.py`；
- 三个 R5-G runner 测试及资格 provider、producer family 的相邻真实 Root 测试；
- 可丢弃探针 `.scidiscovery/r5-e2e-private/d4-prerun-probe-20260830-04/`。

按“旧冻结状态 → 一次性 descriptor 代际 → 当前确定性来源 → 当前 extraction → 当前独立 audit →
split → 当前本地 UI qualification → D4-H 关闭”追踪了 Root、Task、Artifact、Worker、Approval、
插件目录和恢复边界。未启动真实 Codex Agent，未创建或迁移真实 `state-d4-abi8/`，未作出或模拟
人工决定，未调用 8765，未读取科学 payload 内容。本报告之外没有修改实现文件。

## 三、首轮问题闭合情况

### 1. F1 已闭合：旧资格只作历史事实，不被继承或重签

`_validate_old_approval_family()` 现在同时核验：

- 旧请求确实绑定冻结报告中的 foundation、intake、六项来源和 audit；
- 决定存在且 `selected_option=approve`；
- `HumanDecision.subject_refs` 与旧 `ApprovalRequest.subject_refs` 精确相等；
- 旧请求的 provider operation 是 `science.evidence.qualify.v1`。

此检查只证明历史决定真实存在。旧请求、旧决定、旧 subject、旧 compiled identity 均未改写，
也没有被赋予 ABI 8 当前资格。当前已安装目录仍显示旧 provider digest 与 ABI 8 当前 provider
identity 不同；provider-aware admission 继续按完整编译身份失败关闭。

返工后的模块说明也已纠正：旧九对象只用于验证历史边界。新资格的 subject family 包含当前
extract 产生的新 intake、当前独立 audit、由二者 split 的新 foundation、四项保持原绑定的冻结
来源，以及两项由当前确定性投影重建且逐字节相同的来源视图。资格报告显式记录
`old_decision_inherited=false`，没有把它伪装成旧审批的延续。

### 2. 仅确定性 rebind 不足，重新运行两个 Agent 是必要的最小科学边界

可丢弃探针先在 ABI 8 中重建四个确定性对象，并逐项比较旧、新 Schema、媒体类型、大小、SHA-256
和完整 payload 字节。四项均逐字节相同。即使如此，旧 extraction primary 仍因旧 Agent producer
contract 不属于当前目录而以 `input_producer_contract_changed` 失败。

因此不能采用以下更短但不正确的路径：

- 修改旧 task authority 或 operation digest；
- 给核心增加 ABI 6 白名单；
- 用 Transform 为旧 intake/audit 伪造当前 Agent producer 身份；
- 只对旧九对象重新发起当前审批。

当前资格 projector 要求 foundation 精确来自当前 intake 与精确独立 audit，且 extraction primary
属于可验证的 producer family。重新运行当前 extract 和 audit 不是重复 TCAD 求解或重复已跑通的
科学闭环，而是跨 ABI 代际重新建立当前可审计的 Agent 生产者边界。它只增加两次必要科学判断，
没有扩成新的工作流框架。

### 3. F2 已闭合：schema 2 记录并复核完整 descriptor/output/signal 代际

迁移报告对 12 个历史 Task 逐项冻结：

- `task_id`、完整 `old_task_ref` 和 `new_task_ref`；
- 唯一删除字段 `output.revision`；
- 新 descriptor 的直接 `parent_refs` 和 `supersedes_ref`，二者均精确指向旧 descriptor；
- task `state`、`attempt`、primary output ref 和 scheduler signal ref；
- primary/collection output 的完整 ref 及其仍指向旧 descriptor 的 `output_task_ref`；
- scheduler signal 存在时仍指向旧 descriptor 的 `scheduler_signal_task_ref`，不存在时显式为
  `null`。

校验器从实际 SQLite、CAS envelope 和 payload 重新计算上述关系，不只信任报告字段。它还验证
旧 payload 规范 JSON 且只删除值为 `null` 的退役字段，新 payload 严格满足 ABI 8 `AgentTask`。
四个未应变化的控制库 `approvals.sqlite3`、`executions.sqlite3`、
`scheduler-bindings.sqlite3`、`task_tokens.sqlite3` 的完整键集和初始 SHA-256 被报告冻结；task 的
状态、输出和 signal 又逐行复核。科学输出、Approval 和 scheduler signal 没有被复制或重写。

新探针的内外报告字节一致，SHA-256 均为
`667d080ee0adf53c90c80c84c27b7d444f1fc05461c40b86df5cf083387dc5c0`。当前 ABI 8 校验器以
`allow_descendants=true` 对已经增加确定性探针后代的状态复核通过：12 项映射全部存在
`scheduler_signal_task_ref` 字段，其中 11 项为精确旧 task ref，唯一无 signal 的失败 Task 为
`null`。探针记录的真实 `state/` 树前后摘要均为
`129059c89f87c892743d63efb8b6167e7b6d5408100996f9e9203276b77918ca`。

### 4. F3 已闭合：安全 staging、终态门与幂等恢复

迁移在原状态的独占 maintenance lock 内执行以下动作：

1. 拒绝活动 WAL；
2. 拒绝任何非 `completed/failed` Task；
3. 对遗留 `.state-d4-abi8.preparing/` 只允许删除 run root 下的真实直接子目录；
4. 符号链接、非常规文件、越界路径或树在检查期间变化均失败关闭；
5. 从未修改的源状态重新复制并从头生成；
6. 内部完整报告先写入 staging，再原子 rename，最后写外部同字节报告。

若目标已完成但外部报告因 rename 后崩溃而缺失，重跑只会按内部完整报告补写外部记录并再次全量
验证。目标不完整、外部报告孤立或报告内容漂移都会停止。这里没有引入在线迁移协议、回滚状态机
或通用 MigrationManager。

## 四、D4-Q 运行边界核验

### 1. 单一 ABI 8 目录与状态根

当前 `runtime-venv-d4` 实测加载 operation ABI `8`，安装目录共 47 个 Operation。D4-Q 使用同一
runtime 打开 `state-d4-abi8/`。`_run_agent(..., state_root=state_root)` 把同一个显式路径同时传给
control daemon 和 Worker daemon；两个 Agent 调用均显式传参，不会回落到旧 `state/`。
`initialize_platform()` 由这一 CompiledCatalog 重新生成当前 Codex 配置，任务 authority 仍由编译
OperationSpec 冻结。

脚本使用进程内 Root facade 和新启动的 Unix socket daemon，不连接陈旧 8765。唯一 HTTP 监听是
随机空闲端口上的 `127.0.0.1` 审批 UI。

### 2. Agent 权限、文件生命周期和网络

`science.evidence.extract.v1` 与 `science.evidence.audit.intake.v1` 的当前 permission template 实测均为：

- `network.mode=none`；
- 没有注册网络 Worker 工具；
- 仅有编译得到的 Worker 文件生命周期与已声明 PDF/原生只读能力；
- 主结果必须经 task-private `output/result.json`、validate 和 finalize 封存；
- 父 Codex 只启动无父历史子 Agent，聊天返回不作为科学结果。

当前 Codex 0.150.1 原型仍只能通过编译提示明确禁止可见但未授权的原生网络/跨 Operation 工具，
不是内核级隐藏能力。本候选没有夸大成进程级网络隔离。D4-Q 的 Operation、任务指令和模型可见
工具表三处均禁止网络；若执行环境要求强隔离，仍应由外层沙箱关闭网络，这不属于本次一次性代际
迁移新增的问题。

### 3. 7 GiB 与真实执行纪律

本轮所有独立测试和探针复核均在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、串行模式下执行。
真实 D4-Q 也必须从设置同一限制的 shell 依次启动迁移器和 requalification runner，使 UI、control、
Worker 和 Codex 子进程继承限制。脚本本身不创造第二套内存预算权威；若启动命令没有该外层限制，
本报告不视为满足运行条件。

### 4. 科学与人工失败门

当前 split/qualification projector 对 audit 有精确硬门：audit 必须来自
`science.evidence.audit.intake.v1`，handoff verdict 必须为 `pass`，父项必须覆盖 current intake 和
完整六源，且 source keys 必须覆盖 foundation 声明。audit 为 `blocked`、`inconclusive`、来源不全
或父链不符时，split/qualification preflight 停止，审批请求不会创建。

审批请求创建后只轮询 `approval_status`。超时、`revise`、取消或任何非 `approve` 决定都会抛错并
停止；脚本没有审批写入口，也不能把聊天文字转成决定。只有用户在返回的本地 UI URL 上批准精确
新九对象，才会写新的不可变 D4-Q 报告。

## 五、奥卡姆与架构目标

本次返工没有新增核心类型、数据库表、注册表、scheduler 分支、资格权威、领域 operation id 特判
或运行时兼容 Schema。新批准与旧批准是同一 `science.evidence.qualify.v1` 在不同编译代际对不同
不可变 subject family 的两条历史记录；当前 provider 是唯一可供后续准入的资格权威，旧记录只作
来源证明。

新增复杂度被限制在两个一次性 R5-G 运行脚本和一份代际报告。确定性重绑定复用已注册 Operation，
Agent 重跑复用既有 extract/audit Operation、角色、Schema、Worker 工具和 UI。没有把 D4-Q 特例写回
通用 core，也没有为了本次运行新增第二套科研流程控制器。通用 qualification projector 中既存的
producer family 约束未被本阶段扩张；若后续要进一步通用化它，应另立架构任务，不能借 D4-Q 放宽
当前失败关闭边界。

因此，这一方案虽比“改一个 digest”更长，却是保护不可变科学来源、当前生产者身份和人工决定
所需的最小诚实转换；更短的兼容补丁会重新引入用户要求删除的多代际特判。

## 六、独立测试证据

在 7 GiB 虚拟内存限制下独立复跑：

```text
python -m pytest -q \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_r5_g_hypothesis_stage_runner.py \
  tests/operations/test_r5_g_science_chain_runner.py
```

结果：`17 passed in 0.51s`。新增测试同时覆盖 scheduler signal 缺失时报告 `null`、存在时冻结旧
task ref。

另复跑当前 Agent 完整文件/父链、精确 provider identity 和未知插件 producer digest 漂移三组
真实边界测试，因参数化共 `5 passed in 3.79s`。实现方记录的相关集合为 `68/68`；本报告的独立
结论不单靠该记录，而是同时依赖当前 ABI 8 对 disposable probe 的实际复核。

可丢弃探针复核结果：

- schema 2，12 项 Task 映射；
- 内外报告字节一致；
- 当前 `validate_state_generation(..., allow_descendants=True)` 通过；
- 12 项 signal task-edge 字段齐全；
- 四个当前确定性投影与旧对象逐字节相同；
- 旧 Agent producer 在当前资格链仍失败关闭；
- 真实 run 的 `state/` 树前后摘要相同。

没有运行全仓回归、浏览器人工决定、真实 Codex Agent、网络或 TCAD solver。它们不是“只放行
D4-Q 运行”的运行前必要替代证据；真实 Agent 的科学质量和本地 UI 决定必须在 D4-Q 实际运行后
由下一轮独立审查判断。

## 七、D4-Q 执行与后续门

D4-Q 真实执行必须满足以下顺序，任一失败即停止：

1. 在 7 GiB 外层限制下运行当前 ABI 8 迁移器，先验证真实 generation report；
2. 在同一 ABI 8 runtime 和 `state-d4-abi8/` 上启动 requalification runner；
3. current extraction 完成并由 Root 确认 sealed output；
4. current independent audit 完成且 verdict=`pass`；
5. split 与 qualification preflight 通过；
6. 把精确本地 UI URL 交给用户，等待界面决定；
7. 只有 UI=`approve` 才封存 D4-Q 报告；
8. 停止运行，交由新的独立审查者读取新 intake、audit、foundation、Approval、迁移报告和精确父链。

即使 D4-Q 成功，仍然**不得立即运行 D4-H**。只有 D4-Q 后置独立审查明确确认新 audit、完整九对象
subject family、当前 provider identity、旧状态不变及阶段报告均正确，才可另行考虑放行假设完整
对象修订。新 hypothesis critic、最终科学复审和实验设计门仍全部未执行。
