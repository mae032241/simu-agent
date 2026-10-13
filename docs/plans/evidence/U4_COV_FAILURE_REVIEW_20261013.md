# U4 cov 真实场失败独立诊断

状态：**FAIL，真实 H→W 生产链未完成验收**。本记录只读诊断冻结场景与已安装源码；独审未修改生产/测试，未运行测试、构建、恢复或模型，没有新增预算消费。此前 [launcher fresh-context 接缝 PASS](ROOTLESS_FRAGMENT_LAUNCHER_REVIEW_20261013.md) 仅覆盖无模型直接 W 启动，不可据此称本场或真实 H 搜索计划→W 链通过。

## 本场终态

场景原件位于 outer `.trial/rootless-u4-cov-20261013/`。

- [final-result.json](../../../../../.trial/rootless-u4-cov-20261013/final-result.json)：returncode=2、controller.status=`native_stopped`、completed_steps=1、goal_completion=`not_asserted`。自动错误重试、自动 correction acknowledgement、budget increase 均为 false；冻结输入未改变。
- H001 原 scientific output 与 result-identity 已封存，raw SHA256 均为 `20681fc332840e3f0d739bac9e3f62b3af527338456883c28731086cfa959804`。控制 receipt 为 current14、search_status=`applied`、无 diagnostics，focus=`h001.m1/screen`。H 原文声明四个新机制，首个 commitment 的 existing_ref 为 null。
- H [native-outcome.json](../../../../../.trial/rootless-u4-cov-20261013/instance/native-evidence/001/native-outcome.json) returncode=0、cleanup=`observed_group_cleaned`，存在 thread ID。H [usage.json](../../../../../.trial/rootless-u4-cov-20261013/instance/native-evidence/001/usage.json) input=207554、output=8085，因此 observed_tokens=215639；cached_input=175616 已包含在 input 内，不重复相加。
- W002 [native-outcome.json](../../../../../.trial/rootless-u4-cov-20261013/instance/native-evidence/002/native-outcome.json) returncode=1、thread_id=null、cleanup=`observed_group_cleaned`、usage_observed=false。W 无 science-output、usage.json 或 pending 输出；全场无 accepted experiment 原件。控制总用量保留 unknown_steps=[2]，不把缺失 W meter 当作已验证零用量。
- W 故障发生在 launcher 调用实际 native 可执行文件之前；未进入 W 模型线程或实验提交。因此本场未验证真实 worker fragment、soft review、A 复核、提交交付或科学目标完成。

## 已确认的生产根因

[W native.stderr](../../../../../.trial/rootless-u4-cov-20261013/instance/native-evidence/002/native.stderr) 给出完整路径：

```text
rootless_cov_launcher.main
  → cov_lineage.configure
  → lineage.build
  → search.apply_source
  → search.interpret
  → search._apply_science
  → state['order']['remaining'].append(...)
KeyError: 'order'
```

1. `controller.prepare` 的 current14 合同已退役 `exploration_order_version`；提供非 null 值会拒绝。实际 settings 中 handoff_protocol=14、search_policy 启用、该旧 flag 缺席，符合当前合同。
2. `lineage.build` 第99行仍仅在旧 flag 等于1时调用 `search.fold`。当前合同下不会走该初始化；第101行的旧 fallback state 没有 `order`。
3. `cov_lineage.configure` 第358行直接调用 `lineage.build(root, step)`，不传 search_state。进入 W002 时有 H001 的 sealed source，且 search_policy 非 null，因此 build 第106行把缺 `order` 的 fallback 传给 `search.apply_source`。
4. `search.interpret` 复制这一显式传入 state；H 的新 commitment 在 `_apply_science` 第95行首次访问 `state['order']['remaining']` 时失败。即使没有新增 commitment，当前意图解析随后也依赖 order，旧 fallback 并非 current14 合法 search state。
5. `search.fold` 本身已初始化 current order：remaining、seen_w、allocation、diagnostics。`lineage.project` 也按当前 search_policy 调用 fold 并把其 state 传入 build。缺口是直接 build 的旧初始化分支，属于旧协议退役后的生产调用接线遗漏；不能将其归为模型输出格式失败或环境偶发故障。

独审核对实际 wheel05 安装文件与仓库字节一致：

| 模块 | 实际安装及源码 SHA256 |
| --- | --- |
| lineage.py | `5aedd40334c139baec4a8dce4fb7251f2e2d3d95f5d1e12a0e63d97330647b09` |
| search.py | `c58d76fcfdc1e8f38287987e6b73e72a4b0522dbd0873b99cd6990fa72542f9b` |
| cov_lineage.py | `0f23600914e9629c381ad8d7aac6dd8a3b4f81a3727558d32687616b8cc73036` |

## 为什么先前门禁没有覆盖

实际 namespace 测试 `test_rootless_fragment_namespace.py` 显式 `search_policy=None`，并直接创建无 parents 的 W001。首次 configure 的 history sources 为空；第二 context 仍是同一未 stage-seal 的 W001，before_step=1 也没有此前 sealed H。两次都不会调用 search.apply_source，缺 order 的 fallback 因此未被访问。

该测试确实经过真实 generic runner→launcher.main→prepare_home/outer/bwrap，并证明同 job 两 fresh contexts、一次 registered cov 提交与查询原 call；这些机械接缝结论成立，其资格未包含 H 搜索计划重放。通用 fake H→A→W→A 的科学路由门禁与真实 cov launcher 配置门禁分别通过，也不能替代二者串联的实际安装路径。本次真实场揭示了此前未覆盖的串联边界，不能继续使用旧 PASS 作为整场授权依据。

## 收口与证据绑定

- 本场停止于 W002 原 native intent；[runner.stderr](../../../../../.trial/rootless-u4-cov-20261013/instance/native-evidence/002/runner.stderr) 明确保留未验证终态、禁止重放。原 H 科学结论和 W 失败原件保持，未知用量不被补成成功。
- 本次只诊断，不修复、不回填旧 flag、不重跑 H、不恢复 W、不增加预算。后续若授权修复，应在无模型的安装入口覆盖「current14、search 启用、合法 sealed H 新机制→实际 cov configure/launcher W」这一遗漏路径，资格仍须由实际运行结果取得。
- 最终原件 SHA256：final-result=`c26e070accd152b6568adcbfa3f804ff18a3b24dc2545233f0c75a6911d3b181`；controller-result=`226ac5f4b51e30d1394f3077bdc08d1430dcd49b1b51b44b5d282c4442475b5a`；settings=`a305fc9ead679720299e4393c7cee47271df3e8644dbce7e880011cbfb3cab0d`；H result-identity=`5eea17faedd3e491700b821dda49400cc80630bd7ddcfd4ec93a1db931e2614c`；W native-outcome=`63517ed2cfa9ea2e7aa4fdac8bc1c528c7dc1d74949d3f437c050a80a4f9c407`。
