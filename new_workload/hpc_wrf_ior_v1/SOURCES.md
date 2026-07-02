# 来源与映射说明

## 主来源：WRF CONUS-12km benchmark

本 workload 的 HPC 语义来自 WRF weather simulation benchmark：

- NCAR/MMM WRF 模型页面：<https://www.mmm.ucar.edu/models/wrf>
- CONUS-12km WRF 使用案例示例：<https://arxiv.org/abs/2409.07232>
- WRF 是典型 MPI HPC 应用；
- CONUS-12km benchmark 是常用 WRF 性能测试场景；
- WRF 运行过程中涉及输入文件、边界文件、restart/checkpoint 文件和 history/output 文件；
- restart/checkpoint 文件天然具有“写入后短期热、恢复时复热、旧代际冷却”的生命周期。

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
| 输入场 | `input/wrfinput_d01` | prepare 写，run 读 |
| 边界场 | `input/wrfbdy_d01` | prepare 写，run 读 |
| 启动 restart | `restart/wrfrst_initial` | prepare 写，run 读 |
| 旧 checkpoint | `checkpoint/wrfrst_old` | prepare 写，run 恢复读 |
| 旧 history/output | `history/wrfout_old` | prepare 写，可作为冷背景 |
| 当前 checkpoint | `checkpoint/wrfrst_current` | prepare 预创建，run 覆盖写并热读 |
| 当前 history/output | `history/wrfout_current` | prepare 预创建，run 覆盖写并热读 |

## 保留与舍弃

保留：

- MPI 并行 I/O；
- input/restart 启动读；
- checkpoint/history 周期写；
- 新文件短期热；
- 旧 checkpoint 恢复读复热；
- 文件代际冷热变化。

舍弃：

- WRF 数值计算；
- NetCDF/HDF5 变量布局；
- 真实 CONUS-12km 原始文件大小；
- timestep 与物理过程调度；
- 外部冷热真值表。

因此本 workload 应称为“WRF checkpoint/restart 语义的 IOR 冷热识别测试”，不能称为完整 WRF benchmark。
