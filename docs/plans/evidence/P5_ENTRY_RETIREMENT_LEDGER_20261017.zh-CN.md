# P5 旧入口与消费者处置账（独立静态审查通过）

独立审查者 thin_test_review_1017 已核对本表和 ROOTLESS_CLI 新增说明；资源策略示例已按审查修为 allowance 嵌套。未运行任何动态验证。

本表基于当前dev源码，决定哪些能力仍有真实消费者。不是已删除清单，不以静态通过冒称新链生产资格。P5只完成了纯TCAD导入收缩 `3ac974d`；原浏览/归档纯原语复用分别为 `002284e` / `b01e636`。

| 原入口/能力 | 可见源码消费者 | 薄层替代及当前资格 | 处置 |
| --- | --- | --- | --- |
| pyproject `scid` → artifact_agent.interfaces.cli | progression、instance-create/list/close、ingest-file/artifact-catalog/approval-status、旧UI | scid-research已有新实例/预算/角色调度；不读旧SQL/Artifact身份 | 暂留旧实例入口；新项目采用薄CLI。不能删整个cli顺带删除旧档案消费者。 |
| RootToolFacade / RootMCPRouter | interfaces/mcp.py构造；interfaces/__init__.py重导出；旧cli progression、close及原件查询 | 薄CLI无Root，功能插件另经注册，不调用此facade | 当前无证据证明旧MCP消费者已退出，暂留；不得把它接回新链。 |
| ApprovalUI / InstanceReadModel / TrajectoryStore | 旧cli serve-approval-ui直接构造，承载旧审批/实例档案 | 新instance_ui已独审提交a5c3fbe，只读状态/暂停继续/可选执行决定；未浏览器验收 | 新实例用新UI，旧档案与尚未迁移执行仍保留旧UI。两套身份不互换。 |
| 旧InstanceArchive及SQL/CAS reader | 旧serve-approval-ui注入InstanceArchive及旧runtime maintenance | archive_io纯函数已共享；新只读包P4c1设计已审，未实现 | 暂留旧reader/export；不为删除旧代码伪造可写恢复。 |
| 旧TCAD execution_bridge/runtime adapter | 旧完整experiment/remote授权和执行路径 | managed注册、原调用恢复、来源/正式review/资源gate及非空input(4399149)已静态接入；迟批及真实solver资格未完 | 复用adapter与纯compiler，不删除仍承担远端生产授权的原入口。缺口完成后再逐消费者收缩。 |
| 旧安装环境与全套功能重跑 | 565a2e4已把pytest安装cohort从功能集合隔离；旧live环境池仍有消费者 | 新功能fixture不安装，显式安装组只测打包/发现，不递归功能测试 | 保留单一显式安装组；不重新引入矩阵、并行安装、源码/安装功能重复跑。旧live池后续按实际消费者退役。 |
| 共享来源/授权/存储/transport规则 | 新薄层及旧入口均使用 | 已抽中立provenance/review/security/browser/archive原语 | 共享规则保留，不能按旧目录年龄删除。 |

## 后续删除条件

1. 对应薄公开入口及所需真实资格存在，列出待删符号所有生产调用与外部注册；仅同名替代不够。
2. 旧实例至少仍可按原reader检查/导出；不得读取时静默改协议，未知执行不重放。
3. 删除其独占胶水和重复测试，保留共同原件/执行/授权规则。每项独立审查、精确提交，不做整目录清除。
4. 当前资源隔离未确认，不启动安装/HTTP/native/SSH/solver补资格。相关未验收不能靠扩大静态测试数量代替。

目前不能把“所有旧入口退役”标为完成；本表给出保留的具体消费者和解除条件，而不是用历史兼容名义无限保留未使用代码。
