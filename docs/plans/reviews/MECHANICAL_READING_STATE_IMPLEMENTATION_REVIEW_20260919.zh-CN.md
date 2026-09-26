# 读取机械状态内收独立实施审查

日期：2026-09-19。结论：**静态实施审查通过，未发现尚未闭合的正确性或职责边界问题。** 这不是部署或原生模型 token 验收结论。

## 范围与方法

严格比较 `docs/plans/evidence/mechanical-reading-state-20260919/before/` 与当前对应文件：四个生产文件 `service/input_reader.py`、`interfaces/mcp_local_worker.py`、`platforms/codex.py`、`roles/scheduler/dispatch.md`，四个相关测试文件（含补充的 analysis 恢复测试）及中英架构段落。前两个生产文件位于 `src/scidiscovery/artifact_agent/`，platform 文件位于 `src/scidiscovery/`。`local_workspace.py` 与快照一致。本轮没有把整个 dirty tree 归于这次实现，也没有重新审计无关框架。

沿用 scid-cross-boundary-review 技能，检查实际默认 CLI、Python 兼容 API、Workspace 安装入口、open 回退提示、生成角色、导航缓存与恢复扫描边界。审查者未运行任何测试，未修改生产或测试文件，仅新增本报告。

## 审查中发现的问题已闭合

审查曾发现 `read()` 在比较源指纹之前解析所选 JSON：源变化后若字段消失、JSON 损坏或变为非 UTF-8，会先报字段/解析错误，不能给出明确的变化重读提示。它没有混合正文或推进缓存，但不符合计划的恢复说明。

实施方已调整 `service/input_reader.py:198`–`205`：next/repeat 先检查缓存结构及内容指纹，再解析正文；长度检查仍在解析之后。审查者复读该局部和 `test_input_reader.py:213` 起三个变化负例，确认分别覆盖缺字段、坏 JSON、非 UTF-8，以及 next/repeat 都提示 changed/restart 且不推进缓存。**该发现已静态复核闭合**；对应测试运行结果由实施方记录。

## 已核对的关键行为

| 边界 | 静态结论 |
|---|---|
| 默认机械包装 | CLI 使用 `read()`，默认返回精确正文及短 more/end 标记；没有 source/sha256/version/offset 等包装或 fragment 二次 JSON 转义。保留的 Python `page()` 显式偏移 API 不再是默认模型入口。 |
| 正文和选择 | 原始文本直接 UTF-8 解码；JSON 保留 Number 数字词形，正文中的 hash/path/version 不被过滤。多字段按有序编号分别呈现，整份回复共享预算；这是带字段边界的显示，不冒充一个完整 JSON 对象。材料别名/唯一 port 由 assignment 解析，歧义拒绝；`--file` 保留 assignment/schema 等任务文件读取。 |
| 导航和失败 | 状态位于固定 `.read-input/`，只保存选择键、指纹和段范围；每选择独立，Workspace 锁保护读改写，临时文件原子替换。repeat 不推进，restart 从头；损坏/缺失缓存不猜偏移。源变化不拼接不同内容。导航缓存不用于科学提交或资格。 |
| 并发和交付 | 锁只保证段范围推进，不保证 native 回复顺序。生成指引要求同选择顺序读取，丢失最近回复用 repeat，后来调用已推进则 restart；测试也明确检查范围而不承诺交付顺序。无需收悉协议。 |
| 缓存权限和恢复 | 生成指引两处明确仅安装 reader 的 `.read-input` 例外，其他 helper 仍限 scratch。位置避开现有 output/scratch 恢复扫描，测试调用真实 analysis snapshot 验证排除。缓存不随科学输入或恢复草稿进入新 Run。它不是封存原件校验凭据。 |
| 旧 helper 回退 | open 读取实际工作区 helper 标记；缺失或旧版均返回定向标准库读取提示，不热换 helper，不要求模型比较版本/哈希。测试覆盖缺失与存在旧 helper 两类，并检查冻结 assignment/helper 不被改写。 |
| 角色复用 | 只删除 open 角色哈希和提示中的模型比较步骤；保留首次/上下文丢失重读、逐 Run 消费目标/语言/预算等要求。attach、gateway 与 compiled digest 准入代码未改动，没有新角色注册表或读回执。 |
| 最小范围 | 未新增 MCP、Operation、数据库表、科学字段或提交门禁；local_workspace 原有源码复制安装机制可复用。中英架构准确区分分页变化检测与封存原件验证。 |

## 验证证据与限制

实施方报告最终诊断修复后 15 项通过（13 reader、2 实际恢复路径，采样峰值 119.56 MiB），此前 40 项接口/平台/settings 和恢复/schema/architecture 组其余 59 项通过；两条旧角色哈希断言已替换并重跑。以上为实施方提供的结果，审查者检查了新增测试内容但没有独立执行。测试覆盖正文、交错读取、损坏缓存、变化、新 Workspace、边界、并发范围、真实恢复扫描与旧 helper；补充复读了 analysis 恢复测试中角色正文一致、open 无角色哈希、导航缓存不进入恢复草稿或新 Workspace 的断言。部署后一致性仍由实施方验收。

检查了 `replay_reading.json` 的记录：52 个历史片段、49 个唯一选择、`exact_body_equal=true`，完整读取回复为 143,831 → 115,212 字节。该文件明确是离线回放，**不能据此声称原生模型上下文峰值或 token 已降低**；审查者未重跑回放。

未验证：安装/部署后的全链路一致性、原生模型两轮行为与实际峰值、真实平台回复丢失、进程崩溃窗口及硬内存限制。没有检查或承诺恶意本地进程竞态下的安全沙箱；本改动延续 trusted-local 权限边界，缓存不被提升为安全依据。
