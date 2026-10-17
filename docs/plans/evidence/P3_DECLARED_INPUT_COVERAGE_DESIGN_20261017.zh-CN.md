# P3：opaque 与 observer 声明来源闭合（窄设计）

状态：root 与独立评审已批准本节边界；代码、动态验收另记。

## 接缝

复用 `managed_input_sources` 可选能力、原 accepted 和 observation，不建第二来源库或贡献 DAG。
保留 Local 原合同，增加小的“全部框架声明输入与贡献”合同。来源只可指向本 job
已冻结的 global、精确 producer material、明确的当前作者，或 unknown；核验复用
`resolve_native_original`、现 source edges 和 native authors。相同 hash 不选择来源。

TCAD 实际 adapter 对 canonical V2 做真实包校验：零 slots、零 resolved inputs，
已准备的 archive inventory 必须等于嵌入 files；其唯一科学输入绑定原 gate 的
精确 reviewed package。首次沿已有 authority 验签，读时仅复核封存关系。
V3 保留原 compiler 路径；非空 V2、缺合同、额外未覆盖科学输入仍 unknown。

observer 由 prepare 可选冻结可信合同、adapter/config 与实现；本次 response 的独立
source view 明确 complete 才可消费。原展示 `coverage.status` 从不授来源资格。
明确空列表只在此合同范围内有意义。host 绑定 job/raw/配置，模型不填身份字段。
新 source view 保存在原 observation，读取不再次运行 adapter，不补升旧原件。

qualification 与 formal review 消费同一验证结果，实际 producer 贡献进入原 authors
遍历，不把普通 parent 当作者，不复制祖先。未知不授资格，restricted 仍支配 unknown；
普通科学封存不因可选能力缺失而失败。

## 范围与验证

来源保证仅覆盖框架声明/冻结链。不能据此证明任意 solver/native 外读封闭、科学正确、
身份完整或执行获准；不另写 TCAD DSL 依赖分析器。宿主配置与可信 adapter 仍是软信任边界。

实现范围：`execution_inputs.py`、`experiments.py`、`history.py`、`qualification.py`、
`formal_review.py`，TCAD `managed_execution.py`，少量真实封存正负控及本节点实施账。
不改科学输出 schema、预算、UI 或 checkpoint 恢复。只做静态 AST/text 检查；
测试由 root 冻结后唯一串行运行，当前不得声称动态通过。
