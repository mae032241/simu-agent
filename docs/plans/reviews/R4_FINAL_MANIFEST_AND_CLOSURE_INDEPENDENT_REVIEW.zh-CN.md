# R4 最终发布清单与整体跨边界独立审查报告

审查日期：2026-08-29  
审查对象：当前根工作树、根 `MANIFEST.sha256`、新建清洁发布候选、清洁安装后的编译目录，以及 R4-A—R4-D 的既有独立审查证据  
审查性质：冻结清单后的外部只读见证；除本报告外未修改生产代码、测试、计划正文或清单

## 一、结论

**打回。**

R4 的生产实现、单入口编译目录、清单字节、清洁发布、聚焦回归及 A—D 分阶段审查均未发现新的实现阻塞；但本次冻结的 287 路径发布候选同时收录了两份自称当前权威、却仍停留在 R4-C/R4-D-B 的状态文档。它们与 R4 专项实施记录、已收录的 D-B/D-C/D-D 通过报告以及实际代码不一致。

这不是不影响发布的历史措辞：总计划明确声明自己是“唯一活跃”的重构提案，并规定“当前状态只在本文件第 26 节更新”。因此，当前发布物无法从其权威决策语料唯一确定 R4 是否已进入最终审查。按单一权威、可追溯和发布清单一致性要求，本轮不能在文档自相矛盾的情况下签发最终绿灯。

## 二、唯一阻塞项：冻结发布中的权威状态相互矛盾

1. `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md:3-4` 仍写“R4-D-B 核心合同实现进行中”。
2. 同文件 `:1489-1490` 明确规定当前状态只在第 26 节更新，审查报告不能成为另一份进度权威。
3. 同文件第 26 节 R4 行（`:1503`）仍写“R4-D-B 第一环待独立审查”，证据停留在专项 9 项、全仓 216 项，下一步还是首轮核心审批审查。
4. `docs/plans/README.md:75-76` 仍写“当前进入 R4-C”和“R4-D 尚未开始”。
5. 与此相反，`docs/plans/R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md:3-6` 正确记录 R4-D-A 四轮、R4-D-B 六轮及清单收口、R4-D-C、R4-D-D 均已通过，当前正在最终发布与整体边界审查；根清单也确实收录了这些报告。

由于前三项把总计划而非专项记录定义为状态权威，不能用“较新的专项文档看起来更绿”来静默覆盖总计划。冻结清单把矛盾的两侧都纳入了可发布内容，故问题可由任何发布消费者稳定复现。

## 三、清单与清洁发布核验

### 3.1 根清单

- `MANIFEST.sha256` 恰有 287 条记录，路径数也是 287；无绝对路径、父目录穿越或重复路径。
- `sha256sum --check --strict MANIFEST.sha256` 对 287 项全部通过。
- 清单包含 R4-D-A 首轮及第二、三、四轮报告，包含 `R4_D_B_MANIFEST_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`、`R4_D_C_EXECUTION_IDENTITY_INDEPENDENT_REVIEW.zh-CN.md` 和 `R4_D_D_FIXED_RENDERER_INDEPENDENT_REVIEW.zh-CN.md`。
- `git diff --check` 通过。

### 3.2 新建发布候选

以既有构建器新建：

```bash
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
ulimit -v 7340032
python scripts/build_git_release.py \
  --source . \
  --output /tmp/scid-r4-final-review.OTD7Rh/scidiscovery-agent
```

结果：

- 构建器复制 288 个源文件，即 287 个清单成员加清单自身；发布树清单仍为 287 条，连同清单共 288 个文件。
- 发布树内 `sha256sum --check --strict MANIFEST.sha256` 全部通过。
- 发布树与根清单的路径集合完全相同，无任一侧独有路径。
- 262 个成员字节完全一致；25 个差异成员均为审查文档。用构建器现有 `_normalize_text` 对根文件逐个重放后，25 个结果逐字节等于发布文件，未解释差异为零。差异仅是该函数既有的行尾空白清理、末尾空行清理和单一结尾换行，不是内容漂移。
- 发布树没有 `.git`、`__pycache__`、`.pytest_cache`、`build`、`dist`、`*.egg-info`、`*.pyc`、`*.pyo` 或 `:memory:` 临时状态；6 个 shell 脚本全部通过 `bash -n`。

