# P1–P5 分环节受监控验收

基线 `8e29d07`，另包含本轮迟批恢复修复及两处测试断言修正。用户本轮明确要求执行各环节测试并管理内存，故此前仅静态的限制在本轮按下述有限范围解除。没有运行全量测试或真实模型/远端 solver。独立修复审查见 [审查记录](P_MIGRATION_RUNTIME_FIX_REVIEW_20261017.zh-CN.md)。

## 结果

按所选用例最终结果去重：**159 项通过，R0 的 5 项失败尚未验证通过**。这是分环节定向验收，不是整个仓库全量通过。

| 环节 | 最终用例结果 | 验证内容 |
| --- | --- | --- |
| 完整历史容量 | 10 通过 | 完整原件、流式大文件、紧凑展示与历史分离、显式配额 |
| P1 注册/配置 | 27 通过 | 22 源码、4 进程、1 大合同定向用例；配置冻结/注册/真实本地 CLI 接线 |
| P2 执行/异步/恢复 | 84 通过 | TCAD callbacks/gate/retire 14，组合结果 15，非本地观察 22，原调用配置 13，等待/唤醒 20 |
| P3 来源/审查/授权/迟批 | 30 通过 | 来源 9，正式审查 5，授权 5，资源 3，非空编译输入与迟批恢复 8 |
| P4 UI/只读包 | 6 通过 | UI 控制边界 2、归档 4；UI 为直接请求方法，不冒充真实浏览器验收 |
| P5 单环境/安装 | 2 通过 | 原消费者 mock 1、独立 core 安装冒烟 1；一个环境，不递归功能测试 |
| R0 隔离工程重跑 | 5 失败，环境前提缺失 | 当前解释器缺 cloudpickle/pandas，真实隔离路径尚未通过；不改为 skip 或算通过 |

P2 组合文件在 source lane 的 15 deselected 不是通过；随后在 process lane 实际执行，14 通过及 1 修复后单项通过。P3 非空输入首次 3 通过/5 失败；生产修复后 7 通过/1 断言失败，断言修正后最后单项通过。没有重复运行未受影响的通过批次。

## 发现与修复

1. **真实生产缺陷**：`execution_resume.resume` 在 fresh/unprepared 阶段调用 `Records.directory()`。分配已经存在，但 calls 目录只在 prepare 后 accept 时发布，故合法迟批恢复被提前拒绝。现在仅对已有 accepted 的不确定恢复调用严格目录校验；fresh 不预建目录，不放松 positive pending-set/授权/预算/intent，不重放未知提交。成功与 prepare 中断用例强化真实目录生命周期断言。
2. **测试合同错误**：组合结果 helper 无条件读取 outputs，误把旧 unknown 当已完成。改为仅 unknown 且没有 result_status 时允许字段缺席；完成项继续逐字核验。旧 seal、fact 与 A 页在晚到终态后保持原字节及 unknown。
3. **测试可选字段错误**：恢复前冻结的 A 无 recovery prefix，合同省略 execution_recoveries。断言改为 prefix 精确为空且该字段确实不存在，不用默认值吞错；原 job 字节保护保留。
4. **R0 未通过**：测试 runner 要导入 cloudpickle 和 pandas。`importlib.metadata` 确认两者缺失，`python -I -c 'import cloudpickle, pandas'` 实际报 ModuleNotFoundError: cloudpickle；原测试 5 项均未取得 completed receipt。没有安装这些科学依赖或宣称全部失败只剩这一个原因；补齐依赖后仍须重跑隔离检查。

## 内存与执行纪律

所有批次由 root 独占串行执行，独立执行者/审查者只做静态工作。先跑测试、停测试再编辑，避免冻结代码 hash 在执行中变化。

使用现有 `scripts/run_tests.py`：单线程数值库，禁插件自动加载/xdist，独占串行锁。此次参数：进程树采样 RSS 达 768 MiB 停止；系统可用内存低于 10 GiB 或相对批次启动下降超过 1 GiB 停止；每批 120 秒，日志 2 MiB，采样间隔 0.1 秒。达到条件终止并清理已观察的子进程；这是采样止损，不是 cgroup 总量硬隔离，也不是绝对防 OOM 保证。

本轮最高采样进程树 RSS **267.7 MiB**（异步组）；全部 memory_stop_triggers 为空，所有批次 cleanup_complete=true。安装单批约 4.16 秒、145.1 MiB，离线构建一个 core 环境，仅验入口/资源/依赖隔离。没有 TCAD/插件安装矩阵，没有全仓源码/安装双重功能运行。

## 可复核命令与日志

每批使用同一形式，精确 targets/lane/返回码/时间/RSS/日志路径保存在 [机器结果](P_MIGRATION_TARGETED_TEST_RESULTS_20261017.json)：

```sh
python scripts/run_tests.py --config .trial/p_migration_validation_20261017/resources.json --lane <source|process|stress|installed> --output <new-output-directory> <exact-targets>
```

多文件批次使用 `--per-file`，安装组不使用。安装唯一选择 `--installation-cohort core`。根目录为本 dev 仓库。原始日志留在 `.trial/p_migration_validation_20261017/`，完整原始失败记录保留，不覆盖；结果 JSON 也保留失败和重跑，不应直接累加为唯一通过数。

## 尚未验证

R0 的真实隔离回放；真实 Codex 身份/续接/模型科研能力；真实 TCAD/SSH/solver/远端重启；浏览器及真实 HTTP 跨进程流程；TCAD 安装依赖解析；跨主机可写归档恢复（设计仍未实现）；其余旧生产入口退役。这里的模拟 backend/native transport 通过不能替代上述资格。历史 static-only 报告按当时证据保留，本报告增补有限动态事实，不宣称 P1–P5 整体完结。
