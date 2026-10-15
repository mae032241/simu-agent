# Research loop 收口合同一致性修复（协议 17）

基线：`e255a08533d11f9dbacb5bbb10a5eac733cb07e1`，`dev` 工作树。修复范围为新 `research_loop`；没有执行真实模型、修改真实场实例预算、提交或推送。临时预算测试夹具按测试场景调整额度，不作用于真实场。协议 16 真实场及旧证据只读保留，不能用协议 17 误续接。当前读写入口沿用 `require_current`，旧场只允许归档查询。

## 科学授权与机械交付

普通 A 的封存 `next_action=deliver` 直接成为控制层收口授权，绑定精确 A job/raw/seal，不经过 E。未配置选择策略时保持 H/W/A 三节点交付；显式配置 `selection_policy` 时先执行冻结的 control screen，再由精确 closeout A 按默认与显式 override 合同比较，普通 deliver 不能绕过。控制层从冻结科学前缀发现候选，按所选候选解析并冻结原件，适配器执行隔离 audit → promote → confirm。`delivery_confirmed` 只确认精确工件交付，`goal_completion=not_asserted` 保持全局科学目标未断言。

`finish` 结束科学探索，收口 A 的 `finish` 表示拒绝交付。`extract` 仍是科学证据请求：普通 A → E → A 有效，E 不承担模型复制、封装、脚本路径解析或提交。收口已关闭探索，`extract/continue_w/revise_h` 的原输出保留并触发最多两次作者补正，不能被静默翻译为交付授权。

适配器已有的局部台账改写把审计 `script` 指向 `/inputs/source.py`、`model_path` 指向 `/inputs/artifact`。受管 call 的脚本、模型、row.json 来自精确封存原件；旧 W scratch 和当前可变 call 文件不能取代该身份。审计命名空间不扩大到旧 W workspace。只处理单个声明脚本、模型与静态输入；任意兄弟模块、未声明的本地 import 和依赖环境不递归捕获，缺依赖应审计失败，不能声称任意脚本均受支持。旧 v1 observer 仍明确标注为当前源快照，不冒充受管历史原件。

## 十项独立核实与处理

| 审查项 | 原可达缺陷与本次处理 |
| --- | --- |
| 1 | closeout schema 与 controller 动作冲突。明确区分 `deliver/audit/finish/wait`，其他角色合法动作有限补正，原文不改写。 |
| 2 | extract 被用来复制与提交。普通封存 deliver 直接进入控制交付；E 保留科学提取职能；隔离适配器只读选中原件、改写局部路径。 |
| 3 | 审计资格、原件可用性及未知泄漏槽混杂。公开源视图区分 availability 与 scoped audit qualification；receipt 给出精确工件适用范围，历史投影保留 artifact_binding，移除无根据的 leakage_flag=null。匹配未知仍不得升级成历史候选资格。 |
| 4 | 已知 closeout A 失败被 closeout 条件禁止续接。共享 worker-resume 允许精确 closeout A，同 session/job/home，保留原累计预算、attempt 上限和未知执行拒绝。 |
| 5 | 提交前确定审计失败永久卡死。失败 receipt 记录 failure_phase；只有 cleanup 已确认且 audit 阶段失败能改选。相同失败候选工件不能重投。promote/confirm 失败不进入此改选路径。 |
| 6 | 正常 audit 与作者错误共用三轮。正常 audit、确定失败改选受原共享预算约束；仅无效作者选择消耗补正额度，重启重建相同计数。 |
| 7 | 可选审计未保留后续 A token/时间。soft closeout audit 保留后续完整 A 目标及外部底线；新 A 的 controller 准入检查声明目标与外部动作额度。 |
| 8 | 前 128 个历史候选及 16 项摘要遮蔽晚期推荐。冻结完整轻量目录并给 A 精确文件定位，只对选中候选/shortlist 冻结原件；第 140 个候选有实际入口反例。 |
| 9 | 临时准备失败固化 export_only。准备失败单独保留，可复用同一封存作者在原预算内重试。预算不足保留待执行 model 边界；显式 export_only 独立。清理未知封锁重试。 |
| 10 | 终态推荐停留于 source_cutoff。状态从同一原件重建，采用最新封存 closeout A；历史提交观察与当前确认结果保持独立。 |

来源目录本身仍有 256000 字节显式上限，历史科学候选也受既有上限约束；超过边界显式失败，不隐藏省略或声称无限长场。摘要按完整 ID 的实际 UTF-8 字节逐项纳入并计数省略，不截断身份。选中原件沿用单件/总量、解析时间和 adapter scope 的原边界，未扩大旧工作区挂载。

## 验证记录

