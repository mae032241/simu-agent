# 上线前生产配置全链门禁（零模型）

日期：2026-10-15。分支：dev。本门禁是任何真实场启动前的硬前置条件；它不调用模型，不读取隐藏测试或评分，不修改 `.trial` 原件。

## 入口

```
<候选 venv>/bin/python -I scripts/acceptance/prelive_gate.py \
  --settings <最新真实场>/instance/settings.json --work <全新 scratch 目录> --output <verdict.json>
```

- `--launcher-config` 缺省取 `instance` 上级目录的 `launcher.json`。解释器必须是装好候选 wheel 的 venv（`-I` 下可导入 `scidiscovery` 且 CURRENT=16），并且该解释器同时作为 launcher/scid_python 进入 bwrap。
- 输出 verdict 有界（≤64KiB）：`passed`、`models_called=0`、逐项 `checks`、`chain`、`settings_differences`、`usage`、用时；失败只给出 verdict，不重试。
- `--fault a_turn_failed` 是负控（A 原生回合 `turn.failed` 且退出码1），其 `passed` 只表示负控行为符合要求，永远不作为上线资格。
- 回归测试：`tests/research_loop/test_prelive_production_chain.py`（缺 bwrap、缺最新场 settings、缺安装解释器或冻结 task Python 时 skip；可用 `SCID_PRELIVE_SETTINGS` 指定其他 settings）。

## 门禁做什么

1. 只读源场：校验 `settings-identity.json`、源协议等于 CURRENT、对源 `launcher.json` 执行真实 launcher `load()`（公开白名单、manifest、原生二进制 SHA）。任一失败立即判失败，不建场、不启动。源 settings/identity/manifest/公开文件前后 SHA 必须不变。
2. 复制白名单公开文件与 manifest 到 scratch，按原值重建 launcher 配置，只替换 scene/public/runs/submission 路径、原生二进制（假 codex，SHA 重新冻结）和 scid_python。task_python、profile、model、reasoning_effort、receipt channel 保持原值。
3. 以源 settings 原值调用 `controller.prepare`：预算、步数、soft 节点预算、search_policy、correction、portfolio v2、candidate_audit v1、delivery 上限、resume/fragment（new_context）、role_guidance 原文、observer 配置全部照搬。之后逐字段比较新旧 settings：只允许 `goal_id`、`public_root`、`native_launcher_argv`、observer/delivery 适配器代码路径与 SHA、launcher_argv/launcher_files、resume launcher_files 改绑（scratch 路径按前缀映射后必须完全相等，含公开 harness 输入 SHA/大小）。最新场核对结果：差异为空。
4. 一次 `controller.run` 走完整链路，全部经生产路径：真实 `rootless_cov_launcher.py` main → bwrap namespace → 假原生（只替换模型回合）→ `exp` 包装 → 注册的 cov 执行接口 → 真实公开 runner（Ridge 训练、`public_runner_main` 回执通道）→ 封存/谱系/搜索投影 → candidate audit → closeout → `cov_delivery.py --isolate` → bwrap leaf（resolve/audit/promote/confirm）。

链路及逐项检查（全部为真才 `passed`）：

| 步 | 角色 | 内容 | 检查 |
| --- | --- | --- | --- |
| 1 | H | 两个机制 P/Q 的 search_plan，focus screen | 封存，W 任务含 breadth |
| 2 | W screen | P 注册调用；P 第二次被广度准入拒绝（`Other H mechanisms`）；Q 注册调用 | 两条 accepted 调用分别绑定 h001.m1/h001.m2；拒绝被观测 |
| 3 | A | `audit` run-1，两机制 screened | candidate audit 实际 isolated leaf，receipt `audited` |
| 4 | A | 读 audit receipt 后 `continue_w`，next_focus improve h001.m1，含 decision_request | W 任务 focus=improve |
| 5 | W improve | 片段1 `--parent-plan run-1` → `continue`；片段2（新 context-001 home）查询原调用后再调用 → `review` | 两片段、两个 thread、context_mode=new_context |
| 6 | A | `finish` run-4 | 进入 closeout |
| 7 | closeout A | `audit` run-4（真实场 c 的同一路径） | closeout audit receipt `audited`，搜索重放中性 |
| 8 | closeout A | 读 receipt 后 `finish` run-4 | submit(audit+promote)+confirm，`delivery_confirmed` |

另检：`submission/model.pkl` SHA 等于确认 artifact；usage 无 unknown step；`cli.status` 可读；每个 leaf phase 都有 host-only 输出索引；两个 audit receipt 引用其 leaf 输出；leaf 输出字符串不出现在任何 workspace。

## 结果

- 最新真实场 `rootless-task-unit-cov-20261014`（settings SHA `31cfc6a9…b4bf`，协议16）：门禁 PASS，`delivery_confirmed`，settings 差异为空，约 71s，models_called=0；源原件不变。
- 负控 `a_turn_failed`：`native_stopped`，A003 未封存、unknown_steps=[3]、无重放、无交付，约 6s。
- 测试命令和计数见文末。

## 历史故障诊断与回归

