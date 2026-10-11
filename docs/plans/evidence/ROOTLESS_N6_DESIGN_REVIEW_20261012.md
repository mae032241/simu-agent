# N6设计独立审查

结论：PASS（设计范围），未发现阻断，可按第8节先实施N6a，源码冻结后仍须独立复审。审查者/root/n0_baseline，未编写被审设计或实现，未运行模型、测试、评分或修改生产代码。

被审最终设计：.trial/n6-design-20261011/design.md，SHA256 1a9238270349da6c27e31c4d84e7aff696e924a165287413be3a9dface51e100。参考源码020004b；已读budget/native/controller/runtime/search/history/contracts/semantic/correction/CLI相关接口。源码尚无N6，此PASS不是功能或真实交付资格。

## 可独立实施范围

N6a只有prepare --node-budget-policy：四角色节点策略、实际准入/Popen前及运行观测停止、intent budget_slice、恢复/状态。W取原slice和新policy较小界，同一锚点不双计。既有无字段实例保原行为/冻结字节。不得在此节点开放delivery、预留切换、closeout/adapter，停止不是已交A或交付。

N6b必须完整通过预留→有界A科学决定封存→submit→confirm、硬停收口及恢复门禁后才开放delivery-policy/非导出closeout。半接线不得可启用。仅新prepare冻结策略；N6a旧实例不得后补delivery，无delivery实例仅本地export-only。两节点串行、N6a提交后才接N6b；无隐藏第二状态权威。

## 边界核验

- 所有角色同一节点预算函数及持久intent锚点，原global ledger/native usage唯一；turn.completed观测迟滞明示，不伪保证零token超额。原boot/advance并集、accepted pause计时、清理、缺量/unknown仍受约束。
- 三A+submit/confirm资源预留派生自冻结policy，只是原预算内部预留，不是追加额度或新retry授权；必须在派发前及真实Popen入口应用同一边界。N6b动作名额、时间包含零模型动作，确认/query各次显式接受，不能无穷恢复免计。
- 硬停后先收集原可信终态；live/unknown/cleanup/用量缺失禁止新工作，未知外部submit只同operation身份有界query，不盲重放。科学pause与exact ack不被closeout绕过。
- stopped节点不能伪seal；新purpose/source_cutoff限定连续sealed前缀，原停止节点全包保留。前缀必须覆盖build/bind、seal/validate、refresh/rebuild及后续补正，普通run仍拒跳洞，不能全局过滤缺seal。
- 后续closeout作者仅直接绑定完成前驱，不能range到未sealed停止洞；候选和材料从原绑定索引，current submitted必须有可验证ID，否则decision_unresolved而非伪造ID或null当保留。
- 新冻结delivery A任务用原candidate_recommendation作明确交付选择，理由仍科学作者负责；一般A推荐不自动变提交。H/W/E/等待等动作不继续探索；无效/未知、native/schema/资格不软化，硬失败不自动重试。
- 已有最多2次合法作者补正是原白名单/root计数，不允许把3A预留变成通用重试；closeout本身不新增E探索链。此前原科学链/跨E重启的补正根与消费仍保留。
- submit/confirm薄适配器冻结源码/config/权限/目标，A选择不等授权；先intent后副作用，崩溃后只同身份核对。未知替换的当前actual=unknown，旧last_confirmed保留但不虚称仍在目标。qualified工件缺失/digest-only/审计未知拒替换。
- 预算任何一维不足或已耗尽只本地只读导出现有状态，不偷偷远程query，不额外模型/提交。无adapter导出不是confirmed。closeout_begin后重启/amend不再开探索或清零。
- 保持现有协议8 schema/raw/冻结job/view；新purpose只是新host任务身份边界，无科学协议暗改。若新科学表达确需要字段，转T0统一协议设计，不原地修改8。

## 后续必验与资格限制

生产参数不凭空默认；历史单次最大值不是未来请求上界，E/分角色精确时长缺测只能显式有限试用且标假设。实施/独审需查真实子进程硬停、不成功seal、unknown拒绝与无重放、原预算消费、普通连续路径不退化、全部新closeout入口精确prefix、A决定/已确认actual分离以及安装wheel完整闭环。

源码行数估计只是风险提示，不是截断必要恢复路径的理由。超过范围先回设计，不能叠加Root/第二余额或在半功能状态交付。没有真实模型或原N5恢复授权；旧N5已超token，适用export-only，不增额。
