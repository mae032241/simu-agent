# R5-F 发布、扩展性与总回归验证记录

状态：独立审查通过，只放行 R5-G；R5-F 已冻结。

上位计划：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 10 节。

## 1. 本阶段边界

R5-F 不新增科研能力或框架抽象，只对同一冻结候选执行发布态、扩展性、真实入口、最小授权、
运行时一致性、审批界面和复杂度总门。发现缺陷时只回到唯一责任模块作最小修复，随后重跑受影响
测试和全仓串行回归；不得通过放宽断言、恢复旧入口或增加兼容层过关。

R5-F 的独立审查通过前不得启动 R5-G。

## 2. 执行约束

所有本地命令均严格串行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

不运行会向源码树写入字节码的检查；Python 静态语法改用 `ast.parse`。真实 Operation Agent 验证
必须关闭父上下文继承，并分别证明原生只读、一个已注册领域工具、受控输出写入、完整文件校验、
Worker finalize、Root 完成状态及父会话零代写。

## 3. 验证矩阵与状态

| 编号 | 验证项 | 状态 | 证据 |
| --- | --- | --- | --- |
| F1 | diff、Python AST、shell 静态检查 | 通过 | `git diff --check`、全部生产/测试 Python `ast.parse`、全部 `deploy/*.sh` 的 `bash -n` |
| F2 | catalog 正负例与旧 entry point 复活负例 | 通过 | 167 项发布聚焦矩阵及全仓回归 |
| F3 | core/full/full+InGaAs clean-wheel | 通过 | clean-wheel 入口、目录差异和未知插件测试进入同一 167 项矩阵 |
| F4 | Agent/Transform/Effect/Approval 真入口 | 通过 | 四类 `operation_invoke` 真实入口测试进入同一矩阵 |
| F5 | 参数 Agent 双 Worker 文件闭环 | 通过 | 参数 clean-wheel、真实文件集合、coverage/audit/qualification 链测试 |
| F6 | 盲审批任意端口、生产者族和修订链 | 通过 | 未知插件 clean-wheel 与 attachment-primary 错配负例 |
| F7 | TCAD author/reviewer 工具和工作区最小授权 | 通过 | 自动化正负例及真实第 6 轮双 Agent 资格报告 |
| F8 | runtime 缺配置及双 daemon 摘要漂移 | 通过 | 运行时专项及实际 daemon 入口负例 |
| F9 | UI XSS、未知 Schema、原始附件及精确决定 | 通过 | 固定 renderer/审批身份/原始附件聚焦测试 |
| F10 | 全仓串行回归与三重复杂度计量 | 通过 | `299 passed in 92.81s`；见第 5 节 |
| F11 | 无父上下文真实 Operation Agent 工具/文件生命周期 | 通过 | `.scidiscovery/r5-f-private/tcad-run-20260830-06/qualification-report.json`，27 项全真 |

## 4. 真实智能体失败—修复记录

实时验收没有只保留成功轮次：

1. 通用历史 runner 首次由命令环境缺少源码路径而未进入框架；第二次确认内部
   `builtin.test.agent` 已从真实安装目录消失并正确 `operation_unknown`，因此没有为测试恢复旧
   Operation，而改用已安装 TCAD 插件的真实 author/reviewer 链。
2. TCAD 第 1 轮在源码模式 control daemon 传入未安装 runtime 插件配置，启动门正确拒绝；验收器
   改为只传其真实需要的运行时摘要，TCAD 工具权威继续由精确 Worker broker 提供。
3. 第 2 轮 author 已获得且可见 `worker_file_write_begin`，却从未调用 begin、连续误调用 commit，
   并错误自报工具缺失；同时提示把仅 SProcess 确定性工作区存在的 materialization spec 写成所有
   author 必有。插件资源改为条件路径，并明确 begin→chunk→commit 新建序列，没有修改 Worker
   协议或增设工具。
4. 第 3、4 轮功能链全部完成，但 Codex 运行时诊断被混入 JSON 事件而造成证据误判；验收器不再
   扩大字符串白名单，而是把 stderr 单独封存，事件流继续对任意非 JSON 文本失败关闭。
5. 第 5 轮 reviewer 实际执行 `find ..`，被任务根审计正确拒绝。reviewer Operation 资源补充精确
   Schema 路径和禁止父/兄弟目录搜索的指令；没有把该约束夸大为进程级沙箱。
6. 第 6 轮使用全新状态、任务、Agent 和摘要重跑。author/reviewer 均由真实 Codex 父会话通过
   `spawn_agent` 且关闭父上下文继承启动；27 项检查全部为真。author 实际完成原生任务内读取、
   受控新建文件、注册 TCAD 调试工具、validation/finalize 和 Root completed；reviewer 是不同
   Agent、无 debug 工具、只读任务根，并在缺少真实 solver 资格时返回 `blocked`。

第 6 轮报告 SHA-256 为
`0e23b55fb021c6531162d944764200b4d890e2fd9d2c8617f272cecf8217592e`。其
`qualification_scope` 只把 `architecture_integration` 标为 `pass`；Sentaurus 语法、输入槽解析、
执行就绪均为 `not_claimed`，科学主张不可采纳。

## 5. 最终计量与回归

- 发布聚焦矩阵：`167 passed in 67.32s`；
- 修复后的 TCAD/平台/证据专项：`35 passed in 4.04s`；
- 修复后全仓串行回归：`299 passed in 92.81s`；
- R0 六职责后继聚合：`9818 / 13657`，约净减 `28.11%`；
- `src/scidiscovery/operations/`：7 个 Python 文件，`2053 / 2060` 行；
- `src/ + plugins/`：144 个生产 Python 文件，`60723 / 62533` 行；
- `deploy/install.sh`：1026 行；
- 没有新增数据库表、持久状态机、注册表或 entry-point group。

四处 generic core 领域词命中均是已有领域无关曲线数据模型对 `curve_score` Schema 模块的静态
导入，不是 Operation/插件/角色/端口分派；是否满足最终无领域分派门交由独立审查者复核，实施者
不自行豁免。

## 6. 独立审查

独立报告 `reviews/R5_F_RELEASE_AND_EXTENSIBILITY_INDEPENDENT_REVIEW.zh-CN.md`
结论为“通过（仅放行 R5-G）”。审查者独立复跑全仓 `299 passed in 93.01s`，并复核真实
双 Agent 四份会话、数据库终态、失败轮次、clean-wheel、复杂度及四处 core token。
本结论不宣告 R5 完成，也不预先证明科学效果或冻结根发布清单。
