# R5-M7.4 最终物理成果与复杂度独立审查

日期：2026-09-02  
审查性质：未参与实现的物理量、跨边界与奥卡姆审查  
结论：**FAIL（EvidenceAudit：revise）**  
阻断项：**4**  
阶段门：**M7.4 未关闭，不放行 M7.5；不得宣称 M7 或 R5-M 完成。**

## 1. 结论摘要

当前候选的多数可直接复算事实成立：生产 Python 为 141 文件、47,177 行，生产树摘要正确；完整
模块的八删三增成立；Root 工具、fresh DB 表、Run/Execution 状态、Operation 三类字段、33 项状态
均与当前实现一致。当前运行路径也没有发现第二 Operation 注册表、第二默认 Run 生命周期或通用核心
按 TCAD/曲线/InGaAs 分支。Hardened、portable 和 TCAD transport 的“随包存在、按需导入/实例化”
边界基本如实。

但是，报告的两个核心复杂度口径和两个接入劳动事实不准确：旧 Task 责任的当前后继被计为零；实际
默认安装目录被五插件显式组合替代；M6/M7 阶段净变化使用了 M6 的中间端点；盲 CSV 插件的两个
Agent Operation 被写成一个。这四项都属于 M7.4 明确要求复算的材料事实，不能由正确的全树净行数
或通过的回归测试代替，因此当前报告不能进入最终回归阶段。

这些问题只要求修正计量脚本、物理报告和相应结构门；本审查没有发现需要修改生产运行代码的理由。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
|---|---|
| S1 | 待审报告 `docs/plans/evidence/R5_M7_4_FINAL_PHYSICAL_REPORT.zh-CN.md`，SHA-256 `c1b2e12e268843382ed37064eb698cf12f2d5df8283a2e055e448a4ed645b99c`。 |
| S2 | 冻结计量生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；当前聚合器 `scripts/r5_current_metrics.py`，SHA-256 `b81b7d30d1e3c60b965332e875866ef9cf6df6735fae06501a74b7c330002795`。 |
| S3 | M0 账本，SHA-256 `7ce1d20f9533180eff076ce41bdb8915a1a47ed01170e805961254d00bfad5ac`；M6 最终闭合证据，SHA-256 `b7ec8b5fab521df1c59b4233cfa3a70293a41829791bd424b858012e553d5f0a`；M7.1 证据，SHA-256 `19c736ff355c338f89702655640c05e5e899f2a9429a906a37af20a3f770b9ba`。 |
| S4 | 当前 `src/scidiscovery/**/*.py` 与 `plugins/**/*.py` 排序内容清单；独立重算摘要 `d6bfe480ec7b9b724f27c901bce6277da2a2a489dd7823b1f30a7857385078cd`。 |
| S5 | L0 Task 迁移冻结 `docs/plans/evidence/R5_L0_S2_CLASSIFICATION_AND_HARDENED_FREEZE.zh-CN.md`，SHA-256 `66d0d5685b72a22cb15959aa04262e49fed707db2dba1c29567946f6c0ba3a51`；当前五个 `run_*.py`、`runs.py` 与 `local_workspace.py` 聚合摘要 `7dbf18d43534fe49305df99172158233021d2518d1e08bb76af2d9cfa0204e1a`。 |
| S6 | 当前 `spec.py`、`catalog.py`、`mcp_root.py`、`runtime.py`，SHA-256 依次为 `ae7838bf...`、`a1e12de1...`、`e2d8876b...`、`9e1e73c2...`；另以 fresh Local/Hardened runtime 和 Pydantic 模型作独立探针。 |
| S7 | 核心及四个领域 wheel 的五份 `pyproject.toml`、`deploy/install.sh`、`deploy/plugin_selection.py`，聚合摘要 `8df3373ce3c7a8edab0d0d6653c46e36cc6a0bace810fbb59a139224f9ed7326`。 |
| S8 | 盲 CSV 源码四文件及 `pyproject.toml`，聚合摘要 `2f148c6616c6721f12dda77e470dacab9744e410431df168f327f7b43ff7522c`。 |
| S9 | 33 项约束注册表 `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`，SHA-256 `deca6442c486303e169362eceb76c78db3dc479ab1994d7a2085f8cbd3191abf`。 |
| S10 | 本轮独立命令记录：文件/行数/摘要、AST/Pydantic/SQLite、六种精确插件组合、导入集合、生产域 token、entry-point/编译点检索、38 项串行聚焦测试、`compileall` 与 `git diff --check`。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
|---|---|---|---|
| `production_physical_totals` | pass | S1—S4, S10 | 当前为 141 文件、47,177 行，`src/plugins=95/46` 文件、`24,756/22,421` 行；摘要与报告一致。 |
| `whole_module_add_delete` | pass | S1, S3, S4, S10 | 八个列名模块确实不存在，新增论文图入口两文件为 58 行，直接实例管理为 145 行；八删三增与净减 5 文件闭合。 |
| `stage_net_attribution` | revise | S1, S3, S4 | 最终 M6 端点为 46,970 行，故 M6 为 -419、M7 为 +207；报告的 -430/+218 使用了中间端点。 |
| `r0_successor_completeness` | revise | S1, S2, S5, S10 | Task successor 清单只列已删除的 `task*.py`，遗漏已明确承接生命周期、输出、工作区和恢复责任的 Run/Local 模块，3,138 不是完整后继总量。 |
| `root_db_state_and_fields` | pass | S1, S6, S10 | Root 26；Local 15 表、Hardened 额外 1 表；Run 4 态、Execution 10 态；字段为 12/17/12。 |
| `catalog_install_projection` | revise | S1, S6, S7, S10 | 默认核心安装为 63 组件/14 Operation；186/43 是显式 TCAD+InGaAs 组合，不是默认目录。 |
| `single_registry_and_runtime_spine` | pass | S4, S6, S7, S10 | 一个 entry-point group、一个 `compile_catalog` 构造点；Local/Hardened 共用 RunService，后者为显式后端；未见第二目录权威。 |
| `domain_core_boundary` | pass | S4, S6, S10 | 通用核心生产 Python 对 TCAD、InGaAs、Fig.4、device_parameter、curve_score 和 Sentaurus 的直接命中为零；按 executor/port 类型分派不构成领域分支。 |
| `blind_plugin_labor` | revise | S1, S8, S10 | 有效源码确为四文件 353 行加 17 行元数据，但 `PLUGIN.operations` 是 AUTHOR、REVIEWER 两项，不是一项。 |
| `constraint_status` | pass | S1, S9, S10 | 33 个唯一 id，7 conformant、25 pending_review、1 known_issue；`SEC-002` 未被错误升级。 |
| `occam_and_claim_scope` | revise | S1—S10 | 未发现生产侧新增第二权威，但不完整 successor 和错误默认目录会夸大减重及默认面收敛，当前不能据此通过奥卡姆结论。 |

