# R5 E5.4 P3：独立 GPT-6 G3 审查

结论：**FAIL**。日期：2026-09-06。下列三个阻断均属于 P3 现有 figure 角色链的合同或资格判定；修复限定在该插件及相应生产链回归，不要求重做 P2 候选算法、完成 P4/P5 或修改中央机制。

## 审查对象

仓库 `123/scidiscovery-e5.2`，HEAD／比较基线为 `bfc4e3997ecd54bb947bbe02ef6eba52f7a7c488`。检查全部 17 个 staged／unstaged／untracked 变更路径，不含本报告。完整阅读 E5.4 已审计划、P0 合同冻结、P1/P2 evidence 与独立 reviews、P3 evidence、设计宪章及 33 项约束。使用最小改动、跨边界审查和变更范围检查技能；没有改写实现、测试、计划或 evidence，没有提交或部署。

| 本次检查点 | SHA-256 |
|---|---|
| `git diff --binary bfc4e3997ecd54bb947bbe02ef6eba52f7a7c488`，仅 tracked 差异 | `e6477d7bf5ea727437dd461791cd282cbaf45e91882bd6708646d6d9d2cbaa91` |
| 新增 `tests/operations/test_figure_role_chain_v2.py` | `8f3de6d197638e0b433cb44320cd577f46d8733784a860ebbc38f7dd91f2e8ad` |
| 新增 P3 evidence | `76c239d19d80d8dc24679651173f6dcbc0f1bb38b670466149b8a6f6ca758dcf` |
| E5.4 计划 | `79c62adcb017851113b010575658878dd8b0248d69b354a48419a30a25d01efe` |

## G3-1：合法可见标签被隐式要求等于单个 OCR token

