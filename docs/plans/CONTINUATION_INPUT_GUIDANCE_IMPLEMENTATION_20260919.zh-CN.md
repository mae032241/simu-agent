# 接续输入等价导航实施记录

2026-09-19。用户授权按最小范围实施；源码及定向测试完成；用户已部署，[原生G两轮验收](INPUT_GUIDANCE_NATIVE_G_ACCEPTANCE_20260919.zh-CN.md)完成，本次不重读未变输入。独立实施复审及稳定收益验证仍未完成。

依据 [F验收](READER_USABILITY_NATIVE_F_ACCEPTANCE_20260919.zh-CN.md) 和 [独立全局审查](reviews/TOKEN_WASTE_GLOBAL_F_REVIEW_20260919.zh-CN.md) 的第一优先项。本记录不改写F回退结论，也不声称导航必然改变模型策略。

## 范围与行为

仅扩展 LocalWorkerMCPRouter 既有 reading_guidance，调整生成Worker提示及dispatch说明，并同步双语架构。控制层从前一绑定Run和当前Run的持久化输入记录比较完整ArtifactRef、端口、media_type、usage、exposure、require_current，并比较assignment中的historical与来源用途描述。模型仅看到当前别名与unchanged/changed/new/unknown；原件换别名时另给前序别名，不暴露内部身份或哈希。

同一不可变原件且用途未变才提示unchanged；内容/身份/用途变化提示changed；新增输入提示new；前序工作区或记录不可用、不完整或对应歧义提示unknown。没有新增数据库、阅读账本、科学摘要、权限、提交门或自动跳读。未变不证明之前读过、更不证明仍记得。Worker仍核对新任务、总体目标/绑定、语言、预算及输出恢复要求；可复用上下文中保留的原文，需要验证细节或丢失上下文时定向补读。全部精确原件保持可访问。

分页、Worker切换策略、科学合同与原生工具权限未改。

## 验证

- reader之外的接续导航、真实统一MCP生命周期/网关重建、生成平台配置、scheduler指南：33项通过，8.93秒，进程树采样峰值291784 KiB（约285 MiB）。
- 架构约束矩阵：1项通过，0.07秒，峰值49384 KiB。
- git diff --check通过。串行，768 MiB采样退出保护，未跑全量测试。
- 技能中提到的 scripts/validate_architecture_constraints.py 在当前仓库不存在；使用实际存在的 tests/operations/test_architecture_constraint_matrix.py 验证，不声称缺失脚本运行通过。

负例覆盖：相同字节不同Artifact身份、相同别名内容变化、端口/usage/exposure/currentness/historical/来源改变、前序记录缺失、工作区缺失、歧义，以及动态Schema变化不被误判为可复用。

## 部署验收路径（本次G已完成，稳定收益仍待验证）

重新安装并重启控制服务/Codex后，以新Run获取新指引；无需同步VM runner。随后按固定协议做有界重复对照，分别计量未变输入重复返回、新增证据、上下文峰值/净增和科学交付充分性。不能以本地通过数、少一次读取或单组波动宣布token节省稳定成立。
