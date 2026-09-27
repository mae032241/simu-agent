# 实例归档归属清单：源码基线 P0

日期：2026-09-14。源码基线：`da220ce31c8cc9f9a60542a018b279e2f331f4c0`。
依据：`docs/plans/INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md` R2，第 6 节；指定计划 SHA-256：
`3bb73975c075a81312dc8e2fb651e08be0715cb1d574713faa1cc930f18dc7ad`。

本清单仅据源码建立，未打开运行时数据库、CAS、科研工作区、实际日志或配置密钥；未调用 Root/Worker
工具，未运行测试或构建。本文中的 SQL 是实现定位模板，未对真实状态执行。源码位置均相对仓库根，
行号对应上述基线。当前没有实例归档实现；下文区分现有能力与实施时必须检查的边界。

## 1. 固定根与选择原则

`runtime.py:52–140` 构造以下根。令 `S = runtime.state_root`，`P = runtime.project_root`，
`I = 原 instance_id`，`L = 实际 local_workspace_root`（缺省 `P/.scidiscovery-runs`）。
归档目标按计划固定为 `P/.scidiscovery-archive/instances/I`，不能从浏览器接收任意路径。

| 根 | 当前实际资料 | 归属入口 |
| --- | --- | --- |
| `S/database/scheduler-bindings.sqlite3` | 实例、所有语义版本、current、观察、session | `instance` / `instance_id` |
| `S/database/runs.sqlite3` | Run、输入、输出、receipt、activity、tool evidence、recovery | `runs.instance_id` |
| `S/database/approvals.sqlite3` | 请求、决定、nonce、attempt | 全版本 approval binding，再按 `approval_id` |
| `S/database/executions.sqlite3` | request/payload/decision/result 及 external run | 全版本 execution binding，再按 `execution_id` |
| `S/database/artifact_agent.sqlite3` | envelope、links、idempotency；可能存在旧 events | 精确 Artifact 引用闭包；没有实例列 |
| `S/artifacts/sha256/<前2位>/<后62位>` | 原始 payload 字节；跨 Artifact/实例去重 | envelope 的 `payload_sha256` |
| `L` | `.bindings`、workspaces、recovery、quarantine | Run→binding→随机 workspace 名 |
| `S/hardened-runs` | 同上，加 dispatch / transport-locks | Run→binding；dispatch `run_id` |
| `S/execution-exchange/<execution_id>` | payload、prepared、observation、collection | 精确 execution 行 |
| `S/executor-results` | 已配置 command TCAD 的本地结果、inspection、submission、日志 | external_run_id / 本地 descriptor；部分范围无归属 |
| `S/local-tcad-debug` | local Worker 调试准备目录 | 当前存在持久归属缺口，见第 5 节 |
| `S/engineering-diagnostics` | scoped JSON + 原始 stdout/stderr | JSON `scope`；文件名本身无实例信息 |

两个层次必须分开：**控制记录属于实例**，但其引用的 **Artifact/CAS/恢复目录可能共享**。不能将
“Artifact 没有其他语义绑定”当成“没有其他引用”。`closed` 实例仍是活动侧资料保留者；只排除已有
可靠维护索引证明完成迁移的实例，不以 `state='active'` 代替“所有未归档实例”。

## 2. 五个控制库逐表选择

### 2.1 精确控制集合

实现读取使用原始列、原始 SQLite 类型与 BLOB 字节，不能先通过当前 Pydantic 模型再导出。
旧列缺失、SQL NULL、JSON null、缺省字段和未知旧字段均需保留差别。`run_activity` 没有主键，
还应保存原 `rowid` 及稳定顺序；仅按业务字段去重会吞掉真实重复事件。

以下别名只是模板：`sch`、`run_db`、`apr`、`exe`、`art` 为对应数据库的只读附加名。
查询参数 `:instance_id` 绑定原 `I`。不要使用 latest-only 的 `scientific_inventory` 作为归档根。

```sql
-- 每个 namespace 的全部版本；不按 logical_name 取 MAX(revision)。
SELECT * FROM sch.scheduler_bindings
WHERE instance = :instance_id
ORDER BY namespace, logical_name, revision, name;

-- Run 的直接归属能涵盖“创建成功、语义绑定尚未写入”的窗口。
SELECT * FROM run_db.runs WHERE instance_id = :instance_id ORDER BY created_at, run_id;

-- 单独检查绑定指向不存在或异实例的 Run，不能静默忽略。
SELECT b.*, r.instance_id AS recorded_instance
FROM sch.scheduler_bindings b
LEFT JOIN run_db.runs r ON r.run_id = b.object_id
WHERE b.instance = :instance_id AND b.namespace = 'run'
  AND (r.run_id IS NULL OR r.instance_id <> :instance_id);

SELECT p.* FROM apr.approval_requests p
WHERE p.approval_id IN (
  SELECT object_id FROM sch.scheduler_bindings
  WHERE instance = :instance_id AND namespace = 'approval'
);
SELECT x.* FROM exe.executions x
WHERE x.execution_id IN (
  SELECT object_id FROM sch.scheduler_bindings
  WHERE instance = :instance_id AND namespace = 'execution'
);
```

