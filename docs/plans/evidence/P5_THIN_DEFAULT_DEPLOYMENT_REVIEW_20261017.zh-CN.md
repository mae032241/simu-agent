# P5 默认薄 CLI 部署：独立实施审查

结论：**静态 PASS，root 4个 source 目标通过**。只认可新项目默认安装入口迁移；没有实际构建、pip安装或已安装部署资格，也不表示旧CLI/MCP/SQL全部退役。

范围：两deploy shell；原deploy测试仅新增显式legacy fixture；新test_thin_deployment.py；根README/部署README/INSTALL英中、ROOTLESS顶部安装段；对应实施账共12作者文件。仅静态追链和核root日志，未修改实现、未运行测试/项目import/安装/模型/业务CLI或Git。

## 已核实际路径

- `deploy/install.sh:5-29`、`:157-200`、`:1694`：默认thin且明确legacy；独立prefix/backup默认路径。thin source/路径预检不要求旧workspace、服务用户配置或Root平台入口。既有site/任一wrapper含symlink即拒，不默默接管。
- `:649-748`、`:750-773`：复用原离线application staging/cohort/runtime identity；thin只核两项真实console metadata/load，不跑旧ROOT_TOOLS/MCP/平台probe。基础依赖仍由操作者提供，插件安装不配置后端或授执行权。
- `:774-805`、`:1363`、`:1566`：同CLI根flock协调安装，wrapper以link无覆盖发布；新site使用no-clobber移动并确认stage确已移动。沿原transaction仅绑定两个原先不存在的wrapper，不纳旧SQL/key/服务/平台配置。prefix或backup父目录已存在不额外chown/chmod。未新建状态机或安装环境池。
- `:1455`、`:1634-1674`：失败只在命令仍属于当前配置时回滚；遇外来wrapper保守保留整个未完成事务并报incomplete。status只比wrapper内容；uninstall先完整核两项归属再删除，保留prefix供原进程继续使用。不以卸载证明进程已停止。
- `deploy/reinstall.sh`：mode与prefix/backup默认一致，thin不走旧workspace检查；显式legacy仍走旧分支。根README、部署README、INSTALL英中和ROOTLESS入口表述相符，旧教程明确选legacy，不把旧UI/scid变成只读出口。

独审早读要求的两点已收口：thin默认独立`/var/backups/scidiscovery-thin`且不改已有父目录mode；INSTALL英中不再无条件保证失败已完成回滚，明确foreign owner下incomplete。未要求重写transaction或扩大安装矩阵。

## 实际有限验收

已只读核 `.trial/p_completion_20261017/thin-default-deploy/batch-001/{pytest.log,resource.json}`：4 passed，pytest 0.39秒；监督0.573秒，峰值58,429,440 B，cleanup_complete=true、memory_stop_triggers/received_signals为空、address_space_limit_enabled=false。

四项通过实际shell路由/文件操作/原transaction检查默认preview无需旧workspace，已有prefix/外来wrapper拒绝，发布后probe失败的真实回滚，status/uninstall所有权与旧sentinel保留。package supply/preflight/权限有明确stand-in，故不是完成pip安装或systemd端到端验收。未知wrapper和竞争失败不会因测试stub被默认当成功；原旧服务测试仍有消费者，显式legacy fixture保留它们的意义，未删除其独特断言。

## 状态核对与未完范围

主计划当前P4 `b670c2b` 为原实例普通缺件恢复、Local `8bdc517` 为声明输入子范围，与实际边界一致；P5本节点提交前仍标在途，提交后可仅更新这一进度。旧handoff报告明确其历史截面，不回写为当前全部完成。P1–P5尚未整体投产验收。

仍未实现旧SQL纯只读迁移出口、自动就地升级/旧代码回收或完整灾备；不停止旧active服务、不删除旧数据。历史数据读取/迁移只在用户有实际需求时复用原语另议，不是薄层运行/部署前置；无需为默认路径切换重建旧服务。事务前staging失败可能留私有临时文件，已发布prefix在回滚/卸载后保留，文档均披露。安装包内仍含兼容旧模块/入口，不等于默认创建Root。真实安装、domain工具绑定、TCAD、native平台、浏览器及强隔离未由这4项证明。无需重复功能suite或安装矩阵。
