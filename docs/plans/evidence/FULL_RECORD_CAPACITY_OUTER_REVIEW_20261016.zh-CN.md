# 完整记录容量：外侧独立扫描（2026-10-16）

## 最终结论

**root 外侧、历史/恢复、执行/交付三个节点均为有限工程 PASS。** 本轮独审指出的残留容量门槛及旧 schema 续接 P2 已修正，无未处置阻断。结论对应基线 `4c074ad` 上本轮冻结差异，不表示全项目不存在其他缺陷，也不宣称重新运行真实模型/solver 或重写旧真实场。

独立审查读取生产差异、原始 pytest/resource、冻结 SHA 与安装身份；没有改实现、运行重复测试或提交。以下按时间保留初扫与中间失败记录，其中“待补/待验收”状态由本节和末尾最终证据取代。

| 节点 | 独审重点 | 结论 |
| --- | --- | --- |
| root 外侧 | 完整 evidence/metadata、schema、owner/cache、archive inventory、workspace、waiting/continuation 原件；真实性和显式额度保留 | PASS |
| 历史/恢复 | >256KB snapshot 的 25 call/context/candidate 关联、完整 checkpoint/历史重读、有界视图、默认/显式 quota、精确旧 schema 兼容 | PASS |
| 执行/交付 | 完整输入/stdio/descriptor、独立 observer、151 对象目录交付与篡改确认、同候选 unavailable 去重及不同候选负控 | PASS |

基线 `4c074ad7f7e41608d397f7e6135fbdc4720d92ec`。只读扫描 core Artifact/MCP、plugin runtime、launcher、runner、collection、归档与恢复链；research_loop 两执行者负责的差异待冻结后另审。未改源码、未启动模型或 solver、未运行完整回归。以下均为**具体调用路径的代码推断**，不冒称已实测所有尺寸反例；本轮没有新的 P1 实证，列出的阻断按 P2。

根案例为完整 snapshot 297,940 bytes 被 256,000 bytes 门槛拒绝并降成 contexts=[]。这里关注同类完整记录门槛；不把资源、权限、真实性和紧凑视图限制混为一谈。行号按基线，实施中的移动不改变受审路径。

## P2 清单与责任面

