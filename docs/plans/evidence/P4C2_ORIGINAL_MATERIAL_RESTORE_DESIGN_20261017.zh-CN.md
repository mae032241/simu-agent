# P4c2 小节点：原实例缺失成果文件恢复（设计静态审查通过）

本节点已获 root 授权设计；不是完整灾备或可推进副本恢复。可信单宿主、原实例路径、操作者已停止 controller/UI/Worker；仍用真实锁与原终态事实验证静止。不要求抵抗同 UID 恶意复制，也不引入跨宿主 owner/fencing 服务。

## 唯一入口与范围

新增 `archive-restore-material --root ORIGINAL --package ARCHIVE --step N --index N`，index 沿现有科学资料页的精确封存成员序号。恢复到当前 seal 声明的原 source；不接受目的路径或任意包内路径。

操作者须保留当前 settings/identity、job/raw/result/seal、ledger、authority/calls/recovery；本操作不从包修复或覆盖这些控制原件，也不替代后续预算/资格准入。仅恢复普通 `project/nodes/N/artifacts/…` 或该节点下既有 nested `experiments/…/artifacts/…` / experiment conclusion 成果中**当前 seal 已命名**且在包内有对应原件的文件。不得修复 call 证据、host-history 原件、native/control 事实、密钥/session 或外部材料；managed 完整原件校验继续照常，缺失时拒绝，不增加 loader overlay。

## 调用顺序

1. 原 root 与包均 canonical、无 symlink、相互分离；root 必须是当前协议。复用 `instance_archive._owner_locks` 取得 controller/UI/runner/Records/authority/ledger 原锁，冲突即退出；复用 `_quiescent` 核原 native 清理、共同 terminal/fence 与无未决 delivery/preparation，不 query/reconcile/取消/发任务。
2. 复用 `instance_science._sealed` 核当前 job/raw/result/执行引用；按当前 seal 的唯一 index/path 取 material，复用 `_label` 核封存名。source 只能精确等于该 node 的普通 artifacts/nested experiments 所属位置，且必须位于原 root 内、无链接。索引不是对目录重新排序。任意同 hash 的其他 origin 不作候选。
3. 完整 `archive_inspect` 校验原只读包；instance_id/settings_sha256 必须匹配当前原件。流式查 manifest，要求包中同路径的 producer seal 与当前 seal 字节身份相同，材料行精确 logical source-relative path + sha256 + size_bytes 与当前 material 一致。旧包若不含当前确切 seal/成员则拒绝；绝不恢复包中 ledger/settings/seal。
4. 目标已存在：regular 且 exact hash/size 则幂等返回；不同字节、目录或 symlink 均拒绝。目标缺失：只按已验证材料行复用 `archive_io.copy_verified` 流式复制到 root/host-runtime 下独有 temporary，再以 `os.link` 无覆盖发布到 exact source、fsync；不预建 live 根。跨文件系统 link 失败即拒绝，不 fallback 覆盖。finally 清理 temporary；进程崩溃残留不在 artifacts/，不能成为 collect 的科学输入。重复操作重新核验，不成为调度/资格状态机。
5. 不删除 pause、不追加/重置 clock/grant/reservation、不续决定、不自动 continue。结果只报告 `material_restored` / `material_already_present`、step/index/name 与“文件恢复不授执行/科学资格”。既有继续入口仍自行执行原预算、来源与 unknown 不重放准入。跨 boot 补字节不代表跨 boot 科学推进获准。

## 真实 owner 与实施文件

- `research_loop/instance_archive.py`：一个材料恢复函数与少量局部读取/匹配，复用原包检查、锁与静止判定；不另建恢复 registry/数据库。
- `research_loop/cli.py`：上述显式命令，保留 root symlink 拒绝（不能先 resolve 掩盖）。
- `docs/ROOTLESS_CLI.zh-CN.md`：原实例缺失成果恢复能力与灾备/call/control 未支持边界。
- `tests/research_loop/test_instance_archive.py`：沿原小 fixture；封存的科学内容/cleanup 仅为合成 native 边界，不声称真实模型/平台资格。
- 本设计、实施证据。生产外文件不动；其他执行者的 Local 来源模块/deploy 不在范围。

## 最小负控（只编写，由 root 串行决定执行）

1. 公共 CLI 从真实原包恢复普通及 nested 已封存成果，原科学 reader 读回同 bytes；重复幂等；current settings/seal/job/ledger/authority 字节不变，继续入口未被调用。
2. 同 root 后来新增的控制事件不被旧包覆盖；存在不同目标/链接、错误 index、另一实例或不含当前 producer seal 的包拒绝，原件不动。
3. 原 controller/UI/Records 锁忙或原 native/preparation/managed 事实 unknown 时拒绝；不能借材料恢复清除未知执行。可复用既有锁负控，不新造重环境。
4. 复制中目标竞争出现不同 bytes 不覆盖；包 blob/路径身份篡改拒绝。现有 archive-inspect 路径/清单负控继续保留，不复制全部矩阵。

本节点补上原实例内可实际读回的缺失科学成果；只剩包、控制原件丢失、旧消费高水位不明、跨路径/跨宿主 clone 的完整 writable restore 仍未实现。普通只读 v1 包可作为字节来源，其 `restorable=False` 不升级为执行身份或完整恢复资格。

本轮禁止执行测试、项目 import、安装/构建、模型/服务器或 Git 写入；仅文本/AST。migrate 独立静态设计 PASS 后 root 已批准实施；测试由 root 唯一串行执行。
