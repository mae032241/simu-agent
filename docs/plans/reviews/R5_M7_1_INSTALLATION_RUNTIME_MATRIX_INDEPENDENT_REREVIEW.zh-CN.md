# R5-M7.1 安装与运行矩阵返工独立复审

日期：2026-09-02  
审查者：未参与 M7.1 实现、首审和返工的全新独立代码/架构审查者  
结论：**PASS**  
阻断项：**0**  
非阻断项：**1**（首审 N1 保留给 M7.2）  
阶段门：**只放行 M7.2；不得宣称 M7 或 R5-M 完成。**

## 1. 审查范围与方法

这是普通仓库审查，不是科学 Operation Worker。本次只审查 M7.1 首轮 FAIL 后的三项返工和 N1
归属；除本报告外，没有修改生产代码、测试、计划、实现证据或首审报告。

当前分支为 `baseline/8765-codex`，工作树包含 R5 多阶段的大量未提交和未跟踪内容。因此本报告审查
的是当前完整工作树中的 M7.1 候选，不把 `git diff HEAD` 伪称为干净的单阶段补丁。审查完整阅读了：

- `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 当前 M5/M7 边界和实施记录；
- `R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md`；
- 首轮 FAIL 报告；
- 核心、曲线、论文图和 TCAD 的 `pyproject.toml`、入口插件、运行时、Hardened Worker、Codex
  profile 生成和 clean-wheel 测试；
- 当前架构、README、安装文档及 M2/M5 相关活动证据中的产品边界表述。

测试和探针全部串行运行，先设置 `ulimit -Sv 7340032`、`MALLOC_ARENA_MAX=2` 和
`PYTHONDONTWRITEBYTECODE=1`，没有启用并行 pytest。

## 2. 首轮阻断关闭判断

### B1 已关闭：`builtin + general_science` 是明确、诚实且更小的核心发行边界

当前活动计划不再要求一个不存在的 `builtin-only wheel` 和随后另行安装 `general_science`。M5 验收和
M7.1 矩阵现在都明确规定：核心发行固定包含 `builtin + general_science` 两个入口；`CORE_PLUGIN`
可以在声明级单独编译为空目录，但这不是第二种安装产品。

独立构建后的核心 wheel 实物只有以下插件入口：

```text
builtin         = scidiscovery.builtin_plugin:CORE_PLUGIN
general_science = scidiscovery.general_science_plugin:PLUGIN
```

从隔离 venv 的 `site-packages` 调用 `compile_installed_catalog()`，精确得到 14 个领域无关科研
Operation，没有 TCAD 参数 Schema、TCAD Operation 或测试插件入口。

这不是失败后降低质量标准，理由有三点：

1. 首审已明确允许先选择产品边界，返工是在 M7.1 未放行期间先修正规范，再按该规范验证；没有把已
   通过的阶段结果倒签成另一种含义；
2. `general_science` 是通用科学角色和合同的最低产品面，不是 TCAD、曲线或项目领域插件；把一个空
   `builtin` 发行与它机械拆成两个 wheel 不会增加运行隔离、授权隔离或目录可组合性；
3. 强制拆包反而增加发行、依赖和部署胶水。当前仍只有一个 entry-point group、一个编译事务和一个
   `CompiledCatalog`，外部领域插件的安装边界没有因此收窄。

首轮 FAIL 报告仍作为历史审计保留；当前决策索引明确说明历史计划/审查不是并行规范。活动计划、
M7.1 证据和当前发行元数据对核心边界已一致。

### B2 已关闭：安装、注册、启用和导入四类事实已明确分开

独立检查 wheel 内容再次确认首审的物理事实没有消失，也没有被文档隐藏：

- `curve_figure_evidence` 是可独立安装或缺失的入口 wheel；缺失时目录无论文图三项 Operation，安装后
  精确增加提取、独立审查和 bundle 三项；
- 数字化、校准、验证和 Worker tool 实现仍在 `curve_score` wheel 中，入口插件直接复用这些同领域
  算法；当前计划、实现证据和曲线 README 均明确说明这一点；
- `execution_daemon.py`、`execution_mcp.py`、`ssh_transport.py` 和
  `remote_runner_py36.py` 仍随 TCAD wheel 分发，三个管理命令也真实存在；普通 Local 启动不注册、
  不实例化、不导入它们，只有管理员显式配置的 command 或 socket 适配器被加载；
- `portable_bundle` 的三个管理子命令随核心 CLI 存在，但仅构造和解析 parser 不导入实现，进入精确
  管理命令分支才惰性导入。

这符合奥卡姆原则和当前通用 Agent 目标。运行授权来自已编译 Operation 对组件和工具的显式引用，
不是“某个 Python 文件碰巧存在”；为少量同领域标准库实现强制增加 wheel、入口和版本关系，不能
减少默认依赖、已加载代码或 Agent 权限。当前物理报告也明确要求 M7.4 分别报告“未安装”“未注册”
和“未导入”，不得互相替代。

活动规范和面向用户的当前文档未再声称曲线图算法或远程 TCAD 实现已经从所属 wheel 物理移除。
历史首审保留的反例不是当前产品宣称。Local 原生工具隔离的 `SEC-002` 仍为 `known_issue`，代码存在
也未被包装成平台级安全隔离已经解决。

### B3 已关闭：clean-installed blind CSV 插件完成同一 Hardened Run

新增的
`test_clean_installed_pure_mcp_plugin_completes_a_hardened_run` 不是把源码 fixture 和另一个后端单测
拼在一起。它在发布副本构建核心 wheel 和 blind CSV wheel，再于独立 venv 中完成：

```text
compile_installed_catalog
→ open_runtime(worker_backend="hardened")
→ Root operation_invoke（queued）
→ 生成 Hardened Codex profile
→ Worker open（running）
→ 已安装领域工具调用
→ 服务端文件创建/提交
→ worker_submit_result
→ Root run_status（completed）
```

污染负控成立：探针移除了 `PYTHONPATH` 和角色目录变量，设置 `PYTHONNOUSERSITE=1`，工作目录位于
源码 checkout 之外；`scidiscovery.__file__` 与 `blind_csv_plugin.__file__` 都被断言位于该 venv
前缀。独立探针实测入口恰为 `blind_csv/builtin/general_science`，没有从仓库源码得到插件入口。

生成 profile 的 Python 命令指向同一 venv，`PYTHONPATH` 指向该 venv 的 `site-packages`。本次复审又
按 profile 中的真实 command/args 启动 stdio MCP 进程，`tools/list` 返回的集合与 profile
`enabled_tools` 完全一致，包括生命周期工具、三项服务端写入工具和 `worker_csv_summarize`。
Run 数据库显示同一记录具有 `created_at`、`started_at`、`completed_at`，终态为 `completed`，后端为
`hardened_worker`；不存在第二个手工替换的目录或 RunService。

该测试不是真实模型 Agent 科学效果测试，但 B3 要求的是 clean-installed 目录和 Hardened 工程入口
闭合。真实子智能体调用属于 M7.2，不应为 M7.1 再建立一条测试专用运行器。

## 3. N1 仍应留给 M7.2

首审 N1 保留为一项非阻断要求。当前 M7.1 已证明：TCAD wheel 的入口、工具、目录所有权、后端能力
判断以及作者—调试—独立审查的控制生命周期能够接线；它没有证明真实子智能体或真实 solver 的科学
效果。

这正是活动计划 12.2 的职责。M7.2 必须真实拉起 TCAD 作者、领域调试和独立 Deck reviewer，并仍然
只从完成 Run 的封存输出读取结果。若 M7.2 只在源码 checkout 中运行而没有 clean-installed Local
TCAD 纵向入口，则最终 M7 门还需补一条 installed-wheel 冒烟；不得把固定 adapter 或合成 solver
描述成真实模型/solver 证据。

## 4. 独立复算证据

| 检查 | 结果 |
|---|---|
| B3 单项 clean-installed Hardened Run | `1 passed in 37.55s` |
| clean wheel 目录、所有权、领域工具、论文图和 B3 组合 | `19 passed in 47.98s` |
| 安装预览/回滚、SSH runner 配置/升级/绑定、论文图部署和机器中性聚焦组合 | `9 passed in 3.96s` |
| 33 项约束注册表结构 | `1 passed in 0.04s` |
| 隔离核心 venv 实物探针 | PASS：仅两个固定入口，14 个通用 Operation，模块来自 venv 前缀 |
| 隔离 blind CSV venv 污染探针 | PASS：三入口，核心和插件均来自 venv 前缀，工作目录/PYTHONPATH 不指向 checkout |
| 生成 profile 的真实 stdio MCP `tools/list` | PASS：进程正常退出，工具集合与 profile 完全一致 |
| wheel 内容检查 | PASS：如实确认曲线图实现仍随 curve、远程实现仍随 TCAD 分发 |
| 便携 CLI parser 惰性导入探针 | PASS：三个命令存在，parse 后仍未导入 `portable_bundle` |
| `git diff --check HEAD` | PASS |

本次没有重复完整 263 项回归：返工没有修改生产代码，B1/B2 是产品边界和规范对齐，B3 有精确
clean-installed 回归；完整回归本来就是 M7.5 最终门。重复全量测试不能替代上述安装前缀、wheel
内容和真实 profile 命令探针。

## 5. 最终判断

首轮三个阻断均已关闭：核心发行边界已经冻结且与实物一致；可选安装、注册、启用和导入不再混报；
Hardened 正例已经在同一个 clean-installed 入口闭合。返工没有用第二 wheel 拆分工程、第二目录、
第二运行器或领域硬编码换取形式通过。

因此本轮结论为 **PASS，阻断 0，非阻断 1**。只放行 M7.2；N1 必须由真实 Agent/TCAD 纵向回归继续
关闭，M7.3 安全负例、M7.4 物理成果报告、M7.5 全量回归和两位最终独立审查仍未完成。
