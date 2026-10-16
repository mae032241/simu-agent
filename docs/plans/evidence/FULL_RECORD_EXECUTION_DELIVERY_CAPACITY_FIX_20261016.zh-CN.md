# 执行、候选审计与交付完整记录容量修复

基线 `4c074ad7f7e41608d397f7e6135fbdc4720d92ec`；本组未提交，不修改旧真实场，不运行模型或 solver。状态：源码定向检查与安装版 10 项全部通过，等待独立审查。

## 已证明的根因与修改

真实 cov rerun W25 的完整 observer snapshot 为 297,940 字节，超过旧 256,000 字节上限；原 call 在，但 observer 降级后 contexts 为空。完整记录与模型视图共用容量常量，使后续 A 丢失精确 candidate/call 关联。即使历史侧恢复关联，执行快照、交付 sources/descriptor、adapter 内部 stdin/stdout、cov receipt/ledger 和独立启动器还存在同类默认上限。

本组仅清除完整持久化与内部传输的机械字节/累计数量上限，模型视图继续有界：

- `experiments` 完整 accepted 输入、执行原件、共同 observation 和复核不设旧 32MiB/64MiB/128 项上限；原件 proof、复制和重读通过已有 contracts 流式 digest/copy，callback 可直接返回 Path。完整 JSON 仍校验格式和逐项关联。
- `local_experiments` 保留全部 output/result/stdio，长 metadata 不再把已知成功降级为 unavailable；CLI public_result 对 metrics/outputs 提供有界视图及 omitted 数量，完整记录先保存。
- `cov_lineage`、standalone cov observer 完整读取 ledger 和输入、保留全部 contexts/candidates；proof/model 复制流式化。独立 `python -I cov_lineage.py` 的 helper 使用绝对 package import，真实 direct-file observer 测试覆盖该入口。
- `delivery` sources、catalogue、descriptor、输入根和原件集合完整保留；blob 分块 hash/copy，逐块保留 deadline；adapter JSON 通过临时文件传完整请求/答复，诊断尾部和 public_sources 仍有界。未改变进程超时、清理或未知提交语义。
- `generic_delivery` 完整 manifest 与 object 集合不再受 256KB/32MiB 默认上限；流式原件复制与校验。`cov_delivery`/`cov_receipt` 对完整 ledger、receipt、guard、snapshot 使用相同语义；模型 promotion 分块复制至 pending，校验后原子替换。
- 共享 rootless cov launcher 的完整 job/schema/config、材料 digest 不受旧 4MiB/32MiB/64MiB/512MiB 机械上限；精确 frozen job/direct_material 来源、path/hash/size/无符号链接与逐文件只读挂载规则保持。

默认完整存储配额改为 None、显式用户整数配额复用 helper、history/checkpoint/lineage/旧 schema 兼容由同伴负责。旧已冻结整数配额仍执行。没有提高已有 token、秒、实验次数或重试授权。

## 相同 unavailable 审计不无限重派

`candidate_audit._unavailable_input` 绑定 settings 摘要、精确 candidate、其 sealed source/observer receipt 和失败 refs；后续 A 只有相同输入且仍缺原件时，保存 `candidate_audit_unchanged_originals_unavailable`，controller 返回 `candidate_audit_originals_unavailable` 及修复原件绑定的诊断，不再派下一个 A。不同候选不被前次失败误阻断；原件修好后 fingerprint/refs 可变化。原 accepted audit 的未知/未清理状态仍走既有恢复规则，不自动重放。

## 源码证据

全部通过 scripts/run_tests.py 的 serial_lock/run_one 监督，numeric_threads=1，原资源限额不降。

| 原始目录 | 结果 | 覆盖与失败处理 |
|---|---|---|
| `/tmp/scid-full-record-execution-20261016-r1` | 6 passed / 3 failed | 保留失败；修复新 candidate_audit JSON import，以及新夹具错误使用 cov 薄 CLI query。 |
| `/tmp/scid-full-record-execution-20261016-r2` | 4 passed / 1 failed，监督 7.77 秒 | 25 次真实注册 fixture call 的大 snapshot、25 contexts/候选、重启关联与篡改拒绝通过；真实三 context 正控、完整大 stdio 通过。失败仅新增 audit fixture 的 sealed route instruction，修正为实际 route_reason。此批不记为全过。 |
| `/tmp/scid-full-record-execution-20261016-compat` | 98 passed / 2 skipped，pytest 110.42 秒，监督 110.707 秒 | 六个执行/交付/launcher 模块；RSS 246,943,744，cleanup_complete=true，无资源触发。两 skip 是未给公开 harness 的 opt-in 环境。 |
| `/tmp/scid-full-record-execution-20261016-final` | 4 passed，pytest 3.82 秒，监督 4.087 秒 | 给既有公开 harness 后实际两参数审计转正；最终重复 unavailable 路由/重启；5MiB job 和 33MiB 流式 digest。RSS 163,831,808，cleanup_complete=true，无资源触发。 |

