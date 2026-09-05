# R5-G 直接完整对象修订 D1 第三轮独立实现审查

日期：2026-08-30  
审查范围：第二轮唯一阻断 F1-R2 的最小返工及 D1 已通过边界  
审查者：未参与返工实现的独立审查者

## 结论

**通过。只放行 D2。**

第二轮唯一阻断已经按精确最小边界关闭：`consequence="explore"` 和
`revision_base.max_items=2` 两种畸形声明都由未安装的未知插件完整经过 `compile_catalog()`，编译
后的 Operation 均未被 `direct_revision_ports()` 识别；在同一精确 `revise` 审查信号下，真实 Root
`operation_preflight` 均返回 `input_independent_review_missing`。它们没有获得直接完整对象修订的
免审资格。

返工只修改测试和实施记录。未发现生产代码、ABI、目录摘要、持久状态或 D2 消费者变化。首轮 F2
的 TCAD 真实修订 Worker 生命周期和控制证明去继承修复仍成立。

## F1-R2 闭合核验

### 1. 候选经过完整未知插件编译

`tests/operations/test_general_science_plugin.py:910`—`:951` 中，新增的两个 variant 与原三种畸形
声明进入同一个 `_unknown_direct_revision_catalog()`。该 helper 会：

1. 从公开科学插件的完整修订 OperationSpec 派生替换声明；
2. 把插件身份改为测试专用 `unknown_revision_<suffix>`；
3. 调用 `compile_catalog((BUILTIN_PLUGIN, plugin))`；
4. 从编译结果重新取得 Operation，再断言 `direct_revision_ports(...) is None`。

因此两种新增候选不是通过 `dataclasses.replace()` 伪造的不可达 `CompiledOperation`。文件前部的
静态总函数矩阵仍用于覆盖更完整的结构集合；本轮新增路径则专门证明两个当前可编译形态的真实
组合行为。

### 2. 真实 Root 失败关闭

同文件 `:952`—`:986` 为每个已编译未知 catalog 新建 `RootMCPRouter/RootToolFacade`，绑定同一个旧
intake、精确 change request 和冻结来源，并在 TaskService 的精确 review 输出上投影
`SchedulerSignal(verdict="revise")`。

两个新增 variant 的结果均为：

- catalog 编译成功；
- `direct_revision_ports()` 返回 `None`；
- Root `operation_preflight` 返回 `admissible=false`；
- `reason_code=input_independent_review_missing`。

`explore` 不会因 claim-admissibility 的探索语义绕过 producer-output admission，因为唯一 producer
admission 先执行；集合 base 以一个合法基数输入到达相同路径，也没有被错误视为单值完整修订。
核心没有新增 operation id、Schema、插件、角色或端口名分支。

## 已通过边界的未退化复核

### 1. TCAD F2 与控制证明所有权

`tests/operations/test_tcad_operation_plugin.py::test_registered_tcad_author_debug_and_reviewer_lifecycle`
再次通过，仍真实覆盖：

- `tcad.deck.author.revise.v1` 的 Root invoke、Task dispatch/claim/materialize；
- 修订 Worker 获得注册的 `worker_tcad_debug_run` 和受控文件工具，reviewer 不获得调试工具；
- `deck_mode=revise`、源码 patch、重新提交并收集 fake debug run；
- 完整新 `tcad.deck-project.v1` validate/finalize 和全部精确输入父链；
- 旧 review 对新 project 以 `guard_rejected` 失败关闭。

`plugins/tcad_artifact/tcad_artifact/operation_workspace.py` 仍只在既有 revision workspace
materializer 中移除旧 `materialization_report` 与 `preflight_attestation`，条件覆盖两个 TCAD 修订
Operation 且不按 solver 分支。validator、Root、TaskService 和 OperationSpec 未被放宽，也没有
第二证明或物化权威。

### 2. D1/D2 与复杂度边界

生产/动态入口中没有 `unknown_revision` 命中；测试专用声明未安装。blind producer fixture 仍保留旧
apply 链，curve experiment 和 R5-G 评估脚本仍保留旧协议消费者，说明没有偷跑 D2。

独立复算仍为：

- 生产 Python：143 文件、60308 行；
- `operations` 包：7 文件、2097 行；
- Root 职责聚合：3146 行；TaskService 职责聚合：6221 行；
- 通用科学声明：959 行；确定性组件：1036 行；
- `OPERATION_ABI_VERSION` 仍为 7。

未发现新表、注册表、状态机、目录、兼容 facade 或领域核心分支。该修复用两个已有循环项关闭测试
证据，不增加生产复杂度，符合奥卡姆原则和 D1 的轻控制面目标。

## 独立复测

每条命令均严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

1. 两个通用聚焦测试加 TCAD lifecycle：`3 passed in 3.72s`；
2. `pytest -q tests/operations`：`270 passed in 90.94s`；
3. `scripts/r5_current_metrics.py`：上述 60308、2097、3146、6221、959、1036 指标一致；
4. 修改测试 `python -m py_compile`：通过；
5. `git diff --check`：通过；
6. `rg unknown_revision` 在生产、部署、安装配置和测试 fixture 中无命中。

第二轮审查已在相同生产候选上独立运行全仓并得到 `307 passed in 95.17s`；本轮只新增同一既有测试
函数的两个 case 和实施记录，当前全 Operation 回归重新通过，因此没有为仪式重复第三次全仓。实现
方报告的当前 `307 passed` 与这一证据链一致，但不等同于真实 solver、浏览器或科研 Agent 验证；
这些不属于 D1 完成门。

## 放行边界

只放行计划中的 D2“迁移最后生产消费者”。不得据此提前删除旧补丁协议、宣称 D3/R5-G 完成，
也不得跳过 D2 完成后的独立审查。
