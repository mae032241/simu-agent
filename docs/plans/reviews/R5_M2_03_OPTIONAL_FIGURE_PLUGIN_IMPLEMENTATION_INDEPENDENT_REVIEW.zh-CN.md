# R5-M2-03 可选论文图证据插件实现独立审查

日期：2026-09-01  
审查者：未参与实现的独立代码审查者  
结论：**PASS**  
阻断项：**无**  
阶段门：**R5-M2-03 通过；仅放行 M3，M4 及以后仍未放行，不宣称 R5-M 完成。**

## 1. 审查范围与基线

本次是普通仓库架构/实现审查，不是 compiled Operation worker，也没有读取或调度科学任务。审查按
`scid-cross-boundary-review` 追踪真实插件、目录、Root、preflight、Run、平台和发布路径，并按
`scid-change-scope-checks` 选择聚焦与全量检查；除本报告外未修改生产代码或测试。

共享分支为 `baseline/8765-codex`，工作树包含 R5 多阶段的大量未提交和未跟踪文件，因此不能把整个
`git diff HEAD` 伪称为 M2-03 的精确补丁。本报告以 M2-03 实现证据列出的候选面、当前生产入口、
`plugins/curve_figure_evidence/`、相应目录/安装/发布回归，以及当前完整工作树为审查对象。这个基线
限制不影响下述当前行为结论，但后续提交者仍应按阶段边界整理精确提交。

## 2. 正式判断

| 审查问题 | 判断 | 独立证据 |
|---|---|---|
| 默认 `curve_score`/TCAD 是否不再注册论文图 Agent | **通过** | `curve_score.plugin:PLUGIN` 只合并 curve transform 与 science operations；默认 TCAD 编译目录为 45 个 Operation、20 个公开 Agent、20 个 Local 可运行公开 Agent，两个 figure Agent 均不存在 |
| 可选插件是否走同一入口 | **通过** | `plugins/curve_figure_evidence/pyproject.toml:15-16` 只声明 `scidiscovery.plugins` entry point；干净 wheel 环境只多出该 entry point 和两个 Operation |
| 是否产生第二注册表/状态机 | **通过** | 新插件只是一个 `PluginDefinition`；没有新增数据库表、Run 状态、Root 工具、runtime factory、目录编译器或提交协议 |
| 实现复用与依赖方向 | **通过** | 新插件运行代码共 60 行；Agent/组件声明直接引用 `curve_score` 的图数字化、Schema、validator、Worker tool 和确定性变换实现；依赖为 `curve_figure_evidence -> curve_score -> general/core`，TCAD 仍只依赖 `curve_score`，不存在反向 TCAD 导入 |
| 干净 wheel 组合与发布 | **通过** | curve wheel 不含 figure entry point；figure wheel 显式安装后才出现；TCAD 依赖解析安装仍只有 builtin/general/curve/TCAD；可选工具从安装 wheel 实际执行；源码发布显式携带新插件 |
| Root `public`/`all` 与后端能力是否同源 | **通过** | Root 目录、preflight、Run 调度和 Codex profile 均调用同一个 backend `supports_operation()`；collection extraction 在 `public` 消失，在 `all` 精确显示 `agent_collection_outputs`，且不会生成平台 Agent profile |
| 是否存在隐藏可运行能力 | **通过** | 可选完整目录 22 个公开 Agent 中 Local 只投影 21 个；audit profile 生成、collection extraction profile 不生成；不可用项仍可诊断但 preflight/Run 不能绕过能力门 |
| 消费者账本是否属实 | **通过** | 默认编译目录逐端口扫描仅发现 support Transform `scidiscovery.curve-bundle.figure-evidence.v2` 消费 manifest/report；TCAD Operation 不消费 figure Agent 或 figure schema；可选安装后新增的另一消费者仅为其显式 audit Agent |
| 奥卡姆、33 项约束与通用可扩展目标 | **通过（不升级既有状态）** | 默认目录减少两个必然不可运行 Agent；只增加 60 行插件声明，没有增加控制事实或领域分支；33 项登记仍为 33 个唯一编号，并如实保留 7 `conformant`、25 `pending_review`、1 `known_issue` |

## 3. 关键跨边界证据

### 3.1 单一注册入口与默认目录

