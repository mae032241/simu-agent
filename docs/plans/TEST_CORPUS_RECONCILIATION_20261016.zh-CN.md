# 项目缺口与测试清理收口（2026-10-16）

基线 `5251ee05c029774200d77a07bb9f69e403dc22bf`，分支 dev。用户授权独立评估项目及测试、删除过时无用测试。本轮不启动真实模型，也不把删除失败测试作为验收方法。

## 权威与分工

生产代码、已发布入口及当前合同决定行为；历史审计只说明当时的候选。两个独立审查分别评估项目缺口、测试有效性；另一执行者实施测试清理，测试审查者复审实施差异。README英中和文档入口明确区分新 CLI 与现存 MCP 服务。

- [测试过时审计及逐项删除依据](evidence/TEST_OBSOLESCENCE_AUDIT_20261016.zh-CN.md)
- [项目缺陷与产品缺口独立审计](evidence/PROJECT_DEFECT_AUDIT_20261016.zh-CN.md)
- [实施后独立评审：局部PASS，保留整链阻断](evidence/TEST_CLEANUP_INDEPENDENT_REVIEW_20261016.zh-CN.md)
- [清理清单与代码差异指纹](evidence/TEST_CLEANUP_INVENTORY_20261016.json)

## 已实施

1. 删除无消费者的 R5 结构统计脚本与两个 JSON 快照、旧 R3 测试配置。
2. 删除退役 R5 case replay 插件、历史任务夹具及其唯一自测。其 manifest 明示不是当前资格；当前插件动态加载、执行审批及恢复测试保留。
3. 删除12个无调用 helper 及无用 import。独审曾发现其中一个 helper 的三处残余导入，已成组清除并单独验证收集，不隐藏这次修复。
4. 修正 `test_native_cli.py` 的当前角色载荷与父视图断言，保留 HWA、pause/continue、只读status、非法enum和篡改拒绝。
5. 日志游标与执行缓存测试在内部 facade 验证文本缓存，另断言 Root 公共响应不含文本；追加、轮换、溢出和不触发远端读的断言保留。

全树静态 test 函数数由3127减为3126，仅删一项历史夹具自测；不是参数化后 pytest 用例总数。约3000行删除主要来自退役脚本、夹具和死helper。

原文件可用 `git show 5251ee0:<旧路径>` 查看。未改写历史审计、未删除既有未跟踪证据目录。仍注册的 MCP/UI/TCAD、旧协议只读和不确定副作用恢复测试不因年代被删除。

## 验证与保留失败

所有执行验证经过资源监督与串行锁；没有生产实现修改。

| 验证 | 结果与范围 |
|---|---|
| operations六文件 | 初次79通过、1失败；唯一失败为Root文本展示失配，修正层级后单点1通过。没有冒充整批重跑全绿 |
| 三处helper消费者 | collect-only收集18项成功；仅证明收集可用，不等于18项执行通过 |
| 执行日志缓存 | 同类表面失配修正后单文件4项通过；公开元数据/隔离与Worker分页覆盖保留 |
| native CLI进程层 | 5通过、10排除；与源码层分开 |
| native CLI源码层 | 旧协议载荷错误已修；最终一次3失败、7通过、5排除，均保留封存竞态失败。未重跑碰运气、未放宽或删除测试 |
| 静态差异 | 全树测试AST只少指定1项；删除helper后无残余引用；diff check通过 |

原始日志目录：`/tmp/scid-cleanup-operations-source-1016`、`/tmp/scid-tail-cursor-source-1016`、`/tmp/scid-cleanup-collect-consumers-1016`、`/tmp/scid-native-cli-process-1016`、`/tmp/scid-native-cli-source-1016-d`、`/tmp/scid-execution-log-cache-source-1016`。没有全库、安装包或真实模型通过结论。

## 审计发现及后续修复状态

- W封存竞态已由 `4f77574` 修复，独审通过。上表保留修复前测试记录；新负控和修复验证见 [B3/B1评审](evidence/B3_B1_INDEPENDENT_REVIEW_20261016.zh-CN.md)。
- 发布扫描误拦已由 `3d2cc89` 修复；依赖闭包由 `d2e29e2` 修复并独审通过，见 [B2评审](evidence/B2_RELEASE_CLOSURE_REVIEW_20261016.zh-CN.md)。初审发现的canary遗漏及文档断链也已关闭。生成树73项定向源码与3项离线安装通过，完整收集不等于全套执行通过。
- 通用受管执行已支持，但通用指标没有自动成为具备评价口径和精确工件的候选；比较、短名单及交付链尚未完整。不能宣称通用科研插件平台已全部打通。
- 其他未完成能力与未验证科学收益由独立项目报告列出，不与确定代码缺陷混合。

后续新增缺陷见[继续审计清单](REMAINING_FRAMEWORK_BUGS_20261016.zh-CN.md)；通用候选闭环单独设计。B1/B2/B3修复不等于其他问题关闭。
