# 读取机械状态内收实施记录

日期：2026-09-19。状态：**源码、定向测试、隔离安装与独立静态实施审查完成；生产部署和原生 C 对照已完成，token 目标未通过。**

依据：[通过复审的计划](MECHANICAL_READING_STATE_BOUNDARY_PLAN_20260919.zh-CN.md)、[方案复审](reviews/MECHANICAL_READING_STATE_BOUNDARY_PLAN_R1_REVIEW_20260919.zh-CN.md)、[实施审查](reviews/MECHANICAL_READING_STATE_IMPLEMENTATION_REVIEW_20260919.zh-CN.md)。变更基线为已有未提交改动之上的逐文件快照，见[baseline](evidence/mechanical-reading-state-20260919/baseline.json)，不是整个 HEAD 差异。没有提交、回滚他人修改或部署。

## 实现范围

- `input_reader.py`：默认 CLI 返回精确正文和短续读标识，去掉外层 fragment 转义、路径、哈希和游标。按 assignment 现有 source_name/唯一端口定位；支持同一材料的多个有序 pointer 和任务内 `--file`。Python `page` 保留原接口供程序调用，正常 Agent 不再使用该机械接口。
- reader 在固定 `.read-input/` 私有目录中维护可丢弃导航，使用本地锁、原子替换；支持 next/repeat/restart。只比较本次读取内容，不冒称封存哈希核验；丢失旧回复可重读，不提供交付确认或已读证明。
- `mcp_local_worker.py`：去掉角色哈希，检查实际安装 helper 能力；旧 helper 或缺 helper 只返回简短定向读取指引，不改写冻结工作区。
- `platforms/codex.py`、`dispatch.md`：取消模型比较角色哈希，沿用控制层复用准入；明确 reader 私有缓存位置例外，保留任务、总体目标、当前输入、语言、预算、输出及恢复要求。
- `local_workspace.py` 未改。没有新 Operation、MCP、权限实体、科学字段或提交校验。中英架构说明同步更新。

## 验证及资源

所有执行串行，通过已有进程树采样 guard 限制在 768 MiB；未跑全量测试、TCAD 或真实模型。

| 检查 | 结果 | 采样峰值 / 时间 |
|---|---|---|
| 初轮 reader | 10 项通过 | 66.07 MiB / 1.12 s |
| settings、生成角色、指南、统一 MCP | 40 项通过 | 311.95 MiB / 19.92 s |
| reader、schema、analysis recovery、架构矩阵 | 初轮 59 通过、2 条旧哈希断言失败 | 243.35 MiB / 62.31 s |
| 修复后 reader 与失败 Run 恢复接续 | 15 项通过（13 reader + 2 recovery） | 119.56 MiB / 3.57 s |
| 相同原件/字段回放 | 正文一致、回复有界 | 44.23 MiB / 0.68 s |
| core wheel 隔离安装 | helper、open 源码、平台源码、指南包内容一致；独立 helper 和生成指引通过 | 96.73 MiB / 1.88 s |

日志位于 [证据目录](evidence/mechanical-reading-state-20260919/)。初轮两条失败为测试仍索取已删除的角色哈希；改为验证角色正文不变、open 不含哈希，并增加真实恢复路径不携带导航缓存的断言，重跑通过。未重跑其余未受修改影响的已通过用例。独立审查发现变化源若不可解析会先报解析错误，现已把指纹检查前移，新增缺字段、坏 JSON、非 UTF-8 三项负例，均通过。

隔离探针初次用了不合法的测试 Run 名，且脚本未转发子进程 stderr；补齐诊断、改为合法 fixture 名后通过，未修改生产身份规则。一次证据整理命令未设置源码 PYTHONPATH，补齐运行环境后通过。上述属于测试/计量脚本问题，不归因于科研 Worker。既有 datetime.utcnow 警告未改。原生模型硬内存限制未验证，不能以本地 guard 替代。

## 展示开销回放

[回放脚本及结果](evidence/mechanical-reading-state-20260919/replay_reading.json)先由保留原件逐一复现 B1 的 52 个实际 fragment，确认内容与既有记录一致；再把 49 个唯一选择分别通过旧、新 reader **读完**，因此完整正文量大于 B1 当时的局部阅读量，不冒充相同原生调用轨迹。

| 指标 | 旧 reader | 新 reader |
|---|---:|---:|
| 精确正文 | 113,805 字节 | 113,805 字节 |
| 回复总量 | 143,831 字节 | 115,212 字节 |
| 正文以外展示 | 30,026 字节 | 1,407 字节 |
| 回复数 | 68 | 66 |

总回复减少约 19.9%，正文以外减少约 95.3%；每份回复仍不超过默认 4 KiB。没有删除科学字段或放大回复预算。此结果是确定性字节对照，不是模型 token 降幅。

[生成 bootstrap 文本](evidence/mechanical-reading-state-20260919/prompt_bytes.json)为 5,816 → 6,168 字节，增加 352 字节，包含新操作说明及缓存例外。不能隐藏这项固定成本，原生 C 验收须包含它。

## 原生 C 验收及原部署完成门

**后续验收已执行：**[原生 C 报告](MECHANICAL_READING_NATIVE_C_ACCEPTANCE_20260919.zh-CN.md)记录了两轮正常提交，但首轮峰值 +1.1%、整体峰值 +19.1%，token 目标未通过。以下保留实施完成时的部署完成门，不能再解读为当前部署状态。

核对生产文件时，三个关键 Python 文件均尚未与本候选一致。当前服务未加载新实现，不能在旧部署上跑 C 后宣称完成。

1. 用户沿既有部署命令重新安装并重启 Codex；本轮无需同步 VM runner。
2. 核对生产 helper/open/生成角色，再依照原 `native_ab_protocol.json` 创建 C 的两轮 sol/medium、600 秒受控任务，C 使用新 Agent、组内复用。若旧 B 比较条件不再成立，先报告差异再补一对。
3. 仍用逐请求计量，分别报告首轮峰值、复用增量、两轮整体峰值及提交结果、科学必要材料覆盖；不以缓存累计或离线字节减少代替验收。结果不明确至多再补一对。

以上待验收项未标为通过；独立审查结论仅为静态实施通过。
