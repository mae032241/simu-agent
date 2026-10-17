# 不可用正式审查按请求限制：独立审查

结论：**静态 PASS，可由 root 串行运行 source3 / process5。** 基线 `21410f9`；范围为 formal_review/contracts/semantic/controller/continuation 五生产文件、test_formal_review 和实施账。不含Cov预留、P5退役或F1来源生产修复。

## 真实行为

- `formal_review.choice_constraints` 仅冻结当前step之前的 exact unavailable refs。重建retained job沿原refs，不将未来失败倒灌旧job；原件缺失/改变继续拒绝。没有新失败次数库、重复派A队列或全候选作者扫描。
- `validate_choice` 在 formal_review action 上复用原 selected_inputs、exact subject/authors 和共同failure_key；同subject/contract/实际identity失败及无singleton在seal前抛OutputRepairRequired。理由改写不改变key，跨E/普通科研后原失败refs仍存在。不同exact singleton可在同一输出选择，不被全局删动作误封；首次新subject身份不足仍仅形成原不可用事实，不授资格。
- `semantic.outcome` 在真实seal/validate路径执行联合校验；`continuation.output_request` 同样识别原错误，能够供既有有限同session输出修复消费。普通科学action直接跳过该限制；不把同一失败封成新A科学节点，也不自动继续烧新A。
- 只有对任意subject都不支持的launcher从schema enum删formal_review；其余细粒度限制是实际语义校验，非只写提示词，也未引入未经验证的anyOf/not等native schema语法。response_options已用于schema、读取、封存与continuation消费。
- 新路由不创建review专属author_correction，不按其次数强制全场blocked/closeout；原非formal补正root/计数/上限、pause、共享预算及资格门禁保持。合法finish仍按原delivery policy收口，不能把取消局部限制解释成取消正常交付合同。

## 最小证伪及修订

source3覆盖真实薄封存拒同key/原output_request识别、同job新subject/改变identity的key比较、篡改失败原件、unsupported launcher实际enum及普通finish、既有非review补正root。identity stand-in仅隔离key比较，不写假身份原件或冒称真实平台恢复。

process5分别为未知身份后普通finish、理由改写同key不封存不派下一A且重启幂等、跨E限制/正常finish收口、原正常独立pass、原作者self-overlap拒资格。合成launcher提供传输/session事实，控制路由、封存、资格消费为生产函数；不是模型或真实Codex身份资格。

静态独审发现delivery process初稿误期待配置delivery_policy后的合法finish不收口；已修为exported_unsubmitted、completed6、scientific_finish/source_cutoff6、无action/job7，保跨E/预算/无假资格断言。此处修测试合同，不放宽生产。当前无法授权输出修复的实例保留原invalid输出并报告output_repair_required；本节点不保证实际resume成功，不新发尝试/额度。

根风险检查已充分，无需全文件、安装、模型或solver测试。审查者仅文本/调用链与限定diff空白检查（无诊断），未运行测试、收集、项目import、业务CLI或Git写入；动态结果须另据root保存日志追加，不预报通过。

## 首批 source 夹具修复复审

`.trial/review_reserve_followup_20261017/review-source/batch-001/pytest.log` 为2 passed/1 failed，2.44秒。失败在测试为0400冻结原件准备变字节时PermissionError，尚未运行篡改拒绝断言。作者只对该精确fixture路径先chmod600，再原样写入 `original+b' '`，仍由实际 `c._validate_inputs` 要求拒绝；没有放宽生产权限或异常断言。定点静态PASS，可只复测该失败项。此段不预报后续动态结果，原失败日志保留。

## 首批 process 暴露的成功分支回归

`.trial/review_reserve_followup_20261017/review-process/batch-001/pytest.log` 为2 passed/3 failed，10.69秒。两项正常review/self-overlap路径因 `_request_value` 抽取后 `request_route` 成功return仍引用旧局部 `subject` 而NameError；这是实际生产回归，本独审初次静态未发现，不能记为fixture错误。第三项已经合法export-only收口，但测试索取该返回合同不存在的completed_steps，是测试合同错误。

作者经窗口仅修两处：成功route父节点从同一个已存储 `value['subject']['producer_step']` 取得，question/ref仍来自该请求，成功与失败原件/资格绑定不变；测试按实际合同校验exported_unsubmitted，再逐个 `c.validate` 六seal角色HWAAEA，并保持scientific_finish/cutoff6/无job7/actions空。定点完整复查两分支及该断言，静态PASS，可只复测3个失败项。源组已通过不要求重跑；本段不预报最终结果。

## root 最终增量证据核对

独立只读核对同根目录 `review-source`、`review-source-retest`、`review-process`、`review-process-retest` 四批pytest/resource原件：source首批2 passed/1 failed，修正单项1 passed（1.28秒）；process首批2 passed/3 failed，修正3项3 passed（9.19秒）。合计所选 **8个独立用例最终增量通过**，不是最终HEAD全8项重跑；初次四次失败保留，分别为只读篡改fixture权限、一项closeout测试合同及两项同根因的生产NameError。

监管耗时2.621、1.453、10.875、9.364秒，总计24.313秒；峰值145,530,880 bytes（138.789MiB）。四批全部cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]，未启地址空间硬限制；这些数值不构成一般内存/硬实时保证。

结论：静态修正与保存的动态证据一致，可提交本节点。原已通过资格路径和self-overlap负控均已在失败后实际复测；同session修复只验证原错误识别与既有控制接线，未验真实模型resume/平台身份。不安装、不运行模型/solver、不将本8项当成完整产品资格。测试由root唯一串行执行，审查者只核日志。
