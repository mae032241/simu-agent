# TCAD Skill v2 重构与 A/B 评测

## 目标

解决旧 Skill 令 TCAD author/reviewer 先做大范围合规阅读、重复全文检索、
再写 solver 代码的问题。新 Skill 必须提高代码首稿速度，同时保持物理边界、
直接 solver 调用、最早失败层和 solver-only 输出边界。

## 根因

1. `SKILL.md` 同时承载 author、revision、review、diagnosis 和控制面协议，
   所有角色都被引导读取同一组长清单。
2. 常用 R-2020.09 构件没有可直接采用的短 recipe，agent 用同义词反复全文
   搜索 10 MiB PDF；literal miss 被误读为能力缺失。
3. author 的成功标准混入后处理和控制字段，导致 deck 膨胀并稀释 TCAD
   代码推理。
4. reviewer 缺少独立、窄化的 code/physics fidelity 清单，容易越界要求
   scorer、manifest 或 runtime 合同。
5. 旧测试主要检查提示词短语存在，不衡量代码质量、局部修订和完成速度。

## 实施

- 将核心 Skill 缩减为任务路由、write-first 循环、手册检索策略和硬边界。
- author、review、diagnosis 分别加载 release recipe、review checklist、
  earliest-layer diagnostics，不再默认通读全部引用。
- 将常用 R-2020.09 SProcess 构件固化为 source-backed recipe；未知构件才
  查询手册。
- 新增 release/topic 页码索引；literal PDF 提取使用按手册 SHA 的 `/tmp`
  原子缓存。
- deck 只生成 solver 源和原生 TDR/PLX/PLT/log；曲线比较、指标、阈值和
  科学判定继续由确定性 scorer/diagnosis 承担。
- 增加冻结的 authoring 与 diagnosis 前向评测，以及独立确定性评分器。

## 冻结的 A/B 合同

两臂使用相同原始任务；A 不读取 Skill，B 使用重构后的 Skill。每臂由一个
新鲜 agent 完成：

1. authoring：两 case、共享实现、自定义守恒状态、显式双 Dirichlet 边界、
   原生 PLX 输出；
2. diagnosis：从完整 bounded log 的第一个 parser 错误出发，只改一行。

评测不调用 solver，不接触生产控制面。确定性评分检查直接入口、自定义状态、
守恒方程、case 独立性、单位、边界、原生输出、无内嵌后处理、最早失败层和
exact minimal patch。结果目录只位于 `/tmp/tcad-skill-ab-20260813/{a,b}`。

冻结输入与评分器 SHA-256：

- authoring task: `aabca0bfa19888c8a52c06ce4ae7a6f67f20adaa2779edb97c1e5b998db9d5b1`
- diagnosis task: `214d302ebd1412f9f98759bc217162bb3f093ca0a4603dddadbc5f6e31ce08b2`
- broken deck: `90ddfc45bf8ccf29554b92492e9efd138241c7c533dd32f89eac264256e94ac1`
- solver log: `58d57a306481de6e8ffcb1635dc74cf570d1a4c26f12a47126bbd36f6b21de77`
- final evaluator: `40b767144a26c189dec1ce3ccf06a57cd6452be2dfb9d9905e9d007a2f946f8b`

## 通过门槛

- Skill 结构与聚焦回归全部通过；
- B 臂 diagnosis 必须得到 exact one-line correction；
- B 臂 authoring 不得嵌入 scorer/调度职责，且质量分不得低于 A；
- 若 B 只因更长说明而变慢，不扩大 Skill；优先删减说明或把脆弱语法移到
  recipe/script；
- 本次 n=1/arm 属于前向烟测，只支持“发现明显回归/方向性收益”，不支持
  统计显著性结论。

## A/B 结果

### SProcess authoring + diagnosis

最终评分器对首轮两臂重算：

| Arm | Skill | 分数 | 从共同任务修订到首稿 | 失败项 |
| --- | --- | ---: | ---: | --- |
| A | 不读取 Skill | 32/35 | 98 s | 自定义 solution 使用 `ifpresent=<same-state>`；初值写成未建立的 region-field shortcut |
| B1 | Skill v2 首版 | 33/35 | 88 s | 把 simulator-global `solution ... add` 放入两次调用的 case procedure |

两臂的 diagnosis 均得到 exact one-line `MaxTimestep` → `maxstep` 修订。
B1 相比 A 快约 10 s、总分高 1 分，但两者都未通过完整 authoring 门槛，不能称为
成功。

依据 R-2020.09 `solution` command reference（PDF 1285–1287），recipe 随后补充：
共享 custom solution 在 case procedure 外只创建一次，所有 case 必须使用
unconditional `solve`；数据场在每个结构中重新初始化。用同一题做的开发复测 B2
为 35/35。该复测参与迭代，不是独立泛化证据。

首版评分器曾把 procedure 名、浮点字面量和 `${case}` 写法写死；在比较两臂前已
修正为语义等价匹配，并加入 global-solution lifecycle 检查。这里明确记录该协议
偏差，避免把测试工具缺陷隐藏为模型收益。

### 未见过的 SDevice authoring + review 留出集

留出输入与评分器在两臂启动前冻结，之后没有修改：

- authoring: `22baecccebd9571a8d9bb3d91e4100ca46c3dbade41a4df71b7e4119b094929e`
- review: `c4e2d58f6eb8a8d1a4e1ff247f01d111008509b6625e2451693722694c2e573e`
- reviewed source: `584fea98643502aa3691de01d0de56e6aac0ea2bd595dbedb7dd7c62aec4a67c`
- evaluator: `e1d54b47974f36c5734af597a9146df44f1ddc16389f6db5fe80d0da8ea77389`

| Arm | Skill | 分数 | 从冻结输入到首稿 | 结论 |
| --- | --- | ---: | ---: | --- |
| holdout A | 不读取 Skill | 29/29 | 94 s | 正确最小 SDevice deck；发现 contact typo |
| holdout B | Skill v2 | 29/29 | 100 s | 同等正确；finding 更局部；无额外要求 |

新 Skill 在留出集上没有质量退化；时间差约 6 s（7%），在单样本 agent 波动内，
不能认为更快或更慢。方向性收益目前仅由 SProcess 首轮支持，且 n=1/arm。

### 回归

- Skill `quick_validate.py`: pass；
- 聚焦 Skill/role/materializer/debug: 83 passed；
- 全部 `tests/artifact_agent`: 564 passed，4 个既有 UTC deprecation warnings；
- `git diff --check`: pass。

### 遗留限制

1. A/B 是无真实 solver 的静态前向测试；无法证明生成 deck 在 R-2020.09 初始化、
   收敛和输出层可运行。
2. SDevice 尚没有与 SProcess 同等详细的 release recipe；当前留出题由简洁 guide
   足够覆盖，复杂模型仍需精确手册查询。
3. 样本数不足以建立统计显著的速度收益。后续真实任务应记录 materialize、首写、
   preflight terminal 和 finalize 四个控制面时间戳，而不是依赖 agent 自报。
