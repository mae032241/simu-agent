# F1 可信受管输入与作者覆盖：最小设计

状态：候选设计，待独审；未实施、未运行测试。范围承接[功能复审 F1](THIN_FUNCTIONAL_REAUDIT_20261017.zh-CN.md)及[已审 native 输入链](P3D2A_NATIVE_INPUT_CHAIN_DESIGN_20261017.zh-CN.md)，不改变原迁移计划的真实平台资格限制。

## 已确认缺口与退出边界

`qualification._output` 将任意非空 managed_calls 一律变成 `observation_input_provenance_unsupported`；`formal_review.authors` 再以任意 missing_reason 否定作者完整性。来源限制未知与贡献者未知被混成一个事实。只删除作者门槛会错误授独立资格；只保门槛则已冻结的 native inputs 永远无法用于“执行后产生新成果→再审→再执行”。

本节点只接通 **已有 exact sealed compiler 的 TCAD/native 包**。复用原请求、accepted、观察、compiler/producer seal，解析范围仅是框架声明的科学输入及 native 作者贡献，不承诺观察任意 native/solver 外读。local 外源、opaque、旧无 compiler/可信输入证据、外部 history_observer 仍 unknown；不按同 hash、目录归属、完成状态或 W 自报推断来源，不新增通用输入 parser、科学 schema、源注册库或授权流程。

## 单一原件链与最小函数边界

1. **history 仍是观察原件 owner。** 在 `managed_calls/validate_managed` 现有校验之后，增加窄纯函数 `managed_input_coverage(root, job, rows)`；仅派生每 call `{call_id, accepted_ref, compiler_ref, complete, missing_reason}`。不添加 producer edges 或另一套贡献图。accepted 的 scope/native_attempt/interface、prepared 及 observation/retirement 仍走原共同验证器；不在 qualification 重写 accepted/TCAD/manifest 解析。该函数没有 RPC、clock/reserve 或副作用。
2. **execution_authority 只提原绑定关系。** 增加同 owner 只读 `accepted_input_subject(root, job, accepted)`：从已有 `accepted.execution_authority` 原 receipt，核同 call/scope/native attempt/interface、原 signed request/allocation、payload_alias、target、accepted/script/prepared 及 exact subject producer seal/material。复用原签名与身份比较，抽取无当前时效依赖的纯关系校验；不调用整个 `_validate_binding`、`_selected_subject/_remaining` 或 require_review/q.output_status/q.status，以免重进当前来源/审查。不续授权、不以过期或余额抹掉历史事实。缺可信绑定返回 unsupported/unknown，矛盾或改字节明确拒绝；不能接受同 hash 替代路径。
3. **execution_inputs 只证明已有边覆盖。** `execution_input_coverage(root, job, subject)` 先要求 exact payload/subject material 位于本 job 已冻结的 selected_inputs（不能只命中同 hash），且其 producer seal/result 均相同；再找该 producer seal 中唯一同 material 的 compiler，复用 `verify_compilation/resolve_native_original` 核 compiler implementation/helpers/capability/author 及全部 inputs。原 selected producer 的既有 `formal_review.authors` 递归已包含 compiler 所有 slot producer 和 author_input；原 qualification input-provenance 也须确实覆盖这些 producer（仅检查原已绑定边及 compiler job，不补新边，缺边仍 unknown）。完整性只说明本 call 的声明输入未超出这些已有边。当前 W authored 文件仅在现有 host compiler 已冻结 author snapshot、job/native_intent/config 且 author_input 分类有效时归属该 compiler job，不凭 work 路径认作者。无 compiler 或未闭合保持 unknown。绝不调用 `for_payload/_selected_subject` 回溯当前 qualification：它们包含准入逻辑会造成环；这里只读已冻结原件，执行入口原 resolved_inputs 全等检查不动。
4. **两种消费分开。** qualification 的已有 output provenance 可选绑定 coverage 与原 observation ref；complete 时仅表示无需附加一份 unsupported unknown，最终 restriction 仍由原 job input-provenance 递归计算，restricted 支配 unknown，不能把 unknown 清成 clear。formal_review.authors 以 coverage 判断是否穷尽输入，再继续原 selected/compiled 作者遍历，不新增贡献递归；限制 unknown 本身不使已证明的作者集合不完整。reviewer participants 仍只取 reviewer 自身。缺覆盖仍拒 formal request；已知作者但限制 unknown 可独立 review，执行 gate 仍拒新副作用。

新字段仅为既有 host provenance 的可选覆盖投影，不新增公开 schema/version。旧封存没有它时保留旧 unknown，不改原件、不回填，不让新 `_output/validate_outputs` 形状误报旧字节被篡改。`not_submitted` 不是完成观察或来源 clear；只按同一覆盖证据判断。外部 history_observer 的额外输入仍 unknown，不能被完整 native 包覆盖掉。无 call/无 observer 的成本不变；本节点 rows 单次投影、局部 producer/compiler memo，不每 call 扫实例。完整只读核验仍有原件 hash/递归 DAG 成本，不能宣称零 IO；local/opaque 的 F1 剩余问题不因本节点关闭。

## 文件与最少证伪链

候选生产仅 `history.py`、`execution_authority.py`、`execution_inputs.py`、`qualification.py`、`formal_review.py`；若原 accepted→subject 关系或既有来源边不足则先报告，不补一套边/预算/CLI/transport/receipt。helper 归原自动 code proof；缺 pin 仅补既有列表。两处消费共享 coverage，不各写来源算法。

复用 `test_native_execution_inputs.py` 的现有 injected-backend 控制链与正式作者 fixture，最少三组：

- 将 compile→seal→review→run 延长到真实小 terminal observation→新 W 成果 seal→正式 request/独立 qualification，并继续用同 exact package/inputs 准入；后端和 native session 身份仍为可信合成，未验真实 TCAD/平台独立性。
- 在同链原件边界替换同 hash 错 producer/少一 slot/未声明外源，要求拒原件矛盾或贡献 incomplete，不得新 prepare/submit；restricted 仍支配，Local/opaque 缺合同继续 unknown。复用既有负控，不扩矩阵。
- 单独以已知 exact producer/完整 native 作者、未声明限制的科学输入证明：review 可请求，restriction 仍 unknown，执行资格拒绝；不为造这个分支伪造一次应被 gate 禁止的成功执行。另保缺 native participant 时作者仍 incomplete 的原负控。

本页仅静态设计，未执行项目、测试、安装、模型、solver、SSH 或 Git。待两项当前小修提交、设计独审通过和 owner 确认后实施；设计 PASS 不代表闭环代码或生产资格已验收。
