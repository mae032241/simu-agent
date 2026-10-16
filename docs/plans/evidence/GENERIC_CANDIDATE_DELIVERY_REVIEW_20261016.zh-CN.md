# 通用候选与目录交付独立审查（2026-10-16）

结论：**PASS，范围限定为本次 `local_execution:command` 候选登记、精确原件选择、本地目录交付与所测恢复路径。** 未发现本范围内需要阻断本次修改的缺陷。此结论不等于平台全局无缺陷、完整测试全绿、真实模型科学推理通过，或已向外部服务提交。

## 精确差异与方法

基线为 `dev` 的 `6677310b93528fd5a35087493ddcf32b7278265a`，审查其上的未提交修改。行为范围为 8 个生产文件：controller、delivery、history、local_experiments、native、shortlist，以及新增 generic_results、generic_delivery；测试范围为 generic_inverse 的 native.py、run.py 和 test_generic_inverse_tools.py。另阅读实现者的 `GENERIC_CANDIDATE_DELIVERY_20261016.{json,zh-CN.md}`。不把其他未跟踪历史材料或另一个平台边界审计报告算作本次实现。

按 `scid-cross-boundary-review` 与 `scid-change-scope-checks` 逐层只读追踪候选、科学密封、选择、交付原件、隔离进程和恢复账本。审查者未编写上述实现，未修改生产源码、未回退他人改动、未调用模型或 solver、未提交。没有重复运行已有验收负载；本报告依据直接读取的原始日志、安装身份、密封结果与实际交付目录，辅以只读摘要及哈希核对。

11 个行为/测试文件当前 SHA256 与实现者机器记录逐项一致，没有差异；安装版复制测试的执行文件摘要也一致。完整精确摘要见 [验收机器记录](GENERIC_CANDIDATE_DELIVERY_20261016.json)。

## 实现边界审查

### 候选声明与密封原件

`LocalExecution.read_result` 保留 version 1 的既有输入，新增可选 candidate 元数据。候选必须显式指定一个已声明的有限指标，并具备 evaluation_key、direction；artifact 必须属于已声明且真实保留的输出。多指标而未声明 candidate 时只保留测量，不默选一个指标。非法 candidate 保留原始执行事实与文件，但结果为 invalid。失败或 unknown 进程不会投影为成功候选。

`generic_results.identity` 由完整 scope 与 call_id 生成候选身份，不由作者填写 ID 或摘要。投影同时保留所选指标的口径、方向、完成记录与 artifact 原件证据。已有领域 observer 为空或不可用时，通用候选仍来自自己的 managed call；不会冒用领域 observer 的资格。两类观察的身份冲突拒绝通过。

`generic_results.sources` 从同一密封 observation 的 exact candidate、managed call、accepted 清单和 completed 记录解析输入。输入匹配使用 accepted cwd 加原始相对名，并核对摘要/大小，不按最近文件、同名 artifact 或最高分搜索。随后 `delivery.freeze_sources` 和既有 `_proof` 再次校验/冻结原件；A 的选择经既有 binding 绑定到冻结任务、原始结果、科学 seal、候选 source、目标和 operation_id。

### 选择与可选审计

通用候选复用现有 shortlist/public selection 规则与 A 的完整比较及 override 校验。测试的选择是 scripted、公开指标驱动的选择，框架绑定行为和科学判断资格应分别报告。

descriptor 显式 capabilities 决定是否提供可选 audit/smoke；缺失可选能力保持中性的 not_provided/unconfigured，不伪造成 passed。旧 descriptor 没有 capabilities 字段时，submit 仍默认执行必需 audit。若配置显式 candidate_audit_policy，而 descriptor 声明不提供 audit，prepare 在创建实例前拒绝。声明 audit 时，精确 source 的 audit_required 保持在冻结交付绑定中，submit 会先走既有 audit 恢复/判决路径；新的可选语义没有替代必需策略。

### 隔离目录交付与恢复

generic_delivery descriptor 冻结 adapter、launcher、runtime、target；实际 leaf 经 bwrap 的独立 PID/network 等命名空间执行。输入与 adapter 只读；promote 可写目标，confirm 只读目标。控制目录不能作为目标根或目标的后代被暴露。

promote 创建 operation_id 对应的独立 pending 目录，写入选定 artifact、inputs、outputs 与 manifest，逐文件校验摘要后提升到最终目录。存在最终目录或 pending 冲突时拒绝覆盖。confirm 比较精确 manifest 与每个文件的摘要，结果明确标记 `exact_local_directory_delivery_confirmed`。它证明指定本地目录交付，不提供科学或外部服务提交资格。

恢复沿用既有 intent-before-effect 账本。submit 已被接受后，无论 promote 响应丢失、confirm 响应丢失或目标状态不确定，后续仅允许在原预算内确认，不能自动重复 submit。已完成确认复用 sealed outcome，不增加 leaf 调用。pending 冲突保持 unknown，不被翻译为科学 rejected。

### cov 兼容范围

