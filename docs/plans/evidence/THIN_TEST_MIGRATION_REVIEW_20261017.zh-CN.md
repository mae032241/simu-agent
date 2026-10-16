# 测试迁移独立静态复核

日期：2026-10-17。对照：`dev`，HEAD `a1d37aa38e34af1a420fc41b81fe58a5f28f9e37` 与本轮最终工作树迁移差异。

结论：**静态迁移评审 PASS，无剩余阻断项。** 这仅表示本轮分组、消费者迁移和精简方案经静态审查可提交，不表示功能测试、安装、发布构建、资源隔离或生产资格已通过。完整科研结论不在本次评审范围。

本评审者没有运行 pytest、collect-only、测试模块 import、构建、pip、venv、真实模型、SSH 或求解器。只做 Git 差异、文本检索和指定代码段阅读；执行者报告的 AST/内存语法与空白检查不是本评审者重新执行的动态证据。没有读取 `.trial` 或隐藏评分。

## 本次提交范围与明确排除项

本次迁移提交可包括：

- 根收集与运行入口：`tests/conftest.py`、`scripts/run_tests.py`、`tests/README.md`、`.github/workflows/ci.yml`。
- 安装原语与独立包装组：`scripts/installed_candidates.py`、`tests/installation/conftest.py`、`test_packaging.py`、仅显式发现的 `check_source_release.py`。
- 旧安装消费者迁回源码：`tests/operations/conftest.py`；artifact capture、ledger、M7、minimum support、progression acceptance、TCAD knowledge closure 的已跟踪修改；三个 source 文件重命名与两个重复 installed 文件删除，具体账见安装迁移记录。
- 已跟踪薄层精简：`tests/research_loop/test_local_managed.py`、`test_registered_experiments.py`、`test_composed_execution_results.py`。
- 本次复用评审、安装迁移、薄层精简和本文等评审/迁移记录。

**以下继续留在工作树，不能随测试迁移提交混入：**

- 两个未跟踪新测试：`tests/research_loop/test_execution_configuration.py`、`tests/operations/test_tcad_full_transport_records.py`。它们的精简已静态阅读，但依赖尚未提交的对应 P1/TCAD 容量生产修改，分别跟随所属生产节点收口。
- `tests/research_loop/execution_fixtures.py`、`composed_execution_fixture.py` 中既有未提交 P1 能力/schema 支持修改；不因本次源测试迁移而提前纳入。
- `src/scidiscovery/research_loop/` 的 P1 生产差异，以及 `plugin_runtime/collection.py`、TCAD adapter/transport/runner/packager/log 等未提交容量生产差异和其计划文档。这些生产修改不因本次测试静态 PASS 获得批准或动态资格。

## 复核到的真实边界