因此，清单机械完整性本身通过；打回原因是清单忠实冻结了彼此矛盾的权威内容，而非漏文件或摘要错误。

## 四、清洁安装与唯一编译目录

为避免源码树导入遮蔽，先从上述清洁发布复制四个独立 wheel 构建源到 `/tmp/scid-r4-final-review.OTD7Rh/build-sources`，使用串行 `pip wheel --no-deps --no-build-isolation` 构建 core、TCAD、curve-score 和可选 InGaAs wheel，再安装到独立虚拟环境 `/tmp/scid-r4-final-review.OTD7Rh/installed-full`，并从仓库外工作目录探测。

清洁安装只发布一个入口组 `scidiscovery.plugins`，其中恰有：

```text
builtin       -> scidiscovery.builtin_plugin:CORE_PLUGIN
curve_score   -> curve_score.plugin:PLUGIN
general_science -> scidiscovery.general_science_plugin:PLUGIN
ingaas_fig4   -> ingaas_fig4.plugin:PLUGIN
tcad_artifact -> tcad_artifact.plugin:PLUGIN
```

`scidiscovery.transform_adapters` 和 `scidiscovery.operation_specs` 的已安装入口均为空。根及三个领域插件的 `pyproject.toml` 也只声明 `scidiscovery.plugins`。

清洁安装编译结果：

| 投影 | 数量 |
| --- | ---: |
| public | 23 |
| support | 27 |
| internal | 0 |
| all | 50 |

`public`、`support`、`internal` 两两不交，它们的并集与 `all` 精确相等；四个视图来自同一个缓存的 `CompiledCatalog` 对象，而不是四份注册表。按插件所有者计数为 curve-score 6、general-science 32、InGaAs 1、TCAD 11。可选 InGaAs 语义仍隔离在项目插件内，没有进入核心分支。

三个审批 Operation 均在同一 public 投影中：

- `science.evidence.qualify.v1`；
- `science.parameters.qualify.exception.v1`；
- `science.parameters.qualify.pass.v1`。

三者的 executor、编译审批身份和 provider 边均来自各自编译闭包。`tcad.study.execute` 为 TCAD 插件所有的 external Effect；审批身份中的 operation id、version、operation digest 与当前编译对象一致，approval contract digest 也等于当前冻结合同摘要。探测到的 operation digest 为 `89c180…4efe`，合同摘要为 `980e7e…ba2b`。TCAD runtime factory 同样从该目录对象取得，没有第二个运行配置注册表。

## 五、静态旁路与聚焦回归

### 5.1 静态边界

- 发布元数据和清洁安装均无旧 transform/operation-spec 入口。
- 固定 renderer 不再包含按科学基础、图证据、参数或 TCAD Schema 命名的渲染函数；旧 `_safe_raster_preview` 和 `/preview` 路由不存在。`approval_ui/app.py` 中保留的中文 kind 标签只是控制类审批的标题映射，不读取领域 payload，也不是 renderer 注册表。
- 核心仍保留 `artifact_transform`、`task_schedule`、`execution_request_create` 和旧 transform loader 源码；但已迁移 profile/角色由回归测试拒绝旧路径，已安装旧入口为空，只有总计划明确冻结的两个资格前设备参数 bridge 仍可用。它们是 R5 的待删除兼容债务，本轮没有重新成为已迁移 Operation 的第二调用权威。
- `platforms/roles.py` 的旧 role-pack loader、设备参数桥和部分 TCAD 安装/部署探针也仍存在。它们说明 R4 是领域迁移阶段而非“全仓轻量化已经完成”，不构成本阶段新增回归；R5 必须按总计划实际净删除，不能把 R4 绿灯解释为这些债务已消失。

### 5.2 本轮聚焦测试

所有测试均在 7 GiB 虚拟内存上限下严格串行运行：

