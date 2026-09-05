# R5-N 通用增量修订运行语义计划

## 状态

实现完成，独立复审通过。触发证据是 M7 实验计划修订连续三次在 900 秒完整对象重写边界内超时；三次 Run 均未形成可供下游使用的密封输出。

## 问题

当前框架保留旧 Artifact 并创建新 revision，但普通 JSON 修订 Worker 的工作目录从空的 `output/result.json` 开始。Worker 必须重新生成完整对象，局部审查意见因此被放大为整份对象重写。TCAD 工程已经通过领域工作区实现写时复制，通用科学对象却没有同等能力。

恢复表面也不一致：失败 Run 可以保存恢复草稿，但通用修订 Operation 继承 `max_attempts=1`，导致 `run_status` 显示可恢复而精确预检必然拒绝恢复。

## 目标

采用一个最小统一原则：

> Worker 增量编辑，控制面发布完整不可变新快照。

不恢复旧的通用补丁 Artifact、补丁应用 Operation、差异收据或万能修订管理器。增量编辑只是 Run 工作区行为；正式科研对象仍是通过完整 Schema 与上下文校验的新 Artifact，旧对象、旧审查和旧资格均不改变也不继承。

## 实施范围

### N1 修订声明收敛

- 继续以输入端口 `usage=revision_base` 作为 OperationSpec 中唯一修订声明，不新增第二注册表或新的科研实体。
- 编译器继续要求修订基对象和主输出具有相同 Schema、媒体类型、编解码器及 Schema 资源。
- 将跨阶段的 `science.evidence.revise-from-critic.v1` 纳入同一修订声明；其精确批判审查来源和父链仍由 `review_signal`、review edge 与既有 cohort guard 校验，具体操作由调度 Agent 选择。
- 全目录验证所有修订 Operation 都能由同一个总函数识别，包括通用证据、假设、实验以及 TCAD Deck/运行失败修订。

### N2 写时复制工作区

- 对无领域工作区物化器的修订 Operation，控制面在创建 Run 时把精确基对象的 payload 预置到 `output/result.json`。
- 预置文件使用稳定的多行 JSON；handoff 保持为必须由 Worker 完成的无效草稿，不能原样提交。
- assignment 明示基输入、可编辑目标、写时复制模式和“最终提交仍是完整快照”。
- 对同时声明领域工作区物化器和最终器的修订 Operation（当前为 TCAD），继续由插件把 prior project 展开为可编辑文件并最终组装结果；只有物化器的插件仍使用通用 JSON 草稿。
- 默认 Local Worker 使用现有原生文件编辑做局部修改，不增加新的 Worker 生命周期接口。当前 Hardened 后端没有受控读取预置草稿的工具，因而对直接修订诚实拒绝 `server_file_read`，本阶段不为非默认后端扩建文件协议。

### N3 提交与不可变性

- 最终提交仍执行完整 envelope、payload Schema、领域 validator、上下文 validator、父链和大小校验。
- 修订后的 canonical payload 必须与精确基对象不同；未修改的预置草稿要被明确拒绝。
- 发布的新 Artifact 继续包含完整对象，并以所有绑定输入为父链；旧对象不可原地修改。
- 不创建补丁 Artifact。差异可由基对象和新对象确定性计算，首版不增加第二状态权威。

### N4 有界恢复

- 通用修订 Operation 默认允许一次受控恢复（总尝试数 2）；非修订 Operation 的默认值仍为 1。
- `run_status.recovery_available` 表示失败 Run 仍是有效恢复源：必须同时考虑恢复草稿、Operation、输入、后端身份与能力以及剩余尝试次数。它不替代下一次调用对 current、准入和修订后继等条件的完整预检。
- 恢复仍创建新 Run，使用密封的非科学草稿，不恢复隐藏模型会话。

### N5 模型可见合同

- 通用证据、假设和实验提示改为：从预置修订草稿开始，只修改审查要求涉及内容；提交完整新对象，不输出补丁对象。
- 继续禁止 Worker 修改全局目标、证据边界或未获授权字段；现有上下文 validator 保持最终权威。

## 验收标准

1. 普通 JSON 修订 Run 打开后，`output/result.json` 已含精确基 payload，且 assignment 明示写时复制。
2. Worker 对少量字段增量编辑后可以提交完整新 revision；旧 Artifact 字节保持不变。
3. 原样提交预置草稿被拒绝。
4. 通用证据、跨阶段证据、假设、实验和两个 TCAD 修订 Operation 均被统一识别；TCAD 既有领域工作区行为不退化。
5. 通用修订失败后可恢复一次；尝试用尽、合同改变或后端改变时 `recovery_available=false`；下一次调用仍执行完整预检。
6. 聚焦测试、33 项架构约束检查、全量测试及独立跨边界审查通过。

## 明确不做

- 不重新引入 `StructuredRevision`、JSON Patch 科研 Schema、补丁审批、补丁资格或 Root 级递归修订管理器。
- 不允许 Agent 直接修改已发布 Artifact。
- 不用延长超时掩盖整份重写问题；超时调整只有在增量路径实测后仍有证据时再单独决定。
- 不在本阶段改变审查、人工审批、current 或外部执行语义。

## 实施与验证记录

- 六个已安装直接修订操作均由 `revision_base` 同一总函数识别，并默认获得总计两次尝试；普通操作默认仍为一次。
- 普通 JSON 修订采用预置 `output/result.json`，TCAD 修订继续采用插件领域工作区；两者都只在提交时发布完整不可变 Artifact。
- 本地后端的增量编辑、空改拒绝、旧对象字节不变、恢复一次及耗尽后预检拒绝均有自动化覆盖；强化后端在缺少受控读取能力时会在能力预检阶段明确拒绝直接修订，测试不再借助父测试进程绕过 Worker 工具面。
- 返工后的聚焦回归为 `48 passed`；独立审查者另行复跑两组共 `52 passed`，并确认三项初审问题全部闭合。
- 末轮全量回归为 `316 passed, 1 failed`；唯一失败是整个重构工作树既存的生产 Python 文件数 `184 > 159`。本阶段未新增生产 Python 文件，也未抬高该阈值。
- 独立复审结论为“通过”，记录见 `reviews/R5_N_INCREMENTAL_REVISION_RUNTIME_REVIEW.zh-CN.md`。部署后的真实 Codex 修订 Agent 实测留作恢复科学闭环时的下一项验证，不伪装成本轮已经完成。
