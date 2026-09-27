# 实例研究工作台实施记录

> 2026-09-15绑定后的现场可用性检查未通过；本页保留原工程交付事实，当前修订见[可用性修订记录](USABILITY_IMPLEMENTATION.zh-CN.md)。

源码基线：`da220ce31c8cc9f9a60542a018b279e2f331f4c0`。
严格实施 [R3 计划](../../INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md)，批准文本 SHA256：
`f2d917995069e161dccd87897d17659a1095e5ec87a175e35919c0852a175fdf`。
[R2 独立计划复审 PASS](../../reviews/INSTANCE_RESEARCH_WORKBENCH_PLAN_R2_REVIEW_20260914.zh-CN.md)，
[R3 管理入口有界补充 PASS](../../reviews/INSTANCE_RESEARCH_WORKBENCH_PLAN_R3_REVIEW_20260914.zh-CN.md)。

最终状态：**源码实施与隔离交付验证完成，独立实现 R2 审查 PASS**。
[实现复审](../../reviews/INSTANCE_RESEARCH_WORKBENCH_IMPLEMENTATION_R2_REVIEW_20260914.zh-CN.md)
仅放行已验证的工程范围。2026-09-15用户安装重启后，[部署文件与服务核对已通过](POSTINSTALL_20260915.zh-CN.md)，
真实 Fig4 页面验收等待用户绑定；下文保留交付时的测试范围与现场边界。
[最终源码清单](SOURCE_MANIFEST.json)记录71个源码、测试、部署及验收脚本的逐文件摘要，清单 SHA256：
`b69d500a4bcfe0167a09f7124252bb0118f1acc1bac9f1f1dcdfef1c511e4ee2`。

## 进度

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| P0 基线、数据及写入者归属 | 已完成 | 两套合同快照、47项定向测试基线、归属清单 |
| P1 实例读取与浏览权限 | 已完成 | 18项新测试及32项原有回归通过；45个Operation及工具合同与基线完全一致 |
| P2 参数证据与审批排版 | 已完成 | 27项提供者/排版测试及24项HTTP整合/执行身份测试通过 |
| P3 自动轨迹 | 已完成 | 38项读取/页面/缓存及14项实际HTTP/原管理测试通过 |
| P4 有界推送 | 已完成 | 17项SSE/HTTP和锁边界测试通过 |
| P5 实际归档、恢复与安装 | 工程完成 | 86项归档检查通过；另20项最终检查闭合两个接续失败及暂存恢复，等效只读挂载沙箱两次恢复通过 |
| P6 综合验收与独立审查 | 工程交付通过；现场项待部署 | 81项UI检查、30项原接续回归、最终四wheel隔离安装、真实Chromium检查及独立实现R2审查通过 |

永久删除不在本版实施。真实 Fig4 实例未被归档、迁移或重新执行。
测试与构建串行，进程树预算 512 MiB，保留所有失败与未验收边界。

## P0 已取得的基线

- 默认 45 个 Operation：[合同快照](BASELINE_CONTRACTS.json)，目录摘要
  `fdab17d6a0094586b76bc1a1e640b0674c64d6e290fb34ee60df575ed11ea142`。
- 包含可选 figure 插件的 50 个 Operation：[合同快照](BASELINE_CONTRACTS_OPTIONAL_FIGURE.json)，目录摘要
  `65b1538095aa594ab9995f3f2bb913c3e4927e0df38d3c4c778d30e6fb20ff32`。
  快照包含每个 spec、Worker 工具和两类 Root 工具 Schema 摘要；通过相同脚本与插件集合复验。
- 审批渲染、精确执行审批身份、实例管理：[33 passed](baseline-ui-and-identity.log)，
  [进程树峰值 140.28 MiB、51.825 秒](baseline-ui-and-identity.json)。
- 新 runtime 嵌套恢复、改变输入的 draft、复用 Worker 打开新 Run、选择性 status：
  [14 passed](baseline-continuation.log)，[峰值 125.74 MiB、11.252 秒](baseline-continuation.json)。
  保留一项既有 `datetime.utcnow()` 弃用警告；未修改 VM runner。

基线未运行全量套件，未访问或变更真实实例；这些通过结果不代表新功能已经实现。

[归档资料与写入者清单](ARCHIVE_OWNERSHIP_BASELINE.zh-CN.md)由独立源码探查者交付。
旧 local debug 随机临时根及部分按摘要保存的插件缓存缺少持久实例归属；不能猜配或整根迁移。
已封存/工作区中可精确归属的资料照常纳入，未知项在归档预览中明确保留，不宣称已搬走这些历史临时文件。

## P1 实例读取与权限