```bash
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
ulimit -v 7340032
pytest -q \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/operations/test_operation_invoke_installed.py \
  tests/operations/test_r3_agent_contract.py \
  tests/operations/test_codex_worker_process.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_tcad_operation_plugin.py \
  tests/operations/test_curve_score_operation_plugin.py \
  tests/operations/test_ingaas_operation_plugin.py
```

结果为 `56 passed in 39.12s`。它覆盖清洁安装入口/目录、统一调用和视图、Worker 上下文合同与独立进程边界、固定审批 UI、执行审批身份、TCAD、曲线和可选项目插件。

本轮按任务要求没有重复全仓 245 项。紧邻本轮、且已被当前根清单逐字节冻结的 R4-D-D 独立报告已经串行复跑全仓 245 项；本轮用当前摘要一致的聚焦 56 项和清洁安装重新覆盖最终发布关键边界，没有发现需要触发又一次全仓运行的代码疑点。

## 六、总体架构判断

在 R4 自己的阶段边界内，实现方向符合重构目标：

- 领域功能、OperationSpec、小组件、Effect、运行配置和审批 projector 通过一次 `scidiscovery.plugins` 注册，在启动期编译为单一目录；
- public/support/internal/all 只是同一目录投影，support 没有污染规划，审批和执行没有新增状态机或决定权威；
- OperationSpec 组合既有 Task、Artifact、Approval、Execution、Worker 文件生命周期，没有演化成独立巨类；
- Agent 的输入、Worker 服务、任务路径和领域工具由编译 Operation 派生，聊天只保留固定完成信号；R2 首版仍以提示约束继承的原生工具可见性，硬隔离明确留作后续加固，不能夸大为已经实现系统级最小权限；
- TCAD author/reviewer、六个确定性支撑操作、执行 Effect、能力绑定、运行证明、曲线构建/评分和固定审批视图已经接入同一框架。真实 Sentaurus 科学运行与物理资格仍是 R7 验收范围，所以“TCAD 完整支持”在本轮只能解释为框架路径完整，不能解释为求解器科学有效性已实证。

因此，生产架构没有因本轮发现而需要扩大设计或新增实体。当前唯一发布阻塞是决策语料没有随实现事实收口。

## 七、最小修复与复审门

只需修正文档权威并重新冻结，不应修改生产代码：

1. 同步 `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 文件头和第 26 节 R4 行，准确写明 R4-A—D-D 的实现与独立审查均已通过，R4 整体处于“待最终外部独立审查”，且 R5 在最终绿灯前仍不可开始。
2. 同步 `docs/plans/README.md` 的 R4 摘要，删除“当前进入 R4-C / R4-D 尚未开始”的陈旧判断。
3. 为避免自引用悖论，在总计划的状态权威规则中明确：根清单冻结的是“待最终审查”的候选；冻结后产生的最终外部审查报告可以作为该候选的门禁见证，不反向写入自己审查的清单，下一阶段的下一代清单再吸收该报告。不得预先把未经最终审查的 R4 标为通过。
4. 重建根清单和清洁发布，并复核摘要、路径集合、规范化差异、清洁安装目录和上述聚焦测试。由于本次打回报告届时已是既存历史审计材料，下一代清单可正常纳入它；下一轮新的最终报告仍作为清单外见证，不形成递归。

下一轮放行条件是：两份当前状态文档与 R4 专项记录不再矛盾，新的根/发布清单机械闭合，清洁安装目录和聚焦边界无回归。无需为本项文档修复重做 R4-D 的六轮科学资格或全仓测试，除非修复范围越过上述两份状态文档和清单。

## 八、本报告为何不纳入被审查清单

本报告是在 287 项根清单冻结、验证完成后才产生的外部审计见证。若先把本报告摘要写入同一清单，再修改报告记载该摘要，摘要会再次变化，形成自引用；若构建后偷偷追加，则清单又不再代表实际审查输入。因此，本报告有意不反向纳入本次被审查的 287 项清单。这种外置本身不是漏项；真正的问题是本轮输入中的既有权威状态互相冲突。下一代候选可以把本次已完成的打回报告作为普通历史材料收录，而把下一轮最终报告继续留在其冻结边界之外。

## 最终结论

**打回。**