所有 pytest 使用 `scripts/run_tests.py --lane source` 的串行锁、资源监督与确定性本地进程；没有模型调用。日志保留在相应 `/tmp/closeout17-*` 监督结果目录，失败尝试未删改为通过记录。

| 运行 | 结果 | 处理 |
| --- | --- | --- |
| baseline-check | 97 passed, 4 failed, 2 skipped；62.50s | 当前合同所需字段/旧协议测试前提与新的有限补正预期修正。 |
| entry-check | 7 passed, 1 failed；65.13s | CLI 对保留失败返回码 2 的合法约定修正到测试驱动。 |
| regression-check | 153 passed, 10 failed, 2 skipped；186.25s | 区分未知清理与可查询原操作；补旧 fixture 的预算身份、当前协议与必填字段。 |
| direct-check | 7 passed；41.78s | 普通完整 H/W/A 进程直接交付、真正 E 科学路径、未知操作阻止重放、合法动作补正、资格历史传递。 |
| mechanical-check | 1 passed, 3 failed；4.82s | 两处普通路由 fixture 指令身份与负例 adapter 副本协议定位修正。 |
| mechanical-recheck | 4 passed；12.69s | 普通缺选择补正、确定失败改选、旧 W scratch 命名空间正负例全部通过。 |
| final-check | 18 passed, 1 failed；98.59s | 实际发现 audit 自身尚未启动 intent 被来源准备误拦为 unknown，已修正准备检查范围。 |
| final-recheck | **205 passed, 2 skipped**；监督耗时 283.901s | 12 个目标按文件串行通过；两项跳过需要原始公开 harness 与独立 task runtime。 |
| reserve-check | **3 passed**；4.85s | soft 可选审计保留后续 A 的 token/时间，UTF-8 完整 ID 摘要边界。 |

首轮共 **208 passed, 2 skipped**。`git diff --check` 通过。`final-recheck` 目标为 `test_closeout_protocol.py`、`test_closeout.py`、`test_closeout_search_replay.py`、`test_candidate_audit.py`、`test_control_selection.py`、`test_audit_handoff.py`、`test_delivery.py`、`test_cov_delivery_lineage.py`、`test_current_protocol.py`、`test_budget.py`，以及普通同 session 成功续接与未接受 intent 不重放两个 `test_worker_resume.py` 节点；`reserve-check` 单独运行 `test_closeout_reserve.py`。精确测试目标和每批资源/返回码保留于监督结果 JSON；final-recheck 使用 `--per-file`，reserve-check 为单批。

实现检查另发现并修正 `freeze_sources` 的 evidence label 被 execution object proof label 覆盖问题；受管原件回归现断言 selected source 的 ledger SHA 仍对应候选封存公开台账。

首轮未运行完整仓库 pytest、真实 Codex/远程 solver、真实数据科学验收或新的安装 wheel 门禁；后续 fresh wheel 门禁记录在文末。没有包装和依赖元数据修改；本地进程与隔离适配器证据不等价于真实模型资格或未知外部提交的成功确认。

## 独立复审后的入口补正

生产 `prelive_gate.py` 的普通科学 `finish` 保留；收口末次 A 及 fake native 在审计后均显式 `deliver`。源目录按 `availability` 读取可用性，审计资格要求 `status=audited` 且 `qualification=passed`。叶子失败测试区分 audit 的 `failure_phase=audit` 与 promote/confirm 原分支，不放宽为任意字段。

可选审计能力从冻结 `candidate_audit_policy` 宣告，禁用时 native 动作选项排除 audit，科学视图给出 `audit_capability.available=false`。通用请求 schema 保留 audit 请求表达，以便返回明确 `unavailable/candidate_audit_disabled` receipt；执行准入在任何解析或 adapter 外调之前拒绝。已接受 intent 的计步、未知检查独立于此能力开关，配置异常不能隐藏原件。status 与 run 都从相同 audit facts 投影未知状态，低预算不能把未知显示为待执行。

显式选择策略下，普通 deliver 先进行冻结 screening，再新建持同一精确 comparison 的 closeout A；默认候选与 override 仍按原策略比较。此正常比较不占作者补正次数。不配置选择策略保持原 H/W/A 三节点机械交付。

原生 shell 权限与公共 `exp` 命令保留。受管 wrapper 在 submit/help 时只向 stderr 输出警示，随后保留原参数执行公共 CLI；警示说明公共 submit 不解析历史跨节点原件，历史交付应选择 A deliver。通用 native 提示给出同一说明；没有自然语言分类、自动改写提交、禁止 shell 或扩大 E 可见目录。