- [18项新测试通过](p1-read-and-access.log)，峰值112.5MiB，5.325秒：实例隔离、精确历史父链、分页、读取无写入、浏览范围与管理入口续用。
- [32项原有回归通过](p1-original-focused.log)，峰值127.63MiB，23.123秒：审批身份、决定、刷新和原目标接续。
- 原33项批次在最后的4097父引用逐项登记测试触发150秒上限，峰值126.38MiB，[保留超时证据](p1-original-behavior.json)。未改动该测试或对应生产逻辑；P6已[单独复验通过](p6-legacy-parent-bound.log)，32.242秒、128.16MiB。原超时不改写为通过。
- [P1合同快照](P1_CONTRACTS.json)与默认45项基线逐字一致；无新增科学Operation、Worker输入字段或工具。
- P2对大原件增加只读流式打开：固定原件引用、逐块核验同一文件描述符再发送，避免下载整份文件驻留内存；普通CAS写入不变。

## P2 审批、参数和来源

- [27项纯展示与排版测试](p2-providers-and-renderer.log)，峰值114.32MiB、3.718秒。包含来源维度、未知/假设、精确位置、插件失败、安全链接及合法超长请求首屏上限。
- [24项HTTP整合和原执行身份测试](p2-approval-integration.log)，峰值136.78MiB、11.556秒。大计划的协议/源码不挤掉原目标；真实参数结构显示选值、报告值、来源与未知；审批对象和原件字节不变。
- [17项精确原件与读取测试](p2-evidence.log)，峰值121.45MiB。图件校验实际格式/尺寸；原件流式读取先校验同一描述符；HTML伪装图片不内联。
- 默认45项及可选figure50项合同在P1后均与基线一致；P2仅在新UI entry-point group注册两个提供者，最终wheel再验证实际发现。
- 此处为结构/HTTP验收；P6另有实际浏览器排版和Fig4控制API只读核对，真实新页面仍待部署验收。

## P3 自动轨迹

- [38项读取、页面、缓存与权限检查](p3-read-and-pages.log)，峰值122.04MiB、7.711秒。
- [14项HTTP浏览与原实例管理回归](p3-http-pages.log)，峰值133.13MiB、16.795秒；4097父引用慢测仍单列。
- 两类页面使用同一只读服务；旧合同无法证明匹配审查时保留普通历史链接并标明缺口，不重验科学输出。
- 元数据轮询不读成果；封存结论只在选中节点读取。观测时间与原记录时间区分，缓存丢失不补造历史。
- 精确node支持原Run分页诊断、原生计算观测与恢复两标记；新旧Agent的Run错误不会按Agent身份合并。
- 缓存是独立UI数据库，没有新科学Run或摘要任务；缺失/损坏只影响显示。

## P4 有界推送

- [17项HTTP、SSE与锁边界检查通过](p4-stream-and-lock.log)，[峰值128.09MiB、9.954秒](p4-stream-and-lock.json)。
- 浏览器断线游标优先使用 Last-Event-ID；每次连接有界退出，慢连接不持有控制锁。
- 元数据通知、普通页面回复和原件传输均在释放控制读取锁后写入网络；其他实例的控制操作不被长连接占用。

## P5 维护、迁移与恢复验证

- 归档、恢复和实际写入边界分别由两个执行者实现；主执行者负责管理入口、部署权限与整合验证。
- [原写入边界86项通过](p5-writer-second.log)，1项既有L2夹具失败单列，79.973秒、332.59MiB。
  覆盖Root、Worker、收集监督进程、旧实例缓存与恢复预算；维护拒绝不写成Run失败。
- [维护门和活动分配器27项通过](p5-gate-and-allocator.log)，5.139秒、117.9MiB。Run库新增
  `run_activity_sequence`是全局机械分配元数据：七处活动写入仍在原事务内，不改变科学模型，
  不随实例归档或覆盖恢复，避免其他实例复用已归档事件编号。
- [R2候选84项通过、2项失败](p6-archive-r2.log)，41.751秒、188.05MiB。共享原件、原子recovery
  发布/退休、实际进程退出中断、事务/触发器、旧审批只读、恢复权限及其他实例大历史均有实际检查。
  两项失败发生在新hardened接续夹具尚未归档时：旧写文件helper与当前Operation文件政策不符；
  已仅修测试对现有文件合同的调用，未放宽生产政策。
- [随后86项通过、2项失败](p6-archive-final.log)，34.181秒、200.88MiB。剩余失败暴露无可选审批/执行
  服务的合法runtime在overview读取None；现已返回明确展示缺口，不把其他分支推定为完整唯一分支。
- [最终20项通过](p6-final-recovery.log)，9.761秒、133.75MiB，覆盖上述两个失败和最后暂存恢复修正。
  两个hardened用例实际完成保全草稿、归档、浏览、恢复、原resume/变更输入draft的预检与调用，
  新Worker打开新assignment后仍获得原草稿和精确输入。变更输入的resume仍被原规则拒绝。
  第二次归档恢复继续保留非空producer/consumer及resume/draft关系，不只检查空节点。
