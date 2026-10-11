# 节点文件职责收口（源码节点）

范围：基于 2283036 的 rootless CLI；旧 MCP/daemon 未改。

- project/global 冻结目标及创建时用户补充；project/nodes 每节点 work、artifacts、conclusion。
- experiments 子节点采用相同目录；中间材料不采集，子成果由控制层规范路径。
- 科学结论中的 Markdown 成果链接由控制层核对，下一角色得到有界直达入口；目录保留按需读取。
- schema、哈希、清单、封装移至私有 host record；角色指引明确这些事务由宿主负责。
- 已成功结束且原科学输出未变的节点可重试封存；未知执行不重放。

独立评审：thin_files_review，gpt-6.1-sol/high，无源码阻断。
串行定向测试：/tmp/rootless-files-all-20261011-01/batch-001/pytest.log，51 passed in 2.54s。
启动器无模型隔离检查：.trial/rootless-hwa-live-20261011-02/preflight，通过（另存外层）。
未将源码通过等同于角色行为通过；真实 HWA 结果待独立记录。

边界：用户补充当前只支持 prepare；历史中间材料读取接口未实现；旧实例不自动迁移。
