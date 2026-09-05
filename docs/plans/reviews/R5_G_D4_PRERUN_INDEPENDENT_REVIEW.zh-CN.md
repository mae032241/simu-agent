# R5-G D4 真实运行前独立审查

## 一、结论

**结论：不通过。不得迁移真实 D4 状态，不得启动真实 Codex Agent，也不得进入实验设计。**

当前候选的主链方向是正确的：ABI 8 目录中的 `science.hypothesis.revise.v1` 是直接完整对象修订，
随后使用 `science.hypothesis.criticize.v1` 审查新对象；两次 Agent 调用已经显式把控制端和 Worker
端指向 `state-d4-abi8/`，没有使用陈旧 8765；阶段报告也不会把任务 `completed` 当成科学通过。

但真实冻结数据暴露出一个确定性阻断：原证据资格决定绑定的是旧编译合同，ABI 8 当前资格
Operation 的编译身份已经变化。现有 runner 只检查旧决定仍为 `approve`，随后却要求 ABI 8
preflight 按当前 provider 身份承认它；核心的精确合同检查会拒绝该旧决定。因此候选按现状必然在
启动修订 Agent 之前以 `input_cohort_approval_missing` 停止。这个问题不能通过改写旧人工决定或放宽
provider 身份比较解决。

此外，一次性状态转换尚未把“任务描述符代际别名”闭合成可独立复核的精确记录，runner 也没有
验证自己打开的目录正是该迁移报告证明的代际。由于旧科学输出的不可变 `task_ref` 仍指向旧描述符，
而迁移后的 `tasks.task_ref_json` 指向新描述符，这不是只靠两个 SHA 字符串就可以省略的细节。

## 二、审查范围和方法

审查基线为本地 `baseline/8765-codex` 的大规模未提交工作树；没有猜测远端或提交基线。本报告只
审查以下候选及其直接消费者，不评价无关脏文件：

- `scripts/r5_g_hypothesis_revision_stage.py`；
- `scripts/r5_g_migrate_state_to_abi8.py`；
- `scripts/r5_g_science_chain.py` 中 `_run_agent` 的状态根传递；
- `tests/operations/test_r5_g_hypothesis_revision_stage_runner.py`、
  `test_r5_g_hypothesis_stage_runner.py`、`test_r5_g_science_chain_runner.py`；
- ABI 8 已安装目录、OperationSpec、Root 准入、Task 精确 reviewer 判定、Approval provider 判定；
- 持久 run `replay-live-20260830-03` 的旧阶段报告、SQLite 任务/审批记录和不可变 CAS 元数据。

按跨边界路径检查了：冻结报告 → 状态代际 → Root preflight → Task/Worker daemon 状态根 → 完整
修订输出 → 新 critic → 阶段报告。没有运行真实 Agent，没有创建或迁移 `state-d4-abi8/`，没有调用
8765，也没有读取或改写科学输出内容。

## 三、必须修复项

### F1（阻断，代际与人工资格边界）：旧资格决定不属于 ABI 8 当前 provider

**位置：**

