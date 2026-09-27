# R5-L4 本地 TCAD 最小纵向闭环证据

日期：2026-09-01  
阶段：L4 第二轮独立复审候选

## 1. 实现结论

L4 已在 L2 的唯一 `RunService` 和 `LocalTrustedBackend` 上接通 TCAD 作者、开发调试和独立审查，
没有新增 TCAD 调度器、Task 包装层、资格状态或第二运行入口。

通用运行器只识别编译后的工作区物化器、工作区终结器、领域工具及运行时服务引用；Deck 文件结构、
8 MiB 单文件限制、调试适配器和 TCAD 数据合同均留在 `tcad_artifact` 插件。对通用 Run、Local
Workspace、Worker Router、工具上下文和工作区合同的扫描结果为零 TCAD、Deck、Sentaurus 名称分支。

## 2. 同一 OperationSpec 下的能力组合

`tcad.deck.author.initial.v1` 仍由一个启动期编译的 Operation 描述。其能力由已注册窄组件组合：

```text
OperationSpec
→ TCAD workspace materializer：把冻结输入和 Deck 编辑合同物化到任务目录
→ Codex 原生文件能力：编辑本次任务目录中的 Deck
→ worker_tcad_debug_run：调用已注册的本地 TCAD debug service
→ TCAD workspace finalizer：机械收集 Deck 并生成正式 result.json
→ RunService：统一校验、seal、登记 Artifact 和完成 Run
→ OperationSpec.review：建立独立 reviewer Run
```

本地调试服务只保存当前进程内的有界轮询状态，复用既有 TCAD adapter 和项目校验代码；它看不到
Task、session、token、current 写接口或 Artifact 登记接口。调试产物写入本次工作区的
`.operation-tools/tcad/` 私有区，不进入正式输出目录，不具有科学证据资格。`preflight.json` 只有在
完整候选验证后由工具写入声明的 Deck 报告位置。

为避免本地原生编辑绕过文件边界，最终提交再次执行插件 finalizer 与完整输出合同校验。超过 8 MiB
的 Deck 源文件被拒绝且 Run 保持 `running`，可继续修正。

L4 首轮独立审查真实复现了两条控制写出路径：Agent 可把 `deck/reports` 或 `output` 替换为工作区外
符号链接。返修没有为 TCAD 和 finalizer 分别加条件，而是提供一个共享的目录句柄写原语：从工作区
根开始逐级以 `O_NOFOLLOW` 打开目录，并以目录句柄原子替换控制文件；Local backend 的 `open/seal`
同时拒绝符号链接输出根。现在 `.operation-tools/tcad`、`deck/reports` 和 `output` 三条负例均失败
关闭，外部目录无新增文件，Run 不会完成。

## 3. 真实作者—调试—审查闭环

有效持久证据位于：

`deliverables/l4-local-tcad-agent-probe-20260901-round2/`

流程为：

```text
Root invoke TCAD author
→ 无父历史子智能体直接启动该 Operation 的 stdio MCP
→ open，读取冻结输入与 domain-workspace.json
→ 原生编辑 Deck
→ 直接调用 worker_tcad_debug_run
→ submit，Run completed
→ Root invoke 精确 TCAD reviewer
→ 第二个无父历史子智能体直接启动 reviewer stdio MCP
→ 只读作者 Artifact 并提交审查
→ reviewer Run completed + 精确父链 + passing exact-review
```

两个 Agent 均未由父进程桥接工具调用，聊天只返回“已完成受控提交。”。最终持久证据为：

```json
{
  "author_agent_type": "op_tcad_deck_author_initial_v1_a65afef33389",
  "author_state": "completed",
  "bridge_used": false,
  "debug_result_is_private": true,
  "debug_tool_succeeded": true,
  "preflight_attached": true,
  "review_agent_type": "op_tcad_deck_review_v1_712b8bbf5652",
  "review_has_exact_subject_parent": true,
  "review_is_exact_and_passing": true,
  "review_state": "completed",
  "task_service_absent": true
}
```

