# R5-B 领域无关审批生产者族独立复审

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-B 候选  
结论：**打回**  
门禁决定：**不放行 R5-C**

## 1. 审查范围与精确对象

本轮未参与 R5-B 实现。审查完整遵循 `scid-cross-boundary-review`、
`scid-find-simplifications` 和 `scid-change-scope-checks`，从 CompiledOperation、Transform/Agent
产物、Task 完成合同、Artifact 父链和实例 binding 一路追踪到 Approval projector 与唯一
ApprovalService。没有修改生产实现、测试、计划或阶段状态，唯一写入是本报告。

工作树仍是相对 `baseline/8765-codex` 的大范围未提交 R1—R5 候选，没有可单独比较的 R5-B
提交；因此本结论只约束审查时的精确字节。关键摘要为：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `2738490ee94e857f859b5df89f8e14cda49d2af435f8a231067696cdffea276d` |
| `src/scidiscovery/operations/invoke.py` | `0a54429982e11a795d8457cbedd1eb627a704b0bd49c55f7d8fd110381c77ffe` |
| `tests/operations/test_r5_blind_producer_family.py` | `a82d5d97e29c5ecb9d32aec9fcbca3d00b0e00afd2385164d2babcf11394caac` |
| 盲插件 `plugin.py` | `b60ce4272d42508ba0472217095daff3e09b57eb431f6ca261366a2bbd35c74d` |
| `R5_B_GENERIC_PRODUCER_FAMILY_IMPLEMENTATION.zh-CN.md` | `3ea26625afbb4c836a795b9f6245eeeb88db672b01f4dc7ea92c6ffa6c74d6a0` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 3、6 节 |
| S2 | `R5_B_GENERIC_PRODUCER_FAMILY_IMPLEMENTATION.zh-CN.md` |
| S3 | `mcp_root.py`、`operations/invoke.py`、Task/Artifact/binding 生产实现的上述精确字节 |
| S4 | 盲插件声明、runtime projector、R5-B 与既有审批拥有者测试 |
| S5 | 本轮独立串行运行的 42 项审批/盲插件/clean-wheel 测试和静态扫描 |
| S6 | 本轮使用同一盲插件组件构造的“主对象与附件共享 Schema”真实链路反例 |
| S7 | 当前架构、三项审查技能及 `r5_baseline_metrics.py` 结构结果 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `core_domain_neutrality` | 通过：Root 解析区无固定端口、Operation、插件、角色或 Schema 分派 | S1、S3、S5 |
| `agent_family_closure` | 通过：完成任务、当前 authority、主输出与全部集合合同共同还原族 | S3—S5 |
| `transform_family_closure` | 通过：编译身份、调用指纹、顺序父链、实例 binding 和全部输出共同还原族 | S3—S5 |
| `revision_primary_binding` | **不通过：附件可被当作 revision base，随后被错误提升为主对象修订族** | S1、S3、S4、S6 |
| `identity_and_deduplication` | 通过：同族多 subject 去重，同身份异成员失败关闭，异指纹不合并 | S3—S5 |
| `bounds_and_isolation` | 通过：端口/集合基数、递归深度、visited、跨实例、缺指纹和摘要漂移均关闭 | S3—S5 |
| `unknown_clean_wheel_plugin` | 通过：只由测试安装环境加入夹具包，生产 Root/Task/UI/安装器无盲插件命中 | S3—S5 |
| `approval_lifecycle` | 通过：仍复用唯一 ApprovalService、ReviewDocument 和 UI 决定生命周期 | S1、S3—S5 |
| `occam_and_constraints` | 部分通过：无新表/注册表/状态机；但错误修订父链违反精确谱系约束 | S1、S3、S6、S7 |

## 3. 阻塞发现

### F1（阻塞）：修订基线不必是原生产者族主对象

位置：`mcp_root.py` 的 `_revision_transform_family()`，尤其当前第 1786—1806 行。

当前算法正确验证了：修订 Transform 有唯一 `usage=revision_base` 和唯一
`usage=change_request`；patch 来自当前编译 Agent 主输出；patch 的 `revision_base_port`、Task 输入
和目标 Schema 都精确指向 Transform 的同一 base。随后它递归解析 base 的生产者族。

缺失的最后一个条件是：

```text
base_envelope.ref == base_family.primary_ref
```

代码没有检查这一点，而是无条件构造：

```text
新 Transform 主输出 + base_family.members[1:]
```

并把实际选择的 `base_envelope.ref` 写成 `base_primary_ref`。如果原生产者的主对象和一个集合附件
共享同一 Schema，Agent 和 Transform 的编译端口会合法接受该附件为 revision base。递归解析又会
返回附件所属的完整生产者族。最后算法丢弃原族主对象、保留全部旧附件（包括刚被修订的旧附件），
却把新的 Transform 输出声明为该族主对象。插件 projector 收到的结构在形式上完整，因此可以创建
真实待审批请求。

这不是测试内部直接调用私有函数得出的推测。本轮反例使用：

1. 编译通过的未知盲插件变体，主输出与附件集合共享 `blind.object.v1`；
2. 真实 `operation_invoke` 产生一个主对象和两个附件；
3. 真实 Agent Operation 以 `notes_001` 而非主对象为 `ancestor`；
4. 真实 Worker claim/materialize/write/validate/finalize 产生 patch；
5. 真实修订 Transform 仍以该附件为 base；
6. 真实 Approval Operation 绑定修订输出、两个旧附件和 change log。

观察结果：

