# 通用执行组合链再审查（2026-10-16）

受审 HEAD：`53798e9798f6634bd2b62ecedb2bc03e742a7411`，前序 `da7d891`、`727f537`。发现 **2 项新可达 P2，加 1 项既有 G3 恢复缺口补证**；未发现新的 P1/P0 证据。本轮只审查，未修复。

适用 AGENTS、`scid-cross-boundary-review`、`scid-change-scope-checks` 已读。生产代码只读，唯一仓库写入为本报告；未提交、未调用模型或 solver。起止 HEAD 一致，生产 tracked diff 为空。

## R1 — P2：远端私有结果被误当成本地候选，成功执行无法封存

**已实测，有正常远端对照。** 最紧位置：`generic_results.py:16`–`:21`；任意 backend 的 completed.result 经 `history.py:241` 投影，再由 `history.py:309` 及其他 observer 分支调用候选解析。

ManagedExecutionInterface.result 约束终态/proofs，没有把 remote 私有 result 声明为 LocalExecution 的 version-1 候选协议。当前解析却仅凭 status=available 和 candidate 存在，就无保护地 next 查找 metric 与 `artifacts/` 加 collected name。

同一 registered backend 的实际对照：

| result 内容 | CLI / managed history | W 封存 |
| --- | --- | --- |
| 无私有 result | known_success / known_success | sealed |
| available + 空 metrics + candidate.native_model_id | known_success / known_success | StopIteration |
| 本地形状 metric/candidate，但 artifact=model.bin、collect 名=original | known_success / known_success | StopIteration |

路径是合法执行 → 共同 observation → known history → W seal 的 generic candidate 投影异常；下游 A/selection/delivery 因没有 seal 无法继续。第三组不证明 remote 已获得本地候选交付支持；第二组没有请求该能力，仍被误解析。

这是协议身份缺失造成的可用性缺陷，不是因名称或 Schema 同名报错。应只对明确声明的结果协议投影候选；私有结果保持 opaque，已声明协议的坏映射给有界诊断，避免未捕获迭代异常。未观察到错误科学成功资格。

## R2 — P2：异步且 collect=false 的后端没有终态投影入口

**真实 CLI 与生产 history 已实测。** 位置：`experiments.py:643`–`:662`；新接口缺观察时保持 unknown：`history.py:195`。LifecycleCapabilities 允许 query=true、collect=false。

异步 run 返回时尚未完成，控制层正确不生成终态。后端稍后完成后，query/lookup 只验证已存在的 observation；缺失时不创建。唯一后续投影动作 collect 又因能力未声明而拒绝。

| 同一 call 的位置 | 实际结果 |
| --- | --- |
| 初次 run | unknown，任务仍运行 |
| 正常完成后的 query / lookup | exit 0、succeeded |
| collect | exit 2、unavailable，符合能力声明 |
| history | unknown，execution-observation.json 不存在 |

因此原生终态已明确，标准生命周期仍无法把它交给科学封存。这里不要求 query 违反只读边界；应有独立的显式确认/冻结入口，或明确在 admission 拒绝不支持的组合，不能接受任务后依赖不存在的 collection 能力。

## R3 — 既有 P2/G3 恢复缺口补证：late collect 成功后仍被旧 unknown 阻断

**W seal → late collect → A seal → 后继 W admission 已实测。** 不冒称新回归；不可变旧 seal 本身是正确行为。

位置：`history.managed_status():181`/`:195` 使用旧封存事实；`search.py:237`–`:247` 从 sealed unknown 设置 opportunity_unknown；`breadth.admit():69`–`:70` 拒绝新接受。

任务未完成时 W 用 blocked finding 封存 partial。随后原后端完成，对同一 call collect 成功，但没有新科学输入/恢复入口把这一解析事实绑定到原 reservation 并供后继消费者使用：

```text
原 W sealed status       unknown
late collect             collected
当前 managed status      known_success
旧 seal validation       passed（未改历史）
后继 W prior_unknown     true
后继 admission           OpportunityRequired: resolve original unknown execution
后继新接受次数           0
```

原身份已解析，科学预算前缀仍阻断正常继续。需要有来源与权限的追加恢复/输入绑定，保留旧 seal；不能删 unknown、重写历史或加重试预算制造成功。这是既有 G3 的具体组合证据，不另计新缺陷族。

## 验证方法与边界

重新检查 registered execution → 共同终态 → history 三条 capture 分支/验证 → Worker evidence → collect_materials/checkpoint → A 正式挂载 → lineage/search/breadth → candidate/shortlist → delivery intent/confirmation；包括 run/query/lookup/collect/cancel/lineage-status alternate callers 与 native attempt。

静态未发现新的 optional audit 绕过、本地清理条件放宽或重复 promote 路径：显式必需 audit 缺能力仍在 prepare 拒绝；旧 descriptor 默认必需 audit；缺可选能力保持中性。以上是代码检查，不冒充本轮重新执行了交付/audit 故障矩阵。目录确认仍不代表外部服务提交。

与归档审查者协调后，使用仓库 serial_lock/run_one/default limits 运行一个 synthetic registered source backend probe。真实子进程调用 experiment CLI；后端完成是 fixture 模拟事件，H/W/A host anchors 复用封存 helper，无模型。

最终命令：`python /tmp/scid-composed-execution-reaudit-20261016/supervise.py`。exit 0，3.392s，观察 tree RSS 峰值 100204544 bytes，cleanup_complete=true，无内存止损。首批因 harness 对异常类别预期过窄停止；修正后在新案例目录完成全批，未改生产断言。

原始证据根：`/tmp/scid-composed-execution-reaudit-20261016/`：

- `r2/probe-result.json`：全部对照与最终结果。
- `composed_remote.py`、`probe.py`、`supervise.py`：可复现 backend/driver。
- `check-r2/{pytest.log,resource.json}`：完成日志与资源记录。
- `evidence-identity.json`：受审 HEAD、10 个相关生产文件和 probe 摘要。

`git diff --check` 通过。没有跑全套、fresh wheel、真实远端服务、模型、solver、daemon/browser 或跨主机重启；源 entry point 夹具不构成安装资格。前序同步验收没有覆盖本轮私有 metadata 与异步组合。归档再审查由其他审查者独立报告，本报告不重复其发现。
