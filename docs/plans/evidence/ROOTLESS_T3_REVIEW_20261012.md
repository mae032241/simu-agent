# T3 独立代码与 launcher 审查

日期：2026-10-12。审查者 `/root/n1_runtime`，独立于生产/测试作者。基线 T2 提交 `a1881ca`。

## 结论

**PASS：通用冻结角色指导、cov 原件反馈/CLI兼容、已测 bwrap 传输边界与安装范围，无剩余阻断。**

仅只读审查源码、测试和父代理证据；本人没有运行产品测试、模型、公开实验、评分、修改生产源码或提交。T3是原生 W 使用既有有界执行入口的薄实现，不新建搜索 executor、助手系统、预算或科学资格账本。

不以本结论宣称实际 Codex 权限、原线程恢复、观察驱动科学决策、效率或成绩改善已通过；这些属于未来新冻结场次。无 hidden 输入或 N5 恢复。

## 精确冻结对象 SHA256

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/guidance.py` | `32225de55f2171e63f2dc07c380a59330b4a435fe44506d0d49f33b496a2b57b` |
| `src/scidiscovery/research_loop/contracts.py` | `03e0669a21e385694518e626cf93d43239edad3c7230e15e8fd0e0eb5115884e` |
| `src/scidiscovery/research_loop/controller.py` | `6608a24c223743a583a00dfc50d4743ad52ffcc3f12d9bcb214c61eb9cf0c967` |
| `src/scidiscovery/research_loop/cov_lineage.py` | `0602ae27f931ae53825f4f79e6cfa4a29b913177826ea420f16113cfa97663a5` |
| `scripts/acceptance/rootless_cov_launcher.py` | `7d8851839b3d0b65f166a83b2ff803b7dd97bc91b2caaa3ecc143d4c0fe858b6` |
| `tests/research_loop/test_scientific_guidance.py` | `db5919ddf558f4e8d6052548a036e6e7b04b3548894501453cede7e91df2cf57` |

## 科学与控制职责

- 通用 DEFAULT 全为领域无关的 H/W/A/E 科学职责，无 cov `exp`、数据格式、算法或题目机制。四角色 literal合计1511 UTF-8字节、上限2048；domain工具短句只能由新场 operator override 冻结，不写核心默认。
- prepare复制经过校验的 literal到settings，新job只带当前role literal，science_view仅读该job。retained job有自己的literal则保留，无该字段不补；改未来DEFAULT不改旧job/task/seal。科学结果schema8无新增字段，native权限不由这些文字授予。
- W在H范围和原预算内根据观察选择新建、改进、回退或修复；H保机制delta，A区分负证据、工程失败与代理盲区，E保原问题与来源限制。无helpers，原范围、repair root、未知不重放、预算与交付预留仍权威。
- cov省略script仅使用绝对 `EXP_DEFAULT_SCRIPT`，缺失或相对路径不接受调用；显式script仍可科学选择并精确冻结。不是旧模型fallback或按recency选材料。
- 新公开反馈仅从本call已证明row读 finite val_score/val_acc/wall_seconds、有界metric/error和评估key；不输出scope、proof、SHA或host配置。known failed可显示原诊断，unknown仍不获得身份/代理成绩。反馈本身不继承审计或科学支持。
- public submitted artifact仅在与exact managed archived model SHA/size和公开candidate一致时绑定candidate；不匹配保null/partial，缺产物保未知。它是观测，不声称audit或confirmed，不覆盖N6b确认权威。

## Launcher 与已测边界

- trusted host先读实际job/accepted execution，再调用T1 configure；科学namespace只获得immutable config只读挂载，job/控制settings不在该mount范围。wrapper机械绑定由host产生，角色不手填hash链。
- public根及原harness白名单/摘要校验保留。真实runs绝对alias与 `/opt/exp/runs` 同源挂载，回执里的model路径与T1 exact约束一致；旧 `exp`其他子命令仍委托原CLI，只有run/lineage-status进入新模块。
- fresh exec参数、原输出路径、工作目录、model/reasoning及固定配置约束保留；本launcher不支持旧wrapper resume。bwrap具有PID namespace、die-with-parent、独立session；角色profile关闭network/apps/multi_agent。此处没有另起executor或免费预算。
- 当前config包含host机器绑定供wrapper消费，CLI不把该链回显给科学作者。本门禁证明只读和所测mount路径缺席，不声称任意native代码或所有路径秘密隔离已资格。

## 门禁与首失败解释

父代理统一持共享串行锁。证据位于外层 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`。

| 检查 | 结果 |
| --- | --- |
| `.trial/t3-source-20261012-01/batch-001/pytest.log` | 90 passed/1 failed，30.93秒；不是全批通过 |
| `.trial/t3-source-20261012-02/batch-001/pytest.log` | 最终专属12 passed，1.58秒 |
| `.trial/t3-installed-20261012/artifacts/result/result.json` | fresh wheel独立CLI 9 checks PASS，0 model requests |
| `.trial/t3-native-gate-20261012/result-01/result.json` | 实际bwrap、两个原public constant-zero run、同节点parent复用、config readonly、hostsettings/private/未挂canary缺席 PASS；0 LLM |

唯一首测失败为 tiny backend row没有metric字段，fixture却强制索引result.metric；源码条件性回显正确。修测试保val_score、evaluation_key、本call source、无private metadata、readonly查询与不新增run断言，未改生产或放宽原件校验。

本人实际读取最终 ZIP、source、installed files核18/18模块逐字一致，wheel SHA `fb517c29ae5bf87f58248195839047579c1968e0daf8c3fd2a372348776dbc2c`；实际安装H/W/A job与science-task的role_guidance逐字等于settings对应literal。真实namespace gate的public成绩均为0.0，证明合法格式/绑定而非科学质量或适应性效果。

## 后续预算与资格限制

T5草案6M/3600启用秒中，既有delivery_reserve公式得到2.15M tokens、1050秒、5动作slots：3×550k+500k；3×300+30+90+30；3个A加submit/confirm。W有效ceil为旧search2M/900与node1.2M/900的较小值。旧样本tokenmax仅支持有限试用参数；420/900/closeout300秒不是完成保证，观测用量有迟滞且不可承诺零overshoot。参数须新场冻结，不能据本报告扩额或启动对照。

实际Codex角色权限、增量用量/断点恢复、根据真实科学观察改变下一步、低成本收益与最终交付仍待新场证据。T4 staging未进入本wheel，不能计为本次通过。

**最终判定：上述精确源码与零LLM工程范围PASS，可提交T3。**
