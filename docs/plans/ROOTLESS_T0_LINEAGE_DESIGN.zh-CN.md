# T0：统一谱系的责任、接缝与冻结夹具

状态：[独立设计评审通过](evidence/ROOTLESS_T0_REVIEW_20261012.md)，允许按本冻结范围实施 T1；不代表产品能力已通过。基线 `dev/287b2e2`；本节点只读与文档，无生产修改、测试或模型请求。范围依据[主计划](ROOTLESS_LINEAGE_ADAPTIVE_SEARCH_PLAN.zh-CN.md)；N6/N6c 的额度、收口、续接与未知执行边界全部沿用。

## 1. 诊断决定与因果限制

- [92候选全池诊断](evidence/ROOTLESS_N5_LIVE02_POOL_EVALUATION_20261012.md)说明选择与评估盲区值得优先处理；N5 实际 run17 已是有记录审计池最佳。run19 的0.7248仅条件性预测 reward、缺 audit，不能据此承诺换选择算法会涨分。旧审计与保存 pickle 的完整性限制仍保留。
- [只读测量](evidence/ROOTLESS_T0_MEASUREMENT_20261012.zh-CN.md)：N5 六 W 共5,506,854 observed tokens、511,526非缓存输入+输出；science-task 5,831–10,904B，history 1,583–3,371B、search 2,646–3,834B。live02 两 W 共3,013,345/208,865，任务包仅1,267/1,284B，末次输入仍约76K。live02已存在观察后局部细化的call顺序证据；N5多固定CONFIGS但工程修复不冒充科学自适应。不能把上下文增长全归历史，也不能用实验数/token 唯一归因于预排搜索。
- 首版 T3 **原生 W 优先、禁用辅助者**；先统一原件读取与分支选择，不建第二调度层。平台独立上下文、名额释放与开销尚未资格，未来启用必须实际测量；未测项不是 PASS。
- T4 先定义公开输入下的未知/适用范围规则，与 T1/T2 并行设计。已窥见隐藏结果的两池仅作开发诊断，不进入模型视图、运行选择输入或阈值调参，也不作独立验证。

## 2. 单权威与四种对象

| 对象/事实 | 唯一原件 | 谱系可派生内容及禁止推断 |
| --- | --- | --- |
| 科学任务与成功输出 | frozen job、seal、`execution.raw/reference` 成功 attempt | 节点角色/直接输入/原科学摘要；不能将直接输入当候选父或支持证明 |
| 机制身份与状态 | H/A原科学输出+已验证 control_outcome，`search._apply`解释 | 原ref/修订/未处置承诺/W冻结focus；不能用观察节点H范围代替候选所属机制 |
| 候选与评估 | 封存 observer snapshot、确切实验 execution/产物回执 | candidate、evaluation_key+direction、coverage、来源；status=ok不等于审计合格，历史缺关系为unknown |
| 实现复用 | seal.selected_inputs、原materials及host解析 | 已声明的确切复用集合；可见/被挂载不证明实际读取，更不证明派生 |
| 预算/恢复/交付 | 原control-ledger、attempt链、delivery动作原件 | 只引用已有成本/确认；不建余额、current-attempt或actual-submission第二权威 |

候选名是供科学选择的简短、唯一显示名称；宿主解析为确切冻结对象。作者不填写 hash、路径、祖先引用数组或关系账本。节点步数、accepted continuation、候选尝试、A有效决策周期保持不同计数单位。

## 3. 三关系与新候选的真实入口

| 关系 | 可记录的原意 | 不足时 |
| --- | --- | --- |
| 派生 | 作者选择主要父方案的科学意图+同一受管理实验调用的冻结输入/输出回执；null明确新建 | 未声明、旧shell、缺产物或多源：unknown/unresolved，不按最近时间/同名/相似文件猜父 |
| 复用 | implementation_selection 或受管理调用显式材料使用意图及exact原件 | 与派生分栏；推荐/current/proxy best不变为复用或父方案 |
| 支持 | 原作者明确的主张—结果支持意图，保科学结论入口与适用限制 | 普通引用仅导航；无可解析声明则unknown，不由host从关键词/直接输入推科学支持 |

一次任务可产生多个候选，候选主派生为 DAG 的单主要父边，另有多复用边；跨机制组合只有明确科学声明才记录。保留 `declared` 语义：机械绑定证明谁声明及执行对象，不证明算法实际因果依赖或科学正确。原父资格不继承。