- `scripts/r5_g_hypothesis_revision_stage.py:105-113,134-154`；
- `src/scidiscovery/artifact_agent/service/approvals.py:311-367`；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` 的 cohort provider 准入。

冻结审批 `r5g_evidence_qualification.rev2` 的精确编译身份是：

- `operation_id = science.evidence.qualify.v1`；
- `operation_digest = 96a767d58c1a253fb221302ef8596034a5f3c192ebf4a5f34698dcf51f454287`；
- `approval_contract_digest = 68518352e3808d856f35b84b81fcc9f12eeca94f14958a95eb209e17557defeb`。

当前 `runtime-venv-d4` 编译出的 ABI 8 身份是：

- `operation_digest = 5d639ffaf9fd61f53ba1c9fb58bb59213a62dddc4a33166b75b3d41bb789ca16`；
- `approval_contract_digest = e77be3ab60b964ec16ecde3da6be0d4aa614913f7a91a52a113091697d628a0c`。

`are_subjects_approved_by_provider()` 在第 358 行按完整 `CompiledApprovalIdentity` 精确比较，而不是只
比较 operation id。旧 `approval_status` 仍为 `approve` 只能证明旧问题下的人类决定存在，不能把它
升级为对新编译合同的决定。`science.hypothesis.revise.v1` 的 `scientific_foundation` 端口声明了
`qualified_foundation` cohort 和当前 `science.evidence.qualify.v1` provider，所以第 134 行的真实
preflight 必然失败。

**影响：**D4 不会进入 revision Agent；文档中的“复用原 approved foundation”在当前实现中把
“同一科学 foundation”错误等同成了“旧批准可跨编译合同沿用”。

**最小正确修复：**

1. 保留旧审批请求和决定原样，禁止迁移、重签、改写 digest，也禁止在核心增加旧 identity 白名单；
2. 在 ABI 8 新代际中，使用当前唯一 `science.evidence.qualify.v1` 对原完整 evidence family 创建
   一个新的精确资格请求；决定仍只能通过本地回环 UI 产生；
3. 生成新的不可变资格阶段报告，冻结新 approval 名称、revision、当前 compiled identity、原
   foundation 和完整 subject family；
4. D4 runner 改为读取该新报告，同时保留旧报告 SHA 作为历史来源，不把新审批伪装成旧审批延续；
5. 增加真实 Root 测试：旧 identity 必须失败，新 ABI 8 对同一完整 subject family 的决定才通过。

该修复属于**代际转换与人工资格边界**，不是局部准入补丁。它不要求改核心，也不新增资格权威。

### F2（阻断，代际谱系）：runner 没有验证状态代际证明，任务描述符与旧输出的精确引用分叉

**位置：**

- `scripts/r5_g_migrate_state_to_abi8.py:93-140,156-194`；
- `scripts/r5_g_hypothesis_revision_stage.py:192-207`；
- `src/scidiscovery/artifact_agent/service/tasks.py:1431-1469`。

转换器为每个旧 task descriptor 创建一个只删除 `output.revision: null` 的新 descriptor，并让新
descriptor 直接 `parent`/`supersedes` 旧 descriptor；这一思路本身比运行时兼容分支更合适。对真实
12 个旧 task payload 的只读检查也确认：每个 payload 都是规范 JSON，唯一需要删除的字段均为
`output.revision` 且值为 `null`，删除后全部满足 ABI 8 `AgentTask`。

未闭合之处有三点：

1. 迁移报告只记录 old/new payload SHA，没有记录完整 `ArtifactRef`、旧输出指向的 task ref 以及
   新 descriptor 对旧 descriptor 的 parent/supersedes 关系；
2. 既有 output envelope 的不可变 `task_ref` 仍指向旧 descriptor，而 `tasks.task_ref_json` 被更新为
   新 descriptor；`completed_output_contract()` 只通过 output ref 找到 task id，随后读取表中的新
   descriptor，没有核对 output envelope 的旧 `task_ref` 与新 descriptor 的受控代际关系；
3. D4 runner 只检查 `state-d4-abi8/` 是目录和 Python ABI 字符串为 8，完全不读取内外迁移报告，
   也不验证 12 项映射、任务状态、旧科学输出 ref、Approval 与 scheduler signal 未改写。

这会让“新 descriptor 与旧输出合同科学等价”停留在迁移脚本作者的意图，而不是 D4 可复核的输入
事实。它还允许同名但来源不明的状态目录进入真实运行。

**最小正确修复：**不要给通用 TaskService 增加兼容分支，也不要复制或重写旧科学输出。只需在这
个一次性转换器及 D4 runner 内补足代际证明：

- 报告记录每项完整 old/new task `ArtifactRef`、task id、唯一删除路径；
- 转换后逐项验证新 descriptor 的 payload 只发生该字段删除，parent 与 supersedes 都精确指旧
  descriptor；所有既有 output envelope 的 `task_ref` 仍精确指旧 descriptor；表内新 ref 必须与
  报告映射一致；
- 报告冻结转换前后的 task state、output ref、scheduler signal ref，并验证它们逐项相同；
- 内部报告和 run-root 外部报告字节一致；D4 runner 在打开 runtime 前先验证完整报告和实际状态，
  任一缺失或漂移都失败关闭。

该修复属于**状态代际谱系**。它是在一次性边界上证明等价，不应演化成通用 MigrationManager、
兼容 Schema 或第二套 Task 权威。

### F3（必须在运行说明或代码中闭合，局部恢复）：崩溃恢复只覆盖 rename 后窗口

`generation-migration.json` 在 staging 内先写、再 rename，已经解决“destination 已出现、外部报告
尚未写出”这一窗口。但若进程在 copy、CAS 注册或 task 表事务期间崩溃，
`.state-d4-abi8.preparing/` 会保留；下一次调用在 `scripts/r5_g_migrate_state_to_abi8.py:59-61` 永久
拒绝继续。原状态仍安全，因此这不是数据损坏，但不能宣称迁移已具备完整崩溃恢复。

首版可采用很小的恢复边界：仅当 destination 和外部报告都不存在时，验证 staging 是 run root 下
的真实直接子目录，然后在取得原状态独占维护锁后丢弃该**派生临时目录**并从头复制；任何符号链接、
未知文件类型或同时存在的目标/报告均失败关闭。还应在复制前强制确认源状态没有非终态 Task；真实
冻结状态当前为 11 个 completed、1 个 failed，适合转换。无需设计通用在线迁移协议。

## 四、已经成立的边界

以下项目没有发现新的阻断：

1. **单一目录和 ABI 8：**`runtime-venv-d4` 实际加载 ABI 8，安装目录有 47 个 Operation；修订与
   critic 均来自同一个 `CompiledCatalog`。修订 Operation 被结构总函数识别为直接完整对象修订。
2. **完整对象而非补丁：**修订指令明确要求完整替代对象，禁止补丁、差量和回执；Operation 输出
   仍是 `scidiscovery.hypothesis-proposal.v1`，复用 ideator、原 Schema、validator 和 reviewer。
3. **旧 blocked critic 的精确关系：**冻结 critic 的 scheduler signal 为 `blocked`；其 task 输入
   `hypothesis_portfolio` 精确指向 `r5g_hypothesis_portfolio.rev2.output`，两者没有被改写。
4. **新审查关系：**runner 把新 portfolio 作为新 critic 的精确输入，并用
   `is_exact_reviewer_output(... accepted_verdicts=("pass",), subject_ref=new_ref)` 判断合同准入；旧
   critic 不可能因此变成新对象的通过评审。
5. **状态根：**最新 `_run_agent(..., state_root=...)` 同时把控制 daemon 和 Worker daemon 的
   `--state-root` 指向 D4 代际；D4 两次调用都显式传入该目录，没有依赖旧 `state/` 默认值。
6. **科学通过语义：**runner 报告记录 revision/critic task state 和 critic verdict；即使新 critic
   为 pass，也只写 `awaiting_independent_review`，并保持 `stage_admissible=false`、
   `experiment_design_released=false`。脚本没有实验设计调用。
7. **角色与文件边界：**Agent 仍由编译角色、无父历史子 Agent、任务私有文件、validate/finalize 和
   sealed Task 输出完成。父进程只把子会话完成视为信号，随后读 Root `task_status`。
8. **网络边界：**两个 Operation 的编译 limits 均为 `network.mode=none`，指令再次禁止网络。当前
   Codex 原生工具不可见性仍只是已公开的原型提示约束，不能被描述为进程级强隔离；本候选没有
   新增对该限制的夸大。
9. **奥卡姆目标：**候选没有新表、注册表、状态机、通用修订管理器或领域 id 特判；一次性转换是
   为读取已冻结 ABI 6 Task 所需的局部代际边界。F1/F2 应在此局部边界修复，不能把复杂度推回核心。

## 五、测试和只读证据

在 7 GiB 虚拟内存上限、串行模式下运行：

```text
python -m pytest -q \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_r5_g_hypothesis_stage_runner.py \
  tests/operations/test_r5_g_science_chain_runner.py