| 场 | 现象 | 诊断（只读原件） | 状态 |
| --- | --- | --- | --- |
| U4 首轮 | H→W KeyError 'order' | `lineage.build` 依赖退役标记（见 U4_CURRENT_LINEAGE_FIX） | 已修；门禁以 search_policy 开启从 H 开始覆盖 |
| U4 次轮 | closeout_unresolved / delivery_resolver_unavailable | leaf `_current_guard` 对 Path 求 hash（43f77e3 已修）；当时 leaf stderr 被丢弃，只能推断 | 已修；门禁四 phase 实际 leaf 覆盖；本次补 leaf 输出保留 |
| rootless-receipt-cov-20261014 | prepare `public_directory_whitelist_changed` | 共享公开目录 `harness/__pycache__/runner.cpython-312.pyc` 时间戳 16:50:02，即 cov-receipt-public-smoke-01 运行时；`cov_receipt_smoke.py` 在 host 以 task Python 运行 harness，导入 runner 写入字节码；10 分钟后 prepare 被白名单拒绝 | 修：smoke 设 `PYTHONDONTWRITEBYTECODE=1` 并在结束时断言 harness 目录仍只含白名单文件；门禁源 preflight 回归：污染副本在建场前失败 |
| rootless-receipt-cov-20261014b | node 5 `native_stopped (ValueError)` | node 5 实为 A（不是 W；W004 是最后封存节点）。native.jsonl：`workspace routing discovery failed` 重连5次后 `turn.failed`，退出码1；runner 记 RuntimeError，controller 封存时 `seal_or_repair` 抛 `Terminal scientific output is unverified or changed` | 非框架缺陷：Codex 服务路由失败，控制层正确 fail-closed、不重放。负控回归复现同一 reason。局限：controller reason 只给异常类型名，未带消息（controller.py 由并行任务修改中，未动） |
| rootless-receipt-cov-20261014c | `Scientific intent differs from its sealed interpretation` | A012 为 closeout A，`next_action=audit`；closeout 封存与历史重放解释不一致（`search.apply_source`） | 32e4b08 已修；门禁步7/8 在生产配置下覆盖 closeout audit→重放→finish |

## 本次修复：leaf 输出保留

- `delivery._call` 新增 `evidence` 目录参数：每次隔离调用（resolve/audit/promote/confirm 及 candidate audit）结束后，把 stdout/stderr 各自尾部（≤64KiB）写到 `host-delivery/leaf-output/<operation_id>-<phase>-<n>.{stdout,stderr}`，索引 `<...>.json` 记 returncode、结束方式、总字节、保留字节、截断标志、SHA。audit phase 另外保存 leaf 内 `exp submit` 的 `/scratch/audit.{stdout,stderr}` 尾部（O_NOFOLLOW、只读普通文件）。文件 0400，不覆盖，序号递增。
- 引用：candidate audit `outcome.json` 新增 `leaf_output`（resolve 与 audit 操作的索引路径+SHA）。closeout 交付动作的 ledger 结果字段集合固定（budget.py 不改），以结果中的 `operation_id`+phase 确定性定位。
- 边界：输出只在 host-delivery 下，不进 workspace、history、lineage 或 public receipt，不作为科学证据，不转给模型；写入失败不改变交付结果。原有 256000 字节传输上限与超时行为不变，返回值语义不变。

## 不覆盖

- 真实模型行为与科学质量（假原生按固定脚本产出合法结果）；真实 Codex 服务/网络/认证；隐藏 test 评分、reward；远程 TCAD。
- 门禁只走一条代表路径：portfolio 达阈值复审、correction pause、E 抽取、repair/validate、same_session 续接、output repair、预算耗尽 closeout、交付 unknown 恢复不在本链；这些继续由各自单元/namespace 测试承担。
- 门禁验证的是候选代码在最新冻结配置下的机械接缝，不授予真实场 PASS，也不改变任何已结束真实场的结论。

## 协议

协议16冻结：在取得原生对比结果前不新增协议版本，本次无协议或指引文本改动。

## 测试

测试都在干净树中逐文件运行：干净树由 `git archive HEAD` 加上本任务的文件构成，不含并行任务未提交的 budget/controller/search/contracts/cli 改动。运行环境是同一棵树打出的 fresh wheel 安装进 `--system-site-packages` venv，命令为 `venv/bin/python -m pytest -q tests/research_loop/<file>.py`。未跑全量测试。

| 文件 | 候选 | HEAD 基线 |
| --- | --- | --- |
| test_prelive_production_chain.py（新） | 8 passed（79s） | — |
| test_cov_delivery_isolation.py | 8 passed | — |
| test_delivery.py | 13 passed，2 skipped（原 opt-in 公开 harness 用例） | — |
| test_cov_delivery_lineage.py | 8 passed | — |
| test_closeout_search_replay.py | 10 passed | — |
| test_rootless_fragment_namespace.py | 2 passed | — |
| test_rootless_resume_namespace.py | 5 passed | — |
| test_candidate_audit.py | 3 failed / 10 passed | 同样 3 failed / 10 passed |
| test_closeout.py | 2 failed / 11 passed | 同样 2 failed / 11 passed |
| test_audit_handoff.py | 9 failed | 同样 9 failed |

后三个文件的失败在 HEAD 基线上逐条相同，都是既有的过时 fixture：缺 `decision_request`、W 浅筛缺 findings、node budget identity。这些文件正由另一任务清理，与本次改动无关，本次未修改。