**首版唯一选择 B：领域 cov CLI 窄 wrapper。** 当前实际路径是role-native-launcher.prepare_home生成`exp`，exec task_python `/opt/exp/exp_cli.py`；exp_cli.main的run仅有--script，cmd_run直接调用runner。runner.main用台账非空行数+1分配run_id，先写model后append/print；没有request-ID、锁或run恢复。见测量第5节。原 MCP 关闭，不能把不存在的领域Operation当首版依赖；A（扩已有受管理Operation）仅作为其他已具该接口插件的未来适配方式，不是本节点第二入口。

wrapper只增加真正科学选择`parent_plan`（方案名，显式null新建）及可选`change_intent`，委托冻结原public run一次。执行前自动产生本调用context、保选择/脚本原件及当前W/attempt关联；caller不填机械ID/hash。正常成功仅以**该次调用捕获stdout回执**的run_id/完整row，连同冻结脚本、完成row、确切model字节校验绑定；绝不用台账差分唯一、最新行、同名脚本或model_runN存在替代该回执。机械归并发生在seal，关系明确为declared/observed-context，不宣称算法确实使用该父模型。

accepted context与完成回执追加到本节点独占原件目录；W期间controller已持实例writer，wrapper只取本节点调用锁，绝不再取实例锁或创建全局executor/第二预算。借当前W进程生命周期与原node/W额度；入口不提交模型、不增原任务名额。首版同node串行，一次明确batch选择只适用该冻结call，不成为跨调用activehead。

runner训练失败也会append/print完整failed row并exit1：该次stdout回执与冻结脚本/完整失败row精确匹配、进程已结束且清理可确认时为**known failed**，保留成本与诊断、不授model资格；允许在原W范围与剩余额度内有根据地发起新修复尝试，不能伪成新机制或自动重试。仅transport故障、缺精确回执或执行不确定为unknown；`lineage-status`仅读原accepted/completed context及原stdout/row/artifact核对，完整确切回执可收回成功或已知失败，否则保unknown、不重发。存在未结accepted调用时重复run不新建替代调用；native续接读checkpoint/status，不把原public run自动重跑。原进程清理/预算unknown沿现有规则。T1必须以真实wrapper的故障夹具验证此查询，**不要求unknown一定恢复成功**。

`parent_plan`省略=unknown，显式null不是implementation_selection的nullcarry。并行、绕行原exp或普通shell均不保证被完整采集；其关系unknown、coverage partial。缺/歧义只挡依赖该父选择的调用并有限回作者，不静默降回旧CLI实验；其他科学更新仍可封存。科学父声明与实际输入可读性分开；无可回读model原件时不能声称已绑定该父实现。新wrapper/config只能用于新冻结运行，不改旧public/harness/launcher或N5实例。

接口仅升级 **host/plugin合同v2**，科学结果schema保协议8，不空升9。实现前若证实必须新增真正科学结果选择字段，则回本设计统一冻结一次协议9（严格required+nullable、全角色兼容）；禁止连续原地改8或让W补最终候选关系数组。

## 4. 逐函数复用/替换/删除表

拟新增一个只读 `lineage` 投影模块；输入为验证过的源序列，缓存可删重建，不新增原件账本。低层_source/execution读取→机制/关系fold→render单向依赖；fold不反调history.rebuild/search.project/semantic.outcome，避免兼容delegate形成循环。下表是迁移范围，非本节点已实施。

