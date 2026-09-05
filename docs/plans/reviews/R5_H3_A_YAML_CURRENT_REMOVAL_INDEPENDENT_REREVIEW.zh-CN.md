# R5-H H3-A YAML current 删除独立实现复审

日期：2026-08-30  
审查基线：`404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前工作树  
权威计划：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
首轮实现审查：`docs/plans/reviews/R5_H3_A_YAML_CURRENT_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`  
首轮报告 SHA-256：`fceffabfa037bc860f5b0819eb1ce49e6e072871fac2bea404e89ffdb47c405a`  
审查范围：H3-A 当前候选；不审查 H3-B/H3-C/H3-D 的实现  
结论：**通过**

## 1. 首轮阻断复核

| 首轮阻断 | 修复结果 | 当前证据 |
| --- | --- | --- |
| 中英文安装命令仍把 PyYAML 当作部署依赖 | 已关闭 | `docs/INSTALL.md:32-35`、`docs/INSTALL.zh-CN.md:30-33` 的 Conda 示例只保留 Pydantic、setuptools、packaging 和 pip；当前安装文档不再出现 PyYAML |
| 33项约束账本仍声称第二套 current 存在 | 已关闭 | `AUTH-001`、`MIG-001` 均改为 `conformant`，证据准确记录 H3-A 删除和无 YAML installed-wheel 重开；requirement/prohibited 未被改写 |

两项修复均为当前文档真相同步，没有新增入口校验、运行时探针、Registry、状态、兼容层或迁移器。
与首轮审查冻结的哈希相比，`pyproject.toml`、`deploy/install.sh`、`runtime_identity.py` 和三份无 YAML/
规模测试文件均未变化；只有两份安装文档与约束账本发生预期修订。

## 2. H3-A 原边界复核

- `src/scidiscovery/research_state.py` 仍完整删除；基线文件468行。`src`、`deploy`、基础入口、README
  和当前安装文档均不引用 `research_state` 或 `research/current.yaml`；安装器不会读取、迁移或删除
  用户旧 YAML；
- `pyproject.toml` 的基础 dependencies 不含 PyYAML，只在 test extra 声明；
  `runtime_identity.TRACKED_DISTRIBUTIONS` 不含 PyYAML，生产代码没有替代 YAML 解析器；
- `core_no_yaml` 仍由 `system_site_packages=False` 的 venv 构造，core wheel 以 `--no-deps` 安装，只把
  当前 Pillow、Pydantic 及其传递依赖复制进测试 venv。probe 清除 `PYTHONPATH`、启用
  `PYTHONNOUSERSITE`，没有修改 `sys.path` 或拦截 import；
- 真实 installed-wheel probe 确认 `find_spec("yaml") is None`，编译唯一 installed
  `CompiledCatalog`，打开当前格式数据库，创建并关闭 instance，以同一 state root 新建 runtime 后
  读回 `closed` 终态，并通过 CLI、Root daemon 和 Worker daemon 入口探针；
- 当前生产规模仍为150个 Python 文件、59709行，`operations/` 仍为7个文件、2064行。相对 H2b
  第五轮净删1个文件、468行；没有 H3-A 新增生产实体、表、状态、入口、注册表或兼容器；
- `_LEGACY_WORKER_TOOLS`、旧 Worker 路由、`worker_read_input`、旧上传协议和旧
  `worker_finalize` 仍原样存在，证明没有提前实施 H3-B。

## 3. 独立重跑证据

```text
pytest -q \
  tests/operations/test_baseline_plugin_discovery.py::test_core_only_install_has_only_the_unported_domain_bridge \
  tests/operations/test_baseline_plugin_discovery.py::test_core_clean_wheel_runs_runtime_cli_and_both_daemon_entries \
  tests/operations/test_r5_catalog_stages.py::test_catalog_stages_add_no_second_registry_or_complexity_escape \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services
结果：5 passed in 39.49s

pytest -q tests/artifact_agent/test_deploy_scripts.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/operations/test_architecture_constraint_matrix.py
结果：38 passed in 6.07s

pytest --collect-only -q tests/operations
结果：309 tests collected in 0.68s

python scripts/r5_current_metrics.py
结果：production_python={files:150, lines:59709}；operations_package={files:7, lines:2064}

git diff --check
结果：通过

rg -n -i 'research_state|research/current\.yaml|current\.yaml|pyyaml|import yaml|from yaml|ruamel' \
  src deploy README.md README.zh-CN.md docs/INSTALL.md docs/INSTALL.zh-CN.md pyproject.toml
结果：只命中 pyproject.toml 的 test extra；生产、部署和当前安装文档无旧 current 或 PyYAML 引用
```

本复审没有重复执行309项完整 Operation 回归；首轮实施记录已提供全量通过，本轮重新执行了风险对应的
真实无 YAML 安装链及全部38项部署/平台/约束门，并确认测试集合仍为309项。

## 4. 非阻断债务

- 仓库根 `MANIFEST.sha256` 仍保留已删模块的历史条目。发布构建器会按实际输出重新生成 manifest，
  当前安装器不消费根 manifest，且权威计划明确由 H3-D 统一更新发布 manifest；H3-D 必须按计划关闭，
  但不阻断 H3-A。
- H3-B 的旧 Worker 工具和路由仍是已知待删表面；本报告只确认它们没有在 H3-A 被提前或局部删除，
  不代表其实现已经通过。

## 5. 最终判断

首轮两个阻断均以最小文档修复关闭，H3-A 的运行实现、安装发布说明、33项约束账本和唯一 current
语义现已一致。未发现新增控制面或阶段越界。**H3-A 通过，只放行 H3-B；H3-C、H3-D 仍不得开始。**

本报告最终字节的 SHA-256 由交付消息给出；哈希不写入自身以避免自引用改变摘要。
