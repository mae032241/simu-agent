# 科学探索次序独立审查

状态：最终独立审查 PASS，无剩余阻断。本轮不授予科研效果或付费原生资格。

## 范围与规则

只读审查 `/tmp/scid-exploration-order-source-01.json` 的六个生产模块及专属测试，首冻结七项 SHA 全匹配。审查者只写此报告，没有修改实现、运行测试/构建/模型、改真实实例或读取更多隐藏候选。

- 显式新策略依赖 portfolio v2，冻结协议13；旧≤12的 schema、settings、retained job及原 pending/improve 门槛保留。H/A 只给科学 priority 前缀及理由，控制从已封存原件重建次序，没有第二持久队列账本或科学排名。
- 新 H 声明尾入，改名/省略不移除未完成条目；有效前缀保未列尾项。screened 可有理由重新插入深挖；deferred 不自动删除，科学 waived 可移出。不强制所有机制实验。
- 消费发生在当轮前缀之前，绑定实际 W 冻结的 `{mechanism_ref,planned_step}`，共享原 W+seal 合格评估身份。科学合法但排序错误仍消费原机会一次；作者补正不能用旧 W 弹出新插入的同名条目。
- 同队头 repair 保留该机会；修复后合格 A 不再请求该 repair 时完成。A audit/extract/wait、E、失败、未知执行和重启不消费或重计。H可先作科学排序再抽取/等待，但不消费 W；closeout 保留未完成队列。
- H experiment 与 A continue_w 的实际 W admission 都核队头；错 ref/重复或缺理由前缀保原 science，沿原有限 H/A 作者补正。A→H→W 不丢队列，也不会把 H 错序送到只支持 A 的决策补正分支。原权限、来源、额度及完整性硬拒边界不软化。
- 默认≤4项和完整16项分页，原4096字节总包；裁剪保队头、显式 omitted，控制 planned_step/hash不要求科研角色维护，原页篡改仍拒。

## 发现与验收

读过专属13项入口：初始 H 冲突保原件后回 H、A 纠偏/同名重插、已screened深挖、真实 audit/E 返回、repair、坏前缀保部分科学、A→H→W、H→E→H、旧12原件重建及完整20机制页。运输为 fake，实际封存、投影和控制路由均使用生产逻辑。

一项 model-facing 歧义已关闭：当前 A view 的 head 是评当前 W 前，但原 rule 首句泛称 A continue_w 选该队头；实际必须先完成非repair评估，再选 resulting head。最终 rule 明确 shown queue 在当前 A 评估前、H选 shown head、A评估（同head repair保留）→prefix→resulting head。实际 A3 用例同时检查视图head=P、评估后的队列头=Q。仅 lineage文字及既有测试断言变化，无预测字段或消费算法变化；`/tmp/scid-exploration-order-source-final.json` 七项实物已核匹配。

已亲读源码门禁 `.trial/exploration-order-source-20261013/batch-001/pytest.log`：143项通过，62.35s。首安装 `.trial/macro-role-installed-20261012/artifacts-order-20261013/` 的 `order-installed.log`：54项通过，29.02s，九模块导入来自 site-packages；实际 CLI 冻结 exploration_order_version1、portfolio v2、协议13，默认 H→A→W→A 及重启无重放通过，22模块绑定首源码。以上不冒称待修改的最终措辞已安装通过。

最后文案补验也已亲读：`.trial/exploration-order-final-view-20261013/batch-001/pytest.log` 27项通过，9.20s；最终安装 `.trial/macro-role-installed-20261012/artifacts-order-final-20261013/order-installed.log` 54项通过，28.90s。`order-installed-result.json` 的九模块确实从 site-packages 导入且当前 SHA 匹配；`result/module-bindings.json` 的22模块均与当前源匹配。实际 CLI 策略1/portfolio v2/协议13及默认 H→A→W→A、重启不重放通过，模型请求0。最终 wheel SHA 为 `7738ed6ba1bc8cd31f6ff7dded7d888f1759bc2ee83a19a480026094960f397b`。

控制仅执行作者声明的次序和显式变更，不评价排序正确性、理由科学质量、机制覆盖或科研改善。尚未运行新真实科研场。
