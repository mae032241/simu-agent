# R5 E5.3 图曲线提取机制 GPT-6 独立实现审查

日期：2026-09-05。结论：**FAIL：blocker 0，high 1，medium 1，low 0。**

## 发现

### High H1：路径身份歧义被降为纯文本，任意择一的轨迹仍全部获得机械定量资格

位置：[figure_digitization.py:494](../../../plugins/curve_score/curve_score/figure_digitization.py#L494)、同文件 524—552 行；资格赋值在同文件 315—323 行。相关生产链为 `figure_line_tracker.py:280` 的候选平局计数和 404—411 行的 `ambiguous_path` finding。

本轮把 `series_unresolved` 限定为 legend binding 是否 matched，并只把 `binding_pixels_missing` 留在 manifest ambiguities。这个删除范围包括 `ambiguous_path`，不只包括坏 seed、点数、覆盖率和 gap。图例颜色匹配不能证明同色的两个候选轨迹中哪一条属于目标；tracker 当前按成本和 y 坐标机械择一，并未解决这项身份不确定性。

独立负例：12×12 的白底图，x=1…9 每列各有 y=3 和 y=7 两个红色真实像素，seed 位于 y=5；`seed_radius_px=2`、`guide_weight=1`、`max_guide_distance_px=3`，其余使用现有合成请求夹具。两条平行轨迹等成本，tracker 报告 `candidate tie fraction 1.0000 exceeds 0.1000`。结果却是：

- manifest `status=qualified`、`ambiguities=[]`；
- 9 个择一得到的 y=3 直接点全部 `quantitative_measurement_claim_eligible=1`；
- 规范化得到 `availability=available`、连续有效区间 `[0,8]`。

这不只发生在私有函数：独立探针通过现有测试插件的确定性 compiler 产生请求，再调用真实 Root `operation_preflight` / `operation_invoke` 的 `science.figure.evidence.materialize.v1`。预检为 admissible，正式登记的 manifest 与 CSV 仍具有上述结果。测试插件只提供合成几何；物化器、校验器和发布路径是候选生产实现。未伪造真实科学审查或批准；规范化数值结果另外通过生产 adapter 验证。

影响：存在真实来源像素，但归属未定的局部路径被表示成已具备定量资格的目标曲线。独立审查者可能纠正它，但这一额外人工补救不能证明机械字段正确。当前真实 Fig.4 资源的报告未出现此 finding，因此本负例不等于真实 Fig.4 已识别错线，也不是对真实共享区的主张。

最小修复：沿现有 tracker → TracePoint/CSV → manifest/report → normalize/overlay 路径保留实际候选身份未定的局部列信息。保留观测，仅令这些列的定量资格为 0，切分有效区间并显示局部原因；其余直接点继续可用。不要恢复由整个 `findings` 列表清零全系列，不要把纯粹点数/gap/坏 seed 诊断重新升级为全局资格门，也不要新增资格注册表或状态机。

必须补的非同义验收：一幅具有明确前后段、仅中间若干列同色等成本分叉的图，经真实 Root 物化后，中间列保留观测但局部不可定量，前后段保留资格，跨分叉域不被当作连续可用；另以候选距离/导向能够唯一选定的近似双线作正控，不能将所有多候选列一律清零。原坏 seed、局部 gap、少点、共享成员诊断不连坐的正控应继续通过。

### Medium M1：公共意图的结构约束未进入实际 Worker JSON Schema

位置：[figure_digitization_contract.py:46](../../../plugins/curve_score/curve_score/figure_digitization_contract.py#L46)，尤其 49—54 行；[figure_science_operations.py:139](../../../plugins/curve_score/curve_score/figure_science_operations.py#L139) 的提交校验消费该模型。

`series_labels` 的唯一性，以及 `series_labels` / `unresolved_reasons` 恰有一方非空，只在 Python `model_validator` 中实现。独立读取实际 `operation_port_json_schema`：两个数组只有 `maxItems`，没有 `uniqueItems` 或表达非空互斥的条件。语义合同的通用“不可由 JSON Schema 表达的跨字段关系”描述没有列出这些规则，而这些规则完全可以由 JSON Schema 表达。

独立验证中，重复标签、两数组均空、两数组均非空均通过当前 JSON Schema，随后均被模型拒绝。重复标签还通过真实 Root 创建、LocalWorker 打开及提交路径复现：`worker_submit_result` 返回 `rejected`，诊断为 `curve.figure.request.internal_consistency`，Run 保持 running。这里没有发生崩溃或结果错误封存；问题是对 Worker 可见的结构合同与实际提交规则不一致。

最小修复：让同一个公共模型生成 `uniqueItems` 及二选一非空条件，保留 Pydantic 同源防御；不新增独立规则表。用实际生成 Schema 和正式 submit 同时验证三项负例，合法选定及合法未决两项正例均通过。涉及 `ROLE-002`、`AUTH-003` 和宪章的“结构规则由同一 JSON Schema 表达”要求。

## 审查范围与方法

唯一仓库为 `123/scidiscovery-e5.2`；基线为 HEAD `48632238fa85b49df9df2713da51ab306c262531` 上的未提交候选。已读仓库 AGENTS.md、当前中文架构、设计宪章、33 项约束、活动账本 E5.3，以及 E5 完整族、请求物化、修订拓扑、E5.1 共享和 E5.2 集成相关历史审查。历史结论只用来理解原承重条件，不继承为本轮通过。

使用跨边界和奥卡姆审查口径，检查所指定的 curve_score 八个生产文件、ingaas_fig4 注册/编译/资源/包声明、对应 operations 测试及活动账本。必要时只读追踪 Root admission、编译资源摘要、曲线域判断与 tracker 的既有实现。未修改生产代码、测试、部署脚本或论文；本审查文件是唯一仓库写入。`deploy/install.sh` 等此前变更不纳入本结论。

## 其余边界核对

| 边界 | 独立结论及限制 |
| --- | --- |
| 公共 Agent 输出 | 实际编译 Schema 只有来源摘要、figure、panel、series_labels、unresolved_reasons 和版本；`additionalProperties=false`。提示禁止像素、种子、范围、阈值、CSV。旧数值请求不再是该公共 Agent 的可提交结果。M1 是这个新合同内部的剩余问题。 |
| 确定性 compiler 所有权 | 新 support Operation 由原 `ingaas_fig4.plugin:PLUGIN` 的同一 entry point 注册，依赖方向为项目插件到曲线能力；没有核心 Fig.4 分支或第二注册面。`figure_geometry` 作为 transform 的显式 resource 参与编译摘要，`package-data` 包含 JSON；已独立跑安装 entry-point 烟测。当前能力只支持该冻结来源的两条实测线，不能称为任意论文自动识图。 |
| 来源/选择失败关闭 | compiler 先检查冻结 PDF 哈希、意图哈希、figure/panel、可见标签，再检查恢复对象及图像哈希；不支持的来源或选择不产出请求。源码负例和真实 PDF 测试通过。该内容检查发生在 transform 执行，不把通用预检的 admissible 夸大为已完成源图恢复或测量。 |
| 父链与图族 | 真实 PDF 的语义 Agent 受控提交→support→materialize 集成测试通过：source→intent，source+intent→request，source+request→全部附件。既有完整族声明仍用于 Intake/Audit；合成 Root 闭环覆盖缺成员、混族、错 source/request、旧审查、精确重审和规范化。真实 PDF 前半链与合成审查后半链是两项证据，尚无真实模型全链科学通过。 |
| producer id 放宽 | `figure_parentage` 保留来源父链、输出端口、非空调用指纹；Root 仍回查生产 Operation/version/digest/output port，未知或退役合同拒绝。当前安装目录中没有另一公共 Agent 生产旧数值请求；普通文件摄入固定为 opaque，不能借数值 JSON 文件获得请求 Schema。未来通过唯一 catalog 注册的兼容确定性生产者是合法组合；直接调用可信 Artifact 存储接口伪造标签不属于公共 Worker 权限。未发现本轮新增的可达任意伪生产者旁路，也不建议恢复名称名单。 |
| 局部缺点/少点/域 | 坏 seed、gap、点数诊断不再抹除其他观测，valid intervals 按真实相邻可用点生成。单点和全孤立点仍保留观测，但无连续区间时为 `no_continuous_quantitative_interval`，不会冒充覆盖任意下游曲线域。H1 是尚未正确区分的身份歧义例外。 |
| shared provenance | coincident 的 schema 至少两个不同成员；逐列只使用真实源像素，空列不补点，共享列校验完整成员、相同坐标、单一直接供体、正确源系列与原始像素颜色。丢单个共享成员的防线仍在；普通 overdraw 复制行仍不可独立定量，复制行必须有真实供体行。CSV 和 normalization audit 保留 group/source。没有要求某成员必须在整个共享区内独立显色，也没有把供体缺一列扩大成整包失败。 |
| 检测限 | 源绑定资源记录约 `3e15 cm^-3` 和灰色虚线说明；物化器按校准后逐行 y 值处理。Agent 无像素检测限区间输出入口。新真实路径保留黑线 565 个观测中 495 个局部可用点、红线 805 个中 801 个；这些是机械统计，不是科学批准。历史手调夹具仍有独立旧几何回归，不能用其 565 个全可用黑点代替新 compiler 的检测限结果。 |
| 真实 overlay | 已只读查看本轮 `/tmp/e53-figure-final-2v40rsf7/audit_overlays-0.png` 并核对旁边 manifest。上下分别显示黑/红目标系列，保留原图、图例与轴标签，蓝青/品红轨迹及灰色缺失、红色局部限制条可区分；纵轴顶部 `10^20`、底部 `10^15`。源图尾段噪声、同色标注和测量精度仍需独立科学审查。该真实资源 `shared_support=[]`；金色共享标志仅由合成正负控验证，不能称为真实共享证据。 |
| 奥卡姆/33 项约束 | 没有新增通用注册表、数据库事实、任务生命周期、资格层或核心领域分支；一个源绑定几何资源和一个 support compiler 有具体消费者。H1 影响 EVD-001/UNC-001/DET-001 的身份忠实性，M1 影响 ROLE-002/AUTH-003。其余相关检查不升级全部 33 项状态；SEC-002 仍为可信本地软隔离，UI/真实发布状态不在本轮关闭。 |

## 独立执行证据

所有 pytest 命令串行，设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`，无 xdist，`ulimit -v 8388608`。

- `test_figure_semantic_compilation.py`、`test_figure_local_observations.py`、`test_curve_figure_digitization_tool.py`、`test_m5_figure_review_closure.py`：**45 passed，15.91 s**。显式设置 `SCID_FIG4_FROZEN_SOURCE` 为授权的原论文路径，0 skip；不复制论文。
- `test_ingaas_operation_plugin.py`、`test_m2_optional_figure_plugin.py`、`test_m4_scientific_semantic_bridge_removal.py`、`test_m5_plugin_ownership_and_default_surface.py`：**17 passed**。
- `test_installed_semantic_figure_compiler_includes_frozen_geometry`：**1 passed，40.36 s**。实际构建/安装 wheel，在源码之外使用 installed catalog；夹具共享宿主第三方依赖，不称为全依赖隔离或已部署。
- 独立 H1 的两层负例、M1 的实际生成 Schema/正式 Worker submit 负例，以及全孤立点反证均已执行。它们使用临时测试状态，不触碰生产 ResearchInstance，也不代表真实 Agent 科学输出。
- 所审目录的 `git diff --check` 通过。未跑全量 suite。

当前源码及安装集成的正向证据成立，但 H1/M1 尚未关闭，不能把测试全绿称为机制通过。修复后应复审这两个精确边界；随后仍需部署、新合同下真实 Agent 首次语义选择、真实图证独立审查。**本报告不放行 E6。**

## 修复后复审

日期：2026-09-06。结论：**PASS；本次定向复审剩余 blocker 0、high 0、medium 0。** 上文 FAIL 是修复前的历史判断，保留不改写；本节仅关闭 H1/M1 及其必要回归，不代表部署、真实 Agent 首轮或 E6 已通过。

复审对象仍为同一 HEAD 上的共享未提交工作树。已读取当前相关 diff 和活动账本 E5.3 的 H1/M1 修正记录；新增生产变化集中在 `figure_line_tracker.py`、`figure_digitization.py`、`figure_digitization_contract.py`。未修改生产代码、测试、几何或论文，只追加本节。

### H1 已关闭：实际 tie 列保留观测，局部限制沿既有链传播

`figure_line_tracker.py:174` 将原计数改为列集合；281—283 行继续使用原候选成本差和原 `ambiguity_margin_px` 判断，将列加入集合；309 行只在最终保留的相应 TracePoint 上设置 `identity_ambiguous`。没有把一般多候选、坏 seed、gap、少点或整条 finding 列表改为新的全局否决条件。

`figure_digitization.py:320` 将此标记加入逐点定量资格判断，329—330 行输出 `ambiguous_path` 原因，417 行使同一列在 overlay 中显示局部限制。观测和原像素坐标保留；规范化复用原有效区间逻辑，不另造资格层。200—205 行对 coincident 点保留供体及本成员已有直接点的局部歧义，普通 overdraw 的 `replace` 同样保留标记；不会把该列的标记扩散至其它列。

独立复跑的真实 Root 生产入口证明：

- 同色平行轨迹、居中导向：9 个真实观测均保存，9 个 tie 列均不具定量资格，规范化不可用，无虚构连续区间。
- 仅 x=4、5、6 分叉：只排除这三列，其余六点保持可用，产生两段有效区间；跨分叉域返回 `continuous_domain_unavailable`。
- 相同多候选图、唯一导向：全部九点可用，保持一段有效区间；没有把“多个候选”本身作为排除条件。
- 原坏 seed/gap/点数门槛、共享成员统计诊断、共享空列与单点保留回归继续通过；每项 overlay 的红色覆盖列与 CSV 局部排除列一致。

真实 PDF 已独立重新执行原领域 compiler、物化器及规范化器，并只读检查 `/tmp/e53-h1-m1-review-uueojofp/audit_overlays-0.png`。独立生成的 overlay 与该图逐字一致，SHA-256 为 `27ba43648bebde4aff3386a0b2cbae49758f413409699dcc60cbc217b009e334`。两条系列仍保留 **565 / 805** 个直接观测，可用点 **493 / 800**，有效区间 **36 / 5**，均为 available。

为核对新增排除确实来自实际计算，复审时只在原 tracker 的 tie 判断处记录中间数值，没有改阈值或几何。黑线 x=459、538 的前两候选成本差分别约 0.1443、0.0936，红线 x=633 约 0.2131，均小于原 0.25 判据；这些最终保留的源像素存在，CSV 原因是 `ambiguous_path`，对应 overlay 覆盖条像素均为 `(255,64,0)`。tracker 另在黑线 x=722 见过候选 tie，但该列没有进入最终选中轨迹，修复没有因此制造观测。这里确认的是局部保守排除与实际算法、源像素一致，不将几何提取精度或真实科学资格一并判为通过。

### M1 已关闭：实际 Schema 与正式提交同源

`FigureExtractionIntent` 同一模型的 42—53 行生成 `oneOf`，要求恰有一方非空；60 行生成标签数组的 `uniqueItems=true`。原 Pydantic 模型校验只保留为防御，没有新增独立规则表。继承的 `additionalProperties=false` 保持有效。

五项正式 Worker 用例同时检查 `operation_port_json_schema`、Run 落盘 `schema/result.schema.json` 及 `worker_submit_result`：重复标签、两方皆空、两方皆非空均由 Schema 拒绝并在正式提交 rejected；合法选定和合法未决均由 Schema 接受且正式提交 completed。复审另外执行省略两个数组、省略其中一方、只给空数组、重复标签及附带像素区间的真值表，JSON Schema 与 Pydantic 结果一致。

公共输出仍只有六个原语义字段；实际生成 Schema 拒绝额外机械字段，提示仍将坐标、范围、种子、点数、跟踪阈值、CSV 和 overlay 交给确定性 compiler/materializer，没有要求 Agent 排序或填写这些字段。

### 本次验证与放行边界

独立串行执行 `test_figure_local_observations.py`、`test_figure_semantic_compilation.py`、`test_curve_figure_digitization_tool.py`、`test_m5_figure_review_closure.py`：**53 passed，0 skipped，17.78 s**。使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`、显式原论文路径、无 xdist 和 `ulimit -v 8388608`；真实 PDF 重放与补充探针也保持 8 GiB 上限。所审目录 `git diff --check` 通过。未重跑全量 suite，未重新执行安装烟测或部署；上文修复前安装证据只证明已有打包入口，不能替代本代真实部署验证。

H1/M1 最小修复和必要回归符合要求，本次定向实现复审 **PASS**。仍需按既有边界完成部署、新合同下真实 Agent 首次语义选择和独立真实图证审查；**E6 继续关闭**。
