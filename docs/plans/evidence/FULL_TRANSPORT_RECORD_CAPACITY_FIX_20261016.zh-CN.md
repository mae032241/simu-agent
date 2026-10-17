# 完整 TCAD transport / manifest 容量补修

范围：容量修复的同根漏项补充，基于 `a1d37aa` 工作树；与并行 P1 注册接线、[P2 接缝设计](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)分开。未运行模型、真实 SSH、solver 或许可证检查；未修改旧实例/封存/授权或执行资源额度，未提交。

## 精确文件清单

生产：`src/scidiscovery/plugin_runtime/collection.py`、`plugins/tcad_artifact/tcad_artifact/{command_adapter,project_packager,remote_runner_py36,ssh_transport,transport_logs}.py`，共六文件。

测试：仅新增 `tests/operations/test_tcad_full_transport_records.py`；既有兼容检查只运行，未改原测试文件。独立 P2 建议文档仅更新两条预审意见及本容量证据链接，不属于容量生产实现；P1 文档与文件未由本执行者修改。

## 根因与最小改动

- `plugin_runtime/collection.run_bounded` 默认 stdout 8MiB 硬拒、stderr 8MiB 截断；默认改为 None，完整协议/日志保留。显式 `max_output_bytes` 仍按原语义执行 stdout quota 和 stderr excerpt；timeout、idle、停止与进程组回收保持原规则。
- TCAD `command_adapter._call` 额外 stdout 8MiB 硬拒、`SSHRemoteClient._run` 固定传 8MiB、SSH 完整 RPC response header 1MiB、transport/standalone runner 完整 request 1MiB 均移除。它们载有完整 descriptor/控制清单，不是模型视图。response envelope、operation/request identity 与类型检查保留。
- `transport_logs.preserve_log` 取消完整日志 8MiB 拒绝；旧内容重读用流式哈希和 size 校验，不再额外 read_bytes 一份完整日志；内容地址、原路径及符号链接拒绝保留。
- `TCADRuntimeManifest.outputs/collection_errors` 取消固定4096项。正式 attestation 下游的 checks8192、missing_required_outputs4096 和三个 output_count<=4096 同步取消，否则已收全 manifest 仍不能消费。自动生成 RuntimeContractCheck.rationale 的4096字符限制也取消，避免完整未声明输出清单/长终态错误使失败证明自身无法生成。类型、非负计数、路径、唯一性、哈希及 verdict/check 一致性验证保留。

完整文件下载与归档成员仍流式复制/哈希；已存在的分批 get_archive 不截累计清单，继续用有界单批 metadata 传输。**JSON 和 run_bounded 的 bytes 返回仍需完整内存**，本次没有把它们改成流式 JSON 解析，不能宣称无限内存或全链路流式；显式资源限制与外部测试监督照常生效。

## 保留的限制及性质

- 管理员显式 `RunnerPolicy.max_manifest_bytes`（必填；示例为4MiB）及 `max_transfer_bytes`，原 job 的 `ResourceLimits.max_output_bytes/max_storage_bytes`、wall/cpu/memory 和收集 deadline 不修改。它们是声明执行/传输 policy，非本次移除的框架机械容量默认；超限仍明确拒绝。
- 单次 TCAD typed implementation/package 的 payload schema 与资源 policy、inspect/progress 的紧凑预览不在本补丁扩大；不能用这些声明推断完整历史有累计容量上限。
- `known_failed`、取消、科学审计或资格语义未改。本文不授予 managed TCAD 接入或真实远端资格。

## 新增精确检查

仅新增 `tests/operations/test_tcad_full_transport_records.py`，12项：

