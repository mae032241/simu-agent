# R5-M M7.5 全量回归与关闭证据

日期：2026-09-03  
当前状态：**已完成；两位独立终审者均为 PASS、阻断 0，M7.5、M7 与 R5-M 已关闭。**

## 1. 验收范围

M7.5 不再增加运行实体、注册表、准入规则或生产兼容层。它只把 M7.1—M7.4 已分别成立的证据放到
同一个最终候选上，并验证：

1. 全量自动化回归通过；
2. 干净发行源、wheel 构建、隔离安装和插件组合通过；
3. 部署脚本、升级退出旧表面和事务回滚通过；
4. 当前生产树仍满足单一 Operation 目录、单一普通 Run 生命周期和 Local 软隔离边界；
5. 两名未参与实现的独立审查者分别审查正确性/跨边界和简化目标/33 项约束。

## 2. 前置阶段

| 阶段 | 当前结论 | 主要证据 |
|---|---|---|
| M7.1 安装与运行矩阵 | PASS，阻断 0 | `R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md`，SHA-256 `19c736ff355c338f89702655640c05e5e899f2a9429a906a37af20a3f770b9ba`；独立返工复审确认 clean-installed 核心、领域组合和 Hardened 正例。 |
| M7.2 真实 Agent 与恢复 | PASS，阻断 0 | `R5_M7_2_LIVE_AGENT_VERTICAL_EVIDENCE.zh-CN.md`，SHA-256 `596f0c2d5c539bbbd25bf43c0add65f1d00e2370a79fe1a9ab3a6514b54801eb`；持久根中的真实 Codex 恢复证明读取草稿/Schema、调用领域工具、一次提交和恢复树硬上限。 |
| M7.3 科学/控制边界负例 | PASS，阻断 0 | `R5_M7_3_SCIENCE_CONTROL_BOUNDARY_EVIDENCE.zh-CN.md`，SHA-256 `886379fc1e77cec91791ab6bb76629bb0f6a3dc7e7b4436822bd8cd3de4575dc`；未知外部提交只权威查回，恶意来源不能扩大权限。 |
| M7.4 物理与复杂度报告 | PASS，阻断 0 | 修订报告 SHA-256 `b97d34b91aacef9e8eeade872a442278ac153e93f1d14325c341ae1db25c0868`；返工复审 SHA-256 `d77e0fc5a241094b8c0fe92da5a57bc390d9fec752767f10a842496d1d7a2c9c`。 |

首轮失败审查均作为历史事实保留，没有被覆盖或改写成通过。

## 3. 静态门

在 4 GiB 虚拟内存限制、`MALLOC_ARENA_MAX=2` 和串行执行条件下运行：

```text
git diff --check
python -m compileall -q src plugins deploy scripts tests
bash -n <deploy/ 与 plugins/ 下每个 .sh>
```

结果：全部通过。

`compileall` 会显式在源码树生成被 Git 忽略的字节码缓存，即使设置了
`PYTHONDONTWRITEBYTECODE=1`。这导致随后第一次全量回归中的 SSH runner 安装测试检测到一份
`remote_runner_py36.pyc`，得到 `285 passed, 1 failed`。该失败是验证命令污染测试前置状态，不是
产品或测试缺陷。只删除本轮确定生成的那一个缓存文件后，精确失败项立即 `1 passed`；期间没有修改
任何生产代码或测试代码。最终全量结果以下一节的清洁前置重跑为准。后续复验不得在全量测试之前
对该特殊 runner 源执行原地 `compileall`。

## 4. 最终全量回归

命令：

```text
ulimit -v 4194304
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
/usr/bin/time -v pytest -q -p no:cacheprovider
```

最终结果：

```text
286 passed in 119.08s
elapsed 1:58.00
maximum resident set size 140124 KiB
swaps 0
exit status 0
```

没有并发运行 pytest、真实 Codex 或第二个重型审查任务；峰值内存远低于 4 GiB 单进程限制和 8 GiB
总预算。

## 5. 干净安装与部署回滚为何包含在本轮结果中

