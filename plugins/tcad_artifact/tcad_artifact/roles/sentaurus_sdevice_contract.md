# 冻结的 SDevice 最小代码合同

本资源随 TCAD 插件注册并进入操作摘要，不依赖宿主机技能目录。SDevice
直接入口是 `.cmd`，其最小结构如下；只按任务输入启用其中实际需要的部分：

```text
File {
  Grid="device.tdr"
  Parameter="device.par"
  Plot="results/device.tdrdat"
  Current="results/device.plt"
  Output="results/device.log"
}
Electrode { ... }
Physics { ... }
Plot { ... }
Math { ... }
Solve {
  Poisson
  Coupled { Poisson Electron Hole }
  Quasistationary(...) { Coupled { Poisson Electron Hole } }
}
```

其中 `device.tdr` 只是结构示意名，不是可凭空创建的输入。文本占位文件永远
不是有效 TDR；任务没有提供或声明所需网格时必须失败关闭，不得搜索、复制
或改写历史交付物来补齐它。

不得从 SProcess 或其他求解器推断 SDevice 语法。每个电极名必须对应输入
网格中的接触；区域、材料、组分、掺杂场和单位必须与输入网格一致；平衡解
必须先于载流子耦合解；扫描方向、初态、目标和步进控制必须显式；未声明
预处理单元时不得保留 Workbench 占位符。原始输出只包含后续所需的日志、
端口电流电压和场状态。隐藏拟合比例、人工电流下限、未声明寿命、拼接分支
和从未收敛点得出结论均不允许。

`File` 块引用的每个 `Grid`、`Parameter` 或其他原生输入必须闭合：要么该
相对路径是 `deck/files/` 中的真实工程文件，要么在 `input_slots` 中用唯一
语义名、相同目标相对路径和准确媒体类型显式声明。不得为了让预检通过而
删除真实运行所需的输入，也不得让直接入口引用未打包且未声明的文件。

R-2020.09 记录的 `sdevice -P <commandfile>` 参数提取和
`sdevice -i <commandfile>` 初始解只能作为有界开发诊断，不能证明完整求解
或输出合格。关键词和选项嵌套若未由任务内合同确定，应报告缺口，不得搜索
历史工程猜测语法。

依据：*Sentaurus Device User Guide* R-2020.09，第 1477—1478 页；冻结手册
SHA-256 为 `dae2c94b29c92705d3b8d6124c2f0ab595541ed48e4b220a425f72fac42794ce`。
