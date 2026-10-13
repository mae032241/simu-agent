# 科学决策请求与同线程输出修复独立审查（2026-10-13）

状态：**独立审查 PASS，无剩余阻断**。审查者仅只读检查并写本报告，未运行测试、构建、模型或提交，未读取独立隐藏评分，未修改真实实例。

## 审查结论与限制

显式 `prepare --decision-contract` 冻结协议10；旧 settings 无标记及已有协议1..9 对象不升版。A 的 nullable `decision_request` 是科学决定、问题与改判条件，不含模型填写的路径/哈希。缺项与确定重复保留原 science seal，通过现有最多两次作者 A 补正阻止依赖研究派发；未解决的 A 不进入 N4 科学计数。

重复判据限 trim 后相同请求/action、既有机制/候选上下文与没有新增绑定原件 proof；此前请求必须 applied，并实际得到直接绑定的 W/H/E 封存响应。作者 A 自身、未执行请求不算依赖完成。新的负结果可以提供 proof，raw 复制/别名不增加 proof；无 search 不制造机制。**本实现不识别换措辞的语义重复，也不识别“有新产物但没有科学价值”的重复，不裁判科学价值或改判条件真伪。** 必要检查、预承诺、审计及原用户数量要求保留，不因目标仍 unknown 每轮强制 H。

JSON/字段类型/空内容/已知终态缺输出单独归类为 typed 输出修复。仅原冻结 resume policy 的 `output_repair:true` 可接受同 session/home/workspace/node 的 continuation attempt；不新建科学工作者或科学节点，不重复提交已知工作。新 attempt 的本地进程仍由原 runner 机制启动，累计用量、时间、步数和最多两次总额度不重置。无原 session、不足额度、未知执行或清理不明均不走 fresh fallback。科学 null/blank 请求则沿作者 A 补正，不混为格式修复。

raw/task/schema/input 身份及已观测用量守卫先于格式修复；仅捕获明确 typed 错误，I/O 和完整性错误不软化。ordinary restart、closeout 已知终态和非 export 收集统一 helper；纯 export 不派修复模型。旧冻结角色字面保持，未授权旧 policy 不自动修复成功坏输出。

## 发现关闭

- 指引压缩一度丢失“未经审计选择承诺前先审计”职责，已恢复，并将 recommendation 的审计含义限定到 audit 动作。
- 无条件目标缺口回 H 会重复绕 H；已限定当前机制之外的缺口，保留机制内 W 探索。
- retained 终态及 missing 输出初版未接同线程 helper；已统一入口并收紧 known missing 判断。
- 原坏 raw 在续接 Popen 后、最终 seal 前的变动初版未重核；成功 continuation 现在逐链验证所有 repair source。低层重核不递归执行科学投影，真实 admission/Popen 和封存仍各自核原科学输入。

## 验证证据

联合冻结为 `/tmp/scid-decision-output-freeze-20261013/manifest.json`，SHA `357a4883340705f3eb9ce8c075b92b1322935ba065a053edeb43c463059a47f5`，15 个源码/测试文件最终逐项 SHA 已核。父级串行源码门禁覆盖 262 个不同用例，分批完成，不宣称单次全绿：resume49、decision10、schema12、semantic26、controller46、correction40、authority6、scientificguide12、decisionguide5、closeout13、budget24、softadmission7、softnode12。

初门禁的新 repair fixture 缺 host-started，未进入待测路径；预算不足 fixture 随后修正为已知初次完成后显式减少额度、拒新 continuation。旧 schema/controller 分类断言改为 typed code 和 output_repair_required，同时保留错误输出不封存、无未授权 continuation/重派断言。失败过程未丢弃，不将它们改判为成功。

最终安装证据在外层 `.trial/macro-role-installed-20261012/artifacts-decision-repair-20261013`：已亲读 `decision-repair-installed.log` 的 **64 passed / 29.55 秒**（49 resume、10 decision、5 guidance）及结果里的 site-packages 原模块绑定；实际 CLI prepare 的标记1/H protocol10 已核。默认 H-A-W-A 路由与重启无重放验证 PASS；不将该默认路由误称协议10全流程实模型验证。`result/module-bindings.json` 的 22 个当前源码 SHA 全部匹配。wheel SHA `726dd4b301698ceb7a860effb4a4c53444d2bb961b963f9ea8c4c34629164d94`。

以上为 fake process 与无科研模型回归，不是付费原生服务续接或权限资格证明，也没有科学改善证据。完整实现、分批日志与验收记录见 [实施记录](ROOTLESS_DECISION_VALUE_GUIDANCE_20261013.zh-CN.md)。
