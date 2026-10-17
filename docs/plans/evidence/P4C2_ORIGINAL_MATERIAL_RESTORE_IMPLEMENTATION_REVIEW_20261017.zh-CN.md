# 原实例缺失成果恢复：独立实施复审

2026-10-17。结论：**最终静态 PASS，所选3个 unique source 用例由 root 复测通过。** 范围为 instance_archive.archive_restore_material、对应 CLI 分支、ROOTLESS 恢复段、3个新增用例与本节点设计/实施账。不混 P5 部署或 F1 来源变更；不授完整 writable restore/副本 owner 或强隔离资格。

## 真实链路与边界

追到实际 _owner_locks/_quiescent：原 controller/UI/runner/Records/authority/ledger 锁和所有原 native cleanup、terminal/fence、未决 preparation/delivery 校验照常。没有 managed overlay，也不回填 call/control 缺失。当前协议/setting identity、job/result/attempt 与 Original(raw,proof) 继续核验。

普通成果必须是当前 seal 唯一成员；source 只可位于原节点 artifacts 或明确 nested experiments 的 artifacts/conclusion 语法，不接受目的路径，不把 work/lineage/calls、host-history 或密钥纳入。完整包 inspect 后须对应当前 instance/settings 及同路径 producer seal 字节，按原 source-relative path+sha+size 找唯一材料，不按同 hash 换 origin。

独审指出并收口的版本竞态：inspect 后重读 metadata 原先未绑定已验证版本；现 inspect 前记录 archive.json 完整 hash/size/stat 身份，inspect 后 read 再核同一身份，manifest 另核 metadata 声明及扫描前后身份，不能替换成另一未验证版本继续消费。复制继续校验选中 blob。

host-runtime 唯一 temporary→copy_verified→os.link 到精确缺失目标，fsync/finally 清理；无 replace 或跨文件系统 fallback。目标已有不同字节、目录或链接拒绝；竞争只能相同 exact bytes 幂等。崩溃可留下 host temporary/已发布的正确字节，不会将 temporary 当科学成果。恢复不自动 continue、删 pause、取新预算、重签决定或覆盖当前 settings/ledger/seal/authority；current 原件保留条件不是目录路径本身提供 owner 迁移证明。

## 测试首轮遗漏与精确修复

新增3项最初静态审查未发现新 sealed_scene 沿用了 archive-only scene 的 project/nodes/001/work/artifacts。实际 contracts.workspace(root,1) 是 project/nodes/001，故文件未进入科学 seal；root 首批3 failed，均为选择资料成员时 StopIteration，尚未到 restore。此为 fixture owner 错配，也属于本独审首次静态漏项，不能改写为生产 restore 失败或预先动态通过。

修正仅新 sealed_scene：从旧 scene 借原始 bytes，在 c.workspace(root,1)/artifacts/writer.lock 与同 workspace/experiments/bounded/artifacts/nested.txt 写成果，再走真实 finish/seal/export。旧 archive-only scene/旧4项未动，生产 owner 判断未放宽；设计的错误路径同步修正。已定点核同 bytes 成员、原 reader、current budget.amend 后控制文件字节不变、无 budget snapshot/自动推进、原锁/unknown cleanup/目标竞争负控。合成 native cleanup 只令控制路径可达，不证明真实 native/solver 身份。

## root 唯一串行结果

原始证据前缀 `.trial/p_completion_20261017/`，各批 batch-001 的 pytest.log/resource.json 已只读核对：

| 批次 | pytest | supervisor | 树 RSS 峰值 | 清理 |
| --- | --- | --- | --- | --- |
| material-restore | 3 failed / 0.95s（fixture路径） | 1.234s | 66,211,840 bytes | complete=true |
| material-restore-recheck | 原3项 3 passed / 1.07s | 1.361s | 60,669,952 bytes | complete=true |

共6次执行、3个 unique 增量最终通过；监督总2.595s。两批 memory_stop_triggers/received_signals 均为空，未启地址空间硬限制，不能外推资源上限。没有全文件重跑、安装、模型、HTTP、SSH、solver、跨 boot/host 或完整灾备验收；本审查者仅静态阅读和只读核既有结果，未执行上述动态动作。
