# T4 独立源码与安装审查（2026-10-12）

结论：**PASS，范围内没有剩余阻断**。基线 `ac8e3fc`，审查其上的 T4 未提交差异。本人未写生产代码、未运行测试或模型；亲阅父级门禁和原安装产物。

## 路径与权责

- `controller.prepare` 默认将 selection_protocol=1 仅冻结于 unified layout；`contracts.build_job` 对 retained job 取自身 marker，缺字段为0，不跟随新 settings/default。science_view 校验 marker 与冻结 candidate view 一致；旧角色文字从 job literal 读。科学协议8 schema 未变。
- `lineage.project` 仍先验证单一封存来源。纯 selection 投影只抽公开白名单，不读取文件/隐藏分数/交付 ledger，不执行或产生第二权威。optional ValueError 降级只覆盖该纯投影，不覆盖原件/SHA/权限/科学身份校验。
- 同 exact evaluation_key+direction 只列 observed proxy；未指定版本不排名，不构造目标权重或目标最优。A 最新 null 清当前推荐，历史非 null 单列；无 observer 不更新 current；public actual 只是历史观测。缺 audit/冻结交付事实为 unknown，不授 N6b 提交资格。目标适用性、负结果和盲区归 A。
- 新候选槽替换 T2 单 brief，UTF8 indent2+newline 总包≤4096B，有遗漏计数，原分页继续可读；未增机械科学字段、全祖先包或新分页引擎。guidance 仍通用、总1738B；模型不负责哈希/receipt维护。
- 已关闭类型口：排序前 step 强 int；enum/list 和 candidate引用先验类型；极大 metric 不让 OverflowError 越过 optional ValueError 边界。未扩成 broad source catch。

## 独立读取的证据

1. `.trial/t4-source-20261012-01/batch-001/pytest.log`：**71 passed in 13.25s**。五文件 selection/selection_binding/lineage_view/scientific_guidance/closeout；结果文件状态passed、returncode0、cleanup_complete=true。本人未重跑。
2. `.trial/t4-installed-20261012/artifacts/result/result.json`：fresh installed CLI 9checks、HWA wait、0 model_requests；结果 SHA `88466964e6501197cd8cf5730df9ee68f099678b64583b7a400b4be9af8dd720`。
3. 亲自按字节读取 **19模块 source/wheel/installed** 与 module-bindings，每项一致；wheel SHA `63f459e6ba78e80e9af04047650e9f38b2d26eff4be6d01792eb3791c672ff73`。
4. 亲阅安装 A003 science-task：只有单一 lineage，没有 history/search 重复槽；candidate selection_protocol=1、target_best=null、delivery unknown、推荐null；完整 lineage3380B。source fixtures 覆盖 latestA null/历史推荐、旧job科学原件及literal逐字保留、marker漂移拒、输入不变、跨版本/并列/审计未知/hidden拒、UTF8总包与 omissions。
5. `git diff --check` 未输出错误。没有产品测试或模型由本人执行。

## 范围限制

- 仅公开事实投影与安装接口通过，不证明科学选择收益、目标级评分、跨场稳定性或实际 Codex native 权限。
- explicit hidden-key 拒绝不识别改名 secret 值；可信 observer/config 的公开隔离仍为前提。
- 首版无冻结 audit/delivery receipt接线，显示 unknown是正确边界，不将合成 receipt接口宣称生产资格。
- T5路径 alias与 managed source/model交付修复是独立后续节点，本报告不批准其未实现能力；不改变本 T4 source范围。

## 精确冻结 SHA256

- `src/scidiscovery/research_loop/selection.py`: `a500248d576478e8e40ca04b04b6e63ef5f0b9022d6f7d117ecb0923a680e5a0`
- `src/scidiscovery/research_loop/lineage.py`: `920747395e69cbf91436e1ea28d3202a3071a42d18c11c22b7767395ea8255c8`
- `src/scidiscovery/research_loop/controller.py`: `6587f13c94975c0ee23e7db1f8193d185e9a238c83c5ff71bc58313fc9a60f53`
- `src/scidiscovery/research_loop/contracts.py`: `721af3d42e3ef981162a2aaea24ac4649836fcc7fc4b0091507c64b7cec32aa3`
- `src/scidiscovery/research_loop/guidance.py`: `985b05878a5c1425cc3da53fcc6b8449eeecb4c4bd7f106aef2dfd7289c6af34`
- `tests/research_loop/test_selection.py`: `812cf6fe3c4dff68ad2f8114f31ff82abd3225f925a6836d2ceec8bfa64c33e7`
- `tests/research_loop/test_selection_binding.py`: `75bda757671e9c8e27547aae34e22d516c1bb127ee96c82ff1505cb7a1882b25`
- `docs/plans/ROOTLESS_T4_PUBLIC_SELECTION_DESIGN.zh-CN.md`: `5f90cdb6e6c522e5f8bda95833ed60d61515d02153db5a286bf6472af21d40ae`
- `docs/plans/fixtures/rootless-selection-v1.json`: `cd3a552321a8a22fd9f41ba7c28a9563e822b58771319070de8353b84e558c74`
- `docs/plans/evidence/ROOTLESS_T4_PUBLIC_SELECTION_20261012.zh-CN.md`: `961b119bb0daf17108a083c85f42f17b5a5cd8d3ffd441671a52c4ef919077b8`
