# 历史记录兼容与准入修复

2026-09-09。本次增量基于已有未提交工作树；没有回退其他修改。精确增量见 implementation.patch 和 changed-files.json。

## 已实现

- 完成 Run 的生产合同更新或生产者移除后，run_status 仍返回通过原流程封存的载荷及可解析交接，标记 historical。读取继续校验精确 Artifact 引用、内容摘要与大小；运行中结果不公开。不可解析交接仍拒绝暴露结果。
- Agent 的 prior_signal 允许历史生产版本，要求完整生产来源和当前输出端口 schema/kind/media 一致；继续采用当前独立审查关系。已有 evidence_inventory 历史背景读取规则不变。
- 旧审查不能作为当前独立审查；claim_evidence、revision_base、change_request、变换、批准、执行的原有严格合同门不变。不迁移或改写历史记录、不恢复旧 Run、不添加兼容白名单或状态机。
- 合同准入错误返回具体输入端口。
- 更新对应回归预期和中英文架构说明；补齐已有 current_progress 的测试目录预期。

## 验证

validation.log 内为完整命令与资源统计。串行运行，OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1、虚拟内存上限 3 GiB、超时 180 秒。

41 passed，6.42 秒；峰值 RSS 134868 KiB（约 132 MiB）。覆盖真实本地 MCP 的旧输出读取→新审查提交完成、卸载后读取、旧审查资格拒绝、当前与历史计划准入、精确审查主体、输出端口不兼容、缺失来源、旧 Run 的重启生命周期、严格变换/修订合同门。git diff --check 通过。

中间测试失败来自新增测试复用已绑定 Worker Router、旧状态断言及已有进度端口清单未更新；修正后最终定向集合全部通过。没有运行全量/压力测试、全量安装矩阵或真实 solver。安装代际 probe 的预期已更新，但本轮未运行该安装矩阵。架构技能引用的 scripts/validate_architecture_constraints.py 在当前仓库不存在，未执行。

## 生效与限制

源码修复完成，尚未重新部署或验证 M7-test0。安装重启后重新执行原请求 preflight；若要求当前独立审查或当前批准，按精确目录补齐，不能继承旧资格。生产者已卸载或输出类型不兼容时，可读取历史完成记录/声明的 inventory 背景，但不允许作为 prior_signal 越过缺失的当前合同。历史材料可供重新设计，不等于旧计划可以直接执行。
