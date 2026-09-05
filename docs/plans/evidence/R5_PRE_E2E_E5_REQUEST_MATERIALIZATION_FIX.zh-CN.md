# R5 E5：请求—物化合同断裂修复证据

日期：2026-09-05

状态：**实现、聚焦测试与独立代码复审 PASS；等待事务化重装和真实 E5 重跑**

## 1. 真实入口发现的问题

在真实安装态与 `M7-test0` 实例中，`science.figure.request.prepare.v1` 的 Agent Run
`fig4_e5_figure_request` 正常进入 `completed`，Schema 和原上下文校验均通过，并封存
`fig4_e5_figure_request.output`。输出精确绑定论文第 6 页 Fig.4、PDF 对象 `241 0` 和两条可见实线，
没有引入 800°C/900°C 曲线。

紧接着以同一论文和请求调用 `science.figure.evidence.materialize.v1`：preflight 为 admissible，但真实
invoke 失败，Root 按既有错误外观返回 `executor_component_failed`，且没有登记半成品 Artifact。

用真实安装包和同一 CAS 内容进行只读内存重放，取得底层确定性异常：

```text
ValueError: shared support lacks covered-series endpoints
```

论文 CAS 摘要与请求 `source_sha256` 均为
`750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`，故不是错源或身份漂移。

## 2. 根因

请求声明了 shared-support 区间，但物化核要求 donor 全区间有直接点、covered 在两侧有直接端点、
区间内只有 covered 缺点且两侧距离满足阈值。旧提示和语义合同没有向 Worker 明示这些规则，旧
`_validate_request_context` 也只校验来源恢复。因此同一 Operation 的 Worker 可见合同和紧邻确定性
消费者发生断裂。

预修复独立审查见
`reviews/R5_PRE_E2E_E5_REQUEST_MATERIALIZATION_PREFLIGHT_REVIEW.zh-CN.md`，方案阻断项 0。

## 3. 最小源码修改

生产代码只修改 `plugins/curve_score/curve_score/figure_science_operations.py`：

1. 在既有请求提示与同一语义合同中公开 shared-support 的四项真实约束；
2. 继续使用既有 `curve.figure.request.source_binding` 与既有 context validator；
3. `ready` 请求在提交时直接调用唯一 `build_digitized_figure_bundle` 验证可物化性，丢弃预构建结果；
4. `unresolved` 请求仍只调用 `recover_requested_image`，不强迫其伪造标定或曲线。

没有修改请求实体、物化科学规则、Root、Operation 通用调用器、生命周期、数据库、注册表、错误码或
历史请求；旧无效请求保持不可变。

## 4. 测试证据

串行、禁用第三方 pytest 插件并设置 4 GiB 虚拟内存上限：

- 缺 covered 端点的结构合法 shared-support 请求通过编译后的真实 Worker 提交路径被拒绝，诊断
  `rule_id` 精确为 `curve.figure.request.source_binding`；
- 既有合法 shared-support 正例通过同一 context validator，随后正常物化；
- 图工具与五操作闭环两个测试文件：`17 passed`，峰值 RSS `115968 KiB`，无交换；
- 插件归属、默认表面与安装入口：`18 passed, 1 failed`，峰值 RSS `87856 KiB`，无交换。唯一失败为
  已冻结的可选 Hardened 探针在 invoke 时返回 `operation_runtime_unavailable`，与本次 Local Worker
  请求合同修改无调用或数据依赖，且已在 E4 标记为非本轮范围。

`git diff --check` 对本次三个文件通过。

## 5. 阶段边界

本文件不宣称 E5 通过。独立代码复审通过后仍需重新执行 M7 事务化安装、重启 Codex/绑定实例，并以
新 Run 名重新启动真实请求 Agent。只有新请求能完成封存且紧邻真实物化 Transform 成功，才证明该
断裂在安装态闭合。

独立代码复审见
`reviews/R5_PRE_E2E_E5_REQUEST_MATERIALIZATION_FIX_REVIEW.zh-CN.md`，结论 `PASS`、阻断项 0，只放行
事务化重装与真实请求—物化重跑。
