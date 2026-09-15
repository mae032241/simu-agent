# 实例 Agent 执行配置计划 R0 独立审查

2026-09-15。**结论：REVISE。** 一项 P1 计划缺口需补充；没有发现需要改变整体配置归属、增加角色或扩展科学输出校验的理由。本结论不是实现验收，也不授权安装或科研执行。

审查对象：[计划 R0](../INSTANCE_AGENT_EXECUTION_SETTINGS_PLAN.zh-CN.md)，SHA256 为 `0d5693c0b05242f1371512029198fab59bf1aad3c459541328713141db4e0b5d`。仓库 HEAD 为 `da220ce31c8cc9f9a60542a018b279e2f331f4c0`；核查的是当前有既存修改的工作树，不将 HEAD 当作全部代码基线。独立阅读 `scid-cross-boundary-review` 技能并静态追踪代码；未修改计划、运行源码、安装配置或生产状态，未启动科研 Run，未运行测试。

## 必须修订

### P1：旧归档跨新增列恢复缺少可实施的兼容边界

**位置：**计划 P5 第四项（第 110 行），及 P5 实施文件范围。

计划要求新增实例配置列和 Run profile 列，并承诺“旧档缺新增列按默认读取”“导入旧档到新 schema”。现有归档恢复不仅解析行字段，还以封存时的完整 SQLite 结构和实例整行记录作为恢复条件。可空列或读取默认值不能独自满足该路径：

- `src/scidiscovery/artifact_agent/service/instance_archive.py:668` 在恢复预检中比较全部 `sqlite_master` 对象；新增列后即拒绝为 `restore schema differs`。
- 同文件 `:677` 比较旧实例墓碑/原行，`:791` 在提交前再次要求当前实例整行等于旧墓碑或原行。升级数据库添加的配置列、修订号等会使字典不同。
- `src/scidiscovery/artifact_agent/service/instance_archive_records.py:685` 在事务内再次要求结构相等；`:713` 比较墓碑整行；`:738` 提交前再次核对结构。只改恢复预检或读取器仍不能完成恢复。

**可达场景与影响：**先用当前版本归档实例，再升级并迁移活动数据库。旧归档的 schema 与墓碑保持原样，而新活动数据库出现新增列。即使归档原件、科学 Artifact、审批和所有旧字段都未改变，恢复仍会被拒绝。为临时让它通过而删除结构或整行检查，又会削弱现有恢复身份保护。这是计划承诺与现有恢复协议之间必须明确的设计选择，不是单纯补一个字段读取分支。

**最小修订要求：**在 P5 明确只处理本功能已知新增列的旧→新兼容方式，并列入 `instance_archive.py` 的真实恢复路径。原归档及其校验内容保持不变；恢复时仅为这些缺失列形成确定的兼容值/比较投影，保持所有旧字段、墓碑身份、约束、索引和触发器的校验。相同受限规则应覆盖预检、事务写入、提交后重复恢复的判断，其他 schema 或旧字段变化仍拒绝。无需通用迁移注册表、归档重写服务或新数据库。

P6 在已有“旧档恢复”条目下补明两个必要证据：本次已知新增列差异可恢复且重复恢复一致；无关结构差异或旧墓碑字段被改动仍拒绝。恢复后的历史 Run 应继续表示 profile 未记录，不能补写成当前设置。具体辅助函数和 SQL 写法留待实现，不要求在计划中展开。

## 已覆盖的设计与实现检查点

以下不增加阻塞项；计划已有相关目标，实施时须沿实际入口兑现。

