# 项目缺陷与遗留问题独立审计（2026-10-16）

结论：**存在可复现发布阻断、普通 W 封存时序缺陷，以及尚未完成的通用候选产品闭环；不能给整个项目 PASS。** 两项已合入的 P2（launcher tier 传播、closeout 限制省略提示）不再重报。

本报告只读审查生产代码，未修改、commit 或 push；所有补测脚本、受控实例和结果只写 `/tmp`，未运行收费模型、真实 solver 或外部提交。应用 `scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks`。审查者未参与这轮生产实现。

## 1. 审查对象与证据边界

- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；分支 `dev`；起始及受审生产 HEAD：`5251ee05c029774200d77a07bb9f69e403dc22bf`。
- 起始无受跟踪改动，仅原有未跟踪证据目录。审查中另一执行者按用户授权清理历史工具/夹具并修复 `test_native_cli.py`，主线程调整入口文档；本审查没有覆盖其改动。收口时 `git diff -- src/scidiscovery pyproject.toml scripts/build_git_release.py` 为空，以下生产缺陷仍对应上述 HEAD。
- 追踪新 `scid-research`/`scid-experiment`：prepare → 冻结 job/profile → durable runner/watchdog → 观测用量/预算 → W 受管输入和结果 → 科学封存 → lineage/history → shortlist/audit/delivery/closeout；并追踪旧 `scid` → MCP proxy/daemon → installed catalog/runtime factory → Run/Artifact/Execution/Approval → UI 读取与决定。
- 检查发布 builder 的实际 allowlist/copy/scan 路径，核心和 TCAD 的 entry points、原始材料绑定及现行架构/宪章/约束/CLI 文档。历史评审只用于定位，结论以当前代码和本次反例为准。
- 这是按高风险边界的项目审计，不是全库逐行证明。没有运行完整 pytest、installed wheel、真实 daemon/process/UI 浏览器场、真实模型或跨域研究。旧 MCP/TCAD 的历史验证不自动赋予当前薄 CLI 资格。

关键受审生产文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `research_loop/native.py` | `575fcedebaa89a66df41dad8ab40485ff481e87b2ca6cdccccab90ac78d53b2c` |
| `research_loop/runtime.py` | `ddacca632029a5981f6e6c7f090fb6b29436afdf462a240afc22c3d5718f5125` |
| `research_loop/contracts.py` | `e1a8a1e34912397ddf13ff1ee49a9a242c892bb3c24a31c1fba85ca131b0012d` |
| `research_loop/worker_delivery.py` | `3f3aeedf6de5a80787e375c53ae916941c8f553e8dffbc5cf7d5e2d73afd0983` |
| `scripts/build_git_release.py` | `f274cd811edc658f016e1cdde3a8999e276a540f1a088a35191a1c2c8f1d2739` |

## 2. 确证 bug

### B1 — P1（发布阻断）：源码发布扫描器拒绝自身测试中的合成秘密/路径负例

**定位。** `scripts/build_git_release.py:31–41` 复制完整 tests；`:194–226` 对所有复制文本无差别执行秘密与用户路径扫描；`:326` 在 manifest/archive 生成前执行该扫描。

**可达触发。** 直接运行当前发布入口：

```sh
python -B scripts/build_git_release.py --source <本仓库> --output /tmp/scid-project-audit-release-20261016/release
```

在没有受跟踪生产改动的当前 HEAD，退出 1。精确错误为 `release scan failed`，命中：

- `tests/operations/test_artifact_capture.py:252` 的合成 `BEGIN PRIVATE KEY`，`:834` 的 `/home/owner/...` 拒绝样本；
- `tests/operations/test_capture_path_views.py:96` 的合成 key，`:117` 的 `/home/unknown/...` 拒绝样本；
- `tests/operations/test_ledger_capture.py:22,284` 的 `/home/fixture/...` 负例。

