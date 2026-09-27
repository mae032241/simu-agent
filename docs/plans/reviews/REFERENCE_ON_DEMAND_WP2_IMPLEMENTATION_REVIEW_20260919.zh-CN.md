# WP2 按需引用独立实现审查

最终结论：**PASS（本轮WP2实现审查）**。初审三项及显式输入转引的最后入口均已关闭；delivery=file沿同一受控读取边界提供准确原件，未发现新增阻断。初审及中间复核意见保留，最终候选与证据见末节。PASS不等于安装验收、原生token收益、部署或科研恢复通过。

本审查只读检查，未运行测试、未改源码、未调用科研MCP或恢复Fig4。已读服务主链、来源与历史计算消费者、冻结/封存接入及已有测试内容；Harness测试不能替代真实Run/manifest/输出提交闭环，未在此宣称测试已通过。

## 阻断1：跨轮只读计算把授权manifest误当生产证明manifest

位置：`reference_access.py::reference_calculation_sources`，当前第555行起。

可达链为：Run A生产计算C；Run B按需读取C并在自己的报告中引用；B.manifest正确地把C放在accesses而非records；Run D绑定B报告并读取C。D记录的authorizing_manifest_ref是B的manifest，它证明B→C引用边合法，却不是C的生产证明。当前resolver直接在该manifest.records中查C，找不到便返回None，随后calculation_sources拒绝“没有授权原manifest”。即使C的真正producer A已completed仍会失败。

原producer失败、后来由恢复Run封存的计算更需区分这两个关系；不能靠把access记录移进records解决。`_reference_pair`的无completed producer回退也会把引用授权manifest当作工具产物生产manifest，遇到accesses转引时同样无法深入。

**最小修复：** 分开精确引用边授权与原计算/工具产物的证明定位。原producer有正式封存记录时，按其精确manifest配对；原producer失败的恢复产物，沿已封存且有界的恢复/访问证明定位唯一正式配对manifest和attempt origin。继续验证当前根引用边，不让原生产身份替代本次读取授权。不得扫描latest、伪造新producer或把accesses发布为产物。

反例：A生产C→B只读引用C并封存→D只读引用C并提交成功；另加原A失败后由恢复Run封存的同构场景。C的Ref/producer、B/D的冻结inputs均不改变。

## 阻断2：恢复通过新读取重放旧事实，预算不足时静默丢来源

位置：`reference_access.py::adopt_reference_access`，当前第495行起。

当前对每份旧access记录沿chain调用reference_read，逐跳生成新的读取请求；中间节点使用512字节选择器，消耗新的调用/响应/IO额度并可能新建提供事实。预算耗尽、单页不能容纳等失败被 `valid=False; continue`静默处理，Run继续打开，却没有应继承的旧成功来源。根和权限没有变化的合法收据也因此像失权记录一样消失；深链和多页重复记录还会重复回放相同前缀。

这不是“恢复预算不能重置”的必要结果：已提交事实仍然存在，控制恢复验证不应伪装成Worker发起的新提供动作或悄悄丢弃。

**最小修复：** 将旧成功收据的有界身份/根路径验证和别名重建与新Worker读取分开。复用既有成功事实及其原选择范围，不用512字节临时提供替代原链；实际验证IO按声明成本记录，已用额度不清空。若预算或证明问题确实使安全恢复无法完成，返回明确恢复诊断并拒绝假成功打开，不得静默当作“失根/失权”跳过。失根/失权的旧来源才按合同仅留历史。共享前缀可在本次恢复内复用验证事实，无需新全局缓存。

反例：旧Run预算恰已耗尽但存在合法成功收据；恢复不得无提示成功打开空来源集。另验证多页/多跳收据不凭空增加提供范围，真正移除根时才排除来源。

## 阻断3：动态访问别名与既有精确来源重复，使旧解析器拒绝合法输入

位置：`reference_access.py:409` 的root+target别名生成，与 `operations/input_validation.py:192` 的prior_analysis_sources组合。

同Ref不同页已复用别名，但同一目标Ref若原先是冻结补充输入，引用读仍新增reference别名；两个根报告指向同一Ref也生成不同访问别名。旧prior_analysis_sources按Ref查当前descriptors，匹配数大于1即 `input_artifact_duplicate`。带prior_analysis/manifest的正常分析接续，调用calculation_reference_aliases等路径时，会在合法引用后被机械拒绝。当前只测单根/同范围不能证明该边界。

