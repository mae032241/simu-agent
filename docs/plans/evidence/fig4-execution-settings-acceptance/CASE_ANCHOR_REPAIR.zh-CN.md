# 案例锚点丢失修复验收（2026-09-15）

状态：源码修复、独立复审和定向验证通过；尚未部署，生产 Fig.4 仍停在已封存计划/源码之后的打包节点。本记录不替代实例科研记录。

## 最小修复

- 四个生产文件：project_packager.py、project_materializer.py、transform_adapter.py、operation_workspace.py。
- 控制层在 DeckProjectDraft.case_anchors 保留已经核验的声明。案例是否存在不再依赖是否有 comparison variables。沿用既有 DeclaredCaseAnchor 类型和声明，不增加 Agent 填表要求。
- 打包和修订模板优先复用完整锚点；作者元数据去除这一控制生成字段。
- 旧项目缺该字段时，序列化不增加 null，保持原规范字节和项目证明摘要。历史打包只重建旧对象确实保留的参数绑定锚点，不猜测丢失的源位置；新对象继续核验全部声明。参数控制、源摘要、证明、完整重建相等、匹配独立审查和执行审批仍保留。
- 不修改科学方案、求解器源码、原历史对象、角色配置、审批流程或运行器协议。

## 验证

所有 pytest 串行运行，进程虚拟内存上限 2 GiB，BLAS/OMP/MKL 线程数均为 1，关闭外部 pytest 插件自动加载。没有运行全量测试或真实求解器。

1. 扩展既有作者→独立审查→打包回归：四个组合（单案例无控制参数/参数比较 × 导入计划/受审查生产计划）全部通过，6.58 s，峰值 RSS 126572 KiB。包含声明模板复用、历史规范字节和证明兼容、新对象字段删除/空声明、证明篡改及重建差异负例。
2. 相邻路径第一次执行：35 通过，1 失败，21.98 s，峰值 RSS 142908 KiB。失败为 test_local_tcad_debug_rejects_a_private_output_symlink 的既有诊断文案断言：拒绝本身发生，但测试要求 message 包含 unavailable。
3. 在 /tmp 的隔离插件副本中，把四个生产文件恢复到 HEAD，显式确保它优先于仓库插件路径导入。同一新单案例测试准确复现 missing_control_binding: planned case has no declared source anchor；上述符号链接文案断言也失败。此前第一次隔离尝试被仓库 conftest 的路径插入覆盖，已作废，不作为基线证据。
4. 继续执行尚未运行的 test_l4_local_tcad 用例，以及 test_tcad_gap_continuation.py、test_tcad_result_analysis.py：111 通过，1 stress 用例排除，41.47 s，峰值 RSS 135264 KiB。未重复已经通过的前段用例。
5. 累计源码定向验证 150 项通过；另有 1 项已在未修改插件上复现的既有断言失败。未把这项失败改成跳过或宣称全部测试通过。
6. 构建 tcad_artifact-0.1.0-py3-none-any.whl（SHA-256 b2806ddd2fe986ac163dedf78c15194b10a3316b060cb6feffdeef0de9c79a2a），解压后核对四个生产文件与候选源码逐字节相等，再优先从该安装产物导入，运行无参数单案例作者→审查→打包→执行预检：1 通过，2.73 s，峰值 RSS 126468 KiB。这不是生产审批或求解器验收。
7. git diff --check 通过。

## 独立审查

复用独立工程审查者 execution_settings_impl_review，仅进行源码只读审查，无并行测试。首次发现一个测试直接调用未传新增 with_controls 参数；已同步调用，使其覆盖无参数单案例到执行预检。最终六文件复审结论 PASS：未发现新的兼容、证明完整性或职责边界阻断。详见同目录 CASE_ANCHOR_REVIEW.zh-CN.md。

安装重启后，应刷新运行时目录，重新预检并打包已封存的 fig4_single_entry_nonlinear_author_1.output 与其匹配审查，再经正式 UI 审批继续；不需重写科学方案或源码。生产续接是否成功尚待验证。
