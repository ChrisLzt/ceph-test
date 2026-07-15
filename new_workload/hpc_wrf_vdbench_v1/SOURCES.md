# 来源与映射说明

## WRF 官方来源

- WRF Users Guide，Namelist Variables：
  <https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/namelist_variables.html>
- WRF Model documentation，Running WRF：
  <https://www2.mmm.ucar.edu/wrf/site/documentation/users_guide/running_wrf.html>
- NSF NCAR/MMM WRF 模型主页：
  <https://www.mmm.ucar.edu/models/wrf>

这些来源支撑：

- `wrfinput` 和 `wrfbdy` 输入/边界语义；
- `wrfrst` restart/checkpoint 文件；
- `wrfout` history/output 文件；
- restart 文件在恢复运行中重新读取；
- history 和 restart 由不同时间参数控制。

本负载将它们映射为 startup、checkpoint、history 三个数据组，以及最后
一次 checkpoint 复热。

## Zipf 执行模型

- Cooper 等，`Benchmarking Cloud Serving Systems with YCSB`，SoCC 2010：
  <https://doi.org/10.1145/1807128.1807152>
- YCSB Zipfian generator：
  <https://github.com/brianfrankcooper/YCSB/blob/master/core/src/main/java/site/ycsb/generator/ZipfianGenerator.java>

本负载采用 alpha=0.99。每个 WRF 数据组包含 80 个等容量 rank；4/8/16 MiB
三个固定大小档分别按真实文件数计算 Zipf 概率，再聚合到 80 个 rank。Zipf
只用于制造细粒度、非零的冷热访问偏斜，不是 WRF trace 或 WRF 官方参数。

## 执行工具

- Oracle Vdbench 下载和说明入口：
  <https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

Vdbench 用于：

- 创建等容量文件池；
- 通过 FWD `skew` 分配 rank 访问比例；
- 使用固定阶段时间、纯读、顺序文件 I/O 和 Direct I/O；
- 保留 skew report 检查目标比例偏差；不使用 `abort_failed_skew=2` 硬中止，因为
  4 MiB、单盘受限的 10 分钟测试无法保证每个 FSD 达到建议的 2000 次操作。

## 保留的 IOR 版本

- IOR/mdtest 官方仓库：<https://github.com/hpc/ior>
- IOR 文档：<https://ior.readthedocs.io/>

`../hpc_wrf_ior_v1` 保留为 MPI/file-per-process 取向的 HPC I/O 版本；本
目录是面向明确冷热分布的 Vdbench 版本。两者使用不同 CephFS anchor，
互不覆盖。

## 保留与舍弃

保留：

- WRF 输入、checkpoint、history 文件角色；
- checkpoint 首次读取、冷却和复热；
- 大文件内部顺序读取；
- 单阶段内部的可控访问偏斜。

舍弃：

- WRF 数值计算；
- NetCDF/HDF5 内部变量；
- MPI rank 和 collective I/O；
- checkpoint/history 正式写出；
- 真实 CONUS 文件大小、时间间隔和访问比例。
