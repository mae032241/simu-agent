# R5-L4 独立实现复审（第二轮）

日期：2026-09-01  
复审结论：**PASS**  
放行范围：**只放行 L5；不提前放行 L6 或正式发布**

## 1. 复审范围

本轮不重新审查已经在首轮通过的完整 TCAD 作者—调试—独立审查科学链路，只核验首轮唯一阻断
B1 是否以通用、无领域特判的方式闭合，并检查返修是否引入新的运行回归或复杂度反噬。精确范围为：

- `src/scidiscovery/artifact_agent/service/local_workspace.py`；
- `plugins/tcad_artifact/tcad_artifact/local_debug_service.py`；
- `tests/operations/test_l4_local_tcad.py`；
- 更新后的 L4 证据与 R5-L 进度记录。

当前仍是多阶段累计未提交工作树；本报告不把其他历史脏文件归因于 L4。复审者没有修改生产代码。

## 2. 首轮阻断闭合情况

### 2.1 通用控制写原语已关闭父目录符号链接路径

返修没有分别为 TCAD 和 finalizer 增加两个条件分支，而是在 Local workspace owner 中增加一个共享的
`write_control_workspace_file`：

1. 只接受相对路径，并拒绝空组件、`.` 和 `..`；
2. 从精确 workspace 根开始，以 `O_DIRECTORY | O_NOFOLLOW` 逐级打开父目录；
3. 需要创建父目录时，只通过已经持有的父目录句柄执行 `mkdir`，随后再以同样标志打开；
4. 以 `follow_symlinks=False` 检查最终目标，非普通文件失败关闭；
5. 临时文件使用目录句柄、`O_EXCL | O_NOFOLLOW` 创建，写入后 `fsync`，再通过同一父目录句柄原子
   `replace`；
6. 整个写入期间持有逐级目录句柄，路径名被替换时不会重新解析到 Agent 指定的外部目录。

实现位于 `local_workspace.py:412-488`。这是文件传输层的一个机械原语，没有新增业务实体、状态、
注册表、准入门或科学解释。

### 2.2 Local open/seal 已拒绝输出根符号链接

`LocalTrustedBackend.open` 在 `local_workspace.py:150-178` 现在同时要求：

- Run 根不是符号链接；
- assignment 是非符号链接普通文件；
- output 是非符号链接真实目录。

`seal` 每次先调用该 `open`，因此不能再把作为根本身的 `output -> outside` 当作普通输出树遍历。
`write_primary_output` 也不再拼接路径后直接写入，而是调用同一个目录句柄原语写
`output/result.json`。首轮复现的通用 finalizer 写出路径已闭合。

### 2.3 TCAD 调试没有复制第二套安全写协议

`LocalTCADDebugService` 删除了原先只检查最终文件的私有 `_write_control`，直接调用通用
`write_control_workspace_file` 写 `deck/reports/preflight.json`，见
`local_debug_service.py:146-173`。领域层只选择本 Operation 的相对报告路径、内容和是否创建父目录；
路径遍历、符号链接拒绝、原子替换仍只有一个通用实现。

这满足“TCAD 领域插件声明领域行为，通用运行层拥有文件安全机械事实”的职责边界。通用核心扫描
`tcad|deck|sentaurus` 仍为零命中，没有为本次缺陷引入 TCAD 特判。

### 2.4 两条首轮复现已成为真实回归负例

新增测试直接走 `Root → Run → LocalWorkerMCPRouter → TCAD Operation tool`：

- `test_local_tcad_debug_rejects_a_preflight_parent_symlink` 把
  `deck/reports` 指向工作区外目录，要求工具返回 rejected、外部 `preflight.json` 不存在、Run 保持
  `running`；
- `test_local_tcad_finalizer_rejects_an_output_root_symlink` 把
  `output` 指向工作区外目录，要求工具返回 rejected、外部 `result.json` 不存在、Run 保持
  `running`。

二者与既有 `.operation-tools/tcad` 符号链接负例、8 MiB 文件负例同时通过。它们覆盖的是生产调用链，
不是只测试一个孤立帮助函数。首轮两个复现结果已经从“工具成功并写出”变为失败关闭。

## 3. 回归与复杂度复核

### 3.1 最小独立测试

全部命令串行运行，并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
```

独立复审集合覆盖 L4、Local Run/恢复不变量、Codex 平台、运行时插件、旧 TCAD debug owner 和 33 项
登记矩阵，结果为：

```text
40 passed in 8.41s

git diff --check
通过
```

本轮未重跑完整 `tests/operations`；更新后的候选证据已冻结相同摘要下的
`322 passed in 121.97s` 和防腐集合 `64 passed in 9.38s`，本轮聚焦测试足以独立证明 B1 与共享
边界没有回归。

### 3.2 候选摘要与规模

复算摘要与证据文件一致：

```text
Local backend       2c8299b51860f7293e04b975ea0872f626653794f2727e4aca4768e21e2bc8c3
Local debug service 9dcb7834afaf13fee17368e48a5b797a3f5e335b166810205d9fa18506bebf9d
L4 tests            1e2b460617a0630293a897abe6a5f581a5780cc62f7747a5a9a9dd9b90f86f14
```

生产 Python 为 156 文件、61,048 行；`operations` 包仍为 8 文件、2,288 行；本地 TCAD debug
编排器为 237 行。相对首轮，生产增加 74 行，集中在一个通用、可复用的目录句柄原子写原语及一次
领域调用，没有新增类、状态或重复协议。对于关闭真实可达的控制写出边界，该复杂度增量合理，不构成
复杂度反噬。旧中央路径的整体净删除仍由 L6 完成，不能用本轮 PASS 免除。

## 4. 约束与残余边界

首轮 B1 违反的工作区路径边界和领域工具最小授权已经闭合。返修没有改变 Artifact 不可变性、精确
输入、唯一 Operation 授权、作者/审查者独立、聊天非科学结果、插件单一入口、普通 Run 无
qualification/approval 负担或 Hardened 防腐路径。

`SEC-002` 仍按既有定义保留：Local Codex 原生文件能力是提示约束，不是操作系统沙箱。本轮 PASS
只表示服务端控制写不再跟随 Run 内的父目录符号链接，不能解释为已获得完整不可信 Worker 隔离。
当前实现依赖 Linux/POSIX 的目录句柄、`dir_fd`、`O_DIRECTORY` 和 `O_NOFOLLOW`；若未来声明支持不
具备这些语义的平台，必须新增启动期失败关闭或等价后端，但这不是当前 Linux 部署的 L4 阻断。

33 项矩阵测试只证明登记结构完整，本报告不伪称自动得到了 33/33 语义证明；按本次涉及的路径、
权限、单一权威、插件和审查约束族复核，未发现新退化。

## 5. 最终结论

首轮 B1 已用一个通用目录句柄/O_NOFOLLOW 控制写原语闭合；Local open/seal、TCAD preflight 写入和
两条真实负例相互一致。没有新增 TCAD 核心特判、第二权威、第二文件协议或不必要状态，聚焦跨边界
回归全部通过。

因此 R5-L4 第二轮独立复审结论为 **PASS**。当前只放行 L5；L6 删除、正式发布和对不可信 Worker
的安全声明仍需各自后续完成门与独立审查。
