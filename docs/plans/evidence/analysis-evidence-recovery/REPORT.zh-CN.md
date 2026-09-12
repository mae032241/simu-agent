# 分析内受控证据恢复：实施与验收记录

2026-09-10。P0–P3 源码实施、P4 本地目录及安装包验收完成；正式部署、VM 代码同步及原案例现场验收尚未完成。没有把工程夹具通过当成科研结论或线上缺陷关闭。

唯一实施依据是 [R1 计划](../../ANALYSIS_CONTROLLED_EVIDENCE_RECOVERY_PLAN.zh-CN.md)，SHA256 `cf54d6f0fca8a06ffcae09897d43265e986e8b9a32f480b9633bcafd2dc182ce`。计划正文未改动；其冻结页头仍保留提案时状态，当前进度以本记录及计划索引为准。[独立计划审查](../../reviews/ANALYSIS_CONTROLLED_EVIDENCE_RECOVERY_PLAN_REVIEW_R1.zh-CN.md)的 N1/N2/N3 均已落实。实施者完成了增量静态复核，没有另称独立实现审查。

## 本轮实际交付

- 本地和 Python 3.6 VM 收集器继续处理后续有效产物，分别记录 `solver_exit_code`、`collection_errors`；保留原综合失败状态，耗尽总预算时标明未检查的后续项。
- 现有 TCAD 分析增加 `worker_tcad_inspect_outputs`、`worker_tcad_accept_output` 两个可选工具，使用绑定的 `execution_result` 解析原终态执行范围。支持 socket、command、SSH；文件下载和摘要按块处理。没有 solver、改名、覆盖或源码编辑接口，也没有硬编码 `_fps` 配对。
- 工具接收的原字节和来源回执保存在 Artifact/CAS 与 Run 持久索引中。集合能力必须由 Operation 和受信任工具共同声明；普通单文件角色仍走旧合同。新增一个索引表，复用现有 Run 四态及候选接受/完成边界。
- 原 `result.json` 主报告与服务生成的精确证据快照共同封存。Root 在 completed 后发布附属语义名称；读取、评分、schema 投影和输出重放识别受控证据别名。历史恢复清单及原始文件须显式绑定，新 Run 可重放原计算，尚未映射的检查文件也能作为有来源的背景使用。
- 当前输入准入仍只在 preflight。工具边界负责接收检查，提交只检查证据使用、精确字节完整性和计算重放，不访问 VM 或重新执行输入资格检查。原审计只覆盖原执行产物；恢复不使旧审计自动覆盖新文件，也不清除真实失败。
- 新 TCAD 分析合同显式允许最多两次尝试，以支持一次新的受控失败接手；旧 Run 的冻结上限不变。索引、预算和副本可跨进程恢复；预算在 I/O 前原子预留，进程中断后保守保留占用。损坏的保留证据会使接手 Run 明确失败，具体错误不会被自动续接遮盖。
- 可选服务配置缺失、离线或旧 runner 不支持检查时，普通分析仍可打开并提交有限报告。author 的必需调试服务保持原要求；author 提示仅补充真实输出文件名与声明匹配的职责。

不新增公开 Operation、角色、服务、审批或自动重跑；不改通用科学结果 schema、审批资格和原 Execution。未访问或修改真实研究存储，也未验证 VM 原文件仍在。

## 验收证据

完整命令、退出码、耗时、进程树预算及峰值见 `checks.jsonl`，每次 stdout/stderr 均保存在对应 `check-*.log`。有重叠的测试组不累加成独立测试总数。

| 范围 | 结果 | 日志 |
| --- | --- | --- |
| 收集、TCAD 分析、Root 交接、来源描述符、评分、目录、服务配置、日志、通用角色合同 | 284 passed，1 stress deselected | `check-1789045836511971956.log` |
| 安装 wheel 的 core/curve/TCAD 组合、历史读取、工具投影、普通分析、真实 Root/Worker 恢复与原记录重放 | 9 passed | `check-1789045986011624629.log` |
| 最后错误传播修正后，重建安装包恢复贯通（含损坏证据接手失败）、全部本轮恢复测试及原 draft 入口 | 36 passed | `check-1789046091935861914.log` |
| 从 P0 基线及最终源码分别编译目录 | 默认 45 项、figure 50 项；无新增/删除 Operation | `check-1789046176666482964.log` |

