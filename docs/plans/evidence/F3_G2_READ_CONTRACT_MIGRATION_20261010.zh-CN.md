# F3 G2：旧Root读取测试迁移

生产基线 `c4cd0a1`；本切片只修改两个测试文件，生产行为不变。独立评审PASS，源码与证据摘要核对一致。

旧7个参数用Root传入已禁止的stage_reference，全部在输入合同处失败。现通过Root有界navigation获取阶段信息，再由活动且获授权的Worker读取精确原件文件；核对原件字节、SHA和生产者原命名空间，消费别名按ArtifactRef映射，不改写历史JSON，不继承回执。Root的full和stage_reference调用继续明确拒绝。

checks-02为7通过、3失败（测试中重复局部import遮蔽ArtifactRef）；删除该冗余import后checks-03三参数通过。合计7个目标参数及3个相关负例分次通过，非单场10项通过。缺日志、异源和控制回执检查保留；AST及diff检查通过，66行新增、10行删除。原失败、命令和冻结哈希在外层 `.trial/hwa_revision_20261010/f3/g2/`。

本节点不证明G3其他分支、T14、安装、全量回归或真实模型资格，也不代表F3整体完成。
