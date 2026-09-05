# FAIL — R5-M1 实现独立审查

日期：2026-09-01

结论：**FAIL。M1 尚未通过，不放行 M2；M2—M7 均未完成。**

本审查绑定到分支 `baseline/8765-codex`、`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`
和审查时完整工作树。审查者未参与 M1 实现；除本报告外未修改生产代码、测试、计划或其他文档，
也未运行实时外部 Agent。

## 1. 阻断项

### B-1：已有 v1 Artifact 库因惰性 `artifact_events` 表而无法重启

- **位置**：`src/scidiscovery/artifact_agent/storage/sqlite.py:24,389-415,444-456,625-683`；
  `src/scidiscovery/artifact_agent/storage/migrations/0001_artifacts.sql:1-77`；计划
  `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md:174-180`。
- **缺陷**：M1 从新建库 migration 删除了 `artifact_events`，但 `REGISTRY_SCHEMA_VERSION` 仍为 `1`，
  `_verify_schema()` 又要求数据库的完整 `sqlite_master`/表合同与新 migration **精确相等**。因此由 M1
  之前同一 v1 合同创建、按计划保留旧事件表及其触发器的数据库，不会被“惰性忽略”，而是在
  `SQLiteArtifactRegistry` 初始化阶段抛出 `RegistryConfigurationError`。
- **可达场景与影响**：任何保留 M0/L 运行状态目录的安装在 M1 后重启都会先于 Artifact 读取、审计、
  current、Run、审批和执行恢复而失败。新建库和 clean-wheel 测试全绿不能覆盖该升级路径。这直接违反
  “只有新建数据库不再创建废弃表；已有数据库额外表不参与运行，不增加在线删表迁移状态”，也使
  MIG-002 的重启/发布代际门不能通过。
- **独立复现**：

  ```bash
  probe_dir=$(mktemp -d /tmp/r5-m1-old-registry.XXXXXX)
  git show HEAD:src/scidiscovery/artifact_agent/storage/migrations/0001_artifacts.sql \
    | sqlite3 "$probe_dir/artifacts.sqlite3"
  PYTHONPATH=src python -c \
    'import sys; from scidiscovery.artifact_agent.storage.sqlite import SQLiteArtifactRegistry; SQLiteArtifactRegistry(sys.argv[1])' \
    "$probe_dir/artifacts.sqlite3"
  ```

  实际结果：`RegistryConfigurationError: artifact registry schema differs from migration contract`。历史
  migration 与当前 migration 的相关结构差异正是 `artifact_events` 表及两个只追加触发器；两者的
  `user_version` 都是 `1`。
- **测试缺口**：`tests/artifact_agent/test_artifact_audit.py:11-15` 每次只创建当前新库；全测试树已经
  没有 `artifact_events`/`approval_events` 夹具，因此 `205 passed` 没有验证计划要求的旧库惰性兼容。
- **最小返工范围**：只调整 Artifact registry 的结构校验，使当前三张权威表、索引、外键和只追加
  触发器继续精确失败关闭，同时只允许已知旧 `artifact_events` 表及其既有触发器作为惰性额外对象；
  不读取、不写入、不删除该表，不恢复 `ArtifactEvent` 类型，不增加在线 migration、兼容服务或第二
  schema 权威。增加一个由 M1 前 v1 migration 构造的回归：旧库可重启、旧 Artifact 可读/可审计、新
  Artifact 可登记、旧事件行保持原样、未知额外表或当前权威表漂移仍被拒绝。修复后重跑 M1 聚焦集合、
  全量串行测试、clean-wheel 和 `git diff --check`，再接受新的独立 M1 审查。

## 2. M1-01—M1-05 独立核查

