# R3 C 分析连续工作实现：独立静态审查

## 结论

**需修复后复审：发现 1 项 P1，现存固定 curve-error 生产路径在图片集合校验处会遇到未定义的 `Image`。** 本次未发现 checkpoint 的已检查路径允许用工作区副本或不同 Artifact 身份替代原计算输入。

审查日期：2026-09-25。独立审查者按 `scid-cross-boundary-review` 追踪本次七文件候选及其直接控制层消费者；没有审查无关 A/B 改动，没有修改作者代码。基线为 HEAD `5871a64e3585e00f98f5357aadef959d343758c5` 加此前清理和 A/B；不将此前差异归入 C。

精确交接清单 `/tmp/scid-r3-c-candidate.json` SHA-256：`954950860d7a7f78b3e4a1aedd26b9aa0b6e03ad9f0845f941ad7bba0e9cbdb8`。七文件身份全部匹配，五个 Python 文件 AST 可解析。

## C-R1 / P1：PIL 改为绘图函数局部导入，遗漏仍在使用 Image 的生产校验函数

**主要位置：**[analysis.py](../../../plugins/curve_score/curve_score/analysis.py) 第 406 行；对应本次删除的模块级 PIL 导入和第 871 行的新局部导入。

可达场景：已有固定曲线分析 transform 获得有效 complete-plan、curve contract、metric report 和 bundle，成功生成 1200×800 PNG。它在交付 package/plots 前调用 `validate_curve_error_plot_collection`（[science_operations.py](../../../plugins/curve_score/curve_score/science_operations.py) 第 766–786 行，调用点第 781 行）。

该校验函数完成 PNG 魔数和 SHA-256 检查后直接调用 `Image.open`。模块级 `from PIL import Image, ImageDraw, ImageFont` 已删除，新的导入仅位于 `_render_curve_error_plot` 局部作用域，不能为校验函数提供 `Image`。因此有效 PNG 到达第 406 行就会抛出 `NameError`；其 `except (OSError, ValueError)` 也不会处理这个错误。

**影响：**既有固定 curve-error transform 无法返回分析 package 和 plots，后续 `science.result.diagnose.curve-error.v1` 失去这条生产输入路径。候选说明声称保留完整 localization transform API，但现有消费者实际中断。新增 same-Run 工具成功与否不能覆盖这个回归。

**建议：**在 `validate_curve_error_plot_collection` 内局部导入 `PIL.Image`，保持绘图依赖延后加载的目的，并保留真实 PNG 结构校验。不要仅捕获 NameError 或删除校验。修复后静态核对所有非注解的 PIL 名称使用点；用户解除禁测后再验证该真实 transform 的有效 PNG 交付。

## 已追踪的 C 路径

### 数值保存与绘图失败

- [diagnostic_tool.py](../../../plugins/curve_score/curve_score/diagnostic_tool.py) 第 153–183 行先读取声明源、计算 byte digests、完成 scoring 和 `compute_curve_error`，随后保存包含完整原始 request、算法版本、完整输入 ArtifactRef、metric_report 和数值渲染输入的 checkpoint。
- `publish_analysis_file` 先经 `accept_tool_evidence` 注册不可变字节，再写本地只读预览。checkpoint 类型由工具 metadata 标注，不从 Agent 输出目录猜测。
- 第 197–225 行只在数值和 checkpoint 存在时尝试渲染。已捕获的渲染/发布错误保留 computed metric_report，并输出 `diagnostic_render_incomplete`；已经成功返回的 details/images 不会被清空。数值定位或 checkpoint 保存的受支持异常也不会覆盖已经完成的 metric_result。
- 这不表示任意资源耗尽都可无损交付：最终 calculation record 的持久化仍受已有证据数量/字节预算和存储可用性约束，不能把异常捕获描述成无限制可靠保存。

### checkpoint 重绘与精确身份

- `_restore_checkpoint` 第 117–139 行仅从当前/控制接纳的 `context.evidence()` 获取 alias，限定 checkpoint kind、算法版本和两个诊断工具名称；读取控制存储字节后核对大小上限和 artifact SHA-256。
- 相同内容但不同 ArtifactRef、变化的 raw request、输入 digests 或算法版本被拒绝；数值报告与 metric_report 的 bundle/spec digest 也须一致。工作区 JSON 路径不能代替受控 evidence alias。
- 重绘分支不调用 parser、scoring 或 `compute_curve_error`。新 details 和图像的 derived_from 同时包含原输入与 checkpoint alias，便于控制层保留依赖。

