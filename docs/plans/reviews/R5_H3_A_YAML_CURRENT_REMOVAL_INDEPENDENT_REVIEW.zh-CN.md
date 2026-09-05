# R5-H H3-A YAML current 删除独立实现审查

日期：2026-08-30  
审查基线：`404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前工作树  
权威计划：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
权威计划 SHA-256：`16ff56122a8d4a861eb75969b2824e9be3a43d7862b8f2f320485297127b76d0`  
审查范围：只审 H3-A；未审查、未放行 H3-B/H3-C/H3-D  
结论：**打回**

## 1. 阻断项

### 1.1 当前安装命令仍把 PyYAML 当作部署依赖

`docs/INSTALL.md:32-35` 和 `docs/INSTALL.zh-CN.md:30-33` 的 Conda 命令仍显式安装
`pyyaml>=6,<7`。这与同一文档顶部已经删除 PyYAML 前置要求、`pyproject.toml` 只在 test extra
声明 PyYAML、安装器不再探测 PyYAML，以及实施记录所称“仅 test extra 保留 PyYAML”直接矛盾。

可达影响不是运行故障，而是当前发布说明仍要求用户为生产环境安装已删除的依赖，因此 H3-A 的依赖
删除尚未形成一致、可执行的发布合同。

最小修复：只从中英文两条 Conda 示例中删除 `'pyyaml>=6,<7'`，不新增依赖探针、安装兼容分支或文档
解释层。

### 1.2 当前33项约束账本仍声称第二套 current 存在

`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml:6-11` 的 `AUTH-001` 仍为
`known_issue`，并写明 `research_state.py` 与安装期 YAML 校验“仍形成旧 current 表面”；
`MIG-001` 在第192-197行同样写明安装期“仍读取” `research/current.yaml`。这两个事实已经被本次
删除和真实安装测试否定，也与当前中英文架构文档“ResearchInstance/数据库绑定是唯一运行时
current”的说明冲突。

约束账本是当前规范性验收矩阵，不是历史审计，不能保留已失效的现在时结论。历史计划和旧审查报告
继续保留旧 YAML 叙事没有问题。

最小修复：只把 `AUTH-001`、`MIG-001` 的 assessment/evidence 更新为 H3-A 当前事实和已有无 YAML
安装证据；不得改写约束本身，不得增加运行时 current 校验、迁移器或新控制实体。

## 2. 已通过的实现边界

除上述当前文档真相未同步外，H3-A 的生产实现符合“只做减法”：

- `src/scidiscovery/research_state.py` 已完整删除，基线文件为468行；`src`、`deploy`、基础入口和
  安装器均不再引用 `research_state` 或 `research/current.yaml`。安装器没有读取或删除用户旧 YAML；
- 基础依赖不含 PyYAML，`runtime_identity.TRACKED_DISTRIBUTIONS` 只保留 `pydantic` 和
  `setuptools`；生产代码没有引入其他 YAML 解析器；
- `core_no_yaml` 使用 `venv.EnvBuilder(..., system_site_packages=False)`，安装 core wheel 时使用
  `--no-deps`，随后只复制 Pillow、Pydantic 及其现有传递依赖。probe 清除 `PYTHONPATH`、设置
  `PYTHONNOUSERSITE=1`，并验证导入的 `scidiscovery` 位于该 venv 内；没有修改 `sys.path` 或拦截
  import；
- 对审查时生成的该 venv 直接检查，`pyvenv.cfg` 为
  `include-system-site-packages = false`，`find_spec("yaml")` 和
  `find_spec("scidiscovery.research_state")` 均为 `None`；wheel 元数据只在 `extra == "test"` 条件下
  声明 PyYAML；
- 同一无 YAML installed-wheel probe 真实执行唯一 installed catalog 编译，打开当前格式数据库，创建并
  关闭 ResearchInstance，以同一 state root 新建 runtime 后读回 `closed` 终态；还真实启动 CLI、
  Root daemon 和 Worker daemon 的入口探针；
- 当前规模为150个生产 Python 文件、59709行；相对 H2b 第五轮151个文件、60177行，净删1个文件、
  468行。`operations/` 仍为7个文件、2064行。未发现 H3-A 新增生产文件、Schema、数据库表/列、
  状态、Registry、入口或兼容器；
- `_LEGACY_WORKER_TOOLS`、旧 Worker 路由、`worker_read_input` 和旧 `worker_finalize` 仍存在，证明
  H3-B 没有被提前实施。

## 3. 七项核查结论

| 核查项 | 结论 | 证据 |
| --- | --- | --- |
| 删除 YAML current 权威且不碰用户旧文件 | 通过 | 模块删除；生产/部署无路径引用；安装器只清理受管 `.codex` 等目标，不扫描 `research/` |
| PyYAML 只作测试依赖、无替代解析器 | **未完全通过** | 代码与元数据通过；当前中英文安装命令仍要求安装 PyYAML，形成阻断1.1 |
| 无 YAML 环境构造真实 | 通过 | `system_site_packages=False`、无 source `PYTHONPATH`、无 import 拦截，直接检查 `find_spec("yaml") is None` |
| installed catalog 与数据库终态重开 | 通过 | 两个 clean-wheel 聚焦测试真实通过 |
| 净删468行且未开始 H3-B | 通过 | 生产指标及旧 Worker 符号扫描 |
| 回归证据可复核 | 通过 | 309项可收集；实现记录给出全量结果；本审查重跑 clean-wheel、38项聚焦门和 diff check |
| 33项约束、唯一 current 与双语当前语义 | **未完全通过** | 运行实现和中英文架构一致；当前约束账本仍保留已失效事实，形成阻断1.2 |

## 4. 本次独立复核命令与结果

```text
pytest -q \
  tests/operations/test_baseline_plugin_discovery.py::test_core_only_install_has_only_the_unported_domain_bridge \
  tests/operations/test_baseline_plugin_discovery.py::test_core_clean_wheel_runs_runtime_cli_and_both_daemon_entries \
  tests/operations/test_r5_catalog_stages.py::test_catalog_stages_add_no_second_registry_or_complexity_escape \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services
