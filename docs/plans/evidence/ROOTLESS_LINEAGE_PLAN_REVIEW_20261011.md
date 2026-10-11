# 统一谱系/自适应搜索计划独立审查

结论：PASS（计划修订范围）；未发现阻断。审查者 /root/n0_baseline，未编辑被审文档/代码，未运行测试、模型或全池评分。应用 scid-cross-boundary-review 与 scid-decision-corpus-maintenance。

被审文件：docs/plans/ROOTLESS_LINEAGE_ADAPTIVE_SEARCH_PLAN.zh-CN.md；SHA256 0fb3caef8a5beb89fda73846262ec11d65b967792a8b9f5e5cd76b8fe81f3a25。参考实现020004b；当前N6仍为待设计/实施提案。本PASS不授予生产实现、真实恢复、评分结果或科学效果资格。

## 已确认的边界

- 行65–75：全池先冻结台账/模型/公开数据/verifier，缺审计不伪造leakage=false，条件性预测reward单列而非正式资格；模型丢失/载入失败/超时/未知来源进入覆盖缺失分母。可评分池和已审计池分开，池内最优只为事后上界；并列秩相关及条件分组不冒充独立候选重复试验。
- 行72–73、95、158–160、190：已有隐藏结果只开发诊断；T0可以据诊断确定优先级，但不从同隐藏集归因唯一缺陷或编写题目专用权重。T4条款冻结公开输入、适用条件、资格/评估版本、动作/未知处理，隐藏不作规则输入，不按reward调阈值；已见隐藏池回放不称独立验证。后续同题开发局限仍披露。
- 行81–91：全角色单节点执行阈值、A/提交/确认/补正三种资源预留；明说原生token只观测后停止及在途迟滞/终止宽限。硬停收口先核原任务停止与执行可恢复，只用原授权剩余预留；已耗尽只能零模型导出现有提交/未完成状态。未知工作不重放，被杀未sealed输出不冒充合格结论；新提交确认前保留旧提交，权限和资格不解除，重启不续额。
- 行95–111、133–163：T0据全池/步骤成本决定T3/T4规模，低池质量不能推出树结构缺失，复杂辅助者需实际瓶颈证据。T0合并冻结T系列科学协议升级，protocol8冻结字节/含义保留；N6优先host策略/命令，确需协议变化另审兼容设计。
- 行169–190：行为与效果分层，单场/单配对不证明稳定性、优势或方差降低。反事实重排只能诊断既有池的选择损失，不证明动态搜索可产生同池、提高目标成绩；原题停止条件不改，新真实预算另冻结授权。

## 源码接口核对

现有 native.usage/_usage_event 仅turn.completed观测input+output（cached不重复加）；native.run_native在Popen前与循环内检查global budget及W slice，未知终态/cleanup拒sealed。search.accept/stop_reason有immutable W intent anchor，无H/A/E通用node limit。controller._launch_limit/_run保全局预算、accepted工作与retained job，不提供reserve/closeout。budget.snapshot/amend/execution_blocked为唯一时间/额度账本，未知/live原执行禁止暂停退款与修额。cli只有prepare/run/status/pause/continue/budget-amend，尚无N6收口命令。因此本文把N6标待实施符合现状，不能用此计划宣称预算内交付已保证。

## 验证与后续设计要求

所有文档相对链接存在；只读核验，无测试锁占用。全池执行尚无结果，此审查不核准其覆盖率或reward真实性。N6额度数值、在途迟滞容忍、节点名额保留、硬停收口一次性/恢复幂等和unknown拒绝需在实现前独审冻结并以确定性/installed入口验证。零模型导出不是新增外部提交或暗中额度。审查通过后父可将第4行文档状态改为独立计划审查通过；T0详细迁移设计仍待审，生产功能仍待实施。
