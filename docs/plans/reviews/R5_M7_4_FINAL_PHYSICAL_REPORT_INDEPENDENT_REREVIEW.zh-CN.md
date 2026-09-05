# R5-M7.4 最终物理成果与复杂度返工独立复审

日期：2026-09-03  
审查性质：未参与实现和首审的全新独立复审  
结论：**PASS（EvidenceAudit：pass）**  
阻断项：**0**  
阶段门：**M7.4 可以关闭并放行 M7.5；本结论不宣称 M7 或 R5-M 已完成。**

## 1. 结论摘要

首审的四个阻断项均已由当前候选实质关闭，不是只改了叙述：

1. 当前计量器把旧 Task 的后继扩展到由 `runs.py` 和四个 `run_*.py` 构成的五个 Run/输出/当前模块、
   Local/Hardened 工作区与文件实现、Local PDF 工具和无身份工具上下文；Worker router、scheduler prompt 和 Codex
   角色/profile 后继也以整文件列入同一全局集合。脚本和结构门同时拒绝重复路径与不存在路径。
2. 报告首先给出安装器真实默认核心 `builtin + general_science = 63 组件/14 Operation`，并将
   `186/43`、`199/46` 分别限定为显式 TCAD+InGaAs 组合及其再加论文图的组合。
3. 阶段账使用最终通过端点：M5 为 47,389 行，M6 为 46,970 行，当前为 47,177 行，所以 M6
   `-419`、M7 `+207`；全部阶段净变化仍闭合为 `-2,846`。
4. 盲 CSV 接入劳动现准确记为四个有效源码文件、353 行，加 17 行包元数据，并明确包含两个 Agent
   Operation、一个领域工具和一条精确独立审查边。

其余物理事实也可独立复算：生产 Python 为 141 文件、47,177 行；八删三增成立；Root 为 26 项；
完整 Local 通用数据库为 15 表，Hardened 只额外增加一个私有表；Run 为四态，Execution 为十态；
三类 Operation 合同字段为 12/17/12。没有发现第二 Operation 注册表、第二普通 Run 生命周期或通用
核心中的领域名称分派。报告正确区分了未安装、未注册/实例化和未导入，也没有把 Local 软隔离说成
操作系统强隔离。

