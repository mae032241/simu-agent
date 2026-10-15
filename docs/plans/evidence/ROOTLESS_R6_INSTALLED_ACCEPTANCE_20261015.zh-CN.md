# R6 新安装包组合验收

受测提交 `85ca78ce26c92d260eea40ac52943b3655f17614`；包含 R0、R1/R2、R3/R4、R5 及 Local.files 总 entry 有界补修。生产源码在构建前已提交并冻结，协议仍为 18。本次只提交验收证据，没有修改源码、科学阶段、父计划或历史证据目录；未运行模型、增预算、修改真实场或 push。

## 安装与隔离

从提交的 pyproject 声明目录复制到临时构建树，离线构建 wheel，并安装到不继承系统 site-packages 的新 venv。运行入口使用 `python -I`；239 个包文件逐 SHA 与源码一致。实际插件 entry points 仅 builtin/general_science，执行接口为 core 自带 local/cov，没有安装领域插件，没有源码 dist-info fixture。

- wheel：`/tmp/rootless-r6-final-installed-20261015/wheelhouse/scidiscovery-0.1.1-py3-none-any.whl`。
- SHA256：`332cd4c5c93b4482ab99ca538972e9a843e6e920a8eee211ea3abb95be1f6897`。
- 安装身份与标准库/venv sys.path 原件：`installed-identity.json`。

现有部分测试 helper 会将相对 repo/src 放入子进程 PYTHONPATH。本次将 tests/research_loop 原字节复制到独立测试树，该树没有 src，也不复制项目 conftest 的源码插件 metadata 替身；pytest 使用空 pythonpath。测试与 CLI 实际加载新 wheel。补充 observer 是同字节测试脚本，不是包源码。默认链的三个真实 native 子进程另外记录并断言其安装路径与 sys.path。

## 实际入口与组合覆盖

默认链采用确定性的单 argv fake codex，可执行文件 basename 为 codex；prepare 没有传 experiment_mode，因此真实冻结为 local。node_budget_mode 使用默认 soft；为隔离科学搜索，此 fixture 明确禁用 search。prepare/run/closeout 均通过安装版 CLI，fake native 以及其受管 experiment CLI 使用隔离解释器，不调用模型。

H→W→A 完成一个受管本地调用：脚本验证两个含空格/`$()` 的字面 argv，读取控制快照中的输入 42，写出显式有限指标和成果文件。执行后 W 将源输入改为 99 并改写源脚本；控制快照与自动封存成果仍为 42。A 从控制交接索引读取指标与成果原文后 finish。export-only 返回 `exported_unsubmitted`、`goal_completion=not_asserted`，没有外部交付 intent；重复 run 不新增调用。

安装版定向 pytest 覆盖：

- local 受管输入/argv 快照、结果与输出归档、坏/缺/深层结果诚实降级、链接与容量拒绝、总 entry 限制、新旧 job 边界、上层预算/driver/watchdog 清理及 unknown 不重放。
- no-smoke 为中性且无原件仍排除；已知候选局部失败继续后续候选；unknown、未分类和共享环境故障停止且不重复筛选。
- local registered CLI 生命周期、丢回复后的原绑定查询、未知提交不二次启动、真实 entry-point 元数据与控制服务隔离。
- 默认配置下 controller 断开后重接同一原进程、leader 退出后清理存活子进程、过期身份不能误杀其他进程的 R0 小联合。

## 验证结果

全部沿用仓库 serial_lock 与默认 `run_tests.run_one` 资源监督，未调高阈值。原始目录 `/tmp/rootless-r6-final-installed-20261015`；详细机器原件见 [R6 记录](ROOTLESS_R6_INSTALLED_ACCEPTANCE_20261015.json)。

| 阶段 | 结果 |
| --- | --- |
| fresh wheel 构建/安装 | 成功；2.885s。 |
| 239 文件身份与隔离 | 无差异；0.088s。 |
| 默认 local 真实 CLI HWA 联合 | passed；2.344s；0 模型；诚实本地 export 与重复续接通过。 |
| 首轮 installed 定向 pytest | 33 passed, 9 skipped；17.72s。9 项均因新临时环境缺 numpy/pandas，在进入筛选逻辑前跳过。 |
| 科学测试依赖准备 | 从已有 e11 任务环境只读复制 numpy/pandas/dateutil/pytz/tzdata/six/cloudpickle，并复制测试 observer；2.120s。不改核心 wheel 或断言。 |
| 只补跑 9 项筛选用例 | 9 passed，0 skipped；29.70s。未重复之前 33 个通过项。 |

最终所选 42 项各有 installed 通过证据，分两批记录，没有剩余 skip；不宣称单次 42-pass 日志或全库通过。所有阶段 exit 0、cleanup_complete=true，无内存触发。最初 e926600 的预备 wheel 仅完成构建，因随后 P2 修补而弃用，没有对它运行验收，也不纳入最终资格。

上层预算见证原件记录 `stop_reason=node_slice_time_limit`、`cleanup=observed_group_cleaned`；对应测试确认 detached local 进程已停止、调用不伪装 completed，重复 run 保留同一 accepted 原件。driver 中断分支同样记录原组清理完成。

本证据不证明真实模型行为、隐藏目标分数、科学有效性、任意依赖封装、长期资源压力或远程 solver。独立证据复审 PASS：审查者直接核对构建/安装/测试驱动、wheel SHA、239 安装文件与 71 复制测试原字节、默认链归档原件、两批 pytest 与六份资源记录，确认与本记录一致；绑定受测 85ca78c 与上述 wheel。用户追加的两名全新全面审查由父任务另行调度，不能以本记录替代。
