# N-body 双模式冒烟准备记录

状态（2026-10-04）：**准备包已构建，`launch_ready=false`，独立增量审查通过（仅有限准备交付）；未运行模型、任务算例或评分，未授权科研费用。** 本文是本轮实物交接记录；选题、运行资格与资源决定仍由[主计划](plans/SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#真实效果题与机制回归分工)拥有。不是新 runner 或已激活场次。

## 已准备实物

| 项目 | 实际结果 |
|---|---|
| source／installed candidate | 干净提交 `76d1ce52c925ee71c7b368203931d661363b8020` 的独立 detached source `/tmp/scid-nbody-prep-20261004-source`；新 core 安装 `/tmp/scid-nbody-prep-20261004-candidate`。旧 `41c3bb4` candidate／source／suite／case 不改写 |
| wheel 与读回 | `scidiscovery-0.1.1-py3-none-any.whl` SHA-256 `4a86654e639898d3ad36c88c537017e164cfe05cf6527bbe552e204db66fd676`；清除源码 PYTHONPATH、使用 installed `python -I`，195 个 package 成员的 source／wheel／installed bytes 相等，wheel RECORD 210 个带 hash 项有效。两个 plugin origins 均为新 candidate site-packages；schema 9、core catalog 可编译。仅此字节／接口子集，非完整发布或 task image 资格 |
| 无执行状态 | 原安装 profile 实际 Root `gpt-5.6-sol/high`，Worker defaults `gpt-6-astra/high`，operations={}；保留原快照。instance／session／progression／Run 均 0；未配置 approval 的读回 runtime 中 execution service 为 None，记未配置，不冒充已测空 execution 服务。candidate 自带旧 probe 合成 task，不是 N-body 绑定场次 |
| 公开任务包 | 来源 `123/lhtb-tasks`，固定 `d78f5eb52ad754c5ee9154741af73130a85a65b8`／`nbody-accel-iterative`。`/tmp/scid-nbody-prep-20261004-evidence/public-task` 仅含下列 8 个允许文件，各 SHA 见 freeze；原稀疏 checkout 保持干净。没有 tests／solutions／oracle／答案或完整 checkout |
| profile 派生输入 | `/tmp/scid-nbody-prep-20261004-evidence/proposal-agent-settings-v2.json` 经实际 installed AgentSettings／effective_settings 解析：Native Codex Goal 候选及 SciDiscovery Root、Worker defaults、helper 的 inherit／lightweight 选路均为 `gpt-6.1-sol/high`，operations={}、无 instance overrides、progression.enabled=false。当前10个 catalog Operation 的实际 executor defaults 经既有 resolve_settings 后也均为该 profile；helper 原输入／调用限制保留。此同 profile 提案未激活、未改 candidate/settings，不继承开发 subagent xhigh/fast，model alias 仍未 runtime 验证。原混合 v1 提案与证据完整保留 |

允许的任务文件为 `task.toml`、`instruction.md`、`environment/Dockerfile`、`environment/workspace/simulator.py`，以及 Dockerfile 对 agent 公开的 `environment/harness/{baseline,bench_cli,generate_particles,world}.py`。只复制／封存，没有 import／运行这些脚本；两模式须使用完全相同公开输入。最终只转交 regular `simulator.py`，原 manifest 最大 2000000 B。

实际构建命令（已执行，不重跑到同目录）：

```sh
git worktree add --detach /tmp/scid-nbody-prep-20261004-source 76d1ce52c925ee71c7b368203931d661363b8020
# 在上述 source 工作区：
PYTHONPATH=src /home/da/miniconda3/bin/python scripts/probe_root_host_live.py prepare --candidate /tmp/scid-nbody-prep-20261004-candidate
```

原 prepare 内置全 UID 串行锁和 run_one；build/install 为 no-index／no-deps，未下载。AS 2000000000 B／RSS 止损 1500000000 B／300 s／8388608 B log，prepare 3.412 s、RSS 123691008 B。读回同默认监督；首次诊断脚本误读未配置 execution service 的 None，日志保留，修正诊断范围后通过，未重装／修产品。

## 双模式的未激活对照边界

| 条件 | Native Codex Goal 与 SciDiscovery 均须冻结 |
|---|---|
| 题目与版本 | 上述 exact instruction／公开 starter／task commit；不强制 science.experiment.v1、optional declaration、A/B 批次或 Operation DAG |
| profile | 未激活 v2 候选两模式主 Agent 与 SciDiscovery Worker／helper 均为 `gpt-6.1-sol/high`；无角色特定 Operation／instance 模型覆盖，helper 两条配置选路一致。native Goal 的实际 child/helper、profile／权限和全角色成本仍须通过真实驱动冻结；本轮只核 installed 配置解析，alias／运行生效未验证，不把 installer Astra 默认写成已批准比较条件 |
| 原版模式 | 原 manifest agent 10800 s，4 CPU／8192 memory_MB／4096 storage_MB／GPU 0／task network=false；单次 separate verifier 最长 3600 s、build 另计，continue_until_timeout=true。这些是原题声明，非预算授权、已拉取 image digest或实际测量 |
| 短冒烟提议 | 可讨论双方相同 1800 s agent wall time，保留题目／资源／二元反馈；须标 LHTB-derived/custom pilot。总 token、verifier 总次数／时间、setup／失败／恢复／收尾等全角色成本尚未批准／冻结；不沿用旧 P6s 4M，提议不激活 |
| 反馈与停止 | 固定修改版 Harbor 的 binary rejection、separate offline verifier、冻结 agent 进程树、隐藏 grader/logs 不回流。公开 bench 开发反馈两模式相同。原 continue-until-timeout／full pass 行为与总期限必须在有效 harness 中验证，不以普通 codex exec 的退出替代 Goal 或原题继续协议 |
| 输出 | 正式 trusted harness 的 host-only trial `<trial>/result.json` 与 `<trial>/verifier/reward.json`（或 reward.txt）；容器 verifier `/logs/verifier` 不挂给 agent。路径来自固定 Harbor 公共 TrialPaths／Verifier，尚无 trial／score 文件，未运行 scorer |

## 最短剩余动作与证据

1. **Docker WSL 与 image**：当前 Windows-path `docker version` 返回该 WSL distro 未启用 Docker Desktop integration；未有可用 daemon／原 image digest，未 pull/build。由实际环境提供可用 Docker WSL 或等价受控容器，随后只读确认 `zli12321/lhtb-nbody-accel-iterative:20260615` 的实际 digest；本轮不 sudo／提权／大下载。
2. **固定修改版 Harbor 与真实 Goal 接线**：`harbor`／`uv` 均未安装，公开 `lhtb_harbor_preflight.py` 返回2（No module named harbor）。源码来自同一 `d78f5eb` 的 `harbor/`（pyproject 声明0.7.0）；`harbor/src/harbor/agents/installed/codex.py` 当前调用 codex exec，不是 Native Goal，也没有本轮新增 SciDiscovery adapter。需在确定环境中固定有效修改版版本／hardening、两模式实际驱动与继续协议；不能把 stock／源码 README 当 installed passed，不新造 Goal flags。
3. **实际 Root／Worker／helper／native 隔离**：bwrap/userns 基础可用。真实 canary 表明仅 uid65534＋挂载私密目录仍可读（单 host UID 映射），不算独立 UID；白名单 mount 后 host 确实存在的私密原件不可见、公共 sentinel 可读，native 子进程同样拒读。这只证明底层 namespace shell，未接线实际 scientific profiles。实际模式必须只暴露公开 task／必要 runtime，不挂完整题库、grader 副本／日志、Docker socket、host proc、控制原件；保留 Worker 声明 native 权限。task 禁网与模型控制连接须明确隔离边界，不能为跑通偷偷降权。
4. **双模式预算／反馈／profile 冻结**：当前仅有准备证据与上述未激活提案，未批准模型／评分费用。补齐同条件总时间／token／CPU／memory、全部角色计账和停止／反馈后另冻实际场次。单题两模式仅 pilot，不授统计效果、官方全集排名或长期资格；N2/N6 bounded coverage／unknown 继续报告。

本机 codex-cli **0.159.2** 的无模型 schema 导出确有 experimental `thread/goal/set`／`get`／`clear`。set 的字段是 `threadId`（required）、`objective`、`status`、`tokenBudget`；返回含 tokensUsed／timeUsedSeconds。没有从 schema 推出运行生效／全部子角色预算覆盖，未调用这些方法、未创建 thread/session、未启动 app-server。真实入口资格仍 pending。生成命令已核对为：

```sh
codex app-server generate-json-schema --experimental --out /tmp/scid-nbody-prep-20261004-evidence/protocol-schema
```

P2 增量审查入口：`/tmp/scid-nbody-prep-20261004-implementation-v2.md`、`/tmp/scid-nbody-prep-20261004-freeze-v2.json`；原安装／输入／隔离检查由未改写的 implementation／freeze v1 保留。各实际 command/resource/log、installed readback／file audit、Goal schemas 与 canary 原件都在本轮 evidence 目录；此记录不把准备成功改写为 launch ready。
