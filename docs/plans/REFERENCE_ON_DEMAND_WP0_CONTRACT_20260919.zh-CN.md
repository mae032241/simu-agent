# 按需取证 WP0 实施合同

状态：WP0原合同已通过[独立审查](reviews/REFERENCE_ON_DEMAND_WP0_REVIEW_20260919.zh-CN.md)；实现期间的字段澄清及原件文件交付已纳入[WP2实现复审](reviews/REFERENCE_ON_DEMAND_WP2_IMPLEMENTATION_REVIEW_20260919.zh-CN.md)，最终通过。历史审查中的摘要仅标识当时候选，不代表本文件后续字节。唯一上位方案：[R4](REFERENCE_ON_DEMAND_REMEDIATION_PLAN_20260919.zh-CN.md)。部署及原生对照验收另计。

## 1. 一项编译能力

该工具使用自身访问收据，`record_attempts=False`；不伪造计算attempt，不占既有64个计算attempt证明槽，128次访问限额独立计量但同属控制账本。增加 builtin 的 `worker_reference_read` 工具，经已有scid_call路由调用，不增加模型可见MCP入口。WorkerToolDefinition增加可序列化、不可变的引用策略，进入组件digest；未声明策略的工具/Operation无此权限。科学Agent共享声明帮助函数显式加入该工具及控制生成manifest输出；新增manifest时单独增加1文件/1MiB控制输出额度，主科学成果端口原字节上限不变；非Agent、Transform、执行/审批不默认启用。已有tool_evidence权限不自动授予此能力。

请求：`source`为冻结输入别名或当前Run已提交访问别名，`action`为`list|read`，`reference`为list返回的精确引用句柄（read必需），可选`pointer`为JSON Pointer、`offset`为字符偏移、`limit`为512..8192响应字节预算、`cursor`为目录偏移。`delivery`默认`fragment`，文本/JSON分页；`file`为准确完整原件的只读文件入口，仅允许read且不允许pointer或非零offset。非文本同样使用文件入口；文件交付要求native workspace后端，其他后端明确拒绝，不生成虚假的文件提供事实。不得暴露任意Artifact ID读取。不允许Worker传预算作用域或producer ID。

响应总JSON编码计量，不只fragment：返回简短来源别名、选取范围、片段或文件入口、next/omitted及精确错误。目录最多8项/页、响应上限8192B。初始assignment仅说明工具入口，不读所有报告/目录。首次选根时list才解析该根直接引用。

策略首版界限：单原件32MiB、每恢复链累计唯一原件256MiB、128次调用、累计响应2MiB、工具IO120秒（单调用预留最多10秒，同步文件IO超时在边界检测，不声称硬中断；累计实际IO另限256MiB）、最多32份提供事实（与生产产物配额分开）、最多16跳引用链。达到上限给准确缺口；不扩端口、不提高Run输入限额。数值属于显式编译策略并可由声明调整，收据恢复按当前合同验证；不得静默提高。内部读根报告/manifest也受单件、调用IO和时间约束，不能无界解析来源历史。

## 2. 声明式引用提取与生产配对

工具策略声明 `(schema_id, JSON路径, 值/字典键模式)`，只从受支持schema的结构化字段提取别名，不递归搜任意字符串。通用科学组件提供LayeredDiagnosis的source_references/input_alias、evidence/source_key或locator及各evidence_keys的现有引用语义，以及选中calculation_records项的input_digests键规则（内部证据键先映射source_references或evidence；locator只按既有声明的别名前缀语义精确解析，不自由文本猜测；真实新calculation_ref保存在evidence.locator，不存在calculation_refs字段）；计算记录产物可由原manifest中的analysis_artifact_kind=calculation_record及原记录授权提取其input_digests。受控算法/数据发布的metadata.derived_from仅在该原产物记录被精确选中时构成显式引用边，不把整个manifest inventory授权。

别名必须在原生产manifest.bindings或生产记录中准确解析。正式报告从completed_for_output确定原Run，再查其正式output父manifest；工具产物必须在该已完成Run原manifest.records中精确出现。核验manifest生产关联、Ref/hash及原Run实例。标签仅是定位提示。未封存、歧义、不配对或跨实例不给读取权限。只有目录项但未被声明引用的条目是导航，不授权。没有manifest/自由文本无准确绑定则返回可定位缺口，维持Root显式输入退路。

引用句柄由控制层根据源Ref、locator和准确目标Ref生成并在请求时重解析比对；不作为Bearer授权。每次保存原根Ref和逐跳(sourceRef, locator, targetRef)，不遍历其他父链。文件物化路径仅在该Run内可用，不共享跨Run路径。缓存可暂不新增；原件CAS已有去重，先避免缓存引入额外权威。

## 3. 同一存储，生产和访问分开

