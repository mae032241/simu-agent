# 引用按需读取最终独立逻辑审查

当前独立逻辑复核结论：**PASS（修复后窄范围）**。以下保留初次 REVISE 及后续发现历史；两个确认分支均已获得逻辑修复，新增测试结果由父任务记录。本审查未修改生产代码。

## P2：已封存恢复报告的内联计算仍按当前别名解析，丢失原输入入口

位置：`src/scidiscovery/artifact_agent/service/reference_access.py:283`（内联 selected_only 分支）、`:292`（直接收集旧别名），以及 `:314`（只查当前 scoped_bindings）。`:296`—`:301` 仅为独立 `calculation_record` 原件选择 `_calculation_origin`，没有覆盖报告中的内联项。

真实触发路径：

1. A 使用真实 `worker_tcad_curve_score` 生成带受控 attempt 的计算；其原 CSV 输入别名是 `reference_material`。
2. A 失败，B 通过现有 draft_from 恢复，同时在 reference_material 端口加入另一个合法输入。B 当前别名变为编号形式，原 proof.recovery 保留 A 的准确原命名空间。
3. B 将准确原计算放进正式报告 `calculation_records[0]`，将 attempt.proof_kind 设为 recovery。正常 `worker_submit_result` 已返回 **completed**，证明这不是不可准入的伪造报告。
4. C 正常绑定 B 正式报告，调用 `worker_reference_read(source=该报告别名, action="list", pointer="/calculation_records/0")`。
5. 返回 `{"locator":"/calculation_records/0/input_digests/reference_material","alias":"reference_material","error":"reference_binding_missing"}`，没有可读 handle。另一项未改名 solver_outputs 输入正常返回 handle。

影响：已合法封存的恢复计算不能通过声明支持的“选中该项计算→读取该项输入”路径获取准确原 CSV。控制已经持有完整恢复证明，当前实现仍将其错误报告为缺失。此问题是导航/可用性缺陷；本复现没有证明错误授权或科学结果污染。

最小修复方向：为每个被选中的内联计算，按其受控 attempt 和精确 input_digests 选择对应原 namespace，再解析该项边；复用已有 `_calculation_origin`，并保留旧无 attempt 数据既有准入语义。读请求重建相同 handle 时也必须使用同一命名空间，不应只修 list，也不应把各恢复 origin 的别名全局合并。

既有覆盖缺口：`test_inline_calculation_requires_selected_section_and_checks_digest` 只覆盖当前 bindings 的简单内联项；`test_real_recovered_calculation_navigation_uses_original_alias_namespace` 覆盖的是独立 calculation_record 文件。两者分别通过不能证明“恢复 + 内联”组合正确。

## 复现与证据

可运行单测：[test_final_review_inline_recovery.py](../evidence/reference-on-demand-20260919/test_final_review_inline_recovery.py)。基于既有真实恢复测试，使用真实 Operation/MCP router、SQLite、受控计算及提交路径，不启动 solver。仅保留本问题所需步骤。

本次实际命令：

```sh
/home/da/miniconda3/bin/python /tmp/scid_guard_tests.py -c pyproject.toml -p tests.conftest /tmp/test_reference_final_review.py -s --tb=short
```

复现结果：预期存在 reference handle 的断言 **1 failed**；此前 B 完成封存断言通过；2.49 秒，进程树峰值 121.44 MiB，768 MiB 守卫未超限。精确候选摘要和诊断：[FINAL_LOGIC_REPRODUCTION.json](../evidence/reference-on-demand-20260919/FINAL_LOGIC_REPRODUCTION.json)。前两次准备性执行分别因 /tmp 未加载仓库 pytest 配置、工具只返回摘要而未读取 calculation_path 失败；修正测试装配后才得到上述生产缺陷，前两次不计为缺陷证据。

持久源码与最后执行的 /tmp 源码完全相同。复跑时将命令中测试路径换为上述持久源码路径；`-c pyproject.toml -p tests.conftest` 提供插件搜索路径和源码安装元数据 fixture。`/tmp/scid_guard_tests.py` 是本轮父任务提供的守卫包装器，使用仓库 `scripts/compiled_worker_process_guard.py::run_process_group` 执行 `python -m pytest -q`，设置 aggregate_memory_limit_mib=768；复现逻辑不依赖该临时包装器的业务状态。

## 范围与局限

按外层 scid-cross-boundary-review 技能做独立只读审查。对象为 HEAD `943c4626f8490530e9318eb9fbb409d2670908b9` 上 R4 本轮未提交实现；不把工作树此前大量修改归入本轮，也不继承既有 PASS 作为本审查结论。

