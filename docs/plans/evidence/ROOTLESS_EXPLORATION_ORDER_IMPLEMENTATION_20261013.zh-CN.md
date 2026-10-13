# 科学探索次序的冻结与执行

状态：实现冻结、独立源码审查通过、父代理安装验证完成。本轮未启动真实科研模型，未改已运行实例，未跑全量测试。

## 合同与边界

- 新 prepare 显式 `exploration_order_version=1`，CLI `--exploration-order` 同时要求显式 `--portfolio-review-after-cycles` 的 v2 策略，冻结协议13。无开关/retained job继续自身≤12合同，旧 settings/schema/job/视图字节不补字段。
- H 新 commitments 的声明顺序明示为科学探索优先级，在 scope 说明判断依据；新条目尾入，已有身份改名不重排。H/A 只新增一项 nullable `exploration_order={priority:[最多4个机制ref或唯一label],reason}`，是科学优先前缀及理由，角色不填写控制计数、路径或哈希。未列的未完成尾项保留。
- 机会条目与机制寿命分开：screened 不代表永久不用，deferred 不自动删除；waived 需原科学理由才移出队列。完成机会后，继续深挖同机制可显式带理由重新排前；不强制逐机制实验。
- 控制检查 H experiment 和 A continue_w 的 focus 等于确认队头。错身份、重复前缀、空理由或冲突保留原科学结论和合法状态变化，经原有最多两次作者补正，不静默修改科学请求。单次排序错误不立即终止；补正耗尽仍按原 `semantic_correction_required` 收住。新13以确认次序替代旧“任何 pending 都不能 improve”；H授权、精确修复来源、额度和未知执行边界保留。
- 队列只由封存原件及现有 search.fold 重建，无持久队列账本。W任务冻结原机会 `{mechanism_ref,planned_step}`；消费先于当轮前缀。共享现有 W step+seal 的合格科学评估/seen_w，不按工具调用或候选数计数，不以同名 ref 弹出新插入机会。科学评估合格但排序错仍消费原机会一次；作者补正只修排序。
- 同队头 repair 保留原机会。失败、未知和未评估 W 不消费；修复后合格 A 不再请求同 repair 时完成原机会，或作者带科学理由改方向。仍有原修复名额及精确来源边界，不自动把修复升级成新科学排序。
- A audit/extract/wait 不消费或改序。H可以先在科学计划确认次序，再 extract 或 wait；这不消费 W 机会。E自身不排序，返回 H/A 不丢队列。A→H→W、重启及同节点续接保持原确认次序。
- 有效 A 改序 reason 同时承担本轮 portfolio 取舍说明，无须重复写 portfolio_review；旧12语义不变。控制只核声明存在和身份/次序，不判科学理由质量、不自动排名。
- finish、wait 和 closeout 不强迫清空队列；closeout 不消费/清除未完成项，实际 lineage 输入仍给出有界未完成概览及完整只读索引。

## 输入与检查

无新长指导文本。新 schema 描述与实际 science-task 的 lineage order 提供合同；A所见队列在当前评估之前，正常评完原W机会后先消费，再应用科学优先前缀，continue_w选择所得队头；同队头repair保留机会。H experiment选择所见确认队头。默认头、最多四项、总项数/遗漏数及完整16项分页仍在原4096字节总包内，原控制身份不投递。科学算法、分叉、判别及验证设计仍由 W 在用户/H约束内决定。

修改六模块：search、semantic、contracts、controller、cli、lineage。新 `test_exploration_order.py` 覆盖真实 H/A作者补正派发、深挖已筛分支且其他仍pending、原机会消费/重新插入身份、audit/E、修复、部分科学保留、A→H→W、H先排序再E、旧12原件/门禁、完整20机制导航和页损坏。测试/安装/提交由父代理执行；独立审查者不参与源码作者工作。

父代理分批证据，不能相加当作不同用例总数：

- 首次源码143例通过，62.35秒（新增13、旧130），`.trial/exploration-order-source-20261013/batch-001/pytest.log`。核心规则与最终版本相同。
- 仅收窄视图文案，明确显示队列在A评估之前，并在原真实路由用例补断言；最终相关27例通过，9.20秒，`.trial/exploration-order-final-view-20261013/batch-001/pytest.log`。未改变控制规则。
- 最终新wheel安装54例通过，28.90秒，`.trial/macro-role-installed-20261012/artifacts-order-final-20261013`。实际CLI显式开关冻结协议13；default H→A→W→A 和 restart无重派通过。实际site-packages导入检查及22模块 source/wheel/install 字节一致。wheel SHA256：`7738ed6ba1bc8cd31f6ff7dded7d888f1759bc2ee83a19a480026094960f397b`。

上述仅为控制合同、原件/恢复边界和零模型假过程验证；不宣称真实模型已按排序探索或科学选择质量提升。
