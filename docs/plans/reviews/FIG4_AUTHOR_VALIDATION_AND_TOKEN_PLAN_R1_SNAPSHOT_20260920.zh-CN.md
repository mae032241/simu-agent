# Fig4 作者最小动态验证与 token 整改计划

状态：待独立审查的工程提案；仅制定计划，未修改实现、测试、部署或启动科研执行。本文不宣称方案已审查通过。

## 1. 目标、证据与范围

目标是让实现作者在授权范围内尽早发现会使研究无效的运行行为，同时减少信息进入模型之前的重复展开。控制层继续负责不可变绑定、权限和资格，科学充分性由 Worker 判断；不增加新角色、状态机、通用 mandatory-dynamic 字段或科学填表体系。

证据入口为 [progress.json](evidence/fig4-e2e-20260920/progress.json)、[Worker统计](evidence/fig4-e2e-20260920/TOKEN_ROUND_FINAL.json)、[Root快照](evidence/fig4-e2e-20260920/ROOT_ROUND_USAGE_INTERIM.json)。它们是本轮工程观察，不代替科研原件。此次计划只读取这些精确证据及相关源码，未展开全部 trace。

本轮七案计划、源码分别独立审查 pass；生产 solver exit 0，但实际 `*_fps.tdr` 与声明文件名不符。分析又发现有限源时间边界未动态生效、CM/J 派生输出停在初值、重复界面坐标。受控修订修好了部分命名、坐标和 CM；连续边界及 J 仍未验证，作者正式交付 `implementation_gap`，没有重跑七案。这是实现有效性缺口，不能作为有限源物理假说的否定。

| 根因 | 证据与边界 | 整改方向 |
|---|---|---|
| 已有初始化和 first solve 要求，仍未证明时间推进、输出刷新、实际命名 | author 角色已有相关要求，preflight/initialization 均 pass；后续分析 invalid_study | 是诊断覆盖与验收证据质量缺口，不能仅追加一句提示词或把 exit 0 变成科学 pass |
| Root 在选择信息前展开全文 | 审查响应 8326 字符；invoke 请求 961、响应 1258 字符 | 优先修全文审查和重复合同/日志；字符不是 token，invoke 不是最大已证实来源 |
| Worker 大块读取、重复导航及输出截断 | 六线程344请求，峰值74942–131932；修复线程3次截断 | 默认有界视图、定位后读取、按内容身份与范围识别重读；不以缓存命中证明窗口省量 |
| 引用工具用于不支持的根对象 | objective 无 producer；历史缺口无 paired manifest | 给准确可用性及原件入口，不靠失败探测、不补造历史关系 |
| 输出登记与绑定时序不一致 | 登记前 result_artifact_name=null；登记后才可绑定 execution_result；inspect 报 undeclared Run input | 登记响应直接携带准确结果名；创建分析前绑定，冻结后不补写 |

六线程累计输入20143380、缓存19499136（约96.8%）、非缓存644244、输出115055；这些累计值不是上下文窗口大小。Root 84474→165367，净增80893，包含讨论和监控，不能逐项归因。本轮没有完整上一版 Worker A/B；既有一次 Root 旧快照对照不能补成完整基线。`reference_manifest_unpaired` 的精确诊断仍需在实施时按事件定位取得，不推断其缺失正文。

文档责任：本文是新增活跃提案，补充 [R4按需引用计划](REFERENCE_ON_DEMAND_REMEDIATION_PLAN_20260919.zh-CN.md)，不替换其身份、访问收据、权限和预算语义。该计划正文的部署状态叙述落后于其 [实施状态](evidence/reference-on-demand-20260919/IMPLEMENTATION_STATUS.zh-CN.md)：已有部署后有界功能复验，原生版本 token A/B 和综合科学验收仍未完成。实施时仅修当前状态入口并交叉链接，不重写历史审查/失败证据，也不继承旧 PASS。

## 2. 可复用能力和最小动态验证设计

已核对 `plugins/tcad_artifact/tcad_artifact/`：

- `local_debug_service.py` 的 `LocalTCADDebugService.run/_start`、`debug_summary` 已有同名轮询、源码和声明绑定、总6次/360秒预约、剩余 Run 时间收紧、失败不返还预约、选择输出及详情文件入口。
- `debug_adapter.py` 的 `_development_limits/_development_arguments` 和 `TCADDevelopmentDebugBridge.prepare` 已支持独立初始化入口。R-2020.09 的 SProcess initialization 直接调用声明 `.cmd`，120秒上限；SDevice 使用 `-i`。前者可承载有界时间推进的候选诊断，后者不能据名称推定已动态求解。
- `operation_workspace.py:finalize_workspace` 检查当前源码绑定的控制层 preflight/initialization 报告，已有独立 `ImplementationGap` 交付分支；`project_packager.py` 保持工程包、review、runtime attestation 的分工。
- `mcp_response_views.py` 已有 summary/detail 和分页；`input_reader.py:read/page` 已有范围读取；`reference_access.py` 已有精确根、producer/manifest 校验和单跳选择；这些机制应收敛使用，不重建。

