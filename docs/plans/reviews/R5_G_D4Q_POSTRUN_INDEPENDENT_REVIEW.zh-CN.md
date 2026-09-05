# R5-G D4-Q 后置独立审查

## 一、结论

**结论：通过（只放行 D4-H）。**

真实持久 run `.scidiscovery/r5-e2e-private/replay-live-20260830-03` 的 D4-Q 已按第二轮运行前审查限定的
边界完成。一次性状态代际、两个当前 ABI 8 Agent 任务、split、当前 provider 的新 ApprovalRequest
与本地 UI HumanDecision 均形成精确、不可变且相互闭合的谱系；旧 `state/`、旧科学输出和旧决定
没有被改写或继承。新 audit 独立审查了新 intake 与全部六项来源，密封 handoff verdict 为 `pass`；
有限科学内容复核未发现严重错引、对象身份混淆或不应通过资格门的问题。

本结论只放行下一步 `science.hypothesis.revise.v1` 及其新的独立 critic，即 D4-H。它不放行实验设计、
外部 solver、人工审批代写、最终科学准入或 R5 发布冻结。D4-H 即使得到新 critic `pass`，仍必须保持
`stage_admissible=false`，等待下一轮独立科学复审。

## 二、范围与证据纪律

审查基线是 `baseline/8765-codex` 当前未提交工作树，审查时 `HEAD` 为
`404aeb14c6ebc4b08bac599db91eaee54c103f48`。本报告完整阅读了：

- `R5_G_D4Q_PRERUN_INDEPENDENT_REVIEW.zh-CN.md`；
- `R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md` 的 D4 设计与真实运行记录；
- `scripts/r5_g_migrate_state_to_abi8.py`；
- `scripts/r5_g_requalify_evidence_abi8.py`；
- evidence extract/audit、intake split、evidence qualification 的 OperationSpec、projector 与相关测试。

科学内容只取自 `completed` Task 的 sealed primary Artifact 及其精确冻结来源。没有采信 child chat、
Codex 事件内容、工作区草稿或未封存文件；`agent-run-report.json` 和 daemon runtime summary 只用于
运行身份与终态核验，不用于科学结论。没有启动 Agent、solver、网络访问或新科学任务，没有修改
审批，也没有读取事件内容来补足证据。

## 三、机器核验

### 1. schema 2 迁移与旧状态不变

- 内外迁移报告逐字节相同，SHA-256 均为
  `257a2b9f613e7004786c49d587e7144d2b959ec29d2ff0e54f67abb1f1619939`；报告为
  `schema_version=2`、`status=completed`、`operation_abi_version=8`、12 项映射，唯一转换为
  `remove_null_output_revision_only`。
- 独立调用当前 ABI 8 `validate_state_generation(..., allow_descendants=True)` 通过。校验从 SQLite、
  CAS envelope 和 payload 重新核对每项 old/new task ref、唯一删除字段、new descriptor 的单一
  parent/supersedes、primary/collection output 的旧 task edge、scheduler signal 的旧 task edge，以及
  state/attempt/output/signal control snapshot。
- 额外只读探针对原 `state/` 的 12 行 Task 集逐项验证：`task_ref_json` 仍是报告中的
  `old_task_ref`，状态、attempt、output 和 signal 均与迁移时 snapshot 相同；四个报告冻结的控制库
  SHA-256 仍匹配。
- 原 Artifact registry 的 envelope/link/event/idempotency 行是新状态 registry 的逐行精确子集；原
  `state/` 中除 lock/数据库外的全部文件在新状态中具有同路径、同字节副本。原状态没有 D4-Q 新
  对象。该检查结果为：`old_state_rows_exact=PASS`、`old_artifact_registry_subset_exact=PASS`、
  `old_non_db_bytes_exact=PASS`。

### 2. D4-Q 只新增两个当前 Agent Task

迁移报告冻结 12 项 Task；新状态现有 14 项，差集精确为：

| Task | 状态 | Operation | 当前 operation digest |
| --- | --- | --- | --- |
| `tsk_26f77821354f40bb8c3d3c936b19fb38` | `completed` | `science.evidence.extract.v1` | `7acfc6f793eaf9e383b9bfb5ddb9683b475d28f33612177f16bd25c5b95ca822` |
| `tsk_461bbd815161456fbe7ccff949246718` | `completed` | `science.evidence.audit.intake.v1` | `084de74590d85aa69eb71de17df33390632ac50c4a4520494db20bc4ecb53cf0` |

两个 task descriptor、sealed output envelope 和 `agent-run-report.json` 的 operation id/digest/agent type
一致；output envelope 的 `task_ref` 精确回指各自 descriptor。D4 runtime 独立编译得到 ABI `8`、47
项 Operation，当前 extract/audit/split/qualification digest 与持久对象完全一致。

新任务集合中没有 `science.hypothesis.revise.v1`、新 hypothesis critic、experiment design 或其他
D4-H Task。`executions.sqlite3` 仍只有 2026-08-29 的历史 frozen replay；没有 D4-Q 新执行或 solver。

