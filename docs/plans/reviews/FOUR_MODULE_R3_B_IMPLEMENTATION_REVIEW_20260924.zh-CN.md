# R3 B TCAD 配置自主执行候选：独立静态审查

## 结论与精确候选

**结论：REQUEST CHANGES。4 项 P1、2 项 P2；当前候选尚不能作为 R3 B 完成交付。**

本审查只覆盖 R3 B 的真实入口、授权、预算、调试恢复、文件通路和 runner 约束，不重复 A 或历史清理审查。审查者未修改实现。遵守串行和 OOM 限制：没有执行测试、pytest collection、catalog 编译、项目动态导入、安装、构建或 solver。禁测本身不是本报告的阻断理由；以下发现均有静态可达路径。

- 审查日期：2026-09-24。
- 仓库：`123/scidiscovery-e5.2`，未提交工作树，包含既有清理与 A。
- 作者候选清单：`/tmp/scid-r3-b-candidate.json`，41 个文件；清单 SHA256：`a09929017613abac22ad09ca342b856f063c3b2a278487647ee9ad051584ebb6`。
- 审查时逐项重算 41 个文件 SHA256，全部与清单相同。清单中的作者 AST/JSON 检查是作者记录，不代表审查者执行了行为验证。
- 本报告不继承 R2 或 A 的审查结论，也不授予运行资格。

下文路径均相对仓库根目录；行号对应上述候选及末节列出的上下游文件。

## 发现

### B-R1 / P1：预算归属随项目修订变化，失败修复仍能获得完整新额度

**位置：**`plugins/tcad_artifact/tcad_artifact/execution_policy.py:84–92`；`src/scidiscovery/artifact_agent/service/executions.py:457–462`；调试对应 `plugins/tcad_artifact/tcad_artifact/local_debug_service.py:119`。

`reviewed_admission` 用整个 `project.model_dump()` 加 resolved inputs 计算 budget_key。项目源码、诊断、资源声明发生变化，key 就改变；控制层只有 `(executor, budget_key) -> execution_id` 的占用表，没有研究任务的累计耗时/预留额度账本。它防住了同一项目只改 execution 名称，却没有覆盖公开的 `tcad.deck.author.runtime-failure.v1` / revise 生产路径。

**可达场景：**同一科学骨架的运行在接近 3600 秒后失败，runtime-failure 作者修正源码并经新审查封存。下一份 package 的 project hash 不同，`authorize_policy` 为新 key 插入新 owner，再次获得 3600 秒。反过来，仅希望以相同项目消费原任务剩余额度时，新 execution 被永久 owner 冲突直接拒绝。调试账本还把 operation_id 纳入 key，initial → revise/runtime-failure 也会切换额度池。

**影响：**“修订必须获得新身份”与“恢复不能重置累计任务额度”没有同时成立；当前实现不能满足 R3 B 的稳定预算归属和累计恢复语义。

**最小修复：**由控制层从精确科学主体与修订/恢复父链派生稳定预算 owner，单独保存每次 submission 的预留/已耗额度及剩余额度；新项目仍保有自己的不可变身份和独立审查。initial/revise/runtime-failure 共用所归属任务的调试额度，新增科学任务才建立新 owner；不能简单删除 project hash 的安全校验或把历史审查继承给新项目。

### B-R2 / P1：大输入流式适配器未接通正式 package 生产路径

**位置：**`plugins/tcad_artifact/tcad_artifact/operation_transforms.py:503–514`、`:108–114`；`plugins/tcad_artifact/tcad_artifact/transform_adapter.py:199–206`；`plugins/tcad_artifact/tcad_artifact/project_packager.py:891–894`。

新 adapter 的 `prepare_with_artifacts` 可以按 `reviewed.resolved_inputs` 从 CAS 分块取文件，但公开 `tcad.reviewed-deck-package.v2` 仍没有科学文件的精确引用输入；`package()` 只转交 project/review/capability/experiment_plan。`package_reviewed_project` 构造 `ReviewedDeckPackage` 时不传 resolved_inputs，得到默认空元组；schema 同时要求它覆盖每个 input_slot。

