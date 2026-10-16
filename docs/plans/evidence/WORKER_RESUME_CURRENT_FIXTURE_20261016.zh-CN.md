# Worker resume 当前合同夹具修订

本执行者范围：仅 `tests/research_loop/test_worker_resume.py`；未编辑生产、旧实例或已有断言。root 独立修正 native.py 的完整 session header 重读，以及 continuation.validate_task 的精确旧 schema 兼容。

## 六项旧失败的原因

`/tmp/scid-full-record-root-r2-20261016/batch-001/pytest.log` 的六项 resume 失败均源于 fake payload 缺字段：W 缺 `mechanism_findings`、`stage_intent`；A 缺 `decision_request`、`portfolio_review`。`git show 4c074ad:src/scidiscovery/research_loop/contracts.py` 可见这些字段当时已经 required；本轮容量修复未新增它们。因此只在 FAKE/REPAIR_FAKE 补当前合同字段，不放松 schema、预算或原测试断言。

首轮补齐 null 字段后，一个具有真实 screen 任务的 fixture 仍多出一次合法 WorkRepair：null 不满足该任务自身的 finding 义务，使用量为 14+22+22=58，而原断言要求 36。该 fake 现在读取公开 science-task 的 assigned mechanisms，对它未执行的科学测量明确写 blocked finding，不伪称 observed。保留原 36 token、2 dispatch、全场 68 token 等全部断言。

## 新容量正反控

新增三个无模型检查，每场含 258 个 session 原件、原 session header 超过 65,536 字节：

- 实际同 session 续接，header 全文 SHA 匹配，恰好一次 exec 和一次 resume；累计 36 token。
- cwd 不匹配在接受前拒绝，没有 continuation intent 或第二次 launch。
- 接受后只改 header 附加 metadata，保留 id/cwd；native reader 仍按原 SHA 拒绝，不启动新进程或接受下一次 attempt。

范围限定：这些检查验证 `continuation.session` 和 `native.run_native` 的恢复原件读取。fake 文件名为 rollout.jsonl，计量使用独立 turn.completed fallback；不证明 `native_usage.SessionUsage` 对大 header 或大量目录项的活体扫描能力。root 明确将该活体采样与完整历史存储区分，本轮未扩大计量引擎。

## 原始验证

- `/tmp/scid-worker-resume-fixture-current-20261016/source-r1/batch-001/`：只选六项原失败及三项新检查；8 passed、1 failed，pytest 9.57 秒，监督 9.846 秒，cleanup_complete=true。唯一失败为上述 screen finding 夹具遗漏引起的 58/36 差异。
- `/tmp/scid-worker-resume-fixture-current-20261016/source-r2/batch-001/`：仅复测该失败项；1 passed，pytest 1.58 秒，监督 1.828 秒，cleanup_complete=true。
- `/tmp/scid-worker-resume-fixture-current-20261016/schema-r1/batch-001/`：只运行新增 schema 参数测试，5 passed，pytest 0.32 秒，监督 0.566 秒，cleanup_complete=true。
- 三批均经 scripts/run_tests.py serial_lock/run_one，未跑全文件、模型或 solver。保留首轮失败日志。
- `git diff --check` 通过。

最终测试文件 SHA256：`8cf45e140844cc91fcebaa5730ce2d76eac5bdcc254245bfa2550e7654a17e92`。

## 精确旧 schema 兼容

root 的 `continuation.validate_task` 仅接受当前 schema 或与当前 schema 完全相同、唯独 `implementation_selection.maxItems=16` 的旧形状，不重写原件。生产文件 SHA256：`471f0ad8a90397781a66963e5bd73f404c67dbcbc373af82a8e0e497115a4162`。

新增 `test_resume_accepts_only_exact_published_original_schema_shapes` 的五个参数：current、legacy16 均通过；legacy15、required_drift、other_field 均按原 schema 改变诊断拒绝。每项同时断言原 schema、job、science-task 字节不变，未产生 native-intent；未运行额外模型或改写旧 seal。
