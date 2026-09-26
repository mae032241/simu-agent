# Worker 上下文原生 A/B：两组完成，收益分项判断

状态：A、B 各两轮正式提交均完成，均无提交拒绝。首次读取 token 未改善；复用轮与整体峰值在本对样本中改善。不能将全部修复标为 token 验收通过。

## 固定协议

使用用户已绑定的 M7-test0，仅执行 science.object.review.v1，不运行求解器。两组均 sol/medium、每 Run 600 秒、max_attempts=1，每组新 Agent，组内两 Run 同线程接续。第一轮中文，第二轮英文且新增固定的外部历史审查 current_progress。总体研究目标不变，因此不声称覆盖“总体目标改变”的行为场景。

[固定请求](evidence/worker-context-waste-20260919/native_ab_protocol.json)于运行前保存，B 必须复用其中两轮 inputs、instruction、execution_profile，只改 Run name 为 B。首轮同时用于 S1 阅读对照与 S4 的第一轮，避免额外一对重复研究。第二轮不绑定本次 A1/B1 的产物，新增参考始终为 fig4_agent_settings_smoke_review_20260919_1.output，避免科学输入随模型输出变化。

A 原生线程：01a0b762-17bf-7d00-b148-feb8de97a6e4。已通过 worker_identity 确认 sol/medium，两次 worker_attach 均成功。已核对 7 个安装文件全部匹配 before 快照，当前生成角色没有新 reader/hash 提示。扫描 199 个 Python/角色文件，额外发现 mcp_root.py 仅两处 Root 专属描述更新；不进入 Worker 合同，故不能把此对照推广为整个 Root 系统前后比较。

## 结果

| 指标 | A 第一轮 | A 第二轮（复用） |
|---|---:|---:|
| 模型请求数 | 23 | 13 |
| 首请求输入 | 22,502 | 56,394 |
| 输入峰值 | 56,285 | 90,824 |
| 轮内净增长 | 33,783 | 34,430 |
| 工具回复字节（原生记录） | 107,471 | 113,382 |
| 输出截断标记 | 1 | 0 |
| 提交拒绝 | 0 | 0 |
| 科学审查 verdict | reject | revise |

整个 Worker 共 36 次请求，初始 22,502，峰值 90,824，净增长 68,322。第二轮相对第一轮最后请求的增长为 34,539；此数与第二轮首请求至尾请求的 34,430 区分。没有观测到支持的压缩事件标记，但不能据此证明无任何平台裁剪。

两轮状态均 completed。第一轮判断原样重跑已完成计划缺乏价值；第二轮独立核对新增参考，正确使用英文，指出历史完成不等于新机制控制可立即交付。科学 reject/revise 是正常产物，不是提交失败。Root 核对封存 summary、verdict、global_confounders、next_actions、hypothesis_reviews；不以子 Agent 完成聊天代替成果。

## 可追溯证据

- [A 汇总](evidence/worker-context-waste-20260919/native_A_summary.json)
- [A1 逐请求](evidence/worker-context-waste-20260919/native_A1_requests.json)
- [两轮逐请求](evidence/worker-context-waste-20260919/native_A_all_requests.json)
- [两轮边界](evidence/worker-context-waste-20260919/native_A_stage_boundary.json)
- [A1 完成](evidence/worker-context-waste-20260919/native_A1_completion.json) / [A2 完成](evidence/worker-context-waste-20260919/native_A2_completion.json)
- [实际加载版本](evidence/worker-context-waste-20260919/native_A_loaded_version.json) / [源码范围检查](evidence/worker-context-waste-20260919/native_A_source_scope_check.json)
- [B 安装命令预检](evidence/worker-context-waste-20260919/B_install_preflight.log)：pass，95.62 MiB，2.3 秒；无安装或服务修改。systemd verify 同时打印无关 netplan 文件权限和 snapd RestartMode 警告，最终预检通过。

## B 执行与比较

B 原生线程为 01a0b789-3f00-7b72-9580-c07ca16108f1；重新安装和重启后，8 个安装文件匹配 after 指纹，生成角色包含 reader/hash 提示。通过 worker_identity 验证实际 sol/medium，再依次 attach 两个 B Run。请求仅改 Run name，任务、材料、语言和预算保持冻结协议。未复用 A 线程，未中途修改 B 提示。

