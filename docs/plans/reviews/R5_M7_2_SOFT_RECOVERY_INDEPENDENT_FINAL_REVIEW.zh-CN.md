# R5-M7.2 默认软隔离恢复独立终审

日期：2026-09-02  
审查范围：M7.2 第 5 项修订后的生产实现、持久实跑根
`deliverables/m7-live-run-recovery-soft-20260902-01/`、第 15 节机器候选及相关聚焦测试  
审查方式：只读复算数据库、草稿与封存字节、启动收据和生成配置；静态追踪生产入口；运行不启动
真实 Codex 的低内存聚焦测试  
结论：**PASS；阻断项 0。关闭 M7.2 第 5 项，关闭 M7.2，并放行 M7.3。**

## 1. 终审结论

上次终审的两个阻断项均已由最小实现和新的真实运行证据关闭：

1. 恢复 Agent 的封存信号精确保留了只存在于失败草稿的随机标记；封存 payload 又带回只存在于任务
   Schema 的必填常量。恢复 Run 在首次提交前重新调用了声明的 CSV 工具，且持久活动账本中
   `output_rejected=0`。在当前明确接受的可信本地软隔离口径下，这足以排除“只拿相同输入从头重做”
   和“从提交拒绝诊断反推格式”两种替代解释。
2. `max_attempts=2` 已由唯一 `RunService` 解释为“根 Run 加整棵恢复后代的总 Run 数”。Root 预检和
   调度写事务复用同一校验；实跑完成一个恢复后，额外 preflight/invoke 均拒绝且没有新增 Run 或
   binding。自动化还覆盖从根、从子 Run 发起超限请求以及 Runtime 重启后的同样拒绝。

本轮没有新增读取 MCP、读取收据、恢复实体、恢复状态机、后台进程或第二注册入口。恢复草稿仍不是
Artifact，最终 Artifact 仅以精确原 CSV 为父项。因此修正没有把轻量 OperationSpec 主干重新变成
科研流程控制器。

## 2. EvidenceAudit

### 2.1 来源声明

| 键 | 来源与定位 |
|---|---|
| S1 | 持久根 `state/database/runs.sqlite3`，表 `runs`、`run_activity` |
| S2 | 持久根 `state/database/artifact_agent.sqlite3`，表 `artifact_envelopes`、`artifact_links` 及 `state/artifacts/sha256/` |
| S3 | 持久根 `state/database/scheduler-bindings.sqlite3`，表 `scheduler_bindings` |
| S4 | 持久根恢复 Run 的 `assignment.json`、`schema/result.schema.json`、`recovery-draft/result.json`、`output/result.json`，以及 `failure-evidence.json`、`final-evidence.json` |
| S5 | 持久根 `launch-receipts/recovery_launcher_receipt.json`、生成 Agent profile 与启动器当前收据校验器 |
| S6 | `RunService.schedule/validate_resume/_validate_resume/_recovery_root_id`、Root `operation_preflight` 恢复分支、Codex Local/Hardened profile 生成路径 |
| S7 | `test_status_is_pure_and_failure_recovery_is_explicit` 及 Local/Hardened/启动收据聚焦回归 |
| S8 | 当前实施计划第 1.1、12.2、13、15 节，设计宪章和 33 项约束矩阵 |

### 2.2 材料问题检查

| 检查 | 结论 | 证据 |
|---|---|---|
| 草稿是否真实参与恢复结果 | 通过 | S1、S4 |
| Schema 是否在首次成功提交前可用 | 通过 | S1、S4、S5 |
| 恢复是否重新调用声明领域工具 | 通过 | S1 |
| 草稿是否错误晋级为科学 Artifact | 通过，未晋级 | S1、S2、S4 |
| 输出父链和 CAS 是否精确 | 通过 | S1、S2、S4 |
| 恢复次数是否覆盖整棵后代树 | 通过 | S1、S3、S6、S7 |
| 超限拒绝是否零 Run、零 binding | 通过 | S1、S3、S7 |
| 启动身份、工具投影和 4 GiB 边界是否匹配 | 通过 | S5 |
| 是否引入第二控制主干或领域特判 | 未发现 | S6、S8 |
| 是否诚实保留软隔离限制 | 通过 | S5、S8 |

独立总判定：`pass`。没有缺失会改变上述结论的当前证据；实际超时、非 SQLite 并发和强隔离属于未来
验证或已知限制，不作为这次显式失败恢复样本的当前失败。

## 3. 持久状态复算

### 3.1 失败源与恢复关系

`runs` 只有两个 Run：原 Run 为 `failed`，恢复 Run 为 `completed`，后者的 `resume_from_run_id` 精确
指向前者。二者的 Operation id、版本、digest、Agent 类型、instruction 和完整 `inputs_json` 字节相同，
Run 身份和输出绑定不同。原 Run 没有 accepted candidate、output、signal 或 completion receipt，只有
一个 471 字节的恢复草稿清单。

草稿清单、规范恢复副本和恢复工作区副本的大小与 SHA-256 完全一致，两个规范副本模式均为 `0400`。
草稿标记明文不出现在 assignment instruction、输入、Schema、生成 profile 或启动消息中；故障收据
只保存其 SHA-256。完成 Run 的封存 signal 精确保留该标记，因而功能结果要求 Agent 实际取得失败
草稿内容。

