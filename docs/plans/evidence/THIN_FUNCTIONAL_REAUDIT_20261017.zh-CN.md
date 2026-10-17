# 薄 CLI 功能闭环再审

日期：2026-10-17。基线：`dev` / `73f57c6`。结论：**发现两项可达 P2 缺陷；不能据既有节点提交和定向通过认定全部科研闭环完成。** 本报告不授予修改或动态验收结果。

审查独立于实施者，使用 `scid-cross-boundary-review`、`scid-change-scope-checks` 的边界/证据方法。本轮只做文本、行号、Git 只读核对；没有 pytest、收集、项目 import、业务 CLI、构建、安装、模型、服务器或求解器执行。已通知协调者先处理以下两项。没有在所读代表链中确认 P1；这不是全仓无 P1 的证明。

## F1 / P2：做过受管实验的成果无法进入后续正式审查和授权

**位置与因果：**

- `src/scidiscovery/research_loop/qualification.py:249`：只要观察原件有非空 `managed_calls`，或启用了 `history_observer`，就把整个节点的附加输入标成未知，产生 `observation_input_provenance_unsupported`（256–257行）。没有消费该调用已经冻结的精确输入。`not_submitted` 也在非空列表中。
- `src/scidiscovery/research_loop/formal_review.py:143`：任意上述 `missing_reason` 直接令 producer 的 `authors.complete=False`；147–170行又把不完整性沿显式 selected/compiled 贡献传播。
- 同文件 `request_route` 的193–207行：即使原生参与者身份完整且已选择唯一精确工件，也返回 `subject_authorship_unsupported`，不派正式审查。即使另造 pass 文本，325–332行仍要求完整作者及独立 reviewer，不能获得资格。
- `src/scidiscovery/research_loop/qualification.py:298` 和 `execution_authority.py:463`：来源状态同样继续 unknown；后者要求精确 subject 和当前任务都 clear，因此只取消作者拦截仍不能闭合授权。

**复现路径（静态可达，未执行）：** 在显式声明来源、实际可识别 native 身份的实例中，W 做一次真实受管 local 实验，然后保留新实现/实验输出；普通 A 选择该 W 的唯一工件并请求 `formal_review`。封存观察包含原 call，故上述分支必然返回不可用。后继 W 选择/编译来自该 producer 的成果也继承不完整作者集合。TCAD 的正常“已审实现 → 执行 → 根据结果形成下一版 → 再审/再执行”有相同接缝。普通科研封存并未被这一分支直接禁止，但需要正式资格的继续执行闭环被堵住。

**范围判断：** 未声明的外读、身份缺失、opaque 或缺可信输入合同保守 unknown 是正确的；缺陷是对所有受管 call 无差别停止消费。先前 `test_public_compile_exact_review_and_existing_run_keep_native_original`（`tests/research_loop/test_native_execution_inputs.py:138`）证明的是先编译/审查再运行到 queued，没有证明实验之后的新成果还能获得资格。原先 P3a 的保守中间态不能充当本项完整迁移的退出证据。

**最小修复与负控：** 由既有执行/来源 owner 消费已验证 accepted 输入及已有 producer provenance，按精确 slot/ref/producer 连接来源和作者；复用共同 validator，不让资格模块另猜路径/同 hash 身份，不复制祖先，不读取模型 self-label。用一个小型真实控制链覆盖“已有 call → 新封存 subject → 正式 request/资格”，并在同用例中换同 hash 不同 producer 或加入未声明输入，要求后者仍 unknown/不合格。受限输入仍须 restricted 支配；不把完成状态等同于来源 clear。无需真实模型/TCAD即可证伪本缺陷，真实平台资格另列。

### F1 最小设计补充（未实施，P3此闭环仍未完）

不能仅删除 `formal_review.authors` 的 `missing_reason → complete=False` 后称修复完成。来源限制 unknown 与作者未知是不同事实：精确 producer/全部贡献者已知但限制未声明时，作者集合可以完整，独立 review 可以成立，执行 gate 仍应因来源 unknown 拒绝；输入 origin/贡献者集合本身未证明时，作者集合依旧不完整。当前 `observation_input_provenance_unsupported` 同时包含后者，直接删除会产生错误的独立资格；执行 gate 后续阻止副作用不能补救这个资格错误。

候选最小归属（仍需具体设计冻结后实施，非本报告开新协议）：

1. 由 `history.managed_calls / validate_managed / managed_status` 的已验证归档行提供窄的输入/贡献投影：精确原 accepted/native attempt/scope、直接来源 edges 和覆盖完整性；共同 validator 继续唯一核验 accepted/observation/retirement。不让 qualification 另写 accepted 解析器，不递归复制历史。当前 W 作者文件只有在 host 明确冻结其 current-job 归属合同后才继承原任务输入，不能按路径、同 hash 或“执行成功”推断外源身份。
2. TCAD native 包的映射由既有 `execution_inputs.verify_compilation / resolve_native_original` 证明同一 payload/compiler，直接消费已封存 slots 与 `author_input` producer。资格层不解包 tar、不解释 TCAD 私有字段。既有未声明外源、opaque、旧无证明记录仍保守未知，不回填 clear。
3. `qualification._output` 消费上述 owner 的直接投影/ref，独立计算 restriction 三态；`formal_review.authors` 消费贡献覆盖完整性及精确 producer 作者。restriction unknown 不自动等于作者 unknown，贡献覆盖未知也不能自动变完整。不改模型科学 schema、余额、审批或公共执行入口。

