# R5 E5.2 集成验证报告

日期：2026-09-05

状态：P1—P4 均已实现并分别通过独立复审；集成证据已冻结，等待 GPT-6 独立集成复审。本文不宣布部署完成，不授权跳过真实端到端的人机审批与科学审查。

## 1. 唯一开发仓库与提交

本轮唯一活动开发仓库为：

`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`

分支：`refactor/m7-pre-e5.2`。外层 8765 目录只作为退役来源快照，不再编辑、测试或提交其中源码。

| 阶段 | 提交 | 内容 |
|---|---|---|
| 基线 | `a6742b7bfd3113f68f7c9fd2705daa1403027aa9` | M7 进入 E5.2 前快照 |
| P1 | `322d2812da9a18bfbefcbc2180bf3e1c08870509` | 已确认重合像素可供双方定量，删除局部 overdraw 推测的全曲线阻断 |
| P2 | `c7c692ab2dc04d53050dae3c034ae8d714292988` | 来源别名由同一 Operation 合同投影到 Worker Schema 与提交校验，并进入选择性摘要 |
| P3 | `e2af10c4b700d4544dcbeece045bae08c82f4dc3` | 审查判断忠实性而非更广目标的证据充分性 |
| P4 | `036a544d9e0ed502b41e6f36de685c2982f19fbe` | objective closure 条件进入 Worker 可见 JSON Schema |

P1—P4 没有新增公共抽象、Operation、注册表、数据库表、Run 状态、工具或 MCP。集成阶段只增加测试、更新既有复杂度基准和恢复一份封存 oracle 文件；没有修改生产实现。

## 2. 新增集成证据

### 2.1 干净安装态

沿既有 release builder、wheel、隔离虚拟环境、entry point 和 `compile_installed_catalog` 路径运行，源码目录不在 `PYTHONPATH`：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MALLOC_ARENA_MAX=2
python -m pytest -q tests/operations/test_catalog_installed_entrypoint.py
  -k 'installed_e52 or installed_evidence_alias'

3 passed, 12 deselected
最大常驻内存：77,768 KiB
```

三项证据分别证明：

- P3 的审查边界、P4 的条件/唯一性 Schema、参数清单 usage 和两项资格 Operation version 已进入 wheel；
- P1 validator v5、弃用但保留的请求字段和图审查提示已进入 wheel；
- 真实 Root→Local Worker 的任务内来源名为 `source_material`，可见 Schema 只允许该值；非法别名返回 `runtime.schema` 且 Run 保持 running，改正后同一 Run 完成；即使拥有主机权限的测试进程篡改只读工作区 Schema，提交器仍从冻结 Run 重建合同并拒绝非法别名。

### 2.2 来源投影代际

`tests/operations/test_l2_run_invariants.py` 使用相同 Operation 声明、版本和资源，只改变来源投影代际，从当前 Worker 入口跨同一状态库重启验证：

- 旧 queued 不被新摘要 Worker 领取，不能由新合同提交或显式失败收口；
- 旧 running 在截止前先因合同改变拒绝提交，过期 running 先按截止时间拒绝，二者均不能由新合同显式失败收口；
- 旧 failed 恢复草稿保留，但 `recovery_available=false`，新合同不能以它创建恢复 Run；
- 旧 completed 记录、Artifact 和收据保留，但 sealed output 为 `contract_retired`；幂等 submit 不重新登记或赋予当前合同消费权；
- 一个无来源投影且不依赖变化 provider 的实验设计 Operation 摘要保持不变；新摘要可创建自己的新 Run。

结果：5 个代际分例通过；该测试文件完整 17 项通过。

### 2.3 完整目录回归

串行、禁用第三方 pytest 自动加载、无 xdist：

| 范围 | 结果 | 最大常驻内存 |
|---|---:|---:|
| `tests/artifact_agent` | 58 passed | 94,444 KiB |
| `tests/operations`，不排除任何项 | 364 passed，1 skipped，10 failed | 142,516 KiB |
| `tests/operations`，精确排除下节 10 项 | 364 passed，1 skipped，10 deselected | 140,788 KiB |

峰值远低于 Codex 进程树 4 GiB 和 WSL 增量 8 GiB 门。本轮没有并行测试或多 Worker 同驻。

## 3. 10 项基线遗留红项

以下失败对应的生产实现和旧测试主体在 `a6742b7..HEAD` 中均未被 P1—P4 修改。本报告不把它们伪装成本轮通过，也不借 E5.2 扩大修复范围。

### 3.1 强化后端审查能力声明冲突：8 项

纯 MCP 测试插件的作者 Operation 声明 `native_shell="none"`，但它的必需独立审查 Operation 声明 `native_shell="inherited_prototype"`。强化后端正确报告审查操作不可用，Root 因完整审查边不可用返回 `operation_runtime_unavailable`；旧测试却要求创建强化 Run，或期待更晚的 `runtime_backend_capability_missing`。

受影响：安装态纯 MCP 1 项、L4 TCAD 1 项、L5 强化后端 6 项。E5.2 不修改强化后端、审查可用性递归或该旧夹具。

### 3.2 M2 oracle 运行器接口失配：1 项

从外层退役快照恢复的 `archive/r5-m2-transform-oracle/m2-production-source.tar.gz` 摘要为：

`bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002`

它与测试冻结摘要一致，但当前 `m3_transform_equivalence_runner.py` 导入当前测试模块时，后者要求封存 M2 源码尚不存在的 `execute_compiled_transform`，因此 oracle 尚不能执行。E5.2 不改写封存源码、兼容层或变换实现。

### 3.3 OperationSpec 旧字段快照：1 项

`test_operation_spec_is_the_frozen_declarative_contract` 的字段元组早于基线中的 `complete_transform_family` 等既有字段，当前模型和该测试在 P1—P4 中均未修改。E5.2 不顺手重订 OperationSpec 公共形状。

## 4. 集成判定边界

可以据此判定：P1—P4 的新增行为在源码态、真实 wheel 安装态、Root/Worker 提交边界和跨摘要重启边界均有直接证据，没有发现本轮新增回归或内存超限。

不能据此判定：全仓原有回归已全绿、强化后端已可用、M2 oracle 已恢复、真实 Fig.4 科学闭环已经完成，或 E5/E6 已放行。

下一门由未参与实现的 GPT-6 审查者核对：

1. 四个补丁及本次测试是否保持 E5.2 文件/语义边界；
2. 新增约 550 行测试是否都是计划要求的安装态和代际证据，是否存在可删除的重复测试；
3. 10 项遗留红项是否确实与本轮无关，能否在不误报“全量通过”的前提下允许进入部署/真实端到端；
4. 若不能放行，只允许指出阻断 E5.2 目标的最小修正，不得借审查引入强化后端、全局生命周期、UI 或新治理实体开发。
