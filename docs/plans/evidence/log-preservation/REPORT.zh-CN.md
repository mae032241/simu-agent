# 日志原文保留修复记录

## 结论与范围

源码修复与低资源定向验证完成，尚未部署，也未重新执行真实 Sentaurus 实验。保留有界原文、展示摘要、按需分段读取、分类先于截断，作为框架日志的共同要求。覆盖 TCAD 本地与远程开发/正式执行、启动进程、命令与 SSH 传输、PDF 工具诊断；不声称修改外部平台或宿主系统的日志实现。

本轮从已有大量未提交修改继续工作，保留此前改动。tcad-runtime-increment.patch 仅记录具有修改前快照的六个 TCAD 文件增量，不是完整工作树补丁。

## 原因与修复

此前 runner 用首尾摘要覆盖 worker.log，debug adapter 再对拼接后的日志截断，并把同一摘要存为 debug.log.txt，错误分类也读取摘要。stdout 尾部错误在追加 solver.log 后变成中间内容，可能被二次截断。保留截断后的文件无法补救这个问题。

- worker.py 与 remote_runner_py36.py 保留 worker.log，另存 diagnostic.log，采集多个求解器 .log/.err；execution_control.py 与远程启动保留 launcher.log。采集失败明确进入 manifest。
- debug_adapter.py 先对完整有界诊断进行分类，再生成短摘要。Worker 获得完整脱敏副本，原始进程字节保留在 runner。采集不完整不能把退出码 0 判为调试合格。
- local_debug_service.py 发布受控 reports/log-<run>.txt，返回 log_relative_path 与摘要是否完整；沿用文件分段读取和既有缺口成果封存，使下一轮能接手。
- command_adapter.py、ssh_transport.py 与新增 transport_logs.py 保留失败输出、超时输出及成功命令的非空 stderr。使用现有传输目录、内容寻址文件及受限权限，没有新日志服务。
- local_pdf_tool.py 保存 stderr 原文文件，错误消息保持短摘要，成功警告同样保留。
- 作者与审查者角色要求先查完整日志，再判断诊断是否缺失。中英文架构文档记录共同原则。
- 作者成果上限由 512 KiB 调整为 8 MiB，以承载既有最多六次调试的日志与源码；工具回复、调试次数、运行时间和审批边界未放宽。

## 边界

日志不是无限增长：stdout 诊断采集上限 256 KiB，求解器日志合计 240 KiB，传输单条 8 MiB，PDF stderr 1 MiB。超过采集限制明确报告，不以首尾拼接冒充完整日志；runner 原文件仍受既有作业资源限制。历史上已丢弃的中间内容无法自动恢复。本次修复不证明此前物理初始化失败已经解决。

## 验证

所有测试串行，BLAS/OMP 单线程，虚拟地址空间上限 3 GiB、单批超时 120 秒；没有运行全量或压力测试。各批有重叠，不累加为独立用例数量。

- final-tests.log：21 passed，涵盖日志、缺口续接、回复预算、失败标记、PDF；峰值 RSS 102376 KiB。
- process-tests.log：16 passed，含真实短命 shell 子进程、本地/远程 runner、源码证明、路径限制与源码环境平台生成。
- installed-tests.log：初轮安装包定向检查 15 passed。
- installed-final-verification-3.log：最终核心/TCAD wheel 导入、Python 3.6 runner 语法、安装后作者/审查者配置生成验证通过；13 个日志回归用例通过，峰值 RSS 98920 KiB。

安装测试中的失败亦保留：单插件 pip --target --upgrade 替换共享 share 目录导致核心 scheduler 提示丢失，改为全新目录同时安装两个 wheel；随后源码平台测试因硬编码 src 路径而不适用安装目录。独立生成探针初次缺少 curve_score 导入路径，补路径后缺其 entry-point 元数据，最终显式编译核心、通用科学、TCAD、curve_score 四插件目录验证生成配置。没有为这些测试环境问题修改生产源码或削弱断言。

最终验证仅核心与 TCAD 来自新 wheel，其余插件与依赖复用源码/当前环境，不能等同于所有插件全新安装矩阵。部署后应通过受控的新 Run 获取真实求解器诊断，继续定位原初始化失败。
