# 审计工程故障分类与有限恢复（协议 18）

基线为 `ccb3612`。实现位于独立 detached worktree `.trial/closeout-engineering-repair-worktree`；创建 worktree、测试均遵守共享 serial_lock。主工作树、安装目录、协议 17 正在运行的真实场及旧实例均未修改。没有真实模型、增预算、git commit 或 push。

## 实际修复范围

公开 harness 在缺脚本、训练异常、超时等场景仍可能 exit 0，写出 `audit_score=null/leakage_flag=false`。原代码将这些场景与完整审计拒绝统一为失败，最终交 A 改选。本次由领域适配器依据冻结回执的明确字段与已知模板返回 typed 结果：

| 结果 | 意义与路由 |
| --- | --- |
| audited | 完整、有限且不泄漏的审计；模型字节必须匹配绑定原件。 |
| rejected | 完整审计明确不合格；模型字节同样必须匹配，交 A 科学判断。 |
| engineering_error | 脚本准备、依赖、训练、预测、进程、资源等已知工程故障，先有限工程恢复，不冒充科学拒绝。 |
| unclassified | 缺回执、错误结构、无法可靠分类或原件身份异常；保留诊断，不推断通过、泄漏或可重试原因。 |
| unknown | 执行/清理或外部提交未知，只核实原操作，不重放。 |

新增 `audit_recovery.py` 共用候选 audit、shortlist audit、最终 delivery audit 的一次控制恢复。恢复前冻结新 intent，重新准备 scratch 输入，按原总余额和原单次上限接受一个额外计步动作。恢复 outcome 绑定 intent 与实际进程；已接受而未结算的恢复会阻止新执行。恢复不会重放真实 promote/confirm，也不自动修改 adapter、冻结库或安装环境。

新增 `engineering.py` 绑定精确故障回执、原候选、原 W seal 和声明输入。已封存 W 只能生成新 repair W；相同 original_candidate lineage 最多一次。新 W 的注册工具限定为一次精确 parent 调用，拒绝新计划、换 parent 和重复调用。新模型/脚本作为新候选，A 重新判断并明确授权；历史 seal、模型与结论不能覆盖。普通任务保持普通科学路由；收口只允许此精确工程修复例外，不重新开放任意探索。未封存的已知中止 repair W 可复用原 session，原累计预算与次数限制保持。

修复 W 的原件只增补到后续候选目录；原 source_cutoff、旧 job 与旧筛选不变。选择策略按修复 W step 冻结新代筛选/比较，旧故障实现保留并标为不可执行，不能重新变成默认。状态从当前代 intent/outcome 导出。输入容量、原余额、未知用量、暂停和未知操作继续准入；缺少可绑定来源或冻结环境无法支持修复时不能自行发明原件或扩限。

协议升级到 18，旧 17 及更早实例只读归档，不能原地续接或热升级。native.py 未改；另两线的 token 计量与 role profile 由父代理集成后共同验收。

## 无模型验证记录

所有 pytest 经 `scripts/run_tests.py --lane source` 默认资源监督与串行锁执行。日志完整保留于以下 `/tmp/engineering18-*`，不删改失败尝试。

