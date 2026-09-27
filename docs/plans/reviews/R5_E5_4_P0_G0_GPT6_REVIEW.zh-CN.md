# R5 E5.4 P0：独立 GPT-6 G0 审查

结论：**PASS**。日期：2026-09-06。本结论限于 P0 的合同冻结与既有资源边编译探针，不授予自动检测、案例删除、完整隔离安装或真实科学验收通过。

## 审查范围与版本

仓库：`123/scidiscovery-e5.2`；分支：`refactor/m7-pre-e5.2`；比较基线：`HEAD=71b4d890cc62ea7afa052804687afb3058ce581b`。已完整阅读仓库 `AGENTS.md`、[E5.4 计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)、[计划 GPT-6 审查及最终复审](R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN_GPT6_REVIEW.zh-CN.md)、[P0 evidence](../evidence/R5_E5_4_P0_CONTRACT_FREEZE.zh-CN.md)。按跨边界审查、范围检查与最小变更原则审查；未调用科研控制面或 Worker。

相对 HEAD 的已跟踪差异只有两个测试文件，共增加 81 行；计划、计划审查及 P0 evidence 为未跟踪文档。生产源码、插件声明、编译器与 installed fixture 无修改。审查读取的精确文件摘要如下，后续状态更新不应倒推为本次已审内容。

| 文件 | SHA-256 |
|---|---|
| `tests/operations/test_catalog_installed_entrypoint.py` | `739119005e2071854f9cc4adad4867b6ac2081a78f577e6108ce1012e321d8bc` |
| `tests/operations/test_figure_semantic_compilation.py` | `00200dcf0716f1366e34e865d01153c6fd8a39aa59299a5f8157765e81077e0e` |
| E5.4 计划 | `7f8818e1e2fd22374f0f0d7f492e58486c88bdeb604806ffafb77c22f13bdb87` |
| P0 evidence | `1042214ff2756f854592250b1d2b688ed94dcd9fbf96033806396dea940288a4` |

## 六项核对

1. **合法资源边成立。** `test_catalog_installed_entrypoint.py:73–90` 从真实 figure OperationSpec 取 request 输出的 `context_validator` 和 materialize executor component，而非另写假 Operation。当前分别对应 `figure_request_context` 与 `materialize_figure_evidence`。对原 PluginDefinition 及这两个 ComponentSpec 做副本，保留原有 semantic contract 资源，再追加同一测试资源。`catalog.py:327` 从输出 validator 进入资源可达图，`:419` 从 executor component 进入，`:210` 递归解析资源；`:470–485` 仅对另行计算的 worker_scope 限制额外资源。探针没有把资源挂到 worker_tool，也没有放宽该限制。

2. **摘要断言有实际区分力。** 三轮只更换临时资源 bytes，复用同一组 `variants`，没有改变 OperationSpec、组件 target、版本或 callable。`catalog.py:135–143` 对资源 bytes 计算 SHA-256，`:711–715` 将可达组件的资源摘要纳入 Operation 摘要。探针分别改变 detector 版本和 OCR 模型摘要，逐一断言 request/materialize 的 digest 改变、全部 curve_score 所有的 Operation digest 不变；同时检查资源可达、实际编译 implementation 等于该轮 bytes、重复编译稳定及 Operation 集合不变。不是仅比较整个 catalog 或以新增组件定义造成的差异冒充字节敏感性。

3. **未发现 patch、exec 或测试导入导致假通过／全局污染。** `patch.object` 只提供测试资源属性，未替换 loader、compiler、hash 或目标 callable；上下文管理器在成功或异常退出时恢复属性，结尾还断言属性不存在。FrozenSpec 为不可变模型，修改发生在副本和新 tuple 上。源码测试的 `exec` 使用单独 globals 字典，不回写测试模块 globals；导入 installed 测试模块只取得字符串与测试定义，不启动其 fixture，也没有反向循环导入。既有源码测试模块仍导入案例代码，但传给本探针的 catalog 明确只有四个通用插件；因此源码探针不证明案例 import 缺席，独立 installed 子进程承担该项验证。