| 编号 | 可达路径与问题 | 修复方向／责任面 |
| --- | --- | --- |
| E1 完整 evidence manifest | `reference_proofs.py:19-35` 的 encode_snapshot 对完整 ToolEvidenceManifest 固定1MiB；`tool_evidence.py:664` 完整 snapshot 与 `:760` material_snapshot 必经。另 `tool_evidence.py:699` 对 scientific_evidence_projection 后的完整公开 manifest 再限1MiB，raise发生在写 output/tool-evidence.json 前。大合法依赖闭包无法封存/发布，单修 private guard 不够。 | 去完整私有/公开 manifest 固定字节拒绝；持久化完整，紧凑回复另分页并保留导航。schema真实性、任务实际调用/IO配额保持；tool_evidence/reference_proofs/schema owner。 |
| E2 完整 attempt 回执 | `tool_evidence.py:396-399` 对完成回执限4096B并为塞入而删 diagnostics；`:422-423` 对实际 read_sources 回执也限4096B。ToolAttempt 合法来源集合可远大于此，工具已读却不能落完整证明/完成。 | 去落库完整回执固定字节门槛，不为视图截断正式诊断。保留每次工具输入语义、实际次数/授权校验；tool_evidence owner。 |
| E3 owner/provenance | `scientific_usage.py:127/168/299` 将 manifest 的1MiB常量复用于完整 owner、owner缓存和图 work-set；合法大 owner 即使在显式 ReferencePolicy IO预算内也失败。缓存 oversized 分支还可把可选加速失败变成 provenance 错误。 | 大 owner 走未缓存的正确读取，缓存仅淘汰；完整来源图不套显示阈值。ReferencePolicy max_file/max_unique/max_io/time 是显式读取资源预算，应保留；scientific_usage owner。 |
| E4 计算原始记录 | `schema/layered_diagnosis.py:111` 对完整 CalculationRecord canonical JSON 固定32KiB；CalculationResult/ControlledCalculationRecord继承，`analysis_artifacts.retain_calculation`及历史 controlled_calculation重读均经过。合法大计算结果被拒绝，不能由 summary=False 规避。 | 仅去完整 record byte guard；保留 computed/result/reason、算法/输入摘要和数值语义。summary/紧凑展示另限；schema＋calculation proof owner。 |
| E5 归档完整载体 | `instance_archive_records.Records.TARGET_RECORD_BYTES:354` 和 `_materialize:427` 对选中完整控制行累计32MiB拒绝；`_payload_refs:569/581` 对完整控制artifact及gzip解码限16MiB；`instance_archive_files.workspace_refs:177` 对完整 evidence/recovery manifest限16MiB。已合法写入的大实例/控制闭包无法归档。 | 完整记录和精确引用遍历解除显示型cap／流式处理，保留事务快照、所有权、路径、摘要、编码与解压资源安全。foreign异常载体保守保留策略不删；archive records/files owner。未找到 read_database 的生产调用，其16MiB不另计可达缺陷。 |
| E6 collection断点 | `execution_collection._child:478` 恢复 outputs.json 固定4MiB；同路径首次 atomic_json写入没有此限制，ingest_result仅校验输出名唯一且逐文件验证，没有对应descriptor总字节上限。大量合法descriptor写成后若在ingest前退出，重启不能读原checkpoint。 | 完整checkpoint reader去固定记录cap，保留LocalFileDescriptor验证、同execution身份、collection时间/传输预算和不重submit；execution_collection owner。 |
| E7 debug归档 | `plugins/tcad_artifact/debug_archive._json:28` 对完整ledger/receipt限1MiB，local_debug_service原ledger/receipt读写无此cap；`_inspect` 对每ledger先调用它。累计合法记录变大后返回unsupported/unowned，可阻断归档。 | 解除完整元数据读cap；保留run/instance所有权、receipt/submission hash、terminal与锁。实际文件64MiB等额度另属文件预算；TCAD archive provider owner。 |
| E8 launcher完整记录 | `scripts/acceptance/rootless_cov_launcher.regular` 默认4MiB，direct_materials/job读取、prepare_home/outer的完整job digest、main配置与native_args完整schema读取复用。core完整记录放开后，大job/schema仍启动前失败。 | 完整host control读取解除固定byte cap，保持regular/no-symlink/hash/accepted job绑定；材料32/64MiB、二进制512MiB分别是显式文件预算，不机械删；acceptance launcher owner。 |
| E9 启动记录读取 | `worker_start.write_worker_start:569` 对完整domain-workspace.json限1MiB，materializer并无相同全记录cap，足够大的合法manifest阻断worker_open_assignment；`plugin_runtime.observation.effective_timeout:69` 读完整assignment限1MiB，超过后退回 requested/unavailable，失去该辅助launcher的run deadline裁剪。 | 去完整记录读cap，保留安全文件读取与真实外层预算；startup紧凑页仍限。后者不证明突破总Run授权；worker_start／optional observation launcher owner。 |

根已收到逐项消息并承担外侧实施；本表不是修复完成或测试通过声明。不得删除旧证据或为消除失败重写旧 seal。

## 应保留、不可误修的不同约束

- MCP/Unix socket请求1MiB、response16MiB、app-server frame：明确传输边界，不是持久化记录上限。大原件应通过文件/分页访问，不能直接无限放大网络包。
- ReferencePolicy显式IO/时间、operation max_output_bytes/max_files、attachment与execution导出预算、domain算法输入点数/数据传输限制：资源授权，不能当显示门槛全删。
- UI bounded_record、审批页/下载fallback、Root output index/read pages、presentation.safe_value、curve_score启动24KiB view：可省略且能导航原件的紧凑视图；未发现仅凭这些显示失败就必须拒绝已经完整保存的科学原件。
- plugin config、secret、state marker、helper代码校验、路径/权限/摘要/身份约束不可随记录cap一并删除。原件容量放开不能将坏JSON、未知owner、篡改或未确认执行改成成功。

扫描依据是全树容量守卫索引与上述链路的调用者/读写者复核，不声称全项目已无其他缺陷。尚未独立验收实施中的 research_loop 与根外侧补丁；测试应围绕大完整记录仍封存/恢复、紧凑页仍有界、篡改/未知仍拒绝三个负控，不需要用真实模型或全量回归代替。

## 外侧补丁首轮复核（实施中，非最终 PASS）

已只读审查根代理修改的 evidence/schema、scientific_usage、archive records/files、execution_collection、worker_start、plugin runtime workspace/observation、TCAD debug_archive，以及 selection、execution_recovery、worker_delivery、managed_wait、continuation、protocol 的容量相关差异。路径、regular-file、摘要、schema、job/attempt/terminal 绑定校验没有因解除完整记录门槛被移除。ReferencePolicy 的显式文件/IO/时间额度仍在，与完整记录持久化门槛的区分符合本轮要求。

