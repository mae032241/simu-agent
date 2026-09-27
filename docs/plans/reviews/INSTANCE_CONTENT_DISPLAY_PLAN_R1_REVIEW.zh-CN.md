# 科研内容展示修复计划 R1 独立工程审查

日期：2026-09-15。结论：**PASS，P0/P1/P2 及对应 P4 可以实施；未发现必须阻断这部分工作的计划缺陷。** P3 正文翻译明确暂缓，不以缺少翻译服务阻断本轮，也不把固定标签中文化记为正文中文阅读完成。

审查对象：[INSTANCE_RESEARCH_CONTENT_DISPLAY_REPAIR_PLAN.zh-CN.md](../INSTANCE_RESEARCH_CONTENT_DISPLAY_REPAIR_PLAN.zh-CN.md)，以 §9 为执行范围。基线为 HEAD `da220ce31c8cc9f9a60542a018b279e2f331f4c0` 上当前包含大量未提交改动的工作树；本审查未将 HEAD 单独视为已部署状态，未撤销任何原有工作。

## 阻断问题

无。计划已经覆盖两个真实缺口、精确原件关联、历史资料容错、审批读取范围和实际浏览验收；可在已列文件内实现，无需新科学 Operation、Worker 字段、翻译表或科研准入变更。下面的约束是现有计划的必要实现解释，不能在实现时省略后仍报告完成。

## 源码核对与实施要求

### 1. 参数续页必须贯穿原件读取与展示，不能只分页当前数组

`read_model._presentation_view` 对单字段保留 24 KiB 前缀，整件受 `MAX_PAYLOAD_BYTES` 约束；`general_science_views._proposals`、`_foundation` 和 TCAD 提供者有 128 行/项限制；`presentation.build_presentation` 再施加 128 参数与 192 KiB 预算；`presentation_render.render_presentation` 最后在约 26 KiB HTML 后停止。这些是多个独立裁切点。

最小可行方案是：节点保留少量参数预览，提供对应确切原件的参数页入口；参数页从经授权的原始 JSON 选择本页记录，再产生展示行。它不依赖被截断的节点 projection，不必提高全局预览预算，也不必展开所有祖先。以原件、原字段路径、原变量/案例索引形成稳定游标或位置，原 JSON Pointer 必须保持原索引，不得将页内第 0 项错误链接至原数组第 0 项。

现有 `view_models.select_json` 只在选中值超过 64 KiB 时返回子项导航，小值时忽略分页位置而返回整体；它也不会按“变量 × 案例取值”展开参数行。可复用其授权与原件入口，但不能直接把它当成参数分页实现。总条数须来自完整、有界的所选原件参数集合；页面数值明确区分总数、本页数与当前/历史范围。若原件超过既有读取上限、未知格式或单行过长，显示具体缺口及完整原件入口，不冒充已枚举全部参数。

P4 应覆盖：原参数字段超过 24 KiB、超过 128 行、多个变量各含多个案例、首条特别长、第二页与末页、嵌套 reviewed package。主节点即使拿到空前缀，也应有原件参数入口；否则“零行预览”仍可能让后页不可达。

### 2. 记录出处、科学分类与引用解析分别表达

`presentation.parameter` 默认把缺少科学分类映射为“来源未记录/是否默认未知”，`citation` 只识别 `web_snapshot`，`presentation_render._sources` 又对空引用给出统一缺失说明。`_proposals` 已保留变量、取值、案例、理由的确切定位，却没有科学分类字段。P1 针对这些默认值的修复是直接且必要的。

对照变量行应说明“实验计划取值”并指向原变量、案例取值和理由；这表示记录出处，不表示文献实测事实。显式 `tool_default` 等值可如实映射；缺失字段不能推出默认值。`source_type` 未识别时保留原类型，不用“网络检索”覆盖其他来源。新说明若进入纯展示对象，同步更新 `_validate_output` 的允许字段与原件引用检查；不修改科学 Schema。

TCAD `_claim_rows` 当前在整个已读 cohort 中匹配来源目录，并以文本 `requirement_set_key` 匹配要求集；该 cohort 包含多条父链和 supersedes 历史。必须先限制为所选参数记录确切依赖，再匹配键。即使整个 cohort 中只有一条相同 source_key，也不能把来自另一记录分支的目录当成正确引用。多个可达候选、依赖读取超限与实际空引用要分别说明。

`_project_rows` 目前未解析 `approved_parameter_key`。实现时先定位该项目实际绑定的参数集，再匹配该键；不能先在整个 cohort 找同名参数，或借最新参数集补齐旧项目。保留实现值与原批准值的区别，不由 UI 判定两值等价。纯展示提供者可使用已有 provenance/父引用；需要额外读取时由 read_model 完成，不能把 service 或文件读取权限传给 provider。

