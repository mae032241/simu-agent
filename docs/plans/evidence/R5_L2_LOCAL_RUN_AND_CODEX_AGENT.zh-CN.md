# R5-L2 最小 Run 与真实 Codex 智能体验收证据

日期：2026-09-01  
阶段：L2 第三轮独立复审候选

## 1. 验收结论

L2 前两轮独立复审指出的阻断已在同一最小主干内返修。默认本地路径只有一个 `RunService`
终态权威；`Task/token/session/lease/finalizing` 不在默认运行时实例化或暴露。current 是独立的显式
CAS head，不再与 latest 或 qualification 捆绑；Run 完成命令在同一事务内登记输出绑定，状态查询
保持纯读；失败工作区可跨进程幂等隔离和恢复；Local 目录只公开确实可执行的工具。

有效的真实智能体证据保存在仓库 `deliverables/l2-direct-agent-probe-20260901/`，没有使用 `/tmp`。
旧的 `deliverables/l2-live-probe-20260901/` 使用桥接进程代调工具，已被第二轮复审判定无效，只保留为
失败历史，不再作为验收证据。

## 2. 第二轮阻断返修

| 阻断 | 返修结果 | 直接证据 |
| --- | --- | --- |
| B1 生产 current 不是精确 CAS | Root 输入要求显式可空的 `expected_artifact_name`；首次设置必须期望空 head，后续更新必须命中精确旧对象；删除 latest 与 qualification 门 | `test_root_current_is_explicit_unqualified_compare_and_set`、递归 current 测试 |
| B2 失败隔离有不可恢复窗口 | backend-private 绑定保留；隔离路径由工作区身份确定；`discard` 可在原目录已移动后重放；failed Run 可显式继续未完成的隔离和草稿登记 | `test_real_process_failure_isolation_windows_replay_after_restart`、backend reopen 测试 |
| B3 查询路径发布输出 | Run 创建时冻结输出语义名；完成事务通过唯一 `SchedulerBindingService` 同时写 Artifact 绑定与 completed；两库强制使用并验证 DELETE journal 以保持附加库崩溃原子性；`run_status/list` 只返回冻结绑定名 | `test_completed_run_publishes_output_before_pure_status_queries` |
| B5 Local 静默删除声明工具 | 单一工具投影区分原生等价文件能力与必须有 Local handler 的领域工具；缺失时目录标为 unavailable、preflight 失败关闭；PDF 提取使用无 Task/token 的窄 Local handler | `test_all_installed_local_tools_are_explicit_and_pdf_tool_executes`、干净 wheel 回归 |
| B7 Agent 由桥接进程代调工具 | 新探针没有桥接脚本；真实子智能体自己启动精确 stdio MCP、调用 open/CSV tool/submit，并用原生文件能力写正式结果 | 第 4 节与 `final-evidence.json` |

首轮已闭合且未退化的 B4、B6、B8 分别是：Local/Hardened 默认边界、随机工作区身份和统一发布扫描。
返修没有增加第二目录、第二 current、第二调用入口、领域特判或兼容转发。

## 3. 自动测试

所有测试串行运行，并设置 7 GiB 虚拟内存上限：

```text
L0—L2、调用与人工决定聚焦集合
87 passed in 48.82s

tests/operations -m 'not live'
314 passed in 118.67s

部署、平台配置、精确 dispatch、干净安装集合
63 passed in 57.08s
```

其中真实进程恢复测试用两个独立 Python 进程分别在“失败终态提交后、隔离前”和“工作区原子移动后、
恢复登记前”强制退出，再由新进程重放；它验证旧工作区消失、草稿摘要稳定和新 Run 可按精确输入
继续。stdio 测试真实启动 `python -m scidiscovery.artifact_agent.interfaces.mcp_local_worker`，不是
内存 Router 替身。

## 4. 真实子智能体探针

有效流程是：

```text
operation_invoke 创建 queued Run
→ 生成正式 Local Operation Agent profile 和精确 stdio MCP 命令
→ spawn_agent(fork_turns="none")
→ 子智能体自己启动 stdio Worker MCP
→ 子智能体自己调用 open、注册 CSV 工具和 submit
→ 子智能体用原生文件能力读取受控输入并写 output/result.json
→ RunService 校验、绑定候选、登记 Artifact、写完成收据和输出绑定
→ 父进程只从持久化 Run、工具活动、绑定与 Artifact 验证结果
```

持久化最终证据：

```json
{
  "artifact_parent_count": 1,
  "artifact_verified": true,
  "backend": "local_trusted",
  "bridge_used": false,
  "candidate_bound": true,
  "completion_receipt": true,
  "generated_agent_type": "op_blind_csv_observe_v1_bb23321d26a4",
  "generated_worker_server": "scid_worker_blind_csv_observe_v1_bb23321d26a4",
  "operation_id": "blind.csv.observe.v1",
  "output_bound_before_status": true,
  "registered_tool_succeeded": true,
  "state": "completed"
}
```

边界披露：当前协作运行器拒绝热加载本次运行中新生成的自定义 `agent_type`，返回
`unknown agent_type`。因此在用户已经批准的第一版原型边界内，实际 dispatch 使用无父历史的通用
`worker` 子智能体，并把已生成的精确 profile/MCP 命令作为执行合同。与旧失败探针不同，工具调用和
submit 都由该子智能体直接发出，没有父进程或桥接程序代调。这里不声称“动态自定义角色已被运行器
加载”，也不声称提示约束关闭了 `SEC-002`；后者继续是可信本地原型的已知问题。

## 5. 候选摘要

```text
RunService              1d0e77e9e73081770f24c35a36aa82d0ca68f694ee92c71b25b2b43ca313e0c2
RunCurrentGuard         585431894d766e4a7c080dc9f33472d4e0cb8ac7213cb6f8be6350c1996751ae
LocalTrustedBackend     dfa87c78721a9e3de71e8ec7a6a82870a0515d77696774ecdc40c4c3ac7c71da
Run records             686079c872e6cadb035c41357eabc269aadd218f1035709d315842d73ed33a47
Scheduler bindings      211b076500d603dad71db18f70e2f0a92456682314b57275128504f754baf65e
Local Worker MCP        051ac1317d944a0b9930e13a35218a6bd6a1f31867b96970637bbff434abddbc
Local PDF tool          3a7a3f6ba0940fc2663a9f4e5741917dec0dcd84b626b8bc43dd8a0a61bd7dd8
L2 invariant tests      1874df901efc7635c8139c56c6a6d1d8cba0c02f33e4d187243b87cb1f391ba8
direct probe harness    7697aeb16b37218be3f318437b354cf4e0841212510d0dfd64b9a1653cc7ac72
direct final evidence   8cec30907d9e94d4fade6cd6171b53ab5d3085e2924cd25ee52bc93b9c3e266d
```

摘要只界定本轮候选，不能代替独立语义审查。
