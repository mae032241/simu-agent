# R5-G D3 直接完整对象修订独立审查

日期：2026-08-30  
审查对象：当前工作树中的 R5-G D3 最终候选  
审查基准：已独立通过的 D2 合同，以及
`docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md` 冻结的 D3 目标  
审查者权限：只审查并维护本报告；未修改生产代码、测试、架构正文、计划或状态权威

## 一、结论

本轮先后发现并打回了三个问题：发布清单仍引用已删除 Schema、TCAD 插件仍携带一套未注册但可导入的跨 Artifact 补丁协议、删除该协议后机械冻结的生产行数未同步。实现方已分别通过唯一发布构建器重新生成清单、原子删除 TCAD 遗留协议并增加零残留门、按实测值修正当前机械冻结；独立复核未发现仍未闭合的阻断项或重大项。

D3 已实现的合同不是“给旧补丁协议换名”，而是：Worker 读取冻结基对象和变更请求，写出一个新的、完整、不可变对象；该对象具有新 Task、新父链和新的审查义务。旧对象、旧审查和旧资格均不被继承。该合同由 OperationSpec 已有端口、输出、审查声明和统一目录编译表达，没有新增科学实体、持久化表、注册表、状态机或调用入口。

**最终结论：通过（只放行 D4）。**

这不等于 R5 完成，不放行实验设计或发布冻结，也不证明通用科学效果；D4 仍须运行真实假设修订和新的独立科学批评。

## 二、审查方法与边界

本次按以下本地技能执行：

- `scid-cross-boundary-review`：沿 Catalog → Root → Task → Worker → 新审查 → 普通下游追踪完整生命周期；
- `scid-change-scope-checks`：按当前候选的风险选择聚焦测试、全仓测试、生成发布包和静态零残留检查；
- `scid-find-simplifications`：核对删除是否真实、是否仍有兼容门面，以及复杂度是否净下降；
- `karpathy-guidelines`：以最小合同、可验证成功条件和避免补丁式特例为判断原则。

仓库没有逐项编号的“33/33”自动验证器，本报告不伪称运行过该脚本。33 项约束按现行计划冻结的行为约束族进行跨边界复核。历史文件只作为基线证据，不把历史计数改写为当前计数。

由于工作树包含从 R1 到 R5 的未提交累积变更，不能把 `HEAD..工作树` 的全部差异归因于 D3。本报告将 D3 与已通过的 D2 合同、D3 冻结删除清单、当前生产路径和当前测试证据交叉核对。

## 三、打回问题与返工闭合

| 轮次 | 级别 | 独立发现 | 返工与复核结果 |
|---|---|---|---|
| 第一轮 | 阻断 | 根 `MANIFEST.sha256` 仍列出已删除的 `structured_revision.py`、`evidence_receipt.py`，发布候选并非可验证闭合 | 使用 `scripts/build_git_release.py` 的唯一生成路径重建归一化 release；最终 release 共 367 个文件、366 条清单记录，包内 `sha256sum -c MANIFEST.sha256` 全通过，根清单与生成清单逐字节一致 |
| 第二轮 | 阻断 | TCAD 插件仍保留 `DeckFilePatch`、`ParameterBindingPatch`、`DeckProjectPatch`、apply/validate 函数、补丁 profile 和补丁 Operation 标识；虽未注册，却仍是可导入的兼容协议 | 原子删除该协议和角色提示残留；保留合法的 Worker 任务私有文件编辑以及已经注册的完整工程比较/diff；新增七个旧标识的零残留回归门，生产路径扫描为零 |
| 第三轮 | 机械冻结不一致 | 删除 TCAD 遗留后，结构冻结测试仍期待旧的 59238 行 | 当前状态和当前冻结统一为 141 个生产 Python 文件、59061 行；聚焦结构测试闭合，D1/D2 历史计数未被改写 |

最终候选未发现开放的阻断项或重大项。上述三个问题均在本报告形成结论前完成返工并被再次验证。

## 四、核心合同审查

### 4.1 只有一个领域无关的结构判定权威

`src/scidiscovery/operations/invoke.py:110-148` 的 `direct_revision_ports` 是直接完整对象修订形状的唯一实现。它只使用 OperationSpec 通用字段，并同时要求：

