# Root 上下文边界修复 R2 实现独立 Sol 复审

日期：2026-09-21  
结论：**需修复（1 个 P1；无 P0）**

## 1. 复审对象与边界

本复审只检查候选相对实施前实际 dirty working tree 的 29 文件增量，不把 `HEAD` 总 diff 当作候选范围，也未操作科研实例、审批、Fig4、模型、solver、部署或提交。

- 已通过的 R2 计划：`docs/plans/ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_20260921.zh-CN.md`，SHA-256 `8f727cb470fd3df4631a39d2e85674015a02721c197276cc8a02a6ba0f786851`。
- 实施记录：`IMPLEMENTATION_R2_SOL_20260921.zh-CN.md`，SHA-256 `d20b3c14021a64bb41abdb5a4e73fe07e20fe1f2c6cdf19cf294aa1620a31885`。
- 候选补丁：`implementation-relative-to-actual-baseline.patch`，SHA-256 `ac414e5d45a498508bb3ec90600b8f194a25b7a972ab28736d47f32122550fc3`。
- 候选 manifest：`implementation-candidate-manifest.json`，SHA-256 `f4942c1d2c9f1d48b2982c9141b7d4624f3155587f120b62482592a8b931a39f`。

独立静态复核确认：29 个当前文件均匹配 manifest 的 after hash/字节数；27 个 before 文件匹配 `candidate-before-bytes.tar`，另 2 个 late-before 文件匹配各自冻结副本；`implementation-evidence-freeze.json` 引用的 86 个文件 hash 全部匹配。提取脚本从原 trace 重新生成的受限 fixture hash、窗口 hash、行数、31 项元数据和 usage summary 均与冻结 manifest 一致，文件模式为 `0600`，复核临时文件随后已删除。因此 fixture 销毁记录与可复现性本身没有发现问题。

## 2. 阻断发现

### P1：P1 replay 没有经过新的 compact route，且裁剪了旧响应，因而不能成立 matched 字符收益

`replay_context_projections.py:81-96` 将旧 `run_status` 响应直接传给 `run_profile_projection`。它只会从输入中选取已有字段，不能生成新生产路由在 `mcp_root_run_routes.py:238-250` 机械加入的字段。

冻结 manifest 显示 16/16 个 P1 旧响应都缺少以下五项：

- `operation_version`
- `operation_digest`
- `operation_contract_status`
- `created_at`
- `started_at`

新 `_compact_run_status` 对每个 compact 响应都会组装这五项，随后 `run_profile_projection` 又保留它们。当前 replay 的 `new_response_sha256` 与 `new_visible_characters` 因而只是“对旧响应做纯选字段”的结果，不是新 Root façade/route 的响应。它的语义检查也只校验 state，以及 completed decision 的 selected output/signal；没有校验上述身份和时间字段。

旧侧也不是完整的 model-visible 响应。`extract_replay_fixtures.py::minimal_response` 在计数前删掉了 `output_artifact_name`、`agent_type`、`native_execution`、`execution_profile`、`evidence_output_count` 和 `draft_from` 等原响应字段。独立按相同窗口流式复算、只输出非敏感计数，得到 navigation 原响应为 `18,583` 字符而非 `15,753`，decision 原响应为 `29,511` 字符而非 `28,418`。因此表中 old 与 new 两侧均不是相同生产边界。

这不是可忽略的计数误差。即便把 version、时间取为空字符串，并只按 64 字符 digest 与最短的 `current` 合同状态计，五个 JSON 成员仍至少增加 **179 字符/响应**。因此以候选当前 projector 数字为起点，9 次 decision 的新 route 响应下界为：

`26,986 + 9 × 179 = 28,597`

它已经大于候选所用、经过裁剪的旧基线 `28,418`；7 次 navigation 的同一下界为 `10,867`。但完整旧响应分别是 `29,511` 与 `18,583`，而实际新 route 的完整值尚未重放，所以这只能证明实施记录的两组精确数字不可比较，**不能据此断言实际 decision 的升降方向**。这里仍只是 canonical visible JSON 字符，不是模型 token、峰值上下文或净增长结论。

