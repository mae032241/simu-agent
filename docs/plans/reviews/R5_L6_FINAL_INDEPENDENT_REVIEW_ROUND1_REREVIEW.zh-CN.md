# R5-L6 第一轮总审查返修独立复审

日期：2026-09-01  
审查者：未参与返修实现的独立审查者  
结论：**FAIL**  
放行范围：**不放行第二位独立终审**

## 1. 结论摘要

首轮报告的 B1、B2 以及 B3 的文档主体已经实质修复：一个后端值贯穿安装与运行入口；旧中央 Worker
unit 被纳入既有安装事务并可恢复；当前架构、Run 文件协议、TCAD 调试合同、33 项状态和规模口径
已改为 Run v1 的真实表述。Agent collection 暂不可用也已经由同一后端能力结论投影到目录、preflight
和 Codex profile。

但 B3 尚未完整关闭。`PLG-001` 当前被标为 `conformant`，设计宪章和当前架构也声明 Deck 语义属于
TCAD 插件；实际通用核心的生产 Schema 和确定性比较器仍硬编码 `deck_review`、`deck_revision`，并将
任意 reviewed equivalence 的通过理由写成“passing deck review”。这不是文档措辞问题，而是仍会让
新领域为表达审查对象或修订动作修改核心、或者被迫继承 TCAD 语义的真实插件边界缺陷。

因此本轮仍为 **FAIL**。只需关闭这一处通用/领域边界矛盾并做聚焦回归，不需要重开 Task、增加注册表
或扩建运行协议。

## 2. 独立检查范围与证据

本轮检查当前工作树相对 `HEAD` 的未提交整体候选；没有猜测远端基线，也没有修改生产代码或测试。
重点追踪：

```text
SCID_WORKER_BACKEND
→ install preview / rendered systemd
→ control daemon Root runtime
→ Codex Agent 与 Worker MCP profile
→ installation profile validation

旧 Worker unit
→ install transaction snapshot
→ retirement deletion
→ rollback restore

Operation backend capability
→ catalog runtime_binding
→ operation_preflight
→ RunService schedule
→ Codex profile projection
```

所有测试串行执行，虚拟内存上限为 7 GiB，`MALLOC_ARENA_MAX=2`。独立运行结果：

```text
B1/B2、collection、Hardened 与部署聚焦：10 passed in 2.88s
collection 目录/preflight 与 profile 聚焦：2 passed in 0.77s
干净源码发布与领域 wheel 所有权：2 passed in 37.55s
33 项 YAML：33 个唯一编号；7 conformant、25 pending_review、1 known_issue
python -m compileall -q src plugins：通过
bash -n 四个部署脚本：通过
git diff --check：通过
```

另独立组装了与真实服务相同的错配组合：Local Root 创建一个纯 MCP 盲 CSV Run，Hardened Worker 使用
同一数据库尝试打开。`worker_open_assignment` 返回 `WorkerToolError`，Run 被明确置为 `failed`，没有
打开 Local 工作区、产生 Artifact 或静默回退到 Local。该探针只验证失败关闭，不冒充真实 systemd
安装演练。

按照任务要求，没有重跑已有的完整 193 项集合；最新证据中的完整结果由实现方记录，本复审以会命中
返修缺陷的聚焦检查为主。

## 3. 首轮阻断复核

### 3.1 B1：后端部署选择——实质关闭

当前只有一个公开选择值 `local|hardened`：

- `scid init codex --worker-backend` 把值传给平台生成器；
- control daemon 的 `--worker-backend` 把值传给唯一 `build_root_router`；
- `SCID_WORKER_BACKEND` 默认 `local` 且非法值失败关闭；
- 安装预览、systemd 的 `ExecStart`、两处 Codex profile 生成和安装后
  `validate_installation_profile` 均使用同一个 `WORKER_BACKEND`；
- Hardened profile 只生成 Hardened 支持的 Agent；Local/Hardened profile 互相用错误期望验证时被
  `PlatformConflictError` 拒绝。

安装路径没有第二个后端注册表或运行时降级。独立错配探针还证明，即使用户在安装后手工用相反参数
重生成 profile，Worker 也不能打开另一后端的工作区，Run 会失败而不是跨后端消费。

有一个非阻断的证据表述需要修正：总体计划写“实际 daemon/profile 错配由 profile validator
失败关闭”，但 validator 只比较“调用者给定的期望后端”和生成 profile，不读取正在运行的 daemon
事实。安装器因共用同一变量而能防止正常安装错配；安装后人为重生成的错配是在 Worker open 阶段
失败关闭。建议把这两种保证分开写，并把本复审探针固化为一个直接回归；无需增加持久化后端权威。

### 3.2 B2：旧中央 Worker unit 的升级删除与回滚——关闭

`begin_install_transaction` 先以 `unit-scidiscovery-worker` 精确快照旧 unit；
`retire_old_deployment` 在停用服务后调用 `retire_legacy_worker_unit`，后者使用既有
`install_transaction.py remove-target` 校验事务中的精确 name/path 后删除。成功安装不会重新安装该
unit，失败路径的通用 `rollback_install` 会恢复文件、daemon-reload，并按事务前记录恢复 enabled 和
active 状态。

新增测试真实创建一个旧 unit 文件，经安装器实际函数删除，再调用事务 rollback 验证原字节恢复。
这已经超过首轮只有模板/字符串断言的证据强度。未发现第二个迁移账本或专用恢复状态机。

### 3.3 B3：Run v1 文档与证据同步——部分关闭，仍有阻断

已确认下列首轮问题关闭：