- 执行器是 Agent，科学后果为 `scientific`；
- 恰有一个 `revision_base`，且基对象数量严格为 1；
- 恰有一个非集合主输出，不允许集合输出；
- 声明了精确 reviewer、reviewer 输入端口和唯一被审查主输出；
- 新旧对象的 Schema、媒体类型、Codec 和 Schema resource 完全一致；
- 主输出数量严格为 1。

`src/scidiscovery/operations/catalog.py:683-691` 对所有声明了 `revision_base` 的操作无条件调用该判定；不满足者以 `direct_revision_contract_invalid` 在启动编译时失败关闭。Root 在
`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1071-1078`
复用同一函数，不存在第二份领域分派或 TCAD/曲线/假设特例判定。

对应负例位于：

- `tests/operations/test_general_science_plugin.py:249`：未知插件的形状矩阵；
- `tests/operations/test_general_science_plugin.py:365`：畸形 `revision_base` 声明导致目录编译失败；
- `tests/operations/test_r5_blind_producer_family.py:205`：真实未知插件无需核心修改即可完成发现与修订。

判定：单一权威成立，未知声明失败关闭，领域中立性成立。

### 4.2 Root → Task → Worker → 新审查 → 普通下游闭环

跨边界追踪结果如下：

| 边界 | 生产证据 | 判断 |
|---|---|---|
| Root 准入 | `mcp_root_operation_routes.py:1071-1179` | 只有通过统一结构判定的精确 base 端口能进入修订分支；输出 usage 仍受编译合同约束；变更请求必须是旧 reviewer 关于精确旧对象的输出 |
| 变更请求语义 | 同文件 `1161-1178` | `accepted_verdicts=None` 只证明“这是精确 reviewer 对精确基对象的输出”，不把它解释为通过结论 |
| Task 输出 | `task_outputs.py:801-840` | 新对象由新 Task 登记；父链为 instruction、全部冻结输入和 Web 引用；输出不可变并携带精确 operation 标签 |
| 独立审查 | `tasks.py:1472-1499` | reviewer Operation、reviewer 输入端口、subject ref 和（需要时）verdict 必须精确匹配 |
| 普通下游 | `mcp_root_operation_routes.py:1115-1134` | 新对象若声明 review，则普通消费者必须携带关于新 subject 的新 reviewer 输出；旧 review 无法授权 |
| Evidence 投影 | 同文件 `457-494` | 只有 `claim_evidence`、`evidence_inventory`、`cached_excerpt` 以及 Web/PDF 证据进入证据来源；`revision_base`、`change_request`、`prior_signal` 只保留在谱系中，不冒充 Evidence |

`tests/operations/test_general_science_plugin.py:606` 真实覆盖了旧对象、旧审查、修订任务完整父链、新审查、重新资格和普通下游假设生产。测试明确拒绝用旧审查授权新对象，也拒绝在冻结证据集合缺失时继续准入。

判定：修订是新对象生命周期而非状态跳转；旧 review/qualification 不继承；base/request 保留可追溯性但不改变证据语义。

### 4.3 插件安装态和核心/领域分离

独立探针得到当前目录投影：

| 安装态 | 总 Operation | public | support | internal |
|---|---:|---:|---:|---:|
| core-only | 11 | 10 | 1 | 0 |
| full | 43 | 24 | 19 | 0 |
| full + InGaAs | 44 | 24 | 20 | 0 |

三个直接修订 Operation 和 TCAD 两个直接修订 Operation 均由相同结构判定识别。根包、TCAD、曲线、InGaAs 的 Python 包均只使用 `scidiscovery.plugins` 这一统一 entry-point 组；D3 未新增插件入口或子注册表。源码中没有新增迁移，现存迁移仍只有 `0001_artifacts.sql`。

未知插件测试从干净 wheel 安装目录发现新 producer family 与 revision Operation；同 Schema 的错误 sibling 不能冒充生产者，新对象必须获得新审查。核心无需按领域名、Operation 名或 Schema 名分派。

判定：core-only/full/full+InGaAs 和未知插件都沿同一启动编译路径工作，未引入核心领域分派。

### 4.4 TCAD 和实验修订场景

`tests/operations/test_tcad_operation_plugin.py:1581` 覆盖两条真实 TCAD 生命周期：