最小证伪范围：已知输入的 local call 后产生新 subject 能真实请求 review；精确作者已知但限制未知时 review 与执行拒绝分别成立；未声明外源/同 hash 错 producer 仍不能获得错误资格；TCAD 复用现有 compile/review/run 小 fixture 延长至观察后的再编译/再 request。优先复用已有链，不建另一套框架、不跑安装矩阵。上述设计尚未实现，不能将 P3此闭环标完成。

## F2 / P2：永久未提交事实被 screen W 当成完成观察，导致封存失败

**位置与因果：**

- `src/scidiscovery/research_loop/history.py:244`：可信永久退役投影明确为 `status='not_submitted'`，`completed=None`、`terminal=None`，保留独立 retirement 和原件。它不是执行失败，也不是科学观察。
- `src/scidiscovery/research_loop/worker_delivery.py:98`、108：历史和当前 call 两条分支均使用 `status!='unknown'` 选取已知观察，把上述退役行放入 `evidence`；投影还丢弃 retirement 字段。
- 同文件119–122行先发布 `work-evidence.json` 再调用 `validate`；135–137行对该 evidence 强制要求非空 archived completed，必抛 `Worker known observation originals unavailable`。已有事实文件再次 capture 只会重验，不能自行修复该错误。
- `src/scidiscovery/research_loop/checkpoint.py:97` 与 `contracts.py:976`–982：screen W 的 checkpoint/封存必经此检查，因此 W 如实写 `basis='blocked'` 也到不了原 partial → A 路由。

**复现路径（静态可达，未执行）：** 配置 screen 科学任务；原受管 call 在不确定派发后，经公共 `experiments ... retire` 的真实永久 fence 协议证明未提交；W 报告该机制 blocked 并完成原生输出。或者下一个 screen W 在历史中读到同机制的该退役行。两条 capture 分支都会把它当已执行观察，导致封存异常，无法将已知工程事实和科学局限交给 A。

**最小修复与负控：** 完成观察只接受共同定义的 known success/failed；`not_submitted` 继续作为独立、可核验的未观察事实，不能改成 unknown、伪造 completed 或算 screened。复用现有退役 fixture/共同 validator，接一个真实 screen `capture → assessment → seal/route`：blocked finding 能作为 partial 交 A，observed finding 不能凭退役事实满足覆盖；retirement 篡改仍拒绝。现有 `test_retirement_archive_and_recovery_share_original_validator` 只到 history/recovery，`test_worker_delivery.py` 的 failed/blocked 用例未组合永久退役，单项通过不能证明这个边界。

## 代表性功能与计划完成度

| 范围 | 本轮静态核对 | 尚不能据此宣称 |
| --- | --- | --- |
| 普通 H/W/A/E | `controller._run/_route`、`contracts`：父原件、E 返回原请求方、合法科学改道、有限补正；A2 保留非 formal 补正根及原额度 | 全部异常/权限/平台配置均可运行；F1/F2 未修前闭环完整 |
| 正式 review 默认分离 | `formal_review.input_binding/bind_job/validate_job`、`contracts.build_job`、native 专用提示：中立问题，global + exact subject，保 producer/selected 来源边及 host requester 原件；返回仍回普通 A | 盲评、访问隔离、自动包含所有科学支持文件或完整 claim 依赖；默认包不足时须补证/unknown，不能程序制造 pass |
| 暂停、重启、异常修复 | `instance_control`、`controller`、`native`、`continuation`：原 writer、pause 下一节点语义、原 intent 不重派、已接受会话的有限 repair/wake | 任意 unknown 均能自动恢复；跨 boot 可继续原时钟；A4 启动前耗尽可证明未提交（既定为 unknown） |
| 异步执行 | `managed_wait`、`experiments` 的准入/终态观察、恢复消费者代表路径：原 call/external 身份，不将 pending 伪装为成功，未知不发新 call | 所有消费者都正确处理新增 disposition；F2 是遗漏的实际消费者 |
| 通用候选/收口 | `generic_results`、`generic_delivery`、`delivery`、`controller._run_closeout`：明确结果声明、精确原件、A deliver 授权、submit/confirm、未知不重放、有限作者补正 | 实验 metric 科学有效、全局最优、外部服务投产；目录确认只证明目录交付 |
| 计划 R0/P1/P2/P3/A2–A4 | 已有提交和有限验收账成立，不能擦掉历史证据；本轮检查发现跨节点组合未闭合 | 将节点完成直接等同所有领域的完整产品闭环；应为 F1/F2 新增精确修复节点 |
| P4/P5 | UI/只读归档已有；P4c2 缺单 owner/fencing 可写恢复，旧入口仍有实际消费者 | 完整可写恢复、全部旧入口已退役；不是本轮新发现的代码 bug |
| 授权部署/真实科学 | A0/A1 明确可信 Worker 软边界；已有人工批准、预算、幂等仍保留 | 抵抗同权限恶意 Worker、真实 TCAD/SSH/模型/浏览器资格；不把用户已选择的软边界再列为新缺陷 |

## 覆盖、未覆盖与执行建议

本轮读了上述主链及相邻 owner 的代表实现，静态查阅 formal review、native input、retirement、worker delivery 等现有测试的断言边界；没有逐行审完全部测试、全部插件、旧 Root/MCP/SQL 全栈，也未扫描全部秘密或重做全仓实时性审计。Git/text 检查不是运行资格；此前 164 与 A 系列21项的历史通过仍只按各原报告选择/版本解释，本轮没有新增通过数。

建议顺序：先修 F1 的可信受管输入/作者来源接缝，再独立修 F2 的退役 disposition 消费；各自先设计冻结、独审、单一协调者运行最小正负链，不装包、不复制整套旧测试。修后更新主迁移计划的资格范围；P4c2、P5剩余退役和真实平台资格继续保留真实未完状态，不用为完成标签发明新恢复/授权系统。
