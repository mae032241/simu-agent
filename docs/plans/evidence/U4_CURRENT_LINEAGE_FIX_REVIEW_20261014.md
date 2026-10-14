# Current14 lineage 状态统一修复独立审查

状态：**PASS，限定为 current14 lineage 状态/scope 统一修复与无模型组合路径资格**。最终权威为 `/tmp/scid-u4-lineage-full-03.json` 四文件，生产 lineage.py SHA256 `80629cc73b6effb6f7b815779b13a91aa1c38f204eaa8b6081e1225059029f24`；独审实际四文件及安装 lineage 全部 MATCH，核对父代理 source03 37 PASS、installed02 49 PASS 无 skip。独审只读生产/测试及证据，不运行 tests/build/Git/模型，不修改生产/测试。旧真实场 [失败记录](U4_COV_FAILURE_REVIEW_20261013.md) 保留，不在线迁移或恢复该实例。以下初轮记录均为历史阶段，非最终生产 authority。

## 冻结生产与最小合同

初轮 production authority：`/tmp/scid-u4-lineage-production-01.json`，仅 `src/scidiscovery/research_loop/lineage.py`，SHA256 `e55f7ca64410f6736fdb1032a77814f624a21709aafb9fe03fcf7905e0ec6df6`。

- `lineage.build` 无传入 search_state 时仅调用现 `search.fold(root, sources)`；已有 projection state 原样复用。删除退役 exploration_order_version 分支、旧手写 fallback state 和逐 source 第二次 apply_source。
- 原 `search.fold` 是完整 current state 的唯一初始化位置，包括 order、可选 portfolio、accepted slices/repair 依据。原 search_policy 决定是否解释科学意图；本修复不强开 policy，也不制造新 ledger。
- 科学意图仍由原 `apply_source` 对 sealed control_outcome、resolved focus/allocation 和 diagnostics 复核后更新。lineage 只投影已验证 state 的 mechanisms，并继续校验 observation/context 原绑定，不写科学结论或授权原件。
- 正常 `lineage.project` 在 search 启用时预先 fold 并把同一 state 交给 build，build 不重新解释；直接 cov.configure→build 现在也使用完整 current state。search 关闭时 fold 不授科学意图，完整初始化可供原图构建使用。
- 未添加旧 flag 兼容或在线迁移；旧协议 current 写门控与只读 archive 边界沿原合同。

## 最终资格所需证据

须覆盖新建 current14、search 启用的真实合法 H seal（含新增 commitment）→实际安装 rootless launcher/configure W→注册实验→最终 W seal→A 评估链；无模型 namespace 用例必须经过 main/prepare_home/outer/bwrap。直接 build/configure 组合可补源码覆盖，但不能代替实际安装入口。

需同时保留未配置 search 的既有接缝回归、原 call 仅接受一次和新 context 查询原 call、原 stage/job/scope 绑定、H/W/A raw/seal 与 control receipt 的一致性。运行结果尚未绑定，本记录不授真实模型、same_session、科学效果或旧实例恢复资格。

## Full01 测试接线静态审查

`/tmp/scid-u4-lineage-full-01.json` 三文件实际 SHA 全部 MATCH，production 不变：新增 `test_lineage_current_search.py` SHA256 `17b50bb2ece3e834544634e9ad2fea2b6b10ab1a32f04222751f1e586708a121`；namespace 测试 SHA256 `270f30c2cd8d85857b400e2bf156e8d1ed5d09666bbc335eb6e93f9cf74c43f9`。

- 源码组合用真实 seal helper 封存 current H（search.DEFAULT_POLICY + 新 commitment），W configure 调用 registered CLI run 后封存，再以确切 H/W originals 封存 A。断言 direct build 与 search.project mechanisms 一致、A 最终 screened/seen_w 一次/unfinished 空、candidate 原 call 和机制绑定；重复 build 前后文件字节相同。
- namespace 保留 no-search 用例，增加 search-enabled 参数。H、W、A 均使用 native.execute_native→实际 launcher.main→bwrap；W 两 fresh contexts 分别运行一次注册实验和查询同一原 call。验证首 H seal、新机制 focus、原 stage scope、不同 attempt、最终 W/A seal、科学机会计数一次及累计用量。源码未安装或无 bwrap 会 skip，最终安装资格要求实际运行这些用例，不以 skip 代替。
- 父代理以新安装 wheel 对原失败现场调用只读 lineage.build(root,2)，[结果原件](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-lineage-01-20261014/u4-original-replay.json) 为 passed=true、H nodes=1、mechanisms=4、58 files 不变、models_called=0。独审读取 driver：只比较 jobs/project/native-evidence/host-runtime 下普通非符号链接文件 SHA 前后，再比较 current fold 结果，不调用 native/controller 恢复或迁移。本项证明原根因路径消除，非整场恢复资格。

