# Worker 上下文浪费修复计划 R0 独立复审

日期：2026-09-19。结论：**REQUEST_CHANGES（工程计划；1 项阻断）**。

审查对象：[计划原文](../WORKER_CONTEXT_WASTE_REPAIR_PLAN_20260919.zh-CN.md)，SHA256 `2896a90d1e9d023d8ff6459f7170cbb231f78c3991753c7c32665c820c42754e`；源码基线 `HEAD=943c4626f8490530e9318eb9fbb409d2670908b9` 加审查时已有未提交/未跟踪工作树。没有把 HEAD 当成全部候选实现。此次仅新增本报告；未改计划、生产代码或其他工作者的改动，未访问生产实例、运行测试、模型、TCAD 或部署，也未派生 Agent。

依据：[全链审查](TOKEN_WASTE_GLOBAL_REVIEW_20260919.zh-CN.md)、[真实 Worker 计量](../evidence/mcp-response-levels/TOKEN_WASTE_LIVE_REVIEW_USAGE_20260919.json)、当前架构、科学设计宪章和约束登记；历史 M0 账本及后续缺陷入口只作历史背景。应用跨边界评审与简化审查技能。本次通过定向源码阅读验证可实施性，不是实现验收。

## 阻断 B1：真实 Worker 验收尚未选定可用的启动及计量路径

**计划位置：** S0 第 44、49—51 行，S1 第 71 行，S4 第 112、122 行，S6 第 142 行。计划同时要求真实冻结输入、正常 Operation 交付、真实 Worker 对照及资源保护；native 缺少观测时又指向“受保护的独立 CLI”。这些边界正确，但当前列举的工程路径不能直接组成该验收。

**准确代码依据：**

- `scripts/run_compiled_codex_worker.py:145–147` 遇到当前 unified MCP 配置和无独立 role server 时直接抛出 `legacy direct-CLI probe cannot launch unified MCP roles; use native spawn_agent and Root worker_attach`。因此它的进程树保护能力不等于能够启动当前 Worker。
- `docs/plans/evidence/mcp-response-levels/probe_root_boundary_usage.py:50–57` 在 invoke 后由测试 `_worker` 打开任务，直接写 `_envelope()` 并提交；它不执行科研模型阅读。外层 `run_root_boundary_ab.py` 的串行资源保护不会改变这一事实。
- `docs/plans/evidence/mcp-response-levels/probe_request_usage.py:211–225` 创建 `threadSource="user"` 的 read-only 新线程；`:228–242` 首轮完成即终止进程。现有入口没有直接完成 S4 的同 Worker 两 Run 绑定/接续。
- 现有正常路径见 `roles/scheduler/dispatch.md:3–19`：native spawn、必要时取得 worker_identity、Root worker_attach，再打开任务；复用前重新绑定。`service/worker_connections.py:43–52` 校验旧 Run 终态、同 Operation/digest/model/effort。不能用脚本内手写身份或直接套用 fixture 替代。

**可达场景及影响：** 按 S0 完成离线回归后，实施者选择现有受保护 Worker CLI 执行 S1，会在加载 unified profile 时被拒；改用现有 Root probe 则得到 fixture Worker 结果；直接使用现有单轮 request probe 又不能证明真实 Worker 身份、提交与 S4 接续。该缺口影响两项主要完成门，并可能迫使实施时临时扩展启动机制；不是要求提前证明节省比例。

**最小修订：** 在 S0 明确选一条有依据的路径，并将其可达性核对作为付费对照之前的工程检查。最小选项是现有 native spawn → worker_identity（需要时）→ attach → open/submit，使用原生逐请求 usage 记录方式，S4 在第一 Run 终态后重新 attach 同线程；明确 before/after 使用分别冻结的候选与输入，第二组不继承第一组上下文。说明实例/材料通过现有绑定或受控导出取得，模型对照在获授权范围内执行，本计划不代替 UI 执行批准。native 无法观察进程树时，明确其内存覆盖不足，资源验收保持待验证；不得声称 1536 MiB 硬限制已经生效。若该硬限制是不可放宽的完成条件，则先列出真正支持当前 unified Worker 的已有可用入口或一个单独有界的适配任务，明确身份、权限、终止与 usage 收集方式；不可把已拒绝的 legacy CLI 写成可用回退。无需新增 MCP、角色、科研状态或完整科研链。

上述修订只需澄清验证入口和未覆盖状态，不要求本轮启动模型，也不要求开发另一套测量框架。

## 已成立的设计及核对结果

