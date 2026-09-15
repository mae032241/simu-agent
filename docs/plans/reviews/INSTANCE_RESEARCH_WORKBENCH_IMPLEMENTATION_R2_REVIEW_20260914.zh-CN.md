# 实例研究工作台实现 R2 独立工程复审

日期：2026-09-14。最终结论：**PASS，限本文列明的工程实现与隔离交付验证范围**。
本轮源码缺口均已闭合，最终补充测试与修正后四 wheel 安装证据已读取，未发现剩余工程阻断。
R2 起初为 REVISE，以下保留发现、修正与复核经过；本结论不包括尚未部署的真实工作台页面、
真实 systemd 单元启动验收、真实科学接续，或无法确认 native writer 已停止的 LocalTrusted 实例归档。

基线为 `da220ce31c8cc9f9a60542a018b279e2f331f4c0`；对象包括工作树已跟踪改动及新增工作台、归档模块。
最终候选由 [SOURCE_MANIFEST.json](../evidence/instance-workbench/SOURCE_MANIFEST.json) 固定，包含 71 个变更或新增的
源码、测试、部署文件及验收脚本；清单 SHA256 为
`b69d500a4bcfe0167a09f7124252bb0118f1acc1bac9f1f1dcdfef1c511e4ee2`。
冻结 R3 的 SHA256 为 `f2d917995069e161dccd87897d17659a1095e5ec87a175e35919c0852a175fdf`。
依据为冻结的[实施计划 R3](../INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md)及
[scid-cross-boundary-review 技能](../../../../../.agents/skills/scid-cross-boundary-review/SKILL.md)。
保留 [R1 的失败记录](INSTANCE_RESEARCH_WORKBENCH_IMPLEMENTATION_R1_REVIEW_20260914.zh-CN.md)。
本次只读静态审查与读取主代理的隔离证据；未自行运行测试、构建、服务，未接触真实科研 state 或审定科学结论。

## 本轮发现，按影响排序

### B1 / P1：全局排他锁内仍有无界文件哈希与全运行时扫描

`service/instance_archive.py` 的 `_continue_restore` 在最终 EX 中再次调用 `_restore_validation`，
后者对归档文件、原记录数据库和活动目标再次完整 hash；总文件字节数没有上限。
归档 `_check_control` 同样在 EX 内执行 `Records.select`；
`instance_archive_records.py::_retained` 会扫描其他实例的控制记录、控制 CAS 与工作区 manifest。
32 MiB 的目标记录上限和逐行读取仅限制部分内存，不能限制这些 I/O 的总时长。
大输出或大共享 runtime 因而让其他实例的 Root、Worker、收集写入等待全局锁，可能消耗原 Run 时限。
这不满足 R3 的短暂 EX 和保护其他实例要求。

最小修正：全量核验留在 EX 外，持久目标 marker 保护目标；对所有控制数据库保持同一批只读连接，
扫描前后及 EX 内比较各自 `PRAGMA data_version`，核对原数据库 inode 与精确目标/门身份。
版本变化只中止或重做维护，不改变科研 Run。不可在重新打开的连接间比较 `data_version`，也不可长期持有
旧读事务再声称已观察到新版本。freeze 的自身提交后须重新取得下一阶段票据。

正常 CAS 写入只发布已核验临时文件，不原地改写已发布 digest；正常 recovery 发布完整只读 staging 树。
在这些受控路径及目标写入门成立时，EX 内不需要重读全部文件。
任意本机程序绕控制直接修改平台文件不参加 flock；即使 EX 内 hash，hash 后到 COMMIT 仍存在裸写窗口。
不能以扩大该威胁模型为理由，让所有实例等待无界重复 I/O。
**状态：源码已闭合。** `instance_archive_records.py:100–145` 的 ReadTicket 保持同一批 RO 连接，
没有长事务，核对各库 data_version、inode 和数据库集合；初始 freeze、publish、记录 switch 与 cleanup
均在锁外扫描后，于 EX 内再次验证。`instance_archive.py:584–624` 和 `:769–781` 传递已核验的
manifest/snapshot 对象与文件 stat，最终 EX 不再间接重哈希这两个大文件。
全活动库的 foreign_key_check 已移除；原 foreign_keys=ON、defer_foreign_keys=ON、COMMIT 仍约束本次修改，
新增遗漏依赖行的反例要求整笔五库事务回滚。锁内保留有界目标元数据、实际迁移与 fsync；
不承诺任意存储硬件下的固定毫秒时延。严格负例现禁止 EX 内全部 hash_file 调用，不再豁免清单和记录快照。

