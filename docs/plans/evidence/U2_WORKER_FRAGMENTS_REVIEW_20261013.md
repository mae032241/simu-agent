# U2 同科学阶段片段与 checkpoint 独立审查

状态：**PASS（U2内部opt-in片段与checkpoint，无模型）**。production03/source04八文件独立审查、最终安装门禁已绑定，两项边界问题与一项恢复退化均闭合。U1基线提交`9d81262`。独审者参与早期边界设计，但未编写U2生产/测试；只修改本报告，不运行tests/build/Git/model。

## 范围与所有权

本步只审 opt-in 内部片段合同及正常、修复、轮换、unknown机械生命周期。protocol13原科学schema不默认启用stage_intent；U3一次current合同启用另验，不把内部schema fixture当作生产protocol14或真实native模型恢复资格。

沿原job/step/workspace为唯一科学stage，continuations为同一immutable native attempt链。common注册受管执行仍用U1稳定stage owner、原call/external submission身份和原回执，checkpoint不另记候选/预算/科学周期账本。

## 已读实际生产实现

已读checkpoint、execution、continuation、runtime、native、controller、contracts封存差量及test_worker_fragments完整集成；/tmp预审之后已按实际repo fullfreeze03重审：

- 普通continuation_kind=fragment与repair分开计数；repair仍冻结最多两次，正常片段链以原shared max_steps约束。预算沿accept_continuation累计previous_tokens/previous_seconds，used_steps沿原链计入每个accepted attempt，片段不创建科研job/A周期。
- 科学stage仅最终seal；正常continue只保存checkpoint后开启同job下一attempt，query/collect沿原call无需新提交。新context明确轮换home；same session须原thread/header/cwd匹配，不由fresh隐式替代失败resume。
- runtime持本attempt runner lease，在run_native结束所有该attempt原件写入后capture。仅看到outcome/unknown不capture活路径；wait_native等待runner的checkpoint，缺失则停。unknown usage/cleanup可保存机械原件，但不授新native资格。
- checkpoint仅保本attempt小原件及current direct deliverables，材料沿现CAS归档；不递归复制祖先、scratch或大日志。science必须raw_sha绑定真实outcome，否则missing/invalid/unverified显式保留。≤4096B brief按实际JSON编码削减并标遗漏，不曝光host路径/hash。
- 内部fake runner测试包含两种上下文、原call query/collect、四正常片段不耗repair、host投入终止、missing输出修复、known failure及native usage unknown不重放。设计/fixture本身不等于测试通过。

## 实际差量复核与冻结绑定

两项预审问题已在实际fullfreeze03修复：

1. fragment_start在原runner资格/等待完成后重新发布并观察原U1复核事实；命中时不创建下一native intent，caller记录reason并seal现科学输出。必要负控在_eligible_original后模拟投入跨线，验证仍只有一个attempt且原raw continue未改。
2. 本attempt `stage-end.json`冻结控制结束reason、exact job/attempt binding、checkpoint/raw SHA；execution.proof沿同一原件owner把它放入原execution_ref.chain封存。即使只有initial attempt也保存非None execution_ref；contracts仅调整该封存条件。controller给A短reason，不重写科学raw，不另造阶段/科学周期账本。

3. 父共享回归发现controller新增retained job读取会在原科学job缺失时抛FileNotFoundError，打断旧unsealed路径。freeze03在该读取前直接保留native_outcome_unsealed返回；保原件、不重新接受native，不修改旧负控来掩盖退化。

`/tmp/scid-u2-source-04.json`八项已实际读取字节并全部MATCH；其中七项生产与一项测试。

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/checkpoint.py` | `ea1805b14645630391b9ffcf094d42143f7c66a0b00b0ba513d0f66fb5d7a442` |
| `src/scidiscovery/research_loop/execution.py` | `6a37abc846831a90c5a6044e930c494e0b6f1224202e1a89e3b2d798c3df39b2` |
| `src/scidiscovery/research_loop/continuation.py` | `3eba3de7893292a8eced44c00172bb14933099ad6ee4017b04daef8ba31b1d29` |
| `src/scidiscovery/research_loop/native.py` | `ec5d95bc6d192bc7bebd7c7ea7c25219d62e64b3cfb9baa3327d6ac68e3a369c` |
| `src/scidiscovery/research_loop/runtime.py` | `85ae34c3100af36853486eb152c35c6d71249383210d445f3a220c00126f07dd` |
| `src/scidiscovery/research_loop/controller.py` | `2f3d7e8dacb0197f59943de93cb4f7715d144db3da186e409bf475c205caa0e0` |
| `src/scidiscovery/research_loop/contracts.py` | `77fbb363e8b0aeb353281f10a958344dbe15967b93a0df48c823b071b542c098` |
| `tests/research_loop/test_worker_fragments.py` | `afa2ab18123717ee9f534a45d3e631f83d07b68c1dfa2bc94d288d99f647476f` |

## 无模型证据与限制

父source首轮16通过、4项mkdir夹具失败；四处artifacts.mkdir加exist_ok=True，断言不变。父共享回归首轮162通过/1skip、2项缺job/unsealed实际退化；production03已修controller、不放宽旧负控。

- outer `.trial/u2-source-03-20261013/batch-001/pytest.log`：修复后65PASS（含缺job两项），仅brief夹具科学raw超既有64KB原件容量失败，还未进入brief。source04只缩limitations重复500→200并显式assert raw<c.MAX_RESULT_BYTES，仍保60文件/遗漏及≤4KB多字节/nohosthash/前后原件bytes断言。
- outer `.trial/u2-brief-04-20261013/batch-001/pytest.log`：最后合法brief夹具1PASS/0.22s。source04与production03七生产字节相同，八文件final SHA全部MATCH。
- outer `.trial/macro-role-installed-20261012/artifacts-u2-03-20261013/u2-installed.log`：最终全相关安装184PASS/1SKIP，72.51s；包含新增20项与原resume/controller/registered/livefeedback等共享回归。内部fake native执行真实子进程runner、注册local实现和原call query/collect；same_session/new_context的fake线程/header/home合同分别验证，未使用真实模型。
- 同目录`u2-installed-result.json`：site-packages实际导入、model_requests=0。独审直接读取七个本步安装模块字节，SHA全部与production03/source04匹配；不是仅依赖日志中的声明。
- 同目录`result/result.json`：freshwheel build_check PASS、fake H/A/W/A、route context/no_replay保持、model_requests=0。实际wheel SHA256 `85e8cfed6e95f0a2827cd3001006ac12d430179b2ce08e79828a0b987532c533`，独审读取wheel字节hash匹配。

checkpoint只接受既有容量内稳定原件；科学raw超64KB明确拒capture并保留原原件，不能声称任意体积都能capture。完整checkpoint在host，brief≤4096B且标遗漏；checkpoint并不授科学或重启资格。

PASS范围仅U2内部opt-in生命周期。生产protocol13不默认启用stage_intent，测试使用明确schema fixture；U3一次current合同启用另验。无真实native同线程恢复、平台压缩、TCAD、上下文成本或科学效果资格。未受管shell仍沿原权限与覆盖限制。独审未编写生产/测试，未运行tests/build/Git/model。
