# F1 非本地终态修复独立复审（2026-10-16）

结论：**PASS，限定为已注册执行器的共同终结事实、科学封存/成果交接及本轮测试覆盖的消费者。** 未发现当前精确差异中需要阻断提交的剩余缺陷。没有把合成 remote adapter 解释为真实远端服务、模型科学判断或 solver 资格。

## 精确范围与证据身份

实施起点为 `727f5372549148fa2c0f40c51c5bd74692478954`；F2 已独立提交，最终 wheel 验证基线为 `da7d891848bcc0d4a0617095600c36380bebfa8a` 加冻结 F1 差异。F1 包含 6 个生产文件：`operations/execution.py` 和 `research_loop/{contracts,experiments,history,local_experiments,worker_delivery}.py`；2 个测试文件：`execution_fixtures.py` 与新增 `test_nonlocal_execution_observation.py`。不把已提交 F2 或其他未跟踪历史材料计入本范围。

独立复审者未编写这些实现，按 `scid-cross-boundary-review`、`scid-change-scope-checks` 只读审代码及原始证据。最终独立提取 [机器记录](NONLOCAL_EXECUTION_TERMINAL_F1_20261016.json) 的 8 个 SHA256，与当前文件逐项比较，全部一致；安装测试文件与 fixture plugin 中的执行文件也与工作树逐字节一致。记录的 scope SHA256 为 `c1a089707bac17306b415646d3b5fda986fd0335733e478b876d99a719e3386d`。

没有修改生产代码、未重复启动未冻结检查、未调用模型或 solver、未提交。原始 F1 反例没有被重写；本次通过证据与旧审计证据分别保留。

## 修复的权威边界

### 共同终结事实不冒认本地语义

执行协议在同步终结的 run 或显式 collect 时生成一次 `execution-observation.json`，绑定 accepted、host-frozen interface、scope、call、mechanism、external ID、completed 及原 backend proof/collect descriptor。生成前由冻结 adapter 的 status_details/result 验证终结事实，两者必须一致；原件不一致不能生成 known 观察。

消费时依据 accepted 的精确 native attempt，读取并匹配主机保存的 interface，不能只相信 receipt 自报的类型。本地和 cov 声明 local_process，仍须 cleanup_confirmed、transport_complete、整数 returncode 和 completed 状态一致；remote 使用其原生证明，不伪造 POSIX process/terminal。测试保留 remote 没有 process.json、terminal.json 的断言，并拒绝把 local 观察改写为 adapter_result 来绕过本地条件。

缺共同原件的新接口保持 unknown；query 不重建丢失的观察，也不重新 collect。已有观察只读校验。旧 local/cov 回执按原严格本地终态规则兼容读取，没有自动迁移或重写旧 seal。执行状态、科学证据可用性和科学判断资格没有合并成一个 verdict。

### 精确保留原件与 A 挂载

backend proofs 与 collect 文件在共同投影时复制到控制保留区。保留 proof 的原 descriptor 清单逐项等于 completed.proofs；collect 副本同时保留完整 descriptor 身份并核对内容摘要。原 backend 路径可以在 instance 外，或在投影后被后端清理；科学消费者只验证保留副本。

复审中发现的两个同根路径假设均已修正：新观察不再重读 completed.proofs 的外部原路径；remote 即使携带 result/outputs 字段，也按冻结接口选择 retained collect，而非借字段存在性退回本地文件布局。实例外原证明删除后的 W seal 与 A 读回有明确正控；篡改控制保留副本仍拒绝。

contracts.collect_materials 从已经验证的 managed observation 取得 W 工作树中的控制保留文件，沿现有 checkpoint/正式父节点成果路径挂载给 A。它不在封存过程中加载 adapter 或查询 backend。collect 名称另做 canonical 相对路径和重名检查，拒绝 Identifier 所允许但不适合作挂载路径的 `..`/别名。后续 native attempt 首次配置执行器，以及再下一 attempt 不产生新执行时，仍按各 accepted attempt 的精确主机配置读取既有成果。

### 消费者检查范围

