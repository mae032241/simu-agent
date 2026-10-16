# 完整历史记录与紧凑视图容量分离

基线：4c074ad。状态：本组实现/测试冻结，等待最终独立审查；未提交，不修改旧真实场，不调用模型/solver。

## 根因与修复

真实 cov rerun 的 W 有 25 个 call；完整 snapshot 297,940 字节超过旧 256,000 字节限制，observer 捕获降级为 contexts=[]，随后 A 的 observer 按原 scope 过滤旧 call，因而无法补回候选与执行关系。不是原 call 缺失。

本组区分两种载体：

- 完整原件、observer 输入输出、封存 snapshot、checkpoint、历史重读和候选/context 累计列表不使用模型视图的固定字节或累计数量上限。
- 模型导航仍按每页 64,000 字节、brief 4,096 字节处理。过大的导航行明确标记省略；可重建 overview 或 brief 元数据过大时返回有界省略视图，不让它反向拒绝科学封存。分页总量不再作为原件存储上限。

`history._proof` 使用已有流式 digest 和文件复制归档，不把完整 blob 读入内存；继续核验精确实例路径、普通文件、禁止符号链接、源/副本摘要和原件绑定。observer 以临时文件传递完整 JSON 输入输出，保留运行超时、格式和真实性诊断。重启的 `_source`、`validate_observation`、checkpoint.validate 和 managed proof 验证均使用相同完整记录语义；共同 terminal 的验证读取直接传原件 Path。

新实例 `max_output_item_bytes` / `max_output_total_bytes` 默认 None，表示无存储大小配额；明确传正整数才冻结并执行对应配额。旧实例的已冻结整数保持原校验，不修改历史授权。新增 CLI 两个可选参数公开这项显式存储配置。`contracts.output_quota_exceeded(policy,sizes)` 被材料、绑定、恢复和工程修复输入复用；取消固定 16 项完整实施选择限制，仍逐一校验科学对象身份、来源与摘要。模型概览保留分页。

`unresolved_links` 是非权威紧凑诊断，仍保留 16 条和明确 omitted；完整科学 raw 保存全部文本。这项视图额度不参与候选/context 权威图，不用于拒绝封存，未引入旧 seal 迁移。

## 精确测试与失败记录

所有检查通过 scripts/run_tests.py 的 serial_lock/run_one 监督；没有直接裸跑 pytest。

1. `/tmp/scid-full-history-records-20261016/source-r1/batch-001/`：9 passed、5 failed，pytest 6.33 秒，监督 6.605 秒、cleanup_complete=true。保留全部失败日志。
   - 新大记录和两个既有 lineage 用例共同暴露：同伴流式 helper 新增相对 import，独立 `python -I cov_lineage.py` observer 的 package 为空而失败；capture 正确保留 failure 诊断，但 contexts 因 adapter 故障为空。已由执行侧改绝对 import。
   - 新 4100 候选夹具漏 role 字段，补齐元数据。
   - 既有 combined quota 测试只使用已退休引用标记，未产生真实选择；改一行明确 `selection=['W002-I001']`，保留其原有配额负控。
   - 9 项已过包含 >64KB 科学原件/checkpoint、140 个完整材料、34MiB 流式归档、完整大 observer transport、超大导航行省略、默认/显式配额与既有 checkpoint 篡改/幂等/链接负控。
2. `/tmp/scid-full-record-execution-20261016-r2/batch-001/`：其中本组 `test_twenty_five_real_calls_keep_large_snapshot_contexts_and_restart_bindings` 和既有三 context lineage 正控均 PASS。该批整体为 4 passed / 1 failed，失败是执行侧新增 audit restart 夹具 route，不将该批说成全通过；同伴负责窄复核。
   - 25 次真实注册 cov fixture 执行的 snapshot 断言 >256,000 字节；contexts、managed_calls、candidates 各 25，A 获得全部 candidate/call 关联；删除 disposable cache 后重读仍完整，旧 seal/observation 字节不变；归档 accepted 原件篡改仍拒绝。
3. `/tmp/scid-full-history-records-20261016/source-r2/batch-001/`：5 passed，pytest 1.25 秒，监督 1.512 秒、cleanup_complete=true。
   - 4100 候选完整累计，recent 仍只显示 16 并给 omitted；17 项完整科学对象选择/后继读取；160KB coverage 完整封存而 overview 有界省略；context scope/资产篡改硬拒绝；明确整数总配额在后继绑定仍拒绝。

以上共覆盖 16 个本组不同定向 nodeID；不是声称最终单批 16 passed。未重复无关已通过测试。git diff --check 通过。

## 文件与冻结

- history.py：完整 observer/归档/读取、流式原件及有界导航降级。
- lineage.py：完整 context/candidate 累计、有界 brief、恢复材料配额复用。
- contracts.py：完整科学记录读取、完整实施选择、显式配额 helper/消费者。
- checkpoint.py：完整原生原件/材料/checkpoint、有界 resume brief。
- controller.py：本组仅 prepare 默认 None 和参数校验；同文件 audit 路由段由执行侧拥有。
- cli.py：显式可选存储配额参数。
- engineering.py：本组仅 bind_inputs 配额消费者。
- tests/research_loop/test_full_history_records.py；test_history_handoff.py 仅修一行现代选择夹具。

SHA256 清单：`/tmp/scid-full-history-records-20261016/frozen-sha256.json`。共享 controller.py 的最终哈希含同伴已冻结 audit 改动，不能把它全归本组。

## 限制

本报告证明无模型 registered fixture 的封存/关联/重读/负控；不宣称重新运行真实模型或旧 cov 场。完整结构化 JSON 解析需要相应内存；流式承诺针对原件 blob 哈希/复制及不额外串接内部 transport bytes。操作的有限时间、显式用户存储配额、既有 token/秒/次数授权、路径与完整性校验继续有效。最终框架外侧 schema/service/安装包验证由根整合报告说明。
