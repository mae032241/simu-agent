# R5 E1：论文图五操作拓扑实施证据

日期：2026-09-04

状态：**完成；独立审查 PASS，阻断项 0**

## 1. 实际修改边界

本阶段只修改可选论文图插件、其复用的曲线图实现及对应测试：

- 增加类型化 `scidiscovery.curve-figure-digitization-request.v2`；
- 增加插件内 PDF 嵌入图枚举/恢复与 Run 内只读预览工具；
- 以确定性 Transform 物化 manifest、source panel、overlay、curve table 和 validation report；
- 将图 Intake 与图审查拆成两个单输出 Agent；
- 收紧最终打包 guard，使请求、来源、完整物化族、Intake 与通过的独立审查属于同一精确父链；
- 删除旧集合式数字化/验证 Worker 工具和旧 `science.evidence.extract.figure.v1` 路径。

没有修改核心 Run、数据库、MCP 路由、调度器、current、资格体系、Execution 或部署协议；没有新增
Agent 集合输出协议、注册表或状态。

## 2. 编译后唯一拓扑

| Operation | 视图 | 执行器 | 输出端口数 | 本地后端状态 |
|---|---|---|---:|---|
| `science.figure.request.prepare.v1` | public | Agent | 1 | available |
| `science.figure.evidence.materialize.v1` | support | Transform | 5 | available |
| `science.evidence.extract.figure.v2` | public | Agent | 1 | available |
| `science.figure.evidence.audit.v1` | public | Agent | 1 | available |
| `scidiscovery.curve-bundle.figure-evidence.v2` | support | Transform | 2 | available |

旧 `science.evidence.extract.figure.v1` 与 `science.evidence.audit.figure.v1` 均不再注册。三个 Agent 均只有
一个非集合 JSON 主结果；多项附件只由已支持多输出的 Transform 登记。插件仍只有
`curve_figure_evidence.plugin:PLUGIN` 一个入口。

## 3. 精确来源重放

冻结 PDF 第 6 页连续检查两次得到逐字节相同结果：

| 全文图像号 | 页内号 | PDF 对象 | 尺寸 | 规范化 PNG SHA-256 | 字节数 |
|---:|---:|---:|---:|---|---:|
| 46 | 0 | 240 0 | 2100×812 | `9bbd94220ee55c5d475223d4175c763d7767d7feb8f1242855c7850c23200815` | 407811 |
| 47 | 1 | 241 0 | 1000×815 | `88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a` | 226099 |

请求输出的上下文校验器会从精确绑定的 `paper_source` 重新恢复所选对象，并核对源摘要、页、全文与页内
图像号、对象号、恢复图摘要和尺寸。正式物化 Transform 再独立执行同一核对；Worker 的临时预览路径
不进入请求或正式 Artifact。

## 4. 测试证据

聚焦拓扑、Schema、工具、来源重放、完整父链、插件边界、编译负例和 M2 保留 Transform 回归：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_h2b_domain_boundaries.py \
  tests/operations/test_m5_plugin_ownership_and_default_surface.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_m3_transform_equivalence.py
```

结果：`79 passed in 29.79s`。

干净 wheel 安装态的领域工具探针：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_domain_tools_execute_the_packaged_implementations
```

结果：`1 passed in 39.80s`。探针从安装后的请求 Operation 取得
`worker_curve_figure_inspect_source`，实际生成且读取 Run 内只读 PNG 预览。

另一次安装测试文件运行中，前七项（含上述领域工具探针）通过，随后既有 blind-csv Hardened Run 因其
reviewer 在该运行后端不可用而失败；它不触及论文图插件。本阶段没有借此修改 Hardened 后端或测试插件。

## 5. 尚未宣称完成的内容

- 当前简单逐列颜色算法仍属于 E2 阻断，不能用于真实 Fig.4 科学放行；
- 本阶段没有证明真实 Codex Agent 会正确调用工具，该证据属于 E5；
- 尚未修改 Fig.4 安装 profile，也未部署；
- UI 可读性、projector 精细诊断与强隔离继续延期。

## 6. 独立审查

独立审查见 `../reviews/R5_PRE_E2E_E1_INDEPENDENT_REVIEW.zh-CN.md`。审查独立复跑 79 项聚焦测试、
干净 wheel 工具探针和冻结 PDF 双次恢复，并用临时真实 Root 链验证最终打包正例及跨物化族附件
混入负例。结论为 `PASS`、阻断项 0，只放行既定 E2。
