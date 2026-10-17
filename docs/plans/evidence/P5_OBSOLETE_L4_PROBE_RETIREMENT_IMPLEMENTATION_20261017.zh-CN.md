# P5 失效 L4 TCAD probe 精确退役

状态：实现冻结，待独立静态审查；测试未运行。2026-10-17。

## 消费闭包与删除范围

静态检查 scripts/tests/deploy/pyproject/.github：两 probe 使用已不在当前 TCAD plugin 声明中的 `tcad.deck.author.initial.v1`、`tcad.deck.author.revise.v1`、`tcad.deck.review.v1`。仓内非文档消费者形成封闭链：revision probe 导入 agent probe，agent probe prepare 仅消费 sole transport；旧 predicate 测试只导入 revision probe。其余命中仅是两份 source release 文件名单。仓外引用和历史运行资格未验证；不把静态无仓内调用解释成已验证外部服务退役。

精确9文件：

1. 删除 `scripts/l4_live_tcad_agent_probe.py`。
2. 删除 `scripts/l4_live_tcad_revision_probe.py`。
3. 删除只服务上述 probe 的 `scripts/l4_tcad_transport_fixture.py`。
4. 删除 `tests/operations/test_l4_live_tcad_revision_evidence.py`，三独特断言迁到实际生产 owner，见下。
5. `scripts/build_git_release.py`：仅移出上述三条已删脚本名单。
6. `tests/installation/check_source_release.py`：仅移出上述三条必需文件项，不运行安装检查。
7. `scripts/run_root_invoke_ab.py`：仅删除失效的 `tcad_revision` CASE；保留 figure/hypothesis、原 catalog 编译依赖、其它行为，不借本节点重写 live replay。
8. `tests/operations/test_tcad_native_implementation.py`：新增三个纯 source 合同测试，复用既有小包原件，不创建 Runtime/Root、安装环境或 solver。
9. 本实施账。

不整目录删除，不改有效 CLI/runtime/transport/能力，不修改旧历史 evidence 或声称全部旧入口已退役。保留两份 release 名单的其它条目和所有 source fixtures。

## 三条删除保护如何保留

旧 `_is_qualified_debug_report` 没有其它生产消费者，不抽死 helper 续命。已有 diagnostic lineage 测试验证恢复报告的正向保留，但不覆盖本次三种模式/原件关系，因此改为直接测当前 owner：

| 原语义 | 当前实际入口及最小负控 |
| --- | --- |
| 精确 initialization 成功报告可用 | `ProjectInitializationAttestation` 严格解析，再由 `DeckProjectDraft` 校验实际 files 的 source digest；明确 qualified 为真 |
| preflight 不能冒充 initialization | 字面 profile/mode 在 initialization 模型上产生 `ValidationError/literal_error` |
| 过期 source 不能冒充当前项目 | 实际 `DeckProjectDraft` 拒绝 source digest 不同的 initialization attestation |

源向量使用原 fixture 固定的 `main.cmd`、`Solve {}\n` 及既有固定 digest `60d208...499b0d`，正向先断完整 files 列表；不调用生产 digest helper 生成两端自证。原 predicate 的 terminal/exit/layer/qualified 一致性现由 attestation 模型既有 validator 承担，未新造实现或测试矩阵。

## 静态检查与待验收

仅限定四份保留 Python 文件 AST、文本消费者闭包与文件删除检查；结果见冻结通知。未执行 pytest/collect、项目 import、安装/build、CLI业务、模型、solver、SSH 或 Git。

root 最小 source 验收目标为 `tests/operations/test_tcad_native_implementation.py::test_initialization_attestation_accepts_exact_project_source`、`::test_initialization_attestation_rejects_preflight_report`、`::test_initialization_attestation_rejects_stale_project_source`。删除和名单同步用静态检查，不用为此重跑安装/完整旧套件。真实 solver、live MCP/Root 与外部脚本消费者未验收。

## 追加：root 串行定向验收

2026-10-17，root 在实现冻结后唯一串行运行上述3个 source 目标，`3 passed in 0.28s`，退出码0。原日志与资源原件位于 `.trial/review_reserve_followup_20261017/p5-source/batch-001/{pytest.log,resource.json}`。本段补充前述“测试未运行”的初始冻结状态，未改生产或测试。

资源记录：supervisor 总耗时0.728秒，观察到的进程树 RSS 高水位65,941,504字节（约62.89 MiB），`cleanup_complete=true`，`memory_stop_triggers=[]`，`received_signals=[]`。本批未启地址空间限制；结束时系统 MemAvailable 为14,607,413,248字节。该观测不是一般容量上限或硬内存保证。

这3项增量通过只验证迁移后的实际 source/mode 校验保护；未运行安装、全量测试、旧 L4 live probe、模型或 solver，不据此声称仓外消费者或真实平台资格已验收。追加结果待独审核对后由 root 提交。