因此，当前 M7.4 报告足以支持“默认主干比 M0 更小且权威仍唯一”的有限结论。它没有把 7,062 行
包装成全系统复杂度得分，也没有把测试通过扩大成任意领域通用性或生产级强隔离证明，符合本轮
奥卡姆目标。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
|---|---|
| S0 | 首审报告 `R5_M7_4_FINAL_PHYSICAL_REPORT_INDEPENDENT_REVIEW.zh-CN.md`，SHA-256 `a7f7849d8421738e23d2066169063ee661548ac07965f5fb855020f67d105f9c`；只用于定位四个原阻断，不继承结论。 |
| S1 | 修订后的物理报告 `R5_M7_4_FINAL_PHYSICAL_REPORT.zh-CN.md`，SHA-256 `b97d34b91aacef9e8eeade872a442278ac153e93f1d14325c341ae1db25c0868`。 |
| S2 | 当前计量器 `scripts/r5_current_metrics.py`，SHA-256 `a7f8323db2f81cc4fed00b39fa92df51fc24ed2a25e5715df3095e74b882d6c2`；冻结基线生成器 SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`。 |
| S3 | M0 冻结账本 SHA-256 `7ce1d20f9533180eff076ce41bdb8915a1a47ed01170e805961254d00bfad5ac`；M6 最终第三次独立复审 SHA-256 `cfd9b51e31fedf9555fee68d8eb7055256b551f787f19fc4937735e2a0e29a77`。 |
| S4 | 当前 `src/scidiscovery/**/*.py` 与 `plugins/**/*.py` 的排序内容清单；独立摘要 `d6bfe480ec7b9b724f27c901bce6277da2a2a489dd7823b1f30a7857385078cd`。 |
| S5 | L0 Task 迁移冻结 SHA-256 `66d0d5685b72a22cb15959aa04262e49fed707db2dba1c29567946f6c0ba3a51`；当前 Task、Worker、调度提示和 Codex 后继文件聚合摘要 `a0652f5042431668a88c0cb9bdd46752562a8a8d53f07e8517ce645f537d1981`。 |
| S6 | 当前 Root、runtime、Operation Schema 与目录编译器聚合摘要 `ce01ba0a1a48d44bd04f291e94bae52429459472fde5a685adcd54f7d0f410ab`；插件包元数据、安装器和选择器聚合摘要 `8df3373ce3c7a8edab0d0d6653c46e36cc6a0bace810fbb59a139224f9ed7326`。 |
| S7 | 盲 CSV 四个有效源码文件及 `pyproject.toml` 聚合摘要 `42f7ea0c18a619a36e1588d79e4bdff884fc23009654e11065243acfdf3a4f7f`；生成的 `build/lib` 副本不计入手写接入劳动。 |
| S8 | 33 项约束注册表 `SCIENTIFIC_AGENT_CONSTRAINTS.yaml`，SHA-256 `deca6442c486303e169362eceb76c78db3dc479ab1994d7a2085f8cbd3191abf`。 |
| S9 | 本轮独立命令记录：生产树摘要/行数、当前计量器、六种插件组合、Pydantic/Root/fresh SQLite 探针、默认导入探针、结构测试、`compileall` 与空白检查。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
|---|---|---|---|
| `production_totals_and_modules` | pass | S1—S4, S9 | 141 文件、47,177 行及 `95/24,756 + 46/22,421` 精确闭合；生产树摘要、八删三增和 operations `8/2,100` 均成立。 |
| `successor_completeness` | pass | S1, S2, S5, S9 | 六个 8765 集中责任的整文件后继为 7,062 行；Task 为 3,101 行，Worker、调度提示和 Codex 后继均显式纳入全局唯一且存在的路径集合。 |
| `successor_claim_scope` | pass | S1, S2, S5 | 报告明确把 7,062 定义为保守的 Python 整文件口径，不称其为全系统语义复杂度或维护成本得分。 |
| `stage_net_attribution` | pass | S1, S3, S4 | M6 最终端点 46,970 到当前 47,177 为 +207；M5 到 M6 为 -419；阶段总和为 -2,846。 |
| `root_db_state_and_fields` | pass | S1, S6, S9 | Root 26；Local 15 表，Hardened 额外 1 表；Run 4 态、Execution 10 态；字段为 12/17/12。 |
| `catalog_install_projection` | pass | S1, S6, S9 | 默认核心 63/14；其余五种显式组合依次为 103/22、116/25、180/42、186/43、199/46，scope 和 executor 分类均相符。 |
| `blind_plugin_labor` | pass | S1, S7, S9 | 四个有效源码文件为 5、119、197、32 行；元数据 17 行；PluginDefinition 精确注册 AUTHOR、REVIEWER 和一个 CSV 领域工具。 |
| `installation_registration_import` | pass | S1, S6, S9 | 核心 wheel 固定两个入口；四个领域 wheel 各使用同一个 entry-point group；普通 Local 启动未导入 Hardened、portable、TCAD transport 或论文图入口。 |
| `single_registry_and_runtime_spine` | pass | S4, S6, S9 | 生产树只有一个 `CompiledCatalog` 构造点和一个 installed discovery group；Local/Hardened 共用同一 RunService，后端不另建科学终态。 |
| `domain_core_boundary` | pass | S4, S6, S9 | 通用核心对 TCAD、InGaAs、Fig.4、Sentaurus、device parameter 和 curve score 的直接领域分派命中为零；executor 类型分派是通用 Operation 语义。 |
| `constraint_status` | pass | S1, S8, S9 | 33 个唯一约束精确为 7 conformant、25 pending_review、1 known_issue；`SEC-002` 保持已知问题。 |
| `occam_and_authority` | pass | S1—S9 | 默认实体、字段和物理代码净减少，没有以第二目录、第二 Run 或领域硬编码换取表面删行；保留的可靠性复杂度与可选后端被如实标注。 |

## 3. 四个原阻断的独立闭合证据

### 3.1 后继集合不是改名计数

`r5_current_metrics.py` 当前把旧 Task 后继固定为 10 个完整文件：`runs.py`、四个 `run_*.py`、
Local/Hardened 工作区及文件实现、Local PDF 工具和 `operation_tool_context.py`，合计 3,101 行。
旧 Worker router 固定映射为 protocol、Local router、Hardened router 三个完整文件；旧 scheduler
topology 和角色 profile 分别映射到完整 `scheduler_prompt.py` 与 `codex.py`。Root 的七文件拆分也继续
计入原 Root 责任。

计量器在调用冻结生成器前合并这些集合，然后对所有责任的全部后继执行两个总检查：路径全局无重复、
每一项必须是当前普通文件。结构测试还冻结了上述 Task/Worker/调度/角色集合并复算各文件行数。
这关闭了首审所指出的“只列已删除 Task 文件所以得到零行”漏洞。

六个原集中责任的当前整文件计数为：调度 36、角色/profile 787、runtime 173、Root 2,595、Task
3,101、审批渲染 370，合计 7,062。它会把一个后继文件内的辅助代码全部计入，所以是有意偏保守的
物理口径；报告没有用它替代全生产树 47,177 行或未来维护成本分析。

### 3.2 默认目录与显式组合不再混淆

根 `pyproject.toml` 固定发布 `builtin`、`general_science` 两个入口，`SCID_PLUGINS` 默认值为空。
独立直接编译六种精确声明组合得到：

| 组合 | 组件 | Operation | public/support/internal | Agent/Transform/Approval/Effect |
|---|---:|---:|---:|---:|
| 默认核心 | 63 | 14 | 11/3/0 | 10/3/1/0 |
| 显式曲线 | 103 | 22 | 15/7/0 | 14/7/1/0 |
| 显式曲线+论文图 | 116 | 25 | 17/8/0 | 16/8/1/0 |
| 显式 TCAD（含曲线） | 180 | 42 | 24/18/0 | 20/18/3/1 |
| 显式 TCAD+InGaAs | 186 | 43 | 24/19/0 | 20/19/3/1 |
| 上述组合再加论文图 | 199 | 46 | 26/20/0 | 22/20/3/1 |

修订报告第 4.2 节和验证摘要均以 63/14 为真实默认值，对 186/43 与 199/46 的限定准确。

### 3.3 阶段端点使用最终通过状态

M0 为 50,023 行；逐阶段变化
`-1,144 +122 -46 +63 -621 -969 -39 -419 +207 = -2,846`，终点为 47,177。
M6 最终第三次独立复审明确冻结 46,970 行，不再使用此前失败/返工过程中的中间数字。因此 M6 与
M7 的最终归因已经闭合，历史中间报告保留不同数字不构成当前事实冲突。

### 3.4 盲插件劳动按有效源码与真实 Operation 计数

有效源码只计 `blind_csv_plugin` 中四个手写 Python 文件，不重复计算生成的 `build/lib`：5、119、
197、32 行，合计 353 行。`pyproject.toml` 为 17 行并声明唯一 `scidiscovery.plugins` 入口。
`PLUGIN.operations=(AUTHOR, REVIEWER)`，作者的 `ReviewSpec` 精确指向 reviewer；唯一领域工具是
`worker_csv_summarize`。修订报告已逐项写明，不再少记 reviewer Operation。

## 4. 其余边界与奥卡姆判断

- 生产树只在 `operations/catalog.py` 内构造一次 `CompiledCatalog`；`public`、`support`、`internal`
  和 `all` 是一个目录的投影。没有发现插件私表被 Root 当成目录权威。
- Root 的 Agent 分支统一创建 Run；Local 与 Hardened router 都消费同一个 RunService、精确 Operation
  摘要和后端工具投影。生产代码已无 TaskService、角色队列或第二普通生命周期。
- 通用核心不按 TCAD、曲线、InGaAs、Fig.4、Sentaurus 或设备参数名称分支。领域插件保留真实求解、
  数据处理和执行适配复杂度，不因奥卡姆目标被搬回核心或伪装删除。
- `current` 仍由 `scheduler_scientific_selections` 单独拥有；Run 恢复只创建新 Run 并使用冻结草稿，
  两者没有合成额外 checkpoint 状态机。
- 论文图插件、Hardened、portable 及 TCAD transport 的“随包存在、显式注册/实例化、默认不导入”
  边界与源码和默认导入探针一致。
- 7 项 conformant 的精确标识和唯一 `SEC-002` 均与注册表一致。其余 25 项继续 pending_review；
  M7.4 没有以静态计量或 39 项测试将它们自动升级。

未发现需要为了 M7.4 再拆文件、新增状态、增加校验器或修改生产运行代码的问题。千行级审批、Root
Operation 路由和 scheduler bindings 仍是维护热点，但仅凭文件大小不足以证明存在可安全删除的重复
权威；把它们作为本阶段阻断反而会偏离有证据再简化的原则。

## 5. 独立执行记录

所有命令严格串行，设置 7 GiB 虚拟内存上限和 `MALLOC_ARENA_MAX=2`；未运行 M7.5 全量回归。

```text
python scripts/r5_current_metrics.py
# 141/47,177；operations 8/2,100；六责任 7,062；Task 3,101；领域 token 0