98+4 存在重叠，不表述为单批 102 个不同用例。新“不同 candidate 不误阻断”由最终 installed 批覆盖。历史组首批暴露 direct-file observer 新相对 import 错误；本组修正后上表 25-call 和三 context 正控通过，保留原失败日志。git diff --check 与语法检查通过。

具体完整性反例包括：33MiB 原件禁止 read_bytes 仍可 snapshot/proof；128 个长路径 output 完整 metadata 超过 256KB；140 候选 refs 超过 256KB；内部 adapter 请求/答复超过 256KB；隔离 generic delivery 的 151 个对象/大 manifest 确认成功，内容篡改仍 unknown；既有路径、scope、哈希、未知 process、重复提交与 receipt 负控保留。

## 安装版证据

原始准备失败均保留：首轮 `/tmp/scid-full-record-installed-20261016` 因临时脚本复制不需要的 pandas、宿主缺 distribution metadata，在 build 阶段退出；r2 因临时 copytree 带入已有 TCAD `build/lib` 缓存，逐字身份比较拒绝其陈旧 wheel，未进入测试。r3 排除 build/dist，仅从清洁包源重建并继续逐文件身份门禁。最终 `/tmp/scid-full-record-installed-20261016-r3`：build 监督 3.247 秒；10 passed，pytest 14.54 秒、监督 14.854 秒，RSS 267,268,096，cleanup_complete=true，无资源触发。新鲜 core、TCAD 与其 curve 声明依赖 wheel；新隔离 venv，无 source PYTHONPATH、无 fixture 插件，`-I`，导入路径核验在 venv；不会把源码测试当安装验证。288 个 core/TCAD/curve 包文件与源码逐字一致，identity.json 保留全部源 SHA 和 wheel SHA；result.json 记录完整命令，installed/pytest.log 与 resource.json 保留原始结果。完整命令入口为 `python -B /tmp/scid-full-record-installed-20261016-r3/supervise.py`，同一 serial_lock 下先 build 再 installed。

10 项覆盖：generic inverse 真实 CLI 完整 directory delivery；151 objects/大 manifest/tamper；25 个真实注册 cov fixture call 后独立 direct-file observer 的 >256KB snapshot、25 contexts/候选、重启与篡改负控；相同 unavailable 审计停止及不同候选不误阻断；>1MiB 完整 manifest、完整 calculation 与语义负控、5MiB JSON/workspace canonical/symlink、1MiB assignment deadline、6000 候选/>4MiB 完整 history 与有界视图。安装版使用合成科学 fixture 与真实控制链，不调用模型或 solver。

## 冻结文件

精确 17 文件 SHA256 清单：`/tmp/scid-full-record-execution-freeze-final.json`。controller 为共享文件：本组仅重复 unavailable 路由和原因，同伴 prepare 默认配额与根 soft repair 预算逻辑也在其最终 hash 中。

- scripts：`scripts/acceptance/rootless_cov_launcher.py`、`scripts/observe_covshift_candidates.py`。
- research_loop：`candidate_audit.py`、`controller.py`、`cov_delivery.py`、`cov_lineage.py`、`cov_receipt.py`、`delivery.py`、`experiments.py`、`generic_delivery.py`、`local_experiments.py`。
- tests/research_loop：`test_candidate_audit.py`、`test_cov_lineage.py`、`test_delivery.py`、`test_generic_inverse_tools.py`、`test_local_managed.py`、`test_rootless_managed_materials.py`。

`generic_results.py` 无需改动，已读取共同完整记录 API；本组未触碰外侧 archive/plugin/service/history 所有权文件。

## 限制

不宣称重新运行真实模型、旧 cov 场或隐藏评分；无 solver。完整结构化 JSON 解析仍需要对应内存，流式保证针对 blob hash/copy 以及内部 transport 不另拼接完整 bytes。进程实际期限和显式存储配额仍可拒绝操作。日志监督输出上限与模型 compact 视图是各自的展示/诊断边界，不控制完整原件封存。

native_usage 的单轮扫描/活体采样边界不是本次完整存储封存路径；根已核 native 最终 turn.completed fallback。大 session/header 的 native/continuation 完整重读由另组验证，不声称此轮验证了超大 header 的实时 usage 绑定覆盖。
