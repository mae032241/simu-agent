# 读取机械状态内收计划 R1 独立复审

日期：2026-09-19。结论：**通过方案复审，可以按计划进入最小实现。上轮两项必改意见均已闭合；未发现新的方案阻断。** 此结论不代表实现、部署或 token 验收通过。

复审对象：`docs/plans/MECHANICAL_READING_STATE_BOUNDARY_PLAN_20260919.zh-CN.md` 当前 93 行修订版。沿用 scid-cross-boundary-review 技能，仅检查上轮缺口及直接相关边界。源码基线仍为当前工作树，HEAD `943c4626f8490530e9318eb9fbb409d2670908b9`；没有把未提交内容视为 HEAD。

## 必改意见闭合情况

| 上轮问题 | 修订及源码核对 | 结论 |
|---|---|---|
| 私有缓存位置与 helper 提示冲突 | 计划第 50–51 行规定固定私有位置及仅框架 reader 适用的位置例外，其他 helper 仍遵守 scratch 规则；第 79 行同时要求安装行为和 analysis 恢复扫描验收；第 93 行明确该例外属于本轮范围。现 `platforms/codex.py:320`、`:389` 的 scratch 提示和 `analysis_workspace.py:272` 的 output/scratch 扫描确为需要同步处理的现状。 | **闭合。** 计划已给出具体修改落点，无需扩大原生沙箱、科学写权限或引入权限实体；当前源码尚未实施不构成方案缺口。 |
| 分页一致性被误读为封存原件哈希验证 | 计划第 11、21–22、49、53–54 行区分控制层绑定/初始化与 reader 当次基线，明确不能发现首次读取前改动或文件、缓存同时重建的差异；第 77 行加入对应验收。现 `run_assignment.py:63` 起确实无预期内容哈希，`input_reader.py:56` 起确实只对当前字节现算指纹，`local_workspace.py:154` 起负责写入只读输入副本。 | **闭合。** 保证范围与实际接口一致，不再暗示已有独立封存字节校验，也不需要新增哈希清单或提交门禁。 |

上述源码均位于 `src/scidiscovery/artifact_agent/service/`，但 `platforms/codex.py` 位于 `src/scidiscovery/platforms/`，`analysis_workspace.py` 位于 `plugins/curve_score/curve_score/`。

## 实施验收项，不是方案阻断

- **缓存与续读：**验证固定私有位置的实际写入、生成指引一致性、恢复扫描排除，以及同选择并发/丢回复后的 repeat 或 restart。第 55 行已承认交付限制；不要求新增收悉协议或历史段状态机。
- **角色与兼容：**从统一 MCP 入口验证复用准入。计划第 63 行的 attach 是链路概括，实际平台 model/effort 检查位于 `interfaces/mcp_gateway.py:103`–`108`；测试不可只覆盖 attach。旧 helper 存在但只支持 offset/version 的 Workspace 也应验证定向原文回退。无需为此再修改计划或增加准入门禁。
- **正文与成本：**保持 assignment/schema 等任务内文件可定向读取；离线回放以精确原件或真实回复证明正文一致，不能仅凭长度元数据。按计划分别报告首轮、复用轮及整体实际上下文峰值，包装字节降低不能单独证明 token 验收通过。

本轮只新增此复审报告，保留原计划及原审查报告，未修改生产代码；未运行模型、全量测试、安装或部署，也未扩展为全框架审计。缓存实现、旧 Workspace 实际行为及真实 token 收益仍待实施后验证。
