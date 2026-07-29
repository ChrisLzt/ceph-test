# WRF 生命周期 Vdbench 冷热负载

## 来源与设计逻辑

来源是 NSF NCAR/MMM WRF 的输入/边界文件、restart/checkpoint 与
history/output 文件生命周期。Vdbench 版本保留三类数据及 checkpoint 复热，
并用聚合到物理 bin 的分段 Zipf(0.99) 提供阶段内冷热。MPI、collective I/O 和
file-per-process 语义由保留的
[`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md) 表达。

## 数据构造

| 数据组 | 单元 | 容量 | 参考 rank | 物理 bin |
|---|---:|---:|---:|---:|
| `startup` | 800 | 37.5 GiB | 100 | 40 |
| `checkpoint` | 800 | 37.5 GiB | 100 | 40 |
| `history` | 800 | 37.5 GiB | 100 | 40 |

每个固定大小档先按 100 个参考 rank 计算 Zipf(0.99)。前 20 个物理 bin 各含
1 个参考 rank，即 8 单元、384 MiB；后 20 个各合并 4 个参考 rank，即 32 单元、
1.5 GiB。bin 权重是参考 rank 权重之和。

## 正式阶段

| 阶段 | 活动数据 | 模式 | 时长 |
|---|---|---|---:|
| `startup_read` | startup 全部 rank | 顺序读 | 150 s |
| `checkpoint_read` | checkpoint 全部 rank | 顺序读 | 150 s |
| `history_read` | history 全部 rank | 顺序读 | 150 s |
| `checkpoint_reheat` | 同一 checkpoint 全部 rank | 顺序读 | 150 s |

每阶段只活动一个高层数据组，但组内 40 个物理 bin 均有非零理论访问概率；边界
直接切换。全程为 4 MiB Direct I/O、`fwdrate=max`，合计仍为 600 秒。
第二和第四阶段复用同一套 `checkpoint_read*` FWD；单节点每阶段 120 FWD。

## 适用范围

适合评估 WRF 类文件生命周期和 checkpoint 复热识别；不运行数值模式，不复现
NetCDF/HDF5 变量布局，正式阶段也不模拟 checkpoint/history 写出。

数据默认位于 `/mnt/cephfs/hpc_wrf_vdbench_v1`。
