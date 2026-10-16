# 2026-10-16 新 cov 场：准备与启动器合同检查

当前状态：新 runtime-v2 的完整零模型生产配置链 PASS，真实实例 instance-03 已具备启动条件；尚未启动真实模型或评分。下文保留先前失败过程，不用局部通过覆盖旧失败。

基线 `60b535c79d889f948cfb652736d5439fec6e38bf`；本场新目录为仓库 `.trial/cov_live_20261016`。用户授权此场 2,000,000 token／1,200 秒，另有独立 generic 场；根统一以一个 serial_lock/run_one 进程树监督并发，两场共用树 RSS 13GB／系统可用内存 1GB 保底，数值线程为 1，不主动限制虚拟地址空间。本文不记录认证信息或旧科学候选。

## 输入和角色

- 科学工作区仅挂原公开白名单的 8 文件：instruction、task.toml、Dockerfile、harness exp_cli/runner/train/val/meta；逐字匹配原 manifest。未复制旧训练脚本、候选模型、账本、结果或隐藏评分。
- 原件来自历史公开材料副本，历史现场仅复用受核 task Python 依赖环境与启动配置结构；各场实验、提交、预算、科学节点和 native home 均独立新建。
- 当前 native 已升级到 codex-cli 0.163.0，不沿用旧 native 资格；精确 native SHA `399ff69c431c066e40de318fba45c2b07f45a76b19939d247ee4828fc70c4215`，sidecar SHA `8724d73ec190536233ab4628d24a071bfbcf27e5124f08fe35129f26fe48b916`。
- H/W/E 为 gpt-6.1-sol/high，A 为 gpt-5.6-sol/high；default service tier，fast_mode=false，使用框架 role_profiles，不使用历史 monkeypatch。
- soft node 目标为 H/A/E 200k／180s、W650k／480s；closeout A150k／120s，inflight200k，cleanup15s＋submit90s＋confirm15s。共享全场授权仍2M／1200s，无自动扩额。候选 audit、短名单 smoke、角色 token share、new_context 有界分片均显式冻结。

## 启动器缺陷与精确修补

原 production-config 零模型 gate 在 A003 拒绝正式成果：共同执行原件源为 `nodes/002/work/lineage/calls/<call>/observed-originals/<sha>`，冻结目标为 `inputs/parents/002/artifacts/experiments/<call>/artifacts/<name>`；原 launcher 只接受 artifacts/experiments 源目录。原件和失败日志留在本场 `preflight-scene`，真实模型未启动。

只修改共享 `scripts/acceptance/rootless_cov_launcher.py`，增加上述精确六段源路径分支。先用核心 `contracts.validate` 验证 producer seal、冻结共同观察及全部 descriptor/proof，再要求本次 job item 同时存在于 seal.materials，并与该 sealed managed_call 输出的 call/name/path/hash/size 完全对应。目标只从该输出身份推导；不放宽任意 work 文件，不查询 backend，不挂整个父工作树。原32MiB单件、64MiB父总量、内容摘要、长度、无链接与唯一目标约束保留。该 launcher diff 是基线上明确增量，core／TCAD 未改。

| 证据 | 结果 |
| --- | --- |
| `python -B scripts/run_tests.py --output .trial/cov_live_20261016/launcher-regression tests/research_loop/test_rootless_managed_materials.py` | fixture 缺 execution_registry 导入，9 setup errors，0.19s；未进入生产代码，原日志保留。 |
| 同命令 output 改为 launcher-regression-r2 | 9 passed，8.08s；监督8.386s，tree RSS110,817,280B，cleanup=true，无资源触发。 |
| 修后 production-config gate | 实际 bwrap、公开 exp、H/W/A003 audit/A004均通过；W005 new_context 查询原 call 被 core 当前接口与原 accepted 接口 config_sha 差异拒绝，整体尚未通过。该独立问题已交执行侧，未把本次局部通过当作全链成功。 |
| `git diff --check` | 通过。 |

