# R5-M M7.5 实现正确性与跨边界一致性独立终审

日期：2026-09-03  
审查者：未参与本轮实现的独立代码与跨边界审查者  
结论：**PASS**  
阻断项：**0**  
非阻断项：**3**  
阶段门：**允许 M7.5、M7 与 R5-M 在第二位独立终审者同样明确 PASS 后关闭。**

## 1. 终审结论

当前候选满足 M7.5 在实现正确性与跨边界一致性方面的完成门。没有发现第二个 Operation 目录、第二
个普通 Run 生命周期或第二个 current 权威；Run 输出仍须经过固定工作区、完整输出校验和不可变
Artifact 登记。revision 是新对象，旧审查不能放行新 revision。默认 Local 路径的原生文件能力被
如实限定为可信本地软隔离，没有被文档或测试升级为技术沙箱。

恢复链在 Root preflight 和 `RunService.schedule` 的写事务内复用同一精确规则，并把已有
`max_attempts` 解释为恢复根整棵后代树的总 Run 数。正式 Effect 在提交结果未知时先按冻结描述符向
领域权威查回，只在确认不存在时调用必须幂等的 submit；外部响应丢失与本地登记失败两个窗口都能在
重启后接回同一外部任务。

M7.5 记录的最终 `286 passed` 与当前收集到的 286 项测试一致；本次没有重复这轮重型全量回归，而是
串行执行了 16 个针对权威、恢复、revision、Effect、部署回滚、发行清洁性和 Codex profile 的最小
复验，全部通过。四个 M7.2 持久根的 SQLite 完整性均为 `ok`，Run/Execution 终态与最终机器摘要
相符。首轮全量前由原地 `compileall` 产生 runner 字节码并触发清洁性测试的说明与测试实现一致；
它是可复现的验证顺序污染，不是被掩盖的产品失败。

因此，第一位终审者给出 **PASS、阻断 0**。本结论只完成两位终审中的“实现正确性/跨边界”一半；
只有第二位独立审查者也明确 PASS 后，父任务才可将 M7.5、M7 与 R5-M 写为完成。

## 2. 审查边界

当前分支为 `baseline/8765-codex`，工作树包含 R5 多阶段的已跟踪修改、删除和大量未跟踪实现/证据。
本审查对象是当前完整工作树，不把 `git diff HEAD` 冒充一个干净的 M7.5 单阶段补丁，也没有猜测远端
基线。除本报告外，审查者没有修改生产代码、测试、计划或已有证据。

审查覆盖：

- M7.1—M7.5 的实现证据、首轮失败记录与最终独立复审；
- `CompiledCatalog`、Root preflight/invoke、`RunService`、current、工作区封存和 Artifact 登记；
- revision 的生产者合同、精确 reviewer 和旧 verdict 不继承；
- Local Codex profile 的软隔离提示、实际原生工具投影和领域 Worker MCP 投影；
- 恢复草稿、失败比较交换、恢复身份和整树总次数上限；
- Execution 审批、lookup-before-idempotent-submit、登记和收集；
- clean release、wheel/隔离安装测试夹具、默认服务面与安装事务回滚；
- M7.2 四个当前持久实跑根和 M7.5 全量结果摘要。

没有重新启动真实 Codex、审批 UI、真实 SSH/Sentaurus，也没有重复运行 286 项全量回归。它们分别由
已经冻结的持久实跑、独立阶段终审和 M7.5 最终回归记录承担。

## 3. EvidenceAudit

### 3.1 来源声明

