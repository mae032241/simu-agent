# R0：8765 安装态行为基线

状态：实现与独立复审均已通过。本文只记录重构前事实，不定义目标架构，也不证明历史
科研闭环的科学结论。

## 1. 冻结范围

- 分支：`baseline/8765-codex`
- 基线提交：`404aeb14c6ebc4b08bac599db91eaee54c103f48`
- Python：3.12.13
- 源码工作环境没有安装 `scidiscovery`、`tcad-artifact` 或
  `scidiscovery-curve-score` distribution；测试不得借用源码导入。清洁 wheel 夹具固定为
  `scidiscovery==0.1.0`、`tcad-artifact==0.1.0` 和
  `scidiscovery-curve-score==0.1.0`。
- 关键测试依赖：Pydantic 2.11.5、Pillow 12.1.1、PyYAML 6.0.3、
  setuptools 75.1.0、pytest 9.1.1。
- 控制服务入口为 `python -m scidiscovery.artifact_agent.interfaces.mcp_daemon`；完整参数以
  `deploy/systemd/scidiscovery-control.service.in` 为准。

R0 每个会执行框架代码的测试都先从当前源码构建 wheel，再分别安装到两个独立虚拟环境：

1. `core`：只安装核心 wheel；
2. `full`：安装核心、TCAD 和 curve-score 三个 wheel。

子进程在仓库外启动，移除 `PYTHONPATH` 和 `SCIDISCOVERY_ROLE_DIR`，并断言实际导入路径位于
虚拟环境前缀中。因此通过结果是安装入口实证，不是源码插件扫描结果。
自产 distribution 与三个直接运行依赖均在安装态测试中精确断言；如需重建完整传递环境清单，
对两个夹具分别执行 `<venv>/bin/python -m pip list --format=freeze`。虚拟环境以
`system_site_packages=True` 复用上述已冻结依赖，wheel 安装命令明确使用 `--no-deps`。

## 2. 已冻结的生命周期行为

| 边界 | 安装态结果 | 对应测试 |
| --- | --- | --- |
| Agent 文件任务 | `schedule → dispatch → claim → materialize → validate → finalize → status` 完成；Worker assignment 不含控制标识 | `test_baseline_agent_lifecycle.py` |
| 确定性变换 | 相同精确父输入重复调用返回同一结果；主输出和拆分输出均绑定同一父链 | `test_baseline_transform_lifecycle.py` |
| 假外部效果 | UI subject 精确等于 ExecutionRequest 与 payload；未决定时启动失败且提交数为零；决定后只提交一次并可同步、登记输出 | `test_baseline_effect_lifecycle.py` |
| 审批 UI | 两次读取显示同一精确 subject 原始树；读取不写状态；同一表单重复提交幂等返回同一决定 | `test_baseline_approval_ui.py` |
| TCAD 假调试 | author 在任务私有目录暂存源码；无真实 solver 的 adapter 完成一次开发调试；结果明确不可形成科学主张 | `test_baseline_tcad_debug.py` |
| author→reviewer | author 终结后，reviewer 在另一任务目录读取冻结输出；reviewer 在服务端不能获得 debug 权限 | `test_baseline_tcad_debug.py` |
| 上下文交接 | `handoff_only` 必须来自已完成任务，只出现在 assignment 元数据中，无路径和读取权限 | `test_baseline_worker_authority.py` |
| 角色合同 | 八个角色的完整 prompt、Worker JSON Schema、解析后 context policy 和资源 profile 均以规范摘要冻结 | `test_baseline_role_contracts.py` |

8765 的 Root MCP 没有 `task_reconcile`。Agent 终结后由 `task_status` 直接观察完成状态；R0 不为
满足新文档而虚构旧接口。

## 3. 角色合同和资源基线

核心安装发现六个角色；full 安装从清洁交付目录的 TCAD role-pack 发现两个角色。R0 开发中
曾发现直接从带有 `plugins/tcad_artifact/build/lib` 的脏源码树构建，会把已删除的
`tcad_deck_reviser` 重新打入 wheel。正式夹具因此先通过发布构建器生成清洁源码目录，再构建
wheel；该发现是构建卫生警告，不固化为产品角色。

| 角色 | 主输出 | Schema | 当前默认资源上限 |
| --- | --- | --- | ---: |
| 证据提取者 | `scientific_intake` | `scidiscovery.scientific-intake.v1` | 900 秒 / 64 KiB 默认回退 |
| 构想者 | `hypothesis_portfolio` | `scidiscovery.hypothesis-proposal.v1` | 900 秒 / 64 KiB |
| 批判者 | `scientific_review` | `scidiscovery.critic-review.v1` | 600 秒 / 32 KiB |
| 证据审查者 | `evidence_audit` | `scidiscovery.evidence-audit.v1` | 600 秒 / 32 KiB |
| 实验设计者 | `experiment_design_intent` | `scidiscovery.experiment-design-intent.v1` | 900 秒 / 64 KiB |
| 诊断者 | `layered_diagnosis` | `scidiscovery.layered-diagnosis.v1` | 900 秒 / 128 KiB |
| TCAD 代码作者 | `tcad_project` | `tcad.deck-project.v1` | 1200 秒 / 512 KiB |
| TCAD 代码审查者 | `tcad_project_review` | `tcad.deck-review-report.v1` | 600 秒 / 64 KiB |

