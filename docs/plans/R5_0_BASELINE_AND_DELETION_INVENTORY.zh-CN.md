# R5-0：权威语料、结构基线与删除清单

状态：第三轮独立审查通过；只放行 R5-A1，不放行 R5-A2。R5-0 生产行为未修改。

日期：2026-08-29  
上位方案：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`  
行为基线：`baseline/8765-codex@404aeb14c6ebc4b08bac599db91eaee54c103f48`

本文件冻结 R5 开始前的事实和删除顺序，不是第二份架构权威。当前架构事实只在
`docs/ARCHITECTURE.zh-CN.md`/`docs/ARCHITECTURE.md` 描述；R5 总体状态只在上位计划记录。

## 1. 本阶段产物

- 中英文当前架构说明已经同步为 R4 已实现事实，并显式列出 R5 债务；
- `scripts/r5_baseline_metrics.py` 可在不导入产品包的情况下复算三重结构指标、职责后继聚合和
  五类精确消费者；
- `tests/fixtures/r5_structure_baseline.json` 冻结 R5-0 数值和三种洁净安装目录摘要，
  `tests/fixtures/r5_structure_inventory.json` 冻结完整结构与消费者集合；
- `tests/fixtures/r5_e2e_tcad/` 冻结 R5-G 小任务、输入身份和预先量表；
- 本文件冻结每个删除候选的生产、测试、文档和动态入口消费者。

## 2. 结构与目录基线

### 2.1 防搬移的三个统计口径

| 口径 | R5-0 | 8765 | R5 放行规则 |
| --- | ---: | ---: | --- |
| R0 六个 Python 职责聚合 | 11297 行 | 13657 行 | 原职责迁到新文件仍计入；最终相对 8765 至少净减 10% |
| `src/scidiscovery/operations/` 全包 | 7 文件、2060 行 | 不适用 | R5 结束不得高于 2060 行 |
| `src/ + plugins/` 全部生产 Python | 126 文件、62533 行 | 不作为目标分母 | core→plugin 仍计入，核对真删除是否大于新增胶水 |

`deploy/install.sh` 当前 1026 行，8765 为 1008 行；它作为部署表面单列，不进入第一项 Python
分母，但必须报告增减。单文件行数只诊断职责，不是压行目标。

选定大文件当前值：`mcp_root.py` 3531、`tasks.py` 6786、`mcp_worker.py` 1387、
`general_science_plugin.py` 2470、`general_transform_operations.py` 1095、`catalog.py` 636 行。
顶层类/函数清单由基线脚本解析，R5-D 以变化原因和调用者而非文件名美观决定拆分。

第一口径的职责所有者和后继路径由脚本中的 `RESPONSIBILITY_SUCCESSORS` 版本化声明。删除原文件时
该路径仍以零行保留；若职责拆入新文件，必须把新路径追加到原所有者的后继元组并继续聚合，不能
用改名获得虚假减重。专项测试完整比较 R0/R5-0 行数、operations 包、生产 Python 总量、部署行数、
后继路径、逐路径顶层定义及核心领域词位置摘要。历史方案文档只允许单调增加，不允许从冻结集合
消失；生产、动态入口、测试和当前文档消费者必须精确相等，后续阶段只能用带原因的断代快照修改。

### 2.2 编译目录基线

摘要算法：对按 operation id 排序的 `id=digest` 行计算 SHA-256。

| 安装组合 | 总数 | public | support | internal | 摘要 |
| --- | ---: | ---: | ---: | ---: | --- |
| core（builtin + general science） | 32 | 18 | 14 | 0 | `a8257982…f5a11` |
| full（+ TCAD + curve-score） | 49 | 23 | 26 | 0 | `f1dec7d2…fc4a1` |
| full+InGaAs | 50 | 23 | 27 | 0 | `3312dc08…dd1ba` |

这些摘要只冻结 R5-0 候选。完整参数能力迁入 TCAD 后，core/full 摘要按源码断代原则允许变化；
审查必须解释变化来自声明所有权迁移，而不是丢失行为。

`test_r5_clean_wheel_catalogs_match_frozen_snapshot` 复用同一 `installed_probe`，在不依赖源码路径的
wheel 环境中分别计算上述三组完整 `id=digest` 集合摘要并与快照比较；这不是从源码计数推断安装
结果。

## 3. 删除与迁移清单

### 3.1 完整设备参数纵切面：活跃依赖，R5-A1 先迁移

| 当前所有者/消费者 | 当前职责 | R5 处置 |
| --- | --- | --- |
| `schema/device_parameters.py`、`schema/__init__.py` | 参数需求、数值、来源、coverage/uncertainty 类型与通用导出 | 类型与算法归 TCAD 包；core-only 不再导入/导出 |
| `general_transform_operations.py` | coverage、uncertainty Transform 和组件 | 原 operation id 迁入 TCAD `PLUGIN`，不复制实现 |
| `general_science_plugin.py` | 参数资格 projector、两个 Approval Operations、provider | 全部迁入同一 TCAD `PLUGIN` |
| `schema/experiment_intent.py` | 通用 validator 解释 `DeviceParameterSet` 和参数映射 | 通用 validator 去参数语义；TCAD validator/guard 承担映射 |
| `tcad_artifact/plugin.py`、author/reviewer validator | 反向导入核心参数 Schema/provider | 改为插件内引用并保持完整批准组/uncertainty 门 |
| `TaskService`、Root、AGENTS 两个 legacy bridge | 参数提取/审计的旧任务与 bundle 特判 | 两个 Agent Operation 真路径通过后删除 |

分类：**活跃主路径依赖，禁止直接删除**。R5-A1 必须独立审查通过，才可开始 A2。

### 3.2 旧角色发现：最后 bridge 的活跃依赖，A1 后删除

| 符号/入口 | 生产消费者 | 测试/文档消费者 | 替代 |
| --- | --- | --- | --- |
| `scidiscovery.agent_role_packs` | `platforms/roles.py` 的 entry-point 扫描 | baseline discovery、role contract、platform tests | 唯一 `scidiscovery.plugins` |
| `load_roles()` | `runtime.open_runtime` 构造 legacy output/context；`platforms/codex.py` 生成 Agent 与期望集合；`deploy/install.sh` 探针 | baseline discovery/role/platform tests | `TaskOperationAuthority` + 单一 CompiledCatalog |
| role frontmatter 行为元数据 | `load_roles()` 与 prompt 组合 | roles 文档/平台测试 | Operation 编译合同；纯可读身份文本可保留 |
| scheduler prompt loader | 当前和 role discovery 同模块 | Codex 配置测试 | 独立静态 scheduler 资源加载，不发现角色 |

分类：**A1 前活跃，A2 删除**。不得保留空 loader 或兼容 facade。

### 3.3 旧 Transform 发现：发布集合为空但生产可调用，A2 删除

| 符号/入口 | 生产消费者 | 测试消费者 | 替代 |
| --- | --- | --- | --- |
| `scidiscovery.transform_adapters` | `transforms.py` loader；control daemon；安装探针 | baseline discovery、general/TCAD transform tests | compiled Transform Operation |
| `load_transform_adapters()` | control daemon 构造 Root；安装器 | 同上 | `CompiledCatalog` 中的 transform executor |
| `scidiscovery.operation_specs` | 当前发布入口为零 | 安装态反例 | 唯一插件入口；保持不可复活负例 |

分类：**旧入口发布集合为空，但源码生产调用仍可达**。A2 从 clean-wheel control daemon 和安装
探针删除，不能只修改 pyproject metadata。

### 3.4 旧 Root 创建表面：部分仍被历史测试/调度提示消费，A2 删除

| Root 工具 | 当前消费者 | 保留的底层权威 | R5 处置 |
| --- | --- | --- | --- |
| `task_schedule` | legacy 参数 bridge、baseline/R3/R4 测试、scheduler prompt | TaskService | A1 后从 Root MCP 删除；Agent 只由 `operation_invoke` 创建 |
| `artifact_transform` | scheduler prompt、legacy/general/TCAD transform 测试 | Artifact/CAS 与确定性组件 | 从 Root MCP 删除；Transform 只经 `operation_invoke` |
| `approval_request_create` | Root 内部及旧直接审批测试 | ApprovalService | 已迁移科学审批不可直建；实例/进程专用窄审批另行保留 |
| `execution_request_create` | Root 内部及旧 Effect 测试 | ExecutionService | 已迁移 Effect 不可直建；仍保留执行生命周期查询/同步 |

`execution_approval_request_create` 是当前精确执行 UI 授权桥，不在上述直接 Effect 创建删除项中；
R5 只有在 compiled Effect 已提供等价内部路由时才可收窄其调度可见性，不能删除人工授权。

### 3.5 领域特判与静态拓扑：R5-B/C 删除

- Root 固定 `extraction_primary`、参数 legacy producer、intake revision operation/port：R5-B 以
  统一 Transform 调用指纹和完整 producer family 总函数替代；
- TaskService 的设备参数 bundle、figure/TCAD/profile 分派：迁入 compiled validator、bundle
  validator、workspace hook 或 TCAD runtime component；
- `scheduler_topology.py` 的 `RoleRuntimeProfile`、`_ROLE_PROFILES`、`role_runtime_profile`，以及
  `_ADVICE`、`_CAPABILITIES` 和角色预算：删除；不得误删 scientific payload 的
  `RecommendedTaskMode`/`NextTaskMode`；
- `core_context_policies.py` 中已由端口 exposure/cohort/guard/review edge 表达的分支：删除；真正
  实例/会话控制策略按所有者保留；
- `scientific_readiness` 的领域行动和 blocker：R5-C 收缩为 inventory + exact preflight，不增加
  排名器或固定拓扑。

### 3.6 精确消费者与替代权威

`tests/fixtures/r5_structure_inventory.json` 是下表的逐文件机械展开；每个键分别保存
`production`、`dynamic-entry`、`test`、`current-doc`、`historical-doc` 五类精确文件集合和出现
次数。文档不再手抄会漂移的路径列表。A1/A2 删除时，生产、入口、测试和当前文档集合必须按该
键归零或迁到所列替代权威；历史文档保留为审计记录。

| 冻结键/精确符号族 | 阶段 | 唯一替代消费者/权威 |
| --- | --- | --- |
| `device_parameter_schema`、`device_parameter_bundle_validator`、`parameter_operation_ids` | A1 | TCAD 插件内 Schema、validator、四个原 operation id |
| `legacy_role_entry_point`、`load_roles` | A2 | `scidiscovery.plugins`、CompiledCatalog 与 compiled Agent authority |
| `legacy_transform_entry_point`、`load_transform_adapters`、`broken_operation_entry_point` | A2 | 同一个 CompiledCatalog；旧 group 必须不可发现 |
| `task_schedule` | A2 | `operation_invoke` 的 Agent 分支；底层 TaskService 仍是生命周期权威 |
| `artifact_transform` | A2 | `operation_invoke` 的 Transform 分支；Artifact/CAS 仍是数据权威 |
| `approval_request_create` | A2 | compiled Approval Operation；ApprovalService 仍是决定权威 |
| `execution_request_create` | A2 | compiled Effect Operation；ExecutionService 仍是执行记录权威 |
| `producer_family_hardcoding` | B | 编译端口关系与 Transform 调用指纹产生的通用 producer family |
| `scientific_readiness` | C | public catalog inventory + exact `operation_preflight` |
| `role_runtime_profile`、`core_context_policy` | C | compiled Operation limits、ports、cohort、guard、review edge |

### 3.7 大文件：保留到删除完成后再判定

`mcp_root.py`、`tasks.py`、`mcp_worker.py`、两个 general plugin 文件和 `catalog.py` 当前都是活跃
主路径，不能因行数直接删除。R5-D 只拆 A—C 删除后仍有独立变化原因的职责；移动后的代码仍计入
第 2.1 节指标。

## 4. 真实入口删除门

R5-A2 必须从 clean-wheel 观察以下四个入口，而不是只搜源码：

1. `open_runtime` 无旧 role/transform loader；
2. `scid init codex` 只由 CompiledCatalog 生成 Agent 配置；
3. control daemon 可在无旧 transform loader 时启动并解析请求；
4. Worker daemon 可在无旧 role loader 时启动并构建 compiled tool services。

旧 entry-point group、旧 Root 工具或旧 loader 从对应真实入口必须失败，失败原因不能是无关 import
错误。安装器只能断言用户选择的插件协议和目录，不得重建固定角色/operation 列表。

## 5. R5-G 冻结任务与边界

`tests/fixtures/r5_e2e_tcad/manifest.json` 冻结一个已有完整数据的 Fig.4 基线恢复问题。它使用同一
ActiveResearchBundle 的 baseline deck/manifest/PLX/log、exact replay project/review/audit、replay
PLX/TDR/log/runtime manifest、曲线 bundle、目标指标以及 scorer 实现与内嵌合同。全部持久输入均
位于 `workspace/`；旧 staging CAS 不再是唯一来源。

科学范围机械冻结为 InGaAs、Fig.4 标签和 480 °C。目标曲线明确是用户冻结目标，不是已经通过
独立审计的论文图证据；InAlAs、candidate 和 Fig.7 字段不得进入主张证据；mesh diff 只允许作为
待检验的 prior signal。科学问题只要求解释“为什么恢复门仍失败、可排除什么、下一项最小区分
实验是什么”。重放层不是新 Sentaurus 运行；真实 solver 可选且必须经精确 UI 授权。

manifest 逐项冻结 production Operation id、每个必需输入端口、输出、资格 UI、不可跳过规则和
最短允许拓扑。历史导出缺失 legacy experiment plan、capability 及当前 review schema，因此严禁
伪造父对象来冒充通用 package/attestation/curve-score 链；必做机械复算使用已安装 InGaAs 插件的
`ingaas.fig4-baseline-recovery.v2`。评估专用 replay adapter 的 id/version、请求、实现和四项输出
摘要也在运行前冻结，它只复制校验后的历史字节，不执行 solver 或科学变换。该适配器由仅在
R5-G 评估环境安装的标准 `scidiscovery.plugins` 夹具插件贡献；插件只声明一个 public Effect，
其 runtime factory、historical-replay capability、固定审批 projector 和 preparation profile 均被
manifest 绑定，不进入 core/full/full+InGaAs 三种生产组合。

运行前复核发现，原冻结文字把两路模型误写成 `gpt-5.6-sol`，与启动编译目录中九个必需 Agent
Operation 的不可变 `gpt-5.4` 模型权威冲突。尚未产生任何 R5-G 科学结果前修订为：多角色一路
逐项使用编译后的 OperationSpec 模型且禁止补丁生成配置，单 Agent 对照同样使用 `gpt-5.4`；两路
均固定 high reasoning、相同离线输入和可比工具集合。aggregate input/output token 上限仍为
120000/60000，墙钟上限 7200 秒，单 Agent 的 token/墙钟允许差仍为 10%/20%。实际模型、工具、
token、墙钟与修复次数必须记录，不能看过结果后换预算。该修订只修复冻结清单与真实启动权威的
矛盾，不改变任务、输入、量表、拓扑或通过门，并须经独立增量复审后方可运行。预冻结量表包含六
个维度和七类严重退化；一次运行不能被解释为统计优越性。

同一运行前可执行性复核还发现，冻结拓扑曾把通用证据资格产生的 `scientific_foundation` 重复传给
TCAD author/reviewer；这两个可选端口在当前 TCAD 合同中专属于完整设备参数 cohort，只接受参数
资格，不能接收通用证据资格。未产生任何 Agent 结果前，R5-G 依最小授权原则删除这两个重复可选
绑定：精确 experiment plan 与独立 plan review 仍是 TCAD 两角色的必需科学输入，通用 foundation
继续供假设和实验链使用。没有放宽 TCAD 参数资格，也没有修改生产 OperationSpec；修订须经独立
增量复审。

原始冻结输入保存在仓库下非 `/tmp` 的 `workspace/` 持久位置，并由
版本化 manifest 的大小与 SHA-256 校验。R5-G 新运行的 state/secret/raw logs 必须进入权限 0700、
Git 忽略的 `.scidiscovery/r5-e2e-private/`；`deliverables/r5-e2e/` 只保存脱敏可发布证据。

## 6. 可复现命令与内存边界

所有命令严格串行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
python scripts/r5_baseline_metrics.py
python -m pytest -q tests/operations/test_r5_frozen_baselines.py
```