| 边界 | 静态结果与证据 |
| --- | --- |
| 功能/安装收集隔离 | `tests/conftest.py:62` 在测试模块收集前拒绝显式混合目标；`:102` 在目录递归前隔离安装子树，installed 只放行该目录及祖先；`:112` 对功能 item 的安装 fixture 依赖报错，不再自动升级 lane。当前实际 fixture 名 `installed_environment` 已在拒绝集合中 |
| 运行器默认目标 | `scripts/run_tests.py:317` 起安装默认只选 `tests/installation`，功能明确拒绝安装目标，per-file 跳过安装目录；安装禁止 per-file。core/tcad 是显式 cohort 选择，不做参数化矩阵 |
| 安装环境原语 | 新 `create_environment` 调共享构建闭包一次，不经过旧 LazyEnvironments 池；core 一环境一次安装；tcad 同一环境一次 pip 显式安装 core+TCAD wheel，由 wheelhouse 解析 curve。旧 live 池接口及旧解析路径仍兼容，pytest 安装组不消费它 |
| 包装检查边界 | `tests/installation/test_packaging.py:13` 仅真实包导入位置、公共 console 的 help、entry point 名值/唯一性/可加载、必需资源和依赖声明/解析。没有科学实验、H/W/A、daemon 业务、评分或恢复矩阵，没有 source/installed catalog 双算相等充当业务资格 |
| 发布源检查 | `check_source_release.py` 不匹配默认 test 文件名，只有显式文件目标才选；保留真实发布产物/manifest/消费者文件及 PDF 原件摘要，摘要分块计算。删除旧发布测试内部的多轮 pytest 收集、功能和 installed 重跑；没有为了发布换目录再跑一套功能 |
| 功能零环境创建 | 旧 operations 安装 fixtures 已移除。最终静态搜索中安装 fixture 只在独立组使用；`test_unified_mcp.py` 同名局部变量是 shell probe 返回值，`test_root_host_live.py` 对 create_environments 的使用被定向 monkeypatch。服务缺依赖反例使用真正 Python `-I -S`，仍进入真实 install.sh 预检与事务哨兵，不创建 venv |
| source metadata 的证据强度 | `source_catalog` 只选源路径与 EntryPoint 并清真实 catalog cache；`entry.load`、compiler、schema、runtime、准入与 Worker 提交路径保留。stdio/daemon 的子进程只注入相同 source discovery stand-in，不直接制造生产“成功”状态；它们提供功能证据，明确不给 wheel 资格 |
| 重命名消费者 | 当前 scripts、src、deploy、CI、测试及当前架构/安装/发布文档的定向检索未见仍执行旧三个 installed 文件路径的消费者；历史 evidence 保留旧路径。未据此声称逐篇审完所有历史文档 |
| 旧入口独特保护 | reader 越界/冒名/原件身份、derived projection 脱敏和失败 IO 计费、draft/sealed 区别、broken component 和 Unicode resource 各自错误码均保留。RootHost 独特等待/resume/close 由既有 source owning 用例承接，scheduler guides 由既有内容/幂等/冲突测试承接；dormant daemon/UI/重启合入 source progression 检查 |
| 薄层精简 | local 快照检查现含空输入目录和有内容的旧 artifacts 文件，并断言 accepted 清单排除 artifacts；缺 result 场景合入空输出目录且保留 completed 原件；四条无效旧常量补丁不再单独 dispatch。registered CLI 只跑公共 local 生命周期，cov 的独特 receipt/parent/篡改 owning 检查仍在；opaque observer/private 去除全乘积，身份/无 collect/重放负控保留 |
| 成本标识 | 本轮受改薄层 CLI/实际进程场景标为 process；真实越历史容量输入标为 stress，不以“没有模型”冒称纯源码低成本。没有把全仓旧测试全部改标记，也没有声称本轮消除了全部高成本 source 用例 |
| CI 与日志 | 功能 CI 不再夹带 installed lane；matrix 限单并发，证据输出/上传改工作区持久路径。runner 的 output 帮助与 README 要求持久目录，但没有代码层禁止 `/tmp`，不能声称已强制该约束 |

## 评审中已修正的具体问题

1. 安装 fixture 的实际名称与根拒绝集合不一致：已加入 `installed_environment`，保留显式功能依赖报错。
2. 包装烟用 set 吞掉重复 entry point：已改保留重复项的名称列表比较；core console 每个名字恰好一条，TCAD console 使用完整唯一名单。
3. 迁回 source 的第三方用例直接 import tomllib：已加 Python 3.10 的 tomli fallback，复用 pyproject 的条件依赖。
4. 生命周期 source 用例仍检查宿主安装元数据名单：已删除两条与业务无关的包装断言及 metadata import，保留真实子进程能力与控制服务模块未加载断言。真实组名检查只在安装组。
5. tcad 包装路径最初仍沿用两步 pip：新独立组现为一次解析安装；旧 live 兼容路径没有被强行迁移。

## 另行阅读的待提交测试

P1 新测试保留一个真正 native 宿主接线链；W 通过生产 capabilities/describe/run/query 工作，H/A 固定 JSON 只提供机械路由，不证明科学结论。宿主禁止字段使用固定公开契约名单，未再遍历生产常量给自己定义测试域；包变化直接身份校验与代表变化贯穿 query/reconcile/run 的不同入口均在。没有恢复 installed 整套重跑分支。

TCAD 新测试将输入收窄到刚越历史阈值，大日志用分块摘要和末尾验证；路径/唯一性等负控使用小数据。完整 attestation 保留末项字节篡改使 verdict 转为 fail 的负控，失败 rationale 全文和显式 quota/timeout 也保留。SSH/transport/runner 是本地协议 stand-in，不能称真实 SSH、远端解释器、许可证或 solver 已通过。

这两组静态判断不改变前述提交排除项，也不替代对应生产节点的独立语义审查。

## 未验证与后续顺序

没有测试执行、安装或发布构建结果，没有资源峰值或耗时测量；无法从本轮静态成本缺口推出此前 OOM 根因，也不声称安装拆分修复了 OOM。采样运行器没有内核聚合 memory/swap/pids 硬隔离，该缺口仍以事故记录为准。

其余可选 wheel 组合、Python 平台运行、全部源功能、真实异步进程/授权/归档迁移与真实平台/TCAD 资格均未获本次动态证据。本次没有逐行复核全仓所有测试，也不把既有 source fixture 当作尚未实施 P2/P3/P4 的资格。

建议先精确提交上述迁移范围，保留 pending 生产及新测试；再分别收口 P1/TCAD 生产节点。资源域和执行条件落实后，只选择与实际变更/故障对应的最小功能检查；包装变化才显式选择一个独立包装任务，不因提交仪式重建环境或重跑整组功能。