实际追踪：ReferencePolicy/请求合同及编译暴露；本地 Worker 路由；精确 completed producer 与正式 manifest 配对；原计算证明/恢复 namespace；根和访问别名授权；共享恢复作用域的 SQLite 预留/结算及幂等唯一键；取消/候选接受前提交门；CAS 提交后文件入口和重放；访问 records 与生产 records、manifest parents、completed_for_output 的隔离；ValidationSources 与报告计算来源校验。

上述其余路径未确认新的实质缺陷，这不构成其全部生产场景已验证。既有 32 项定向、94 项兼容、3 项安装及 1 项权限结果来自本轮既有证据，本审查未重跑或合并为新增通过数。只新增上述串行最小复现；未全量/并行测试、未部署、未科研执行。hardened 原生文件拒绝分支、跨进程崩溃恢复和原生模型行为未新增运行验证；原生 A/B 与综合科学验收仍未完成。

## 修复后窄范围只读复核

父任务在用户授权后修改内联 selected_only 分支：有 attempt 的项复用 `_calculation_origin`，将对应 bindings 存入以完整 locator 为键的 `alias_scopes`；每条边分别选取 namespace。独立复核认为**原复现缺陷在逻辑上得到修复**：不同 calculation section 的同名 alias 不会覆盖；list 与 read 不带 pointer 的重建都经过相同提取循环；无 attempt 的 legacy 项仍走原 bindings 路径。参数化真实回归已扩展为外置/内联两种表示，且检查 read 获取准确 Ref 和下一轮封存；测试由父任务运行，本复核未运行。

另发现新分支风险，不能把上述窄结论扩大为整体 PASS：`tests/operations/test_analysis_evidence_recovery.py:260`—`:268` 已有合法正式路径将原计算 attempt.manifest_alias 改为 `prior_analysis_manifest` 后在新 C 中封存。C 没有新工具调用或恢复链，其当前 manifest.attempts/recovery 不包含原 attempt；准确旧证明在 C 冻结绑定的 prior manifest 中。此次新分支对所有有 attempt 的内联项无条件调用 `_calculation_origin(当前manifest, calculation)`，会在该合法输入上产生 `reference_attempt_unpaired`。此外，read 重建不带 pointer 时遍历所有内联项，因此无关的该类项也会使另一个正常 handle 的读取在过滤 handle 前失败。

这是由既有正式封存测试与新分支控制流交叉确认的可达性判断，尚未新增执行复现；本轮遵守“不运行测试”的复核范围。需由父任务处理准确 prior-proof namespace，并避免无关无法解析项中断其他直接引用；不能通过合并所有 origin bindings 解决。原 P2 的关闭结论与这一新增可达分支应分别记录。

## 第二次修复后的独立复核：PASS（窄范围）

父任务已实证上节准确 prior-manifest 分支：C 正式 completed 后 D 读取其内联计算失败，诊断为 reference_attempt_unpaired；父报告峰值 129.41 MiB。随后加入 `_reference_calculation_origin`，独立只读复核如下：

- 当前/恢复 proof 继续使用原 `_calculation_origin`；非 `tool_recovery_manifest` 的 proof 只从该报告正式 manifest 的精确 binding 获取。
- prior proof 检查 schema 和生产者声明后，沿生产者正式 report 复用 `_reference_pair` 的 completed、同实例、正式 parent 配对校验，最终要求 `paired_ref == proof_ref`。标签不是单独授权，未扫描或合并祖先。
- 原 attempt namespace 仍逐完整 locator 保存，多个内联项同名 alias 不相互覆盖；list 与不带 pointer 的 read 重建走同一逻辑；legacy 无 attempt 保持旧路径。
- 扩展既有历史回归在正式 C 后建立 D，实际调用 list/read 并核对原 Ref，覆盖先前漏掉的准确 prior-proof 分支。

因此原恢复内联 P2 及随后确认的 prior-manifest 分支，在本次候选中均可逻辑关闭；未发现此窄修复留下新的可达实质缺陷。父任务提供最终验证结果：29 项 reference 与该历史 case 合计 **30 passed**，11.71 秒，峰值 129.66 MiB；日志 `/tmp/scid-inline-prior-green.log`。本独立复核未自行运行测试。多 origin 同别名和 legacy 路径在本次是控制流复核，不声称已有新增运行覆盖。上述总体审查局限仍有效。

修复候选 `src/scidiscovery/artifact_agent/service/reference_access.py` SHA-256：`30728895d11ca03f5814c2b7e849253d99c047ea0aa9cdfb2ca5c019032c3043`。
