# 双场真实测试启动独审（2026-10-16）

最终 **双场受管并行启动 PASS（工程准备范围）**。共享 launcher 和原 call 跨 attempt 修复均已独审通过，最终零模型 gate 与冻结身份已核对。核对时实际两场尚未运行模型。只读实现，仅写审查证据；未占用测试锁、未改 core、未提交。

## 共享 launcher 修复

受审 HEAD `60b535c79d889f948cfb652736d5439fec6e38bf` 上的精确两文件：

| 文件 | 冻结 SHA256（独立计算相符） |
| --- | --- |
| `scripts/acceptance/rootless_cov_launcher.py` | `5cc660c8e4884dfb80aff692a67adc86d963a1751aa2bcee343e1befe01caff3` |
| `tests/research_loop/test_rootless_managed_materials.py` | `5aec3be090394fb73fc4ac1c44ba16c66303a638e5f21cd5875c6ae3c3065ef8` |

新分支仅接受精确 `work/lineage/calls/<call>/observed-originals/<sha>`。它验证 producer seal，再匹配其 materials、managed output 的 call/name/path/hash/size；同字节不同 descriptor 不靠 basename 猜测。当前 consumer job 仍由原 accepted intent 的 task hash 与 validate_task 冻结校验。未放宽任意 work 文件来源，未重新加载 backend。

32MiB 单件、64MiB 每父节点总量、原件哈希与大小、非 symlink、唯一目标和精确父节点目标路径边界保留。outer 继续逐文件 `--ro-bind`；没有挂整个 producer work、instance 或仓库。

`.trial/cov_live_20261016/launcher-regression-r2/batch-001/pytest.log`：**9 passed / 8.08s**，监督 8.386s、returncode 0、cleanup_complete=true。已读原始日志和资源记录；覆盖真实封存输出及错误 call/name/source/proof/digest/size/symlink/重复目标。首批 fixture 导入错误保留原日志，不算生产通过。精确 diff 空白检查通过。

## 其他启动面预读与未完成 gate

generic launcher 的 mount 集合限定公开目录、当前 workspace/home/evidence、所需 runtime/native 和本实例控制原件；未挂整个 repo 或其他 trial。shell 使用 root deny、inputs 只读、独立环境和禁网，auth/provider 仅供 native，shell 没有 native home 读取权限。最终实际 native 的零模型 command/exec 已验证默认 local 工具执行、成果读取及凭证/旧场隔离。

两场 settings 分别为 2,000,000 tokens、1200 seconds，分开实例与账本。统一监督配置为总 RSS 13,000,000,000 bytes、最低可用 1,000,000,000 bytes、1500s、数字线程 1；pair/driver 使用独占启动标记，不自动重放。pair 用 runtime-v2/venv/bin/python -I 启动两个 driver，一场非零不取消另一场，最终向上返回失败；退出 0 仍不能代替科学成功判定。

前轮 `.trial/cov_live_20261016/preflight-verdict-v2.json` 为 passed=false、models_called=0；W005 新 context 对原 call query 时发生 accepted interface 校验错误。失败原件保留。这不是挂载分支的残余错误；对应[核心修复已独审限定 PASS](ORIGINAL_CALL_CONFIGURATION_REVIEW_20261016.zh-CN.md)，并在最终 runtime-v2 重跑通过。

## 最终 gate 与冻结核对

| 场景 | 最终已核对证据 |
| --- | --- |
| cov | `preflight-verdict-v3.json` 全部 checks=true、delivery_confirmed、0 model；实际 bwrap 下 H/W/A、两 new-context fragments、audit/selection/交付均完成。监督 `preflight-r5-namespace-fullchain/resource.json` 为106.897s、returncode0、cleanup=true。`readiness.json` 9项均true。 |
| generic native | `preflight/result.json` 全true：公开读取、工作区写入、输入写拒绝、private/auth/foreign trial读取拒绝、网络拒绝、默认local run/query与retained output读取；0 model。监督1.579s、cleanup=true。 |
| generic chain | `preflight/fullchain-result.json` passed=true、scripted_transport=true、delivery_confirmed、manifest_count=1、exact_bundle_reproduction=true、0 model；监督5.994s、returncode0、cleanup=true。A3读取6个原件，closeout A4消费冻结comparison。 |

独立复核实际 cov `instance-03` 与 generic `instance` 均 jobs=0、started标记不存在；各自所有冻结文件摘要匹配，预算精确2M/1200。runtime-v2 为已核236核心文件的安装版，匹配提交 `8ab844f422be16b5a5c9aa8a1876978af2426a90` 的代码；无合成fixture插件安装。

最终身份（SHA256）：

- cov frozen-manifest-v3：`b15636aa9fa2912871d2f8574d75cde5863fa1b9abbbc49982132d69ff9a0684`；verdict-v3：`f58bacc0fd93a021b72e25f081c3af1abaadbdda19315a265d5297d1dad8551a`。
- generic operator：`9615a5667f254f3935c015c83c167e0db5e3664330092200f7b7698456ba28d9`；launcher：`7efa0c7edca5b6fdb4ec8c8628a0a060100e95e8545a220c0a2e0bcbf56a55ba`；driver：`964a3cac52554c254082503c2a1571d94bd22bf3ecdc3863baa5fca20e1ff8c5`。
- pair：`de5abca224991d37d97b3c565b9ffeb9a4cd9de1e3da72decffad763503c5ef2`；supervise：`5810b49d5455b4106ce234660c3b2508821d441f8d1ba48443e2cc136f15391e`。

这只允许按用户已授权预算进入真实并行测试，不证明模型行为、科学效果、隐藏评分或全局能力。generic 的非direct-parent历史附件未证明任意可读；目录交付不代表外部服务提交。早期预检失败与窄修证据保留。未追加无关测试或节点。
