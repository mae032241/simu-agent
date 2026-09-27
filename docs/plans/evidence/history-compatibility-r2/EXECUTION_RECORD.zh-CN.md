# 历史兼容 R2 执行记录

2026-09-09。按 `docs/plans/HISTORICAL_COMPATIBILITY_REPAIR_PLAN_R2.zh-CN.md` 经执行前自审及执行中补充审查后实施。没有冒充独立审查。修改前为已有未提交工作树，精确增量见 implementation.patch、changed-files.json 和 baseline.tar.gz。

## 完成情况

- P1：按既有输入用途允许历史参考和修订基底，打通完整 cohort 展开；当前精确审查继续强制，跨版本不重置修订次数或无进展约束，回溯达到上限立即停止。
- P2：Run/Transform 来源族保留原生产身份，验证冻结来源、完整集合及唯一绑定，支持在当前审计后请求新的批准。旧批准不继承。
- P3：历史结构化输入按消费者 JSON Schema 校验，报端口和 JSON Pointer；完成载荷不因 handoff 不可解析被隐藏；inventory 与 Worker assignment 标记 historical。资格查询仍默认只返回当前交接。
- 补充检查：历史 blocked/revise 仍经过 Transform 传播非合格标记，历史可读性不清除负面事实。
- P4：完成串行定向检查、单核心 wheel 安装态冒烟、编译摘要对比、中英文架构说明及精确增量记录。

本轮只改 6 个运行源码文件；未改 OperationSpec、角色提示、存储表或 Run 生命周期，也没有新增操作、迁移引擎或兼容白名单。比较实施前后实际编译结果：50 个 Operation 的 digest 全部不变（digests.log），避免因本轮兼容修复再次退休整批科研合同。

## 关键验收证据

1. acceptance.log：9 passed，4.88 秒，RSS 106772 KiB。覆盖历史假设→当前真实独立审查→新设计→完整 cohort 展开→计划审查→author 准入；历史计划→新非通过审查→新修订；原计划审查不能用于新修订，新审查后可继续；历史 TCAD 项目修订及跨代预算负控。
2. final-boundary.log：24 passed，5.53 秒。含当前科学/历史结构准入、无进展修订、参数族扩展/审核/批准及通用变换检查。
3. installed-tests.log：单核心 wheel 实际安装到 /tmp 后，5 项历史兼容串联测试通过，3.10 秒，RSS 104384 KiB。明确断言 scidiscovery 来自安装目录；插件和依赖复用当前环境，不能冒充全插件清洁安装矩阵。该安装检查先于测试中补充的新修订审查断言；该断言随后在 acceptance.log 通过，运行源码未再改变。
4. 其他日志保留阶段结果：最终 core 批次曾有 57 passed/1 failed，领域批次曾有 38 passed/1 failed；两次失败均为同一旧测试把 `{}` 当历史项目/审查、仍期待摘要错误。修正为结构不兼容预期后，该测试在 final-boundary.log 通过。更早测试 mock 未接受 allow_historical 参数的失败也已修正并单独验证。没有删除失败记录或声称这些原批次全通过。
5. 结果分析零输出/错 case/错 round、执行准入、批准 provider 约束负控在 domain.log 的通过项中验证；没有执行真实 solver。
6. git diff --check 通过。

全部 pytest 批次串行，BLAS 线程为 1，虚拟内存上限 3 GiB，最长批次超时 180 秒。记录到的最高测试 RSS 为 136212 KiB，约 133 MiB。未跑全量或压力测试，没有并行 Agent 或多环境安装矩阵。架构技能引用的约束脚本在仓库不存在；未将其记为通过。

## 实施后自审

- F1–F6 均有对应代码改动及上述验证；没有发现本轮范围内新的阻断项。
- 历史原始身份与当前资格分别判断；当前审查检查、执行批准匹配、精确引用及跨合同 Run 恢复限制未被取消。
- JSON Schema 校验不推断科学正确性、不补字段、不迁移对象。未知生产者或无法唯一承接的旧 Transform 仍不能用于结构化续接，只能以声明的历史背景阅读并报告缺失。
- 基础主链路测试只 stub 已批准 foundation 状态，没有 mock 独立审查为通过；审查结果经真实本地 Worker 提交。新批准请求另外通过真实 Root 准入和请求创建验证，未模拟用户已批准。

## 部署边界

源码完成，尚未重新安装到运行服务，未重跑 M7-test0 的控制面。下一步安装重启、绑定原实例后，从已完成的 `fig4_continuation_experiment_intent_3.output` 继续完整 cohort 的 materialize preflight。没有必要重做已完成的新设计；实际控制面仍是最终准入依据。
