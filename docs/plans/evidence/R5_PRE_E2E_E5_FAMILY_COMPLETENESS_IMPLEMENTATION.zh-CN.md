# R5 E5 完整确定性生产族契约实现记录

日期：2026-09-05

状态：实现与聚焦测试完成；独立复审 PASS，阻断项 0。允许重新部署 ABI 15 并继续真实 E5，
不代表 E5 已完成。

## 1. 现场缺陷

真实 Fig.4 物化调用登记了两张 `curve_tables`，但图 Intake 只绑定其中一张时，普通端口基数
`min_items=1,max_items=32` 仍会让预检通过。OperationSpec 没有表达该消费者需要同一次确定性
调用的完整输出族及其精确输入父链。

## 2. 最小修改

- Operation ABI 从 14 升为 15；`OperationSpec` 新增一个可选、单族
  `complete_transform_family` 值合同，仅含 `output_ports` 与 `input_ports`。
- 编译器只检查合同名称合法、集合非空不重复、不交叠并且均引用消费者自身的真实输入端口。
- 调度目录直接投影同一合同，不建立第二注册表或隐藏名单。
- Root 的共享 `preflight/invoke` 准入路径复用已有 `_transform_output_family`、
  `_validated_transform_members` 与 `_transform_input_groups`：
  - 从冻结标签、Operation 摘要、调用指纹和实例绑定恢复一次 Transform 的完整成员；
  - 按同名生产输出端口比较等长引用集合；
  - 按同名生产输入端口比较精确父链；
  - 任一不一致统一返回领域无关的 `input_producer_family_mismatch`。
- 只有 `science.evidence.extract.figure.v2` 与
  `science.figure.evidence.audit.v1` 声明该要求。未声明的 Operation 行为不变。

未新增数据库、状态机、收据、资格、审批、领域分支、图像清单解析或 family 注册表；未修改生产者
Operation、`InputAdmissionSpec`、UI、Hardened 后端和最终曲线包 guard。

## 3. 测试证据

受影响边界串行测试命令：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
ulimit -v 4194304
python -m pytest -q \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_l2_local_run.py
```

结果：46 项通过；最大常驻内存 106016 KiB；无交换。

已覆盖：

- 完整的两表生产族通过；
- 缺少一个变长 sibling 在 preflight 与 invoke 均失败，失败前后 Run/Artifact 绑定数量不变；
- 替换独立来源、替换独立请求、混入另一 Transform 调用均失败；
- 图审计同样拒绝缺表；
- 未声明完整族要求的通用证据提取仍可只消费一张 source panel；
- 非法消费者端口引用在目录编译时失败；
- public/all 目录展示的合同与 OperationSpec 相同。

## 4. 部署影响

ABI 和使用该合同的 Operation 摘要均已改变。历史 Artifact 保持不可变，旧生产者摘要不得绕过
`input_producer_contract_changed`；继续 E5 前必须重新安装并重启服务，再以有意修订/新调用生成
同代际请求和物化输出族。

独立复审通过后已生成干净发布目录与归档：

```text
deliverables/r5-pre-e2e-e5-abi15-clean-release/
deliverables/r5-pre-e2e-e5-abi15-clean-release.tar.gz
```

发布目录包含 240 个清单化源文件。使用真实 M7 workspace、四插件组合、8765 端口和既有 TCAD
adapter 的安装前 `--dry-run` 已通过；最大常驻内存 48620 KiB，未修改包、状态、服务或平台配置。
