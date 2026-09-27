# R5-M7.1 安装与运行矩阵独立审查

日期：2026-09-02  
审查者：未参与实现的独立代码与架构审查者  
结论：**FAIL**  
阻断项：**3**  
非阻断项：**1**  
阶段门：**不得放行 M7.2；不得宣称 M7 或 R5-M 完成。**

## 1. 审查范围和方法

本次是普通仓库审查，不是科学 Operation Worker。除本报告外，没有修改生产代码、测试、计划或既有
证据。当前分支为 `baseline/8765-codex`，工作树包含 R5 多阶段的大量未提交及未跟踪内容，因此本
报告审查的是当前完整工作树中的 M7.1 候选，不把 `git diff HEAD` 伪称为一个干净阶段补丁。

审查没有采信实现证据的自我结论，而是从当前规范、wheel 元数据、wheel 实际内容、已安装前缀、
目录编译、Root/preflight/Run/Codex 后端判断、默认导入面和部署入口反向寻找反例。测试均串行执行，
先设置 `ulimit -Sv 7340032`、`MALLOC_ARENA_MAX=2` 和
`PYTHONDONTWRITEBYTECODE=1`，未启用并行 pytest。

## 2. 阻断项

### B1：计划要求的两个安装组合被实现证据合并成一个，`core-only` 与 `core + general_science` 没有分别成立

**位置。** 计划在
`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md:417-419` 分别要求干净 `core-only wheel`、
`core + general_science` 和 `core + curve core`。核心发行元数据却在 `pyproject.toml:27-29` 的同一个
wheel 中无条件发布 `builtin` 和 `general_science` 两个入口。实现证据又在
`R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md:15-18` 现场把 `core-only` 重解释为二者同装，
并以源码内 `compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))` 代替第二个安装组合。

**可达反例。** 对候选实际构建的核心 wheel 建立干净前缀后，入口精确为：

```text
entrypoints [('builtin', 'scidiscovery.builtin_plugin:CORE_PLUGIN'),
             ('general_science', 'scidiscovery.general_science_plugin:PLUGIN')]
operations 14
```

不存在一个已安装 `builtin-only` 状态，也不存在从同一发行边界另行“加装 general_science”的状态。
`CORE_PLUGIN` 在源码级可以单独编译为空目录，只能证明声明可组合，不能证明计划列出的安装组合。

**影响。** 这不说明把 `builtin` 和领域无关 `general_science` 放在同一产品 wheel 本身一定错误；按
奥卡姆原则，它完全可能是正确的产品边界。但 M7.1 不能在审查阶段单方面修改已冻结完成门，又同时
宣称所有组合已覆盖。当前报告读者无法判断 general_science 是不可卸载的默认产品面，还是原计划中
可独立安装的插件。

**解除条件。** 不应只为满足名称机械拆包。必须先在规范事实中明确选择一种边界：若
general_science 是核心发行的固定组成，就将 M5/M7 的安装矩阵和所有证据统一改成“核心发行
（builtin + general_science）”，删除并不存在的独立安装行；若它必须可独立选择，再提供两个真实
wheel/安装组合。二者任一完成前，M7.1 不能通过。

### B2：可选图证据和远程 TCAD 只证明了“未注册/未导入”，没有证明计划要求的可选安装和缺失组合

**位置。** 计划在 `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md:321-331` 要求把论文图能力收成
可选插件、把 SSH、Python 3.6 runner 和套接字守护迁为显式可选安装；M7.1 又在该文件
`419-424` 要求 `curve core` 以及图证据、远程 transport 的存在/缺失组合。候选证据
`R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md:31-32,83-84` 实际只证明默认目录不注册能力、
普通进程不导入模块，并明确承认没有物理拆分。

**可复现 wheel 反例。** 当前干净 wheel 矩阵中：

1. 只安装 `scidiscovery-curve-score`、未安装 `curve_figure_evidence` 时，已安装前缀仍然存在：

   ```text
   curve_score/figure_digitization.py
   curve_score/figure_evidence.py
   curve_score/figure_evidence_validation.py
   curve_score/figure_science_operations.py
   curve_score/figure_worker_tool.py
   ```

   `importlib.util.find_spec()` 可直接定位这些模块；仅
   `curve_figure_evidence` 入口模块不存在。可选插件
   `plugins/curve_figure_evidence/curve_figure_evidence/plugin.py:3-49` 只是从已经安装的
   `curve_score.figure_*` 和 `curve_score.operation_transforms` 导入并注册声明。因此当前证明的是
   “论文图 Operation 激活可选”，不是“curve core 的论文图实现缺失”。

