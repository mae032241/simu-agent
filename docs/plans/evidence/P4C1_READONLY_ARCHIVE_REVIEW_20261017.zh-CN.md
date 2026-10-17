# P4c1 只读归档包独立静态评审

结论：**本节点静态 PASS，可精确提交**。仅 export 与包内 inspect；不是可写恢复、完整环境覆盖或动态验收。

## 范围与方法

基线含 `4399149` 输入链及 `a5c3fbe` UI。阅读新 `research_loop/instance_archive.py`、`cli.py` 的 archive 子命令限定 diff、新 `tests/research_loop/test_instance_archive.py` 四条、范围设计补入 correction-ledger 的一行及本节点实施报告；对照 archive_io、原 controller/Records/authority 锁、runtime/native cleanup、原 budget.closeout_state 与 verify_observation/verify_retirement。作者全模块 literal 扫描是其实施证据；本独审追代表性精确 owner 链，不声称逐行审完整项目。

没有运行项目 import、测试/收集、CLI、线程/HTTP、构建安装、模型或远端执行。作者 AST/空白检查不算动态通过。

## 可达行为与边界

- `archive-export` 要明确原 root/全新 output，拒绝源目标包含、覆盖与非规范/符号链接路径。staging 与目标同文件系统，用 Linux renameat2 NOREPLACE 发布，没有覆盖 fallback；失败清 staging，不回滚原写者的修改。
- 包只有 metadata、逐行 manifest/dependencies 和序号 blobs，没有 live settings/jobs 布局。inspect 只读 stdlib/archive_io，不 import 插件、load factory、运行包内内容或调用后端。原 CLI 仍加载其已有 core 模块，不能宣称整个 CLI 零项目 import。
- 明确 owning namespaces 包括 control/correction ledger、host-runtime/experiment-control、host-history 恢复事实、delivery、native-evidence、来源/资格、authority 及完整 project/global/nodes。未知根只记 gap 不递归；native-homes、宿主 key locator、启动 endpoint 与具体 owner 锁不复制。正常科学材料中的 writer.lock 保留，没有全树锁后缀删除。
- `_owner_locks` 先原 controller，继而 UI host、native runner、Records node/accept/具体 call lease、admission accept、authority、ledger，全部非阻塞且在首次 inventory 前完成。冲突拒绝，不取消原研究；持锁后只读原件，不重入 snapshot/执行维护高层。
- `_quiescent` 要原 job/intent/outcome/cleanup，拒绝活过程、未知 native、未完成 prepare/accept、无 verified terminal/fence 的受管 call、replay/delivery/audit cleanup 不明。核受管终态只用共同 validator+精确原 interface/原件 loader，没有 factory/query/reconcile 或新 grant。
- export 流式 hash/copy 后重新遍历完整逻辑 scope；逐行比对顺序、数量、stat/哈希，新增/删除/变更不发布。inspect 校验两清单和全部 blob 的大小/SHA/mode、逻辑路径/重复/顺序、计数、未列 blob，并将 metadata instance/settings 身份与已验证的 settings/identity blobs 绑定。页大小仅限制返回，不能跳过其余字节校验。

## 测试价值与修正（全部未运行）

1. 实际 prepare 后归档静态原字节，固定验证 scope、普通同名科学锁文件、凭据排除、未知存储 gap、缺 public_root 的依赖记录、分页、CLI inspect、目标不覆盖及 controller.run 无法把包识别为 live root。人为 correction/locator JSON 只验证字节范围，不自证审批或科学有效。
2. 使用真实 controller/UI/Records 锁冲突与实际 job 的缺 outcome intent；若导出忽略 owner 锁或把未知 native 当静止，该负控会失败。未启动业务进程。
3. copy 期间联合修改原内容与新增文件，验证最终 scope 重扫拒绝、原修改保留、无已发布包/staging。它是联合扰动，不分别证明两个检测分支都被执行。
4. 改 manifest 后重算外层 checksum，要求语义 validator 拒绝 traversal/重复项；坏 blob 和 symlink 单独拒绝。评审指出坏内容前 chmod 可能让 mode 差异代替内容检查，已修为写坏后恢复原 mode，再要求 SHA 拒绝。

这些测试不伪造成功 native/远端 JSON；不靠 subprocess/installed 外壳宣称真实资格。当前没有实际执行结果。

## 限制与提交

原件复制和 inspect 多次流式哈希；每页仍验全包。每目录排序、call/intent 集合、持锁 FD、JSONL 单行/metadata/settings/terminal JSON 和原 ledger fold 仍有内存及 IO 成本；没有恒定资源/硬实时或 OOM 根因结论，没有新增隐含材料 cap。真实大包、磁盘满、跨进程发布竞争、活 native/交付和 renameat2 实际行为尚未动态验收。

包的内部一致性不证明外部来源真实性、签名授权、完整平台环境或任意 detached/同 uid 写者静止；外部插件存储未有冻结拥有范围时明确缺口。历史决定/消费只是原字节，不续 grant。P4c2 可写恢复未批准；d2b 仅设计另审，不能混入此次提交或由包重建执行 owner。

可提交范围：新 instance_archive.py、CLI archive 两分支/参数、新四条测试、范围设计 correction-ledger 补行、实施及本独审。未发现剩余具体阻断；不要求扩矩阵或开启任何动态检查。
