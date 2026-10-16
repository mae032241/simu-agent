# 薄控制层能力迁移计划独立审查

## 结论

**PASS：可冻结 P0 计划，进入独立 P1 实施。** 未发现剩余计划阻断。本结论是设计审查，不表示 P1–P5 已实现、真实 TCAD 已合格或新增付费模型/远端计算已获授权。

代码基线为容量修复收口后的 `bbd6cb9`（前序 `e285f17`、`1f7cc56`）。只读对照了当前 CLI/prepare、native 自动配置、experiments.configure/freeze/_adapter、RuntimePluginFactory、TCAD runtime factory、旧 ExecutionBridge/执行授权，以及新旧计划归属。未改实现、未跑模型/solver/测试、未提交；文档差异 `git diff --check` 通过。

## 已收口的设计边界

- **P1 配置入口可执行。** 现在明确 `--execution-config` 的 executor/configuration 形状、默认 local、与 launcher-owned 模式互斥；操作者不能覆盖 scope、record_dir、native_attempt、admission 等宿主身份。prepare 冻结选择与配置，job/native intent 存在后 configure 注入真实绑定，符合当前 configure 的前置条件。配置仅含公开设置，凭据留宿主；验收必须经过安装版 CLI → prepare → native 自动接线，不由 fixture launcher 代接。
- **P2/P3 授权顺序成立。** 异步 fixture 可与来源/资格接口分别开发；真实 TCAD 启用必须先完成所需 P3 授权/资格。查询原未知提交不重发，opaque 不冒认 local result；缺 collect 或原 session 恢复能力明确报告。普通 A 判断不替代正式独立审查，普通无资格要求任务不被强制套审查流程。
- **旧能力复用和退役有明确边界。** 新层继续唯一持有实例、预算、路由和原件；复用原注册、adapter、来源/授权及归档验证原语，不迁入影子 Run/旧调度权威。P5 新增逐入口消费者/替代公开入口/安装及真实资格证据的删除账；仅 TCAD fixture 通过不能删除仍承担真实远端执行的旧入口。
- **未重新引入重控制流程。** 不恢复 LLM Root、MCP Agent 调度或模型机械填表；不重造已验收的通用候选和 wait/reconcile。UI 读取同一实例，写操作依赖授权接缝；浏览器/远端环境缺失保持未验收，不用单元测试冒充产品通过。
- **当前计划归属可解析。** 旧薄交接计划只保留 C0–C2 历史范围，C3–C5 明确链接新计划；plans/README 区分当前入口与较早阶段标题。历史科学/运行报告没有被改写成迁移完成证明。

## 审查快照

| 文件 | SHA256 |
| --- | --- |
| `docs/plans/THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md` | `4658dea45871a7e72ba21185ab12dbd0636254a9e1000d94608d82305dd2bf78` |
| `docs/plans/ROOTLESS_THIN_HANDOFF_PLAN.zh-CN.md` | `3455f1c74eae5067be43d42a82c1534060448c979bb37c6bcb4a60e8b9dbd4b1` |
| `docs/plans/README.md` | `75f0cc89422b92a511bf10f38de04073a9cc3be0ee46a499727524990dcf2f34` |

P1 仍须通过其安装接线/缺失重名/实现替换/旧调用不重发负控；P2 具体适配接口按计划先独审再实现。P3/P4/P5 的授权、浏览器和退役条件保持各自验收，不能由本次 P0 PASS 代替。
