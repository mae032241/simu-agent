# R5 E5 完整确定性生产族契约独立实现复审

日期：2026-09-05

结论：**PASS**  
阻断项：**0**  
放行范围：**允许重新生成发布包、部署 ABI 15 并重新执行真实 E5 正反例；本结论不代表 E5 已完成。**

## 1. 审查范围与基准

本次只审查已批准的
`R5_PRE_E2E_E5_FAMILY_COMPLETENESS_ASSESSMENT.zh-CN.md`、实现记录，以及下列精确相关边界：

- `src/scidiscovery/operations/spec.py`
- `src/scidiscovery/operations/catalog.py`
- `src/scidiscovery/operations/__init__.py`
- `src/scidiscovery/operation_declaration.py`
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`
- `plugins/curve_score/curve_score/figure_science_operations.py`
- `tests/operations/test_catalog_compile.py`
- `tests/operations/test_m2_optional_figure_plugin.py`
- `tests/operations/test_m5_figure_review_closure.py`

仓库当前包含大量早期未提交改动，不能把相对 `HEAD` 的全仓差异冒充本次 E5 差异。生产源码的精确
变化通过当前工作树与真实安装态 `/opt/scidiscovery-m7/site`（ABI 14）的逐文件比较确认；测试变化按
本次新增断言及其可达生产路径审查。未审查或修改 UI、部署协议、Hardened 后端、E4 既有问题和其他
裁剪工作。

## 2. 主要结论

### 2.1 OperationSpec 是唯一合同来源

新增事实只有 `OperationSpec.complete_transform_family`，值类型只包含 `output_ports` 和
`input_ports`。图插件仅在 Intake 与 Audit 两个消费者上声明同一不可变值；生产者没有声明下游
用途。目录的 public/all 投影直接读取该字段，Root 也直接读取 `bound.compiled.spec`，没有新增名单、
注册表、数据库事实、状态或领域分支。

这满足 `AUTH-003`、`PLG-001/002` 和奥卡姆边界。合同没有吸收到既有
`InputAdmissionSpec`，因而没有改变其 all-or-none 或审批语义。

### 2.2 编译期约束足够且保持最小

`CompleteTransformFamilySpec.issue()` 拒绝空集合、非法名称、重复和输入/输出交叠；目录编译器还
要求所有名称引用消费者自身的真实输入端口。生产者身份由运行时所绑定 Artifact 的冻结标签推导，
编译期没有引入显式生产者列表或领域依赖。

非法端口的目录编译负例通过。对于当前单生产族需求，不需要新增多族、版本选择、选择器或资格字段。

### 2.3 Root 只读复用既有生产族恢复

`operation_preflight` 与 `operation_invoke` 都先进入同一个 `_prepare_operation_call`，再进入同一个
`_validate_operation_input_admission`。新增校验只调用已有 `_transform_output_family`、
`_validated_transform_members` 和 `_transform_input_groups`：

- 由生产操作摘要、版本、调用指纹、父链和实例绑定恢复完整确定性输出族；
- 按生产输出端口比较等长引用集合，不能以一个成员替代变长完整集合；
- 按生产输入端口精确比较父链顺序；
- 未声明合同的消费者立即返回，不被强迫读取 sibling。

校验不读取 manifest 或曲线 payload，不解释科学内容，也不创建 Run、Artifact、Approval、current 或
收据。调用路径在任何创建动作之前再次执行同一校验。因此符合 `CQRS-001`、`TOP-002`、
`ROLE-001/002`、`DET-001/002` 和 `RES-001`。

### 2.4 正反例及零写入

聚焦测试证明：

- 同一次物化的五个输出端口及两张曲线表完整绑定时，Intake 和 Audit 均可通过；
- 缺一张变长曲线表在 preflight 失败，invoke 写前复核也失败；失败前后 Run/Artifact 绑定数量不变；
- 替换为另一独立来源、另一请求或混入另一调用成员均在 preflight 失败；
- 未声明该合同的通用证据提取仍可合法只消费单个 source panel；
- public/all 目录投影与 OperationSpec 中的合同完全一致。

后三类负例没有逐一重复 invoke 的计数断言，但不是不同实现路径：所有 invoke 在进入任何 executor 或
创建函数前都会重新调用同一个 `_prepare_operation_call`，而该函数中的生产族读取全部为只读。已有
缺成员 invoke 零写入负例已覆盖该共同边界，因此这不是放行缺口。

### 2.5 ABI 与审批语义

Operation ABI 已从安装态的 14 明确提升到 15。新增字段参与现有 `CompiledDigestEnvelope`，因此合同
变化会改变操作摘要，旧代际 Artifact 不会被当前生产者合同静默接纳。实现没有改变审批身份、审批
选项、后果、review edge 或 Approval projector；图 Intake/Audit 原有角色和独立审查关系保持不变。

这一代际变化是共享 OperationSpec 形状变化所需的显式 ABI 变化，不是隐藏兼容补丁。真实 E5 必须在
重新部署后生成同代际请求与物化族，历史对象保持不可变。

## 3. 独立检查证据

低内存、无 xdist、禁用第三方 pytest 自动加载：

```text
ulimit -v 4194304
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_figure_review_closure.py
```

结果：`25 passed in 2.56s`，进程最大常驻内存约 `104348 KiB`。

```text
ulimit -v 4194304
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_agent_contract_alignment.py
```

结果：`12 passed in 0.95s`，进程最大常驻内存约 `85384 KiB`。

`git diff --check` 未发现已跟踪差异的空白错误。仓库未提供
`scripts/validate_architecture_constraints.py`，因此未把该不存在的命令计为通过；本次改动也没有修改
33 项约束清单或状态。

## 4. 残余非阻断风险

1. 当前值合同有意只支持一个完整 Transform 族。没有真实多族消费者前不应预先扩展。
2. 运行时从 `output_ports` 的首端口取锚点；当前两个声明都以必需、单项的
   `figure_manifest` 为首端口，因此本轮没有可达缺陷。将来若复用于首端口可为空的生产者，应改为从
   任一非空声明输出取锚点，或在编译期明确禁止该声明；本轮不应为不存在的用例扩张实现。
3. 本复审是源码与内存运行时证据，不替代 clean wheel、真实 systemd 入口和实际 Fig.4 E5 重跑。
   ABI 15 尚未部署，因此当前活动服务不能作为本实现的运行证据。

## 5. 最终判断

实现与批准的 B 方案一致：消费者声明需求，核心只机械验证不可变元数据，普通消费者不受影响。未发现
完整族旁路、第二事实源、隐藏写入、审批语义漂移、领域硬编码或不必要的新控制实体。**阻断项为 0，
独立复审通过。**
