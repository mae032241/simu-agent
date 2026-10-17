# P3d2-a：科学文件到精确 TCAD package 的最小接线

状态：**设计独审 PASS，尚未实施。** [独立设计审查](P3D2A_NATIVE_INPUT_CHAIN_DESIGN_REVIEW_20261017.zh-CN.md)。P2d 已提交 `7effe2f`；P3d1 正由另一 owner 实施。本节点在其提交后串行接共享文件，不修改当前 gate/预算工作树。依据[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)、[已审 TCAD seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)第 4 节及[P2/P3 拆分](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)。本文不授予生产资格。

## 一条实际可达的链

1. H/W 沿现有任务产出科学文件；当前 W 阅读现有冻结输入。TCAD 可选工具接收 `ScientificDeckImplementation` 文件，以及 `scientific_files={slot_name: input_alias}`。alias 是任务已经公开的科学文件名/输入路径；不要求模型填写内部 object ID、hash、producer、storage 或 ArtifactRef。host 仅在当前 job 的冻结输入表中做精确对应；缺失、同名歧义、未封存或越出绑定返回修复信息，不搜索“最近”、同 hash 或磁盘相似路径。
2. 工具纯本地生成 package，将其放入该 W 的 `artifacts/`，保留不可变 compiler proof。复用现有节点封存，将 package 作为正常 material，并把 compiler proof 绑定到同一 seal；无新任务/Root、无 prepare/upload/RPC，也不 reserve。
3. 普通 A 通过现有科学选择选中这份 package，要求现有 `formal_review`。独立 A 的正式 subject **就是 package 的 sealed material**，不是另写的一份科学说明。作者/助手及所有 slot 来源贡献都沿已封存原件排除；身份缺失仍 unsupported。
4. 后继 W 已有任务携带该 exact package 与正式 qualification。`experiments run --payload` 消费 subject 的原始 source，继续现有 call/Records。d1 gate 验证原 review、compiler proof、来源与授权；trusted provider 再核 active capability/policy。P2b callbacks 读取该 package 原先冻结的 slot originals。**review 后不重编译、不换包、不用同 hash 的另一份材料继承资格。**

编译是 TCAD 的可选功能，不成为普通 HWA 必经阶段。已有空输入/普通任务不因此扩 schema 或增加新 review 要求。

## 精确合同与最小新原件

| 接缝 | 候选精确责任 |
| --- | --- |
| 输入选择 | `scientific_files` 仅包含科学 slot→公开输入 alias。host 用当前 job 已冻结的 `direct_materials/selected_inputs` 精确解析其唯一原 material、producer job/result/seal；复用现有 `selected_inputs`、`qualification._inputs` 的原件条件及 explicit quota。公开 alias 是选择关系，不是可自由打开的文件路径。 |
| native ref | 新 `NativeOriginalRef`：`instance_id`、`producer_step`、完整 `producer_seal` proof、`material_path`、`sha256`、`size_bytes`；均由 host 生成。新 `NativeResolvedProjectInput` 保留 `semantic_name/target_relative_path/media_type/size_bytes`，使用 `original`，不包含/伪造 ArtifactRef。source 路径只能从该 producer seal 的唯一完整 material 行取回，不能由 ref 提交一个替代物理路径。 |
| package | 独立 `NativeExecutionPackage`（v3），与 v2 共用 project/capability/slot 的纯字段校验。v2 模型、默认字段、canonical bytes 和旧 Artifact 入口保持；v3 绝不先伪造 ArtifactRef 转 v2。materialize/package 的共享 identity accessor 只分别取已验证的 v2 Artifact sha 或 v3 native sha。远端仍收到原 `TCADJobSpec`、job.json/project.tar，无 native-ref 远端协议迁移。 |
| compiler | 复用旧 `experiment_capability.prepare` 中 scientific author→control capture/project 的纯逻辑，抽成一份小函数，不搬 ExperimentTools/ArtifactService。`compile_native_implementation(authored, *, capability, resolved_inputs) -> bytes` 只接受 host 已解析输入。宿主提供一个明确冻结的离线 `SolverCapabilitySnapshot` 文件；它只是待审编译输入，不能证明当前远端 active 或授权。缺快照 unavailable，不绕 gate 查询远端。 |
| compiler proof | 当前 W host record 保存不可变 proof：job/native-intent、author 文档原件、slot alias→完整 native refs、离线 capability proof、实际 compiler/共享 helpers 的冻结 registration/code/contract、输出 descriptor。host 先保存原件再发布输出；重复相同绑定幂等，修改需新输出，不覆盖旧原件。proof 不写预算/科学状态。 |
| node seal | 在现有 material seal 加可选 host 字段 `compiled_implementations`，仅绑定输出 material 与 compiler proof；普通 HWA 最终 JSON不加字段。seal/validate 必须重验实际输出及 compiler/helper 身份。compiler 选用的来源必须已在 producer job 绑定，继续现有 provenance 的限制传播；不能靠 compiler proof 洗掉 restricted/unknown。 |
| 正式作者/独审 | 复用 `formal_review.authors/_subject/require_review`。仅给作者遍历补读已验证 compiler proof 的确切 source producer 贡献；它们即使只在 `direct_materials`、没有旧 `selected_inputs`，也不能被遗漏。原 native author/helper 参与者仍由既有真实身份链提供，不接受作者自填。review subject、compiler output、后继 run payload 必须指同一 sealed material/source。 |
| P2b resolver | 唯一 loader `resolve_native_original(root, ref, *, compiler_binding)` 校验 instance、精确 producer seal/job/result/raw、唯一 material membership、声明 size/hash、canonical regular source，以及它属于原 compiler job 的冻结输入。`input_metadata(item)` 返回该已冻结绑定的 size/media；`open_input(item)` 打开同一 source。P2b 继续检查 slot/path/hash/media/size、cache 重验、显式 storage quota 和安全目录。 |

