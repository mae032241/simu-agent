# P4c1 归档导出范围独立设计评审

结论：**设计 PASS，可冻结**。仅批准导出与包内只读检查；不是实现验收，不批准可写恢复。

静态阅读对象：`P4C1_ARCHIVE_SCOPE_DESIGN_20261017.zh-CN.md` 当前补充，以及此前已审 `THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md` 的相关边界。本轮没有运行项目、测试收集、测试、构建、安装或实例操作。

## 已收口的设计边界

- 包使用逻辑清单与序号 blobs，不生成可被现有实例推进入口直接识别的 settings/jobs 布局；不以 chmod 或可删除标记承担只读保证。
- 范围表明确包含 host-runtime/experiment-control、host-history 恢复原件、host-delivery、来源/资格、native-evidence 及 authority 历史。只按具体 owner 排除启动凭据、宿主密钥 locator、endpoint 和锁；不通配删除科学材料中的同名文件。
- 不递归 native-homes/public_root/home；未 retained 的外部 session、插件存储或不可证明所有权明确列缺口，不声称完整可续接，不复制凭据。
- 取得原 controller、UI host、budget、authority 与现有 call lease，冲突立即退出；活动、未知或未确认提交写者拒导出。持锁只读原件，不重入同一锁的 snapshot/维护路径。
- 流式复制并最终重新核对完整目录清单与身份；新增、删除和修改都使发布失败。不以数量或字节截断伪造完整包。

## 实施交审条件

实施前仍需从实际生产写入点确认全部目录与精确排除项，并给出真实 owner 的锁顺序；当前范围表不是已经扫描所有路径的证明。P4b 新增持久状态需明确 owner 和归档处理。检查器应拒绝重复逻辑路径、路径越界、符号链接、缺 blob 与哈希变化，不导入插件或执行包内内容。

这不是 OS 级防同 uid 任意写者的承诺，也不证明原生会话可恢复、历史 HMAC 可在无原密钥时重新授权、或同路径副本仍是原执行 owner。P4c2 保持未批准。本报告不覆盖尚未实现的导出锁/复制/检查器，也不改变 d2a、P4b 或 d2b 的独立评审状态。