已追查 run/collect/query/lookup → history capture/validate 的三个 observer 分支 → Worker delivery capture/validate → contracts.collect_materials/checkpoint → lineage 实验索引 → search/breadth → generic_results/delivery。通用消费者复用共同观察。剩余直接读取本地 terminal.json 的位置属于 local/cov 实现及旧严格本地兼容，没有继续把 POSIX 布局施加到 remote 科学封存。

W 的机械 complete 只表示结构证据完整；scientific screened 仍由 A 的密封 disposition 产生。unknown 执行不允许自动再提交；测试没有以额外重试或虚构终态消除不确定性。

## 直接核查的测试证据

所有检查由执行者使用 serial_lock/run_one 资源监督；复审者只读最终日志、driver、安装身份和结果，未重复执行。

| 检查 | 原始结果 |
| --- | --- |
| source r3：nonlocal、registered、breadth、Worker delivery、generic inverse、local managed | 95 passed、1 skipped，92.63s；监督 92.954s、exit 0 |
| 最终移除 latest-config guard 的精确 attempt 回归 | 1 passed，0.47s；监督 1.008s、exit 0 |
| 最终 fresh core wheel + fixture plugin wheel，隔离 venv | 21 passed、1 skipped，10.06s；监督 10.728s、exit 0 |

source 主批在最后一处 guard 删除前运行；该删除仅取消“最新 attempt 必须存在 config”这一先决条件，随后针对同一 attempt 回归补测，并由最终安装文件完整覆盖新 nonlocal 测试文件。没有把前一批源码检查伪称为最后字节的重复全批运行。

source skip 是 registered cov 参数化中的 local payload 专属检查；安装 skip 是旧 cov source harness 兼容用例，已在 source lane 执行。安装树没有复制该 source-only cov harness，因此没有伪称安装版 cov 原始任务运行通过。

安装 driver 清除 PYTHONPATH，以独立 venv 的 `python -I -m pytest`、空 pytest.ini、空 source pythonpath 运行；只复制测试 helper，不复制 src 或项目 conftest。真实 remote execution entry point 来自已安装的 `scid-nonlocal-contract-fixture` wheel；core 与 factory 都位于 venv site-packages。241 个安装包文件与冻结构建源逐字节一致，无 mismatch。core wheel SHA256 为 `1a722d21ce956d15c2ae54c52ca775190cb1eecd0013451de989736627c3b589`。

最终负控覆盖：accepted/interface、completed 状态、external ID、retained backend proof、retained collect 文件篡改；缺观察但 query 不补写；本地 cleanup/transport/exit/status 与伪装后端；unsafe/重名 collect 输出；错误 attempt 配置；未知状态阻止第二次 submission。正控对 remote 成功与失败都真实执行 CLI run/query/lookup/collect，封存 W、让 A 从正式挂载读产物，再构建后继 W admission。A/host anchors 是协议 fixture，不是模型推理。

另检查 sealed validation 时 adapter.load 被替换为失败断言，读回仍通过且无文件改写；因此科学历史没有用 live backend query 补造结论。旧 local 与 cov 原件也保持不创建新控制投影的兼容读取。

资源记录均 cleanup_complete=true、无内存停止触发。source 观察 tree RSS 峰值 283283456 bytes，最终安装检查峰值 160829440 bytes。原始证据分别保留于 `/tmp/scid-nonlocal-f1-final-source-r3`、`/tmp/scid-nonlocal-f1-attempt-final`、`/tmp/scid-nonlocal-f1-installed-final-20261016`；精确命令见机器记录。`git diff --check` 通过。

## 限制与冻结结论

没有运行全套平台矩阵、真实远端 executor 服务、模型、solver、daemon/browser 或跨主机恢复。共同协议以安装的可信 adapter 对自身原生终结证据的验证为前提，不对任意插件错误实现作普遍正确性承诺。H/W/A fixture、公开指标和目录交付均不赋予科学目标完成或外部服务提交资格。

在上述边界内，F1 当前 8 文件差异可冻结提交。F2 的独立通过结论保留在 [F2 复审报告](GENERIC_PLATFORM_ARCHIVE_F2_REVIEW_20261016.zh-CN.md)，两者不互相替代验证范围。复审者已结束实现审查，不再写入被审代码。