9项回归用真实控制 seal 和共同观察，不 mock descriptor；覆盖合法跨节点文件挂载、同字节但不同 call 归属，错 call/name、外部 source、坏 observation、错 digest/size、链接和重复目标拒绝，并禁止 launcher 重载 backend。

冻结启动器 SHA `5cc660c8e4884dfb80aff692a67adc86d963a1751aa2bcee343e1befe01caff3`；新增测试 SHA `5aec3be090394fb73fc4ac1c44ba16c66303a638e5f21cd5875c6ae3c3065ef8`。独立审查已对这项 launcher 修复给出限定 PASS；整场启动仍被原 call 接口绑定问题阻断，见 DUAL_LIVE_LAUNCH_REVIEW_20261016.zh-CN.md。新实际 instance-02 保持 prepared_not_started，旧无模型准备和失败 gate 不重放；真实模型启动、交付、目标效果及评分尚无证据。

## 当前 native 引擎零模型检查

根授权后，受管执行本场 `sidecar_managed.py`，调用仓库 `probe_native_code_mode.py` 并绑定上述精确 sidecar SHA；实际 connection/ready、session/open、算术 JavaScript 返回2，0 model requests。监督0.125秒，tree RSS45,502,464B，cleanup=true，无资源触发。原始监督记录 `sidecar-supervised/{pytest.log,resource.json}`、引擎事件 `sidecar-probe-artifacts/native-code-mode-events.log` 与结果 `sidecar-probe-result.json` 均在本场目录。仅证明当前打包引擎能够运行，不证明真实模型内工具、账户别名或整场科学资格。


## 最终 runtime-v2 重冻与全链结果

原 call 身份修补已经独立复审并提交为 `8ab844f422be16b5a5c9aa8a1876978af2426a90`。本场新 runtime-v2 准备时基线是 `0c435f87f1e361c44027b3b8919103af8f2498cf`＋当时的精确 core diff，现已与该提交逐字对应。236个 core Python 源码和安装文件全部逐字核同并纳入冻结，保留旧 runtime、instance 与失败 gate，不热修原失败现场。

实际命令 `python -B .trial/cov_live_20261016/preflight_managed_v3.py`，自带原 serial_lock/run_one，先新建实际 instance-03，再在独立 preflight-scene-v3 使用 exact production config 与假 native transport 运行公开真实 exp：

| 阶段 | 结果 |
| --- | --- |
| fresh prepare-v3 | exit0，1.474s，RSS64,372,736B，0模型，实际实例无科学 jobs。 |
| production-config fullchain | **PASS / delivery_confirmed**，106.897s，RSS339,943,424B，cleanup=true、无资源触发。H→W→A audit→A→W两new_context fragments→A→closeout A audit→A deliver全部封存；旧call query、原件挂载、候选审计、短名单smoke、隔离resolve/audit/promote/confirm及最终字节校验均通过。 |
| 最终只读 readiness | 9项检查全true：冻结hash、public whitelist、无jobs、无ledger、无submission、未started、完整零模型链通过、原2M/1200预算、236core一致。无剩余工程阻断，真实模型行为和目标效果仍待实际运行。 |

原始监督日志/资源：`.trial/cov_live_20261016/preflight-r5-{prepare,namespace-fullchain}/{pytest.log,resource.json}`；汇总 `preflight-r5-result.json`。完整 gate verdict 为 `preflight-verdict-v3.json`，SHA `f58bacc0fd93a021b72e25f081c3af1abaadbdda19315a265d5297d1dad8551a`；实际运行冻结 manifest 为 `frozen-manifest-v3.json`，SHA `b15636aa9fa2912871d2f8574d75cde5863fa1b9abbbc49982132d69ff9a0684`。本场 `readiness.json` 保存精确启动argv，run_case.py自身不获取锁，必须由根的共享监督树启动。

共享launcher独审PASS；core原call修补独审PASS。无模型全链是工程门禁，不能替代真实模型验收，也不证明未知在途计费绝不会越过授权。最后复核时原2M/1200s真实授权尚未消费；未自动启动、重试、扩额或进行隐藏评分。
