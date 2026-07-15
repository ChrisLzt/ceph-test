# WRF 生命周期 Vdbench 冷热负载

## 来源与设计逻辑

来源是 NSF NCAR/MMM WRF 的输入/边界文件、restart/checkpoint 与
history/output 文件生命周期。Vdbench 版本保留三类数据及 checkpoint 复热，
并用文件级 Zipf(0.99) 提供阶段内冷热。MPI、collective I/O 和 file-per-process
语义由保留的 [`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md) 表达。

## 数据构造

| 数据组 | 单元 | 容量 | rank | 每 rank 容量 |
|---|---:|---:|---:|---:|
| `startup` | 800 | 37.5 GiB | 80 | 480 MiB |
| `checkpoint` | 800 | 37.5 GiB | 80 | 480 MiB |
| `history` | 800 | 37.5 GiB | 80 | 480 MiB |

每 rank 为 10 个容量单元，包含 40 个 4 MiB、20 个 8 MiB 和 10 个 16 MiB
文件。每个固定大小档独立计算 Zipf(0.99)，再聚合到 80 个等容量 rank；不再
使用会抹平长尾的整数百分比或“至少 1%”规则。

## 正式阶段

| 阶段 | 活动数据 | 模式 | 时长 |
|---|---|---|---:|
| `startup_read` | startup 全部 rank | 顺序读 | 150 s |
| `checkpoint_read` | checkpoint 全部 rank | 顺序读 | 150 s |
| `history_read` | history 全部 rank | 顺序读 | 150 s |
| `checkpoint_reheat` | 同一 checkpoint 全部 rank | 顺序读 | 150 s |

每阶段只活动一个高层数据组，但组内 80 个 rank 均有非零理论访问概率；边界
直接切换。全程为 4 MiB Direct I/O、`fwdrate=max`，合计仍为 600 秒。

## 适用范围

适合评估 WRF 类文件生命周期和 checkpoint 复热识别；不运行数值模式，不复现
NetCDF/HDF5 变量布局，正式阶段也不模拟 checkpoint/history 写出。

数据默认位于 `/mnt/cephfs/hpc_wrf_vdbench_v1`。
