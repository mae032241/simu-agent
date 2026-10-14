# Closeout封存与搜索重放独立复核

## 最终结论

**PASS，限定closeout封存/搜索重放一致性与零模型工程资格；未发现剩余阻断。** 新安装版本新增回归10项通过，旧d5462f9安装版本同一tests02为4失败/6通过，四项closeout行为失败已消除。审查基线为 `d5462f9`，权威冻结为 `/tmp/scid-closeout-search-production-01.json` 两个生产文件与 `/tmp/scid-closeout-search-tests-02.json` 一个新增测试文件。审查者仅阅读源码、原件和父代理运行证据，仅编写本报告，未运行测试、构建、模型或恢复真实实例。

## 根因与修复边界

真实场 A012 是 `purpose=closeout`，封存的科学控制回执为 null focus/allocation。旧 semantic 在 closeout 不解释探索意图，但 search 重放仍解释 A 的 audit 决策，重新得到先前 h001.m1/screen，触发封存一致性拒绝。

- semantic 与重放共同调用 search.interpret；closeout 返回中性 focus/allocation/diagnostics，并保留原探索状态的副本。apply_source 先核当前协议、search_status、搜索diagnostics和中性focus/allocation，再返回；并非跳过封存回执验证。
- closeout 不发布探索变化，其他selection/decision/portfolio unresolved也不会清掉原focus/order。既有portfolio与decision的closeout排除继续有效。普通科学A仍可按明确选择改变探索解释，不扩大improve配额、机会计数或预算。
- 新回归覆盖真实build/seal closeout A→audit unavailable原回执→后续closeout A；全探索state相等、重复validate/project树字节不变；五种协议/状态/诊断/focus/allocation篡改仍拒。普通A测试使用真实build_job和parents，不以mock绕过来源读取。

## 实际运行证据

证据路径均相对外层 `.trial/macro-role-installed-20261012/`：

- `artifacts-closeout-search-finaltests-20261014/breadth-context.log`：10通过，3.23s；result JSON returncode0、0模型请求，32个安装模块的实际字节SHA＝记录SHA＝当前源码，审查者已复核。
- `artifacts-closeout-search-finalbaseline-20261014/pytest.log`：旧wheel同一tests02为4失败/6通过，3.00s，失败为封存意图与重放不一致。
- `artifacts-closeout-search-01-20261014`：fresh wheel/基本实际CLI门禁PASS；既有窄集失败与基线对照保留。

`artifacts-closeout-search-01-20261014/original-replay.json`：新安装版本对真实场只读比较 project(12)与project(13)全状态相等，5546个原文件SHA前后完全相同，0模型请求。原场未续跑、迁移、回填或恢复。

既有六文件窄集在修前与修后均53失败/49通过；baseline-comparison.json记录失败测试标题集合相同。保留旧schema夹具债务，不称全仓或该窄集绿色。新增tests01在旧wheel为4行为失败/5负控通过/1普通A夹具失败，新wheel为9通过/同夹具失败；tests02仅将该普通A夹具改成真实构建，保留原断言。

## 冻结SHA

| 文件 | SHA256 |
| --- | --- |
| search.py | `7c51a0bf2208e65b6283c2e14268db9d0e2c6bbf979818b00a62bb263d24c093` |
| semantic.py | `d0d79b627d218895ce265ca62038f0e6ba17f4b3725d83e1ce16b2ced594335d` |
| test_closeout_search_replay.py | `7b8ae9f35f5e509082328ba266f8e08c708edd2f9de02f49d071be4c51cdfbfa` |

本次资格限封存/重放一致性与零模型工程路径；不授真实模型、科学结论、目标达标、在线恢复或额外探索执行资格。