1. 真实子进程 stdout/stderr 各9MiB且末尾字节完整。
2. 显式 transport quota 及总 timeout 保留。
3. 真实 command collect 返回9000项 descriptor、JSON超过8MiB，逐件原路径/hash验证并完整保留超过8MiB stderr；重复日志按内容复用，原件/目录逃逸/旧日志变化拒绝。
4. 本地 SSH 协议 stand-in 真实子进程接收2MiB请求、返回9MiB RPC JSON header，不触网。
5. 真实 standalone runner 接收超过1MiB的1600项 archive请求，归档清单及成员完整；显式 transfer quota 超限仍拒绝。
6. 真实 command→transport CLI→本地 SSH stand-in→standalone runner 处理超过1MiB请求，返回原 terminal status；显式 max_manifest_bytes=1仍拒绝。
7. 9000项 manifest 经正式 `transform_adapter.attest_runtime` 消费，产生9002项完整 checks；篡改payload返回fail而非通过；5000项collection_errors保留。
8–10. 超4096项 manifest 的重名、重复路径、路径逃逸分别拒绝。
11–12. 独审补充的大量未声明输出、8192字符终态error，经真实transform形成完整fail attestation，长理由原文保留，原manifest字节不变；不将工程失败改为通过。

SSH stand-in 只在本地 exec 真实 runner/本地协议脚本，不能冒称真实远端或 solver 验收。大JSON检查不是科学评分。

## 原始结果与冻结

所有命令经 `scripts/run_tests.py` 的 serial_lock/run_one 监督；与 P1 执行者协调，无并发测试、无全量扩测。证据根 `/tmp/scid-tcad-full-transport-20261016/`：

| 批次 | 原始结果 | 监督 |
| --- | --- | --- |
| source-r1/batch-001 | 新文件9 passed、1 failed，2.90s；唯一失败为新CLI夹具漏 `SCIDISCOVERY_TCAD_RESULT_ROOT`，尝试默认只读 `/var/lib`；保留日志 | 3.578s，RSS174108672，cleanup_complete=true |
| source-r2/batch-001 | 仅复测失败项及既有archive/quota/attestation兼容，8 passed、1 deselected，1.04s；只改fixture结果目录env与既有policy报错匹配，生产未改 | 1.377s，RSS161865728，cleanup_complete=true |
| process-r1/batch-001 | 上批因process lane标记未选的真实 timeout/idle 单项补验，1 passed，0.48s | 0.778s，RSS79224832，cleanup_complete=true |
| source-r3/batch-001 | 独审发现上述长失败理由同根残余后，只复测两项真实失败attestation，2 passed，1.21s | 1.567s，RSS128258048，cleanup_complete=true |

最终覆盖新增12项和既有8项；不是一次20pass批次。各批 `pytest.log`、`resource.json` 与顶层 `result.json` 保留。初始三批生产六源未变，新测试只在首轮后补夹具；独审后仅 project_packager 长失败理由字段及两项检查新增，source-r3对应此窄修。初冻7文件哈希保留于证据根 `frozen-sha256.json`，最终哈希见 `frozen-final-sha256.json`；不宣称所有源码批使用相同文件哈希。本批未单独构建/测试安装包，源码结果不冒充 installed 或远端资格。

`git diff --check` 通过；未跟踪新文件另以 `git diff --no-index --check /dev/null <file>` 检查，无空白诊断。等待独立审查，root决定提交。

## 2026-10-17 重启后证据状态

上述动态批次是重启前执行者报告，不是当前工作树的新验收。重启后 `/tmp` 原始日志不可复查，不能继续宣称上表日志和哈希文件仍保留；565a2e4 已精简相关测试，本文的原始测试数量也不代表修改后的测试集已运行。当前仅做静态审查，未重跑 pytest、安装或构建；资源硬隔离尚未确认。最终提交需要独立复核，动态资格仍未完成。

独立静态复核补修：真实runner会在已截至8192字符的error后追加diagnostic collection失败信息，原Manifest.error的8192上限仍会拒收完整失败manifest。现取消该字段的机械上限，并将terminal_error负例改为原错误加真实类型的诊断后缀；不运行测试。RuntimeAttestation.rationale由producer生成固定短范围说明，仍保留其上限。