| 候选 | 当前实现与证据 | 判定 |
|---|---|---|
| M1-01 死 Schema/周期状态 | 四个 Schema 文件和三种伪周期状态均从生产源码消失；领域中性测试改验有真实消费者的开放标识，没有替代科学状态或固定阶段 | 通过 |
| M1-02 僵尸 web/analysis 工具 | `worker_fetch_web_evidence`、`worker_run_analysis`、组件常量和 `web_fetch.py` 在生产零命中；I-2 的无效 fixture 导入已删除，网络负例改用测试插件私有 `NETWORK_TOOL`；领域曲线分析工具仍由曲线插件显式拥有，不是核心兼容别名 | 通过 |
| M1-03 第二运行投影 | `RuntimeOperationProjection`、两个 runtime projection 函数和导出均消失；`CompiledCatalog.__slots__` 没有替代运行投影，Root 仅把同一目录投成 `SchedulerOperationView`，运行仍消费 `CompiledOperation` | 通过 |
| M1-04 在线清除 | 四个删除接口、临时拆除/恢复只追加触发器辅助和相关数据库 DELETE 路径均消失；未新增离线清理器或转发层。Hardened 的 Run 文件删除是既有有界输出生命周期，不是事实库清除 | 通过 |
| M1-05 事件与 audit | 新建 Artifact/Approval 库不再创建或写两个事件表；audit 已去除事件依赖，并对 CAS、Envelope、精确父引用/`artifact_links`、幂等绑定和孤儿报告保持失败关闭测试；但已有 Artifact 库被 B-1 拒绝，故本候选整体失败 | **失败** |

I-1 的“先保 audit 再删事件”在最终代码中已经落实：新增五项审计测试分别覆盖正常链、缺失 CAS 与
孤儿、Envelope 列损坏、父链接位置损坏和幂等哈希损坏。I-2 已按要求把网络负例归入测试夹具且没有
生产别名。I-3 的账本现统一写明 19 个候选；M1 实现没有借计数歧义扩大到 M2—M6。

## 3. 净复杂度、目录和承重不变量

独立复算与 M1 证据一致：生产 Python 从 M0 的 146 文件/50,023 行降为 141 文件/48,844 行，当前
摘要为 `ee4a91f4ebdc87d56471081a67ce3d2f8e9e956119fa743247a711790062dea4`；Root 工具仍为 30，
Run 仍只有 queued/running/completed/failed 四态，没有新增 Registry、运行状态、表、守护进程、
preflight/invoke、兼容 adapter 或领域实体。

五个生产插件仍编译为 220 个组件、46 个 Operation（public 26/support 20；Agent 22/Transform 20/
Approval 3/Effect 1），目录摘要仍为
`4c17c856ba4249d400d8d1455139b2e39588759e16ee1c31e5122b4e97dbb57e`。这支持 M1-01—04 的真实
物理删除结论：没有用第二目录、替代投影或兼容层换取表面减量。

全量回归覆盖了 Artifact/current、Run、精确审批 subject、防重放、Execution/Effect、插件安装目录、
Local/Hardened、最小 Worker 上下文和 TCAD 本地闭环，未发现这些承重边界因 M1 退化。审计源码与
损坏负例也证明 CAS、Envelope、父链、幂等和孤儿检测仍在；本次 FAIL 仅由旧库启动路径的独立缺陷
触发，不否定这些已通过项。

## 4. 33 项约束与奥卡姆判断

逐组核查计划引用的 33 项约束：AUTH-001—003、IMM-001—002、LIN-001—002、EVD-001—002、
UNC-001—002、TOP-001—002、ROLE-001—002、DET-001—002、HIL-001—002、CQRS-001—002、
EFF-001—002、PLG-001—002、SEC-001—002、RES-001—002、UI-001—002、MIG-001—002。M1 没有把
既有 `pending_review`/`known_issue` 自动晋级，也未改写 `SEC-002 known_issue`。删除在线清除和重复
日志总体上强化 IMM/CQRS/AUTH，目录不漂移且无新实体，符合奥卡姆和通用 AI 科学家目标；但 B-1
使旧状态目录无法重启，故 M1 的明确迁移门和 MIG-002 尚未满足，不能以净删行或测试数量覆盖。

## 5. 独立执行结果

所有 pytest 串行执行，设置 `ulimit -v 7340032`（7 GiB）与 `MALLOC_ARENA_MAX=2`：

```text
python -m pytest -q
205 passed in 64.02s
```

以下检查也通过：

```text
git diff --check
bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh
```

未运行真实浏览器、远程 SSH/VM、Sentaurus solver 或实时外部 Agent；它们不是 M1 删除面的必要门，
本报告也不把工程回归提升为科学准确率或 M2—M7 资格。

## 6. 最终判定

**FAIL：B-1 是可复现的 M1 阻断项。** 返工必须限制在旧 `artifact_events` 惰性容忍与相应升级回归，
不得恢复事件生产责任或增加在线迁移/兼容层。修复并重新独立审查前，**M2 不放行；M2—M7 均未完成。**
