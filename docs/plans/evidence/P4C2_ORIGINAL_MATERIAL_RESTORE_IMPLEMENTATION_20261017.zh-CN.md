# P4c2 原实例缺失成果文件恢复：实施账

状态：实施已获独立静态审查；root修复后原3项全部通过。范围见[设计](P4C2_ORIGINAL_MATERIAL_RESTORE_DESIGN_20261017.zh-CN.md)。本节点只补原实例内普通科学成果缺件恢复，不实现完整灾备、可推进副本或跨宿主恢复。

## 精确文件与路径

- `research_loop/instance_archive.py` 新 `archive_restore_material`：原锁/静止判定→当前科学 seal/raw/job/result/执行引用→封存成员/普通 source owner→完整原包检查→当前 producer seal 与 exact 原逻辑路径/hash/size→目标同字节幂等或 host-runtime 独有 staging→硬链接无覆盖发布/fsync/清理。
- `research_loop/cli.py` 新 `archive-restore-material --root --package --step --index`；root 保留原 canonical/symlink 拒绝，成功状态明确加入返回码0，不落入 run 分支。
- `docs/ROOTLESS_CLI.zh-CN.md` 仅原恢复/归档段追加能力与边界；另一作者持有顶部安装段，不覆盖其改动。
- `tests/research_loop/test_instance_archive.py` 保留原4项，新增3个小 source 用例，沿既有小 prepare/finish helper，不创建安装环境，不起模型/HTTP/后端。
- 设计与本文；无 Local 来源、deploy、预算或权限生产文件变动。

普通 source 必须精确位于当前节点 artifacts，或既有 nested experiments 语法中的 artifacts/conclusion 成员。不能把 managed call/host-history/control 路径当作该成果源。所有原 managed terminal/fence/native 清理校验照常；缺任何所需执行证据时保持拒绝，未提供 overlay 或新资格 schema。

包仍是 `restorable=False` 的只读 v1 布局；仅作为 exact 字节来源。完整 inspect 前记录metadata文件身份，inspect后读取再核同一hash/size/stat，不能在间隙换另一版metadata与manifest。重新读取 manifest 时，sha/size须对应该metadata声明，扫描后再核其完整身份；选中blob复制再次验证。包中的 producer seal 字节须与当前 live seal一致；不以同hash另一原路径选源，不从包重写当前seal。单条目标已存在而不同、symlink/目录或发布竞争出现不同原件都拒绝，无先exists后replace覆盖。

temporary 位于 `root/host-runtime/material-restore-…/`，不会作为 artifacts 收集；finally 清理。跨文件系统硬链接失败即失败，无覆盖fallback。崩溃后可能留下该host temporary或已发布的正确文件；重复命令仍完整核验，仅同bytes幂等，不增加恢复状态机。一般单次IO/掉电并无硬实时或事务跨文件保证。

## 控制原件与预算边界

操作者必须保留当前控制原件；恢复不负责证明目录中不存在早已丢失的更晚事件。锁和原_quiescent核当前事实，未新增全预算/当前时钟snapshot，也不授执行资格。ledger/settings/seals/decisions/accepted/recovery均不从包写入；没有grant、退款、改clock、重签决定、删除pause或自动continue。后续推进仍由原入口按原clock/来源/权限/unknown不重放规则裁定。跨boot仅补字节不代表原推进规则可跨boot续用。

## 最小负控与未运行范围

1. 公共CLI恢复普通及nested封存文件，原科学reader读回同bytes，重复幂等；真实budget.amend在旧包之后追加的当前事件以及所有当前控制文件保持原字节；snapshot/自动推进哨兵不得触发。
2. 已有不同文件/链接、当前producer seal与包不同、伪装为control目标、错误index拒绝，原件不动。
3. 活controller/unknown native cleanup拒绝；实际link前创建不同竞争原件不覆盖，staging清理。

沿原archive-inspect已有路径/重复/坏blob/链接负控，不复制整个矩阵。合成native cleanup只让实际control消费路径可达，不声称真实平台、科学资格或恶意Worker隔离。root可仅串行选择这3项；未要求全文件、安装矩阵、真实模型/solver或服务器。

作者只执行stdlib AST/空白静态检查；没有pytest/collect、项目import、安装/构建、业务CLI、模型/HTTP/SSH或Git写入。独立审查与root定向验收待追加，不以本文替代通过证据。

## 首批实际失败与fixture路径修复

root 唯一串行首批 `.trial/p_completion_20261017/material-restore/batch-001/pytest.log` 记录3 failed、0.95秒。三个用例都在从科学资料页选择成员时 StopIteration；尚未到恢复行为。新sealed_scene误沿用旧archive-only字节fixture的 `project/nodes/001/work/artifacts`，但真实 `contracts.workspace(root,1)` 是 `project/nodes/001`，这些字节未进入科学seal。

只修新sealed_scene：普通与nested成果均按 `c.workspace(root,1)` 建立；原archive-only scene及旧4项不动，生产owner判断不放宽。设计中误写的work/artifacts同步改正。作者静态AST/空白检查通过；尚未复测，不把此前静态PASS写为动态通过。

## Root 最终定向验收

root唯一串行复测原3项，`.trial/p_completion_20261017/material-restore-recheck/batch-001/pytest.log` 为3 passed、1.07秒；resource.json监督耗时1.361秒，进程树峰值60,669,952 B，cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]、address_space_limit_enabled=false。

两批共3个独立目标、6次执行；首批3个fixture失败记录保留，监督总耗时2.595秒、两批最大RSS66,211,840 B。采样止损并非硬内存限额。最终3项证明公共CLI精确字节恢复/幂等、保留新于包的实际预算事件及当前控制字节、既有不同文件/链接/错误seal或control目标/活动与unknown owner/发布竞争拒绝。未重跑旧4项或全库，没有安装、真实模型/平台/solver、跨boot、掉电或完整灾备资格宣称。作者仅核对root原日志和JSON，未自行执行测试。
