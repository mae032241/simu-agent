# 审批提交 403 修复（2026-09-15）

用户现场：Fig.4 执行审批链接 GET 正常返回 200，点击“授权执行/确认并记录决定”后返回 403，控制层仍记录 pending。真实审批未由 Agent 代为提交。

## 原因与最小修改

隔离合成审批使用当前源码和真实 Chromium 复现：表单 POST 的 Origin 为字符串 null，服务端在同源检查分支返回 403，决定未保存。HTTP 虽已发送 Referrer-Policy: same-origin，但审批 HTML 的 meta referrer=no-referrer 覆盖了文档策略。此前浏览器验收只查看 pending 表单，没有提交，因此漏掉问题。

移除 render.py、management_render.py、workbench_render.py 中冲突的文档级 meta，以及 agent_settings.py 中重复的文档级 meta，统一由现有 HTTP 响应策略管理。原有 Origin、CSRF、token、nonce、审批身份和实例维护检查未变；外部引用链接/独立资源的 no-referrer、noreferrer 仍保留。

精确修改基线为 /tmp/scid-approval-origin-before-1oao2qaf 中四个文件的副本；这些文件相对 HEAD 还包含此前已完成改动，不能把整份 HEAD 差异归入本次。

## 验证结果

- 修复前真实浏览器：Origin:null，POST 403，审批 pending。
- 修复后同一浏览器动作：Origin 等于当前本地服务源，POST 303，审批 decided。
- 持久复现脚本 browser_probe.py，仅建立临时目录、随机端口和 synthetic_execution 合成审批，显式禁止端口 8765。启用与禁用页面 JavaScript 两种情况下均通过真实表单提交。
- 两种浏览器模式下均先验证四项负例：缺 Origin、Origin:null、外部 Origin、错误 CSRF，均返回 403，决定仍为 pending；之后合法点击保存为 decided。
- 四个相关测试文件共 37 项通过，5.63 s，峰值 RSS 128748 KiB；均为串行低资源测试。真实浏览器单次约 2 s，所测最大进程 RSS 223468 KiB。未跑全量测试。
- git diff --check 通过。
- 独立审查者 execution_settings_impl_review 比对精确四文件基线，结论 PASS：改动最小，全部页面仍由同一 HTTP 策略管理，没有安全放宽或新负面影响。审查者未运行测试或操作审批。

复现命令（浏览器与驱动已经安装在临时工具目录时）：

```bash
SCID_BROWSER_PYTHONPATH=/tmp/scid-workbench-browser \
PLAYWRIGHT_BROWSERS_PATH=/tmp/scid-workbench-browsers \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python docs/plans/evidence/approval-form-origin/browser_probe.py
```

增加 --no-js 验证禁用页面脚本的原生表单。

部署状态：源码已修，尚未重装审批 UI。原 Fig.4 执行审批尚未保存，仍需安装重启后由用户在真实审批页作决定；先前 TCAD 锚点修复已完成实际打包验收。
