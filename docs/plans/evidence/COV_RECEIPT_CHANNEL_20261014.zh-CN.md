# cov执行日志与回执分离

状态：修复及定向验收完成，独立复审通过。基线 `c395ed3`。

## 真实场证据

场次位于外层 `.trial/rootless-worker-task-cov-20261014/`，模型gpt-6.1-sol high，单场额度600万token/60分钟。约19分钟后A005选择wait，实际用量1,734,985 token，非缓存输入加输出269,001。仅1次正式实验，run1公开验证分0.896。本场没有实现四机制浅筛，不能算通过。

W002首个受管调用的terminal原件：退出码0、transport_complete=true、cleanup_confirmed=true。stdout含4503字节前置日志及末尾正式JSON，末尾JSON与公开results.jsonl中的run1逐字段一致。然而cov_lineage._receipt与_completed都要求整个stdout是单个JSON，导致completed.status=unknown。未知原始执行阻止剩余三个机制准入；W004重查未解除，A005最终等待。控制层的防重放规则确实触发，根因是领域适配器将日志误当机器回执。

## 修复范围与通过条件

- 日志与机器回执独立通道；不从stdout尾部、日志中的JSON或最近台账条目猜调用归属，不要求模型禁止打印。
- 独立回执绑定确切call、accepted原件和source；仍核对台账、run_id、模型原件、终态及清理状态。
- 冻结公开题目/runner文件保持原样，只由领域适配器连接其正式产出点。共用执行控制层不引入cov科学判断。
- 回执缺失、错身份、重复或损坏仍保留unknown/完整性错误，不重放。正常训练失败保持known_failed。
- 用真实公开runner进行零模型回归，包含日志和伪JSON日志，验证第二个机制仍能准入；另测缺回执、篡改、查询只读及安装隔离入口。

旧真实场原件只读保留，不热改completed或重写资格。新真实模型场需在修复验收后单独启动；本次修复不宣称已改善得分或token效率。

## 实现

- `cov_receipt.py`是领域适配器的独立回执传输。真实通道冻结公共CLI和runner的原件及正式输出点，从runner自己的最终记录对象发布`receipt.json`；不解析训练日志、不修改公开题目。测试后端显式声明文件回执通道，没有自动降级。
- 独立回执绑定call、accepted与source哈希。完成判定和事后读取共用此绑定；stdout/stderr只作为日志原件。
- 读取器按独立脚本入口使用绝对导入。谱系证明上限从8到9，容纳回执、日志及完成原件；共用执行器和角色协议未改变。

## 验收记录

所有运行由父执行者在共享串行锁下完成，未调用模型或隐藏评分。证据位于外层`.trial/`：

1. `cov-receipt-source-01-20261014`：96通过、7失败、1跳过。暴露假后端通道漏接及候选投影问题。
2. `cov-receipt-source-02-20261014`：103通过、12失败、1跳过。新回执读取器的相对导入不能用于独立观察器脚本入口。
3. `macro-role-installed-20261012/artifacts-cov-receipt-01-20261014`：安装CLI通过；安装回归109通过、13失败、1跳过，确认该问题确实存在于安装入口。
4. `macro-role-installed-20261012/artifacts-cov-receipt-02-20261014`：绝对导入修复后，安装CLI通过，10文件回归131通过、2失败、1跳过。剩余两项是负控准备错误：只读源码尚未成功篡改，以及伪造父绑定被新回执绑定更早拒绝。修正夹具以到达原校验点，保留拒绝断言，没有放宽生产判断。
5. `cov-receipt-public-smoke-01-20261014`：真实公共runner、公共train/val数据、实际Ridge训练，两机制P/Q均known_success；日志分别866/865字节，含伪JSON记录。W封存、两候选谱系和只读复查通过，公共原件哈希不变。该脚本可由`scripts/acceptance/cov_receipt_smoke.py`复现；不包含真实模型H/A或科学方向有效性判断。

6. `macro-role-installed-20261012/artifacts-cov-receipt-final-20261014`：保持同一安装包，两个修改过的负控测试文件复测23通过。结合第4批未改动的通过项，最终覆盖10文件、133个通过用例、1个不适用跳过；这不是一次全绿批次，更不是全仓测试。namespace真实进程入口包含7例，均在第4批通过。

生产冻结清单`/tmp/scid-cov-receipt-production-03.json`对应五文件；安装包SHA256为`2f778e3c361ae32e58bb437f6bdd83f2300becfce8d249806e2af9ef03d52f99`。独立复核见同目录`COV_RECEIPT_CHANNEL_REVIEW_20261014.zh-CN.md`。

未跑全量测试、真实模型新场、隐藏评分或TCAD。旧场仍保持原终态，不以此次无模型验证代替广搜效果验收。
