# T1 独立代码审查

日期：2026-10-12。审查者 `/root/n1_runtime`，独立于生产作者和测试作者。

## 结论与范围

**PASS：T1 调用原件、可选 observer v2、可重建关系投影及已验证的 installed CLI 范围。无剩余阻断。**

基线 `c1dea80`，按已通过 T0 的唯一 B 薄 cov wrapper 实施。审查为只读源码、测试与证据核对；本人没有执行产品测试、科研模型、训练、评估器或修改生产/测试源码。父代理运行门禁并持共享串行锁。

本结论不资格原生 Codex 的跨 namespace 配置投递/权限，不资格辅助者、T2 默认视图、T3 搜索收益或 T4 科学评估效果；不批准原 N5 恢复。

## 最终冻结源码

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/cov_lineage.py` | `badd95a7d681f233590bfd1b6236fe1fb2084a33dfcc96ed617091047d1ea09f` |
| `src/scidiscovery/research_loop/lineage.py` | `c2e457cd7e065330a0084c0ef0639b6ced3d63360755211a22c611dfba65695e` |
| `src/scidiscovery/research_loop/history.py` | `401bfad8040f6effa9b8f31bc4cc0cafcb06625ef288624b832be6c8657e2282` |
| `src/scidiscovery/research_loop/search.py` | `9e8fd066b0dcd1d514f34a79fc4dc45726863fc8638c743bbfea89acb52d45eb` |
| `tests/research_loop/test_lineage.py` | `582ff44bc2eececb81740f1a98145f1d546f26fffe6fa4149aac15b7f4200006` |
| `tests/research_loop/test_cov_lineage.py` | `6a6aea0ddf1e150bafcffbb86553d52599a9caa9b0f136a7ade7accb7bc0c624` |

已独立读取最终源码 SHA，并比较最终 wheel 内17个 research_loop 模块、当前源码与独立安装模块的实际字节；17/17 一致。

## 核对结果及已关闭发现

- **单权威与边界：** lineage 从原 job、成功 scientific execution raw/seal、observer archive 和 selected receipts 重建；不创建余额、active head、资格账本或 executor。只读 build 不写缓存。派生声明、实现复用和科学支持分开；支持保持未知，关系不继承审计资格。
- **机制解释：** `search.apply_source` 抽取原 binding8、legacy7 typed attempt、状态/诊断重算校验，`search.project` 与 lineage 共用。原 W intent、accepted slice 和 repair 计数仍由 search.project 保管；当前 fold 只输出 mechanisms，不将其用作新准入或计量权威。
- **执行归属：** v2 context 精确核原 job SHA、step/role、冻结 mechanism focus 和真实 accepted attempt identity。允许同节点较早失败 native attempt 内已精确完成的实验事实；这不使失败 native 科学输出成功，最终科学 source 仍来自集中 execution 成功 attempt。
- **父方案：** accepted 原件中的 parent_binding 绑定父 call、step、completed SHA、model SHA/size。capture 与 build 共用前缀校验，先验证当前 context 再加入 available；封存父与同节点更早成功调用分栏，未来调用、错模型或仅可见候选不能授父关系。P→Q 与退回 P→R 在同 W 未 seal 期间真实 CLI 可发生，复用另列。
- **精确完成记录：** known 状态纯读核 accepted 四字段、stdout=row、row script/run/ok、candidate 身份、terminal returncode/cleanup/transport；成功模型必须为本 call 的 exact model.pkl 且在 proof 中。candidate/run/status 篡改和跨 call 模型换绑均拒。查询不重新读取可变训练源、台账来改写已完成归属，不执行实验。
- **生命周期和输出：** node lock 不重取实例 writer；子进程独立 session，复用原 subreaper/精确 group 清理。stdout+stderr 合计字节上限，时间或输出截断不能因前缀恰为有效 JSON 获成功资格。未知 accepted call 阻下一替代 run，不重放。
- **未知与已知失败：** 已完整失败 row、终态和清理证明为 known_failed，无模型资格，可有科学理由在原额度内新修复；未知保留、coverage partial。已接受未 completed 调用不会从 observer 消失；普通 shell 或缺 parent 声明不猜派生。
- **兼容：** observer v2 显式版本及 binding，未声明版本的 v1 保留原布局。新增 integrity sentinel 仅 v2 硬拒，v1 同非法 reply 仍保持可选失败/unavailable 科学封存。科学 schema8、default science view、budget、controller/executor 和 continuation 源接口未改；旧 job/task/seal 原件不重写。

## 实际证据

路径均相对仓库外层 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`。

| 检查 | 最终证据 |
| --- | --- |
| 最终 source 门禁 | `.trial/t1-final-20261012-05/batch-001/pytest.log`：**125 passed，38.26 秒**；result.json 无 skip/失败，覆盖 lineage、cov wrapper、history、handoff、search、semantic recovery 六文件 |
| 最终 installed CLI | `.trial/t1-installed-20261012/artifacts-04/result/result.json`：9 checks PASS，0 model requests；真实 controller H→W→A、持 instance lock 的调用、P/Q/R、known failure repair、unknown/no replay、v2 seal |
| 字节一致 | 同目录 module-bindings.json；本人实际读取 ZIP 与 installed files 核17/17模块、最终 wheel SHA `90d66c80c9b771a21fe5fbbe85b1a65a682475a9b4cc3fe192f8ff64f27a819c` |
| 原 public harness | `.trial/t1-installed-20261012/real-public-result/result.json` 与 manifest.json：一次公开 constant-zero predictor run，stdout=completed row=ledger、artifact exact、query readonly、公开输入不变；0 LLM/无 hidden/无 submit/无 audit |

原 public 补充门禁使用 synthetic standalone scope，受测 wheel 为 artifacts-03；到最终 artifacts-04 只有 history.py 变化，其余16模块逐字相同，已读 `public-evidence-reuse.json`。所测 installed cov 模块 SHA 为 `badd95a7…ea09f`，与最终源码/wheel完全一致；它证明真实原 harness 格式和同调用归属，不证明 native namespace 或 bwrap 权限。最终 history 分支另经125门禁及最终安装核验。首次101、第二104及中间25用例的旧快照仅过程证据，不代替最终125门禁。

## 明确能力限制

`lineage-status`只核已有 completed.json；缺此文件时，即使另有 terminal/stdout/ledger 也保守 unknown，不声称已经恢复该崩溃窗口。模型实际算法使用父实现、科学正确性和审计资格不由机械谱系证明。configure 要求实际新 launcher 保留原绝对目录及 public runs alias；任意跨 namespace 路径映射尚未资格，不能用本次假 native 安装与 synthetic public run 冒充。

wrapper 超出 T0 领域180行估量的部分承担 bounded IO、快照、同节点父解析、只读查询与 observer 端；已审未引入第二调度引擎或预算。原 stdout 不是可唯一解析完整 JSON 时保未知，不把噪声文本猜为正确回执。软隔离不声明能抵御作者重写整组 workspace 原件；已封存 archive/digest 边界保持硬校验。

**最终判定：上述精确冻结与已测范围 PASS，可提交 T1；后续实际 native/T2/T3/T4 仍需各自门禁。**
