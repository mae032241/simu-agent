# N-body 双模式冒烟准备记录

状态（2026-10-04）：**本机公开 starter 工程 smoke 已完成，独立审查通过（仅本机无模型工程 smoke）；`launch_ready=false`，未运行模型或评分，未授权科研费用。** 原 core 离线安装及未激活 profile 准备已独立审查通过，原实物不改写。本文是有限实物交接记录；选题、运行资格与资源决定仍由[主计划](plans/SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#真实效果题与机制回归分工)拥有。不是 Goal runner 或已激活科学场次；Docker／Harbor 仅为严格复现原 harness 的可选路线，不是本机工程 smoke 前置。

## 已准备实物

| 项目 | 实际结果 |
|---|---|
| source／installed candidate | 干净提交 `76d1ce52c925ee71c7b368203931d661363b8020` 的独立 detached source `/tmp/scid-nbody-prep-20261004-source`；新 core 安装 `/tmp/scid-nbody-prep-20261004-candidate`。旧 `41c3bb4` candidate／source／suite／case 不改写 |
| wheel 与读回 | `scidiscovery-0.1.1-py3-none-any.whl` SHA-256 `4a86654e639898d3ad36c88c537017e164cfe05cf6527bbe552e204db66fd676`；清除源码 PYTHONPATH、使用 installed `python -I`，195 个 package 成员的 source／wheel／installed bytes 相等，wheel RECORD 210 个带 hash 项有效。两个 plugin origins 均为新 candidate site-packages；schema 9、core catalog 可编译。仅此字节／接口子集，非完整发布或 task image 资格 |
| 无执行状态 | 原安装 profile 实际 Root `gpt-5.6-sol/high`，Worker defaults `gpt-6-astra/high`，operations={}；保留原快照。instance／session／progression／Run 均 0；未配置 approval 的读回 runtime 中 execution service 为 None，记未配置，不冒充已测空 execution 服务。candidate 自带旧 probe 合成 task，不是 N-body 绑定场次 |
| 公开任务包 | 来源 `123/lhtb-tasks`，固定 `d78f5eb52ad754c5ee9154741af73130a85a65b8`／`nbody-accel-iterative`。`/tmp/scid-nbody-prep-20261004-evidence/public-task` 仅含下列 8 个允许文件，各 SHA 见 freeze；原稀疏 checkout 保持干净。没有 tests／solutions／oracle／答案或完整 checkout |
| profile 派生输入 | `/tmp/scid-nbody-prep-20261004-evidence/proposal-agent-settings-v2.json` 经实际 installed AgentSettings／effective_settings 解析：Native Codex Goal 候选及 SciDiscovery Root、Worker defaults、helper 的 inherit／lightweight 选路均为 `gpt-6.1-sol/high`，operations={}、无 instance overrides、progression.enabled=false。当前10个 catalog Operation 的实际 executor defaults 经既有 resolve_settings 后也均为该 profile；helper 原输入／调用限制保留。此同 profile 提案未激活、未改 candidate/settings，不继承开发 subagent xhigh/fast，model alias 仍未 runtime 验证。原混合 v1 提案与证据完整保留 |
| 本机工程 smoke | [任务专用薄入口](../scripts/prepare_nbody_local.py) 只准备、计算和交接，不启动 Agent。`/tmp/scid-nbody-local-20261004-prepared-002` 保留相同 8 个冻结公开文件：实际 public `Simulator` 24 粒子／2 步，粒子数／ID／有限值通过；Python 3.12.13、NumPy 2.4.4，不是原 Dockerfile 的 NumPy 1.24.4 环境，标 custom 工程检查。`submission/simulator.py` 为 1286 B，SHA-256 `a4cb0b6717cf077699eb71a7f80f9e4dac4c091fe44d56d9d5ac175ff7cc64b6`，未评分 |

允许的任务文件为 `task.toml`、`instruction.md`、`environment/Dockerfile`、`environment/workspace/simulator.py`，以及 Dockerfile 对 agent 公开的 `environment/harness/{baseline,bench_cli,generate_particles,world}.py`。初版仅复制／封存；本机增量只 import 公开 Simulator／world 做上述极小计算，没有运行原 bench_cli／verifier／参考解。两模式须使用完全相同公开输入。最终只转交 regular `simulator.py`，原 manifest 最大 2000000 B。

实际构建命令（已执行，不重跑到同目录）：

```sh
git worktree add --detach /tmp/scid-nbody-prep-20261004-source 76d1ce52c925ee71c7b368203931d661363b8020
# 在上述 source 工作区：
PYTHONPATH=src /home/da/miniconda3/bin/python scripts/probe_root_host_live.py prepare --candidate /tmp/scid-nbody-prep-20261004-candidate
```

原 prepare 内置全 UID 串行锁和 run_one；build/install 为 no-index／no-deps，未下载。AS 2000000000 B／RSS 止损 1500000000 B／300 s／8388608 B log，prepare 3.412 s、RSS 123691008 B。读回同默认监督；首次诊断脚本误读未配置 execution service 的 None，日志保留，修正诊断范围后通过，未重装／修产品。

本机增量实际命令（已执行，输出目录不可复用）：

```sh
# 监督包装内调用同一 serial_lock/run_one，复制 8 个冻结公开输入到 prepared-002：
/home/da/miniconda3/bin/python /tmp/scid-nbody-local-20261004-evidence-002/supervise_prepare.py
# 此入口自身按默认资源、同一串行锁分别监督计算和合成停止检查：
/home/da/miniconda3/bin/python scripts/prepare_nbody_local.py smoke --prepared /tmp/scid-nbody-local-20261004-prepared-002 --python /home/da/miniconda3/bin/python3.12
```

bwrap 白名单只暴露该公开输入、可写 workspace／output、只读必要 Python／系统 runtime；host-private 合成 canary 与合成秘密环境变量未暴露，任务及其 native 子进程使用独立禁网 namespace。首轮 `prepared-001` 计算后发现继承了监督锁 FD，隔离断言失败；修复在执行任何 public Simulator／native 代码前关闭任务子进程的确切继承 FD，监督父进程仍持锁。新目录计算 0.239 s／RSS 39026688 B 通过，红日志保留。这只验证该 CPU 入口，尚未接线 Root／Worker／helper 的真实 model/API 启动。

停止检查另用**合成自建 process group**：0.15 s 后 SIGSTOP、确认 pulse 不再写入，再 SIGKILL／回收直接子进程；不证明 detached native 进程覆盖、run_one 真实超时或正式全进程树 deadline 合格。8 项有限文件白名单、篡改、symlink、size／提交检查通过；记录见 `/tmp/scid-nbody-local-20261004-implementation.md` 与本轮 freeze，未运行科学评分。

## 双模式的未激活对照边界

| 条件 | Native Codex Goal 与 SciDiscovery 均须冻结 |
|---|---|
| 题目与版本 | 上述 exact instruction／公开 starter／task commit；不强制 science.experiment.v1、optional declaration、A/B 批次或 Operation DAG |
| profile | 未激活 v2 候选两模式主 Agent 与 SciDiscovery Worker／helper 均为 `gpt-6.1-sol/high`；无角色特定 Operation／instance 模型覆盖，helper 两条配置选路一致。native Goal 的实际 child/helper、profile／权限和全角色成本仍须通过真实驱动冻结；本轮只核 installed 配置解析，alias／运行生效未验证，不把 installer Astra 默认写成已批准比较条件 |
| 原版模式 | 原 manifest agent 10800 s，4 CPU／8192 memory_MB／4096 storage_MB／GPU 0／task network=false；单次 separate verifier 最长 3600 s、build 另计，continue_until_timeout=true。这些是原题声明，非预算授权、已拉取 image digest或实际测量 |
| 短冒烟提议 | 可讨论双方相同 1800 s agent wall time，保留题目／资源／二元反馈；须标 LHTB-derived/custom pilot。总 token、verifier 总次数／时间、setup／失败／恢复／收尾等全角色成本尚未批准／冻结；不沿用旧 P6s 4M，提议不激活 |
| 反馈与停止 | 两模式须有相同有效反馈、host-only 隐藏评分／日志与可验证停止。可采用本机 trusted host-only 评分交接（尚未实现／评分）；严格复现修改版 Harbor 时才沿其 binary rejection、separate offline verifier 与继续策略。公开 bench 开发反馈两模式相同。原 continue-until-timeout／full pass 与总期限必须在实际驱动中验证，不以普通 codex exec 的退出替代 Goal 或原题继续协议 |
| 输出 | 本机当前仅有 input／output／cpu-smoke／stop-smoke JSON 与 regular `submission/simulator.py`；正式本机评分输出路径和 trusted 交接仍待冻结。若用 Harbor，则沿其 host-only `<trial>/result.json`、`<trial>/verifier/reward.json`（或 reward.txt），容器 `/logs/verifier` 不挂给 agent。尚无 trial／score 文件 |

## 最短剩余动作与证据

1. **本机双模式真实驱动与评分交接**：当前 task CPU 入口可运行；Native Goal 与 SciDiscovery 的实际驱动、继续／停止协议及 trusted host-only 评分交接尚未实现。可配置的共同 AppServer 启动命令不是已接线证明；模型 API／私密控制连接与 task 命令禁网不能混为同一 namespace。本轮不设置 active Goal、不启动模型，不能用 codex exec 冒充 Goal。
2. **实际 Root／Worker／helper／native 隔离**：既有底层 canary 与本轮实际 Simulator／native 子进程白名单入口通过，但尚未接线真实 scientific profiles。实际模式必须只暴露公开 task／必要 runtime，不挂完整题库、grader 副本／日志、Docker socket、host proc、控制原件；保留 Worker 声明 native 权限。workspace-write／同 UID 换目录不算读隔离；直接设 root_network_access=false 会与现全 catalog 的 evidence.extract 权限冲突，也不能替代 Worker／helper 网络边界。
3. **可选原 harness 复现**：若选择严格复现原题容器，Docker WSL integration／daemon 与 image digest 未就绪，未 pull/build；这不阻止本机路线。`harbor`／`uv` 未安装，公开 preflight 返回2；同一 `d78f5eb` 的 `harbor/` 仅已读源码（pyproject 0.7.0），其 `agents/installed/codex.py` 调 codex exec，未有本轮 Goal／SciDiscovery adapter。选择该路线时才需固定有效修改版／hardening，不把 schema／README 当 runtime ready。
4. **双模式预算／反馈／profile 冻结**：当前仅有准备证据与上述未激活提案，未批准模型／评分费用。补齐同条件总时间／token／CPU／memory、全部角色计账和停止／反馈后另冻实际场次。单题两模式仅 pilot，不授统计效果、官方全集排名或长期资格；N2/N6 bounded coverage／unknown 继续报告。

本机 codex-cli **0.159.2** 的无模型 schema 导出确有 experimental `thread/goal/set`／`get`／`clear`。set 的字段是 `threadId`（required）、`objective`、`status`、`tokenBudget`；返回含 tokensUsed／timeUsedSeconds。没有从 schema 推出运行生效／全部子角色预算覆盖，未调用这些方法、未创建 thread/session、未启动 app-server。真实入口资格仍 pending。生成命令已核对为：

```sh
codex app-server generate-json-schema --experimental --out /tmp/scid-nbody-prep-20261004-evidence/protocol-schema
```

P2 增量审查入口：`/tmp/scid-nbody-prep-20261004-implementation-v2.md`、`/tmp/scid-nbody-prep-20261004-freeze-v2.json`；原安装／输入／隔离检查由未改写的 implementation／freeze v1 保留。各实际 command/resource/log、installed readback／file audit、Goal schemas 与 canary 原件都在本轮 evidence 目录；此记录不把准备成功改写为 launch ready。
