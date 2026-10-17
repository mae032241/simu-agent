# P4c1 归档包范围补充（设计独审通过）

独立审查见 [设计审查](P4C1_ARCHIVE_SCOPE_DESIGN_REVIEW_20261017.zh-CN.md)。本补充只解决导出与包内只读检查；不引入可推进副本或归档恢复授权。复用已提交 `archive_io` 原语。P4b 的 CLI/UI 文件暂由另一执行者持有，未实施本节点。

## 原件范围

- 导出命令显式指定原实例与全新目标包目录；禁止目标位于原实例内，也禁止覆盖已有包。包顶层仅有清单/元信息；文件内容放入按序号命名的 blobs，不保留可直接作为 live 实例运行的 settings/jobs 布局。逻辑原路径仅在清单中保存。
- 从框架拥有的 settings/identity、jobs、control ledger、project/global、project/nodes、native-evidence、host-history、execution-authority 持久事实取得范围。逐文件流式复制/哈希；不把完整内容或全文件清单读入单个 JSON。具体完整目录名须实施前逐生产写入点核对，未知根目录登记为范围缺口，不偷偷全盘递归。
- `native-homes` 不作为普通科学成果复制：它含运行环境、缓存及可能的凭据。框架保留在 native-evidence 的原件仍归档；未被保留的外部原生 session 明确列为缺失，不宣称会话可恢复。
- UI endpoint、浏览启动凭据、宿主 secret locator、锁文件不复制为持久授权。保留决定/撤销等历史原件，不导出密钥。归档验证可证明字节一致，缺原密钥时不把历史签名升级成新执行权限。
- 插件外部存储只接受已冻结的明确拥有范围；无声明则列外部依赖缺口，不扫描 public_root/home，不追符号链接。特殊文件/越界路径/不可判定所有权使该次导出失败或显式缺口，不能静默冒称完整。

## 已核到的范围与生产 owner

| 原实例路径 | 生产 owner / 导出处理 |
| --- | --- |
| settings.json、settings-identity.json、host-started.json、pause.request | controller/contracts；完整原件，暂停标记仅历史事实。 |
| jobs/、project/global/、project/nodes/ | controller/contracts；含原始目标、节点成果与受管 work/lineage/calls 原件；不按附件数量裁剪。 |
| control-ledger/ | budget；完整追加事件，含科学及执行资源账；只读包不授预算。 |
| correction-ledger/ | correction；实施前全模块写入点扫描补全，保留原触发/ack追加事实，不复制新许可。 |
| native-evidence/ | native/runtime/execution；原 intent/outcome/process/continuation/封存证据；不据缺失原生环境声称可续接。 |
| host-runtime/experiment-control/ | budget/experiments；原 interface projection、准入窗口与accept记录，不能因为名称runtime就漏掉。 |
| host-history/ | history/qualification/execution_recovery；观察原件和追加恢复ref。 |
| host-delivery/ | delivery/budget；候选对象、prepare/action/process原件，存在未完成owner先拒导出。 |
| source-provenance/、qualification/ | qualification/formal_review；来源原件、声明和审查合同。 |
| execution-authority/ | execution_authority；保留contract、host-key身份hash、calls和requests下历史决定/撤销；精确排除host-key-source.json、ui-endpoint.json、ui.lock、writer.lock。缺验证密钥不等于历史决定有效。 |

已核来源是上述模块的写入位置，不声称表外目录不存在。实施必须完成全模块路径扫描并对未识别根目录显式报告。`*.lock`只按实际锁owner位置排除，不能通配删除用户成果中同名科学文件。P4b若新增持久UI状态，应先说明它是否原事实或仅瞬态，不自动纳入科研授权。

## 静止与一致性

- 取得原 controller writer；另以非阻塞方式取得原 UI host 锁、budget ledger 锁、authority writer 锁和已存在受管调用的写 lease。锁冲突立即退出本次导出，不取消研究、不等待模型。具体锁顺序按实际 owner 核对，不新增全局调度锁；持锁检查只读原件，不调用会重入同一budget/authority/lease锁的高层snapshot或维护接口。
- 不以 controller writer 独占替代活动作业检查。原生必须有原 outcome 与确定清理事实；任何 running/unknown/未确认提交/未结束交付或外部写者不能证明静止时拒绝本次导出。导出本身不调用 query/reconcile/submit，不更新科学记录。当前软隔离不承诺阻止同 uid 任意外部写者。
- 复制前记录原件身份/大小/时间戳/哈希；复制后及最终发布前重核逻辑清单和文件身份。新增/删除/修改则不发布，旧实例与旧包不动。无隐含文件数/总字节截断；可选显式磁盘额度仅使导出失败，不能令科学封存失败。
- 包创建、复制、检查流式进行；原子发布前所有清单行与 blob 哈希对应。检查器拒重复逻辑路径、缺 blob、非规范路径、越界/符号链接和哈希变化，不导入插件或执行包内代码。

## 公共入口与证明边界

- 接原 CLI 的 `archive-export` 与 `archive-inspect` 子命令，不另建实例注册表。inspect 输出有界统计/分页清单；完整清单与原件保留在包中。
- 不提供解包成 live 实例的命令，不通过 chmod 或可删除标记实现只读限制。既有运行入口不会将 blobs 布局认作 live 实例。手工重建目录不是已授权恢复，P4c2 仍待独立设计。
- 最小负控只覆盖导出中变化、活跃/未知写者、路径篡改、重复清单、包无法被现有实例入口直接识别、缺外部原件如实报告。当前只写必要用例与静态审查，不执行项目、安装或大规模回归。