```

结果：`12 passed in 0.39s`（5 + 4 + 3）。

另做的只读检查：

- 冻结报告 SHA：evidence `e9470066...581`，hypothesis `c1928b3c...b16`，均与常量一致；
- 源状态 12 个 Task：11 completed、1 failed；全部旧 descriptor 仅需删除 null revision 即可被
  ABI 8 严格解码；
- 旧 critic/portfolio 的 Task 输入、output ref、scheduler signal 和 output envelope 父链；
- ABI 8 安装目录及两个 OperationSpec；
- 新旧资格 Approval 的完整 compiled identity。

现有 12 项测试只证明局部函数和提示/字段形状。尤其
`test_agent_runner_accepts_one_explicit_state_generation` 只检查函数签名存在参数，没有断言两个 daemon
命令实际获得同一个 D4 state root；迁移测试也只使用人工构造的单个 Task，没有覆盖完整迁移报告、
SQLite/CAS 引用闭合、崩溃恢复或当前 provider 对旧 Approval 的真实拒绝。修复 F1/F2 后，必须增加
一个**可丢弃状态副本**上的真实 Root preflight/迁移集成测试；该测试不能触碰真实 D4 目录，也不能
运行 Codex Agent。

由于已存在确定性阻断，本轮没有运行全仓测试、clean-wheel、真实 Worker、浏览器、网络或 solver。
这些检查不能弥补 F1/F2，也不应在修复前消耗真实运行状态。

## 六、重新送审门

只有同时满足以下条件才可重新提交 D4 运行前审查：

1. ABI 8 当前资格 Operation 对原完整 evidence family 产生新的、经本地 UI 决定的精确资格记录；
   旧审批保持原样；
2. runner 冻结并验证新的资格报告，不再把旧 compiled identity 当作当前资格；
3. 状态代际报告和 runner 按 F2 闭合完整引用、旧输出 task ref、表内新 task ref 与不变控制字段；
4. pre-rename staging 恢复边界明确且有负例；
5. 可丢弃状态副本上的真实 ABI 8 Root preflight 通过，并证明旧 identity 负例仍失败关闭；
6. 独立复审明确给出“通过”后，方可迁移真实 D4 状态和启动真实修订 Agent。

本结论不否定 D3，也不要求回退直接完整对象修订。当前问题是 D4 对历史控制状态的代际使用尚未
闭合；正确做法是在最小一次性边界补足新资格和可审计映射，而不是恢复旧补丁协议或放宽核心门禁。