| 键 | 来源 |
|---|---|
| S1 | `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 第 1.1、12、13、15、16 节。 |
| S2 | M7.1—M7.5 五份实现证据；M7.1—M7.4 摘要分别为 `19c736ff...`、`596f0c2d...`、`886379fc...`、`b97d34b9...`，均与 M7.5 引用值一致。 |
| S3 | M7.1 安装矩阵返工复审、M7.2 通用/TCAD v8/Effect/软恢复终审、M7.3 边界复审和 M7.4 返工复审。 |
| S4 | 当前 `operations/catalog.py`、Root operation/execution routes、`service/runs.py`、`run_current.py`、`local_workspace.py`、`artifacts.py`、`executions.py`、`execution_bridge.py`、`platforms/codex.py` 及 TCAD 四段执行适配代码。 |
| S5 | 当前相关自动化测试、`tests/operations/conftest.py`、`scripts/build_git_release.py`、部署脚本和 `deploy/install_transaction.py`。 |
| S6 | 四个持久根：`m7-live-generic-20260902-01`、`m7-live-tcad-receipt-v8-20260902-01`、`m7-live-effect-20260902-01`、`m7-live-run-recovery-soft-20260902-01`。 |
| S7 | 本次只读/低内存命令：证据 SHA-256、286 项 collection、结构计量、SQLite 只读完整性、静态门和 16 项聚焦复验。 |

### 3.2 材料问题检查

| 检查 | 判定 | 证据 |
|---|---|---|
| 是否只有一个启动期编译目录 | pass | S1、S3—S5、S7 |
| Agent 是否只经一个普通 Run 主干登记结果 | pass | S1、S3—S5、S7 |
| current 是否由一个精确 CAS 权威拥有 | pass | S1、S4、S5、S7 |
| revision 是否保持不可变且不继承旧审查 | pass | S1、S3—S5、S7 |
| Local 软隔离是否与实现、提示和声明一致 | pass | S1—S5、S7 |
| 恢复 Agent 是否真实使用草稿与 Schema | pass | S2、S3、S6 |
| 恢复树是否消费 `max_attempts` 且超限零写入 | pass | S2—S7 |
| Effect 未知提交是否只查回、不盲重发 | pass | S2—S7 |
| clean source/wheel/隔离安装是否进入最终套件 | pass | S2、S3、S5、S7 |
| 部署旧表面退出与事务回滚是否有真实测试 | pass | S2、S5、S7 |
| `compileall` 首跑污染说明是否诚实 | pass | S2、S5、S7 |
| 未证生产资格是否被错误扩大 | pass，未扩大 | S1—S3、S6 |

独立总判定：`pass`。当前缺失的真实 SSH/Sentaurus、强隔离、多租户和任意领域科学质量属于已明确
排除的未来资格，不是本轮已实现主张的缺证。

## 4. 跨边界复核结果

### 4.1 单一目录、Run 与 current 权威

生产树中 `CompiledCatalog` 只在 `operations/catalog.py` 内构造；安装入口统一使用
`scidiscovery.plugins`，`public/support/internal/all` 只是同一不可变对象的投影。Local 与 Hardened
虽然分别有 Worker router 和工作区实现，但都重建同一个 `RunService` 类并指向同一状态根、同一
Operation digest 和同一四态表，没有第二种科研完成事实。

Root 对 Agent Operation 的调用先完成同一 preflight，再由 `RunService.schedule` 在
`BEGIN IMMEDIATE` 内重新冻结实例输入和 current anchors。完成提交时，`RunCurrentGuard` 再核对精确
head；head 已变化只把收据记为 `stale_rejected`，不会偷推 current。`scientific_current_select` 的
唯一持久事实是 `scheduler_scientific_selections`，使用 expected ref 做比较交换。聚焦复验覆盖了
输入 current 继承、提交时 head 变化和 Root current CAS。

### 4.2 不可变 revision 与精确新审查

Artifact 注册仍执行 CAS 完整读取、append-only envelope 和完整幂等请求摘要。`create_revision`
建立新的语义绑定和新 Artifact，不覆盖旧字节。生产者输出标签冻结原 Operation id、版本、摘要和
端口；消费者准入用这些冻结字段恢复 reviewer 合同。

直接修订要求恰好一个 `revision_base`，输入/输出 Schema、媒体类型、codec 与 Schema resource 必须
一致，并声明精确 reviewer Operation/端口。不同 reviewer 合同、错误 change request 和用首版
review 放行 revision 均失败关闭；只有绑定新 subject 的新 review 可被消费。本次复验中的精确
revision 正反例全部通过，TCAD v8 持久根也再次显示旧 `revise` 没有成为新项目的 `pass`。

### 4.3 Local 软隔离边界

Local profile 真实启用 Codex file/code/view-image 能力，并让 Agent 在打开后的 Run 工作区内读取
assignment、Schema、显式输入和恢复草稿，也允许写声明的 output 或领域 manifest 标记的可编辑路径。
领域 Worker MCP 仍由同一编译 Operation 投影；Root、兄弟 Worker、原生网络和工作区外访问在提示中
明确禁止。服务端仍固定结果位置，拒绝符号链接、逃逸路径、宿主路径、秘密和未声明二进制。

这些约束不阻止可信 Local 进程在操作系统层越界，代码也没有声称能够阻止。架构、计划、约束表和
M7.5 证据均保持 `SEC-002=known_issue`。因此当前实现与“只控制物化上下文和正式结果边界”的软隔离
决策一致，没有重新增加逐文件读取 MCP、读取收据或第二权限状态机。

### 4.4 失败恢复与次数上限

恢复 preflight 通过 `RunService.validate_resume` 检查 failed+draft、同一 Operation digest 和有序精确
输入；真正 schedule 在冻结输入后的写事务内调用同一 `_validate_resume`。恢复根通过父链追溯，递归
CTE 计算根和所有恢复后代，总数达到现有 `LimitsSpec.max_attempts` 即拒绝。当前自动化覆盖从根或子
Run 发起、重启后发起、preflight 与 invoke 两个入口，均保持 Run 和 binding 不变。

软恢复持久根只有一个 failed 源和一个 completed 恢复 Run，所有数据库完整性为 `ok`。最终机器摘要
显示：草稿独有标记进入封存 signal、只存在于 Schema 的必填常量在首次提交进入 payload、注册领域
工具重新成功、`output_rejected=0`、草稿未成为 Artifact、父项仍是精确原输入。这足以支持当前
“失败 Run 的有界续作”主张。

### 4.5 Effect 未知提交窗口

`ExecutionBridge` 在装配时拒绝没有 `lookup_submission` 的 adapter。`start` 经精确 UI 决定授权并
物化冻结 descriptor 后，固定执行 lookup；只有权威返回不存在才调用按同一 descriptor 幂等的
submit。若 lookup 不可用，副作用发生前失败；若外部响应丢失或本地 `record_submission` 失败，重启
后 lookup 返回同一外部编号并完成登记，提交计数保持 1。相同 external id 的登记可重放，不同 id
仍冲突。

TCAD socket、command、SSH transport 与 Python 3.6 runner 都实现同一查回路径。远端 runner 用摘要
派生稳定运行目录，并在锁内完成检查/创建，因而也覆盖 lookup 与 submit 间的并发竞态。本轮没有
连接真实远端或许可证系统；因此只证明合同、持久接线和故障窗口，不宣称真实长任务失联恢复。

### 4.6 clean install、部署回滚与首跑污染

全量 suite 的 session fixture 先调用发行构建器产生清洁源码，构建核心、四个领域 wheel 和测试插件
wheel，再建立 14 种隔离环境；探针清除 `PYTHONPATH`、关闭 user site，并要求导入路径位于对应 venv。
本次没有重建这组成本较高的环境，但独立读取了真实夹具，并另行复验发行构建器：输出无
`__pycache__`、实验/交付目录或旧中央 Worker 表面，manifest 覆盖全部发行文件。

部署回滚不是字符串断言：聚焦测试真实快照受管 skill/transport/unit，调用安装脚本退出当前不应
存在的 TCAD 或旧中央 Worker 表面，再由同一事务恢复原字节；两项均通过。Shell 语法和默认无中央
Worker unit 也通过。

`compileall` 明确会写入 `.pyc`，即使设置 `PYTHONDONTWRITEBYTECODE=1`。SSH runner 安装测试又明确
要求源码 runner 周边不存在 `remote_runner_py36*.pyc`。因此先原地 compileall、再跑全量时得到一个
清洁前置失败，与 M7.5 的说明一致。删除该次确定生成缓存后，记录的精确项和完整重跑通过；没有靠
改生产或测试代码消除失败。最终候选未遗留该 runner 缓存。

## 5. 独立执行记录

所有测试严格串行，设置 `ulimit -v 4194304`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1`，未执行原地 compileall。

