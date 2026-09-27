# R5-M6C 生产者下游拓扑预测删除实施证据

状态：实现、全量回归与独立审查均已通过；仅放行 M6-D，M7 未放行

## 1. 本阶段回答的问题

旧 `OutputPortSpec.allowed_input_usages` 要求生产者预先列出未来消费者会怎样使用输出。这把本应由
下游输入端口、独立审查边和修订合同决定的事实复制到生产者，新增领域或新增消费者时必须反向修改
既有生产 Operation，形成手写拓扑和跨插件耦合。

M6-C 删除该预测字段，不建立替代用途图、注册表、规划器规则或兼容双路径。生产者只声明自己产生
什么；消费者声明自己怎样使用输入。

## 2. 当前唯一合同

`OutputPortSpec` 只保留输出自身的 Schema、媒体类型、基数、current、校验器和科学语义合同。
Root 对有 Operation 来源标签的输入只解析以下冻结事实：

1. 精确生产 Operation 标识、版本、摘要和输出端口；
2. 该输出是否位于编译后的独立审查 subject edge；
3. 下游输入端口自己的 `usage`；
4. 直接修订的 base、change request 和目标 reviewer 合同；
5. M6-B 已编译的 Operation 级资格准入。

`_operation_output_contract` 因而只返回精确输出端口及其可选 reviewer 合同，不返回未来用途集合。
ABI 从 10 提升为 11，目录摘要同步更新；冻结 M2 oracle 继续以旧 ABI9 运行，不在生产路径增加历史
字段兼容。

## 3. 保留的失败关闭边界

- 未审查 subject 可以进入其精确 reviewer 的精确输入端口，不能直接进入其他需要审查的消费；
- reviewer 结果必须对应同一 subject revision，旧审查不能覆盖新 revision；
- 直接修订仍要求 base 的冻结 reviewer 合同与修订 Operation 的 reviewer 合同一致；
- change request 必须是该 base 的精确 reviewer 输出；
- 生产 Operation 卸载、版本漂移、摘要漂移或输出端口不存在仍拒绝；
- `explore` 后果或 `internal` 目录范围的输出在 Agent 和确定性 Transform 两条登记路径中都固有标记
  为不可充当科学 claim，而不是依赖已删除的未来用途声明。

## 4. 新的可扩展性正例

盲 CSV 观察生产者的输出现在由下游消费者按 `evidence_inventory` 使用。旧生产者预测没有允许该用途；
删除字段后，只要 Schema/媒体合同匹配且存在该 revision 的精确独立审查，预检即通过。测试同时覆盖：

- 缺失独立审查时拒绝；
- 精确审查时通过；
- 修订后旧审查失效；
- 新 revision 的精确审查重新通过。

这证明新消费者不再要求回改既有生产者，同时没有弱化审查边。

## 5. 实现范围

- 删除 `OutputPortSpec.allowed_input_usages` 及相关枚举、字段校验和目录编译规则；
- 删除 core、通用科学、曲线、论文图、TCAD、InGaAs 及测试插件中的所有生产者用途清单；
- 将 Root 的生产输出解析器收敛为精确生产合同解析器；
- 在 Artifact 标签生成和 Agent 输出登记处统一保护探索/内部输出的不可 claim 属性；
- 删除目录编译器中一段已被前置审批执行器校验和 `ApprovalContract.issue()` 完全覆盖的重复校验，
  编译器保持唯一且缩至 734 行，没有提高既有 738 行复杂度上限。

## 6. 已执行验证

聚焦回归：

```text
pytest -q \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_l3_review_and_human_policy.py
36 passed in 2.98s
```

M6-C 分组回归此前分别通过 64、57 和 46 项；最终以 7 GiB 虚拟内存上限串行运行完整测试：

```text
pytest -q
255 passed in 111.03s
```

同时通过：

- `python -m compileall -q src plugins tests`；
- 生产源码和插件中已删除字段、旧用途变量及旧解析器名称零命中；
- `git diff --check`；
- 当前生产规模脚本确认目录编译器 734 行。

首次全量回归暴露一条旧 ABI10 目录摘要金丝雀以及目录行数门。处理方式不是恢复字段或放宽门：更新
ABI11 的精确摘要，并删除重复编译期校验；随后重新执行完整回归全绿。

## 7. 未实施内容

- 未修改 Approval 或 M6-B 资格语义；
- 未删除精确 reviewer、revision、change request、current 或来源身份校验；
- 未新增全局用途图、跨插件依赖表或调度阶段；
- M6-D 的 Effect 自动审批请求尚未实施，M7 尚未放行。
