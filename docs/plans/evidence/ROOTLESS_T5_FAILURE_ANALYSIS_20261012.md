# T5 H001 独立失败诊断（只读，2026-10-12）

## 结论

本场停在第一个 H：原冻结 H 单节点 420 active 秒到限，native returncode=-15、stop_reason=node_slice_time_limit，控制记录 advance_seconds=420.4141；driver wall=422.191。无封存节点、无正式 exp run、无提交。没有源码封存 bug、schema 400、原件失配或权限故障的证据。硬上限按冻结规则执行；失败是本次 H 工作范围扩展、产出收口顺序与 420 秒配置组合未完成，不是仅凭“七分钟失败”就可称代码 bug。

已形成方向草稿及可用局部诊断，但没有最终科学 JSON、turn.completed、science-output.json 或 result-identity.json；稿件不能冒充已封存 H，不能据此派 W。本诊断未修改实例、源码、预算或判据，未恢复/测试/调用模型；未读隐藏评分或旧答案。

## 1. 真实预算可见性与计量

- science-task.json 为 3,130 B，里面没有预算字段；这不表示 H 看不到预算。
- exact native session 的用户启动 prompt（06:51:56.798Z）确有 shared_seconds_remaining=3599、shared_observed_tokens_remaining=6000000，以及 node_budget={max_observed_tokens:500000,max_seconds:420}。实际安装 native.py:153–171 把这些字段发送进 stdin，契约确已可见。
- 同 prompt 要求“有决策相关贡献就收口”、由 host 采集/封存；没有节点软收口时点、实时倒计时或到限前通知。可见额度不保证模型在硬停前完成 final。
- native.jsonl 没有 turn.completed，控制 usage.observed_tokens=0 且 unknown_steps=[1]；这是未观测，不是零成本。
- 父代理独立追到同 session 的最后 token_count：06:57:49.918Z，input=209783、cached=173440、output=7709、total=217492；非缓存输入+输出为44052。该数是终止前的最后原生累计报告，不是终态 completed meter；最后在途成本仍未知，未用于退款/改控制预算。
- UTC events 首尾相差约389.608秒，而 driver monotonic 为422.191秒、节点 active为420.414秒。下表只用 UTC 表示次序，不能将 UTC 段差当 active 计费或精确归因占比。

## 2. 可观察工作顺序

| UTC（本地时间再加8小时） | 可观察工作 |
| --- | --- |
| 06:52:09–06:52:49 | 读任务、objective；发现工具；枚举 inputs/公开目录/AGENTS；读 exp brief、meta、runner、instruction |
| 06:53:18 | 指出题面50维与实际40维、IID句与shift目标冲突，宣布局部压力诊断 |
| 06:54:06–06:54:33 | 写并运行第一版 forward/OMP/ridge/合成shift诊断，读结果摘要 |
| 06:55:12–06:55:51 | 加信号能量、拟合不确定性、mismatch-aware stopping，重跑并读结果 |
| 06:56:27 | 已明确优先 mismatch-aware stopping，保留竞争机制 |
| 06:57:26 | 写7,662 B scientific_direction.md，再核表格 |
| 06:57:49 | 最后原生累计token报告；之后无最终科学输出 |
| 达420 active秒 | TERM、group清理确认、native_stopped；未自动重发 |

native公开事件包含15次 shell 命令、3次文件变更、3条进度消息。9个 exec cell 的 UTC调用/返回跨度合计约5.624秒（非完整进程CPU计量）；最终诊断自记运行0.66754秒。第一轮异步启动/后续收集也成功，没有卡住计算或长期等待的证据。绝大部分节点活动时长位于模型侧生成、请求间隔及工具编排/结果处理；不能进一步从这些间隔证明具体推理耗时或后端延迟。

## 3. 阅读与机械事务

必要公共阅读包括 objective、meta/runner 的实际输入和审计约束。确有少量重复/额外开销：

