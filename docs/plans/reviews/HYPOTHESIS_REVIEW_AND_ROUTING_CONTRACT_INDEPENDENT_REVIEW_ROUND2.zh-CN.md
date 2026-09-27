# 假设审查与后续行动契约第二轮独立复审

审查日期：2026-09-03  
候选：首轮来源集合与稳定假设键返工后的工作树，第二轮 exact audit 与单后继返工之前  
审查者权限：只读，未参与实现，未修改文件  
结论：**FAIL；阻断项 2**

## 1. 阻断项

### B1 可用另一份 passing audit 替换 foundation 实际采用的来源

候选从所选 audit 的父引用推导冻结来源，也要求 prior 同时属于 audit 与 foundation，但没有要求所选
audit 本身属于 foundation 的父链。因此，同一 prior 先后产生 `audit_A(source_A)` 与
`audit_B(source_B)`，foundation 由 `audit_A` 拆分后，证据修订仍可绑定 `audit_B + source_B`。
独立审查以真实 Artifact、Run、reviewer identity、父链和 Root preflight 复现了该旁路。

最小修复是要求 exact `intake_audit.ref` 属于 foundation 父集合，并继续用 ArtifactRef 集合比较多
来源；无需增加来源 kind 白名单、状态机或注册表。

### B2 同一基线可建立任意多个 sibling revision

次数限制和问题指纹只沿当前 `prior_draft` 的祖先 revision Run 回溯。第一次修订完成后，再次选择同一
原始 portfolio 作为基线，就会从零开始计算；`prior_draft` 也没有要求 current。独立审查完成第一次
真实 revision 后，第二个 sibling 的 Root preflight 仍然通过，故两次上限和无进展停止均可绕过。

最小修复是复用既有 Run 与 Run 输入记录，在调度事务中保证
`(instance_id, operation_digest, revision_base_ref)` 至多一个非失败后继；后续修订只能以该后继输出
作为新基线。无需新增 revision 表、current 或第二状态机。

## 2. 已确认但不自动继承的结果

- 假设键集合已冻结：允许重排，拒绝新增、删除与改名；问题指纹忽略措辞并按稳定键排序；
- 六种 disposition 的 Schema、verdict/action 一致性、消费者和两个显式终止状态未见新断路；
- evidence remediation 仍输出完整 `ScientificIntake` 并重新进入独立审计，不会直接晋级假设；
- 未发现第二 Operation 注册表、第二 Run 状态机、固定科研 DAG 或 TCAD 名称进入通用核心；
- 14 项契约测试通过；扩展回归唯一语义无关失败为既有 184/159 文件数门。三个 Worker 子进程测试
  因源码 checkout 的 `egg-info` 与临时测试入口重复而失败，应与本轮两个阻断分别记录。

## 3. 未验证边界

- 未验证 sibling 调度的事务竞态和失败后重试；
- 未执行完整全仓套件、部署升级或真实 Fig.4 科学闭环；
- 未驱动真实审批界面；来源错配探针只替换了批准状态查询，没有替用户写入决定。

本报告只约束第二轮候选。后续返工必须形成新候选并重新独立审查，不能继承本报告中的局部肯定为
最终 PASS。
