# 输入等价接续导航：原生 G 验收

2026-09-19。已部署，固定协议两轮完成。功能导航正确，本次消除了F中的旧输入重复展开；token恢复至D/E附近，但没有证明稳定优于此前较好版本。未进行额外独立实施复审或重复抽样。

## 方法

同B/D/E/F协议，sol/medium，新Worker首轮、同Worker接续，串行、每轮600秒一次预算。原始输入字节、科学角色、编译Operation、指令和语言与B一致。安装mcp_local_worker.py及平台生成器与源码一致。原生硬内存限制未覆盖。没有执行TCAD或中途调整任务。

## 结果

| 指标 | E | F | G |
|---|---:|---:|---:|
| 初始输入 | 21,595 | 21,595 | 21,619 |
| 首轮峰值 | 52,693 | 52,991 | 53,970 |
| 接续净增长 | 9,301 | 25,519 | 10,310 |
| 整体峰值 | 62,097 | 78,617 | 64,393 |
| 整体净增长 | 40,502 | 57,022 | 42,774 |
| 请求数 | 36+8 | 37+24 | 34+9 |
| 接续工具回复字节 | 14,572 | 68,535 | 17,997 |

G整体峰值比F下降18.09%，接续净增长下降59.60%；相对E整体峰值增加3.70%，接续净增长增加10.85%；相对B整体峰值下降13.59%。不能只选择较差的F基线宣布全面成功。增加指引和生成提示也有成本，初始输入增加24 token；各组单样本仍有策略与写作波动，不足以隔离全部因果。

G2的open实际返回五个unchanged：experiment_plan、research_objective、execution_context、result_analysis、user_context；current_progress为new。角色、工具合同、Schema列为条件复用，明确提示未变不代表记忆。本轮实际只读新assignment及新参考审查，没有用reader再次展开五份旧输入；角色/Schema也无重读。两轮读取器错误、Schema错误和提交拒绝均为零，未观测到工具截断或context_events。

## 交付边界

两轮均completed、scientific verdict=revise，Root阅读了封存summary、verdict、global_confounders、next_actions、hypothesis_reviews和scheduler_signal。新参考审查得到实质评价：停止原六案与关闭总体目标被区分；保留数值/物理机制差别、联合不确定度、尾区和InAlAs限制。这是封存交付检查，不是独立科学复算或科学质量完全等价认证。

## 结论与下一步

本次部署功能验收通过，提供了一次减少重读的正向轨迹。尚未证明多轮稳定收益；后续应保持原件/总体目标可访问、上下文丢失时重读、未知绑定回退，不新增记忆校验或强制跳读。若做稳定性评价应预先固定重复次数，不选择性重跑。本轮不追加测试挑样本，不改源码。

证据见 [G目录](evidence/input-guidance-native-20260919/)：native_G_environment、逐请求记录、边界、完成记录、summary、B/E/F比较、原件一致性、visible_guidance、reading_behaviour。线程01a0b89b-fc02-75a0-8653-0e3286df2e7d；Run worker_context_ab_G_review_20260919_1、_2。