- review-request：已有作者输出被审查要求修改，新的作者修订任务获得 TCAD 领域调试工具和任务私有工作区，完成文件编辑、调试、完整 bundle 验证和 finalize；旧审查不能进入后续 packaging；
- runtime-failure：冻结失败 attestation/log 后建立新的完整 deck 修订，继续通过领域工具、私有工作区和完整文件生命周期；旧审查同样不能授权下游。

该测试还验证修订 Task 的精确父链和不继承旧 attestation。通用科学、未知插件和曲线实验测试共同证明新 reviewer 输出进入普通下游的正向链路；TCAD 测试证明没有新 reviewer 时下游门保持关闭。

`tests/operations/test_curve_score_operation_plugin.py:303,331` 覆盖实验修订为完整对象，以及工程实验计划改写后重新审查；scientific experiment 的 cohort 部分缺失时以 `input_cohort_approval_missing` 失败关闭。工程实验计划本身未声明该科学 cohort，因此不被错误套用额外门禁。

判定：两条 TCAD 路径、领域工具、私有工作区、新审查门和实验 cohort 负例均达到 D3 的合同目标。真实求解器和 D4 科学效果不属于本阶段通过范围。

## 五、旧协议零残留与复杂度判断

### 5.1 旧协议已经从生产路径原子删除

当前 `src/`、`plugins/`、`roles/`、双语架构正文和生成 release 中不存在以下旧跨 Artifact 协议标识：

- `DeckFilePatch`
- `ParameterBindingPatch`
- `DeckProjectPatch`
- `apply_deck_project_patch`
- `validate_deck_project_patch`
- `DECK_PATCH_PROFILE`
- `tcad.deck-project-apply-patch.v1`

旧通用 `structured patch/apply/diff/receipt` Schema、六个 apply/receipt Operation、Task 投影分支、Root 递归、Transform 组件和相应角色提示也已删除。仍存在的两类行为不构成旧协议门面：

1. Worker 在自己的任务私有工作区编辑文件，这是受控文件生命周期的基础能力；
2. 已注册的完整 TCAD 工程 compare/diff 是确定性比较能力，不生成跨 Artifact patch，也不承担修订提交协议。

因此未发现兼容 facade、换名残留或双写路径。

### 5.2 奥卡姆剃刀和净复杂度

最终机械计量为：

- 生产 Python：141 个文件、59061 行；
- `operations` 包：7 个文件、2062 行；
- Root 聚合：2949 行；
- Task 聚合：6170 行；
- 通用科学组件：1754 行；
- R0 六职责聚合：9642 行。

D2 生产 Python 为 60313 行，D3 最终为 59061 行，净删 1252 行。D3 没有新增科学对象、持久化表、Schema 注册表、Operation 注册表、状态机、MCP 入口或插件 entry-point；修订形状只是对已有 OperationSpec 字段的一次纯结构判定。

这次删除把“修订是什么”从多个补丁实体、apply 操作、receipt 和递归协议收敛为完整对象输出及既有不可变父链。净复杂度确实下降，未见以新控制面重量换取表面删行。

## 六、33 项架构约束族复核

| 行为约束族 | 复核结果 |
|---|---|
| 启动编译唯一权威、统一目录、无硬编码工作流 | 修订能力只来自编译后的 OperationSpec；未知插件测试无核心改动；无第二注册表 |
| 不可变 Artifact、精确父链、实例隔离 | 新修订拥有新 Task/Artifact；旧对象不覆盖；所有冻结输入进入父链；既有实例边界未放宽 |
| Worker 最小上下文和受控文件生命周期 | Worker 只读取绑定输入与任务私有工作区，通过既有 validate/finalize 产出；未引入 Worker→Worker 通信 |
| 科学内容归 Worker、确定性校验归控制层 | Worker 负责完整对象内容；核心只判定结构、身份、谱系、审查和准入，不解释领域 payload |
| reviewer 独立、资格和人工决定不继承 | 新 subject 要求新 reviewer；旧 reviewer 输出只可作为 change request；旧资格不能授权新对象；人工审批合同未被绕过 |
| current/readiness/admission 失败关闭 | 错误 sibling、错误 subject、畸形声明、缺失 cohort、缺失新审查均被拒绝；没有默认放行分支 |
| 领域插件与副作用边界 | TCAD 工具仍由插件声明，核心无 TCAD 分派；外部执行/副作用权限没有扩大 |
| Task 生命周期、恢复和有界执行 | 沿用现有 Task/Worker/Artifact 生命周期，没有新增旁路状态或恢复权威 |
| 原型边界诚实 | 当前仍是提示约束下的工具可见性原型；D3 文档没有把它宣称为强沙箱，也没有宣称真实科学效果已通过 |