这些是检测规则的输入夹具，不是实际秘密。本反例不把扫描失败解释成泄密。发布 builder 因而不能完成文档所声明的 Git 源码目录/tar.gz 交付入口，也不会生成本次 manifest/archive。

**最小修复。** 保留生产秘密扫描，将合成负例按构造方式表达，避免在发布源码中嵌入 scanner 禁止的完整模式；或为明确、可核对的合成样本设计窄处理。不要全目录豁免 tests，更不要关掉扫描器。用当前发布命令验证真实交付生成，并保留一个真实秘密负控确保仍拒绝。

**证据。** `/tmp/scid-project-audit-release-20261016/{probe-result.json,build.log,resource.json}`；启动脚本 `/tmp/scid-project-audit-supervise-20261016.py`。监督耗时 0.617 秒，tree RSS 高水位 46,075,904 bytes，cleanup 完成。

### B2 — P1（独立发布闭包阻断）：发布树携带新测试，却遗漏其脚本与冻结夹具依赖

**定位。** `scripts/build_git_release.py:43–92` 的 DOCUMENTS/TOOLS 白名单没有 `scripts/acceptance/rootless_cov_launcher.py`、`rootless_public_selection_replay.py`，也没有 `docs/plans/fixtures/rootless-selection-actions-v1.json` 与 `rootless-selection-v1.json`；同文件 `:317–322` 仍复制所有 tests。

**确定消费者。** `tests/research_loop/test_public_selection_replay.py:12–14` 在收集时加载 replay 脚本和冻结 fixture；`test_selection.py:10` 使用 selection fixture；`test_rootless_fragments.py:18` 加载 cov launcher，`test_role_profiles.py:14` 又导入该模块。namespace/resume 测试也调用同一 launcher。它们是当前测试消费者，不能靠删除这些测试假装发布闭包完整。

**实际负例。** B1 失败前已经按白名单复制出 stage；对这个未改的复制树，以独立 cwd、该树自身 src/PYTHONPATH 执行：

```sh
python -B -m pytest --collect-only -q -p no:cacheprovider --test-lane source tests/research_loop/test_public_selection_replay.py
```

退出 2，`FileNotFoundError` 明确指向 stage 缺失的 `scripts/acceptance/rootless_public_selection_replay.py`。因此即使 B1 的扫描问题修好，发布树的测试仍不能正常收集。补一个脚本后还需闭合它和测试的冻结数据依赖，不能只修首个 FileNotFound。

**附带文档缺项。** 发布白名单没有 `docs/ROOTLESS_CLI.zh-CN.md`。当前主线程新增的 README 薄 CLI 链接若随原 builder 发布，将形成断链；新用户也拿不到该入口的操作/恢复/资格限制。此项是可用性债务，主阻断是缺失的运行/测试依赖。

**最小修复。** 明确哪些 rootless 入口与验收工具属于发布支持范围，补齐其精确依赖闭包与冻结 fixture；在生成源码发布树中完成收集和一个窄无模型入口回归。不要把所有 `.trial` 历史数据或 acceptance 脚本盲目塞进发行包。此处没有建议把测试计数当交付证据。

**证据。** `/tmp/scid-project-audit-release-collect2-20261016/{pytest.log,resource.json}`；监督脚本 `/tmp/scid-project-audit-collect-supervise2-20261016.py`。0.392 秒，tree RSS 高水位 58,372,096 bytes，cleanup 完成。第一次试图切 cwd 的监督调用实际仍在原仓库运行（guard 固定 cwd），那次原树收集通过**不构成发布证据**；第二次 bootstrap 明确切到 stage，是本结论采用的负例。

### B3 — P2：普通 screen W 把“原生终态已发布”误当作“原 runner 已退出”，偶发提前返回 seal_pending