find src/scidiscovery plugins ... | sha256sum / wc -l
# d6bfe480...；src 95/24,756；plugins 46/22,421

python <六种 PluginDefinition 精确组合编译探针>
# 63/14、103/22、116/25、180/42、186/43、199/46；scope/executor 分类一致

python <Root + Pydantic + fresh Local/Hardened SQLite 探针>
# Root 26/26/26；字段 12/17/12；Local 15 表；Hardened 16 表

python <普通 Local 导入集合探针>
# Hardened、portable、TCAD command/socket/SSH/remote runner、论文图入口均未导入

pytest -q -p no:cacheprovider \
  test_architecture_constraint_matrix.py \
  test_m2_optional_figure_plugin.py \
  test_m5_plugin_ownership_and_default_surface.py \
  test_m6a_direct_instance_management.py \
  test_m6b_operation_input_admission.py \
  test_m6c_producer_topology_removal.py \
  test_r5_catalog_stages.py \
  test_l6_runtime_capabilities.py
# 39 passed in 15.33s；MAXRSS 102,568 KiB；swap 0

python -m compileall -q src plugins
git diff --check
# 通过
```

仓库没有 `scripts/validate_architecture_constraints.py`；因此约束结构由现存的
`test_architecture_constraint_matrix.py`、独立 YAML 解析及 39 项组合测试验证，没有虚构脚本通过
记录。

## 6. 保留限制

本次通过不证明真实远端长期运行/失联恢复、任意大附件、多租户强隔离、任意新领域的科学质量或正式
生产升级。它们在注册表中仍为 `pending_review` 或 `SEC-002 known_issue`，属于未来要求，不是当前
M7.4 物理报告缺失的已实现事实。

本轮也没有重复 M7.3 的 82 项边界回归、M7.2 真实 Agent、M7.1 clean-wheel 矩阵或真实 solver。
这些阶段已有各自独立证据；M7.5 将负责全量测试、干净安装、部署回滚及两名最终独立审查。

## 7. 最终判定

**PASS；阻断项 0。M7.4 关闭，允许进入 M7.5。**

该放行仅说明当前物理成果报告、复杂度口径和默认路径边界准确且可复算；M7 和 R5-M 仍必须等待
M7.5 全量回归、clean install、部署回滚和两名最终独立审查均明确通过。