令 `R` 为直接属于 `I` 的所有 Run，`A` 为精确归属的 approval_id，`E` 为 execution_id，
`F` 为第 3 节闭包后的精确 ArtifactRef 集合。控制对象绑定必须反向检查其他实例；同一实例多个别名
不是多个 owner。`SchedulerBindingService.object_owner_count()` 仅计算直接绑定，不能证明 CAS 独占。
`find_owner()` 在两条绑定时就报歧义，不能代替归档的 `COUNT(DISTINCT instance)` 检查。

| 库 / 表 | 精确选择 | 必须保存的内容 / 源码 |
| --- | --- | --- |
| scheduler / `scheduler_instances` | `instance_id=I` | 原 `active/closed`、时间、name/title/objective；`scheduler_bindings.py:841` |
| scheduler / `scheduler_bindings` | `instance=I`，所有 namespace、name、revision | `object_id`、fingerprint、创建时间与旧列；`:854`；`instance_bindings():678` 已读全版本 |
| scheduler / `scheduler_observations` | `instance=I` | observer_key、object_type、name、state、observed_at；`:869`；这是每观察者/对象的末态，非完整事件流 |
| scheduler / `scheduler_scientific_selections` | `instance=I` | kind/logical_name、原 `artifact_ref_json`（含 NULL）、selected_at；`:882`；current 更新覆盖旧行 |
| scheduler / `scheduler_sessions` | `instance_id=I` | 作为历史保存 session_key、updated_at；恢复不重新绑定；`:904`；`:203` 的 close 会删除，须在关闭前冻结 |
| runs / `runs` | `run_id IN R` | 所有列，不只完成 Run；DDL `runs.py:1634`，追加列 `:1675` |
| runs / `run_activity` | `run_id IN R` | `rowid,*`，activity、recorded_at、diagnostic_json；`:1668`、`:779`；包含工具开始/完成/拒绝、framework_failure、attempt/io 记录 |
| runs / `run_tool_evidence` | `run_id IN R` | run_id/ordinal/evidence_key/record_json/alias；`:1633`；`tool_evidence.py:352–404` |
| approvals / `approval_requests` | `approval_id IN A` | 原 refs、hashes、status、access/CSRF/nonce、截止时间、create_request_json、idempotency_key；`approvals.py:1025` |
| approvals / `approval_decisions` | `approval_id IN A` | decision_id、ref、option、decided_at；`:1045` |
| approvals / `used_nonces` | `approval_id IN A` | 已使用 nonce、decision_ref_json、used_at；`:1054` |
| approvals / `decision_attempts` | `approval_id IN A` | binding_json/sha、ui_session_id、decided_at；`:1061`；不是仅成功决定 |
| executions / `executions` | `execution_id IN E` | request_ref_json/payload_ref_json/decision_ref_json/result_ref_json、executor/state/external_run_id/created_at；`executions.py:670` |
| artifacts / `artifact_envelopes` | 精确四元组属于 `F` | 所有原列与 envelope_json/envelope_sha256；`storage/migrations/0001_artifacts.sql:3` |
| artifacts / `artifact_links` | `source_artifact_id IN F.ids` | 全部 relation（含兼容 `task`）、position、目标精确四元组；同文件 `:17`；目标必须纳入闭包 |
| artifacts / `idempotency_records` | `artifact_id IN F.ids` | 原 request/response BLOB 与各自摘要、key、时间；同文件 `:33` |
| artifacts / 旧 `artifact_events`（存在才选） | `artifact_id IN F.ids` | 全部原列，旧 event_json/event_sha256；`storage/sqlite.py:31–50,645`；当前不创建/写入，但精确旧 v1 schema 可读 |

当前没有独立 `run_inputs`、`run_outputs`、`receipt`、`recovery`、`qualification` 数据表。
它们分别位于 `runs.inputs_json`、`output_ref_json`、`completion_receipt_json`、
`recovery_draft_json/recovery_policy_json`，以及 current、exact review Run、Artifact labels 与 signal
组合中。不要为盘点臆造新表或从展示状态重算原资格。

`runs` 还要原样保留：操作/后端版本和 digest、backend_capabilities_json、instruction、全部输出绑定
身份、request_digest、resume_from_run_id、draft_from_run_id、accepted_candidate_digest、
recovery_candidate_digest、signal_json、reason、所有时间。`RunStatus` 数据类不暴露所有原列，
例如原 `resume_from_run_id`，因此服务层投影不足以用作迁移格式（`run_records.py:78–173`）。

### 2.2 旧表、原 Schema、触发器与导入次序

每库先保存 `PRAGMA user_version`、`sqlite_master` 中 table/index/trigger 定义、
`PRAGMA table_xinfo/table_info`、foreign_key_list、index_list/index_xinfo。这些是当前 Schema 检查所依据的
源码接口（`storage/sqlite.py:659`）。不能初始化一个新库后按现行模型重写旧行：scheduler 的构造函数
会补列/回填并去重 sessions（`:828–965`），Run 构造函数会补列，registry 构造函数会核验完整 schema。