**定位。** `research_loop/native.py:94–106` 看到 terminal 即进入 `continuation.seal_or_repair`，只有 `checkpoint.enabled` 时等待 checkpoint；`runtime.py:244–254` 在 `run_native` 发布 outcome 后仍执行 finally 并退出；`contracts.py:885–891` 对适用的 screen W 在无 checkpoint 时要求 writers 已停止；`worker_delivery.py:50–63` 发现原 runner 仍活着就拒绝捕获。

**实际交错。** 默认未配置 worker fragments 的 W，`checkpoint.enabled=False`，但 H 正常选择 screen 时 `worker_delivery.applicable=True`。runner 在 `native.py:478` 原子发布已成功 outcome 后尚未退出，控制器可立即读到 terminal；随后的 writers_stopped 会按正确身份检查拒绝仍活着的 writer。控制器将它暴露为 `seal_pending` 并结束本次 run，H→W→A 推进因此偶发停在 W。

**单次因果反例。** `/tmp` 的 `sitecustomize` 只把实际 W2 runner 写完 `native-outcome.json` 到原退出之间的既有间隙延长 0.8 秒，没有修改生产代码、结果或守卫。使用当前已修好 schema 的确定性 native CLI fixture，首次实际 `controller.run` 返回：

```json
{"status":"seal_pending","completed_steps":1,"next_role":"W","reason":"Native turn completed; host sealing requires repair: Original native writer still owns this attempt; no delivery snapshot can be captured"}
```

返回时原 runner 仍通过身份匹配。等同一原 runner 退出后再次 run，原实例正常 `finish / completed_steps=3`。原 W 不需要重新发起模型请求。反例证明状态交错可达；0.8 秒是放大既有窗口的测试手段，不是声称生产通常存在该时长。

**影响。** 单次 run/continue 会因调度时序提前停止，要求操作者再次 run；正常长链和默认 CLI 回归存在非确定失败。未观测证据损坏、重复外部提交或权限扩大。

**最小修复。** 在封存需要静止 writer 的 W 前，等待同一个原 runner 的终结/就绪边界，或让 owner 在不可再写后发布既有的就绪事实；保留精确身份和未知拒绝。不要用任意 sleep、删除 writers_stopped 或盲目重发 native 来修。补一个延长 outcome 发布后窗口的实际 runner 回归，并证明首次 run 仍可完成、原 intent/usage 不重复。

**证据。** `/tmp/scid-project-audit-race-20261016/probe-result.json`、`/tmp/scid-project-audit-race-resource2-20261016/{pytest.log,resource.json}`；probe 和 supervisor 为 `/tmp/scid-project-audit-race-probe-20261016.py`、`/tmp/scid-project-audit-pair-supervise-20261016.py`。2.585 秒，tree RSS 高水位 123,879,424 bytes，cleanup 完成。

**与原偶发失败的关系。** 另一执行者 `/tmp/scid-native-cli-source-1016-b` 保存了 `completed_steps=1 / seal_pending` 的失败断言；其 pytest 临时实例已清理，日志没有完整 reason，无法认定该次就是 B3。本次独立反例足以证明 B3，不能反向补造原失败的事实。修 fixture 暴露了生产问题，不应删除该默认链路测试掩盖它。

## 3. 当前设计/产品缺口（与确证 bug 分列）

### G1 — P1 产品完成度：通用执行有实现，通用候选—比较—短名单—审计—交付闭环未完成

**事实链。** `local_experiments.py:214–240` 保留命令/指标/成果，但 `candidate_id=None`；`:304–312` 的 status_details 固定 `candidate_id/evaluation_key/metric/direction=None`。`history.py:249–262` 在没有专用 observer 时明确构造 `candidates=[]`、`current_candidate=None`、`actual_submission=None`。`controller.py:119–122` 的 selection_policy 还要求专用公开指标 observer 与隔离交付 adapter；`delivery.py:70–105` 另需显式 resolver/launcher/配置/原件范围。

