# R5-L6 第一轮总审查返修第二次独立复核

日期：2026-09-01  
审查对象：第一轮返修后唯一剩余阻断 `B3-R1`  
审查身份：未参与本次返修的独立审查者  
结论：**PASS**

## 1. 放行结论

`B3-R1` 已以通用、最小且无领域特判的方式关闭。

通用核心不再闭集枚举 `deck_review` 或 `deck_revision`，任意插件可以使用同一受格式约束的稳定标识
表达自己的 Artifact kind 和建议行动；通用 reviewed-equivalence 结果也不再把任何领域的审查误称为
Deck 审查。对 `src/scidiscovery` 生产 Python 的独立扫描未发现 `deck`、`tcad`、`sentaurus`、
`sdevice` 或 `sprocess` 命中。

本次返修没有建立领域 kind 注册表、Schema 路由器、第二目录、第二 preflight 或新的生命周期状态。
因此，本报告放行**第二位独立总审查**，但不单独宣布 L6 或 L 系列已经完成。

## 2. 源码核验

### 2.1 Artifact kind 已从核心闭集改为有界开放标识

`src/scidiscovery/artifact_agent/schema/research_cycle.py` 将 `ArtifactKind` 直接定义为共享
`Identifier`。后者仍有明确的 `1..256` 长度和字符格式约束，不接受空字符串、空格、以点开头的
路径式值或超长值。因此这不是把合同降为任意字符串，而是删除核心对领域词汇的所有权。

`ScientificReadiness.available_artifacts` 和 `ScientificObjectStatus.kind` 继续消费同一个别名，未增加
旁路或按插件名分派。核心中保留的 `research_objective`、`validation_report` 等判断属于通用科研
状态语义，不是 TCAD/Deck 领域规则，也不阻止插件声明自己的 kind。

### 2.2 建议行动已交回插件能力命名

`src/scidiscovery/artifact_agent/schema/validation.py` 将 `RecommendedTaskMode` 定义为同一个
`Identifier`。`ValidationReport`、知识状态和分层诊断仍只通过这一类型表达建议，没有新增行动注册表
或让建议结果绕过唯一 Operation 目录。科学结果可以建议 `protocol_revision` 等领域行动，但能否执行
仍由既有 catalog、preflight 和 invoke 决定；建议字符串没有获得调度权威。

### 2.3 reviewed equivalence 已领域中性

`src/scidiscovery/artifact_agent/schema/comparison.py` 的三个通过分支统一说明为
`accepted independent review`。非 TCAD 的 sample-identity reviewed-equivalence 实例能够通过，输出
理由不含 Deck 或 TCAD；缺少审查时原有 `inconclusive` 语义未改变。TCAD 的
`transform_adapter.py` 仍复用该通用比较器，插件侧 Deck 语义保留在插件内。

### 2.4 Worker 文件协议未残留 Deck 名称

`src/scidiscovery/artifact_agent/interfaces/mcp_worker_protocol.py` 的文件创建和分块写入描述已经改为
普通 Run 文件/源文本措辞。它们仍是同一组通用文件工具，没有按 TCAD 文件类型新增 handler、权限
分支或工具定义。对生产核心的上述领域词扫描为零命中。

## 3. 测试与机械检查

在 7 GiB 虚拟内存限制内串行执行了最小可信集合：

```text
python -m pytest -q \
  tests/operations/test_l6_domain_neutral_core.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py
45 passed in 0.35s

python -m pytest -q \
  tests/operations/test_ingaas_operation_plugin.py \
  tests/operations/test_catalog_installed_entrypoint.py
14 passed in 44.04s
```

另独立执行：

- 对 `ArtifactKind` 和 `RecommendedTaskMode` 的空值、含空格、路径逃逸式前缀和 257 字符值做
  `TypeAdapter(..., strict=True)` 负例，全部拒绝；
- `python -m compileall -q src/scidiscovery plugins/curve_score plugins/tcad_artifact`：通过；
- 四个部署 shell 的 `bash -n`：通过；
- `git diff --check`：通过；
- `rg -n -i "deck|tcad|sentaurus|sdevice|sprocess" src/scidiscovery --glob '*.py'`：零命中。

本轮没有重复运行证据文件所记载的完整 `196 passed`；聚焦集合覆盖了此次实际改动的 Schema、比较器、
统一目录负例、TCAD 消费者和安装入口，完整结果作为实现方证据保留，未被本报告冒充为独立重跑。

## 4. 文档与约束一致性

`SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 `PLG-001` 证据已明确记录开放 Artifact kind、开放建议行动、
领域中性比较理由和非 TCAD 回归。总体计划与 L6 证据矩阵同步为 `196 passed`，并仍诚实保留
25 项 `pending_review`、1 项 `known_issue` 以及 Agent collection、Local 原生工具隔离和 Hardened
能力边界，没有把本次修复扩大宣称为科学通用性实证。

## 5. 复杂度与奥卡姆剃刀审查

本次关闭方式是删除两个核心 Literal 闭集并中性化四处描述文本，复用已有 `Identifier`、已有
比较器和已有 Operation 执行权威。没有为领域扩展增加注册对象或控制状态，代码方向是减法。
`RecommendedTaskMode` 只是科学输出中的候选建议，不能创建 Run；`ArtifactKind` 也只是结构化内容
标识，不能替代 Artifact/CAS 或目录身份。未发现第二权威或针对测试写入的领域分支。

新增测试当前主要证明正向插件标识和 Schema/结果不泄漏 Deck/TCAD；共享 `Identifier` 的负边界由
既有公共类型和本轮独立探针确认。若以后固化专门负例可提高防回归可读性，但不构成本次阻断。

## 6. 最终决定

**PASS。** 首轮唯一剩余阻断 `B3-R1` 已关闭，`PLG-001` 的当前 `conformant` 证据与实现一致。

放行范围仅为：允许进入第二位独立总审查。第二位审查未 PASS 前，不得宣布 L6、L 系列或正式发布
完成；既有 `SEC-002`、Agent collection、Hardened 原生工具和科学效果实证限制继续有效。
