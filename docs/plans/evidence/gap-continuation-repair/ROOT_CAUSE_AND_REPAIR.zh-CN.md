# Author 失败接续：根因与本轮修复

2026-09-10。基于已有未提交工作树做最小增量；未回退已有改动。此前复现见相邻 gap-continuation-validation/REPORT.zh-CN.md。本轮为实现与定向验证，没有在正式研究实例部署或执行新的 solver。

## 根因

不是“Agent 不记得”，也不是“Run 终态不应存在”，而是终态、会话与交付类型之间的接口没有闭合。

| 断点 | 已确认原因 | 后果 |
| --- | --- | --- |
| 原会话无法领取下一任务 | LocalWorkerMCPRouter._open 在 _completed 为真时直接返回 completed，永远不查询新排队任务；Codex 生成提示只描述一次领取与固定完成回执 | 即使会话仍存在，也没有同角色领取新 Run 的通路。此前两次原 Agent 只返回回执，控制记录无变化；不能据此证明其内部进行了诊断 |
| 有源码但交接没有源码 | gap finalizer 只封存缺口文字；snapshot_workspace 和恢复分支遇 gap 提前返回；诊断主要留在逐 Run 私有工具状态，公开报告只有摘要 | 新审查者与修订者只看到“缺什么”，看不到“已做过什么及失败证据”；completed 的缺口也没有失败 Run 恢复快照 |
| 新修订 Run 创建失败 | prior_project 端口允许项目与 ImplementationGap，但 workspace materializer 仍只解析 DeckProjectDraft | preflight 通过，invoke 在工作区构建时以 local_run_creation_failed 失败 |
| 打通创建后仍可能再次卡住 | validate_implementation_gap 对 prior_project 同样只解析 DeckProjectDraft | 以 gap 为基底的新任务仍不能诚实提交 gap |
| 跨角色不能直接复用 | initial-author 与 revise-author 是不同的编译 agent_type / Operation / Worker 服务 | 原角色权限不能通过一条聊天升级成另一角色；需要新角色通过受控记录接手 |

旧 Run 在缺口提交后 completed 本身是正确行为：它记录“负面交付完成”，不是“实验成功”。修复不重新开启旧 Run，不恢复旧预算，不放宽执行审批。

## 本轮修改

1. 缺口增加默认空的 attempt_files，沿用 DeckFile 表达，路径仅允许源码、project/declarations、attempts.md 与 reports；拒绝重复、越界路径。finalizer 从当前工作区捕获，不采用 Agent 在 gap.json 中自填的快照。捕获最多 128 项、16 MiB，且最终交付仍受原 Operation 输出字节上限约束；超限报错，不静默丢弃。
2. 每次开发诊断另存一份有界记录，保留失败状态、退出码、诊断层、日志摘录，以及精确 source/project/declarations 摘要。attempts.md 用于记录已尝试修改和观察结果。源日志仍沿用原适配器的有界、脱敏摘录；本轮未宣称保存无限完整日志。
3. 修订工作区与 gap 校验统一解析项目/缺口联合类型。审查能读取捕获的源文件与诊断；新修订恢复源码、声明、尝试记录，旧报告进入 reports/history，不写入当前 preflight/initialization 证明位置。损坏的部分元数据作为历史诊断保留，不再阻止工作区创建。没有文件的旧 gap 仍可审查和形成准确缺口，不能自动重建旧源码。
4. 失败 Run 的快照和恢复不再因 gap 丢弃已有源码、声明或诊断。保留原文件数/总量和防符号链接检查；旧完成证明不继承。
5. trusted-local Router 在旧 Run completed/failed 后可领取同一精确 Operation/digest 的新 queued Run；取得新 workspace 后清空逐 Run 工具状态与 completed 标记。没有新任务时仍返回终态，活动 Run 不切换，单纯聊天不产生预算。
6. Codex 提示允许后续明确任务重新 open assignment；Root 可选择复用匹配的空闲 Agent。新任务必须重读绑定记录，不使用旧路径/工具句柄/权限；不同编译角色、升级后的不同 digest、独立审查自身成果仍使用新 Agent。hardened 后端未扩展复用，其原编译检查通过。

没有新增 Run 状态、会话注册表、依赖图、Operation 或数据库迁移。修改了 TCAD 输出合同与角色提示，安装后相关编译身份可能变化；旧进程/旧角色不会原地升级。

## 验证证据

- tests.log：8 passed，4.14 秒。新 Worker 接受 gap 修订、同 Router 跨 Run 领取及状态清理、空 gap 审查、失败快照接续、正常项目修订对照。
- boundary.log：8 passed，5.76 秒。每次失败诊断留存及现有预算上限、旧证明剥离、当前源码证明、符号链接负控、通用 Run 生命周期、Codex 生成入口。
- final.log：8 passed，3.15 秒。加入损坏元数据可交接、尝试记录保留，以及 hardened 编译对照；与前批有重叠，不计作独立 24 项。
- installed.log：核心包与 TCAD 插件均从新 wheel 安装到 /tmp，断言真实 import 路径后 5 passed，2.78 秒。其余插件及依赖复用环境，非全插件清洁环境矩阵。
- wheel 构建成功；build.log 含 wheel 摘要。git diff --check 通过。
- 每批串行，BLAS/OMP/MKL 为 1，定向测试地址空间上限 3 GiB、超时 120 秒。峰值 RSS 102724 KiB，约 100 MiB，无 swap。未执行全量、压力或真实 solver 测试。
- 自审完成；本轮没有调用独立审查 Agent，也没有将自审描述为独立审查。架构约束脚本在当前仓库不存在，未将其记为通过。

## 部署与实际验收边界

本轮证明代码和已构建包支持受控记录接续，以及同编译角色的 Worker 路由复用；未证明 LLM 会话复用的速度收益，也未解决真实 Sentaurus 退出码 1 的科学/数值原因。

重新安装后需启动当前编译角色，先用有界真实失败交付验证“新 Agent 无聊天历史也能接手”，再在同角色新 Run 上验证存活 Agent 复用。旧 initial-author 不能直接领取 revise-author 的任务，旧 gap 未封存的文件也不会由升级补出。不可为了演示复用而绕过这些边界。
