# 实例执行配置实施记录（实现与隔离验收完成）

按精确 R1（SHA256 见 CANDIDATE_R1.json）实施；P0 与计划 R1 独立审查已通过。未部署、未提交 Git、未操作生产状态、未重算 Fig.4。实施前已有大量 UI 改动，审查应使用 BASELINE.json 与 IMPLEMENTATION_DIFF.patch，不能把 HEAD 全量 diff 归入本轮。

## 已实现

- 一个配置解析器；公共文件启动加载、实例稀疏覆盖、CAS 与维护锁；四个新增字段。
- 预检 normalized_request 冻结模型/推理/语言和既有预算，invoke 原样复用；恢复仍继承来源预算，不把继承值变成显式延长授权。来源说明不进入行为指纹。
- 同一编译角色动态分发；语言只进入新 assignment，不增加输出校验。两种 Worker 后端读取冻结语言。已适配旧 CLI launcher 和两个 live probe 消费点，未创建模型角色池。
- 实例配置表单、来源、任务覆盖、只读/CSRF/Origin/CAS；Run 页面显示“请求配置”，历史未记录不回填。
- 旧归档仅四列受限投影，原文件不变、NULL/0 默认；预检/事务/故障后续接一致。
- 安装首次创建 agent-settings.json，升级保留，纳入原事务；控制/UI 同路径。无需 VM 同步。

## 实际证据

- P0：独立 Codex 0.154.0 CLI 同角色 Luna/low 与 Sol/medium，均受控提交；固定模型角色反例证明旧 role 会覆盖 spawn 请求。见 P0_RESULT.json、P0_PLATFORM_OBSERVATIONS.json。
- 候选四 wheel 隔离安装：50 Operation/spec/Worker 合同逐项不变；Root 仅 preflight/invoke Schema 增加控制参数。见 CONTRACTS_BEFORE/AFTER.json、INSTALLED_PROBE.json。
- P6：两个独立实例、同角色/路由/digest，平台 turn_context 确认 Luna/low 与 Sol/medium；均 completed，中文与英文封存摘要分别生效。见 P6_RESULT.json、P6_PLATFORM_OBSERVATIONS.json。不是 Agent 自报模型。首次候选 CLI 有 models refresh 非致命超时，原日志保留。
- 实际旧 /opt 安装产生归档，新隔离安装恢复成功；旧成果和全归档散列未变，历史 profile=NULL，实例覆盖为空。见 OLD_INSTALLED_ARCHIVE_RESTORE.json。
- 浏览器：初次失败 Origin=null，精确定位新页面 meta no-referrer 覆盖已有 same-origin；仅改新页面 meta，未放宽校验。p6-browser-r2 实际 Chromium 保存成功，无 JS/HTTP 错误，412px 无横向溢出。见 BROWSER_RESULT.json、SETTINGS_MOBILE.png。

## 定向测试与失败追溯

每条命令、退出码、时长和自有进程树峰值均在对应 .json/.log 中；全部串行，512 MiB 守卫，无全量测试。

- 配置基础9项；两后端快照与提交联调11项，补充恢复快照/预算后13项配置测试通过；平台生成14项、旧 launcher 定向测试通过。
- 新 UI 2项及既有管理22项通过；安装首次创建、保留、symlink拒绝、两个服务同路径通过。
- 归档/续接/配置71项通过；四列新旧档正反例8项通过（含提交后中断恢复、无关列/索引/触发器冲突）。实际旧安装归档额外通过。
- p6-regression：39通过，两个既有失败：recursive_current 的 output_context_invalid、hardened_stdio 的 operation_runtime_unavailable。分别以冻结实施前源码复现，见 p6-baseline-failures-r1、p6-baseline-hardened-r2。首次基线运行遗漏 pytest 插件路径、第二次缺快照中未收录的 SQL 资源，已补齐未改资源后确认。未改无关生产校验或旧夹具。
- p6-final-focused：41通过，3个只读模型夹具缺新增可选属性失败；展示读取改为缺省 None 后 p6-read-model-r1 14通过。架构矩阵、页面渲染、归档全部通过。语言配置文件非UTF8错误现保留路径。
- 现仓库无技能提及的 scripts/validate_architecture_constraints.py 和 run_science_control_bench.py；执行现有 architecture_constraint_matrix，另以本地真实 stdio、实际 CLI、精确合同对照覆盖本轮边界，不宣称执行不存在脚本。既有 hardened stdio 夹具失败不作为成功证据；hardened 配置提交/恢复路径已有进程内定向证据。

以上是 R1 前验收记录；最终状态见下方。计划原文件保留审查时字节，状态以本记录与 plans/README 为准。


## 独立 R1 修订

R1 独立审查唯一 P2：旧空实例档恢复提交前中断，_migrated 比较原始墓碑导致安全回滚被错误拒绝。保留 R1 报告和复现/新档对照证据。生产修复仅 instance_archive.py 一行，复用已有 execution_settings_tombstone；未扩大迁移或状态边界。

定向回归9项通过；另用新/旧空档 × 数据库提交前/后4种情况确认：提交前可以回滚后重新恢复，提交后必须续接且成功恢复，归档散列不变。见 p6-empty-archive-boundaries。R2 精确候选仅改该行和此测试文件（CANDIDATE_R2.json）；后续独立 R2 已通过，最终包已重建，详见下方。


## 最终状态（2026-09-15）

[R2 独立复审](../../reviews/INSTANCE_AGENT_EXECUTION_SETTINGS_IMPLEMENTATION_R2_REVIEW.zh-CN.md) PASS，精确 CANDIDATE_R2 37项源码/测试散列保持一致。

- 最终四 wheel 隔离构建通过，8.258秒 / 93.18 MiB；28项本轮运行源码及部署导出文件与审查候选逐字节一致（FINAL_INSTALLED_MATCH.json）。三个开发 CLI/probe 脚本按既有发布策略不进入 release payload，工作树散列仍与审查一致；首次包匹配脚本尝试读取不存在的开发脚本已纠正并记录，不是包源码差异。
- 最终安装版 50个 Operation/spec/Worker 合同不变，25个动态角色，Root 仅预检/调用两接口新增控制参数（p6-final-installed-probe）。
- 从最终 venv 使用 -I、禁用源码 src pythonpath，执行新旧空档四项恢复边界全部通过（3.217秒 / 106.77 MiB）；测试夹具来自源码，框架来自安装包。
- 最终安装版 Chromium 页面保存通过，无 JS/HTTP 错误，412px无横向溢出（2.819秒 / 291.22 MiB）。
- git diff --check 通过。未跑全量测试；已披露的两个既有夹具失败未被改写或掩盖。

本轮实施与隔离验收完成。生产尚未安装；首次升级须按正常安装流程重启控制/UI并重新加载 Codex角色，之后实例设置动态用于新预检/Run，无需再生成角色。VM runner未改、不需同步。实际生产实例修改与正常科学任务新语言验收留待用户安装后；没有将合成小任务视为 Fig.4 或生产科研结论。