| 边界 | 核查与判断 |
|---|---|
| 功能及科学职责 | P1–P4 覆盖公共默认、实例覆盖、语言/model/effort/max_attempts、逐字段继承及页面来源。配置存 scheduler，科学文本由 Worker 生成；不新增语言输出拒绝条件、翻译 Artifact 或角色映射，符合目标。 |
| 预检/调用/幂等 | `mcp_root_operation_routes.py:324` 计算语义名称请求指纹，`runs.py:238` 另算持久 Run 请求摘要；两处均须使用同一有效行为值。`runs.py:154` 会重新调用 `preflight_operation` 构造 bound，配置不能只附在上一份 bound 后被重建丢失。P2 已要求共享解析与贯穿，属于具体实现检查点。 |
| max_attempts 恢复 | `runs.py:1594` 先使用本次显式值、来源 scheduler override，再取原恢复链策略与当前 Operation 限制的较小值。保留“未显式覆盖”与“显式预算”的意义，不能把页面默认或预检展示值无条件变成恢复的新增 override。P1 已要求原语义及不自动扩次，无需新增预算系统。 |
| 单角色领取与跨实例 | `runs.py:1767` 的唯一索引按 operation_digest 限制一个 queued/running Run，作用于所有实例；`:458` 按 Operation ID/digest 选择槽位。两实例同 Operation 的配置隔离验收应串行，保留现有槽位。不要为通过该用例移除唯一索引或建立每模型队列。计划已要求串行，不构成缺陷。 |
| Worker 复用 | `mcp_local_worker.py:354` 在旧 Run 终态后可领取新槽位；`mcp_hardened_worker.py:167` 有独立的重开和传输所有权行为。P3 的配置匹配要求落实于调度分发，模型/effort 不匹配或旧 Agent 配置未知时不复用；语言从新 assignment 读取。无需改变 Worker 权限或让 Worker 自证模型。 |
| 角色身份和生成 | `platforms/codex.py:596` 当前固定写 model，`:359` 安装验证要求匹配编译默认；`operations/catalog.py:748` 的摘要保留 Operation 与 permission 内容。P3 同时改生成与安装验证、保留摘要中的兼容默认且只对 Run 加覆盖，路线可实施。不要把实例设置送入 catalog 编译。 |
| 平台实际配置 | 计划已正确区分请求配置与实际可观察设置，禁止把子 Agent 自述当证据；P0 是先行验证条件。`platforms/codex.py:840` 附近还对平台功能配置有实际入口约束，应从隔离安装入口验证。没有实测便不能宣称同角色覆盖已可用。 |
| UI 与维护 | 现有 `approval_ui/app.py` 提供浏览/管理授权区分、同源与表单保护，`approval_ui/management.py` 使用实例维护边界。P4 要求设置保存沿用这些授权和维护互斥，并比较独立配置修订号，不改变会话绑定或产生审批决定，边界合理。 |
| 历史与提交 | P5 已禁止回填旧 Run、改动历史成果或运行中重新解析设置；两种 Worker 读取已有 assignment 的路径均需保留旧字段缺失兼容。新增运行配置不应成为科学资格检查条件。 |

## 证据范围与未验证事实

重点代码在本次阅读时的 SHA256：

| 文件 | SHA256 |
|---|---|
| `service/instance_archive.py` | `1dd6f72a31510f1c74b3ef9d379d3050e7fdd6112fb51995c5e2af3c319ae853` |
| `service/instance_archive_records.py` | `3ae56a92e885b6c8d6837c1b76ebd4fcec1e117f10b9fb6383ff07880a93784f` |
| `service/runs.py` | `542554128ed0dd429980394ee78aaac0100b639f974a77edcc06f43715994337` |
| `interfaces/mcp_root_operation_routes.py` | `94a74950df3d6443759ae68484ee08851d501fd66c23f24ca9138f1e42ef73cd` |
| `platforms/codex.py` | `51cb3102a004c906eb28980f1e5ca685e34fdc4b75b32c96667a909901120c18` |

前三类相对路径位于 `src/scidiscovery/artifact_agent/`，平台文件位于 `src/scidiscovery/`。另阅读了纯 Operation 绑定、Run records/assignment、scheduler 实例存储、归档读取器及 local/hardened Worker 开启路径。

未验证当前平台省略 role model 后是否接受并真正执行两组模型/推理参数；未获得实际模型遥测；未运行隔离安装、合成 Agent、归档恢复、数据库迁移或浏览器测试。官方能力说明由任务提供，本审查未独立重做官方资料查询，也未把说明当作安装环境实测。上述事实由 P0 和实现后的定向验收确认，不能将本报告理解为这些验证已通过。