因此普通 local `result.metrics` 即使 available，也不会自动形成可比较候选，不会进入通用 shortlist、候选审计和外部确认交付链。此处不只是“实现已有，余下一点边界”：对希望安装一个通用科研框架、换领域即能端到端产出和选择成果的用户，这是**尚未完成的核心产品能力**。现在可以执行并保留研究结果，也可以手工/科学判断比较；不能据此宣称已经提供通用候选选择和交付平台。

**最小后续范围。** 先定义可选候选/目标口径/成果身份的跨域契约，把明确由领域提供的候选对象接入既有 history/selection/shortlist/delivery；不从任意 metric 名推断候选，不把最高代理值当原始目标。只加 min/max 不够：还需 evaluation 版本和条件、可比范围、实现/模型或成果的确切字节身份、有效性/缺失/失败状态、来源和未决限制。用非 cov 的小型实际插件走通一条可审计闭环，再讨论“通用”。不要求所有临时 shell 都变成候选，也不增加每候选强制 reviewer。

### G2 — P1 产品迁移：两套入口尚未共享实例、权限、能力发现和 UI

`pyproject.toml:26–40` 同时发布 scid/MCP、薄 CLI、execution_interfaces；`artifact_agent/runtime.py:78–145` 的旧服务仍组装 catalog、SQLite instance/Run/Artifact/Approval/Execution，`interfaces/mcp.py:21–85` 及 daemon/proxy 仍是活入口。`approval_ui/read_model.py:34–70` 读取旧 binding/Run/Approval/Execution，没有薄 CLI 文件节点读取链。

薄 W 默认在 `native.py:137–141` 选择 `local_execution:command`；自定义 launcher 的 external 路径由 launcher 配置。TCAD 包 `plugins/tcad_artifact/pyproject.toml:20–24` 只有 scientific plugin 和 instance view 注册，没有新的 execution_interfaces 注册。安装 TCAD 插件不等于薄 CLI 获得 TCAD 的执行授权、诊断、恢复、结果解析或资格链。local、cov、TCAD 必须逐接口列能力事实；例如 local 只声明 lookup/query/collect/atomic_admission（`:36–37`），未声明 cancel/resume，不能从通用 CLI 命令名推断支持。

**最小后续范围。** 维护一份可执行入口/能力矩阵与冻结实例 capability 摘要，显式标出哪个入口、adapter、隔离、审计/交付、恢复方式可用；迁移一个有真实消费者的接缝再收敛实现。当前主线程已补 README/docs 索引入口说明，这改善发现性，但没有完成运行时迁移。旧入口仍生产注册，有大量实际消费者，不建议仅因“旧”删除 daemon/UI/TCAD 或对应测试。

### G3 — P2：unknown 和跨 boot 仍是人工恢复断点，普通 status 也可能不可用

`runtime.py:100–120`、`native.py:112–116` 保留丢失原 runner 身份的 unknown、不重放；`experiments.py:418–421` 遇任何未知原调用会拒绝新接受。`budget.py:28–29,125–164` 在 boot 改变时拒绝消费区间，CLI status (`cli.py:44–47`) 也需要该 snapshot。文档诚实声明人工修复，但当前 CLI subcommands 没有带审计的跨 boot reconciliation/恢复工具。

拒绝重放与不退款是正确底线；产品缺口是操作者尚无正常入口查明并终结这类保留状态，可能只剩编辑控制原件。长期无人值守不能只拿“前台控制器断连后同 boot 重连”当主机重启恢复资格。

**最小修复方向。** 先提供不依赖可验证预算的只读原调用诊断，再以原身份权威查回/显式审计终结未知范围与 boot 边界；不能重发以代替查明，不自动退款或扩额。需单独 host-reboot/unknown 的受限验收。

### G4 — P2：公开数据和环境未纳入完整不可变输入，复现范围不足