结果：5 passed in 38.95s

pytest -q tests/artifact_agent/test_deploy_scripts.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/operations/test_architecture_constraint_matrix.py
结果：38 passed in 5.88s

pytest --collect-only -q tests/operations
结果：309 tests collected in 0.74s

git diff --check
结果：通过

python scripts/r5_current_metrics.py
结果：production_python={files:150, lines:59709}；operations_package={files:7, lines:2064}

rg -n -i 'research_state|research/current\.yaml|current\.yaml|pyyaml|import yaml|from yaml' \
  src deploy pyproject.toml README.md README.zh-CN.md docs/INSTALL.md docs/INSTALL.zh-CN.md
结果：生产/部署无旧 current；只命中 test extra 和中英文 Conda 示例
```

另对测试生成的 `core_no_yaml` venv 直接执行 installed Python，结果为：

```text
include-system-site-packages = false
yaml None
research_state None
scidiscovery 位于 core_no_yaml/lib/python3.12/site-packages
PyYAML 只以 extra == "test" 出现在 wheel requires 中
```

## 5. 非阻断债务

- 本审查没有重复执行309项完整 Operation 回归；实施记录给出全量309项通过，本审查确认测试集合仍为
  309项并重跑了真实无 YAML 安装链和38项部署/平台/约束门，足以定位 H3-A 风险。
- 仓库根 `MANIFEST.sha256` 仍有已删 `research_state.py` 的历史条目；发布构建器会从实际输出重新生成
  manifest，当前安装器不读取根 manifest，且计划已把总 manifest 更新冻结在 H3-D，因此不作为
  H3-A 阻断，但 H3-D 必须关闭。

## 6. 最终判断

H3-A 的运行代码和真实无 YAML 安装路径已经达到预期，也没有把控制面重新做重；但当前安装命令和
规范性约束账本仍与实现矛盾。完成上述两组纯文档最小修复并复审通过前，结论保持“打回”，不得开始
H3-B。修复不得触碰生产控制面。