第一步是审查既有开发权限是否覆盖“小案例、短演化、少量诊断输出”。可执行 `.cmd`、已有时长限额都不等于任意生产批跑授权或正确性证明。只在已编译能力和既有开发授权确实覆盖时复用 initialization；若授权文字只允许初始化，先明确其受控范围，按现有审批合同取得所需网页授权。不得借名字隐藏扩权，不直接 shell 运行 solver。无法在既有路径合法完成时交付具体缺口，另走现有带网页审批的精确外部执行路径；本计划不默认新增 mode 或通用执行器。

作者针对当前更改选能区分正确/错误实现的最小观察，不要求所有科学任务跑仿真。纯源码合同、解析修订保留 preflight 路径；涉及随时间更新、状态耦合或输出采样的实现，需要在授权允许时取得相应非初值观察。诊断应调用生产相关过程/定义，压缩案例或时长，不能另写一套只会通过的替身。可在现有源码注释和 handoff 中说明目的、与生产对应位置、检查的原始输出和未覆盖项，不新增重复字段。

记录复用现有工程报告、attempt_files、封存项目和日志：控制保存准确源码/声明身份、模式、后端版本、选定输出、预约/实际耗时和退出信息；作者解释观察是否回答所选问题。需保证 reviewer 能通过精确已封存入口读取被引用诊断输出；若现有封存只保留报告而遗漏相关文件，则在现有工程附件/attempt_files 边界补最少文件，不另造证据数据库。开发诊断可支撑实现有效性判断，仍不是论文结论或生产科学证据。

## 3. 责任与交付门

| 角色/组件 | 责任与禁止代替的判断 |
|---|---|
| author | 选择能暴露更改层错误的最小诊断、写真实入口、读取实际输出并报告局限；未验证不得写成已验证。成功或 implementation_gap 均可正式交付 |
| 控制层 | 核查权限、精确身份、当前报告、预算、冻结输入与独立审查；不通过搜索 `Time`、非零 J 或固定科学字段判定物理正确 |
| 领域执行器 | 严守模式、资源和输出范围，保存原始观察、实际文件名及终止信息；exit 0 只代表执行事实 |
| 独立 reviewer | 检查诊断是否覆盖变更、生产对应关系及未覆盖风险，按需核对原始观察；不得沿用 author 身份，也不必机械重跑全部诊断 |
| analysis | 在精确生产结果/原件绑定上作数值和物理判定；开发通过不替代生产有效性，invalid_study/implementation_gap 不解释为物理否定 |
| Root | 选择当前科学决策所需行动、绑定登记后的结果、读取结论/限制/剩余矛盾/scheduler_signal；提供全部审批URL，不把聊天当审批 |

完成门沿用两层：机械门只校验已有权限/报告身份及真实记录；语义门由作者和独立 reviewer 判断覆盖。仅有初始化 pass 而关键动态行为未知时，合格交付是明确缺口，不能进入“已验证可生产”的结论。修改任何相关源码、声明或调用后，旧诊断与审查不得充当新版本证明。

## 4. 工作包与实施顺序

以下路径均相对仓库根；按包做窄实现审查，不以一次全库 diff 混入此前工作。

