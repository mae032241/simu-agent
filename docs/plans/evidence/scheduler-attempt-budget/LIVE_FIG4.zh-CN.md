# Fig.4 本轮形貌分析：封存与问题记录

2026-09-12。**本轮有界分析交付完成；未证明成功拟合，也未识别微观机制。**
科学内容仅回读控制报告 completed 的 fig4_morphology_closure_2.output 及同次 scheduler_signal。
原 execution_result/runtime_manifest 的 failed/97 保持不变，恢复数据可供分析不改写执行历史。

## 控制记录

- 安装五个生产模块与候选一致，Root 支持新 max_attempts，原 M7-test0 已绑定。
- 旧链 used=2/limit=2；新请求显式 max_attempts=3，预检与调用均通过，新 Run used=3/limit=3。
- 创建 09:47:58.551414Z，打开 09:48:20.515431Z；在 10:02:40.353498Z 完成，距截止约 18.20 秒。
- 第一项受观测原生执行在 09:50:28.714263Z 开始，距创建约 150.16 秒。它不是完整阅读/推理耗时指标。
- 两次输出拒绝，同一 Run 修正后完成；无工具调用错误、无本轮 Run timeout。未重启求解器、未并发跑测试。
- 20 个证据对象（包括保留的旧证据）与一份恢复清单注册。三张 PNG、60 单元结果、逐指标记录、
  目标处分表及工程日志都有受控语义名；输出父链含本 Run 的同生产者清单。
- 本操作目录 review_edge=null、requires_independent_review=false；没有另行声称独立分析审查通过。
  原执行计划和回顾性计划各自的匹配审查仍在绑定材料中。

## 封存分析的结论与边界

Worker 报告复用了 50 个原子单元，仅补算缺失的 InGaAs S1/S2 共 10 个单元，完成 60/60。
两个补算步骤分别约 57.77 秒、58.53 秒；随后从检查点聚合，图只读取已保存数值，不因更换绘图库重跑拟合。
两材料六掩码中央拟合均有有限解，四条 257 点 M0 对齐轨迹保留了缺口；供应数字化角点全部有明确处分。

| 中央 M0 指标 | InAlAs：参考 → 仿真 | InGaAs：参考 → 仿真 |
| --- | --- | --- |
| 操作性深度终点 b2（µm） | 0.474752 → 0.618317 | 0.387624 → 0.535149 |
| 转变宽度（µm） | 0.054455 → 0.176238 | 0.053465 → 0.262376 |
| 尾段中心 log10(cm^-3) | 15.670704 → 18.712136 | 15.933217 → 18.473775 |

以上为封存主报告中的中央估计，描述当前常数-D own-anchor 家族更深、更宽、尾部更高。
不能把中央差异直接提升为带不确定度的复现否定或统计显著性结论。
前/尾区的候选支持和水平/斜率已计算；候选段可估计不等于物理平台平坦或再现合格。

48 个全局数字化角点全部不可用：38 个破坏块内严格 x 次序，10 个使浓度非正或非有限。
因此 not_determinable 的来源是计划规定的不确定度传播与当前数据/拟合条件不兼容，已经完成计算并明确定位，
不是未完成计算，也不是框架阻止 Agent 返回有限结论。总体 verdict 仍 inconclusive，claim_allowed=false。
现有模型家族也不足以识别 kick-out、VCD 或其他微观机制。

## 本轮实际问题与来源

