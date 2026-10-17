# P1–P5 剩余工作：最小交接表

日期：2026-10-17。基线为 root 指定 `dev@ad89b41`；P5 L4 专属胶水已在 `513a7b0` 退役。使用 `scid-decision-corpus-maintenance` 只读核对现有计划、代码入口和结果 owner；本轮只新增本文，不改主计划、历史验收或生产，不运行测试/项目 import/安装/模型/远端，也不运行 Git。F1 exact-native 在另一作者实施中，本文不抢报其完成或新增通过数。

规则归属：[主迁移计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)仍管 P1–P5；[P4/P5 notes](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md)管实施边界；[原完成度复审](THIN_PLAN_COMPLETION_REAUDIT_20261017.zh-CN.md)是 `73f57c6` 的历史截面。后来的 P4 科学浏览、F2、L4 退役和精确请求级审查限制分别更新其对应事实，不能把旧截面的“未实现”照搬为当前状态，也不回写旧报告。

## 一、尚可直接代码实施（逐个小节点）

| 剩余项 | 当前事实与最小下一节点 | 停止边界 |
| --- | --- | --- |
| P3/F1 exact-native 输入贡献闭环 | **正在 trim 实施，先等其独立冻结/独审。** 按[已审设计](F1_MANAGED_INPUT_PROVENANCE_DESIGN_20261017.zh-CN.md)，已有 accepted→authority subject→compiler/slots→sealed inputs 的 owner 投影供来源/作者分别消费。之后只验一条实际 observation→新成果→正式 review 链及错 origin/缺输入负控。 | 不并行改其文件，不把 queued 或先 review 后 run 当观察后的闭环；不能只删 unknown/作者门槛。 |
| P5 A/B 脚本的失效 hypothesis case | `scripts/run_root_invoke_ab.py:26` 固定 `science.hypothesis.revise.v1`；`emit_contract:66` 调 compiled catalog，`main:228` 无条件遍历 CASES。当前 `tests/operations/test_r4_science_tasks.py:150` 明确要求该 ID 不再注册，`operations.catalog:75` 是 exact 字典查找。**最小节点：仅删除 hypothesis CASE 两行，保 figure 与通用实现。** | 源码 arm 在其余环境前提满足时必因已删 ID 无法投影，`--prepare-only` 也不绕过；这是脚本用户可达错误，非薄 CLI 生产路由缺陷。不开模型验证删除，不将其改名成 propose 并凭空重定义实验。 |
| P5 当前文档状态收口 | 主计划仍有旧静态阶段/P4 无科学浏览/A2 累计收口等局部文字；由 root 统一按各新结果 owner 修正当前段，保历史报告。先收 F1 结果再做一轮当前状态对齐即可。 | 本文不抢写 root 所有计划；不累加不同 revision 的通过数成全库验收。 |

**local/opaque 不是当前可无条件直接填 clear 的小补丁。** 其额外输入/贡献覆盖仍缺既有可信 owner 合同。若实际科研需要这些执行器的正式资格，最小下一节点是先盘一个具体 executor 的现有 accepted/snapshot/直接输入，证明可由原 owner 给出完备映射，再独审该可选投影；已有 exact sealed local 输入可先讨论，任意 command 外读、opaque/外部 observer 没证据就继续 unknown。来源限制未知与作者未知须分开，但缺贡献覆盖不能授独立资格。无需另建通用来源注册服务、复制 public_root/home、扫描祖先或按同 hash/同路径认同源；普通无资格科研继续。

## 二、需要真实部署或明确资源授权的验收