clean-wheel 目录组合、121 项 R4 聚焦测试和全仓测试的本轮结果在 R5-0 独立审查前追加到第 7 节。
任何命令不得超过 8 GiB，也不得并行 pytest。

## 7. 验证记录

全部命令均使用第 6 节的 7 GiB 限制并严格串行：

- R5 冻结基线专项：`6 passed in 28.40s`；完整比较结构/消费者快照，从 clean wheel 核对三种
  catalog，逐文件验证 19 个持久科学输入、task/rubric、replay plugin/adapter/request 与 scorer
  合同，并在评估插件 clean wheel 中实际走过 `operation_invoke → UI → ExecutionBridge → collect`
  的四输出登记与摘要校验；
- R4 跨边界聚焦矩阵加 R5 新测试：`127 passed in 53.89s`；其中既有 121 项包含
  core/full/full+InGaAs/broken clean-wheel 隔离安装和真实入口探针；
- 全仓串行回归：`251 passed in 76.85s`；
- `scripts/r5_baseline_metrics.py` 成功复算第 2 节数值；
- `git diff --check` 在送审前必须再次通过。

根 `MANIFEST.sha256` 仍是 R4 冻结发布候选，当前故意不把未审查 R5-0 候选冒充为发布清单。R5-0
独立审查报告作为候选外见证；R5-F 统一生成下一代根发布清单并执行 clean release 校验。

## 8. R5-0 完成门

- 两份架构说明表达相同已实现事实与相同债务；
- 删除清单没有把活跃依赖误标为可直接删除；
- 三重结构口径和部署脚本单列可机械复算；
- 目录组合与测试结果来自 7 GiB 串行真实命令；
- TCAD 小任务文件全部存在且 hash 一致，量表在运行前冻结；
- 独立审查者确认未删除承重边界、未把 R5 目标冒充当前事实、未扩张为新控制系统。

本门通过前不得进入 R5-A1。
