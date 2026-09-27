# R4-D-A 审批视图设计独立审查

状态：独立审查完成  
范围：`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 第 7 节、当前 Operation 编译/调用链、审批服务、执行授权、参数资格和固定 UI 安全边界  
方法：跨边界审查、单一权威审查、插件生命周期审查、最小复杂度审查

## 结论

**打回，不允许进入 R4-D-B。**

方向本身成立：人工审批适合成为一种没有科学输出、没有 Worker、没有执行状态的
`OperationSpec executor.kind="approval"`；这比再建审批注册表更符合单一目录，也比生成占位
Artifact 更诚实。`ReviewDocument` 只保存指向冻结 subject 的声明、历史查看不再执行插件代码，
同样是正确的收缩方向。三个公开科学审批 Operation 的数量也不需要继续增加：一个通用证据资格、
参数正常通过和参数例外通过，已经是最小可解释集合。

但第 7 节尚未闭合“审批产生者身份进入下游准入”这一关键边。现有准入只验证审批种类、选择项和
subject 成员关系；即使新请求保存了 operation digest，只保存而不消费也不能阻止旧审批、通用入口
或另一插件的同名审批成为资格。参数最终审批束还遗漏 extraction primary，且“复用现有 source
closure”会把当前错误的全等规则一并迁走。另有 projector 信任边界、固定文档的二进制/集合与资源
上限、执行启动再次校验编译身份三处未冻结。它们都直接关系最小授权和 fail-closed，不是可留到编码
时自由决定的细节。

## 审查判断

| 审查点 | 判断 | 依据 |
| --- | --- | --- |
| `approval` executor 是否必要 | 通过方向 | 最终审批消费多个既有 Operation 的不可变结果，不能自然附着到其中一个 producer；独立审批注册表会形成第二权威，transform 占位输出会伪造科学对象。无输出的 approval executor 复用输入、guard、limits、ReviewSpec 和唯一 catalog，是更小模型。 |
| `ReviewDocument` 总体协议 | 方向正确、合同未闭合 | 指针式声明和创建时冻结可支持插件卸载后的历史审计，也能消除领域 HTML renderer；但当前设计没有冻结非 JSON subject、展示类型、集合顺序、总 subject/文档上限和转义规则。 |
| 三个通用科学审批 Operation | 数量合适、参数合同不完整 | pass/exception 分开避免运行时改写选项；但两个参数 Operation 都漏掉最终 extraction primary，不能承接已冻结的完整参数 review bundle。 |
| 参数特判迁出 Root | 可以迁出，但不得原样复用 | projector 的受控输入足以完成目标一致、coverage 重算、父链、audit checks 和 handoff 校验；当前 Root 的 source catalog 全等检查本身与“允许 metadata-only catalog 条目”的合同冲突。 |
| 通用审批与 execution fallback | 未闭合 | 阻止新 `scientific_foundation` 走通用入口是必要的，但只封入口不封资格消费者仍可旁路；execution 创建端去 fallback 后，启动端也必须核对同一 compiled contract。 |
| 三视图 | 通过 | public/support/internal 仍是同一 compiled catalog 的投影；审批 Operation 放 public、support 只保留机械变换，不需要第二注册表。 |
| 总体目标 | 暂未偏离，但需先修边界 | 方案保留多角色文件通信，把人类决定留在控制面，把领域展示/校验放入插件组件；以下修复不需要新增状态机、领域路由或 UI registry。 |

## 阻塞 1：审批合同身份只被记录，没有成为下游资格条件

第 7.2 节计划在 `ApprovalRequest` 保存 operation id/version/digest 和 approval contract digest，
但第 7.3 节没有规定输入端口如何声明并校验允许的审批产生者。当前实现仍然是：

- `InputPortSpec` 只有 `approval_kind` 和 `accepted_approval_options`，没有审批 Operation 身份；
- `_validate_operation_input_cohorts` 把这两个值交给
  `ApprovalService.are_subjects_approved`；
- `are_subjects_approved` 只检查 request kind、decision option 以及所需 refs 是否出现在同一决定中，
  不检查 request 的 operation/contract 身份；
- readiness 和临时 legacy schedule 还直接用 `is_subject_approved` 判断单个 foundation。

因此，“新请求写完整身份”本身没有准入效果。旧 foundation-only 请求、通用入口曾创建的请求，或
另一插件创建的相同 kind/option 请求仍可能满足新任务。完整 cohort 只在请求创建时校验也不够，
除非下游能证明决定确实来自那个校验过完整 cohort 的 compiled approval Operation。

### 最小修复

1. 在唯一 `OperationSpec` 输入准入合同中声明允许的 approval Operation，例如一个有界的
   `accepted_approval_operations`；编译器必须把这些 id 解析为同一 catalog 中 `public + approval`
   Operation，并冻结其 version、operation digest 和 approval contract digest。参数 cohort 允许精确
   引用 pass/exception 两个 provider；不得在 Root 另建 allowlist。
2. `ApprovalRequest`、不可变指纹和决定校验保存完整 compiled identity；通用资格查询除 kind/option/
   同一决定外，还必须匹配输入合同接受的 provider identity。历史缺身份或合同 digest 不匹配的决定
   只可审计，不为新调用提供资格。
3. readiness、Operation cohort、剩余两个 legacy bridge 都调用同一个 provider-aware 资格查询；删除
   foundation 单对象的旧 `is_subject_approved` 资格语义。通用 `approval_request_create` 禁止创建新的
   科学资格请求，但不再承担“靠 kind 名字保护所有准入”的职责。
4. 保留“同一完整审批决定覆盖所有被消费 cohort 成员”的检查。审批请求可以包含 extraction primary
   和 frozen sources 等额外 subject；完整性由精确 provider 在创建时保证，下游不应自行重演领域
   Schema 分支。

## 阻塞 2：参数审批 Operation 没有承接完整冻结 cohort，source closure 规则也写错了继承方向

已冻结的完整科学审批束至少包含 final foundation、final extraction primary、全部附件、全部冻结来源、
deterministic coverage/validation 和 final independent audit。第 7.3 节两个参数审批 Operation 的输入
列出了 foundation、requirements、parameters、catalog、coverage、audit 和 frozen sources，却遗漏
了 extraction primary。

同时，当前 Root 参数特判要求参数观测使用的 source keys 与 catalog source keys 全等。这个规则会
拒绝合法的 metadata-only catalog 条目；这类条目可以说明来源存在和缺失状态，但不能被伪装成定量
观测。第 7.3 节笼统写“复用现有 source closure”，会把这个错误一并迁入插件。

### 最小修复

1. 给 pass/exception 两个参数 approval Operation 都增加恰好一个 `extraction_primary` 输入，并把它
   纳入 subject 顺序、完整请求指纹、audit lineage 校验和 ReviewDocument。
2. 明确 source closure 为：每个参数 observation 的 source key 必须存在于 catalog；catalog 可以多出
   明确标记为 metadata-only/无观测的条目，这些条目不得贡献参数值、coverage 或独立来源计数；
   audit 必须按其合同覆盖完整 catalog，并绑定审批中的全部 frozen sources。
3. 不应机械要求 audit 直接 parent 整个审批束。它必须直接绑定其实际审查过的 extraction primary、
   参数附件、coverage 和 frozen sources；foundation 与 extraction/来源的关系由冻结 lineage 校验。
   否则会为满足审批而要求 reviewer 声称读取未实际消费的对象。

无需增加第四个审批 Operation，也无需新增 QualificationReceipt 或专用参数状态机。

## 阻塞 3：projector 的“拿不到目录和网络”不是当前进程内插件模型能够提供的保证

第 7.2 节把 projector 描述为拿不到数据库、目录和网络。前半句只有在“没有把 service/DB handle
作为参数传入”时成立；后半句不成立。当前插件组件是启动时导入、在控制进程内直接调用的 Python
callable。窄 subject snapshot 可以限制正式 API 和数据依赖，却不能阻止代码自行 import 文件系统或
网络模块。

这不会否定 projector 方案，因为安装插件本来就是受信任的控制面扩展；但把接口收窄误写成硬沙箱，
会产生无法通过测试兑现的权限声明。

### 最小修复

1. 明确 projector 是“受信任、启动时编译的插件控制组件”；窄快照是 API/authority 最小化，不是
   进程隔离。它不得接收 ArtifactService、TaskService、ApprovalService、数据库连接或可写路径。
2. 本阶段只测试参数对象和返回类型的能力边界，不声称可证明无文件系统/网络访问。若未来允许不受
   信任插件，再单独引入进程沙箱；不得为 R4-D 增加这套复杂度。
3. 编译规则要明确：`executor.kind="approval"` 的 executor component 按现有 `projector` component
   kind 解析，并且与 `ReviewSpec.approval.projector` 是同一个精确引用；不要新增一种重复的
   `approval_projector` 组件注册类型。

## 阻塞 4：固定文档尚未定义足以覆盖 PDF/图像/TCAD 包和集合的最小安全合同

当前 UI 已有严格 CSP、`nosniff` 和 attachment 下载，这些基础可以复用。但第 7.2 节把每个 item 都
描述为 subject index + JSON Pointer，没有定义二进制 subject 如何展示，也没有冻结集合展开顺序。
科学证据会包含 PDF、图像、表格附件，TCAD 审批会包含工程包；若一律要求 JSON Pointer，这些对象
无法进入文档；若实现时临时加入 URL/HTML，又会重新打开 XSS 和插件 renderer 缝隙。

Approval/ReviewManifest 当前最多 256 subjects。一个 approval Operation 的多个 collection 展平后
可能超过该值；若编译期和 preflight 不共同限制，会在请求创建末端才失败。文档本身也需要有界，
否则受信插件的错误输出仍可造成页面资源放大。

### 最小修复

冻结一个无需领域分支的最小协议：

1. item 仅允许固定枚举，例如 `json_value`、`json_table`、`status`、`subject_metadata`、`download`；
   JSON 类型必须使用能解析且存在的 RFC 6901 pointer；二进制只能使用 subject metadata/安全下载，
   不允许插件 URL、data URI、富文本、HTML 或 inline media source。
2. subject 顺序唯一规定为 approval contract 的 `subject_ports` 顺序，collection 内保持调用绑定顺序；
   ReviewDocument 只能引用这个冻结序号，不能重排或注入未绑定 subject。
3. 编译期验证各 subject port 的 `max_items` 总和不超过 256；preflight 对实际展开数、单项/总字节、
   sections、items、label/description 长度和 document 总字节再次有界失败。
4. 核心渲染器对插件文字和解析出的值统一 HTML escape；继续保持 CSP、`nosniff`、固定 attachment
   disposition 和完整 raw tree。文档只保存指针声明，不复制科学值；插件卸载后由请求内冻结文档和
   subjects 完整重放，绝不重新调用 projector。

## 阻塞 5：execution 创建端关闭 fallback 后，启动端仍需验证同一合同身份

第 7.3 节正确要求：没有当前 compiled operation identity/approval contract 的新执行请求不能新建
审批，旧 fallback 只能历史只读。但当前 `ExecutionService.authorize` 只验证审批 kind、授权 option
和 `(request_ref, payload_ref)` 精确 subject，没有验证审批请求保存的 compiled identity 与
ExecutionRequest labels 是否一致。

仅修改 `execution_approval_request_create` 不足以证明 `execution_start` 消费的是由同一个 compiled
Effect contract 生成的授权；旧的已决定 fallback 也仍可能被拿来启动。

### 最小修复

1. 新 execution approval 的不可变请求保存 Effect operation id/version/digest 和 approval contract
   digest，projector 文档也进入同一创建指纹。
2. `execution_start/authorize` 再次比较决定对应 ApprovalRequest 的完整 compiled identity、精确两个
   subjects 与 ExecutionRequest 的冻结 labels；缺身份、漂移或插件缺失均失败关闭。
3. 无 compiled identity 的历史请求和决定只能查看，不可新授权、重提或启动。增加“旧已决定 fallback
   仍不能 start”的负例，而不只测试“不能 create”。

## 通过 R4-D-A 复审所需的最小文档返工

只需在第 7 节冻结以下五项，不需要提前写生产代码：

1. provider-aware 的审批资格合同及其唯一 catalog 编译方式；
2. 参数 approval 输入补齐 extraction primary，并更正 metadata-only source closure；
3. projector 是受信进程内组件、窄 API 而非硬沙箱；
4. ReviewDocument 的 JSON/二进制类型、稳定集合顺序、256 subject 与文档资源上限；
5. execution 从审批创建到 `execution_start` 的同一 compiled identity 复核。

返工后应先做第二轮只读设计复审。上述修复都能在现有 Operation catalog、ApprovalService 和固定 UI
内完成，不要求第二注册表、新状态机、领域 UI 分支或额外科学实体，因此仍契合轻控制面、最小授权、
通专分离、多角色文件通信和“everything is operation”的重构目标。