| 问题 | 定位与后果 | 处置/保留限制 |
| --- | --- | --- |
| 旧链最多 2 Run | 原恢复预算属于工程默认值；新 Root 显式预算使旧草稿能进入新 Run | 新 Run 限额 3，旧 Run 不变，已真实通过 |
| 复制后 PermissionError | 封存主报告指出恢复 scratch 内 launcher lock 文件继承只读权限 | 仅修正新工作副本可写性后继续；原草稿保持只读。全局运行锁应否随恢复复制纳入第一优先级优化 |
| 10:00:15 首次输出拒绝 | result_analysis.py analysis_context：source_references 的 source_key 集合不是 evidence 的子集（当前第 395—396 行） | 同 Run 修正后重提。程序只报告 $.payload，未保留出错 key；不能伪称 Root 已恢复首次候选的具体条目 |
| 10:01:21 第二次输出拒绝 | resolve_case_mapping：声明中缺少显式 case_key，而输出声称具体案例且未给 evidence 型 case_mapping_basis（当前第 373—374 行） | 最终报告为四条 own-anchor PLX 给出原 solver_log 分段和 reviewed_package 锚点依据；第三次提交完成 |
| matplotlib 缺失（上轮） | plot_morphology.py:4 的 ModuleNotFoundError 已定位于上轮日志 | 本轮改 Pillow，只补图，不重算已有数值；三图已发布 |
| 相对路径/只读副本（上轮） | morphology_analysis.py:19 FileNotFoundError、输入 cp 保留 0400 导致补丁失败 | 本轮封存工程记录包含恢复的异常与修复说明；不可把旧错误记成本轮工具错误 |
| 中断步骤缺少结束记录（上轮） | 前轮中断后没有取回某批次终止回执，原始 stderr 空 | 保留证据缺口，不臆测成功或异常；本轮有限后续单元已原子落盘 |
| 原外部执行 failed/97 | 声明无 _fps 的 TDR 路径缺失，实际 *_fps.tdr 已恢复 | 未重写历史执行状态；路径声明缺陷未在本轮源码中修复 |
| 48 个角点不可判定 | 38 个 non_strict_x_within_block；10 个 nonpositive_or_nonfinite_corner | 按科学方法合同返回 not_determinable，不排序、删行或发明替代阈值 |
| Root 观测文件写入工具拒绝 | 本轮记录过程中 apply_patch 不允许同一补丁 delete/add 同一文件 | 改用一次完整写入保存，未影响科研 Run；此项是 Root 记录工具错误 |

两次提交拒绝是输出上下文关系检查，不是重新准入冻结输入。但不能据此认为它们的阻断范围都合理：
第一条只检查两份引用表关系；没有实际主张使用的多余映射不应自动等同于缺乏科学证据。
第二条有防止错误案例归属的目的，但当前实现只检查说明结构和绑定来源，不能证明科学映射成立；
旧产物缺少结构化案例归属，使 Agent 再次人工搬运日志锚点。下一轮应区分真正新增科学归属判断和可由既有记录物化的关系。
两条诊断都只给 $.payload，缺少 source_key/input_alias/条目路径，属于明确的纠错反馈缺陷。
本轮未直接删除这些规则，也未绕过它们接受结果。

工程附件 fig4_morphology_closure_2.output.tool_evidence_042 于 10:02:28Z 发布，23517 字节，
晚于两次拒绝，封存报告明确引用它保存 native 终止、异常、修复、提交拒绝和预算界限。
Root 已核对受控注册元数据；对附件内容的概述依据封存主报告，未越过控制接口直接读取 Worker 草稿或私有存储。
Root 的 native_execution 是最近一项摘要，当前轮询并未捕获每一步结束；不能从未看到错误推断没有原生错误，
也不能把局部峰值当整 Run 峰值。科学 Worker 报告的 512 MiB 上限与低资源工程测试峰值不是同一测量。

## 下一步优先级

第一优先级仍为 CONTINUATION_PRIORITY_1.zh-CN.md：最小续接入口、可直接修改的工作副本、
完成项与缺失项清晰交付；这次第一项观测执行提前到 2 分 30 秒，但全 Run 仍约 14 分 42 秒，
不能凭单次更早启动断言上下文问题已经解决。

科学上不要重算已经封存的 60 单元。若继续要求带不确定度的复现判断，先让证据/设计角色修正并审查
合法的不确定度传播方法；若继续微观机制识别，则需新的有区分力的结构性对照。两者不属于本轮已完成的有限交付。

精确请求与原始控制状态见 fig4-closure-2-start.json、fig4-closure-2-completed.json、fig4-closure-2-observations.json。

## 用户追问后的补充核实：确有重复手工映射

Root 通过已 completed 的 fig4_morphology_analysis_2 主报告复查：四条 own-anchor primary/tight PLX
已经分别列出相同的 experiment_key/case_key 与 evidence 型 case_mapping_basis（各三个依据）。
对比两 Run 的 bound_inputs，solver_outputs、experiment_plan、reviewed_package 的绑定均一致。
本轮仍为同四条 PLX 手工重写映射说明，表明问题包含已经封存的关系未被控制层复用，不能统称为新的科学归属判断。

代码原因：_identity_context 的 known 只从 project.expected_outputs 取声明；resolve_case_mapping
在声明 case_key 为空时要求当前输出再给 basis，没有从绑定的 prior_analysis 及其同生产者清单恢复已确认关系。
source_references 虽为可选，但一旦填写就重新承担 evidence 配对与案例依据的校验。
当前实现做到可省略，未做到机械字段自动生成和历史对应关系复用；这属于此前职责裁剪未完成。
下一轮应首先复用确切绑定身份下已有的对应，真实新增或冲突的科学归属才由 Agent 判断；
不得按同名/文件名猜测或把不相干历史关系直接套用。此补充只定位问题，未修改生产规则。
