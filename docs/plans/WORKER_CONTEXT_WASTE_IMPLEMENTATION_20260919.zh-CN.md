# Worker 上下文浪费修复实施记录

日期：2026-09-19。状态：源码五项修复已实现，定向测试与隔离安装通过；真实 Worker A/B 和生产部署加载仍待验收。

## 范围

按[修复计划 R1](WORKER_CONTEXT_WASTE_REPAIR_PLAN_20260919.zh-CN.md)实施。未修改科学 Schema、科学准入、审批、恢复预算或 Worker 复用条件；未执行 Fig4、TCAD、生产部署、Git 提交或推送。工作树包含其他既有修改，本轮以 [before 清单](evidence/worker-context-waste-20260919/baseline.json)和对应快照界定，不能按整个 HEAD diff 归因。

## 实现

1. S1：安装独立 stdlib `tools/read_input.py`。按文本或 JSON Pointer 读取，目录模式只列直接键；默认完整回复 4 KiB、最大 8 KiB。数字保留词形，分页带版本，拒绝跨文件系统边界与过期续读。旧 Workspace 可继续标准库定向读取。平台指引覆盖所有 Local Worker 角色，仍可按需读完整原件和总体目标。
2. S2：analysis launcher 默认 summary，显式 `--display raw` 供 stdout 数据消费者使用；inherit 默认保留 raw。日志原有留存上限、argv/stdin、退出码和进程组处理不改。摘要分别报告总量、保存量、展示片段和日志路径，不把错误关键词当根因。
3. S3：TCAD author 从短返回的 details_path 定向读 `/progress/log_tails`、`/log_excerpt`，再访问 log_relative_path。角色包同步消费修改，影响 tcad.deck.author.initial.v1、tcad.deck.author.revise.v1、tcad.deck.author.runtime-failure.v1 的角色合同；旧冻结 assignment 不重写。
4. S4：Local open 从当前冻结 role_instructions 计算 SHA256。只在全文仍保留且身份一致时允许省去角色重印；首次、变更、失忆仍重读，每轮任务、输入/总体目标、语言和预算必读。哈希不是已读证明，不改变身份与独立审查边界。
5. S5：常规 run summary 保留恢复覆盖、遗漏数量及原因类别；完整清单仍在现有 detail，历史缺字段和损坏恢复不会冒称完整。
6. 计量：既有 probe_request_usage.py 增加 `--native-trace TRACE OUTPUT`，逐 response 去重，记录相邻请求变化和可观测压缩事件；缺失 usage、模型不符标无效。只导出计量/读取元数据，不导出隐藏推理、科学正文或工具正文。

## 验证及实际失败

测试全部串行，用现有 run_process_group 采样保护，预算 768 MiB；它是进程树采样停止机制，不是 cgroup 硬隔离。未跑全量测试或并行模型。

| 检查 | 结果 | 峰值 / 耗时 |
|---|---|---|
| input_reader + output_schema_reader | 11 passed | 54.88 MiB / 0.77 s |
| local_process_observation | 13 passed | 91.97 MiB / 3.41 s |
| TCAD 详情读取、agent execution settings、MCP response views、analysis evidence recovery | 76 passed | 255.66 MiB / 44.29 s |
| 原生计量、生成平台配置、历史合同兼容、真实 stdio Worker | 首轮 7 passed、1 个旧文字断言失败；修正后该项 1 passed | 首轮 185.77 MiB / 5.03 s；复测 96.85 MiB / 1.39 s |
| 计量缺字段及压缩事件补测 | 1 passed | 48.68 MiB / 0.44 s |
| 确定性展示回放 | 通过，原文/退出码保持 | 63.42 MiB / 0.47 s |
| 三个 wheel 构建与隔离安装 | 通过，核对 7 个文件，安装后 helper 可独立运行 | 97.04 MiB / 4.27 s |

初轮 helper 测试发现负偏移诊断顺序和测试 Run 名格式问题，均已修正后通过。生成配置失败是当前指南已采用 `invoke the immutable request`，旧测试仍要求 `same immutable request`；修正断言同时增加所有角色的 reader/目标入口检查。离线回放脚本两次加载失败分别因 /tmp 入口未给源码 PYTHONPATH、旧文件按无 package 名导入；修正运行环境和相对 import 名后通过，不归因于科学 Worker。既有 recovery 测试产生 datetime.utcnow deprecation warning；本轮未修改其行为。

追加测试结果见 evidence 目录 tests.json；测试组可能重叠，不累加为唯一测试数量。

## 展示量对照与含义

[确定性回放](evidence/worker-context-waste-20260919/deterministic_playback.json)：

- 单次日志回复 136,094 → 1,027 字节。两条原始留存日志 SHA256 与字节数相同，退出码同为 3。
- 恢复 summary 45,626 → 311 字节；detail 保留原清单。
- 63,044 字节原件分页后单次回复峰值 4,096 字节，19 页精确拼回，无重复原文；总回复 76,135 字节，增加的是分页元数据。不能将此描述为总 token 已下降。
- [旧真实 Worker usage 回放](evidence/worker-context-waste-20260919/native_baseline_replay.json)仍为 21 次请求，初始 22,521、峰值 67,196、净增 44,675，仅证明计量口径可复现旧记录。

这些是确定性字节量和旧样本回放，不是修复后的真实 Worker token 收益。

## 独立审查与剩余验收

[独立实施审查](reviews/WORKER_CONTEXT_WASTE_IMPLEMENTATION_REVIEW_20260919.zh-CN.md)未发现阻断性源码问题；指出的计量压缩事件/缺字段边界已补齐并定向复核。该结论不替代行为验收。

1. 需要安装控制端与重新生成 Codex 配置；重新启动相关服务/会话后核对加载指纹。TCAD VM 本轮没有改动，不需要同步 runner。旧运行中的科研 Worker 保持冻结合同，旧 Workspace 不假装升级。
2. 部署后用已确认的 native spawn → identity → attach → open/submit → sealed completion/usage 路径做 S1 一对真实 review 和 S4 一对两 Run 接续。固定前后源码、材料、任务、sol/medium、预算及各自新 Agent；不得将当前 after 与不等价历史样本直接拼成 A/B。
3. native 进程树硬限制未覆盖。模型测试串行，单组 600 秒，不自动延长；若必须硬限才可执行，则保持待验收。实际 usage 缺失或模型不符不出收益结论。
4. 本次隔离安装只证明包内容和可运行入口，[隔离安装记录](evidence/worker-context-waste-20260919/package_check.json)不证明生产加载，后者尚未核对。

所有旧原件与新增完整错误定位仍可读。当前可以进入安装与实际行为验收，不能宣称五项真实科研行为均已关闭。