**最小修复：** 在已有映射消费者中保持明确作用域，或优先复用已绑定精确来源的可见别名，同时保留各访问链的授权事实。不能任取第一个alias、把不同Ref按hash合并，也不能删除所有歧义检查。来源身份唯一和访问路径可能多条必须分别处理。

反例：同Ref已是补充输入又被报告引用；两根共享同Ref；各自通过prior_analysis映射及输出校验，错误Ref/错误作用域仍拒绝。

## 审查中已修正的两处边界

- `_open`已改回按原有tool.evidence_ports或record_attempts决定“无queued Run时隐式重开”，reference-only新增manifest不再扩大重开权限。显式bound Run和显式queued恢复路径保留；这是适当的窄兼容修复。
- 最初选中恢复计算时，导航只使用外层当前manifest.bindings，会误解改名后的旧input_digests。当前候选已增加 `_calculation_origin` 并由导航与机械resolver共用attempt/request/digest匹配的原作用域。该项源码方向已修正，但仍需真实改名/alias碰撞fixture验证；它并未自动解决阻断1的“访问转引manifest不是生产manifest”。

## 已核查的成立边界

1. `reference_policy`在编译工具中显式声明、进入digest，类型/正数与每Operation唯一性有检查，公开inputSchema投影限额。reference_access合法来源类由同一编译集合供Schema和context读取使用；没有新增必需输入端口或主产物容量扩张。
2. 访问记录与生产记录共用存储但有类型过滤；manifest.parents纳入精确访问Ref，访问对象不进入当前Run生产发布集合。原Artifact字节及producer不改写，旧无类型记录保留生产语义。
3. 独立Run与恢复链预算作用域分别确定；短事务预留调用、响应、时间、唯一原Ref及实际读取字节，同请求竞争有唯一键，真实并发调用各记成本。取消/候选接受后的提交拒绝有效来源，成本留存。`_accept_candidate`在接受事务中比对封存manifest快照，避免晚到来源悄悄改变已验候选。未见全实例长锁包围外部文件读取。
4. 文本片段按UTF-8编码后的完整JSON预算裁剪，locator/范围保留，不以片段代全文已读；图像/二进制仅native_workspace后端开放文件入口，其他后端明确unavailable。CAS原Ref及响应先提交，文件物化失败后可重取修复，不需要额外暂存产物权威。
5. 历史计算机械校验在原命名空间构造ValidationSources，不改Worker冻结inputs；采用共享validation deadline和本次验证聚合字节预算。该路径只作收据/字节真实性检查，不应扩展成科学充分性或全文阅读门。

## 有界验证要求与候选身份

关闭三项后，重点跑真实报告→访问→封存→下一轮读取/引用闭环及恢复负例；并发Harness可继续用于同请求双提交、取消/封存抢先、独立/同scope预算，但不能单凭其替代完成态生产者与manifest查询。无需扩大全量测试、启动多个模型或恢复科研仿真。当前未确认安装入口、原生token收益或全部历史格式。

| 本轮读取文件 | SHA-256 |
|---|---|
| service/reference_access.py | `424f1c9036b0ec4f3c5ac9482eae02d7ab3a4af684b3f07f067bb5b444c926cc` |
| service/tool_evidence.py | `60eda5678c9f4a64c457c893f5307249d710683466f13bb8b461da33a5009b0e` |
| service/runs.py | `c67b056db62eb85df1f925ebe7f3d01a1a655e7e683a6da2e563311300d56043` |
| operations/input_validation.py | `6872dbc08fa3b578cc0cc2b0a23bfa5c750ca5149f452ff088c00058ead15626` |
| interfaces/mcp_local_worker.py | `8ffed4d8e1db6c2600f3622c8270b0d3b5e7b9a8cf18ddf138c1bf36adccc17e` |

服务仍在修改时后续候选须重新记录摘要并对修复做窄复核，不把本报告当作后来字节的结论。


## 三项修复窄复核

