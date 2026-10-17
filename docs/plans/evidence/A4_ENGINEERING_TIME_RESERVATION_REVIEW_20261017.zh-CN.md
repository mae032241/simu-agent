# A4 原调用内工程检查预留独立静态审查

结论：**冻结六文件静态 PASS，可交 root 串行定向验证。** 只审三生产文件、两测试及[实施账](A4_ENGINEERING_TIME_RESERVATION_IMPLEMENTATION_20261017.zh-CN.md)，不混并行 A2/A3，不授动态或真实科学资格。

## 生产链与边界

- `engineering_check_reserve_seconds` 默认 0；Cov 验证有限非负且拒绝 bool。现有 `operator_configuration → configure → freeze/load` 将配置及代码身份绑定；`configure` 仍精确匹配操作者冻结配置，未新增 W 自报预留/权限入口或预算 owner。
- `replay_check.acceptance` 在 Records.accept/submit 前绑定原总截止与分配。只有可选能力明确支持切分且原窗口容得下实验、检查和反馈时为 reserved；实验截止为同总截止减预留，检查仍受同总截止减反馈及原能力上限约束。soft admission 原截止只会进一步裁小，重试不刷新授时。
- Cov 只消费 accepted 内原分配；Local 私有 hook 默认 None，普通 Local、默认 0 和无分配 accepted 保持原路径。不会切分的可选插件如实报告 unsupported 预留，并仅沿原窗口尽力检查；不足为 unavailable/not_run。不新增必需 Lifecycle 字段、TCAD RPC 或后置检查入口。
- Local `_execute` 使用冻结绝对截止，Popen 前再次看钟，循环不重新加完整 max_seconds。工程检查仍需原已确认成功，不改候选/原成功 CLI 码；未执行不是通过，也不是所有候选的否决门。已有检查 intent 无 outcome 仍 unknown，不重放。

## 已明确接受的启动边界

accepted 发布后、Popen 前耗尽 cutoff 会抛超时，保留既有 accepted/no-process unknown。Local.submit 在执行前已消费 fresh lease；后续无 lease 的 lookup/submit 只返回同 call unknown，不新派发，不伪造 run_id、completed、known_failed 或永久未提交证明。

此路径没有新增终态清阻保证，需保留原件供原合同维护；本轮不扩 local retirement 系统。轮询、退出清理和单次 IO/Popen 不构成硬实时保证，可能耗尽预留；实施账已如实披露。这是预留检查机会，不是保证每个 call 都完成检查，更不是新授权或远端 solver wall 修改。

## 负控是否能发现真实缺陷

- 四个小型 source/时钟测试固定原数值边界，能发现误加总时间、重算授时、错误缩短旧 accepted、伪称不支持适配器已预留、配置未冻结或非法数值被接受。它们核时间/合同，不冒充完整训练或真实超时进程验收。
- 既有短训练/缺 train-only 依赖回归 opt-in 12 秒，走真实 managed accept/公共 runner/隔离 leaf，核 accepted 分配及工程反馈；不是只手写成功 JSON 检查分配字段。其模型、数据和科学指标仍为小型 fixture。
- 新增启动前耗尽用例走真实 dispatch/submit，以时钟推进和 Popen 哨兵要求不启动进程；核无 process/terminal/completed、查询和两次重复 submit 仍 unknown、未启动 replay。若截止未作用于真实提交路径或重试再派发，会失败。

没有新增安装、环境矩阵或完整 cov 科学场。此前默认 0、工程失败不抹原成功、原 intent 不重放的独特断言保留。

## 检查与未验证范围

独立仅静态阅读冻结差异、原配置身份/lease/submit 直接调用链及限定 `git diff --check`，无报错。作者 AST 结果见实施账；独审未运行测试、收集、项目 import、CLI、模型、服务器、安装/build 或 solver，唯一写入为本报告。

root 后续验证应限定本节点 source 用例与受影响 process 用例；结果另记。真实调度延迟、长训练退出/清理、实际隔离环境和跨 boot 等不能由本静态 PASS 宣称通过；原软宿主边界及 A1 强隔离未具备的事实保留。
