# P3b 正式独审入口独立代码审查

## 结论与范围

**静态代码审查 PASS**。已核对[实施记录](P3B_FORMAL_REVIEW_IMPLEMENTATION_20261017.zh-CN.md)最终 17 个 Python 文件及该记录；当前 HEAD 为 `002284e`。不包含并行 P2c 的 experiments/插件，也不代表 P3c/d 或真实 TCAD 资格通过。

审查独立于实施者，采用文本/Git 阅读及精确调用链追踪。没有运行测试、收集、项目导入、CLI/native、构建安装、真实模型或远端操作；实施者报告的 AST 检查不等于动态验收。

## 真实入口、原预算与必要复杂度

`cli --enable-formal-review → controller.prepare → contracts.build_job` 冻结可选合同；只有启用实例的普通 A 显式选择 formal_review，才经 `controller._route:320` 和 `formal_review.request_route:170` 创建请求。下一节点仍是原 jobs/native-evidence 下的 A，沿原 controller/native.execute_native/runtime/seal_result；四字段正式结果封存后由 `return_route:284` 回普通 A，科学 verdict 不替其选择后续动作。

`contracts.response_options` 是 task marker 的共同 schema 入口，贯穿生成、science_payload、native schema 与 continuation validate/repair。history 保留 raw；内部 envelope 补回程字段。search/scientific_intent/correction/decision 的小 guard 防止把 formal 四字段 raw 当普通 A 决策/进展字段解析，也防止把请求 review 本身计作已完成科学推进；这些是实际消费者需要的差异，没有新增第二套调度器或任务账。

`role_share.reason` 仅允许显式请求/回程的 A→A，后续 thinking/share 预算检查仍执行；native 仍接受原节点和共享总预算/max_steps，没有独立 review grant。普通 A 的默认 schema、candidate_audit 与 pass 文字不能生成正式资格。

## 精确主体与独立身份

- `_subject:157` 从已解析唯一 selected material 取得 exact producer/member/seal，验证原科学封存；没有新增模型 subject/path/hash 字段，也不按最新或同 schema 补选。
- `freeze_contract/contract:38` 绑定当前共享 review 规则、指令、四字段 schema 和实现原件。request 另绑精确 requester，receipt 绑 subject、producer、合同、作者、reviewer、native proof、raw/result 与 verdict；`require_review:292` 只消费显式 ref，错主体或非独立 pass 不能复用。
- native opt-in outcome 记录实际 meter_home/live_meter.path。`continuation.session` 用同一 thread.started/session_meta 解析器，允许宿主明确确切 home/path；旧默认返回 shape 保留，不为资格扫描整个人 home，不改原 launcher/home/权限。
- `capture_participants:52` 遍历全部 execution.records，保留每个 attempt/context 的 intent/outcome/header 原件；`participants:93` 复核范围与完整性。只有已有实际 raw Codex argv 禁 native multi_agent 的范围可 complete；缺证、外部 launcher 和未知 helpers 不自报完整。
- `authors:127` 仅取精确 producer 的全部 native 参与者和明确 selected implementation 贡献，不沿普通 H/A parents 猜作者。reviewer 只核自己的 native 参与者，避免把被审作者错误继承成 reviewer。稳定 engine/thread 比较不会因换 home 或代码版本“变独立”。
- 新 `review_rules` 是纯集合判定及原 verdict/语义的抽取；旧 ExperimentReview 和 WorkerConnections 继续复用，不搬旧 SQL/连接表。只有完整独立且明确 pass 才写 passed；重叠/缺证保留科学原文，receipt 为 not_qualified。

## 本轮发现并修复

初稿 unavailable 比较整个 failure，其中含 A 自写 question/route_reason。同主体、合同与缺身份事实不变，单改措辞即可反复自动增加 A。最终 `request_route` 保存独立 failure_key，只含合同/subject/作者/歧义选择/reason；question 留作科学原文但不改变可行性。第一次 unavailable 给下一普通 A 一次精确反馈；相同已绑定失败再请求即 neutral wait，不新造 retry 计数或全局 latest 索引。

## 五个定向用例能证伪什么

| 用例 | 生产故障与证据边界 |
| --- | --- |
| `test_independence_needs_every_verified_participant` | 若只看一个 reviewer、忽略共同参与者或把不完整作者集合当独立，字面集合预期失败；它是纯规则检查。 |
| `test_real_native_route_freezes_exact_review_and_uses_actual_home` | 实际 controller/native/runtime 控制链若不派发 formal 节点、schema/回程不一致、误猜 native home、错成员仍获资格或重复 run 新建 jobs，会失败。启动的是独立脚本提供合成协议，不是真实 Codex 身份证明。 |
| `test_native_author_session_cannot_review_itself_even_with_pass` | 若只信 pass/不同节点或 home、不比较作者 UUID，synthetic 同身份将错误 passed，用例失败。 |
| `test_unknown_identity_preserves_science_and_rewording_cannot_repeat_unavailable` | 若缺 session header 却授资格、丢 requester science，或改写 route_reason 可继续启动节点，会失败；确实覆盖此次去重缺陷。 |
| `test_ordinary_a_and_pass_text_do_not_gain_formal_qualification` | 若普通 A/pass 文本或未 opt-in schema 自动升级资格，会失败。finish helper 模拟 native 完成，只证明真实封存消费行为。 |

三个 process_e2e 脚本的 verdict、session header 和身份 UUID 是已知合成输入；价值在检验生产控制怎样验证和传播它们，不能因有 subprocess 就称真实模型/平台独立性已验收。未扩大安装/环境矩阵，也未重建旧 Root fixture。

## 未覆盖与限制

没有运行上述用例；真实 Codex rollout/参与者支持、跨 attempt/context 全链、明确 selected 共同作者继承、合同升级、budget 耗尽/恢复和文件竞争仍未动态验收。scope 只覆盖受控 native 参与者，任意 shell 工作与宿主原件写权限仍是软隔离边界；不宣称发现全部 OS 外部协作。

正式合同/subject 身份不兼容必须重新取得资格，不能继承旧 pass。P3c/d 尚缺，`require_review` 不是执行授权或资源 gate；真实 TCAD prepare/upload/submit 仍须保持 blocked。