本次 probe 使用确定性的命令传输夹具验证运行链路，并不声称调用了真实 Sentaurus 许可证或产生了可
发表的器件结论。与 L2/L3 相同，当前协作运行器不能在会话中热加载刚生成的自定义 Agent 类型，
因此在用户批准的原型边界内使用两个 `fork_turns="none"` 通用 worker 执行各自精确生成的 profile
和 MCP 合同；`SEC-002` 仍为已知问题。

## 4. 插件配置与后端边界

- 本地 Worker 只加载该 Operation 工具实际要求的运行时插件配置；reviewer 不携带 TCAD debug 配置；
- 未出现在编译目录中的插件配置会在平台生成和安装校验时拒绝；
- `local_worker` 只实例化明确提供的插件服务，不要求普通 Operation 支付其他插件运行时成本；
- 旧 Hardened TCAD debug service、Task 绑定、服务端文件协议和适配器合同没有被 Local 实现替换或
  包装；相关防腐回归继续通过；
- 生产 Python 当前为 156 个文件、61,048 行；其中新的本地 TCAD debug 编排器为 237 行，并复用既有
  adapter/bridge 校验，未复制一套 300 余行的领域执行协议。行数暂时仍受 L6 删除旧中央路径约束。

## 5. 最终回归

全部测试串行执行，并限制为 7 GiB 虚拟内存：

```text
L4/平台/运行时插件/Run 聚焦回归
30 passed in 7.58s

tests/operations -m 'not live'
322 passed in 121.97s

部署、平台、运行时插件、旧 TCAD debug 所有权与 L4 防腐集合
64 passed in 9.38s

git diff --check
通过
```

## 6. 候选摘要

```text
L4 tests                 1e2b460617a0630293a897abe6a5f581a5780cc62f7747a5a9a9dd9b90f86f14
live probe harness       240c9196d398475192e96a45a442ff862b60ab53ccc9971ea2d0f24ac4b74cef
transport fixture        3c9ac7bc61066f5a5a50a113ee1eebfd22d6d985119be65ed11c0a44f3a10478
local debug service      9dcb7834afaf13fee17368e48a5b797a3f5e335b166810205d9fa18506bebf9d
TCAD workspace           1989fc1c61ca6109317b78a0de2facc3e33024dcfa333fb379e6ab2bbdc03891
TCAD runtime plugin      ae1749e7c0dbf5e064e2cc2b594d60916f17b25165ab18f972c54b59da8ec628
RunService               9ba5565c6ee994e8141b6f57521e050fdc34d988e2723b97c7579e3466631362
Local backend            2c8299b51860f7293e04b975ea0872f626653794f2727e4aca4768e21e2bc8c3
Local Worker MCP         78ba195454b4ad4ff1cc036efc71559a1215d59999b16193bcb93966c72eae48
OperationToolContext     a6acfc9d16636a196b644b144528f447f68c3e4d6e0ee4c1082172345f7587c1
Codex platform           e0354a808d7f2e55ed0a9a7b711f8e537a0e53c9f8672294238ee213984e0bd7
author dispatch          c8aac1ce1d4196836f9bf9538305c288c5a24ba12cd74f92343b92dc5d132983
reviewer dispatch        520f7bbad49143e8dff8fd63147cbd44392ab906449c3d0ddf81287fdd84876f
final evidence           94b61ebd1dc14a7ef1aff52766317e6bb2ca3b40357b2faa94eab33ee2b770f6
TCAD plugin config       5dc601aabd8b8c4335e7f8bf55cf4006056139fbe54704162b6efbbcdb60fbd4
command adapter config   c9632af864bdba40e5acc1978ddf7cefcceafc2932ce0df978b4dea6da55eef8
```

摘要只冻结候选，不代替独立审查。
