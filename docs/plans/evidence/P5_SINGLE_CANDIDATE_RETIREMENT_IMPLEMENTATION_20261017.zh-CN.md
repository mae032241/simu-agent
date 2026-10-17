# P5 单环境入口与旧 live 池退役实施账

状态：**实现冻结，[独立静态审查](P5_SINGLE_CANDIDATE_RETIREMENT_REVIEW_20261017.zh-CN.md)通过，待 root 提交。** 基线 `71394a3`；[窄设计](P5_SINGLE_CANDIDATE_RETIREMENT_DESIGN_20261017.zh-CN.md)已由 thin_test_review_1017 独审通过。未运行测试、收集、项目导入、构建、安装、CLI、模型或服务器。

## 精确变化与消费者

本节点只有三处 Python 文件，另更新本设计/实施账、[消费者账](P5_ENTRY_RETIREMENT_LEDGER_20261017.zh-CN.md)及[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)状态。

| 文件 | 变动及保护 |
| --- | --- |
| `scripts/probe_root_host_live.py` | package/direct-file 两种导入均改已有 `create_environment`；`prepare` 唯一调用传明确 `cohort=distribution`。原 core/all_domains 参数限制、profile、manifest、后续 live 行为不变。 |
| `scripts/installed_candidates.py` | 删除 `create_environments` 和其 `LazyEnvironments` 切换/销毁环境逻辑。删除不可达 curve/architecture/blind_csv/m7_effect/broken/invalid_unicode 选择及五项 fixture wheel sources；fixture 源文件不删。删除仅旧池可达的 TCAD 两次 pip fallback 和 resolve_once 参数。共享 `_candidate_creator` 只由单环境 wrapper 使用。 |
| `tests/operations/test_root_host_live.py` | 原 profile 隔离测试改显式单环境 mock，并断言 cohort=core；原 Root/个人 Worker model 断言全部保留。5个测试函数名/数量不变，无新增 fixture、安装或重跑矩阵。 |

删除前仓内可执行消费者仅 live 的两种导入/一次调用和上述测试 mock。删除后 `src/plugins/scripts/tests/deploy/.github/pyproject.toml` 中无 `create_environments/LazyEnvironments` 命中；文档历史提及不作可执行消费者。仓外私有 helper 调用未获盘点，不声称兼容旧 dict API。

保留 wheel sources core/tcad/curve/figure。core 安装一份 core；live all_domains 仍同一环境安装原四 wheel 且 `--no-deps`。pytest tcad 仍先构建 core/curve/tcad wheel，再一次 pip 仅显式给 core+tcad、通过 wheelhouse 解析 curve；本地 `resolve_once` 由 tcad_resolved 派生，未把 all_domains 宣称为依赖解析验证。`_run_logged` 与 root_host_upgrade 消费、依赖缓存、隔离解释器/日志/超时规则未改。pytest 和 runner 的安装 choices 均仍 core/tcad；不把 all_domains 加进 pytest。

## 静态证据与未验收

- 标准库 AST 解析上述三文件通过；与 HEAD AST 比较，测试文件全部5个 test_* 函数保留。未 import 项目或测试。
- 限定 `git diff --check` 通过；文本核对 sources/selection 闭包、唯一 wrapper 消费和 installation fixture/runner choices。
- 未执行 pip、venv、live prepare、测试、收集或任何旧安装逻辑，因此安装产物、依赖解析和 live 远端行为仅静态保真，未动态验收；资源硬隔离资格仍未补。
- 真实旧 scid/CLI/MCP/UI/SQL/CAS/授权仍有消费者，见消费者账；本项不等于旧入口整体退役。`history.bind`/旧测试迁移另有未解决断言归属，不混入本次。