### B2 / P1：共享 recovery 目录逐文件恢复或清理会让其他实例读到半棵树

`instance_archive.py::_continue_restore` 逐项调用 `copy_verified`；
`instance_archive_files.py::copy_verified` 的目录分支立即创建活动 `recovery/<digest>`，随后才复制其子文件。
此时其他实例正常进入 `local_workspace.py::finalize`，发现同 digest 目录已经存在就跳过 staging 发布，
直接执行 `_sealed_files` 与 `verify_recovery`。恢复尚未复制完整时，该实例原本合法的 recovery finalize 会失败。
Hardened 继承同一实现，目标实例 marker 不阻挡另一实例，最终 EX hash 无法修复此前发生的失败。

最小修正仅针对共享不可变 recovery 根：在同一父目录私有 staging 中完整复制、核验、fsync 后原子发布整树；
已有 digest 仅精确核验并复用，不逐文件补写已发布目录。沿用已有 staging 机制，无须新复制系统。

作者进一步定位到对称归档窗口，本审查独立核对成立：`instance_archive_files.py::cleanup` 逐子文件删除，
其 late-retention guard 在文件间释放 EX。若 B 尚未登记同 digest 引用，A 可以先删一个文件；
B 随后正常 finalize 仍会发现 digest 目录存在并读取半删除树。完整性的单位必须是共享目录本身。
最小修正是在最后引用复核的 EX 内将整个 digest 根原子 rename 到同父目录私有 retired 名称，锁外清理。
rename 前须持久记录精确原路径、退休路径和 job；崩溃继续只清退休目录，不能再碰 B 新发布的原同名目录。
原包已经核验保存全部原件，退休路径只属于可重试清理日志；实际释放量按真实删除计算。
**状态：源码已闭合。** `instance_archive_files.py:455–499` 核验私有完整树后在短 EX 内发布；
已有 digest 只读核验且保留原 inode。`instance_archive.py::_retire_recovery_trees` 在 rename 前持久记录
精确 job、原目录 inode 与 retired 路径；resume/rollback 都只消费原 retired 副本，保留 B 新发布的同名根。
CAS 复制也改为不覆盖的硬链接发布，晚到相同内容原件核验后复用。

后续两处恢复收尾已补齐：同 job 私有 stage 的部分文件、`.archive-copy` 临时文件在 rollback 或已有目标的
resume 时均安全清理，其他 job 的 staging 保留；若根尚未发布，先从已核验归档重建自己的 stage，
避免硬退出在子文件 link 后、临时 unlink 前造成无进展的重复 resume。
新增源码负例分别覆盖 B 晚到完整发布、retirement rename 后重启的 resume/rollback、B 新 inode 保留、
私有 stage 中断以及没有 B 发布时的临时硬链接恢复。原生 hard-exit 覆盖退休 rename 窗口；通过证据见文末最终补充。

### B3 / P2：节点达到响应上限后丢失全部诊断及继续游标

`approval_ui/read_model.py::_bounded_node` 在节点超过 256 KiB 时仅保留少量元数据和 outputs，
同时删除 `diagnostics` 和 `next_after`。默认 50 条错误、每条 16 个合法长诊断消息即可超过上限。
`workbench_render.py::_diagnostics` 的分页逻辑尚未运行就失去事件，因此页面无完整错误或继续入口。