复用run_tool_evidence，新增记录判别`record_type=reference_access`；旧无判别记录仍是生产证据。增加访问记录查询；现有tool_evidence默认只返回生产记录，使生产发布/evidence_output_refs/completed_for_output保持原语义。新manifest在同一结构增加可选`accesses`集合；旧records/bindings/attempts不重写。访问Ref仍是原Artifact，绝不accept_tool_evidence重注册。

访问记录字段：alias、artifact_ref、media_type、size_bytes、record_type、access_run_id、原producer_run_id、root_ref、chain、operation/tool策略digest、selector、提供范围、request_key、response（有界可重取）、budget_scope。alias由控制层生成，映射作用于当前Run；不要求Agent登记sources或hash。响应持久化不意味着默认向Root展开。

唯一键继续使用(run_id,evidence_key)，evidence_key为`reference:`前缀+规范请求hash；hash包含访问Run、能力合同、根/精确引用链、action、选择器和响应预算。材料去重按完整ArtifactRef，不能拿该请求hash代替。不同范围为不同事实。所有序号分配统计原表全部记录，不能用过滤后的生产记录数量分配。

source_descriptor/evidence_sources/validation_source_ports增加访问记录消费，port标签为`reference_access`；operation_contract投影及run_outputs.context_validator来源筛选共同使用一个由编译能力导出的合法工具来源集合；不要求把reference_access伪填进context_sources输入端口，不放宽catalog对普通输入的检查，不把它伪装为必需输入端口。内部可加载准确全文供机械校验，locator保留在收据，不给模型全文已读资格。manifest.bindings保存访问别名便于下一轮明确引用；新manifest的parent_refs包含inputs、生产records及accesses准确Ref并去重，以满足既有绑定来源检查，旧manifest/原件父链不修改。accesses不发布为本Run生产成果。生产记录配额与读取配额分别计算，防止读取占满作者产物槽。

恢复：adopt_tool_evidence保留生产分支，独立访问分支核对新冻结根、每跳引用及当前策略；原访问者与原生产者不混同。合法记录重建当前Run别名/请求作用域，保留原精确Ref与链；失权/根丢失只留历史，不进入有效来源。manifest历史读取不依赖当前operation digest，但旧运行合同漂移继续拒绝执行。

## 4. 原子提交和预算

复用run_activity预算事件，增加reference_read_reserved/settled；不新建预算服务。budget_scope沿控制库冻结draft_from/resume_from链找到根，核对实例，限既有恢复链范围；独立Run各自计量。作用域不可由客户端指定。事务内收集该作用域事件计算用量；WP0实现可用同库索引加速，不建另一个权威账本。

步骤：
1. 事务内复查running且accepted_candidate_digest为空，定位作用域，检查调用数/剩余IO，预留该请求的有界IO和响应额度，记录唯一请求预留ID；崩溃保留未决用量。
2. 事务外做原件读取、引用解析、范围提取/文件物化。唯一材料成本在读取目标前按Ref和envelope.size_bytes事务内预留；同scope相同Ref一次预留，持有者关联请求，取消一个不释放另一个额度。对根/manifest内部读取的实际IO同样计量。
3. 短事务内再次复查生命周期，检查请求是否已提交；授权链源为冻结根/已提交收据不可变事实。原子写入访问记录与预算结算。同请求并发只留一份事实，但每个真实调用/IO保留实际消耗。取消/封存先赢则不追加来源，只结算真实成本/诊断。不得持锁跨IO。
4. 返回已提交响应；传输未知不改变有效来源。相同请求取回原封存响应，计真实新调用及输出成本，不重收材料成本。新请求不能靠更换幂等键扩大权限。

计时以服务端monotonic；实际IO/生成响应字节是可观测口径，无客户端已读确认。未决预留在重启后保守计费，只有可证明未消耗部分释放。预算超限、取消、崩溃产生精确诊断，不伪成功，不自动重试。

## 5. 接入和验收责任

- 注册与编译：builtin_plugin、tooling、catalog digest、科学Agent声明/manifest输出；local与hardened OperationToolContext路由同一RunService方法，不能只支持一种后端。
- 存储与来源：新reference_access服务模块作为ToolEvidenceMixin组合能力，最小修改tool_evidence、runs发布和schema投影；原对象发布过滤、ordinal/恢复消费者全部检查。
- 交接：run_assignment仅加短入口；公共提示要求按问题选引用、不批量打印；总体目标原入口不变。Root不搬详细收据。
- 定向验证：旧manifest/生产发布兼容、真实MCP受限接口、准确配对/错误hash/未封存/跨实例、局部成功不等于全文阅读、发布后响应丢失、恢复失根/权限、同scope和独立scope并发、同请求竞争/不同范围、取消/封存竞争。测试用小文件和屏障，不启动并行模型。
- 最后验证安装包接口及非TCAD报告→引用→输出来源链。原生A/B固定sol+medium等同条件，至少两组、分Root/Worker计窗口增量和峰值；未部署时只报告源码/本地结果，不编造原生收益。WP1/2/3分别审查，之后WP4兼容验收。测试串行768MiB守卫。
