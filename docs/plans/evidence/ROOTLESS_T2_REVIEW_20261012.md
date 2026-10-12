# T2 独立代码审查

日期：2026-10-12。审查者 `/root/n1_runtime`，独立于生产实现者。基线为 T1 提交 `5a4713e318e9a973f2891f5033711b627ad2a622`；本次工作树含独立清理文档提交 `95a15b3`，不将其归为 T2 生产差异。

## 结论

**PASS：冻结的新 lineage marker、统一默认工作集、原件分页、旧布局兼容与已测安装范围，无剩余阻断。**

本人仅只读源码、测试和证据，并核文件字节；未运行产品测试、模型、训练、评估器，未修改生产/测试源码或提交。测试均由父代理持共享串行锁执行。本结论不批准实际 native namespace、T3 效率、T4 选择效果或 T5 启动。

## 最终 source/test SHA256

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/contracts.py` | `97761cb18fdb3dcea133e2e172e3d0c1a77693dd331049ad5a22634b368c971a` |
| `src/scidiscovery/research_loop/controller.py` | `fc68dfd1c1b0878e75d6f43193a6529815f44b7193931cba1f81c1bea48f1728` |
| `src/scidiscovery/research_loop/history.py` | `88575dacac54d1a6d1101096fa7d1f74296cc61cfc78614fa5e9d21469e1e645` |
| `src/scidiscovery/research_loop/lineage.py` | `4b86cec509fb6b946aa7e0981d6d5aad381457ef894157ce51a4c72eed621897` |
| `src/scidiscovery/research_loop/search.py` | `fb753e7d1522b118a5a03dbc64916c8b6ce03f1a73cbd5a6cfe0089a19a053ae` |
| `tests/research_loop/test_lineage_view.py` | `86cb7c444c014146d2b11183e3536dd8887d421e489b4871e34e902290f41cf7` |
| `tests/research_loop/test_search.py` | `9558e8001e173668f5b8cb448d9b4796fd08772873f010a0ffdd69d49429a79f` |
| `tests/research_loop/test_semantic_recovery.py` | `36508504bf79812ea194deaa920367ebf38942162a7168a3c9f178edf45b5b95` |

## 语义与权限边界

- 新 prepare 冻结 `lineage_projection_version=1`，job 继承自身 retained marker，不将旧 job 或旧 settings 静默迁移。科学 schema 仍为协议8；旧1..8无 marker布局、任务/原 raw/seal/schema字节保持，由八协议恢复用例核对。
- 新 science_view只投递一个 lineage brief，不另加 history/search/default implementation_options；全部 lineage 内容按 UTF-8、indent2、末换行共同计≤4096字节。可删导航预览明确计遗漏，身份槽及原件入口保留；implementation options 后加也重新执行同一包界限。
- `history.source_sequence` 提供共同源边界，records、机制、候选和关系共享源序列；`search.fold`保原科学解释及 native intent/slice/repair。候选装配迁入 lineage，history facade沿同实现保 legacy结果，不建第二 ledger、预算、活跃头或资格表。必要准入 focus/repair/limits仍冻结于host job，未交角色决定。
- 原科学全文分页面仍可按需读取；节点≤8、候选/机制/实现/关系≤16且页≤64,000字节，联合打包。第9节点、第17候选/实现及20长多字节机制可达，不将前16当权限边界。绑定页只读、hash/大小校验，缺页或改页不成为语义补正。
- **已关闭私有 receipt 投递发现：** host图可保 reuse material完整原件，但公开关系页由 `public_relations`只投稳定 implementation ID、来源节点、有界label和原科学入口；不把绝对host source、SHA、私有原件receipt投递给科学角色。实际 selected-input原件权限/单跳/null/clear/replace不变，不复制祖先附件。
- 机械 execution_status从T1原 context同源投影，known_failed/known_success与科学作者负结论分栏；host不因工程失败判机制无效，不制造新科学证据或进展。
- Closeout使用原 source_cutoff与额外直接作者节点，普通历史不能跳未封存洞；未改变N6/N6c的消费、未知、恢复、提交确认或资格。T4未混入，当前推荐等槽保原历史语义，科学适用性不由host判断。

## 失败定位与保护断言

首批并非通过：`.trial/t2-source-20261012-01` 为120 passed/3 failed，35.40秒。

1. 五节点实际 detached native夹具把新 task无 `search` 当legacy，A3主动写finish；控制器诚实结束3。修复fake科学输入读取新lineage机制page及旧search两条路径，保真实H-W-A-W-A、两W计量和重启不重放断言；没有将生产默认入口全部pin旧布局。
2. 首H无历史时新布局没有旧空 candidates占位页，损坏测试错误索引 files[0]。改为合法H1/W2前缀后accepted A3真实readonly节点页损坏。
3. 20长UTF8机制检查旧search.view路径，转新lineage机制索引；保20机制、两页、16行/64KB、readonly、160B最小试验摘录、截断与原文入口全部检查。

第二批30 passed/1 failed，6.25秒；尚存损坏夹具前驱W2 instruction未承接H1 route_reason，controller先拒既有W2，不能证明A3坏页。最终按原H路由构建W2，严格assert **A3 seal_pending、completed_steps=2、Bound scientific history page changed、无A3 seal/无补正新job**。未仅扩大可接受status掩盖错误生命周期。

## 验证证据

所有路径相对外层 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`。

- `.trial/t2-source-20261012-01`：六文件首批120/3，非PASS，保留过程证据。
- `.trial/t2-source-20261012-02`：新lineage/view全文件、五节点native及机制/原件负例30/1；通过部分保护断言保留，非全批PASS。
- `.trial/t2-source-20261012-03/batch-001/pytest.log`：最终损坏参数组+closeout13，**16 passed，9.77秒**。最终修订只闭合上述fixture，沿未失败范围继续成立，不拼称一个不存在的全套通过数字。
- `.trial/t2-installed-20261012/artifacts/result/result.json`：fresh wheel/独立venv真实CLI 9 checks PASS，0 model requests，H→W→A与T1调用/unknown/锁/原件封存路径。
- 本人只读实际wheel ZIP、当前source、installed files核 **17/17模块逐字一致**；wheel SHA `8abaf641e9858971edcee2988202fd93e0232cf94df8d671f6f1dbdec53882b2`。
- 本人读取实际安装实例：settings和H1/W2/A3 job均marker1；三science-task只有lineage、无history/search；完整lineage写入大小依次1059/1579/2115字节，均≤4096。

## 未验证结论

默认 brief较小不是token、费用或效率收益证明；1000节点测试是包界限合成测量，不证明真实长链平台性能。实际native跨namespace/权限及同thread增量用量沿原未资格边界。T4规则与T3搜索效果须分别独审；本次不读hidden、不恢复N5或扩额。

**最终判定：T2上述精确冻结与工程证据范围PASS，可提交。**
