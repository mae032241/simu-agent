# R5 E5.2 集成验证报告

日期：2026-09-05

状态：集成门 PASS。P1—P4 均已实现并分别通过独立复审；GPT-6 首轮指出的安装态证据缺口已按原计划补齐，[第二轮独立复审](../reviews/R5_E5_2_INTEGRATION_GPT6_SECOND_REVIEW.zh-CN.md) PASS、剩余阻断项 0。本文不宣布部署完成，不授权跳过真实端到端的人机审批与科学审查。

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

首轮 GPT-6 集成审查判定 P1—P4 生产实现通过、阻断项为零；未放行部署的原因只是原报告尚未分别证明：P1—P3 独立安装、P4 独立安装、真实不同 wheel 跨状态根切换、安装态参数正负矩阵，以及 Fig.4 配置投影。以下新增证据只关闭这些原计划内验收项，没有修改生产实现。

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

另外从 P3 提交 `e2af10c` 构建独立发行源和 wheel，不包含 P4：

```text
P3 wheel + P3 Fig.4 测试：1 passed；最大常驻内存 97,684 KiB
P3 wheel + P3 TCAD 参数测试：2 passed；最大常驻内存 94,752 KiB
```

该 P3 环境未启用 `system-site-packages`；`scidiscovery`、`curve_score`、`curve_figure_evidence` 和 `tcad_artifact` 均核对为本虚拟环境内安装模块。Fig.4 用例经真实 Root→Local Worker 依次覆盖请求准备、物化、提取、审查和后继准入；每个带 `evidence_paths` 的操作都核对冻结输入实际别名、Worker 可见枚举和提交校验一致。参数用例重放有/无清单正例，以及错清单、漏来源、换参数族等负例，而不只检查静态版本号。

另一套安装相同 P3 wheel 的 Fig.4 环境生成 `science.evidence.extract.figure.v2` 的 Codex 配置，确认：

- agent 类型和 Worker 服务器名均包含该操作的精确摘要；
- 配置中只有该操作自己的 Worker MCP 服务器；
- 配置的操作编号、摘要和工具清单与编译目录一致；工具为 `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result`、`worker_extract_pdf_text`。

### 2.2 来源投影代际

源码态 `tests/operations/test_l2_run_invariants.py` 使用相同 Operation 声明、版本和资源，只改变来源投影代际，从当前 Worker 入口跨同一状态库重启验证：

- 旧 queued 不被新摘要 Worker 领取，不能由新合同提交或显式失败收口；
- 旧 running 在截止前先因合同改变拒绝提交，过期 running 先按截止时间拒绝，二者均不能由新合同显式失败收口；
- 旧 failed 恢复草稿保留，但 `recovery_available=false`，新合同不能以它创建恢复 Run；
- 旧 completed 记录、Artifact 和收据保留，但 sealed output 为 `contract_retired`；幂等 submit 不重新登记或赋予当前合同消费权；
- 一个无来源投影且不依赖变化 provider 的实验设计 Operation 摘要保持不变；新摘要可创建自己的新 Run。

结果：5 个代际分例通过；该测试文件完整 17 项通过。

为排除“同一程序内替换摘要”的伪证据，又使用
`tests/fixtures/e52_installed_generation_probe.py` 在两个不同虚拟环境中执行：旧环境安装 P1 提交 `322d281` 的 core wheel，新环境安装当前 core wheel，两个 `scidiscovery` 模块均来自各自虚拟环境；这两个轻量探针环境共享宿主的第三方依赖，本文不把它们表述成完全独立的依赖集合。旧环境写入状态后退出，新环境才从同一状态根重开。排队、运行、过期运行、带恢复草稿的失败、完成五个隔离分例全部通过。为形成失败恢复分例，探针在两代中对同一 audit 声明把 `max_attempts` 一致设为 2；下列摘要因此是该同形恢复夹具的摘要，不是默认 audit 摘要。旧/新受影响摘要分别为
`90c4ef014eeb85b8b1a21b49d3fc632ab6362fe4703250df4cf1ea5acfb7d596` 与
`5a34f3bb271d552eed19d6262efaade879380cacbdacb44d903123e25f65e01f`；未受影响的
`science.object.review.v1` 在两套 wheel 中均为
`844970daca34297a6845b4db1eaf87a3bc0182a3d115397af807171c4ba0e69d`。

