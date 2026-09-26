# 测试范围与静态清理

默认配置只排除 `stress`，安装测试仍会构建 wheel、创建隔离环境、启动子进程。不能将整套测试视为低资源检查。2026-09-24 本轮只做文本、AST 和消费者检查，**没有执行测试、收集测试、安装、构建或动态导入**。

## 分层口径

- 源码测试覆盖业务规则、身份、资格、审批、恢复及拒绝非法输入。
- 安装测试覆盖打包资源、插件发现、解释器隔离、依赖解析、真实 MCP 入口、代表性 Worker 完成与审批 UI。不同 Operation 的相同业务矩阵不再在 venv 重跑。
- 安装 fixture 按请求构建并缓存所需 wheel；core 暂存范围来自 `pyproject.toml` 的 package/readme/data 声明，不再先复制发布树和手册。发布组装仍由 `test_deploy_scripts.py` 的真实 release-builder 用例覆盖。

| 删除或收敛的家族 | 剩余覆盖 |
| --- | --- |
| 安装环境中的 retry/budget、recovery、hypothesis feedback、原始 TCAD 分析函数副本 | `test_l4_local_tcad.py`、`test_analysis_evidence_recovery.py`、`test_hypothesis_feedback_flow.py`、`test_tcad_result_analysis.py` 保留原有行为与负例。 |
| 安装中的 schema/角色/alias/上下文/skeleton/结果注册/claim admission/生成输出业务矩阵 | 对应源码 `test_agent_contract_alignment.py`、`test_role_schema_navigation.py`、`test_evidence_source_capture.py`、`test_general_transform_operations.py`、`test_tcad_scientific_skeleton.py`、`test_tcad_development_delivery.py`、`test_reviewed_claim_admission.py`、`test_tcad_generated_capture.py`；整个安装 catalog 仍与源码 digest/agent_type 精确比对。 |
| 各插件安装组合的固定完整清单、重复 fake Context 业务、reader 全量字段/补丁矩阵 | 源码 catalog 编译/负例、`test_h2b_domain_boundaries.py`、`test_l1_minimal_runtime_projection.py`、`test_tool_contract_reader.py`、`test_output_schema_reader.py`；安装保留 core/curve 隔离、figure 图片依赖、blind Worker 完成、runtime factory、坏资源及两种独立 reader 脚本 smoke。 |
| M3 历史动态 19 transform 汇总 runner、固定数量、每项重复 Root/replay/revision/approval | 源码 general transform、M2 parameter/curve、L4 package 业务回归；`test_transform_components.py` 承接原先唯一的 6 种 coverage/realization/curve 组件与 8 类 compiled guard，并逐条断父链验证拒绝。共享科学夹具迁到 `science_fixtures.py`，专用输入在 `transform_fixtures.py`。 |
| 多份 synthetic analysis/UI runtime 与每种 verdict 的完整 TCAD Run | `test_analysis_decision_contract.py` 的实际完成链路同时验证 UI 原文和读取无副作用；`test_analysis_handoff_report.py` 用共享 finalizer 参数例覆盖四类 verdict，并保留一个真实 TCAD 链路。 |
| 固定源码类/函数形状、目录行数、已删除文件名称、固定文档清单、固定旧版本/digest | 删除 architecture matrix、adapter-removal、baseline role、general-plugin-split 等历史结构验收；保留 catalog 编译不变性/非法声明、插件加载、领域组合和实际部署事务。具有独立业务/权限含义的断言保留。 |
| 旧版本 wheel 反复构建与 return 后不可达代码 | dist-info 四组轻量夹具直接检查真实 installer 依赖守卫；独立 TCAD 依赖解析、资源完整性及 source-release 检查保留。 |
| 产品已删除的旧格式与路由字段 | 删除 Task/envelope UI 两文件、Historical experiment 正例、无 anchors 的打包兼容正例、旧序列化字节保留断言和路由字段夹具；保留当前格式、旧格式拒绝、anchors/proof 拒绝与 compact 无损展开。历史 producer 可读性不等于重新获得资格的负例保留。 |

另外移除 221 个未跟踪缓存/build 文件（8,906,244 字节）。仍有消费者的历史证据夹具与发布范围说明未按名称删除。静态检查不能证明运行通过，也不代表已部署或真实求解器闭环完成。