- 中英文 `ARCHITECTURE` 均以 R5-L Run v1 为当前真相；
- 设计宪章已用唯一 Run 权威替代 Task；
- 角色结果协议只保留 `worker_open_assignment`、`worker_heartbeat`、
  `worker_submit_result`，并诚实声明 Agent collection 不可用；
- TCAD 合同已删除 Task/attempt/session/token/provisional CAS/reconciler 承诺，改为
  `OperationToolContext` 和 Run 私有 debug 状态；
- 33 项 YAML 可解析且状态总数正确，没有把 25 项 pending 和 `SEC-002 known_issue` 写成全部通过；
- 规模口径可复算：`src/scidiscovery` 为 101 文件/27,268 行，插件为 45 文件/22,763 行，总计
  146 文件/50,031 行，与证据一致。

剩余阻断见第 5 节。

## 4. Agent collection 和唯一权威复核

Agent collection 暂不支持是可接受的 v1 边界，当前实现已经诚实闭合：

- `LocalTrustedBackend.unsupported_requirements` 返回 `agent_collection_outputs`；
- Hardened 由同一方法同时报告 native 和 collection 缺口；
- catalog 的 `runtime_binding.required` 直接使用该后端结果，不再伪报
  `native_tools_disabled`；
- preflight 返回 `runtime_backend_capability_missing`，并且不创建 Run；
- Local/Hardened 的 Codex 生成都排除相应 Agent profile；
- Transform 多输出没有被一并禁用。

`RunService.schedule` 仍在通用 backend 拒绝之后保留一个不可达的 collection 专用拒绝，属于可删除的
防御性重复，不构成第二 admission 权威，也不阻断本阶段。

返修没有恢复 Task、token、中央 Worker daemon/proxy、兼容 invoke 或第二目录。Local 与 Hardened
仍复用一个 `RunService`、一个 compiled catalog 和一个 preflight/invoke；Hardened 只增加文件传输和
每 Run fencing。

## 5. 剩余阻断项

### B3-R1：`PLG-001` 被误标为已符合，通用核心仍包含 TCAD Deck 语义

精确位置和生产消费者：

1. `src/scidiscovery/artifact_agent/schema/research_cycle.py` 的 `ArtifactKind` 包含
   `deck_review`。该闭集定义属于通用科学 readiness Schema；新领域若需要自己的领域审查 kind，
   无法只靠插件扩展。
2. `src/scidiscovery/artifact_agent/schema/validation.py` 的 `RecommendedTaskMode` 包含
   `deck_revision`。它被通用 `LayeredDiagnosisReport` 和知识 Schema 消费；曲线插件也使用
   `LayeredDiagnosisReport`，因此非 TCAD 诊断仍继承 Deck 修订动作。
3. `src/scidiscovery/artifact_agent/schema/comparison.py` 在三个通用 reviewed-equivalence 分支中固定生成
   “The exact passing deck review ...”。该比较器由 TCAD 插件直接导入，但其声明位置和行为属于
   `src/scidiscovery`；任何其他领域复用 reviewed equivalence 都会得到错误的 Deck 来源解释。

这直接冲突于：

- 设计宪章第 4 节“TCAD 插件拥有参数、Deck、求解器和运行适配”；
- 当前架构第 6 节“领域 Schema、validator、角色由插件负责”；
- `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 `PLG-001`：领域 Schema/规则必须由插件提供，核心不得按领域
  Schema、角色或 profile 分派能力。

当前 YAML 却把 `PLG-001` 标为 `conformant`，总体计划和 L6 证据又以“核心无领域名称分支”掩盖了
核心 Schema 与确定性文本仍然领域化的事实。虽然这些残留不是新的运行时路由，但它们会重新制造
“安装新领域仍要修改核心科学枚举”的纵向耦合，属于本轮通用/领域解耦目标的承重缺陷。

最小修复方向：

- 将 reviewed-equivalence 的通用理由改为领域中性 independent review，不在通用比较器命名 Deck；
- 将 `deck_revision` 改为真正领域中性的动作，或把领域行动完全交回 Operation/插件声明；
- 删除、开放或领域中性化 `ArtifactKind.deck_review`，不能为每个新领域继续向核心 Literal 增项；
- 增加一个非 TCAD 插件/诊断回归，证明通用 Schema 和比较结果不出现 Deck/TCAD 词汇；
- 更新 `PLG-001` 证据后再决定是否仍可标为 `conformant`。

不应为此建立新的 Schema 注册表、领域 kind registry 或第二调度表。优先删除未被当前 Run 目录消费的
旧 readiness 枚举；确有消费者的部分使用一个领域中性开放值或已有 Operation id 即可。

## 6. 非阻断事项

1. 建议固化 Local daemon/Hardened profile 和反向组合的直接错配测试。当前实现已失败关闭，缺的是
   防回归证据，不是另一套配置权威。
2. `docs/ARCHITECTURE.md` 的 Agent 段落有一次重复的 “write, write”；不影响合同，可随 B3-R1
   文档更新一并修正。

## 7. 放行决定

**FAIL。** B1、B2、collection 等价性和 B3 的主要文档同步已经通过复核，但 `B3-R1` 未关闭，因此
不放行第二位独立终审，也不宣布 L6 完成。

返修只需收回通用核心中的三个 Deck 语义点并完成相应非 TCAD 聚焦回归。不得借此增加第二注册表、
领域 kind 注册系统、Task 兼容层或新的生命周期状态机。返修后应重跑本报告的部署/collection 聚焦
集以及直接受影响的通用诊断、比较与 TCAD 插件测试，再申请本轮复审。
