# R4-C-A 迁移边界第二轮独立复审

审查日期：2026-08-29  
审查范围：`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 第 6 节首轮打回后的冻结边界。  
审查性质：只读跨边界与简化性复审；未修改实现或总体计划。

## 一、结论

**通过，允许进入 R4-C-B**

首轮两个阻断项均已按最小范围关闭。修订没有要求修改通用集合类型、Artifact 模型、执行生命周期、
调度器或 UI，也没有新增注册表和持久化权威。

## 二、首轮阻断项关闭情况

### 2.1 多 PLX 身份已经可以由现有边界闭合

修订不再声称 experiment plan 的位置足以证明 PLX 身份，而是把职责拆成两个现有不可变对象：

- experiment plan 声明所需科学 series；
- 同次执行的 `runtime_manifest` 以 solver-native 逻辑名、SHA-256、大小、媒体类型和声明顺序绑定
  原始输出字节。

插件包装可以在不修改核心的情况下完成该映射：`CompiledTransformAdapter` 虽然只向 executor
传递按端口分组的 bytes，但其中包含 manifest bytes 和有序 PLX bytes；包装器可解析 manifest，
要求每个计划 series 与同名唯一 solver-native 记录对应，再逐项核对摘要、大小、媒体类型和顺序。
逻辑名来自执行输出合同，不是文件名猜测。不同摘要的成员错序会在逐项摘要核对时失败；缺失、
额外或重名也都有确定拒绝条件。

谱系 guard 同样可由现有 `BoundInput` 完成：它能读取每个 Artifact ref 与 parent refs，因而可以要求
manifest 和全部 PLX 具有完全相同的 execution 父链，并要求 exact passing runtime attestation
直接以该 manifest 和每个 PLX 为父项。科学映射在 executor、不可变谱系在 guard，各自只有一个
权威，不需要把 Artifact 标签或动态别名暴露给通用集合接口。

第 6.2 节已经把验收提升到 Root `operation_invoke` 真实路径，并冻结四类关键反例：成员交换、
同 Schema/大小的外来 PLX、另一执行的 manifest、未包含输出的 attestation。该证据要求足以防止
用手工 `Mapping[str, bytes]` 单元测试掩盖真实 Artifact 边界缺口。

论文图集合继续由 manifest、validation report、CSV 自描述身份与摘要闭合；reference CurveBundle
由内容中的唯一 series identity 闭合，并按内容摘要形成稳定审计名称。两者均不再依赖调用方动态
别名承担科学身份。

### 2.2 Operation 数量已经收敛到生产需要

修订只登记六个有当前生产消费者的 support Operation：

1. `scidiscovery.curve-bundle.sprocess-plx.v1`；
2. `scidiscovery.curve-score.v1`；
3. `scidiscovery.curve-score.sprocess-log.v1`；
4. `scidiscovery.curve-bundle.figure-evidence.v2`；
5. `scidiscovery.curve-reference-coverage.v1`；
6. `scidiscovery.objective-coverage.v1`。

单项 log/PLX normalizer 与 bare consistency 继续作为上述 executor 复用的内部函数，但没有目录
Operation；论文图 v1 既有 Artifact 仍可读，却不能再新建旧语义产物。这同时保留 active PLX、
direct process-log、论文图 v2、评分和两个执行前 coverage gate，删除了四个无生产消费者的可调用
表面，没有损失当前 TCAD 主链能力。

清洁安装门已经相应改为精确六项，并要求三个内部函数无目录项、figure v1 精确调用为 unknown、
旧 adapter 与断裂 operation-spec entry point 均为零。该门同时验证“保留算法代码”没有重新变成
第二行为注册表。

## 三、其余边界复核

### 3.1 三种视图与单一权威

六项均为科学行动选定后的确定性物化或门结果，声明为 `catalog_scope="support"` 正确。support
不会进入 `scientific_readiness` 或默认 public 规划视图，但仍由同一 CompiledCatalog、同一
`operation_invoke`、同一端口、guard、validator 和摘要执行。没有新增 support allowlist、profile
registry 或领域路由器。

### 3.2 InGaAs 项目插件

保留 `ingaas.fig4-baseline-recovery.v2` 为默认不安装、只有一个 support Operation 的项目插件仍是
合理最小边界。它继续承载冻结项目合同中的专用复算，不把图号、材料或项目阈值泄漏到核心、TCAD
或 curve-score。显式安装门新增了“只增加该一个 Operation，且任何既有编译摘要不变”，足以验证
可选项目插件不会改写默认目录权威。

### 3.3 阶段门

R4-C-B 必须先完成六项迁移、真实 Root 身份负例、core-only/full 清洁安装、旧入口清空、全仓回归
和独立审查；未通过不得迁移 InGaAs 或删除全局旧 loader。R4-C-C 再验证显式项目安装、摘要不变、
所有发布组合旧 entry point 为空、发布清单和独立审查。该串行顺序足以把 curve-score 通用迁移与
项目插件迁移隔离，不需要新增阶段或状态。

## 四、33 项约束族与剩余风险

按冻结的行为约束族复核，修订保持：单一启动编译权威、不可变 Artifact 与显式父链、确定性算法与
科学判断分离、support 不参与规划、插件单入口、核心/领域分离及清洁安装失败关闭。未新增数据库表、
生命周期、Schema registry、动态端口类型、领域 scheduler 分支或 UI renderer 分支。

本轮通过的是可实施的设计边界，不是实现通过。R4-C-B 的独立审查仍必须查看真实
`operation_invoke` 路径的四类 PLX 身份负例、六项成功执行、安装态 entry points、目录范围、输出
validator、发布清单及全仓回归；任何以调用顺序代替 manifest 摘要核对、以手工字节映射代替真实
Artifact、或重新发布 figure v1/单项 helper 的实现都应打回。
