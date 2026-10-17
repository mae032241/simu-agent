# main 结果呈现适配薄UI：独立静态审查

结论：**修正缺失import后的冻结版静态 PASS**，可交root唯一串行2 source + 1 HTTP目标。作者与评审者未在此报告阶段运行测试；本评审未执行项目import、业务CLI、安装、模型、浏览器或Git。不是浏览器/真实科学资格。

## 范围与来源

三生产 `instance_ui.py`、新 `instance_render.py`、`execution_authority.py` 单项helper pin；新 `test_instance_results.py` 两函数、既有 `test_instance_ui.py` 一个HTTP函数增量，以及设计/实施账。未改旧SQL/read-model/Root/MCP或执行准入。main只读renderer和CSS SHA分别为 `5411ae6f3697beafc4cdf520b785f0dd7ace3af8737c63fe89f46b9b5a2508db`、`2683808df5fc266f45a25f3ed9eb970eed1d25aea7b8f2546eee9d3a2b4e3571`，与原评估一致。本轮借鉴展示语义，不复制其存储模型或自动图件推断。

最终代码/测试SHA256冻结：

| 文件 | SHA256 |
|---|---|
| instance_ui.py | af20a7e09fa2f58f0643ea0f9401f19adb65984be2da91730d903bb2fa363860 |
| instance_render.py | 114b26d533f01a0d8236727138a048f8a0774fa658eb8b4ebc64c9ba35fdc7c7 |
| execution_authority.py | 3e98f0783808df0464b365fd068de264ca048680aba51de69f2c05fbee850770 |
| test_instance_results.py | 7ba240e83cafc7e30ae742c8c67c00edb4529120b915e6a74523e54f8089f803 |
| test_instance_ui.py | 20e6acd841933cf904426fb12169108ab13ef9e9a8e0019236319d7f150f8814 |

## 已核跨界行为

- `/results?after=N`仅列exact编号且存在seal的节点，20条分页；没有自动选择当前最佳或解析全部科学历史。打开exact step先沿原Host/read Cookie鉴权，`science._sealed`核job/result/raw/attempt；再按seal.job_sha256重读同job，raw使用同一个Original fd。未调用活钟/status/history rebuild/selection重投影，不创建第二份科学状态。
- `job.history.view.candidates`是**节点输入时**的原冻结摘要。proxy_highest的metric/direction/candidate_ids和a_recommended的author_step/candidate_id已对selection.project原schema核对；同分保留、浮点原值不人为截小数。unknown/failed/alerts/省略数在scope公开，缺摘要不宣称不存在候选。
- 当前ordinary A原raw推荐与输入边界的早期推荐分栏；null不复用旧推荐。job.formal_review或raw next_action=audit均不当ordinary A；不从proxy、机械封存、执行成功或review文字制造accepted/target optimum。
- 所有科学文本HTML escaping；excerpt有明确省略数与完整JSON链接。只取公共白名单，不渲染完整host job/config。原HTML/SVG成果仍attachment/octet-stream，未加自动图片或active文档内嵌。
- 固定CSS与CSP hash来自同一常量，输出style内容一致；不新增unsafe-inline、script/CDN或外部静态目录。authority原implementation自动pin新增render模块，实际helper不脱离冻结代码身份。

## 修正与最小验收

冻结前 `_results_page` 调用execution.origin但顶部缺execution import，会使列表真实NameError。作者自查与评审定点确认后只补单import；root尚未开始测试，没有将该错隐藏为通过。scope初稿遗漏unknown/failed候选信息，已改为显示原摘要相应字段，未重新计算。

两个source目标分别使用真实selection纯投影检查tie/metric/清推荐/unknown/escaping/CSP，以及真实prepare/seal/readcookie检查read-only、exact job/raw篡改拒绝、分页、附件和活钟/重算哨兵。renderer-only test的手工job只证明呈现；另一真实seal测试补调用边界，不以手工job冒充生产完整协议。

HTTP目标沿原loopback server/既有cookie下载函数追加results与CSP响应检查，附件bytes/attachment/nosniff仍严格。原浏览器RSS止损未获资格，不追加Chrome重跑或安装矩阵。

结果页仍完整解析单个raw科学JSON和job再摘录，不能据短HTML承诺常量内存；没有完整候选原件浏览、自动主图、跨producer去重或当前全局ranking。本评审只覆盖本节点实际调用链和必要负控，真实浏览器渲染、平台身份与科学效果仍未验。

## root串行动态结果独立复核

已只读核两批 `batch-001/{pytest.log,resource.json}`：

| 输出目录（`.trial/` 下） | 结果 | 监督秒 | 树RSS峰值bytes |
|---|---|---:|---:|
| main_ui_source_20261017 | 2 passed / 0.64s | 0.861 | 66,510,848 |
| main_ui_http_20261017 | 1 passed / 1.02s | 1.239 | 67,137,536 |

3个不同目标均通过，监督共2.100s，退出均0、cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]，无地址空间硬限制。实际执行者只有root，评审者没有运行HTTP或测试。结论为此冻结版源码/loopback HTTP有限验收通过，可提交；不将HTTP/CSP检查称为真实浏览器或完整科研任务通过。
