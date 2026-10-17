# P3a 来源限制独立静态审查

## 结论与精确范围

**静态代码审查 PASS**。基线 `c925873`，仅限 P3a 来源事实与传播基础；不代表 P3b 正式独审、P3c 执行授权、P3d 预算门禁或真实 TCAD 准备/上传已获准。

审查者独立于实施者，只读文本与 Git 差异，未执行测试、测试收集、模块导入、CLI、构建、安装、模型或远端操作。受审生产为新增 `operations/provenance_rules.py`、`research_loop/qualification.py`，以及 `research_loop/{controller,cli,contracts}.py` 和旧 `artifact_agent/service/reference_proofs.py` 的窄差异；测试只读新增 `tests/research_loop/test_source_qualification.py`。补读现有输入选择、history 观察验证与工程修复来源接口，未全审旧 Artifact 服务、全部测试或所有候选交付路径。

已核对[实施记录](P3A_SOURCE_RESTRICTIONS_IMPLEMENTATION_20261017.zh-CN.md)的最终八文件范围及九个定向测试函数；最后增量为观察原件窄核验、单次声明 memo、direct ref 的原 producer raw hash 对照和零 call 用例，均已静态补读。同期 P2b 差异不在本报告范围内。

## 设计信任边界

最终设计采用现有操作者 prepare/CLI 配置边界，替代早期的私有 retain_original setter 设想。`--source-restrictions` 是明确的来源限制声明，不是来源语义的密码学认证，不授科学合格、独立审查或执行权限。任意 shell 能改宿主原件的情形仍属现有软隔离限制，不宣称与操作者认证等价。

`clear` 仅指框架声明/冻结输入成果链在此范围内没有来源限制。它不证明 native 任意外部读取已封闭。实际 bound 叶缺声明为 unknown；不会为保证范围以外的任意潜在读取伪造永久 unknown 输入。普通科研 build/seal 不因 unknown/restricted 阻断；后续需要资格的消费者须明确 fail closed，本节点不伪造该门禁已完成。

## 精确调用链与身份

| 检查 | 静态证据 |
| --- | --- |
| 可信入口与精确原件 | `controller.py:100` 与 `cli.py:137` 接 prepare 操作者配置。`qualification.source_configuration:65` 限定绝对 canonical regular 路径、声明 sha、clear/restricted，拒绝重复、目录/链接别名、public_root 之外且非明确 global 的来源。模型结果没有 setter 或入口。 |
| 声明冻结及 global 映射 | `freeze_sources:92` 仅复制明确声明的原件，冻结声明 ref 到 settings；objective/updates 原路径显式对应已冻结 global 副本，未按相同 sha 推断同源。public_root 不扫描全树。 |
| 唯一事实 owner | `provenance_rules.py:4` 的 dependency_sources 将 None 解释为全部冻结输入，显式空仅可由受信适配器确认；新薄路径不读取模型推导标签。三态 restricted 支配 unknown；没有新增 SQL、CAS、独立状态账或授权账。旧 reference_proofs 仅复用依赖选择原语，保留原恢复命名空间与历史 all-input fallback。 |
| 直接边与原 producer | `qualification._inputs:123` 只封存 global/明确 public 声明、直接 parent、明确 selected origin、repair/closeout 的 producer ref。直接结论 sha 与原 producer 一致；材料须是精确 producer seal 成员，同 path 改身份拒绝，缺/歧义映为 unknown。没有把历史阅读 view 当来源事实，也不复制祖先清单。 |
| 保守传播 | `_restriction:179` 按需沿直接 ref 验证 job/raw/result/来源原件；访问中环为 unknown，合法构造本身要求 preceding step。缺历史来源 receipt 为 unknown。每次求值复用 memo；模型自写 clear/review 字符串不参与来源事实。 |
| 输出身份 | `_output:236` 封存 job/raw/result、当前 materials canonical 摘要、input ref 和观察原件 ref。所有本任务输出自动继承全部冻结输入；`output_status:285` 校验精确 sealed subject 与材料成员，不能用别处相同字节冒充此 producer 原件。 |
| 兼容与公开视图 | `contracts.py:717` 不给旧 retained job 补写新字段；`:783` 校验冻结输入状态，`:939` 为新输出附来源原件。science_view 仅给紧凑状态/直接输入数/scope，不提供祖先、宿主路径或声明原件。 |