五个分例均证明旧记录和 Artifact 数量不变、旧 Worker 身份不可在新安装下恢复、新摘要可创建独立新 Run；探针没有迁移旧记录，也没有新增运行时兼容逻辑。

### 2.3 P4 独立发行边界

分别从 P3 `e2af10c` 和 P4 `036a544` 构建并安装 core wheel；两个 `scidiscovery` 模块均来自各自虚拟环境，源码路径不在解释器搜索路径，第三方依赖由宿主共享。相同非法 `comparison_present` 组合在 P3 的 JSON Schema 中错误数为 0，在 P4 中为 1；合法组合在两版中错误数均为 0。P4 的 `comparison_purposes.uniqueItems` 从无声明变为 `true`。

受影响的 `science.objective.project.v1` 摘要由
`76029d1c7e531698e7cb98e9e0b3b09319892e4f34d8ada9cdf503a709eb374c` 变为
`e72e1e0d88d75111ba8f65e66ed17f136e13f392ca0392ce82c223ae70f11860`；无关的
`science.object.review.v1` 摘要保持上述 `844970...` 不变。这证明 P4 可独立安装并与 P3 形成明确合同代际，没有借 P1—P3 主批次混合通过；实际安装事务回退仍属于后续部署门，本文不提前宣称已验证。

### 2.4 完整目录回归

串行、禁用第三方 pytest 自动加载、无 xdist：

| 范围 | 结果 | 最大常驻内存 |
|---|---:|---:|
| `tests/artifact_agent` | 58 passed | 94,444 KiB |
| `tests/operations`，不排除任何项 | 364 passed，1 skipped，10 failed | 142,516 KiB |
| `tests/operations`，精确排除下节 10 项 | 364 passed，1 skipped，10 deselected | 140,788 KiB |

表中数值只是 `/usr/bin/time` 记录的直接测试命令最大常驻内存；它们低于数值门限，但不能单独证明整个 Codex 进程树峰值或 WSL 相对基线增量。安装态探针同样保持单进程串行，未启动多 Worker；完整部署和真实 Agent 验收时仍须分别记录 Codex 进程树与 WSL 增量，本文不提前宣称这两个系统级内存门已通过。

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

可以据此判定：P1—P4 的新增行为在源码态、相互独立的真实 wheel 安装态、Root/Worker 提交边界和跨摘要重启边界均有直接证据，没有发现本轮新增功能回归；已记录的直接命令内存峰值没有超限。

不能据此判定：全仓原有回归已全绿、强化后端已可用、M2 oracle 已恢复、真实 Fig.4 科学闭环已经完成，或 E5/E6 已放行。

第二轮 GPT-6 审查者已按以下口径复核新增安装证据：

1. 四个补丁及本次测试是否保持 E5.2 文件/语义边界；
2. 新增测试与验收探针是否都是计划要求的安装态和代际证据，是否存在可删除的重复；
3. 10 项遗留红项是否确实与本轮无关，能否在不误报“全量通过”的前提下允许进入部署/真实端到端；
4. 若不能放行，只允许指出阻断 E5.2 目标的最小修正，不得借审查引入强化后端、全局生命周期、UI 或新治理实体开发。

复核结论为 PASS、剩余阻断项 0。下一步只进入原计划的部署事务、服务与 Codex 切换、系统级内存记录及真实 Fig.4 科学闭环；不在 E5.2 集成阶段追加新架构或范围外清理。