- `plugins/curve_score/curve_score/plugin.py:9-25` 不导入或合并
  `figure_science_operations.OPERATIONS`；因此仅安装 curve 或 TCAD 不会注册
  `science.evidence.extract.figure.v1`、`science.evidence.audit.figure.v1`。
- `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py:3-52` 从 `curve_score` 复用原声明和
  实现，并通过一个 `PluginDefinition(plugin_id="curve_figure_evidence")` 注册。
- `plugins/curve_figure_evidence/pyproject.toml:10-16` 的 wheel 依赖与运行声明一致：依赖 core 和
  `scidiscovery-curve-score>=0.2.0`，入口仍是全产品唯一的 `scidiscovery.plugins` group。
- 独立目录复算结果：

  | 组合 | Operation | 公开 Agent | Local 可运行公开 Agent | catalog digest |
  |---|---:|---:|---:|---|
  | builtin/general/curve/TCAD | 45 | 20 | 20 | `546421934d77110b144788872c0110f7c250ae94da19e1db8a199058f208a403` |
  | 上述组合 + figure | 47 | 22 | 21 | `39e20b502a963ec365fdb758c729c88ba10413371fb9746197013148fdd40bf1` |
  | 默认完整组合 + InGaAs | 46 | 20 | 20 | `31a380bac3a2e231a44f9f51d867962f37957129de5aac6e5f9f7381dd439600` |
  | 可选完整组合 + InGaAs | 48 | 22 | 21 | `6f6592e5ca396cc05eb17b27420becdf0cd6f8b40cfebc77493d1ef07fcc1213` |

后两项摘要与实现证据完全一致。可选插件相对默认 curve 目录精确增加两个 Operation，二者编译所有者
均为 `curve_figure_evidence`；没有隐式增加 support/internal Operation。

### 3.2 复用、组件所有权和部署组合

- 新插件的四个局部共享组件声明分别绑定 `curve_score.science_operations` 与
  `curve_score.operation_transforms` 中的既有对象；其余 figure 组件和 Operation 也直接导入既有
  tuple。这里是在同一个编译 catalog 内为可选 Operation 建立插件限定引用，不是复制算法或建立第二
  组件注册表。
- `tcad_artifact` wheel 的元数据只依赖 `scidiscovery-curve-score`，不依赖可选 figure wheel；
  `curve_score` 也不依赖 TCAD，依赖方向正确。
- `deploy/plugin_selection.py` 仍按本地 wheel 元数据通用解析依赖，未加入 figure 专用注册表；
  `deploy/install.sh:79-90` 使用同一选择器，只有显式选择 figure 时才安装该分发包，
  `deploy/install.sh:126-129` 才启用其外部工具预检。
- `scripts/build_git_release.py:32-41` 只在既有发布树 allowlist 中加入新插件目录。该静态发布边界不是
  运行时能力注册表；运行时仍由 wheel entry point 一次编译。
- 干净 wheel 探针确认：
  - curve 环境 entry points 精确为 `builtin,curve_score,general_science`；
  - figure 环境精确为 `builtin,curve_figure_evidence,curve_score,general_science`；
  - TCAD resolved 环境精确为 `builtin,curve_score,general_science,tcad_artifact`；
  - figure 环境中的 `worker_curve_figure_digitize` 从安装 wheel 实际执行并生成 CSV 与 PNG，不依赖
    源码树导入。

### 3.3 Root、preflight、Run 与平台投影一致性

- `mcp_root_operation_routes.py:51-63` 从同一 compiled scheduler projection 构造视图；`public` 只过滤
  已标为 `unavailable` 的项，`all` 保留原声明。
- `mcp_root_operation_routes.py:91-109` 直接调用当前 `RunService.backend.supports_operation()` 和同一
  local worker tool 投影生成 `runtime_binding`。
- `mcp_root_operation_routes.py:976-994` 的精确调用 preflight 重用相同两项判断；
  `RunService.schedule()` 又在写 Run 前复核 backend，目录诊断不能成为调用旁路。
- `LocalTrustedBackend` 在 `local_workspace.py:97-109` 由输出端口是否声明 collection 唯一派生
  `agent_collection_outputs`；没有 Operation id、插件名或 figure 特判。
- Codex 生成器在 `platforms/codex.py:116-122` 也使用同一 backend 判断。独立临时平台探针得到 21 个
  Agent profile：figure audit 存在，figure extraction 不存在；与 Root `public`/`all` 结果一致。

