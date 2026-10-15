# 协议 18 三线集成与安装入口验收

基线 `ccb36127fe767b431c192fa44dabaf503ba1e155`，主工作树 `dev`。本次合入已经独立复审的 E1 工程审计恢复、E2 native 用量观测、E3 角色配置补丁。原有计划索引、未跟踪可靠性计划及 18 个历史证据目录未覆盖、未纳入本次提交范围。没有模型调用、预算提升、真实场修改或 push。

## 集成差异

- E1 为唯一协议升级归属，当前协议为 18，旧实例保持归档不可续接。
- `native.py` 首个 import hunk 手工同时保留 E2 `SessionUsage` 与 E3 `profiles`；其余补丁自动应用。`contracts` 的新 repair W 也绑定原 W role profile；continuation 的角色冻结与用量基线同时保留。
- 安装验收入口 `prelive_gate.rebind` 增加一项 `role_profiles` 原样传递，防止异构配置在重建 fixture 时丢失。既有 normalized 比较继续检查全部角色配置，不放宽策略差异。

## 新安装产物

只复制 pyproject 声明的包、README、roles、systemd 数据到临时构建目录，离线构建新 wheel。新 venv 不继承系统 site-packages；依赖按现有安装测试帮助器从 wheel RECORD 离线复制，核心只安装新 wheel。主源码没有生成 egg-info/build，也未覆盖旧安装。

- wheel SHA256：`562bb143faf00c3fcde54d230f883ce81dcf5b286e4b21a769baf00fb105a061`。
- `python -I` 逐一核对 239 个包文件，安装与当前源码无差异。源文件清单 SHA256：`9946a917dd2d3667723d7a1a29f61733df29d0d8de7e7d286a27dd598cb40d1d`。
- 隔离 sys.path 仅含标准库与新 venv site-packages，无 repo/src；实际发现 builtin/general_science 插件与 cov/local execution 接口。
- 新 fixture 从冻结 public harness 只读材料复制，重新 prepare 协议 18。H/W 使用 6.1-sol、A 使用 5.6-sol 的参数只交给确定性 fake native；原全局/节点预算不增加。最终 fixture-2 在 prepare 前同步冻结 launcher 的角色配置。

## 最小安装验证

所有阶段沿用 `scripts.run_tests.py` 的共享 serial_lock、默认资源监督和清理机制；未提高资源阈值。完整 JSON 见同目录 [验收记录](ROOTLESS_ENGINEERING_INTEGRATION_PROTOCOL18_20261015.json)。完整原始日志保留在 `/tmp/engineering18-integrated`。

| 验证 | 结果 |
| --- | --- |
| 新 wheel 构建、隔离安装 | 成功，监督 2.819s。 |
| 真实 CLI/bwrap prelive 8 节点正常链 | `delivery_confirmed`、0 模型、无策略差异；监督 67.693s。 |
| 安装版定向 pytest：registered lifecycle、三个 prelive 场景、五种 fresh/resume 角色参数、计量 reader | 35 passed, 1 skipped，84.65s；此前两个 metadata 失败和三个 prelive 跳过全部实际执行通过。剩余一跳过是 cov 参数不适用的 local payload 专属测试。 |
| 联合工程修复 | 依赖故障→控制有界重试→新 W→新 A→确认交付，8.339s。实际 W/A argv 与 job/intent 各自冻结配置一致；W 的 live token_count 与终态精确 matched，A 无 live 事件明确 terminal_fallback，累计 unknown_steps 为空。历史 seal 不改写，重复 CLI 不重放或重复计步。 |
| 安装版 native process 用例 | 5 passed, 10 deselected，1.82s：运行中投影、用量不重复、终态回退保护、原总额终止、两种实际继承 HOME/CODEX_HOME。 |
| 源码/安装身份与 whitespace | 239 文件无差异，`git diff --check` 通过。 |

临时验收脚本首次启动 pytest 缺额外测试依赖 pygments，下一次 nested pytest 没传递锁 FD；两次均在测试前停止，日志保留。只修新临时环境与监督脚本，随后相同安装产物完成上述验证。未伪造插件 metadata、放宽断言或删除失败记录。

## 结论边界

安装入口已关闭 E1 的两个 metadata 前置失败和三个 prelive 跳过。三线各自独审与最终集成独审均已 PASS。最终审查者直接核对 239 文件安装身份、35+5 pytest 结果、联合检查的实际 argv/intent 断言与正负 gate 原件，确认两个 metadata 失败和三个 prelive 跳过已关闭；审查者未改文件、运行测试或调用模型。证据证明确定性 native 运输、注册 CLI、bwrap、工程恢复/配置/计量组合；不证明真实模型行为、隐藏分数、任意 sibling import 捕获、实时账单上限或远程 solver。全库测试与真实模型场未运行。
