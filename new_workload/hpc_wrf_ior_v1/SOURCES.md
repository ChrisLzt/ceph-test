# 来源与映射说明

## 主来源：WRF CONUS-12km benchmark

本 workload 的 HPC 语义来自 WRF weather simulation benchmark：

- NCAR/MMM WRF 模型页面：<https://www.mmm.ucar.edu/models/wrf>
- CONUS-12km WRF 使用案例示例：<https://arxiv.org/abs/2409.07232>
- WRF 是典型 MPI HPC 应用；
- CONUS-12km benchmark 是常用 WRF 性能测试场景；
- WRF 运行过程中涉及输入文件、边界文件、restart/checkpoint 文件和 history/output 文件；
- restart/checkpoint 文件可以在恢复时重新读取，形成再次访问同一状态文件的生命周期。

v1 只保留这些存储访问语义，不运行 WRF 模型本身。

## 执行工具：IOR

- 官方仓库：<https://github.com/hpc/ior>
- 官方文档：<https://ior.readthedocs.io/>

IOR 官方仓库定位为 IOR/mdtest parallel I/O benchmark。这里使用 IOR 的：

- MPI 并行启动；
- POSIX backend；
- file-per-process；
- read/write 分离；
- block size / transfer size 控制数据量；
- 多次 IOR 调用表达不同 HPC I/O 阶段。

## WRF 语义到 IOR 的映射

| WRF/HPC 语义 | IOR 文件路径 | IOR 操作 |
|---|---|---|
| 输入场和边界场 | `startup/wrf_state` | prepare 写，run 启动读 |
| checkpoint/restart | `checkpoint/wrfrst_current` | prepare 写，run 首次读和复热读 |
| history/output | `history/wrfout_current` | prepare 写，run 分析读 |

## 保留与舍弃

保留：

- MPI 并行 I/O；
- input/boundary 启动读；
- checkpoint/restart 首次读和冷却后复热；
- history/output 分析读；
- 文件间的阶段性冷热变化。

舍弃：

- WRF 数值计算；
- NetCDF/HDF5 变量布局；
- 真实 CONUS-12km 原始文件大小；
- timestep 与物理过程调度；
- checkpoint/history 正式写出；
- 外部冷热真值表。

因此本 workload 应称为“WRF 文件生命周期启发的 IOR 只读冷热识别测试”，不能称为完整 WRF benchmark。三个 36 GiB 等容量池、四阶段和每阶段 150 秒均为单节点实验参数，不是 WRF 官方或 trace 给出的比例。