影响是：候选目前不能用该 replay 证明 P1 的 matched 字符收益，也不能据此评估长链中 decision 读取是否减少 Root 上下文。生产实现的身份、诊断、恢复字段不能为追求数字而静默删除；需要修复的是 replay/验收证据，随后依据真实结果决定是否还需最小产品调整。

最小补足要求：

1. 旧侧在 `minimal_response` 裁剪前计数，并把完整值只保留在 `0600` 临时 fixture；新侧用冻结的非科研 Run/control fixture 让同一组请求经过实际 `RootMCPRouter -> RootRunRoutes._compact_run_status -> root_response`，或用来源 Run 记录机械补齐 route 必有字段后再重放。不能再把裁剪后的旧展示响应直接当成新 route 输入。
2. 每行同时校验 operation id/version/digest/contract status、状态、所请求科学值和 signal 身份；失败样本另校验 compact recovery gate 与精确诊断。原窗口没有失败/poll 样本时，继续明确由 golden 覆盖，不能伪装成 trace matched 收益。
3. 重新生成 P1 totals、联合 replay、实施记录和 evidence freeze/hash。若无法取得同输入 control fixture，应撤回 navigation/decision 的 matched 新字符数并标为未验证；仅保留结构/golden 结论。
4. 根据修正后的 decision 数字判断是否保留现状或做另一个有界调整。不得删除合同身份、精确失败诊断、恢复 gate、来源或审批边界来制造下降，也不需要为此运行模型 A/B。

## 3. 其余定向结论

在本轮限定范围内，没有发现第二个阻断：

- `poll/navigation/decision` 的组合校验由接口与 route 共用；非完成状态不暴露科学 payload/signal。失败 compact 响应复用现有 recovery gate，只公开 allowlist `reason_code`，未知值映射为 `other`；`diagnostic_after` 缺省与 `0` 的行为有 golden 覆盖。
- producer 投影使用 Run 冻结输入，保留端口和 item index；current、历史合同不可用、同 id 异 digest、transform 歧义、跨实例、imported 和只读边界均有显式结果。原 trace 的 6 个 parents 请求缺 control fixture，候选只报告旧 `12,463` 字符且没有伪造收益，这一处理正确。
- `view="invoke"` 先读取同一完整 compiled catalog item，再投影 digest、完整端口/准入、review/approval、revision、attempt/runtime applicability 和 consequence；通用调用字段仍由 `operation_invoke` interface 提供。默认 `full`/`compat` 保留，guide、scheduler prompt、installed gateway 与 install runner 的只读 probe 指向新路径。实际常驻 runner 部署和真实采用率仍明确未验证，没有被安装测试冒充。
- P4 的两个启用条件没有被证据证明，未增加 `decision_paths`、状态机或机械科学 checklist 是合理的。上面的 P1 计数错误不产生“多个 Operation 因未知结构重复 index”的新证据，因此不要求借机实施 P4。
- 实施证据记录的最终 123 个定向测试批次均为通过，最高记录 `147,212 KiB`，低于 `768 MiB`；早期失败和对应修正被保留，没有被写成最终通过。由于本次阻断来自 replay 输入边界，重复运行同一批产品测试不会验证该缺口，本复审未额外跑完整测试。

## 4. 最终判定

**需修复。** 候选的控制边界、生产投影和兼容路径暂未发现 P0/P1 语义缺陷；唯一 P1 是收益 replay 两侧没有使用同一生产边界，报告的 navigation/decision 精确字符数及 matched 收益均未得到证明。完成上述有界证据修订后，只需针对 P1 replay、更新后的收益结论及其直接产品影响复审，不应重开已经通过的 producer、invoke、P4 或安装边界。