首轮反馈的三项已由根代理补正，代码复核确认：material_snapshot 不再拒绝跨历史聚合的 64 attempts/32 accesses；oversized 可选 provenance cache 退回原件冷路径；selection 的紧凑省略分支保持下游所需字段及 omitted 计数。第三项此前仅证实分支组合契约不完整，未证明普通生产 observer 的 ASCII 候选身份能触发，不作为新的实测 P2。上述修正仍需最小测试证据，当前未提前验收。

补充 E7：debug_archive 的 `_verify` 固定 64MiB 是归档自身的隐式再拒绝，并未读取实际 record.collection_limits；`MAX_ENTRIES=4096` 还作用于完整目录、ledger、跨 ledger 身份和 receipt files。DebugPolicy 的 max_runs/max_output_files 只要求正数，多个合法实例/任务也可累计超过该完整 inventory 门槛。应移除归档重复上限，保留 exact size、stream SHA、重复身份、所有权、terminal 和锁；真实执行侧 DebugPolicy、DEVELOPMENT_ARTIFACT_LIMIT_BYTES 收集/传输额度另行保留。未运行 >64MiB 真实 solver 原件反例，不能据此声称当前内置 writer 已产生该尺寸。

E8 初扫的暂定分类亦作澄清：launcher 的材料 32MiB/parent 64MiB 和 native binary 512MiB 是其内部常量，未绑定独立用户/operation 配额。当前补丁去除这些重复门槛，仍保留路径、exact size/hash 和只读挂载；未发现由此新增读取或执行权限。显式执行/收集预算、MCP/pipe 传输约束继续按各自合同保留。

本节只记录独立静态复核；未占用 serial 测试锁、未启动模型/solver，未改实现。最终冻结哈希、定向测试结果及两执行者的 history/delivery 补丁尚待合并核对。

### 后续扫描发现的剩余路径

- E4 尚有完整登记的二次门槛：`analysis_artifacts.retain_calculation` 将完整 ControlledCalculationRecord 放入 `metadata.calculation_proof`，经 `publish_analysis_file → context.accept_evidence → tool_evidence._register_tool_evidence`，仍遇 `metadata_bytes` 固定 40KiB（其他 metadata 8KiB）。去掉 CalculationRecord 32KiB 不足以让较大合法结果正式登记；应补真实 retain_calculation 的正控，保留原件/父摘要/算法语义负控。同处完整 raw 的 `min(port.max_item_bytes, 32MiB)` 也须区分 port 显式额度与内部重复门槛。
- 归档完整文件 inventory 还受 `instance_archive_files.MAX_FILES=50000`，分别作用于 `Files.add`、provider `selection.paths` 和 `cleanup_restore_stage` 的派生文件数。此处是模块常量，未找到独立实例归档配额配置；足够大的合法完整目录仍可拒绝归档/清理。此项为静态路径结论，未创建五万个文件实测。foreign 异常载体的保守引用扫描和 engineering diagnostics 的显式 retention 设置不据此删除。

上述剩余路径均已即时反馈根代理；本报告不把实施过程中的首轮结果写成最终通过。

## 外侧最终代码复核快照

当时结论：**静态审查通过，测试窄复核待补；现已由首节最终 PASS 取代。** 首轮指出的残留门槛均已修正，未发现本次外侧差异新增的权限、身份、未知执行或显式配额放行。未独立启动测试。

