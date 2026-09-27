# R5 E5 请求—物化合同修复独立代码复审

日期：2026-09-05

结论：**PASS**  
阻断项：**0**  
放行范围：**仅允许重新部署并重跑真实 E5 请求 Agent → 物化 Transform；不代表 E5 完成。**

## 1. 审查边界

本审查者未参与本次实现，只审查：

- `plugins/curve_score/curve_score/figure_science_operations.py`；
- `tests/operations/test_curve_figure_digitization_tool.py`；
- `tests/operations/test_m5_figure_review_closure.py`；
- `docs/plans/evidence/R5_PRE_E2E_E5_REQUEST_MATERIALIZATION_FIX.zh-CN.md`。

没有审查或修改 Root、注册表、数据库、Run 生命周期、Hardened、UI 或其他领域逻辑。E4 已冻结的
Hardened `operation_runtime_unavailable` 不属于本次结论。

## 2. 逐项复审结论

### 2.1 四项 shared-support 规则已经对 Worker 可见

请求 Agent 提示现在明确声明：

1. `[left,right)` 每一列都必须有 visible donor 的直接跟踪点；
2. 每条 covered series 在 `left-1` 与 `right` 必须有直接端点；
3. covered 与 donor 两侧端点距离不得超过 `max_endpoint_distance_px`；
4. shared interval 只能填补 covered series 的缺失像素。

提示还明确禁止为通过物化而放宽阈值或发明端点。相同四项规则进入既有
`FIGURE_REQUEST_SEMANTIC_CONTRACT`，没有新建合同或规则注册表。

独立编译请求 Operation 并读取其实际输出 Schema，确认
`x-scidiscovery-semantic-constraints` 中包含上述完整规则；validation contract 的 context checker 仍
使用 `curve.figure.request.source_binding`，所需精确输入仍只有 `paper_source`。因此这些规则不是只
存在于源码注释，而会进入 Worker 可见 `output.schema.json`。

### 2.2 ready 与 unresolved 分支符合预审边界

`_validate_request_context` 只规范编码和解析请求一次：

- `request_status == "ready"` 时直接调用唯一现有
  `build_digitized_figure_bundle(paper_source, encoded)`，没有先调用
  `recover_requested_image`；来源恢复、线跟踪、shared-support 和正式附件校验均复用同一个实现。
- `unresolved` 时只调用 `recover_requested_image`，不会进入要求 ready 的 builder，也不会强迫未决
  请求补写标定、曲线或 shared support。

异常继续转换为已有 `SemanticRuleViolation`。实现没有复制 donor/端点算法，没有新增缓存、预检状态
或第二事实源。

### 2.3 失败负例经过编译后的真实提交路径

新增负例不是直接调用 Pydantic：它编译完整插件目录，通过 Root preflight/invoke 建立请求 Run，
再由 `LocalWorkerMCPRouter` 打开 assignment、写入 `result.json` 并执行
`worker_submit_result`。结构和来源身份合法、但 covered 端点缺失的 shared-support 请求得到：

```text
state = rejected
rule_id = curve.figure.request.source_binding
message 包含 shared support lacks covered-series endpoints
```

因此错误在请求提交时由已编译 context validator 返回，不再等到后续 materialize invoke 才首次
暴露。Run 没有被误标 completed，也没有封存不满足同一消费者合同的新请求。

### 2.4 合法 shared-support 与未决请求未退化

现有合法 fixture 在 covered 两侧保留端点、donor 覆盖完整区间且 covered 区间内部缺点。它先通过
同一 `FIGURE_REQUEST_CONTEXT`，随后正式物化成功；共享两点保持
`shared_occlusion` 且默认不可用于定量主张。

既有 unresolved 正例继续通过 context validator 的来源恢复，并继续被正式 builder 以
“unresolved request cannot be materialized”拒绝。这证明修复没有把所有 shared support 禁掉，也没有
把未决请求强行升级为 ready。

### 2.5 修改没有扩大控制面

生产修改只发生在已批准的一个插件模块：补充模型可见文字，并让已有 context validator 调用已有
builder。没有新增实体、错误码、MCP、Operation、端口、注册表、Root 分支、状态或数据库字段；也没有
修改物化核的科学要求或历史已封存请求。

该修复重新对齐 `AUTH-003`、`ROLE-002`、`DET-001`、`TOP-002` 与 `EVD-001`，同时仍由 Worker 决定
科学声明、确定性程序只验证精确来源可重放性，符合 `ROLE-001/DET-002`。相较复制线跟踪预检或新增
状态层，复用唯一 builder 是当前 Fig.4 范围内更小且更可靠的方案。

## 3. 独立验证

独立执行：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_m5_figure_review_closure.py

17 passed in 6.77s
peak RSS: 116440 KiB
```

同时独立编译 `CORE_PLUGIN + GENERAL_PLUGIN + CURVE_PLUGIN + FIGURE_PLUGIN`，读取请求输出的实际模型可见
Schema，确认 shared-support 语义规则与 context checker/rule id 均已编入合同。

## 4. 剩余阶段边界

源码测试只能证明新合同能够拒绝复现负例。当前 `/opt/scidiscovery-m7/site` 是否已经包含该修复、真实
Codex Agent 是否能依据新增提示自行产生可物化请求，仍必须通过重新部署及新的真实 Run 名验证。

因此本次 **PASS** 只放行：事务化重装、安装态摘要核验、重新绑定既有实例、以新 Run 重跑真实请求
Agent，并紧接同一请求调用物化 Transform。只有真实物化成功后才能继续 E5 后续 Intake、独立图审查
与资格链；不得把本报告解释为 E5 已完成。