registry 当前接受的 schema 只有迁移原版及含 retired events 的精确旧版（`storage/sqlite.py:470–489`）。
移植到原根时遇到不同 Schema 必须明确报告；不能悄悄丢旧表或转换内容。未知表若无实例归属规则须列为
不支持范围；不能复制其他实例全部行以掩盖缺口。

归档删除记录受到以下已有 append-only 触发器阻止：artifact_envelopes、artifact_links、
idempotency_records、可选 artifact_events；approval_decisions、used_nonces、decision_attempts。
只允许计划第 6 节规定的维护事务定向删除，提交前恢复**原定义**。`runs` 与 scheduler 当前明确使用
DELETE journal（`runs.py:1625`，`scheduler_bindings.py:828`）；其余库没有同样的显式 journal_mode 设置，
不能凭代码推断部署库一定不是 WAL。跨库切换前按计划核验所有参与库，不能替换数据库 inode。

导入按外键与精确 links 排序：实例→绑定/session，所有 envelope→links/idempotency/events，
Run→activity/evidence，approval_requests→decisions/nonces/attempts，execution 行。
恢复共享对象时逐列/字节一致才视为幂等；保留 rowid 的 activity 如与后来记录冲突，要报告身份/排序问题，
不能用 `INSERT OR REPLACE` 覆盖。凭据列为历史保存，不因此激活旧浏览器访问权或 session。

## 3. Artifact / CAS 全历史及共享闭包

### 3.1 根、边和精确校验

ArtifactRef 的完整身份是 `(artifact_id, sha256, kind, schema_id)`（`schema/refs.py:15`）。
SQLite 中对应 `(artifact_id,payload_sha256,kind,schema_id)`。`artifact_id` 可用于找候选 envelope，
**实际引用边必须四项都一致**；`storage/sqlite.py:490–515` 是现有精确查询。

至少从以下记录取根；每项保留其原 JSON Pointer 作为归属证据：

| 根来源 | 要取的 refs / 补充身份 |
| --- | --- |
| 所有版本 `namespace='artifact'` bindings | object_id 对应 envelope 的四元组；绑定本身没有 hash，保留这种来源差别 |
| `scheduler_scientific_selections` | 非 NULL artifact_ref_json；NULL 不用最新版本补齐 |
| `runs` | inputs_json 的 artifact_ref、current_anchors[*].artifact_ref；output_ref_json；completion_receipt_json 内 output/current anchors；recovery_draft_json.input_refs |
| `run_tool_evidence.record_json` | artifact_ref、source_ref 及 metadata 中实际存在的精确 refs；不能只读输出 alias |
| `run_activity.diagnostic_json` / recovery snapshot | ToolAttemptProof/ToolRecoveryProof 的 source binding 精确 refs，含 ancestors；保存原始日志即使当前 schema 无法解析 |
| `approval_requests` | request_ref_json、decision_ref_json、create_request_json 内 subject_refs；审批 CAS 的 manifest ref/subjects |
| `approval_decisions` / `used_nonces` / `decision_attempts` | 各 decision_ref_json、binding_json 中精确 refs |
| `executions` | 四个 `*_ref_json` 字段；ExecutionRequest.payload_ref；ExecutionResultManifest.output_refs |
| 已有可证明生产者的半完成注册 | 属于 `R` 的 `run:<run_id>:candidate:<digest>`、`run:<run_id>:tool:<key>`、`run:<run_id>:tool-manifest:<digest>` idempotency 记录；属于 `E` 的 `execution:<execution_id>:request/output:<name>/result` |
| workspace / recovery 的受控 manifest | `tool-evidence.json`、恢复 proof 中精确 refs；普通文件摘要不是 ArtifactRef，不把任意 64 位字符串当成 CAS 根 |

Run candidate 的注册发生在 completion/scheduler 附加事务之前（`runs.py:1223,1263`）；tool Artifact
注册也先于 run_tool_evidence 的插入（`tool_evidence.py:390–404`）。因此仅按最终 output 或 alias
会漏掉中断窗口里的注册。上述确定格式的 idempotency key 应对精确 Run/执行集合匹配，并校验其
request/response、Artifact identity、候选 digest；不要对任意业务文本做模糊 `LIKE '%run_id%'`。
`tool_producer_run` label 是已有补充索引，仍需验证 producer 属于 `R`。正常 candidate 没有 run_id label。

同样，审批注册 CAS 早于 approval DB 行：已有 `A` 可按精确 `review_manifest_<approval_id>`、
`approval_request_<approval_id>` 和原 idempotency key 找中断注册（`approvals.py:194–244`）；
不能仅根据 subject 被本实例引用就推断一条无 binding 的审批属于该实例。

每加入一个 Artifact：保存其完整 envelope、出向 links、idempotency、payload；沿 `parent`、
`supersedes`、兼容旧 `task` 继续精确解析。示意只读 SQL 如下，`root_refs` 为已校验根的临时关系：