2. 安装 TCAD wheel 后，`plugins/tcad_artifact/pyproject.toml:15-25` 无条件安装
   `tcad-control-daemon`、`tcad-control-mcp`、`scidiscovery-tcad-transport`，且包内实际携带
   `ssh_transport.py`、`remote_runner_py36.py` 和 `execution_daemon.py`。干净前缀中的实际可执行文件为：

   ```text
   scidiscovery-tcad-transport
   tcad-control-daemon
   tcad-control-mcp
   ```

   当前没有“本地 TCAD 已安装但远程 transport/守护产品未安装”的组合。测试
   `test_default_imports_do_not_load_optional_runtime_products` 和
   `test_tcad_runtime_loads_only_the_selected_transport`
   （`test_m5_plugin_ownership_and_default_surface.py:113-205`）只检查 `sys.modules` 和两种适配器的惰性
   导入，不能证明安装缺失。

**影响。** 当前目录授权和启动内存面是真实减法，不是伪造；但把它写成“curve core”“显式可选
安装”及存在/缺失安装组合会掩盖实际部署表面、更新面和插件接入成本，也会使 M7.4 的“退出默认安装
/导入面的可选代码”无法按两个口径分别报告。可选 figure wrapper 还承担了一个纯激活胶水层，却未
迁出它所声称可选的实现代码。

**解除条件。** 同样不要求为形式纯洁盲目拆包。实现者必须逐项选择并冻结：

- 若目标是“激活和导入可选、安装包不拆”，则把规范、阶段名、证据和最终物理报告统一改成这个
  较小目标，明确列出仍随 curve/TCAD wheel 安装的文件与命令，不能继续称为安装缺失组合；
- 若目标仍是“显式可选安装/curve core”，则真实迁出相关模块或脚本，并增加本地 TCAD 无远程产品
  的干净 wheel 负例。

当前规范与实现未统一，故阻断 M7.1。

### B3：Hardened 正例只在源码测试夹具上成立，干净已安装产品没有纯 MCP Agent Operation

**位置。** M7.1 计划要求显式 Hardened 的纯 MCP Operation；实现证据
`R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md:29` 没有说明正例来自测试插件。
`test_l5_hardened_run_backend.py:16-35,41-65` 实际导入 `blind_csv_plugin` 源码 fixture 并手工
`compile_catalog`，不是 `compile_installed_catalog()` 的真实发行入口。

**可复现反例。** 在候选实际构建的干净核心 wheel 环境中，编译出的 14 个 Operation 里，所有 10 个
Agent 都声明原生 shell，部分还声明原生图像，因此：

```text
hardened_agent_ops []
```

现有 clean-installed blind plugin 探针只直接调用领域工具，没有打开 Hardened runtime、生成 Hardened
Codex profile、完成四态 Run。反过来，Hardened Run 测试又依赖源码 checkout 的 pytest
`pythonpath` fixture。两半证据没有在同一真实安装入口闭合。

**影响。** 已有测试充分证明 Hardened backend 的内部协议可工作，也证明 TCAD 原生工具 Operation
会在 Run 创建前失败关闭；但它尚未证明“干净安装一个纯 MCP 插件后，显式 Hardened 能从已安装入口
完成同一 Run”。安装或 entry-point 打包错误仍可能被源码 fixture 掩盖。

**解除条件。** 不要求为了 Hardened 在通用科研插件中新增一个无消费者 Operation。复用现有 blind
CSV 小插件即可，但必须在隔离 venv 通过其真实 wheel entry point 编译目录，打开显式 Hardened
runtime，完成至少一个 Run，并验证生成 profile、Worker 工具投影和 Root 状态来自该已安装前缀。

## 3. 非阻断项

### N1：完整 Local TCAD 仍是“已安装工具探针 + 源码合成生命周期”两段证据，尚非单一已安装纵向入口