### 3. 新 intake、六源与独立 audit

新 intake 为 `art_cf01b62681624e4c8c061f1ac21ea278`，新 audit 为
`art_89b11f3c54f346c3b70af007273f3dd6`。extract descriptor 绑定六项 `claim_evidence`；audit descriptor
绑定该精确 intake 与相同六项 `evidence_inventory`。audit sealed envelope 的直接 parent 精确包含
任务指令、新 intake 和六源；没有替换或遗漏来源。

audit payload 只声明一次 `source_material_001`—`source_material_006`，七项 material check 均为
`pass`，每项决定性检查都有精确 evidence key；scheduler signal handoff verdict 为 `pass`，同时继续
披露三项 provenance 缺口。全部六个 source key 都被 audit evidence 声明覆盖，且来源 locator 与
实际对象类型一致。

有限科学内容复核结果：

- evaluation contract 明确把冻结 target 限定为用户定义比较目标，并禁止把它当独立合格论文证据；
  intake/audit 没有越过该边界；
- metric source 的 `baseline_recovery.pass=false`，front RMS 单项通过而 crossings、lower width、
  max-absolute-residual 和 full-RMS 相关门失败；intake/audit 表述一致；
- source report 给出的残差区间 `0.366337–0.386139 um`、峰值位置 `0.380198 um`、峰值有符号残差
  `-1.0786323340881445 decade` 和 21 点均被准确引用；
- CSV 独立计数为 1504 个数据行，其中 InGaAs 803 行，深度范围 `0.00297–0.79703 um`，SHA-256 为
  `0c66052fb28b69f720877d48dee334db5618aa158de652d2c29188befe952e1c`；与 manifest、intake 和 audit
  一致；
- deck diff 实际为 86 行，包含网格、参数化/分支、区域名与输出路径差异；intake 只把它列为待检验
  prior signal，没有宣称因果；
- 原历史 audit 的旧输入缺口没有被继承为当前事实：当前 CSV 已供给，而原始历史 PLX/执行绑定、
  target_metrics 原始字节和完整 scorer 执行绑定仍被诚实列为缺口。它们是后续独立闭合要求，不是
  当前有界 intake 源支持检查的失败。

因此，新 audit 的 `pass` 只支持当前 intake 的有界陈述、限制和下一测试定位；它没有把缺失绑定、
因果机制、物理模型或未来 replay/A-B 观察伪装成当前事实。该 verdict 足以通过当前 qualification
projector 的准入门。

### 4. split 父链与内容投影

problem frame `art_7385b24492a3439a8c6c13ce44aff8ae` 和 foundation
`art_e83715c2fb404cac8ccf33317ec181d1` 均由当前
`science.intake.split.v1` digest
`c4f7695f829e0ea00f34fac7f0664ad99922dda0856fd9185e19f0307ac6cfb9` 生成。两者 parent refs 均按
顺序精确为新 intake、新 audit；problem frame 字节等于 intake 中的 `problem_frame` 投影，foundation
字节等于 intake 中的 `scientific_foundation` 投影。没有旧 intake、旧 audit 或其他对象混入父链。

### 5. 当前九对象 Approval 与决定

ApprovalRequest `apr_170810300c844aa1bd8222180617bc35` 的 subject refs 按端口顺序精确为：

1. 新 foundation `4f134362…1939b`；
2. 新 intake `75fdc52e…4595d`；
3. evaluation contract `8c45f32f…ad8a8`；
4. ABI 8 metric source `7f3a5fe6…b53aa`；
5. active bundle manifest `684d106d…18e3`；
6. historical independent audit `72a70ea4…0a325`；
7. historical deck diff `452135f0…10ee2`；
8. ABI 8 curve source `0c66052f…e1c`；
9. 新 audit `b656ffea…a67f7`。

Request 的 `subject_set_sha256` 为
`6375f4a34c7ae0c63954aa0233cf7e6a359ff3e6ce14d006efe1f1d4f7fb8398`。HumanDecision 精确引用同一
Request、同一有序九对象与同一 subject-set digest，`selected_option=approve`、
`previous_decision_ref=null`，决定者认证方式为 `local_ui_session`；不存在聊天文字转决定。

Request、阶段报告和当前安装目录三者的 provider identity 完全一致：

- operation id：`science.evidence.qualify.v1`；
- operation digest：`5d639ffaf9fd61f53ba1c9fb58bb59213a62dddc4a33166b75b3d41bb789ca16`；
- approval contract digest：`e77be3ab60b964ec16ecde3da6be0d4aa614913f7a91a52a113091697d628a0c`。

阶段报告 SHA-256 为
`85a2e257233843192ddc472fc435b66786043ea6c20811460969ad4f39cebccc`，并明确记录
`old_decision_inherited=false`。这是一个新的 revision 1 决定，不是 ABI 6 决定换 digest 或继承 verdict。

