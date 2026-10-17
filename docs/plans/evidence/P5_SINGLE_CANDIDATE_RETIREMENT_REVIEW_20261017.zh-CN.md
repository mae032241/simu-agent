# P5 单环境入口与旧 live 池退役独立静态审查

结论：**静态 PASS，可精确提交本节点。** 基线 `71394a3`；审查三处 Python 差异及对应设计、实施账、消费者账、主计划四文档。不代表安装产物、live 执行或全部旧入口退役已验收。

## 删除依据与行为保留

- 删除前 `create_environments/LazyEnvironments` 的仓内生产调用仅 `probe_root_host_live.py` 两种导入与 `prepare` 的一次 `[distribution]` 取值；该函数本来只允许 core/all_domains。测试唯一命中是 `tests/operations/test_root_host_live.py` 的 mock。无其他已发现的仓内注册/调用，未声称覆盖仓外私有脚本。
- 当前 `scripts/probe_root_host_live.py:145` 直接调已有 `create_environment(..., cohort=distribution)`；两种导入同步。没有新增环境选择、循环、重试、fallback 或另一安装框架。旧池切换/销毁语义没有剩余消费者。
- `scripts/installed_candidates.py:87` 保留 core/tcad/curve/figure 的 wheel 源。删除只由已退役池触达的环境选择、五个 fixture wheel source 条目及 TCAD 双 pip fallback；fixture 源文件及其源码功能消费者未删除。
- `tcad` 仍构建 core/curve/tcad wheel，单次 pip 显式安装 core+tcad、通过 wheelhouse 解析 curve；`all_domains` 仍同一环境装原四 wheel 且 `--no-deps`。后者不被冒称 TCAD 依赖解析验收。core 路径保持单 core。
- `tests/conftest.py:58` 和 `scripts/run_tests.py:295` 的安装 choices 仍只有 core/tcad；普通功能 fixture 不增安装，未恢复矩阵。`_run_logged` 仍由 `root_host_upgrade.py` 等使用，不在删除范围。

## 现有负控的实际价值

唯一测试修改保持原 `test_new_candidate_root_does_not_inherit_personal_worker_model` 的所有 Root/个人 Worker model 隔离断言，mock 返回单个环境，并要求调用显式传 `cohort='core'`。若迁移遗漏新 API、丢失/改错该 cohort 或把个人 Worker model 泄漏为 Root model，该检查能失败。它 mock 安装/命令执行，不证明真实 wheel、pip 或 live host 成功；本节点没有因此再造安装测试或新增矩阵。原五个 test 函数均保留。

## 证据与范围

独立检查为源码/Git 差异与消费者文本搜索、三 Python 文件标准库 AST 解析、限定 `git diff --check`，均无报错。未运行 pytest/collect、项目 import、pip/venv/build、live prepare、业务 CLI、模型或服务器。作者完整文件账见[实施记录](P5_SINGLE_CANDIDATE_RETIREMENT_IMPLEMENTATION_20261017.zh-CN.md)。

四文档准确区分此次旧池退役、历史事故事实和安装动态资格。旧 scid/CLI/MCP、systemd/installer、旧 SQL/CAS 档案及 TCAD 生产授权仍有实际消费者，本节点未删；`history.bind` 旧测试仍有断言归属待审，未顺带整删。P4c2 可写恢复仍 BLOCKED，不混入本次结论。后续按消费者继续独立退役，不需要为本次静态提交启动安装或全量回归。