### 3. 同调用查询只是候选集，清单身份才决定图卡

`mcp_root_operation_routes._transform_output_family` 使用实例绑定的 request_fingerprint、操作标签、完整有序 parent_refs，并检查成员标签冲突；随后调用当前编译目录和科学家族验证。因此计划明确不复用此函数读取历史图件是正确的。

`figure_digitization` 已在清单 `provenance.output_artifacts` 保存每个 data_item 的 collection、sha256、bytes、media_type；系列自身保存 data_item 与 point_count。`operation_transforms` 将文件按顺序变为端口内容，原注册标签主要是端口和序号。最小关联路径应为：

1. 确认当前原件在该实例的确切绑定及保存的调用指纹。
2. 只读查询同实例、artifact namespace、同 request_fingerprint 的候选，核对保存的 operation_id/version/digest、调用指纹、transform 标识及完整有序父引用；不检查当前编译科学合同。
3. 在该已确认候选集中，以清单保存的 collection/端口、sha256、bytes、media_type 对应原件元数据；由清单 data_item 解释 CSV 与两类图件用途。不能以 `_001/_002` 或当前文件排序推测身份。
4. 对重复绑定到同一完整 ArtifactRef 可去重；对不同原件的重复成员、身份冲突、清单信息不足明确显示歧义，不选第一项。达到查询预算且仍有后页时，不能把已看过的一项宣称为唯一；记录未完成关联，并保留原件入口。

`scheduler_bindings.binding_page` 当前只支持实例游标，没有 fingerprint 过滤。计划允许的有界只读查询足够；应明确稳定排序、分页游标及跨实例隔离。只增加查询不需要更改绑定写入、幂等或登记规则。

图证 provider 可解释清单，read_model 负责候选授权及元数据。`presentation.build_presentation` 当前过滤输入字段，且图件输出仅允许 artifact_id/label/source 三项；若需要图卡元数据，应只扩展必需的纯展示字段并继续验证每项精确来源。不要把 metadata 过滤导致的数据缺失通过允许任意 provider 输出来解决。

### 4. 审批 token 不能借兄弟发现扩大范围

`app._handle_evidence` 已区分实例浏览与 review token，`approval_artifact_reference` 仅沿冻结 subjects 的 parent/supersedes 来源读取。只把 siblings 加进普通节点上下文是可行的；切勿直接放入共用 `_lineage_views` 后让 approval_context 自动获得它们。

审批页面若展示家族，只能与原 token 已授权集合取交集，并在图片、CSV 下载、参数续页各入口再次执行相同的审批授权。先保证范围，再构造页面；不能先暴露未授权成员名称/清单内容，再指望图片 GET 返回 403。没有权限的兄弟不是损坏科研证据，不应影响原决定表单。

P4 的负例必须包含：同实例、同调用、确有已登记兄弟，但它不是冻结审批 subjects 的可达来源；review 页面与下载/图片/参数页都不得读取它，普通实例浏览可按原权限读取。原 subject 的可见图件保持可读，审批写入身份和允许选项保持不变。

### 5. 历史容错和交付范围

已有数值重绘 PNG 直接展示即可，无需重新画图或跑提取。只有 identity-fidelity 原图叠点时如实标注并记录 numeric redraw 缺口；点数与轴信息注明来自保存清单，不由 UI 重新作科学认证。新 provider 应直接读取历史 JSON 的可用字段，不调用 `FigureEvidenceManifest.model_validate_json` 或完整家族验证阻断旧记录。

仅 provider 的 `scidiscovery.instance_views` entry point 是本轮插件扩展，现有 Operation/Root/Worker 合同应完全不变。源码可读取不证明 wheel 中 entry point 能发现；串行隔离安装和插件移除负例仍必要。新图证区需实际加载图像，CSV 下载以注册字节散列核对，后续参数页实际点击可达。真实实例只浏览，待审批表单使用隔离状态；不改真实科学记录或作决定。

## 审查边界与完成状态

本次只阅读计划、现场诊断与上述源码，未运行测试、构建、浏览器、服务或科研 MCP，未修改生产代码。只新增本报告。部分探索命令遇到不存在的候选文件路径，已通过实际文件继续定位；未将其当成功证据。

本结论是计划可实施性通过，不是实现、性能、浏览效果或现场验收通过。后续独立实现复审应以冻结工作树为基线检查精确 diff，核验以上源身份、分页和权限负例，再分别记录 P1/P2 的实际完成状态；P3 保持暂缓。
