# 工作台可用性修订记录

2026-09-15。工程实现、隔离可用性与安装包验证完成，独立最终审查进行中；尚未部署本修订。

## 判定与范围

用户反馈属实：旧现场页面将30,114字符排成长页，最新审查节点高18,111px，无法有效阅读。
原工作台的工程PASS保留，但不能据此宣称现场可用性通过。
执行[修订计划R1](../../INSTANCE_WORKBENCH_USABILITY_REPAIR_PLAN.zh-CN.md)及
[独立计划PASS](../../reviews/INSTANCE_WORKBENCH_USABILITY_PLAN_R1_REVIEW_20260915.zh-CN.md)。
冻结计划SHA256：`0052352c68a53aa11a28b56a1ab0e03bc8e5a937f0fb2593edb6451114266048`。

本轮只修改8个既有UI生产文件，未修改Operation、Worker、运行与审批状态、准入、归档或执行适配器。
[本轮源码清单](USABILITY_SOURCE_MANIFEST.json)保存8个生产文件、4个测试文件和2个浏览器探针；
其SHA256为`b151d91f1a377a96fc2c652a143823511f1d5591354bd321ac3d1757b1145ce4`。
原[SOURCE_MANIFEST](SOURCE_MANIFEST.json)及原实现审查保持历史原样。

## 已修复

- 读取、提供者拼接和HTML三层预算先保留本节点成果。最新正式审查pass成为主结论；作为输入的旧blocked归入背景。
  失败Run不借用旧输入的pass。原目标优先沿精确producer输入端口恢复，兼容`research_objective`，不让背景同schema计划抢占。
- 首页以原目标、最近节点、可点击轨迹组织；机械登记归入全部记录。所有活动分支及原分页入口保留。
- 节点页以正式结论和精确计划入口为主；审查意见、缺口与限制计数可直接读取原字段。
  参数按本节点成果/绑定计划与关联历史来源分组。长报告、原字段、日志与历史按需展开，原件入口保留。
- 历史审批默认展示原问题与原决定，保持只读。待审批原表单保留原option ID、nonce、CSRF及身份；已知内置选项只作中文文案翻译，未知自定义文案仍按原文显示。
- 中文导航、状态、时间及按钮；英文科学叙述明确标为原文，不由展示层生成科学翻译或新结论。
  参数保留原精度，科学计数法不内部断行；图件点击展开/打开原图，手机表格内部滚动。

## 浏览器结果

使用授权只读UI捕获的真实Fig4节点、精确引用和原件进行隔离重放。65项原件均核对SHA，
未读取生产数据库、启动科学Run、提交审批决定、执行仿真或归档。临时fixture不作为新的科学证据。
由于仅保存有界来源子集，重放中部分`source_missing`来自未导出的祖先，不能当作生产资料丢失。
最新审查原目标恢复1项且无目标歧义；历史审批原来没有目标或有歧义的记录仍如实保留。
SSE在重放中仅为无变化fixture，不能据此声称生产实时推送经过新部署验收。

| 页面（1280×900） | 旧默认高度 | 新默认高度 |
|---|---:|---:|
| 最新独立审查 | 18,111px | 1,025px（减少94.3%） |
| 实例概览 | — | 1,470px |
| 原执行审批节点 | 4,828px | 974px |
| 原证据审批节点 | 15,694px | 1,034px |
| 失败节点 | 8,735px | 900px |

[真实材料重放记录](USABILITY_REAL_REPLAY.json)，[最新节点截图](usability-current_review-wide.png)，
[实例首页](usability-overview-wide.png)，[历史审批](usability-evidence_approval-wide.png)，
[手机](usability-current_review-390.png)，[参数](usability-current_review-parameters.png)，
[已加载论文图件](usability-evidence_approval-figures.png)。逐张目视检查，390px无横向页面溢出。

原历史已决定请求和隔离pending请求分别检查。
[pending探针](USABILITY_PENDING_BROWSER.json)默认1,433px，1280/768/390宽度通过，
手机依据先于决定，[审批截图](usability-pending-wide.png)与[手机截图](usability-pending-390.png)。
[无JS探针](usability-pending-nojs.log)验证原生details和决定表单，无决定写入。
旧live探针曾将未触发懒加载记为loaded=false，本次展开且等待后图片真实加载；不能把旧标记解读为坏图。
旧failed节点探针计数误用items而非events，不列为产品缺陷；诊断分页通过专门测试。

## 检查与失败记录

所有测试、浏览器和构建串行，由同一512MiB进程树保护器执行；没有全量或多路pytest。

- [最终定向回归](usability-final-regression.log)：88项通过，峰值141.88MiB。
- [权限/HTTP/诊断/推送/原件回归](usability-boundary-tests.log)：34项通过，峰值136.0MiB；与前项有交集，不相加作为独立测试总数。
- 默认45项和可选figure50项Operation、Root与Worker工具合同均与原基线逐字一致：
  [45项](USABILITY_CONTRACTS.json)、[50项](USABILITY_CONTRACTS_OPTIONAL_FIGURE.json)。
- [数值排版浏览器复验](usability-real-replay-numeric.json)：3.97秒、478.77MiB，数值token保持整行，原精度未舍入。
- [冻结源码最终重放](usability-frozen-replay.json)：3.668秒、484.74MiB，布局、原文入口与数值断行检查均通过。
- [隔离4wheel安装](usability-installed.log)：16.145秒、395.12MiB；50合同、provider与静态文件、隔离归档浏览恢复、Root/Worker stdio及两次原UTF8接续通过。
- [中文pending浏览器](usability-pending-localized.json)：2.442秒、444.14MiB；[无JS](usability-pending-nojs.json)：2.756秒、410.66MiB。
- 首次合并pending/无JS浏览器检查触及512MiB保护上限，[记录](usability-pending-browser.json)为memory_budget_exceeded，
  监测峰值523.23MiB，保护器仅终止自身进程树。随后拆成串行独立进程并通过，未提高预算。
- 早期renderer失败日志保留。实际缺陷包括活动分支被截短、额外审批script、执行收集状态遗漏，均修复；
  其余旧布局文案断言按新语义调整，来源、身份、安全及完整入口断言保留。两次补丁/文案核对错误也保留失败，不改写历史为通过。

## 交付边界

需要重新安装并重启approval-ui后，用户浏览器才会看到本轮修订；当前线上仍是原版本。
不声称科学实验完成、历史记录已经补全或归档问题被本轮修复。
最终独立审查完成后补入本记录。安装包已完成隔离验证，未部署线上。
