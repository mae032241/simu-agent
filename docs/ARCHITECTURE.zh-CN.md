# 当前架构：薄 H/W/A/E 控制层

简体中文 | [English](ARCHITECTURE.md)

新实例由 `scid-research` 管理，实验工具为 `scid-experiment`。没有 LLM Root、MCP 调度服务或后台 Root daemon。
核心提供薄 CLI 与实例 UI；旧 CLI/MCP/UI、Root 宿主、平台配置生成与 legacy systemd 部署已退役。

## 责任与数据流

```text
操作者的目标、输入、配置、有限预算
  -> CLI prepare：冻结实例设置
  -> controller：原实例写锁、预算、暂停、角色路由
  -> native：独立 H / W / A / E 原生线程
  -> 科学 JSON 与精确成果封存
  -> A 的科学去向 -> controller

W -> scid-experiment -> 冻结执行接口 -> local / 领域 adapter
                              -> 原调用 query / cancel / collect
CLI serve-ui -> 同一实例的只读视图与控制命令
CLI archive / checkpoint -> 原件核验与限定恢复
```

H 负责机制与假设；W 负责有界实验设计、实现与观察；A 负责贡献、证据缺口、后继方向和交付选择；E 负责所请求的证据工作。
控制层拥有身份、冻结绑定、预算、资格、权限和机械发布，不制造科学结论，也不要求模型推算哈希或引用。

## 实现归属

| 责任 | 唯一实现范围 |
| --- | --- |
| 实例准备、路由与暂停 | `research_loop/controller.py`、`runtime.py`、`instance_control.py` |
| 原生执行、原线程续接与计量 | `native.py`、`execution.py`、`continuation.py` |
| 科学合同、原文与成果 | `contracts.py`、`semantic.py`、`instance_science.py` |
| 候选比较与交付 | `selection.py`、`delivery.py`、`worker_delivery.py` |
| 执行注册与原调用恢复 | `experiments.py`、`managed_wait.py`、`local_experiments.py`；领域插件提供 adapter |
| 来源、正式独审和执行批准 | `qualification.py`、`formal_review.py`、`execution_inputs.py`、`execution_authority.py` |
| 预算与累计资源 | `budget.py` 的原 control ledger |
| 实例 UI | `instance_ui.py`、`instance_render.py`；不建立第二份状态 |
| 归档与同宿主冷恢复 | `instance_archive.py`、`instance_owner.py`、共享 `archive_io.py` |

上述文件均位于 `src/scidiscovery/research_loop/`，另有说明者除外。
`scidiscovery.execution_interfaces` 发现执行接口，薄实例冻结精确选择及实现身份。
保留的 Operation 编译器、插件声明、共享 schema、抽取的回调及独立存储原语不是旧 MCP 服务入口。
`artifact_agent/service` 旧 Run/SQL 宿主及运行辅助模块已删除；存储库保留不表示薄链依赖它作为宿主。
不按目录名删除 adapter、来源规则或存储校验。Operation ABI 以 `operations/spec.py` 为准，当前为 26；插件接口见[API](PLUGIN_RUNTIME_API.md)。

## 不可退化的边界

- 一个实例只有一个推进写者；只读页面不调模型，不重建第二份预算或科研状态。
- 科学原文、成果、配置和原调用均按精确身份冻结；修订不能继承旧对象的批准或资格。
- 来源未知保持 unknown；正式独审排除精确对象的全部已知作者与参与者，普通 A 不自动成为正式审查。
- 科学判断、正式资格与执行批准分别解释；聊天或手写决定文件不构成人工批准。
- 未知外部提交只核对原调用，不退款、不重发；恢复不重置额度、不生成另一个 owner。
- UI 转义作者内容；附件按精确封存成员读取，HTML/SVG 仍下载，不执行。
- 当前信任 Worker 及宿主同权限进程，属于软控制边界，不主张防恶意进程隔离。

## 声明来源与审查

资格消费精确冻结原件，不按名字、相同字节或最近对象猜测来源。受管执行可通过
冻结能力声明输入来源；自包含 TCAD V2 package 必须匹配准备归档和原 reviewed
producer，编译 V3 输入保持原 compiler 链。明确不完整的声明不能回退为更广的来源主张。
可选 observer 须另行启用冻结来源合同，并提供绑定精确 observation 的来源视图；
展示 coverage 本身不授予资格。真实 producer 贡献即使未被选为 implementation 也进入
作者集合；普通 parent 链不自动生成作者关系。

普通探索不要求固定的正式审查阶段。所请求的审查须绑定精确对象与经核验的贡献者；
普通 A 解释不构成独立审查。来源限制沿冻结输入传播，未知来源保持 unknown。
这些核验仅覆盖框架声明范围，不证明任意 native 外读封闭或科学正确。

## 扩展规则

领域算法、科学 schema 和执行 adapter 归插件。核心按冻结的声明能力路由，不按领域
或插件名称分支决定科学行为。schema 结构、声明的科学语义与 validator 必须一致；
工程故障不能伪装成科学拒绝或科学重试理由。恢复保留原限制和失败证据。
只读视图与 UI 呈现同一封存科学字节，不改写科学内容。

## 支持与资格

本地受管实验、候选交付、实例 UI、声明来源、执行 gate、原调用维护与同宿主原路径冷 checkpoint 已实现。
`/results?after=N` 分页显示封存节点，`/results/<step>` 显示精确结果；排名来自该节点输入时的冻结摘要，不冒充全局最新排名。
普通只读包不能自动恢复为可推进实例；跨宿主、anchor 丢失和任意原生外读不在保证范围。
源码/HTTP/合成进程检查不替代真实浏览器、Codex 原线程、TCAD solver 或真实掉电资格。
旧入口退役不授予新链这些资格，也不自动操作已有主机服务、数据库或外部作业。

TCAD 专项提升资格所需证据见[资格状态](TCAD_QUALIFICATION_STATUS.zh-CN.md)。

使用方法见[CLI 指南](ROOTLESS_CLI.zh-CN.md)，部署见[安装](INSTALL.zh-CN.md)，验证口径见[发布](RELEASE.zh-CN.md)。
