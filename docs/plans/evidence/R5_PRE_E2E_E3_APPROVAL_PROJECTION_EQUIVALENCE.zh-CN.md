# R5 E3：审批预检与调用投影等价实施证据

日期：2026-09-04

状态：**完成；独立跨边界审查 PASS，阻断项 0，只放行 E4**

## 1. 修改边界

本阶段只修改一个生产模块：

- `mcp_root_operation_routes.py` 新增私有、无状态、只读的
  `_prepare_approval_projection()`；
- `operation_preflight` 遇到 approval Operation 时调用该函数；
- `_invoke_approval_operation` 在创建 Approval 前再次调用同一函数，并继续使用其返回的精确
  `ReviewDocument` 与 subject snapshots。

该函数只完成已有调用路径原本执行的工作：读取已绑定 Artifact、恢复完整 producer family、构造
projector context、执行已编译 projector 并检查返回类型。没有新增公共 MCP、错误码、数据库字段、
审批状态、注册表、端口诊断或 UI 展示逻辑；invoke 的 Approval 创建、指纹、选项、身份和绑定逻辑
未改变。

## 2. 等价与无写入证据

聚焦测试覆盖：

- 正确的参数多输出家族：preflight 为 admissible，invoke 创建 pending Approval；
- 正确的单输出图 Intake：其 PDF/请求/manifest/report/panel/overlay/table 完整来源族通过 preflight，
  invoke 创建 pending Approval；
- 图来源族少一张 curve table：preflight 返回 `approval_projector_failed`；
- 图来源族替换精确冻结来源：preflight 返回 `approval_projector_failed`；
- 把同一 split 的 `problem_frame` 错加到 `scientific_foundation` 端口：preflight 失败；
- 参数多输出家族增加无关冻结来源：preflight 返回 `approval_projector_failed`；
- 参数家族用相同 Schema、不同父链的对象替换成员：preflight 返回
  `approval_projector_failed`；
- 上述 projector 负例在 preflight 和 invoke 前后 Approval 总数不变，证明预检无写入且调用仍复核。

## 3. 测试结果

最直接的两个测试文件：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_m5_figure_review_closure.py

8 passed in 3.32s
```

审批、预检、输入准入和人审相关扩展集合中，除已知全仓规模阈值外：

```text
43 passed
peak RSS: 107704 KiB
```

`test_r5_catalog_stages.py::test_catalog_stages_add_no_second_registry_or_complexity_escape` 仍按旧上限要求
生产 Python 文件数不超过 159，当前工作树基线为 188，因此单独失败。E3 没有新增生产文件，也没有
修改 catalog 或注册入口；本阶段不借该历史规模账本失败扩大为全仓裁剪。

`py_compile` 与相关文件 `git diff --check` 通过。

## 4. 尚未放行

- 独立跨边界审查见 `reviews/R5_PRE_E2E_E3_INDEPENDENT_REVIEW.zh-CN.md`，结论 `PASS`、阻断 0；
- 尚未执行 E4 安装组合，也未运行 E5 真实 Codex Agent；
- projector 细粒度 reason/port 诊断和审批页可读性仍按计划延期。
