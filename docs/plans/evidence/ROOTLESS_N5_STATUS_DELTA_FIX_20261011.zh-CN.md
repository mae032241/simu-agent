# N5：科学角色判断与控制绑定分工（协议 7）

状态：统一修订已通过独立审查及定向门禁；提交前未启动新模型、未修改真实试跑实例，原场恢复另记。

本记录已并入并取代此前仅处理“同状态空操作”的未发布协议7小修方案；新协议7只有下述统一分工，不再要求角色填写机械引用字段。

真实协议 6 的 A007 已正常完成模型输出，但重述旧 m1 `screened` 时引用历史索引，封存被证据门槛拒绝。这不是新的科学状态变化。控制层应从封存原件重建旧状态，模型无需重新维护它。

## 已统一的机械交接边界

- `search_review.dispositions` 只声明本轮变化；遗漏保留旧机制状态。
- 已知机制的同状态重述是空操作。原模型输出完整保留，但其新 reason/evidence 不替换旧依据，也不提供新的机制状态资格。此规则包括同状态 `pending`。
- 新协议 A 只填机制身份、状态、理由与下一科学动作，不填 disposition.evidence 或 repair_source。首次或重新授予 `screened` 由 host 绑定冻结 direct_refs 中唯一同机制、action=`screen` 的 W；同状态重述不覆写旧理由和依据。
- H/A 的 repair 由 host 精确匹配同机制直接 W/root；缺失或歧义保留 H/A 科学结论，阻止后续 W 启动，不按最近节点猜。
- A 的 progress_assessment 只填 verdict。Host 仅绑定实际路由的直接前一任务（W、analyze H，或确切返回 A 的 E），以原 raw 身份去重。这证明被评任务归属，不证明它支持科学主张；没有确切来源时计为 unknown。正文科学依据、负结果与限制仍由角色判断。
- H/W/A/E 的 implementation_selection 为必填 nullable 科学选择：null 承接当前任务已有选中集合，[] 清空，ID 列表替换。可读对象 ID 只映射唯一封存材料；索引仅显示前16项，余项沿 implementation_index/next_page 按需读，每页最多16项且受既有字节限制，第17项不会失去选择资格。Host 沿精确直接前驱搬运少量选中原件，不合并全部祖先，不从推荐、最高分或正文猜实现。
- 新协议不要求 #reuse-implementation、文件路径或哈希交接。普通 Markdown 坏链接不阻止整份科学结论封存；只保留最多16项有界 unresolved_links 与遗漏数，不伪称可用。显式非法实现 ID、原件或输入完整性失败仍拒绝。
- 索引页仅作导航；真实材料/结论的按需入口由 host 提供。E 的原始文献 locator、普通正文科学引用保留。没有新增状态账本或放宽原 managed 目录、regular、SHA、实例及字节边界。

## 兼容与证据

新协议 7 的四角色 schema、science-view 和 native prompt 同步上述责任。协议 1–6 的 schema 与视图原字节保持；既有任务按其冻结协议重建。真实协议6 A007 不修改。

无模型夹具重现四机制的 A007：既可重述 m1/m2、仅新增 m4 并选择 m3，也可省略全部旧状态只报 m4。原科学输出及旧 reason 保持原字节。负例覆盖首次引用索引、伪造 job view、同机制非 screen W、变化空证据/篡改页、pending 重开后 A-only 再授 screened，以及索引不能提供 N4 progress。

此前同状态小修的独立证据保存在 `.trial/n5-status-delta-20261011/`（140 passed /70.80s、文案相关3 passed /1.42s）；该快照没有发布。统一修订的失败分类、最终门禁、独立 wheel 和原 A007 完整只读验证另存 `.trial/n5-mechanical-free-20261011/`，不能用旧安装快照代表本次源码。

统一修订完整 rootless 门禁为 245 passed /90.96s。预审随后发现首16个对象的永久选择上限；仅历史分页与新增三条夹具作增量修复，再跑新交接与历史边界集合，55 passed /10.47s（含第17项成功选中、缺页与损坏页拒封存）。没有重复扩大旧平台测试。此前18项失败全部先卡在旧本地 fake 输出未适配新必填字段；默认协议7入口已修正并保留，新旧普通坏链接行为分别测试，没有把全部夹具固定到旧协议。

最终独立 wheel 完成 H/W/A/H/E/H/W/A 八节点真实 CLI 假进程：一次科学 ID 选择、null 跨角色承接、精确只读输入、普通坏链接、用户暂停/继续与不重放均通过，记录80假用量，0模型。安装模块 SHA 与五生产源文件完全一致。

同一 wheel 对真实 A007 完整核验 science_payload、旧协议 schema、native 原身份、冻结输入、search 与 correction；未封存、未继续、未增加预算。隔离命名空间将独立临时副本挂到原绝对路径后，`build_job` 返回原 job 且 job/task/schema/raw 原字节保持。真实3198文件前后 SHA 一致。最终 wheel SHA 为 `4c587b991c49eefda877360c1488fc57ceb6427eaafe3ffde876262bfe5d8e5e`，结果在 `installed-result.json`。

此前小修的直接换目录副本因原绝对材料路径失败、首个命名空间因 `/tmp` 只读失败的日志保留，未修改生产代码规避。源码、diff 与门禁清单在 `source-freeze.json`；本次独立审查 PASS；原场是否恢复及结果另行记录，不由测试通过自动推定。

独立审查报告保存在本地 `.trial/n5-mechanical-free-20261011/independent-review.md`，审查冻结源码与安装包一致；仅状态文字在通过后同步。
