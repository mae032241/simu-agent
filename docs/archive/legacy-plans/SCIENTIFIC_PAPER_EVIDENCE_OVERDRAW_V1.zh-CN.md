# 科学论文曲线多色覆盖提取 v1

日期：2026-08-15

## 问题与边界

Fig.4 的红、黑实测曲线在峰值附近存在绘制覆盖。旧实现还把 seed guide
当作硬过滤器，使黑色曲线在陡峭、锯齿区即使存在真实像素也会丢失；旧
support renderer 又把不合格区画成整幅竖向色带，造成“存在大量遮罩”的
错误观感。

本版不从颜色自动推断物理身份。工具只报告几何上可能的多色覆盖；必须在
对照原图、图例和两端汇合后，由提取规格显式声明 visible/covered series
及半开像素区间。隐藏曲线的共享行复用可见曲线坐标并标为
`shared_occlusion`，不是插值。

## 已实现

- bounded global line tracker；guide 仅限制新路径起点，连续路径可在步长
  约束内偏离 guide。
- gap 后重捕获的垂直位移独立封顶，避免跳到远处同色文字或噪声。
- 默认排除 plot 外缘四像素，避免把横轴当作黑色曲线。
- `shared_support` 显式契约、候选检测、共享坐标生成和严格 validator v3。
- CSV 增加 `support_kind`、`coordinate_ownership`、`shared_group` 和
  `support_source_series`。
- support PNG 必须显式选择 series；direct/shared 分别用实线/虚线，局部
  mask 只画局部符号，不再生成全高背景带。
- renderer 写入 bundle 内部时自动更新 PNG 的大小与 SHA-256 provenance。

## 验证结果

- 自动化：Fig.7 同色点/虚线、Fig.10 四条多色近邻曲线、Fig.13 六条
  log10 近邻曲线、显式覆盖和未确认覆盖 fail-closed 均通过。
- 聚焦测试：`34 passed`。
- 真实 Fig.4 原始嵌入图（1000×815，SHA-256 前缀 `2c8166`）：
  - 未声明共享时，工具只报告黑线覆盖候选，不自动补点；
  - 显式确认八个红覆黑区间后，黑线为 657 个 direct rows + 116 个
    shared rows，共 773 rows，visible fraction 0.954320988，最大剩余 raster
    gap 6 px；红线 806 个 direct rows；
  - validator v3 通过，`cross_series_shared_pixel_count=116`；
  - fidelity overlay 目视核验中，提取轨迹与原图红/黑像素一致，未再跟踪
    顶部坐标轴；完整 bundle fingerprint 为
    `3bd2e1302bf95e21b01d06431ecd0ca3c0318c0059fa104ab790a413673e6294`。

该真实 Fig.4 测试包位于临时目录，仅用于实现核验，不替代控制面正式注册
的科学证据。正式 evidence revision 仍需由 scheduler 重新派发 extractor、
完成独立 audit 后再进入最终审批。