cov_delivery 未修改。已有 cov 候选走原领域 resolver；generic direct source 只匹配其 scope/call 派生的候选 ID。旧 descriptor 的必需 audit 默认保持。源码验收包含 cov delivery lineage、control selection 与既有 delivery 检查，支持已执行的兼容路径；两项需要原始 cov public harness/runtime 的 opt-in 测试未执行，因此不作真实 cov 外部双目标提交或 public audit 完整通过声明。

## 独立核查的证据

实际执行者使用仓库 serial_lock/run_one 与默认资源监督；审查者只读其结果。

| 范围 | 直接读到的结果 |
| --- | --- |
| 当前 generic/local/delivery/cov lineage/control selection | 140 passed、2 skipped |
| 加入旧 history 文件后的源码合并命令 | 151 passed、14 failed、2 skipped，167.86s；监督 exit 1、cleanup_complete true |
| 独立 git archive 6677310 的旧 history | 11 passed、14 failed，4.56s；失败 node IDs 与合并命令完全一致 |
| fresh wheel 与隔离 venv 的同一 generic 文件 | 14 passed，37.51s；监督 38.269s、exit 0、cleanup_complete true |
| 离线 wheel 构建/安装 | 监督 2.630s、exit 0、cleanup_complete true |

源码命令：

```text
python scripts/run_tests.py --lane source
  --output /tmp/scid-generic-delivery-final-source
  tests/research_loop/test_generic_inverse_tools.py
  tests/research_loop/test_local_managed.py
  tests/research_loop/test_delivery.py
  tests/research_loop/test_cov_delivery_lineage.py
  tests/research_loop/test_control_selection.py
  tests/research_loop/test_history.py
```

原始日志为 `/tmp/scid-generic-delivery-final-source/batch-001/pytest.log`、`/tmp/scid-generic-delivery-history-baseline/batch-001/pytest.log` 和 `/tmp/generic-candidate-delivery-installed-20261016/check/pytest.log`。审查者独立提取并比较 14 个失败 node IDs，确实一致；还将 baseline 的 history.py、contracts.py、selection.py 与 test_history.py 逐字节对照 `git show 6677310`，一致。这证明本次所观察失败在基线可复现，不证明这些历史问题无害或全局没有其他回归。

安装驱动为 `/tmp/generic-candidate-delivery-installed-20261016/supervise.py`。实际 check 使用独立测试目录，只复制新 test、execution_fixtures 与任务 fixture，不复制 src/conftest；清除 PYTHONPATH，通过隔离 venv 的 `python -I -m pytest`、空 pytest.ini、`-o pythonpath=` 运行。已读 installed-identity：core 来自 venv site-packages；241 个安装包文件与冻结构建源逐字节一致，无 mismatch；真实 console help 入口亦已检查。安装测试真实运行本地进程与 bwrap 目录适配器，不以 mock 替代成功交付。

14 个 generic 用例包含：两候选与一次失败、export 和目录交付、promote/confirm 响应丢失、pending 冲突、完成确认重读、非法候选元数据、跨 scope 身份、必需 audit 缺失、空/不可用 observer。响应丢失测试只截断真实 leaf 已产生的返回；实际交付或冲突仍经过原适配器。负面对照保留已提交调用且禁止第二次 promote。

另直接打开安装版成功交付的 bundle：manifest 绑定选定 `operator_ridge` 候选、operation_id、artifact 摘要、三份 inputs、三份 outputs 和相对 replay 参数；所有对象的当前字节摘要与 manifest 一致。测试仅从**实际交付的 inputs 与 replay**重新执行并逐字节比较全部 outputs，此项比上一轮仅从同 instance archive 复现多覆盖了实际交付产品。原 archive 复现路径仍通过。

`submit_count=1`、`goal_completion=not_asserted`、`models_called=0`、`scientific_reasoning=false` 均已在原始证据核对。公开 MSE 与上一轮一致，两口径下 operator_ridge 较低；此事实没有被当成隐藏分数或真实模型科学结论。审查者运行 `git diff --check` 通过。

## 剩余验证范围

- 本轮 PASS 限本地 managed command 的候选/目录交付，不代表任意第三方 execution adapter、plugin 平台接口或非本地运行时都已闭环。另一个平台边界审计独立记录这些范围，不能由本报告覆盖。
- 没有运行全套测试或完整平台矩阵；共享 history 的 14 项基线失败仍存在。此次针对变更表面的检查不是全局无 bug 证明。
- 两项真实 cov public harness/runtime opt-in 检查缺输入而跳过；未执行 live model、真实 solver、网络服务提交或浏览器流。
- audit/smoke 缺能力时只有交付事实，没有该项科学资格。目录确认和框架 action_kind=submit 不等于向远程服务提交。
- scripted H/W/A 只证明候选登记、科学选择输出的结构绑定、精确产品与恢复链；没有证明模型能提出机制、作出可靠科学判断或达到 objective 的全部科学完成条件。
- 通用 bundle 保留接受时的输入/结果与 replay 信息；本次复现资格针对标准库 fixture，不把未冻结的外部环境、任意依赖或未知分布性能纳入资格。

在这些明确边界内，本差异可冻结提交。生产源码审查期间未被审查者更改。