```sql
WITH RECURSIVE reachable(artifact_id,sha256,kind,schema_id) AS (
  SELECT artifact_id,sha256,kind,schema_id FROM root_refs
  UNION
  SELECT l.target_artifact_id,l.target_sha256,l.target_kind,l.target_schema_id
  FROM reachable f
  JOIN art.artifact_envelopes e
    ON (e.artifact_id,e.payload_sha256,e.kind,e.schema_id)
       = (f.artifact_id,f.sha256,f.kind,f.schema_id)
  JOIN art.artifact_links l ON l.source_artifact_id=e.artifact_id
)
SELECT f.*, e.size_bytes, e.envelope_json, e.envelope_sha256
FROM reachable f LEFT JOIN art.artifact_envelopes e
  ON (e.artifact_id,e.payload_sha256,e.kind,e.schema_id)
     = (f.artifact_id,f.sha256,f.kind,f.schema_id);
```

此 SQL **只完成 registry links 闭包**，不能独立证明全部引用已覆盖。当前 registry 写 links 只覆盖
parent/supersedes，不索引 payload 的嵌套 refs（`storage/sqlite.py:575–611`）。
现有 `audit.py:354` 同样只检查 envelope 引用；`referenced_digests()` / orphan scan 仅知道 registry
payload 摘要，不是实例共享判定器。`portable_bundle.py` 是身份中立的选定成果导出，包含 omitted refs
及重新注册语义，不适用于原身份、全历史归档。

嵌套精确 refs 至少覆盖 `ApprovalRequest.subject_refs/review_manifest_ref`、
`ReviewManifest.subjects[*].artifact_ref`、`HumanDecision.approval_request_ref/subject_refs/previous_decision_ref`、
`ExecutionRequest.payload_ref`、`ExecutionResultManifest.output_refs`、
TCAD `ResolvedProjectInput.artifact_ref`（`project_packager.py:87`）、tool manifest
records/bindings/recovery/ancestors（`tool_evidence.py:20–71`）。应对可解码 JSON 的完整字典/数组
遍历精确四元组，并与 registry 四项校验；找不到、损坏、未知编码不能跳过后声称闭包完整。
不是四元组的逻辑 alias / 文献 source_key / 普通 sha256 只保留原载体，不能猜新 Artifact 身份。

数据量或未知 schema 使嵌套遍历无法证明完备时，保留活跃侧相关 bytes，记录不支持/缺失范围。
保留源文件自身不依赖当前科学模型验证通过。CAS `content_encoding` 允许 identity/gzip/zstd
（`schema/artifact.py:30`），实际解码范围须明确；不能把不能解码的 payload 当作“无子引用”。

### 3.2 共享判断和可释放字节

对每个其他未归档实例重复建立同样闭包，包括 closed 实例、失败 Run、历史 approvals/executions、
恢复根及嵌套引用。还要保留无实例归属的 registry/执行/恢复根所需内容；它们不因没有 binding 就成为
可删除孤儿。出向引用决定目标依赖；别的实例的入向 link/ref 决定目标仍被需要，不将入向生产者
自动纳入目标实例的“拥有记录”。

| 对象 | 归档包 | 活动侧可移除条件 |
| --- | --- | --- |
| 实例专属 scheduler / Run / approval / execution 行 | 原始记录 | 精确归属、无其他控制 owner、相关 writer 已停、事务切换成功 |
| Artifact 四元组 | 完整 envelope/links/idempotency/旧events 与 payload | 不在其他保留根闭包中；不存在留下的精确入向引用 |
| CAS digest | 包内完整原字节副本；一个 digest 只需一份 | 该 digest 的**所有**仍需保留 Artifact identity 均已排除，且不被其他已知根引用 |
| recovery digest | 完整目录、原权限与 manifest | 所有 backend 同根的其他 Run 均不引用该 digest；不能只按本实例所见 Run 计数 |
| control lock / lease | 历史元数据 | 不复制活跃持锁状态；恢复重获新锁，不回放 owner/PID/FD |

最终 SQL 可用两个已形成的精确关系 `target_refs`、`retained_refs` 做差集；CAS 再按 digest 去重，
不能只按 artifact_id 做字节释放统计：

```sql
SELECT DISTINCT t.sha256
FROM target_refs t
WHERE NOT EXISTS (SELECT 1 FROM retained_refs k WHERE k.sha256=t.sha256);

-- 对保留 registry 行作第二道核查；exclusive_artifact_ids 是精确闭包差集结果。
SELECT DISTINCT e.payload_sha256 FROM art.artifact_envelopes e
WHERE e.artifact_id NOT IN (SELECT artifact_id FROM exclusive_artifact_ids);
```

包内字节量、活动侧实际独占释放量、共享保留量、缺失字节量分别报告。`ContentAddressedStore.put()`
先发布 CAS 再注册（`artifacts.py:83`），崩溃留下的无 registry CAS 不能从内容或 mtime 推断实例。
`cas.py:139` 的路径映射可直接复用；临时 `.digest.*`、异常路径要单列，不默认清理。

## 4. Local / hardened 工作区及恢复现场

`LocalTrustedBackend` 的创建与定位见 `local_workspace.py:124–175,438–455`。
精确映射为 `sha256(run_id.encode('ascii')).hexdigest()`→`L/.bindings/<digest>` 的 ASCII 内容，
内容必须匹配 `workspace_[0-9a-f]{32}`。不是 hash 反推 UUID；也不是遍历目录后匹配科研文字。