| 当前文件/函数 | T1/T2处理 | 消费者与删除证据/保护边界 |
| --- | --- | --- |
| history._source、direct_sources | 保留唯一原科学/观察完整性读取；单次构建共享verified源集合 | search/semantic/correction/delivery；绑定来源不等于科学支持 |
| execution.records/reference/record/raw/identity | 原样复用 | 所有continuation消费者；不回退根failed raw，不改attempt链 |
| search._apply_science/_apply | 保留机制delta、screen准入与receipt重算 | lineage重放调用原解释；同态no-op、pending重开、未知focus边界不松 |
| search.project | 新投影路径只做兼容返回机制状态 | 当前逐节点_source循环与history.rebuild重复；新路径删除第二轮同源装配，旧packet保legacy重放 |
| search.bind | 保留focus/repair_root/limits，改读统一机制页/最近W | 当前commitments、mechanism registry、recent_w重复摘要由T2单view替换；准入字段不删 |
| search.launch_reason/accept/stop_reason/report | 保留 | native/controller；W范围、repair次数、原anchor不交给lineage判定 |
| history.rebuild | 新路径薄包装统一nodes/候选/关系投影 | 当前h_scope/h_parents/view拼装移入一处；观测H标签仍不等于候选归属 |
| history.candidate_overview | 迁至统一candidate_view并保兼容facade | history.bind/refresh、closeout；删除重复current/proxy/Arec/actual/recent拼装，不改其独立性 |
| history.bind/refresh | T2统一分页/默认brief；refresh只写可删projection | 当前history.recent/declaredlimitations/h_lineage与search摘要不再双份投递；原结论页和遗漏入口不删 |
| history.capture/_capture/validate_observation | 复用v1；新v2机械归并execution关系来源 | optional timeout/capacity仍保science；adapter/原件篡改硬拒，旧snapshot不重采或补关系 |
| history.implementation_options/resolve_implementation、contracts.selected_inputs | 保留独立exact复用接缝 | nullcarry/[]clear/listreplace、immediate-hop、多父及Eclear边界；不能改义成候选父 |
| semantic.outcome/_source/validate_job/effective_route/accepted | 复用，来源查询指统一源入口 | 8部分生效/有限补正、root计数、preparedjob不覆写；不建另一semantic状态 |
| correction._proofs/project/publish/gate/acknowledge | 保留，读取统一原源 | A全局verdict+原science/limitations解释盲区，无新增必填表；raw去重不当科学verified，sticky pause/ack保留 |
| budget.snapshot/node_admission/_attempt_consumption/used_steps/delivery_reserve | 原样复用，只对外给成本引用 | 原ledger/当前grant/原cap/收口slots/unknown；谱系不保存第二余额 |
| contracts.build_job/science_view/_validate_inputs/validate/seal_result | 新host投影marker选择新view路径；旧job缺marker走原生成器 | old1..8 job/schema/task/seal逐字恢复；不得用删除旧生成器换代码“精简” |
| delivery.binding/invoke、controller._route/_run_closeout | 原样保持candidate选择与动作身份 | exact成功attempt、prefix、安全确认；lineage推荐不执行提交，不改科学路由 |

删除完成证据：新投影fixture逐字段同源核对；新science-task只出现一个谱系brief；现两处装配调用仅剩legacy旧packet分支，生产新路径无第二候选/机制摘要。保留兼容facade不宣称已删除旧历史责任；失败可回退新投影marker，不改既有封存。

新job冻结host `lineage_projection_version=1`及adapter合同版本；已冻结job无marker保持原解释/原science-task，不改旧settings。marker只选择投影布局，不改变科学schema或资格。T1先原件→关系，T2再新marker投递；每节点独审提交。

## 5. 冻结夹具、容量与计数

机器可读设计夹具：[rootless-lineage-v1.json](fixtures/rootless-lineage-v1.json)。它是合成语义预期，非已通过产品测试；只含公开虚构名称，不拷native日志。阈值在实施测试前固定，变更须独审，不按运行结果倒调。

| 项 | 冻结首版值/行为 |
| --- | --- |
| 新默认谱系brief | UTF-8 JSON（indent2+末newline）合计≤4096B，取代history+search双摘要；其他必要任务文字不计为谱系“收益” |
| 每页 | nodes≤8、candidate/机制/实现/关系≤16且实际≤64,000B；双限制打包，合法单row过大明确unavailable+原入口 |
| 历史投递总量 | 原32MiB上限；超过保partial/omitted与页入口，不整包复制模型或祖先附件 |
| 摘要 | summary≤160B、单limitation≤96B、label≤80B、minimal_test≤160B；UTF-8安全截断+标记+原页入口 |
| 观测 | 原5s/输入输出256,000B/新增128/历史候选4096；unknown/partial不能声称完整树或best |
| 搜索片与纠偏 | 沿原冻结node/W策略、repair同root≤2、author补正≤2、N4阈值及ack；T0不重冻结实例预算 |
| 评估可比性 | 同evaluation_key、方向、资格/数据版本才进同组；未知版本不跨组排序，不混正式/条件性reward |

