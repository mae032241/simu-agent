# P5 首节点：新项目默认薄 CLI 部署

2026-10-17。状态：实现冻结，经 root/thin 独立静态核对，root 串行4项 source 增量通过；本 worker 未运行测试/项目导入/安装/模型/服务器或 Git。当前原实例材料恢复已另节点提交，本节点不改其恢复段或实现。

## 当前缺陷与最小迁移顺序

旧 installer 始终创建 SQL/key、生成 Root MCP/角色，并 enable control/旧 approval UI。wheel 虽有 thin entrypoints，activate_packages 只公开旧 scid wrapper，因此仅 README 写“可用薄 CLI”不足以退出新项目默认 Root 调度。旧 instance-list/旧 UI 先 open_runtime，也不能冒称停 daemon 后就已有只读旧 SQL 出口。

本节点实际完成新项目默认路径；新薄层不依赖重建旧 SQL reader。旧数据、显式 legacy 部署与现有 portable_bundle 的选定 Artifact 导出/离线 verify 保留，不把它们冒充全量 SQL/control 状态迁移。只有用户实际提出历史资料迁移需求时，才考虑复用已有原语补所需读取/导出；这是后置可选数据工程，不是本轮或薄层部署的前置。旧 active 服务不默停，旧调用仍按原合同维护，不删除旧数据，也不为宣称全部历史层退役扩新服务。

## 真实分流

- 唯一 `SCID_DEPLOY_MODE=thin|legacy`，默认 thin；旧服务需显式 legacy。install/reinstall wrapper 透传同一选择。thin 参数校验、preview、安装、status、rollback、uninstall 均先分流，不要求旧 workspace/launch-root、systemd/pdf 工具或旧 runtime。
- 沿原 install_packages staging/cohort 检查及 activate_packages，thin 用两项精确 console metadata/load 检查，不走 ROOT_TOOLS/catalog/MCP probe。默认 `/opt/scidiscovery-thin/site`、`/var/backups/scidiscovery-thin`；prefix 父目录可已存在且不改其 owner/mode，site 必须不存在。只安装应用与显式选定插件；选插件不配置/授权远端服务。
- 仅发布 scid-research / scid-experiment 的精确 Python/PYTHONPATH wrapper。旧 scid、SQL/key/settings、平台角色/skill、units、remote 激活都不写。没有默认实例/预算或自动 run/UI，用户继续现有显式 prepare/run/serve-ui。
- 任一已有 site/wrapper（含 symlink）先拒绝，不静默接管另一部署。以 CLI_ROOT 同一 flock 串行协作安装，wrapper 用无覆盖 link；site 用 mv -T -n，并确认 stage 确已移动，不覆盖并发出现的目录。这是可信宿主下的部署互斥，不是恶意同 UID 隔离或可迁移执行 owner。
- 复用原 install_transaction.py，仅绑定两个原先不存在的新 wrapper；没有 SQL/unit 事务。失败只在 wrapper 仍匹配本配置时回滚，否则保留未知 owner 并明确 rollback incomplete。不删除已发布 site；卸载也只移除两项匹配本配置的 wrapper，保留代码以免删仍被进程使用的 prefix。status 只报告 wrapper 匹配，不加载实例/clock。

## 精确文件

生产 shell：deploy/install.sh、deploy/reinstall.sh。没有新服务、角色、账本、Python生产模块或对 install_transaction.py 的改动。

测试：tests/artifact_agent/test_deploy_scripts.py 仅增加本模块 autouse fixture 显式选择 legacy，保留原服务测试意义；新增 tests/artifact_agent/test_thin_deployment.py 四个小 source 定义（未运行）：默认 thin 预检不需旧 workspace/服务；site/foreign wrapper 碰撞拒绝；实际 activation/transaction/rollback 保旧 sentinel；status/uninstall 拒外来 wrapper，匹配时仅移除命令、保代码。

测试不构建/安装包。回滚用例的 package supply/preflight/权限入口是 stand-in，真实临时文件发布和原 transaction helper 执行，不伪造业务成功；故不能把它当 package/deploy end-to-end 验收。旧 SQL/config/scid sentinel 字节必须保留，原 service 函数调用哨兵必须不触发。

文档：README.md、README.zh-CN.md、deploy/README.md、deploy/README.zh-CN.md、docs/INSTALL.md、docs/INSTALL.zh-CN.md、docs/ROOTLESS_CLI.zh-CN.md（仅顶部安装节）。README 默认改为 thin，旧教程显式标 legacy、export 与 sudo 透传。本文为实施证据；没有修改主计划/旧历史审计。

## 静态检查与限制

两 shell 的 bash -n 通过；两测试文件及 install.sh 14段 literal Python heredoc 均用 stdlib AST解析，限定文件尾空白检查通过。未 source 执行 shell/CLI，没有 pytest/收集、安装、项目 import、模型或远端运行；后续 root 指定最小验收结果见末节。

事务前 staging 失败沿既有行为可能留下私有 source tmp/.site.new.*；没有已发布 wrapper/实例/执行权，不承诺本节点完整清理，也不为此扩 installer 框架。新路径只支持新 site/空命令槽的安装，未实现自动就地升级或旧代码垃圾回收；卸载命令不证明所有原生/外部进程已停止。缺依赖、figure 工具绑定、实际 TCAD/native/浏览器及旧存量迁移保持明确未验，不恢复环境矩阵或全套已安装功能重跑。

## root 唯一串行定向结果

root 在冻结后执行新模块四个精确 source 目标，**4 passed in 0.39s**，首次全部通过，4个 unique 增量用例。原始证据：`.trial/p_completion_20261017/thin-default-deploy/batch-001/{pytest.log,resource.json}`；本 worker 只读核对，未运行测试。

监督0.573s，观察进程树 RSS 峰值58,429,440 bytes（55.723MiB），returncode=0、cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]。address_space_limit_enabled=false，采样不能外推硬内存/最坏容量保证。

本批验证默认 thin 分流/无需旧 workspace、旧 SQL/config/scid sentinel 保留、site/foreign wrapper 碰撞拒绝、实际临时文件激活与原事务回滚、status/卸载范围。package supply/权限前提/包检查为明示 stand-in，不装包、不启动服务/模型。没有运行旧 legacy 全文件、发布构建或新安装环境；不能据此声称真实部署、所有插件/native/TCAD/浏览器及历史 SQL 迁移资格已通过。生产/测试在执行前后保持冻结；后续只补本文结果与可选历史迁移边界。