| 顺序 | 精确落点 | 最小改动和退出条件 |
|---|---|---|
| WP0 基线及合同收口 | 本计划、`docs/plans/evidence/fig4-e2e-20260920/`；新建本次实施证据子目录 | 保存实施前工作树与环境快照，冻结两组测量任务；独立审查权限/后端差异和动态诊断对应关系，先确定是否无需新执行模式 |
| WP1 作者覆盖与交付 | `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md`、`plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_reviewer.md`；`local_debug_service.py:debug_tool_description/debug_summary/_finish`、`debug_adapter.py:_development_arguments/prepare`；`operation_workspace.py:finalize_workspace`、`project_packager.py:validate_deck_review_against_project` | 明确“first solve 不证明时间行为”；准确表达后端能力，补必要工程文件入口。优先文案/现有记录修订；只有实证遗漏才改封存代码，不新增万能物理断言。旧报告仍可读，不能自动升级动态资格 |
| WP2 输出登记到分析 | `src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py:execution_outputs/_publish_execution_result`；`mcp_response_views.py:root_response`；`plugins/tcad_artifact/tcad_artifact/output_recovery.py:inspect_tool/_inspect`；`roles/scheduler/execution.md`、`domain-analysis.md` | `execution_outputs` 返回 `_publish_execution_result` 的准确 `result_artifact_name`，分页保留；没有结果明确 null/尚不可用。Root 用登记响应创建分析并绑定声明端口。inspect 无输入时明确不可用及修复途径，不能自动搜索最新结果或修改 frozen Run；只需有限原件分析者仍可带限制完成 |
| WP3 引用入口可用性 | `src/scidiscovery/artifact_agent/service/reference_access.py:_reference_pair/_reference_source/reference_read`；`run_assignment.py:assignment_json` | 在已有根导航中给可用/不可用/尚未检查及准确理由和显式原件入口。复用配对检查；不为所有根递归读取 manifest，不假称未检查为不存在。首次确切发现无 producer/paired manifest 后复用结果，别名权限仍每次校验；正文可读与引用展开可用分开。错误码保留，历史缺关系不补造 |
| WP4 进入模型前裁剪 | `src/scidiscovery/artifact_agent/interfaces/mcp_response_views.py:root_response/execution_summary/run_summary`；`mcp_root_operation_routes.py:_operation_catalog_item`；`service/input_reader.py:read/page`、`run_assignment.py:assignment_json`；`roles/scheduler/{research,results,inputs,dispatch}.md` | 目录默认只导航，所选合同 describe 一次完整读取并按安装版本复用；审查默认决策字段组合，不全文；execution detail 默认日志索引/有界不同片段，stdout/solver_log相同内容只显示一次并保留两来源入口。错误原文、遗漏、游标、准确全文访问路径不得丢失；`operation_invoke` 成功响应只保留创建/派发必需字段及详情入口，保留必要参数配置、exact errors 和 approval URL，不能误删影响下一步合法调用的信息。它不是本轮最大已证实来源 |
| WP5 验证、测量和文档 | 下节定向测试、隔离安装入口；R4实施状态入口与本计划 | 独立源码审查、两组可比测量，再单独决定部署；后续真实 Fig4 诊断/生产授权另走运行合同，不由工程测试 PASS 自动触发 |

WP2–WP4 的默认响应改变必须同步工具 schema/description 的真实定义（实施时从现有路由注册定位），不能只裁剪 Python 后留下不可调用的全文入口。完整合同不截断，detail 的历史消费者须保留显式原始内容选项或兼容版本。Root 可以主动取全文，但不得把全量响应先打印进模型再筛选。Worker 原生读取不能虚称受框架硬限额：指引先目录/关键词/JSON指针再读指定段，遇截断改范围；不并发抓取全部分页后汇总打印。控制不以“已提供收据”证明模型已读懂，也不建立阅读覆盖率资格门。

## 5. 兼容、定向测试和资源约束

不迁移历史 Artifact，不改旧 manifest/输入，不继承旧审查或生产授权。目录可用性是派生导航而非新权威；历史无配对资料保持显式绑定读取。执行结果绑定只来自本 execution 的准确结果，冲突仍拒绝；重复登记幂等，多页返回同一身份。精简视图不得吞掉不同日志的独有错误、approval URL、missing inputs 或 pagination/omission 标志。开发/生产资源限额分别保留，不因本地测试限额反向改写已授权求解器资源。

实施后串行运行选择到用例的 pytest 批次，整个本地进程树 ≤768MiB；使用既有 `scripts/compiled_worker_process_guard.py`，记录命令、退出码、峰值RSS与超限。模型进程曾超过该限制，达到上限立即停止，标记该次测量无效/未完成，不自动提高、重启重试或换无限额路径。没有本轮必要性不跑全量套件。

- WP1：`tests/operations/test_tcad_initialization_outputs.py`、`test_tcad_development_lifecycle.py`、`test_l4_local_tcad.py` 中相关用例。覆盖后端参数差异、选定输出、预算耗尽、源码变更后旧报告失效、封存可读、implementation_gap 合法。mock 只验证边界，不证明真实时间推进。
- WP2：`tests/operations/test_analysis_evidence_recovery.py`、`test_execution_collection.py`。覆盖登记前/后、分页及重复调用、缺 execution_result、绑定错执行/跨实例拒绝、冻结后不补绑；允许有界分析明确缺口。
- WP3：`tests/operations/test_reference_access.py`、`tests/artifact_agent/test_input_reader.py`。覆盖无 producer、无 paired manifest、旧显式原件可读、未知状态、单跳授权及禁止递归，导航不能授予新权限。
- WP4：`tests/operations/test_mcp_response_views.py`、`test_catalog_installed_entrypoint.py`。用大报告与重复/不同日志验证默认大小有界、错误和完整合同保留、全文入口真正可达。再做一个非TCAD fixture，避免把 Fig4 规则全局化。
- 最终仅做选中变更需要的隔离安装/文档链接及 `git diff --check`，报告精确测试范围；不把工作树此前测试计作新候选通过。

## 6. 两组可比测量：先保存当前基线，再编码

