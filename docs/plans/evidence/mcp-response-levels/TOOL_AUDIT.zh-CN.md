# MCP 逐接口信息审计与实施清单

覆盖：29 个 Root、19 个领域/通用 Worker 工具、3 个生命周期工具。Local/Hardened 共用工具定义，生命周期投影分别核查。

本文件为静态审查清单，不是第二工具注册表。权限未扩大；Root 只通过 MCP 读摘要和受控详情，Worker 的本地详情仅在其任务工作区可读。

内部消费者：审批、轨迹、归档及 Python facade 保持原完整返回；仅 RootMCPRouter 应用展示投影。stdio/daemon/proxy 保留同一个结果的 text/structuredContent 兼容表示。

大小目标不是输出准入。normalized_request、明确请求的详情、无详情引用的具体错误是保留例外；不能为凑大小丢掉修复依据。

## root

| 工具 | 类别 / 处理 | 原件与权限 |
| --- | --- | --- |
| `diagnostic_read` | 显式诊断读取；保持：调用者已经选择 section/offset/max_bytes，不能二次摘要 | 同工具按范围续读；scoped diagnostic 权限不变 |
| `instance_current` | 实例状态/回执；修改：名称、状态、管理 URL；目标不再重复 | instance_current view=detail；不增加写权限 |
| `instance_list` | 目录列表；修改：有限页与名称、标题、状态 | view=detail + limit/before |
| `instance_close` | 实例状态/回执；修改：名称、状态、管理 URL；目标不再重复 | instance_current view=detail；不增加写权限 |
| `scientific_inventory` | 科研目录；修改：有限成果元数据页，独立目录入口 | limit/before；operation_catalog 按 ID detail |
| `scientific_current` | 当前选择目录；修改：稳定 kind 游标分页，保留选择事实 | limit/before |
| `scientific_current_select` | 变更回执；保持：无正文，无复制科学内容 | 原对象通过 artifact_catalog；变更授权保持 |
| `lifecycle_events` | 持久事件轮询；修改：有界页，未交付事件不移动观察记录；poll_again | 继续轮询；保持既有消费语义 |
| `artifact_ingest_file` | 变更回执；保持：无正文，无复制科学内容 | 原对象通过 artifact_catalog；变更授权保持 |
| `artifact_ingest_text` | 变更回执；保持：无正文，无复制科学内容 | 原对象通过 artifact_catalog；变更授权保持 |
| `artifact_catalog` | 单对象元数据；修改：身份、schema、大小、parent_count | view=detail 取原顺序 parents/null aliases；不替换缺失对象 |
| `operation_catalog` | 完整合同目录；修改：有限摘要目录，按 operation_id 选择完整项 | operation_id + view=detail；同一编译目录 |
| `operation_preflight` | 准入；保持：一次性完整 normalized_request 必须可原样 invoke；完整具体错误 | 无缩减机器请求；失败诊断原入口 |
| `operation_invoke` | 创建回执；修改：Agent 名、类型、profile、恢复预算；其他执行器本来只返登记回执 | named status detail；保留审批 URL 和精确派发配置 |
| `run_list` | 对象列表；修改：有限页、短行、next_before | 各自 named status view=detail |
| `run_status` | 运行状态；修改：恢复/错误/输出身份；status 默认至多 summary 原文片段 | output_paths 精确选择，view=detail 恢复原记录，diagnostic_after 分页 |
| `run_record_failure` | 运行状态；修改：恢复/错误/输出身份；status 默认至多 summary 原文片段 | output_paths 精确选择，view=detail 恢复原记录，diagnostic_after 分页 |
| `approval_list` | 对象列表；修改：有限页、短行、next_before | 各自 named status view=detail |
| `approval_status` | 审批状态；修改：保持决定/URL；长理由明示 excerpt | view=detail；不能替代 UI 决策 |
| `execution_capabilities` | 能力目录；修改：有界能力摘要；完整选中参数可读取 | view=detail + limit/before；不得据局部页声称能力不存在 |
| `execution_capability_bind` | 变更回执；保持：无正文，无复制科学内容 | 原对象通过 artifact_catalog；变更授权保持 |
| `execution_abandon` | 执行状态/回执；修改：状态、观测耗时、具体错误、收集状态；不回显日志 | execution_status view=detail；sync 可同次请求 detail |
| `execution_cancel` | 执行状态/回执；修改：状态、观测耗时、具体错误、收集状态；不回显日志 | execution_status view=detail；sync 可同次请求 detail |
| `execution_list` | 对象列表；修改：有限页、短行、next_before | 各自 named status view=detail |
| `execution_status` | 执行状态/回执；修改：状态、观测耗时、具体错误、收集状态；不回显日志 | execution_status view=detail；sync 可同次请求 detail |
| `execution_outputs` | 产品元数据目录；修改：output_label 游标分页，不读产品正文 | limit/before；登记语义不变 |
| `execution_start` | 执行状态/回执；修改：状态、观测耗时、具体错误、收集状态；不回显日志 | execution_status view=detail；sync 可同次请求 detail |
| `execution_sync` | 执行状态/回执；修改：状态、观测耗时、具体错误、收集状态；不回显日志 | execution_status view=detail；sync 可同次请求 detail |
| `execution_collect` | 异步收集回执；保持：无产品正文，既有短回执与错误 | execution_status view=detail；不重启求解器 |

