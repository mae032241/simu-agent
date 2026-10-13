# 全局组合复议独立审查

状态：最终独立审查 PASS，无剩余阻断；不授予科学覆盖或付费原生模型资格。

## 范围与事实

- 只读核对第二冻结 `/tmp/scid-portfolio-freeze-20261013/source-test-02.json` 的八个生产文件及专属测试，九项实物 SHA 均匹配；manifest SHA 为 `91fb3e1b78817eb0882db12c506110ab0acdf76c1e611d0f284280a921c8ff0d`。审查者未修改实现、执行测试、构建安装包、调用模型或读取隐藏评分。
- 显式 `portfolio_policy` 启用新协议 11 并启用既有 decision 合同；协议 1..10 的科学 schema、旧 retained job 取值分支保持。新增字段仅为 A 的可空科学短文 `portfolio_review`。
- 窗口采用同一机制 ref 的累计真实 W+A 投入，不是连续 streak，也不涉及 proxy 分数。仅继续最近实际投入的 ref，且另有已承诺 pending/deferred 机制达到延期阈值时要求复议；复议允许继续原方向。

## 已关闭的首版发现

首版 `search.fold` 引用未定义的 `seal_sha`，AST 未发现实际启动阻断；第二版已将循环第四项绑定为实际已验证的 seal SHA，不另造身份。

首版准备 API 允许 portfolio 与关闭统一 lineage layout 的组合，导致 A 缺少到期概览；第二版在实例创建前拒绝该组合，专属负例检查没有生成实例。不扩展旧 renderer。

## 已核对的设计边界

- 既有 audit/E 返回 A 的路由保留 current W 直接绑定；查询、等待、续接和重启不会新增 W 身份。
- 首稿的两个计数风险已有结构修正：合格作者 A 按冻结 root A 的原 W 绑定消费一次；计入 `seen_w` 后清除 pending。原 portfolio 缺项 A 已消费的 W 不由作者补正重计。
- 有效复议关闭当前窗口，不删除原科学输出、机制身份或历史来源。H `existing_ref` 改名及遗漏不会删除已承诺机制；未知 ref 不按文字推断同义。
- 默认 overview 最多四条，优先延期及 pending/deferred 项，显示 omitted 数与完整机制分页入口；整体复用 4096-byte brief 上限。
- 原 A 科学输出保留，缺少复议通过既有最多两次作者 A 补正；N4 排除 unresolved portfolio A，审计/E 的延期动作不被复议强制改写。没有新增状态账本或执行引擎。

## 最终验收

父代理已报告八文件旧协议回归 145 项通过。专属首轮 13 项通过、1 个 fixture 失败：extract 用例设置 `decision_request=None`，正确进入既有 A 缺项补正，尚未走通 E 返回路径。作者仅把 extract 的请求改为合法 REQUEST，audit 仍为 None；最终测试 SHA 为 `41ac02e5eeaef49e2a7e0a6af33a52eba1926d50ed38a83b654456fd225020e5`，实物已核。该 selector 复验 1 项通过（0.95s），生产源码未变。不宣称一次完整源回归全绿。

已逐条读取专属测试：实际 controller 作者 A 复议后允许同 ref W、下一窗口再次触发；实际 audit/E 路由返回 A 仅消费原 W 一次；原 decision 缺项的合格作者消费及 H analyze 不重计；H 改名/遗漏、P/Q/P 累计、科学 waived、二十机制分页/篡改、旧协议 10 实物保留及不支持 layout 的拒绝。测试 mock 仅执行运输，封存、投影和路由使用生产入口，不能据此称付费原生运行资格。

已亲读外层 `.trial/macro-role-installed-20261012/artifacts-portfolio-20261013/` 的 `portfolio-installed.log`、`portfolio-installed-result.json`、`result/result.json` 及 `result/module-bindings.json`：

- 安装包内完整 portfolio 14、decision 10、guidance 5 用例共 29 项通过，11.14s；导入来源为 installed site-packages。
- 实际 CLI `--portfolio-review-after-cycles 3` 的 `cli-instance/settings.json` 冻结阈值 3，`jobs/001.json` 为协议 11；默认 H→A→W→A 封存及重启无重放也通过。
- 22 个模块 source/wheel/site-packages 字节绑定；当前源码 SHA 与 module-bindings 全匹配，八个被审生产文件与第二冻结版一致。最终 wheel SHA 为 `6c0d23060f25bdfb54bce68835746ef1cf34023fec6a6c74da4113963d8c6cb4`。
- 以上运输均为 fake native，`model_requests=0`。没有运行新科研模型或证明科学效果。

控制层仅确保作者作出可见的全局组合复议声明，不判断理由科学充分性，不强制逐机制实验，也不保证科学覆盖或目标改善。
