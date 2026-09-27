# 已登记路径修复后：原生 E 两轮测试

2026-09-19。固定 B/C/D 协议，sol/medium，新 Worker 首轮、同 Worker 接续，串行、每轮 600 秒及一次预算，无 TCAD。已确认绑定 M7-test0、实际模型及安装源码一致。两轮输入原始字节、编译 Operation、科学角色、指令和语言与 B 一致。

| 指标 | D | E |
|---|---:|---:|
| 初始输入 | 21,595 | 21,595 |
| 首轮峰值 | 53,358 | 52,693 |
| 首轮净增长 | 31,763 | 31,098 |
| 接续净增长 | 9,329 | 9,301 |
| 整体峰值 | 62,789 | 62,097 |
| 整体净增长 | 41,194 | 40,502 |
| 请求数 | 37+10 | 36+8 |

整体峰值较 D -1.10%，较 B -16.67%；接续净增长较 D -0.30%，较 B -39.78%。一组结果只支持收益未明显回退，不能证明 1.1% 差异稳定或全部由路径修复产生。E 主要用端口名读取绑定材料；原四个已登记路径的兼容由安装版本定向 CLI 验收证明，不能将未重现误用等同于实际经过该分支。

两轮 completed、提交拒绝均为零，科学 verdict 均 revise。Root 读取封存 summary、verdict、global_confounders、next_actions、hypothesis_reviews 及 scheduler_signal；总体目标和限制仍保留，第二轮独立挑战参考审查的停止所有后续研究建议，并要求新设计先获得具体实现合同。E1 identifiability=pass 使用较窄的冻结实现可检验解释，E2 为 fail；这说明报告仍有语义波动，不能将 token 验收当成独立科学质量认证。

首轮两项读取错误：assignment.json 未加 --file，返回 input missing or ambiguous；对 user_context 纯文本执行 --directory，返回 JSONDecodeError。二者不属于本次新增的已登记 relative_path 匹配范围。接续收到 reading_guidance，无角色正文或 Schema 重读，无 reader 错误。首轮 role_read_replies=2 包含失败调用，不能解读为两次完整角色正文重读。未观测到工具截断或 context_events；原生硬内存限制仍不在覆盖范围。

本轮不修改生产代码、不重试挑选结果。上述两项易用性问题保留为后续工作。

证据：[E 目录](evidence/registered-path-native-20260919/)，包含环境、两轮完成记录、逐请求数据、任务边界、B/E 原件对照、D/E 与 B/E 比较、读取行为元数据。原生线程：01a0b869-f3a1-72c2-adcc-603f2dec8196；Run：worker_context_ab_E_review_20260919_1、worker_context_ab_E_review_20260919_2。