```text
approval_status pending
base_is_original_family_primary False
base_is_selected_sibling True
retained_selected_sibling True
retained_original_primary False
```

因此当前解析不是计划要求的“递归取得原生产者族，再以本次编译输出替换被修订主对象”总函数。
它在同 Schema 异成员场景返回了错误但可审批的族，而不是失败关闭。人工 UI 虽仍绑定精确 subject，
却无法弥补投影前已错误解释的父链。这违反不可变谱系、精确资格对象和插件失败关闭三项承重约束。

#### 最小修复边界

1. 在递归得到 `base_family` 后，要求 `base_envelope.ref == base_family.primary_ref`；不相等时返回
   `None` 或一个既有通用失败原因，不得构造修订族。
2. 增加一个持久负例：未知插件的主输出和集合附件使用同一 Schema，以附件完成真实 patch Agent
   和 revision Transform 后，Approval 必须失败，且不得创建 Approval binding。
3. 保留现有“以原族主对象为 base”的初始/修订 clean-wheel 正例，证明一行前置条件没有破坏合法
   链式修订。
4. 不为“附件修订”新增 provider 表、Schema 字段、族实体或第二修订协议。R5-B 的现有语义只承诺
   替换主对象；未来若要支持附件级修订，应另行设计显式编译合同，不能在本轮猜测。

这一修复只需一个精确父链守卫和一个盲插件负例，不应扩张 R5-B 或提前实施 R5-C。

## 4. 已正确实现的边界

除 F1 外，本轮没有发现固定领域分派或第二权威：

- Root 对 Agent 族使用完成 Task、当前 OperationAuthority、主输出合同和所有 collection 合同；
- Transform 族以当前编译 Operation、控制端调用指纹、有序父引用和当前实例 binding 为闭包；
- 输出端口、单值/集合基数、kind、Schema、payload 版本、媒体类型、大小和规范标签均被复核；
- 同一 family 的多个 subject 只交付一份，同一 identity 对应不同成员集合立即拒绝；
- 深度达到 8 或重复访问同一不可变 Artifact 时停止，Artifact 注册本身不允许凭空建立循环父引用；
- 跨实例名称不能通过 Operation 输入解析，缺 fingerprint、fingerprint/摘要漂移和兄弟输出不完整均
  不能形成可用 family；
- clean-wheel 只安装 core 与测试夹具 wheel，通过唯一 `scidiscovery.plugins` 发现并真实调用盲
  Operation。生产 `src/`、Root、Task、Scheduler、UI、部署脚本和发行 pyproject 均不认识盲插件；
- Approval 创建仍调用已有 `ApprovalService.create_request()`，决定、资格和 UI 生命周期没有复制。

这说明 R5-B 的总体方向正确；打回原因是一个精确且可复现的谱系漏洞，不需要推翻领域无关模型。

## 5. 复杂度与目标一致性

当前 family 解析没有新增数据库列、持久对象、注册表、状态机或 entry-point group，测试夹具接入
`tests/operations/conftest.py` 也不是产品安装器分支。它确实删除了固定领域知识，符合“插件一次
注册、核心不认识新领域”的目标。

成本也必须如实记录：`mcp_root.py` 当前 3394 行，R0 精确聚合口径当前为 10194 行；operations 包
仍为 7 文件、2060 行。相对 R5-0 冻结的 9931 行，当前聚合暂增 263 行。R5-D 的最终净删除门尚未
到期，不能把本阶段增长单独判成失败；但也不能宣称复杂度已经下降。F1 的修复应保持为一个守卫和
一个测试，不得用新的 family registry 或附件修订协议放大这段逻辑。后续 R5-C 删除旧领域分支、
R5-D 按职责拆分后仍须满足冻结净复杂度门。

仓库仍没有逐项编号的“33/33”自动验证器，本报告没有伪称运行。按单一权威、不可变父链、Worker
最小上下文、人工审批、核心/领域分离和失败关闭等行为约束族检查，除 F1 的精确谱系错误外未见新
退化。F1 本身足以阻止阶段通过。

## 6. 独立运行证据

所有测试严格串行，且命令前设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
git diff --check
# 通过

pytest -q \
  tests/operations/test_r4_approval_operation.py \
  tests/operations/test_r5_blind_producer_family.py
# 42 passed in 36.14s
```

42 项包括既有 Agent/Transform/Approval/资格与修订边界、盲插件 8 项源码态正负例及 1 项
clean-wheel 真入口。全绿没有覆盖“主对象和附件共享 Schema 时修订附件”的情况；上述独立真实链
反例稳定得到 `pending`，直接证明缺口。

实现记录中的全仓 `261 passed` 没有被当作继承批准。本轮已经有生产路径可复现阻塞，重复全仓测试
不会改变门禁结论，因此没有为仪式重跑无关 Worker、TCAD 和执行测试。

## 7. 最终结论

**打回。**

R5-B 已经实现领域无关的 Agent/Transform family 重建、控制端调用指纹、完整集合校验、去重、
同身份冲突、递归界限、实例隔离和未知 clean-wheel 插件接入，且没有复制 ApprovalService 或引入
新注册表。但修订递归没有证明 base 是原族主输出，能够把同 Schema 附件错误提升成主对象修订族并
进入真实人工审批。

因此本轮**不放行 R5-C**。只允许按 F1 的最小边界增加主对象引用相等守卫和真实负例，然后由未
参与修复的独立审查者复审；不得借此扩张为附件修订系统或提前进行 R5-C/D。
