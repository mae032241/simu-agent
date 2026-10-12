# Soft node budget 独立审查（2026-10-12）

结论：**最终 PASS，源码与受测安装范围没有剩余阻断**。本人未改生产、未运行测试/模型/build/git mutation。审查基线 `df0091219d57bdb561484ba84eb79c0ac1da0421` 上被冻结的 budget/native/controller/search/CLI接缝与相关tests；亲自读取父级结果与安装字节。

## 源码审查

- 新prepare/CLI默认node_budget_mode=soft并冻结到settings身份；显式hard仍可选。旧实例missing mode按hard，不写回字段、不迁移原settings/job/view/seal。未升科学协议8。
- 三条局部硬停全部收口：budget.stop_node、search.stop_reason、budget.exploration_stop软模式不以节点/W slice/reserve阈值杀已接受工作。前两者仍先验证task/boot/anchor/非倒退计量；没有把soft作为完整性豁免。
- 真正native Popen与loop全局seconds/observed tokens/unknown检查保留；全局用量仍可能滞后，未伪称精确在途billing cap。已接受科学工作可以越soft目标返回、seal真实原结论；全局hard stop仍保失败原件，不seal成功。
- reserve仅继续作为新node/实际Popen准入与节点间收口保护，软模式越目标可能消耗原预留，未承诺保证完成delivery。没有新增余额、状态权威、模型权限或预算扩额。
- known nonzero failed、cleanup确认、有效usage、精确same-session/home/workspace、无后继/paused/closeout等原continuation条件不变。soft仅允许超过局部目标的原节点续接；_attempt_consumption/_node_duration仍核原attempt累计token/seconds/report/dispatch，global/reserve/slots计数不退款。unknown仍拒，未对真实T5失败旧实例作恢复。
- negative soft-target gap归零，不能把overrun变负成本从global余额扣除。resume prompt明确zero不续额；initial prompt、search instructions、CLI帮助一致说明soft targets/shared hard。旧missing/hard分支仍原文字。
- 轻量work/budget-status.json≤4096B，每5s/新已观测usage更新；model需在bounded行动间主动读文件，未声称stdin动态通知/保证看到。token未知用None/inflight_unknown，缓存不重加。hint没有被读回准入/账本/科学proof，不授权限，不退款。
- hint安全：固定work目录，symlink/非regular目标跳过；目录resolve/no-follow+目录FD/inode比对、exclusive临时文件、atomic替换与清理。不能通过hint symlink写外部；OSError只使建议不可用，独立硬guard不降级。模型伪改hint没有修改控制条件。
- 相关旧hard回归明确选择hard，不盲将所有测试pin旧科学协议；新专属tests用真实detachedfake transport覆盖四角色超time/token后seal、旧W slice不杀但identity拒、reserve不杀当前/挡下一步、globalhard与伪造hint、same-thread失败累计续接、unknown拒、symlink外部不变、missing-mode oldsettings不改。

## 独立读取的验证证据

- 六文件首轮 `.trial/soft-node-source-20261012/batch-001/pytest.log`：132 passed、8 failed，53.35s。8项全部在新fixture budget.transition缺host-started的原检查处失败，尚未进入待测native执行；没有软化生产检查。保留首轮失败，不声明首轮全绿。
- 父仅补start_clock建立原host-started和advance，未改生产；专属文件 `.trial/soft-node-source-fix1-20261012/batch-001/pytest.log`：12 passed，6.89s，result状态passed/returncode0/cleanup_complete=true。**distinct140用例通过=128既有+12新**；不是将重复的4个新用例另计成144。fixture最终SHA更新见末。
- fresh wheel/venv实际CLI五lane `.trial/soft-node-installed-20261012/artifacts/result/result.json`：默认soft越局部time/token后sealed wait，explicit hard time/token停，全局time/token仍停且不seal；0 model_requests。本人读取原产物、按字节亲核**19模块 source/wheel/installed一致**。
- wheel SHA `dbf66983f21845e288036973abe149b81202c0c4ab50368554ecd29b4a43c968`；installed result SHA `083f2e17ccd8a61d52808955b699bbac5ca3ba5f2d5ddf27b30081c0938f41b1`。
- 亲阅installed默认soft实际H outcome：active_seconds0.7579990789963631超过目标0.1；observed43=40input+3output超过目标10，cached30不重加；stop_reason=null，真实result-identity存在，原shared1000tokens/60s未扩。
- 相关knownfailure续接的新实进程fixture用原session/home/workspace，累计30tokens/dispatch2/steps2、原initial全部文件字节保留；unknown不可建新attempt。missing-mode旧settings夹具在派发前构造有效原旧设置身份，执行后其settings/identity字节未改，hard仍停。
- 初审发现的hint symlink fixture与replace行为已对齐为跳过symlink，不写外部、不让hint成为权限；新版prompt/search/CLI软目标措辞已核。`git diff --check`无错误；没有测试/模型由本人执行。

## 未验证能力

- 只验证安装CLI/control与fake native过程；不证明实际Codex会及时读hint或合作收尾，不声称stdin动态通知，也不证明科学目标质量/实际same-threadlauncher资格。
- 节点局部目标已soft；shared观察token仍可能延后或overshoot，不是精确在途billing cap。unknown依旧是unknown，不解释成零消费或退款。
- 旧T5条件/失败原件没有修改，没有重新运行cov或追加预算；主计划与实施证据由父同步，本独审不替科学作者判断。

## 当前冻结SHA256

- `src/scidiscovery/research_loop/budget.py`: `dfb4d76cff35bf48d5cbba3dd6ebb1cd5c4b6d57275f374ea7c76f6db81cee6b`
- `src/scidiscovery/research_loop/native.py`: `6b240f8ac057003ba9f6f17ee0b988122f1be9b225924a80df7c418880efaf04`
- `src/scidiscovery/research_loop/controller.py`: `881d90c88efb9168ec564d615ed6106f491b6745387df6ece1bc3f1db7b7f489`
- `src/scidiscovery/research_loop/search.py`: `7d0ceb69815ee483090faa1c92a566e770d6f82983f7243e5654695727599330`
- `src/scidiscovery/research_loop/cli.py`: `56398625b8d786bf99098f15c6053363f8b094602b8fad72290781c537e618e4`
- `tests/research_loop/test_soft_node_budget.py`: `8cc951d5d1993522c3532f8c640b1ac12b6148a5fe1f1edc9ab933716ebe8456`
- `tests/research_loop/test_node_budget.py`: `24fa3b06a0402afdd2f1dd230f7a8f69610ed65af10ba76374f6162e53d4ef73`
- `tests/research_loop/test_search.py`: `d893b3530db661a95ff878cd808c12e31fc81931ccd05233a93bec31239b3326`
- `tests/research_loop/test_worker_resume.py`: `a252fe95e8498fe17557d8b8acbcf2909e1005bf48625e526241fe960e20a88c`