最终补测包含：前项缺失后项保留、solver 0 与综合 97 分离、旧 97 不猜 solver 成功、明确非零与取消不被恢复清除、text/plain 原生 PLX 不改媒体标签直接评分、同 Run 取证/评分/封存、原记录跨 Run 重放、旧审计范围、同字节异执行拒绝、符号链接/文件变化/预算拒绝、回执伪造、CAS 损坏、迟到接收、重复接收、进程重开、失败后接手和普通角色集合禁用。

测试全过程串行；每次完整进程树上限 `min(512 MiB, MemAvailable/4)`，所有批次最大观测峰值 218951680 字节（约 208.8 MiB），无内存超限终止。没有全量/压力测试，没有实际 Sentaurus 或真实 VM 调用。socket 测试只启动一个短暂的隔离测试 daemon，command/SSH 测试使用确定性本地传输夹具。

失败记录未删除。最初失败证明收集器确实在缺失前项时停止；后续检验定位并修正了来源描述符不能自证绑定、历史证据别名投影、附属清单归属、接手错误被重开逻辑遮盖等真实问题。旧评分夹具的 `read_input` 假对象改为当前 `read_evidence` 接口；socket 夹具补齐真实 MCP 包装和已提交记录；没有为通过测试取消生产约束。

补充的普通 Run 不变量、本地 Run 和基础投影测试有 39 项通过；该批随后在一个旧能力测试处停止，不能称整批通过（`check-1789046445704663977.log`）。该测试给科学输入统一写 `{}`，却要求 preflight 通过。用 P0 代码及未修改的 SQL 资源复现，得到相同 `input_checker_failed` 和同一断言失败（`check-1789046617625589628.log`），确认本轮未引入。首次基线复现缺 SQL 资源的环境错误亦保留在日志中。该测试未修改；排除这一个已确认的基线失败后，其余运行能力及平台配置 14 项通过（`check-1789046644214963173.log`）。

这项既有失败作为单独记录保留，不把它隐藏为“全量测试通过”，也不扩大本轮范围修订旧测试。

## 精确增量与兼容

实施前工作树已有大量未提交改动。`baseline.json` 和 `baseline.tar.gz` 保存了 P0 的源码/角色/测试/文档基线；`implementation.patch` 仅包含本轮增量，`source-check.json` 保存最终 35 个增量文件的摘要及静态检查。Python AST、Python 3.6 语法、`git diff --check` 及增量反向应用检查通过（`check-1789046389229167565.log`）。没有用 HEAD 累计差异冒充本任务，也没有修改安装器实现。

`catalog-before.json` 从保存的 P0 源码重建，资源补充范围见 `baseline-projection.json`；补充项是在本任务中没有修改的构建描述与非源码资源。`catalog-source.json` 和 `digest-impact.json` 给出最终比较。只有 TCAD 分析以及共用 author 提示的三个 author Operation digest 改变；其余 46 个 Operation 不变。三个 author digest 变化来自计划允许的输出名称职责澄清，没有增加历史执行读取权限。

旧分析输入可继续不用新端口；不调用工具就不需要新的检查服务。恢复成果跨轮必须显式绑定同一执行结果、恢复清单和所需原始文件；读取历史成果不恢复当前实施/审批资格。旧 queued/running Run 不由新合同验收，新尝试遵守冻结预算及原失败记录。

## 部署后仍需完成的 P4

1. 按现有插件及运行配置安装本地控制端/Worker；本轮没有代用户安装或重启服务。
2. 同步 VM helper。沿用现有 `/etc/scidiscovery/tcad-transport.json` 时，代码更新入口为：

   ```bash
   SCID_PYTHON=/home/da/miniconda3/bin/python \
     deploy/install_ssh_tcad_runner.sh upgrade-code
   ```

   此入口只更新代码，保留远端配置和结果目录；不要重新提交原执行来刷新收集。
3. 重启 Codex 会话并绑定原实例，创建新的 TCAD 分析 Run，绑定原 plan/review/package/execution_result、已有 manifest/diagnostics 和原目标/进展。由受控分析角色检查原文件、决定映射并封存，调度者不代配对。
4. 分开记录原文件是否仍在、工具是否恢复、分析是否 completed、哪些科学目标可评价。缺失或歧义时保留具体缺口；不自动重跑 solver。

因此，本记录支持进入匹配安装及现场验证，不声称已经完成原案例恢复或总体科研目标。
