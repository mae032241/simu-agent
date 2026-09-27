# 分析 Agent 详细残差诊断与识图权限实施记录

日期：2026-09-12。状态：源码实现及定向安装验证完成；未更新生产安装、未重启服务、未重新运行科学分析或 solver。

## 实施范围

- 通用结果分析增加 `worker_curve_diagnose`，TCAD 结果分析增加 `worker_tcad_curve_diagnose`。两者在当前分析 Run 内调用，复用现有解析、评分、残差定位及绘图算法。
- 返回已有局部残差轨迹、分段误差贡献、覆盖信息及曲线叠加／残差 PNG。残差分段边界不等于梯度变化点；本次未添加新的梯度或曲率算法。
- 分析者自行选择方法。诊断不要求先准备曲线合同、不创建独立评分 Run、不成为额外审查或提交条件；超时或不可计算时允许携带原因提交有限分析。
- `science.result.diagnose.v1`、`tcad.result.analyze.v1`、`science.result.diagnose.curve-error.v1` 均声明 `native_tools.view_image=true`。已验证当前 Codex trusted-local 安装生成的角色权限；原 Hardened 后端禁止原生工具的政策未扩展。
- 既有预计算曲线诊断角色新增可选 `curve_analysis_plots` 输入，可读取绑定的 PNG。通用和 TCAD 分析者可读取当前工具返回的任务内只读图片。
- 计算记录及图片走既有 receipt、tool evidence 和不可变成果封存。工具调用不提前校验尚未完成的科学报告，提交不重新计算诊断。
- 唯一控制层扩展是既有证据注册回调接受 `derived_from`：由可信工具指定当前输入或已注册证据作为派生图片的来源。默认原执行文件恢复路径仍要求精确绑定的 execution result；无新增状态机、数据库迁移或外部执行权限。

## 明示的资源与能力边界

每次诊断选择一个 comparison、一个 residual operator、2–257 个采样点。Schema、工具说明、提示词使用相同限制，不静默修改采样网格。完整记录沿用已有计算记录大小预算；超出预算返回有原因的不可用结果。原评分工具继续提供 crossing、width 等指标及原有采样范围。

PNG 使用既有 `tool_evidence` 输出，任务内预览路径不写入科学记录。来源、内容摘要及计算 receipt 保留在封存结果中。诊断方法和指标是否足以支持结论，仍由分析者和独立审查判断。

## 改动文件

- `plugins/curve_score/curve_score/analysis.py`：提取可独立调用的定位函数，保留原算法及旧入口，添加预算检查。
- `plugins/curve_score/curve_score/diagnostic_tool.py`：共享诊断接口、可选图片输出与分析指导。
- `plugins/curve_score/curve_score/science_operations.py`：通用工具注册、图片输入／输出、角色权限及计算记录兼容。
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py`：TCAD 解析适配、工具注册与角色权限。
- `src/scidiscovery/artifact_agent/service/tool_evidence.py`：当前来源派生证据注册。
- `tests/operations/test_analysis_diagnostic_tool.py`：9 个新增定向用例。
- `tests/operations/test_analysis_tool_installed.py`：安装后的真实工具、PNG 与角色权限投影检查。
- `tests/operations/test_m2_curve_analysis_boundary.py`：原预计算诊断路径绑定真实 PNG。

本轮起点已含大量未提交改动。仅本轮差异见 `DIAGNOSTIC_TASK_DELTA.patch`，没有回滚或混入其他模块修订。

## 验证证据

所有执行串行，沿用 `check_guard.py`：单进程地址空间上限 512 MiB，整棵测试进程树 RSS 达到 448 MiB 提前停止；BLAS／OMP 单线程。未运行全量测试或完整安装矩阵。

| 检查 | 结果 | 进程树峰值 |
| --- | --- | --- |
| `DIAGNOSTIC_REGRESSION_1`：新诊断、现有评分、TCAD 分析、证据恢复、结论范围、旧曲线分析 | 149 passed、1 deselected，随后遇到下述既有失败 | 274.6 MiB |
| `DIAGNOSTIC_REGRESSION_2`：最终派生来源实现的新诊断和恢复路径 | 前 39 项通过；随后旧测试仍假定仅有一个输入，因本次增加可选 PNG 输入而失败；该断言已修订，并由下一项验证 | 258.4 MiB |
| `DIAGNOSTIC_LEGACY_IMAGE_PATH`：实际 PNG 绑定、旧算法包与图片篡改拒绝、移除旧工具 | 3 passed | 124.7 MiB |
| `DIAGNOSTIC_BASELINE_PROOF`：加载本轮修改前源文件复现旧断言 | 证明下述失败在本轮修改前已存在 | 86.5 MiB |
| `DIAGNOSTIC_INSTALLED_R3`：curve 与 full 两个隔离安装组合 | 工具注册／角色图片权限、无 TCAD 的真实诊断及 PNG、安装与源码 catalog 身份一致，全部通过 | 178.1 MiB |
| 本轮文件空白检查 | 通过 | — |

上述日志及 JSON 资源记录位于同目录；数字不可相加作为唯一用例总数。安装验证仅离线构建 core、curve、TCAD 三个 wheel，并使用两个临时隔离 venv。第一次临时脚本继承源码 PYTHONPATH，导致 pip 误判已安装；第二次测试使用了与 local profile 不同的权限措辞。隔离环境和断言修正后 R3 通过，未因此修改生产部署代码。可复现脚本见 `DIAGNOSTIC_INSTALL_SMOKE.py`。

### 已确认的既有失败

`test_legacy_curve_diagnosis_cannot_pass_with_uncovered_checks` 仍期待“未完成检查自动拒绝通过”。本轮修改前的 `_validate_diagnosis_against` 已不执行该自动科学裁决，因此旧断言同样失败。没有恢复用户此前要求移除的校验，也没有在本轮删除这个旧测试。该测试与此前校验裁剪的同步问题仍需另行清理；不宣称全量测试通过。

## 后续实际验收

重新安装并重启后，用新分析 Run 绑定当前案例的精确计划、审查、执行结果及参考证据，观察分析者能否根据科学问题选择诊断、查看图像并给出有证据的结论或停止理由。当前记录证明工具和权限路径可用，不证明实际科学案例已使用新增能力完成分析。
