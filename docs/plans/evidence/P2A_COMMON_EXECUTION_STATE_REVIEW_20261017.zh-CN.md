# P2a 共通执行状态独立静态审查

## 结论与范围

结论：**静态代码审查 PASS**，受审差异未发现须阻断提交的生产问题。最终冻结基线为 `be1b379`；本结论只覆盖 P2a，不代表 P2b/P2c、P3a 或真实 TCAD 生命周期通过。

审查者独立于实施者。只读 Git 差异及精确调用链，未运行测试、测试收集、模块导入、构建、安装、真实模型或远端操作。测试下述描述表示其静态可证伪目标，不表示执行通过。

受审生产文件：`operations/execution.py`；`research_loop/{experiments,managed_wait,history,lineage}.py`。测试范围为 `tests/research_loop/{composed_execution_fixture,test_composed_execution_results,test_managed_execution_wait}.py` 的本次差异。补读 `continuation.wake_start` 与 controller 的等待消费点，没有全审其余控制系统或全量测试。

## 生产调用链

| 职责 | 静态证据与判断 |
| --- | --- |
| 原始 pending 状态保真 | `operations/execution.py:10` 的唯一 pending 集合及 `execution_status` 保留 accepted/submitted/queued/running/cancelling；未知或非字符串归 unknown，cancelled 只映为工程 known_failed。未新增状态数据库。 |
| 阻止重复提交 | `experiments.py:688` 的 dispatch 在 prepare/accept/submit 之前检查原调用：所有非已知终态、缺 external 绑定均返回原 call；不会因 queued/cancelling/未识别字符串落穿创建新 call。cancelled 在放行后继前要求原终态观察通过验证。 |
| 原终态身份与兼容 | `experiments.py:524` 的 Records.state 校验显式 native_state 与工程状态一致；`verify_observation:560`、`record_observation:613` 将 completed 原件与 observation 同值绑定。cancelled 不允许只报 known_failed 而丢失原因；旧 completed/observation 都无该字段时继续旧兼容路径，不回写历史原件。 |
| CLI 与进度 | `experiments.py:737`、`:855` 附近分别保留 pending 状态和计数；reconcile 缺 external 绑定时仍 unknown，所有非终态均退出 2，原 call 不变。progress 是只读适配器事实投影，保留真实 local process 已启动、submission 尚未写下期间的 running 可见性，不据此授准入或等待资格。query/lookup 本身不冒充新提交。 |
| 等待与唤醒 | `managed_wait.py:77`、`:124` 使用同一映射；queued/cancelling 等继续等待，不提前唤醒或封存。终态仍经 record_observation 验证，`wait_and_wake` 保留原总预算、暂停检查与原 continuation.wake_start，未新增授权/重试。 |
| cancelled 传到科学读者 | `managed_wait.py:155` 的 wake packet、`history.py:229` 的归档及 `:261` 的复核、`lineage.py:413` 的 A 视图保留 native_state。工程 known_failed 不构造科学否定结论，也不据此生成候选。 |
| 保留 R0 | dispatch 与 reconcile 的 `replay_check.complete` 仍在既有观察确认后调用，未改 optional 能力或重放规则。 |
| 实现身份 | `experiments.freeze:250` 自动把 `inspect.getfile(execution_status)` 加到既有 code proof 集合；提到共通模块的映射和 pending 常量仍随原配置冻结，未依赖插件作者额外声明。 |

最终四处增量已复核：progress 不额外要求 submission 的理由与 `local_experiments._state` 的原 process 身份验证一致；cancelled 准入明确检查返回 observation 的 native_state，而非只调用观察函数；默认等待 reason 与内部循环改为 pending 中性命名，未发现旧 reason 的代码消费者；helper 的源文件纳入 freeze。与实施报告的八文件冻结范围一致，P3a 同期差异未纳入本结论。

## 最小负控是否能证伪实际行为

- `test_composed_execution_results.py:180` 通过独立的字面状态序列和预期，检查实际 dispatch/progress/CLI。若漏拦 queued/cancelling/未知状态、伪装 running、创建第二 call、修改旧原件，原 call 数及逐文件字节断言会失败。它未导入生产 pending 集合来生成预期，不是同源常量自证。
- `test_async_without_collect_reconciles_same_call_before_seal:92` 在既有用例加 cancelled 情况。若控制层丢失 cancelled、接受 observation 篡改/删字段、历史或 A 视图丢失原因，断言会失败。禁止后端再读的负控检验重复 reconcile 复用冻结 observation；不是只检查成功 JSON。
- `test_reconcile_rejects_changed_original_identity_and_native_evidence:166` 的新增 backend-acceptance 篡改，验证共通路径确实调用适配器的原件身份校验。其 native 验证器属于 synthetic fixture，因此不能独自证明真实 TCAD/远端后端的校验语义正确；accepted/interface、submission 和冻结 proof 的共通检查仍有独立价值。
- `test_one_run_waits_without_llm_then_automatically_wakes_same_session_and_seals:83` 增加一个 queued→cancelling→cancelled 情况，复用原有真实本地控制进程和注册接口 seam。若 queued/cancelling 提前结束等待、重复启动 W/提交、唤醒 packet 丢 cancelled 或封存丢原因，观察到的 call/launch 次数及原件断言会失败。模型与后端均为确定性替身，不能称真实模型/求解器验收。
- `test_uncertain_execution_is_not_running_or_replayed:177` 保留 unknown 单项；accepted/submitted 改为 pending 后，其行为由直接状态循环覆盖，未为每个拼写重复整套进程场景。

新增检查复用既有小型接口 fixture，没有安装或构建依赖。fixture 中的 `execution_status` 只用于模拟后端 collect 的终态可用性；关键 pending 预期及 cancelled 保真断言独立写明。不能因为调用 subprocess 就声称后端真实性已获证明。

## 限制

本轮只验证共通适配协议与消费者的静态一致性；真实适配器须自行验证 pending 和终态原件，真实 TCAD 接线、取消请求到远端的行为留给后续节点。未执行进程等待/超时测试，不能证明时序稳定或资源峰值；没有推断此前 OOM 根因。科学结论、正式独审、来源资格和执行授权均不在 P2a 完成范围内。