审查文件 SHA256 如下；此快照不替代之后改动的重新核对。

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` | `bcc264fa23199084ecbd2d5ab63cd35628ac37f9a30ca982c49ccef38235f16b` |
| `src/scidiscovery/artifact_agent/schema/tool_evidence.py` | `b0d3e9e2d711c27e366acb562b0c037625ebf9f507a85c8663c491c8d6800ec7` |
| `src/scidiscovery/artifact_agent/service/execution_collection.py` | `dae2ca07a4b1afc28677903a9ed4ae08082470a253b789acf5a17c5c88658733` |
| `src/scidiscovery/artifact_agent/service/instance_archive_files.py` | `b8f2be12819daa9d326f74543dc81e9c0a900c70ae74817a85b8f3e9b170c907` |
| `src/scidiscovery/artifact_agent/service/instance_archive_records.py` | `f424d4473353ce78d606c4de96b5ead67275ad000a872c2408862b32aed2bea0` |
| `src/scidiscovery/artifact_agent/service/reference_proofs.py` | `90bfb620d73ef3915a7f8c453228a2747d0d84b921d48636dd140bdd5b6c616d` |
| `src/scidiscovery/artifact_agent/service/scientific_usage.py` | `3144a9a4a8b22bf8aa1135d3b69eded88bcde83a74f96e94df4cde141fc073c7` |
| `src/scidiscovery/artifact_agent/service/tool_evidence.py` | `89781eeceb689047e9e856bfddb002ebfb0c9c68a1bebfe28d16aebd86966936` |
| `src/scidiscovery/artifact_agent/service/worker_start.py` | `d5ee319aab03e9d96684280e4e153bb7401a27bb443cce6d826580d2f79d1e63` |
| `src/scidiscovery/plugin_runtime/workspace.py` | `e641784503a5d945aad34c04e4808191e907554f0c4bcbd911ab1d8133288222` |
| `src/scidiscovery/plugin_runtime/observation.py` | `780b12cd33918344d3c6aa60f4eb97c0fbf2c49c2bf834fda5dcb130b83c3472` |
| `plugins/tcad_artifact/tcad_artifact/debug_archive.py` | `1f0ba3e427d3a3b86aed8312b5270df976eb919d75453097460f6900739fa9ba` |
| `src/scidiscovery/research_loop/continuation.py` | `471f0ad8a90397781a66963e5bd73f404c67dbcbc373af82a8e0e497115a4162` |
| `src/scidiscovery/research_loop/managed_wait.py` | `8e893f3fdba4dae3354179870fa7e7973627ea047720ad17bfecf34a08c17b4b` |
| `src/scidiscovery/research_loop/native.py` | `d954b1846bfd0bb38c4e133e641c126afa6a8987ad565bd39a6c85f7b38c3277` |
| `src/scidiscovery/research_loop/protocol.py` | `958ab0da56eb9e9942a7499ca735296b51c8c92bf859b2ffa0a34a55e94f939a` |
| `src/scidiscovery/research_loop/selection.py` | `41820ac2aad2af540f3d7d59249e567fcfdf6d07382a24680d305f8210ee28ab` |
| `src/scidiscovery/research_loop/worker_delivery.py` | `dd07340fb2251adce0bf82b1b0bc9e5f34ed8297da5bc088c2eba62b5b205619` |
| `src/scidiscovery/research_loop/execution_recovery.py` | `452821c10af738e691180e67d3021534b61c09c7d8df84c10455d6d2e2fd7634` |

### 合同边界与验收证据

TCAD project_packager 的 MAX_PROJECT_BYTES 64MiB 明确属于 ScientificDeckImplementation 的 x-max-source-bytes / combined source 预算；DeckFile.content 8MiB 是单次源文件载荷合同；ExecutionPackage.resolved_inputs 4096 与 project.input_slots 的单次槽位合同一一对应，并要求唯一性及 exact set equality。它们不是历史累计记录或紧凑视图上限，本轮保留。

root-r2 原始日志 `/tmp/scid-full-record-root-r2-20261016/batch-001/pytest.log` 为 **137 passed / 9 failed**，不能说该批通过。根代理说明六项 worker_resume 的旧 required 夹具、一项新增 calculation proof 缺字段、一项旧 cache-cap 预期已修正；坏大 inputs 的 SQLite JSON 失败则改为 ScientificProvenanceError，继续拒绝坏原件。最终窄复核证据待补。

### 组合审查追加项（已关闭）

**P2，代码推断：同为当前协议 18 的旧已准备 job 续接。** 本补丁从 `contracts.result_schema` 移除 `implementation_selection.maxItems=16`，而原 `continuation.validate_task` 将原 attempt 的 `science-result.schema.json` 与当前生成 schema 全量比较。升级前创建、尚待 same-session resume 的 job，其旧冻结 schema 仍含该字段，因而在原件没有变化时也会报 `Original native output schema changed`。本轮新 fixture 从当前代码生成 schema，不能覆盖此升级路径。根代理已增加精确兼容：只接受当前 schema，或仅额外带 `implementation_selection.maxItems=16` 的确切旧形状；其他字段差异仍拒绝，不写 schema/job/seal。独立代码复核及精确正负控已确认该路径修正，P2 关闭。

历史/执行两组的生产差异亦已读完：完整 observation、checkpoint、lineage、显式 quota helper 与控制准备默认值；完整执行 snapshot/stdio、standalone observer、generic/cov resolver、目录 promotion/confirmation、审计 originals unavailable 的去重终态。未发现其他本差异新增的真实性/权限/未知重提交放行。源码冻结清单核对时，历史清单只有共享 controller 与执行侧最终值不同，执行清单只有补充 diagnostic reason 断言的 test_candidate_audit.py 不同；不将这些解释为未知生产漂移。

执行侧兼容批 `/tmp/scid-full-record-execution-20261016-compat/batch-001/` 为 98 passed / 2 skipped；收尾 `/tmp/scid-full-record-execution-20261016-final/batch-001/` 为 4 passed（含两项显式启用的公开 harness、重复 unavailable 原诊断、launcher 大记录），资源记录均 returncode=0、cleanup_complete=true。较早 r2 的 4 passed / 1 failed 原件仍在。历史 source-r2 为 5 passed / cleanup_complete=true；其余逐批证据和安装包验证待最终汇总，尚不据此宣称全项目无容量缺陷。

## 最终源码证据补齐

- root-r3 `/tmp/scid-full-record-root-r3-20261016/batch-001/`：12 passed / 1 failed；唯一新增 metadata 夹具错误随后在 root-r4 同 nodeID 1 passed 闭合。root-r4 实际经过 retain_calculation(summary=True) → publish → accept → manifest，完整保存 20,000 项结果及完整 proof；compact reply 不复制结果。两批 cleanup_complete=true，保留原失败。
- `/tmp/scid-worker-resume-fixture-current-20261016/schema-r1/batch-001/`：5 passed，0.32 秒，监督 0.566 秒、cleanup_complete=true。current/legacy16 可读；legacy15、required_drift、other_field 拒绝；schema/job/science-task 字节不变，无新增 intent。
- 同目录 source-r1：8 passed / 1 failed；source-r2 仅窄复测该失败：1 passed。最终夹具补当前已要求的字段，并对实际 screen 任务写明确 blocked finding；没有放松 36 token、2 dispatch 等原断言。三项新容量检查保留 >64KiB header、258 session、cwd 拒绝、已接受 header hash 漂移拒绝。

至此静态审查和源码失败收口未发现未处置阻断；最后安装包身份及定向运行证据仍待核，尚不将源码分批结果说成最终单批全绿或真实模型复测。

## 最终安装与文档核证

最终安装树 `/tmp/scid-full-record-installed-20261016-r3`：

- `installed/pytest.log`：**10 passed in 14.54s**；`installed/resource.json`：监督 14.854 秒、returncode=0、cleanup_complete=true、RSS 高水位 267,268,096 bytes，无资源触发。build 监督 3.247 秒、returncode=0、cleanup_complete=true。
- 新鲜 core、TCAD、curve 声明依赖 wheel；隔离 venv、`python -I`、无 source PYTHONPATH/fixture plugin；真实入口为 builtin/general_science/curve_score/tcad_artifact 和 cov_execution/local_execution。安装身份记录 288 个文件，独立重算其 SHA 与当前源码全部匹配。
- `identity.json` SHA256：`9cf4b491e8c15a338cdbdb8c1e3415eb80dcbf7dcfac85c91d1938c4ac697b90`；`result.json`：`65079585542f292a44e8d12b9896c2a1329b67cdfa6da22b0c1712497f61c957`。core wheel：`2f514ee8ad2c5a77feb94bb7907a30810dd16019025c954ec4bf727a5e0d200d`。原始 r1/r2 build 准备失败保留，r2 的陈旧 TCAD build 缓存由身份门禁拒绝，未冒称进入测试。
- execution 最终 17 文件清单 `/tmp/scid-full-record-execution-freeze-final.json` 独立重算零漂移。history 原 9 文件清单仅共享 controller 更新为执行侧冻结值；最终包身份覆盖该共享文件。root 表中 19 个生产文件 SHA 已刷新，包括 continuation 的精确旧 schema 修正。

`docs/ROOTLESS_CLI.zh-CN.md` 最终 SHA256 为 `f3960e35a3bb1e083d8bd706d5c4811ff26355e7878a298968c9f365ba9b94cd`，语义复核通过：完整存储与 compact 视图区分、显式/旧整数配额保留、候选 metric/artifact 精确映射、optional audit/smoke 缺失中性但不绕过必需策略、目录确认不冒称外部接收，且真实 generic 报告链接存在。

源码多批存在重叠和先失败后窄转正，不相加成虚构唯一用例数。未使用模型/solver 复跑；完整结构化 JSON 仍需要对应内存，流式保证仅覆盖原件 blob hash/copy 和内部传输不额外拼接完整 bytes。native_usage 的活体扫描能力未据大 session 原件重读测试推断扩大。保留这些边界后，三个节点可冻结提交。