```text
pytest <目录/Run/current/revision/Effect/回滚/profile 的精确节点>
14 passed in 3.72s
MAXRSS 102532 KiB；swap 0

pytest <clean release builder + 默认无中央 Worker unit>
2 passed in 1.67s
MAXRSS 68400 KiB；swap 0

pytest --collect-only -q -p no:cacheprovider
286 tests collected in 0.78s

git diff --check
bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh
AST 解析 7 个关键生产模块
全部通过
```

一次试图附加不存在的 clean-wheel 测试节点的命令在 collection 阶段退出 4，显示 `no tests ran`；
这是审查者节点名选择错误，不是产品/测试失败。随后只运行实际存在的两个轻量发行节点并通过。为
遵守终审任务的资源与范围要求，没有借此触发 session 级全 wheel 重建。

只读持久状态复算结果：

| 根 | 当前终态 | SQLite 完整性 |
|---|---|---|
| 通用作者/审查 | 5 completed、8 历史 failed，无活动 Run | 全部 `ok` |
| TCAD v8 | 4 completed | 全部 `ok` |
| Effect/UI | 1 collected Execution | 全部 `ok` |
| 软恢复 | 1 failed、1 completed，无活动 Run | 全部 `ok` |

当前结构计量仍为 141 个生产 Python 文件、47,177 行、operations 8/2,100，生产树摘要仍是
`d6bfe480ec7b9b724f27c901bce6277da2a2a489dd7823b1f30a7857385078cd`，与 M7.4/M7.5 候选相符。

