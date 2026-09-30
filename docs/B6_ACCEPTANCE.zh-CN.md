# B6 剩余项验收

入口：`python scripts/accept_b6.py`。所有案例串行，复用已有实例的静止副本，
不改正式服务、不自动选择实例、不运行 TCAD。配置在 `scripts/acceptance/b6.json`。

## 覆盖范围

| 案例 | 实际动作与通过依据 |
| --- | --- |
| `managed` | 已安装 UI/daemon 由临时 user systemd unit 托管；启动命令退出后服务可访问；重启 daemon 后 PID 改变、旧 Run 和封存字节不变 |
| `manual-known` / `auto-known` | 同一三点合成材料，分别交互 Root / 后台 Root 派发一个完整任务；核对封存结果、科学限制及用量 |
| `manual-ambiguous` / `auto-ambiguous` | 同一不可辨识问题；必须保留无法区分的结论，不能靠给出错误确定结论降低成本 |
| `helper` | 一个负责人调用原生助手；核验原生完成状态，以及负责人封存结果中的核验、整合 |
| `helper-crash` | 观测助手正在运行时终止自己启动的控制 daemon 并重启；要求原 Worker/helper 身份、助手确切回合及封存交付保留 |
| `authority` | 后台 Root 运行后由交互 Root 接管；在控制 socket 重放实际记录的旧代理身份，确认旧实例仍可读而迟到写入被所有权守卫拒绝。该故障注入不等同于复用原生旧连接 |
| `recovery` | 原生暂停/恢复，再重启控制服务，要求原 Root 自动继续且目标、配置、消耗不回退；安全暂停不算通过 |
| `closeout` | 一轮 Root 只读既有封存结果并自然完成交接；核对确切原生回合 completed，再接管、释放旧 writer、停止。无崩溃注入，不重复科学任务 |
| `rollback` | 在 `managed` 后的状态副本上启动明确指定的旧安装版本，验证服务及封存内容可读；仅证明隔离环境兼容性 |

`helper` 案例的显式助手要求仅用于验收能力，不是生产工作流的强制阶段。
若助手太快结束、故障注入窗口未出现，结果为未观测，不自动重试。
已实现恢复时确认原 Root 中断后的有预算续推，源码及子进程验证通过，真实模型验收仍待执行。
恢复消耗已有 max_attempts 预算，不自动增加配置；max_attempts=1 会在第一次中断后停止。
`recovery` 必须观测重启后实际完成交接，不能只凭连接恢复或旧回合仍为 running 判通过。
回滚按用户决定后置，不阻塞本轮恢复与服务托管验收。

尚不覆盖：正式安装器及正式 systemd 服务的事务回滚、所有脱离监督树的原生模型进程
资源、真实 TCAD（A6 后置）。单个案例通过不能宣称整个 B6 通过。

## 准备和执行

先使用已有的安装候选和**尚未开始后台目标**的旧实例快照。不能把已耗尽预算的目标清零
作为基线。下面路径为本轮已存在的候选；保留 `/tmp` 下安装直到验收完成。

```bash
cd /path/to/scidiscovery-dev
python scripts/accept_b6.py init \
  --suite ../../.b6-acceptance \
  --source ../../.a6-upgrade \
  --installed /tmp/scid-b6-interrupt-fixed-install-20260928

python scripts/accept_b6.py prepare manual-known --suite ../../.b6-acceptance
python scripts/accept_b6.py run manual-known --suite ../../.b6-acceptance
```

`init` 已执行过就跳过，不能覆盖已有目录。`prepare` 复用安装而不重新构建，并冻结配置、
基线和程序身份。原生案例的 `run` 在普通终端执行，打印管理链接；选择已有 `b0a-calibration`，
无需再执行 continue。每次只选一个案例；配对另一组用 `auto-known`，依次 prepare/run。

`managed` 不调用模型、不要求绑定；在能访问用户 systemd 总线的普通终端执行。

建议顺序：`managed` → 已知关系配对 → 歧义配对 → `helper` → `helper-crash` →
`authority`。恢复修复完成后再测 `recovery`。`rollback` 需在 init 时额外传
`--previous-installed <旧安装候选>`，不能用同一构建冒充回滚。