**可达场景：**当前 SDevice 详细计划路线中的项目声明外部 device_grid input_slot，独立 review 通过后调用正式 package Operation，尚未进入新 adapter 就报 `reviewed deck package must resolve every project input slot`。此外，唯一显式 device_grid 作者端口仍在 `plugin.py:480–487` 固定为 64 MiB；调试 `_candidate` 在 `local_debug_service.py:480` 仍整块 `read_input`，不能据新的 adapter helper 宣称大输入端到端贯通。

**影响：**流式 archive/SSH/CAS 的后半段改动不能使真实 SDevice 大输入路径可达；这属于 B 承诺范围内尚未补齐的现存断点，不认定为本次新引入的旧路由回归。

**最小修复：**在正式合同中声明并绑定所需科学文件的精确 Artifact 元数据/引用，由控制层校验并封存 resolved_inputs、父链和审查关系，再以文件流交给 adapter；同步适用作者/调试输入路径及其实际字节额度。不要把 2GB payload 放入 transform 的 bytes tuple 或将全部模型消息上限放大。

### B-R3 / P1：调试持久账本缓存了成功响应，却丢失最终封存所需的可信记录

**位置：**`plugins/tcad_artifact/tcad_artifact/local_debug_service.py:125–138`、`:171–172`、`:416`；`src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:322–326`；`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:691–698`。

账本只持久化 debug_policy/reserved_wall_seconds/runs/reservations。成功采集产生的 finalization_records 只留在进程内，而已持久化的 runs.response 在下一次调用会直接返回。真正 `worker_submit_result` 只从进程内 finalization_records 提供 trusted_tool_records；finalizer 还要求精确当前 run_id、operation_id、project 和 declarations 身份。

**可达场景：**成功 preflight/initialization 后 Worker MCP 进程重启，重新打开同一 Run 并轮询原 run_name。服务从账本恢复“已成功”响应，却不重新构造可信记录，提交结果报 trusted development record missing。以相同主体恢复到另一 Run 时，还可能返回只存在于旧工作区的路径，或携带旧 run_id 的记录。

**影响：**预算已经被保留/消耗，原任务不能通过轮询恢复封存；若额度耗尽，只能被迫另起不合规预算或停在工程错误，违背恢复复用目标。

**最小修复：**把预算账本与可恢复的执行/采集凭证分开保存。恢复时通过原 submission、文件 hash 和控制层恢复关系重建本次可用的 trusted records/工作区文件；保持原科学产物和 Run 身份，不将旧响应直接当作新 Run 的证明，也不要靠重跑 solver 修复记录丢失。

### B-R4 / P1：process_log 路径被提前当作镜像，既漏计存储又可能采集失败

**位置：**`plugins/tcad_artifact/tcad_artifact/worker.py:188–192`、`:323–347`；远端 `remote_runner_py36.py:737–741`、`:871–898`；上游 `project_materializer.py:455–458`。

存储扫描按 expected_outputs 的 `capture=process_log` 将目标路径无条件排除，而采集阶段才会把 `worker.log` 复制到这个路径。当前仍支持的 `collect_generated_outputs=false` 路线使用 `<entrypoint stem>.log`，求解器可以正常写出自己的同名日志。该文件在求解期间并不是 stdout 镜像。复制此次又从原子替换改为 `open(..., "xb")`，已有文件会导致 FileExistsError。

**可达场景：**合法 deck 为 `main.cmd`、关闭 generated collection，求解器生成 `main.log`。这份实际日志在整个存储监测期间不计费；结束时 stdout 复制遇到已存在 `main.log`，输出收集记录失败，成功 solver 被标成失败。两端实现相同。

**影响：**任务总存储额度可能被日志突破；已有合法执行路线的成功终态回归。无需恶意写文件即可触发。

**最小修复：**将控制层 stdout 镜像放到明确保留且不会与 solver 原产物冲突的路径，并在写入后以实际身份识别镜像；运行期间对 solver 所写文件全部计量。镜像采集用受校验的原子流式发布；不能仅改成无条件覆盖并丢弃真实 solver 日志。

### B-R5 / P2：effect 预检与 invoke 没有复用策略判断

**位置：**`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:244–261`；`src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py:142`。

preflight.prepare 仅处理 agent 和 approval 的专用预备检查，effect 直接返回 bound；新的 execution_bridge.validate_request / execution_admission 只在 invoke 的执行创建路径调用。