| 指标 | A1 | B1 | A2 | B2 |
|---|---:|---:|---:|---:|
| 请求数 | 23 | 23 | 13 | 8 |
| 首请求输入 | 22,502 | 21,583 | 56,394 | 59,073 |
| 输入峰值 | 56,285 | 58,970 | 90,824 | 74,518 |
| 本轮净增长 | 33,783 | 37,387 | 34,430 | 15,445 |
| 工具回复字节 | 107,471 | 118,563 | 113,382 | 43,715 |
| 截断标记 | 1 | 0 | 0 | 0 |
| 提交拒绝 | 0 | 0 | 0 | 0 |

- 首轮净增长 **增加 10.67%**，峰值增加 4.77%。S1 消除本样本截断，但 token 降低目标未通过。
- 复用轮净增长 **减少 55.14%**。B2 的工具代码没有再次引用 role_instructions 正文，A2 仍将它纳入读取；同时其他已读材料的展开也减少，不能将全部差额单独归因于角色哈希。
- 两轮整体峰值 **90,824 → 74,518，下降 17.95%**；净增长 **68,322 → 52,935，下降 22.52%**。
- B 初始输入比 A 少 919 token，重启前后的平台启动上下文并非字节级一致。因此同时给出各轮净增长，不将启动差异全算作本次修复收益。

B1、B2 分别完成 reject/revise 科学审查，和 A 的 disposition 一致；B2 明确使用了新增参考审查并按英文交付。总体目标、原计划与既往已完成结果、数值/机制限制、后续行动边界均在封存结果中保留。Root 核对的是必要覆盖，不声称四份科学文本完全等价或已另做独立科学审计。

## 首轮为何没有节省

[读取包装计量](evidence/worker-context-waste-20260919/native_B1_reader_overhead.json)从真实工具回复中抽取了 52 个 helper 回复对象，仅统计结构与长度，不导出科学片段：

- 原文片段 UTF-8：60,730 字节；
- 元数据包装：17,864 字节；
- JSON 字符串转义额外量：3,365 字节；
- helper 回复对象合计：81,959 字节。

约 21.2 KB 包装/转义开销属于这一类 helper 回复，不是全部工具输出，也不是精确 token 归因。每字段/片段重复输出 source、sha256、version、pointer、mode、offset 等信息，并把正文再次 JSON 字符串化；按字段拆分较多时增加模型可见的机械内容。减少截断/补读未能抵消首轮总开销。这个问题在返回表示层，而不是需要新增科学校验或让审查者少看必要原件。

下一步应单独修首次读取的显示包装：区分模型阅读正文与机器解析的完整元数据，减少重复来源/版本展开，同时保留精确内容、分页定位、原件变化检测及错误可定位性。不要直接放大单次输出预算，也不要为制造收益删去审查所需证据。本次未在观察 A/B 后改生产实现，也未挑选额外试跑来覆盖该回归。

## 新增证据与边界

- [B 加载版本](evidence/worker-context-waste-20260919/native_B_loaded_version.json)
- [B1 逐请求](evidence/worker-context-waste-20260919/native_B1_requests.json)、[B 全部逐请求](evidence/worker-context-waste-20260919/native_B_all_requests.json)、[B 两轮边界](evidence/worker-context-waste-20260919/native_B_stage_boundary.json)
- [B1 完成](evidence/worker-context-waste-20260919/native_B1_completion.json)、[B2 完成](evidence/worker-context-waste-20260919/native_B2_completion.json)
- [B 汇总](evidence/worker-context-waste-20260919/native_B_summary.json)、[A/B 对比](evidence/worker-context-waste-20260919/native_AB_comparison.json)

一对样本提供方向证据，不是稳定收益率估计。未观察到支持的压缩事件，但不能证明无平台裁剪。native 硬内存限制仍未覆盖；模型串行，不运行 TCAD。零提交拒绝来自控制层正式诊断，不能扩写为所有原生命令绝无错误。

结论：S4 本场景的复用收益成立；S1 仅实现有界读取，token 目标仍需修正。日志和恢复摘要的独立离线收益不与本次百分比相加。总体目标变化场景、其他 Operation 类型及独立科学质量评价未由此对照覆盖。