### 失败 Run 恢复与最终消费

- 现有 `adopt_tool_evidence` 按原生产者的 derived_from 解析 ArtifactRef；只有当前输入/已接纳证据具备全部依赖才收养，保留原收据和 CAS ref。checkpoint 先于其 details/images 注册，符合依赖收养顺序。范围外旧记录保留在恢复记录中，不能被 `_restore_checkpoint` 当作当前证据选用。
- LocalWorker 仍记录真实读源和终态 receipt。重绘读取 checkpoint 也进入 attempt 的 read_sources；`calculation_sources` 在最终消费时核对其确切绑定、完整 request digest 和结果 digest，不重新计算科学数值。
- `record_metric_report` 已识别 v3 的嵌套 `metric_report`；general 与 TCAD 的最终分析校验都消费受控 calculation records。TCAD 入口在共享诊断调用前仍执行 case/source mapping 检查。
- `DiagnosticInput` 和 `TCADDiagnosticInput` 均声明可选 `checkpoint_alias`；两种 Worker tools 使用相同实现，提示明确区分指标已完成与图片成功。两组件 configuration_identity 已同步到 checkpoint v3。

上述结论为静态调用链与合同检查；没有将新增测试代码视为已经运行通过。

## 任务范围与尚未验证内容

本次没有重造实验作者或 hypothesis critic。候选将 `tcad.execution-plan.project.v1` 和 reviewed package 的机械节点内化留给 D，未把它们隐藏后宣称任务颗粒度已完成收敛；C 的本次改动集中在分析数值复用。

所有操作串行。未执行测试、pytest collection、项目动态导入、catalog 编译、安装、构建、solver 或部署。真实 renderer、受控保存中断、failed Run adoption、重绘后的最终提交及资源行为仍待后续获准运行验证；本报告不授予运行资格，也不声明完整 R3 完成。

## 精确候选身份

| 文件 | SHA-256 |
| --- | --- |
| `plugins/curve_score/curve_score/analysis.py` | `284f94941b09893c821e2a83f9da779878c1d6bba2ef795126baf5ab467d98b0` |
| `plugins/curve_score/curve_score/diagnostic_tool.py` | `317bd87a39fa57cedb49e969c23b4bb3ea47ce0d47a6e7c570a580d6435c762d` |
| `plugins/curve_score/curve_score/science_operations.py` | `04ba97f81e0f4a5032478fd3b99c4c3b8fdbd64fa4af6874220ee58be9dd80f9` |
| `plugins/tcad_artifact/tcad_artifact/result_analysis.py` | `bc756ddcdad40b18656c9d2301abe59461dbbdcd1f2f60323b8ceaa627ee9de4` |
| `tests/operations/test_analysis_diagnostic_tool.py` | `c3b896d203718062e219a2f326974507c99336230caa08d0a9773924623be7b5` |
| `docs/ARCHITECTURE.md` | `f3bdc26b9cee7f643d085af05ad2eadad38063d7bb09a8c5a26b7625f0bff661` |
| `docs/ARCHITECTURE.zh-CN.md` | `9c5f2b5d05c1ed184f89872500791576bac7620dd6f74beed295bf734ca94646` |

## 修复后的最小复核（2026-09-25）

**最新处置：C-R1/P1 静态关闭。本次已报告问题全部完成静态修复复核；运行仍未验证。** 前文保留原候选的审查事实。

修订候选 `/tmp/scid-r3-c-candidate-fixed.json` SHA-256：`b8ad5af367bdffb956a3576eeb9833afc8274409cd0a4c1b421122d1b549cf34`。七文件身份全部匹配；仅 `plugins/curve_score/curve_score/analysis.py` 变化，新 SHA-256 为 `f32424d4b9fc67330054de198fa54665783924b0ae1ad774e2d658189e4b5e6f`，其余六文件沿用前表。

`validate_curve_error_plot_collection` 现于函数内、第一次使用 `Image.open` 之前执行 `from PIL import Image`；渲染函数的局部导入继续保留。原 PNG 魔数、摘要、格式、尺寸及 `verify()` 校验均保留，没有通过跳过校验规避错误。用 stdlib AST 核对导入作用域和先后关系，文件语法可解析。

本轮未扩大复审范围，未执行测试、动态导入、catalog 编译、安装或构建；不将修复确认写成真实 transform 已运行通过。
