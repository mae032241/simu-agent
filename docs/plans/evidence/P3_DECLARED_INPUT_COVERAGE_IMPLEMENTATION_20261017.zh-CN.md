# P3 声明输入来源闭合：实施与验收账

状态：生产与测试冻结，交独立评审；作者仅完成静态 AST/尾空白检查，未运行测试、
项目导入、安装、模型、solver 或业务子进程。动态结果不得由本记录推定。

## 实际变化

- `execution_inputs.py`：小的可选 declared-source 合同与纯核验；只认已冻结 global、
  exact producer original、明确当前 job 作者或 unknown。不建新来源库或祖先列表。
- `experiments.py`：保留 Local 现合同，接受第二明确来源合同；自动 pin 实际共通来源
  helper。仍保存原 accepted，不新增科学输出字段。
- `history.py`：managed 来源覆盖保存在原 coverage 原件；带原 authority 的调用首次
  验签并核 package source、读时验证封存关系。明确 incomplete 不 fallback 到 compiler。
  observer 只有 prepare 配置显式 opt-in 新可信合同与本次 source view 才可消费，
  host 绑定 job/raw/config/实现；原展示 coverage 无资格含义。
- `qualification.py`、`formal_review.py`：消费同一原件；实际 producer 贡献进入现 authors
  遍历，未选作 implementation 的真实贡献也不能漏掉；不把普通 parents 继承为作者。
- TCAD `managed_execution.py`：对 V2 真实 canonical 包、零 slots/resolved inputs、prepared
  archive inventory、逐成员字节和原 gate reviewed package 核对。V3 沿已有 compiler；
  非空 V2/缺声明仍不提供覆盖。

原 accepted 与 observation 仍是唯一事实；readonly 不调用 adapter，不提升旧原件。
未知不授资格、restricted 支配 unknown。clear 仅覆盖框架声明/冻结链，不能证明任意
TCAD/native 外读封闭、科学正确、真实 native 身份或执行许可。宿主/可信 adapter 仍为软信任边界。

## 精确建议验收

仅新增两个目标，不建立安装/模型矩阵：

1. `tests/research_loop/test_native_execution_inputs.py::test_self_contained_v2_terminal_keeps_exact_inputs_and_next_subject_review`
   沿真实包准备、gate/accepted、terminal observation、W seal、后继正式 review 请求；
   核 unknown 不提前 complete、无 compiler 的 V2 完整来源/作者、错误 producer、
   明确 incomplete、缺能力与真实 archive 篡改。backend 与 native 身份仍是可信 fixture DI，非 solver 验收。
2. `tests/research_loop/test_observer_input_sources.py::test_observer_declared_sources_bind_authors_and_never_upgrade_display_coverage`
   沿真实输入/输出 seal，观察未 selected producer 贡献进入作者集合；核未知来源、错当前
   作者、错 producer、缺 view 与原 observation 篡改；readonly adapter 哨兵禁止重跑。
   adapter response 与 native identity 是合成输入，不声称真实平台独立性通过。

可能影响旧 Local source 与 V3 compiler 消费，root 可选原定向用例各一项；作者不自行扩大运行。

## 与并行节点的文件账

P3：上述六份生产、两份测试、本设计和本账。`experiments.py` 另含受 root 委托的 P4
独立 owner-lease hooks（完整 effect 与 Records 写发布、CLI action 生命周期、helper pin）；
它们属于冷 checkpoint 接线，依赖 `instance_owner.py`，不得作为 P3 独立代码声称。
P2 budget/maintenance、P4 owner/archive/CLI 与 UI/browser 作者文件不在本节点实现所有权内。

尚未动态验收：真实 observer 集成、真实 TCAD/SSH/solver、实际 native 作者与全权限外读范围。
本节点不补未知来源 clear、不增加授权或预算，也不实现 checkpoint 恢复。