### 3.2 Schema、首次提交与领域重验

测试必填常量不出现在 assignment、输入、恢复草稿、生成 profile 或项目级 AGENTS 指令中，只出现在
恢复工作区的输出 Schema；完成 payload 带回相同常量。恢复 Run 的 `run_activity` 只有一次
`tool_succeeded:worker_csv_summarize`，没有 `output_rejected`。因此记录的是领域工具重验后的首次成功
提交，不是控制面拒绝后修格式。

这是一项功能性证明，不是原生文件读取审计。默认 Local profile 明确开启原生文件/代码/图像能力并
关闭 Codex web search，提示限制其只使用 Run 工作区；启动调试时使用外层软隔离，不能从这些事实
推出操作系统级文件或网络隔离。该边界与 `SEC-002 known_issue` 一致，报告没有把它误写为
`conformant`。

### 3.3 Artifact、父链与完整性

Artifact 库只有原 CSV、错误输入负控 CSV 和最终 observation 三项；不存在草稿 Artifact。最终
observation 的唯一 `parent` 是原 CSV，错误负控和恢复草稿都未进入父链。三个 CAS 文件的实际
SHA-256 均与登记值一致，三个 SQLite 数据库的 `pragma integrity_check` 均为 `ok`。

启动收据经当前校验器重新验证通过。它绑定精确 Agent profile、唯一目标 Worker MCP、所需的三个
生命周期工具加 CSV 工具、关闭 web search、正常退出和 4096 MiB 限制；记录峰值进程树 RSS 为
291576 KiB，未触发内存限制。

## 4. `max_attempts` 与零写入拒绝

生产实现先沿 `resume_from_run_id` 找到恢复根，再用递归 CTE 对根和全部后代计数；达到 OperationSpec
已有的 `max_attempts` 即拒绝。Root preflight 调用同一方法，真正 schedule 在冻结输入后、
`BEGIN IMMEDIATE` 写事务内重新校验，再决定是否插入 Run。这使 SQLite 当前后进入的兄弟恢复请求会
看到已提交的计数，而不是依赖一次可过期的预检。

持久实跑在根加一个完成恢复后，从失败根再次 preflight 和 invoke 均拒绝，最终数据库仍只有两个
Run、两个 Run binding。聚焦自动化进一步覆盖：恢复 Run 再失败、重新打开 Runtime 后，分别从根和
子 Run 发起 preflight/invoke 都被拒绝，Run 列表不变。因而旧阻断 B2 已关闭。

## 5. 轻量性与 33 项约束边界

本轮受影响边界未发现新的 33 项约束偏离：

- `AUTH`/`ROLE`：Worker 仍无 Root 控制接口，正式状态只由 Run 服务推进；
- `IMM`/`CQRS`：失败草稿不成为 Artifact，查询不代替显式失败或恢复命令；
- `PLG`/`TOP`：能力仍来自单一编译 Operation，恢复没有新增目录或专用调度入口；
- `RES-002`：单次时间、输入/输出字节、文件、进程内存和恢复总次数均有界，重启不换 Operation 或输入；
- `SEC-002`：默认 Local 仍是提示与任务物化形成的软隔离，已知问题继续公开，不冒充技术沙箱。

该判断仅覆盖本轮恢复改动触及的约束，不把矩阵中其他 `pending_review` 项自动升级为已符合。

## 6. 非阻断债务

1. 失败隔离后仍保留一份只读 quarantine 候选副本。它没有进入 Artifact、父链、Run 授权或最终输出，
   不影响两个旧阻断项，但应继续作为低优先级存储清理债务。
2. `NativeToolPolicy.shell="none"` 现在表达 Operation 对后端的最低要求，而默认 Local 仍统一提供任务内
   原生文件/代码能力；字段名容易被误读。后续可重命名或删除，不应为此再增加一层权限状态。
3. 当前整树并发结论依赖 SQLite `BEGIN IMMEDIATE`。若未来替换存储后端，必须重新验证兄弟恢复竞争；
   本轮不需要预先建设分布式恢复协议。
4. 本样本验证显式进程失败，不验证真实长任务超时。计划使用“失败或超时”的择一门，因此这不是
   M7.2 当前缺口。

## 7. 独立检查结果与放行

独立运行四项聚焦回归，结果为：

```text
4 passed in 1.15s
```

覆盖重启后整树超限、Local 能力投影、Hardened 非退化和启动收据绑定。另完成持久数据库完整性、
草稿/Artifact/CAS 摘要、文件模式、profile digest、启动收据和相关差异格式复算，均通过。本审查未
启动 Codex、未修改持久根，也未把聚焦测试扩大为全仓资格。

最终放行结果：

- 上次阻断 B1（真实利用恢复草稿）：**关闭**；
- 上次阻断 B2（恢复链无硬上限）：**关闭**；
- M7.2 第 5 项：**PASS**；
- M7.2：**PASS**；
- M7.3：**允许开始**；
- M7、R5-M：**尚未完成，仍须完成 M7.3—M7.5 及其独立审查。**