| 资料 | 精确选择与范围 | 写入者 / 特别边界 |
| --- | --- | --- |
| `.bindings/<hash(run_id)>` | 每个 `R` 的映射原文件 | `prepare()` 最后写；保留映射即使对应现场已被隔离/删除 |
| `workspaces/<workspace_name>` | 整棵树：inputs/schema/assignment/output/candidates、domain-workspace、deck、scratch、reports、tools、`.operation-tools`、recovery-draft 等 | `LocalTrustedBackend`、RunService 的 workspace hooks、Worker 原生工具和子进程、插件工具都可写 |
| `quarantine/<workspace_name>` | 同一 binding 精确定位，保存所有残留 | `discard():339` 用 rename 隔离；两处同时存在需诊断，不能随意丢一份 |
| `recovery/<digest>` | `recovery_draft_json.draft_digest`；还有 recovery_candidate_digest/complete_snapshot_digest 指向候选/隔离进度，逐个核对存在位置 | `discard():368` 从候选复制；目录按内容去重，没有 instance 子目录 |
| `workspaces/.../candidates/<digest>` | 归入整棵 Run 现场；accepted/recovery candidate 需核验 | `seal():241`；原候选可能在 quarantine，不能仅取 recovery 根 |
| `recovery/.staging_<digest>_<uuid>` | 可据已知 exact digest 识别候选 staging，但仍核对 writer/根/manifest；有歧义保留 | `discard():373–384` 的中断现场；`finally` 正常清理不保证崩溃时不存在 |
| `scratch/.analysis-process` | `<uuid>.json`、latest.json、stdout/stderr `.raw/.log`、stop、lock、临时文件均随 Run 保存 | 原生 launcher `local_process_observation.py:145,219–328`；没有全历史服务 DB 映射 |

`recovery_draft_json` 保存 source_run_id/source_request_digest/operation_digest/input_refs/backend/
backend_version/draft_digest/files；`recovery_pending`、`original_retained` 和
`complete_snapshot_digest` 表示不同保存范围（`runs.py:638–739`）。
**draft_available 不等于旧目录可移走**。`retain_original_on_failure` 会请求 launcher stop，但保留 cwd，
随后可同时交付不可变子集与 `writers_unconfirmed`；不能调用 failure/recovery 函数作为“只读盘点”，
这些函数会封存、写 DB、rename/delete。

恢复共享图还应沿 `resume_from_run_id` / `draft_from_run_id` 定位前序 Run；同根目录下所有 Run 的
draft/candidate/complete snapshot、workspace/recovery-draft 引用都纳入保留判定。不存在的 queued
workspace、已经正常清理的 quarantine、应有但损坏的 .bindings 是不同类别，不统一算成“空目录”。
正常 `discard` 已删除的非保留原现场无法通过归档重建，应如实记录原有历史缺失。

Hardened 继承同一存储结构，但根固定 `S/hardened-runs`（`runtime.py:81`），并新增：

| 资料 | 精确选择 | 占用与恢复 |
| --- | --- | --- |
| `dispatch.sqlite3.active_transport` | `SELECT * FROM active_transport WHERE run_id IN R` | run_id/owner_id/lease_deadline_at；`hardened_workspace.py:45`；原始历史保存，不重插成有效租约 |
| `transport-locks/<sha256(run_id UTF-8)>.lock` | 按精确 `R` 派生路径 | `claim_transport/transport_guard/release_transport` 持该 Run `flock LOCK_EX`；`:107–194` |
| 正在上传的文件 | `HardenedFileEditor._upload` 只是内存 bytearray，commit 后才写 workspace | `hardened_files.py:32–81`；无可归档的持久 chunk 库；不能把未提交内存声称已保存 |

Hardened 单次工具执行期间持续持有 Run transport lock，SQLite writer 锁在工具执行前已释放
（`hardened_workspace.py:137–171`；`mcp_hardened_worker.py:67`）。未过期 lease / 正持锁均是占用，
不能只看 Run state；deadline 过期不是正在运行调用结束的证据。

## 5. 执行、TCAD 本地资料与不能可靠归属的范围

### 5.1 通用 execution exchange / collection

每个 `E` 包含整个 `S/execution-exchange/<execution_id>`。创建/授权时的 payload.bin 由
`ExecutionService.authorize():333–416` 写；TCAD prepare 在 `prepared/pkg_<package_sha256>/`
写 job.json/project.tar，可能留下 `.package-*`（`project_packager.py:1101–1150`）。
`ExecutionBridge.start():79` 的 prepare→lookup/submit→record_submission 分离，可能出现外部已提交而
DB 未记录 external_run_id；只有现有精确 submission lookup 能解决，归档不能重提求解或靠文件名猜。

