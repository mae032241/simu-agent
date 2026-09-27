# 工作台与科研客户端：修复与验收记录

状态：源码修复完成；隔离测试与浏览器验证通过。尚未安装到实际 8765 服务。

## 问题与职责

原实例浏览授权依赖科研对话的短期管理凭据。凭据缺失时，首页仍显示不可用入口，实例页退回旧元数据页，设置页返回 403；“创建与绑定”仅跳转锚点，未展开创建表单。

本轮按用户补充明确服务端与客户端关系：工作台负责实例管理、选择客户端及控制后续调度；客户端连接时登记绑定申请；实际绑定仍由用户在浏览器确认。浏览器未选中客户端不表示服务端没有已绑定会话。

## 实现范围

- 保留 loopback Host、同源 Origin、CSRF 与具体实例的浏览/维护 grant。用户通过本地表单取得实例访问，不再要求科研对话 capability；普通 GET 不自动签发实例 grant。执行审批的 token、nonce 和精确任务绑定保持原机制。
- 未选中客户端时可以创建未绑定实例；原创建并绑定、切换与接管的确认和事务内冲突检查保留。
- 首页新增科研会话管理，分页显示客户端申请及绑定。可以选择客户端处理申请，暂停或恢复后续调度。不把登记时间或“允许调度”当作在线遥测。
- `build_root_router` 在连接建立时登记客户端，`instance_current` 仍为只读查询。相同客户端重建路由不会清除暂停状态。暂停后 preflight、invoke 和新的 execution_start 均拒绝继续调度；历史状态、日志与原执行收集不被这项暂停限制阻断。
- 客户端登记与暂停状态保存在服务器共享的 `database/scheduler-bindings-clients.sqlite3`。该记录属于客户端，不属于某一实例归档；未改变已有科研数据库 schema、不可变结果或历史归档格式。历史未登记 transport 保留原绑定语义；更新后的控制入口会在建立连接时登记。
- 归档预览和真正建立归档隔离门之前都检查关联的已登记客户端，允许调度时要求先暂停。暂停后仍执行原有 Run、外部执行、收集锁和写入者静止检查。没有新增实例删除入口。
- HTML 访问缺少实例 grant 时提供明确的本地重新进入表单。首页锚点展开目标区域；无 JavaScript 时原生 summary/form 仍可使用。

没有改变 Operation 定义、Agent 科学输出要求、评分器、VM runner 或 Run 生命周期。暂停表示禁止后续调度，不是停止已运行的子 Agent 或杀掉仿真进程。

## 验证

均在隔离目录中运行，无真实审批、实例绑定、归档或仿真副作用。测试串行执行，未跑全量套件。

- `test_home_navigation.py`、`test_agent_settings_ui.py`、`test_instance_browser_http.py` 及两项归档回归：21 passed，14.99 秒。覆盖无对话访问、独立创建、跨实例拒绝、绑定确认、客户端登记/暂停/恢复、暂停后仍可读状态、拒绝新任务。
- `test_m6a_direct_instance_management.py`、`test_instance_browser_access.py`、`test_instance_management_http.py`、`test_instance_archive.py`、`test_instance_maintenance.py`、`test_r4_approval_ui_renderer.py`：111 passed，105.31 秒；`/usr/bin/time` 报告最大 RSS 150668 KiB。
- 新增实际 queued/running Run 回归，确认暂停客户端后仍不能归档：1 passed，1.10 秒。
- 对最终中文入口说明和归档原因反馈的变更补跑首页与两项归档定向检查：15 passed，9.77 秒。
- `browser_probe.py` 使用实际 Chromium、原生表单和临时 SQLite/CAS：无对话创建 → 设置 → 当前实例 → 另一客户端申请绑定 → 暂停 → 清空凭据后重新进入。零 JS 异常，零科学 Run。
- 构建 wheel 并安装到 `/tmp`，确认实际加载安装目录代码后执行同一浏览器流程；新 `home.js` 已打包，内容与源码一致。最终安装包浏览器验证通过，12.96 秒，最大 RSS 511712 KiB；wheel SHA-256 为 `565206ce98defa718d2095beee1c7411d6c8d21e52d53512637a8921be77f556`。
- `git diff --check` 通过。语义检查使用本轮开始前的文件副本，排除此前的大量工作树变更；未提交或回退无关修改。

## 测试中定位到的问题

初始将客户端登记加入科研数据库时，历史归档的已知表检查正确拒绝新增表。改为服务器客户端独立数据库后，旧归档往返测试通过，避免为了 UI 会话功能修改科学归档合同。

安装包首次浏览器检查在锚点 hashchange 事件完成前立即读取可见性，导致断言失败。已确认 wheel、安装文件和源码内容完全一致；将测试改为等待实际元素可见后，安装包流程通过。未通过延长业务超时或修改权限来掩盖失败。

## 部署与实际验收

需要更新 Python 安装包并重启 `scidiscovery-control.service` 和 `scidiscovery-approval-ui.service`，不需要同步 VM runner。更新后客户端下次接入新控制路由会登记申请。

实际验收从普通 `http://127.0.0.1:8765/` 开始，不携带对话 capability：先查看实例与设置，再进入科研会话管理。真实暂停、绑定、审批和归档由用户操作。实际服务安装验收与后续 Fig.4 科学结论均未在此报告中宣称完成。
