# N5/live02 全候选池独立证据审查

结论：PASS，限冻结保存候选池的隔离事后评分及描述性统计。审查者 /root/n0_baseline；未编写被审脚本、未执行预测/训练/模型、未改原实例或生产代码，未占测试锁。

## 冻结范围

外层 .trial/n5-live02-pool-eval-20261011/。manifest SHA256 845ccab03e1e2a36af295a759e350fbce7a7f00fa2c9a4b9cb55175a58c3bc07；evaluate.py 78e6f43b36624100025958c246155192ac13057771ac585fdfdf970e91d8adb2；report.py 4294cde2a0cadb8e08d96b604dcb55bfed7273ca2a1cf1d8ca8d96ba3fd51842；REPORT.md 18f3c2d7f84148ab4e7d9de0cfb41aecdddbd36ddb5b2e4dca50a6abcbd4a07a；final-summary.json ad19466e0550e332717c7fecad8cb1cc741dc1dbdf595e63927bde98408f775f。

已追踪 evaluate.py 的 audit_map、原池保存模型快照、官方 verifier RUNNER、bwrap 映射、run_tests guard、source before/after及report平均并列秩/选择损失。官方 verifier _predict_isolated 保留，预测/反序列化走官方隔离边界，评分观察 wrapper只捕获原_score；未训练、不反馈角色。原有官方隔离本身的安全能力不是本审查重新证明的任意恶意pickle保证。

## 独立只读核验

- manifest哈希/评估脚本哈希、全部冻结verifier和runtime_files哈希一致；两个源实例before/after哈希映射完全相同。
- 全92条候选ID唯一：N5 50/live02 42。全部原模型及独立快照哈希一致，每条hidden.json与candidates统计值一致，全部resource returncode为0。
- 原台账哈希和逐候选已有audit来源SHA一致；actual submitted_model与候选N5 run17/live02 run42哈希相同。全部audit missing snapshot leakage_flag为null、official_reward为null，无编造false。
- run19：audit_missing，hidden_recovery=0.6775303170210535，conditional_reward=0.7248，official_reward=null。官方函数在null元数据下产生的verifier数字不能冒充已审计正式候选成绩。N5历史记录审计池best是run17=0.2172；live02池best是run30=0.506。
- 独立实现平均并列秩并重算相关：N5 val/hidden0.6087165369842712(n50)，live02 0.2909253032017031(n42)；val/conditional reward分别0.600706738490837及0.28501943523376405；val/recorded-audit reward分别0.7719729489736509(n20)及0.28501943523376405(n42)。pooled hidden0.4496036810108389、conditional0.4425259753300453、recorded-audit reward0.4662124828441665(n62)，均与final-summary一致。并列公共分数使用原台账舍入值。
- 选择损失直接重算与显示一致：N5 run17相对条件池best0.5076但相对记录审计池best为0；live02 actual42相对best30为0.0855。它们是事后池内比较，不是科学作者能合法使用隐藏信息选择后的成绩。
- 结构化推荐raw SHA与ID逐项核对；N5最后非空为历史A013/run34，最新A016为null，原科学正文保留run17，未伪造当次结构化推荐。live02旧A006正文保留run42，与structured推荐分栏。

## 资格/归因限制

N5只有20条已有completed nonleakage audit记录，30条缺审计；live02有42条已有记录。除了实际提交模型/receipt配对，已有honesty audit未以加密hash绑定其另拟合audit模型和当前保存pickle。本PASS只承认报告披露的“recorded completed audit”层，不升级为新的独立模型审计或补发科学资格。

评分低于passband的AssertionError仍有正式评分数字，是已评低分；运行/缺模型异常另计。当前92条均有评分，不据未来脚本容错推测成功。候选相互依赖，pool最高只事后上界，不能将92条当独立框架重复样本，也不能将高选择损失唯一归因于HWA/树结构/压力评估。两池相同公开条件已核对，但历史协议、过程、预算及采样差异仍限制因果比较。

隐藏池结果只能开发诊断，不进入原场角色/调参；任何由已见隐藏池开发的选择规则须标开发性回放，不称独立验证。没有额外真实恢复、预算扩额或外部提交。未重复92预测。
