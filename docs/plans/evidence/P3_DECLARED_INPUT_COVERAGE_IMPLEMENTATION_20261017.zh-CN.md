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

## root 唯一串行验收追加

下列均由 root 运行，作者只读日志/资源记录，未自行运行。原失败日志保留。

| 证据目录（`.trial/p_finish_20261017/` 下） | pytest 结果/耗时 | supervisor 秒 | 树 RSS 峰值 B |
| --- | --- | --- | --- |
| `sources/batch-001` | 1 fail、3 pass / 16.90s | 17.108 | 85,745,664 |
| `opaque_retry/batch-001` | 1 fail / 3.82s | 4.021 | 84,447,232 |
| `opaque_generic_fix/batch-001` | 1 pass / 5.80s | 5.988 | 84,434,944 |
| `lease_and_local/batch-001` | 2 pass / 2.10s | 2.274 | 70,680,576 |

四批 `cleanup_complete=true`、`memory_stop_triggers=[]`，无安装/模型/solver。
最后一批只有 Local 正向属于本 P3；另一条独立进程 owner lease 属 P4，不重复计。
P3 共 **5 unique 目标最终通过**：opaque、observer、V3、Local 负向及 Local 正向；
opaque 共三次执行（第一次 fixture 错、第二次真实生产缺陷、第三次通过），
不把首轮或静态 PASS 改写为全程通过。

第一次：fixture 假定没有 compiler 的 seal 也必有 `compiled_implementations` 键，
而原生产仅在非空时发布。两处改为 opaque 严格 absent，V3 保留 len=1，不改生产。
第二次：新 exact validator 错用 Local 专属 accepted 顶层 `config_sha256`，TCAD 无该字段。
修为 mandatory 通用 `accepted.interface.config_sha256`，按原 `_adapter`/`freeze` 的同一
body 编码核对；不补假 Local 字段。原 case 明确顶层 absent、通用 hash 匹配及篡改拒绝。
这也是初次静态实施/独审遗漏的跨 adapter 假设，真实定向执行才暴露。

最终通过只覆盖这些可信 DI/source/process 路径；不提升为真实 TCAD、observer 部署、
native 身份、SSH/许可证或任意外读封闭验收。P2/P4 source 与浏览器结果属各自原账。