- objective与公共instruction分别完整读取，各7,778 B，内容相同；runner整份6,697 B、meta4,280 B、brief2,501 B。
- 枚举工具元数据与三次文件/AGENTS发现；无AGENTS的rg退出1，此后继续，未形成权限故障/修复循环。
- 已完成 shell 命令回显合计约46,193 B（不含其他工具元数据/调用结构）。两次诊断摘要分别4,903 B、7,556 B，增加后续模型上下文。
- 这场没有手填hash、历史账本、分页拼接、祖先附件复制、manifest/包装脚本或schema验证器。目录仅按已有 work/artifacts 约定使用。因此不能把失败主因描述成“机械交接维护耗尽七分钟”，也不能把上下文成本全部归给3.1KB science-task/lineage。

## 4. H 科学范围

H 做出了真实局部研究：训练集forward最小二乘、OMP每行最多20步路径、多个gamma/floor、4个ridge控制、2个seed×4个人工shift场景，并在第二版扩展能量/估计误差诊断。这些是 scratch 科学检查，不是经managed exp封存的候选或官方实验，不计25-run目标，也没有公开审计或目标泛化资格。

功能上，H已承担了类似W的方法实现、筛选和多场景消融；不是只提出机制与最小判别设计。已有角色合同允许探索和科学检查，不能据此断言它违反权限；但该范围和长篇方向产出使“先完成一个可派W的H final”被推迟。06:56:27已有决策，随后写7.7KB稿和表格核验，而最终7字段科学JSON仍未提交。稿中无错配adaptive列与最后table check输出还有数值不一致，说明稿件亦不能直接作为已核结论。

H稿明确留有未知shift、标签不可识别、validation比较和人工扰动局限，未冒称目标完成。没读隐藏数据的证据；这里不评其最终科学正确性或预测质量。

## 5. 为什么未封存

实际安装 native.py:284–310 在 stop非空/非零退出/缺completed用量时写原outcome并拒绝verified terminal；只有随后311–315才将成功pending final换成science-output。contracts.py:680–702还要求原intent/输入完整性、最终raw、returncode0、无stop/unknown用量及raw SHA一致。

本场在前一条硬停路径结束：没有最终JSON可供封存。runner.stderr中的“preserved without replay”符合该事实；controller的native_stopped及ValueError只是未能封存后的上层状态，不能反推一个schema/机制引用校验 bug。正确保留了失败意图、native事件和草稿，未把草稿补造为成功。

## 6. 最小后续方向（本次不实施、不重跑）

- H优先给定性竞争机制和最小判别设计；方法实现、参数/压力筛选交W。在已有方向稿/决策时先交小final，避免继续完整研究报告导致没有H交接。
- 节点资源配置应与真实模型生成/收口行为共同验证；增加额度本身没有因果或收益保证，不能暗改本场授权。
- 若加入收口提醒/保留时窗，应验证实际可见与final完成路径，不能以强杀代科学封存。运行中原生计量及同线程续接在该launcher仍未取得真实资格，不硬恢复本失败。
- 保持原件和未知计量；本场不自动重跑、不伪报正式实验/科学完成。

## 来源核验（SHA256）

外层来源均为本T5场，只读；native/session原文未复制到报告。

- native.jsonl：cbbe49e63a80c9f3250694b3decd4f876bacb7fe3f101a802fe82c3fee6d5b00
- native-intent.json：9eb8758387b8b81449e32ed309517649e01a3ce64e123c873f91913e7ab90145
- native-outcome.json：da4ad3f177dd6fb7b7be7f95155a227a7620f20362a0397a37d421dc8e65d2d1
- science-task.json：045df05a31327d4d31225b8df5ccd7800cf7c088ee0b1af973cce41c60abcbaf
- direction_diagnostics.py：d39ee3e114596366d48f5bcfb4476b1876eae31ec8dbcceaf6d7895a4ea7b272
- diagnostics.json：9ffbbfa8fdba2fff7df72dc1d776f78f527133ee3e1472c2cd56fdf16ba20626
- scientific_direction.md：32c8a32a364d52a2fe9b0b2c3d0741e1f52737972632dafa159a8678df4cb3c4
- exact session（父已匹配/归档digest）：23090c05af08e0bf125406ffce187022ae39eadd127cc3e3f9d07a8e3aa8e266
- postmortem-native-usage.json：0feeb7fb5d8ad6f29b5e7986f9b6e294e273c5308a4dcf77a4feaaff8eac253c