## 3. 阻断项

### B1：所谓“旧六个集中责任完整后继 3,138 行”遗漏了 Task 的真实后继

位置：`scripts/r5_current_metrics.py:18-27,53-70`；待审报告第 1、8 节。

`TASK_SUCCESSORS` 只包含已经全部删除的 `tasks.py`、`task_shared.py`、`task_worker_files.py`、
`task_evidence.py`、`task_outputs.py`，所以脚本机械得到 Task 当前 0 行。可是 L0 冻结已经明确：
Artifact/终态迁入 `RunService`，Task 输出合同由 RunService 使用，文件协议中的 Local seal 迁入新的
本地工作区后端。当前 `runs.py`、四个 `run_*.py` 和 `local_workspace.py` 也确实实现创建、打开、
heartbeat、提交、完成、失败、恢复、assignment、输出校验和工作区封存。

仅把这六个无争议后继计入，Task 当前下界已经是 2,433 行，六职责当前下界由 3,138 变为 5,571；
因此 77.02% 的净减主张不成立。这个 5,571 仍只是下界，不是建议硬编码的新总数：还需独立检查已
删除的 scheduler topology 和全局 role profile 是否有语义后继，再冻结全局无重不漏的 successor
清单。

修正要求：补齐语义后继计量及精确集合测试，或删除“完整后继总量/77.02%”主张，只报告可证明的
物理事实。不得把 Run 文件改名回 Task，也不得为计量新增运行包装层。

### B2：186 组件/43 Operation 被错误标为“默认目录”

位置：待审报告第 3、4.2、8 节；`deploy/install.sh:10-12,79-91,267-274`；根
`pyproject.toml:27-29`。

当前安装器的 `SCID_PLUGINS` 默认值为空，核心 wheel 固定只有 `builtin` 与 `general_science` 两个
入口。独立编译的实际组合为：

| 安装/声明组合 | 组件 | Operation | public/support | Agent/Transform/Approval/Effect |
|---|---:|---:|---:|---:|
| 默认核心 `builtin+general_science` | 63 | 14 | 11/3 | 10/3/1/0 |
| 显式曲线 | 103 | 22 | 15/7 | 14/7/1/0 |
| 显式曲线+论文图 | 116 | 25 | 17/8 | 16/8/1/0 |
| 显式 TCAD（含曲线依赖） | 180 | 42 | 24/18 | 20/18/3/1 |
| 显式 TCAD+InGaAs | 186 | 43 | 24/19 | 20/19/3/1 |
| 上一组合再加论文图 | 199 | 46 | 26/20 | 22/20/3/1 |

因此报告的 186/43 和 199/46 数字本身可复现，但它们分别属于两个显式组合，不是“默认”及“默认
加论文图”。这种命名与第 3 节正确区分安装/注册/导入的口径直接冲突。

修正要求：第 4.2 和第 8 节必须首先报告真实默认核心 63/14，再把 186/43、199/46 标成精确显式
组合；不能用源树可导入五个插件替代安装器默认注册事实。

### B3：阶段净变化使用 M6 中间状态，未按最终端点记账

位置：待审报告第 2.1 节；M6 闭合证据第 10、11 节；M7.1 证据第 4 节。

