# 安装重启后核对：2026-09-15

状态：**部署文件与服务检查通过，实例页面验收等待用户绑定**。

- 原审批服务为 active/running，实际 systemd 单元已启动新版 CLI，含 local workspace 和 plugin config 参数。
- 实际单元保留 ProtectSystem=strict、ProtectHome=read-only；写目录仅 state、local workspaces 和固定 archive/instances。
- 已安装的39个本轮生产文件全部匹配独立审查的 SOURCE_MANIFEST；两个实例展示提供者均已安装。
- 正在运行的 HTTP 服务返回新版 CSS 和 workbench.js，均为200且内容摘要与安装文件一致。
- `instance_current` 返回 unbound；精确管理入口已交给用户。未读取实例科学 payload，未创建科学 Run、审批决定、执行或归档。

[结构化核对结果](POSTINSTALL_20260915.json)、[最终检查日志](postinstall-service-final-20260915.log)、
[资源记录](postinstall-service-final-20260915.json)：0.206秒、进程树峰值26.16MiB。

首轮检查脚本对两个字典直接排序，触发 TypeError；已改为按 group/name 排序并复验通过。
[原失败日志](postinstall-service-20260915.log)保留。这是安装核对脚本错误，不是产品服务故障，未因此修改产品源码。

下一步是在用户绑定原 Fig4 实例后，只读检查总体目标、任务、参数出处、两类历史审批、图件和轨迹。
实际 systemd 启动已核对，但没有在真实服务内执行资料迁移；此前等效权限沙箱和隔离恢复证据不扩大为真实 Fig4 归档通过。