已知 HEAD 为 `943c4626f8490530e9318eb9fbb409d2670908b9`，父调度器报告327项脏记录；HEAD 不是本轮实施前版本。WP0 必须保存本次改动前精确工作树快照（包括所依赖未提交/未跟踪源码、插件、角色、schema、安装配置；不采集密钥），清单含路径/hash、HEAD、脏状态、依赖锁和可重建安装版本。之后保存新候选同类快照，以两快照差异定义增量。原始响应及 usage 独立保存，只向模型提供测量摘要。旧证据可作背景，不补造缺失的上一版 Worker。

稳定收益判断要求每组至少两对 before/after，即 Root 和 Worker 各两对，以观察重复间波动；若768MiB限制或既定预算不允许，则明确标为仅单对或缺测，不能声称已排除波动。交替版本顺序，单次新线程，固定 `gpt-5.6-sol`、`medium`、精确输入、任务目标、时间/尝试/输出预算、工具和后端 fixture。不得一边恢复长线程、一边用干净线程比较。Root 与 Worker 分开计量，任何 compaction/重启分段；监控、人工讨论和失败测量单列。

1. **Root 决策及登记组**：同一封存审查与执行 fixture，从目录选择合同、读结论/限制/矛盾到输出登记和创建分析请求。固定重复日志和 result 从 null 到可绑定的事件；比较重复合同、全文审查、重复日志及漏绑定发生率，不能删掉必要决定来省 token。
2. **Worker 作者/取证组**：同一最小实现有效性问题、源码与精确原件，提供确定性的受控诊断记录（含非初值输出缺口），加无 producer/无 manifest 的历史入口。比较相关段读取、无效引用探测、重读、截断、能否交付准确的实现缺口。两版本都要求同样的诊断任务，避免把新增职责差异误记为 token 退化；此组是工作流测量，不证明真实 solver 能力。

每次记录首次输入、末次输入、逐请求输入峰值，分别报告峰值增长（peak−first）和末次净增长（last−first），以及请求数、工具可见字节、同一内容身份/选择范围的重复提供字节与重复读取次数、截断及无效调用、输出token；缓存/非缓存累计只作成本补充。首要判据是峰值、峰值增长和末次净增长下降、已知重复展开/无效调用消失，且身份、结论和遗漏保持准确。报告每对差值与重复间波动；小于波动、仅有单对或有缺测只报稳定收益未证实。无法在768MiB运行模型时仍可完成确定性响应测量，但不得称原生 A/B 完成。

## 7. 真实 Fig4 有界验收与后续生产审批

源码/测试/安装完成并经独立审查后，才能决定后续部署；本计划本身不授权部署或执行。部署改变合同则刷新描述，旧 Run 不偷换合同。真实科研验收从已封存 `implementation_gap` 及准确输入出发，由 Root 选择一个能改变实施有效性判断的最小任务：验证连续时间边界更新和最终通量/派生量导出，顺带核查所选实际文件名与界面坐标处理。作者选择一个代表性有限源案例、最短能区分初值与演化的时间点及必要输出，参数/阈值沿精确科研输入；不能由工程计划编造数值。七案不自动重复。

沿已有开发能力、范围及预算执行；如需要外部审批，给精确网页 review URL 并读取封存决定后才开始。诊断须覆盖生产定义/调用路径，保留初值与演化后的原始观察，不能以手工刷新一份派生报告证明持续边界更新。若输出仍只能证明若干时点，明确这不等于连续/accepted-step 守恒已通过，由科学设计者判断所需下一步，不静默放松冻结要求。

验收可能产生两种诚实交付：有原始诊断支持的实现修订，或准确界定的 implementation_gap。独立 reviewer 检查对应关系和观察；只有关键实现有效性缺口得到支持的解决，才可提出新的精确生产包，并重新独立审查及网页审批。生产后登记结果、绑定 execution_result 和必要输出，再由 analysis 作数值/物理结论。若连续边界、J 或其他科学门仍未验证，本项只能报告诊断链/缺口交付有效，不能宣称 Fig4 科学闭环通过。

## 8. 本轮不做与未决问题

不实施源码、不运行测试/模型/科研MCP或 solver；不部署，不重跑七案，不改科学阈值、不将当前 TCAD 症状写成全局校验；不新增通用执行器、角色、预算调度器、阅读状态机、依赖递归展开或历史补登记；不回退既有工作树，不把整个 HEAD diff 当本轮增量。

实施前待独立审查确定：现有开发授权是否确切覆盖所需短动态诊断；SProcess 入口与真实生产路径能否在既有预算内实现有区分力的观察；诊断原始文件是否已随现有封存链足量保留；SDevice 的不同能力如何只在其真实边界表达；native 模型在768MiB下是否可完成成对测量。前述不确定项不足以授权新模式、放松审批或提前声称科学通过。
