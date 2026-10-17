# main 曲线锚点修复：选择性移植

状态：生产/测试冻结交独审；作者仅 stdlib AST/尾空白检查，未执行测试、项目导入、
安装、模型或 solver。目标起点 dev `326b573`，不是整颗 main merge/cherry-pick。

## 来源与采用范围

只读来源 `/123/main`，本地 main 提交 `15d2985` 的未提交 WIP：

- `plugins/curve_figure_evidence/curve_figure_evidence/figure_line_tracker.py` SHA256：
  `aeb6ca7f701624e15bdb83813b6fe4e9f9d2f81fb3330895f993d70d9f03578f`。
  与[已提交评估](MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md)一致，复制前后均复核。
- 来源测试文件 SHA256：`fd563117e6a7730dd07d31a65f6f56059a09100edc1f459744df636089d3c1be`。
- dev 原 tracker SHA256：`40e09421cef2a6a8b77a07ef7721a9fc98d593c0e0951e2af580bb31a3af1181`。

只采用此单生产文件的相关 WIP（77增/23删），目标字节与上述来源 tracker 相同：

1. `_column_candidates` 把正权重均值的浮点误差夹回实际观测支撑，不修改像素或平滑尖峰。
2. `_identity_supported_columns` 不用整个连通分量的全局 anchor 数提前淘汰另一真实断段。
3. `_continuous_paths` 从每个实际锚点双向生长；guide-only 分量仍只选其最佳接续位置。
   半像素先在原图取整，再作方向变换，避免负方向重新取整偏一列。
4. `_grow_columns` 只在经过当前候选的可达前缀/后缀记录实际锚支持，断段重新开始。
   实际锚路径优于 guide-nearest 干扰；同等实际支持仍保歧义，不借另一互斥分支的锚点。

不采用 UI/SQL/Root/MCP、presentation、提交恢复、安装文档改动；不修改 main 工作树。
不复制 main 整套测试。算法会从更多实际锚点生长，工作量随实际锚数量增加；
本轮小图测试不证明所有大图/密集候选的时间与内存上限，不新增任意记录 cap。

## 精确文件与最小验收

生产：上述 tracker；新测试：`tests/operations/test_figure_anchor_tracking.py`；本记录。
新模块只依赖 Pillow、pytest 与公开 `trace_continuous_line`，不导入旧 service 测试夹具。

六个独立目标：

- `test_disconnected_anchors_survive_tail_frame_without_bridging_gaps`
- `test_every_actual_anchor_recovers_full_stroke_inside_one_frame_component`
- `test_actual_anchor_path_beats_nearer_straight_guide_distractor`
- `test_half_pixel_anchor_keeps_support_on_both_sides_and_mirror`
- `test_branch_must_visit_actual_anchor_and_equal_supported_branches_stay_ambiguous`
- `test_weighted_singleton_center_stays_in_its_observed_pixel_support`

前五项明确核原图/水平镜像；分支项分别核内部实际锚与共同端点的真实歧义。
像素 oracle 来自已知画图坐标或加 frame 前的实际 raster，不以另一算法输出作唯一真值。
保留 gap、不许可歧义插值与原始 support range 都是断言内容。

建议 root 首批只运行此新模块；必要现有行为复核可另选
`test_figure_raster_support.py::test_neighbor_continuity_rejects_isolated_nearest_guide_distractor`、
`::test_mirrored_competing_paths_preserve_identity_and_interpolation_eligibility`，不运行安装矩阵。
本轮新例不覆盖完整 CSV/normalizer/curve-score 消费、真实论文图或科学模型可识别性；
不能据纯像素追踪通过声称科学结论通过。动态结果由 root 运行后追加。

## Root 动态验收

独立静态审查 PASS（见同目录 `MAIN_CURVE_ANCHOR_MIGRATION_REVIEW_20261017.zh-CN.md`）。
所有作者冻结后，root 单独执行：

```
/home/da/miniconda3/bin/python scripts/run_tests.py --config .trial/p_migration_validation_20261017/resources.json --lane source --output .trial/main_curve_20261017 tests/operations/test_figure_anchor_tracking.py
```

结果：6 passed in 0.48s；监督总时长1.054s，RSS峰值68,874,240字节，
returncode=0、cleanup_complete=true、无内存止损。`git diff --check` 通过。
未扩大到旧套件、安装、真实图或浏览器。原始日志位于命令指定输出目录。
