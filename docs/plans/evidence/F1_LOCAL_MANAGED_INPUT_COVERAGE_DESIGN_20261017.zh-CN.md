# F1 Local 受管输入覆盖：最小候选设计

状态：root 条件设计 PASS，按下列边界授权实施；本页仍为设计，代码须另行独审，测试未运行。承接 `e770b62` 的 native 子链及 [F1原设计](F1_MANAGED_INPUT_PROVENANCE_DESIGN_20261017.zh-CN.md)。

## 原件与软边界

现有 accepted 已冻结 `source_script/prepared/script`、`experiment_directory/entry/snapshot_files`、argv、cwd、scope/native_attempt/interface；Records.accept 保留 `source.py` 和每个 `inputs/<name>`，history 共同验证实际 terminal 和归档原件。缺的是“这些明确输入属于哪个已冻结来源/当前作者”的合同。不能按同 hash、文件名或目录位置自动发现外源，不能把任意 shell/库/argv 隐含读取说成已跟踪。

与 native compiler 一致，**显式当前 job 的 `experiments/<name>/` 目录快照是一个受管 authoring 包**：其中新 script、helper 和生成材料由当前 W 的已封存 native participants 负责，保守继承全部 job 来源与已声明贡献；这不是证明 W 从未 copy 未声明外源。现有 `--experiment-dir` 表达该作者动作，不增加模型字段、手填来源表或新 CLI。精确命中 job 已冻结原件/只读副本的输入按原 source 绑定解释，不能被路径归入当前作者。外部目录、无合同旧 call、单 script 加未快照 cwd、opaque 继续 unknown；任意未声明的 shell 外读仍在软边界外，不声称恶意同 UID 防御。

## 唯一合同与实际接线

1. **可选能力，不硬编码 executor。** 默认 Local 经原 registration 声明一个窄 `AdapterCapability`：`managed_input_sources`（source-provenance 类，冻结声明“current-job explicit experiment-directory snapshot authoring / exact bound input copies / declared inputs only”），并提供接受时的纯输入视图。无该能力/方法不解释来源；第三方若实际继承并声明同能力，则按其自身被冻结的同合同处理，不能笼统声称继承类均无此能力。不建另一个 registry，不扩科学输出 schema。
2. **调用前绑定。** experiments.dispatch 从已加载 adapter 冻结该可选声明（完整原内容及 key/schema/version/hash）到原 accepted metadata，不接受 operator/W 自报；metadata 的 source 字段仍由可信 adapter 构造。Local factory 复用已有非 JSON `RuntimePluginContext.frozen_execution_interface`，核原 host projection、job/native-intent、scope/attempt后为 authoring 包生成窄 binding。freeze 探测占位接口不可发表该 binding；接口缺失保持无覆盖，不影响普通实验可运行。实际 helper 自动加入 Local code_assets，不扫描全依赖树。
3. **每件快照有确切归属。** source helper 对原 `snapshot_files` 单次处理并校验已保留副本：源 path 精确命中 job global/direct_material 的原件或该 job 的显式读副本时，验证 exact producer seal/material 与其 producer 确实位于原 source edges，不按 hash 选择。其余文件只有在本次显式、canonical、位于当前 job `experiments/<name>/` 的 authoring 包中，且 entry/全清单/job/native-intent/config 均被 host 绑定，才归本 W；非该范围没有默认归属。符号链接/路径逃逸/快照缺项或改字节拒绝；原 authored 文件之后继续编辑不改变已保留原件，不依赖重开其当前路径来改写历史。
4. **既有 coverage 与作者遍历。** history 仅在 frozen 可选合同下消费该纯 adapter 视图，仍先共同校验 known_success/known_failed；unknown/not_submitted 不能 complete。新 marker 只冻结 accepted/config/intent/清单的 exact 对照，以及实际输入已有 producer 的贡献引用；不建第二来源图。qualification 继续原 job 全输入 restriction 三态。**formal_review.authors 不能只看 source 有边**：对实际命中的 direct_material，即使未 selected，也把已验证 exact producer/material 加入现有 selected/compiled 的 contributions 遍历；只追加实际输入，不扫全部 direct_refs/祖先。当前 W authoring 用自身 participants，不造自递归；global/user 原文不凭此创造 native 作者。
5. **只读不升级。** 接受时由实际 adapter 产出并冻结规范输入视图；历史读取只消费该已归档视图，核原 marker、实际 retained input bytes 和原 source/author关系，绝不重新调用 adapter 生成事实或构造可能有副作用的 adapter。旧无 contract/marker 的 accepted/provenance 不回填或重签。Local 不引入 HMAC/key/预算/授权/执行新门禁。未声明来源限制的输入仍 unknown、restricted 支配，作者已知不等于 source clear。

## 文件与最小验收

候选生产：`local_experiments.py`（能力、现有 factory context/metadata、纯 view）、`experiments.py`（仅可选 contract 冻入现有 accepted）、`execution_inputs.py`（精确输入归属原语）、`history.py`（同 owner capture/readonly消费）、`formal_review.py`（仅 authors 既有遍历加实际输入贡献）。qualification 现有 coverage 消费可复用，若需改其形状先报告，不自行扩大。共享区只在 root 排定提交/owner 后编辑。

复用现有 Local/正式作者小 fixture，最少一条真实 local 进程：有已知 native 作者的 W authoring 包，读明确 bound 科学输入，受管 run→共同 terminal→新成果 seal→正式 request/独立资格；在同链断 actual direct input producer 即使未 selected 也包含在作者集合。用两三个小变体/既有负控证明未知限制不清、restricted 支配、外部目录/缺合同/错 producer/快照改动不得完整、旧 proof 字节不变。请求文件只写科学内容/文件关系，不让模型填原件ID/hash/ref。禁止新安装/模型/solver矩阵，具体最小目标在代码冻结后交 root 唯一串行运行。

设计不表示已完成 Local/F1。若现有快照无法证明某个 origin/作者绑定，保留 unknown 并报告缺口；不靠重述路径、同 hash 或降低作者门槛补齐。本文仅静态阅读，未测试/import/安装/模型/SSH/业务进程或 Git。
