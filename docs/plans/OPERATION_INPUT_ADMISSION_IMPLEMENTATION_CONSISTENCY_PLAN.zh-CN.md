# Operation 输入、准入与实现一致性修订计划

状态：R2，独立复审 PASS，实施冻结版。2026-09-10。R1 已冻结于 evidence/input-admission-consistency/PLAN_R1.zh-CN.md。

## 1. 已确认事实与 R1 修订

实际 tcad.reviewed-deck-package.v2 绑定 author_4、deck review_5、capability_1 与 experiment_plan_3，预检返回 input_independent_review_missing，port 为 experiment_plan。通过的 experiment_review_6 已存在，但打包缺少其输入端口。

纠正 R1：operation_transforms.package 已将完整绑定投影成四个业务输入，再调用 transform_adapter；后者的四项校验不是此次失败原因，不需要重构 Mapping 接口。

独立 R1 审查为 REVISE：全 Schema 生产者扫描不能作为全局启动硬门禁；编译 reviewer 资源兼容和运行时绑定兼容不是一套规则；集合共享审查取决于实际身份；删除无依据的业务接口重构。全部接受。

## 2. 唯一权威与保证范围

OperationSpec 决定允许的输入集合、类型、基数和用途；现有 ReviewSpec/review_edge 决定 reviewer、subject 与可接受结论。确定性诊断从二者计算，不新增 review_for、持久化索引、状态机或依赖清单。

三层分别负责：声明接收证明的方式；运行时验证实际精确证明；包装器向算法投影业务操作数。保留现有投影，不把框架证明强行变成业务参数。

本轮保证当前真实打包链闭合，并提供可复用的目录诊断在研发阶段发现同类遗漏。不声称仅凭 Schema 静态保证所有未来插件组合可执行。目录诊断不是新的生产启动门禁；实际绑定继续严格预检。全局编译拒绝只有在合同能够证明依赖必需时才成立，本轮不扩张该政策。

## 3. P0：证据与清点

冻结当前工作树基线和失败请求，保留先前改动。研究记录仅从公开控制接口读取，不访问数据库或 Worker 隐藏目录。

清点 consumer/subject/producer/reviewer/candidate ports，覆盖当前四插件目录与 core/general 最小组合。Schema/media 匹配只表示可能来源。粗筛已有 14 个缺口组合，包括打包、control-equivalence、deck compare、跨来源 intake audit；正式结果要区分背景、直接修订、审查本身。

除本次打包，其余缺口列入报告，不批量加端口、改 usage 或豁免；遇到真实后续阻断再作证据驱动修订。

## 4. P1：最小端口修复

只修改 operation_transforms.py 的打包声明：增加 experiment_review，复用 general_science scientific-review schema/codec，0..1，usage=prior_signal。可选保留无生产者合同的导入计划行为；真实生成计划是否必须带证明由实际 producer review edge 决定。

项目证明仍为 review，计划证明为 experiment_review，不能互换。保留 package_parentage 精确关联。包装器仍投影四个业务输入；experiment_review 经框架验证，保留为不可变调用父记录。不改 transform_adapter.py Mapping 接口、业务数据、初始化证明或审批规则。

## 5. P2：共享结构规则与目录诊断

新增小型 operations/review_admission.py，供 Root 准入和目录诊断两个实际调用者使用。不增加服务、MCP 工具或持久化状态。

共享内容仅为现有结构分类：evidence_inventory 跳过；已激活直接修订的 base；消费者恰为所需 reviewer 且绑定 subject port 的豁免；其余要求 witness。激活条件仍由 active_direct_revision_ports 按实际已绑定端口判断。

RootOperationRoutes._validate_producer_output_admission 使用共享分类替换等价分支；生产者合同读取、历史兼容、is_exact_reviewer_output、非通过 verdict 策略和 consumed/unbound signals 不变。背景必须在读取生产者合同前跳过。

诊断函数接收已编译目录，遍历可接收的生产者输出，使用共享分类，寻找 Schema/media 可接收 reviewer 输出的端口。输出缺口与需要实际绑定判断的事项，不改变 compile_catalog 接受集合，不向运行时增加 codec/resource 全等。

直接修订须区分必需端口与可选端口激活情形，不能把全部可选端口都存在当作所有请求保证。集合容量、同一审查覆盖多个 subject 和不同 Run 证明仍由运行时按身份验证；不按最大集合容量新增拒绝。

定向测试及工程探针调用诊断。删除打包证明端口的反例应被诊断定位，并在实际 Root 绑定时拒绝；不是整个目录拒绝启动。

## 6. P3：最少有效测试

复用 test_l4_local_tcad.py 系统与作者/审查设施。用小型计划生产者和真实 compiled review edge，通过 invoke/受控 submit 生成计划及独立审查；可用小型测试插件，但不能直接注册无生产者合同的计划。无需 LLM/VM/Sentaurus。

- 正确计划审查、作者、源码审查、打包 Root 链成功；证明保留在包的父记录，四项业务投影成功。
- 缺失计划审查、另一计划 pass、当前计划非 pass、错误 reviewer 均在业务实现前拒绝；未知端口仍拒绝。
- 删除接收端口后目录仍编译，诊断定位缺口，真实调用失败。
- 合法导入计划、同 Schema 不同来源、可选未绑定、blocked 项目可审查、直接修订及非通过 review signal 代表回归保持不变。
- 若既有测试没有共享审查覆盖，补小型真实 reviewer Run 多 subject 测试：完整覆盖通过，仅部分覆盖拒绝，不同 Run 需要各自证明；不以容量推断代替。
- core/general 最小目录与完整目录编译成功；其他缺口记录而非宣称已修复。

主要测试在 test_l4_local_tcad.py、test_agent_contract_alignment.py；可新增一个 test_review_admission.py 放小型诊断及真实 review-edge 用例，避免大文件重构。

串行、BLAS/OMP 单线程、每批 120 秒超时、地址空间 3 GiB 上限，记录 RSS；不跑全量、压力或并行求解器。失败先定位，不扩跑掩盖。

## 7. P4：安装、兼容与真实续接

核心与 TCAD wheel 同时安装到全新临时目录，明确其他依赖范围；从 wheel 导入走 Root 打包回归，不称全新依赖矩阵。

保存前后完整目录 Operation 摘要。共享结构函数不改科学合同语义，不全局提升 ABI，不放宽旧摘要。新增输入仅影响必要打包及声明依赖。使用公开控制元数据及本地编译结果核验 plan_3、experiment_review_6、author_4、deck_review_5 对应摘要保持兼容；非预期变化先分析组件资源范围，禁止重做科学内容绕过。

本轮完成工程实现、定向/安装检查与独立结果审查。正式安装重启需要宿主权限时提供准确命令并等用户实际完成；不能把此前安装确认当作本次已部署。

部署后用新打包名称显式绑定原 experiment_review_6，preflight 通过才 invoke。随后创建六案例 execution 审批 URL，UI 封存批准后才能执行。结果不完整时允许目录支持的有限分析，不新增科学判定。

## 8. 顺序与验收

独立复审 PASS 后冻结计划，按 P0→P1→P2→P3→P4 实施；最终差异独立审查。P1/P2 共同验收，不部署中间版本。

工程完成标准：真实 producer 合同链正确绑定通过、错误证明仍拒绝、诊断发现本类遗漏、合法历史分支不变、wheel 检查通过。部署后的真实记录打包另记状态，未部署不称实际阻断解除。

新增全局来源限制、状态机、批量科学合同变更或资格迁移超出本计划，需停止修订。交付失败证据、同类清点、增量理由、测试/内存日志、摘要影响、安装命令与待验收项。