最小修正：按节点字节预算保留诊断事件前缀，以最后实际返回 event_id 续读；单事件过大也须保留其定位和原件入口。
降级摘要时保留精确原引用，不新增科学输出约束。
**状态：源码已闭合。** `read_model.py:767–804` 按总预算保留原事件前缀，续读游标使用最后实际返回 event_id；
单条旧事件超限仍保留事件身份及原 scoped engineering 引用，并能继续后页。
已静态核对 70 条长诊断逐页拼回与原列表完全一致的回归，以及超大旧事件后继续读取的负例；
对应通过证据见下文，本审查未运行。

复核时还发现同类 overview wrapper 预算缺口：`overview` 嵌入接近 256 KiB 的 nodes 页后，
另加实例描述、目标与 selections，仅通过删除 active_tasks 降量；无活动任务时可能仍然超限。
需给节点页预留整份 overview 的预算，并保留最后实际返回节点对应的继续游标。
**相关 wrapper 修正亦已静态闭合。** `overview` 计入完整外层开销后缩减 recent 节点页，
游标由最后实际保留 binding 重算；新增合法长实例描述与 current selections 的 30 节点无重复续页用例。

### B4 / P2：归档只读代理遗漏已有的两个关系查询

`instance_archive_reader.py` 的 `run_reads` allowlist 未包含 `related_runs` 与 `recovery_links`。
`read_model.py::_relationships` 因而对所有归档节点丢失 producer/consumer Run、匹配审查与 resume/draft 关系，
尽管这些原记录已完整保存在归档数据库中。

两个方法在 `runs.py` 中仅执行 SELECT，最小修正是允许归档 clone 调用这两个已有只读方法，并比较同节点归档前后关系。
**状态：源码已闭合。** 两个已有 SELECT 方法已加入归档只读 allowlist；backend `supports_operation`
也可用于只读恢复能力检查。底层仍为原数据库 clone 的 mode=ro/query_only 连接，未增加写方法。

### B5 / P2：只有待审批或已完成成果的实例概览无法定位已有原目标

`read_model.py::overview` 只从活动 Run 的显式 objective port 取目标。
只有 pending approval、或所有 Run 已终态但已有 selected/recent 节点时，原目标仍可沿精确父链定位，
概览却一律报告未提供。这是概览完整性缺口，不会改变科研状态或审批。

最小修正不需要科学 payload 或全库查询：显式目标为空时，选至多一个有明确显示依据的节点
（唯一活动审批、唯一 selected 节点或现有 recent 节点），复用有界 envelope 父链查询取得目标引用。
记录该定位的 basis；多个分支或歧义仍给明确节点入口，不猜一个共同研究目标。
若保留纯 metadata 首屏并要求用户逐节点阅读，应明确它是 R3 概览范围的收窄。
**状态：源码已闭合。** 已加入单节点、有明确 basis 的 128 项上限 metadata 父链回退；
不读取科学 payload。唯一性按原始 selection 数量与完整 active 归属判断，缺失 binding 不被过滤成
“唯一分支”；父链查询有缺口或歧义时保留节点入口，不把仅找到的一项当成完整唯一目标。

## 已核对且未发现新增阻断的问题

- P0–P4 的浏览器读取使用精确实例 grant；维护操作另需 maintenance scope、CSRF、明确确认与预览指纹。
  审批决定仍经过原 token、精确请求身份、nonce 与原审批服务，浏览凭据不直接成为决定。
  归档审批只读，恢复提高 browser epoch，不自动重绑会话、续租 transport 或执行任务。
- 读取模型从实际 binding、Run 输入/输出、冻结审批 subjects 与 Artifact 父链取得来源。
  未用最新同 Schema 记录替代原始目标或审批依据；未知资格与缺失历史观测明确显示，不自动续资格。
- 两个 presentation entry point 接收冻结数据与授权引用，没有 runtime/数据库写句柄；异常退回原件阅读。
  安全输出映射拒绝任意 HTML/JS，图件只允许登记原件的有界 PNG/JPEG 解码，未知格式下载。