| exchange 相对位置 | 实际内容与写入者 | 选择/占用 |
| --- | --- | --- |
| `payload.bin`, `prepared/` | execution authorize、配置 adapter/package builder | 随精确 execution 整体保存，原始路径保持 |
| `observation.json` | `ExecutionBridge.sync()`→`save_observation()`；`executions.py:573–587` | 保存 observed_at/solver_state/progress/error；无每次状态事件日志 |
| `collection/request.json` | `ExecutionCollection.collect():311` | execution_id、scope、state_root、plugin config 路径、actor、budget、parent_fd、work_command；历史，不恢复成后台请求 |
| `collection/status.json/progress.json/stop.json` | coordinator、watcher、guard、child 都有写入点 | `execution_collection.py:294–438,483–584`；单看 status 终态不够 |
| `collection/outputs.json` | child 在 adapter 收集结束、registry ingest 前封存 LocalFileDescriptor 列表 | `:561–577`；精确 local_path/sha256/size 为恢复收集与文件归属根；外部路径须核对配置可管理根 |
| `collection/attempt-<time_ns>.json/.stdout.log/.stderr.log` | 每次新 collect 保存上一状态/进程日志；`:302–308` | 全部尝试，不只 status 最新一次 |
| `collection/process.stdout.log/process.stderr.log` | watcher finally，最多每流 256 KiB；`:426–439` | guard 结束后仍可能补写，不能先移走目录 |
| `collection/active.lock` | 每 execution 非阻塞排他 flock | coordinator/guard 继承 FD 保持到真正退出；`:282,318,509` |
| `S/collection.lock` | 全运行时唯一 collection slot | 共享系统控制，不属于单个实例迁移；归档需观察但不能搬走 |

`ExecutionCollection.summary():230` 能用 active.lock 观察中断，但锁空闲不能反推出所有未知外部
求解器已退出。原通用 instance_close 只允许 execution `collected/abandoned`
（`mcp_root_instance_routes.py:37`）；失败/成功终态但未收集仍是未收集资料。
归档不补造本来未收集的输出；先沿已有 collect/recovery 路径处理或明确历史缺失。

### 5.2 TCAD command adapter

`runtime_plugin.py:69–100` 只在 command 配置下传 `S/executor-results`，socket 下由独立 TCAD
daemon 返回本地 descriptors。命令配置还可指定环境；SSH transport 实际根取
`SCIDISCOVERY_TCAD_RESULT_ROOT`（缺省 `/var/lib/scidiscovery/transport-results`），
见 `ssh_transport.py:628–650`。归档实现须从**当前受控运行配置**证明实际根与预期一致；本盘点未读
部署配置，不能声称所有部署都在 `S/executor-results`。

| TCAD 路径 / 数据 | 可证明的归属 | 写入与缺口 |
| --- | --- | --- |
| `executor-results/runs/<external_run_id>/` | `E` 的 external_run_id；以及拥有可靠持久 Run 关联的 development run | `ssh_transport._collect():436`；正式输出与 `.download` 同目录；完整保存已收集本地 bytes |
| `executor-results/inspection/<external_run_id>/<sha256>` | 精确 execution external_run_id / tool execution scope | `_inspect_outputs():410`；可能有 TemporaryDirectory 的中断目录；不能只取已被注册的 inspection 文件 |
| `executor-results/submissions/<sha256(local job bytes)>.json` | 根据目标 exchange 下原 job 文件字节计算 digest，再校验 marker 内 remote_submission descriptor | `_prepare():359–396`；仅 marker 内容没有 instance_id；不同对象共享时保留活动原件；缺原 job 时不能重打包新 job 冒充原件 |
| `executor-results/logs/<sha256(raw)>.<stdout|stderr>.log` | 存在被目标 scoped 原始诊断/受控 descriptor 明确引用时可列为候选；无引用不能认定独占 | `transport_logs.preserve_log():8`；command `_call():256`、SSHRemoteClient 均写；成功调用 stderr 也可落盘，没有持久 instance/execution 索引 |
| `local-tcad-debug/<random_uuid>/<run_name>/` | 当前无稳定持久 Run→exchange 映射 | `local_debug_service._start():149–197` 随机生成，返回值不含 exchange；见下段 |
| workspace `.operation-tools/tcad/<run_name>/`、`deck/reports/` | 已有 Run→workspace 映射 | debug `_finish():199–295` 已落盘文件随 Run 迁移；可归属这些文件不等于能归属其原 exchange |

**现有 local debug 是具体实施缺口**：`LocalWorkerMCPRouter._tool_state` 是进程内 dict
（`mcp_local_worker.py:79,437`），`LocalTCADDebugService.run():95` 将 external_run_id/state/source
摘要写入该 dict；没有控制 DB 或本地原子 state 文件。`_start()` 的 UUID exchange 路径甚至不在返回
record 中。一个 debug submit 后 Worker 重启，可留下未归属 exchange 和外部 run。不能按同名 run_name、
project 摘要、mtime 或“只有一个实例”推断归属。首版若此类资料存在且无法证明，应在预览明确未支持
范围/阻止声称完整迁移；需要的维护登记属于后续实施，不要求科学 Agent 补填归属。

Tool output inspection 使用原 execution_result 的精确 execution scope
（`mcp_local_worker.py:421`→`ExecutionService.resolve_result_scope():92`），可追溯 formal execution。
debug collection 自己启动有界子进程（`debug_collection.py:20–94`），没有通用 collection active.lock；
它及命令传输 writer 必须按独立入口隔离，不能依赖正式执行已终态。