| 运行 | 结果 | 处理 |
| --- | --- | --- |
| smoke | 4 passed, 10 failed；13.26s | 配置多传 None 字段与筛选引用变量覆盖；收窄到真实可选工程配置并固定 catalogue 引用。 |
| smoke-recheck | 13 passed, 1 failed；26.57s | 旧 audit 错误断言按新 unclassified 语义调整，不放宽成功条件。 |
| worker | 11 passed, 1 failed；10.01s | 普通 audit 测试未启用能力，实际尚未触发工程路由。 |
| ordinary-debug | 1 failed；1.78s | 确认该夹具把 unavailable 当成工程审计；冻结启用正确能力。 |
| worker-recheck | 12 passed；17.64s | 普通/收口依赖故障→新 W→新候选→新 A 授权；实际 experiment CLI 与 bwrap audit。 |
| boundaries | 17 passed, 3 failed；48.85s | 新增负例夹具误解包 prepare_fixture 返回值，未进入被测逻辑。 |
| boundaries-recheck | 19 passed, 1 failed；50.47s | 已到 deadline 而未启动的 audit 被无效回执覆盖；改为明确工程超时。 |
| regression | 103 passed, 15 failed；六文件 | 20 工程、6 策略、19 closeout、13 candidate audit、8 isolation 通过；15 个纯比较测试暴露目录 helper 不必要读取 settings，已修。 |
| supplement | 77 passed, 1 failed；45.34s | control selection 52、budget 24、未封存 W 同 session 续接通过；新 selection→W 夹具错误附加 A 专有 JSON 字段。 |
| selection-fix | 2 passed；15.44s | selection 工程→W→A 与原 session 续接/已封存不重写通过。 |
| final-check（中间） | 22 passed；69.61s；后 delivery 12 passed, 1 failed, 2 skipped | 原 _call 超时测试期待 None；精确调整为 typed timeout 异常，并保留真实子进程清理断言。 |
| malformed-receipt | 4 passed；7.89s | 独审发现无效 JSON 二次解析问题；非法 JSON/数组/null 实际 leaf 均 exit 0 且稳定 unclassified，无工程重试。真实超时子进程也确认清理。 |
| review-fixes | 5 passed；18.52s | 完整拒绝的模型缺失/替换不产生科学结论；selection 非分类/不可控制修复故障的 run、status、重启投影一致；正向 selection 修复仍通过。 |
| capacity | 1 passed；5.14s | 原输入容量不足时冻结精确准备失败回执，不接受 Worker；run、status、重启保持同一原因。 |
| final-remaining | delivery 13 passed, 2 skipped；audit_handoff 2 passed, 7 failed | 交接测试缺少源码 entry-point fixture，在独立 worktree 注册前即停止；补显式 fixture 引用，不改变生产发现机制。 |
| final-boundaries | audit_handoff 9 passed；56.81s；current_protocol 40 passed；2.25s；budget 24 passed；0.46s；prelive 10 passed, 1 failed, 3 skipped | prelive 原断言只准一份审计 stderr，有限工程恢复实际产生两份；调整为审计必须一次恢复与两份精确 trace，其余阶段不得重试。 |
| final-last | prelive 11 passed, 3 skipped；7.19s；cov_delivery_lineage 10 passed；7.18s；control_selection 52 passed；30.34s；registered_experiments 14 passed, 2 failed, 1 skipped；11.84s | 最后两失败位于未修改的注册测试：实际 CLI 生命周期及控制模块隔离已通过后，安装插件 metadata 断言发现空 entry-point。独立 worktree 无 wheel/egg-info；需要三线集成 fresh wheel 重验，不伪造插件 metadata 或放宽断言。 |

独立审查确认并修复：非法回执只解析一次；完整拒绝前同样检查审计模型 SHA；selection typed 早停由同代原件重建 status。输入容量准备失败也保留精确、有限的控制回执。最后受影响回归结果见上表。

最后源回归的两个安装前置失败保留：`test_cli_discovery_and_lifecycle_do_not_load_control_plane_services[local/cov]`。`test_registered_experiments.py`、`pyproject.toml`、`tests/conftest.py` 相对基线无 diff；项目声明 `builtin/general_science` 插件，但当前解释器实际 `scidiscovery.plugins` entry-point 为空，`src/*.egg-info` 也为空。3 个 prelive 全链测试因未安装 CURRENT18 跳过。上述不构成安装包通过证据；集成后必须用新 wheel、独立环境及 `python -I` 完成真实入口资格。

`git diff --check` 最后在共享 serial_lock 下通过。测试均以默认资源上限完成或明确失败，无资源上限提升。

独立只读核心复审最终 PASS：审查者逐项核对三项 P2 修复、容量 receipt、`malformed-receipt/review-fixes/capacity` 的日志与资源结果，以及 whitespace 检查；无剩余源码阻断。安装 metadata 两项失败仍保留 fresh-wheel gate，不以源码复审关闭。复审者未重跑测试、调用模型或修改文件。

## 明确限制

当前证据为确定性 native 运输、真实注册 CLI 与 bwrap 适配器，不证明真实模型行为、隐藏目标效果或科学任务完成。自动恢复不解析任意 shell 输出；原生公共 exp submit 保留权限，其 exit 0 不授予控制交付资格。只封存单个 source.py、模型与声明静态输入；任意 sibling import 不递归捕获。缺少足够科学依据的原件不能伪造，Worker 应报告需要 A 的科学决定。冻结 runtime/harness 不可由控制恢复热改。

本线尚未构建/安装新 wheel；父代理计划三线按依赖集成后统一 fresh wheel 无模型验收。尚未运行全库 pytest、真实 Codex/solver、真实数据科学资格或远程 TCAD。