先取得全局串行锁，再在子进程启动前写入不可覆盖的 attempt 记录；监督器继承同一把锁。
锁忙时返回 serial_lock_busy，不消耗 attempt、不启动模型，待占用结束可重试原命令。
失败、终端中断、超时都保留原记录，禁止
自动重放。先读 summary/resource/状态再制定恢复动作；不能通过删除 attempt 文件重跑。
新一轮复验须使用新 suite，保留旧轮成本和失败证据。

## 读取结果及科学内容复核

```bash
python scripts/accept_b6.py report --suite ../../.b6-acceptance
```

这是只读命令，不启动模型。报告区分 passed / failed / blocked / not_observed，
保留资源止损、失败尝试和缺测。详细证据在各案例的 `journey-*` 内；这些目录含私有运行
信息，不应作为科学证据公开或提交 Git。

程序验证输出引用和 CAS 字节摘要；科学正确性不从聊天“完成”推断。报告包含
`review_template`：复制为本地 JSON，按 rubric 填 reviewer、每项 status 与证据位置/reason，
然后导入。可由维护者或负责验收的 Agent 阅读封存内容后完成；这是验收记录，不授予科研
审批资格、不修改 Run、不增加生产审批门。

```bash
python scripts/accept_b6.py review manual-known --suite ../../.b6-acceptance \
  --review-file /tmp/manual-known-review.json
```

复核必须匹配确切封存内容摘要和 rubric，不能用另一个 Run 的结论替代。

## Token 和资源解释

### 回包观测和收尾预算

`usage.tool_output_observation` 区分已收到的通知字节与模型实际看到的文本。
缺少后者时 `tool_result_bytes` 为 `null`，不能把通知缺测记成零。
代码模式中的 MCP、shell 和包装文本可能混在同一次输出中，不自动归类为科学正文。

可在验收后对已确认的线程日志作只读审计；显式提供精确身份和路径，不扫描会话目录：

```bash
python scripts/native_usage_audit.py \
  --thread 'root:实际线程ID=/绝对路径/rollout.jsonl' \
  --thread 'worker:实际Worker线程ID=/绝对路径/worker-rollout.jsonl' \
  --output /tmp/scid-native-usage-audit.json
```

输出文件必须尚不存在。审计按 `response_id` 去重请求，按调用身份去重返回；
保存逐请求计数和外层工具类别，不复制提示词、工具正文或管理凭据。
它是指定日志的离线证据，不代替实时预算，也不自动证明所有参与线程均已覆盖。

`progression.closeout_reserve_tokens` 默认 100000，可配置为 0 关闭预留；
该值从 `max_tokens` 内保留，达到预留区后停止新任务准入，已接受的任务仍可交付。
Root 可以报告有证据的完成或未完成情况；耗尽总预算后不再启动额外模型回合。
历史 Worker 线程消耗仅供判断，不按估算成本强制拦截任务。
异步用量通知和已接受任务的继续消耗意味着预留不是硬性成本保证。

`input_materials.startup_read_page_bytes` 默认 16384，仅用于控制生成的
`worker-start.json`；超出该大小继续分页，普通科学原文的默认分页不变。
`instance_current` 摘要保留目标和恢复导航；历史科学交付通过 `progression_status`
或指定 `run_status` 回读。MCP 单份解包是调用指导，不承诺平台禁止 `text(r)`。

- 分开报告 Root、Worker、helper、setup Root；未归属线程保留，缺测不是零。
- 原生通知与控制 checkpoint 按线程去重；输入已包含缓存输入，不再次相加。
- 对照要求同基线、同模型/配置、同目标、两边科学质量通过且计量完整；否则不计算收益。
- 单次配对是小样本证据，不证明普遍收益；不提供虚构的逐请求账单或货币成本。
- 原生任务沿用 `scripts/test_resources.json` 的串行、RSS 和系统余量止损；用户绑定等待
  与执行预算分开。无需提高原生进程虚拟地址限制。
- 不再采样或监控系统 Dirty，不因脏页等待、拒绝启动或终止任务。保留 RAM 余量、
  余量骤降、进程树 RSS、超时与日志上限保护；旧验收的 Dirty 止损记录仅作历史证据。
  资源配置纳入验收工具指纹；不能在配对实验之间静默修改阈值。
- managed 的两个 unit 各有配置化 MemoryMax 和 RuntimeMaxSec；监督器退出或崩溃后也受
  systemd 时限约束。正常退出会停止自己创建的 unit，不碰正式服务。
- unit 的 MemoryPeak/MemoryCurrent 与原生监督树 RSS 是不同统计范围，不能相加冒充
  所有脱离树的原生进程峰值。