4. **installed 路径在本次实际环境成立，隔离边界明确。** 既有 fixture 先从 release 副本构建 wheel，在 `figure` venv 只安装 core、curve、figure 三个 distribution，从仓外空工作目录运行；清除 PYTHONPATH 与 role override，禁用 user site。探针从唯一 `scidiscovery.plugins` group 加载声明，断言插件精确集合为 builtin/general_science/curve_score/curve_figure_evidence；fixture 检查 core 路径，新增断言检查资源实现模块路径。本审查另在同一环境核对四个 entry point 的实现模块全部位于该 venv 安装前缀，`find_spec('ingaas_fig4')` 返回 None，案例 distribution 查询抛出 PackageNotFoundError。fixture 确实仍会构建旧案例 wheel 并创建其他环境，但它们没有成为本探针的安装或导入来源。

   此 venv 使用 `system_site_packages=True`，不是所有依赖都隔离的 hermetic 环境；仓外 cwd 也不能证明 checkout 或旧答案不可读取。上述实际检查支持 P0 的 wheel 应用包导入与案例包缺席，不支持 P4 的文件不可读声明。P0 evidence 已明确不把此次运行记为案例删除、完整安装矩阵或自动检测通过；本限制不要求在 P0 改造既有 fixture。

5. **证据与三种冻结形状一致，未冒充实现。** evidence 的 `1/1/1–32`、`1/1/0`、`0/0/0` 附件基数，与计划第 3.2 节一致；每种 request/manifest/report 各一个。无可信轴／身份不补确认测量，无图不补 image hash、正宽高、panel 或 CSV；稳定锚点、按形状校验、实际完整族、零表修订和领域 normalization 拒绝的边界保留。版本仍限于 figure 私有合同，Intake/Audit schema 不变。删除引用记录与只读扫描相符。原 evidence 的 41.99 秒及 RSS 是原运行自报记录，本审查没有原始监测日志可独立追认；下节提供另一次完整复跑证据。

   evidence 明说未来 detector/schema 红测尚未编写或运行，未借现有测试中的历史 skip 掩盖新增失败。计划第 129 行“P0 先观察并记录预期失败”仍不是本次已完成的证据；红测分配表只能记录后续待办，不能当成已观察到失败。本 G0 只确认该表未被偷换为通过证据，不给未来行为提前转绿。

6. **范围仅 P0。** 没有新增生产资源、插件、Operation、Agent、状态或平台机制；未实现 P1–P6，也未迁移或删除生产案例。两个新增测试共享一段有界探针，符合当前两个测试文件的范围。未发现需要本阶段阻断的实现缺陷，不提出新增平台抽象或后续功能要求。

## 独立验证

在仓库根目录串行执行以下两个精确测试，未使用 xdist；设置 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`：

```sh
python -m pytest -q tests/operations/test_figure_semantic_compilation.py::test_detector_resource_uses_existing_compilation_edges tests/operations/test_catalog_installed_entrypoint.py::test_installed_detector_resource_uses_existing_compilation_edges
```

结果：**2 passed in 40.59s**，退出码 0；外层监测总耗时 41.08 秒。监测器每 0.1 秒读取 `ps -e -o pid=,ppid=,rss=`，递归汇总 pytest 及子进程，并设置达到 8 GiB 时终止进程组的保护。采样峰值 **183,328 KiB，约 179 MiB**，包含本次串行 wheel/venv 构建子进程。该数字是采样 RSS，不是内核强制总量上限，也不包含整个 live Codex/WSL 内存门；不据此授予真实运行内存验收。

另执行同一 installed figure 环境的 entry point 模块前缀、案例 import/distribution 缺席检查，退出码 0；`git diff --check` 通过。未跑整文件、全目录、OCR/PDF、真实 Worker、solver 或部署，因为这些不是当前 P0 差异的已实现行为。

本轮仅新增本审查文件，没有修改被审文件、生产代码、测试、fixture 或计划，没有提交。建议项不构成额外阻断或扩大范围。
