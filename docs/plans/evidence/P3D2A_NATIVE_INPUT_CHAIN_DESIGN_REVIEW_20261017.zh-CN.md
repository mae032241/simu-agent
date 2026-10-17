# P3d2-a 精确 native 输入链设计独审

结论：**设计 PASS；三个串行小节点仍须分别实施独审，不代表非空输入已经可运行。** 对象为 `P3D2A_NATIVE_INPUT_CHAIN_DESIGN_20261017.zh-CN.md` 当前含离线 capability 配置入口的版本；基线 P2d `7effe2f`，P3d1 尚在另一 owner 实施。本审只静态核对设计、既有 author/packager/materializer 与 formal-review 作者入口；没有测试、项目 import、构建、安装、模型或远端执行。

## 认可的最小链

1. 现有 W 可选 compile 接收科学 author 文档及 slot→已公开输入 alias；host 仅解析本 job 已 bound 的唯一 sealed material。模型不抄内部 hash/object ID/ref，alias 不是任意本地文件权限。
2. 诚实新增 v3 `NativeOriginalRef` / `NativeExecutionPackage`，保留原 v2 Artifact 语义。不能内部伪造 ArtifactRef 转 v2；project/capability/slot 校验与捕获编译逻辑抽成一份纯实现，远端仍是原 TCADJobSpec/project.tar 协议。
3. compiler 输出进入原 W artifacts，host proof 先落原件再发布，随同原 material seal 绑定。实际 compiler/helpers、author 文档、slot 原 producer/member、capability 与输出字节均不可替换。普通 HWA 结果 JSON 不加机械字段，不新增任务、包库或状态账。
4. 正式 review subject、compiler 输出及后继 run payload 必须是同一 sealed material/source；不允许 pass 后重编译。作者链补入已验证 compiler 引用的全部 slot producer 贡献，含只有 direct_materials 而无旧 selected_inputs 的贡献；不把任意父节点都推为作者。缺实际身份继续 unsupported。
5. P3a 继续继承 compiler job 已绑定来源，restricted/unknown 不能因新 package 或 compiler proof 洗清。唯一 loader 核 instance、producer seal/job/result/raw、唯一 member、字节/size、canonical source 及其属于原 compiler job 绑定输入。P2b callbacks 只沿此原件，继续 slot/path/media/hash/size/cache/quota 检查，不扫工作区或近似匹配。

## 独审提出的入口缺口已补齐

原文只有“宿主提供离线 SolverCapabilitySnapshot 文件”，未明确从产品配置进入。最终设计补为 `tcad_execution:tcad` 可选 operator 字段 `implementation_compilation.capability_snapshot_path`，独立严格 TCADCompilationConfig；无配置 unavailable，W 无自选 snapshot path 参数，不做 RPC。

snapshot 纳入 wrapper code_assets 与 target configuration-file proofs，经现有 configure/freeze/load 固定 path/hash/size；compiler 保存同一原字节/proof，可选能力合同同时绑定 schema/snapshot，seal/review/run 再核。不仅记一个路径。离线 snapshot 仅为待审编译输入，实际 active capability/policy 仍在 P3d provider/gate 独立验证。

## 实施审查与最少证伪

按 typed-ref/纯 compiler、现有 W 编译/封存、可信 gate/回调三个节点串行交接共享文件，P3d1 未提交前不改其工作树。每个未完成节点保持明确 blocked，不能把类型/helper 完成称为真实闭环。

少量负控分别证伪：未绑定/歧义 alias 被打开、同 hash 异 producer 或异 instance 被冒认；slot/path/类型/字节/显式 quota 校验丢失；compiler/helper/author/snapshot/输出变化却继承旧 proof/review；来源或共同作者遗漏；真实现有 review→后继 run→P2b 所读原件改变。v2 canonical 回归使用固定旧字节/合同依据，不能由新 serializer 同时生成 expected 与 actual 自证。可信 fake provider 不证明远端能力或执行通过。

media_type 明确是 slot 的科学类型声明并冻结，当前无独立 MIME 鉴定，不能写成按字节已鉴别。旧 debug/result_analysis 等可选消费者未支持 v3 就明确 unavailable，不借此迁整套旧框架。

本报告不审 P3d1 实现、长时间 pending 后原 call 恢复、真实原生身份、生产 TCAD、跨 boot 或归档。设计 PASS 不替代这些节点，也不授权动态验证或安装矩阵。

## 同次主计划状态核对

仅附带阅读 `THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md` 本轮单文件 diff：新增 P2d `7effe2f`、P3c `309cf67`、P4c 纯 I/O `b01e636` 的已提交状态与相应独审一致；能力表已区分实际已有中间层与未接通的资源/非空输入、通用 UI、归档包。P3d1/d2 未完和 P4c2 尚未通过均明确，未宣称动态验收。此状态同步 PASS，不重新评审未改段落中的历史实验结果。