每个角色的完整 prompt、Pydantic 输出 JSON Schema、解析后的全部 context policy 以及 runtime
profile 均由安装态测试规范化后计算 SHA-256，并与 R0 摘要精确比较。资源上限当前来自
`scheduler_topology.py` 的角色表，不属于一个统一编译合同；证据提取者落到通用默认值。这正是
后续要收进已编译 OperationSpec 的分散表面。摘要只冻结语义输入，不要求保留旧 loader 或
entry-point 形式。

## 4. 插件与控制面事实

full 安装有三个并列 entry-point group：

- `scidiscovery.agent_role_packs`：1 个入口；
- `scidiscovery.transform_adapters`：2 个入口；
- `scidiscovery.operation_specs`：2 个入口。

两个 operation-spec 入口都存在于 distribution 元数据中，但清洁安装后加载分别得到
`tcad_artifact.operation_specs` 与 `curve_score.operation_specs` 模块缺失。开发中曾观察到它们
从脏 `build/lib` 成功加载，这恰好证明旧构建残留会掩盖发布缺陷。可复现基线是：角色资源和
变换 adapter 可发现，operation group 已声明但断裂，同时三类能力仍由三个入口分别注册。

核心 `src/` 中仍有 6 处对 `tcad_artifact` 的直接导入，位于 control/worker daemon 的 TCAD
启动分支。对六个关键通用模块做的词法基线统计有 114 个 role/schema/profile/TCAD 相关命中；
该数字只用于后续同口径趋势比较，不等同于 114 个语义缺陷。

这两个数字的唯一可执行口径在 `tests/operations/test_baseline_structure_metrics.py`：UTF-8、
大小写敏感、每个匹配源码行只计一次。114 的正则为
`if .*role|elif .*role|role ==|role in|schema_id ==|profile ==|context_profile ==|tcad`，文件集合为
下表除 `deploy/install.sh` 外的六个 Python 文件；6 个 import 命中的正则为
`(^|\s)(from|import) (tcad_artifact|curve_score|ingaas)`，扫描 `src/**/*.py`。运行
`pytest -q tests/operations/test_baseline_structure_metrics.py` 即同时复现行数、114 和 6。

| 关键文件 | 行数 |
| --- | ---: |
| `scheduler_topology.py` | 341 |
| `platforms/roles.py` | 339 |
| `artifact_agent/runtime.py` | 256 |
| `artifact_agent/interfaces/mcp_root.py` | 2616 |
| `artifact_agent/service/tasks.py` | 6952 |
| `artifact_agent/approval_ui/render.py` | 3153 |
| `deploy/install.sh` | 1008 |
| 合计 | 14665 |

## 5. 当前 Worker 授权基线

这些是待替换事实，不是目标合同：

- 默认 context policy 为 `allow_additional=True`，最多 32 个输入、64 MiB 可读内容；
- Codex 为全部角色默认启用实时网页搜索和图像查看；
- 同类角色获得角色级固定工具集合，只有 TCAD author 额外获得 debug 工具；
- 所有角色配置都原生可读同一个共享 workspace 根，任务私有目录主要靠逻辑边界而不是
  每次调用的最小原生路径授权；安装态测试建立两个并发活动任务，确认同一进程可直接读取
  兄弟任务的 `assignment.json`，而任务完成后该 workspace 会被删除；
- `fork_turns="none"` 已防止调度器对话上下文直接继承给 Worker；
- `handoff_only` 内容不可读，但兼容读取接口直接泄漏服务层 `TaskInputError`；
- 文件通过最终校验后进入非续期终结窗口，开发调试不再允许运行。

R1—R3 应让工具、输入路径、网络和资源上限都由同一 compiled operation 派生并默认拒绝；
不得为修补以上问题新增 Worker 权限状态机。

## 6. 文档与源码差异

当前 `src/`、插件和 R0 测试中没有 `OperationIntent`、`QualificationReceipt` 或 `ActiveHead`
实现。历史计划对这些对象的描述不能当成当前源码事实，也不是本轮最小重构的建设目标。

R0 没有重跑已经完成的真实科研闭环，没有连接真实 TCAD、远程服务或生产状态目录。它只证明
本轮要保留的通用生命周期和当前待删除的结构债务能够从安装包入口稳定复现。

## 7. 自动化结果

`pytest -q tests/operations`：11 项通过；`pytest -q`：41 项通过。最终阶段状态以
`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 26 节和独立审查报告为准。