- 独立[R1](../../reviews/INSTANCE_RESEARCH_WORKBENCH_IMPLEMENTATION_R1_REVIEW_20260914.zh-CN.md)
  与[R2](../../reviews/INSTANCE_RESEARCH_WORKBENCH_IMPLEMENTATION_R2_REVIEW_20260914.zh-CN.md)
  的失败记录保留；短排他锁、共享目录原子发布/退休、精确暂存目录收尾及恢复接续已由R2复核闭合。

## P6 已取得的工程证据

- [81项UI/只读/API/SSE/原审批渲染回归通过](p6-ui-final.log)，14.387秒、143.04MiB。
  后续有界诊断及概览小修另由[23项读取/页面检查](p6-read-final.log)覆盖。
- [30项原接续与用户文本回归通过](p6-original-continuation.log)，20.318秒、132.95MiB。
  包括原结果、变更输入draft、复用Worker打开新Run、选择性status及用户原文绑定；保留既有弃用警告。
- [源码45项合同](FINAL_CONTRACTS.json)与[可选figure的50项合同](FINAL_CONTRACTS_OPTIONAL_FIGURE.json)
  分别与P0原始快照逐字一致，包含Operation spec/digest和两种Root及Worker工具Schema。
- [四个wheel隔离安装](p6-installed-wheels.log)通过，15.24秒、394.68MiB。临时venv不使用系统site-packages，
  实际发现两个UI提供者、读取安装后静态资源并归档浏览恢复；原UTF-8附加文本经过Root/Worker stdio完成
  两轮提交及Worker复用。是合成控制链，不是新科学Agent。
- [最终修正后四wheel复验](p6-installed-final.log)通过，15.3秒、394.59MiB：重新构建、隔离安装，
  再次核对50项合同、两个展示提供者、CLI参数、静态资源、归档浏览恢复和两次stdio接续。
  原候选日志保留，临时安装已清理，未更新运行中的服务。
- [等效权限挂载沙箱](p6-permissions-sandbox.log)通过，1.815秒、107.68MiB。实际bwrap只读挂载项目与
  源码，仅state、local workspaces、archive/instances可写；两次归档、原件读取和恢复通过，
  对源码/工作区写入的负控成立。该检查不等同真实systemd单元启动。
- [最终静态检查](p6-source-final.log)通过：变更Python语法、部署脚本语法、diff空白检查、
  45/50合同字节一致及R3计划摘要均正确。文件身份见上述最终源码清单。
- [实际Chromium最终页面检查](browser-final.log)通过，3.626秒、471.88MiB：1280/768/390像素，
  中文可读、长参数表/长引用有界与原件入口、图片加载、原生维护表单、JS无错误，原审批保持pending。
  参数报告值已改为值/单位/条件和来源链接，原机械source字典不再成为表格正文。
  [审批](browser-approval-wide.png)、[参数表](browser-parameters-wide.png)、
  [窄屏](browser-approval-390.png)、[轨迹](browser-trajectory-wide.png)、[管理](browser-management-wide.png)。
- 浏览器早期两次准备环境触发512MiB预算守护（见`browser-layout-second/final.json`），进程树被停止，
  未提高预算；通过减少测试环境加载与限制Node heap完成后续验收。另有两次UI夹具/预览行数断言失败，
  原日志保留。临时Playwright/字体配置不进入产品依赖或发布包。
- [当前Fig4控制API只读核对](FIG4_READONLY_CONTROL_CHECK.json)确认原实例及封存节点仍可读；
  未创建Run、审批决定、执行或归档。新工作台尚未部署，不能据此称真实Fig4页面已验收。
- [既有L2失败在精确Git基线复现](p6-baseline-fixture.log)：`_catalog(require_current=True)`旧夹具去掉
  user_context输入而保留输出context_sources，编译报`output_context_invalid`，本次未改相关合同或夹具。
  [原始失败](preexisting-l2-baseline.log)保留；这不是本轮新增回归，也不是已修复的测试。

## 可部署范围与明确限制

- 首版没有永久删除，不修改VM runner或远端文件；只移动可精确归属的本地实例资料。
- 目标控制记录快照上限32MiB、单个控制载荷读取上限16MiB、目标文件清单50,000项。其他实例资料流式读取；未知共享引用保守保留，
  不按目录相似性猜归属。上限属于存储维护，绝不变成科学Operation准入条件。
- 所有受控写入服从维护门；任意外部程序并发裸改state不在该协议的保证范围。
  CAS与共享recovery采用现有不可变发布语义，完整内容验证在全局排他锁外完成；最终切换须用同一只读
  SQLite连接的data_version票据复核扫描后的提交变化，不以文件时间戳代替数据库版本。
- LocalTrusted历史Run不能单凭terminal证明原生写入者已停止；未知时预览busy并保留现场。
  当前Fig4属于该范围，不能宣称已验证其归档；普通科研调用和工作台阅读不受此维护限制影响。
- 正式部署、实际systemd单元、两类真实Fig4审批及真实科学接续仍为现场项；等效文件系统权限验证已通过。
  回滚前使用新版恢复已归档实例，或明确保留为旧版不可续跑的离线资料；不能删除维护日志强行开放。