| 范围 | 已有有限证据 | 最小下一节点；不自动授权 |
| --- | --- | --- |
| P1/P5 包发现与依赖 | [分环节报告](P_MIGRATION_TARGETED_TEST_REPORT_20261017.zh-CN.md)：P1 27 项，core 单环境冒烟已做；功能测试与安装已分离。 | 真有 TCAD 安装部署需要时，仅显式 tcad cohort 一次环境，验证依赖/公共入口/资源；不在安装环境重跑全功能，不恢复矩阵。原 local/两个注册实现源码链已验，无需为 P1 再写注册框架。 |
| P2/P3 真实 Codex 身份与续接 | 合成进程已有正式 review/重叠、same-call 等保护；[新审查限制](FORMAL_REVIEW_REQUEST_SCOPED_UNAVAILABLE_IMPLEMENTATION_20261017.zh-CN.md)8 unique 增量通过。 | 一个有显式预算的真实 native 会话，核实际 home/thread/header/全部 attempt 与 reviewer 独立性，再视需要验同 session 有限 repair/wake。不得把合成 session 或新模型名称当真实平台资格。 |
| P2/P3 真实 TCAD 远端与资源 | command/socket/managed、非空输入、审批/ledger/retirement/迟批已有有限 fixture 证据，F2 真实退役控制链已单项通过。 | 在部署/凭据/许可、精确 review/批准及两维资源额度具备后，只做一条小远端 submit→query→collect；丢响应/fence 持久性另需可控服务证据。跨 boot/掉电/并发窗口逐项验，不重放 unknown、不发新预算补旧调用。 |
| P4 浏览器交互与长期控制 | 科学原文/成果浏览已 `537a483`，[7项增量](P4_SEALED_SCIENCE_BROWSING_IMPLEMENTATION_20261017.zh-CN.md)含真实 loopback HTTP；状态/暂停继续共用原 writer。 | 有浏览器能力时在同一 InstanceUI host 验登录/分页/附件/CSRF、长 continue 时 pause、服务重启。浏览器检查本身不需付费模型；需要推进科学时另给原预算。当前 HTTP 通过不等于浏览器通过。 |
| P4c1/P5 容量、发布、最终检查 | 只读包 4 项、P4 reader 与各故障负控、有限 core 安装已有记录。 | 只有明确剩余风险才补大包/磁盘满/跨进程竞态或当前 diff 所需发布/架构检查；资源门槛先明确。首次元数据/日志全 hash 仍有 IO 成本，不承诺常量 IO。没有全仓最终通过声明，也无需为凑全量重复所有旧环境。 |

以上不同历史结果不能相加为一次最终 HEAD 全套通过。需要真实模型/solver/安装或新资源时由 root 与用户另定范围，本轮不启动。

## 三、已明确后置或真实阻断的设计

| 项 | 当前界限 | 最小下一步 |
| --- | --- | --- |
| A1 强隔离 | 用户明确后置，当前是可信 Worker/同 UID 的软控制边界，HMAC 不是恶意进程隔离。 | 维持边界说明；只有用户重新提出强隔离目标才设计信任域，不擅自加服务、RPC、系统账户。 |
| P4c2 可写归档恢复 | [已审 BLOCKED](P4C2_WRITABLE_RESTORE_BOUNDARY_DESIGN_20261017.zh-CN.md)：包 restorable=false，没有唯一 owner 转移/永久 fencing/最新 ledger 高水位与全部外部依赖证明。同路径、空目录、goal_id/hash 或 root 内 flock 不证明唯一执行权。 | 当前使用 archive-inspect 只读核验；原 live 目录继续原 run/continue、worker-resume、execution-recover/execution-resume 的原合同。缺正面 pending/session/原 owner 仍 unsupported；不实现 material-repair、可写副本或第二 owner 库。 |
| 全部旧 Root/MCP/SQL 入口退役 | `pyproject:27` 仍公开 scid；`platforms/codex:471` 生成 mcp_proxy；`deploy/install.sh:1188`、control/approval systemd 模板仍调用旧服务，旧 CLI 还提供 serve-approval-ui/档案读取。 | 先决定旧部署是否迁移及旧 SQL/CAS 只读导出如何继续，逐消费者退役；新 UI/包 reader 不等于旧档案协议替代，不能整删。真正旧远端执行替代也须其真实资格。 |
| TCAD opaque 的通用候选/审计/交付能力 | P2 设计明确按声明 capability，不能套 local entry/snapshot 协议；缺能力属于诚实 unsupported，不是必须默认实现所有组合。 | 有实际交付需求再给一个 adapter 的精确功能合同和小闭环，不为 P1–P5 标签增通用平台。 |

## 四、P5 再删范围的精确证据

本次检查 scripts/src/plugins/tests/deploy/pyproject/.github：`science.hypothesis.revise.v1` 仅有上述 A/B CASE 和原负向 test 的命中，无当前注册；`run_root_invoke_ab` 没有仓内其它生产导入/测试调用/公共 console 注册或 release 名单依赖，直接脚本 main 是可达入口。删除该独占 CASE 不删除共享 `scenario/grade/projection` 等 helper，它们仍服务有效 figure；不删负向 test 或历史 A/B 证据。未搜索/验收仓外调用。

其余代表抽查：L2/L3 的 blind.csv.observe/review 在 fixture plugin 仍有声明，M7 frozen-copy 也仍注册；它们不是 L4 同类失效证据。旧 runtime/transport、TCAD v2、curve/API、来源/安全/存储纯规则、source negative fixtures 和旧包 re-export 仍有消费者，不能为删除量动它们。本轮没有证明另一整层或整目录可安全删除，也不宣称完成全仓 dead-code 审计。

**建议顺序：F1 exact-native 单节点收口 → A/B stale hypothesis CASE 精确退役 → root 同步当前状态 → 按实际部署需求选择有限验收。P4c2/A1 保留真实边界；local/opaque 没有来源证据时保持 unknown，不以扩系统换完成标签。**
