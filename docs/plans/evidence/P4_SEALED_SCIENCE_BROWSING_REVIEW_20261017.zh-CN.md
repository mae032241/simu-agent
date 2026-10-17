# P4 已封存科学浏览：独立审查

结论：**静态 PASS，可由 root 运行冻结的最小定向检查。动态未由本审查者执行。** 基线 `73f57c6`；范围为本节点两生产、两测试及实施账五文件，不含并行 F2 或未实施的 F1。

## 核对结果

- `instance_ui.py:166` 起在新 GET 之前保留 exact Host、原 browser 实例/boot/read scope；不要求普通实例启用 execution authority。新增路由仅 exact step/成果序号和分页位置，不接收任意文件路径。管理/审批 POST owner 未改变。
- `instance_science.py:85` 的 `_sealed` 核 settings、job/raw/result 和封存 attempt ref。`execution.reference → records/proof` 为只读；读取 raw 使用 `execution.record(..., attempt=...)`，不会走默认 `record` 的 `_terminal` 分支，也不调用 status/snapshot、plugin/query/reconcile 或采样预算活钟。
- `instance_science.py:139` 起只从 seal 的唯一成员选择成果。成员须属于本节点 artifacts/嵌套 experiments，或同 seal observation 的 exact raw、scope/job、output/source/SHA/size、既有 archived snapshot；不公开 originals/private logs、native home、密钥或任意宿主目录。missing/tampered/link/非 regular 明确拒绝，不补造归档。
- `Original`（13–71行）使用 nofollow/nonblock 打开，先核 fstat/size/分块 hash，再 rewind，并持同一个 fd 传输；HTTP handler（`instance_ui.py:343`–368）在异常和完成时关闭 fd。替换路径不会令下载转读另一个新文件。
- 成果统一 attachment/octet-stream；HTML/SVG 不作为页面解释，保留 nosniff、CSP、no-store/no-referrer。科学结论按原 JSON 返回，不让展示改变科学字节或获得新的资格。

## 最小证伪证据与限制

已静态阅读五个 reader 用例、一项 direct UI read-cookie 用例及一项真实 loopback HTTP 用例定义：覆盖未封存/篡改/缺失/链接、路径替换、私有路径拒绝、完整分页/字面 percent 文件名、managed retained member、Host/cookie 及附件响应头。这些断言分别能证伪具体读取/授权故障；managed fixture 只证明封存读取边界，不冒称真实 backend terminal 或科学资格。原有 UI 控制测试未删除。

建议 root 仅运行 `test_instance_science.py` 的5项、`test_read_cookie_opens_only_sealed_science_and_attachment_members`，再单独运行 `test_loopback_science_download_uses_existing_browser_scope_and_safe_headers`。没有安装/打包变更，不要求安装、全量 suite、模型或求解器。

原文/成果虽分块读取，seal/job/observation 元数据仍全量 JSON 解析，完整 hash/传输成本不会因分页消失。传输中改变可能中断响应，不能撤回已发送字节；这不是文件系统事务、硬实时保证或恶意同 UID 隔离。作者主动写入科学成果的敏感字节不在路径归属检查的语义识别范围。真实浏览器、长期并发及科学有效性未验证。

最终文案收口：作者在测试前窗口修正实施账/注释及测试哨兵文案，默认 `record → _terminal` 准确描述为额外只读终态/预算/恢复校验，不再称“写投影”。复核此文字增量不改变行为或静态 PASS；本审查不以未经证明的旧路径写行为作为必要性证据。

审查仅文本/调用链/Git只读与限定 `git diff --check`（无诊断）。没有测试、收集、项目 import、HTTP/server、安装或业务执行；无生产/测试编辑及 Git 写入。

## 首次 source 结果后的负控断言复审

root 的 `.trial/functional_reaudit_20261017/p4-source/batch-001/pytest.log` 记录5 passed、1 failed（0.91秒）。symlink 负控原期待 `Original.check_path` 的 RuntimeError，但实际先由 `artifact:150` 的 canonical owner 检查精确拒绝为 ValueError，安全拒绝已经成立。作者仅将该断言改为 `raises(ValueError, match='source escaped its exact output owner')`，未放宽生产或吞掉拒绝；定点静态 PASS，可只复测失败项。审查者没有执行测试，此段不预报复测结果。

## root 串行动态证据核对

独立只读核对同目录 `p4-source`、`p4-retest`、`p4-http` 的 `result.json`、各 batch 的 `pytest.log/resource.json`：首次5通过/1失败；修正的单项1 passed（0.50秒）；真实 loopback HTTP 单项1 passed（0.97秒）。因此所选 **7个独立用例最终增量通过**，不是最后版本整组7项重跑。初次失败原日志保留。

三批受监控耗时分别1.096、0.689、1.167秒，总计2.952秒；峰值65,925,120 bytes（62.871 MiB）。全部 `cleanup_complete=true`、`memory_stop_triggers=[]`，无受监控止损。监控为768MiB RSS采样停止/10GiB可用下限/120秒每批，不是硬cgroup内存保证。

结论：静态 PASS 与所列小型动态检查证据相符，可提交本节点；不扩展成真实浏览器、实际科研资格、全局并发或可写归档恢复通过。以上动态由 root 唯一执行，本审查者只核日志，未启动测试。