## worker

| 工具 | 类别 / 处理 | 原件与权限 |
| --- | --- | --- |
| `worker_curve_contract_compile` | 确定性编译回执；保持：无完整科学对象内联；非分析前置门禁 | 原工具返回的本 Run 文件 |
| `worker_file_write_begin` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_file_write_chunk` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_file_write_commit` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_file_apply_patch` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_extract_pdf_text` | 证据读取；保持：不是把 max_chars 全量文本塞进响应，无需降低取证能力 | 精确本 Run 只读正文路径 |
| `worker_curve_figure_inspect_source` | 取证预览；修改：首8个图引用和遗漏数量；完整 JSON 保存到只读详情 | details_path + 图文件；不摘要原始图片 |
| `worker_curve_figure_preview` | 取证预览；修改：首8个图引用和遗漏数量；完整 JSON 保存到只读详情 | details_path + 图文件；不摘要原始图片 |
| `worker_curve_score` | 计算；修改：原件先封存，再返回少量实际指标、计数与引用 | calculation_path 完整只读记录，calculation_ref 正式引用 |
| `worker_curve_diagnose` | 残差诊断；修改：record 为计算摘要；图像权限、详情/证据保留 | record.calculation_path、details.path、images 原图 |
| `worker_analysis_publish_files` | 证据发布；保持：短 alias/path/hash 收据；每个实际发布文件均需可定位 | 既有受控工作区文件和 tool evidence；不证明脚本执行 |
| `worker_file_json_patch` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_file_delete` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_file_move` | 文件编辑；保持：不回显整个正文或 diff；具体错误不改成泛化文本 | 当前工作区文件；权限及原子编辑不变 |
| `worker_tcad_debug_run` | 工程调试；修改：状态、耗时、预算、具体错误和完整快照路径 | details_path 同 Run 快照；log_relative_path 原日志；不授科学资格 |
| `worker_tcad_curve_score` | 计算；修改：原件先封存，再返回少量实际指标、计数与引用 | calculation_path 完整只读记录，calculation_ref 正式引用 |
| `worker_tcad_curve_diagnose` | 残差诊断；修改：record 为计算摘要；图像权限、详情/证据保留 | record.calculation_path、details.path、images 原图 |
| `worker_tcad_inspect_outputs` | 原执行文件检查；修改：目录首10项+遗漏计数；显式单文件检查保持 | details_path 完整目录；单文件受控证据原件 |
| `worker_tcad_accept_output` | 精确产物接收；保持：只有一个已检查文件的短回执；身份和 lineage 必须完整 | 返回当前受控证据文件；同 execution 约束不变 |

## lifecycle

| 工具 | 类别 / 处理 | 原件与权限 |
| --- | --- | --- |
| `worker_open_assignment` | 任务/合同读取；修改 Local 为冻结合同路径/指针；Hardened 保留必要内联合同例外（禁止原生文件读取），不扩权限、不增工具 | 本 Run 只读文件；legacy 同 identity 的受控原合同 |
| `worker_heartbeat` | 生命周期；保持：短回执，不能延长绝对预算 | assignment 与状态 |
| `worker_submit_result` | 提交；保持：不回显科学 JSON；没有可读详情引用时保留全部具体诊断，允许超体积目标 | 同 Run 纠错；Root diagnostic_after 翻查历史 |
