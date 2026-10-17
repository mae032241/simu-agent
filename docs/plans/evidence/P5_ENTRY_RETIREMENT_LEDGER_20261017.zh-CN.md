# P5 旧入口与消费者处置账（独立静态审查通过）

独立审查者 thin_test_review_1017 已核对本表和 ROOTLESS_CLI 新增说明；资源策略示例已按审查修为 allowance 嵌套。该初始静态审查未运行动态验证；后续增量资格见下文，不回写初始结论。

本表基于当前dev源码，决定哪些能力仍有真实消费者。不是已删除清单，不以静态通过冒称新链生产资格。P5已提交纯TCAD导入收缩 `3ac974d`；本轮旧live池的唯一调用已迁移到单环境入口、池及不可达构建选择已移除，已独审提交 `6dcf7ac`，见[实施账](P5_SINGLE_CANDIDATE_RETIREMENT_IMPLEMENTATION_20261017.zh-CN.md)。原浏览/归档纯原语复用分别为 `002284e` / `b01e636`。

| 原入口/能力 | 可见源码消费者 | 薄层替代及当前资格 | 处置 |
| --- | --- | --- | --- |
| pyproject `scid` → artifact_agent.interfaces.cli | progression、instance-create/list/close、ingest-file/artifact-catalog/approval-status、旧UI | scid-research已有新实例/预算/角色调度；不读旧SQL/Artifact身份 | 暂留旧实例入口；新项目采用薄CLI。不能删整个cli顺带删除旧档案消费者。 |
| RootToolFacade / RootMCPRouter | interfaces/mcp.py构造；interfaces/__init__.py重导出；旧cli progression、close及原件查询 | 薄CLI无Root，功能插件另经注册，不调用此facade | 当前无证据证明旧MCP消费者已退出，暂留；不得把它接回新链。 |
| ApprovalUI / InstanceReadModel / TrajectoryStore | 旧cli serve-approval-ui直接构造，承载旧审批/实例档案 | 新instance_ui已独审提交a5c3fbe，只读状态/暂停继续/可选执行决定；未浏览器验收 | 新实例用新UI，旧档案与尚未迁移执行仍保留旧UI。两套身份不互换。 |
| 旧InstanceArchive及SQL/CAS reader | 旧serve-approval-ui注入InstanceArchive及旧runtime maintenance | archive_io纯函数已共享；新只读包P4c1已静态独审提交(799036e)，无可写恢复 | 暂留旧reader/export；不为删除旧代码伪造可写恢复。 |
| 旧TCAD execution_bridge/runtime adapter | 旧完整experiment/remote授权和执行路径 | managed注册、原调用恢复、来源/正式review/资源gate及非空input(4399149)已静态接入；迟批恢复已静态接入(9405b03)，真实solver资格未完 | 复用adapter与纯compiler，不删除仍承担远端生产授权的原入口。缺口完成后再逐消费者收缩。 |
| 旧安装环境与全套功能重跑 | 565a2e4已把pytest安装cohort从功能集合隔离；本轮live唯一调用改用已有单环境入口，旧池已移除（已独审提交 `6dcf7ac`） | 新功能fixture不安装，显式安装组只测打包/发现；live保留明确core/all_domains，pytest仍仅core/tcad | 保留单一显式安装组，不重新引入矩阵/并行安装/功能重复跑；保留TCAD一次依赖解析与all_domains原四wheel/no-deps语义，不把静态迁移当安装验收。 |
| 共享来源/授权/存储/transport规则 | 新薄层及旧入口均使用 | 已抽中立provenance/review/security/browser/archive原语 | 共享规则保留，不能按旧目录年龄删除。 |

## 已退役增量

`513a7b0` 删除两个调用未注册Operation的L4探针及其专用transport、独占测试及发布清单项；3个初始化契约负/正例迁到真实契约owner，串行源码检查通过。见[精确实施范围](P5_OBSOLETE_L4_PROBE_RETIREMENT_IMPLEMENTATION_20261017.zh-CN.md)。没有运行安装、远端作业或整套回归，其余表内生产消费者未删除。

## 后续删除条件

1. 对应薄公开入口及所需真实资格存在，列出待删符号所有生产调用与外部注册；仅同名替代不够。
2. 旧实例至少仍可按原reader检查/导出；不得读取时静默改协议，未知执行不重放。
3. 删除其独占胶水和重复测试，保留共同原件/执行/授权规则。每项独立审查、精确提交，不做整目录清除。
4. 当前资源隔离未确认，不启动安装/HTTP/native/SSH/solver补资格。相关未验收不能靠扩大静态测试数量代替。

目前不能把“所有旧入口退役”标为完成；本表给出保留的具体消费者和解除条件，而不是用历史兼容名义无限保留未使用代码。
