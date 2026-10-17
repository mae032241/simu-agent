# 原实例缺失成果恢复：独立设计审查

2026-10-17。结论：**窄范围设计静态 PASS，可依 root 授权实施。** 不是代码/运行验收，不授灾备、可推进副本或同 UID 强隔离资格。审查对象：[设计](P4C2_ORIGINAL_MATERIAL_RESTORE_DESIGN_20261017.zh-CN.md)及 root/实施者收窄补充。

已追实际原语：instance_archive._owner_locks 使用非阻塞原 controller/UI/runner/Records/authority/ledger 锁；_quiescent 仍完整验证原 native cleanup、terminal/fence、未决 preparation/delivery，不能 overlay 或跳过 managed 原件。instance_science._sealed 校验当前 job/result/attempt，实施须额外持 Original(raw,proof) 核确切 raw，而非只取其描述。archive_inspect 继续完整检查只读包。

允许写者仅当前 seal 已列名的普通 artifacts 或明确 nested experiment artifacts/conclusion 成员。目标从当前 exact source 计算，不能由包/命令提供任意目的路径；必须限定 canonical、原 root 内且无链接。包内同路径 producer seal 字节身份必须等于当前 seal，再以原路径+sha+size 找唯一材料。不同 origin 同 hash 不够；managed/call/control、host-history、密钥/session、外部原件都不得补。

root 补充的 staging 方案可接受：root/host-runtime 下唯一 temporary directory，copy_verified 先流式核到 staged original，再 os.link 无覆盖发布到精确缺失目标并 fsync；跨文件系统失败即拒，不 fallback replace。崩溃残留不能进入 collect。目标竞争只可对同 exact bytes 幂等，不能替换已有异字节/目录/链接；copy_verified 与最终发布均不可扩大可写成员范围。

保留 current settings/jobs/seals/raw/result、账本高水位、authority/accepted/recovery 原件；旧包不能覆盖它们。缺这些当前原件或无法证明静止仍拒绝。恢复不删 pause、不续预算/决定、不调用 continue、不将包 restorable=false 升级成 owner 证明；只有同一原实例的材料字节恢复。完整 writable restore 仍按旧 BLOCKED 边界处理。

最小负控设计足够：原包→当前缺件→原 reader 读回、幂等、控制字节不变；错实例/错 seal/链接/异目标/锁忙/未知原 call 拒绝；发布竞争不覆盖；无调度调用。fixture 合成身份只能证明控制链，不能声称真实模型/remote 或任意同 UID 对手防护。

本审查只静态阅读，未测试/项目导入/安装/模型/服务器/远端或 Git 操作。生产实现仍须 root 独审和其指定有限验收；本 PASS 不预报代码正确或动态成功。
