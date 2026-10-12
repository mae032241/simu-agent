# T5 cov 真实场终态独立审查（2026-10-12）

结论：**真实 T5 验收未通过；终态分类与失败事实核查通过**。只有 H001 已接受执行，因冻结节点时长上限停止，没有封存科学结论、正式实验候选或可评分提交。本人只读核查，没有运行/恢复/测试/模型、改原件或预算；本报告不授续跑或扩额。

## 终态与身份

- 候选 `f8427dfe69319e2cac0ecf6b7033da409172159f`，wheel `224c76eef9cd84615c16473d23bf3db65edc181b0970ee26a1c00387dd65fc29`；冻结6,000,000 observed tokens/3600 active秒/24步，H节点500,000 observed tokens/420秒。
- 亲阅原 job001/native-intent：task SHA完全一致；intent冻结 H role、boot和原额度。outcome returncode=-15、stop_reason=node_slice_time_limit、cleanup=observed_group_cleaned，budget_slice.advance_seconds=420.4141269929969、dispatches=1。controller native_stopped/exit2/completed_steps0，与driver wall422.191s一致。
- 此为已知节点时间硬停，不能当native成功或科学完成；其usage未知是另一维度。未触发全局时间上限；最终token总量未知，不能由partial回执推算精确剩余token或确认全局token余额。
- clock ledger原同boot advance→paused间隔420.465931744s；计费依据BOOTTIME，不以UTC展示间隔推翻此量。没有人为退款/额外预算或重发事实。
- session `01a12ee1-c2ec-7741-8725-7a7a787ad99d` 与 native.jsonl thread.started、outcome.thread_id、session_meta.id/cwd全部精确匹配；native0.162.1，精确H001工作目录。这里只采用有来源的终态记录；不以未经namespace转换的数字PID缺席单独证明无进程。

## 用量可信范围

- native.jsonl没有turn.completed。原控制usage observed_tokens=0、unknown_steps=[1]表示缺终态用量回执，绝非零消费。
- sessionSHA `23090c05af08e0bf125406ffce187022ae39eadd127cc3e3f9d07a8e3aa8e266` 与postmortem记录一致。11个token_count事件，其中10个含info；可读累计total非递减。最后含info事件2026-10-12T06:57:49.918Z与postmortem.latest逐字段一致。
- 最后累计观测 **217,492 total =209,783 input+7,709 output**。173,440 cached是input子集，不再加一次；reasoning_output2585已属于output，不重复加。未缓存输入36,343、未缓存输入+输出44,052，可作为这份partial观察的派生量。
- 最后token_count早于强制中断；末尾在途调用和最终整回合用量未知。这是精确session的事后诊断，不能作为完整账单、直接写回control预算或论证薄链效率。

## 封存、实验与提交

本人遍历真实instance：

- jobs仅001，未见任何result-identity.json或science-output.json，无conclusions；W/A/E未派发。
- runs、submission目录均空；没有managed accepted.json、rootless-delivery-operation.json或正式submitted/model原件。因此 **0正式exp run、0提交、reward=N/A不可评分**。不能制造0分、伪leakage=false或另造H诊断模型作为候选。
- H部分artifact scientific_direction.md 7662B/SHA `32c8a32a364d52a2fe9b0b2c3d0741e1f52737972632dafa159a8678df4cb3c4`与terminal-evidence一致；属于保留的未封存工作，不当结论或继承材料。
- terminal-evidence列出的五项原件SHA全部相符；frozen-manifest的80项文件现读全部SHA未变，原预检/条件未改。没有重试、amend、ack或未资格nativecontinuation。

## 验收判定与限制

H→W→A真实链、跨节点承接、自适应选择、预算closeout/实际交付均未在本场观测，工程与科学真实验收不通过。已有T1–T4源码/installed/零模型公开harness门禁仍保留其原范围，不替代本场真实通过。

本场支持“H420s时长未容纳实际H行为”的判断；职责、工具调用耗时或主要原因由独立轨迹分析负责，不根据未封存文字替H作科学结论。单个失败场不能推出整体token效率、科学得分、native比较或跨场稳定性。

## 精确证据 SHA256

证据根：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/.trial/rootless-t5-cov-20261012`。

- `terminal-evidence.json`: `2124787582e122c2550d53255089d1cce174dc3ed6f883f89188d958892224cb`
- `postmortem-native-usage.json`: `0feeb7fb5d8ad6f29b5e7986f9b6e294e273c5308a4dcf77a4feaaff8eac253c`
- `final-result.json`: `52618ff3cf3fc82be3127706d7f891cc8079ec916822c87698aac4a3460c85e6`
- `frozen-manifest.json`: `e39db2d64ab0be344ed0b943d534690118bfe6fae8b2f421cb164a69a5cc76ec`
- `instance/native-evidence/001/native-intent.json`: `9eb8758387b8b81449e32ed309517649e01a3ce64e123c873f91913e7ab90145`
- `instance/native-evidence/001/native-outcome.json`: `da4ad3f177dd6fb7b7be7f95155a227a7620f20362a0397a37d421dc8e65d2d1`
- `instance/native-evidence/001/native.jsonl`: `cbbe49e63a80c9f3250694b3decd4f876bacb7fe3f101a802fe82c3fee6d5b00`