全量测试的 session 级 `installed_environments` 不是从 checkout 直接导入：它先调用
`scripts/build_git_release.py` 生成干净发行源，再为核心、TCAD、曲线、可选论文图、InGaAs 以及六个
盲/负例插件构建 wheel；随后建立隔离虚拟环境并分别安装 `core`、`curve`、`figure`、`table`、
`blind_csv`、`architecture`、`m7_effect`、`full`、`ingaas`、`producer_family`、`broken`、
`invalid_unicode`、`core_no_yaml` 和 `tcad_resolved` 组合。探针移除 `PYTHONPATH` 并断言导入模块来自
隔离环境前缀。因此 286 项通过包含了 clean source、clean wheel、隔离安装和缺失/存在组合，而不只是
源码树单元测试。

同一全量套件还实际覆盖：

- 核心安装退出受管理 TCAD 表面后，事务回滚恢复原内容；
- 升级删除旧中央 Worker unit 后，事务回滚恢复原内容；
- SSH runner 安装、私有配置绑定、升级、清理和失败路径；
- 安装/重装/遗留服务清理脚本的语法、机器中性路径与发布内容；
- 默认部署没有第二中央 Worker 服务。

这满足 M7.5 的“干净安装、部署回滚”门，不需要再建立另一套发布测试器。

## 6. 当前候选的边界结论

- 默认主干仍是：编译 Operation → 建立 Run 目录 → 启动角色 → 校验封存输出 → 登记 Artifact →
  按声明进入独立审查或人工决定。
- public/support/internal 是同一个编译目录的投影；没有第二注册表。
- Local 与 Hardened 共用一个四态 RunService；Hardened 是可选后端，不是第二科研生命周期。
- `current`、不可变 Artifact/revision、精确独立审查、UI 人工决定和 Effect 的
  lookup-before-idempotent-submit 边界保留。
- Worker 负责科学内容；控制层不补参数、不生成诊断，也不从来源文本扩大工具、网络、审批或外部
  执行权限。
- 当前物理事实仍为 141 个生产 Python 文件、47,177 行；相对 M0 净减 2,846 行。默认核心为
  63 个组件、14 个 Operation；这些计量只说明默认表面和物理代码，没有冒充科学质量指标。

## 7. 33 项约束与诚实限制

本轮不按测试数量自动升级约束状态。注册表仍是：7 项 `conformant`、25 项 `pending_review`、1 项
`known_issue`。`SEC-002` 继续明确为 Local 软隔离已知问题；当前版本不声称操作系统级强隔离、
不可信多租户安全或任意宿主文件不可读。

本轮也没有真实连接 Sentaurus/SSH 长任务，没有证明任意新领域科学质量、远端长期失联恢复或大附件
性能。M7.2 的真实 Agent、TCAD 工具和恢复闭环以及 M7.3 的 Effect 故障窗口是当前证明范围，不能
外推为上述生产资格。128 位远端目录摘要的理论碰撞风险继续记录，不为极小概率风险扩建状态机。

## 8. 独立终审与最终判断

两名未参与实现的独立终审者已经分别完成审查：

- 正确性与跨边界终审报告 SHA-256 为
  `81db0f5dc7ac5128d1c30d2fbd6bb27b09394cbaf7929a571370d108d2c67096`，结论 PASS、阻断 0；
- 奥卡姆简化、架构目标与 33 项约束终审报告 SHA-256 为
  `6387147f294e40f52bf64932f1210a6c8aa479fc49651c9cd09a5d3968e11159`，结论 PASS、阻断 0。

第一位独立串行复验 16 项并复核四个持久运行根；第二位独立串行复验 22 项，并确认 33 项状态仍为
7/25/1。二者都没有重复 286 项长回归，也没有修改生产代码或测试。两份终审的共同条件已经满足，
据此将 M7.5、M7 和 R5-M 标记为完成。

非阻断后续项原样保留：无 Effect 的默认目录可在后续独立候选中从同一编译目录派生 Root 工具投影，
隐藏当前无用的 execution 工具，但不得建立第二工具注册表；正式发布签署可原子冻结全量 stdout/
stderr；审批 UI 视觉、强隔离、真实 SSH/Sentaurus 和更多学科科学质量仍需独立里程碑。本轮不为这些
事项追加生产补丁，也不扩大当前通过范围。
