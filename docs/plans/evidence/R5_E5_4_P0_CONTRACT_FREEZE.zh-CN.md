# R5 E5.4 P0 合同冻结证据

日期：2026-09-06。代码基线：`71b4d890cc62ea7afa052804687afb3058ce581b`，分支 `refactor/m7-pre-e5.2`；范围为相对 HEAD 的工作树修改，无提交。依据[已通过的计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)第 3.2、5 节及[GPT-6 复审](../reviews/R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN_GPT6_REVIEW.zh-CN.md)第 6 节。复审绑定计划 SHA-256 为 `68d294535b85ebdbde8022aa85fb9651a51218aaa6998042ee08d7cb76e46927`；P0 后仅更新计划状态／进度，不改变已审合同。

## 冻结合同

本表是计划第 3.2 节的实施检查索引，不是已实现 schema 或科学结果。所有形状都保留 request、manifest、report 各 1；intent v2、request v3、manifest/report v2、私有候选 v1，Intake/Audit schema 不变。

| 结果 | source_panels / audit_overlays / curve_tables | 必须保留／禁止伪造 | 下游 |
|---|---|---|---|
| 可信测量 | 1 / 1 / 1–32 | 真实来源、轴、绑定、series 与实际附件；部分未决逐项保留 | Intake、audit、合格表 normalization；不自动代表全目标覆盖 |
| 恢复图但无可信轴或身份 | 1 / 1 / 0 | unresolved 原因与真实候选叠图；缺轴不填 calibration，身份不清不填确认 series | 零表初稿、audit、一次完整修订合法；领域 normalization 拒绝 |
| 无可恢复图 | 0 / 0 / 0 | 源 hash、receipt、原因；空 panels/series/图像附件；无假 hash、宽高、轴或 CSV | 零图零表初稿、audit、一次修订合法；领域 normalization 拒绝 |

来源使用 embedded image / page render / raster / unrecovered 判别分支；只有 embedded 要求 PDF 对象身份。附件允许零的端口仍受按形状校验和实际完整族约束，缺锚点、丢应有附件、混族必须拒绝。修订 guard 核对实际附件集合；不改变中央生命周期。

职责固定：figure 插件拥有恢复、候选、轴解、测量和重放；Agent 只选择候选并绑定可见科学身份，不能写几何／统计；curve 保留通用合同、评分、误差分析，TCAD 保留项目／原始解析／执行。实例拥有论文、目标、材料身份和科学比较要求。候选是确定性文件与 receipt，不新增注册表、Operation、Agent 或状态。

## 合法资源边的编译探针

探针定义在 `tests/operations/test_catalog_installed_entrypoint.py::_DETECTOR_RESOURCE_PROBE`；同一文本由源码测试和 installed figure 环境执行，避免两套断言漂移。只对测试内现有 figure PluginDefinition 做 `model_copy`：

- request 输出的实际 `context_validator` 与 materialize 的实际 transform 各追加同一个 `ComponentRef`；保留原 semantic contract 资源。
- 临时资源由现有模块上的测试属性提供，`patch.object` 在每次编译后还原；没有新生产资源、模块、注册表或 callable 实现。
- baseline、只改 `detector_version`、只改 `ocr_model_sha256` 三种字节，复用未经修改的 `compile_catalog`。每种重复编译摘要稳定；两个目标 Operation 都能到达该资源且得到精确字节。
- 两种单字段变更都改变 request/materialize digest，所有 curve_score 所有的 Operation digest 不变，目录 Operation 集不变。成功编译本身证明合法边不触发 `agent_resources_unsupported`；没有放宽 worker 资源限制。

installed 探针从唯一 `scidiscovery.plugins` entry point 加载真实 wheel 声明，核对四插件精确集合和资源所在实现模块位于环境安装前缀。既有 fixture 会串行构建包括旧案例在内的其他测试 wheel；本探针执行环境不安装案例。P0 不删除既有构建项，不把这次测试记为案例删除、完整安装矩阵或自动检测通过。

## 删除引用基线

已执行以下只读扫描；与计划第 2 节矩阵一致，本次没有删除命中项。路径为本仓库相对路径。

