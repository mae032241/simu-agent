# P3d2-a native 输入公共链独立静态评审

结论：**本节点静态 PASS，可精确提交**。评审基于 P3d1 `c03d0c3` 及之后独立提交的 UI；不包含 P3d2-b 迟批恢复或 P4c 导出实现，不代表真实 TCAD/平台身份资格已通过。

## 精确范围与检查方法

生产 12 文件：`operations/runtime_plugins.py`；`research_loop/{execution_inputs,execution_authority,experiments,contracts,formal_review}.py`；插件 `tcad_artifact/{project_packager,native_implementation,experiment_capability,managed_execution,execution_adapter,command_adapter}.py`。其中 execution_inputs/native_implementation 新增。测试为新 `test_tcad_native_implementation.py`、新 `test_native_execution_inputs.py`，以及既有 `test_runtime_plugin_configuration.py` / `test_execution_configuration.py` 的必要 fixture/字段拒绝同步。另读本节点设计与实施证据。

只读源码、限定 diff、调用链及测试断言；没有运行测试/收集、项目 import、CLI、线程/原生进程、构建、安装、HTTP、SSH 或 solver。作者 AST/固定旧字段比较仅为静态证据。

## 公共链与真实职责

1. **可选本地编译。** experiments 的 `compile` 入口要求已冻结的 implementation_authoring 能力；宿主从原 operator 配置选离线 capability snapshot，不能由 W 传 snapshot 路径或任意身份。managed factory 将可选编译配置与旧严格 transport 配置分开，快照字节/身份与实际 compiler/helper 纳入冻结资产。编译只使用原 live W 授权，不创建请求、reserve、远端 prepare 或执行许可。
2. **来源唯一。** `execution_inputs.py:41` 以 instance、producer step/seal、material_path、sha/size 和当前 compiler job 已绑定成员复核，缺失/歧义拒绝；同哈希不用于认同源。V3 为独立 native 类型，不伪造 ArtifactRef。slot media 只是冻结的科学类型声明，不是字节 MIME 鉴定。
3. **编译原件。** `execution_inputs.py:152` 将 author/capability 原字节、当前 job/native intent/config、完整 slots、实际实现/合同、输出身份保存到当前 W 的 host 原件。输出仅允许 artifacts 下规范路径；同路径不同内容不能覆盖原编译输出。返回 W 的是科学输出 path/status，不返回 private compiler ref。
4. **封存与独审。** contracts 在原 seal 添加可选 compiled_implementations，并使用共同 validator 复核；普通 HWA 最终 JSON 不新增机械字段。formal_review 作者集合加入全部 slot producer，以及作者文档确为 bound 输入副本时的原 producer；没有从任意上下文父节点推作者。来源沿原 all-frozen-input provenance 保守继承，编译不授 clear 或 review。
5. **执行同一包。** `execution_inputs.py:220` 在 gate 前核 exact reviewed subject、编译输出和整个 resolved slot 列表；回调仍从同一原 producer 成员读取。后继现有 `run --payload` 复用原 d1 来源/review/policy/authority/资源账，再沿两个 adapter 的显式 v3 profile 和 P2b 流式 materializer。未审/手写包、错原件或缺回调不先 reserve。review 后不重编译。
6. **兼容范围。** V2 默认 profile、模型字段和旧物理 job.json/tar/submit/retire 协议保留；V2/V3 共用科学 slot/identity 校验及纯 project capture 生成逻辑。旧可选 debug/result 消费者没有冒充全面支持 V3。

## 评审发现及修复

- **作者读取竞态。** 原先先读取 author raw，再独立取 identity，可能编译旧字节但保存新作者原件。现 `execution_inputs.py:160` 将本次 raw 的 SHA/size 与 identity 比对，保留编译后 identity 检查和 copy_bound 校验。
- **真实工厂接口断链。** 原 core `_adapter` 从 JSON body 剥 execution_interface，wrapper `_bound` 却要与 accepted.interface 全等，旧直接 full-config fixture 遮住了真实路径。现 RuntimePluginContext 默认 None 的非 JSON frozen_execution_interface 由 core 传已验证接口，factory 才恢复 wrapper 内部投影。operator JSON 明确拒绝该字段；prepare/acceptance/_bound 拒绝仅 executor 的发现占位，不能据此授资格。
- **旧负控被新门槛挡住。** 新完整接口检查会使旧可信 DI fixture 提前失败，collection/retirement 等断言不可达。现仅补 fixture 的合成 version/code 与 factory 的可信 context，明确不冒称真实 freeze；原独特保护未删除。新公共链另走实际 load/_adapter/factory，而非继续只靠直接 wrapper 构造。

未发现剩余具体阻断。

## 测试是否能证伪行为（全部未运行）

- 两个纯合同用例：固定旧 V2 文档/envelope 的字节与摘要能发现序列化/字段默认回归，预期不是新 model 两端自证；native 编译保留不同 producer 原件身份、固定 control capture，并拒绝 slot/size/storage 错配。
- 公共链用例：实际 e.main compile、seal、formal qualification 函数、后继 e.main run、注册 factory、现有 gate/ledger、P2b 输入读取和 accepted/_bound。若缺 compiler 封存、丢输入作者、工厂漏接口、读错原件或把同一 pending call 重发，断言会失败。backend、调度 eligibility 和 native session 身份为可信合成输入，不能证明真实 Codex 独立性、SSH/solver 或真正活 owner 准入。
- 两个原件负控：未 bound alias 与 author raw/identity 间正文改动须在 gate/后端前拒绝；同哈希错 producer/instance、修改包不能借旧 compiler proof 封存。预期错误有独立身份/路径负控，非只断言假成功 JSON。
- 既有 fixture 只同步新可信边界，仍保留原默认 blocked、missing resolver、collection/expiry、retirement 与恢复保护；新增宿主字段拒绝和发现占位不可 prepare。

## 负载与未覆盖

没有安装、子进程或测试矩阵增量。生产链仍有整包/author/schema JSON 的完整内存解析；来源、封存、review 与 callbacks 可重复流式哈希同一原件，物理打包也会再核输入。这是实际 IO 成本，不能宣称恒定内存/IO、硬实时或已测资源上界；本轮未做测量，也不能归因为此前 OOM。没有新增原件字节 cap；显式 handoff/output/storage quota 与身份/路径/类型检查保留。

完整动态 native/compiler/review/远端链、真实平台参与者、跨 boot、迟批后的 same-call 恢复均未验收。d2b 仍须先解决原 seal 的正向无 prepare 证据及同 recovery owner 的追加 pending→terminal 语义；不能从本节点 PASS 推导其通过或宣称 P2/P3 整体完成。