`controller.py:123–124` 对 public_root 只冻结绝对路径；`contracts.py:412` 直接交给科学角色，没有对应全局数据清单/哈希。local 只快照选择的实验目录 (`local_experiments.py:70–84`)，执行解释器、环境、库、外部导入、绝对 argv 路径未被完整冻结。

同一 job/科学 seal 可依赖在运行期间改变的公开数据；当前可证明的是指定快照和收到结果的字节，不是科学执行读取了所有快照，也不是完整环境可复现。这是明确范围缺口，不是指控软隔离被突破。

**最小修复方向。** 允许操作者显式声明有界数据原件/数据集版本和环境指纹，并准确展示“保留了哪些输入、实际读取哪些未经观测、哪些环境未保留”；不要扫描全盘猜依赖。

### G5 — P2：自身 native 传输和普通成果采集尚无完整资源止损

`native.py:301–341` 持续写 stdout JSONL/stderr，只限制 pending 单行 64MiB，没有 native stdout 总量、stderr 总量或磁盘总量上限。`contracts.py:454–517` 普通 native artifacts/嵌套 experiments 按内容字节限额，但没有文件/目录项数量、路径元数据总量、递归深度或采集时长界限；大量空文件不消耗内容额度。local `files()` 的 1024 扫描项与128文件限制并未覆盖该普通成果采集路径。

**影响与修复方向。** 正常科学工具大量日志/小文件也可使磁盘或封存元数据增长超出 token/time 的直观限制。应给框架自有传输/采集加总量、数量、元数据和截止限制，保留明确 unavailable/omitted；不要把测试 supervisor 的外部资源上限写成产品 runner 已有保证。本次仅静态追链，不声称已发生填盘/OOM。

### G6 — P2 产品路由：deliver 与“交付后继续研究”不能同时表达

`controller.py:323–324` 将 A 的 finish/deliver/wait 都路由到终止；`:529–532` 的 deliver 开始 closeout；`:366–367` 此后所有 run 固定进入 closeout。当前合同可表达“选择提交”“结束探索”“等待”，不能表达“先提交可用候选，再按原授权继续未满足目标”。对持续探索目标，阶段性可交付不应天然耗尽全部科学推进能力。

这是当前显式合同的能力缺口，不把合法枚举执行本身算程序 bug。最小后续是让科学角色明确声明交付与继续/结束的关系，并绑定原预算和原资格；不从自然语言猜隐含授权、不自动重启全新实例。

## 4. 测试与文档债务

