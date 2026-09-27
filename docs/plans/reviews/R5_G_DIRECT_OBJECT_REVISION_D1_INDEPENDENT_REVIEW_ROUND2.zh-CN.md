# R5-G 直接完整对象修订 D1 第二轮独立实现审查

日期：2026-08-30  
审查范围：首轮 F1/F2 返工后的当前共享工作树精确候选  
审查者：未参与返工实现的独立审查者

## 结论

**打回。不得进入 D2。**

首轮 F2 已真实闭合：TCAD review-request 修订已从 Root `operation_invoke` 走到 Task/Worker、注册领域
调试工具、受控文件修改、重新预检、完整工程校验与封存；旧 review 不能用于新 project。返工发现的
旧 `preflight_attestation`/`materialization_report` 继承问题也确属工作区所有权错误，修复位于唯一
TCAD workspace materializer，未放宽 Root、Task、OperationSpec 或输出 validator。

首轮 F1 仍少两种**当前确实可编译**畸形声明的真实 Root 失败关闭证据：
`consequence="explore"` 和 `revision_base.max_items=2`。静态矩阵虽然把它们判为非直接修订，但真实
Root 循环只覆盖无 ReviewSpec、零 base 和双 base。首轮报告冻结的门是：迁移期仍允许编译的畸形
结构必须携带精确 `revise` 信号通过真实 Root preflight，证明没有获得免审。绿色全仓回归不能替代
这个尚未执行的门。

该剩余问题分类为**测试与冻结证据缺口**，不是生产架构或实现缺陷。最小修复不得修改生产代码。

## 阻断项

### F1-R2：两个可编译畸形结构未进入真实 Root 负例

证据位置：

- `tests/operations/test_general_science_plugin.py:249`—`362` 的静态总函数矩阵包含
  `exploratory consequence` 和 `revision base collection`，但它通过
  `dataclasses.replace(valid, spec=...)` 构造候选，只调用 `direct_revision_ports()`；
- 同文件 `:910`—`:974` 的真实 `unknown_revision_*` catalog/Root 循环仅含
  `no_review`、`no_base`、`two_bases`；
- 首轮审查报告 F1 明确要求所有迁移期可编译畸形形态经真实 Root preflight 失败关闭。

独立只读编译探针从同一未知插件声明派生候选，结果为：

- `consequence="explore"`：catalog 编译成功，`direct_revision_ports()` 返回 `None`；
- 唯一 base 的 `max_items=2`：catalog 编译成功，`direct_revision_ports()` 返回 `None`；
- 无 review、零 base、双 base 同样可编译并已被当前 Root 循环覆盖；
- 双主输出、主输出 `max_items=2`、Schema 或媒体不匹配在当前精确声明下由 catalog 更早拒绝。

因此当前静态谓词逻辑看起来正确，但没有证据证明前两种真实已编译 Operation 在
`revise` 旧对象上经过 `_prepare_operation_call` 与唯一 producer admission 时仍失败关闭。该缺口
不会授权向核心增加分支。

最小修复：

1. 把 `explore` 和 `revision_base.max_items=2` 两个 update 加入现有
   `unknown_variants` 真实 Root 循环；集合 base 用一个实际绑定仍应落入普通独立评审门，或增加
   合法基数绑定后证明同一门；
2. 断言它们均成功编译、`direct_revision_ports()` 为 `None`，并在精确 `revise` 信号下通过
   `operation_preflight` 返回 `input_independent_review_missing`；
3. 同步 D1 返工记录。不得修改 Root、TaskService、OperationSpec、catalog 规则，不得迁移 blind
   fixture 或 curve experiment。

## 已通过的返工核验

### 1. 未知插件边界与 D1/D2 分界

合法 `unknown_revision_valid` 会由结构总函数识别；静态非法矩阵没有 operation id、Schema 名、插件
名、角色名或端口名白名单。`unknown_revision_*` 只存在于测试源码，不在生产、安装 entry point 或
fixture 插件目录注册。blind producer fixture 仍使用旧 apply 链，curve experiment 和
`scripts/r5_g_science_chain.py` 仍保留旧 diff/receipt 消费者，说明返工未偷跑 D2。

### 2. TCAD 完整修订生命周期

`tests/operations/test_tcad_operation_plugin.py:1869`—`:2004` 真实验证：

1. 精确旧 project、精确 review、能力和实验计划通过同一 Root preflight/invoke 创建 revision Task；
2. Task 经 dispatch、claim 和 materialize，`deck_mode=revise`，Worker 可见
   `worker_tcad_debug_run` 与受控 patch 工具；reviewer 仍不可见调试工具；
3. 旧源码被复制到任务私有 workspace，旧控制证明不进入可编辑 metadata；
4. Worker 经受控 patch 修改 `main.cmd`，重新调用已注册 debug service，真实状态从 running 到
   succeeded，adapter 总提交数由一增为二；
5. 完整新 `tcad.deck-project.v1` 经 validator 与 finalizer 封存，内容包含修订，父链覆盖全部精确
   Task 输入；
6. 旧 review 与新 project 组合被 reviewed-package 的精确父关系 guard 以 `guard_rejected` 拒绝。

`guard_rejected` 的定性正确：该 Transform 的 RequiredParentage guard 在通用 producer admission
之前验证“review 必须直接审查当前 project”；旧 review 的 subject 是旧 project，因此精确父关系
首先失败。这不是资格放宽或异常码掩盖。

### 3. 控制证明所有权修复

`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:350`—`:358` 在已有 revision workspace
materialization 分支统一移除旧 `materialization_report` 与 `preflight_attestation`。条件来自既有
`_REVISION_OPERATIONS`，不按 solver 分支，因此同时适用于 review-request 和 runtime-failure 两个
TCAD 修订 Operation，也覆盖 SDevice/SProcess。新证明仍只能由注册 debug 工具写入 reports 并由
同一 finalizer/validator 合并；没有第二物化器、证明注册表、持久状态或 Root TCAD 特判。

这属于正确的架构所有权修复：旧证明绑定旧源码摘要，不能作为 Worker 科学内容继承。净增五行
保护已有不变量，没有形成复杂度反噬。

### 4. 指标与阶段边界

独立复算与记录一致：

- 生产 Python：143 文件、60308 行；
- `operations` 包：7 文件、2097 行，仍在 D1 临时上限内；
- Root 职责聚合：3146 行；TaskService 职责聚合：6221 行；
- 通用科学声明：959 行；确定性组件：1036 行，合计 1995 行。

未发现新增表、注册表、状态机、兼容 facade、核心领域分支或新的科学对象。D1 的临时旧协议重叠仍
明确等待 D2/D3 删除，没有把断裂转移成新的控制层实体。

## 独立复测

每条命令均串行运行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

1. 返工聚焦三项：`3 passed in 4.07s`；
2. `pytest -q tests/operations`：`270 passed in 90.98s`；
3. `pytest -q`：`307 passed in 95.17s`；
4. 受影响生产/测试文件 `python -m py_compile`：通过；
5. `git diff --check`：通过；
6. `scripts/r5_current_metrics.py`：产生上述 60308、2097、3146、6221、959、1036 指标。

完整回归说明候选没有已观察到的组合退化，但不改变 F1-R2 精确门尚未执行的事实。

## 再审边界

只允许补 F1-R2 两个真实 Root 负例并同步实施记录，然后重新独立复审。F2、生产修复、指标与
D1/D2 边界本轮已通过，不应再次扩大实现。复审通过前不得进入 D2。