| 追加运行 | 结果 | 说明 |
| --- | --- | --- |
| prelive-entry-check | **11 passed, 3 skipped**；6.56s | 实际 fake native 子进程覆盖无审计、通过审计、未知审计和默认/比较分支；安装 lane 仍缺独立运行时。 |
| policy-check | 4 passed, 2 failed；17.32s | 两个异常 accepted intent 测试夹具缺原始 host clock；未进入目标逻辑，已补原始测试时钟。 |
| policy-recheck | **11 passed**；18.30s | 6 个真实 CLI 能力/策略/unknown 反例及 5 个实际 wrapper 进程参数、警示与原退出码检查。 |
| review-regression | **155 passed, 3 skipped**；监督耗时 249.747s | 按文件串行运行 candidate_audit 13、control_selection 52、closeout_protocol 19、audit_handoff 9、budget 24、prelive_production_chain 11（3 skip）、rootless_fragments 27。全部批次 returncode=0，无资源中止。 |

本轮当前源码验证共 **161 个不同用例通过、3 个跳过**：review-regression 的 155 项加 policy-recheck 中 6 个独立策略边界用例；其中 5 个 wrapper 用例也在完整 rootless_fragments 回归执行，不重复计数。`git diff --check` 通过。完整命令为 `python scripts/run_tests.py --lane source --per-file --output /tmp/closeout17-review-regression` 加上述七个 `tests/research_loop/test_*.py` 文件；policy-recheck 精确目标为 `test_closeout_policy_boundaries.py` 与 `test_rootless_fragments.py::test_native_exp_warning_preserves_public_command_and_exit_status`。

上述入口检查时，新 installed 完整生产门禁尚未完成；随后已完成，记录见下一节。`/tmp/closeout17-prelive-entry-check/installed-readiness.json` 记录当前 `python -I` 未安装目标包，命名真实源场仍为冻结协议 16；不能用它续接协议 17 或把 source 测试称作安装验证。当前仓库没有 `validate_architecture_constraints.py` 或 `run_science_control_bench.py`；其他 checkout 的同名脚本不构成本次修复门禁。


## Fresh wheel 安装入口验收

已完成；独立复审 PASS 后只增加此安装验收与证据，没有再修改源码。所有步骤调用仓库 `scripts.run_tests.serial_lock/run_one`，使用 `scripts/test_resources.json` 原资源限制串行监督；完整驱动为 `/tmp/closeout17-installed-wheel/supervise.py`，结果为同目录 `result.json`。没有运行完整 pytest 或真实模型。

1. `python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/closeout17-installed-wheel/wheel <repo>` 构建当前工作树 wheel。
2. `python -m venv /tmp/closeout17-installed-wheel/venv` 新建独立环境；未使用 system-site-packages。用其 `python -I -m pip install <wheel>` 安装 wheel 和声明依赖。
3. 使用新解释器 `python -I verify_install.py`：安装包全部 228 个 Python 模块与当前源码逐文件 SHA 完全一致；`isolated=1`，`sys.path` 不含仓库源码。源模块清单聚合 SHA 保留于 JSON 证据。
4. 从既有 public harness 只读材料与策略重新 prepare **独立协议 17 fixture**，不升级或改写旧场；max_tokens/max_seconds/max_steps 原数值保留。fixture 与实际 gate scene 都在临时目录。旧 settings/launcher/public 全部哈希在所有步骤后再次核对一致。
5. 新解释器以 `-I` 执行当前 `prelive_gate.py`，以新 fixture 为只读源；真实 rootless launcher、bwrap、注册实验 CLI、候选 audit、隔离 resolve/audit/promote/confirm 全链通过。8 节点与 W 两个新 context fragment 如预期，**21 项检查全部为真**，`delivery_confirmed`，`settings_differences=[]`，`repo_source_mismatch=[]`，`models_called=model_requests=0`。
6. 独立 `python -I -m scidiscovery.research_loop.cli status --root <gate-instance>` 成功，状态同为 `delivery_confirmed`。

监督耗时：构建 3.356s、venv 1.424s、依赖安装 67.169s、模块/fixture 核对 0.581s、全链 70.869s（门禁内部 70.8s）、安装后 CLI status 5.922s；所有步骤 exit 0，无资源中止或清理失败。wheel SHA-256 为 `a4dfb091c1b0ced27d57eb401192d74137757bca7bcda2eecff8c2c55b2eac8e`。

持久证据为相邻 `ROOTLESS_CLOSEOUT_PROTOCOL17_INSTALLED_20261015.json`，包含监督命令、逐步资源结果、21 项 gate verdict、导入身份及旧资料 SHA。此安装链保留源配置的 `selection_policy=None`；启用选择策略的默认/override 在此前 source CLI 定向测试覆盖，不能声称此 wheel 链也覆盖启用策略。公共 Ridge 训练由既有 task runtime 执行，native 运输用本地确定性程序；结果不证明真实模型行为、隐藏目标效果、远程 TCAD 或完整科学任务达成。成功后停止扩展测试。
