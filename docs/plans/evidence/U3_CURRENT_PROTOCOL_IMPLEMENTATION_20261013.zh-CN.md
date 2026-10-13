# U3：当前科学协议、意图解析与条件复核

状态：开发、源码/安装无模型验收与独立审查PASS；U4未授权。

## 范围

基于U1 `9d81262`、U2 `285cc35`，统一当前科学合同并启用W片段接缝。H/A表达科学选择及理由，不要求自行维护priority队列或计算消费后的队首；控制层单次解析意图，用同一结果生成准入、绑定与展示。

正常W片段可以继续，原预算/复核请求优先；科学阶段结束后才进入A，片段与native/output repair不重复算科研周期。机制repair保留全部A原判断和实际用量，沿原机会资格只完成一次，不新增计数账本。

旧实例归档只读，不迁移、不复用预算，不执行旧协议。当前写入口在锁、预算或外部调用之前拒绝旧合同。归档显示保留有界读取及遗漏说明，不把部分用量当作完整总量。

## 验收证据

- 首批协议/纯意图：37通过、1失败；合法只读归档CLI返回码错误，已修复，写拒绝不放宽。
- 首次安装入口暴露validate清理旧分支时留下无条件raise；即便存在控制回执也拒绝封存。改回仅缺回执时拒绝，没有强开search策略掩盖。
- 第二批工程集成：120通过、10失败、1不适用。7项分段失败来自host身份三处手工构造不同步；统一protocol.stage_scope供四处调用。另3项更新旧fixture为当前科学字段/当前拒旧异常。
- production04/source04工程5文件：130通过、1不适用（36.78s）；同版安装5文件130通过、1不适用（34.81s）。源码日志`.trial/u3-source-04-20261013/batch-001/pytest.log`，安装`.trial/macro-role-installed-20261012/artifacts-u3-04-20261013/u3-installed.log`。
- source05科学路由首批5通过、2失败（1.86s）：新测试直接把controller六元路由传给需要correction_request的七元semantic入口，属于测试调用未对齐真实入口；修正夹具拼接，不放宽生产合同。
- freshwheel04实际CLI假H→A→W→A及重启不重放PASS，29模块SHA核对；显式关闭search的基础链仅证明安装/路由/封存，不能替代科学计划分配测试。

- 最终production05/source06：科学路由8项、W片段20项、当前协议38项，共66通过（24.33s）。科学路由默认分配、带理由换向/深挖、E返回、A→H修订、repair原机会去重、控制错误不冒充作者补正均已覆盖；未配置续接时原科学字节不改、转A原因可见、不消耗作者补正。日志`.trial/u3-source-06-20261013/batch-001/pytest.log`。

独立实施、独立审查、父级串行测试/build/git；所有native均为无模型夹具，没有真实模型场或隐藏评分。最终独审结论见[独立审查记录](U3_CURRENT_PROTOCOL_INTENT_REVIEW_20261013.md)。

- 最终freshwheel05：实际安装CLI假H→A→W→A、重启不重放PASS，29模块源码/安装SHA核对，模型请求0。wheel SHA256：`f71d793a28fc942d41432c3e8c45eeed190790fdc74524c5ce0cbe67547eeab9`；证据`.trial/macro-role-installed-20261012/artifacts-u3-05-20261013/result/result.json`。
- source07补充实际A任务question断言；同production05安装六文件135通过、3失败、1不适用（35.61s），科学路由8项均通过。3项控制器mock未提供当前封存control_outcome；修复仅补齐mock回执，生产不放宽，保留原失败日志`artifacts-u3-05-20261013/u3-installed.log`。

- source08仅补控制器mock两处中性回执；同一wheel05定向安装复验`test_controller.py`46通过（2.84s），日志`artifacts-u3-05-20261013/u3-controller.log`。合并前次未改动通过项，最终六文件覆盖138通过、1不适用；这是差量验收，不声称重新全跑一次。全部生产仍是production05，`git diff --check`通过。

## 能力与限制

CURRENT14新实例只冻结已配置能力。`--worker-context same_session|new_context`还需`--worker-resume-policy`与`--node-budget-policy`；每次接续重新核验原线程/session、旧执行终态与清理、用量及共享预算。未配置时W的任务明确显示unavailable；若仍返回continue，保留原科学输出并记录控制结束原因后转A。

旧协议在途作业仍由原冻结owner和原运行环境负责采集/清理，本步不提供跨包在线迁移；归档只读不代表旧作业已完成。

无模型进程门禁不证明真实Codex同session恢复、科学搜索效果或成本收益。旧协议仅保留有界status及已有原件/页面读取，不迁移，不补建投影，不宣称历史export资格。当前入口拒绝旧协议写入；旧安装包和任意原生shell不在该入口保证内。TCAD实际远端执行、U4真实模型场与原生对照均未运行。