| 项目 | 判断与源码对应 |
|---|---|
| 目标口径 | 第 29—35 行以单请求峰值、净新增和无效重复为主，明确累计缓存不是多份窗口增长。真实样本 22,521→67,196 仅为定位依据；首次完整独立审查、必要科学字段和平台成本未被一概列为浪费。没有要求凭字符数估算精确 token。 |
| S1 本地 reader | 单个普通 helper 与 `local_workspace.py:164–168` 复制既有 stdlib reader 的模式相容。计划覆盖 JSON Pointer、精确值/数字、UTF-8 与转义后完整回复预算、长元数据失败、连续分页、可变源版本、外层聚合截断、旧 Workspace 回退和安装态。它不产生科学摘要或读取资格；没有证据仅因新增 helper 就否决该设计。科学上需要全篇时仍可完整读取。 |
| S2 日志 | `local_process_observation.py:270–276` 的保留/回显共用预算确实存在；`:284、318、337` 分别涉及返回退出码、观测记录和 CLI 传参。计划保留原日志上限、退出码、stdin/argv/超时及非 analysis 权限；明确盘点后仅改模型展示消费者，机器消费者保留 raw。因此不构成无条件全局更改 stdout 的方案。 |
| S3 author 指引 | `local_debug_service.py:82–94` 保存完整 details 并投影 progress；role 当前 `:186–195` 仍期待内联日志。计划中的 details/log_relative_path 修正有直接 producer 依据；`role_pack.py:10–11` 会把文本拼入角色，计划已处理 digest 改变和旧冻结 assignment 不重写。 |
| S4 角色复用 | `codex.py:341` 每新 assignment 全文重读，`mcp_local_worker.py:391–419` 已读取当前冻结 assignment，适合计算只读正文指纹。第 114—116 行明确指纹不是记忆证明，失忆/变化必须回退，新 instruction、目标/inputs、预算、语言、输出/恢复入口每轮仍读。没有引入持久缓存或放宽作者自审、复用准入。行为收益仍必须由两轮实际对照确认，不能由哈希单测代替。 |
| S5 恢复投影 | `runs.py:1703–1714` 提供 coverage 明细；`mcp_root_run_routes.py:233–234` 交给 Root 返回；`mcp_response_views.py:58–73、90–94` 有 summary/detail 分支。仅在 summary 缩小 coverage 可保留 detail 原信息；未发现需要新增数据库字段或恢复生命周期的理由。精确路径是 `recovery.coverage.omitted`，不是顶层 `recovery.omitted`。 |
| 阶段与回滚 | 各项有定向负例、信息完整性检查、可撤回的展示/推荐入口和旧对象兼容边界；S6 包含安装包与生成提示核对，不把旧 Workspace 视为自动升级。S2/S3/S5 用确定性回放足够，无需补跑求解器或为小投影建立科研验收链。串行/超限停止原则成立，具体模型资源入口按 B1 补清。 |

## 可选收敛建议（不阻断）

1. **S1 数字精度负例写具体。** 当前 `output_schema_reader.py:24、148` 使用普通 `json.loads`/`json.dumps`，只能复用安装方式，不能据此保证一般科学 JSON 数值无损。建议把超长小数、大整数、极端指数加入已有精确拼回测试，明确“精确选定值”是否保留数字原词形。全文模式可直接分页源文本；不要为不必要的规范化另造通用 JSON 框架。可变文件优先选择计划已允许的版本变化报错并重新开始，避免引入快照管理子系统。
2. **S2 将现有明确消费者写进实施清单。** `analysis_workspace.py:243` 的 `--command cat analysis-start.json` 示例应明确 raw 或改为定向原文读取；`test_local_process_observation.py:123–140` 当前断言 stdout 恰为 LOG_LIMIT，需要区分新 summary 与 raw 的预期。对 `policy="inherit"` 单独验证原有直接转发/退出行为。摘要内错误引用应保留已有脱敏规则，不以“精确原文”为由回显未脱敏机器路径。
3. **S5 校正字段名。** 第 132 行的消费盘点应写 `recovery.coverage.omitted`；现有通用 detail 入口已经足够，若实现没有新增缺口，不再增加专用详情接口。未知/历史字段不应推断出“完整”。

## 复审边界

未发现需要阻断的 S1—S5 职责设计或科学权限退化；唯一阻断是两项关键真实模型验收的实际入口未落实。修订 B1 后可定向复核该条，无需重做全链审查或穷举新异常。计划通过仍不代表源码、安装、真实行为或研究目标已经验收完成。