- 轨迹仅写独立 UI 数据库；一个有界观察线程只轮询元数据。SSE 连接和游标有界，等待与网络发送在读取锁外，
  失败写 UI 日志而不写 Run 科学失败。JS 失败仍保留原生审批表单与原件入口。
- CLI 与 systemd 沿用现有 UI 服务和端口；部署只创建固定 archive 两级目录并拒绝 symlink，
  没有对整个工作区 chmod/chown。归档历史目录已位于获准的 instances 根下。
- R1 的旧 open 归属、无实例目录只读准入、collection 诊断 scope 误作 owner 均已闭合。
  Writer lease 覆盖 guard 子进程、最终日志与退出；维护拒绝不改写成 Run 科学失败。
- `run_activity_sequence` 是保留在活动库的全局存储计数元数据；七处活动写入共用同事务分配器。
  归档只保留其 Schema，不迁走或恢复覆盖旧计数；活动原 event_id 不重编号。
- 五主库保持原 inode，通过 DELETE journal 的 ATTACH 事务迁移精确行；删除触发器的短暂移除与原样恢复
  都位于同一事务。共享 Artifact 与 CAS 保留，cleanup 在临界检查中覆盖 recovery 子文件和目录。
- 恢复提交后先保存可 resume 的 finalizing，随后清门，最后完成；硬退出可以继续清门。
  marker handoff 为原子替换，并记录旧 job 以覆盖交接前后崩溃。完成后的恢复不回放旧会话或 dispatch lease。

## 规模与证据边界

Records 已改为按目标 SQL 筛选与流式检查外部引用，其他实例大 BLOB 不再直接占用目标记录预算；
无法读取的外部控制 carrier 保守保留关联原件并报告缺口。
当前仍有目标原记录 32 MiB、单个控制 payload 16 MiB、目标文件清单 50,000 项的明确支持上限。
它们不损坏超限实例，但该实例无法完成本版归档，交付文档应说明，不能宣称任意规模完整迁移。
Local backend 历史 Run 的 native writer 未确认停止仍报告 busy；真实 Fig4 归档与该组合未验收。

已读取以下主代理证据；本复审未自行重跑：

- [Writer 定向证据](../evidence/instance-workbench/p5-writer-second.json)：86 passed、1 deselected，峰值 332.59 MiB。
- [浏览器中文排版](../evidence/instance-workbench/browser-layout-cjk.json)：1280/768/390 宽度，真实 Chromium、CJK 字体，
  无 JS 错误，原决定未变；峰值 458.69 MiB。移动端依据位于决定区前。
- [最终长参数表浏览器检查](../evidence/instance-workbench/browser-final.json)：相同三档宽度、真实 CJK 字体，
  原图成功加载、无 JS 错误、原决定未变；峰值 471.88 MiB。补充静态核对紧凑 reported value/unit 与
  条件 name/value/unit：保留原值，不换算或新增科学字段；来源仍以精确原件和 pointer 链接呈现。
- [首轮隔离四 wheel 验证](../evidence/instance-workbench/p6-installed-wheels.log)：50 项合同一致、两个展示 entry point、
  static HTTP、隔离归档浏览恢复、两次 Root/Worker stdio 提交与 Worker 复用；峰值 394.68 MiB。
  这是旧候选证据；其后已按文末最终四 wheel 隔离安装记录重新构建复验。并非真实科学 Agent 或远程 TCAD 执行验收。
- `p5-archive-final` 保留 72 passed / 1 failed；`p6-ui-regression` 保留 74 passed / 1 failed。
  前者暴露裸文件修改检测边界，后者是旧布局 CSS 字串断言；最终候选的通过证据已另行登记，未覆盖失败日志。
- [后续 UI 回归](../evidence/instance-workbench/p6-ui-final.json)：81 passed，峰值 143.04 MiB；
  [诊断/概览与页面补充](../evidence/instance-workbench/p6-read-final.json)：23 passed，峰值 81.33 MiB。
- [原恢复、Worker 复用、选择性 status 与用户原文续接](../evidence/instance-workbench/p6-original-continuation.json)：
  30 passed，峰值 132.95 MiB；保留既有 datetime.utcnow 弃用警告。
