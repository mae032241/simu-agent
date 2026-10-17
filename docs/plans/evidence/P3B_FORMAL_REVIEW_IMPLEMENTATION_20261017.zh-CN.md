# P3b 正式独审资格实施记录

状态：实现已获[独立代码静态审查 PASS](P3B_FORMAL_REVIEW_REVIEW_20261017.zh-CN.md)；只做静态检查，未运行测试、native、模型或 solver。依据[最终设计审查](P3B_FORMAL_REVIEW_DESIGN_REVIEW_20261017.zh-CN.md)。P3c/d 未完成，真实 TCAD prepare/upload/submit 仍 blocked。

## 根因与已有规则复用

普通 A 分析及 candidate audit 没有正式 review 的精确合同与独立身份资格。native outcome 单独的 thread_id 也不足以证明真实 session 或完整参与者；raw Codex 未配置 resume 时实际 home 可能是继承的 CODEX_HOME，不能猜成任务 native home。

本轮将旧 `ExperimentReview` 的 verdict 类型、科学 review 语义及 `worker_connections` 的独立性集合规则抽到纯 `operations/review_rules.py`，旧路径继续复用。没有导入旧 SQL/CAS/Run/connection 状态，也没有新增任务注册、Root、预算池或审批库。

## 真实产品入口与完整回程

1. 操作者可选 `scid-research prepare --enable-formal-review`，由既有 prepare 冻结 `formal_review_policy={version:1}` 及当前合同原件 ref。默认不启用，不要求普通任务经过 review。
2. H 用既有 analyze 到 A；W 用 review/decision 阶段意图到 A；E 按既有 requester 返回 H/A。只有普通 A 明确选择 `next_action=formal_review` 才请求正式审查。
3. A 继续用已有 implementation_selection 作科学对象选择。控制只接受唯一已解析的 selected material，绑定精确原件、producer seal、作者事实、当前 review 合同及 requester 原件。模型不填新的 subject、路径、hash、作者 ID 或回执字段，不按“最近成果”补选。
4. 控制通过既有 evidence_return 携带 request ref，在下一个现有 A job 标记 `purpose=formal_review`。继续走 `_run → build_job → native.execute_native → runtime → native.run_native → seal_result`。原 max_steps、A 节点预算、thinking share 和共享总授权照常消耗，没有新 grant。
5. 正式 A 只输出 `verdict/summary/scientific_result/limitations` 四个科学字段。模型 packet 只给精确 subject、原始目标与 review 问题，不附全历史或作者意见列表。控制绑定身份、资格与回程。
6. 封存后回到下一普通 A，绑定 requester、原科学 subject、review 原件与紧凑资格状态，由 A 决定继续、修订或结束。正式 verdict 不替 A 选择下一科学动作，也不授执行权限。

formal-only schema 由同一 job marker 选择，贯穿结果 schema、science_payload、native schema 文件及 continuation validate/repair。history 保留原四字段 raw；envelope 的内部回程字段由控制补。search/scientific_intent/correction/decision 避免把正式 review 或其请求当普通 A 科学进展。role_share 允许显式 A→正式 A→普通 A，仍检查原 thinking/shared 预算。

## 身份与 exact-subject 原件

- opt-in native outcome 记录宿主实际 meter_home 和已由 SessionUsage 找到的 session path。只有当前受控 raw Codex 已有实际 argv 禁用 native multi_agent 的分支声明完整参与者范围；不改变原 launcher、权限、home 或 resume 配置。
- continuation.session 增加宿主明确 home/path 的窄参数，复用同一 thread.started/session_meta 解析器，不再为资格扫描整个人 home。旧 resume 默认返回 shape 不变。
- seal 遍历整个 execution.records，保留每个 attempt/context 的 intent、outcome、session header 原件与稳定 engine/thread 身份。缺任一证明即 unsupported，普通科学成果仍可封存。外部 launcher、历史无证明和未知 helpers 不凭自报名单得到完整性。
- subject 作者取精确 producer 全部原生参与者，并按明确 authors_contract 继承 selected implementation 贡献；不把任意 H/A 上下文 parents 变成作者。没有可信 authorship adapter 的 managed/observer 额外输入保持 unsupported。
- reviewer 只取其自己的真实 native 参与者，不把被审材料作者继承成 reviewer。比较稳定 engine/thread，不用 home 或代码版本变化制造独立。所有共同参与者的交集都拒绝资格；身份集合不完整也不给资格。
- 当前 review 合同绑定共享规则、科学指令、四字段 schema 与实现原件身份；request 再绑定精确 requester。成果 receipt 绑定 subject/producer、合同、作者、reviewer、原 native proof、raw/result 与 verdict。只有身份完整独立且明确 pass 才有 passed 状态；普通 A、工程 audit 和任意 pass 文本不生成该 receipt。

