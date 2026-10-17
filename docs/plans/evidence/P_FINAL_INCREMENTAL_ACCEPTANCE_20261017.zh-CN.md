# P1–P5 本轮补齐：有限验收与剩余边界

基线 `29a7f69`；恢复节点 `c59e4b6`，来源节点 `e7e8bb1`。本轮没有新增模型或 solver 场，也没有安装、全量测试或并行测试。代码先独立复审；全部作者冻结后，由 root 唯一执行定向检查。

## 交付与独审

- P1 配置/注册入口沿用已提交实现，不重建注册表。
- P2：显式有限的原 accepted 调用 query/collect/cancel；科学时钟失效不阻止旧调用维护，不派发新的执行。与 P4 共用原账本的已暂停跨 boot 段。见 [P2 独审](P2_CROSS_BOOT_MAINTENANCE_AND_CLOCK_REVIEW_20261017.zh-CN.md)。
- P3：自包含 TCAD V2 的实际准备原件与审查 subject、可选 observer 声明来源接入既有资格及作者遍历。未声明来源继续 unknown，不证明任意 shell 外读。见 [P3 独审](P3_DECLARED_INPUT_COVERAGE_REVIEW_20261017.zh-CN.md)。
- P4：外部唯一 owner、冷 checkpoint、同宿主原路径恢复；恢复保留原账本，默认暂停，重复恢复不会回滚后续进展。见 [P4 独审](P4C2_COLD_CHECKPOINT_IMPLEMENTATION_REVIEW_20261017.zh-CN.md)。
- P5：默认薄 CLI 部署已有 `86e1683`，本轮同步新维护/恢复用法与当前资格。仍有旧 SQL/真实执行消费者的入口按[消费者账](P5_ENTRY_RETIREMENT_LEDGER_20261017.zh-CN.md)保留显式维护，未宣称全部旧代码已删除。

P2 的暂停时钟桥和 P4 的唯一恢复 owner 相互依赖，以同一个可运行恢复节点提交；P3 来源接缝另行提交。没有可独立使用的第二份预算状态。

## 定向结果

所有命令使用 `/home/da/miniconda3/bin/python scripts/run_tests.py`，配置 `.trial/p_migration_validation_20261017/resources.json`；lane 与输出目录如下。日志根为 `.trial/p_finish_20261017/`，原失败日志保留。

| 输出目录 / lane | 精确目标 | 结果 |
| --- | --- | --- |
| `cold_source` / source | `test_cold_checkpoint.py` 的 4 个 source 用例 | 4 通过；两次完整恢复，第二次模拟 boot 变更但使用真实 owner/transfer 校验；原账本前缀不变 |
| `cross_boot` / source | `test_cross_boot_maintenance.py` 的 3 个用例 | 3 通过；有限原调用维护、原预算分段、非法续钟拒绝 |
| `sources` / source | 自包含 V2、observer、V3 后继审查、Local 未知来源四个目标 | 首次 3 通过、1 失败 |
| `opaque_retry` / source | 仅失败的 V2 目标 | 失败，暴露真实通用字段误用 |
| `opaque_generic_fix` / source | 同一 V2 目标 | 修复及独审后通过 |
| `lease_and_local` / process | 外部独立 Python 持 owner lease；Local 实际命令输入→独立审查 | 2 通过；非模型/非远端 solver |

**13 个不同功能目标最终通过**，含修复复测共 15 次功能目标执行。这是逐项修复后的增量通过；没有在最终 HEAD 重跑全部 13 项。模拟 boot 改变不等于真的重启宿主；假后端及合成 native 身份不等于真实 TCAD/模型资格。

失败根因与处置：

1. V2 无编译步骤时封存不含可选 `compiled_implementations` 字段，新 fixture 错用必填索引。改为严格断言 V2 缺席、V3 非空，未放宽生产合同。
2. 进入深层校验后发现 exact 来源 validator 错取 Local 私有 `accepted.config_sha256`。改为通用 `accepted.interface.config_sha256` 与原配置完整正文哈希核对，增加字段归属及篡改负控；不为 TCAD 伪造 Local 字段。独立静态审查先前漏过此项，已在独审账记录。

## 浏览器与内存

真实 Chrome 只测试 read/manage cookie 与暂停按钮，不执行模型或审批，不下载/安装浏览器。

- `browser`、`browser_diagnostic`：启动失败；诊断确认监督器的长 TMPDIR 导致 Chrome Unix socket 路径超限，并尝试使用只读全局配置。
- fixture 改用独立短 `/tmp` 目录、局部 XDG 配置，保留 Chrome sandbox；独审后单项重跑 `browser_short_tmp`。
- Chrome 启动后进程树 RSS 达到 **1,121,267,712 B**，超过本轮 805,306,368 B 的采样止损线，监督器终止并报告清理完成。**浏览器验收未完成**，不是通过；没有提高限额再次试跑。
- 浏览器用例现在须显式 `SCID_RUN_BROWSER_CHECK=1`，默认跳过，避免普通功能测试意外启动重负载浏览器；缺已有浏览器同样跳过，不安装。

9 次监督器批次总耗时 **40.515 秒**。不含浏览器的功能批次最高 RSS **85,745,664 B**（约 81.8 MiB）。所有批次 `cleanup_complete=true`；除上述浏览器 RSS 止损外无资源止损。采样监督不是 cgroup 硬上限或 OOM 保证。

## 不能由本轮结果推出的结论

- 未做真实模型、SSH/许可证/TCAD solver、真实掉电或跨宿主恢复。
- 冷恢复仅接受显式 enrolled checkpoint、同宿主原路径及原外部 anchor；普通历史只读包不能追认恢复权，强隔离仍按用户决定后置。
- 新入口功能接缝已经补齐本轮实现范围，但 P4 的真实浏览器资格和真实远端投产资格仍未完成；不能称全部 P1–P5 生产验收通过。
- main 仅完成[选择性整合评估](MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md)，未修改其未提交工作区，也未整包合并旧调度体系。
