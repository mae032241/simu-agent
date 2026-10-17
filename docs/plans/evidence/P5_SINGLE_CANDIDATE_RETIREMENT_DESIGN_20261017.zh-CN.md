# P5：退役旧 live 安装池的最小设计

状态：**设计经 thin_test_review_1017 独立静态审查通过；[实现独立静态审查](P5_SINGLE_CANDIDATE_RETIREMENT_REVIEW_20261017.zh-CN.md)通过，待 root 提交。** 基线 `71394a3`；依据[旧入口处置账](P5_ENTRY_RETIREMENT_LEDGER_20261017.zh-CN.md)，具体变动见[实施账](P5_SINGLE_CANDIDATE_RETIREMENT_IMPLEMENTATION_20261017.zh-CN.md)。仅静态阅读/文本/AST，不运行安装、pytest/collect、CLI、模型或服务器。

## 精确消费者与替代

| 对象 | 当前可执行消费者 | 处置 |
| --- | --- | --- |
| `scripts/installed_candidates.py::create_environments/LazyEnvironments` | `probe_root_host_live.py` 两种模块导入及 `prepare()` 唯一调用；`prepare` 已只允许 `core/all_domains`，每次只索引一个环境。`test_root_host_live.py::test_new_candidate_root_does_not_inherit_personal_worker_model` 仅 monkeypatch 此调用 | 迁到已有 `create_environment`，随后删除 pool。仓内无其他调用/反射注册/入口声明；不声称已盘点仓外调用。 |
| `create_environment` | `tests/installation/conftest.py` 唯一环境 fixture，显式 `core/tcad` | 扩展函数可接原 live 的显式 `all_domains`；pytest 参数 choices 仍只 `core/tcad`，不新增 cohort/matrix。 |
| `_candidate_creator` | 只由上述两个 wrapper 使用；迁移后只剩单环境 wrapper | 保留一次构建/一次目标环境的共用原语。仅移除已不可达的环境选择及对应 fixture wheel 构建分支，不删 fixture 源文件。 |
| `_run_logged` | 安装 fixture、creator、live prepare；`root_host_upgrade.py::prepare_upgrade` 继续使用 | 保留；日志/时限/隔离解释器规则不改。 |

同树 `rg` 已覆盖 src/plugins/scripts/tests/deploy/CI 与非历史引用。真实生产旧栈并非零消费者：`pyproject` 的 `scid`、旧 CLI 的 progression/close/ingest/catalog/approval/active-bundle/UI、MCP daemon/facade、systemd control/UI 和 installer probe 仍连接旧 Run/Artifact/SQL/审批。薄 UI/只读包没有接管旧身份/可写恢复，也没有新的真实 solver 资格，因此本节点不删除这些入口。

## 三文件方案

1. `scripts/probe_root_host_live.py`：两种导入均用 `create_environment`；`prepare` 调用 `create_environment(..., cohort=distribution)`，沿原明确 `core/all_domains` 参数，无自动 fallback 或额外环境。
2. `scripts/installed_candidates.py`：单环境 API 允许 `core/tcad/all_domains`。`core` 与 `all_domains` wheel 集合分别保持 `(core)`、`(core,tcad,curve,figure)`；`tcad` 保留现有单次 pip 的 core+TCAD 安装和 wheelhouse curve 依赖解析。删除 `create_environments/LazyEnvironments`；删除已不可达 `curve/architecture/blind_csv/m7_effect/broken/invalid_unicode` 环境选择及仅其使用的五个 fixture wheel source 条目。curve wheel 仍被 TCAD 依赖解析和 all_domains 使用，不能删。可同时收掉仅旧 pool 触达的 TCAD 两次 pip fallback；新 tcad 路径已经始终一次安装，不给它换资格语义。
3. `tests/operations/test_root_host_live.py`：原唯一 mock 改为单个返回值，并记录明确传入的 `cohort='core'`；保留 Root profile 与个人 Worker profile 分离的所有现有断言，不构建环境、不新增功能重跑。

放弃的只是未注册的旧多环境 helper/dict API 及不可达历史选择；live `all_domains` 明确请求保持其原行为，不把它声称为 TCAD 依赖解析验收。源码功能 fixture、现有单一安装组、安装 smoke、当前 plugin 注册及旧 reader/权限路径不改。

## 静态验收与边界

设计通过后只实施这三文件及证据：核 `create_environments/LazyEnvironments` 无剩余可执行消费者；删除旧 `resolve_once` 参数及两次安装分支，保留按 `tcad_resolved` 派生的本地同名 selector；核私有 wheel 源/选择闭包、唯一环境返回、pytest `core/tcad` choices、TCAD 一次依赖解析语义；三文件 AST 和 `git diff --check`。不运行脚本、安装或测试，不增加环境/重试预算或 whole-suite 入口。独审后由 root 精确提交；回滚边界为本节点三文件。

另一候选 `research_loop.history.bind` 只有旧测试调用、生产已是无条件 retired 拒绝。但这些测试混有分页/原件完整性等仍有效断言，须先逐条映射到当前 lineage 路径；本节点不借此整删 `test_history.py` 或宣称全部重复。旧栈整体退役仍被上述真实消费者和未验收资格阻断。