复核服务摘要：`reference_access.py`为`00cdbb92bc3e999da9795a24a6180383e98a2c4adba7294108ab354dfedfe936`；`tool_evidence.py`为`db2c8bb9d5ce3f0258903ea61b635b2befe18ba40a4ae92675c65a0c868de332`。未自行执行测试；服务执行者的最终测试结果尚待提供。

- **原阻断2关闭。** adoption不再调用reference_read重放，而按原根、相同提取policy、连续精确chain及原operation身份复用已提交控制事实；不新造512字节中间提供，不消耗伪Worker调用/返回额度。移除根、能力变化和后端不可用都有reference_access_not_adopted诊断，结构不一致拒绝恢复。同库短事务检查当前生命周期、作用域、记录数和manifest大小。新增耗尽调用额度后恢复旧成功来源fixture与该行为一致。
- **原阻断3关闭。** _reference_alias优先复用可见冻结输入alias，否则按精确target Ref复用当前alias；各根链仍分别记录。validation_source_ports和manifest.bindings采用setdefault保留原端口，未把既有受信/背景输入改标为新来源。跨根同Ref以及显式已绑同Ref均有新增fixture。handoff_only输入不能通过猜alias作为读取根。
- **原阻断1部分关闭。** authorizing与proof字段已分离，封存accesses继承proof而不变producer，真实A计算→B访问引用→D再次访问引用fixture已补；恢复计算的导航与校验复用_calculation_origin，原失败producer身份保留。尚有下面一个现成合法入口。

### 唯一剩余入口：显式输入中的计算缺少proof定位

_reference_edges现在只有“目标在当前manifest.records”或“目标在当前manifest.accesses且有继承proof”时设置original_proof。若报告B显式绑定A的计算C并引用，C只在B.bindings，`completed_for_output(C)`已经返回A，但代码没有取A正式封存manifest。下游D读取后proof为空，reference_calculation_sources退回B的authorizing manifest，在B.records找不到C，仍失败。

这不是新增支持范围：`tests/operations/test_analysis_artifact_references.py`中已有“prior_analysis + prior_analysis_manifest + 原计算Ref加入reference_material，再引用reference_material_002并成功封存”的真实回归。只需在其后接D读取B即可复现同一证明缺口。

**最小修订：** 对已确定唯一completed target producer的计算/工具产物，按其正式output的精确manifest且records准确含该Ref取得proof；当前引用边授权仍来自B，不以原producer代替本次授权。不建立latest查找，不把B.bindings当B生产记录。新增上述现成链后的一个定向断言即可。

### 身份映射的职责判断

analysis_evidence_aliases在此仅将source_key/input_alias/locator映射到原生产绑定，拒绝的是互相冲突的身份声明；没有验证结论是否被证据充分支持、是否读完全文或是否已证明物理机制。缺失/歧义可明确拒绝导航，不得猜最新；不需要另建科学充分性检查或扩展自由文本推断。当前不因此新增审查阻断。


## 最终有界复核：PASS

### 最后证明入口关闭

_reference_edges在当前records/accesses无法提供proof时，若target_producer是唯一已完成生产者且target为其工具产物，则调用既有_reference_pair核对该生产者正式manifest.records确切包含target，保存proof_run_id/proof_manifest_ref。引用授权仍保留当前报告的authorizing身份，没有把原producer当作本次授权，也没有将显式输入或accesses提升成生产records。

真实Worker回归现以explicit_input=False/True参数覆盖A计算C→B访问引用/显式绑定C→D读取并封存；另保留失败原producer→恢复封存且旧alias改变→准确原CSV导航及提交路径。已核查这些断言不修改原Ref/producer、不暗增Worker冻结inputs。本轮最后阻断关闭。

### delivery=file的边界