**可达场景：**精确 package 通过编译和科学输入检查，但管理员设置 deny 或 runner transfer 能力低于请求预算。相同请求 preflight 返回 admissible，invoke 却因策略/执行能力拒绝；预检不能提供与实际执行一致的自主/人工/拒绝判断。

**最小修复：**提取无副作用的 effect 准入函数供 preflight/invoke 共用，包含精确 payload、能力、策略及 compiled allow_policy_authorization 检查；预检不创建 execution、审批或预算 owner。submit 前的重新判断继续保留。

### B-R6 / P2：调试配置尚有未贯通的隐藏限制和错误模式消费

**位置：**`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:704`；`plugins/tcad_artifact/tcad_artifact/debug_adapter.py:465–470`。

`debug.max_output_file_bytes` 已在 prepare/collect 中读取，但最终封存仍固定 `_read(..., max_bytes=8 * 1024 * 1024)`。例如管理员将单文件限额改为 16 MiB，预算允许的 12 MiB initialization 文件可采集、却不能封存。此外，所有模式的最终文件总量仍以 `self.policy.smoke.max_output_bytes` 校验，配置较大的 initialization 输出额度会被 smoke 的较小限额再次拒绝。

**影响：**JSON 接受配置不等于配置实际生效；用户明确要求可配置的调试限制仍存在第二套隐藏阈值。

**最小修复：**将冻结的实际模式/交付额度传至采集和最终验证消费点；小 JSON、模型响应、可信文件封存分别保持具名边界。不要将 finalizer 的读取上限直接改成无界，也不要以 smoke 值替代 initialization 策略。

## 已核对的边界与仍待运行验证的内容

- `AgentExecutionPolicy` 的 storage/wall 比较包含等号，默认示例为十进制 2,000,000,000 与 3600；enabled/outside_limits、missing/非法字段有显式处理，没有静默迁移旧配置。
- compiled `allow_policy_authorization`、Root → Bridge → ExecutionService 中的 policy/human 分支及 human sealed decision 校验已静态追踪。策略记录未伪造 HumanDecision；状态字段经 read model 的 `asdict` 能带出授权来源。
- submit 会重新取得策略；已记录 prepared submission 时优先查询可能已接受的原任务。其余 crash window、真实重复请求和远端重启行为仍需后续验证。
- job wire 两端均为 4；请求有 total storage 声明；runner 使用目录采样、观测高水位和进程组停止，未声称严格磁盘配额。B-R4 是实际计量遗漏，不能用“采样可能超调”解释。
- 输出端 hash/SSH download/CAS `put_file` 已采用分块路径；输入 archive 的核心读写已分块。B-R2 是正式输入生产合同尚未接通，不能以这些局部实现证明端到端通过。
- 配置样例和 setuptools config package-data 已检查；未实际安装。新 policy 模块位于现有包发现范围。
- 当前新增策略测试主要覆盖纯 admission 数值判断；未运行。解除禁测后应优先补上述真实入口/恢复/文件路径负例，用小额度资源验证，不重复安装业务矩阵，不自动启动全套测试。
- 未验证真实 solver、远端 SSH、进程树停止、大文件峰值内存、吞吐、故障恢复；本报告只能对代码路径作静态结论。

## 补充上下游身份

以下文件不在作者 41 文件清单内，但直接参与上述真实路径；记录其审查时 SHA256，以免后续引用报告时混淆候选。

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | `0b85d9a48b7862c5d889b8ce9f894dda784caa7c610f54d32ee6d9e8e032f7b4` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` | `c1d534eda9eda0ec7414be54e059317db993a86080326254d0dd498fb5e2b734` |
| `plugins/tcad_artifact/tcad_artifact/operation_transforms.py` | `060c2d6d48f84ec2fc9d1087745ea7db5442a35610236884aca7637b18fd8f98` |
| `plugins/tcad_artifact/tcad_artifact/transform_adapter.py` | `3bc1cdde6ab4c8c98b22c885a2d0d804c9942fcc1dfe39aaf92e1847eed14d8f` |
| `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` | `28fc9d7941d8c575db05388f9d1b0478a3161f28c6612421ed6bbeb405fd3937` |

修订后应重新冻结文件清单，针对 B-R1–B-R6 复审。此报告保留为原候选结论，不原地替换为后续候选的 PASS。