- `p6-archive-final` 保留 86 passed / 2 failed，峰值 200.88 MiB：两项新恢复续接用例暴露可选服务 None 的
  overview 缺口。当前已改为显式 control_service_unavailable，且不把其余 namespace 推定为完整唯一分支；
  此修正、最终 stage 前进用例与新候选 wheel 均已由文末最终补充证据闭合。

## 最终补充证据与放行范围

- [最终源码静态检查](../evidence/instance-workbench/p6-source-final.log)及
  [资源记录](../evidence/instance-workbench/p6-source-final.json)：退出码 0，峰值 28.48 MiB。
  已读取检查脚本，确认其覆盖变更 Python AST、git diff --check、部署脚本 bash -n、45/50 项合同快照字节一致
  及冻结 R3 摘要；生成上述 71 文件清单，日志中的清单摘要与本报告候选身份一致。
- [最终恢复/接续补充](../evidence/instance-workbench/p6-final-recovery.log)及
  [资源记录](../evidence/instance-workbench/p6-final-recovery.json)：20 passed，峰值 133.75 MiB。
  覆盖原 `resume_from`/`draft_from` 实际准入和新 assignment、最后的未发布 stage 临时硬链接恢复、
  可选服务缺口，以及诊断/概览/管理页面。上轮两个 optional-service 失败已闭合。
- [最终四 wheel 隔离安装](../evidence/instance-workbench/p6-installed-final.log)及
  [资源记录](../evidence/instance-workbench/p6-installed-final.json)：退出码 0，峰值 394.59 MiB。
  修正后源码重新构建并装入不共享系统 site-packages 的临时 venv；50 项原 Operation/tool 合同一致，
  两个展示 entry point、静态 HTTP、隔离归档/浏览/恢复、两次 Root/Worker stdio 提交和 Worker 复用通过。
  旧候选的安装日志未被覆盖；临时安装已清理。
- [4097 父引用原回归](../evidence/instance-workbench/p6-legacy-parent-bound.log)：1 passed，32.242 秒，
  峰值 128.16 MiB，先前超时边界已取得独立串行通过结果。
- [既有 L2 夹具失败复现](../evidence/instance-workbench/p6-baseline-fixture.log)：在精确基线仍失败，
  原因是旧测试目录构造的 output_context_invalid，不能计为本轮新回归或已修复用例。
- [等效权限挂载沙箱](../evidence/instance-workbench/p6-permissions-sandbox.log)及
  [资源记录](../evidence/instance-workbench/p6-permissions-sandbox.json)：退出码 0，1.815 秒，峰值 107.68 MiB。
  已静态核对 [sandbox_check.py](../evidence/instance-workbench/sandbox_check.py)：真实 bwrap 将根目录挂载只读，
  仅为 state、local workspaces、archive/instances 单独添加可写 bind，实际写源码/工作区失败。
  在该沙箱内完成两次隔离归档—原件读取—恢复，包括再次归档产生 history 的路径。
  因此 R3 的等效权限沙箱项已闭合；它不等同真实 systemd 单元启动或外部求解器执行。

据此放行本轮工程实现与隔离包交付。测试是按边界挑选的串行集合，本审查没有运行全量套件，
也不把通过数量当成未运行场景的证明。主干科研行动目录、冻结输入、原审批权威和已有恢复规则未见被本轮改写。

部署边界继续保留：固定原根/原后端恢复；目标 32 MiB 原记录、单个控制 payload 16 MiB 和 50,000 项文件清单上限；
未知归属/共享资料保守保留；LocalTrusted 有历史 Run 仍不能证明无 native writer，不宣称该组合归档通过。
真实 systemd 单元启动、两类真实 Fig4 页面阅读及真实科学接续仍需现场验收。
安装目录创建/权限、unit 渲染和等效挂载沙箱均已验证，不能将它们等同实际 systemd 服务启动。
永久删除未实现，真实 Fig4 实例未由本轮归档测试移动；本 PASS 不授权绕过维护预览或原人工审批。