M5 最终为 47,389 行，M6 通过第三名复审的最终端点为 46,970 行，当前为 47,177 行。正确阶段变化
应为 M6 `-419`、M7 `+207`，不是 `-430/+218`。总变化仍为 `-2,846`，所以这不是全树总数错误，
而是用返工前中间态分割最终阶段归因。

修正要求：改用每阶段最终 PASS 端点，并保持总和 47,177；首轮/中间失败数字可保留在历史证据中，
不能作为最终阶段边界。

### B4：盲 CSV 插件劳动说明少记一个 Agent Operation

位置：待审报告第 5 节；
`tests/fixtures/plugins/blind_csv_operation_plugin/blind_csv_plugin/plugin.py:134-194`。

四个有效源码文件为 5、119、197、32 行，合计 353 行；`pyproject.toml` 为 17 行，这两项正确。
但是该 PluginDefinition 注册 `(AUTHOR, REVIEWER)` 两个 Agent Operation，且作者 Operation 的 review
edge 指向 reviewer；不是“一个 Agent Operation 声明”。

修正要求：写成“一个 entry point、一个 PluginDefinition、两个 Agent Operation、一个领域工具及其
Schema/validator”。测试夹具的 `build/lib` 是生成副本，不计入有效手写源码，但报告可明确该口径。

## 4. 已通过的物理和跨边界事实

- 生产 Python 摘要、141/47,177、95/24,756 与 46/22,421 全部独立复算一致；operations 包为
  8 文件/2,100 行，`catalog.py` 为 734 行。
- 八个删除模块均已不存在；当前仅新增的三个 M 系列完整模块与阶段证据闭合。报告没有把论文图
  算法本体错误说成已从 curve wheel 删除。
- Root 26 项，Local fresh DB 15 表；显式 Hardened 只额外创建私有 `active_transport` 一表。TCAD
  controller 的 `submissions` 不属于通用数据库。
- `InputPortSpec/OutputPortSpec/OperationSpec` 分别为 12/17/12 字段；Run 仍只有
  `queued/running/completed/failed`，Execution 10 态只在 Effect 路径存在。
- `compile_catalog()` 是唯一 `CompiledCatalog` 构造入口，installed discovery 只有
  `scidiscovery.plugins` 一组；public/support/internal/all 是投影。Local/Hardened 的 Worker handler
  映射按单个 compiled Operation 派生，不是第二 Operation 注册表。
- 普通 Local 组合启动没有导入 Hardened、portable、TCAD command/socket/SSH/remote runner 或论文图
  入口；配置选择的 runtime factory 才惰性导入一个 TCAD adapter。源码随 wheel 分发与默认导入被
  正确区分。
- 通用核心没有发现 TCAD、InGaAs、Fig.4、Sentaurus、device_parameter 或 curve_score 领域分派；
  Effect adapter 与普通 Run 分离也没有形成第二科学结果权威。
- 33 项状态精确为 7/25/1；真实远端失联、通用大附件、多租户强隔离、更多领域科学质量及真实发布
  演练仍是后续要求，不作为本次当前失败。`SEC-002` 保持已知问题是诚实边界。

## 5. 独立执行记录

全部测试严格串行，设置 7 GiB 虚拟内存上限和 `MALLOC_ARENA_MAX=2`，没有并行插件。

```text
find ... sha256sum / wc -l
# d6bfe480...；src 95/24,756；plugins 46/22,421；合计 141/47,177

python scripts/r5_current_metrics.py
# 当前脚本复现 3,138，但 Task successor 明细全部指向不存在文件，见 B1

python <Pydantic + ROOT_TOOLS + fresh Local/Hardened SQLite 探针>
# fields 12/17/12；Root 26；Local 15 表；Hardened 16 表

python <六种显式 PluginDefinition 组合编译探针>
# 63/14、103/22、116/25、180/42、186/43、199/46，见 B2

python <sys.modules 默认导入探针>
# 未导入 Hardened/portable/TCAD adapters/SSH/runner/figure plugin

pytest -q -p no:cacheprovider \
  test_architecture_constraint_matrix.py \
  test_m2_optional_figure_plugin.py \
  test_m5_plugin_ownership_and_default_surface.py \
  test_m6a_direct_instance_management.py \
  test_m6b_operation_input_admission.py \
  test_m6c_producer_topology_removal.py \
  test_r5_catalog_stages.py \
  test_l6_runtime_capabilities.py
# 38 passed in 13.86s

python -m compileall -q src plugins
git diff --check
# 通过
```

本审查没有重复 M7.5 的全量测试、clean-wheel 全矩阵、真实浏览器或真实 solver；这些未来观察不能
修复上述当前静态计量错误，也不是发现四个阻断的必要条件。

## 6. 最终判定

**FAIL；阻断项 4。M7.4 未关闭，不放行 M7.5。**

返工应只修正计量脚本、结构门和物理报告：补齐或撤销不完整 successor 主张，分开真实默认目录与
显式领域组合，按最终阶段端点记账，并如实记录盲插件的两个 Agent Operation。修复后必须由未参与
本轮修正的全新独立审查者重新复算；本报告的其余通过项不自动继承为下一轮批准。