native material seal 目前没有独立 MIME 鉴定。v3 `media_type` 是原 scientific slot 的明确类型声明，compiler proof 将它与该原件冻结；slot/resolved/callback 必须一致，不声称已经从文件字节独立识别 MIME。若未来要求独立媒体证明，应另立明确合同，不能静默猜测。

### 离线 capability 的实际配置入口

仅 `tcad_execution:tcad` 的 operator configuration 增加可选 `implementation_compilation={"capability_snapshot_path":"/absolute/operator/file.json"}`。由插件独立严格 `TCADCompilationConfig` 解析，绝对 canonical regular file、无 symlink；不向旧 `TCADRuntimeConfig` 增加默认字段。缺该项时 compile/schema 功能 unavailable，既有 v2 执行语义不变。W 的 CLI 没有 capability path 或自选 snapshot 参数。

`build_managed_runtime` 仅接受该已声明插件字段并保留原 transport 解析；wrapper 的 `code_assets()` 及 `target.configuration_files` 在配置存在时加入这份 snapshot。现有 `experiments.configure → freeze` 把其实际 path/hash/size 纳入已冻结 interface，`load → freeze` 在每次消费时核同一原件；原件变化不能继续旧配置。compiler 从这项冻结配置读取并严格解析 `SolverCapabilitySnapshot`，将原 snapshot 字节及其同一 proof 保留在 compiler 原件组，不只保存路径。可选编译 capability 的合同同时绑定该 snapshot 身份与纯 author schema；它不发 RPC。后续 node seal、formal review 消费和 run 的 compiler verifier 都核该同一 proof；d1 provider 仍独立验证 target 上实际 active profile/capability 与 policy。

## 文件责任与实施拆分

在 d1 提交并设计 PASS 后再按顺序实施；每个节点可独审，未全部收口前非空 native 输入继续 blocked。

1. **typed ref 与纯 compiler**：插件 `project_packager.py`，候选小模块 `native_implementation.py`；旧 `experiment_capability.py` 仅调用共享纯 compiler。两底层 adapter 支持明确 v3 preparation profile、共享物理 package 路径；不改远端 job/retire 协议。原 v2 serializer 不变；不扩旧 result_analysis/debug 等消费者支持 v3，这些可选功能若收到 v3 明确 unavailable。
2. **现有任务中的可选编译入口与封存**：候选 `research_loop/execution_inputs.py` 持有原件解析/proof 校验；`experiments.py` 仅经现有注册 adapter 的冻结可选 `AdapterCapability` 调用 `compile_implementation`，缺方法 unavailable。CLI 候选 `compile --implementation <author-file> --scientific-files <slot-alias-json> --output artifacts/<name>.json`；没有授权/remote 开关。`contracts.py` 仅 capture/validate 可选 compiler proof，`formal_review.py` 仅复用作者遍历核贡献。当前入口限制于已有受控 W；H 继续供科学文件/选择，不新增 H 执行权限。
3. **消费同一原件**：`managed_execution.py`/trusted factory 消费 d1 的单一 HostServices 注入；d1 provider 在既有 review/source/authority 检查顺序内验证 v3 compiler 绑定，再交原 policy/admission 校验。native callbacks 由上述同一 loader 提供；不新 resolver registry、package 库或授权/预算池。`execution_authority.py` 仍只接受原 sealed reviewed payload；`budget.py` 继续唯一 reserve/settle/release owner，不由本节点写余额。

新模块名/极窄共享段在独审后固定。与 d1 owner 串行交接 `experiments.py`、`managed_execution.py` 和 HostServices；不改其现有未提交段。必要 native prompt 仅告知可选工具入口，不扩普通 HWA 输出字段。自动发现、通用缓存、旧 Artifact 库迁移、展示/归档优先工作均不在本节点。

## 最小负控与未验收

写入已有小 fixture 的定向负控，不新增 Root/安装环境：①未知/歧义/unbound alias 不编译；同 hash 不同 producer、换 instance/源路径/字节均拒绝；②少/多 slot、类型/size/hash/quota 仍拒绝；③换 compiler/helper、author/capability/包字节后不能保留旧 proof/review，遗漏来源贡献或 restricted/unknown 不执行；④既有正式 review subject=生成 package，existing run 使用同一 source，P2b 返回该 slot 原件；无 gate/快照/能力、非空旧 Artifact 无映射仍 blocked；⑤v2 canonical/legacy 适配与原远端 job spec 的兼容小断言，v2 用固定旧字节/旧合同为预期，不由新 serializer 生成两端自证。只保留能证伪这条链的用例，不做笛卡尔积。

本文仅文本与已知函数定位；无 pytest/collect、项目导入、CLI/进程、构建、安装、模型或 solver 执行。真实 capability/远端 TCAD、平台作者身份、跨 boot 与完整原生闭环尚未动态验收。设计或 fixture PASS 均不替代主计划的生产资格。