### 6. 四个确定性重绑定

逐项从 scheduler binding、envelope 和 CAS 重算 schema、media type、size、SHA-256 与 payload bytes：

| 旧对象 → ABI 8 新对象 | payload SHA-256 | 结果 |
| --- | --- | --- |
| `qualified_replay_profile` → `r5g_d4_replay_profile_abi8` | `62dbca930c64d14868617e8982d0fe4a6e2b6f5b7a04f11dcdbe4c5356be06d7` | 逐字节相同 |
| `computed_baseline_recovery_metric` → `r5g_d4_metric_abi8` | `7f3a5fe6f1c7614e5ce82d9fd429947b68bfc4132148737dc4bb189c1e4b53aa` | 逐字节相同 |
| `r5g_science_source_views` → `r5g_d4_science_source_views_abi8` | `7f3a5fe6f1c7614e5ce82d9fd429947b68bfc4132148737dc4bb189c1e4b53aa` | 逐字节相同 |
| 旧 curve source → ABI 8 curve source | `0c66052fb28b69f720877d48dee334db5618aa158de652d2c29188befe952e1c` | 逐字节相同 |

它们只重建当前 deterministic producer identity；没有冒充新 Agent 判断，也没有改变科学字节。

### 7. 7 GiB 与越权检查

`_run_agent` 在任何 invoke 前读取 `RLIMIT_AS`，无限制或高于 `7 * 1024^3` 会直接停止。两个
`agent-run-report.json` 均记录从 `created` 到 `completed`、Codex return code 0，并与当前 task/digest
一致，说明两次 Agent 调用均通过这一运行前硬门；报告本身不重复记录数值 limit，因此不能用于
事后恢复更细的峰值内存曲线，但这不影响“未通过 7 GiB 门就不能创建这两次运行”的控制事实。

两个 task authority 均为 `network_mode=none`、`max_network_requests=0`、无 allowed domain；其
`task_web_evidence`、PDF excerpt 和 collection output 数量均为 0。control/worker runtime summary
对两个任务均给出相同 catalog digest
`21fc1b1cfb6ccca54f6de9a0dd5c0e55302aa7e380139d75a108256dc6596e4c`，daemon log 为空，任务只产生
声明的单一 sealed primary。持久 execution 表没有 D4-Q 新执行。未发现网络、solver、跨 Operation
输出或其他越权迹象。

## 四、审批 UI 可用性仍未通过

用户再次反馈审批页排版太差。现场记录也显示页面把九个完整对象平铺展示，缺少关键科学结论、
限制、来源身份的优先摘要与清楚的信息层级。结论保持：

- 审批 UI 信息架构、可理解性和操作效率：**未通过**；
- 精确对象绑定、local-loopback UI 写入和单一决定权威：本次运行有效；
- 本次 `approve`：不因产品可用性缺陷而被反向改写或判为无效；
- 后续 UI 改进仍需单独的真实用户可用性验收，不能把本次成功写决定宣称为 UI 质量通过。

这是一项应修复的产品风险，但不是篡改本次已封存决定或阻止 D4-H 的理由。

## 五、独立测试

所有命令严格串行，并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
```

执行最小相关集合：

```text
python -m pytest -q \
  tests/operations/test_r5_g_hypothesis_revision_stage_runner.py \
  tests/operations/test_general_science_plugin.py::test_general_science_agent_operation_uses_exact_files_and_parent_chain \
  tests/operations/test_r4_approval_operation.py::test_provider_identity_is_frozen_into_consumer_contract_and_digest \
  tests/operations/test_r4_approval_operation.py::test_changed_approval_subject_creates_pending_revision_without_old_decision \
  tests/operations/test_r4_approval_operation.py::test_provider_qualification_requires_the_exact_compiled_identity
```

结果：`14 passed in 3.36s`。

另执行了不落盘的当前安装目录编译、schema 2 全量迁移验证、旧/新 SQLite/CAS 子集核验、九对象
Approval/Decision 比较、四项 byte comparison，以及 CSV 行数/范围复算，全部通过。

未运行全仓测试、浏览器自动化、真实 Agent、网络、solver 或 D4-H。全仓与浏览器矩阵不是本次
“真实 D4-Q 后置谱系与有限科学内容审查”的最小必要替代证据；审批 UI 可用性已按现场反馈明确保留
为未通过。

## 六、放行边界

D4-H 必须只使用本报告核验的新 foundation、旧精确 portfolio 和旧精确 blocked critic，真实运行
完整 hypothesis revision 与新的独立 critic。不得继承旧 critic verdict，不得用 Task completed 代替
科学 `pass`，不得提前调度 experiment designer 或 solver。若 D4-H 的新 critic 不是 `pass`，立即
停止；若为 `pass`，仍由下一名独立科学审查者核验新 portfolio、critic、父链和修改是否真正解决
两个可识别性问题后，才可考虑后续阶段。