### 本轮指出并修复的两项

1. 初稿输出来源原件未绑定 materials：仅换材料而保留 raw/result 时，新增来源 proof 无法发现。最终以当前列表的确定性摘要绑定，未复制材料树或祖先，新增针对该差异的负控。
2. 为区分空观察，初稿 `_output` 调用 history.validate_observation，会在来源递归时重复校验全部执行原件/日志。最终只校验既有 `host-history/observations/<step>.json` 的确切路径和 sha，再读 managed_calls 是否存在；没有再解析 accepted 或重哈希 native logs。完整执行观察校验仍由既有 contracts/history 路径负责。

## 负控能证伪什么

- `test_operator_clear_is_not_inferred_for_an_identical_undeclared_original`：若实现按 sha 合并不同原件，声明过的 objective 会错误清除同字节未声明 update，该用例将失败。
- `test_restricted_automatic_outputs_and_copies_cannot_clear_their_sources`：真实 build/seal/copy 链若丢 restricted、信任结果 prose 的 clear/review 字样、遗漏 output_status 的原件成员验证或公开视图泄露 ref，会失败。fixture 直接准备 native 成功原件，只用于进入来源封存路径，不证明真实模型执行或结论正确。
- `test_clear_is_scoped_and_missing_material_edges_remain_unknown` 与纯规则用例：若把缺边当 clear、把 unknown 布尔化、让 unknown 覆盖 restricted，明确的字面预期会失败。缺边用例直接构造来源规则输入，不能称完整科研调度负控。
- `test_changed_host_receipt_is_an_identity_error_not_clearance`：若来源原件被改后仍接受其新 clear，实际 q.status 将错误通过。
- `test_output_proof_binds_materials_even_with_unchanged_scientific_json`：只改材料身份且 raw/result 不变，验证新 proof 对应此次真实遗漏，不是随生产常量生成预期。
- `test_undeclared_ordinary_science_still_seals_and_legacy_status_is_unknown`：若没有声明就错误阻断普通科研或默认 clear，会失败；其 legacy 检查是缺字段 status 分支，不冒称完整历史实例升级验收。
- `test_zero_call_registered_capture_does_not_invent_unknown_inputs`：真实 local prepare 和零调用 W 封存若仅因存在观察 ref 就错误增加 unknown，该用例会失败。其 discovery fixture 仅提供源码入口元数据，无安装、构建、真实执行或伪造 managed 成功回执。
- `test_cli_freezes_declared_public_source_and_rejects_alias_paths`：真实 CLI→prepare 接线若不冻结声明原件、容许 symlink 别名、错误 sha 或重复声明，会失败。没有真实 launcher、安装或外部付费执行。

上述测试仅已静态阅读，未执行；不是运行通过记录。未要求为每个状态/路径重复整套进程测试或安装矩阵。

## 尚未覆盖与保守限制

实际 managed call 的额外输入及外部 history observer 来源，本节点尚无可信完整来源适配契约，成果明确标 `observation_input_provenance_unsupported`、unknown；已知 restricted 仍支配该 unknown。空 registered capture 不凭观察 ref 本身新增 unknown。本轮未平行解析 accepted 或猜测 work 源码依赖来制造 clear。

未动态验证 source receipts 的文件系统竞争、长链性能、跨恢复/closeout 全链；未逐个执行歧义/循环/legacy producer 场景，不能用静态分支代替运行证据。全量原件 JSON 仍需要内存，不称流式化或 OOM 修复。正式独审身份、可信执行授权入口、预算消费和真实 TCAD gate 均留给各自节点，不能凭本报告启用真实 prepare/upload。