T1最小产品夹具：父P→Q→回退P派生R；组合明确复用S但主父仍P；旧shell/重名/缺产物unknown；A→H→W复用只取所选原件；重启去重、cache删重建、source/attempt篡改拒、unknown执行不重发、持实例锁时插件写不deadlock。追加stdout丢失但row/model看似存在→unknown，精确回执存在但row/model被改→硬拒，绕行/并发→partial不得猜绑定。candidate映射必须通过真实wrapper调用，不仅静态导入JSON。

T2最小产品夹具：H/W/A/E同节点/三关系一致；第17候选/实现与第9node可按页找到，1000节点默认brief仍≤4096B；多字节长字段/缺页/改页、当前角色即读旧结论、科学失败与工程失败分栏；旧1..8任务逐字恢复，坏普通链接不阻科学seal但不获取原件权限。

## 6. T3/T4的实施选择与未决门禁

T3首版不要求helper。原生W在H范围内使用上述科学调用入口，根据返回结果新建/回退/改进；一批廉价实验仍可一次调用，批内父关系须有明确声明。工程repair不是新机制。数值片预算与原节点授权不变；效率收益要比较同口径有效步骤成本、读取与上下文，不能从压缩brief推定模型费用下降。

T4首版可执行条款仅用公开事实：未知/部分coverage保未知；不同评估组不排序；代理胜出只报告该组代理最高；审计pending/skip不当qualified；A推荐与actual分别输出；完整性失配硬拒、未知submit不重放。压力测试适用范围/排名反转及不能观察目标时的科学理由由A判断，host不自动淘汰机制。先冻结规则版本和公开输入，再离线回测；隐藏列在执行入口负控制中不可读。

T4阴性夹具：公开排名在两压力条件反转且目标权重未知→保条件性/未知，不造总分；缺审计候选只条件性，不进正式交付资格；proxy最高、A选定、actual三者不同仍可表示。没有目标代表性证据时不自动等价no_progress；N4仍读取A科学判断与原proof。

## 7. T0退出清单与来源

| 节点粗规模（新增/迁移生产） | 最小范围/主要风险 |
| --- | --- |
| T1：核心250–400行、领域wrapper100–180行；测试150–250行 | 验证原源/三关系与正常调用归并；风险为stdout丢失、可变旧model和锁重入，unknown不猜 |
| T2：180–300行；测试120–200行 | 单brief/共用分页/旧renderer兼容；风险为循环依赖、旧8字节变化及首16项死路 |
| T3：80–160行；测试80–140行 | 原生W观察驱动使用入口，保scope与预算；无helper/新调度器，成本收益仍待真实测量 |
| T4：120–220行；测试120–200行 | 冻结公开规则/未知与A选择视图；风险为隐含目标权重、缺audit与隐藏池过拟合 |

这是实施前估量，不是守门删减目标；明显超范围先复审具体新职责，不能靠删身份/恢复验证凑行数。T1/T2分别独立实施、定向与安装门禁、独审、Git，不把全部T系列合成一个巨大节点。

| 退出项 | 当前事实/阻断 |
| --- | --- |
| 单权威、函数迁移/删除证据、容量及合成夹具冻结 | 设计独审确认；不等于T1/T2产品门禁通过 |
| 新运行已知candidate派生入口 | 唯一首版B及正常回执绑定/unknown查询已冻结；设计独审认可，T1实际资格仍待wrapper门禁，不以不存在的MCP入口占位 |
| 协议兼容 | 首选科学8不变、host/plugin合同v2；若需科学9须统一重审后冻结，不能默加字段 |
| W成本/上下文及观察驱动测量 | 已冻结归档，具体call顺序/批量与修复区别可复查；支持原生W首版，不声称瓶颈已因果归因或效率已提高 |
| 辅助者能力 | 未资格，首版明确禁用，非原生W实施前置；未来启用门禁未满足 |
| T4公开规则/未知与隐藏隔离 | 本草案列出可执行负例；规则回测和独立科学效果尚未执行 |

来源：主计划与已独审全池证据；当前各源码函数基线287b2e2；[只读测量归档](evidence/ROOTLESS_T0_MEASUREMENT_20261012.zh-CN.md) SHA `caf09039d43508b3dd17b69100145e9857de22a21eed141fc204c559a8741b82`，机械JSON SHA `90e14eaa030214b848037c3bdbf9762d4530d52b01e49d9790df61e4d4f0dba6`仅外层留档，native原文不入git/模型。T0只在设计决定/未决门禁明确且独审通过后提交；未知不伪装完成。
