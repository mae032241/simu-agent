# P4a 浏览凭据原语抽取独立静态审查

结论：**静态 PASS，可提交此窄节点**。受审为新 `src/scidiscovery/browser_access.py`、旧 `artifact_agent/approval_ui/access.py` 兼容入口及[作者记录](P4A_BROWSER_ACCESS_EXTRACTION_20261017.zh-CN.md)，不是 P4 完整 UI 验收。

独立复核迁移前 Git 原件与新文件完整字节 SHA-256 均为 `6cde4ff126928021e2afa9a460ad610382e3f92e882c623f2fc02861834491ba`。比正文 AST 相同更强：原 token/密钥派生/AAD、实例与 maintenance scope、有效期、boot/restore 失效和 cookie 实现均逐字保留。

旧 shim 显式导出原七个公共定义：BrowserAccess、BrowserAccessDenied、BrowserAccessService、access_cookie、cookie_name、management_cookie、management_token。静态检索未见 `_AAD/_utc/_timestamp` 的跨模块消费者；现有 app 和浏览访问测试的公共导入继续满足。函数使用新 owner 的模块 globals，未复制第二份凭据实现。

新 owner 仅依赖标准库与原有 cryptography；顶层 `scidiscovery/__init__.py` 无 eager imports。新入口因此不经过旧 approval_ui 包；旧入口自身仍会按旧包初始化路径加载 app，不能声称旧栈已整体移除。未改旧消费者或添加新 UI、授权、SQL/归档接线，浏览凭据仍不构成科学资格或执行许可。

只做文件/Git/符号阅读与摘要比较，未导入项目，未运行测试、收集、安装、构建、HTTP 服务或浏览器；现有 scope/expiry/tamper 用例未执行。无新增行为或协议，未要求为逐字迁移再写一套测试。P4 后续真实入口仍须独立验收。