未观察到 33 项约束覆盖的行为族因 D3 而退化。

## 七、双语架构、状态权威和历史冻结

以下当前权威保持一致：

- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE.zh-CN.md`
- `docs/plans/README.md`
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`
- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`
- `docs/plans/R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md`

它们在本审查前均诚实记为“D3 候选已完成本地回归、等待独立审查；D4 未放行”，并统一记录当前 271 项 Operation 测试、308 项全仓测试和 59061 行生产 Python。英文和中文架构对直接完整对象修订、旧协议删除、工具隔离限制和 D4 未执行的表述语义一致。

D1 的历史测试计数和结构计数仍保留当时值；冻结的 `tests/fixtures/r5_structure_inventory.json` 继续作为 R5-0 历史清单，未被伪装成当前生产清单。未发现为了让 D3 通过而改写历史证据。

本报告通过后，父会话可把当前状态权威从“等待 D3 独立审查”更新为“D3 已独立通过，只放行 D4”；这项状态推进不属于审查者文件权限。

## 八、测试与命令证据

所有独立测试均串行执行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

独立审查实际执行和观察到的关键结果：

1. 七项跨边界聚焦测试：`7 passed in 6.32s`。覆盖未知插件形状、目录硬门、通用科学完整父链、实验完整对象、工程实验重审、未知插件真实安装和 TCAD 双修订生命周期。
2. 首轮全仓：`307 passed in 99.37s`。该轮发生在新增 TCAD 零残留门之前，证明当时所有既有测试闭合。
3. TCAD 遗留删除后的 py_compile 与三项聚焦测试：`3 passed in 3.06s`。覆盖旧协议零残留、TCAD 变换算法/父守卫和双修订生命周期。
4. 删除遗留后的独立全仓：`307 passed, 1 failed in 101.87s`。唯一失败是结构冻结仍期待 59238 行，而实测已降至 59061；没有行为失败。
5. 修正机械冻结后的精确闭合：`tests/operations/test_r5_catalog_stages.py` 为 `4 passed in 1.35s`；`pytest --collect-only -q tests/operations` 收集 271 项；`git diff --check` 通过。
6. 实现方在最终未再改变生产逻辑的候选上串行复跑：`tests/operations` 为 `271 passed in 91.34s`，全仓为 `308 passed in 98.05s`。独立审查者没有为仪式性重复而再次全跑不变的 308 项，而是复核了最后改动的精确冻结、目录收集和发布生成路径。
7. 独立生成最终 release：367 个文件、366 条 `MANIFEST.sha256` 记录；在生成包根运行 `sha256sum -c MANIFEST.sha256` 全部通过；生成清单与仓库根清单 `cmp -s` 一致。源码树经过发布构建器 `_normalize_text` 归一化，因此权威清单校验位置是生成 release，而不是未归一化源码根。
8. 对生产路径和生成 release 扫描七个 TCAD 旧协议标识，结果为零；标识只保留在防回归负例自身。

这些检查与风险相称：全仓行为、关键边界、最终机械改动、启动安装态和发布候选均有证据，且没有并行测试或超过 8GB 的执行。

## 九、非阻断剩余风险

1. D4 尚未执行真实假设对象的修订、新 critic 和科学内容复审；D3 只能证明协议和生命周期正确。
2. Codex 0.150.1 原型仍以可见但禁止使用的提示合同约束子 Agent 工具，不能等价宣称为进程级强隔离；这是已公开的后续 Worker 隔离目标，不是 D3 新引入的问题。
3. 真实 TCAD solver、浏览器和外部执行效果不由本阶段本地测试证明；D3 只冻结领域工具可达性、任务私有工作区和准入门。
4. 小概率内容哈希碰撞加固按用户要求只记录为后续事项，不作为本阶段阻断。

以上风险均不得被解释为 D4、实验设计或 R5 发布已经完成。
