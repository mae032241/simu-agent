# TCAD Deck 文件沙箱重构计划与实施记录

> 已被 [Subagent 任务绑定读写机制重构](SUBAGENT_TASK_BOUND_FILE_IO_REFACTOR.zh-CN.md)
> 取代。下文保留为历史设计记录；当前 subagent 对物化路径只做原生读取，所有
> deck 变更均由 task/session 绑定的 Worker MCP create/apply-patch/move/delete 接口执行。

## 目标

本轮重构解决此前 `DeckProjectPatch`、`DeckFileOperation` 与 worker JSON 上传链路造成的高成本迭代：

1. deck 编写、修订和代码审查使用受控沙箱内的普通文件操作；
2. `tcad_deck_author` 同时负责首次编写和后续修订，退出主流程中的独立 reviser；
3. 控制面负责把沙箱文件树重建为规范对象、校验、冻结、注册和重试恢复；
4. `tcad_deck_reviewer` 只做独立的物理实现与代码逻辑审查，不修改 deck、不运行求解器，也不扩张输出合同。

Alpha 阶段的判据是缩短“代码诊断 → 局部修订 → 同一候选复测”的闭环，而不是继续完善中间 patch 表达能力。

## 当前架构

每个 deck 任务由控制面物化以下目录：

```text
<state>/workspaces/ses_*/
├── deck/
│   ├── project.json       # DeckProjectDraft 的非文件元数据
│   ├── files/             # .cmd/.par/脚本等真实工程文件
│   ├── handoff.json       # author 的有界 verdict/summary/next_role
│   └── README.md
└── output/
    └── result.json        # 控制面生成的 author 正式输出，或 reviewer 报告
```

### Author

- initial profile 从空模板开始；revision profile 从 exact prior project 展开真实文件；
- 使用普通 Codex 文件工具直接修改 `deck/files/**`；
- 同一个目录同时用于 development debug，避免调试候选与最终提交候选分叉；
- 不上传 `DeckProjectPatch`，也不直接写规范 `DeckProjectDraft` envelope；
- validation 时由控制面读取文件、验证安全相对路径和 UTF-8 内容，并重建完整 `DeckProjectDraft`；
- revision 时控制面强制冻结 `tool_profile`、`solver_kind` 和 `capability_sha256`。

### Reviewer

- 控制面把待审 project 展开到只读 `deck/**`；
- reviewer 只读实现文件与 realization manifest，并写 `output/result.json` 中的 `DeckReviewReport`；
- reviewer 不具有 deck 写权限，不具有 development-debug 工具；
- 审查范围限定为物理假设到实现的忠实性、显式代码逻辑错误、manifest locator 可追溯性和既有输出/断言的一致性。

### Control plane

- 拥有任务生命周期、输入展开、路径边界、规范对象重建、schema validation、冻结快照和 Artifact 注册；
- author 校验失败或 lease 重试时保存/恢复 deck 文件快照，而不是要求重新生成整份 JSON；
- 正式输出仍是规范 `RoleResultEnvelope[DeckProjectDraft]`，下游执行与审计无需理解沙箱布局；
- 历史 `DeckProjectPatch` 模型和 deterministic apply transform 暂时保留用于旧 Artifact 兼容，但不在新任务拓扑、角色注册或 scheduler 主路径中使用。

## Codex 权限模型

- 所有 deck 角色从 `:read-only` 权限继承；
- author 只增加 worker workspace 下 `ses_*/deck/**` 的写权限；
- reviewer 只增加 `ses_*/output/**` 的写权限，`deck/**` 仍只读；
- 普通科研角色继续使用只读 sandbox；
- author/reviewer 不再暴露 primary-result chunk upload 工具；reviewer 额外不暴露 TCAD debug。

控制面仍会在读取时拒绝绝对路径、路径穿越、符号链接、非普通文件、非 UTF-8 内容和越界大小；Codex 权限不是唯一安全边界。

## 已完成

- [x] 合并 author/reviser 的角色职责与 context profile；
- [x] `deck_revision` 拓扑改为 `tcad_deck_author -> deterministic diff -> tcad_deck_reviewer`；
- [x] author initial/revision/retry 的 deck workspace 物化；
- [x] reviewer 只读 project 展开；
- [x] 控制面从真实文件重建并冻结完整 project；
- [x] development debug 读取同一 workspace candidate；
- [x] Codex role-specific filesystem permissions；
- [x] author/reviewer prompt 与公共 worker 协议更新；
- [x] initial/revision/reviewer 的聚焦端到端测试；
- [x] 保留旧已上传 author candidate 的迁移兼容入口。

## 验收标准

1. revision author 能看到 prior project 的真实文件，直接改单行并由控制面生成完整 revised project；
2. author 无需构造 `DeckFileOperation` 或上传大段 envelope；
3. reviewer 能逐文件审查，但文件系统拒绝其修改 deck；
4. 冻结 capability 元数据被修改时 validation 必须失败；
5. debug、validate 与 finalize 使用同一文件候选；
6. 主 scheduler、角色注册和新任务 profile 不再派发 `tcad_deck_reviser`；
7. 完整测试套件通过后，重新安装生成的新 Codex agent 配置中不再存在 reviser。

## 未完成缺陷与后续项

### P1：权限目前按角色而非精确 session 收窄

Codex 静态 agent 配置只能预先声明 workspace pattern，因此当前 author 的写规则是
`ses_*/deck/**`，而非仅当前 `ses_<session>/deck/**`。控制面仍串行绑定 worker、校验实际
session 路径并在输出边界重读，但从最小权限角度仍应研究 task claim 后的动态权限注入。
该项不阻塞 Alpha 科学闭环。

### P1：旧 patch 类型仍存在于兼容层

`DeckProjectPatch`、`DeckFileOperation` 和旧 apply transform 尚未删除，以保证历史 Artifact、
迁移测试和旧状态可读。新角色、主拓扑和 Codex 工具面均不再依赖它们。待历史状态迁移窗口
结束后，再做破坏性 schema 移除。

### P1：非 Codex 平台权限尚未等价实现

本轮实现了 Codex 的定向权限配置。Claude 等平台仍需单独确认其文件沙箱是否能表达相同的
author 可写/reviewer 只读边界；在此之前，不把它们声明为该文件工作流的等价实现。

### P0 验收：真实安装后的单次纵向闭环

单元与进程测试只能证明控制面协议一致；重装并重启后仍需完成一次真实
author 文件修订 → debug → reviewer → package/execution → score/diagnosis 的 Alpha 纵向链。
这仍是当前最高优先级验收，不应被上述 P1 加固项阻塞。