- 请求仅新增同工具的交付选项，默认fragment。file必须read、禁pointer和非零offset；仍需从当前冻结根/合法访问来源解析精确引用句柄，不能传任意Artifact ID或路径。
- delivery进入规范请求身份与持久selector，文件与片段为不同提供事实，但唯一材料成本仍按准确Ref去重；重复文件请求重新计实际读取/调用/返回成本，不放宽单件、累计IO、记录或响应上限。
- 文件请求先按原Ref读取并校验hash/大小，再沿同一事务检查running/候选接受状态及预算，一致提交访问事实；提交前取消不物化文件。提交后安全物化失败仍可从CAS按原请求修复，未新增暂存产物或生产身份。
- 只在native_workspace后端提供文件入口；不支持的后端明确unavailable。文本CSV/脚本不再被迫分页打印，文件入口不宣称全文进入模型。用控制生成别名构造当前Run内路径，并复用非symlink目录句柄原子写入；同Ref并发文件交付写相同精确字节，不分享其他Run的路径/权限。
- 原响应/记录的恢复延续此前准确Ref及链，delivery保留；根、策略和后端限制继续适用，没有新增客户端确认或全文阅读门。

### 证据与适用限制

已阅读 `WP2_SERVICE.md` 的分批记录：最终reference_access与WP1定向集合 **32 passed**（27项reference及5项WP1），8.02秒，峰值126.83MiB；此前两个原生产证据恢复/候选接受门回归也通过。新增CSV file测试核对准确原字节、无fragment和file_access范围；参数拒绝覆盖file配pointer/offset。测试由实施者在父调度串行时隙执行，本审查没有重跑，未把结果扩大为模型行为/solver或安装验证。

已知三项各有针对性关闭证据，当前无须继续扩计划或增加身份、预算、交付状态机。analysis_evidence_aliases仍只处理身份映射冲突，不要求证据科学充分、阅读全文或证明模型记忆。旧记录、未知/歧义引用及不支持后端仍按既定缺口路径处理。

最终读取候选：

| 文件 | SHA-256 |
|---|---|
| service/reference_access.py | `0893c5e038028ea46ac113e17c157e5fa3a091e72ede7cef5a4e7cf7bd855ec4` |
| service/tool_evidence.py | `9e4834e46b232c6d703c78e2730f6ca80c1700543367e26b84a9eda039cfe9e5` |
| reference_tools.py | `993ccafe7fdff2fca46dfda0d5034ce5e2a7b8d3d9240947ddf7b544f0e96994` |
| tests/operations/test_reference_access.py | `5ee4bdbf6dfa14dd1962c8b416293db7b6bf7e38baaa87c0a4cd12dc71a5b968` |

Run/历史来源解析/Local router摘要与本报告初审表列候选一致。可进入既定安装与WP4验收；部署及Fig4恢复不在此审查授权范围内。


## WP4跨边界覆盖补充

本次有界代码审查与现有定向证据足以支持上述WP2实施PASS；不等于WP4全部验收完成。

- 通用入口由with_user_context调用with_reference_access，后者先检查executor.kind，仅agent获得显式编译能力；transform/effect不变。公开工具Schema、策略digest、Local/hardened路由及control manifest上限已纳入本轮核对，没有据此扩大原科学主产物上限或开放未声明native能力。reference-only操作不再因control manifest意外获得no-queued重开入口。
- 生产边界已有集中过滤：tool_evidence排除reference_access，evidence_output_refs及Run完成时发布清单复用该生产集合。访问进入manifest.accesses/parents和验证来源，不进入新producer集合。CLI/UI沿既有生产清单消费时不会因新增访问记录把旧Artifact展示成当前Run生产；本轮没有重新穷举所有UI展示路径，不能将此结论扩大为完整UI验收。
- 32项定向结果覆盖实际报告/计算/显式绑定跨Run闭环、原失败producer恢复、预算/幂等/取消与候选接受竞争、file交付及WP1边界。它们与静态审查共同覆盖本次最关键的新增控制边界；未发现需要为此补建状态机、科学充分性或全文阅读门的具体缺口。
- 父调度随后报告隔离wheel的3项验证全部通过，峰值188.14MiB；该结果来自独立安装验证者，本审查未重跑。父调度另说明审查后仅新增reference-only隐式/显式重开回归、生产代码未变，4文件兼容回归仍在串行执行；本报告不将尚未完成的兼容结果计为通过。不需重复本轮语义设计审查。
- 原生两组A/B尚未执行，**不能宣称token收益、模型按需阅读效果或生产验收完成**。native文件入口和有界初始索引提供减少上下文的机制，实际收益仍须既定A/B验收；本次未运行科研MCP、测试或Fig4恢复。

以上未完成项属于既定安装/原生验收范围，不重新打开已关闭的WP2实现阻断。