### 5.3 Socket daemon / 远端边界

`TCADExecutionFacade` 有独立 `state_root/submissions.sqlite3` 与 `state_root/runs/<external_run_id>`，
`execution_control.py:406–413,808`：表 `submissions(job_sha256 PK,run_id UNIQUE,submitted_at,lifecycle_state)`。
独立根来自 daemon 参数，不是 runtime_plugin 的 socket 配置暴露出来的目录。只有部署确认这是当前
纳管**本地**根且精确 external_run_id 属于目标，才能按 run_id 查询 submissions 与该 run 目录；
不能把任意 daemon 根当成 `S` 子目录。运行目录由 facade、`tcad_artifact/worker.py` 和 solver 写，
不是通用 maintenance lock 的自动参与者。

SSH 的 `remote_exchange_root/transport/<job_digest>`、远端 submissions/runs、求解器临时文件
不在首版迁移范围。保存本地 marker/descriptor 与未收集说明；不访问/修改远端状态、不将远端字节
计入已迁移量。socket 返回的 LocalFileDescriptor 也不等于授权移动 daemon 文件，须先证明本地归属根。

## 6. Engineering diagnostics

`EngineeringDiagnostics.capture()` 创建 `diag_<uuid>.json`，先写可能存在的同名前缀 `.stdout` /
`.stderr`，再写 JSON。JSON 原字段为 scope、created_at、public、traceback、sections、
public_traceback（`engineering_diagnostics.py:103–134`）；公开 read 做脱敏投影，不能用投影替代归档原件。
按完整 manifest 保存原权限和 bytes，不将 raw traceback/凭据列直接渲染到浏览器。

| scope / 引用情况 | 归属规则 |
| --- | --- |
| `instance:<I>` | 直接属于目标实例；收齐 JSON 及 sections 声明的 stdout/stderr；无 DB 索引，需有界逐个读取 JSON 元数据 |
| exact execution scope | 当前正式 collect/sync 传的也是 `instance:<I>`（Root execution routes `:473,526`），**没有既成 `execution:<id>` 写入约定**；execution 内 observation/collection 的 reference 可用于精确关联与核验 |
| `worker:unbound` | 原样留系统侧并单列。worker timing 记录失败也会用此 scope，即使曾有 Run；不能根据临近时间追认 |
| `session:<key>` / `session:unbound` | 只证明 session，不能从当前 scheduler_sessions 绑定推断历史实例；session 可以后来换绑。需已有精确实例载体引用才可记录有关联副本，不能推断独占 |
| stdout/stderr 已落盘而 JSON 缺失、坏 JSON、未知 scope | capture 中断/坏记录；不能从 UUID 猜实例；保留并列出无归属范围 |
| workspace `reports/diag_<uuid>.json` | 随 Run 保存，是公开 section 的副本；不意味着系统原件所有字节都已包含 |

生产者包括 Root router 异常（`mcp_root.py:472`）、Run open/checker/materializer（`runs.py:502,552,1107`）、
Worker `_engineering_failure()` / timing finally（`mcp_local_worker.py:158–186`）、execution sync、
collection coordinator/watcher/guard/child。capture 无内部跨进程锁；atomic_json 只保证单文件替换，
不保证 stdout/stderr/JSON 三件套在一次事务中。归档冻结后仍需覆盖所有写入入口及后置 finally。

## 7. 现有写入入口与占用锁：P5 接线依据

