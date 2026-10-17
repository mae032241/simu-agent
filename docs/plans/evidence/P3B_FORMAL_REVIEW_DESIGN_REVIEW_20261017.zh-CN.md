# P3b 最小正式独审设计独立评审

结论：**最终设计 PASS，可按收口方案实施**。这不是代码或运行验收，不授予真实 TCAD 执行资格。仅文本核对既有入口/身份/预算原语及实施者书面设计；没有测试、收集、项目导入、CLI、构建、安装或模型执行。

## 已确认边界

- **显式产品入口**：prepare/CLI opt-in `formal_review_policy={version:1}`；普通 A 才可显式选择 formal_review，控制从已有 implementation_selection 的唯一精确 sealed subject 解析原件与 producer。不增加模型路径/hash/作者/资格字段，普通 H/W/A/E 流程不因此强制经过正式独审。
- **同一任务与预算 owner**：下一现有 A job 标正式 review marker/purpose，经原 native.execute_native/runtime、原 max_steps、A 预算与共享总预算派发。四字段 review raw 为 verdict/summary/scientific_result/limitations；之后普通 A 消费请求、subject 与 review 原件再作科学决策。没有第二 Root、Run 库、连接表或独立预算池。
- **精确合同与主体**：请求绑定 requester 原件、唯一 subject/member、producer seal 及当前 review 合同；合同包含实际共享规则、科学指令、schema 与实现身份，不能只比较 JSON shape。receipt 绑定精确主体/合同/作者集合/实际 reviewer/raw/seal/verdict，未来 gate 显式消费 ref，不搜索“最新 pass”。普通 A、工程 audit 或 package pass 文本均不能生成正式资格。
- **真实身份**：`native.py:319` 之后的实际 home 可能与任务 native home 不同；仅用原生受控 Codex 现有实际 argv 禁 multi_agent 的范围声明完整。native 从已有 SessionUsage 已发现 path 绑定实际 meter_home/path；continuation.session 复用同一解析器核 thread.started 与 session_meta header，不扫描整个人 home，不改 launcher 权限/配置。所有 execution.records attempt/context 都须有证，缺一 unsupported。旧无证明和外部 launcher 不凭自报名单获得完整性。
- **作者与 reviewer 分清**：subject 作者来自精确 producer 的全部 native 参与者及 host authors_contract 明确继承的 selected implementation 贡献；不从任意 H/A 上下文 parents 推作者。reviewer 只核自己实际 native 参与者，不能把被审主体作者继承成 reviewer。稳定 engine/thread 身份比较不能靠 home 或代码版本变化制造独立。
- **未知保留科学**：subject 歧义/身份缺证不破坏 requester science；冻结 unavailable 原件，下一普通 A 可消费一次反馈。若该 A 再提相同 subject/合同/未改变身份原件的不可行请求，复用精确绑定的反馈后 wait/unavailable，不自动继续增加 A 到耗尽预算，不新造 retry 状态机。reviewer 完成仍缺证时保留其科学原文和 unknown receipt，不能授资格。
- **schema 与消费者一致**：以同一 job marker 决定四字段正式 schema，贯穿 result_schema/science_payload、native 输出 schema、continuation.validate_task 与 repair。history 保留 raw；controller 优先处理 formal 回程。search/correction/decision 及其他直接索引普通 A 字段的消费点须逐项 guard，不能只给 envelope 补 next_action 就假定所有旧消费者兼容。

## 后续代码独审重点

验证真实 action→原 native 派发→封存→普通 A 反馈调用链；证明未知身份不会写合格 receipt，普通 A 不自动升级。核对 exact subject/合同替换、共同作者/所有 context、自审和缺证负控，以及 unavailable 不重试。测试替身仅能证明控制接线，不能用自写身份 JSON 声称真实 native 资格通过。

实施者的拟议文件范围含 formal_review/review_rules 新模块及既有 contracts/controller/CLI/native/continuation 和必要科学控制 guards；须按实际冻结差异再审，不预先宣布全部代码通过。P3c/d、可信授权与累计 solver 预算仍未完成，真实 TCAD prepare/upload/submit 继续 blocked。