`test_catalog_installed_entrypoint.py` 证明 TCAD wheel 的领域工具从安装前缀真实导入并调用；
`test_l4_local_tcad.py:356-451` 又证明作者、开发调试和独立审查共享同一 Run/Operation 路径。不过后者
在源码 checkout 中用 `_ImmediateDebugAdapter` 合成 solver 结果，并由测试代码写作者和审查者输出。
这足以作为 M7.1 的工程接线证据，且 M7.2 已明确负责真实子智能体纵向回归，所以本轮不单独阻断；
但最终报告不得把它描述成真实模型或真实 solver 科学效果验证。若 M7.2 仍从源码而非已安装发布入口
运行，最终门需要补一条 clean-installed Local TCAD 纵向冒烟。

## 4. 已确认成立的部分

下列候选结论经独立复核成立，不应因本次 FAIL 被推倒：

- 运行时插件发现只有 `scidiscovery.plugins` 一个 entry-point group；`public`、`support`、
  `internal`、`all` 仍是同一 `CompiledCatalog` 的投影，没有第二注册表。
- 未在核心调度、Root、Run 或 Codex 生成路径发现按 TCAD、曲线、论文图、InGaAs 或盲插件名分支；
  部署选择器是安装期通用 wheel 选择，不是第二运行时目录。
- Hardened 的目录诊断、Root preflight、RunService 和 Codex profile 都调用当前 backend 的同一
  `supports_operation/unsupported_requirements` 能力判断。生产 TCAD 原生 shell Operation 的独立负例
  确认拒绝发生在 Run 写入前，`runs.list(...) == ()`。
- 默认 CLI/runtime 不导入 Hardened、portable、SSH 或未选中的 TCAD adapter；便携管理的三个命令在
  parser 中存在，解析命令不会导入 `portable_bundle`，只有进入相应命令分支才惰性导入。
- 可选 figure entry point 缺失时，目录中确实没有三项 figure Operation；显式安装 entry point 后
  精确增加 extraction、audit、bundle 三项，确定性工具从已安装前缀真实执行。
- 盲 CSV 插件只需一个入口即可编译和调用真实领域工具，核心没有插件名特判。
- `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 仍为 33 个唯一约束：7 `conformant`、25
  `pending_review`、1 `known_issue`；`SEC-002` 仍明确记录 Local 原生工具隔离只是提示约束，没有被
  Hardened 测试或测试数量虚假升级。

## 5. 独立运行的证据

| 检查 | 结果 |
|---|---|
| clean wheel 目录、所有权、已安装领域工具、figure、Hardened/TCAD 聚焦组合 | `18 passed in 46.68s` |
| 部署预览、TCAD 表面回滚、SSH 配置/升级/绑定、发布和机器中性聚焦组合 | `9 passed in 4.04s` |
| 便携管理三个命令 parser 惰性导入探针 | PASS |
| `git diff --check HEAD` | PASS |
| 实际 wheel 内容和隔离前缀可执行文件探针 | PASS，得到 B1/B2 中列出的反例 |
| 干净核心 catalog 的 Hardened 可运行 Agent 枚举 | `[]`，得到 B3 |

没有再次运行完整 263 项回归：本次审查没有修改生产代码，且三个阻断都是已通过单测无法反驳的安装
口径或真实入口缺口。重复全量绿测不能关闭这些问题。

## 6. 最终判断

候选在单一目录、后端同源判断、默认惰性导入、TCAD 原生工具失败关闭、盲插件可扩展和
`SEC-002` 诚实披露方面方向正确。失败原因不是要求增加新的控制实体，而是当前 M7.1 把三类不同事实
混成同一个“安装矩阵通过”结论：

1. 同一 wheel 内的固定入口与可独立安装插件；
2. 未注册/未导入与未安装；
3. 源码 fixture 的后端正例与干净已安装入口的正例。

因此结论为 **FAIL，阻断 3，非阻断 1**。修复应优先收紧并统一产品边界和验收用语，再补一条已安装
Hardened 纵向探针；不得为追求字面“纯净”扩建第二注册表、第二部署事务或领域特判。只有三项阻断
均关闭并由未参与修复者重新独立审查明确 PASS 后，才可放行 M7.2。