```sh
rg -n 'ingaas_fig4|ingaas\.fig4|figure_geometry|SCORER_CONTRACT|ZnTotal' pyproject.toml plugins deploy scripts tests README.md README.zh-CN.md docs/INSTALL.md docs/INSTALL.zh-CN.md
rg -n 'ingaas_fig4|ingaas\.fig4|figure_geometry|SCORER_CONTRACT|ZnTotal' src scripts/r5_baseline_metrics.py
```

| 命中组 | P1 基线处置 |
|---|---|
| `plugins/ingaas_fig4/` 的 plugin、transform_adapter、figure_compilation、geometry 和 pyproject | 全部生产删除；两条案例 Operation 不迁移 |
| `deploy/apply_ingaas_fig4_profile.sh`、根 pyproject pythonpath、`scripts/build_git_release.py` | 删除 wrapper、案例导入路径和发布项 |
| README、INSTALL、deploy README 中英文现行说明 | 删除案例安装建议，保留通用显式安装入口 |
| `test_ingaas_operation_plugin.py`、两个 figure 测试、installed/conftest、m3/m4/m5 所有权与等价性测试、deploy 测试 | 删除案例成功路径，按计划补通用边界；不能仅过滤目录结果 |
| `tests/fixtures/plugins/r5_e2e_tcad_plugin/` 与 `tests/fixtures/r5_e2e_tcad/manifest.json` | 去除当前资格对案例 schema、runtime import 和依赖的加载；历史记录不作为新证据 |
| `ZnTotal` / `SCORER_CONTRACT` | 本轮命中位于案例 scorer 及相关 fixture/测试；合法 TCAD 字段与独立实例数据不得按词机械删除 |
| `src` 与 `scripts/r5_baseline_metrics.py` 的上述精确模式 | 无命中（rg 返回 1）；不新增核心案例识别逻辑，不删除扫描器 |

## 红测试策略与后续门

P0 独立交付仅含当前可通过的编译探针和本冻结记录。本次未编写或运行 detector／新 schema 的预期失败用例，不将未来行为记为已验证。按计划，P1–P4 对应实现前在工作树观察并记录红测，随该实现转绿；不提交阻断基础回归的红套件，不新增 skip/xfail。

| 实施阶段 | 必须先观察的未来失败 |
|---|---|
| P1 | 未安装 figure 的 curve 导入／评分；案例 distribution、import、entry point 和发布几何缺席 |
| P2 | 无 seed 原始源恢复／三刻度轴解／路径重放；文字、黑线、交叉、方向与不可识别轴反例 |
| P3 | Agent 几何字段、伪造 receipt/candidate/source 拒绝；两种零表初稿→audit→一次修订；缺锚点、丢附件、混族与零表 normalization 拒绝 |
| P4/P5 | 安装缺依赖在切换前拒绝；实际文件打开失败探针；独立验收器拒绝过宽包络与容易局部覆盖；两个真实 PDF 和真实 spawn |

## 验证记录

聚焦命令（仓库根目录，外层监测进程设置同样环境，pytest 无 xdist）：

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 pytest -q tests/operations/test_figure_semantic_compilation.py::test_detector_resource_uses_existing_compilation_edges tests/operations/test_catalog_installed_entrypoint.py::test_installed_detector_resource_uses_existing_compilation_edges
git diff --check
```

结果：**2 passed in 41.99s**，监测总耗时 42.48 秒；无新增 skip/xfail。外层 Python `subprocess.Popen` 启动上述 pytest，每 0.1 秒以 `ps -e -o pid=,ppid=,rss=` 递归汇总 pytest 及子进程 RSS；达到 8 GiB 时中止。采样峰值 **194,148 KiB（约 190 MiB）**，低于预算。该值包含 wheel/venv 子进程，是采样值而非内核强制内存上限；未测 live Codex 进程树或 WSL 系统增量，不代表计划第 6.1 节真实运行内存门已通过。首次单独源码探针调用的终端返回未保留最终结果，因此不计入通过证据；以上双探针运行提供完整退出码 0 与结果。

`git diff --check` 通过。修改只涉及两个测试文件、计划状态／P0 进度与本文；生产组件、编译器、旧案例插件和既有 fixture 不变。未运行整个测试文件／全目录回归、真实 OCR/PDF、spawn、solver 或部署：本次没有实现对应行为，不能以 P0 编译通过替代 P1–P6 验收。G0 独立审查仍待完成。
