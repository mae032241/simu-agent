# P3 声明输入覆盖独立静态审查

结论：**限定范围静态 PASS**，可交root唯一串行定向验收。不是动态/真实solver资格。评审者未运行测试、收集、项目import、业务CLI、安装、模型、服务器或Git。

## 范围与调用链

检查 `execution_inputs.py` 的typed合同/纯来源核验、`experiments.py` 的公开能力冻结与accepted capture、`history.py` managed/observer发布及只读消费、`qualification.py`输出限制、`formal_review.py`贡献作者，以及TCAD `managed_execution.py::input_sources`；定点读两新增用例与实施账。并行P2预算/维护、P4 owner lease hook不混称本节点通过。

- TCAD只有实际V2 canonical package且project.input_slots、resolved_inputs均空才声明本合同。prepared spec的完整archive inventory、solver/profile/arguments/capability和流式tar成员字节与包中files核对；缺成员、额外成员、重复或错字节均拒绝。来源是原gate许可的精确package producer，不按相同hash猜源。非空V2不提供覆盖，V3保原compiler路径。
- 共通`validate_exact_input_sources`核唯一frozen optional capability、actual contract、scope/native attempt/job/config/prepared与evidence原件；typed来源只能来自当前job既有global/producer边、显式当前作者或unknown。readonly不构造adapter。明确incomplete不会fallback到compiler；unknown/not_submitted不能发表complete。
- observer必须prepare显式冻结新合同和实际adapter/共通代码身份，响应另给完整来源view；job/raw绑定封存原observation。原展示coverage=complete不提供来源资格。缺view/旧配置继续unknown，空列表只有可信声明覆盖边界内才有效。
- restriction沿原全部冻结输入边传播；来源覆盖不把未知原始材料变clear。真实producer贡献进入既有authors递归，未selected的实际贡献也保留；普通parent不自动成为作者。旧provenance path.exists只恢复已发表覆盖，不生成新资格或回填旧proof。

## 最小动态目标与局限

作者两新增目标能证伪实际跨owner接缝：

1. `test_native_execution_inputs.py::test_self_contained_v2_terminal_keeps_exact_inputs_and_next_subject_review`：实际factory/prepare/gate/accepted/terminal/seal到后继review请求；queued不能提前complete，错producer、显式incomplete、缺合同与actual archive篡改必须失败。
2. `test_observer_input_sources.py::test_observer_declared_sources_bind_authors_and_never_upgrade_display_coverage`：实际seal/source/authors消费，未selected producer必须加入作者集合；错job作者/producer、unknown、缺view、原observation篡改负控；只读adapter哨兵防重跑。

如需共享边界回归，原Local覆盖与V3 compiler闭环各选一个即可，无安装/模型矩阵。新增用例的backend/adapter response与native身份为可信合成DI；只能证明实际控制消费，不证明真实observer/solver输入诚实、真实平台独立性或任意native外读封闭。本评审不保证完整审阅全部历史测试，不承诺归档跨目录可迁移资格、强隔离或科研正确性。

## root动态增量与审查漏项

已只读核对 `.trial/p_finish_20261017` 下 sources、opaque_retry、opaque_generic_fix 的pytest/result/resource原件：

| 批次 | 实际结果 | 监督秒数 | 树RSS峰值bytes |
|---|---|---:|---:|
| sources | 3 passed、1 failed：opaque fixture访问可选compiled_implementations键 | 17.108 | 85,745,664 |
| opaque_retry | 1 failed：通用validator误读Local专有accepted.config_sha256 | 4.021 | 84,447,232 |
| opaque_generic_fix | 原opaque单项1 passed | 5.988 | 84,434,944 |

三批监督共27.117s；4个唯一source目标最终增量通过，6次执行含两次失败，不称最终HEAD全4项重跑。三批cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]，无地址空间硬限制。另lease_and_local的Local真实tiny进程回归通过（与P4 lease同批两目标共2.274s、峰值70,680,576 bytes），不另算P3新增用例。

fixture改为opaque严格无compiled_implementations、V3仍严格len=1；production contracts原本只发表非空compiler字段。第二次是**真实通用/Local owner混淆**：exact来源validator应核mandatory `accepted.interface.config_sha256`。已静态追 `_adapter` body精确为config去execution_interface，freeze将同编码hash保存在interface；修复不新增TCAD假字段、不fallback，原projection/interface相等检查与新增错hash负控保留。最后单项pytest1 passed / 5.80s，实际闭合到精确来源/作者和后继review请求。

此缺陷在评审者首轮静态PASS中漏检；动态用例实际证伪并促成修正，不能用静态结论覆盖失败历史。当前结论为修正后上述有限动态增量通过，可提交；其余真实平台、solver、任意外读与归档可移资格仍未证明。评审者本人未运行任何测试。
