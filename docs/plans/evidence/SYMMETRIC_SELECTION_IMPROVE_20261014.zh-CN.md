# 对称选择与改进任务职责修订（2026-10-14）

## 根因与纠正

基线 `32e4b08`。本轮公开轨迹中，A已承认新候选的条件改善及受保护条件下不劣，
仍以其目标适用性未知为由保留旧候选，却没有对旧候选的同类未知作对称比较。
本次修订不将任何隐藏分数、具体候选编号或目标算法加入运行规则。

此前将 `grant.extra_calls=1` 解释为 improve 单次实验硬上限是不准确的。
实际 breadth.admit 仅在其他机制仍有初始机会时使用额外授权；本地 improve
只有一个机制，因此不触发该限制。以真实 W008 冻结配置纯调用准入函数，连续
四次模拟均可准入，grant均为null；没有执行实验或改动原场。
证据：外层 `.trial/receipt-cov-c-rewards-20261014/improve-admission-check.json`。

W008实际按A的问题进行重复拟合与不确定性验证后主动交回。因此此次不调整
准入额度、计数、协议或预算；修改的是科学任务指导，避免把 improve 默认做成
一个候选的完整验证。

## 修订目标

- A对保留与替换使用相同标准，比较已观察收益、损失、证据适用条件与未知。
  旧选择没有默认优先权；不要求新候选先证明目标最优才能入选，也不强制选择代理最高。
- improve允许在既定H范围内依据新观察连续调整、回退和比较；validate针对具体
  决策缺口检验，不默认要求在每次候选改动之后全面重复验证。
- 必要验证、用户要求、审计、总预算、机械停止与未知执行保护保持有效。
- 新指引经既有冻结角色文本传递；既有任务及自定义指引保持原字节，不新增模型表单。

## 验收

生产只改 guidance.py 的 DEFAULT / OPPORTUNITY 中 A、W 四段文字；不改控制逻辑。
DEFAULT 2,342 字节、OPPORTUNITY 2,435 字节，加实际领域工具提示仍满足原 2,560 字节上限。

- 新 wheel 安装及实际 CLI / fake-native 检查 PASS，0 模型请求。
- 安装包既有定向集 scientific_guidance、breadth_admission、closeout_search_replay：
  **38 passed (16.19s)**；覆盖提示冻结、通用及 cov 执行机会/未知保护、收口一致性。
- 证据：外层 `.trial/macro-role-installed-20261012/artifacts-symmetric-guidance-01-20261014/`。
- 新增精确角色输入回归：**10 passed (2.02s)**。覆盖 DEFAULT / OPPORTUNITY / 领域后缀 / None回退 / 自定义原文、旧任务重建字节不变、通用执行层同一 improve 三次实际子进程调用、保留与替换都不被机械代理排名决定。
- 新测试证据：`artifacts-symmetric-guidance-newtests-20261014`。两批合计 **48 passed**。
- 独立复审见同目录 `SYMMETRIC_SELECTION_IMPROVE_REVIEW_20261014.zh-CN.md`。

未跑全量回归、真实模型、浏览器或 TCAD。零模型验收证明指导送达和现有边界未回归，
不能证明 A 已改变选择行为，也不能证明科学收益提高；这些仍需后续真实场验证。