| 真实 writer / 入口 | 当前写入范围 | 当前锁 / 归档必须看到的缺口 |
| --- | --- | --- |
| 控制 daemon `SessionRouterPool.handle()` | Root 调用中的 scheduler/Run/Artifact/approval/execution 与诊断 | `mcp_daemon.py:51–78`：一般 `S/maintenance.lock LOCK_SH`，instance_close `LOCK_EX|NB`；进程内 router lock 不是跨进程隔离 |
| runtime 初始化 / CLI 受控命令 | 建目录、建表/补列，部分 ingest/audit/导入 | `runtime.py:67`、`interfaces/cli.py:130,166–209` 持 maintenance shared；读取构造器可能写 schema，归档只读清单不能误调用 |
| Approval UI 请求处理 | 创建/选择实例、refresh access、record decision、相关 CAS | `approval_ui/app.py:_shared_maintenance():476`；HTTP 持锁范围须逐路由缩短，不能把网络发送或 SSE 等待留在锁内 |
| `ArtifactService.register()` | CAS、registry | `S/database/artifact_agent.sqlite3.mutation.lock LOCK_EX`，`artifacts.py:162–184`；只串行化注册，不是实例 maintenance gate；CAS 临时与 registry 之间有窗口 |
| `SchedulerBindingService` / `RunService` | 五库中的各自控制记录、workspace、candidate/recovery、hooks、tool evidence | 各自 SQLite 事务；Run 完成 ATTACH scheduler crash-atomic commit；服务本身没有通用 maintenance 锁装饰 |
| local Worker `call_tool()` | Run/activity、workspace、工具证据、CAS、诊断与插件写入 | `mcp_local_worker.py:93` 仅 `threading.RLock`；现行工具调用不持 S/maintenance 共享锁；P5 不能只拦 Root |
| local Worker 原生 shell / 子进程 | workspace 内脚本、scratch、deck、stdout/stderr；可能跨 tool call 生命周期 | `scratch/.analysis-process/lock LOCK_EX|NB` 只覆盖受控 launcher；`request_stop()` 只尽力等待 1 秒且吞观察错误；无 telemetry 不证明无 writer |
| hardened Worker | dispatch/lease、workspace 文件/提交、诊断 | Run 级 transport flock + DB 事务；还需统一实例 maintenance gate，现有 transport 锁本身不检查 instance closed/archiving |
| 正式 execution prepare/start/sync/cancel | exchange、plugin results、execution DB、远端调用 | 经 Root 时在全局 shared 内；adapter 自己无实例维护门；正式 external_run_id 尚未记录窗口必须有恢复事实 |
| collection coordinator `collect()` / watcher | request/status/attempt/process log、诊断 | 进程内 RLock；每execution active.lock + 全局 collection.lock；watcher 活过 Root 调用并有 finally 写入 |
| collection `_guard()` | stop.json、诊断；持继承 locks | 自身不持 maintenance shared；FD 保持到实际工作组结束；仅停止 child 不够 |
| collection `_child()` | plugin collect、本地传输、outputs checkpoint、CAS/registry/execution ingest | `execution_collection.py:558` 持 maintenance shared；except 中诊断/status 在该 with 之外 |
| TCAD command / SSH subprocess | executor-results 的 download/inspection/submission/logs | `run_bounded()` 过程组与预算，不持独立实例锁；parent writer/collector 结束前不可迁移 |
| TCAD development debug / `debug_collection` | 随机 debug exchange、remote submit、executor-results、workspace reports | 仅 Worker 进程内 tool state 与外部 run；通用正式执行表/collection slot 看不到，见第 5 节 |
| socket TCAD facade / local solver worker | 独立 daemon submissions DB、runs/work/日志/状态/输出 | 独立 SQLite 事务、进程生命周期；没有 runtime S/maintenance 锁，未明确根与写入隔离时不支持在线移动 |
| EngineeringDiagnostics 独立 capture | JSON、stdout、stderr、临时文件 | 无实例锁；Root/Worker/collection error/finally 路径需统一门或确定已结束 |

`StateMaintenanceLock` 的机制是 `fcntl.flock`，正常 shared、维护 exclusive，路径本身是稳定全局
协调点（`maintenance.py:22–60`），不能随单实例目录移动。SQLite journal、WAL/SHM（若存在）、mutation
lock、collection slot 等也不是某实例独占文件；数据库采用定向记录迁移，不移动整个共享 DB。

现有普通 close 仅阻止 bound active Run、pending approval、未 collected/abandoned execution，
并不覆盖 `.bindings` / recovery_pending / native cwd / debug 外部 run / collection watcher。
因此 close 成功不构成归档无 writer 的证明。计划 B1 的 gate 需要覆盖表中全部持久 writer；已有数据的
无归属/未知 writer 必须先报告具体范围，不能把 Run fail 或 deadline 到期当作物理进程已停。

## 8. 可直接用于 P0/P5 验收的结论

1. 五库所有表的确定归属如第 2 节；全版本绑定、Run 原始行、每次 activity、审批 nonce/attempt、
   旧 artifact_events 与原 Schema 都在范围。current/资格保留原记录，不以现行 catalog 重新判断。
2. 精确 refs 是四元组；links 闭包不足以覆盖嵌套 JSON、tool/recovery、半完成注册。共享判断须包括
   所有未归档实例与无归属保留根，CAS 按 digest 再去重，不能拿 registry orphan scan 替代。
3. local/hardened 工作区归属需要 .bindings；恢复按原根、原 backend、原映射和权限。共享 recovery、
   quarantine、保留原 cwd、partial draft/pending 标志不能遗漏；PID/lease/FD 仅作历史。
4. 正式 execution exchange 可直接按 execution_id，command TCAD results 可按可信 external_run_id /
   descriptor；`local-tcad-debug`、无索引 transport logs、无 JSON diagnostics、无 registry CAS、
   未绑定审批/执行、未知根/后端/编码均不能从当前源码可靠证明实例独占。
5. 当前 maintenance shared 未覆盖 local/hardened Worker 工具、原生 writer、collection 后置写入和
   TCAD debug/独立 daemon。上线迁移前必须接入计划中的维护门或明确该范围未支持。
6. 原输入 Git/用户手工文件只迁移已经纳管的 CAS 副本；`source_path` 是来源标签，不授权搬走原文件。
   服务程序、部署配置/密钥、远端 VM 文件不属于本次实例迁移。原本不存在的历史字节保持缺失清单。

本清单没有创造新的科研框架、状态或 Agent 任务；它给出的空缺是当前源码的存储归属/写入隔离空缺。
P5 的具体实现及验证应逐项消费本表，不能将本文当作任何真实实例已经可安全归档的结论。
