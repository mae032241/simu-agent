# Fig.4 真实接续验收（2026-09-15）

后续工程进展：案例锚点丢失已完成源码修复、独立复审和安装产物定向验证，尚待部署后的真实续接。详见 [修复验收](CASE_ANCHOR_REPAIR.zh-CN.md)。下文保留当时观察到的原始阻断。

状态：角色配置与受控接续已实际验证；科研推进至新单案例计划和源码均独立审查通过，执行包生成被控制层缺陷阻断，未开始生产仿真。

- 实际作者和独立审查者均使用 gpt-5.6-sol / medium，平台元数据见 AUTHOR_PLATFORM.json、REVIEW_PLATFORM.json；新封存报告为中文。
- 原双案例实现经独立审查发现无法兑现案例间外部门槛；修订者提交 implementation_gap，Run 正常 completed，没有占位代码。精确缺口随后绑定到新设计。
- 新设计采用单入口非线性首步任务，保留 Fig.4 后续目标；正式方案 fig4_single_entry_initialization_plan_2 和实现 fig4_single_entry_nonlinear_author_1.output 均通过独立审查。科学内容应从实例封存结果读取，本文件不是研究 checkpoint。
- 同一编译 Operation、相同已知模型/强度的空闲作者和实现审查者分别复用；均创建新 Run、重新 worker_open_assignment。新单案例作者没有拒绝或超时。

## 阻断与诊断

1. 初始作者调试的一次枚举错误产生两个拒绝事件，其中一个详细、一个为空；不能当成两次独立失败。详见 RUN_ACCEPTANCE.json。
2. 新设计有五次结构拒绝，涉及 baseline、cases/variables 和 engineering objective，最终同一 Run 提交成功。是否所有限制均有必要尚未完整审计。详见 DESIGN_ENGINEERING_EVENTS.json。
3. 工程计划生成器公开可选科学背景输入，preflight 放行，却在 transform 中拒绝非 intent 输入。改用只绑定 intent 的新请求成功；原目标继续明确绑定给下游审查。第一次错误还被 Root 本地 JSON 解析假设遮蔽，随后保留原始 MCP 文本并读取完整诊断。
4. **当前阻断**：project_materializer.py:404 仅针对 comparison variables 生成 case_parameter_bindings；本轮合法单案例没有变化参数，因此此列表为空。transform_adapter.py:163 从该列表反推所有 case_anchors，导致打包重建丢失已经验证的源码锚点，再被 project_materializer.py:338 拒绝。原始源码锚点确实存在，作者 materialization_report=pass，两个部署文件 SHA-256 与仓库相同，排除安装版本不一致。详见 PACKAGE_BLOCKER.json。

最小修复方向：让控制层独立保存并复用已验证的案例源锚点，避免从参数变化列表推断案例是否存在；兼顾模板复用和旧对象处理，增加“单案例且无变化参数，从作者物化到打包”的定向回归。不要要求设计者添加虚假比较参数，不要让作者再次机械登记。需要完成修复与部署后，才能从已封存计划和源码继续。

本轮未修改框架源码，未启动全量测试，未申请或绕过生产仿真审批。尚无新的 Fig.4 拟合结论。