## 6. 非阻断项与诚实限制

1. **当前状态标题需要在正式关闭时归一。** 活动计划开头以及 M7.2、M7.3、M7.4 证据文件的标题状态
   仍保留各自形成候选时的“暂停/等待复审”文字，文件后续章节和独立报告已经记载最终 PASS。它没有
   改变代码或证据链，但父任务在两位终审都通过后应只更新这些当前状态标题及计划终态，不得改写
   其中保留的历史 FAIL 过程。
2. **强隔离和真实远端资格未完成。** `SEC-002` 必须继续是 `known_issue`；本 PASS 不证明多租户、
   不可信 Worker、真实 SSH/Sentaurus、长任务失联恢复或操作系统级网络/文件隔离。
3. **全量回归的原始终端流没有单独冻结为日志文件。** 当前证据包含精确命令、计数、时间、RSS、
   clean-wheel 夹具和当前候选摘要；本次 collection 与聚焦复验一致，已足够满足本里程碑。后续若把
   同类回归用于发布签署，应把 stdout/stderr、退出码和候选摘要原子保存，避免只依赖人工转录。

这些事项均不要求新增实体、状态机、准入器或当前阶段的生产补丁，也不阻断 R5-M 关闭。

## 7. 最终放行

**PASS；阻断项 0。**

实现正确性与跨边界一致性完成门已经满足。若第二位独立终审者对复杂度、33 项约束和通用科研 Agent
目标同样给出 **PASS、阻断 0**，允许父任务：

1. 将 M7.5、M7 和 R5-M 标记为完成；
2. 更新活动计划和阶段证据的当前状态标题，同时原样保留历史失败审查；
3. 保持 `SEC-002=known_issue` 和其余无直接证据的 `pending_review`，不得因 286 项回归自动晋级。

