# 全局组合复议最小实现（2026-10-13）

状态：实现、父级分批源码门禁和安装验证通过，独立审查 PASS，报告已归档；源码与测试保持冻结。作者未运行测试、构建、模型或 git，未读取隐藏评分。

## 目的与科学权限

控制记录对已承诺机制的投入和延期，周期性要求 A 重新考虑全局组合。覆盖范围就是 H 已注册承诺；不新增“关键”布尔标签，不由控制评价科学理由或强迫逐个机制实验。A 可给简短组合权衡后合理维持原分支，也可换方向、回 H、请求证据或审计。显式 waive 使用原 dispositions 的非空科学 reason；控制不裁判 reason。

CLI `--portfolio-review-after-cycles 3` 显式启用，默认不启用；API `portfolio_policy={review_after_cycles:3}`。3 是工程复议频率，不是科学停滞阈值；测试使用2。启用要求已有 H commitment search 与统一 lineage1 展示，自动冻结 decision_contract1，新任务使用 protocol11。既有协议1..10 schema、任务与投影保持；缺策略的旧实例未来节点不升级。

仅 A 增加 required nullable `portfolio_review:string`（≤1024字符），为简短科学权衡；不要求填写计数、ID清单、原件或整张机制表。正文无需控制台账。

## 计数、触发与清账

- 单位为实际封存 W 身份（root step + seal）及首次合格的后继 A 判断。相同 raw 的不同 W 仍是不同投入，同 W 多个 continuation 不产生新周期。
- audit/extract/wait、E节点、作者补正、查询和重启不另增周期；audit/E 后 A 仍需实际直绑该 W 才消费原周期一次。H analyze 没有新 W 不增加。
- 原 A 的 decision/selection/search 未解决时保留 pending 原 W。合格 author A 按冻结 root A 的原 W 绑定完成这一个周期，而不是制造新周期；复议履行后 seen 身份与 pending 都明确保留/清理，避免以后重新计旧 W。
- 自上次有效复议窗口起，按 ref 累计投入；其他 pending/deferred 承诺按窗口累计未投入周期。遗漏和 same-status 重述不清账；existing_ref 改 label 也不清账。某机制实际获得本轮投入则清其延期计数，screened/waived 不算未处理。
- 只有 A 继续最近实际投入的同分支，且该 ref 在窗口内累计达到频率，同时至少另一个未处理承诺延期达到频率，才要求非空复议。不是必须连续三轮；P/Q/P 累计保留。合理换方向/回 H/必要 audit/E 不被强挡，audit/E 也不能刷新旧窗口。
- 到期原 A 仍保科学 seal/本周期事实；缺复议走现有有界 author A 路径。有效复议可维持原 ref，关闭派生窗口；后续窗口仍可再次到期。seen W、原 ref、绝对历史、预算与重启事实不退款、不删除。声明证明作者复议，不证明科学判断正确或全面覆盖。

## 模型可见范围与实现

实际 `science_view.lineage.mechanisms` 给出≤4行的机制概览，优先到期/未处理，再按延期数；裁剪有 omitted_count，完整既有 mechanisms 页按16条分页。默认总 brief 仍≤4096 UTF-8字节，无全量原件复制。

真实已消费 `completed_cycles` 与 `cycles_if_assessed` / `pending_assessment` 分栏，不能把本轮尚未 A 评审的 W 声称为已完成周期。due/阈值/遗漏/完整入口在容量裁剪后仍保留。原页或原件哈希失配硬拒。

生产复用 search.fold 的纯重放、decision/semantic 既有诊断与作者纠偏、lineage 既有分页/有界投影。无新持久账本、状态模块、搜索器、Root 科学判断、比例预算或祖先附件继承。

冻结：`/tmp/scid-portfolio-freeze-20261013/source-test-02.json`，8生产文件及 `tests/research_loop/test_portfolio_review.py`。专属场景包括实际控制器缺复议→A补正→继续原ref/下一窗口、实际 audit/E 返 A、原未解决 A 补正/旧 W 不重计、延期重述/改名/遗漏、P/Q/P累计、科学 waive、20机制多字节/完整索引/页损坏、旧10字节及不支持旧布局的明确拒绝。首静态审查的 seal_sha 名称错误及 portfolio+非统一展示配置缺口已修，失败/修复证据由父保留。无模型回归不代表科学效果验证。

## 父级验收证据

既有8文件145 PASS。新专属文件首轮13 PASS / 1 FAIL：extract fixture漏了既有合法 decision REQUEST，实际正确转 A 补正，未进入 E；只修该 fixture，生产未放宽，精准1 PASS。分批源码覆盖159个不同场景，不是单次整套全绿。初始失败记录保留在外层 `.trial/portfolio-new-20261013`，既有门禁在 `.trial/portfolio-existing-20261013`。

安装包完整专属14场景通过；installed整组29 PASS / 11.14s（portfolio14 + decision10 + guide5）。fresh wheel22模块源码/包/安装哈希一致；实际 CLI portfolio prepare冻结protocol11，默认 H-A-W-A 与重启无重放通过。wheel SHA256：`6c0d23060f25bdfb54bce68835746ef1cf34023fec6a6c74da4113963d8c6cb4`。独立 reviewer n1 最终审查 PASS，见 [独立审查记录](ROOTLESS_PORTFOLIO_REVIEW_20261013.md)。这些无科研模型验收证明合同/计数/恢复接线，不证明科研效果或全面机制覆盖。