位置：[figure_digitization.py:71](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization.py#L71)。

`build_automatic_figure_bundle` 仅在某个 `detection.tokens` 的完整 `text` 等于 `binding.visible_label` 时保留测量。这个条件无视可选 `identity_anchor_id`，也没有出现在 request 的公开 Schema、prompt 或 context 接纳规则中。正常 OCR 分词、caption／原文身份说明和视觉可读但 OCR 漏读的标签均可能因此丢失。它把计划明确属于 Agent 的语义绑定，增加了一个不等价的机械确认门。

独立反例从现场绘制的原始 PNG 进入实际 detector 和 `materialize_figure_evidence`，没有注入 path、axes 或旧 request。图像为 340×250 白底，框 `(40,30,300,200)`，x ticks `80/170/260 → 0/3/6 V`，y ticks `50/115/180 → 100/10/1 A`；红线实际像素为 `x=80..260, y=150-x//5`。图上明确画出 `Reference data`。只替换缺席 OCR 的 TSV adapter：标签正常分为 `Reference` 与 `data` 两个 token，bbox 分别为 `(130,8,180,18)`、`(185,8,212,18)`；刻度 tokens 对应图上实际 tick ink。其余恢复、候选、轴解、receipt、像素和物化均走生产函数。

同一 source、receipt、plot 和 path 的结果如下：

| Agent 的 `visible_label` | Schema／Pydantic／context | 生产物化 |
|---|---|---|
| `Reference data`，未提供可选 anchor | 全部接受 | `unresolved_image`，0 表，原因 `identity_visible_label_unconfirmed`、`no_trustworthy_measurement` |
| 仅改成 `Reference` | 接受 | `measured`，1 表，181 个 eligible rows |

轴和像素没有变化，失败不能归因于轴不可靠或 OCR 尚未供应。当前测试 helper 只使用单词 `Reference`／`Candidate`，未覆盖此真实 adapter 形状。

最小修复：让已接纳的无 anchor 语义绑定按计划由 Agent 的原图／原文判断与后续独立 audit 承担，不再要求完整标签恰好等于一个 OCR word；提供 anchor 时继续严格验证其源、存在性和文字绑定。保留真正未决身份的显式拒绝，不开放几何或参数。补一个完整多词可见标签的 source→intent→materialize 正例，以及伪造显式 anchor 的反例；不能以截短科学标签令测试通过。

## G3-2：共享物理支持被统一撤销定量用途

位置：[figure_digitization.py:129](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization.py#L129)、[figure_digitization.py:142](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization.py#L142)，以及 [test_figure_role_chain_v2.py:272](../../../tests/operations/test_figure_role_chain_v2.py#L272)。

当前判定是 `int(not shared and not ambiguous)`，并将 `shared or ambiguous` 一律解释为 `ambiguous_path`。因此共享这一事实本身就足以令每个系列的观测不可计量，即使科学身份和实际坐标已经确定，也没有共享可计量分支。这违反用户已明确的语义：同一重合像素可由双方系列用于定量，只不能重复算成统计独立的物理样本。计划保留的共享支持和真正连接歧义也应区别处理。

独立原始图探针沿用上述坐标框与可信 ticks，将图内曲线改为黑色双线：`x=80..260`，`d=max(0,abs(x-170)-12)//3`，分别画 `y=115-d`、`y=115+d`。选择实际 detector 返回的四条候选，不传任何共享范围或像素。生产链得到 545 个 observed rows、333 个 global unique pixels，其中 319 行标 shared、226 行标 exclusive；545 行全部 eligible=0，四个 normalized series 均为 `no_quantitative_eligible_rows`。已独立通过的 owning 测试也明确断言任何 shared 行都必须 eligible=0。

这个交叉探针本身存在连接歧义，**本审查不要求把它的四条完整候选全部改为合格**。它证明当前实际执行的禁用路径；阻断依据是代码另有独立的 `not shared` 硬否决，不能表示用户要求的已确认共享定量。P2 会给共享候选保留粗粒度的 `path_junction_ambiguous`，那是待解释的候选限制，不能在 P3 中把所有共享观测永久等同于科学身份或连接不确定。

测试覆盖也发生了实质变化：`test_shared_direct_pixels_survive_member_tracking_diagnostics`、`test_shared_gap_preserves_real_pixels_without_inventing_a_source` 等原有正例现在通过 `_legacy_algorithm_bundle` 调用旧算法；局部歧义的原 Root 测试也改为历史 helper。保留这些单测合理，但它们不再证明新 source+intent 生产入口保留了共享定量和局部限制语义。新自动链只有“共享不可计量”的反例，没有对应的可计量共享正例。

最小修复：只在 P3 资格判定中区别“共享同一已确认观测”和“身份／连接确实未决”，保留同一 `pixel_id`／shared provenance 与全局唯一像素去重；真实歧义仍不得资格化。不能只翻转所有共享行，也不能靠 Agent 填区间、seed 或统计。增加经过新生产 materialize／normalization 的成对回归：确认的共享支持双方可用且物理计数去重；真正连接歧义保持不可计量。无需新协方差模型、P2 候选算法重写或中央字段。

补充核对：上述探针同时得到 `qualified_series_count=4` 与 `eligible_curve_rows=0`。既有 manifest 模型的该计数按 matched identity binding 计算，normalizer 实际拒绝零 eligible 的系列，所以**本审查没有发现由该计数绕过定量资格**，不把它另列为阻断，也不据此要求重写资格机制。它不能被报告为“四条曲线已获定量资格”。

## G3-3：候选唯一／互斥限制未在 Worker 可见合同中闭合

位置：[figure_digitization_contract.py:112](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py#L112)、[figure_digitization_contract.py:120](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py#L120)，以及 [figure_science_operations.py:142](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py#L142)。

`_unique_labels` 要求 selected／rejected 的全部 `candidate_id` 唯一且互斥；公开数组 Schema 没有相应约束，compiled semantic contract 也只泛称 cross-field consistency，未列出该实际规则。完整重复的 binding 甚至是 JSON Schema 可表达的数组唯一性，却只在 Python validator 中被拒绝。

独立复现使用现有自动合成图 helper 生成合法 intent，只执行 `intent['bindings'].append(dict(intent['bindings'][0]))`。随后在隔离临时 runtime 经真实 Root preflight/invoke → `LocalWorkerMCPRouter.worker_open_assignment` 读取本次生成的 `schema/result.schema.json`：它接受完整 envelope（`is_valid=True`）；把同一 envelope 写入该 Run 的 `result.json`，实际 `worker_submit_result` 返回 `state=rejected`。直接 Pydantic 校验的错误是 `candidate selections and rejections must be disjoint and unique`。这不是仅比较两份手写 fixture Schema。

最小修复：把可表达的数组唯一性放入同一个输出 Schema；对按 candidate ID 去重、selected/rejected 互斥等关联规则，在现有有稳定 ID 的 payload 语义规则中精确声明，并使现有 validator 与其一致。补真实 assignment／submit 的重复 binding、同 ID 不同文字和 selected/rejected 冲突负例。只闭合 figure 的已有合同，不新增中央校验框架或放宽 extra=forbid。

## 已核对路径与执行证据

生产差异仅在 figure 的八个既有模块；没有新增 Operation／Agent／plugin／registry／状态机，没有修改 `src/`、其他插件、部署或 P2 detector/source。完整 catalog 仍为 48 条，figure 为 5 条。inspect 参数仅为绑定源名，公开投影不包含 bbox、ticks、像素、种子或统计；intent 顶层及 nested binding 的机械字段 extra 拒绝通过。旧 geometry request 已从正式 materialize 输入移除，历史算法 helper 不是现行 Operation。

已检查并运行的自动链覆盖 source/hash/receipt/plot/path/显式 anchor 拒绝、跨 source／plot 拒绝、删除工具目录后的重放、正反向 x 和 log y、真实像素局部空白、选择顺序、三种结果形状、精确附件数量／声明、混族拒绝及完整父链。两种零表形状均通过真实本地 Root/Worker 文件链的初稿→audit→一次完整修订→再次 audit；零表 normalization 在领域 guard 和直接 normalizer 两处拒绝。这些工程 payload 是测试生成的，不是 live 科学 Agent。

DETECTOR_CONTRACT 沿 request context validator 和 materialize transform 的现有资源边编译；修改 detector version／测试 OCR digest 会改变两条目标 Operation 摘要，curve 摘要不变。实际 Pillow／PDF Poppler 的运行边界已核查。当前 `tesseract` 不存在，OCR version/model digest 为 null、明确 awaiting_P4，未经供应的 executable 会失败；本次结构化 tokens 替换不证明真实 OCR 或模型摘要验证。

所有执行串行，环境统一 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS='' PYTHONDONTWRITEBYTECODE=1`，没有 xdist。外层监测器每 0.1 秒用 `ps -e -o pid=,ppid=,rss=` 递归汇总被测进程树 RSS；达到 8 GiB 即终止进程组，未触发。

| 独立执行 | 结果 | 外层耗时／采样进程树峰值 |
|---|---|---|
| 下列七文件聚焦 pytest | **136 passed in 23.75s**，退出码 0 | 24.25s／228,928 KiB |
| 独立原始合成图多词标签、共享观测与 Schema/model 比较 | 得到上述确定性反例，探针正常退出 0 | 1.13s／61,940 KiB |
| 重复 binding 的真实本地 Worker assignment/submit 探针 | 实际 Schema 接受、实际提交拒绝，退出码 0 | 1.23s／93,836 KiB |
| `git diff --check` | 通过 | 无空白错误 |

```sh
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_figure_role_chain_v2.py \
  tests/operations/test_figure_semantic_compilation.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_figure_local_observations.py \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_m2_optional_figure_plugin.py
```

监测值是 pytest／探针及其子进程的采样 RSS，不是 cgroup 强制上限或 live Codex／WSL 增量。确认上述阻断后没有扩大到完整目录、重复安装矩阵或真实论文运行。P3 evidence 的 176 passed 和 installed 证据已阅读，但不冒充本次独立执行结果。

P1/G1 已独立复现的九项基线失败仍按既有记录处理：installed hardened 一项、L4 一项、L5 六项为既有 runtime admission 问题，另有 `test_spec` 字段序列遗漏 `complete_transform_family`。本审查没有重跑基线或归责 P3，也不称完整目录全绿。

P4 的干净发行／服务身份和 PATH／实际模型依赖预检、五类安装负测及文件不可读负探针，P5 的两张真实 PDF、真实 spawn、独立精度／覆盖门仍未完成；这不是本次 FAIL 的原因，也不能由修复以上三项代替。33 项约束只用于本次 ROLE、DET、EVD、UNC、LIN、PLG 等边界审查，没有重新授予全表 conformant。只新增本报告，未修改其他仓库文件，未提交，未部署。

## 有界返工复审

最终结论：**P3/G3 PASS**。日期：2026-09-06。G3-1、G3-2、G3-3 均已关闭，本次限定范围未发现新的阻断。上述首轮 FAIL 与反例原样保留；本结论绑定下述返工版本，不授予 P4/P5、真实 OCR、科学资格或部署通过。

### 精确复审对象

HEAD／比较基线仍为 `bfc4e3997ecd54bb947bbe02ef6eba52f7a7c488`。完整阅读更新的 P3 evidence、有界返工的三个生产模块和两个测试文件，并核对其余 P3 差异与边界。没有引入新的候选算法、字段、连通组、协方差系统或隐藏资格门。

| 返工检查点 | SHA-256 |
|---|---|
| 当前 tracked binary diff，相对上述基线 | `26c199f2c9dce1e243c3e8198bafb975b7c7fbbce1deac708f596dcf4ebfff89` |
| `figure_digitization.py` | `a76afd44ba658f1408fb839377febc0a433417e7b16e3156b521059bc663d810` |
| `figure_digitization_contract.py` | `6103f2b97ac04459421128dbf49f81b33d049148a9cb8b7a2e6b79ea8643827e` |
| `figure_science_operations.py` | `1c50e9ee1c8095aaafa122677c0545b6c534a858692d117eebb766343bfcf25c` |
| `test_figure_role_chain_v2.py` | `62e43812b7c05537d94f1048db3600bfaa148374918b34339a242c68c77000a1` |
| `test_figure_semantic_compilation.py` | `e92c841cf12238e745dd257dba8a9ab13b54efface44487cd5cdc5bee6b75ffa` |
| 更新的 P3 evidence | `281b164ec619f8b76cbecec945c2d2228a68e2d6696ac05e4dc56de6bc3bd0bd` |

### 三项关闭依据

**G3-1 已关闭。** 物化器删除了完整标签等于单个 OCR token 的条件，prompt 也明确无 anchor 的语义标签可以跨 OCR 词或来自原文 caption。本审查重新现场绘制首轮独立 340×250 原图，保留原三刻度轴、181 像素红线及分开的 `Reference`／`data` tokens，未使用新增测试的图像 helper。完整 `Reference data` 通过实际 context，生成 measured／1 表／181 eligible rows；标签原样保留，实际 normalization 为 available。再分别提供不存在的 anchor，以及真实 `Reference` token 的 anchor 但仍绑定完整 `Reference data`，两者都被 context 和 materialize 拒绝。没有为绕过失败截短标签或修改轴／路径。

**G3-2 已关闭。** 新逻辑只统计已选择路径对真实 `pixel_id` 的引用。多个所选系列引用同一物理观测时，双方对应行可以定量；带 junction 歧义的路径，其未共同引用行继续不可计量。P2 留下的 shared provenance 单独不会解开歧义。没有扫描未选候选来添加新的资格条件，没有把所有共享分支整体改为可用，也没有改变全局物理像素去重。

本审查再次现场绘制首轮黑色双线原图，独立调用实际 detector、context、materialize 和 normalization；未替换候选或其 ambiguity 标志。自动生成的四条路径均带 `path_junction_ambiguous`。逐行检验实际图像支持、当前所选集合的重复引用、eligibility、唯一像素和 normalization 区间，结果如下：

| 同一原图的语义选择 | observed rows | unique physical pixels | eligible rows | normalization |
|---|---:|---:|---:|---|
| 选择四条实际候选 | 545 | 333 | 319 | 3 个系列有可用定量区间；纯非共享歧义分支仍 unavailable |
| 仅选择其中一条歧义路径 | 181 | 181 | 0 | `no_quantitative_eligible_rows`，无有效区间 |

第一行的 319 个共同引用观测逐行 eligible=1，其余 226 行 eligible=0；`global_duplicate_pixel_rows=212`，没有把 545 个引用算成 545 个独立样本。第二行即使保留 detector 的 shared provenance，仍不因未选路径而取得资格。还逐个核对 normalization 的有效区间：区间中的该系列行均 eligible，没有跨非共享歧义段拼出定量连续域。这些正反例经过新生产入口，原历史 helper 的通过不是本次关闭依据。

**G3-3 已关闭。** `bindings` 与 `rejected_candidates` 的同一输出 Schema 均声明 `uniqueItems`；按 candidate ID 唯一、同 ID 不同文字以及 selected/rejected 互斥，明确写入原有 `curve.figure.request.internal_consistency`，prompt 与 validator 一致。没有新增规则注册表或中央处理。

除 owning 回归，本审查用上述独立多词图建立五次隔离的实际 Root／Local Worker 文件流程，读取每次生成的 `result.schema.json` 后提交同一 envelope；结果如下：

| 提交情形 | 实际 assignment Schema | 实际 submit 与诊断 |
|---|---|---|
| 合法完整多词 binding | 接受 | completed |
| 完整重复 binding | 拒绝 | rejected，`runtime.schema` |
| 完整重复 rejection | 拒绝 | rejected，`runtime.schema` |
| 同 candidate ID、不同 semantic identity | 结构接受，关联规则明确可见 | rejected，`curve.figure.request.internal_consistency` |
| 同一 candidate 同时 selected/rejected | 结构接受，互斥规则明确可见 | rejected，`curve.figure.request.internal_consistency` |

关联约束的文字明确包含所有 candidate ID 至多一次、不同可见文字／语义／anchor／reason 也不能重复，以及两集合 disjoint；未把泛称“内部一致”当作精确规则公开。额外字段禁令保持。

### 回归、资源与未完成门

独立串行执行首轮列出的七文件聚焦命令，另加入 `tests/operations/test_figure_automatic_detection.py`，仍使用 `-p no:cacheprovider`。结果 **181 passed in 32.21s**，退出码 0；外层耗时 **32.69s**，采样进程树峰值 **158,016 KiB**。上述独立原始图和五次实际 Worker 探针随后串行执行，全部断言通过，退出码 0；外层耗时 **3.17s**，采样峰值 **97,708 KiB**。

两次均设置 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS='' PYTHONDONTWRITEBYTECODE=1`，没有 xdist 或并行测试。外层每 0.1 秒递归汇总被测进程树 RSS，达到 8 GiB 即终止，未触发。这是采样 RSS，不是 cgroup 强制内存上限或 live Codex／WSL 增量认证。

聚焦回归同时重验三种完整族形状、两种零表初稿／audit／一次修订、零表 normalization 双重拒绝、混族和附件丢失拒绝、source／receipt／plot／path／anchor 绑定、反向轴、log 轴、局部空白和重放。实际 compiled catalog 仍为 48 条，figure 仍为 5 条；资源摘要边测试继续通过。只读 diff 确认 P2 detector/source、`src/`、其他插件、figure plugin 注册和 deploy 相对基线均无改动，没有中央或候选算法扩展。`git diff --check` 通过。

OCR adapter 在本次独立图与相关合成回归中使用结构化 token 替换；当前缺席的 tesseract、awaiting_P4 的真实版本／模型 hash 门没有被称为通过。没有重跑完整目录、安装矩阵、真实论文／spawn 或部署；这些并非三项局部返工所需。九项既有基线失败仍按首轮记录处理，本次没有重跑或归责 P3，完整目录不能称全绿。

P4 的干净发行、真实服务依赖／PATH／模型和安装负测、实际读取隔离探针，以及 P5 的两张真实图／真实 Agent／独立精度与覆盖门保持未完成。此次 PASS 只关闭 P3 工程合同门，不授予科学资格或 E5.4 最终验收。本次只追加本审查文件，首轮 FAIL 未删除；未修改实现、测试、计划或 evidence，未提交，未部署。