## Full03 生产及测试差量复审

首轮 source01 运行发现另一处实际边界遗漏：`lineage.contexts` 的旧五字段 scope 白名单缺少 current handoff_protocol；另八项测试仍要求旧协议在线重建。生产02 把 contexts 校验归入现 `protocol.stage_scope(root,job)` 唯一 owner，使用 exact equality，删除重复字段表与任意 native attempt execution key 许可。稳定 stage scope 的 execution_key 固定初始 attempt0；各 native_attempt 由对应 experiment-config 原件单独绑定。此处沿既定合同，没有因多片段扩大科学 stage 身份。

最终 scope 负控覆盖缺 protocol 和不同 owner，均在资产归档前 typed ObserverIntegrityError，拒绝前后原件字节不变。旧协议1–8测试只验证 UnsupportedProtocol 和目录树字节/mode不变，不授旧 writer 兼容；source02 的八失败为夹具改 settings 后未更新其 identity，full03 仅重签合法夹具 identity 后进入目标协议断言，未放宽生产完整性校验。

最终 source03 三测试 SHA256：

| 文件 | SHA256 |
| --- | --- |
| test_lineage_current_search.py | `b579c9c37660addeceb10b97e6470dce288d2a9fb5f63961c664e7d6918e3cde` |
| test_rootless_fragment_namespace.py | `270f30c2cd8d85857b400e2bf156e8d1ed5d09666bbc335eb6e93f9cf74c43f9` |
| test_lineage_view.py | `60a25782aecce785455a8558c891d1f3bbc4e6a6ab55c2c2ad7044e168d440b6` |

namespace 的 search-enabled 分支显式启用 contract2 history_observer；W 使用 native.execute_native 并 c.validate 最终 seal，封存必经真实 observer→lineage.contexts，覆盖此前遗漏的 scope 边界，非只写 raw 后绕过 qualification。最终复审无剩余本修复生产阻断。

## 最终运行证据与限制

- [source03 日志](../../../../../.trial/u4-lineage-source-03-20261014/batch-001/pytest.log)：37 PASS，12.61s。独审读取实际日志，并再次核对最终四文件冻结 SHA；旧协议拒绝与 scope 负控均纳入此最终 freeze。
- [installed02 日志](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-lineage-02-20261014/u4-lineage.log)：49 PASS，19.73s，无 skip。包含实际 installed launcher.main/bwrap 的 search-enabled H→W 两 new_context→A observer/seal 链和原 no-search 路径。
- [installed02 结果](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-lineage-02-20261014/u4-lineage-result.json)：returncode=0、model_requests=0。独审实际读取其22个安装模块并核对 SHA 全部一致；该旧 module list 未列 lineage，因此独立读取 site-packages/scidiscovery/research_loop/lineage.py 确认 SHA=`80629cc73b6effb6f7b815779b13a91aa1c38f204eaa8b6081e1225059029f24`，与最终 production 相同。
- [freshwheel 基础结果](../../../../../.trial/macro-role-installed-20261012/artifacts-u4-lineage-02-20261014/result/result.json)：passed=true、model_requests=0、实际安装 CLI H→A→W→A、route context preserved、no replay。实际 wheel 文件 SHA256=`e13aecb0dd49d733cad35688536b87d4cdd04e5c47f8dff17954f7b9da358984`，独审已读取文件核对。
- 首轮23 PASS/12 FAIL 与第二轮27 PASS/8 FAIL作为历史定位证据保留：先发现实际旧 scope 白名单，再修旧协议夹具 identity；不能用失败轮替代最终门禁，也未为通过门禁恢复旧兼容。

本次修复资格证明原 current14 H 搜索计划经真实 launcher 配置、注册实验与后续 W/A 原件封存的串联边界可用。没有新增平行账本、状态 owner 或旧 marker 兼容。其余既有能力仍受原合同约束；本 PASS 不证明真实模型遵循、科学有效性、same_session 支持或失败旧实例在线迁移。原真实场仍为 FAIL；只读投影回放不消费模型预算，也不改变其终态。