1. **旧 fixture 失配不等于 production 无事。** 起始七个 CLI 失败主要源于替身未产当前 schema 必填字段及旧断言；这些应修 fixture/断言，不能直接删默认 H→W→A、pause/continue、status 只读和交接测试。另一执行者本轮正在修复，实际结果由其独立批次记录。本审查不冒领其通过数。B3 说明旧红测试在修通之后能暴露真实生产缺陷。
2. **发布验证和源码验证必须分开。** B1/B2 证明本地 src 路径可收集，不能代表生成 release tree 可构建/收集，更不能代表 installed wheel 入口。下一批发布门应在实际生成树内验证，包含负控。
3. **当前架构说明需要作用域。** 宪章与 `docs/ARCHITECTURE.md` 的“唯一 OperationSpec/CompiledCatalog/单注册入口”描述适用于 MCP 科学平台，薄 CLI 实际有自身冻结 settings/job、protocol18 和 execution_interfaces。主线程已经在 README 与 docs 索引区分入口；后续应同步架构/发布与薄 CLI 的责任边界，不能把旧约束的 conformant/pending 状态直接外推到新入口。
4. **历史计划不能充当当前资格。** `docs/plans/README.md` 仍包含多个不同日期的“当前实施入口”及较早的 T2–T5 状态，与较新的 thin CLI/工程计划并存。需要归并当前索引、将旧节点标历史，而不是删证据来闭合问题。`SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 SEC-002、UI-001、RES/MIG pending 属保留问题，尚未被本审查重新资格化。

## 5. 未验证能力与静态疑点（不列成确证 bug）

- **通用 local 历史第9项以后指标/成果的当回合补读。** `lineage.py:369–375` 每 call 固定只投影8指标/8输出，外层分页仅按 call；没有内层指标/输出 continuation/ref。完整原始 result.json 被保留且直接前驱可读，非直接祖先材料需 `implementation_selection` 交给后继才挂载 (`contracts.py:243–259,593–614`)。尚未证明隔离中的当前角色能读到遗漏内容；也未证明其完全不可恢复。准备的12指标/13输出 W2→A3→H4 probe 在临时发现 metadata 重复处失败，未接受实验，本次按要求收口不扩跑。应以后用一个已安装/隔离无模型小例验证当前回合是否可按需取回，再决定补完整 receipt 分页或明确延后读取规则。不能把“有 omission count”当已有可补读入口，也不能凭静态片段宣布证据已丢失。
- 当前薄 CLI 真正 E 原件提取、多域科学闭环、长期负例/旧实现找回、同线程/new-context 长阶段记忆、异构角色模型的效果，未取得本次独立行为证据。
- raw Codex 与所有第三方 launcher 的权限、脱离进程组后代清理、真实服务模型/tier 接受性和实际账单，不由 argv/记录一致性独自证明。共享 UID 软隔离仍是当前显式范围，不把提示词当强沙箱。
- 旧 daemon 的真实重启/恢复、TCAD solver、UI人工审阅可用性、实例归档/恢复和真实部署回滚未重跑。静态看到执行审批仍核对精确 request/payload/compiled identity (`service/executions.py:405–449`)，UI决定仍经 loopback/Origin/token/nonce/CSRF 和写守卫 (`approval_ui/app.py:855–942`)，提交丢失走 exact lookup 而非盲重发 (`execution_bridge.py:93–102`、`execution_submission.py:159–173`)；这些是检查过的路径，不是整体资格声明。

## 6. 精简判断与下一批修复顺序

本轮没有发现足以支持删除整个旧 MCP/daemon/UI、把两套状态机直接合并，或弱化不可变原件/unknown/审批边界的证据。两个入口各有已注册消费者与不同持久化合同；“旧”不是零消费者证明。已确认的精简对象应由另一条测试清理工作逐项提供消费者证据。

建议下一批按根因与可验收范围推进，每项独立提交/定向验证：

1. **先修 B3 正常推进竞态。** 保留当前默认 CLI 回归；用单次 post-outcome delay 精确验证首次 run 完成和原请求不重放。它直接影响用户一次运行能否继续。
2. **合并处理发布闭包 B1/B2。** 保留秘密拒绝；修合成负例表达，补受支持的脚本/fixture/CLI手册；从实际 generated tree 完成 build→收集→一个无模型入口，再做 required installed gate。修复之前不宣称可交付 release。
3. **给 G1 单独安排产品节点。** 先冻结一套跨域候选/评价口径/工件身份契约，走非 cov 的小型完整例；再接现有 shortlist/audit/delivery。不能以增加一个 min/max 字段充当通用闭环完成。
4. **随后补 G3 的可诊断恢复，再补 G4/G5。** unknown/跨boot不重发底线保持；明确输入复现范围，给框架自身磁盘/目录元数据止损。分别有独立负例，不扩大成一次大重写。
5. **保留 G2/G6 与科学效果为显式后续。** 入口/能力矩阵同步当前字节；交付后继续的产品语义应先明确；真实多域/长期/效果试验另需冻结任务、预算与评估，不由本轮工程审查顺带启动。

本次所有实际 probe 都经过仓库 `serial_lock` 和 `run_one` 资源监督；锁忙时未绕过、未启动测试。未运行完整 suite，未把相关局部通过或旧报告 PASS 外推整个项目。未进行本轮生产修复。