### 3.4 消费者账本

对默认 TCAD 编译目录逐个扫描所有精确输入/输出 schema 后，结论为：

1. 两个论文图 Agent Operation 完全不存在；
2. 默认目录没有输出 `scidiscovery.figure-evidence-manifest.v1` 或
   `scidiscovery.figure-evidence-validation-report.v1` 的生产者；
3. 默认目录中这两个 schema 的唯一消费者是 curve 插件的 support Transform
   `scidiscovery.curve-bundle.figure-evidence.v2`；
4. TCAD Operation 只通过公开 curve contract、canonical curve、评分/诊断等能力依赖 curve 插件，
   没有任何 figure Agent id、figure manifest/report 端口或反向导入；
5. 显式安装可选插件后，figure audit 自然成为 manifest/report 的第二个显式消费者。这不反驳“默认
   目录唯一消费者”的账本边界，也没有把它变成 TCAD 默认阶段。

因此“论文图提取/审查不是默认 TCAD 闭环真实依赖”的结论成立。保留确定性 support Transform 和
算法是为可选插件提供可复用能力，不等于默认注册论文图 Agent。

## 4. 奥卡姆剃刀、33 项约束和通用 Agent 目标

本候选是产品面减法而不是控制面扩张：默认目录去掉两个当前后端不能完成的 Agent，新增插件只有
`__init__.py` 5 行和 `plugin.py` 55 行；没有新增表、状态、Root 工具、生命周期、目录、审批、资格、
执行或 collection 提交协议。核心源码没有按 figure/curve/TCAD 名称增加调度分支，第三方插件仍通过
同一 entry point、依赖声明和 OperationSpec ABI 组合，符合低成本、可选安装、领域中性控制面的目标。

33 项登记的结构门通过，但本报告不把结构测试伪称为 33/33 科学与安全资格。与本候选直接相关的
AUTH-001/003、TOP-002、ROLE-002、DET-001/002、PLG-001/002、RES-002、MIG-002 未发现新增退化；
尤其未建立第二事实权威、未隐藏 backend blocker、未让 Agent 手工替代确定性数字化，也未让默认
安装携带无关 Agent。既有 `SEC-002` 仍诚实保持 `known_issue`，25 个 `pending_review` 也没有因
`222 passed` 被擅自升级。

本阶段仍未证明真实模型对论文图的科学提取质量、真实 Solver 科学有效性或 Local 原生工具技术沙箱；
这些是当前文档已声明的资格边界，不是 M2-03 可选注册改造的阻断项。

## 5. 独立运行的检查

所有 pytest 均串行运行，使用 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2`，没有启用并发 pytest。

| 检查 | 结果 |
|---|---|
| `pytest -q -p no:cacheprovider tests/operations/test_m2_optional_figure_plugin.py` | **3 passed in 1.22s** |
| clean installed wheel ownership + installed tool 两项 | **2 passed in 43.31s** |
| H2b 领域边界、33 项结构、安装预览、插件所有权、clean release 聚焦集合 | **8 passed in 4.17s** |
| `pytest -q -p no:cacheprovider` | **222 passed in 77.23s** |
| `git diff --check` 与 `git diff --cached --check` | **通过** |
| 默认/可选四组合目录、消费者端口和 catalog digest 只读探针 | **通过，结果见 3.1/3.4** |
| 可选完整目录临时 Codex profile 探针 | **21 个 profile；audit 有、extraction 无** |

未运行真实 Codex 模型科学任务、真实论文资格数据重跑或真实 TCAD Solver；这些不应由本次工程测试
冒充。本阶段的 real-entry 证据由干净源码发布、wheel entry point、安装工具执行和平台配置组成。

## 6. 阻断项与只允许的下一阶段

**阻断项：无。R5-M2-03 判定 PASS。**

M2-01、M2-02 已有各自独立 PASS，本报告又在当前整体工作树上复核了 M2-03 与全量回归，因此当前
**只放行 M3（删除新旧确定性 Transform 双层）的候选设计与实现**。M3 必须继续遵守字节、媒体类型、
父链、Operation identity、集合顺序和幂等重放等价门，并在独立审查通过前不得进入 M4。本文不宣称
M3、M4—M7 或 R5-M 已完成，也不授权修改既有 33 项未关闭状态。
