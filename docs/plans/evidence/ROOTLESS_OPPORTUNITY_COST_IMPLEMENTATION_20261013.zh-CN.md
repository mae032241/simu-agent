# 长期未执行机制的机会成本复议

状态：实现与源码/安装门禁通过，独立最终审查 PASS，证据已归档；本轮未运行真实模型。

## 冻结规则

- 新 prepare 显式启用 `portfolio_policy`，冻结 `version: 2`，产生协议12；CLI 仍使用 `--portfolio-review-after-cycles 3`。不启用不改变合同。
- 已有策略缺 `version` 仍是 v1，协议11继续采用原同分支累计规则；旧 settings、job、schema、视图和已冻结指导不重写。显式 v1 输入保留旧存储形状。
- v2 复用已承诺 H 机制的 pending/deferred 状态和实际 W→A 周期。当前选择若是逾期机制，可以继续；否则任一其他机制延期达到阈值时，A `continue_w` 需要既有 `portfolio_review` 的非空科学取舍说明。允许说明后继续原方向，不要求各机制逐一实验，不判理由质量或科学排名。
- P→Q→R 不会清除未执行 S 的延期。已完成 W 以 step+seal 身份只记一次；audit、E、wait、作者补正与重启不增加周期或刷新窗口。复议只清派生窗口，保留绝对已消费 W 身份、机制身份及原预算。
- 门控范围是 **A continue_w**。A revise_h、H experiment 保持科学路由权；回 H 不抹延期事实，后续仍显示原机会成本。本版不宣称阻止所有 A→H→W 绕行，不新增 H 机械声明。

## 实际角色输入

新版 H 指导要求科学排序、目标缺口、代理可见性、最小改变决策的试验和机会成本；W 先短步判别，再随观察 draft/improve/repair/backtrack，明确负结果及时交 A。必要核验、独立审核和原文数量要求保留；不规定算法、网格、硬时限或科研比例。

`guidance.DEFAULT` 原1822字节不改。新 `OPPORTUNITY` 全四角色1843字节，保留200字节域增补空间。prepare 仅在传入内部 canonical DEFAULT 对象时切换新版；任意自定义 literal 原样冻结。新领域配置应显式用 `OPPORTUNITY` 再增补工具用法，不能宣称启用 v2 会强改自定义提示。新 schema/view 仍提供必要门控说明。

实际统一 lineage brief 继续合计≤4096字节。默认最多四条机制概览，遗漏数和完整只读分页入口保留；已完成周期与待评 W 的预计贡献、预计延期分栏，不能把 pending 当完成。原科学输出字段保持，协议12只冻结新的既有字段描述/投影语义。

## 修改与验证范围

生产接缝：`search.py` 策略/门控/派生视图，`contracts.py` 新协议选择与 schema，`semantic.py` 版本白名单，`lineage.py` 紧凑概览，`controller.py` 新 literal 冻结，`cli.py` 入口说明，`guidance.py` 新短指导。无新状态账本、模型字段、搜索器或辅助代理。

旧 `test_portfolio_review.py` 显式 v1 保留原断言；新 `test_opportunity_cost.py` 覆盖跨分支延期、逾期机制可选、合理维持原路线、有界作者复议/再次到期、真实 audit/E 返回、H 改名/省略不清账、待评/事实分栏与页损坏、协议11原件重建、新任务 literal/域增补和自定义权限保留。测试/安装/模型执行由父代理负责。

## 父级门禁记录

- 既有8文件118 PASS / 43.76s，保留旧协议、搜索、lineage、semantic、decision、guidance、native CLI与schema回归。
- 新文件+旧portfolio+guidance首轮30 PASS / 1 FAIL：测试错误要求默认brief始终四行；实际合法按4KB裁剪为三行。生产未变，仅测试改为最多四行、显式遗漏、逾期S可见、完整索引四行和事实/预计计数准确；精准复跑1 PASS。首轮失败证据不删除。
- 分批源码共覆盖130个不同用例，不宣称单次全套通过。证据分别在外层 `.trial/opportunity-existing-20261013`、`.trial/opportunity-new-20261013`、`.trial/opportunity-brief-fix-20261013`。
- 最终fresh wheel及全新venv通过既有安装CLI H-A-W-A/重启不重放检查；实际新CLI prepare冻结version2/protocol12。已安装包专属41 PASS / 21.76s，9个直接检查模块确认为site-packages且SHA与源码一致；全包22个loop模块绑定检查一致。
- 安装证据：外层 `.trial/macro-role-installed-20261012/artifacts-opportunity-final-20261013/`，包含result、opportunity-installed.log、opportunity-installed-result.json、cli-instance与wheel。
- 最终wheel SHA256：`be3e0cc8581902416bf484c3bc68a8577d1120a3f64fe06d2f0888dbca40caea`。
- 未跑全量测试、真实科研模型、浏览器或TCAD；本次证明合同/视图/路由接线，不能证明探索排序或目标分数提升。独立审查见 [评审记录](ROOTLESS_OPPORTUNITY_REVIEW_20261013.md)。

前置真实场证据见 [组合复议首场](ROOTLESS_PORTFOLIO_LIVE_20261013.zh-CN.md)。本版只对新显式v2实例补足跨分支机会成本规则，不改写该历史运行的未触发结论。
