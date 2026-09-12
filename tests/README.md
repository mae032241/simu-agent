# 测试运行范围

普通回归使用 `python -m pytest`，默认排除 `stress`。普通回归仍包含安装测试，不能将它视为低资源测试集。日常修改优先显式选择相关文件或用例；重测试串行运行。

原始大文件解析及提交不重算的压力验收单独执行：

```bash
python -m pytest -q -m stress tests/operations/test_tcad_result_analysis.py
```

仅检查压力用例的选择，不执行计算：

```bash
python -m pytest --collect-only -q -m stress tests/operations/test_tcad_result_analysis.py
```

安装测试保留包发现、通用入口、原始 PLX/CSV 正式提交、失败运行和错误输出名拒绝。其余 case、数值篡改、取消运行及旧输出关联等排列由源码测试覆盖，避免在每个安装环境重复整套业务矩阵。

本次裁剪移除固定历史提交行数、编译器内部函数形状、固定整目录摘要、模块行数/文件数量及历史计划措辞断言。历史结构度量工具仍在 `scripts/r5_baseline_metrics.py` 和 `scripts/r5_current_metrics.py`；这些度量不再作为产品正确性的默认测试门槛。

保留的承接检查包括：

- `test_catalog_compile.py`：声明不被修改、相同输入摘要稳定、权限和资源变化影响摘要。
- `test_catalog_negative_cases.py`：重复或非法声明拒绝。
- `test_m2_optional_figure_plugin.py`：有/无 TCAD 的图证插件组合与工具、审查接线。
- `test_h2b_domain_boundaries.py`：领域依赖方向及输入用途边界。
- `test_result_analysis_tool.py`：封存分析实际进入下一轮设计。
- `test_tcad_result_analysis.py`：原始结果、身份核验及正式提交。

源码和安装测试通过不代表已部署，也不代表真实求解器研究闭环完成。
