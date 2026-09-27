# R5-M7.1 安装与运行矩阵实现证据

日期：2026-09-02

状态：首轮独立审查 FAIL 后返工；全新独立复审 PASS，仅放行 M7.2

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 边界

本阶段没有新增运行器、注册表、状态、Root 工具、领域分支或兼容桥，只验证 M5/M6 通过态能从干净
发行包和显式后端配置中真实建立。测试全部串行执行，设置 7 GiB 虚拟内存上限和
`MALLOC_ARENA_MAX=2`。

首轮审查正确指出，不能用实现证据现场改写冻结计划。返工已先修正规范事实：核心发行固定包含
`builtin` 与领域无关 `general_science` 两个统一插件入口，不再声称存在 core-only 与另行加装
general_science 两种物理安装状态。`builtin` 可在声明级独立编译为空目录；核心发行从干净 wheel
编译出 14 个通用科研 Operation。该边界不需要第二 wheel、第二目录或部署胶水。

同理，本轮“可选”明确区分三件事：wheel 是否安装、Operation 是否注册、模块是否默认导入。论文图
插件入口确实可独立安装/缺失；曲线基础 wheel 仍携带其复用的同领域确定性实现。远程 TCAD 命令与
模块仍随 TCAD wheel 分发，但只有显式管理命令或运行配置才启用，普通路径不注册、不实例化、不导入。

## 2. 矩阵结果

| 计划项 | 实际证据 | 结果 |
|---|---|---|
| 干净核心发行包 | 隔离 venv 只安装核心 wheel；固定且仅有 `builtin`、`general_science`，无 TCAD Schema、旧角色/Worker 模块或领域 Operation | PASS |
| 声明级核心组合 | `compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))` 精确得到 14 项；不再把它写成第二种安装状态 | PASS |
| 核心与曲线 | 隔离 venv 安装核心、曲线 wheel；只增加曲线合同、分析与诊断，不出现论文图和 TCAD | PASS |
| 核心与 TCAD | 依赖解析安装 TCAD wheel 后入口所有权精确；TCAD 工具从安装前缀加载并真实调用 | PASS |
| 完整本地 TCAD | 本地作者、调试和独立审查共享同一已编译 Operation 路径；socket/command 只加载显式选择的一套适配器 | PASS |
| 已安装入口的显式强化纯 MCP | 干净核心 wheel 加已安装 blind CSV wheel；由 `compile_installed_catalog` 打开强化 runtime，真实完成同一四态 Run，并核对配置、assignment、router 工具完全一致 | PASS |
| 强化与原生工具不兼容 | TCAD/曲线原生 shell Operation 在 Run 创建前以同一能力结论失败关闭 | PASS |
| 可选论文图 | 默认目录无三项论文图能力；安装可选 wheel 后一次且只增加 extraction、audit、bundle 三项，并真实调用打包工具 | PASS |
| 远程传输 | 远程实现随 TCAD wheel 分发但普通启动不注册/实例化/导入；显式 command/socket 配置只加载选中适配器；SSH runner 管理、升级、绑定拒绝和配置保留均通过 | PASS |
| 便携管理 | 普通 CLI/runtime 不导入 `portable_bundle`；三个管理子命令存在，解析命令也不加载实现，只有进入对应命令分支才惰性导入 | PASS |
| 盲领域插件 | 干净核心 wheel 加一个小型 CSV 插件后，单一入口完成编译并真实调用领域工具，核心无插件名分支 | PASS |

## 3. 自动化证据

### 3.1 干净 wheel、插件所有权和可选论文图

```text
pytest ... test_catalog_installed_entrypoint.py \
  test_m5_plugin_ownership_and_default_surface.py \
  test_m2_optional_figure_plugin.py
18 passed in 45.86s
```

该组实际构建源码发布副本、核心和各领域 wheel，再为 core、curve、figure、table、TCAD、完整组合及
故障插件分别建立隔离 venv；探针禁止从源码 checkout 导入。

### 3.2 Local、Hardened、TCAD 和运行插件

```text
pytest ... test_platform_configuration.py \
  test_l5_hardened_run_backend.py \
  test_l4_local_tcad.py \
  test_runtime_plugin_configuration.py
29 passed in 4.86s
```

### 3.3 部署、回滚和远程管理

```text
pytest ... test_deploy_scripts.py
33 passed in 5.37s
```

### 3.4 源码组合、盲插件和已安装 Effect

```text
pytest ... test_install_combinations_compile_without_reverse_dependency \
  test_general_science_composition_is_complete_unique_and_frozen \
  test_clean_installed_blind_plugin_compiles_and_calls_its_tool \
  test_installed_no_effect_execution_requires_exact_ui_decision
4 passed in 38.96s
```

### 3.5 首轮审查 B3 返工：已安装入口的 Hardened Run

新增 `test_clean_installed_pure_mcp_plugin_completes_a_hardened_run`。它不覆盖源码目录，不手工替换
`RunService.operation_catalog`，而是在 `blind_csv` 隔离 venv 内完成：

```text
compile_installed_catalog
→ open_runtime(worker_backend="hardened")
→ Root operation_invoke
→ 生成 Hardened Codex profile
→ Hardened Worker open/领域工具/服务端写入/submit
→ Root run_status(completed)
1 passed in 38.83s
```

同时断言 `blind_csv_plugin.__file__` 位于该 venv 前缀，profile、assignment 与 router 的工具集合完全
相同，最终后端为 `hardened_worker`。

便携 CLI 惰性表面探针和 `git diff --check HEAD` 另行通过。

## 4. 当前物理规模与有意保留

- 生产 Python：141 个文件、46,970 行；
- `operations` 包：8 个文件、2,100 行；目录编译器 734 行；
- 默认 Local 不导入 Hardened、portable、SSH、TCAD daemon 或未选择的 transport；
- Hardened、portable 和远程 TCAD 仍保留为显式能力，不伪称已经物理拆成独立发行包；
- `SEC-002` 继续是 Local 原生工具隔离的已知问题，不因本矩阵通过而升级。

## 5. 首轮独立审查与返工判断

首轮报告 `../reviews/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_INDEPENDENT_REVIEW.zh-CN.md` 结论为 FAIL，
阻断 3 项、非阻断 1 项。B1/B2 通过统一规范与真实产品边界修复，没有机械拆 wheel；B3 新增一条
已安装入口的真实 Hardened Run。N1 留给计划原本负责真实子智能体的 M7.2，但最终不得把固定 adapter
冒烟描述成真实模型或 solver 科学效果。

返工没有修改生产代码，没有增加 Registry、Operation、状态、Root 工具、后端或部署事务。只有全新
独立审查者复算规范、wheel 内容和 B3 真实入口并明确 PASS 后，才允许进入 M7.2。

全新复审报告 `../reviews/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_INDEPENDENT_REREVIEW.zh-CN.md`
结论为 PASS，阻断 0；首审 N1 作为唯一非阻断明确转交 M7.2。该结论只放行真实智能体纵向回归，
不代表 M7 或 R5-M 完成。
