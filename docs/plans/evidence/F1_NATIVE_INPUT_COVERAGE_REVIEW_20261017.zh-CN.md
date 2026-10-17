# F1 精确 native 覆盖：独立实施审查

范围：五生产 owner（history、execution_authority、execution_inputs、qualification、formal_review）、既有native input测试及实施账七文件。仅关闭exact sealed native/compiler子范围；local/opaque/外部observer及真实平台资格仍未关闭。

## 初审判断与保护

共同validate_managed后仅known_success/known_failed可发布complete；unknown/not_submitted capture保持incomplete，read也拒其完整投影。原retirement不被当科学观察，F2 blocked封存语义保持。

原accepted→原HMAC授权/决定→request/allocation/native intent/interface/target→exact subject→唯一compiler→既有selected/source edges的关系均静态追过。首次publication验原签名；已有sealed projection只读核原refs/关系，不索当前key、不重签或重新生成coverage。没有进入当前_remaining/_selected_subject/_validate_binding/q.status/review准入循环；没有RPC、预算grant或新贡献DAG。

旧provenance缺marker走旧_output形状；seal_outputs既有path只读取原marker并_save一致核验，不为旧proof回填clear。complete只取消附加unsupported unknown，原restriction递归不变；作者覆盖与来源三态分开。recent review选择/路由未改。

科学字节浏览和archive-inspect不调用该资格重验。该重验仍依赖原live路径及外部code/capability_source；alias/prepared/script/native intent等位于原归档roots，但包内blob核验不等于脱原路径的qualification加载。首次capture有局部compiler memo；最终只读增量也按exact compiler ref+material在单次调用去重，未增加持久缓存，其他完整hash仍保留，不承诺硬实时或零IO。

最小4个source目标覆盖：真实非空native执行终态后新成果→再review/资格→后继run；已知作者/unknown限制允许review但在RPC前拒执行；原unbound alias/author race；原same-hash错origin/instance/package篡改。合成transport/native identity只提供可信依赖，不把它们当真实TCAD或平台资格。

## 首批实际失败与修复边界

root 首批 `.trial/review_reserve_followup_20261017/f1-source/batch-001/pytest.log` 为2 passed/2 failed，2.92秒。新seal_outputs错误将history观察receipt `{path,sha256}` 送入qualification三字段ref读取器；`q._check`正确拒其形状。两新用例在原W首次封存即失败，未到本次长链；测试中另有同一错误读法。初审静态未发现这个跨owner合同错配，必须如实保留生产回归。

已定点复核最终增量：history owner抽取其原validate_observation的scope/path/hash/raw binding读取段，保formal/unconfigured原None语义；seal_outputs/测试消费合法owner reader，原完整managed/proofs验证保留。q._check、receipt形状不变、未伪造size，coverage仍只走一次共同完整校验。相邻新增读取的accepted/request/allocation/decision/native-intent/compiler/source-provenance均按各原三字段ref，无同类错配。静态PASS，可只复测两新增失败项；尚不声明动态通过。

审查者仅文本/调用链/Git只读与限定空白检查，未运行测试、收集、项目import、安装、模型、业务CLI或Git写入。

## 第二批失败：测试选错确切被审材料

root 第二批 `f1-source-retest/batch-001/pytest.log` 为1 passed/1 failed；unknown来源与已知作者分离用例已通过。主链到W6封存、A7请求和review8通过，W10执行revised包返回unresolved。

独立静态确认：`contracts.py:542-549`将managed日志/manifest也作为材料加入并按path排序；`history.py:582-604`据此编号，`experiments/…`排在`revised-package.json`前。因此原硬编码W006-I001实际选择日志，review8并未审查revised包。`execution_authority.py:451-464`拒绝未获精确review的另一包，符合合同；不是本次生产准入失效。

已定点复核最终测试修正：以既有implementation_options和resolve_implementation在A7冻结history中选唯一exact revised material，分别断request与qualification的subject.material等于该原件，并在A9复核同ID解析；不重述排序算法、不改backend或生产门禁。保留queued严格断言并附完整返回诊断。静态PASS，仅需root复测这个失败项；尚未把修正后主链记为通过。

## 最终有限验收：PASS

已只读核对三个目录 `f1-source`、`f1-source-retest`、`f1-chain-retest` 的 result.json、resource.json 与 pytest.log：结果依次为2通过/2失败、1通过/1失败、单项1通过；最终单项 pytest 14.82秒、监督15.14秒、峰值84,176,896 B。合计4个独立目标、7次执行、监督30.286秒，三批最大84,332,544 B（约80.43MiB），全部cleanup_complete=true、memory_stop_triggers及received_signals为空，均未启用address-space硬限制。先通过目标没有重复跑，不能表述为最终HEAD全部4项重跑。

最终成功主链实际覆盖原非空native输入执行终态→W6新成果封存→精确revised包独立审查→W10后继run，并完成删除operator key后live只读资格重核/原封存字节不变。另一个新增目标保留unknown限制、允许已知作者接受审查、拒绝实际执行；两个既有错来源/绑定/竞态负控保持通过。首批生产reader错误及第二批测试错选对象均保留为失败记录。

当前实施账、迁移主计划和plans/README状态一致：仅精确native/compiler子范围有限PASS。Local、opaque、外部observer的额外来源/贡献覆盖仍未闭合；合成身份/后端不证明真实平台独立性或TCAD科学资格，不证明任意外读封闭，也不提供可迁移/离线归档资格。P1–P5未整体完成。未发现需要阻止本节点提交的剩余问题；无需增加重复验收。审查者未执行任何测试或业务运行，仅核root产生的原始证据。