`require_review(root, exact_subject, explicit_receipt_ref)` 是未来 P3 gate 的只读核验口：核对精确 sealed review/member/当前合同，不搜索 latest pass。P2c 仍须通过后续单一宿主 gate 在 prepare/upload 前消费它，并在 submit 前核验；P3b 本身不是授权或资源 gate。

## 不可用与不重试

subject 缺失/歧义、作者缺证或 reviewer launcher 身份未支持时，保留 requester 科学原件，冻结 unavailable 原件，下一普通 A 可消费一次紧凑反馈。相同 subject、合同、身份/选择事实及 reason 未变时，再请求复用已绑定不可用事实后 neutral wait，不继续自动增加 A。

独审预读发现初稿把科学 question 纳入比较，A 改写一句 route_reason 就能绕过去重；已将 failure_key 独立为上述控制事实，排除 question。原 question 仍完整保留。没有新增 retry 计数、全局“最新”索引或第二状态机。

reviewer 完成后身份仍缺证或与作者重叠时，科学 review 原文和 not_qualified receipt 保留，普通 A 可继续科学决策；不把该 verdict 改成科学失败，也不授执行资格。预算不足沿原控制边界停止，不为反馈或 review 新增额度。

## 精确文件清单

本轮修改以前置 P3a `da87484` 为基础；最终静态检查时 HEAD 为并行已提交的纯 browser access 抽取 `002284e`。本轮不编辑并行 P2c 的插件、experiments 或注册文件，也不依赖 browser access 改动。

- 新 `src/scidiscovery/operations/review_rules.py`：共享纯 verdict/语义/身份集合规则。
- 新 `src/scidiscovery/research_loop/formal_review.py`：原实例 host review 合同、请求、作者/参与者原件、资格与窄路由。
- `research_loop/{contracts,controller,cli}.py`：可选入口、正式 job marker、四字段 schema、原生命周期封存与回程。
- `research_loop/{native,continuation}.py`：实际 home/path 事实与同一 session 解析器，保留旧默认 resume shape。
- `research_loop/{history,semantic,search,scientific_intent,correction,decision,role_share}.py`：正式 schema 的必要消费 guard；无新 scheduler、预算或 registry。
- `src/scidiscovery/general_science_experiment_review.py`、`src/scidiscovery/artifact_agent/service/worker_connections.py`：旧 review 路径复用纯规则，旧服务仍拥有自己的状态。
- 新 `tests/research_loop/test_formal_review.py`：下述定向用例。
- 本记录。

以上共 17 个 Python 文件及本记录；独审文档另由独审作者负责。

## 定向负控与证据层级

已写五个测试函数，未运行：

- 纯集合规则：不同参与者、共同作者重叠、不完整作者集合。
- 实际 controller/native/runtime 派发到独立脚本进程的协议 fixture，完整走显式请求、四字段 review、封存和普通 A 回程；核实际 CODEX_HOME 不等于任务假定 home，错来源成员不能复用 receipt，重复 run 不新建 jobs。
- 同一作者 UUID 即使返回 pass，也只得到 not_qualified。
- 故意缺 W session header 保留科学成果；后继 A 改写 route_reason 仍只获一次 unavailable 反馈，之后 wait，不继续启动节点。
- 普通 A/pass 文字不获得正式资格；默认普通 schema 不开放 formal_review。

脚本 fixture 的身份、session header 和科学 verdict 都是**合成协议输入**，只能检查真实 native 控制路径怎样消费这些事实，不能证明真实 Codex/平台身份、真实独立审查或 TCAD 可执行。另一个普通用例复用 finish helper 模拟 native terminal；同样不是原生运行证明。

最终静态检查：17 个本轮 Python 文件及嵌入 native fixture 脚本均通过 `ast.parse`，17 个 Python 文件尾空白检查及本轮限定路径的 `git diff --check` 通过；没有执行这些模块或脚本。

项目 import、pytest/collect、CLI/native/任何业务子进程、构建安装、真实模型、远端/solver 均未运行。代码独审结论另行补记，不以测试已写或设计 PASS 代替运行验收。
