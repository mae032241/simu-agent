# F1 受管输入/作者覆盖：独立设计审查

结论：**精确 TCAD/native compiler 子范围设计 PASS；未实施、未验收，完整 F1 仍未关闭。** 审查对象为 `F1_MANAGED_INPUT_PROVENANCE_DESIGN_20261017.zh-CN.md`，并静态对照 history、execution_authority、execution_inputs、qualification、formal_review 的现有 owner 接口；不含并行 review 动作修复。

## 可实施边界

- history 继续唯一消费已验证 accepted/observation/retirement，只给覆盖证明，不新增一份 contributors/producer edges。证明 exact payload 和 compiler slots/author_input 已被本job既有 selected/compiled 的递归边覆盖；qualification 保留原restriction算法，authors保留原贡献遍历。qualification 不另写 accepted/TCAD parser。没有 call 时保原成本，不重扫实例，不复制祖先。
- authority 的新增纯身份抽取只能核原 signed receipt/request/allocation/accepted 的精确 call/scope/attempt/interface/target/payload/producer 关系；不能调用整个 `_validate_binding` 重新进入当前 job 的 `_validate_inputs`、`require_review`、`q.status/output_status`，否则产生当前封存/来源/审查循环。历史事实不因当下额度/expiry 失效而消失；该 helper 也不授新的准入。
- compiler/slot 仍由 `verify_compilation/resolve_native_original` 核 exact reviewed package、全部 slots 和 author_input 贡献，并证明既有源边已穷尽覆盖。仅路径在work下、相同hash、成功状态或模型声明都不足以认定来源；新author文件按已有 host compiler 原件绑定归属。不另保存或遍历第二份贡献DAG。
- 作者覆盖完整性与来源限制三态独立：已知作者但限制unknown可做身份独立review，执行gate仍拒绝；未证明全部贡献者不能获独立资格。restricted仍支配unknown；外部observer存在额外未闭合输入时，不能因native包完整就清掉它。
- 旧无projection输出proof按原格式只读核对，不回填、重写或动态派生新形状而误判旧sha。原local/opaque/外源无合同仍unknown，这些剩余F1不能随本子节点标完成。

## 最小证伪与退出

延长现有native compile/review/run小链至真实terminal observation后的新成果、再request/资格及原输入准入，复用共同validator；同链负控覆盖同hash错producer、遗漏slot/未声明输入、缺participant。限制unknown与身份已知的分离用另一合法未执行subject证明，不能伪造一个原gate本应禁止的成功call。

这足以验证声明输入表面，不证明任意solver/native外读、真实平台身份或恶意Worker隔离。设计应先冻结并由root授权后实施；如原accepted不能支持精确关系，回报缺口，不增加新服务、授权/余额库或假receipt。本审查者未运行测试/import/业务CLI/安装/模型，未修改生产或Git。
