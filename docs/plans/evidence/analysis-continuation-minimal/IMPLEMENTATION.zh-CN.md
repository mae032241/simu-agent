# 分析续接最小修订：完成记录

2026-09-12。源码修订和隔离工程验收完成，线上安装及真实 Agent 耗时收益尚待验证。

## 计划与独立审查

用户授权“详细计划→独立审核最小变更→通过后执行”。R0 被独立审查要求修订，R1 复审 PASS 后才开始源码修改。
冻结 R1 SHA256：e30e39e1e476b5e3ae7d90a7ef2e011f69ec95c4fc8ef78a2cd23c626f20b1ed。
见 PLAN_R1.zh-CN.md、REVIEW_R0.zh-CN.md、REVIEW_R1.zh-CN.md。
实施后又做有界独立符合性检查，发现并关闭较大 package 的隐性读取限制，见 IMPLEMENTATION_REVIEW.zh-CN.md 及其最终兼容补充。

仓库原有大量未提交修改，HEAD 不能代表本轮基线。本轮修改前文件逐字保存于 baseline/ 与 baseline.json，最终增量为 implementation.patch，当前文件摘要为 changed-files.json。
本轮不提交 commit、不回滚他人工作、不修改历史科学 Artifact 或部署状态。

## 已完成的四项工作

1. **简明入口。** 新分析工作区生成不超过 24 KiB 的 analysis-start.json，索引绑定目标/进度、逐字短摘录及 JSON 指针、恢复覆盖和脚本/结果/日志路径。完整 assignment/输出合同/选定工具合同仍可追查。新 native analysis open 不再重复内联完整工具合同；非分析、旧工作区及缺少内嵌合同的旧 assignment 继续使用原回退方式。未知进度只索引，不编造阶段；遗漏有明确标识。
2. **可编辑恢复。** 复用原有安全快照与 no-follow 读写边界，将已保全 scratch 文件复制为新目录 0700/新文件 0600。原件仍为 0500/0400。活动观测目录不复制，旧日志在 recovery-draft 可读，新 Run 不继承旧 latest.json/lock/stop；未自动提交草稿或重新计算。
3. **复用案例对应关系。** TCAD 新增一个纯函数模块，复用 exact prior/manifest 和完整 Artifact 身份映射，只在相同执行 plan/package cohort、原始来源及依据均可映射且案例唯一时继承原条件性关联。入口、工具关系检查、结果 finalizer/context 使用同一视图；工具只保留科学 case/series/axes 选择，不再手抄已有 output/experiment/basis。原调用 JSON、计算记录 request 和 receipt 摘要保持不变。结果缺省机械引用由 finalizer 补齐；新科学 basis 不被覆盖，歧义允许有限报告。删除引用表必须另有同名证据表行的冗余门槛。
4. **准确诊断。** 新输出的源、输出名、案例及依据错误定位到 source_references 的具体索引/字段，证据 locator 定位到具体项；旧式内联计算收据冲突保留具体原因与记录索引。未知 input_alias 不回显任意文本，不增添格式准入条件。错误仍能在同一 Run 修正后封存。

生产改动共七个文件：共享 analysis_workspace.py、通用 science_operations.py、TCAD result_analysis.py/analysis_bindings.py、operations/workspace.py、service/runs.py、mcp_local_worker.py。
workspace 请求仅加默认空、不可变的 descriptor 元数据；不新增 Operation、角色、状态、端口、工具、必填科学字段、收据协议或 runner 能力。

## 验证范围与资源

全部测试和构建串行。复用受限检查器 check.py：512 MiB 地址空间与进程树 RSS 上限、CPU 120 秒、单组墙钟 150 秒、BLAS/OMP 单线程、关闭 pytest 插件自动加载。
修改前 151 项定向基线通过。最终不同测试用例共 **201 项通过**，原 stress 用例按标记未运行；未运行全量测试。

| 最终覆盖组 | 不重复用例数 | 主要事实 |
| --- | ---: | --- |
| 恢复/来源描述/旧证明/案例及新增续接 | 95 | 新旧 Agent 路由、别名重排、精确身份、不可编辑原件与可编辑副本、部分恢复/安全过滤、24 KiB 与隐藏输入、合法大包、明确新 basis |
| TCAD/通用分析/launcher/评分合同/编译消费者 | 98 | 已有有限分析、原生错误、评分边界、无输入重准入/数值重算、收据和字段一致性 |
| 既有 open/单字段合同传播测试 | 5 | native/hardened、新旧合同、声明到工具/文件/执行的一致性 |
| 已安装包的三个定向回归 | 3 | 通用无评分分析、TCAD 原始评分与封存、hardened 原合同和编辑诊断 |

测试曾重复验证修改处，上表已去重，不能将 checks.jsonl 中所有 passed 相加当作不同测试数量。
生产五插件目录编译通过，共 50 个 Operation，确认 TCAD 绑定 materializer/finalizer，通用与 TCAD 共享 snapshot；见 catalog-check.json。

独立 wheel/stdio smoke 串行构建并安装核心、curve_score、tcad_artifact 三包（该组合 45 个 Operation），使用实际 Worker stdio MCP 完成：

- 数值数据保存后绘图依赖报错，日志和失败状态可见。
- 新 Run 打开简明入口，直接修改工作副本；新活动目录为空，旧错误日志仍可追查。
- 仅补图、发布结果并封存，数值调用次数保持 1、已存数字字节不变。
- 下一 Run 从精确先前分析/manifest 自动复用案例依据，原评分请求不变，报告自动带入对应关系后封存。

见 installed_smoke.py、installed-smoke.json、installed-environment.txt。当前七个生产模块的已安装字节摘要逐项核对，不以源码 import 冒充安装验证。
所有检查日志/命令/退出码/耗时/峰值及 watchdog 状态保留于 checks.jsonl 和 check-*.log；本轮进程树峰值约 287 MiB，未触发资源终止或 OOM。

## 中间失败及修正定位

- 首批新诊断测试错误地按 RPC error 取提交拒绝；实际协议是 structuredContent.state=rejected。修正测试读取方式，服务不改协议。
- 独立实现审查指出新投影用 2 MiB 上限读取 package，会低于原已准入的 64 MiB 端口。改按受控 descriptor.size_bytes 读取；使用合法 JSON 大于 2 MiB 的完整 preflight/open/submit 验证。
- 大包测试的第一版改变源文件但保留旧内容摘要，被既有输入一致性检查正确拒绝。改为增加合法 JSON 空白，保持原科学对象/源码摘要不变，以精确测试字节读取边界。
- 安装回归的共享 invoke 同时服务审查与分析，测试一度对审查也要求简明入口。修正测试分支和子进程 import；非分析服务行为保持原状。
- 最后扫描既有合同消费者时补齐两个测试的入口断言，发现旧 assignment 缺少 tool_contracts 时应保留 inline 回退。补齐回退与工具指针，并移除对控制生成 assignment 的任意固定读取上限；相关 18 项及最终 wheel smoke 重新验证。

这些中间失败没有通过放松来源身份、原始请求/收据、输出科学主张或执行授权校验来绕过。

## 部署与真实验收边界

可按 DEPLOYMENT.zh-CN.md 安装，无需同步 VM runner。本轮未执行线上安装或创建研究 Run。
原 Fig.4 60/60 单元、三图与有限结论保持已完成状态；这不是全目标拟合成功，也不改写原 failed/97 外部执行。
新入口消除了确定的重复合同返回，恢复/映射闭环在安装包中已成立；真实 Agent 首项动作耗时、重复读取/截断和总时间仍须安装后另测，不能以工程 smoke 代替。
