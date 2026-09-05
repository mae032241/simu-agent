# 假设审查与后续行动契约第四轮独立复审

审查日期：2026-09-03  
候选：完整请求指纹与创建目标统一返工后的工作树  
审查者权限：只读，未参与实现，未修改文件  
结论：**PASS；阻断项 0**

## 1. 请求身份与单后继边界

`_prepare_local_run` 统一解析恢复来源、计算完整请求指纹和创建目标，preflight 与 invoke 使用同一
路径。独立 Root 探针确认：

- 同名同请求在 `reject`、`create_revision` 下都返回同一 Run；
- critic、instruction、foundation、resume 任一改变，以及不同名字绑定同一 base，preflight 均返回
  `revision_branch_forbidden`，invoke 返回相同原因，不再延迟为 `local_run_creation_failed`；
- 两个 preflight 同时通过后并发 invoke，只有一个请求被接受，持久层只有一个 Run 和一个 binding；
- 底层双线程事务同样只有一个 scheduled，另一个得到明确的 successor busy；
- completed 后不同 base、不同 instance 不串扰，failed successor 后可重新排队。

Root 的提前判断直接调用 `RunService.revision_successor`；该公开只读投影和 `BEGIN IMMEDIATE` 调度事务
都复用 `_revision_successor`，没有复制 SQL、状态集合或另建修订权威。Root 负责请求身份与可读预检，
Run 事务负责竞态下最终提交，分工合理。

## 2. 科学谱系与职责边界

- `audit_A/foundation_A/source_A` 正例通过，改绑另一份 passing `audit_B/source_B` 时
  `guard_rejected`；
- 人为构造的多 audit foundation 在纯 guard 层只检查成员关系，但公开 Root 路径要求已资格化
  foundation，审批 projector 又要求 split 输出父集合精确为 `(primary, audit)`，未形成可达旁路；
- 真实两级 completed Run 链中，同问题维度只改措辞触发 `revision_no_progress`，第三次修订触发
  `revision_limit_reached`；
- hypothesis key 新增、删除、改名均拒绝，重排接受；
- 六种 disposition 的 verdict、action 与声明消费者闭合，`inconclusive`、`reject` 为无后继的显式
  终止；critic 与实验设计职责没有回退。

未发现第二 Run 状态机、第二 Operation 注册表、第二 current、固定科研 DAG、TCAD 核心硬编码或
针对单一用例的特殊分支。

## 3. 命令证据与边界

全部命令使用 `MALLOC_ARENA_MAX=2` 与 `ulimit -v 7340032`：

- 独立聚焦回归：`32 passed in 1.75s`；
- `git diff --check`：通过；
- 审查未移动或删除源码安装元数据。

未验证部署后的 daemon/MCP 入口、真实 Fig.4 闭环、人工审批 UI、六种 disposition 全部经真实 Worker
提交的端到端矩阵，以及全仓测试。源码 checkout 的重复 `egg-info` 和既有 184/159 文件数门不属于
本契约的语义阻断。
