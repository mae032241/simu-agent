# R4 实施与验收记录

2026-09-10。状态：计划范围内源码修复、独立静态审查和定向工程验收完成；未部署，未进行真实科研实例或求解器验收。
依据 INPUT_VALIDATION_PHASE_REPAIR_PLAN.zh-CN.md R4 及其独立计划 PASS。冻结计划保持原文，实施状态以本记录为准。

## 范围与结果

- P0：盘点默认 45 项、含可选 figure 的 50 项动态 Operation 及可达组件，迁移/保留归属见 MIGRATION_INVENTORY.zh-CN.md。
- P1/P2：单一 input_validation 声明和共享创建前检查；Root、目录、Worker 合同同源。提交与预览不调用输入 checker；输出仍核对候选与冻结证据，控制层核对字节完整性。实际冻结源解析发现准入漏检归 admission_defect，保存交付而非要求改稿。
- P3：严格 resume 保留，draft_from 在新 Run 接续受控草稿。合同失配不运行新 hook、不删除未完整保全的源码；旧预览 A 与最新源码 B、隔离中断、重启、恢复预算和副本摘要均有定向验证。
- P4：生产 collector → ingest_result → execution_outputs → 分析提交贯通；诊断日志与 solver 产品分端口，失败/缺产物允许有限报告。通用分析正式封存后交给下一轮设计的绑定记录路径通过。
- P5：安全类别、规则、可修性和恢复状态沿现有 Run 活动持久化，区分候选错误与工程故障。
- P6：真实 wheel/entrypoint 与 installed Root/Worker 投影通过。最终目录相对实际部署版 20 项合同变化、30 项不变，ABI 不变。历史读取不自动授予新资格。

## 定向验证

每行完整命令、耗时、预算与峰值见 checks.jsonl；日志位于本目录。组合有重叠，不累加为独立测试总数。

| 范围 | 结果 | 完整日志 |
| --- | --- | --- |
| L2 Run 生命周期、保全、重启、CAS | 32 passed | check-1789031531661894904.log |
| hypothesis routing、revision、curve、parameter | 65 passed | check-1789031658993188878.log |
| TCAD 有限结果、gap、准入漏检分类 | 36 passed，1 stress deselected | check-1789032086367758731.log |
| 编译、非法目录、preflight、Spec、历史兼容、域边界 | 106 passed | check-1789032139066378795.log |
| 真实 wheel 与安装入口 | 5 passed | check-1789032167554047346.log |
| 通用合同、目标、curve/parameter、figure | 169 passed | check-1789032300278621979.log |
| 分析到下一轮设计、可选插件、Root draft、author 接续 | 42 passed | check-1789032740384360167.log |
| TCAD 作者与审查整文件 | 94 passed | check-1789032756587136991.log |
| 描述符与生产 collector 到分析交接 | 20 passed | check-1789032814074982391.log |

最后 TCAD context 身份调整后已重建 wheel 并仅重装临时 full/all_domains 环境；check-1789032394828237590.log 验证实际 installed Root/Worker 的 13 项输入规则投影一致及 draft_from 请求字段。最终目录见 catalog-source.json；实际部署目录见 catalog-installed.json。

独立实现审查 FINAL_CODE_REVIEW.zh-CN.md 为有界静态 PASS，恢复专项见 RECOVERY_CODE_REVIEW.zh-CN.md。发现的非 pass 审查被错误参数阻断、准入缺陷无实际分类产生者等均修复并验证。最后跨轮测试原用空对象作设计输入，被正确准入拒绝；改用既有真实结构 fixture，随后补齐 json 导入，42 项组合通过。失败日志保留，不计为成功。

git diff --check 通过；113 个当前修改/未跟踪 Python 文件 AST 与空字节检查通过，逐文件 SHA256 见 source-check.json。工作树含大量前史，HEAD 为 2edac5d317a74056869a567bd0daa7f556ecbc85；该静态范围及部署对照不是伪造的本轮初始干净 diff，不将历史修改归为本轮新增。

## 资源与中断事实

用户已确认系统崩溃由另一个程序导致。第一次恢复发现 checks.jsonl 尾部 98 个空字节，原件保留 checks-crash-original.bin，工作记录仅恢复完整行；源码复核无空字节损坏。

测试由 Root 单进程串行执行，子执行者不运行测试。早期测试树上限 1 GiB，恢复后收紧为 min(512 MiB, MemAvailable/4)，监测子进程总 RSS，超限停止进程组。最新完整记录测试峰值 170532864 字节（约 162.6 MiB），没有触及预算。日志及摘要 fsync；该数不代表宿主或全部 Agent 内存。

## 验收边界与后续发布

未运行全量/压力测试或真实求解器，符合冻结计划；测试使用小型执行产物 fixture，真实 collector/入库/Root/Worker 提交路径不等于已完成在线研究。未部署或重启服务，未创建真实实例审批。

技能列出的 scripts/validate_architecture_constraints.py 和 scripts/run_science_control_bench.py 在本仓库不存在，未虚构运行；以现存边界、生命周期、安装与交接测试验证相应路径。

下一步是按匹配 core/插件/配置安装，在替换前处理受影响的活动 Run，再使用现有研究产物进行线上预检和有限分析验证。不能让新合同验收旧活动 Run；恢复材料按已验证的保全/draft_from 规则处理。详细历史影响见 COMPATIBILITY_MATRIX.zh-CN.md，不把本地通过视作线上旧记录已获新资格。
