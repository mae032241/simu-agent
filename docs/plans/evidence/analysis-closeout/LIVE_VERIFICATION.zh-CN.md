# 三项收尾现场验收

2026-09-12。科学事实只引用 completed Run 的 Root sealed_output 与 scheduler_signal；工具调用另核对 Root artifact_catalog 的注册元数据。未读取 Worker 工作目录、未封存草稿或 opaque 证据正文。完整控制返回见 [live-curve-completed.json](live-curve-completed.json)。

## 验收结论

| 收尾项 | 本轮结果 | 实际覆盖边界 |
| --- | --- | --- |
| 可选恢复路径 | 修复；无草稿和旧草稿缺清单/日志目录时返回 null，真实存在的恢复文件仍可读写 | 源码定向测试及隔离 wheel/stdio 通过，线上需安装 |
| 原生命令错误可定位 | 修复；命令/脚本共用有界观测，成功不抹除先前错误，Root 给出类型及日志相对指针 | 失败→成功、启动失败、超时、旧记录兼容已验证；直接平台调用仍不保证观测，线上需安装 |
| 恢复与机械映射真实使用 | 实际完成两次曲线诊断及映射；恢复打开缺陷已复现并修复，隔离安装路径通过 | 真实恢复在旧线上打开失败；不能写成真实恢复已通过。需安装后新建受控恢复 Run 补验 |

六个生产文件、两个所属测试文件的本轮增量保存于 implementation.patch；未新增 Operation、科学字段或提交门槛。

## 实际分析

fig4_curve_diagnostic_verification_1 于 12:18:02.993999 UTC 创建，12:18:25.338782 UTC 打开，12:27:05.821191 UTC 完成，创建至完成 542.827 秒。Root 返回 completed、rejection_count=0、failure=null、latest_tool_error=null。

Root 注册的 tool_evidence_025 与 tool_evidence_028 均为 calculation_record、tool_name=worker_tcad_curve_diagnose，各 3,087 字节。它们与完成的主结果属于同一生产 Run。这证明工具确实被调用；主结果 calculation_records 为空不代表没有调用，因为该结果使用已注册的 calculation_ref 引用。tool_evidence_030 为已注册的工程派生产物。

封存分析方法说明，两次调用没有手抄 output_name、experiment_key、case_mapping_basis，而是使用当前 analysis-bindings 的既有映射；最终 source_references 指向 AL 的 solver_outputs_002 与 Ga 的 solver_outputs_003，并保留原执行案例来源。关于请求省略字段的判断来自封存过程说明；Root 没有直接读取 opaque 计算记录的请求正文。隔离 stdio 检查另有确定性断言，证明省略字段能完成工具调用、原请求保持不变且最终来源由控制补齐。

分析者在封存记录中报告，两材料调用均 computed，读取完整 details 并查看两张 overlay/residual 图。本轮没有重跑求解器、已完成的 60 个拟合单元或数字化角点。

科学结果的有限结论是：探索性残差在参考曲线进入陡降后明显增加，并延续到尾段，与既往中央结果中仿真端点偏深、过渡偏宽、尾部偏高的方向一致。工具分段被截断，其边界不能当成梯度变点或物理界面；原始 CSV 调用不表达已审 M0 的资格、共享权重和缺口规则，不能代替正式形貌比较或不确定度结论。机制仍不确定，旧外部执行 failed/97 保持原状。这是封存 Worker 结论的转述，不是调度方新增科学判断。

## 本轮错误及归属

| 事件 | 定位证据 | 本轮处理 |
| --- | --- | --- |
| 恢复打开失败 | fig4_curve_diagnostic_continuation_1 预检通过，打开时报 preserved evidence receipt differs from its origin，未进入计算/提交 | 代码复现发现旧证据当前依赖缺失被误当原收据损坏，以及多次恢复使用中间别名的缺陷。改为核实原 producer，保留草稿并报告未采用收据。真正来源不符仍拒绝；隔离安装已通过，真实新恢复待安装 |
| 工程脚本 FileNotFoundError | 完成后的封存方法明确报告 launcher 在 scratch 内运行，脚本又给输出加 scratch/ 前缀 | Agent 修正相对路径，仅重跑工程记录小脚本，没有重算科学任务 |
| Root 看不到先前原生错误 | 旧线上 native_execution 只保存最后一次成功，诊断摘要未记录上述 FileNotFoundError | 新源码保存最多八项历史错误，Root/Worker 同源投影；启动器真实失败→成功与隔离 stdio 验证通过 |
| 扩展测试四项失败 | 在恢复本轮全部基线文件的临时副本中同样失败 | 旧异常文本及旧返回字段的断言与已有实现不同；保留日志，不扩大本轮范围，不声称全套通过 |

旧恢复现场没有具体 records[i]，因此无法仅凭旧错误消息断定是哪一条收据触发；本轮实现为新错误增加该位置。草稿是否适用于本轮与原件是否损坏分别处理，没有改写旧收据或续开失败 Run。

## 资源和耗时

工程检查与构建串行，科学 Agent 运行期间不跑测试；进程树与地址空间各设 512 MiB 上限、单次 150 秒上限。242 项不同定向用例通过，另有四项已证明的基线失败及一项压力测试未运行。最终三 wheel/stdio 检查通过，整个检查记录最高进程树 RSS 约 287 MiB，无看门狗终止。

同一隔离 Run 的实际简明打开返回为 956 字节，旧兼容格式 33,907 字节，减少约 97.18%。该数值衡量接口返回，不衡量 Agent 所有文件阅读或总推理成本。真实任务用时约九分钟，包含两次诊断、读图和封存；旧观测不足以给出完整逐阶段耗时，也不能把最后一次原生命令时间当作首次计算时间。

本轮源码尚未部署。下一步使用 [部署命令](DEPLOYMENT.zh-CN.md) 安装重启，再验证一项新恢复 Run；无需更新 VM runner。这个安装后的验证是剩余验收项，不是继续重构框架的理由。
